import type { Note } from '../../domain/model';
import { noteDescendants } from '../../domain/commands';
import { useEditor } from '../EditorContext';
import { Field, InputField } from '../../shared/ui/FormField';
import { formText } from '../../shared/ui/formValues';
import { SourceReferences } from './SourceReferences';

export function NoteInspector({ note }: { note: Note }) {
  const { board, execute, remove, add } = useEditor();
  const descendants = new Set(noteDescendants(board, note.id));
  return (
    <>
      <p className="eyebrow">NOTE / 説明メモ</p>
      <h2>{note.label}</h2>
      <p className="help">
        説明の階層です。追加・字下げで配分は変わりません。数値要因にしたい場合は、要因を作成して仮説へ接続してください。
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          execute(
            {
              type: 'editNote',
              id: note.id,
              patch: {
                label: formText(form, 'label'),
                body: formText(form, 'body'),
                parentNoteId: formText(form, 'parent') || null,
                sourceRefs: form.getAll('source').map(String),
              },
            },
            '説明メモを編集',
          );
        }}
      >
        <InputField
          label="メモのタイトル"
          name="label"
          defaultValue={note.label}
          required
          maxLength={120}
        />
        <Field label="メモの本文">
          <textarea
            name="body"
            rows={7}
            defaultValue={note.body}
            maxLength={4000}
          />
        </Field>
        <Field label="親メモ">
          <select name="parent" defaultValue={note.parentNoteId ?? ''}>
            <option value="">仮説の直下</option>
            {board.notes
              .filter(
                (n) =>
                  n.ownerHypothesisId === note.ownerHypothesisId &&
                  !descendants.has(n.id),
              )
              .map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
          </select>
        </Field>
        {board.sourceMaterials.length > 0 && (
          <fieldset>
            <legend>根拠原文の紐付け</legend>
            {board.sourceMaterials.map((s) => (
              <label key={s.id}>
                <input
                  type="checkbox"
                  name="source"
                  value={s.id}
                  defaultChecked={note.sourceRefs.includes(s.id)}
                />
                {s.label}
              </label>
            ))}
          </fieldset>
        )}
        <button className="primary" type="submit">
          メモの変更を保存
        </button>
      </form>
      <div className="button-row">
        <button
          onClick={() =>
            execute({ type: 'indentNote', id: note.id }, 'メモを字下げ')
          }
        >
          字下げ
        </button>
        <button
          onClick={() =>
            execute({ type: 'outdentNote', id: note.id }, 'メモを字上げ')
          }
        >
          字上げ
        </button>
        <button onClick={() => add('note', note.ownerHypothesisId, note.id)}>
          子メモを追加
        </button>
      </div>
      <SourceReferences refs={note.sourceRefs} />
      <button className="danger-text" onClick={() => remove('note', note.id)}>
        メモを削除
      </button>
    </>
  );
}
