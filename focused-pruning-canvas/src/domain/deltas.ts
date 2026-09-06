import type { BoardDocument } from './model';
import { evaluate, stableSoftmax, type HypothesisEvaluation } from './scoring';

export interface BoardDelta {
  id: string;
  rawScoreDelta: number;
  shareDelta: number;
  includedChanged: boolean;
  reason: string;
  ownEffect: number | null;
  otherEffect: number | null;
}
export function compareBoards(
  before: BoardDocument,
  after: BoardDocument,
): BoardDelta[] {
  const prev = evaluate(before),
    next = evaluate(after);
  const structural =
    JSON.stringify(before.hypotheses.map((h) => h.id).sort()) !==
      JSON.stringify(after.hypotheses.map((h) => h.id).sort()) ||
    JSON.stringify(before.modelConfig) !== JSON.stringify(after.modelConfig);
  const mixedShare = (
    own: HypothesisEvaluation,
    others: HypothesisEvaluation[],
  ) => {
    if (!own.included) return 0;
    const all = [own, ...others.filter((h) => h.id !== own.id && h.included)];
    return stableSoftmax(
      all.map((h) => h.rawScore / after.modelConfig.temperature),
    )[0];
  };
  return next.hypotheses.map((h) => {
    const p = prev.hypotheses.find((p) => p.id === h.id);
    const shareDelta = h.displayShare - (p?.displayShare ?? 0),
      rawScoreDelta = h.rawScore - (p?.rawScore ?? 0);
    const result: BoardDelta = {
      id: h.id,
      shareDelta,
      rawScoreDelta,
      includedChanged: p?.included !== h.included,
      reason: '変化なし',
      ownEffect: null,
      otherEffect: null,
    };
    if (structural || !p) return { ...result, reason: '構造/モデル設定変更' };
    const f00 = mixedShare(p, prev.hypotheses),
      f10 = mixedShare(h, prev.hypotheses),
      f01 = mixedShare(p, next.hypotheses),
      f11 = mixedShare(h, next.hypotheses);
    result.ownEffect = (f10 - f00 + (f11 - f01)) / 2;
    result.otherEffect = (f01 - f00 + (f11 - f10)) / 2;
    const oldInput = before.hypotheses.find((x) => x.id === h.id)!,
      input = after.hypotheses.find((x) => x.id === h.id)!;
    if (result.includedChanged) result.reason = '計算対象の変更';
    else if (oldInput.manualAdjustment !== input.manualAdjustment)
      result.reason = '手動調整による変化';
    else if (oldInput.baseScore !== input.baseScore)
      result.reason = '基準変更による変化';
    else if (Math.abs(rawScoreDelta) > 1e-12)
      result.reason = '要因・成立条件の変更';
    else if (shareDelta > 1e-12) result.reason = '競合候補低下による相対上昇';
    else if (shareDelta < -1e-12) result.reason = '競合候補上昇による相対低下';
    return result;
  });
}
