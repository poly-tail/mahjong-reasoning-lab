import { useMemo, useRef } from 'react';
import {
  Background,
  ReactFlow,
  Handle,
  Position,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react';
import {
  Maximize,
  Minus,
  Plus,
  ShieldCheck,
  GitBranch,
  AlertTriangle,
} from 'lucide-react';
import { useEditor } from '../EditorContext';
import { graphAdapter, type CanvasNode } from './graphAdapter';
import { formatShare } from '../../domain/scoring';

function CanvasCard({ data }: NodeProps<CanvasNode>) {
  if (data.kind === 'board')
    return (
      <div className="question-node">
        <span className="eyebrow">FOCUS QUESTION</span>
        <strong>{data.label}</strong>
        <small>{data.subtitle}</small>
        <Handle type="source" position={Position.Right} />
      </div>
    );
  if (data.kind === 'hypothesis')
    return (
      <div
        className={`hypothesis-node ${data.selected ? 'is-selected' : ''} ${data.residual ? 'is-residual' : ''} ${data.excluded ? 'is-excluded' : ''}`}
      >
        <Handle type="target" id="main" position={Position.Left} />
        <Handle type="target" id="evidence" position={Position.Right} />
        <div className="node-kicker">
          <span>{data.subtitle}</span>
          {data.protected && <ShieldCheck size={14} aria-label="保護" />}
        </div>
        <strong>{data.label}</strong>
        <div className="node-stats">
          <span className="share-number">{formatShare(data.share ?? 0)}</span>
          <span className="impact">
            <AlertTriangle size={11} />
            重要度 {data.impact}
          </span>
        </div>
        <div className="share-track">
          <div style={{ width: `${(data.share ?? 0) * 100}%` }} />
        </div>
      </div>
    );
  const state =
    data.state === 'present'
      ? 'あり'
      : data.state === 'absent'
        ? 'なし'
        : data.state === 'unobservable'
          ? '観測不能'
          : '未確認';
  return (
    <div
      className={`factor-node ${data.kind === 'gate' ? 'gate-node' : ''} ${data.selected ? 'is-selected' : ''}`}
    >
      <Handle id="factor" type="source" position={Position.Left} />
      <div>
        <span>{data.subtitle}</span>
        <small>
          {data.kind === 'factor'
            ? `${state} · C ${data.confidence}`
            : '条件表示'}
        </small>
      </div>
      <strong>{data.label}</strong>
    </div>
  );
}
const nodeTypes = { canvasCard: CanvasCard };
export function FocusedPruningCanvas() {
  const { board, evaluation, selection, select, density } = useEditor();
  const graph = useMemo(
    () => graphAdapter(board, evaluation, selection, density),
    [board, evaluation, selection, density],
  );
  const flow = useRef<ReactFlowInstance<CanvasNode> | null>(null);
  return (
    <section className="canvas pane" aria-label="仮説キャンバス">
      <div className="canvas-heading">
        <div>
          <p className="eyebrow">FOCUSED PRUNING CANVAS</p>
          <h2>
            <GitBranch size={19} />
            本線を見て、薄い枝を確かめる
          </h2>
        </div>
        <span className="quiet-badge">
          {board.hypotheses.length} 仮説 / {board.factors.length} 要因
        </span>
      </div>
      <div className="canvas-area">
        <ReactFlow<CanvasNode>
          nodes={graph.nodes}
          edges={graph.edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          minZoom={0.25}
          maxZoom={1.6}
          proOptions={{ hideAttribution: true }}
          onInit={(instance) => {
            flow.current = instance;
            void instance.fitView({
              padding: 0.08,
              maxZoom: 1,
              nodes: graph.nodes.filter(
                (n) => n.data.kind === 'board' || n.data.kind === 'hypothesis',
              ),
            });
          }}
          onNodeClick={(_, node) =>
            select({ kind: node.data.kind, id: node.id })
          }
          aria-label="仮説と要因の関係図"
        >
          <Background color="#d9ded6" gap={22} size={1} />
        </ReactFlow>
        <div className="canvas-controls">
          <button
            aria-label="縮小"
            onClick={() => void flow.current?.zoomOut()}
          >
            <Minus size={15} />
          </button>
          <button aria-label="拡大" onClick={() => void flow.current?.zoomIn()}>
            <Plus size={15} />
          </button>
          <button
            aria-label="全体を表示"
            onClick={() =>
              void flow.current?.fitView({ padding: 0.08, maxZoom: 1 })
            }
          >
            <Maximize size={15} />
          </button>
        </div>
        <div className="canvas-hint">
          カードを選択して理由を確認 · ドラッグで移動 · ホイールで拡大縮小
        </div>
      </div>
      <div className="canvas-legend">
        <span>
          <i className="line-sample" />
          主枝の太さ ∝ √配分（非線形）
        </span>
        <span>
          <i className="bar-sample" />
          バーは線形
        </span>
        <span>
          <ShieldCheck size={13} />
          保護 ≠ 数値固定
        </span>
        <span>破線：根拠信頼度 &lt; 1 / 未適用 / 除外（ラベル併記）</span>
      </div>
    </section>
  );
}
