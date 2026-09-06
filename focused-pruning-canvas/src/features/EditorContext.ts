import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import type { BoardStore, BoardState } from '../application/boardStore';
import type { BoardDocument } from '../domain/model';
import type { Evaluation } from '../domain/scoring';
import type { BoardDelta } from '../domain/deltas';
import type { Command, Entity } from '../domain/commands';

export type Selection = {
  kind: 'board' | 'hypothesis' | 'factor' | 'note' | 'gate';
  id: string;
};
export type Density = 'conclusion' | 'standard' | 'expanded';
export interface Confirmation {
  title: string;
  body: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
}
export interface Editor {
  store: BoardStore;
  state: BoardState;
  board: BoardDocument;
  evaluation: Evaluation;
  deltas: BoardDelta[];
  selection: Selection;
  select: (selection: Selection) => void;
  density: Density;
  setDensity: (density: Density) => void;
  confirm: (confirmation: Confirmation) => void;
  remove: (entity: Entity, id: string) => void;
  execute: (command: Command, label: string) => boolean;
  add: (
    kind: 'hypothesis' | 'factor' | 'note',
    owner?: string,
    parent?: string | null,
  ) => void;
}
export const EditorContext = createContext<Editor | null>(null);
export function useEditor(): Editor {
  const value = useContext(EditorContext);
  if (!value) throw new Error('Editor context is unavailable');
  return value;
}
