import { useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Plus,
  Pencil,
  ShieldCheck,
} from 'lucide-react';
import { useEditor, type Selection } from '../EditorContext';
import { composing, isTextEditing } from './OutlineKeyboard';
import { addItem } from '../../application/editorCommands';
import type { Command } from '../../domain/commands';
import { formatShare } from '../../domain/scoring';

export function OutlinePanel() {
  const editor = useEditor();
  const { board, selection, select, add, execute } = editor;
  const [editing, setEditing] = useState<string | null>(null);
  const [structure, setStructure] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const panelRef = useRef<HTMLElement>(null);
  function rename(kind: Selection['kind'], id: string, label: string): Command {
    if (kind === 'hypothesis')
      return { type: 'editHypothesis', id, patch: { label } };
    if (kind === 'factor') return { type: 'editFactor', id, patch: { label } };
    if (kind === 'note') return { type: 'editNote', id, patch: { label } };
    return { type: 'editBoard', patch: { title: label } };
  }
  function commitLabel(item: Selection, label: string, sibling: boolean) {
    if (!label.trim()) {
      setEditing(null);
      return;
    }
    if (
      sibling &&
      (item.kind === 'hypothesis' ||
        item.kind === 'factor' ||
        item.kind === 'note')
    ) {
      const id = crypto.randomUUID();
      const note = board.notes.find((n) => n.id === item.id);
      const command = addItem(
        board,
        item.kind,
        id,
        note?.ownerHypothesisId,
        note?.parentNoteId,
      );
      if (
        execute(
          {
            type: 'batch',
            commands: [rename(item.kind, item.id, label), command],
          },
          'ラベル確定と兄弟追加',
        )
      ) {
        select({ kind: item.kind, id });
        setEditing(id);
      }
    } else {
      execute(rename(item.kind, item.id, label), 'ラベルを変更');
      setEditing(null);
    }
  }
  function row(item: Selection, label: string, depth = 0, extra?: string) {
    return (
      <div
        key={item.id}
        className={`outline-row ${selection.id === item.id ? 'selected' : ''}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onKeyDown={(event) => {
          if (isTextEditing(event.target)) return;
          if (event.key === 'Escape') {
            setStructure(false);
            return;
          }
          if (
            (event.ctrlKey || event.metaKey) &&
            event.key === 'Delete' &&
            item.kind !== 'board' &&
            item.kind !== 'gate'
          ) {
            event.preventDefault();
            editor.remove(item.kind, item.id);
          }
          if (
            structure &&
            item.kind === 'note' &&
            event.key === 'Tab' &&
            !composing(event.nativeEvent, false)
          ) {
            event.preventDefault();
            execute(
              {
                type: event.shiftKey ? 'outdentNote' : 'indentNote',
                id: item.id,
              },
              event.shiftKey ? 'メモを字上げ' : 'メモを字下げ',
            );
            select(item);
            requestAnimationFrame(() => {
              const buttons =
                panelRef.current?.querySelectorAll<HTMLButtonElement>(
                  'button[data-outline-id]',
                );
              const button =
                buttons &&
                Array.from(buttons).find(
                  (button) => button.dataset.outlineId === item.id,
                );
              button?.focus();
            });
          }
        }}
      >
        {editing === item.id ? (
          <OutlineLabel
            key={item.id}
            label={label}
            commit={(value, sibling) => commitLabel(item, value, sibling)}
            cancel={() => setEditing(null)}
          />
        ) : (
          <button
            className="row-label"
            data-outline-id={item.id}
            aria-pressed={selection.id === item.id}
            onClick={() => select(item)}
            onDoubleClick={() => setEditing(item.id)}
            title={label}
          >
            {item.kind === 'note' && <FileText size={12} />}
            <span>{label}</span>
          </button>
        )}
        {extra && <span className="outline-value">{extra}</span>}
        <button
          className="icon-button row-edit"
          aria-label={`${label}のラベルを編集`}
          onClick={() => {
            select(item);
            setEditing(item.id);
          }}
        >
          <Pencil size={12} />
        </button>
      </div>
    );
  }
  function notes(
    owner: string,
    parent: string | null = null,
    depth = 1,
  ): React.ReactNode {
    return board.notes
      .filter((n) => n.ownerHypothesisId === owner && n.parentNoteId === parent)
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id))
      .map((n) => (
        <div key={n.id}>
          {row({ kind: 'note', id: n.id }, n.label, depth)}
          {notes(owner, n.id, depth + 1)}
        </div>
      ));
  }
  return (
    <aside ref={panelRef} className="outline pane" aria-label="アウトライン">
      <div className="pane-heading">
        <div>
          <p className="eyebrow">STRUCTURE</p>
          <h2>考察のアウトライン</h2>
        </div>
        <span className="count">{board.hypotheses.length}</span>
      </div>
      <div className="outline-body">
        <p className="section-label">問い</p>
        {row({ kind: 'board', id: board.id }, board.title)}
        <div className="section-heading">
          <span>競合仮説</span>
          <button
            className="icon-button"
            aria-label="仮説を追加"
            onClick={() => add('hypothesis')}
          >
            <Plus size={16} />
          </button>
        </div>
        {board.hypotheses.map((h) => (
          <div key={h.id} className="outline-branch">
            <div className="branch-heading">
              <button
                className="icon-button"
                aria-label={`${h.label}のメモを${collapsed.has(h.id) ? '展開' : '折り畳む'}`}
                onClick={() =>
                  setCollapsed((previous) => {
                    const next = new Set(previous);
                    if (next.has(h.id)) next.delete(h.id);
                    else next.add(h.id);
                    return next;
                  })
                }
              >
                {collapsed.has(h.id) ? (
                  <ChevronRight size={14} />
                ) : (
                  <ChevronDown size={14} />
                )}
              </button>
              <span>{h.id.length < 8 ? h.id : '仮説'}</span>
              {h.mustKeep && <ShieldCheck size={13} aria-label="保護" />}
              <button
                className="icon-button"
                aria-label={`${h.label}にメモを追加`}
                onClick={() => add('note', h.id)}
              >
                <Plus size={13} />
              </button>
            </div>
            {row(
              { kind: 'hypothesis', id: h.id },
              h.label,
              0,
              formatShare(
                editor.evaluation.hypotheses.find((r) => r.id === h.id)!
                  .displayShare,
              ),
            )}
            {!collapsed.has(h.id) && notes(h.id)}
          </div>
        ))}
        <div className="section-heading">
          <span>
            要因 <small>{board.factors.length}</small>
          </span>
          <button
            className="icon-button"
            aria-label="要因を追加"
            onClick={() => add('factor')}
          >
            <Plus size={16} />
          </button>
        </div>
        {board.factors.map((f) => row({ kind: 'factor', id: f.id }, f.label))}
      </div>
      <div className="outline-footer">
        <label className="check-label">
          <input
            type="checkbox"
            checked={structure}
            onChange={(e) => setStructure(e.target.checked)}
          />
          メモの構造編集
        </label>
        <small>
          {structure
            ? 'メモ行でTab: 字下げ / Shift+Tab: 字上げ。Escで終了。'
            : 'ラベルをダブルクリックで編集。Enterで兄弟を追加。'}
        </small>
      </div>
    </aside>
  );
}
export function OutlineLabel({
  label,
  commit,
  cancel,
}: {
  label: string;
  commit: (value: string, sibling: boolean) => void;
  cancel: () => void;
}) {
  const [value, setValue] = useState(label);
  const activeComposition = useRef(false);
  const handled = useRef(false);
  return (
    <input
      className="outline-label-input"
      aria-label="項目ラベル"
      autoFocus
      maxLength={120}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onCompositionStart={() => {
        activeComposition.current = true;
      }}
      onCompositionEnd={() => {
        activeComposition.current = false;
      }}
      onBlur={() => {
        if (!handled.current && !activeComposition.current) {
          handled.current = true;
          commit(value, false);
        }
      }}
      onKeyDown={(e) => {
        if (composing(e.nativeEvent, activeComposition.current)) return;
        if (e.key === 'Escape') {
          e.preventDefault();
          handled.current = true;
          cancel();
        }
        if (e.key === 'Enter') {
          e.preventDefault();
          handled.current = true;
          commit(value, true);
        }
      }}
    />
  );
}
