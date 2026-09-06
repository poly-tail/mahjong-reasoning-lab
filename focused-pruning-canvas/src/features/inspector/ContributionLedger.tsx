import type { HypothesisEvaluation, LedgerRow } from '../../domain/scoring';
import { useEditor } from '../EditorContext';
import { GateTree } from './GateInspector';
import { evaluateGate } from '../../domain/gates';
import { explainHypothesis } from '../../domain/explanations';

function Reasons({ rows }: { rows: LedgerRow[] }) {
  return rows.length ? (
    <ul className="reason-list">
      {rows.map((r) => (
        <li key={r.id}>
          <span>{r.label}</span>
          <b>
            {r.appliedValue > 0 ? '+' : ''}
            {r.appliedValue.toFixed(2)}
            <small>{r.unit === 'score' ? 'score' : '寄与'}</small>
          </b>
          <small>{r.reason}</small>
        </li>
      ))}
    </ul>
  ) : (
    <p className="help">該当なし</p>
  );
}
export function ContributionLedger({
  result,
}: {
  result: HypothesisEvaluation;
}) {
  const { board } = useEditor();
  const {
    weak: negative,
    support: positive,
    inactive,
    suppressed,
    unknown,
  } = explainHypothesis(board, result);
  return (
    <>
      <section className="inspector-section">
        <h3>
          なぜ薄いか <span>上位3件</span>
        </h3>
        <Reasons rows={negative.slice(0, 3)} />
      </section>
      <details>
        <summary>
          何が支持しているか <span>{positive.length}</span>
        </summary>
        <Reasons rows={positive} />
      </details>
      <details>
        <summary>
          適用されなかった理由 <span>{inactive.length}</span>
        </summary>
        <Reasons rows={inactive} />
      </details>
      <details>
        <summary>
          同根抑制 <span>{suppressed.length}</span>
        </summary>
        <Reasons rows={suppressed} />
      </details>
      <details>
        <summary>
          条件未確定 <span>{unknown.length}</span>
        </summary>
        <Reasons rows={unknown} />
      </details>
      <details>
        <summary>何なら復活するか / 成立条件</summary>
        <p className="help">
          明示された条件です。最小変更の組合せを計算したものではありません。
        </p>
        {result.gates.map((g) => (
          <div key={g.id}>
            <p className="quiet-badge">
              {g.mode} · {g.mode === 'informational' ? '寄与なし' : '条件評価'}
            </p>
            <GateTree tree={g.tree} />
          </div>
        ))}
        {board.effects
          .filter((e) => e.hypothesisId === result.id && e.when)
          .map((e) => {
            const tree = evaluateGate(e.when!, board.factors);
            return tree.value === 'true' ? null : (
              <div key={e.id}>
                <p>{e.id} の適用条件</p>
                <GateTree tree={tree} />
              </div>
            );
          })}
      </details>
      <details>
        <summary>寄与台帳と計算式</summary>
        <p className="formula">
          raw = base + {board.modelConfig.scoreScale} × 寄与合計 + 手動調整
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>項目 / 理由</th>
                <th>元値</th>
                <th>適用値</th>
              </tr>
            </thead>
            <tbody>
              {result.ledger.map((l) => (
                <tr key={l.id}>
                  <td>
                    {l.label}
                    <small>
                      {l.kind} · {l.unit}
                      <br />
                      {l.reason}
                    </small>
                  </td>
                  <td>{l.rawValue.toFixed(3)}</td>
                  <td>{l.appliedValue.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="help">正規化は非線形で、スコア加算行には含めません。</p>
        <Normalization />
      </details>
    </>
  );
}
function Normalization() {
  const { evaluation } = useEditor();
  const n = evaluation.normalizationSummary;
  return (
    <p className="formula">
      対象: {n.includedIds.join(', ')}
      <br />
      temperature: {n.temperature}
      <br />
      安定化の基準 m: {n.maxScaledScore.toFixed(4)}
      <br />Σ exp(x − m): {n.shiftedDenominator.toFixed(6)}
    </p>
  );
}
