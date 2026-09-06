import { Position, type Node, type Edge } from '@xyflow/react';
import type { BoardDocument } from '../../domain/model';
import type { Evaluation } from '../../domain/scoring';
import { formatShare } from '../../domain/scoring';
import type { Density, Selection } from '../EditorContext';
export type CanvasData = {
  label: string;
  subtitle: string;
  kind: Selection['kind'];
  share?: number;
  rawScore?: number;
  protected?: boolean;
  residual?: boolean;
  excluded?: boolean;
  impact?: number;
  selected?: boolean;
  state?: string;
  confidence?: number;
};
export type CanvasNode = Node<CanvasData, 'canvasCard'>;
export function graphAdapter(
  board: BoardDocument,
  evaluation: Evaluation,
  selection: Selection,
  density: Density,
): { nodes: CanvasNode[]; edges: Edge[] } {
  const selectedHypothesis =
    selection.kind === 'hypothesis'
      ? selection.id
      : selection.kind === 'note'
        ? board.notes.find((n) => n.id === selection.id)?.ownerHypothesisId
        : selection.kind === 'gate'
          ? board.gates.find((g) => g.id === selection.id)?.hypothesisId
          : undefined;
  const nodes: CanvasNode[] = [
    {
      id: board.id,
      type: 'canvasCard',
      position: { x: 0, y: Math.max(0, (board.hypotheses.length - 1) * 59) },
      data: {
        kind: 'board',
        label: board.question || '問いを編集してください',
        subtitle: '同じ問いを、複数の仮説で考える',
      },
      sourcePosition: Position.Right,
    },
  ];
  const edges: Edge[] = [];
  board.hypotheses.forEach((h, i) => {
    const result = evaluation.hypotheses.find((r) => r.id === h.id)!;
    nodes.push({
      id: h.id,
      type: 'canvasCard',
      position: { x: 250, y: i * 118 },
      data: {
        kind: 'hypothesis',
        label: h.label,
        subtitle: h.residual
          ? '未知・未分類の余地'
          : result.exclusionReason ||
            `${h.id.length < 8 ? h.id : '仮説'} · raw ${result.rawScore.toFixed(2)}`,
        share: result.displayShare,
        rawScore: result.rawScore,
        protected: h.mustKeep,
        residual: h.residual,
        excluded: !result.included,
        impact: h.decisionImpact,
        selected: selection.id === h.id,
      },
      targetPosition: Position.Left,
      sourcePosition: Position.Right,
    });
    edges.push({
      id: `main-${h.id}`,
      source: board.id,
      target: h.id,
      targetHandle: 'main',
      type: 'default',
      style: {
        stroke: h.residual
          ? '#9f9479'
          : result.included
            ? '#688c7f'
            : '#b7b9b4',
        strokeWidth: result.included
          ? 2 + 16 * Math.sqrt(result.displayShare)
          : 1.2,
        strokeDasharray: result.included ? undefined : '4 5',
        opacity: result.included ? 0.68 : 0.5,
      },
      ariaLabel: `${h.label} ${formatShare(result.displayShare)}`,
    });
  });
  if (density === 'conclusion') return { nodes, edges };
  const effects = board.effects.filter(
    (e) =>
      density === 'expanded' ||
      e.hypothesisId === selectedHypothesis ||
      (selection.kind === 'factor' && e.factorId === selection.id),
  );
  const factorIds = new Set(effects.map((e) => e.factorId));
  const gates = board.gates.filter(
    (g) => density === 'expanded' || g.hypothesisId === selectedHypothesis,
  );
  const visibleFactors = board.factors.filter((f) => factorIds.has(f.id));
  visibleFactors.forEach((f, i) => {
    nodes.push({
      id: f.id,
      type: 'canvasCard',
      position: { x: 565, y: i * 54 },
      data: {
        kind: 'factor',
        label: f.label,
        subtitle: f.id.length < 8 ? f.id : '要因',
        state: f.state,
        confidence: f.confidence,
        selected: selection.id === f.id,
      },
    });
  });
  for (const e of effects) {
    const row = evaluation.hypotheses
      .find((h) => h.id === e.hypothesisId)!
      .ledger.find((l) => l.sourceId === e.id)!;
    const active = row.appliedValue !== 0;
    edges.push({
      id: e.id,
      source: e.factorId,
      sourceHandle: 'factor',
      target: e.hypothesisId,
      targetHandle: 'evidence',
      type: 'smoothstep',
      label: active
        ? `${e.strength > 0 ? '+' : ''}${row.appliedValue.toFixed(1)} ${e.strength > 0 ? '支持' : '弱化'}`
        : '未適用',
      labelStyle: { fontSize: 9, fill: '#56625b' },
      labelBgStyle: { fill: '#f5f5f0', fillOpacity: 0.95 },
      style: {
        stroke: active ? (e.strength > 0 ? '#427a67' : '#b49265') : '#c6ccc5',
        strokeWidth: active ? 1.7 : 1,
        strokeDasharray:
          !active ||
          board.factors.find((f) => f.id === e.factorId)!.confidence < 1
            ? '3 4'
            : undefined,
      },
    });
  }
  gates.forEach((gate, i) => {
    const result = evaluation.hypotheses
      .find((h) => h.id === gate.hypothesisId)!
      .gates.find((g) => g.id === gate.id)!;
    nodes.push({
      id: gate.id,
      type: 'canvasCard',
      position: { x: 565, y: (visibleFactors.length + i) * 54 },
      data: {
        kind: 'gate',
        label: `成立条件 · ${result.tree.value === 'true' ? '成立' : result.tree.value === 'false' ? '不成立' : '未確定'}`,
        subtitle: `${result.tree.label} · ${gate.mode}`,
        selected: selection.id === gate.id,
      },
    });
    edges.push({
      id: `gate-${gate.id}`,
      source: gate.id,
      sourceHandle: 'factor',
      target: gate.hypothesisId,
      targetHandle: 'evidence',
      style: { stroke: '#8b83a5', strokeDasharray: '4 4' },
      label: '条件',
    });
  });
  return { nodes, edges };
}
