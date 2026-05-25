export type RescueRateBand = "low" | "some" | "medium" | "high";

export type RescueRateEventEstimate = {
  id: string;
  label: string;
  probability?: number;
  enabled: boolean;
};

export type RescueRateEstimate = {
  q_total?: number;
  band_label: string;
  range_label: string;
  warnings: string[];
};

const bandRanges: Record<RescueRateBand, { label: string; range: string }> = {
  low: { label: "低い", range: "0-10%" },
  some: { label: "ややある", range: "10-20%" },
  medium: { label: "そこそこ", range: "20-30%" },
  high: { label: "高い", range: "30%超" },
};

export function calculateRescueRate(probabilities: number[]) {
  const sanitized = probabilities
    .filter((value) => Number.isFinite(value))
    .map((value) => Math.max(0, Math.min(1, value)));
  const qTotal =
    sanitized.length === 0
      ? undefined
      : 1 - sanitized.reduce((product, value) => product * (1 - value), 1);
  return qTotal === undefined ? undefined : round(qTotal);
}

export function estimateRescueRate(
  events: RescueRateEventEstimate[],
  fallbackBand: RescueRateBand,
): RescueRateEstimate {
  const activeValues = events
    .filter((event) => event.enabled && event.probability !== undefined)
    .map((event) => event.probability ?? 0);
  const qTotal = calculateRescueRate(activeValues);
  const band = qTotal === undefined ? bandRanges[fallbackBand] : bandFor(qTotal);
  const warnings = rescueRateWarnings(qTotal, events);

  return {
    q_total: qTotal,
    band_label: band.label,
    range_label: qTotal === undefined ? band.range : `${Math.round(qTotal * 100)}%`,
    warnings,
  };
}

export function rescueRateWarnings(
  qTotal: number | undefined,
  events: RescueRateEventEstimate[] = [],
) {
  const warnings: string[] = [];
  if (qTotal !== undefined && qTotal > 0.3) {
    warnings.push("脇救済率を高く見積もりすぎている可能性があります。");
  }
  const enabledCount = events.filter((event) => event.enabled).length;
  if (enabledCount >= 3) {
    warnings.push("救済イベントが独立とは限らないため、合算は上限レンジとして扱ってください。");
  }
  if (qTotal !== undefined && qTotal > 0.2) {
    warnings.push("他力期待で危険牌選択を正当化していないか確認してください。");
  }
  return warnings;
}

function bandFor(value: number) {
  if (value < 0.1) return bandRanges.low;
  if (value < 0.2) return bandRanges.some;
  if (value <= 0.3) return bandRanges.medium;
  return bandRanges.high;
}

function round(value: number) {
  return Math.round(value * 10000) / 10000;
}
