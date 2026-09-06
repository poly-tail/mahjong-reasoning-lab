import { useState } from 'react';
import type { Factor } from '../../domain/model';
import { factorAvailability } from '../../domain/gates';
import { useEditor } from '../EditorContext';
import { Field, InputField } from '../../shared/ui/FormField';
import { formText, formNumber } from '../../shared/ui/formValues';
import { SourceReferences } from './SourceReferences';
import { EffectForm, GroupForm } from './EffectForm';
import type { Command } from '../../domain/commands';

export function FactorInspector({ factor }: { factor: Factor }) {
  const { board, execute, remove } = useEditor();
  const effects = board.effects.filter((e) => e.factorId === factor.id);
  const [confidence, setConfidence] = useState(String(factor.confidence));
  const needsReason =
    Number(confidence) !== factor.confidence &&
    effects.some((e) => e.applicabilityConfidence !== 1);
  const availability = factorAvailability(factor);
  return (
    <>
      <p className="eyebrow">FACTOR / 要因</p>
      <h2>{factor.label}</h2>
      {availability && (
        <p className="warning">
          {availability}。否定の証拠としては適用しません。
        </p>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const state = formText(form, 'state'),
            kind = formText(form, 'kind'),
            opportunity = formText(form, 'opportunity');
          const commands: Command[] = [
            {
              type: 'editFactor',
              id: factor.id,
              patch: {
                label: formText(form, 'label'),
                kind:
                  kind === 'observation'
                    ? 'observation'
                    : kind === 'model_rule'
                      ? 'model_rule'
                      : 'assumption',
                state:
                  state === 'present'
                    ? 'present'
                    : state === 'absent'
                      ? 'absent'
                      : state === 'unobservable'
                        ? 'unobservable'
                        : 'unknown',
                confidence: formNumber(form, 'confidence'),
                opportunity:
                  opportunity === 'yes'
                    ? 'yes'
                    : opportunity === 'no'
                      ? 'no'
                      : 'unknown',
                verification: form.has('verified') ? 'verified' : 'unverified',
                sourceRefs: form.getAll('source').map(String),
              },
            },
          ];
          const reason = formText(form, 'reason');
          if (reason.trim())
            for (const owner of new Set(effects.map((e) => e.hypothesisId)))
              commands.push({
                type: 'addNote',
                value: {
                  id: crypto.randomUUID(),
                  ownerHypothesisId: owner,
                  parentNoteId: null,
                  order: board.notes.length,
                  label: '根拠信頼度の調整理由',
                  body: reason,
                  sourceRefs: factor.sourceRefs,
                },
              });
          execute({ type: 'batch', commands }, `${factor.label}を変更`);
        }}
      >
        <InputField
          label="要因名"
          name="label"
          defaultValue={factor.label}
          required
          maxLength={120}
        />
        <Field label="要因の種類">
          <select name="kind" defaultValue={factor.kind}>
            <option value="assumption">仮定</option>
            <option value="observation">観測</option>
            <option value="model_rule">モデル規則</option>
          </select>
        </Field>
        <Field label="要因の状態">
          <select name="state" defaultValue={factor.state}>
            <option value="present">あり (present)</option>
            <option value="absent">なし (absent)</option>
            <option value="unknown">未確認 (unknown)</option>
            <option value="unobservable">観測不能 (unobservable)</option>
          </select>
        </Field>
        <Field
          label="根拠信頼度"
          hint="入力者の信頼度です。真である確率とは断定しません。"
        >
          <input
            name="confidence"
            type="number"
            min={0}
            max={1}
            step="0.1"
            required
            value={confidence}
            onChange={(e) => setConfidence(e.target.value)}
          />
        </Field>
        <Field
          label="観測機会"
          hint="観測イベントの「なし」は、機会「あり」のときだけ否定として扱います。"
        >
          <select name="opportunity" defaultValue={factor.opportunity}>
            <option value="unknown">未確認</option>
            <option value="yes">あり</option>
            <option value="no">なし</option>
          </select>
        </Field>
        <label className="check-label">
          <input
            name="verified"
            type="checkbox"
            defaultChecked={factor.verification === 'verified'}
          />
          利用者が明示的に確認済み
        </label>
        <p className="help">
          アプリが正しさを保証する印ではありません。hard条件の確定には信頼度1も必要です。
        </p>
        {needsReason && (
          <Field label="根拠信頼度の変更理由">
            <textarea name="reason" required maxLength={4000} />
          </Field>
        )}
        {board.sourceMaterials.length > 0 && (
          <fieldset>
            <legend>原文の紐付け</legend>
            {board.sourceMaterials.map((s) => (
              <label key={s.id}>
                <input
                  type="checkbox"
                  name="source"
                  value={s.id}
                  defaultChecked={factor.sourceRefs.includes(s.id)}
                />
                {s.label}
              </label>
            ))}
          </fieldset>
        )}
        <button type="submit" className="primary">
          要因の変更を保存
        </button>
      </form>
      <section className="inspector-section">
        <h3>適用先と影響</h3>
        {effects.map((e) => (
          <details key={e.id}>
            <summary>
              {board.hypotheses.find((h) => h.id === e.hypothesisId)?.label}{' '}
              <span>
                {e.strength > 0 ? '+' : ''}
                {e.strength}
              </span>
            </summary>
            <EffectForm factor={factor} effect={e} />
          </details>
        ))}
      </section>
      <details open={effects.length === 0}>
        <summary>仮説への接続を追加</summary>
        <EffectForm factor={factor} />
      </details>
      <GroupForm />
      <SourceReferences refs={factor.sourceRefs} />
      <button
        className="danger-text"
        onClick={() => remove('factor', factor.id)}
      >
        要因を削除
      </button>
    </>
  );
}
