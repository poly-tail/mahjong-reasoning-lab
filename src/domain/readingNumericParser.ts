import type { AxisImpactDraft, ReadingNumericParseResult } from "./readingNumerics";
import type { InfluenceSign, LockMode } from "./schema";

type AxisId = AxisImpactDraft["axis_id"];

const axisPatterns: Array<{
  axis_id: AxisId;
  patterns: RegExp[];
}> = [
  {
    axis_id: "progress_tenpai_axis",
    patterns: [/進行度?|聴牌率?|テンパイ|先制率?|シャンテン|進行/u],
  },
  {
    axis_id: "value_axis",
    patterns: [/打点|満貫|高打点|score|value/u],
  },
  {
    axis_id: "wait_shape_quality_axis",
    patterns: [/待ち・形|待ち|形|良形|愚形|安全度|危険牌/u],
  },
  {
    axis_id: "score_situation_threshold_axis",
    patterns: [/点数状況|行動閾値|点棒|順位|条件戦|親子|供託|本場/u],
  },
];

export function parseReadingNumericHints(
  text: string,
): ReadingNumericParseResult {
  const warnings: string[] = [];
  const result: ReadingNumericParseResult = { warnings };

  result.confidence = firstNumber(text, [/\bconf(?:idence)?\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu]);
  result.prior_probability = firstNumber(text, [/\bprior\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu]);
  result.posterior_probability = firstNumber(text, [
    /\bposterior\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
    /\bp\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
  ]);
  result.base_weight = firstSignedNumber(text, [
    /\bbase[_\s-]?weight\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
    /\bb\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
  ]);
  result.dynamic_weight = firstSignedNumber(text, [
    /\bdynamic[_\s-]?weight\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
    /\bweight\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
    /\bw\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu,
  ]);

  if (/hard_prune|hard prune/u.test(text)) result.pruning_action = "hard_prune";
  if (/downweight|soft_downweight|弱め/u.test(text)) {
    result.pruning_action = "soft_downweight";
  }
  const keepTopK = text.match(/keep[_\s-]?top[_\s-]?k\s*=\s*(\d+)/iu);
  if (keepTopK) {
    result.pruning_action = "keep_top_k";
    result.lock_mode = "keep_top_k";
    result.lock_value = Number(keepTopK[1]);
  }
  const freezeRatio = text.match(/freeze[_\s-]?ratio\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu);
  if (freezeRatio) {
    result.pruning_action = "freeze_ratio";
    result.lock_mode = "freeze_ratio";
    result.lock_value = normalizeNumber(freezeRatio[1], warnings);
  }
  const lock = text.match(/\block\s*=\s*([+-]?\d+(?:\.\d+)?%?)/iu);
  if (lock) {
    result.lock_mode = result.lock_mode ?? "soft_lock";
    result.lock_value = normalizeNumber(lock[1], warnings);
  }

  const axisImpacts = parseAxisImpacts(text, warnings);
  if (axisImpacts.length > 0) result.axis_impacts = axisImpacts;

  for (const [label, value] of [
    ["confidence", result.confidence],
    ["prior", result.prior_probability],
    ["posterior", result.posterior_probability],
    ["lock", result.lock_value],
  ] as const) {
    if (value !== undefined && (value < 0 || value > 1)) {
      warnings.push(`${label} は0-100%の範囲で入力してください。`);
    }
  }

  return result;
}

function parseAxisImpacts(text: string, warnings: string[]) {
  const impacts: AxisImpactDraft[] = [];
  const chunks = text.split(/\s+/);
  for (const chunk of chunks) {
    const normalized = chunk.trim();
    if (!normalized) continue;
    for (const axis of axisPatterns) {
      if (!axis.patterns.some((pattern) => pattern.test(normalized))) continue;
      const signValue = normalized.match(/(?:=|:)?(mixed|unknown|不明|文脈次第)/iu);
      const numericValue = normalized.match(/([+-])\s*(\d+(?:\.\d+)?%?)/u);
      if (!signValue && !numericValue) continue;
      const sign: InfluenceSign = signValue
        ? signFromText(signValue[1])
        : numericValue?.[1] === "-"
          ? "-"
          : "+";
      const magnitude = numericValue
        ? normalizeNumber(numericValue[2], warnings) ?? 0
        : 0;
      impacts.push({
        axis_id: axis.axis_id,
        sign,
        magnitude,
        confidence: 0.6,
        enabled: true,
      });
    }
  }
  return dedupeAxisImpacts(impacts);
}

function dedupeAxisImpacts(impacts: AxisImpactDraft[]) {
  const byAxis = new Map<AxisId, AxisImpactDraft>();
  for (const impact of impacts) byAxis.set(impact.axis_id, impact);
  return Array.from(byAxis.values());
}

function firstNumber(text: string, patterns: RegExp[]) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return normalizeNumber(match[1], []);
  }
  return undefined;
}

function firstSignedNumber(text: string, patterns: RegExp[]) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return normalizeSignedNumber(match[1], []);
  }
  return undefined;
}

function normalizeNumber(value: string, warnings: string[]) {
  const normalized = normalizeSignedNumber(value, warnings);
  if (normalized === undefined) return undefined;
  return Math.min(1, Math.max(0, normalized));
}

function normalizeSignedNumber(value: string, warnings: string[]) {
  const trimmed = value.trim();
  const numeric = Number(trimmed.replace("%", ""));
  if (!Number.isFinite(numeric)) {
    warnings.push(`${value} を数値として解釈できません。`);
    return undefined;
  }
  if (trimmed.includes("%")) return numeric / 100;
  if (Math.abs(numeric) > 1) return numeric / 100;
  return numeric;
}

function signFromText(value: string): InfluenceSign {
  const normalized = value.toLowerCase();
  if (normalized === "mixed" || value === "文脈次第") return "mixed";
  if (normalized === "unknown" || value === "不明") return "unknown";
  return "unknown";
}

export type ParsedLockMode = LockMode;
