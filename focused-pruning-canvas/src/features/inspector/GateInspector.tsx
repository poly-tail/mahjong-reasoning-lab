import type { GateEvaluation } from '../../domain/gates';
import type { Gate } from '../../domain/model';
import { evaluateGate } from '../../domain/gates';
import { useEditor } from '../EditorContext';

const truthLabel = (value: string) =>
  value === 'true' ? '成立' : value === 'false' ? '不成立' : '未確定';
export function GateTree({ tree }: { tree: GateEvaluation }) {
  return (
    <div className={`gate-tree truth-${tree.value}`}>
      <div>
        <strong>{tree.label}</strong>
        <span>{truthLabel(tree.value)}</span>
      </div>
      <small>{tree.reason}</small>
      {tree.children.map((child, i) => (
        <GateTree key={i} tree={child} />
      ))}
    </div>
  );
}
export function GateInspector({ gate }: { gate: Gate }) {
  const { board, remove } = useEditor();
  return (
    <>
      <p className="eyebrow">GATE / 成立条件</p>
      <h2>条件の評価</h2>
      <p>{gate.explanation}</p>
      <div className="quiet-badge">
        {gate.mode} ·{' '}
        {gate.mode === 'informational'
          ? '数値寄与なし'
          : gate.mode === 'soft'
            ? `不成立時 ${gate.falsePenalty}`
            : '確認済み false だけ除外'}
      </div>
      <GateTree
        tree={evaluateGate(
          gate.expression,
          board.factors,
          gate.mode === 'hard',
        )}
      />
      <p className="help">
        条件に使うだけでは重みを加算しません。条件値は要因のフォームで変更できます。式とmodeは検証付きJSON/専用Markdownでも保持されます。
      </p>
      <button className="danger-text" onClick={() => remove('gate', gate.id)}>
        このゲートを削除
      </button>
    </>
  );
}
