import { useEditor } from '../EditorContext';
import { HypothesisInspector } from './HypothesisInspector';
import { FactorInspector } from './FactorInspector';
import { NoteInspector } from './NoteInspector';
import { GateInspector } from './GateInspector';
import { BoardInspector } from './BoardInspector';

export function InspectorPanel() {
  const { board, selection, state } = useEditor();
  const hypothesis = board.hypotheses.find((h) => h.id === selection.id),
    factor = board.factors.find((f) => f.id === selection.id),
    note = board.notes.find((n) => n.id === selection.id),
    gate = board.gates.find((g) => g.id === selection.id);
  const key = `${selection.id}:${state.envelope?.snapshots[state.envelope.cursor].id}`;
  return (
    <aside className="inspector pane" aria-label="インスペクター">
      <div className="pane-heading">
        <div>
          <p className="eyebrow">INSPECTOR</p>
          <h2>根拠と変化を見る</h2>
        </div>
        <span className="status-dot" />
      </div>
      <div className="inspector-body" key={key}>
        {selection.kind === 'hypothesis' && hypothesis ? (
          <HypothesisInspector hypothesis={hypothesis} />
        ) : selection.kind === 'factor' && factor ? (
          <FactorInspector factor={factor} />
        ) : selection.kind === 'note' && note ? (
          <NoteInspector note={note} />
        ) : selection.kind === 'gate' && gate ? (
          <GateInspector gate={gate} />
        ) : (
          <BoardInspector />
        )}
      </div>
    </aside>
  );
}
