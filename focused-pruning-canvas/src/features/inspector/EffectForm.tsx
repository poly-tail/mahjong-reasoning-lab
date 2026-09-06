import { useState } from 'react';
import type { Effect, Factor } from '../../domain/model';
import type { Command } from '../../domain/commands';
import { useEditor } from '../EditorContext';
import { Field, InputField } from '../../shared/ui/FormField';
import { formText, formNumber } from '../../shared/ui/formValues';
import { GateTree } from './GateInspector';
import { evaluateGate } from '../../domain/gates';

export function EffectForm({
  factor,
  effect,
}: {
  factor: Factor;
  effect?: Effect;
}) {
  const { board, execute, remove } = useEditor();
  const [applicationConfidence, setApplicationConfidence] = useState(
    String(effect?.applicabilityConfidence ?? 1),
  );
  const needsReason =
    Number(applicationConfidence) !== 1 &&
    factor.confidence !== 1 &&
    Number(applicationConfidence) !== (effect?.applicabilityConfidence ?? 1);
  return (
    <form
      className="effect-form"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const whenValue = formText(form, 'when');
        const value: Effect = {
          id: effect?.id ?? crypto.randomUUID(),
          factorId: factor.id,
          hypothesisId: formText(form, 'target'),
          strength: formNumber(form, 'strength'),
          applicabilityConfidence: Number(applicationConfidence),
          activeStates: form
            .getAll('active')
            .map((s) => (s === 'present' ? 'present' : 'absent')),
          evidenceGroupId: formText(form, 'group') || null,
          sourceRefs: effect?.sourceRefs ?? factor.sourceRefs,
          ...(effect?.when
            ? { when: effect.when }
            : whenValue
              ? {
                  when: {
                    kind: 'condition',
                    factorId: whenValue,
                    is: 'present',
                  },
                }
              : {}),
        };
        const commands: Command[] = [
          effect
            ? { type: 'editEffect', id: effect.id, patch: value }
            : { type: 'addEffect', value },
        ];
        const reason = formText(form, 'reason');
        if (reason.trim())
          commands.push({
            type: 'addNote',
            value: {
              id: crypto.randomUUID(),
              ownerHypothesisId: value.hypothesisId,
              parentNoteId: null,
              order: board.notes.length,
              label: '適用信頼度の調整理由',
              body: reason,
              sourceRefs: factor.sourceRefs,
            },
          });
        execute(
          { type: 'batch', commands },
          effect ? '効果の接続を編集' : '要因と仮説を接続',
        );
      }}
    >
      <Field label="接続先の仮説">
        <select
          name="target"
          defaultValue={
            effect?.hypothesisId ??
            board.hypotheses.find((h) => !h.residual)?.id
          }
        >
          {board.hypotheses.map((h) => (
            <option key={h.id} value={h.id}>
              {h.label}
            </option>
          ))}
        </select>
      </Field>
      <div className="form-grid">
        <InputField
          label="影響強度"
          name="strength"
          type="number"
          min={-2}
          max={2}
          step="0.1"
          defaultValue={effect?.strength ?? 1}
          required
        />
        <Field label="適用信頼度">
          <input
            type="number"
            min={0}
            max={1}
            step="0.1"
            required
            value={applicationConfidence}
            onChange={(e) => setApplicationConfidence(e.target.value)}
          />
        </Field>
      </div>
      <fieldset>
        <legend>適用する状態</legend>
        <label>
          <input
            type="checkbox"
            name="active"
            value="present"
            defaultChecked={!effect || effect.activeStates.includes('present')}
          />
          あり
        </label>
        <label>
          <input
            type="checkbox"
            name="active"
            value="absent"
            defaultChecked={effect?.activeStates.includes('absent')}
          />
          なし
        </label>
      </fieldset>
      <Field label="同根グループ">
        <select name="group" defaultValue={effect?.evidenceGroupId ?? ''}>
          <option value="">割当なし</option>
          {board.evidenceGroups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.label} ({g.aggregation})
            </option>
          ))}
        </select>
      </Field>
      {effect?.when ? (
        <>
          <p className="section-label">適用条件（読取）</p>
          <GateTree tree={evaluateGate(effect.when, board.factors)} />
        </>
      ) : (
        <Field label="適用条件プリセット">
          <select name="when" defaultValue="">
            <option value="">常に適用</option>
            {board.factors.map((f) => (
              <option key={f.id} value={f.id}>
                {f.label} = あり
              </option>
            ))}
          </select>
        </Field>
      )}
      <p className="help">
        根拠信頼度と適用信頼度で同じ不確実性を二重に下げないでください。
      </p>
      <Field
        label="適用信頼度の変更理由"
        hint="二つの信頼度を調整するときは説明メモとして残します。"
      >
        <textarea name="reason" required={needsReason} maxLength={4000} />
      </Field>
      <div className="button-row">
        <button type="submit" className="primary">
          {effect ? '接続の変更を保存' : '接続を追加'}
        </button>
        {effect && (
          <button
            type="button"
            className="danger-text"
            onClick={() => remove('effect', effect.id)}
          >
            接続を解除
          </button>
        )}
      </div>
    </form>
  );
}
export function GroupForm() {
  const { execute } = useEditor();
  return (
    <details>
      <summary>同根グループを作成</summary>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const f = new FormData(event.currentTarget);
          const aggregation = formText(f, 'aggregation');
          execute(
            {
              type: 'addGroup',
              value: {
                id: crypto.randomUUID(),
                label: formText(f, 'label'),
                aggregation:
                  aggregation === 'mean'
                    ? 'mean'
                    : aggregation === 'sum'
                      ? 'sum'
                      : 'maxAbs',
                rationale: formText(f, 'rationale'),
              },
            },
            '同根グループを作成',
          );
        }}
      >
        <InputField label="グループ名" name="label" required maxLength={120} />
        <Field label="集約規則">
          <select name="aggregation" defaultValue="maxAbs">
            <option value="maxAbs">maxAbs · 最大絶対値だけ</option>
            <option value="mean">mean · 有効な寄与の平均</option>
            <option value="sum">sum · 意図した加算</option>
          </select>
        </Field>
        <Field
          label="同根と判断した理由"
          hint="sum は加算理由が必須です。統計的相関の推定ではありません。"
        >
          <textarea name="rationale" maxLength={4000} />
        </Field>
        <button type="submit">グループを作成</button>
      </form>
    </details>
  );
}
