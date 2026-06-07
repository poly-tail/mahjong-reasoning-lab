import { createId } from "./factory";
import {
  createExceptionCandidateDraft,
  type ResidualMassBucket,
} from "./residualMass";
import type { MappingDraftNode } from "./mappingTemplates";
import type { AxisImpactDraft, ChoiceCandidateDraft } from "./readingNumerics";

export type ReadingDrawerCategory =
  | "call_intent"
  | "value_pattern"
  | "progress_pattern"
  | "wait_shape"
  | "danger_safety"
  | "score_threshold"
  | "table_dynamics"
  | "player_tendency"
  | "exception_noise";

export type ReadingDrawerItem = {
  id: string;
  category: ReadingDrawerCategory;
  label: string;
  description: string;
  default_probability?: number;
  axis_impacts?: AxisImpactDraft[];
  tags: string[];
  caution?: string;
};

export const readingDrawerCategories: {
  id: ReadingDrawerCategory;
  label: string;
  description: string;
}[] = [
  {
    id: "call_intent",
    label: "副露意図",
    description: "鳴きの目的を速度、打点、牽制、形テンなどに分解する。",
  },
  {
    id: "value_pattern",
    label: "打点パターン",
    description: "ドラ、赤、染め、役牌など打点側の読み漏れを拾う。",
  },
  {
    id: "progress_pattern",
    label: "進行度",
    description: "先制、1シャンテン、巡目に対する遅速を扱う。",
  },
  {
    id: "wait_shape",
    label: "待ち・形",
    description: "良形、愚形、くっつき、変化残りなど形の未確定部分。",
  },
  {
    id: "danger_safety",
    label: "危険牌・安全度",
    description: "筋、壁、現物などを読み候補・観測候補として残す。",
  },
  {
    id: "score_threshold",
    label: "点数状況",
    description: "順位点、オーラス条件、供託、本場を文脈射影として残す。",
  },
  {
    id: "table_dynamics",
    label: "卓上動態",
    description: "脇の和了、放銃、鳴きによる安牌供給、流局接近。",
  },
  {
    id: "player_tendency",
    label: "相手傾向",
    description: "鳴きの軽さ、打点寄せ、守備寄せ、ブラフ傾向。",
  },
  {
    id: "exception_noise",
    label: "例外・ノイズ",
    description: "空切り、手順偽装、観測ミス、レア役などの残差候補。",
  },
];

export const readingDrawerItems: ReadingDrawerItem[] = [
  item(
    "call_intent",
    "速度副露",
    "和了到達やテンパイ率を上げるための鳴き。",
    0.08,
    [progress("+", 0.18)],
  ),
  item(
    "call_intent",
    "役牌バック",
    "役牌後付けや役牌重なりを見た副露。",
    0.07,
    [value("+", 0.12), wait("mixed", 0.08)],
  ),
  item(
    "call_intent",
    "染め移行",
    "色寄せの途中段階。打点上昇と速度低下が同時に起きやすい。",
    0.1,
    [value("+", 0.22), progress("mixed", 0.1)],
  ),
  item(
    "call_intent",
    "形式テンパイ",
    "終盤のノーテン罰符回避や形式聴牌狙い。",
    0.06,
    [progress("+", 0.12), value("-", 0.08)],
  ),
  item(
    "call_intent",
    "安牌確保副露",
    "手牌進行よりも安全牌や守備余地を確保する鳴き。",
    0.05,
    [wait("mixed", 0.08)],
  ),
  item(
    "call_intent",
    "牽制/ブラフ",
    "本線確率を上げすぎないために残す牽制・ブラフ候補。",
    0.04,
    [value("unknown", 0.05)],
    "hard prune前に相手傾向と河の一貫性を見る。",
  ),

  item(
    "value_pattern",
    "ドラ絡み",
    "ドラ周辺やドラ色から打点尾部を残す。",
    0.08,
    [value("+", 0.2)],
  ),
  item("value_pattern", "赤絡み", "赤5や赤受けで実打点が上振れる候補。", 0.05, [
    value("+", 0.14),
  ]),
  item("value_pattern", "染め", "色寄せによる打点上昇と待ちの偏り。", 0.1, [
    value("+", 0.22),
    wait("mixed", 0.08),
  ]),
  item("value_pattern", "トイトイ", "対子系に寄った鳴き打点候補。", 0.06, [
    value("+", 0.16),
    wait("-", 0.08),
  ]),
  item("value_pattern", "チャンタ", "端牌・字牌寄りのレア寄せ候補。", 0.04, [
    value("+", 0.1),
    wait("-", 0.08),
  ]),
  item(
    "value_pattern",
    "役牌重なり",
    "役牌対子/暗刻からの打点・速度候補。",
    0.07,
    [value("+", 0.12), progress("+", 0.1)],
  ),
  item(
    "value_pattern",
    "親番高打点",
    "親の連荘価値込みで打点文脈が強くなる候補。",
    0.06,
    [value("+", 0.16), threshold("+", 0.12)],
  ),

  item(
    "progress_pattern",
    "先制テンパイ",
    "先にテンパイしている読みを残す。",
    0.09,
    [progress("+", 0.22)],
  ),
  item(
    "progress_pattern",
    "1シャンテン",
    "テンパイ手前で反撃余地がある候補。",
    0.08,
    [progress("+", 0.14)],
  ),
  item(
    "progress_pattern",
    "まだ遠い",
    "進行度が低く、打点や守備意図を別に見る候補。",
    0.06,
    [progress("-", 0.16)],
  ),
  item(
    "progress_pattern",
    "鳴きで急加速",
    "鳴き後にテンパイ率が急に上がる形。",
    0.08,
    [progress("+", 0.2)],
  ),
  item(
    "progress_pattern",
    "巡目に対して遅い",
    "巡目との比較で本線化しすぎを抑える候補。",
    0.05,
    [progress("-", 0.14)],
  ),

  item(
    "wait_shape",
    "良形テンパイ",
    "両面以上のテンパイとして残す候補。",
    0.07,
    [wait("+", 0.18)],
  ),
  item(
    "wait_shape",
    "愚形テンパイ",
    "愚形で和了率や反撃余地が落ちる候補。",
    0.07,
    [wait("-", 0.18)],
  ),
  item("wait_shape", "くっつき", "未完成だが変化余地が大きい候補。", 0.06, [
    wait("mixed", 0.14),
  ]),
  item("wait_shape", "縦受け", "対子・暗刻化による変化や役牌絡み。", 0.05, [
    wait("mixed", 0.1),
  ]),
  item(
    "wait_shape",
    "変化残り",
    "現在形だけでなく次巡以降の改善を残す。",
    0.05,
    [wait("+", 0.1)],
  ),
  item(
    "wait_shape",
    "待ち候補不明",
    "観測不足で待ち形を断定しないための未知候補。",
    0.08,
    [wait("unknown", 0.16)],
    "安全度評価を確定しすぎない。",
  ),

  item("danger_safety", "無筋危険牌", "危険牌比較で残す強い危険候補。", 0.06, [
    wait("-", 0.1),
  ]),
  item(
    "danger_safety",
    "片筋",
    "安全とも危険とも決めきれない比較候補。",
    0.04,
    [wait("mixed", 0.08)],
  ),
  item("danger_safety", "壁", "壁情報による安全度上昇候補。", 0.04, [
    wait("+", 0.08),
  ]),
  item(
    "danger_safety",
    "ワンチャンス",
    "安全度を少し上げるが過信しない候補。",
    0.04,
    [wait("mixed", 0.08)],
  ),
  item("danger_safety", "現物", "守備寄せの文脈を強める安全候補。", 0.05, [
    threshold("+", 0.08),
  ]),
  item(
    "danger_safety",
    "スジ引っかけ",
    "筋を安全扱いしすぎない例外候補。",
    0.04,
    [wait("unknown", 0.08)],
  ),
  item("danger_safety", "間4軒", "安全度評価の過大化を抑える候補。", 0.03, [
    wait("mixed", 0.07),
  ]),

  item(
    "score_threshold",
    "トップ目維持",
    "リード維持で危険読みを軽く見ない局面。",
    0.05,
    [threshold("-", 0.14)],
  ),
  item(
    "score_threshold",
    "ラス回避",
    "放銃回避や着順価値で閾値が変わる局面。",
    0.06,
    [threshold("mixed", 0.16)],
  ),
  item(
    "score_threshold",
    "親番維持",
    "親番の連荘価値で確認優先度が変わる候補。",
    0.06,
    [threshold("+", 0.14)],
  ),
  item(
    "score_threshold",
    "オーラス条件",
    "着順条件で必要打点や候補保持方針が変わる候補。",
    0.06,
    [threshold("mixed", 0.18)],
  ),
  item(
    "score_threshold",
    "供託回収",
    "供託により和了価値が上がる候補。",
    0.04,
    [threshold("+", 0.08)],
  ),
  item(
    "score_threshold",
    "本場価値",
    "本場込みの和了価値文脈を残す候補。",
    0.04,
    [threshold("+", 0.08)],
  ),

  item(
    "table_dynamics",
    "他家介入仮説",
    "脇の和了/放銃で局面文脈が変わる候補。",
    0.06,
    [threshold("mixed", 0.14)],
  ),
  item(
    "table_dynamics",
    "脇の和了",
    "対象以外の和了で局面が終了する可能性。",
    0.05,
    [threshold("mixed", 0.1)],
  ),
  item(
    "table_dynamics",
    "脇の放銃",
    "対象以外の放銃で点数状況が変わる候補。",
    0.04,
    [threshold("mixed", 0.1)],
  ),
  item(
    "table_dynamics",
    "鳴きによる安牌供給",
    "他家の鳴きで安全牌が増える候補。",
    0.04,
    [wait("+", 0.07)],
  ),
  item(
    "table_dynamics",
    "流局接近",
    "流局までの距離でテンパイ料や安全度が変わる候補。",
    0.05,
    [progress("mixed", 0.08), threshold("mixed", 0.08)],
  ),

  item(
    "player_tendency",
    "鳴きが軽い",
    "軽い仕掛けを高打点や本線に寄せすぎない。",
    0.06,
    [progress("+", 0.1), value("-", 0.08)],
  ),
  item(
    "player_tendency",
    "打点寄せ",
    "速度より打点を重視する相手傾向。",
    0.06,
    [value("+", 0.14)],
  ),
  item(
    "player_tendency",
    "守備寄せ",
    "攻撃本線の過大評価を抑える傾向。",
    0.05,
    [progress("-", 0.1)],
  ),
  item(
    "player_tendency",
    "ブラフ多め",
    "観測と打牌意図のズレを残す傾向。",
    0.05,
    [value("unknown", 0.08)],
  ),
  item(
    "player_tendency",
    "反撃多め",
    "反撃発生で安全度や進行度が変わる候補。",
    0.05,
    [progress("+", 0.09), threshold("+", 0.08)],
  ),

  item(
    "exception_noise",
    "空切り",
    "手出し/ツモ切り読みを崩す例外。",
    0.04,
    [wait("unknown", 0.07)],
    "観測ミスと区別して低確率で残す。",
  ),
  item(
    "exception_noise",
    "手順偽装",
    "手順から本線を断定しすぎないための例外。",
    0.04,
    [value("unknown", 0.07)],
  ),
  item(
    "exception_noise",
    "観測ミス",
    "見落としや記録漏れを未知バッファに残す。",
    0.05,
    [wait("unknown", 0.08)],
  ),
  item("exception_noise", "記憶違い", "局面再現の不確実性を表す候補。", 0.04, [
    progress("unknown", 0.06),
  ]),
  item(
    "exception_noise",
    "河のノイズ",
    "河からの意図推定を弱めるノイズ。",
    0.05,
    [wait("mixed", 0.07)],
  ),
  item("exception_noise", "レア役", "低頻度だが枝刈り前に残す役候補。", 0.03, [
    value("+", 0.09),
  ]),
  item(
    "exception_noise",
    "意図不明打牌",
    "説明不能な打牌を無理に既存候補へ吸収しない。",
    0.05,
    [value("unknown", 0.06), wait("unknown", 0.06)],
    "例外集か未知バッファとして保存する。",
  ),
];

export function getReadingDrawerItems(category?: ReadingDrawerCategory) {
  return category
    ? readingDrawerItems.filter((item) => item.category === category)
    : readingDrawerItems;
}

export function searchReadingDrawerItems(query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return readingDrawerItems;
  return readingDrawerItems.filter((item) =>
    [item.label, item.description, item.category, ...item.tags]
      .join(" ")
      .toLowerCase()
      .includes(normalized),
  );
}

export function findReadingDrawerItem(id: string) {
  return readingDrawerItems.find((item) => item.id === id);
}

export function createChoiceCandidateFromDrawerItem(
  item: ReadingDrawerItem,
  probability?: number,
): ChoiceCandidateDraft {
  const assigned = clampProbability(
    probability ?? item.default_probability ?? 0,
  );
  return {
    label: item.label,
    posterior_probability: assigned,
    raw_probability: assigned,
    base_weight: assigned,
    dynamic_weight: 0,
    lock_mode: "none",
    tags: unique(["reading_drawer", item.category, ...item.tags]),
  };
}

export function createResidualBucketFromDrawerItem(
  item: ReadingDrawerItem,
  probability?: number,
): ResidualMassBucket {
  const assigned = clampProbability(
    probability ?? item.default_probability ?? 0,
  );
  return {
    id: createId("residual_bucket"),
    label: item.label,
    kind:
      item.category === "exception_noise"
        ? "exception"
        : "unrecalled_candidate",
    probability: assigned,
    note: item.description,
    tags: unique(["reading_drawer", item.category, ...item.tags]),
  };
}

export function createExceptionDraftFromDrawerItem(
  item: ReadingDrawerItem,
  probability?: number,
): MappingDraftNode {
  return createExceptionCandidateDraft(
    createResidualBucketFromDrawerItem(item, probability),
  );
}

function item(
  category: ReadingDrawerCategory,
  label: string,
  description: string,
  defaultProbability: number,
  axisImpacts: AxisImpactDraft[],
  caution?: string,
): ReadingDrawerItem {
  return {
    id: `${category}_${slug(label)}`,
    category,
    label,
    description,
    default_probability: defaultProbability,
    axis_impacts: axisImpacts,
    tags: unique([
      category,
      label,
      ...axisImpacts.map((impact) => impact.axis_id),
    ]),
    caution,
  };
}

function progress(
  sign: AxisImpactDraft["sign"],
  magnitude: number,
): AxisImpactDraft {
  return axis("progress_tenpai_axis", sign, magnitude);
}

function value(
  sign: AxisImpactDraft["sign"],
  magnitude: number,
): AxisImpactDraft {
  return axis("value_axis", sign, magnitude);
}

function wait(
  sign: AxisImpactDraft["sign"],
  magnitude: number,
): AxisImpactDraft {
  return axis("wait_shape_quality_axis", sign, magnitude);
}

function threshold(
  sign: AxisImpactDraft["sign"],
  magnitude: number,
): AxisImpactDraft {
  return axis("score_situation_threshold_axis", sign, magnitude);
}

function axis(
  axisId: AxisImpactDraft["axis_id"],
  sign: AxisImpactDraft["sign"],
  magnitude: number,
): AxisImpactDraft {
  return {
    axis_id: axisId,
    sign,
    magnitude,
    confidence: 0.55,
    dynamic_weight: 0,
    enabled: true,
  };
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function clampProbability(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}
