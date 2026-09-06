import type { BoardDocument } from './model';
import type { HypothesisEvaluation, LedgerRow } from './scoring';

export function explainHypothesis(
  board: BoardDocument,
  result: HypothesisEvaluation,
) {
  const scoreValue = (row: LedgerRow) =>
    row.unit === 'score'
      ? row.appliedValue
      : row.appliedValue * board.modelConfig.scoreScale;
  const additive = result.ledger.filter((row) => row.unit !== 'summary');
  return {
    weak: additive
      .filter((row) => row.appliedValue < 0)
      .sort((a, b) => scoreValue(a) - scoreValue(b) || a.id.localeCompare(b.id))
      .slice(0, 3),
    support: additive.filter((row) => row.appliedValue > 0),
    inactive: result.ledger.filter((row) => row.kind === 'inactive'),
    suppressed: result.ledger.filter((row) => row.kind === 'group_suppressed'),
    unknown: result.ledger.filter((row) => row.kind === 'unknown'),
  };
}
