import { useEffect, useMemo, useState } from 'react';
import { useStore } from 'zustand';
import {
  GitBranch,
  PanelLeft,
  PanelRight,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import type { BoardStore } from '../application/boardStore';
import { currentDocument } from '../application/history';
import { addItem } from '../application/editorCommands';
import { deletionPreview, type Entity } from '../domain/commands';
import { evaluate } from '../domain/scoring';
import { compareBoards } from '../domain/deltas';
import {
  EditorContext,
  type Confirmation,
  type Density,
  type Selection,
} from '../features/EditorContext';
import { Toolbar } from '../features/toolbar/Toolbar';
import { OutlinePanel } from '../features/outline/OutlinePanel';
import { isTextEditing } from '../features/outline/OutlineKeyboard';
import { FocusedPruningCanvas } from '../features/canvas/FocusedPruningCanvas';
import { InspectorPanel } from '../features/inspector/InspectorPanel';
import { TimelinePanel } from '../features/timeline/TimelinePanel';
import { ConfirmDialog } from '../shared/ui/ConfirmDialog';
import { RecoveryPanel, SaveMessages } from './RecoveryPanel';

export function App({ store }: { store: BoardStore }) {
  const state = useStore(store);
  const [selection, select] = useState<Selection>({
    kind: 'hypothesis',
    id: 'H2',
  });
  const [density, setDensity] = useState<Density>('standard');
  const [confirmation, confirm] = useState<Confirmation | null>(null);
  const [left, setLeft] = useState(false),
    [right, setRight] = useState(true);
  const board = state.envelope ? currentDocument(state.envelope) : null;
  const evaluation = useMemo(() => (board ? evaluate(board) : null), [board]);
  const deltas = useMemo(
    () =>
      state.envelope && state.envelope.cursor > 0
        ? compareBoards(
            state.envelope.snapshots[state.envelope.cursor - 1].document,
            currentDocument(state.envelope),
          )
        : [],
    [state.envelope],
  );
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (confirmation || isTextEditing(event.target) || event.isComposing)
        return;
      if (event.ctrlKey || event.metaKey) {
        if (event.key.toLowerCase() === 'z') {
          event.preventDefault();
          if (event.shiftKey) store.getState().redo();
          else store.getState().undo();
        } else if (event.key.toLowerCase() === 'y') {
          event.preventDefault();
          store.getState().redo();
        }
      }
    };
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, [store, confirmation]);
  function remove(entity: Entity, id: string) {
    if (!board) return;
    const preview = deletionPreview(board, entity, id);
    if (preview.blocked) {
      state.reportError(preview.blocked);
      return;
    }
    const all = [
      ...board.hypotheses,
      ...board.factors,
      ...board.notes,
      ...board.effects,
      ...board.gates,
      ...board.evidenceGroups,
    ];
    confirm({
      title: '参照関係を確認して削除',
      body: (
        <>
          <p>
            次の {preview.affected.length}{' '}
            要素を一操作で削除します。Undoで戻せます。
          </p>
          <ul>
            {preview.affected.map((id) => {
              const item = all.find((e) => e.id === id);
              return (
                <li key={id}>{item && 'label' in item ? item.label : id}</li>
              );
            })}
          </ul>
        </>
      ),
      confirmLabel: '削除を適用',
      onConfirm: () => {
        state.execute({ type: 'delete', entity, id }, '参照を含めて削除');
      },
    });
  }
  return (
    <div
      className={`app-shell ${left ? 'show-outline' : ''} ${right ? 'show-inspector' : ''}`}
    >
      <header className="app-header">
        <div className="brand-mark">
          <GitBranch size={23} />
        </div>
        <div className="brand">
          <h1>Focused Pruning Canvas</h1>
          <p>競合仮説・成立条件・薄まり理由を編集して比較</p>
        </div>
        <span className="local-badge">
          LOCAL FIRST <span>研究・牌譜検討用</span>
        </span>
        <div className={`save-indicator save-${state.status}`} role="status">
          {state.status === 'saved' ? (
            <CheckCircle2 size={15} />
          ) : (
            <AlertCircle size={15} />
          )}
          {
            {
              saved: '保存済み',
              unsaved: '未保存',
              blocked: '自動保存停止',
              conflict: '他タブ更新・保存停止',
            }[state.status]
          }
        </div>
      </header>
      {board && evaluation ? (
        <EditorContext.Provider
          value={{
            store,
            state,
            board,
            evaluation,
            deltas,
            selection,
            select,
            density,
            setDensity,
            confirm,
            remove,
            execute: state.execute,
            add: (kind, owner, parent) => {
              const id = crypto.randomUUID();
              const selectedOwner =
                selection.kind === 'hypothesis'
                  ? selection.id
                  : board.notes.find((n) => n.id === selection.id)
                      ?.ownerHypothesisId;
              try {
                if (
                  state.execute(
                    addItem(board, kind, id, owner ?? selectedOwner, parent),
                    `${kind === 'hypothesis' ? '仮説' : kind === 'factor' ? '要因' : 'メモ'}を追加`,
                  )
                )
                  select({ kind, id });
              } catch (error) {
                state.reportError(error);
              }
            },
          }}
        >
          <Toolbar />
          <div className="model-notice">
            <span>相対配分（未校正）</span>
            分類仮定と仮置き重みに依存し、実測確率ではありません。
            <span>
              {board.classificationAssumption.startsWith('デモ用')
                ? 'デモ用仮置きモデル · '
                : ''}
              麻雀理論・頻度は未検証
            </span>
            <details>
              <summary>モデルの留保</summary>
              <p>{board.classificationAssumption}</p>
            </details>
          </div>
          <SaveMessages store={store} confirm={confirm} />
          <nav className="pane-switch" aria-label="ペイン切替">
            <button
              aria-pressed={left}
              onClick={() => {
                setLeft(!left);
                if (!left) setRight(false);
              }}
            >
              <PanelLeft size={15} />
              アウトライン
            </button>
            <button
              aria-pressed={right}
              onClick={() => {
                setRight(!right);
                if (!right) setLeft(false);
              }}
            >
              <PanelRight size={15} />
              インスペクター
            </button>
          </nav>
          <main className="workspace">
            <OutlinePanel />
            <FocusedPruningCanvas />
            <InspectorPanel />
          </main>
          <TimelinePanel />
        </EditorContext.Provider>
      ) : (
        <RecoveryPanel store={store} confirm={confirm} />
      )}
      <ConfirmDialog
        confirmation={confirmation}
        onClose={() => confirm(null)}
      />
    </div>
  );
}
