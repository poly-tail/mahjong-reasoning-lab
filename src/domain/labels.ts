import type {
  CaseLane,
  DistributionFamily,
  EdgeType,
  LockMode,
  NodeType,
  ProbabilityRole,
  PropagationPolicy,
  RelationLayer,
  RuleCategory,
  CombinationMode,
  InfluenceSign,
} from "./schema";

export const nodeTypeLabels: Record<NodeType, string> = {
  concept: "概念",
  signal: "シグナル",
  condition: "条件",
  metric: "指標",
  heuristic: "ヒューリスティック",
  exception: "例外",
  scenario: "シナリオ",
  action: "判断/行動",
  evidence: "根拠",
  question: "問い",
  hypothesis: "仮説",
  branch: "枝",
  choice_group: "Choice group",
  observation: "観測",
  weight_modifier: "重み補正",
  lock_controller: "Lock制御",
  distribution_assumption: "分布仮定",
  probability_aggregate: "確率集約",
  observation_candidate: "観測候補",
  ambiguity_marker: "曖昧性",
  pruning_suggestion: "Prune提案",
  weight_adjustment_suggestion: "重み調整提案",
};

export const edgeTypeLabels: Record<EdgeType, string> = {
  supports: "支持",
  contradicts: "相反",
  refines: "詳細化",
  triggers: "トリガー",
  overrides: "上書き",
  applies_to: "適用先",
  measured_by: "測定",
  exported_as: "export",
  influences: "影響",
  resolves: "解消",
  weakens: "弱める",
  strengthens: "強める",
  disambiguates: "曖昧性解消",
  blocks_pruning: "prune禁止",
  enables_pruning: "prune許可",
};

export const laneLabels: Record<CaseLane, string> = {
  observation: "観測",
  hypothesis: "仮説",
  condition: "条件",
  decision: "判断",
};

export const ruleCategoryLabels: Record<RuleCategory, string> = {
  hard_gate: "Hard gate",
  soft_score: "Soft score",
  override: "Override",
  fallback: "Fallback",
  mixed: "Mixed",
};

export const probabilityRoleLabels: Record<ProbabilityRole, string> = {
  none: "none",
  prior: "prior",
  posterior: "posterior",
  control: "control",
};

export const lockModeLabels: Record<LockMode, string> = {
  none: "なし",
  hard: "hard lock",
  soft: "soft lock",
  keep_top_k: "keep top-k",
  freeze_ratio: "freeze ratio",
  hard_lock: "hard lock",
  soft_lock: "soft lock",
  freeze_concentration_band: "freeze concentration band",
};

export const distributionFamilyLabels: Record<DistributionFamily, string> = {
  categorical: "categorical",
  interval: "interval",
  bimodal: "bimodal",
  multimodal: "multimodal",
  asymmetric_tail: "asymmetric tail",
  mixture: "mixture",
};

export const propagationPolicyLabels: Record<PropagationPolicy, string> = {
  none: "none",
  normalize_siblings: "normalize siblings",
  multiply_downstream: "multiply downstream",
  gated: "gated",
};

export const relationLayerLabels: Record<RelationLayer, string> = {
  semantic: "semantic",
  probabilistic: "probabilistic",
  influence: "influence",
};

export const influenceSignLabels: Record<InfluenceSign, string> = {
  "+": "+ positive",
  "-": "- negative",
  mixed: "mixed",
  unknown: "unknown",
};

export const combinationModeLabels: Record<CombinationMode, string> = {
  additive: "additive",
  multiplicative: "multiplicative",
  override: "override",
};
