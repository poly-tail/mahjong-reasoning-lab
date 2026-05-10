import type {
  InfluenceSign,
  KnowledgeEdge,
  KnowledgeNode,
  WorkspaceDocument,
} from "./schema";

export type MetricInfluence = {
  edge: KnowledgeEdge;
  source: KnowledgeNode;
  metric: KnowledgeNode;
  signed_score: number;
};

export type AmbiguityItem = {
  id: string;
  metric_id: string;
  metric_title: string;
  status: "mixed" | "unknown" | "conflicting";
  influence_edge_ids: string[];
  source_titles: string[];
  unresolved_score: number;
  prune_candidate: boolean;
  downweight_candidate: boolean;
  observe_candidate_ids: string[];
};

export type BranchVector = {
  branch_id: string;
  title: string;
  metric_scores: Record<string, number>;
  dominant_direction: InfluenceSign;
  uncertainty: number;
  conflict_count: number;
  prune_action: "prune" | "downweight" | "keep" | "observe";
  prune_confidence: number;
  prune_reason: string;
};

export type ObservationPlanItem = {
  node: KnowledgeNode;
  gain_cost_ratio: number;
  target_titles: string[];
};

export type InfluenceModelSummary = {
  metrics: KnowledgeNode[];
  influence_edges: KnowledgeEdge[];
  ambiguities: AmbiguityItem[];
  branch_vectors: BranchVector[];
  observation_plan: ObservationPlanItem[];
};

export function isMetricNode(node: KnowledgeNode) {
  return (
    node.type === "metric" &&
    (node.tags.includes("metric") || node.id.startsWith("metric_"))
  );
}

export function isInfluenceEdge(edge: KnowledgeEdge) {
  return edge.relation_layer === "influence" || edge.type === "influences";
}

export function getInfluenceModel(
  doc: WorkspaceDocument,
): InfluenceModelSummary {
  const nodeById = new Map(doc.nodes.map((node) => [node.id, node]));
  const metrics = doc.nodes.filter(isMetricNode);
  const metricIds = new Set(metrics.map((metric) => metric.id));
  const influenceEdges = doc.edges.filter(
    (edge) =>
      isInfluenceEdge(edge) &&
      metricIds.has(edge.target) &&
      nodeById.has(edge.source),
  );

  return {
    metrics,
    influence_edges: influenceEdges,
    ambiguities: getAmbiguities(doc),
    branch_vectors: getBranchVectors(doc),
    observation_plan: getObservationPlan(doc),
  };
}

export function getMetricInfluences(
  doc: WorkspaceDocument,
  metricId: string,
): MetricInfluence[] {
  const nodeById = new Map(doc.nodes.map((node) => [node.id, node]));
  const metric = nodeById.get(metricId);
  if (!metric) return [];

  return doc.edges
    .filter((edge) => isInfluenceEdge(edge) && edge.target === metricId)
    .map((edge) => {
      const source = nodeById.get(edge.source);
      if (!source) return undefined;
      return {
        edge,
        source,
        metric,
        signed_score: signedScore(edge),
      };
    })
    .filter((item): item is MetricInfluence => Boolean(item));
}

export function getAmbiguities(doc: WorkspaceDocument): AmbiguityItem[] {
  const metrics = doc.nodes.filter(isMetricNode);
  const observationCandidates = doc.nodes.filter(
    (node) => node.type === "observation_candidate",
  );
  return metrics.flatMap((metric) => {
    const influences = getMetricInfluences(doc, metric.id);
    if (influences.length === 0) return [];

    const positives = influences.filter((item) => item.edge.sign === "+");
    const negatives = influences.filter((item) => item.edge.sign === "-");
    const mixed = influences.filter((item) => item.edge.sign === "mixed");
    const unknown = influences.filter((item) => item.edge.sign === "unknown");
    const items: AmbiguityItem[] = [];

    if (mixed.length > 0) {
      items.push(
        createAmbiguityItem("mixed", metric, mixed, observationCandidates),
      );
    }
    if (unknown.length > 0) {
      items.push(
        createAmbiguityItem("unknown", metric, unknown, observationCandidates),
      );
    }
    if (positives.length > 0 && negatives.length > 0) {
      items.push(
        createAmbiguityItem(
          "conflicting",
          metric,
          influences,
          observationCandidates,
        ),
      );
    }
    return items;
  });
}

export function getBranchVectors(doc: WorkspaceDocument): BranchVector[] {
  const branchNodes = doc.nodes.filter((node) =>
    ["branch", "hypothesis", "scenario"].includes(node.type),
  );
  const metrics = doc.nodes.filter(isMetricNode);
  const metricIds = new Set(metrics.map((metric) => metric.id));
  const ambiguities = getAmbiguities(doc);

  return branchNodes
    .map((branch) => {
      const outgoing = doc.edges.filter(
        (edge) =>
          isInfluenceEdge(edge) &&
          edge.source === branch.id &&
          metricIds.has(edge.target),
      );
      if (outgoing.length === 0) return undefined;

      const metricScores = Object.fromEntries(
        metrics.map((metric) => [
          metric.id,
          outgoing
            .filter((edge) => edge.target === metric.id)
            .reduce((sum, edge) => combineScore(sum, edge), 0),
        ]),
      );
      const total = Object.values(metricScores).reduce(
        (sum, value) => sum + value,
        0,
      );
      const conflictCount = ambiguities.filter((item) =>
        outgoing.some((edge) => item.influence_edge_ids.includes(edge.id)),
      ).length;
      const avgConfidence =
        outgoing.reduce((sum, edge) => sum + edge.confidence, 0) /
        Math.max(outgoing.length, 1);
      const uncertainty = clamp01(1 - avgConfidence + conflictCount * 0.15);
      const prune = evaluatePruning(
        branch,
        metricScores,
        uncertainty,
        conflictCount,
        outgoing,
      );

      return {
        branch_id: branch.id,
        title: branch.title,
        metric_scores: metricScores,
        dominant_direction: dominantDirection(total, outgoing),
        uncertainty,
        conflict_count: conflictCount,
        prune_action: prune.action,
        prune_confidence: prune.confidence,
        prune_reason: prune.reason,
      };
    })
    .filter((item): item is BranchVector => Boolean(item));
}

export function getObservationPlan(
  doc: WorkspaceDocument,
): ObservationPlanItem[] {
  const nodeById = new Map(doc.nodes.map((node) => [node.id, node]));
  return doc.nodes
    .filter((node) => node.type === "observation_candidate")
    .map((node) => {
      const cost = Math.max(node.observation_cost ?? 1, 0.01);
      const signGain = node.expected_sign_gain ?? 0;
      const weightGain = node.expected_weight_gain ?? 0;
      const timeliness = node.timeliness ?? 0.5;
      return {
        node,
        gain_cost_ratio: ((signGain + weightGain) * (0.5 + timeliness)) / cost,
        target_titles: node.resolves_targets.map(
          (id) => nodeById.get(id)?.title ?? id,
        ),
      };
    })
    .sort((a, b) => b.gain_cost_ratio - a.gain_cost_ratio);
}

function createAmbiguityItem(
  status: AmbiguityItem["status"],
  metric: KnowledgeNode,
  influences: MetricInfluence[],
  observationCandidates: KnowledgeNode[],
): AmbiguityItem {
  const unresolved = influences.reduce((sum, item) => {
    if (item.edge.sign === "unknown")
      return sum + item.edge.magnitude * (1 - item.edge.confidence);
    if (item.edge.sign === "mixed") return sum + item.edge.magnitude;
    return sum + Math.abs(item.signed_score);
  }, 0);
  const candidates = observationCandidates
    .filter((node) => node.resolves_targets.includes(metric.id))
    .map((node) => node.id);

  return {
    id: `${metric.id}_${status}`,
    metric_id: metric.id,
    metric_title: metric.title,
    status,
    influence_edge_ids: influences.map((item) => item.edge.id),
    source_titles: influences.map((item) => item.source.title),
    unresolved_score: round(unresolved),
    prune_candidate: status === "conflicting" ? false : unresolved < 0.25,
    downweight_candidate: status !== "unknown" && unresolved >= 0.25,
    observe_candidate_ids: candidates,
  };
}

function evaluatePruning(
  branch: KnowledgeNode,
  metricScores: Record<string, number>,
  uncertainty: number,
  conflictCount: number,
  edges: KnowledgeEdge[],
) {
  if (
    branch.lock_mode === "keep_top_k" ||
    branch.pruning_hints.includes("must_keep_top_k")
  ) {
    return {
      action: "keep" as const,
      confidence: 1,
      reason: "top-k keep constraint blocks pruning",
    };
  }
  const unresolved = uncertainty + conflictCount * 0.2;
  if (unresolved > 0.55) {
    return {
      action: "observe" as const,
      confidence: round(1 - Math.min(unresolved, 1)),
      reason: "unresolved ambiguity is too large",
    };
  }

  const foldRisk = scoreForMetric(metricScores, "fold_risk");
  const safety = scoreForMetric(metricScores, "safety");
  const winRate = scoreForMetric(metricScores, "win_rate");
  const value = scoreForMetric(metricScores, "value");
  const rankEv = scoreForMetric(metricScores, "rank_ev");
  const pruningPressure = foldRisk - safety - winRate - value - rankEv;
  const avgConfidence =
    edges.reduce((sum, edge) => sum + edge.confidence, 0) /
    Math.max(edges.length, 1);

  if (pruningPressure > 0.45 && avgConfidence > 0.65) {
    return {
      action: "prune" as const,
      confidence: round(avgConfidence * Math.min(pruningPressure, 1)),
      reason: "risk direction dominates with enough confidence",
    };
  }
  if (pruningPressure > 0.15) {
    return {
      action: "downweight" as const,
      confidence: round(avgConfidence * 0.65),
      reason: "risk direction is present but not decisive",
    };
  }
  return {
    action: "keep" as const,
    confidence: round(avgConfidence),
    reason: "benefit or safety directions prevent pruning",
  };
}

function scoreForMetric(scores: Record<string, number>, metricKey: string) {
  const match = Object.entries(scores).find(([id]) => id.includes(metricKey));
  return match?.[1] ?? 0;
}

function combineScore(current: number, edge: KnowledgeEdge) {
  const score = signedScore(edge);
  if (edge.combination_mode === "override") return score;
  if (edge.combination_mode === "multiplicative")
    return current === 0 ? score : current * score;
  return current + score;
}

function signedScore(edge: KnowledgeEdge) {
  const base = edge.magnitude * edge.confidence;
  if (edge.sign === "+") return base;
  if (edge.sign === "-") return -base;
  return 0;
}

function dominantDirection(
  total: number,
  edges: KnowledgeEdge[],
): InfluenceSign {
  if (edges.some((edge) => edge.sign === "unknown")) return "unknown";
  if (edges.some((edge) => edge.sign === "mixed")) return "mixed";
  if (Math.abs(total) < 0.05) return "mixed";
  return total > 0 ? "+" : "-";
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}

function round(value: number) {
  return Math.round(value * 10000) / 10000;
}
