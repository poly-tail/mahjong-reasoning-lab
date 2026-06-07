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
import { edgeTypeLabels, labelTag, nodeTypeLabels } from "../../domain/labels";
import {
  createDomainLensSelection,
  domainLensDefinitions,
  type DomainLensId,
} from "../../domain/mahjongTaxonomy";
import {
  nodeTypes,
  type EdgeType,
  type KnowledgeNode,
} from "../../domain/schema";
import { getScopedWorkspace } from "../../domain/projectSheets";
import { cn } from "../../shared/cn";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Input, Select } from "../components/form";
import { Inspector } from "./Inspector";
import {
  KnowledgeFlowNode,
  type KnowledgeFlowNodeType,
} from "./KnowledgeFlowNode";
import { LegendPanel } from "./LegendPanel";
import { MappingGuidePanel } from "./MappingGuidePanel";

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
  activeLens: DomainLensId;
  onChange: (lens: DomainLensId) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-stone-200 bg-stone-50 px-3 py-2">
      <span className="text-xs font-semibold text-stone-500">レンズ</span>
      <div
        className="flex flex-wrap gap-1"
        role="toolbar"
        aria-label="レンズ切替"
      >
        {domainLensDefinitions.map((lens) => (
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

export function KnowledgeMap() {
  return (
    <ReactFlowProvider>
      <KnowledgeMapInner />
    </ReactFlowProvider>
  );
}

function KnowledgeMapInner() {
  const doc = useAppStore((state) => state.doc);
  const scopeMode = useAppStore((state) => state.scopeMode);
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
  const [activeLens, setActiveLens] = useState<DomainLensId>("all");
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [guideCollapsed, setGuideCollapsed] = useState(true);
  const scopedDoc = useMemo(
    () => getScopedWorkspace(doc, scopeMode),
    [doc, scopeMode],
  );

  const allTags = useMemo(
    () =>
      Array.from(new Set(scopedDoc.nodes.flatMap((node) => node.tags))).sort(
        (a, b) => a.localeCompare(b),
      ),
    [scopedDoc.nodes],
  );

  const visible = useMemo(() => {
    const collapsedGroupIds = new Set(
      scopedDoc.nodes
        .filter((node) => node.is_group && node.collapsed)
        .map((node) => node.id),
    );
    const lensSelection = createDomainLensSelection(activeLens, scopedDoc);
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
    const nodes = scopedDoc.nodes.filter(matches);
    const nodeIds = new Set(nodes.map((node) => node.id));
    const edges = scopedDoc.edges.filter(
      (edge) =>
        lensSelection.edgeIds.has(edge.id) &&
        nodeIds.has(edge.source) &&
        nodeIds.has(edge.target),
    );
    return { nodes, edges };
  }, [activeLens, nodeTypeFilter, scopedDoc, search, tagFilter]);

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

  const closeGraphPopups = () => {
    setLegendCollapsed(true);
    setGuideCollapsed(true);
  };

  const onNodeDoubleClick = (_event: unknown, node: KnowledgeMapNodeType) => {
    if (node.type !== "knowledgeNode") return;
    closeGraphPopups();
    setSelection([node.id], []);
    setInspectorCollapsed(false);
  };

  return (
    <div
      className="grid min-h-0 flex-1 gap-3 p-3"
      onPointerDown={closeGraphPopups}
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
            onNodeDoubleClick={onNodeDoubleClick}
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
            onPaneClick={() => {
              closeGraphPopups();
              setSelection([], []);
            }}
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
              edgeColors={edgeColors}
            />
            <MappingGuidePanel
              collapsed={guideCollapsed}
              onToggle={() => setGuideCollapsed((value) => !value)}
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
