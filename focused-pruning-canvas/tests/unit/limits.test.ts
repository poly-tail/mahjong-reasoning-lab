import { describe, expect, it } from 'vitest';
import { createSeed, emptyBoard } from '../../src/seed/ponDiscardCase';
import {
  createEnvelope,
  commit,
  currentDocument,
} from '../../src/application/history';
import { parseBoard, parseEnvelope } from '../../src/domain/validation';
import { byteSize, limits, type GateExpression } from '../../src/domain/model';
import { evaluate } from '../../src/domain/scoring';
import { compareBoards } from '../../src/domain/deltas';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { originalSource } from '../../src/seed/sourceMaterial';

const meta = (i: number) => ({
  id: `s${i}`,
  revision: `r${i}`,
  timestamp: '2026-09-05T00:00:00.000Z',
  actionLabel: `edit ${i}`,
});
describe('remaining acceptance boundaries', () => {
  it('source material remains identical between preserved document and seed', () => {
    const doc = readFileSync(
      resolve('docs/source-material.md'),
      'utf8',
    ).replace(/\r\n/g, '\n');
    const raw = doc.split('```text\n')[1]?.split('\n```')[0];
    expect(raw).toBe(originalSource.replace(/\r\n/g, '\n'));
    expect(raw).toContain('246から2か4切り');
    expect(createSeed().notes.every((n) => n.sourceRefs.includes('S1'))).toBe(
      true,
    );
  });
  it('B04 trims by UTF-8 capacity even below 50 snapshots without cutting source text', () => {
    const b = createSeed();
    b.sourceMaterials[0].text = 'あ'.repeat(64000);
    for (let i = 0; i < 20; i++)
      b.notes.push({
        id: `bulk${i}`,
        ownerHypothesisId: 'H1',
        parentNoteId: null,
        order: i,
        label: `説明${i}`,
        body: '漢'.repeat(2000),
        sourceRefs: ['S1'],
      });
    let env = createEnvelope(b, meta(0));
    let trimmed = false;
    for (let i = 1; i < 12; i++) {
      const r = commit(
        env,
        { type: 'editBoard', patch: { title: `title${i}` } },
        meta(i),
      );
      env = r.envelope;
      trimmed ||= r.trimmed;
    }
    expect(trimmed).toBe(true);
    expect(env.snapshots.length).toBeLessThan(12);
    expect(byteSize(env)).toBeLessThanOrEqual(limits.envelope);
    expect(env.cursor).toBe(env.snapshots.length - 1);
    expect(currentDocument(env).sourceMaterials[0].text).toBe(
      b.sourceMaterials[0].text,
    );
    const over = {
      ...env,
      snapshots: Array.from({ length: 20 }, (_, i) => ({
        ...env.snapshots[0],
        id: `over${i}`,
      })),
    };
    expect(() => parseEnvelope(over)).toThrow(/2MiB/);
  });
  it('B07 rejects current document overflow, all invalid historical snapshots and exact limits', () => {
    const b = createSeed();
    for (let i = 0; i < 45; i++)
      b.notes.push({
        id: `huge${i}`,
        ownerHypothesisId: 'H1',
        parentNoteId: null,
        order: i,
        label: `大きい説明${i}`,
        body: 'あ'.repeat(4000),
        sourceRefs: [],
      });
    expect(() => parseBoard(b)).toThrow(/512KiB/);
    const initial = createEnvelope(createSeed(), meta(0));
    const env = commit(initial, { type: 'weaken', id: 'H1' }, meta(1)).envelope;
    env.snapshots[0].document.effects[0].factorId = 'missing';
    expect(() => parseEnvelope(env)).toThrow(/参照/);
    const bad = createSeed();
    bad.notes[0].label = 'x'.repeat(121);
    expect(() => parseBoard(bad)).toThrow();
    const count = createSeed();
    count.factors = Array.from({ length: 101 }, (_, i) => ({
      ...count.factors[0],
      id: `factor${i}`,
    }));
    expect(() => parseBoard(count)).toThrow();
  });
  it('A05 maxAbs ties use ID order independent of array order; inactive is excluded from mean denominator', () => {
    const b = createSeed();
    b.effects[2].strength = -1;
    let rows = evaluate(b).hypotheses[1].ledger;
    expect(rows.find((r) => r.sourceId === 'E2')?.appliedValue).toBe(-0.7);
    b.effects.reverse();
    expect(
      evaluate(b).hypotheses[1].ledger.find((r) => r.sourceId === 'E2')
        ?.appliedValue,
    ).toBe(-0.7);
    b.evidenceGroups[0].aggregation = 'mean';
    b.factors.find((f) => f.id === 'F4')!.state = 'unknown';
    rows = evaluate(b).hypotheses[1].ledger;
    expect(rows.find((r) => r.sourceId === 'E2')?.appliedValue).toBe(-0.35);
    expect(rows.find((r) => r.sourceId === 'E4')?.appliedValue).toBe(0);
  });
  it('A07 cycles and unknown references are rejected before recursive schema parsing', () => {
    const b = createSeed();
    const expression: GateExpression = { kind: 'all', children: [] };
    expression.children.push(expression);
    b.gates[0].expression = expression;
    expect(() => parseBoard(b)).toThrow(/循環/);
    b.gates[0].expression = {
      kind: 'condition',
      factorId: 'no-such-factor',
      is: 'present',
    };
    expect(() => parseBoard(b)).toThrow(/参照/);
  });
  it('A09 when unknown/unobservable produce zero and clear unknown ledger', () => {
    const b = createSeed();
    b.factors.find((f) => f.id === 'F5')!.state = 'unknown';
    const e = evaluate(b).hypotheses[1].ledger.find(
      (r) => r.sourceId === 'E7',
    )!;
    expect(e.appliedValue).toBe(0);
    expect(e.reason).toBe('適用条件未確定');
    b.factors[0].state = 'unobservable';
    expect(
      evaluate(b).hypotheses[0].ledger.find((r) => r.sourceId === 'E1')
        ?.appliedValue,
    ).toBe(0);
  });
  it('A13 new candidate yields structural label without fabricated decomposition', () => {
    const b = createSeed();
    const after = emptyBoard('empty', 'residual');
    expect(
      compareBoards(b, after).every(
        (d) =>
          d.reason === '構造/モデル設定変更' &&
          d.ownEffect === null &&
          d.otherEffect === null,
      ),
    ).toBe(true);
  });
  it('B02 note depth 6 is valid and 7 is rejected', () => {
    const b = createSeed();
    b.notes = [];
    for (let i = 0; i < 6; i++)
      b.notes.push({
        id: `n${i}`,
        ownerHypothesisId: 'H1',
        parentNoteId: i ? `n${i - 1}` : null,
        order: i,
        label: `note${i}`,
        body: '',
        sourceRefs: [],
      });
    expect(() => parseBoard(b)).not.toThrow();
    b.notes.push({ ...b.notes[5], id: 'n6', parentNoteId: 'n5' });
    expect(() => parseBoard(b)).toThrow(/深さ6/);
  });
});
