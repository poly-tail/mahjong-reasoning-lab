import { ShieldCheck } from 'lucide-react';
import { useEditor } from '../EditorContext';
import type { Hypothesis } from '../../domain/model';
import { applyCommand } from '../../domain/commands';
import { evaluate, formatShare } from '../../domain/scoring';
import { compareBoards } from '../../domain/deltas';
import { Field, InputField } from '../../shared/ui/FormField';
import { formText, formNumber } from '../../shared/ui/formValues';
import { ContributionLedger } from './ContributionLedger';
import { SourceReferences } from './SourceReferences';

export function HypothesisInspector({
  hypothesis: h,
}: {
  hypothesis: Hypothesis;
}) {
  const { board, evaluation, deltas, execute, confirm, remove, add } =
    useEditor();
  const result = evaluation.hypotheses.find((r) => r.id === h.id)!;
  const delta = deltas.find((d) => d.id === h.id);
  function prune() {
    const after = applyCommand(board, { type: 'prune', id: h.id });
    const next = evaluate(after);
    const changes = compareBoards(board, after);
    confirm({
      title: `「${h.label}」をprune`,
      body: (
        <>
          <p>手動で計算対象外にします。カードと根拠は残り、復元できます。</p>
          <table>
            <thead>
              <tr>
                <th>仮説</th>
                <th>変更前</th>
                <th>変更後</th>
              </tr>
            </thead>
            <tbody>
              {board.hypotheses.map((item) => (
                <tr key={item.id}>
                  <td>{item.label}</td>
                  <td>
                    {formatShare(
                      evaluation.hypotheses.find((r) => r.id === item.id)!
                        .displayShare,
                    )}
                  </td>
                  <td>
                    {formatShare(
                      next.hypotheses.find((r) => r.id === item.id)!
                        .displayShare,
                    )}
                    <small>
                      {(
                        changes.find((d) => d.id === item.id)!.shareDelta * 100
                      ).toFixed(1)}{' '}
                      pt
                    </small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ),
      confirmLabel: 'pruneを適用',
      onConfirm: () => {
        execute({ type: 'prune', id: h.id }, `${h.label}をprune`);
      },
    });
  }
  return (
    <>
      <p className="eyebrow">HYPOTHESIS / 仮説</p>
      <h2>{h.label}</h2>
      <div className="inspector-share">
        <strong>{formatShare(result.displayShare)}</strong>
        <span>
          相対配分（未校正）
          <small>raw score {result.rawScore.toFixed(3)}</small>
        </span>
      </div>
      <div className="badge-row">
        {h.mustKeep && (
          <span className="badge">
            <ShieldCheck size={13} />
            保護
          </span>
        )}
        {h.residual && <span className="badge">残余</span>}
        <span className="badge amber">重要度 {h.decisionImpact} / 100</span>
        {h.manualAdjustment < 0 && <span className="badge">手動で弱化</span>}
      </div>
      {result.exclusionReason && (
        <p className="warning">{result.exclusionReason}</p>
      )}
      {h.riskNote && <p className="risk-note">{h.riskNote}</p>}
      <div className="button-row action-buttons">
        <button
          onClick={() =>
            execute({ type: 'weaken', id: h.id }, `${h.label}を弱める`)
          }
        >
          弱める
        </button>
        <button
          disabled={h.mustKeep || h.residual || h.manualPruned}
          title={h.mustKeep ? '保護枝はpruneできません' : undefined}
          onClick={prune}
        >
          prune
        </button>
        <button
          onClick={() =>
            execute({ type: 'restore', id: h.id }, `${h.label}を復元`)
          }
        >
          復元
        </button>
      </div>
      {h.mustKeep && (
        <p className="help">
          保護枝はprune・削除不可。確定したhard不成立は配分0です。
        </p>
      )}
      <ContributionLedger result={result} />
      <details open={Boolean(delta && Math.abs(delta.shareDelta) > 1e-12)}>
        <summary>直前の操作との差分</summary>
        {delta ? (
          <>
            <p>{delta.reason}</p>
            <div className="delta-grid">
              <span>
                raw変化 <b>{delta.rawScoreDelta.toFixed(3)}</b>
              </span>
              <span>
                配分変化 <b>{(delta.shareDelta * 100).toFixed(2)} pt</b>
              </span>
            </div>
            {delta.ownEffect !== null && (
              <p className="help">
                自身の変更: {(delta.ownEffect * 100).toFixed(2)} pt
                <br />
                他候補全体の変更: {(delta.otherEffect! * 100).toFixed(2)} pt
                <br />
                モデル内の対称分解です。現実の因果効果ではありません。
              </p>
            )}
            {deltas
              .filter(
                (d) =>
                  d.id !== h.id &&
                  (Math.abs(d.rawScoreDelta) > 1e-12 || d.includedChanged),
              )
              .map((d) => (
                <p key={d.id} className="help">
                  {board.hypotheses.find((h) => h.id === d.id)?.label}: raw Δ{' '}
                  {d.rawScoreDelta.toFixed(3)}
                  {d.includedChanged ? ' / 計算対象の変更' : ''}
                </p>
              ))}
          </>
        ) : (
          <p className="help">最初の履歴です。</p>
        )}
      </details>
      <details>
        <summary>仮説の編集</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const f = new FormData(event.currentTarget);
            execute(
              {
                type: 'editHypothesis',
                id: h.id,
                patch: {
                  label: formText(f, 'label'),
                  baseScore: formNumber(f, 'base'),
                  manualAdjustment: formNumber(f, 'manual'),
                  decisionImpact: formNumber(f, 'impact'),
                  riskNote: formText(f, 'risk'),
                  mustKeep: h.residual || f.has('keep'),
                },
              },
              '仮説を編集',
            );
          }}
        >
          <InputField
            label="仮説名"
            name="label"
            defaultValue={h.label}
            maxLength={120}
            required
          />
          <div className="form-grid">
            <InputField
              label="基準スコア"
              name="base"
              type="number"
              min={-5}
              max={5}
              step="0.1"
              defaultValue={h.baseScore}
              required
            />
            <InputField
              label="手動調整"
              name="manual"
              type="number"
              min={-5}
              max={5}
              step="0.1"
              defaultValue={h.manualAdjustment}
              required
            />
          </div>
          <InputField
            label="判断上の重要度"
            name="impact"
            type="number"
            min={0}
            max={100}
            defaultValue={h.decisionImpact}
            required
            hint="主観的重要度。確率・EVではなく、配分計算には使いません。"
          />
          <Field label="見落としたくない理由">
            <textarea name="risk" defaultValue={h.riskNote} maxLength={4000} />
          </Field>
          <label className="check-label">
            <input
              name="keep"
              type="checkbox"
              defaultChecked={h.mustKeep}
              disabled={h.residual}
            />
            保護する（prunedなら先に復元）
          </label>
          <button className="primary" type="submit">
            仮説の変更を保存
          </button>
        </form>
      </details>
      <SourceReferences refs={h.sourceRefs} />
      <div className="button-row">
        <button onClick={() => add('note', h.id)}>説明メモを追加</button>
        <button
          className="danger-text"
          disabled={h.mustKeep || h.residual}
          onClick={() => remove('hypothesis', h.id)}
        >
          仮説を削除
        </button>
      </div>
    </>
  );
}
