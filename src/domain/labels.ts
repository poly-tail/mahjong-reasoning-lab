import type {
  CaseLane,
  DistributionFamily,
  EdgeType,
  LockMode,
  NodeType,
  ProbabilityRole,
  SourceType,
  PropagationPolicy,
  RelationLayer,
  RuleCategory,
  PruningHint,
  PruningActionType,
  AveragingSafetyLabel,
  ReadingChainStepType,
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
  choice_group: "選択候補群",
  observation: "観測",
  weight_modifier: "重み補正",
  lock_controller: "ロック制御",
  distribution_assumption: "分布仮定",
  probability_aggregate: "確率集約",
  observation_candidate: "観測候補",
  ambiguity_marker: "曖昧性",
  pruning_suggestion: "枝刈り提案",
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
  exported_as: "出力",
  influences: "影響",
  resolves: "解消",
  weakens: "弱める",
  strengthens: "強める",
  disambiguates: "曖昧性解消",
  blocks_pruning: "枝刈り禁止",
  enables_pruning: "枝刈り許可",
};

export const laneLabels: Record<CaseLane, string> = {
  observation: "観測",
  hypothesis: "仮説",
  condition: "条件",
  decision: "判断",
};

export const ruleCategoryLabels: Record<RuleCategory, string> = {
  hard_gate: "強制ゲート",
  soft_score: "ソフトスコア",
  override: "上書き",
  fallback: "フォールバック",
  mixed: "混合",
};

export const probabilityRoleLabels: Record<ProbabilityRole, string> = {
  none: "なし",
  prior: "事前",
  posterior: "事後",
  control: "制御",
};

export const lockModeLabels: Record<LockMode, string> = {
  none: "なし",
  hard: "強制ロック",
  soft: "ソフトロック",
  keep_top_k: "上位候補保持",
  freeze_ratio: "比率固定",
  hard_lock: "強制ロック",
  soft_lock: "ソフトロック",
  freeze_concentration_band: "集中帯固定",
};

export const distributionFamilyLabels: Record<DistributionFamily, string> = {
  categorical: "カテゴリ分布",
  interval: "区間分布",
  bimodal: "二峰性分布",
  multimodal: "多峰性分布",
  asymmetric_tail: "非対称テール",
  mixture: "混合分布",
};

export const propagationPolicyLabels: Record<PropagationPolicy, string> = {
  none: "なし",
  normalize_siblings: "同階層を正規化",
  multiply_downstream: "下流へ乗算",
  gated: "ゲート制御",
};

export const relationLayerLabels: Record<RelationLayer, string> = {
  semantic: "意味レイヤー",
  probabilistic: "確率レイヤー",
  influence: "影響レイヤー",
};

export const influenceSignLabels: Record<InfluenceSign, string> = {
  "+": "+ 正方向",
  "-": "- 負方向",
  mixed: "混合",
  unknown: "不明",
};

export const combinationModeLabels: Record<CombinationMode, string> = {
  additive: "加算",
  multiplicative: "乗算",
  override: "上書き",
};

export const sourceTypeLabels: Record<SourceType, string> = {
  idea: "アイデア",
  note: "メモ",
  replay: "牌譜",
  stats: "統計",
  theory: "理論",
};

export const pruningHintLabels: Record<PruningHint, string> = {
  can_prune: "枝刈り可能",
  must_keep_top_k: "上位候補保持",
  hard_gate_candidate: "強制ゲート候補",
  score_only: "スコア専用",
  override_only: "上書き専用",
};

export const pruningActionTypeLabels: Record<PruningActionType, string> = {
  hard_prune: "強制枝刈り",
  soft_downweight: "ソフト減衰",
  hard_lock: "強制ロック",
  soft_lock: "ソフトロック",
  keep_top_k: "上位候補保持",
  freeze_ratio: "比率固定",
  freeze_concentration_band: "集中帯固定",
};

export const averagingSafetyLabels: Record<AveragingSafetyLabel, string> = {
  safe: "安全",
  caution: "注意",
  unsafe: "危険",
};

export const readingChainStepTypeLabels: Record<ReadingChainStepType, string> =
  {
    observation: "観測",
    hypothesis_split: "仮説分岐",
    lock: "ロック",
    pruning: "枝刈り",
    weight_update: "重み更新",
    direction_update: "方向更新",
    observation_request: "観測依頼",
    fallback: "フォールバック",
    compare: "比較",
  };

export const tagLabels: Record<string, string> = {
  "Hard gate": "強制ゲート",
  "Soft score": "ソフトスコア",
  Override: "上書き",
  Fallback: "フォールバック",
  "Rule Builder": "ルール作成",
  "Top-k": "上位候補",
  ambiguity: "曖昧性",
  asymmetric_tail: "非対称テール",
  bimodal: "二峰性",
  "choice-group": "選択候補群",
  concentration: "集中度",
  diffuse: "分散",
  downweight: "弱め",
  fold_risk: "放銃率",
  inference: "推論",
  influence: "影響",
  information_value: "情報価値",
  metric: "指標",
  mixed: "混合",
  multimodal: "多峰性",
  observation: "観測",
  observation_candidate: "観測候補",
  pruning: "枝刈り",
  "pruning-ui": "枝刈り画面",
  rank_ev: "順位期待値",
  safety: "安全度",
  speed: "速度",
  training: "訓練",
  unknown: "不明",
  utility: "有用度",
  value: "打点価値",
  warning: "警告",
  "weight-modifier": "重み補正",
  win_rate: "和了率",
};

export function labelTag(tag: string) {
  return tagLabels[tag] ?? tag;
}
