import type {
  DistributionFamily,
  LockMode,
  NodeType,
  ProbabilityRole,
  PruningHint,
  RelationLayer,
} from "./schema";

type DraftThreshold = {
  name: string;
  value: string;
  note: string;
};

export type MappingTemplateId =
  | "hand_value_range"
  | "push_fold"
  | "danger_tile"
  | "rescue_rate"
  | "node_lock"
  | "pruning"
  | "reading_utility"
  | "rank_condition"
  | "intermediate_state";

export type MappingDraftNode = {
  draft_id: string;
  title: string;
  type: NodeType;
  tags: string[];
  summary: string;
  description?: string;
  confidence?: number;
  applicability?: string[];
  formulas?: string[];
  thresholds?: DraftThreshold[];
  pruning_hints?: PruningHint[];
  probability_role?: ProbabilityRole;
  base_weight?: number;
  dynamic_weight?: number;
  prior_probability?: number;
  posterior_probability?: number;
  lock_mode?: LockMode;
  lock_value?: number;
  resolves_targets?: string[];
  expected_sign_gain?: number;
  expected_weight_gain?: number;
  expected_margin_gain?: number;
  pruning_safety_change?: number;
  observation_cost?: number;
  timeliness?: number;
  distribution_family?: DistributionFamily;
  relation_layer_candidate?: RelationLayer;
  pruning_hint_text?: string;
};

export type MappingTemplate = {
  id: MappingTemplateId;
  label: string;
  description: string;
};

export type MappingDraftResult = {
  template_id: MappingTemplateId;
  source_summary: string;
  nodes: MappingDraftNode[];
  edge_candidates: string[];
};

export const mappingTemplates: MappingTemplate[] = [
  {
    id: "hand_value_range",
    label: "手牌価値レンジ",
    description: "打点・早さ・形と外部補正を指標へ分ける。",
  },
  {
    id: "push_fold",
    label: "押し引き",
    description: "押し価値、放銃リスク、順位価値の比較へ落とす。",
  },
  {
    id: "danger_tile",
    label: "危険牌比較",
    description: "危険牌候補、安全度、追加観測を整理する。",
  },
  {
    id: "rescue_rate",
    label: "脇救済率",
    description: "短時間窓の救済イベント束と上限レンジを作る。",
  },
  {
    id: "node_lock",
    label: "ノードロック",
    description: "候補を消さずに分布や比率を固定する操作へ分ける。",
  },
  {
    id: "pruning",
    label: "枝刈り",
    description: "hard prune、downweight、keep top-kを区別する。",
  },
  {
    id: "reading_utility",
    label: "読みの有用性",
    description: "判断を動かした量、曖昧性低減、観測コストを残す。",
  },
  {
    id: "rank_condition",
    label: "条件戦/順位点",
    description: "点棒状況、順位点、局面条件を外部補正にする。",
  },
  {
    id: "intermediate_state",
    label: "中間状態",
    description: "洗い出しから反省までの判断プロセスへ割り当てる。",
  },
];

export function createMappingDraft(
  templateId: MappingTemplateId,
  sourceText: string,
): MappingDraftResult {
  const sourceSummary = summarizeSource(sourceText);

  if (templateId === "hand_value_range") {
    return {
      template_id: templateId,
      source_summary: sourceSummary,
      nodes: [
        draft("concept", "手牌価値レンジ理論", sourceSummary, [
          "hand_value_range",
          "手牌価値",
          "theory",
        ]),
        draft("metric", "打点レンジ", "打点が上がった/下がった理由を集約する。", [
          "hand_value_range",
          "value_axis",
          "value",
          "打点",
          "metric",
          "influence",
        ]),
        draft("metric", "速度レンジ", "先制性、テンパイ近さ、鳴き速度を集約する。", [
          "hand_value_range",
          "speed_axis",
          "speed",
          "早さ",
          "metric",
          "influence",
        ]),
        draft("metric", "形レンジ", "良形/愚形/受け入れの幅を集約する。", [
          "hand_value_range",
          "shape_axis",
          "shape",
          "形",
          "metric",
          "influence",
        ]),
        draft("condition", "外部補正", "巡目、親子、点棒、ドラ、供託、本場、順位点を条件として扱う。", [
          "external_modifier",
          "turn",
          "dealer",
          "score_context",
          "dora",
          "honba",
          "riichi_sticks",
          "rank_point",
        ]),
        draft("heuristic", "レンジ更新ルール", "観測がどの軸を動かしたかを明示してから比較する。", [
          "hand_value_range",
          "reweight",
          "heuristic",
        ]),
        draft("question", "どの軸が上がったのか？", "打点・速度・形のどれが判断を動かしたかを確認する。", [
          "hand_value_range",
          "review",
        ]),
      ],
      edge_candidates: [
        "観測/仮説 -> 打点レンジ",
        "観測/仮説 -> 速度レンジ",
        "観測/仮説 -> 形レンジ",
      ],
    };
  }

  if (templateId === "rescue_rate") {
    return createRescueRateDraft(sourceSummary);
  }

  if (templateId === "intermediate_state") {
    return {
      template_id: templateId,
      source_summary: sourceSummary,
      nodes: [
        draft("concept", "中間状態モデル", sourceSummary, [
          "intermediate_state",
          "decision_pipeline",
        ]),
        draft("heuristic", "洗い出し", "観測、問い、根拠、シグナルを列挙する。", [
          "collect",
          "decision_pipeline",
        ]),
        draft("weight_modifier", "重み付け", "仮説や指標に対して弱い根拠を重みとして足す。", [
          "weight",
          "decision_pipeline",
          "weight-modifier",
        ]),
        draft("probability_aggregate", "加算/合成", "複数の重みや確率を合成する中間状態。", [
          "combine",
          "decision_pipeline",
          "probability_tree",
        ]),
        draft("scenario", "比較", "候補同士を同じ軸で比較する。", [
          "compare",
          "decision_pipeline",
        ]),
        draft("action", "選択", "選んだ判断と採用理由を残す。", [
          "choose",
          "decision_pipeline",
        ]),
        draft("evidence", "反省/検証ログ", "判断後に何が効いたかを検証する。", [
          "review",
          "decision_pipeline",
          "teaching",
        ]),
      ],
      edge_candidates: [
        "洗い出し -> 重み付け",
        "重み付け -> 加算/合成",
        "加算/合成 -> 比較",
        "比較 -> 選択",
        "選択 -> 反省/検証ログ",
      ],
    };
  }

  if (templateId === "node_lock") {
    return {
      template_id: templateId,
      source_summary: sourceSummary,
      nodes: [
        draft("concept", "ノードロック", sourceSummary, [
          "node_lock",
          "lock",
          "probability_tree",
        ]),
        draft("lock_controller", "比率固定", "候補を消さず、分布の比率を固定して比較する。", [
          "node_lock",
          "freeze_ratio",
        ], {
          lock_mode: "freeze_ratio",
          probability_role: "control",
        }),
        draft("distribution_assumption", "固定して比較する分布", "hard pruneとは別に、比較用の分布仮定として残す。", [
          "node_lock",
          "distribution",
        ], {
          distribution_family: "categorical",
        }),
        draft("question", "何を固定しているのか？", "候補削除ではなく、確率/戦略分布の固定かを確認する。", [
          "node_lock",
          "review",
        ]),
      ],
      edge_candidates: ["ロック制御 -> 分布仮定", "分布仮定 -> 比較対象"],
    };
  }

  if (templateId === "pruning") {
    return {
      template_id: templateId,
      source_summary: sourceSummary,
      nodes: [
        draft("concept", "枝刈り", sourceSummary, ["pruning", "probability_tree"]),
        draft("pruning_suggestion", "hard prune候補", "候補を削ってよい条件が強い場合だけ使う。", [
          "pruning",
          "hard_prune",
        ], {
          pruning_hints: ["can_prune", "hard_gate_candidate"],
        }),
        draft("weight_adjustment_suggestion", "soft downweight候補", "消さずに弱め、曖昧性を残す。", [
          "pruning",
          "downweight",
          "soft_downweight",
        ], {
          pruning_hints: ["score_only"],
        }),
        draft("heuristic", "keep top-k", "1つに絞らず複数仮説を残す。", [
          "pruning",
          "keep_top_k",
        ], {
          pruning_hints: ["must_keep_top_k"],
          lock_mode: "keep_top_k",
          lock_value: 3,
        }),
      ],
      edge_candidates: ["曖昧性 -> hard prune禁止", "観測 -> downweight候補"],
    };
  }

  return createGenericDraft(templateId, sourceSummary);
}

export function createRescueRateDraft(
  sourceSummary = "脇救済率を短時間窓の外部補正として整理する。",
): MappingDraftResult {
  return {
    template_id: "rescue_rate",
    source_summary: sourceSummary,
    nodes: [
      draft("concept", "脇救済率", sourceSummary, [
        "rescue_rate",
        "脇救済率",
        "push_fold",
      ]),
      draft("metric", "rescue_rate", "短時間窓内に不利局面が緩和される概算確率。", [
        "metric",
        "influence",
        "rescue_rate",
        "脇救済率",
      ], {
        thresholds: [
          { name: "低い", value: "0-0.10", note: "ほぼ補正しない" },
          { name: "ややある", value: "0.10-0.20", note: "小さく補正" },
          { name: "高すぎ注意", value: "0.30+", note: "過大評価警告" },
        ],
      }),
      draft("metric", "fold_risk", "危険牌選択時の放銃リスク。", [
        "metric",
        "influence",
        "fold_risk",
        "push_fold",
      ]),
      draft("probability_aggregate", "脇救済イベント束", "脇の和了、放銃、鳴き、安牌供給、流局接近を束で扱う。", [
        "rescue_rate",
        "probability_tree",
        "side_win",
        "side_deal_in",
        "side_call",
        "safe_tile_supply",
        "exhaustive_draw_approach",
      ], {
        probability_role: "control",
        distribution_family: "categorical",
      }),
      draft("observation_candidate", "脇の救済イベント観測", "脇の鳴き/和了/放銃/安牌供給/流局接近を見る。", [
        "rescue_rate",
        "observation_candidate",
      ], {
        expected_sign_gain: 0.24,
        expected_weight_gain: 0.18,
        observation_cost: 0.22,
        timeliness: 0.8,
      }),
      draft("heuristic", "上限レンジで見積もる", "救済イベントを独立と決めつけず、時間窓と上限で制御する。", [
        "rescue_rate",
        "warning",
        "heuristic",
      ]),
    ],
    edge_candidates: [
      "脇救済率 -> fold_risk は sign: -",
      "脇救済率 -> push_value は sign: +",
      "confidenceは控えめにし、context_gateに時間窓を入れる",
    ],
  };
}

type GenericTemplateId = Exclude<
  MappingTemplateId,
  | "hand_value_range"
  | "rescue_rate"
  | "intermediate_state"
  | "node_lock"
  | "pruning"
>;

function createGenericDraft(
  templateId: GenericTemplateId,
  sourceSummary: string,
): MappingDraftResult {
  const genericByTemplate: Record<GenericTemplateId, MappingDraftNode[]> = {
    push_fold: [
      draft("scenario", "押し引き判断", sourceSummary, ["push_fold", "押し引き"]),
      draft("metric", "push_value", "押す価値を和了率・打点・順位点で見る。", [
        "metric",
        "push_value",
        "rank_ev",
      ]),
      draft("metric", "fold_risk", "放銃率と放銃時損失を分けて見る。", [
        "metric",
        "fold_risk",
        "safety",
      ]),
      draft("action", "押す/引くの選択", "比較後に採用した判断を残す。", [
        "choose",
        "push_fold",
      ]),
    ],
    danger_tile: [
      draft("scenario", "危険牌比較", sourceSummary, [
        "danger_tile",
        "安全度評価",
      ]),
      draft("metric", "安全度", "各候補牌の安全側評価。", [
        "metric",
        "safety",
        "danger_tile",
      ]),
      draft("observation_candidate", "追加で見るべき安全情報", "現物、筋、壁、手出し、鳴き後変化を確認する。", [
        "observation_candidate",
        "danger_tile",
      ]),
    ],
    reading_utility: [
      draft("metric", "読みの有用度", sourceSummary, [
        "reading",
        "utility",
        "teaching",
      ]),
      draft("evidence", "この読みで何が変わったか", "選択肢比較、枝刈り、曖昧性解消、追加観測への効きを残す。", [
        "reading_utility",
        "review",
      ]),
    ],
    rank_condition: [
      draft("condition", "条件戦/順位点補正", sourceSummary, [
        "rank_ev",
        "rank_point",
        "score_context",
      ]),
      draft("metric", "順位期待値", "点棒状況と順位点の外部補正。", [
        "metric",
        "rank_ev",
      ]),
    ],
  };

  return {
    template_id: templateId,
    source_summary: sourceSummary,
    nodes: genericByTemplate[templateId],
    edge_candidates: ["観測/仮説 -> 指標", "指標 -> 判断", "曖昧性 -> 追加観測"],
  };
}

function draft(
  type: NodeType,
  title: string,
  summary: string,
  tags: string[],
  overrides: Partial<MappingDraftNode> = {},
): MappingDraftNode {
  return {
    draft_id: `${type}_${slug(title)}`,
    type,
    title,
    summary,
    description: overrides.description ?? summary,
    tags: unique(tags),
    confidence: overrides.confidence ?? 0.58,
    applicability: overrides.applicability ?? [],
    formulas: overrides.formulas ?? [],
    thresholds: overrides.thresholds ?? [],
    pruning_hints: overrides.pruning_hints ?? [],
    probability_role: overrides.probability_role ?? "none",
    base_weight: overrides.base_weight,
    dynamic_weight: overrides.dynamic_weight,
    prior_probability: overrides.prior_probability,
    posterior_probability: overrides.posterior_probability,
    lock_mode: overrides.lock_mode ?? "none",
    lock_value: overrides.lock_value,
    resolves_targets: overrides.resolves_targets ?? [],
    expected_sign_gain: overrides.expected_sign_gain,
    expected_weight_gain: overrides.expected_weight_gain,
    expected_margin_gain: overrides.expected_margin_gain,
    pruning_safety_change: overrides.pruning_safety_change,
    observation_cost: overrides.observation_cost,
    timeliness: overrides.timeliness,
    distribution_family: overrides.distribution_family,
    relation_layer_candidate: overrides.relation_layer_candidate ?? "semantic",
    pruning_hint_text: overrides.pruning_hint_text ?? "",
  };
}

function summarizeSource(sourceText: string) {
  const normalized = sourceText.trim().replace(/\s+/g, " ");
  if (!normalized) return "貼り付けた考察から作成した下書き。";
  return normalized.length > 140 ? `${normalized.slice(0, 140)}...` : normalized;
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function slug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}
