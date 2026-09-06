import { describe, expect, it } from 'vitest';
import { createSeed } from '../../src/seed/ponDiscardCase';
import { evaluate, stableSoftmax } from '../../src/domain/scoring';
import { parseBoard } from '../../src/domain/validation';
import { evaluateGate } from '../../src/domain/gates';
import { compareBoards } from '../../src/domain/deltas';
import type { GateExpression } from '../../src/domain/model';

describe('A01–A14: pure weighted-score model', () => {
  it('A01 golden raw scores and independently calculated shares', () => {
    const result = evaluate(createSeed());
    const scores = [0.7, -1.2, -1.5, -0.75, -0.8];
    const denominator = scores.reduce((sum, x) => sum + Math.exp(x), 0);
    result.hypotheses.forEach((h, i) => {
      expect(h.rawScore).toBeCloseTo(scores[i], 12);
      expect(h.displayShare).toBeCloseTo(Math.exp(scores[i]) / denominator, 12);
    });
    expect(
      result.hypotheses.reduce((s, h) => s + h.displayShare, 0),
    ).toBeCloseTo(1, 10);
    expect(result.hypotheses[0].displayShare).toBeGreaterThan(0.4);
    expect(result.hypotheses[0].displayShare).toBeLessThan(0.7);
    expect(result.hypotheses[1].displayShare).toBeGreaterThan(0.05);
    expect(result.hypotheses[1].displayShare).toBeLessThan(0.2);
    expect(result.hypotheses[2].displayShare).toBeLessThan(
      result.hypotheses[3].displayShare,
    );
    expect(result.hypotheses[4].displayShare).toBeGreaterThan(0.05);
  });
  it('A02 stable softmax handles large finite scores', () => {
    expect(stableSoftmax([10000, 10000, -10000])).toEqual([0.5, 0.5, 0]);
    expect(stableSoftmax([Number.MAX_VALUE, Number.MAX_VALUE])).toEqual([
      0.5, 0.5,
    ]);
  });
  it('A10 changed context removes obsolete penalties', () => {
    const board = createSeed();
    const initial = evaluate(board).hypotheses[1].displayShare;
    board.factors.find((f) => f.id === 'F5')!.state = 'present';
    board.factors.find((f) => f.id === 'F6')!.state = 'present';
    const h2 = evaluate(board).hypotheses[1];
    expect(h2.displayShare - initial).toBeGreaterThan(0.15);
    expect(h2.displayShare).toBeGreaterThan(0.3);
    expect(
      h2.ledger
        .filter((l) => ['E7', 'E8'].includes(l.sourceId))
        .every((l) => l.appliedValue === 0),
    ).toBe(true);
  });
  it('A09 observation absence requires opportunity and known confidence', () => {
    const board = createSeed();
    const f = board.factors.find((f) => f.id === 'F12')!;
    f.state = 'absent';
    f.opportunity = 'no';
    expect(
      evaluate(board).hypotheses[1].ledger.find((l) => l.sourceId === 'E13')
        ?.appliedValue,
    ).toBe(0);
    f.opportunity = 'yes';
    expect(
      evaluate(board).hypotheses[1].ledger.find((l) => l.sourceId === 'E13')
        ?.appliedValue,
    ).toBe(-0.6);
    f.confidence = 0;
    expect(
      evaluateGate(
        { kind: 'condition', factorId: 'F12', is: 'absent' },
        board.factors,
      ).value,
    ).toBe('unknown');
  });
  it('A11 ledger reconstruction and reevaluation are identical', () => {
    const board = createSeed();
    const first = evaluate(board);
    expect(evaluate(board)).toEqual(first);
    for (const h of first.hypotheses) {
      const summed =
        h.ledger
          .filter((l) => l.unit === 'score')
          .reduce((s, l) => s + l.appliedValue, 0) +
        board.modelConfig.scoreScale *
          h.ledger
            .filter((l) => l.unit === 'contribution')
            .reduce((s, l) => s + l.appliedValue, 0);
      expect(summed).toBeCloseTo(h.rawScore, 12);
    }
  });
  it('A08 hard gates require verified confidence 1; protected hard false stays visible at zero', () => {
    const board = createSeed();
    board.gates[0].mode = 'hard';
    expect(evaluate(board).hypotheses[1].included).toBe(true);
    board.factors.forEach((f) => {
      f.verification = 'verified';
      f.confidence = 1;
    });
    const h2 = evaluate(board).hypotheses[1];
    expect(h2.included).toBe(false);
    expect(h2.displayShare).toBe(0);
    expect(h2.exclusionReason).toContain('保護対象');
  });
  it('A05 maxAbs suppression, mean, sum rationale and mixed-sign rejection', () => {
    const board = createSeed();
    const h = evaluate(board).hypotheses[1];
    expect(h.ledger.find((l) => l.sourceId === 'E2')?.kind).toBe(
      'group_suppressed',
    );
    expect(h.ledger.find((l) => l.sourceId === 'E3')?.appliedValue).toBe(-1.4);
    board.evidenceGroups[0].aggregation = 'mean';
    expect(
      evaluate(board).hypotheses[1].ledger.find((l) => l.sourceId === 'E3')
        ?.appliedValue,
    ).toBeCloseTo(-1.4 / 3, 12);
    board.effects[1].strength = 1;
    expect(() => parseBoard(board)).toThrow(/正負/);
    board.evidenceGroups[0].aggregation = 'sum';
    board.evidenceGroups[0].rationale = '';
    expect(() => parseBoard(board)).toThrow();
    board.evidenceGroups[0].rationale = '独立した根拠として加算する';
    expect(() => parseBoard(board)).not.toThrow();
  });
  it('A06 soft gate and effect share aggregation without duplicate penalty', () => {
    const board = createSeed();
    board.gates[0].mode = 'soft';
    board.gates[0].falsePenalty = -1;
    board.gates[0].evidenceGroupId = 'G1';
    expect(evaluate(board).hypotheses[1].rawScore).toBeCloseTo(-1.2, 12);
    expect(
      evaluate(board).hypotheses[1].ledger.find((l) => l.sourceId === 'GT1')
        ?.kind,
    ).toBe('group_suppressed');
  });
  it('A12–13 symmetric decomposition sums for own, competitors, both, exclusion; structure is separate', () => {
    const before = createSeed();
    for (const scenario of ['own', 'other', 'both', 'exclude']) {
      const after = createSeed();
      if (scenario === 'own' || scenario === 'both')
        after.hypotheses[0].manualAdjustment = 1;
      if (scenario === 'other' || scenario === 'both')
        after.hypotheses[2].manualAdjustment = -1;
      if (scenario === 'exclude') after.hypotheses[2].manualPruned = true;
      const deltas = compareBoards(before, after);
      for (const delta of deltas)
        expect(delta.ownEffect! + delta.otherEffect!).toBeCloseTo(
          delta.shareDelta,
          12,
        );
      if (scenario === 'other')
        expect(deltas[0].reason).toContain('競合候補低下');
      if (scenario === 'own') expect(deltas[0].reason).toContain('手動調整');
    }
    const after = createSeed();
    after.modelConfig.temperature = 2;
    expect(compareBoards(before, after)[0].reason).toBe('構造/モデル設定変更');
  });
  it('A07 all truth combinations including unknown and NOT', () => {
    const board = createSeed();
    const a = board.factors[0],
      b = board.factors[1];
    const leafA: GateExpression = {
      kind: 'condition',
      factorId: a.id,
      is: 'present',
    };
    const leafB: GateExpression = {
      kind: 'condition',
      factorId: b.id,
      is: 'present',
    };
    const states = ['present', 'absent', 'unknown'] as const;
    for (const x of states)
      for (const y of states) {
        a.state = x;
        b.state = y;
        const expectedAll =
          x === 'absent' || y === 'absent'
            ? 'false'
            : x === 'present' && y === 'present'
              ? 'true'
              : 'unknown';
        const expectedAny =
          x === 'present' || y === 'present'
            ? 'true'
            : x === 'absent' && y === 'absent'
              ? 'false'
              : 'unknown';
        expect(
          evaluateGate({ kind: 'all', children: [leafA, leafB] }, board.factors)
            .value,
        ).toBe(expectedAll);
        expect(
          evaluateGate({ kind: 'any', children: [leafA, leafB] }, board.factors)
            .value,
        ).toBe(expectedAny);
        expect(
          evaluateGate({ kind: 'not', child: leafA }, board.factors).value,
        ).toBe(x === 'present' ? 'false' : x === 'absent' ? 'true' : 'unknown');
      }
  });
});
