import type { BoardDocument } from '../domain/model';
import type { Command } from '../domain/commands';
export function addItem(
  board: BoardDocument,
  kind: 'hypothesis' | 'factor' | 'note',
  id: string,
  owner?: string,
  parent: string | null = null,
): Command {
  if (kind === 'hypothesis')
    return {
      type: 'addHypothesis',
      value: {
        id,
        label: '新しい仮説',
        baseScore: 0,
        manualAdjustment: 0,
        manualPruned: false,
        mustKeep: false,
        residual: false,
        decisionImpact: 50,
        riskNote: '',
        sourceRefs: [],
      },
    };
  if (kind === 'factor')
    return {
      type: 'addFactor',
      value: {
        id,
        label: '新しい要因',
        kind: 'assumption',
        state: 'unknown',
        confidence: 0.5,
        opportunity: 'unknown',
        verification: 'unverified',
        sourceRefs: [],
      },
    };
  if (!owner) throw new Error('説明メモを追加する仮説を選択してください');
  return {
    type: 'addNote',
    value: {
      id,
      ownerHypothesisId: owner,
      parentNoteId: parent,
      order:
        Math.max(
          -1,
          ...board.notes
            .filter(
              (n) => n.ownerHypothesisId === owner && n.parentNoteId === parent,
            )
            .map((n) => n.order),
        ) + 1,
      label: '新しいメモ',
      body: '',
      sourceRefs: [],
    },
  };
}
