import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge as FlowEdge,
  type Node as FlowNode,
  type NodeProps,
  type NodeTypes,
  type OnNodeDrag,
} from "@xyflow/react";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  FilterX,
  Layers,
  Plus,
  Redo2,
  Save,
  Search,
  Trash2,
  Undo2,
} from "lucide-react";
import {
  resolveNonOverlappingNodePosition,
  useAppStore,
} from "../../app/store";
import {
  edgeTypeLabels,
  labelTag,
  nodeTypeLabels,
  relationLayerLabels,
} from "../../domain/labels";
import {
  edgeTypes,
  nodeTypes,
  type EdgeType,
  type KnowledgeEdge,
  type KnowledgeNode,
  type WorkspaceDocument,
} from "../../domain/schema";
import { cn } from "../../shared/cn";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Input, Select } from "../components/form";
import { Inspector } from "./Inspector";
import {
  KnowledgeFlowNode,
  type KnowledgeFlowNodeType,
} from "./KnowledgeFlowNode";

const flowNodeTypes: NodeTypes = {
  knowledgeNode: KnowledgeFlowNode,
  dropPreview: DropPreviewNode,
};

type DropPreview = {
  nodeId: string;
  position: KnowledgeNode["position"];
  shifted: boolean;
};

type DropPreviewData = {
  shifted: boolean;
};

type DropPreviewNodeType = FlowNode<DropPreviewData, "dropPreview">;
type KnowledgeMapNodeType = KnowledgeFlowNodeType | DropPreviewNodeType;

const dropPreviewNodeId = "__drop_preview__";
const dropPreviewSize = {
  width: 252,
  height: 172,
} as const;

const edgeColors: Record<EdgeType, string> = {
  supports: "#0e7490",
  contradicts: "#be123c",
  refines: "#047857",
  triggers: "#b45309",
  overrides: "#9f1239",
  applies_to: "#0369a1",
  measured_by: "#4d7c0f",
  exported_as: "#57534e",
  influences: "#7c3aed",
  resolves: "#0891b2",
  weakens: "#ea580c",
  strengthens: "#16a34a",
  disambiguates: "#c026d3",
  blocks_pruning: "#be123c",
  enables_pruning: "#15803d",
};

type KnowledgeLens =
  | "semantic"
  | "probability"
  | "influence"
  | "pruning"
  | "education"
  | "all";

const lensItems: { id: KnowledgeLens; label: string }[] = [
  { id: "semantic", label: "意味" },
  { id: "probability", label: "確率" },
  { id: "influence", label: "影響" },
  { id: "pruning", label: "枝刈り" },
  { id: "education", label: "教育" },
  { id: "all", label: "全部" },
];

const educationLensTerms = [
  "teaching",
  "training",
  "review",
  "explanation",
  "教育",
  "訓練",
  "レビュー",
  "説明",
];

function addEdgeAndEndpoints(
  edge: KnowledgeEdge,
  nodeIds: Set<string>,
  edgeIds: Set<string>,
) {
  edgeIds.add(edge.id);
  nodeIds.add(edge.source);
  nodeIds.add(edge.target);
}

function addTouchingEdges(
  seedNodeIds: Set<string>,
  edges: KnowledgeEdge[],
  nodeIds: Set<string>,
  edgeIds: Set<string>,
) {
  for (const edge of edges) {
    if (seedNodeIds.has(edge.source) || seedNodeIds.has(edge.target)) {
      addEdgeAndEndpoints(edge, nodeIds, edgeIds);
    }
  }
}

function hasEducationMarker(node: KnowledgeNode) {
  const text = [
    node.title,
    node.summary,
    node.description,
    node.notes,
    node.stage,
    ...node.tags,
    ...node.applicability,
  ]
    .join(" ")
    .toLowerCase();
  return educationLensTerms.some((term) => text.includes(term.toLowerCase()));
}

function createLensSelection(lens: KnowledgeLens, doc: WorkspaceDocument) {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();

  if (lens === "all") {
    for (const node of doc.nodes) nodeIds.add(node.id);
    for (const edge of doc.edges) edgeIds.add(edge.id);
    return { nodeIds, edgeIds };
  }

  if (lens === "semantic") {
    for (const node of doc.nodes) {
      if (node.probability_role === "none") nodeIds.add(node.id);
    }
    for (const edge of doc.edges) {
      if (edge.relation_layer === "semantic") {
        addEdgeAndEndpoints(edge, nodeIds, edgeIds);
      }
    }
    return { nodeIds, edgeIds };
  }

  if (lens === "probability") {
    for (const node of doc.nodes) {
      if (node.probability_role !== "none") nodeIds.add(node.id);
    }
    for (const edge of doc.edges) {
      if (edge.relation_layer === "probabilistic") {
        addEdgeAndEndpoints(edge, nodeIds, edgeIds);
      }
    }
    return { nodeIds, edgeIds };
  }

  if (lens === "influence") {
    for (const node of doc.nodes) {
      if (node.tags.includes("influence") || node.type === "metric") {
        nodeIds.add(node.id);
      }
    }
    for (const edge of doc.edges) {
      if (edge.relation_layer === "influence") {
        addEdgeAndEndpoints(edge, nodeIds, edgeIds);
      }
    }
    return { nodeIds, edgeIds };
  }

  if (lens === "pruning") {
    const seedNodeIds = new Set<string>();
    for (const node of doc.nodes) {
      if (
        node.pruning_hints.length > 0 ||
        node.type === "pruning_suggestion" ||
        node.type === "weight_adjustment_suggestion" ||
        node.lock_mode !== "none"
      ) {
        seedNodeIds.add(node.id);
        nodeIds.add(node.id);
      }
    }
    for (const edge of doc.edges) {
      if (edge.type === "blocks_pruning" || edge.type === "enables_pruning") {
        addEdgeAndEndpoints(edge, nodeIds, edgeIds);
      }
    }
    addTouchingEdges(seedNodeIds, doc.edges, nodeIds, edgeIds);
    return { nodeIds, edgeIds };
  }

  const seedNodeIds = new Set<string>();
  for (const node of doc.nodes) {
    if (hasEducationMarker(node) || node.reading_utility_ids.length > 0) {
      seedNodeIds.add(node.id);
      nodeIds.add(node.id);
    }
  }
  for (const utility of doc.reading_utilities) {
    seedNodeIds.add(utility.target_id);
    nodeIds.add(utility.target_id);
  }
  for (const chain of doc.reading_chains) {
    for (const step of chain.steps) {
      for (const sourceId of step.source_ids) {
        seedNodeIds.add(sourceId);
        nodeIds.add(sourceId);
      }
    }
  }
  addTouchingEdges(seedNodeIds, doc.edges, nodeIds, edgeIds);
  return { nodeIds, edgeIds };
}

function normalizeFlowPosition(position: KnowledgeNode["position"]) {
  return {
    x: Math.max(0, Math.round(position.x)),
    y: Math.max(0, Math.round(position.y)),
  };
}

function samePosition(
  left: KnowledgeNode["position"],
  right: KnowledgeNode["position"],
) {
  return left.x === right.x && left.y === right.y;
}

function DropPreviewNode({ data }: NodeProps<DropPreviewNodeType>) {
  return (
    <div
      aria-hidden="true"
      data-testid="drop-preview"
      className={cn(
        "pointer-events-none rounded-lg border-2 border-dashed bg-cyan-500/10 shadow-[0_0_0_5px_rgba(8,145,178,0.10)]",
        data.shifted &&
          "border-amber-500 bg-amber-400/15 shadow-[0_0_0_5px_rgba(245,158,11,0.12)]",
      )}
      style={{
        width: dropPreviewSize.width,
        height: dropPreviewSize.height,
      }}
    />
  );
}

function LensBar({
  activeLens,
  onChange,
}: {
  activeLens: KnowledgeLens;
  onChange: (lens: KnowledgeLens) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-stone-200 bg-stone-50 px-3 py-2">
      <span className="text-xs font-semibold text-stone-500">レンズ</span>
      <div
        className="flex flex-wrap gap-1"
        role="toolbar"
        aria-label="レンズ切替"
      >
        {lensItems.map((lens) => (
          <Button
            key={lens.id}
            size="sm"
            variant={activeLens === lens.id ? "primary" : "secondary"}
            onClick={() => onChange(lens.id)}
            aria-pressed={activeLens === lens.id}
          >
            {lens.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

function LegendPanel({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  if (collapsed) {
    return (
      <div className="absolute bottom-3 left-14 z-10">
        <Button
          size="sm"
          onClick={onToggle}
          title="凡例を開く"
          aria-label="凡例を開く"
        >
          凡例
        </Button>
      </div>
    );
  }

  return (
    <aside className="absolute bottom-3 left-14 z-10 max-h-[62%] w-80 overflow-auto rounded-md border border-stone-200 bg-white/95 shadow-lg backdrop-blur">
      <div className="flex h-9 items-center justify-between border-b border-stone-200 px-3">
        <h3 className="text-sm font-semibold text-stone-950">凡例</h3>
        <Button
          size="sm"
          variant="ghost"
          onClick={onToggle}
          title="凡例を畳む"
          aria-label="凡例を畳む"
        >
          畳む
        </Button>
      </div>

      <div className="grid gap-3 p-3 text-xs text-stone-600">
        <div>
          <h4 className="mb-1 font-semibold text-stone-800">線種とレイヤ</h4>
          <div className="grid gap-1.5">
            <LegendLine
              label={relationLayerLabels.semantic}
              description="意味関係"
            />
            <LegendLine
              label={relationLayerLabels.probabilistic}
              description="破線 / 確率伝播"
              dashed="8 4"
            />
            <LegendLine
              label={relationLayerLabels.influence}
              description="点線 / 指標影響"
              dashed="3 4"
            />
          </div>
        </div>

        <div>
          <h4 className="mb-1 font-semibold text-stone-800">線色</h4>
          <div className="grid grid-cols-2 gap-1.5">
            {edgeTypes.map((type) => (
              <div key={type} className="flex min-w-0 items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: edgeColors[type] }}
                />
                <span className="truncate">{edgeTypeLabels[type]}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h4 className="mb-1 font-semibold text-stone-800">ノード種別</h4>
          <div className="flex flex-wrap gap-1">
            {nodeTypes.map((type) => (
              <Badge key={type} tone="stone">
                {nodeTypeLabels[type]}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

function LegendLine({
  label,
  description,
  dashed,
}: {
  label: string;
  description: string;
  dashed?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <svg className="h-3 w-14 shrink-0" viewBox="0 0 56 12" aria-hidden="true">
        <line
          x1="2"
          y1="6"
          x2="54"
          y2="6"
          stroke="#0e7490"
          strokeWidth="2"
          strokeDasharray={dashed}
          strokeLinecap="round"
        />
      </svg>
      <span className="font-medium text-stone-800">{label}</span>
      <span className="text-stone-500">{description}</span>
    </div>
  );
}

export function KnowledgeMap() {
  return (
    <ReactFlowProvider>
      <KnowledgeMapInner />
    </ReactFlowProvider>
  );
}

function KnowledgeMapInner() {
  const doc = useAppStore((state) => state.doc);
  const search = useAppStore((state) => state.search);
  const tagFilter = useAppStore((state) => state.tagFilter);
  const nodeTypeFilter = useAppStore((state) => state.nodeTypeFilter);
  const activeSavedViewId = useAppStore((state) => state.activeSavedViewId);
  const selectedNodeIds = useAppStore((state) => state.selectedNodeIds);
  const selectedEdgeIds = useAppStore((state) => state.selectedEdgeIds);
  const addNode = useAppStore((state) => state.addNode);
  const addEdge = useAppStore((state) => state.addEdge);
  const setSelection = useAppStore((state) => state.setSelection);
  const updateNodePosition = useAppStore((state) => state.updateNodePosition);
  const deleteSelection = useAppStore((state) => state.deleteSelection);
  const duplicateSelectedNodes = useAppStore(
    (state) => state.duplicateSelectedNodes,
  );
  const groupSelectedNodes = useAppStore((state) => state.groupSelectedNodes);
  const undo = useAppStore((state) => state.undo);
  const redo = useAppStore((state) => state.redo);
  const undoStack = useAppStore((state) => state.undoStack);
  const redoStack = useAppStore((state) => state.redoStack);
  const setSearch = useAppStore((state) => state.setSearch);
  const toggleTagFilter = useAppStore((state) => state.toggleTagFilter);
  const clearTagFilter = useAppStore((state) => state.clearTagFilter);
  const toggleNodeTypeFilter = useAppStore(
    (state) => state.toggleNodeTypeFilter,
  );
  const clearNodeTypeFilter = useAppStore((state) => state.clearNodeTypeFilter);
  const createSavedView = useAppStore((state) => state.createSavedView);
  const applySavedView = useAppStore((state) => state.applySavedView);
  const deleteSavedView = useAppStore((state) => state.deleteSavedView);
  const [dropPreview, setDropPreview] = useState<DropPreview | null>(null);
  const [nodePanelCollapsed, setNodePanelCollapsed] = useState(false);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false);
  const [activeLens, setActiveLens] = useState<KnowledgeLens>("all");
  const [legendCollapsed, setLegendCollapsed] = useState(false);

  const allTags = useMemo(
    () =>
      Array.from(new Set(doc.nodes.flatMap((node) => node.tags))).sort((a, b) =>
        a.localeCompare(b),
      ),
    [doc.nodes],
  );

  const visible = useMemo(() => {
    const collapsedGroupIds = new Set(
      doc.nodes
        .filter((node) => node.is_group && node.collapsed)
        .map((node) => node.id),
    );
    const lensSelection = createLensSelection(activeLens, doc);
    const text = search.trim().toLowerCase();
    const matches = (node: KnowledgeNode) => {
      if (node.group_id && collapsedGroupIds.has(node.group_id)) return false;
      if (!lensSelection.nodeIds.has(node.id)) return false;
      if (nodeTypeFilter.length > 0 && !nodeTypeFilter.includes(node.type))
        return false;
      if (
        tagFilter.length > 0 &&
        !tagFilter.every((tag) => node.tags.includes(tag))
      )
        return false;
      if (!text) return true;
      return [
        node.title,
        node.summary,
        node.description,
        node.notes,
        ...node.tags,
      ]
        .join(" ")
        .toLowerCase()
        .includes(text);
    };
    const nodes = doc.nodes.filter(matches);
    const nodeIds = new Set(nodes.map((node) => node.id));
    const edges = doc.edges.filter(
      (edge) =>
        lensSelection.edgeIds.has(edge.id) &&
        nodeIds.has(edge.source) &&
        nodeIds.has(edge.target),
    );
    return { nodes, edges };
  }, [activeLens, doc, nodeTypeFilter, search, tagFilter]);

  const flowNodes = useMemo<KnowledgeMapNodeType[]>(() => {
    const nodes: KnowledgeMapNodeType[] = visible.nodes.map((node) => ({
      id: node.id,
      type: "knowledgeNode",
      position: node.position,
      data: node,
      draggable: true,
      zIndex: dropPreview?.nodeId === node.id ? 3 : 1,
    }));

    if (dropPreview) {
      nodes.push({
        id: dropPreviewNodeId,
        type: "dropPreview",
        position: dropPreview.position,
        data: { shifted: dropPreview.shifted },
        draggable: false,
        selectable: false,
        connectable: false,
        deletable: false,
        focusable: false,
        zIndex: 2,
        style: { pointerEvents: "none" },
      });
    }

    return nodes;
  }, [dropPreview, visible.nodes]);

  const flowEdges = useMemo<FlowEdge[]>(
    () =>
      visible.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label || edgeTypeLabels[edge.type],
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColors[edge.type],
        },
        style: {
          stroke: edgeColors[edge.type],
          strokeWidth:
            edge.relation_layer === "probabilistic" ||
            edge.relation_layer === "influence"
              ? 3
              : 2,
          strokeDasharray:
            edge.relation_layer === "probabilistic"
              ? "8 4"
              : edge.relation_layer === "influence"
                ? "3 4"
                : undefined,
        },
        labelStyle: { fill: "#44403c", fontWeight: 600, fontSize: 12 },
        labelBgStyle: { fill: "#fff", fillOpacity: 0.86 },
      })),
    [visible.edges],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName;
      if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT")
        return;
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        deleteSelection();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteSelection]);

  const onConnect = (connection: Connection) => {
    if (connection.source && connection.target)
      addEdge(connection.source, connection.target);
  };

  const updateDropPreview = (node: KnowledgeMapNodeType) => {
    if (node.type !== "knowledgeNode") return;
    const desired = normalizeFlowPosition(node.position);
    const resolved = resolveNonOverlappingNodePosition(
      node.id,
      node.position,
      doc.nodes,
    );

    setDropPreview({
      nodeId: node.id,
      position: resolved,
      shifted: !samePosition(desired, resolved),
    });
  };

  const onNodeDragStart: OnNodeDrag<KnowledgeMapNodeType> = (_event, node) => {
    updateDropPreview(node);
  };

  const onNodeDrag: OnNodeDrag<KnowledgeMapNodeType> = (_event, node) => {
    updateDropPreview(node);
  };

  const onNodeDragStop: OnNodeDrag<KnowledgeMapNodeType> = (_event, node) => {
    setDropPreview(null);
    if (node.type !== "knowledgeNode") return;
    updateNodePosition(node.id, node.position);
  };

  return (
    <div
      className="grid min-h-0 flex-1 gap-3 p-3"
      style={{
        gridTemplateColumns: `${
          nodePanelCollapsed ? "44px" : "252px"
        } minmax(0,1fr) ${inspectorCollapsed ? "44px" : "360px"}`,
      }}
    >
      <aside
        className={cn(
          "min-h-0",
          nodePanelCollapsed
            ? "flex flex-col items-center gap-3 rounded-lg border border-stone-200 bg-white py-2"
            : "flex flex-col gap-3",
        )}
      >
        {nodePanelCollapsed ? (
          <>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setNodePanelCollapsed(false)}
              title="ノードパレットを開く"
              aria-label="ノードパレットを開く"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
            <span
              className="select-none text-xs font-semibold text-stone-600"
              style={{ writingMode: "vertical-rl" }}
            >
              ノードパレット
            </span>
          </>
        ) : (
          <>
            <section className="rounded-lg border border-stone-200 bg-white">
              <div className="flex h-10 items-center justify-between border-b border-stone-200 px-3">
                <h2 className="text-sm font-semibold text-stone-950">
                  ノードパレット
                </h2>
                <div className="flex items-center gap-1">
                  <Badge>{doc.nodes.length}</Badge>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setNodePanelCollapsed(true)}
                    title="ノードパレットを畳む"
                    aria-label="ノードパレットを畳む"
                  >
                    <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </div>
              <div className="grid gap-1.5 p-2">
                {nodeTypes.map((type) => (
                  <Button
                    key={type}
                    className="justify-start"
                    onClick={() => addNode(type)}
                    title={`${nodeTypeLabels[type]}を追加`}
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    {nodeTypeLabels[type]}
                  </Button>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-stone-200 bg-white">
              <div className="border-b border-stone-200 px-3 py-2">
                <h2 className="text-sm font-semibold text-stone-950">編集</h2>
              </div>
              <div className="grid grid-cols-2 gap-1.5 p-2">
                <Button
                  onClick={duplicateSelectedNodes}
                  disabled={selectedNodeIds.length === 0}
                >
                  <Copy className="h-4 w-4" aria-hidden="true" />
                  複製
                </Button>
                <Button
                  onClick={groupSelectedNodes}
                  disabled={selectedNodeIds.length < 2}
                >
                  <Layers className="h-4 w-4" aria-hidden="true" />
                  グループ化
                </Button>
                <Button
                  onClick={undo}
                  disabled={undoStack.length === 0}
                  title="元に戻す (Ctrl+Z)"
                >
                  <Undo2 className="h-4 w-4" aria-hidden="true" />
                  元に戻す
                </Button>
                <Button
                  onClick={redo}
                  disabled={redoStack.length === 0}
                  title="やり直す (Ctrl+Y)"
                >
                  <Redo2 className="h-4 w-4" aria-hidden="true" />
                  やり直す
                </Button>
                <Button
                  className="col-span-2"
                  variant="danger"
                  onClick={deleteSelection}
                  disabled={
                    selectedNodeIds.length + selectedEdgeIds.length === 0
                  }
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  削除
                </Button>
              </div>
            </section>

            <section className="min-h-0 rounded-lg border border-stone-200 bg-white">
              <div className="flex h-10 items-center justify-between border-b border-stone-200 px-3">
                <h2 className="text-sm font-semibold text-stone-950">タグ</h2>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={clearTagFilter}
                  disabled={tagFilter.length === 0}
                >
                  <FilterX className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
              <div className="max-h-56 overflow-auto p-2">
                <div className="flex flex-wrap gap-1">
                  {allTags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => toggleTagFilter(tag)}
                      className={cn(
                        "rounded border px-1.5 py-0.5 text-xs transition-colors",
                        tagFilter.includes(tag)
                          ? "border-cyan-700 bg-cyan-700 text-white"
                          : "border-stone-300 bg-white text-stone-700 hover:bg-stone-100",
                      )}
                    >
                      {labelTag(tag)}
                    </button>
                  ))}
                </div>
              </div>
            </section>
          </>
        )}
      </aside>

      <main className="flex min-w-0 min-h-0 flex-col rounded-lg border border-stone-200 bg-white">
        <div className="flex min-h-12 flex-wrap items-center gap-2 border-b border-stone-200 px-3 py-2">
          <div className="relative min-w-64 flex-1">
            <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-stone-400" />
            <Input
              className="w-full pl-8"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="検索: タイトル / タグ / 要約"
            />
          </div>
          <Select
            className="w-44"
            value={activeSavedViewId ?? ""}
            onChange={(event) => {
              if (event.target.value) applySavedView(event.target.value);
            }}
            aria-label="保存ビュー"
          >
            <option value="">保存ビュー</option>
            {doc.saved_views.map((view) => (
              <option key={view.id} value={view.id}>
                {view.name}
              </option>
            ))}
          </Select>
          <Button onClick={createSavedView} title="現在のフィルタを保存">
            <Save className="h-4 w-4" aria-hidden="true" />
            ビュー
          </Button>
          <Button
            variant="ghost"
            onClick={() =>
              activeSavedViewId && deleteSavedView(activeSavedViewId)
            }
            disabled={!activeSavedViewId}
            title="保存ビューを削除"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        <LensBar activeLens={activeLens} onChange={setActiveLens} />

        <div className="flex flex-wrap gap-1 border-b border-stone-200 px-3 py-2">
          {nodeTypes.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => toggleNodeTypeFilter(type)}
              className={cn(
                "rounded border px-2 py-1 text-xs",
                nodeTypeFilter.includes(type)
                  ? "border-cyan-700 bg-cyan-700 text-white"
                  : "border-stone-300 bg-white text-stone-700 hover:bg-stone-100",
              )}
            >
              {nodeTypeLabels[type]}
            </button>
          ))}
          <Button
            size="sm"
            variant="ghost"
            onClick={clearNodeTypeFilter}
            disabled={nodeTypeFilter.length === 0}
          >
            <FilterX className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        <div className="min-h-0 flex-1">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={flowNodeTypes}
            onConnect={onConnect}
            onNodeDragStart={onNodeDragStart}
            onNodeDrag={onNodeDrag}
            onNodeDragStop={onNodeDragStop}
            onSelectionChange={({ nodes, edges }) => {
              if (
                nodes.length === 0 &&
                edges.length === 0 &&
                selectedNodeIds.length + selectedEdgeIds.length > 0
              ) {
                return;
              }
              setSelection(
                nodes.map((node) => node.id),
                edges.map((edge) => edge.id),
              );
            }}
            onPaneClick={() => setSelection([], [])}
            fitView
            minZoom={0.25}
            maxZoom={1.8}
            deleteKeyCode={null}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#d6d3d1" gap={24} />
            <Controls position="bottom-left" />
            <MiniMap
              pannable
              zoomable
              nodeStrokeWidth={3}
              nodeColor={(node) => {
                if (node.type === "dropPreview") return "#06b6d4";
                const data = node.data as KnowledgeNode;
                return edgeColors[
                  (data.pruning_hints[0] === "override_only"
                    ? "overrides"
                    : "supports") as EdgeType
                ];
              }}
            />
            <LegendPanel
              collapsed={legendCollapsed}
              onToggle={() => setLegendCollapsed((value) => !value)}
            />
          </ReactFlow>
        </div>

        <div className="flex items-center gap-2 border-t border-stone-200 px-3 py-2 text-xs text-stone-500">
          <span>{visible.nodes.length}件のノードを表示</span>
          <span>{visible.edges.length}件のエッジを表示</span>
          <span>{selectedNodeIds.length}件のノードを選択中</span>
          <span>{selectedEdgeIds.length}件のエッジを選択中</span>
        </div>
      </main>

      {inspectorCollapsed ? (
        <aside className="flex min-h-0 flex-col items-center gap-3 rounded-lg border border-stone-200 bg-white py-2">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => setInspectorCollapsed(false)}
            title="インスペクターを開く"
            aria-label="インスペクターを開く"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span
            className="select-none text-xs font-semibold text-stone-600"
            style={{ writingMode: "vertical-rl" }}
          >
            インスペクター
          </span>
        </aside>
      ) : (
        <div className="relative min-h-0">
          <Button
            className="absolute right-2 top-2 z-10"
            size="icon"
            variant="ghost"
            onClick={() => setInspectorCollapsed(true)}
            title="インスペクターを畳む"
            aria-label="インスペクターを畳む"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Inspector />
        </div>
      )}
    </div>
  );
}
