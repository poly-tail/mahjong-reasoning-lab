import {
  WORKSPACE_SCHEMA_VERSION,
  type CaseData,
  type CaseLane,
  type KnowledgeEdge,
  type KnowledgeNode,
  type NodeType,
  type RuleCategory,
  type RuleDefinition,
  type WorkspaceDocument,
} from "./schema";

export function nowIso(): string {
  return new Date().toISOString();
}

export function createId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

export function createKnowledgeNode(
  type: NodeType,
  overrides: Partial<KnowledgeNode> & Pick<KnowledgeNode, "title">,
): KnowledgeNode {
  const now = nowIso();
  return {
    id: overrides.id ?? createId("node"),
    type,
    title: overrides.title,
    summary: overrides.summary ?? "",
    description: overrides.description ?? "",
    tags: overrides.tags ?? [],
    confidence: overrides.confidence ?? 0.55,
    applicability: overrides.applicability ?? [],
    stage: overrides.stage ?? "unspecified",
    actor: overrides.actor ?? "全員",
    source_type: overrides.source_type ?? "idea",
    reproducibility: overrides.reproducibility ?? 0.45,
    notes: overrides.notes ?? "",
    formulas: overrides.formulas ?? [],
    thresholds: overrides.thresholds ?? [],
    related_rule_ids: overrides.related_rule_ids ?? [],
    pruning_hints: overrides.pruning_hints ?? [],
    reading_utility_ids: overrides.reading_utility_ids ?? [],
    probability_role: overrides.probability_role ?? "none",
    choice_group_id: overrides.choice_group_id,
    concentration_group_id: overrides.concentration_group_id,
    base_weight: overrides.base_weight,
    dynamic_weight: overrides.dynamic_weight,
    posterior_probability: overrides.posterior_probability,
    prior_probability: overrides.prior_probability,
    lock_mode: overrides.lock_mode ?? "none",
    lock_value: overrides.lock_value,
    lock_rationale: overrides.lock_rationale ?? "",
    distribution_family: overrides.distribution_family,
    propagation_policy: overrides.propagation_policy ?? "none",
    hysteresis_band: overrides.hysteresis_band,
    pruning_priority: overrides.pruning_priority,
    resolves_targets: overrides.resolves_targets ?? [],
    expected_sign_gain: overrides.expected_sign_gain,
    expected_weight_gain: overrides.expected_weight_gain,
    expected_margin_gain: overrides.expected_margin_gain,
    pruning_safety_change: overrides.pruning_safety_change,
    observation_cost: overrides.observation_cost,
    timeliness: overrides.timeliness,
    position: overrides.position ?? { x: 120, y: 120 },
    group_id: overrides.group_id,
    is_group: overrides.is_group ?? false,
    collapsed: overrides.collapsed ?? false,
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
  };
}

export function createKnowledgeEdge(
  overrides: Partial<KnowledgeEdge> &
    Pick<KnowledgeEdge, "source" | "target" | "type">,
): KnowledgeEdge {
  const now = nowIso();
  return {
    id: overrides.id ?? createId("edge"),
    source: overrides.source,
    target: overrides.target,
    type: overrides.type,
    label: overrides.label ?? overrides.type,
    notes: overrides.notes ?? "",
    relation_layer: overrides.relation_layer ?? "semantic",
    conditional_weight: overrides.conditional_weight,
    transition_rule: overrides.transition_rule,
    propagate_probability: overrides.propagate_probability ?? false,
    edge_group_id: overrides.edge_group_id,
    sign: overrides.sign ?? "unknown",
    magnitude: overrides.magnitude ?? 0,
    confidence: overrides.confidence ?? 0.5,
    context_gate: overrides.context_gate,
    combination_mode: overrides.combination_mode ?? "additive",
    ambiguity_group_id: overrides.ambiguity_group_id,
    evidence_refs: overrides.evidence_refs ?? [],
    note: overrides.note,
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
  };
}

export function createRule(
  overrides: Partial<RuleDefinition> & Pick<RuleDefinition, "name">,
): RuleDefinition {
  const now = nowIso();
  return {
    id: overrides.id ?? createId("rule"),
    name: overrides.name,
    category: overrides.category ?? ("mixed" satisfies RuleCategory),
    target_node_ids: overrides.target_node_ids ?? [],
    hard_gates: overrides.hard_gates ?? [],
    soft_score_terms: overrides.soft_score_terms ?? [],
    override_conditions: overrides.override_conditions ?? [],
    fallback_behavior: overrides.fallback_behavior ?? "",
    note: overrides.note ?? "",
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
  };
}

export function createCase(
  overrides: Partial<CaseData> & Pick<CaseData, "title">,
): CaseData {
  const now = nowIso();
  return {
    id: overrides.id ?? createId("case"),
    title: overrides.title,
    round: overrides.round ?? "東1局",
    honba: overrides.honba ?? 0,
    riichi_sticks: overrides.riichi_sticks ?? 0,
    turn: overrides.turn ?? 6,
    scores: overrides.scores ?? {
      east: 25000,
      south: 25000,
      west: 25000,
      north: 25000,
    },
    dealer: overrides.dealer ?? "east",
    seat: overrides.seat ?? "south",
    riichi_status: overrides.riichi_status ?? "なし",
    melds_summary: overrides.melds_summary ?? "",
    discard_notes: overrides.discard_notes ?? "",
    observations: overrides.observations ?? [],
    hypotheses: overrides.hypotheses ?? [],
    attached_node_ids: overrides.attached_node_ids ?? [],
    selected_rule_ids: overrides.selected_rule_ids ?? [],
    lane_assignments: overrides.lane_assignments ?? {},
    top_k_hypotheses: overrides.top_k_hypotheses ?? 3,
    decision_note: overrides.decision_note ?? "",
    review_note: overrides.review_note ?? "",
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
  };
}

export function createWorkspaceDocument(
  overrides: Partial<WorkspaceDocument> = {},
): WorkspaceDocument {
  return {
    schema_version: WORKSPACE_SCHEMA_VERSION,
    nodes: overrides.nodes ?? [],
    edges: overrides.edges ?? [],
    cases: overrides.cases ?? [],
    rules: overrides.rules ?? [],
    saved_views: overrides.saved_views ?? [],
    pruning_actions: overrides.pruning_actions ?? [],
    impact_summaries: overrides.impact_summaries ?? [],
    reading_utilities: overrides.reading_utilities ?? [],
    reading_chains: overrides.reading_chains ?? [],
    averaging_safety: overrides.averaging_safety ?? [],
    teaching_logs: overrides.teaching_logs ?? [],
    active_case_id: overrides.active_case_id,
    updated_at: overrides.updated_at ?? nowIso(),
  };
}

export function inferLaneFromNodeType(type: NodeType): CaseLane {
  if (
    type === "signal" ||
    type === "evidence" ||
    type === "metric" ||
    type === "observation" ||
    type === "weight_modifier"
  ) {
    return "observation";
  }
  if (
    type === "heuristic" ||
    type === "question" ||
    type === "hypothesis" ||
    type === "branch" ||
    type === "distribution_assumption"
  ) {
    return "hypothesis";
  }
  if (
    type === "condition" ||
    type === "exception" ||
    type === "choice_group" ||
    type === "lock_controller" ||
    type === "ambiguity_marker"
  ) {
    return "condition";
  }
  return "decision";
}
