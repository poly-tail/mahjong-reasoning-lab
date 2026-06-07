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
    description:
      "進行度・聴牌率、打点、待ち・形の良さ、点数状況・行動閾値へ分ける。",
  },
  {
    id: "push_fold",
    label: "押し引き（読み整理）",
    description:
      "押し/守備寄り文脈を読み候補カテゴリとして整理する。行動推奨は出さない。",
  },
  {
    id: "danger_tile",
    label: "危険牌比較",
    description: "危険牌候補、安全度、追加観測を整理する。",
  },
  {
    id: "rescue_rate",
    label: "卓上動態 / 他家介入読み",
    description:
      "脇の和了、放銃、鳴き、安牌供給、流局接近を読み候補として残す。",
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
    description: "候補集中、曖昧性低減、観測コストへの効きを残す。",
  },
  {
    id: "rank_condition",
    label: "条件戦/順位点",
    description: "点棒状況、順位点、局面条件を読みの文脈射影として残す。",
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
        draft(
          "metric",
          "進行度・聴牌率",
          "シャンテン数、聴牌率、先制率、和了到達の近さを集約する。",
          [
            "hand_value_range",
            "progress_tenpai_axis",
            "speed_axis",
            "speed",
            "速度",
            "早さ",
            "metric",
            "influence",
          ],
        ),
        draft(
          "metric",
          "打点",
          "打点は固定値ではなく、レンジ・分布として上振れと尾部リスクまで見る。",
          [
            "hand_value_range",
            "value_axis",
            "value_distribution_axis",
            "value_distribution",
            "score_distribution",
            "value",
            "打点",
            "打点レンジ",
            "打点レンジ推定",
            "metric",
            "influence",
          ],
        ),
        draft(
          "metric",
          "待ち・形の良さ",
          "良形/愚形、待ち候補、危険牌比較、安全度評価への接続を扱う。",
          [
            "hand_value_range",
            "wait_shape_quality_axis",
            "shape_axis",
            "wait_danger_distribution_axis",
            "wait_distribution",
            "danger_tile_distribution",
            "shape",
            "形",
            "待ち",
            "良形",
            "愚形",
            "安全度",
            "metric",
            "influence",
          ],
        ),
        draft(
          "metric",
          "点数状況・行動閾値",
          "点棒状況、順位点、親子、局、巡目、供託、本場が読みの重みや確認優先度にどう効くかを扱う。",
          [
            "hand_value_range",
            "score_situation_threshold_axis",
            "situation_threshold_axis",
            "situation_value",
            "action_threshold",
            "rank_ev",
            "rank_point",
            "external_modifier",
            "turn",
            "dealer",
            "round",
            "score_context",
            "dora",
            "honba",
            "riichi_sticks",
            "条件戦",
            "metric",
            "influence",
          ],
        ),
        draft(
          "heuristic",
          "レンジ更新ルール",
          "観測が4軸のどこを動かしたかを明示してから比較する。",
          ["hand_value_range", "reweight", "heuristic"],
        ),
        draft(
          "question",
          "どの軸が上がったのか？",
          "進行度・聴牌率、打点、待ち・形の良さ、点数状況・行動閾値のどれへ読みが射影されたかを確認する。",
          ["hand_value_range", "review"],
        ),
      ],
      edge_candidates: [
        "観測/仮説 -> 進行度・聴牌率",
        "観測/仮説 -> 打点",
        "観測/仮説 -> 待ち・形の良さ",
        "観測/仮説 -> 点数状況・行動閾値",
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
        draft(
          "heuristic",
          "洗い出し",
          "観測、問い、根拠、シグナルを列挙する。",
          ["collect", "decision_pipeline"],
        ),
        draft(
          "weight_modifier",
          "重み付け",
          "仮説や指標に対して弱い根拠を重みとして足す。",
          ["weight", "decision_pipeline", "weight-modifier"],
        ),
        draft(
          "probability_aggregate",
          "加算/合成",
          "複数の重みや確率を合成する中間状態。",
          ["combine", "decision_pipeline", "probability_tree"],
        ),
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
        draft(
          "lock_controller",
          "比率固定",
          "候補を消さず、分布の比率を固定して比較する。",
          ["node_lock", "freeze_ratio"],
          {
            lock_mode: "freeze_ratio",
            probability_role: "control",
          },
        ),
        draft(
          "distribution_assumption",
          "固定して比較する分布",
          "hard pruneとは別に、比較用の分布仮定として残す。",
          ["node_lock", "distribution"],
          {
            distribution_family: "categorical",
          },
        ),
        draft(
          "question",
          "何を固定しているのか？",
          "候補削除ではなく、確率/戦略分布の固定かを確認する。",
          ["node_lock", "review"],
        ),
      ],
      edge_candidates: ["ロック制御 -> 分布仮定", "分布仮定 -> 比較対象"],
    };
  }

  if (templateId === "pruning") {
    return {
      template_id: templateId,
      source_summary: sourceSummary,
      nodes: [
        draft("concept", "枝刈り", sourceSummary, [
          "pruning",
          "probability_tree",
        ]),
        draft(
          "pruning_suggestion",
          "hard prune候補",
          "候補を削ってよい条件が強い場合だけ使う。",
          ["pruning", "hard_prune"],
          {
            pruning_hints: ["can_prune", "hard_gate_candidate"],
          },
        ),
        draft(
          "weight_adjustment_suggestion",
          "soft downweight候補",
          "消さずに弱め、曖昧性を残す。",
          ["pruning", "downweight", "soft_downweight"],
          {
            pruning_hints: ["score_only"],
          },
        ),
        draft(
          "heuristic",
          "keep top-k",
          "1つに絞らず複数仮説を残す。",
          ["pruning", "keep_top_k"],
          {
            pruning_hints: ["must_keep_top_k"],
            lock_mode: "keep_top_k",
            lock_value: 3,
          },
        ),
      ],
      edge_candidates: ["曖昧性 -> hard prune禁止", "観測 -> downweight候補"],
    };
  }

  return createGenericDraft(templateId, sourceSummary);
}

export function createRescueRateDraft(
  sourceSummary = "卓上動態 / 他家介入読みを短時間窓の候補として整理する。",
): MappingDraftResult {
  return {
    template_id: "rescue_rate",
    source_summary: sourceSummary,
    nodes: [
      draft("concept", "卓上動態 / 他家介入読み", sourceSummary, [
        "rescue_rate",
        "table_dynamics",
        "side_intervention",
        "脇救済率",
        "push_fold",
      ]),
      draft(
        "metric",
        "rescue_rate",
        "短時間窓内に他家介入で局面文脈が変わる可能性を表す読みスコア。",
        [
          "metric",
          "influence",
          "rescue_rate",
          "table_dynamics",
          "side_intervention",
          "脇救済率",
        ],
        {
          thresholds: [
            { name: "低い", value: "0-0.10", note: "ほぼ補正しない" },
            { name: "ややある", value: "0.10-0.20", note: "小さく補正" },
            { name: "高すぎ注意", value: "0.30+", note: "過大評価警告" },
          ],
        },
      ),
      draft(
        "metric",
        "卓上動態の文脈射影",
        "他家介入が候補保持、確認優先度、未配分候補にどう効くかを見る。",
        [
          "metric",
          "influence",
          "table_dynamics",
          "score_situation_threshold_axis",
        ],
      ),
      draft(
        "probability_aggregate",
        "脇介入イベント仮説",
        "脇の和了、放銃、鳴き、安牌供給、流局接近を束で扱う。",
        [
          "rescue_rate",
          "table_dynamics",
          "side_intervention",
          "probability_tree",
          "side_win",
          "side_deal_in",
          "side_call",
          "safe_tile_supply",
          "exhaustive_draw_approach",
        ],
        {
          probability_role: "control",
          distribution_family: "categorical",
        },
      ),
      draft(
        "observation_candidate",
        "他家介入イベント観測",
        "脇の鳴き/和了/放銃/安牌供給/流局接近を見る。",
        ["rescue_rate", "table_dynamics", "observation_candidate"],
        {
          expected_sign_gain: 0.24,
          expected_weight_gain: 0.18,
          observation_cost: 0.22,
          timeliness: 0.8,
        },
      ),
      draft(
        "heuristic",
        "行動推奨に直結しない",
        "他家介入読みは行動判断の免罪符ではなく、候補確率・未配分・例外候補の整理に使う。",
        ["rescue_rate", "table_dynamics", "warning", "heuristic"],
      ),
    ],
    edge_candidates: [
      "卓上動態読み -> 未配分候補の提案",
      "他家介入仮説 -> 点数状況・行動閾値 は context projection",
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
      draft("scenario", "押し引き文脈の読み整理", sourceSummary, [
        "push_fold",
        "押し引き",
        "reading_context",
      ]),
      draft(
        "metric",
        "攻撃寄り文脈",
        "和了率・打点・順位点が読み候補の保持方針にどう効くかを見る。",
        ["metric", "push_value", "rank_ev", "reading_context"],
      ),
      draft(
        "metric",
        "守備寄り文脈",
        "放銃率と放銃時損失を、行動推奨ではなく読みの文脈として分けて見る。",
        ["metric", "fold_risk", "safety", "reading_context"],
      ),
      draft(
        "evidence",
        "読み整理メモ",
        "Phase1では押す/引くを決めず、候補確率・未配分・例外候補への影響だけを残す。",
        ["review", "push_fold"],
      ),
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
      draft(
        "observation_candidate",
        "追加で見るべき安全情報",
        "現物、筋、壁、手出し、鳴き後変化を確認する。",
        ["observation_candidate", "danger_tile"],
      ),
    ],
    reading_utility: [
      draft("metric", "読みの有用度", sourceSummary, [
        "reading",
        "utility",
        "teaching",
      ]),
      draft(
        "evidence",
        "この読みで何が変わったか",
        "選択肢比較、枝刈り、曖昧性解消、追加観測への効きを残す。",
        ["reading_utility", "review"],
      ),
    ],
    rank_condition: [
      draft("condition", "条件戦/順位点補正", sourceSummary, [
        "score_situation_threshold_axis",
        "action_threshold",
        "rank_ev",
        "rank_point",
        "score_context",
      ]),
      draft(
        "metric",
        "点数状況・行動閾値",
        "点棒状況と順位点が読みの重みや確認優先度にどう効くかを見る。",
        [
          "metric",
          "score_situation_threshold_axis",
          "action_threshold",
          "rank_ev",
          "rank_point",
          "score_context",
          "順位期待値",
        ],
      ),
    ],
  };

  return {
    template_id: templateId,
    source_summary: sourceSummary,
    nodes: genericByTemplate[templateId],
    edge_candidates: [
      "観測/仮説 -> 指標",
      "指標 -> 判断",
      "曖昧性 -> 追加観測",
    ],
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
  return normalized.length > 140
    ? `${normalized.slice(0, 140)}...`
    : normalized;
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
