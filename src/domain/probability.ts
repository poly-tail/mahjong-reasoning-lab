import { nowIso } from "./factory";
import type {
  DistributionFamily,
  KnowledgeEdge,
  KnowledgeNode,
  WorkspaceDocument,
} from "./schema";

export type ChoiceGroupSummary = {
  id: string;
  node_ids: string[];
  normalized_total: number;
  distribution_family?: DistributionFamily;
};

export type PropagationDiff = {
  node_id: string;
  title: string;
  before: number | undefined;
  after: number | undefined;
  delta: number;
  reason: string;
};

export type PropagationPreview = {
  before_nodes: Record<string, number | undefined>;
  after_nodes: Record<string, number | undefined>;
  diffs: PropagationDiff[];
  affected_node_ids: string[];
  propagation_order: string[];
  warnings: string[];
  steps: string[];
  updated_workspace: WorkspaceDocument;
};

type MutableNode = KnowledgeNode & {
  _effectiveWeight?: number;
  _localProbability?: number;
  _previousPosterior?: number;
  _reason?: string;
};

const epsilon = 0.000001;

export function isInferenceNode(node: KnowledgeNode): boolean {
  return (
    node.probability_role !== "none" ||
    node.type === "hypothesis" ||
    node.type === "branch" ||
    node.type === "choice_group" ||
    node.type === "weight_modifier" ||
    node.type === "lock_controller" ||
    node.type === "distribution_assumption" ||
    node.type === "probability_aggregate"
  );
}

export function isProbabilisticEdge(edge: KnowledgeEdge): boolean {
  return edge.relation_layer === "probabilistic" || edge.propagate_probability;
}

export function getInferenceSubgraph(doc: WorkspaceDocument) {
  const inferenceNodeIds = new Set(
    doc.nodes.filter(isInferenceNode).map((node) => node.id),
  );
  for (const edge of doc.edges.filter(isProbabilisticEdge)) {
    inferenceNodeIds.add(edge.source);
    inferenceNodeIds.add(edge.target);
  }
  const nodes = doc.nodes.filter((node) => inferenceNodeIds.has(node.id));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = doc.edges.filter(
    (edge) =>
      isProbabilisticEdge(edge) &&
      nodeIds.has(edge.source) &&
      nodeIds.has(edge.target),
  );
  return { nodes, edges };
}

export function getChoiceGroups(nodes: KnowledgeNode[]): ChoiceGroupSummary[] {
  const grouped = new Map<string, KnowledgeNode[]>();
  for (const node of nodes) {
    if (!node.choice_group_id) continue;
    const groupNodes = grouped.get(node.choice_group_id) ?? [];
    groupNodes.push(node);
    grouped.set(node.choice_group_id, groupNodes);
  }

  return Array.from(grouped.entries()).map(([id, groupNodes]) => {
    const total = groupNodes.reduce(
      (sum, node) => sum + (node.posterior_probability ?? 0),
      0,
    );
    const distribution =
      groupNodes.find((node) => node.distribution_family)
        ?.distribution_family ??
      (groupNodes.length > 0 ? "categorical" : undefined);
    return {
      id,
      node_ids: groupNodes.map((node) => node.id),
      normalized_total: round(total),
      distribution_family: distribution,
    };
  });
}

export function getPropagationOrder(
  nodes: KnowledgeNode[],
  edges: KnowledgeEdge[],
) {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const indegree = new Map<string, number>();
  const outgoing = new Map<string, KnowledgeEdge[]>();
  for (const node of nodes) indegree.set(node.id, 0);

  for (const edge of edges) {
    if (
      !edge.propagate_probability ||
      !nodeIds.has(edge.source) ||
      !nodeIds.has(edge.target)
    )
      continue;
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge]);
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
  }

  const queue = Array.from(indegree.entries())
    .filter(([, degree]) => degree === 0)
    .map(([id]) => id);
  const order: string[] = [];

  while (queue.length > 0) {
    const id = queue.shift();
    if (!id) continue;
    order.push(id);
    for (const edge of outgoing.get(id) ?? []) {
      const next = (indegree.get(edge.target) ?? 0) - 1;
      indegree.set(edge.target, next);
      if (next === 0) queue.push(edge.target);
    }
  }

  const hasCycle = order.length !== nodes.length;
  return {
    order: hasCycle ? nodes.map((node) => node.id) : order,
    hasCycle,
  };
}

export function runPropagation(
  doc: WorkspaceDocument,
  changedNodeId?: string,
): PropagationPreview {
  const { nodes: inferenceNodes, edges: inferenceEdges } =
    getInferenceSubgraph(doc);
  const warnings: string[] = [];
  const steps: string[] = [
    "1 observation update",
    "2 gate prune",
    "3 weight modifier apply",
    "4 lock apply",
    "5 sibling normalization",
    "6 downstream propagation",
    "7 hysteresis / keep-top-k adjust",
  ];
  const beforeNodes = Object.fromEntries(
    doc.nodes.map((node) => [node.id, node.posterior_probability]),
  );

  const mutable = new Map<string, MutableNode>(
    doc.nodes.map((node) => [
      node.id,
      {
        ...node,
        _previousPosterior: node.posterior_probability,
        _effectiveWeight: initialWeight(node),
        _reason: isInferenceNode(node)
          ? "initial weight"
          : "semantic node excluded",
      },
    ]),
  );

  applyObservationAndModifiers(mutable, inferenceEdges);
  applyGatePrune(mutable);
  normalizeChoiceGroups(mutable, inferenceNodes, warnings);
  applyDownstreamPropagation(mutable, inferenceEdges, warnings);
  applyHysteresisAndTopK(mutable, inferenceNodes);

  const { order, hasCycle } = getPropagationOrder(
    inferenceNodes,
    inferenceEdges,
  );
  if (hasCycle) {
    warnings.push(
      "Probabilistic edge cycle detected. MVP skipped general cyclic inference and used document order.",
    );
  }

  const afterNodes = Object.fromEntries(
    doc.nodes.map((node) => [
      node.id,
      mutable.get(node.id)?.posterior_probability,
    ]),
  );

  const diffs = doc.nodes
    .map((node) => {
      const before = beforeNodes[node.id];
      const after = afterNodes[node.id];
      const delta = round((after ?? 0) - (before ?? 0));
      return {
        node_id: node.id,
        title: node.title,
        before,
        after,
        delta,
        reason: mutable.get(node.id)?._reason ?? "",
      };
    })
    .filter(
      (diff) =>
        Math.abs(diff.delta) > epsilon || diff.node_id === changedNodeId,
    );

  const affectedIds = new Set<string>();
  if (changedNodeId) affectedIds.add(changedNodeId);
  for (const diff of diffs) affectedIds.add(diff.node_id);
  for (const edge of inferenceEdges) {
    if (affectedIds.has(edge.source)) affectedIds.add(edge.target);
  }

  const updatedNodes = doc.nodes.map((node) => {
    const next = mutable.get(node.id);
    if (!next || !isInferenceNode(next)) return node;
    return {
      ...node,
      posterior_probability: round(next.posterior_probability ?? 0),
      updated_at: nowIso(),
    };
  });

  return {
    before_nodes: beforeNodes,
    after_nodes: afterNodes,
    diffs,
    affected_node_ids: Array.from(affectedIds),
    propagation_order: order,
    warnings,
    steps,
    updated_workspace: {
      ...doc,
      nodes: updatedNodes,
      updated_at: nowIso(),
    },
  };
}

function initialWeight(node: KnowledgeNode): number {
  if (!isInferenceNode(node)) return 0;
  const base =
    node.base_weight ??
    node.prior_probability ??
    node.posterior_probability ??
    node.confidence ??
    0;
  return Math.max(0, base + (node.dynamic_weight ?? 0));
}

function applyObservationAndModifiers(
  nodes: Map<string, MutableNode>,
  edges: KnowledgeEdge[],
) {
  for (const node of nodes.values()) {
    if (!isInferenceNode(node)) continue;
    if (node.type === "observation" && node.dynamic_weight !== undefined) {
      node._effectiveWeight = Math.max(
        0,
        (node.base_weight ?? node.prior_probability ?? 0.5) +
          node.dynamic_weight,
      );
      node._reason = "observation update";
    }
  }

  for (const edge of edges) {
    if (!isProbabilisticEdge(edge)) continue;
    const source = nodes.get(edge.source);
    const target = nodes.get(edge.target);
    if (!source || !target) continue;
    if (source.type !== "weight_modifier" && source.type !== "observation")
      continue;
    const modifier =
      (source.dynamic_weight ?? source.base_weight ?? 0) *
      (edge.conditional_weight ?? 1);
    target._effectiveWeight = Math.max(
      0,
      (target._effectiveWeight ?? initialWeight(target)) + modifier,
    );
    target._reason = `weight modifier from ${source.title}`;
  }
}

function applyGatePrune(nodes: Map<string, MutableNode>) {
  for (const node of nodes.values()) {
    if (!isInferenceNode(node)) continue;
    const hardZero = isHardLock(node) && (node.lock_value ?? 0) <= 0;
    const gatedZero =
      node.propagation_policy === "gated" && (node._effectiveWeight ?? 0) <= 0;
    if (hardZero || gatedZero) {
      node._effectiveWeight = 0;
      node.posterior_probability = 0;
      node._reason = hardZero
        ? "gate prune by hard lock 0"
        : "gate prune by gated weight 0";
    }
  }
}

function normalizeChoiceGroups(
  nodes: Map<string, MutableNode>,
  inferenceNodes: KnowledgeNode[],
  warnings: string[],
) {
  const groupIds = new Set(
    inferenceNodes
      .map((node) => node.choice_group_id)
      .filter((id): id is string => Boolean(id)),
  );

  for (const groupId of groupIds) {
    const members = Array.from(nodes.values()).filter(
      (node) =>
        node.choice_group_id === groupId &&
        isInferenceNode(node) &&
        node.probability_role !== "control",
    );
    if (members.length === 0) continue;

    const hardLocks = members.filter(
      (node) => isHardLock(node) && (node.lock_value ?? 0) > 0,
    );
    const hardTotal = hardLocks.reduce(
      (sum, node) => sum + clampProbability(node.lock_value ?? 1),
      0,
    );
    if (hardTotal > 1 + epsilon) {
      warnings.push(
        `Choice group ${groupId} has hard locks over 1. Values were scaled.`,
      );
    }
    const scaledHardTotal = Math.min(1, hardTotal);
    const hardScale = hardTotal > 1 ? 1 / hardTotal : 1;
    const unlocked = members.filter(
      (node) => !hardLocks.includes(node) && node.posterior_probability !== 0,
    );
    const unlockedTotal = unlocked.reduce(
      (sum, node) => sum + Math.max(0, node._effectiveWeight ?? 0),
      0,
    );
    const remainder = Math.max(0, 1 - scaledHardTotal);

    for (const node of members) {
      if (hardLocks.includes(node)) {
        node._localProbability = clampProbability(
          (node.lock_value ?? 1) * hardScale,
        );
        node.posterior_probability = node._localProbability;
        node._reason = "hard lock";
        continue;
      }
      if (node.posterior_probability === 0 && node._effectiveWeight === 0) {
        node._localProbability = 0;
        continue;
      }
      node._localProbability =
        unlockedTotal > epsilon
          ? ((node._effectiveWeight ?? 0) / unlockedTotal) * remainder
          : 0;
      node.posterior_probability = node._localProbability;
      node._reason = "sibling normalization";
    }

    applySoftLocks(members);
  }

  for (const node of nodes.values()) {
    if (!isInferenceNode(node) || node.choice_group_id) continue;
    if (isHardLock(node)) {
      node.posterior_probability = clampProbability(
        node.lock_value ?? node.posterior_probability ?? 1,
      );
      node._reason = "standalone hard lock";
    } else {
      node.posterior_probability = clampProbability(
        node._effectiveWeight ?? initialWeight(node),
      );
    }
  }
}

function applySoftLocks(members: MutableNode[]) {
  const softLocks = members.filter(
    (node) => isSoftLock(node) && node.lock_value !== undefined,
  );
  if (softLocks.length === 0) return;
  for (const node of softLocks) {
    const minimum = clampProbability(node.lock_value ?? 0);
    if ((node.posterior_probability ?? 0) < minimum) {
      node.posterior_probability = minimum;
      node._reason = "soft lock minimum";
    }
  }
  renormalizeMembers(members);
}

function applyDownstreamPropagation(
  nodes: Map<string, MutableNode>,
  edges: KnowledgeEdge[],
  warnings: string[],
) {
  const inferenceNodes = Array.from(nodes.values()).filter(isInferenceNode);
  const { order } = getPropagationOrder(inferenceNodes, edges);
  const bySource = new Map<string, KnowledgeEdge[]>();
  for (const edge of edges) {
    if (!edge.propagate_probability || !isProbabilisticEdge(edge)) continue;
    bySource.set(edge.source, [...(bySource.get(edge.source) ?? []), edge]);
  }

  const visitedTargets = new Set<string>();
  for (const sourceId of order) {
    const source = nodes.get(sourceId);
    if (!source) continue;
    for (const edge of bySource.get(sourceId) ?? []) {
      const target = nodes.get(edge.target);
      if (!target || !isInferenceNode(target)) continue;
      if (target.choice_group_id) continue;
      const factor = clampProbability(
        (source.posterior_probability ?? 0) * (edge.conditional_weight ?? 1),
      );
      const base =
        target._localProbability ??
        target.posterior_probability ??
        initialWeight(target);
      target.posterior_probability = clampProbability(base * factor);
      target._reason = `downstream from ${source.title}`;
      visitedTargets.add(target.id);
    }
  }

  const affectedGroupIds = new Set(
    Array.from(visitedTargets)
      .map((id) => nodes.get(id)?.choice_group_id)
      .filter((id): id is string => Boolean(id)),
  );
  for (const groupId of affectedGroupIds) {
    const members = Array.from(nodes.values()).filter(
      (node) => node.choice_group_id === groupId,
    );
    const parentTotals = members.reduce(
      (sum, node) => sum + (node.posterior_probability ?? 0),
      0,
    );
    if (parentTotals > 1 + epsilon) {
      warnings.push(
        `Downstream probabilities in ${groupId} exceeded 1 before normalization.`,
      );
      renormalizeMembers(members);
    }
  }
}

function applyHysteresisAndTopK(
  nodes: Map<string, MutableNode>,
  inferenceNodes: KnowledgeNode[],
) {
  for (const node of nodes.values()) {
    if (!isInferenceNode(node)) continue;
    if (isFreezeRatio(node)) {
      const ratio = clampProbability(node.lock_value ?? 1);
      const previous = node._previousPosterior ?? node.prior_probability ?? 0;
      const computed = node.posterior_probability ?? 0;
      node.posterior_probability = round(
        previous * ratio + computed * (1 - ratio),
      );
      node._reason = "freeze ratio";
    }
    if (
      node.hysteresis_band !== undefined &&
      Math.abs(
        (node.posterior_probability ?? 0) - (node.prior_probability ?? 0),
      ) < node.hysteresis_band
    ) {
      node.posterior_probability = node.prior_probability;
      node._reason = "hysteresis band";
    }
  }

  const groupIds = new Set(
    inferenceNodes
      .map((node) => node.choice_group_id)
      .filter((id): id is string => Boolean(id)),
  );
  for (const groupId of groupIds) {
    const members = Array.from(nodes.values()).filter(
      (node) => node.choice_group_id === groupId,
    );
    const topK = Math.max(
      0,
      ...members
        .filter((node) => node.lock_mode === "keep_top_k")
        .map((node) => Math.round(node.lock_value ?? 2)),
    );
    if (topK <= 0 || members.length <= topK) continue;
    const hardLocked = members.filter(isHardLock);
    const keep = new Set(
      members
        .filter((node) => !isHardLock(node))
        .sort(
          (a, b) =>
            (b.posterior_probability ?? 0) - (a.posterior_probability ?? 0),
        )
        .slice(0, Math.max(0, topK - hardLocked.length))
        .map((node) => node.id),
    );
    for (const node of members) {
      if (isHardLock(node)) continue;
      if (!keep.has(node.id)) {
        node.posterior_probability = 0;
        node._reason = "keep top-k collapsed";
      }
    }
    renormalizeMembers(members);
  }
}

function renormalizeMembers(members: MutableNode[]) {
  const hard = members.filter(isHardLock);
  const hardTotal = Math.min(
    1,
    hard.reduce((sum, node) => sum + (node.posterior_probability ?? 0), 0),
  );
  const rest = members.filter((node) => !hard.includes(node));
  const total = rest.reduce(
    (sum, node) => sum + (node.posterior_probability ?? 0),
    0,
  );
  const remainder = Math.max(0, 1 - hardTotal);
  for (const node of rest) {
    node.posterior_probability =
      total > epsilon
        ? ((node.posterior_probability ?? 0) / total) * remainder
        : 0;
  }
}

function clampProbability(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function isHardLock(node: KnowledgeNode) {
  return node.lock_mode === "hard" || node.lock_mode === "hard_lock";
}

function isSoftLock(node: KnowledgeNode) {
  return node.lock_mode === "soft" || node.lock_mode === "soft_lock";
}

function isFreezeRatio(node: KnowledgeNode) {
  return (
    node.lock_mode === "freeze_ratio" ||
    node.lock_mode === "freeze_concentration_band"
  );
}

function round(value: number) {
  return Math.round(value * 10000) / 10000;
}
