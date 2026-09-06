import type {
  BoardDocument,
  Hypothesis,
  Factor,
  Effect,
  Note,
  EvidenceGroup,
  Gate,
} from './model';
import { parseBoard } from './validation';
import { expressionFactorIds } from './gates';

export type Entity =
  | 'hypothesis'
  | 'factor'
  | 'note'
  | 'effect'
  | 'gate'
  | 'group';
export type Command =
  | { type: 'replace'; document: BoardDocument }
  | {
      type: 'editBoard';
      patch: Partial<
        Pick<
          BoardDocument,
          | 'title'
          | 'question'
          | 'classificationAssumption'
          | 'decisionMemo'
          | 'reflectionMemo'
          | 'modelConfig'
          | 'sourceMaterials'
        >
      >;
    }
  | { type: 'addHypothesis'; value: Hypothesis }
  | {
      type: 'editHypothesis';
      id: string;
      patch: Partial<Omit<Hypothesis, 'id' | 'residual'>>;
    }
  | { type: 'addFactor'; value: Factor }
  | { type: 'editFactor'; id: string; patch: Partial<Omit<Factor, 'id'>> }
  | { type: 'addEffect'; value: Effect }
  | { type: 'editEffect'; id: string; patch: Partial<Omit<Effect, 'id'>> }
  | { type: 'addNote'; value: Note }
  | { type: 'editNote'; id: string; patch: Partial<Omit<Note, 'id'>> }
  | { type: 'addGroup'; value: EvidenceGroup }
  | { type: 'editGroup'; id: string; patch: Partial<Omit<EvidenceGroup, 'id'>> }
  | { type: 'addGate'; value: Gate }
  | { type: 'editGate'; id: string; patch: Partial<Omit<Gate, 'id'>> }
  | {
      type: 'weaken' | 'restore' | 'prune' | 'indentNote' | 'outdentNote';
      id: string;
    }
  | { type: 'delete'; entity: Entity; id: string }
  | { type: 'batch'; commands: Command[] };

export function noteDescendants(board: BoardDocument, id: string): string[] {
  const found = new Set([id]);
  let added = true;
  while (added) {
    added = false;
    for (const n of board.notes)
      if (n.parentNoteId && found.has(n.parentNoteId) && !found.has(n.id)) {
        found.add(n.id);
        added = true;
      }
  }
  return [...found];
}
export function deletionPreview(
  board: BoardDocument,
  entity: Entity,
  id: string,
): { blocked: string | null; affected: string[] } {
  if (entity === 'hypothesis') {
    const h = board.hypotheses.find((h) => h.id === id);
    if (!h) return { blocked: '仮説が見つかりません', affected: [] };
    if (h.mustKeep || h.residual)
      return { blocked: '保護/残余枝は削除・pruneできません', affected: [] };
    return {
      blocked: null,
      affected: [
        id,
        ...board.effects.filter((e) => e.hypothesisId === id).map((e) => e.id),
        ...board.gates.filter((g) => g.hypothesisId === id).map((g) => g.id),
        ...board.notes
          .filter((n) => n.ownerHypothesisId === id)
          .map((n) => n.id),
      ],
    };
  }
  if (entity === 'factor') {
    const gates = board.gates.filter((g) =>
      expressionFactorIds(g.expression).includes(id),
    );
    const contexts = board.effects.filter(
      (e) => e.when && expressionFactorIds(e.when).includes(id),
    );
    if (gates.length || contexts.length)
      return {
        blocked: `条件式から参照されています: ${[...gates, ...contexts].map((e) => e.id).join('、')}。先に参照を編集/解除してください`,
        affected: [],
      };
    return {
      blocked: null,
      affected: [
        id,
        ...board.effects.filter((e) => e.factorId === id).map((e) => e.id),
      ],
    };
  }
  if (entity === 'note')
    return { blocked: null, affected: noteDescendants(board, id) };
  if (
    entity === 'group' &&
    (board.effects.some((e) => e.evidenceGroupId === id) ||
      board.gates.some((g) => g.evidenceGroupId === id))
  )
    return {
      blocked: '同根グループの割当を先に解除してください',
      affected: [],
    };
  return { blocked: null, affected: [id] };
}
function getById<T extends { id: string }>(items: T[], id: string): T {
  const value = items.find((i) => i.id === id);
  if (!value) throw new Error(`要素が見つかりません: ${id}`);
  return value;
}
function mutate(board: BoardDocument, command: Command): BoardDocument {
  switch (command.type) {
    case 'replace':
      return structuredClone(command.document);
    case 'batch':
      return command.commands.reduce(mutate, board);
    case 'editBoard':
      Object.assign(board, command.patch);
      break;
    case 'addHypothesis':
      board.hypotheses.push(command.value);
      break;
    case 'editHypothesis':
      Object.assign(getById(board.hypotheses, command.id), command.patch);
      break;
    case 'addFactor':
      board.factors.push(command.value);
      break;
    case 'editFactor':
      Object.assign(getById(board.factors, command.id), command.patch);
      break;
    case 'addEffect':
      board.effects.push(command.value);
      break;
    case 'editEffect':
      Object.assign(getById(board.effects, command.id), command.patch);
      break;
    case 'addNote':
      board.notes.push(command.value);
      break;
    case 'editNote':
      Object.assign(getById(board.notes, command.id), command.patch);
      break;
    case 'addGroup':
      board.evidenceGroups.push(command.value);
      break;
    case 'editGroup':
      Object.assign(getById(board.evidenceGroups, command.id), command.patch);
      break;
    case 'addGate':
      board.gates.push(command.value);
      break;
    case 'editGate':
      Object.assign(getById(board.gates, command.id), command.patch);
      break;
    case 'weaken':
      getById(board.hypotheses, command.id).manualAdjustment = -1;
      break;
    case 'restore': {
      const h = getById(board.hypotheses, command.id);
      h.manualAdjustment = 0;
      h.manualPruned = false;
      break;
    }
    case 'prune': {
      const h = getById(board.hypotheses, command.id);
      if (h.mustKeep || h.residual)
        throw new Error('保護/残余枝はpruneできません');
      h.manualPruned = true;
      break;
    }
    case 'indentNote': {
      const note = getById(board.notes, command.id);
      const siblings = board.notes
        .filter(
          (n) =>
            n.ownerHypothesisId === note.ownerHypothesisId &&
            n.parentNoteId === note.parentNoteId,
        )
        .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
      const previous = siblings[siblings.indexOf(note) - 1];
      if (previous) {
        note.parentNoteId = previous.id;
        note.order =
          Math.max(
            -1,
            ...board.notes
              .filter((n) => n.parentNoteId === previous.id && n !== note)
              .map((n) => n.order),
          ) + 1;
      }
      break;
    }
    case 'outdentNote': {
      const note = getById(board.notes, command.id);
      if (!note.parentNoteId) break;
      const parent = getById(board.notes, note.parentNoteId);
      note.parentNoteId = parent.parentNoteId;
      board.notes
        .filter(
          (n) =>
            n.ownerHypothesisId === note.ownerHypothesisId &&
            n.parentNoteId === parent.parentNoteId &&
            n !== note &&
            n.order > parent.order,
        )
        .forEach((n) => {
          n.order += 1;
        });
      note.order = parent.order + 1;
      break;
    }
    case 'delete': {
      const preview = deletionPreview(board, command.entity, command.id);
      if (preview.blocked) throw new Error(preview.blocked);
      const ids = new Set(preview.affected);
      board.hypotheses = board.hypotheses.filter((h) => !ids.has(h.id));
      board.factors = board.factors.filter((f) => !ids.has(f.id));
      board.effects = board.effects.filter((e) => !ids.has(e.id));
      board.notes = board.notes.filter((n) => !ids.has(n.id));
      board.gates = board.gates.filter((g) => !ids.has(g.id));
      board.evidenceGroups = board.evidenceGroups.filter((g) => !ids.has(g.id));
      break;
    }
  }
  return board;
}
export function applyCommand(
  board: BoardDocument,
  command: Command,
): BoardDocument {
  return parseBoard(mutate(structuredClone(board), command));
}
