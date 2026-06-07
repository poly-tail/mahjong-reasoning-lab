import { nowIso } from "./factory";
import {
  getAmbiguities,
  getBranchVectors,
  getInfluenceModel,
  getObservationPlan,
} from "./influence";
import {
  getChoiceGroups,
  getInferenceSubgraph,
  isInferenceNode,
  runPropagation,
} from "./probability";
import { getResidualMassChoiceGroups } from "./residualMass";
import type {
  AveragingSafety,
  ConcentrationMetrics,
  ImpactSummary,
  KnowledgeNode,
  PruningAction,
  ReadingChain,
  ReadingUtility,
  TeachingLog,
  WorkspaceDocument,
} from "./schema";

export type DistributionSnapshot = {
  id: string;
  node_probabilities: Record<string, number>;
  dominant_node_id?: string;
  margin: number;
  total_mass: number;
};

export type ConcentrationItem = {
  id: string;
  title: string;
  scope: "choice_group" | "concentration_group" | "inference_subgraph";
  node_ids: string[];
  metrics: ConcentrationMetrics;
  impact_prediction: string;
};

export type PruningSimulation = {
  action: PruningAction;
  before: DistributionSnapshot;
  after: DistributionSnapshot;
  impact_summary: ImpactSummary;
  affected_node_ids: string[];
  preview_doc: WorkspaceDocument;
  rationale: string[];
};

export type ChainReplayStep = {
  step_id: string;
  before: DistributionSnapshot;
  after: DistributionSnapshot;
  impact_summary: ImpactSummary;
  rationale: string;
};

export type ChainReplay = {
  chain_id: string;
  steps: ChainReplayStep[];
  final_doc: WorkspaceDocument;
};

const epsilon = 0.000001;

export function createDistributionSnapshot(
  doc: WorkspaceDocument,
  id: string,
  targetIds?: string[],
): DistributionSnapshot {
  const targetSet = targetIds ? new Set(targetIds) : undefined;
  const inferenceNodes = doc.nodes.filter(
    (node) => isInferenceNode(node) && (!targetSet || targetSet.has(node.id)),
  );
  const probabilities = Object.fromEntries(
    inferenceNodes.map((node) => [
      node.id,
      round(node.posterior_probability ?? node.prior_probability ?? 0),
    ]),
  );
  const ranked = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);
  const dominant = ranked[0];
  const runnerUp = ranked[1];
  const totalMass = Object.values(probabilities).reduce(
    (sum, value) => sum + value,
    0,
  );

  return {
    id,
    node_probabilities: probabilities,
    dominant_node_id: dominant?.[0],
    margin: round((dominant?.[1] ?? 0) - (runnerUp?.[1] ?? 0)),
    total_mass: round(totalMass),
  };
}

export function calculateConcentration(
  probabilities: number[],
  topK = 2,
): ConcentrationMetrics {
  const positive = probabilities.map((value) => Math.max(0, value));
  const total = positive.reduce((sum, value) => sum + value, 0);
  const normalized =
    total > epsilon
      ? positive.map((value) => value / total)
      : positive.map(() => 0);
  const ranked = [...normalized].sort((a, b) => b - a);
  const entropyRaw = normalized.reduce(
    (sum, value) => (value > epsilon ? sum - value * Math.log2(value) : sum),
    0,
  );
  const maxEntropy = normalized.length > 1 ? Math.log2(normalized.length) : 1;
  const entropy = maxEntropy > epsilon ? entropyRaw / maxEntropy : 0;
  const peakMass = ranked[0] ?? 0;
  const topKMass = ranked
    .slice(0, Math.max(1, topK))
    .reduce((sum, value) => sum + value, 0);
  const hhi = normalized.reduce((sum, value) => sum + value * value, 0);
  const dispersionNote =
    peakMass >= 0.62
      ? "高集中"
      : topKMass >= 0.78
        ? "上位候補集中"
        : entropy >= 0.82
          ? "広く分散"
          : "分布が分岐";

  return {
    entropy: round(entropy),
    top_k_mass: round(topKMass),
    peak_mass: round(peakMass),
    hhi: round(hhi),
    dispersion_note: dispersionNote,
  };
}

export function getConcentrationItems(
  doc: WorkspaceDocument,
): ConcentrationItem[] {
  const { nodes: inferenceNodes } = getInferenceSubgraph(doc);
  const nodeById = new Map(doc.nodes.map((node) => [node.id, node]));
  const items: ConcentrationItem[] = [];
  const seen = new Set<string>();

  for (const group of getChoiceGroups(inferenceNodes)) {
    const nodes = group.node_ids
      .map((id) => nodeById.get(id))
      .filter((node): node is KnowledgeNode => Boolean(node));
    items.push(
      createConcentrationItem(group.id, group.id, "choice_group", nodes),
    );
    seen.add(group.id);
  }

  const concentrationGroups = new Map<string, KnowledgeNode[]>();
  for (const node of inferenceNodes) {
    if (!node.concentration_group_id || seen.has(node.concentration_group_id))
      continue;
    concentrationGroups.set(node.concentration_group_id, [
      ...(concentrationGroups.get(node.concentration_group_id) ?? []),
      node,
    ]);
  }
  for (const [id, nodes] of concentrationGroups) {
    items.push(createConcentrationItem(id, id, "concentration_group", nodes));
  }

  items.push(
    createConcentrationItem(
      "inference_subgraph",
      "推論サブグラフ",
      "inference_subgraph",
      inferenceNodes,
    ),
  );

  return items.sort((a, b) => b.metrics.hhi - a.metrics.hhi);
}

export function simulatePruningAction(
  doc: WorkspaceDocument,
  action: PruningAction,
): PruningSimulation {
  const baseline = runPropagation(doc).updated_workspace;
  const before = createDistributionSnapshot(baseline, `${action.id}_before`);
  const actionDoc = applyPruningAction(baseline, action);
  const preview = runPropagation(actionDoc, action.target_ids[0]);
  const afterDoc = preview.updated_workspace;
  const after = createDistributionSnapshot(afterDoc, `${action.id}_after`);
  const impactSummary = buildImpactSummary(
    action,
    baseline,
    afterDoc,
    before,
    after,
  );

  return {
    action,
    before,
    after,
    impact_summary: impactSummary,
    affected_node_ids: preview.affected_node_ids,
    preview_doc: afterDoc,
    rationale: [
      `${action.target_ids.length}件の対象に操作を適用しました。`,
      `質量差分=${impactSummary.delta_mass}、変更ノード数=${impactSummary.changed_node_count}。`,
      impactSummary.notes,
    ].filter(Boolean),
  };
}

export function evaluateReadingUtilities(
  doc: WorkspaceDocument,
): ReadingUtility[] {
  const inferred = inferReadingUtilities(doc);
  const byTarget = new Map<string, ReadingUtility>();
  for (const utility of inferred) byTarget.set(utility.target_id, utility);
  for (const utility of doc.reading_utilities) {
    byTarget.set(utility.target_id, utility);
  }
  return Array.from(byTarget.values()).sort(
    (a, b) => b.utility_score - a.utility_score,
  );
}

export function estimateAveragingSafety(
  doc: WorkspaceDocument,
): AveragingSafety[] {
  const seeded = new Map(
    doc.averaging_safety.map((item) => [item.target_id, item]),
  );
  for (const item of getConcentrationItems(doc)) {
    const nodes = item.node_ids
      .map((id) => doc.nodes.find((node) => node.id === id))
      .filter((node): node is KnowledgeNode => Boolean(node));
    if (nodes.length === 0 || seeded.has(item.id)) continue;

    const probabilities = nodes.map(
      (node) => node.posterior_probability ?? node.prior_probability ?? 0,
    );
    const mean =
      probabilities.reduce((sum, value) => sum + value, 0) /
      Math.max(probabilities.length, 1);
    const varianceProxy =
      probabilities.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) /
      Math.max(probabilities.length, 1);
    const sensitive =
      item.metrics.peak_mass > 0.62 ||
      item.metrics.top_k_mass > 0.82 ||
      hasSensitiveDistribution(nodes);
    const ambiguity = getAmbiguities(doc).filter((ambiguityItem) =>
      ambiguityItem.influence_edge_ids.some((edgeId) => {
        const edge = doc.edges.find((candidate) => candidate.id === edgeId);
        return Boolean(edge && item.node_ids.includes(edge.source));
      }),
    ).length;
    const score = clamp01(
      1 -
        varianceProxy * 4 -
        (sensitive ? 0.28 : 0) -
        Math.min(0.35, ambiguity * 0.12),
    );
    const label = score >= 0.68 ? "safe" : score >= 0.4 ? "caution" : "unsafe";
    const reasons = [
      `分散の代理値 ${round(varianceProxy)}`,
      `集中度 ${item.metrics.dispersion_note}`,
      ambiguity > 0
        ? `未解決の影響曖昧性 ${ambiguity}件`
        : "局所的な影響曖昧性はありません",
      sensitive
        ? "小さな変化で枝集合が動く可能性があります"
        : "小さな変化への感度は限定的です",
    ];

    seeded.set(item.id, {
      target_id: item.id,
      score: round(score),
      label,
      reasons,
    });
  }
  return Array.from(seeded.values()).sort((a, b) => b.score - a.score);
}

export function replayReadingChain(
  doc: WorkspaceDocument,
  chain: ReadingChain,
): ChainReplay {
  let current = runPropagation(doc).updated_workspace;
  const steps: ChainReplayStep[] = [];

  chain.steps.forEach((step, index) => {
    const action = actionFromChainStep(chain.id, step, index);
    const before = createDistributionSnapshot(
      current,
      `${chain.id}_${step.id}_before`,
    );
    let afterDoc = current;
    let after = before;
    let impactSummary = emptyImpactSummary(before.id, before.id, step.note);

    if (action) {
      const simulation = simulatePruningAction(current, action);
      afterDoc = simulation.preview_doc;
      after = {
        ...simulation.after,
        id: `${chain.id}_${step.id}_after`,
      };
      impactSummary = {
        ...simulation.impact_summary,
        before_snapshot_id: before.id,
        after_snapshot_id: after.id,
      };
    }

    steps.push({
      step_id: step.id,
      before,
      after,
      impact_summary: impactSummary,
      rationale: step.rationale,
    });
    current = afterDoc;
  });

  return { chain_id: chain.id, steps, final_doc: current };
}

export function buildTeachingLogs(doc: WorkspaceDocument): TeachingLog[] {
  if (doc.teaching_logs.length > 0) return doc.teaching_logs;
  const activeCaseId = doc.active_case_id ?? doc.cases[0]?.id ?? "ケース不明";
  return evaluateReadingUtilities(doc)
    .slice(0, 4)
    .map((utility) => {
      const node = doc.nodes.find(
        (candidate) => candidate.id === utility.target_id,
      );
      const high = utility.utility_score >= 0.55;
      return {
        case_id: activeCaseId,
        action_id: utility.target_id,
        explanation_short: `${node?.title ?? utility.target_id}: 有用度 ${round(
          utility.utility_score,
        )}`,
        explanation_full: high
          ? "上位確率質量、曖昧性低減、投影余裕度のどれかに十分効いているため、読みの検討価値が高い。"
          : "削れる範囲が狭い、全体影響が小さい、または曖昧性が残るため、単独では判断を動かしにくい。",
        key_terms: ["分布形状", "集中度", "曖昧性", "解像度", "投影余裕度"],
        created_at: nowIso(),
      };
    });
}

export function createTeachingLogFromSimulation(
  caseId: string,
  simulation: PruningSimulation,
  targetTitle: string,
): TeachingLog {
  const summary = simulation.impact_summary;
  const actionType = simulation.action.action_type;
  const safeAlternative =
    actionType === "hard_prune" && summary.ambiguity_change <= 0
      ? "hard prune より downweight / keep-top-k が安全です。"
      : "操作後も残る候補と曖昧性を確認してください。";

  return {
    case_id: caseId,
    action_id: simulation.action.id,
    explanation_short: `${targetTitle}: ${actionType} の判断差分`,
    explanation_full: `この読みは ${targetTitle} に ${actionType} を適用し、質量差分を ${summary.delta_mass}、判断余裕を ${summary.margin_change} 変化させました。主枝変化は「${summary.dominant_branch_change}」です。曖昧性変化は ${summary.ambiguity_change} で、${safeAlternative}`,
    key_terms: [
      "この読みで何が変わったか",
      "質量差分",
      "判断余裕",
      "曖昧性",
    ],
    created_at: nowIso(),
  };
}

function createConcentrationItem(
  id: string,
  title: string,
  scope: ConcentrationItem["scope"],
  nodes: KnowledgeNode[],
): ConcentrationItem {
  const metrics = calculateConcentration(
    nodes.map(
      (node) => node.posterior_probability ?? node.prior_probability ?? 0,
    ),
  );
  const impact =
    metrics.peak_mass >= 0.62 || metrics.top_k_mass >= 0.82
      ? "小さな枝刈りでも全体分布が動く可能性があります"
      : metrics.entropy >= 0.82
        ? "局所的な枝刈りの影響は多くの枝へ分散しやすいです"
        : "どのピークに作用するかで影響が変わります";
  return {
    id,
    title,
    scope,
    node_ids: nodes.map((node) => node.id),
    metrics,
    impact_prediction: impact,
  };
}

function applyPruningAction(
  doc: WorkspaceDocument,
  action: PruningAction,
): WorkspaceDocument {
  const targets = expandActionTargets(doc, action);
  const targetSet = new Set(targets);
  const now = nowIso();

  return {
    ...doc,
    nodes: doc.nodes.map((node) => {
      if (!targetSet.has(node.id)) return node;
      const current =
        node.posterior_probability ??
        node.prior_probability ??
        node.base_weight ??
        0;
      if (action.action_type === "hard_prune") {
        return {
          ...node,
          base_weight: 0,
          dynamic_weight: 0,
          posterior_probability: 0,
          prior_probability: 0,
          lock_rationale: action.rationale,
          updated_at: now,
        };
      }
      if (action.action_type === "soft_downweight") {
        const factor = clamp01(1 - action.strength);
        return {
          ...node,
          base_weight: round(current * factor),
          posterior_probability: round(current * factor),
          lock_rationale: action.rationale,
          updated_at: now,
        };
      }
      if (action.action_type === "hard_lock") {
        return {
          ...node,
          lock_mode: "hard_lock",
          lock_value: clamp01(action.strength),
          lock_rationale: action.rationale,
          updated_at: now,
        };
      }
      if (action.action_type === "soft_lock") {
        return {
          ...node,
          lock_mode: "soft_lock",
          lock_value: clamp01(action.strength),
          lock_rationale: action.rationale,
          updated_at: now,
        };
      }
      if (action.action_type === "keep_top_k") {
        return {
          ...node,
          lock_mode: "keep_top_k",
          lock_value: Math.max(1, Math.round(action.strength)),
          lock_rationale: action.rationale,
          updated_at: now,
        };
      }
      if (action.action_type === "freeze_concentration_band") {
        return {
          ...node,
          lock_mode: "freeze_concentration_band",
          lock_value: clamp01(action.strength),
          lock_rationale: action.rationale,
          updated_at: now,
        };
      }
      return {
        ...node,
        lock_mode: "freeze_ratio",
        lock_value: clamp01(action.strength),
        lock_rationale: action.rationale,
        updated_at: now,
      };
    }),
    updated_at: now,
  };
}

function expandActionTargets(doc: WorkspaceDocument, action: PruningAction) {
  if (action.action_type !== "keep_top_k") return action.target_ids;
  const targetGroups = new Set(
    doc.nodes
      .filter((node) => action.target_ids.includes(node.id))
      .map((node) => node.choice_group_id)
      .filter((id): id is string => Boolean(id)),
  );
  if (targetGroups.size === 0) return action.target_ids;
  return doc.nodes
    .filter(
      (node) => node.choice_group_id && targetGroups.has(node.choice_group_id),
    )
    .map((node) => node.id);
}

function buildImpactSummary(
  action: PruningAction,
  beforeDoc: WorkspaceDocument,
  afterDoc: WorkspaceDocument,
  before: DistributionSnapshot,
  after: DistributionSnapshot,
): ImpactSummary {
  const ids = new Set([
    ...Object.keys(before.node_probabilities),
    ...Object.keys(after.node_probabilities),
  ]);
  let changed = 0;
  let absoluteDelta = 0;
  for (const id of ids) {
    const delta =
      (after.node_probabilities[id] ?? 0) -
      (before.node_probabilities[id] ?? 0);
    if (Math.abs(delta) > 0.0001) changed += 1;
    absoluteDelta += Math.abs(delta);
  }
  const beforeAmbiguity = unresolvedAmbiguity(beforeDoc);
  const afterAmbiguity = unresolvedAmbiguity(afterDoc);
  const beforeVector = aggregateMetricProjection(beforeDoc);
  const afterVector = aggregateMetricProjection(afterDoc);
  const vectorDelta = Object.fromEntries(
    Array.from(
      new Set([...Object.keys(beforeVector), ...Object.keys(afterVector)]),
    )
      .map((metricId) => [
        metricId,
        round((afterVector[metricId] ?? 0) - (beforeVector[metricId] ?? 0)),
      ])
      .filter(([, value]) => Math.abs(value as number) > 0.0001),
  );
  const nodeById = new Map(afterDoc.nodes.map((node) => [node.id, node.title]));
  const dominantChange =
    before.dominant_node_id === after.dominant_node_id
      ? `安定: ${nodeById.get(after.dominant_node_id ?? "") ?? "なし"}`
      : `${nodeById.get(before.dominant_node_id ?? "") ?? "なし"} -> ${
          nodeById.get(after.dominant_node_id ?? "") ?? "なし"
        }`;

  return {
    before_snapshot_id: before.id,
    after_snapshot_id: after.id,
    delta_mass: round(absoluteDelta / 2),
    changed_node_count: changed,
    dominant_branch_change: dominantChange,
    ambiguity_change: round(beforeAmbiguity - afterAmbiguity),
    margin_change: round(after.margin - before.margin),
    vector_delta_by_metric: vectorDelta,
    notes: `操作強度=${action.strength}。曖昧性変化が正なら曖昧性が減っています。`,
  };
}

function inferReadingUtilities(doc: WorkspaceDocument): ReadingUtility[] {
  const inferenceNodes = doc.nodes.filter(isInferenceNode);
  const residualGroups = getResidualMassChoiceGroups(doc.nodes);
  const residualByNodeId = new Map<string, (typeof residualGroups)[number]>();
  for (const group of residualGroups) {
    for (const nodeId of group.node_ids) residualByNodeId.set(nodeId, group);
    for (const nodeId of group.residual_node_ids) residualByNodeId.set(nodeId, group);
  }
  const totalMass = inferenceNodes.reduce(
    (sum, node) =>
      sum + (node.posterior_probability ?? node.prior_probability ?? 0),
    0,
  );
  const observationPlan = new Map(
    getObservationPlan(doc).map((item) => [item.node.id, item]),
  );

  return doc.nodes
    .filter((node) =>
      [
        "signal",
        "observation",
        "observation_candidate",
        "heuristic",
        "weight_modifier",
        "pruning_suggestion",
        "weight_adjustment_suggestion",
      ].includes(node.type),
    )
    .map((node) => {
      const outgoing = doc.edges.filter((edge) => edge.source === node.id);
      const targetIds = new Set([
        ...outgoing.map((edge) => edge.target),
        ...node.resolves_targets,
      ]);
      const residualMetrics = summarizeResidualForTargets(
        [...targetIds, node.id],
        residualByNodeId,
      );
      const targetMass = inferenceNodes
        .filter((target) => targetIds.has(target.id) || target.id === node.id)
        .reduce(
          (sum, target) =>
            sum +
            (target.posterior_probability ?? target.prior_probability ?? 0),
          0,
        );
      const selectivePruningRatio =
        totalMass > epsilon ? clamp01(targetMass / totalMass) : 0;
      const influenceStrength = outgoing.reduce(
        (sum, edge) => sum + edge.magnitude * edge.confidence,
        0,
      );
      const plan = observationPlan.get(node.id);
      const ambiguityReduction =
        (node.expected_sign_gain ?? 0) * 0.55 +
        (plan?.gain_cost_ratio ? Math.min(0.45, plan.gain_cost_ratio / 6) : 0);
      const resolutionGain =
        (node.expected_weight_gain ?? 0) * 0.45 + (node.timeliness ?? 0) * 0.2;
      const concentrationShift =
        selectivePruningRatio * Math.min(1, influenceStrength);
      const globalImpact =
        concentrationShift * 0.6 + Math.min(1, influenceStrength) * 0.4;
      const projectedMarginGain =
        node.expected_margin_gain ??
        outgoing.reduce(
          (sum, edge) => sum + edge.magnitude * edge.confidence,
          0,
        ) * 0.18;
      const cost =
        node.observation_cost ?? (node.type === "signal" ? 0.35 : 0.7);
      const breadthPenalty = 0.35 + selectivePruningRatio * 0.65;
      const utility = clamp01(
        ((globalImpact * 0.35 +
          concentrationShift * 0.2 +
          ambiguityReduction * 0.2 +
          resolutionGain * 0.1 +
          projectedMarginGain * 0.15) *
          breadthPenalty) /
          (0.8 + cost * 0.25),
      );

      return {
        target_id: node.id,
        selective_pruning_ratio: round(selectivePruningRatio),
        global_impact_score: round(globalImpact),
        concentration_shift: round(concentrationShift),
        residual_mass_before: residualMetrics.before,
        residual_mass_after: residualMetrics.after,
        residual_reduction: residualMetrics.reduction,
        exception_candidates_added: residualMetrics.exceptionCandidates,
        unknown_buffer_remaining: residualMetrics.unknownRemaining,
        projected_margin_gain: round(projectedMarginGain),
        ambiguity_reduction: round(ambiguityReduction),
        resolution_gain: round(resolutionGain),
        cost_estimate: round(cost),
        utility_score: round(utility),
      };
    });
}

function summarizeResidualForTargets(
  targetIds: string[],
  residualByNodeId: Map<string, ReturnType<typeof getResidualMassChoiceGroups>[number]>,
) {
  type ResidualGroup = ReturnType<typeof getResidualMassChoiceGroups>[number];
  const groups = uniqueBy(
    targetIds
      .map((id) => residualByNodeId.get(id))
      .filter((item): item is ResidualGroup => Boolean(item)),
    (group) => group.id,
  );
  if (groups.length === 0) {
    return {
      before: 0,
      after: 0,
      reduction: 0,
      exceptionCandidates: 0,
      unknownRemaining: 0,
    };
  }

  const before = Math.max(
    ...groups.map((group) => group.summary.residual_probability),
  );
  const unknownRemaining = groups.reduce(
    (sum, group) =>
      sum +
      group.summary.buckets
        .filter((bucket) => bucket.kind === "unknown_buffer")
        .reduce((bucketSum, bucket) => bucketSum + bucket.probability, 0),
    0,
  );
  const exceptionCandidates = groups.reduce(
    (sum, group) =>
      sum +
      group.summary.buckets.filter((bucket) => bucket.kind === "exception")
        .length,
    0,
  );
  const resolvedResidual = groups.reduce(
    (sum, group) =>
      sum +
      group.summary.buckets
        .filter((bucket) => bucket.kind !== "unknown_buffer")
        .reduce((bucketSum, bucket) => bucketSum + bucket.probability, 0),
    0,
  );
  const after = clamp01(before - resolvedResidual);

  return {
    before: round(before),
    after: round(after),
    reduction: round(before - after),
    exceptionCandidates,
    unknownRemaining: round(Math.min(before, unknownRemaining)),
  };
}

function uniqueBy<T>(values: T[], getKey: (value: T) => string): T[] {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = getKey(value);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function actionFromChainStep(
  chainId: string,
  step: ReadingChain["steps"][number],
  index: number,
): PruningAction | undefined {
  if (step.step_type === "pruning") {
    return {
      id: `${chainId}_${step.id}_${index}_prune`,
      action_type: "hard_prune",
      target_ids: step.target_ids,
      strength: 1,
      rationale: step.rationale,
      created_at: nowIso(),
    };
  }
  if (step.step_type === "lock") {
    return {
      id: `${chainId}_${step.id}_${index}_lock`,
      action_type: "freeze_ratio",
      target_ids: step.target_ids,
      strength: 0.85,
      rationale: step.rationale,
      created_at: nowIso(),
    };
  }
  if (step.step_type === "weight_update") {
    return {
      id: `${chainId}_${step.id}_${index}_weight`,
      action_type: "soft_downweight",
      target_ids: step.target_ids,
      strength: 0.25,
      rationale: step.rationale,
      created_at: nowIso(),
    };
  }
  if (step.step_type === "fallback") {
    return {
      id: `${chainId}_${step.id}_${index}_topk`,
      action_type: "keep_top_k",
      target_ids: step.target_ids,
      strength: 2,
      rationale: step.rationale,
      created_at: nowIso(),
    };
  }
  return undefined;
}

function emptyImpactSummary(
  beforeId: string,
  afterId: string,
  notes: string,
): ImpactSummary {
  return {
    before_snapshot_id: beforeId,
    after_snapshot_id: afterId,
    delta_mass: 0,
    changed_node_count: 0,
    dominant_branch_change: "確率操作なし",
    ambiguity_change: 0,
    margin_change: 0,
    vector_delta_by_metric: {},
    notes,
  };
}

function aggregateMetricProjection(doc: WorkspaceDocument) {
  const nodeById = new Map(doc.nodes.map((node) => [node.id, node]));
  const vectors = getBranchVectors(doc);
  const totals: Record<string, number> = {};
  for (const vector of vectors) {
    const posterior =
      nodeById.get(vector.branch_id)?.posterior_probability ?? 1;
    for (const [metricId, score] of Object.entries(vector.metric_scores)) {
      totals[metricId] = (totals[metricId] ?? 0) + score * posterior;
    }
  }
  return Object.fromEntries(
    Object.entries(totals).map(([metricId, value]) => [metricId, round(value)]),
  );
}

function unresolvedAmbiguity(doc: WorkspaceDocument) {
  return getInfluenceModel(doc).ambiguities.reduce(
    (sum, item) => sum + item.unresolved_score,
    0,
  );
}

function hasSensitiveDistribution(nodes: KnowledgeNode[]) {
  return nodes.some((node) =>
    ["bimodal", "multimodal", "asymmetric_tail", "mixture"].includes(
      node.distribution_family ?? "",
    ),
  );
}

function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function round(value: number) {
  return Math.round(value * 10000) / 10000;
}
