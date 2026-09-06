import type { BoardDocument, Hypothesis } from './model';
import { evaluateGate, factorAvailability, type GateEvaluation } from './gates';

export type LedgerKind =
  | 'base'
  | 'effect'
  | 'inactive'
  | 'unknown'
  | 'group_suppressed'
  | 'gate'
  | 'manual'
  | 'finalScore';
export interface LedgerRow {
  id: string;
  sourceId: string;
  hypothesisId: string;
  label: string;
  kind: LedgerKind;
  rawValue: number;
  appliedValue: number;
  reason: string;
  unit: 'score' | 'contribution' | 'summary';
  evidenceGroupId: string | null;
  eligible: boolean;
}
export interface HypothesisEvaluation {
  id: string;
  rawScore: number;
  displayShare: number;
  included: boolean;
  exclusionReason: string;
  ledger: LedgerRow[];
  gates: { id: string; mode: string; tree: GateEvaluation }[];
}
export interface Evaluation {
  hypotheses: HypothesisEvaluation[];
  normalizationSummary: {
    includedIds: string[];
    shiftedDenominator: number;
    maxScaledScore: number;
    temperature: number;
  };
  warnings: string[];
}
export function stableSoftmax(scores: number[]): number[] {
  if (!scores.length || scores.some((s) => !Number.isFinite(s)))
    throw new Error('有限のスコアと計算対象が必要です');
  const max = Math.max(...scores);
  const exp = scores.map((s) => Math.exp(s - max));
  const sum = exp.reduce((a, b) => a + b, 0);
  return exp.map((e) => e / sum);
}
function row(
  h: Hypothesis,
  sourceId: string,
  kind: LedgerKind,
  label: string,
  rawValue: number,
  reason: string,
  unit: LedgerRow['unit'],
  eligible = true,
  group: string | null = null,
): LedgerRow {
  return {
    id: `${h.id}:${sourceId}`,
    sourceId,
    hypothesisId: h.id,
    label,
    kind,
    rawValue,
    appliedValue: eligible ? rawValue : 0,
    reason,
    unit,
    evidenceGroupId: group,
    eligible,
  };
}
export function contributionCandidates(
  board: BoardDocument,
  h: Hypothesis,
): LedgerRow[] {
  const rows: LedgerRow[] = [];
  for (const effect of board.effects.filter((e) => e.hypothesisId === h.id)) {
    const f = board.factors.find((f) => f.id === effect.factorId);
    if (!f) throw new Error(`要因参照が不明: ${effect.factorId}`);
    const availability = factorAvailability(f);
    const context = effect.when
      ? evaluateGate(effect.when, board.factors)
      : null;
    const stateActive =
      (f.state === 'present' || f.state === 'absent') &&
      effect.activeStates.includes(f.state);
    const reason =
      availability ??
      (!stateActive
        ? '現在の要因状態では適用外'
        : context?.value === 'false'
          ? '適用条件不成立'
          : context?.value === 'unknown'
            ? '適用条件未確定'
            : null);
    const kind: LedgerKind = reason
      ? availability || context?.value === 'unknown'
        ? 'unknown'
        : 'inactive'
      : 'effect';
    rows.push(
      row(
        h,
        effect.id,
        kind,
        f.label,
        effect.strength * f.confidence * effect.applicabilityConfidence,
        reason ?? '強度 × 根拠信頼度 × 適用信頼度',
        'contribution',
        !reason,
        effect.evidenceGroupId,
      ),
    );
  }
  for (const gate of board.gates.filter((g) => g.hypothesisId === h.id)) {
    const result = evaluateGate(
      gate.expression,
      board.factors,
      gate.mode === 'hard',
    );
    const eligible = gate.mode === 'soft' && result.value === 'false';
    rows.push(
      row(
        h,
        gate.id,
        result.value === 'unknown' ? 'unknown' : 'gate',
        gate.explanation,
        eligible ? gate.falsePenalty : 0,
        gate.mode === 'informational'
          ? `情報表示のみ・寄与なし (${result.value})`
          : result.value === 'unknown'
            ? '条件未確定・寄与なし'
            : gate.mode === 'hard'
              ? `hard条件 ${result.value}・加算なし`
              : 'soft条件の評価',
        'contribution',
        eligible,
        gate.evidenceGroupId,
      ),
    );
  }
  return rows;
}
export function aggregateContributions(
  board: BoardDocument,
  candidates: LedgerRow[],
): LedgerRow[] {
  const rows = candidates.map((r) => ({ ...r }));
  for (const group of board.evidenceGroups) {
    const members = rows.filter(
      (r) => r.evidenceGroupId === group.id && r.eligible,
    );
    if (!members.length) continue;
    if (
      group.aggregation !== 'sum' &&
      members.some((r) => r.rawValue > 0) &&
      members.some((r) => r.rawValue < 0)
    )
      throw new Error(
        `同根グループ「${group.label}」の有効寄与に正負が混在しています`,
      );
    if (group.aggregation === 'maxAbs') {
      const winner = [...members].sort(
        (a, b) =>
          Math.abs(b.rawValue) - Math.abs(a.rawValue) ||
          (a.sourceId < b.sourceId ? -1 : a.sourceId > b.sourceId ? 1 : 0),
      )[0];
      for (const member of members)
        if (member !== winner) {
          member.appliedValue = 0;
          member.kind = 'group_suppressed';
          member.reason = `同根抑制: ${group.label} は ${winner.sourceId} の最大絶対値だけ適用`;
        }
    } else if (group.aggregation === 'mean') {
      members.forEach((r) => {
        r.appliedValue = r.rawValue / members.length;
        r.reason = `同根平均: ${group.label} の有効 ${members.length} 件で配分`;
      });
    } else
      members.forEach((r) => {
        r.reason = `同根加算: ${group.rationale}`;
      });
  }
  return rows;
}
export function evaluate(board: BoardDocument): Evaluation {
  const hypotheses = board.hypotheses.map((h) => {
    const contributions = aggregateContributions(
      board,
      contributionCandidates(board, h),
    );
    const gates = board.gates
      .filter((g) => g.hypothesisId === h.id)
      .map((g) => ({
        id: g.id,
        mode: g.mode,
        tree: evaluateGate(g.expression, board.factors, g.mode === 'hard'),
      }));
    const hardFalse = gates.some(
      (g) => g.mode === 'hard' && g.tree.value === 'false',
    );
    const included = !h.manualPruned && !hardFalse;
    const rawScore =
      h.baseScore +
      board.modelConfig.scoreScale *
        contributions.reduce((sum, r) => sum + r.appliedValue, 0) +
      h.manualAdjustment;
    return {
      id: h.id,
      rawScore,
      displayShare: 0,
      included,
      exclusionReason: hardFalse
        ? h.mustKeep
          ? '保護対象だが条件不成立'
          : 'hard条件不成立'
        : h.manualPruned
          ? '手動pruneで計算対象外'
          : '',
      gates,
      ledger: [
        row(
          h,
          'base',
          'base',
          '基準スコア',
          h.baseScore,
          '入力した基準',
          'score',
        ),
        ...contributions,
        row(
          h,
          'manual',
          'manual',
          '手動調整',
          h.manualAdjustment,
          '入力者の手動調整',
          'score',
        ),
        row(
          h,
          'final',
          'finalScore',
          '最終スコア',
          rawScore,
          'base + scoreScale × 寄与合計 + manual',
          'summary',
        ),
      ],
    };
  });
  const included = hypotheses.filter((h) => h.included);
  const scores = included.map(
    (h) => h.rawScore / board.modelConfig.temperature,
  );
  const shares = stableSoftmax(scores);
  included.forEach((h, i) => {
    h.displayShare = shares[i];
  });
  const max = Math.max(...scores);
  const warnings = board.factors.flatMap((f) => {
    const reason = factorAvailability(f);
    return reason ? [`${f.label}: ${reason}`] : [];
  });
  for (const effect of board.effects) {
    if (
      board.effects.some(
        (e) =>
          e.id !== effect.id &&
          e.factorId === effect.factorId &&
          e.hypothesisId === effect.hypothesisId,
      )
    )
      warnings.push(
        `${effect.id}: 同じ要因からの複数接続は文脈が重なる可能性があります`,
      );
  }
  return {
    hypotheses,
    normalizationSummary: {
      includedIds: included.map((h) => h.id),
      shiftedDenominator: scores.reduce((s, x) => s + Math.exp(x - max), 0),
      maxScaledScore: max,
      temperature: board.modelConfig.temperature,
    },
    warnings,
  };
}
export const formatShare = (share: number) =>
  share > 0 && share < 0.001 ? '<0.1%' : `${(share * 100).toFixed(1)}%`;
