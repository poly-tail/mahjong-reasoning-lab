import { useEffect, useMemo } from "react";
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
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
import {
  Copy,
  FilterX,
  Layers,
  Plus,
  RotateCcw,
  RotateCw,
  Save,
  Search,
  Trash2,
} from "lucide-react";
import { useAppStore } from "../../app/store";
import { edgeTypeLabels, nodeTypeLabels } from "../../domain/labels";
import {
  nodeTypes,
  type EdgeType,
  type KnowledgeNode,
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
};

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
    const text = search.trim().toLowerCase();
    const matches = (node: KnowledgeNode) => {
      if (node.group_id && collapsedGroupIds.has(node.group_id)) return false;
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
      (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
    );
    return { nodes, edges };
  }, [doc.edges, doc.nodes, nodeTypeFilter, search, tagFilter]);

  const flowNodes = useMemo<KnowledgeFlowNodeType[]>(
    () =>
      visible.nodes.map((node) => ({
        id: node.id,
        type: "knowledgeNode",
        position: node.position,
        data: node,
        draggable: true,
      })),
    [visible.nodes],
  );

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
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteSelection, redo, undo]);

  const onConnect = (connection: Connection) => {
    if (connection.source && connection.target)
      addEdge(connection.source, connection.target);
  };

  const onNodeDragStop: NodeMouseHandler<FlowNode> = (_event, node) => {
    updateNodePosition(node.id, node.position);
  };

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[252px_minmax(0,1fr)_360px] gap-3 p-3">
      <aside className="flex min-h-0 flex-col gap-3">
        <section className="rounded-lg border border-stone-200 bg-white">
          <div className="flex h-10 items-center justify-between border-b border-stone-200 px-3">
            <h2 className="text-sm font-semibold text-stone-950">
              Node Palette
            </h2>
            <Badge>{doc.nodes.length}</Badge>
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
            <h2 className="text-sm font-semibold text-stone-950">Edit</h2>
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
              Group
            </Button>
            <Button
              onClick={undo}
              disabled={undoStack.length === 0}
              title="Undo"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Undo
            </Button>
            <Button
              onClick={redo}
              disabled={redoStack.length === 0}
              title="Redo"
            >
              <RotateCw className="h-4 w-4" aria-hidden="true" />
              Redo
            </Button>
            <Button
              className="col-span-2"
              variant="danger"
              onClick={deleteSelection}
              disabled={selectedNodeIds.length + selectedEdgeIds.length === 0}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              削除
            </Button>
          </div>
        </section>

        <section className="min-h-0 rounded-lg border border-stone-200 bg-white">
          <div className="flex h-10 items-center justify-between border-b border-stone-200 px-3">
            <h2 className="text-sm font-semibold text-stone-950">Tags</h2>
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
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </section>
      </aside>

      <main className="flex min-w-0 min-h-0 flex-col rounded-lg border border-stone-200 bg-white">
        <div className="flex min-h-12 flex-wrap items-center gap-2 border-b border-stone-200 px-3 py-2">
          <div className="relative min-w-64 flex-1">
            <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-stone-400" />
            <Input
              className="w-full pl-8"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="検索: タイトル / タグ / summary"
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
            View
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
            onNodeDragStop={onNodeDragStop}
            onSelectionChange={({ nodes, edges }) => {
              setSelection(
                nodes.map((node) => node.id),
                edges.map((edge) => edge.id),
              );
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
                const data = node.data as KnowledgeNode;
                return edgeColors[
                  (data.pruning_hints[0] === "override_only"
                    ? "overrides"
                    : "supports") as EdgeType
                ];
              }}
            />
          </ReactFlow>
        </div>

        <div className="flex items-center gap-2 border-t border-stone-200 px-3 py-2 text-xs text-stone-500">
          <span>{visible.nodes.length} nodes shown</span>
          <span>{visible.edges.length} edges shown</span>
          <span>{selectedNodeIds.length} nodes selected</span>
          <span>{selectedEdgeIds.length} edges selected</span>
        </div>
      </main>

      <Inspector />
    </div>
  );
}
