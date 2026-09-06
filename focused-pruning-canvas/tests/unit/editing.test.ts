import { describe, expect, it } from 'vitest';
import { createSeed, emptyBoard } from '../../src/seed/ponDiscardCase';
import { applyCommand, deletionPreview } from '../../src/domain/commands';
import { evaluate } from '../../src/domain/scoring';
import { parseBoard, parseEnvelope } from '../../src/domain/validation';
import {
  createEnvelope,
  commit,
  moveCursor,
} from '../../src/application/history';
import { exportJson, importJson } from '../../src/infrastructure/jsonTransfer';
import {
  exportMarkdown,
  importMarkdown,
} from '../../src/infrastructure/markdownTransfer';
import type { GateExpression } from '../../src/domain/model';
import { byteSize, limits } from '../../src/domain/model';

const meta = (i: number) => ({
  id: `snap-${i}`,
  revision: `rev-${i}`,
  timestamp: '2026-09-05T00:00:00.000Z',
  actionLabel: `操作 ${i}`,
});
describe('commands, validation, history and transfer', () => {
  it('B06 export remains importable near capacity with fence-heavy text', () => {
    const b = createSeed();
    b.notes = [];
    for (let i = 0; i < 110; i++)
      b.notes.push({
        id: `fenced${i}`,
        ownerHypothesisId: 'H1',
        parentNoteId: null,
        order: i,
        label: `note${i}`,
        body: '`'.repeat(3900),
        sourceRefs: [],
      });
    let env = createEnvelope(b, meta(0));
    for (let i = 1; i < 6; i++)
      env = commit(
        env,
        { type: 'editBoard', patch: { title: `title${i}` } },
        meta(i),
      ).envelope;
    const md = exportMarkdown(env);
    expect(byteSize(md)).toBeLessThanOrEqual(limits.file);
    expect(importMarkdown(md)).toEqual(env);
    expect(importJson(exportJson(env))).toEqual(env);
  });
  it('A03–04 idempotent downweight, restore and protected prune/delete', () => {
    const seed = createSeed();
    const weak = applyCommand(seed, { type: 'weaken', id: 'H1' });
    expect(applyCommand(weak, { type: 'weaken', id: 'H1' })).toEqual(weak);
    expect(weak.hypotheses[0].manualAdjustment).toBe(-1);
    const pruned = applyCommand(weak, { type: 'prune', id: 'H1' });
    expect(evaluate(pruned).hypotheses[0].displayShare).toBe(0);
    expect(applyCommand(pruned, { type: 'restore', id: 'H1' })).toEqual(seed);
    for (const id of ['H2', 'H5']) {
      expect(() => applyCommand(seed, { type: 'prune', id })).toThrow(/保護/);
      expect(() =>
        applyCommand(seed, { type: 'delete', entity: 'hypothesis', id }),
      ).toThrow(/保護/);
    }
    const residual = createSeed();
    residual.hypotheses.forEach((h) => {
      if (!h.residual) {
        h.mustKeep = false;
        h.manualPruned = true;
      }
    });
    expect(evaluate(parseBoard(residual)).hypotheses[4].displayShare).toBe(1);
  });
  it('B01 empty board CRUD and note-only A14 changes leave scores unchanged', () => {
    let b = emptyBoard('board', 'residual');
    b = applyCommand(b, {
      type: 'addHypothesis',
      value: { ...createSeed().hypotheses[0], id: 'hyp', sourceRefs: [] },
    });
    b = applyCommand(b, {
      type: 'addFactor',
      value: { ...createSeed().factors[0], id: 'factor', sourceRefs: [] },
    });
    b = applyCommand(b, {
      type: 'addEffect',
      value: {
        ...createSeed().effects[0],
        id: 'effect',
        factorId: 'factor',
        hypothesisId: 'hyp',
        sourceRefs: [],
      },
    });
    const scores = evaluate(b).hypotheses;
    b = applyCommand(b, {
      type: 'addNote',
      value: {
        id: 'note',
        ownerHypothesisId: 'hyp',
        parentNoteId: null,
        order: 0,
        label: '説明',
        body: '本文',
        sourceRefs: [],
      },
    });
    expect(evaluate(b).hypotheses).toEqual(scores);
    b = applyCommand(b, {
      type: 'editBoard',
      patch: { question: '自分の問い' },
    });
    expect(b.question).toBe('自分の問い');
  });
  it('B02 note indent/outdent, owner and cycle checks', () => {
    const seed = createSeed();
    const b = applyCommand(seed, { type: 'indentNote', id: 'N6' });
    expect(b.notes.find((n) => n.id === 'N6')?.parentNoteId).toBe('N2');
    expect(
      applyCommand(b, { type: 'outdentNote', id: 'N6' }).notes.find(
        (n) => n.id === 'N6',
      )?.parentNoteId,
    ).toBeNull();
    seed.notes[1].parentNoteId = 'N3';
    expect(() => parseBoard(seed)).toThrow(/循環/);
    const other = createSeed();
    other.notes[1].parentNoteId = 'N1';
    expect(() => parseBoard(other)).toThrow(/異なる/);
  });
  it('B03 deletes referenced effects atomically but rejects factors in gates/when', () => {
    const b = createSeed();
    expect(deletionPreview(b, 'factor', 'F5').blocked).toContain('条件');
    expect(() =>
      applyCommand(b, { type: 'delete', entity: 'factor', id: 'F5' }),
    ).toThrow(/条件/);
    expect(deletionPreview(b, 'factor', 'F1').affected).toContain('E1');
    const after = applyCommand(b, {
      type: 'delete',
      entity: 'factor',
      id: 'F1',
    });
    expect(after.factors.some((f) => f.id === 'F1')).toBe(false);
    expect(after.effects.some((e) => e.id === 'E1')).toBe(false);
  });
  it('B04–05 one action, no-op keeps future, new branch, cap and undoable reset', () => {
    const initial = createEnvelope(createSeed(), meta(0));
    const changed = commit(
      initial,
      { type: 'weaken', id: 'H1' },
      meta(1),
    ).envelope;
    const undone = moveCursor(changed, 0);
    expect(
      commit(undone, { type: 'restore', id: 'H1' }, meta(2)).envelope,
    ).toBe(undone);
    const reset = commit(
      changed,
      { type: 'replace', document: emptyBoard('new', 'residual') },
      meta(3),
    ).envelope;
    expect(moveCursor(reset, 1).snapshots[1].document).toEqual(
      changed.snapshots[1].document,
    );
    const branch = commit(
      undone,
      { type: 'weaken', id: 'H3' },
      meta(4),
    ).envelope;
    expect(branch.snapshots).toHaveLength(2);
    expect(branch.snapshots[1].id).toBe('snap-4');
    let env = initial;
    let trimmed = false;
    for (let i = 1; i < 65; i++) {
      const r = commit(
        env,
        { type: 'editBoard', patch: { title: `title ${i}` } },
        meta(i),
      );
      env = r.envelope;
      trimmed ||= r.trimmed;
    }
    expect(env.snapshots).toHaveLength(50);
    expect(env.cursor).toBe(49);
    expect(trimmed).toBe(true);
  });
  it('B06 JSON and dedicated Markdown preserve whole envelope including hostile fences', () => {
    const b = createSeed();
    b.decisionMemo =
      '```pruning-ui-json\n{"fake":true}\n``` <script>alert(1)</script>';
    const env = commit(
      createEnvelope(b, meta(0)),
      { type: 'weaken', id: 'H1' },
      meta(1),
    ).envelope;
    const cursor = moveCursor(env, 0);
    expect(importJson(exportJson(cursor))).toEqual(cursor);
    expect(importMarkdown(exportMarkdown(cursor))).toEqual(cursor);
    expect(exportMarkdown(cursor).match(/^```pruning-ui-json$/gm)).toHaveLength(
      1,
    );
    expect(() =>
      importMarkdown(exportMarkdown(cursor) + '\n```pruning-ui-json\n{}\n```'),
    ).toThrow();
    expect(() => importMarkdown('# plain')).toThrow();
  });
  it('B07 strict fields, versions, IDs, references, source and cursor limits', () => {
    const env = createEnvelope(createSeed(), meta(0));
    expect(() => importJson('{bad')).toThrow();
    expect(() =>
      parseEnvelope({ ...env, schemaVersion: 'workspace.v4' }),
    ).toThrow();
    expect(() => parseEnvelope({ ...env, hidden: 1 })).toThrow();
    expect(() => parseEnvelope({ ...env, cursor: 2 })).toThrow();
    const b = createSeed();
    b.factors[0].id = 'H1';
    expect(() => parseBoard(b)).toThrow(/重複/);
    const bad = createSeed();
    bad.effects[0].factorId = 'missing';
    expect(() => parseBoard(bad)).toThrow(/参照/);
    bad.sourceMaterials[0].text = 'あ'.repeat(64001);
    expect(() => parseBoard(bad)).toThrow();
    const missing = createSeed();
    missing.hypotheses.pop();
    expect(() => parseBoard(missing)).toThrow(/残余/);
    const gate = createSeed();
    gate.gates[0].expression = { kind: 'all', children: [] };
    expect(() => parseBoard(gate)).toThrow();
    let deep: GateExpression = {
      kind: 'condition',
      factorId: 'F1',
      is: 'present',
    };
    for (let i = 0; i < 8; i++) deep = { kind: 'not', child: deep };
    gate.gates[0].expression = deep;
    expect(() => parseBoard(gate)).toThrow(/深さ/);
  });
});
