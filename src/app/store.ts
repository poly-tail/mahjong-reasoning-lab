import { create } from "zustand";
import {
  createCase,
  createId,
  createKnowledgeEdge,
  createKnowledgeNode,
  createRule,
  inferLaneFromNodeType,
  nowIso,
} from "../domain/factory";
import { runPropagation, type PropagationPreview } from "../domain/probability";
import { seedWorkspace } from "../domain/seed";
import {
  caseLanes,
  normalizeWorkspaceDocument,
  workspaceDocumentSchema,
  type CaseData,
  type CaseLane,
  type EdgeType,
  type KnowledgeEdge,
  type KnowledgeNode,
  type NodeType,
  type ImpactSummary,
  type PruningAction,
  type RuleDefinition,
  type SavedView,
  type TeachingLog,
  type WorkspaceDocument,
} from "../domain/schema";

export type Screen =
  | "knowledge"
  | "case"
  | "rules"
  | "probability"
  | "influence"
  | "lab"
  | "io";
export type SaveStatus = "loading" | "idle" | "saving" | "saved" | "error";

type WorkspaceMutation = (doc: WorkspaceDocument) => WorkspaceDocument;

type AppState = {
  doc: WorkspaceDocument;
  activeScreen: Screen;
  selectedNodeIds: string[];
  selectedEdgeIds: string[];
  search: string;
  tagFilter: string[];
  nodeTypeFilter: NodeType[];
  activeSavedViewId?: string;
  undoStack: WorkspaceDocument[];
  redoStack: WorkspaceDocument[];
  saveStatus: SaveStatus;
  lastSavedAt?: string;
  errorMessage?: string;
  lastPropagationPreview?: PropagationPreview;
  hydrate: (doc: WorkspaceDocument) => void;
  resetToSeed: () => void;
  setScreen: (screen: Screen) => void;
  setSaveStatus: (status: SaveStatus, message?: string) => void;
  markSaved: () => void;
  setSelection: (nodeIds: string[], edgeIds: string[]) => void;
  setSearch: (search: string) => void;
  toggleTagFilter: (tag: string) => void;
  clearTagFilter: () => void;
  toggleNodeTypeFilter: (type: NodeType) => void;
  clearNodeTypeFilter: () => void;
  createSavedView: () => void;
  applySavedView: (id: string) => void;
  deleteSavedView: (id: string) => void;
  addNode: (type: NodeType) => void;
  duplicateSelectedNodes: () => void;
  deleteSelection: () => void;
  groupSelectedNodes: () => void;
  toggleGroupCollapsed: (id: string) => void;
  updateNode: (id: string, patch: Partial<KnowledgeNode>) => void;
  updateNodePosition: (id: string, position: { x: number; y: number }) => void;
  addEdge: (source: string, target: string, type?: EdgeType) => void;
  updateEdge: (id: string, patch: Partial<KnowledgeEdge>) => void;
  deleteEdge: (id: string) => void;
  addCase: () => void;
  setActiveCase: (id: string) => void;
  updateCase: (id: string, patch: Partial<CaseData>) => void;
  attachNodeToCase: (caseId: string, nodeId: string) => void;
  detachNodeFromCase: (caseId: string, nodeId: string) => void;
  setCaseNodeLane: (caseId: string, nodeId: string, lane: CaseLane) => void;
  addRule: () => void;
  updateRule: (id: string, patch: Partial<RuleDefinition>) => void;
  deleteRule: (id: string) => void;
  createChoiceGroupFromSelection: () => void;
  runPropagationPreview: (changedNodeId?: string) => void;
  applyPropagationPreview: () => void;
  clearPropagationPreview: () => void;
  recordReasoningLabSimulation: (
    action: PruningAction,
    summary: ImpactSummary,
  ) => void;
  addTeachingLog: (log: TeachingLog) => void;
  importDocument: (doc: WorkspaceDocument) => void;
  undo: () => void;
  redo: () => void;
};

const historyLimit = 50;

function touch(doc: WorkspaceDocument): WorkspaceDocument {
  return { ...doc, updated_at: nowIso() };
}

function commit(
  set: (partial: Partial<AppState>) => void,
  get: () => AppState,
  mutation: WorkspaceMutation,
  trackHistory = true,
) {
  const previous = get().doc;
  const next = workspaceDocumentSchema.parse(touch(mutation(previous)));
  const history = trackHistory
    ? [previous, ...get().undoStack].slice(0, historyLimit)
    : get().undoStack;
  set({
    doc: next,
    undoStack: history,
    redoStack: trackHistory ? [] : get().redoStack,
    saveStatus: "idle",
    errorMessage: undefined,
  });
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function removeIds(values: string[], idsToRemove: Set<string>): string[] {
  return values.filter((value) => !idsToRemove.has(value));
}

function findActiveCase(doc: WorkspaceDocument): CaseData | undefined {
  return (
    doc.cases.find((caseItem) => caseItem.id === doc.active_case_id) ??
    doc.cases[0]
  );
}

function averagePosition(nodes: KnowledgeNode[]) {
  if (nodes.length === 0) return { x: 160, y: 160 };
  const total = nodes.reduce(
    (acc, node) => ({ x: acc.x + node.position.x, y: acc.y + node.position.y }),
    { x: 0, y: 0 },
  );
  return { x: total.x / nodes.length - 60, y: total.y / nodes.length - 70 };
}

export const useAppStore = create<AppState>((set, get) => ({
  doc: seedWorkspace,
  activeScreen: "knowledge",
  selectedNodeIds: [],
  selectedEdgeIds: [],
  search: "",
  tagFilter: [],
  nodeTypeFilter: [],
  undoStack: [],
  redoStack: [],
  saveStatus: "loading",
  hydrate: (doc) => {
    const parsed = normalizeWorkspaceDocument(doc);
    set({
      doc: parsed,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      undoStack: [],
      redoStack: [],
      saveStatus: "idle",
      errorMessage: undefined,
      lastPropagationPreview: undefined,
    });
  },
  resetToSeed: () => {
    commit(set, get, () => seedWorkspace);
  },
  setScreen: (screen) => set({ activeScreen: screen }),
  setSaveStatus: (status, message) =>
    set({ saveStatus: status, errorMessage: message }),
  markSaved: () =>
    set({
      saveStatus: "saved",
      lastSavedAt: nowIso(),
      errorMessage: undefined,
    }),
  setSelection: (nodeIds, edgeIds) => {
    const nextNodeIds = unique(nodeIds);
    const nextEdgeIds = unique(edgeIds);
    if (
      nextNodeIds.join("\u0000") === get().selectedNodeIds.join("\u0000") &&
      nextEdgeIds.join("\u0000") === get().selectedEdgeIds.join("\u0000")
    ) {
      return;
    }
    set({ selectedNodeIds: nextNodeIds, selectedEdgeIds: nextEdgeIds });
  },
  setSearch: (search) => set({ search, activeSavedViewId: undefined }),
  toggleTagFilter: (tag) => {
    const current = get().tagFilter;
    set({
      tagFilter: current.includes(tag)
        ? current.filter((item) => item !== tag)
        : [...current, tag],
      activeSavedViewId: undefined,
    });
  },
  clearTagFilter: () => set({ tagFilter: [], activeSavedViewId: undefined }),
  toggleNodeTypeFilter: (type) => {
    const current = get().nodeTypeFilter;
    set({
      nodeTypeFilter: current.includes(type)
        ? current.filter((item) => item !== type)
        : [...current, type],
      activeSavedViewId: undefined,
    });
  },
  clearNodeTypeFilter: () =>
    set({ nodeTypeFilter: [], activeSavedViewId: undefined }),
  createSavedView: () => {
    const name = window.prompt("保存ビュー名", "研究ビュー");
    if (!name) return;
    const now = nowIso();
    const view: SavedView = {
      id: createId("view"),
      name,
      search: get().search,
      tag_filter: get().tagFilter,
      node_type_filter: get().nodeTypeFilter,
      created_at: now,
    };
    commit(set, get, (doc) => ({
      ...doc,
      saved_views: [...doc.saved_views, view],
    }));
    set({ activeSavedViewId: view.id });
  },
  applySavedView: (id) => {
    const view = get().doc.saved_views.find((item) => item.id === id);
    if (!view) return;
    set({
      search: view.search,
      tagFilter: view.tag_filter,
      nodeTypeFilter: view.node_type_filter,
      activeSavedViewId: view.id,
    });
  },
  deleteSavedView: (id) => {
    commit(set, get, (doc) => ({
      ...doc,
      saved_views: doc.saved_views.filter((view) => view.id !== id),
    }));
    if (get().activeSavedViewId === id) set({ activeSavedViewId: undefined });
  },
  addNode: (type) => {
    const count = get().doc.nodes.length;
    const created = createKnowledgeNode(type, {
      title: `${type} node`,
      tags: ["draft"],
      position: { x: 180 + (count % 8) * 40, y: 140 + (count % 6) * 52 },
    });
    commit(set, get, (doc) => ({ ...doc, nodes: [...doc.nodes, created] }));
    set({ selectedNodeIds: [created.id], selectedEdgeIds: [] });
  },
  duplicateSelectedNodes: () => {
    const selected = get().doc.nodes.filter((node) =>
      get().selectedNodeIds.includes(node.id),
    );
    if (selected.length === 0) return;
    const copies = selected.map((node) => ({
      ...node,
      id: createId("node"),
      title: `${node.title} copy`,
      position: { x: node.position.x + 48, y: node.position.y + 48 },
      group_id: node.group_id,
      created_at: nowIso(),
      updated_at: nowIso(),
    }));
    commit(set, get, (doc) => ({ ...doc, nodes: [...doc.nodes, ...copies] }));
    set({
      selectedNodeIds: copies.map((node) => node.id),
      selectedEdgeIds: [],
    });
  },
  deleteSelection: () => {
    const nodeIds = new Set(get().selectedNodeIds);
    const edgeIds = new Set(get().selectedEdgeIds);
    if (nodeIds.size === 0 && edgeIds.size === 0) return;
    commit(set, get, (doc) => {
      const edgesToRemove = new Set(edgeIds);
      for (const edgeItem of doc.edges) {
        if (nodeIds.has(edgeItem.source) || nodeIds.has(edgeItem.target))
          edgesToRemove.add(edgeItem.id);
      }
      return {
        ...doc,
        nodes: doc.nodes
          .filter((node) => !nodeIds.has(node.id))
          .map((node) => ({
            ...node,
            group_id:
              node.group_id && nodeIds.has(node.group_id)
                ? undefined
                : node.group_id,
          })),
        edges: doc.edges.filter((edgeItem) => !edgesToRemove.has(edgeItem.id)),
        cases: doc.cases.map((caseItem) => ({
          ...caseItem,
          attached_node_ids: removeIds(caseItem.attached_node_ids, nodeIds),
          selected_rule_ids: caseItem.selected_rule_ids,
          lane_assignments: Object.fromEntries(
            Object.entries(caseItem.lane_assignments).filter(
              ([nodeId]) => !nodeIds.has(nodeId),
            ),
          ),
        })),
        rules: doc.rules.map((ruleItem) => ({
          ...ruleItem,
          target_node_ids: removeIds(ruleItem.target_node_ids, nodeIds),
        })),
      };
    });
    set({ selectedNodeIds: [], selectedEdgeIds: [] });
  },
  groupSelectedNodes: () => {
    const selected = get().doc.nodes.filter((node) =>
      get().selectedNodeIds.includes(node.id),
    );
    if (selected.length < 2) return;
    const group = createKnowledgeNode("concept", {
      title: "New section",
      summary: "Collapsed section for selected nodes.",
      tags: ["section"],
      position: averagePosition(selected),
      is_group: true,
    });
    const selectedIds = new Set(selected.map((node) => node.id));
    commit(set, get, (doc) => ({
      ...doc,
      nodes: [
        ...doc.nodes.map((node) =>
          selectedIds.has(node.id)
            ? { ...node, group_id: group.id, updated_at: nowIso() }
            : node,
        ),
        group,
      ],
    }));
    set({ selectedNodeIds: [group.id], selectedEdgeIds: [] });
  },
  toggleGroupCollapsed: (id) => {
    commit(set, get, (doc) => ({
      ...doc,
      nodes: doc.nodes.map((node) =>
        node.id === id && node.is_group
          ? { ...node, collapsed: !node.collapsed, updated_at: nowIso() }
          : node,
      ),
    }));
  },
  updateNode: (id, patch) => {
    commit(set, get, (doc) => ({
      ...doc,
      nodes: doc.nodes.map((node) =>
        node.id === id
          ? { ...node, ...patch, id: node.id, updated_at: nowIso() }
          : node,
      ),
    }));
  },
  updateNodePosition: (id, position) => {
    commit(set, get, (doc) => ({
      ...doc,
      nodes: doc.nodes.map((node) =>
        node.id === id ? { ...node, position, updated_at: nowIso() } : node,
      ),
    }));
  },
  addEdge: (source, target, type = "supports") => {
    if (source === target) return;
    const exists = get().doc.edges.some(
      (edgeItem) =>
        edgeItem.source === source &&
        edgeItem.target === target &&
        edgeItem.type === type,
    );
    if (exists) return;
    const edgeItem = createKnowledgeEdge({ source, target, type, label: type });
    commit(set, get, (doc) => ({ ...doc, edges: [...doc.edges, edgeItem] }));
    set({ selectedNodeIds: [], selectedEdgeIds: [edgeItem.id] });
  },
  updateEdge: (id, patch) => {
    commit(set, get, (doc) => ({
      ...doc,
      edges: doc.edges.map((edgeItem) =>
        edgeItem.id === id
          ? { ...edgeItem, ...patch, id: edgeItem.id, updated_at: nowIso() }
          : edgeItem,
      ),
    }));
  },
  deleteEdge: (id) => {
    commit(set, get, (doc) => ({
      ...doc,
      edges: doc.edges.filter((edgeItem) => edgeItem.id !== id),
    }));
    set({
      selectedEdgeIds: get().selectedEdgeIds.filter((edgeId) => edgeId !== id),
    });
  },
  addCase: () => {
    const created = createCase({ title: "New case" });
    commit(set, get, (doc) => ({
      ...doc,
      cases: [...doc.cases, created],
      active_case_id: created.id,
    }));
  },
  setActiveCase: (id) => {
    commit(
      set,
      get,
      (doc) => ({
        ...doc,
        active_case_id: doc.cases.some((caseItem) => caseItem.id === id)
          ? id
          : findActiveCase(doc)?.id,
      }),
      false,
    );
  },
  updateCase: (id, patch) => {
    commit(set, get, (doc) => ({
      ...doc,
      cases: doc.cases.map((caseItem) =>
        caseItem.id === id
          ? { ...caseItem, ...patch, id: caseItem.id, updated_at: nowIso() }
          : caseItem,
      ),
    }));
  },
  attachNodeToCase: (caseId, nodeId) => {
    const targetNode = get().doc.nodes.find(
      (nodeItem) => nodeItem.id === nodeId,
    );
    if (!targetNode) return;
    commit(set, get, (doc) => ({
      ...doc,
      cases: doc.cases.map((caseItem) => {
        if (caseItem.id !== caseId) return caseItem;
        const lane =
          caseItem.lane_assignments[nodeId] ??
          inferLaneFromNodeType(targetNode.type);
        return {
          ...caseItem,
          attached_node_ids: unique([...caseItem.attached_node_ids, nodeId]),
          lane_assignments: { ...caseItem.lane_assignments, [nodeId]: lane },
          updated_at: nowIso(),
        };
      }),
    }));
  },
  detachNodeFromCase: (caseId, nodeId) => {
    commit(set, get, (doc) => ({
      ...doc,
      cases: doc.cases.map((caseItem) => {
        if (caseItem.id !== caseId) return caseItem;
        const nextAssignments = { ...caseItem.lane_assignments };
        delete nextAssignments[nodeId];
        return {
          ...caseItem,
          attached_node_ids: caseItem.attached_node_ids.filter(
            (id) => id !== nodeId,
          ),
          lane_assignments: nextAssignments,
          updated_at: nowIso(),
        };
      }),
    }));
  },
  setCaseNodeLane: (caseId, nodeId, lane) => {
    if (!caseLanes.includes(lane)) return;
    commit(set, get, (doc) => ({
      ...doc,
      cases: doc.cases.map((caseItem) =>
        caseItem.id === caseId
          ? {
              ...caseItem,
              lane_assignments: {
                ...caseItem.lane_assignments,
                [nodeId]: lane,
              },
              updated_at: nowIso(),
            }
          : caseItem,
      ),
    }));
  },
  addRule: () => {
    const created = createRule({ name: "New rule", category: "mixed" });
    commit(set, get, (doc) => ({ ...doc, rules: [...doc.rules, created] }));
  },
  updateRule: (id, patch) => {
    commit(set, get, (doc) => ({
      ...doc,
      rules: doc.rules.map((ruleItem) =>
        ruleItem.id === id
          ? { ...ruleItem, ...patch, id: ruleItem.id, updated_at: nowIso() }
          : ruleItem,
      ),
      nodes: doc.nodes.map((node) => {
        if (!patch.target_node_ids) return node;
        const shouldHaveRule = patch.target_node_ids.includes(node.id);
        const hasRule = node.related_rule_ids.includes(id);
        if (shouldHaveRule === hasRule) return node;
        return {
          ...node,
          related_rule_ids: shouldHaveRule
            ? [...node.related_rule_ids, id]
            : node.related_rule_ids.filter((ruleId) => ruleId !== id),
          updated_at: nowIso(),
        };
      }),
    }));
  },
  deleteRule: (id) => {
    const idSet = new Set([id]);
    commit(set, get, (doc) => ({
      ...doc,
      rules: doc.rules.filter((ruleItem) => ruleItem.id !== id),
      nodes: doc.nodes.map((node) => ({
        ...node,
        related_rule_ids: removeIds(node.related_rule_ids, idSet),
      })),
      cases: doc.cases.map((caseItem) => ({
        ...caseItem,
        selected_rule_ids: removeIds(caseItem.selected_rule_ids, idSet),
      })),
    }));
  },
  createChoiceGroupFromSelection: () => {
    const selected = get().doc.nodes.filter((node) =>
      get().selectedNodeIds.includes(node.id),
    );
    if (selected.length < 2) return;
    const groupId = createId("choice_group");
    commit(set, get, (doc) => ({
      ...doc,
      nodes: doc.nodes.map((node) =>
        selected.some((selectedNode) => selectedNode.id === node.id)
          ? {
              ...node,
              probability_role:
                node.probability_role === "none"
                  ? "posterior"
                  : node.probability_role,
              choice_group_id: groupId,
              base_weight:
                node.base_weight ??
                node.prior_probability ??
                node.posterior_probability ??
                node.confidence,
              prior_probability:
                node.prior_probability ??
                node.posterior_probability ??
                1 / selected.length,
              posterior_probability:
                node.posterior_probability ??
                node.prior_probability ??
                1 / selected.length,
              distribution_family: node.distribution_family ?? "categorical",
              propagation_policy: "normalize_siblings",
              updated_at: nowIso(),
            }
          : node,
      ),
    }));
  },
  runPropagationPreview: (changedNodeId) => {
    const preview = runPropagation(get().doc, changedNodeId);
    set({ lastPropagationPreview: preview });
  },
  applyPropagationPreview: () => {
    const preview = get().lastPropagationPreview;
    if (!preview) return;
    commit(set, get, () => preview.updated_workspace);
    set({ lastPropagationPreview: undefined });
  },
  clearPropagationPreview: () => set({ lastPropagationPreview: undefined }),
  recordReasoningLabSimulation: (action, summary) => {
    commit(set, get, (doc) => ({
      ...doc,
      pruning_actions: [
        ...doc.pruning_actions.filter((item) => item.id !== action.id),
        action,
      ],
      impact_summaries: [
        ...doc.impact_summaries.filter(
          (item) =>
            item.before_snapshot_id !== summary.before_snapshot_id ||
            item.after_snapshot_id !== summary.after_snapshot_id,
        ),
        summary,
      ],
    }));
  },
  addTeachingLog: (log) => {
    commit(set, get, (doc) => ({
      ...doc,
      teaching_logs: [...doc.teaching_logs, log],
    }));
  },
  importDocument: (doc) => {
    const parsed = normalizeWorkspaceDocument(doc);
    commit(set, get, () => parsed);
    set({
      selectedNodeIds: [],
      selectedEdgeIds: [],
      lastPropagationPreview: undefined,
    });
  },
  undo: () => {
    const [previous, ...rest] = get().undoStack;
    if (!previous) return;
    set({
      doc: previous,
      undoStack: rest,
      redoStack: [get().doc, ...get().redoStack].slice(0, historyLimit),
      saveStatus: "idle",
    });
  },
  redo: () => {
    const [next, ...rest] = get().redoStack;
    if (!next) return;
    set({
      doc: next,
      redoStack: rest,
      undoStack: [get().doc, ...get().undoStack].slice(0, historyLimit),
      saveStatus: "idle",
    });
  },
}));
