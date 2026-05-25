import type {
  KnowledgeEdge,
  KnowledgeNode,
  LockMode,
  NodeType,
  ProbabilityRole,
  PruningHint,
  RelationLayer,
  WorkspaceDocument,
} from "./schema";

export const domainAreas = [
  "hand_value_range",
  "push_fold",
  "danger_tile",
  "reading",
  "probability_tree",
  "pruning",
  "node_lock",
  "rescue_rate",
  "rank_ev",
  "teaching",
  "review",
] as const;

export const handValueAxes = [
  { id: "value_axis", label: "打点" },
  { id: "speed_axis", label: "早さ" },
  { id: "shape_axis", label: "形" },
] as const;

export const externalModifiers = [
  { id: "turn", label: "巡目" },
  { id: "dealer", label: "親子" },
  { id: "score_context", label: "点棒状況" },
  { id: "dora", label: "ドラ" },
  { id: "honba", label: "本場" },
  { id: "riichi_sticks", label: "供託" },
  { id: "rank_point", label: "順位点" },
  { id: "opponent_style", label: "相手傾向" },
  { id: "table_context", label: "局面条件" },
] as const;

export const decisionPipelineSteps = [
  { id: "collect", label: "洗い出し" },
  { id: "weight", label: "重み付け" },
  { id: "combine", label: "加算/合成" },
  { id: "compare", label: "比較" },
  { id: "choose", label: "選択" },
  { id: "review", label: "反省" },
] as const;

export const probabilityOperations = [
  "condition",
  "reweight",
  "normalize",
  "prune",
  "downweight",
  "lock",
  "keep_top_k",
  "freeze_ratio",
] as const;

export const rescueEvents = [
  { id: "side_win", label: "脇の和了" },
  { id: "side_deal_in", label: "脇の放銃" },
  { id: "side_call", label: "脇の鳴き" },
  { id: "safe_tile_supply", label: "安牌供給" },
  { id: "exhaustive_draw_approach", label: "流局接近" },
  { id: "opponent_hand_deceleration", label: "相手の速度低下" },
] as const;

export type DomainArea = (typeof domainAreas)[number];
export type DecisionPipelineStepId = (typeof decisionPipelineSteps)[number]["id"];
export type DomainLensId =
  | "all"
  | "hand_value"
  | "push_fold"
  | "danger_tile"
  | "probability_tree"
  | "pruning"
  | "node_lock"
  | "rescue_rate"
  | "teaching"
  | "review";

export type DomainLensDefinition = {
  id: DomainLensId;
  label: string;
  tags: string[];
  nodeTypes?: NodeType[];
  probabilityRoles?: ProbabilityRole[];
  relationLayers?: RelationLayer[];
  pruningHints?: PruningHint[];
  lockModes?: LockMode[];
};

export const domainLensDefinitions: DomainLensDefinition[] = [
  {
    id: "all",
    label: "全部",
    tags: [],
  },
  {
    id: "hand_value",
    label: "手牌価値",
    tags: [
      "hand_value_range",
      "value_axis",
      "speed_axis",
      "shape_axis",
      "value",
      "speed",
      "shape",
      "打点",
      "速度",
      "早さ",
      "形",
      "打点レンジ推定",
      "手牌価値",
    ],
    nodeTypes: ["metric", "condition", "heuristic", "weight_modifier"],
  },
  {
    id: "push_fold",
    label: "押し引き",
    tags: ["push_fold", "押し引き", "fold_risk", "push_value", "rank_ev"],
    nodeTypes: ["scenario", "action", "metric", "hypothesis"],
  },
  {
    id: "danger_tile",
    label: "安全度",
    tags: ["danger_tile", "safety", "安全度", "安全度評価", "fold_risk"],
    nodeTypes: ["metric", "observation", "signal", "condition"],
  },
  {
    id: "probability_tree",
    label: "確率木",
    tags: ["probability_tree", "choice-group", "inference", "確率木"],
    nodeTypes: ["choice_group", "branch", "hypothesis", "probability_aggregate"],
    probabilityRoles: ["prior", "posterior", "control"],
    relationLayers: ["probabilistic"],
  },
  {
    id: "pruning",
    label: "枝刈り",
    tags: ["pruning", "downweight", "keep_top_k", "枝刈り"],
    nodeTypes: ["pruning_suggestion", "weight_adjustment_suggestion"],
    pruningHints: [
      "can_prune",
      "must_keep_top_k",
      "hard_gate_candidate",
      "score_only",
      "override_only",
    ],
  },
  {
    id: "node_lock",
    label: "ロック",
    tags: ["node_lock", "lock", "freeze_ratio", "ロック"],
    nodeTypes: ["lock_controller", "distribution_assumption"],
    lockModes: [
      "hard",
      "soft",
      "keep_top_k",
      "freeze_ratio",
      "hard_lock",
      "soft_lock",
      "freeze_concentration_band",
    ],
  },
  {
    id: "rescue_rate",
    label: "脇救済",
    tags: [
      "rescue_rate",
      "side_win",
      "side_deal_in",
      "side_call",
      "safe_tile_supply",
      "exhaustive_draw_approach",
      "opponent_hand_deceleration",
      "脇救済率",
    ],
    nodeTypes: ["metric", "probability_aggregate", "observation_candidate"],
  },
  {
    id: "teaching",
    label: "教育",
    tags: ["teaching", "training", "教育", "訓練", "学習ポイント"],
    nodeTypes: ["evidence", "heuristic", "question"],
  },
  {
    id: "review",
    label: "反省",
    tags: ["review", "レビュー", "反省", "検証"],
    nodeTypes: ["evidence", "question", "ambiguity_marker"],
  },
];

export function getDomainLensDefinition(id: DomainLensId) {
  return domainLensDefinitions.find((lens) => lens.id === id);
}

export function createDomainLensSelection(
  lensId: DomainLensId,
  doc: WorkspaceDocument,
) {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();

  if (lensId === "all") {
    for (const node of doc.nodes) nodeIds.add(node.id);
    for (const edge of doc.edges) edgeIds.add(edge.id);
    return { nodeIds, edgeIds };
  }

  for (const node of doc.nodes) {
    if (nodeMatchesDomainLens(node, lensId)) nodeIds.add(node.id);
  }

  for (const edge of doc.edges) {
    if (
      edgeMatchesDomainLens(edge, lensId) ||
      nodeIds.has(edge.source) ||
      nodeIds.has(edge.target)
    ) {
      if (edgeMatchesDomainLens(edge, lensId)) {
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
      }
      if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
        edgeIds.add(edge.id);
      }
    }
  }

  return { nodeIds, edgeIds };
}

export function nodeMatchesDomainLens(
  node: KnowledgeNode,
  lensId: DomainLensId,
) {
  const lens = getDomainLensDefinition(lensId);
  if (!lens) return true;
  if (lens.id === "all") return true;

  const lowerTags = node.tags.map((tag) => tag.toLowerCase());
  const searchable = [
    node.title,
    node.summary,
    node.description,
    node.notes,
    node.stage,
    ...node.tags,
    ...node.applicability,
  ]
    .join(" ")
    .toLowerCase();

  const tagMatch = lens.tags.some((tag) => {
    const normalized = tag.toLowerCase();
    if (/^[a-z0-9_-]+$/.test(normalized)) {
      return lowerTags.includes(normalized);
    }
    return searchable.includes(normalized);
  });
  const structuralTypeLens = [
    "probability_tree",
    "pruning",
    "node_lock",
    "teaching",
    "review",
  ].includes(lens.id);
  const typeMatch =
    Boolean(lens.nodeTypes?.includes(node.type)) &&
    (tagMatch || structuralTypeLens);
  const readingUtilityMatch =
    (lens.id === "teaching" || lens.id === "review") &&
    node.reading_utility_ids.length > 0;

  return (
    tagMatch ||
    typeMatch ||
    Boolean(lens.probabilityRoles?.includes(node.probability_role)) ||
    Boolean(
      lens.pruningHints?.some((hint) => node.pruning_hints.includes(hint)),
    ) ||
    Boolean(lens.lockModes?.includes(node.lock_mode)) ||
    readingUtilityMatch
  );
}

export function edgeMatchesDomainLens(
  edge: KnowledgeEdge,
  lensId: DomainLensId,
) {
  const lens = getDomainLensDefinition(lensId);
  if (!lens) return true;
  if (lens.id === "all") return true;

  const searchable = [
    edge.type,
    edge.label,
    edge.notes,
    edge.note,
    edge.relation_layer,
    edge.sign,
    edge.context_gate,
  ]
    .flat()
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return (
    Boolean(lens.relationLayers?.includes(edge.relation_layer)) ||
    lens.tags.some((tag) => {
      const normalized = tag.toLowerCase();
      if (/^[a-z0-9_-]+$/.test(normalized)) return false;
      return searchable.includes(normalized);
    }) ||
    (lens.id === "pruning" &&
      (edge.type === "blocks_pruning" || edge.type === "enables_pruning")) ||
    (lens.id === "node_lock" && searchable.includes("lock"))
  );
}

export function labelDomainTag(tag: string) {
  const area = domainAreas.find((item) => item === tag);
  if (area) return area;
  return tag;
}
