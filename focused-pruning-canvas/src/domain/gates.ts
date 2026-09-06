import type { Factor, GateExpression, Truth } from './model';

export interface GateEvaluation {
  value: Truth;
  label: string;
  reason: string;
  children: GateEvaluation[];
}
export function factorAvailability(factor: Factor): string | null {
  if (factor.confidence === 0) return '根拠信頼度が0のため未確定';
  if (factor.state === 'unknown') return '要因が未確認';
  if (factor.state === 'unobservable') return '要因は観測不能';
  if (
    factor.kind === 'observation' &&
    factor.state === 'absent' &&
    factor.opportunity !== 'yes'
  )
    return '不在を判断する観測機会が確認できません';
  return null;
}
export function expressionFactorIds(expression: GateExpression): string[] {
  if (expression.kind === 'condition') return [expression.factorId];
  if (expression.kind === 'not') return expressionFactorIds(expression.child);
  return expression.children.flatMap(expressionFactorIds);
}
export function evaluateGate(
  expression: GateExpression,
  factors: Factor[],
  hard = false,
): GateEvaluation {
  if (expression.kind === 'condition') {
    const f = factors.find((f) => f.id === expression.factorId);
    if (!f) throw new Error(`条件参照が不明: ${expression.factorId}`);
    const reason =
      factorAvailability(f) ??
      (hard && (f.verification !== 'verified' || f.confidence !== 1)
        ? 'hard条件には明示確認済み・信頼度1が必要'
        : null);
    const value = reason
      ? 'unknown'
      : f.state === expression.is
        ? 'true'
        : 'false';
    return {
      value,
      label: `${f.label} = ${expression.is === 'present' ? 'あり' : 'なし'}`,
      reason:
        reason ?? (value === 'true' ? '条件成立' : '現在値と条件が不一致'),
      children: [],
    };
  }
  const children =
    expression.kind === 'not'
      ? [evaluateGate(expression.child, factors, hard)]
      : expression.children.map((e) => evaluateGate(e, factors, hard));
  if (!children.length) throw new Error('空の条件式は使えません');
  const values = children.map((c) => c.value);
  const value: Truth =
    expression.kind === 'not'
      ? values[0] === 'unknown'
        ? 'unknown'
        : values[0] === 'true'
          ? 'false'
          : 'true'
      : expression.kind === 'all'
        ? values.includes('false')
          ? 'false'
          : values.every((v) => v === 'true')
            ? 'true'
            : 'unknown'
        : values.includes('true')
          ? 'true'
          : values.every((v) => v === 'false')
            ? 'false'
            : 'unknown';
  return {
    value,
    label:
      expression.kind === 'all'
        ? 'AND'
        : expression.kind === 'any'
          ? 'OR'
          : 'NOT',
    reason:
      value === 'unknown'
        ? '未確定の条件が残っています'
        : value === 'false'
          ? '成立条件を満たしていません'
          : '条件成立',
    children,
  };
}
