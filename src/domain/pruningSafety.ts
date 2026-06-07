import { calculateConcentration } from "./reasoningLab";
import {
  getResidualMassChoiceGroups,
  shouldBlockHardPrune,
} from "./residualMass";
import type {
  KnowledgeEdge,
  KnowledgeNode,
  PruningAction,
  PruningActionType,
  WorkspaceDocument,
} from "./schema";

export const pruningActionGroups: {
  label: string;
  actions: PruningActionType[];
}[] = [
  { label: "削る", actions: ["hard_prune", "soft_downweight"] },
  { label: "残す", actions: ["keep_top_k"] },
  {
    label: "固定する",
    actions: [
      "hard_lock",
      "soft_lock",
      "freeze_ratio",
      "freeze_concentration_band",
    ],
  },
];

export function isPruningActionType(actionType: PruningActionType) {
  return actionType === "hard_prune" || actionType === "soft_downweight";
}

export function isLockActionType(actionType: PruningActionType) {
  return [
    "hard_lock",
    "soft_lock",
    "freeze_ratio",
    "freeze_concentration_band",
  ].includes(actionType);
}

export function getPruningLockWarnings(
  doc: WorkspaceDocument,
  action: PruningAction,
) {
  const warnings: string[] = [];
  const residualGroups = getResidualMassChoiceGroups(doc.nodes);
  const residualByGroupId = new Map(
    residualGroups.map((group) => [group.id, group]),
  );
  const targetNodes = action.target_ids
    .map((id) => doc.nodes.find((node) => node.id === id))
    .filter((node): node is KnowledgeNode => Boolean(node));

  if (action.action_type === "hard_prune") {
    for (const node of targetNodes) {
      const residualGroup = node.choice_group_id
        ? residualByGroupId.get(node.choice_group_id)
        : undefined;
      if (residualGroup && residualGroup.summary.residual_probability > 0) {
        warnings.push(
          `${node.title}: 未配分確率が残っています。これは未想起候補・例外・観測ノイズ・未知を含む可能性があります。hard pruneではなくkeep top-k/downweightを検討してください。`,
        );
      }
      if (residualGroup && shouldBlockHardPrune(residualGroup.summary)) {
        warnings.push(
          `${node.title}: 未配分確率 ${Math.round(
            residualGroup.summary.residual_probability * 1000,
          ) / 10}% のため、このchoice groupでのhard pruneは危険です。`,
        );
      }

      if (
        node.type === "exception" ||
        node.tags.some((tag) => ["exception", "residual_mass"].includes(tag))
      ) {
        warnings.push(
          `${node.title}: 例外候補または未配分由来ノードです。prune対象にする前に例外集/未知バッファとして残すか確認してください。`,
        );
      }

      if (node.pruning_hints.includes("must_keep_top_k")) {
        warnings.push(
          `${node.title}: must_keep_top_k があるため、hard prune ではなく keep top-k / downweight を検討してください。`,
        );
      }

      const ambiguousEdges = getTouchingInfluenceEdges(doc, node.id).filter(
        (edge) => edge.sign === "mixed" || edge.sign === "unknown",
      );
      if (ambiguousEdges.length > 0) {
        warnings.push(
          `${node.title}: mixed/unknown influence が残っているため、hard prune 前に追加観測か downweight を検討してください。`,
        );
      }

      if (hasThinWideGroupRisk(doc, node)) {
        warnings.push(
          `${node.title}: top-k mass が低く候補が薄く広いため、1枝だけを hard prune しても判断が安定しない可能性があります。`,
        );
      }
    }
  }

  if (isPruningActionType(action.action_type) || action.action_type === "keep_top_k") {
    for (const node of targetNodes) {
      if (
        node.lock_mode === "hard_lock" ||
        node.lock_mode === "hard" ||
        node.lock_mode === "freeze_ratio" ||
        node.lock_mode === "freeze_concentration_band"
      ) {
        warnings.push(
          `${node.title}: ${node.lock_mode} 中のため、再正規化や枝刈り操作が固定意図と衝突する可能性があります。`,
        );
      }
    }
  }

  if (isLockActionType(action.action_type)) {
    for (const node of targetNodes) {
      const residualGroup = node.choice_group_id
        ? residualByGroupId.get(node.choice_group_id)
        : undefined;
      const unknownRemaining =
        residualGroup?.summary.buckets
          .filter((bucket) => bucket.kind === "unknown_buffer")
          .reduce((sum, bucket) => sum + bucket.probability, 0) ?? 0;
      if (unknownRemaining >= 0.15) {
        warnings.push(
          `${node.title}: unknown_bufferが大きい状態でlock/freezeしようとしています。候補追加または未知として保持する根拠を確認してください。`,
        );
      }
    }
  }

  return Array.from(new Set(warnings));
}

export function describeActionEffect(actionType: PruningActionType) {
  if (actionType === "hard_prune") return "削られた";
  if (actionType === "soft_downweight") return "弱まった";
  if (actionType === "keep_top_k") return "保持された";
  return "固定された";
}

function getTouchingInfluenceEdges(doc: WorkspaceDocument, nodeId: string) {
  return doc.edges.filter(
    (edge): edge is KnowledgeEdge =>
      (edge.source === nodeId || edge.target === nodeId) &&
      (edge.relation_layer === "influence" || edge.type === "influences"),
  );
}

function hasThinWideGroupRisk(doc: WorkspaceDocument, node: KnowledgeNode) {
  if (!node.choice_group_id) return false;
  const groupNodes = doc.nodes.filter(
    (candidate) => candidate.choice_group_id === node.choice_group_id,
  );
  if (groupNodes.length < 4) return false;
  const concentration = calculateConcentration(
    groupNodes.map(
      (candidate) =>
        candidate.posterior_probability ?? candidate.prior_probability ?? 0,
    ),
    2,
  );
  return concentration.top_k_mass < 0.55;
}
