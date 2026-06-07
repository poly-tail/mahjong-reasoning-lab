import { create } from "zustand";
import {
  createCase,
  createId,
  createKnowledgeEdge,
  createKnowledgeNode,
  createProject as createProjectRecord,
  createRule,
  createSheet as createSheetRecord,
  inferLaneFromNodeType,
  nowIso,
} from "../domain/factory";
import { runPropagation, type PropagationPreview } from "../domain/probability";
import {
  buildReadingImpactPreview,
  type ReadingImpactDraft,
} from "../domain/readingNumerics";
import { edgeTypeLabels, nodeTypeLabels } from "../domain/labels";
import type { MappingDraftNode } from "../domain/mappingTemplates";
import { seedWorkspace } from "../domain/seed";
import { applyTemplatesToSheet } from "../domain/templateCatalog";
import {
  addIdsToActiveSheet,
  getActiveSheet,
  removeIdsFromSheets,
} from "../domain/projectSheets";
import {
  caseLanes,
  defaultGlobalSettings,
  mergeTemplateSelectionOptions,
  normalizeWorkspaceDocument,
  normalizeWorkspaceScopes,
  workspaceDocumentSchema,
  type CaseData,
  type CaseLane,
  type EdgeType,
  type GlobalSettings,
  type KnowledgeEdge,
  type KnowledgeNode,
  type NodeType,
  type ImpactSummary,
  type PruningAction,
  type RuleDefinition,
  type SavedView,
  type TeachingLog,
  type TemplateSelectionOptions,
  type WorkspaceDocument,
  type WorkspaceScopeMode,
} from "../domain/schema";

export type Screen =
  | "case"
  | "theory"
  | "probability"
  | "validation"
  | "teaching"
  | "data";
export type SaveStatus = "loading" | "idle" | "saving" | "saved" | "error";

type WorkspaceMutation = (doc: WorkspaceDocument) => WorkspaceDocument;

export type CreateProjectInput = {
  title: string;
  description?: string;
  tags?: string[];
  createInitialSheet: boolean;
  initialSheetTitle?: string;
  templateOptions: TemplateSelectionOptions;
};

export type CreateSheetInput = {
  projectId: string;
  title: string;
  description?: string;
  tags?: string[];
  templateOptions: TemplateSelectionOptions;
};

export const defaultAutoSaveIntervalMinutes = 5;
const minAutoSaveIntervalMinutes = 1;
const maxAutoSaveIntervalMinutes = 60;
const autoSaveIntervalStorageKey =
  "mahjongKnowledgeMap.autoSaveIntervalMinutes";

type AppState = {
  doc: WorkspaceDocument;
  activeScreen: Screen;
  selectedNodeIds: string[];
  selectedEdgeIds: string[];
  search: string;
  tagFilter: string[];
  nodeTypeFilter: NodeType[];
  scopeMode: WorkspaceScopeMode;
  activeSavedViewId?: string;
  undoStack: WorkspaceDocument[];
  redoStack: WorkspaceDocument[];
  saveStatus: SaveStatus;
  autoSaveIntervalMinutes: number;
  lastSavedAt?: string;
  errorMessage?: string;
  lastPropagationPreview?: PropagationPreview;
  hydrate: (doc: WorkspaceDocument) => void;
  resetToSeed: () => void;
  setScreen: (screen: Screen) => void;
  setSaveStatus: (status: SaveStatus, message?: string) => void;
  markSaved: () => void;
  setAutoSaveIntervalMinutes: (minutes: number) => void;
  setScopeMode: (mode: WorkspaceScopeMode) => void;
  setActiveProject: (projectId: string) => void;
  setActiveSheet: (sheetId: string) => void;
  createProject: (input: CreateProjectInput) => void;
  createSheet: (input: CreateSheetInput) => void;
  updateGlobalSettings: (patch: Partial<GlobalSettings>) => void;
  resetGlobalSettings: () => void;
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
  createKnowledgeNodesFromDrafts: (
    drafts: MappingDraftNode[],
    attachToActiveCase?: boolean,
  ) => void;
  applyReadingImpactDraft: (
    draft: ReadingImpactDraft,
    attachToActiveCase?: boolean,
  ) => void;
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
const nodeLayout = {
  width: 252,
  height: 172,
  gap: 24,
} as const;

type NodePosition = KnowledgeNode["position"];

type NodeBounds = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

function normalizeAutoSaveIntervalMinutes(minutes: number): number {
  if (!Number.isFinite(minutes)) return defaultAutoSaveIntervalMinutes;
  return Math.min(
    maxAutoSaveIntervalMinutes,
    Math.max(minAutoSaveIntervalMinutes, Math.round(minutes)),
  );
}

function readAutoSaveIntervalMinutes(): number {
  if (typeof window === "undefined") return defaultAutoSaveIntervalMinutes;
  try {
    const saved = window.localStorage.getItem(autoSaveIntervalStorageKey);
    return saved
      ? normalizeAutoSaveIntervalMinutes(Number(saved))
      : defaultAutoSaveIntervalMinutes;
  } catch {
    return defaultAutoSaveIntervalMinutes;
  }
}

function writeAutoSaveIntervalMinutes(minutes: number) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(autoSaveIntervalStorageKey, String(minutes));
  } catch {
    // Local storage can be unavailable in restricted browser contexts.
  }
}

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
  const next = normalizeWorkspaceScopes(
    workspaceDocumentSchema.parse(touch(mutation(previous))),
  );
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
  const activeSheet = getActiveSheet(doc);
  if (activeSheet) {
    const activeCaseInSheet = doc.cases.find(
      (caseItem) =>
        caseItem.id === doc.active_case_id &&
        activeSheet.case_ids.includes(caseItem.id),
    );
    if (activeCaseInSheet) return activeCaseInSheet;
    const firstSheetCase = doc.cases.find((caseItem) =>
      activeSheet.case_ids.includes(caseItem.id),
    );
    if (firstSheetCase) return firstSheetCase;
  }
  return (
    doc.cases.find((caseItem) => caseItem.id === doc.active_case_id) ??
    doc.cases[0]
  );
}

function firstCaseIdForSheet(
  doc: WorkspaceDocument,
  sheetId?: string,
): string | undefined {
  const sheet = doc.sheets.find((item) => item.id === sheetId);
  return (
    doc.cases.find((caseItem) => sheet?.case_ids.includes(caseItem.id))?.id ??
    doc.cases[0]?.id
  );
}

function tagsFromInput(tags?: string[]): string[] {
  return unique((tags ?? []).map((tag) => tag.trim()));
}

function averagePosition(nodes: KnowledgeNode[]) {
  if (nodes.length === 0) return { x: 160, y: 160 };
  const total = nodes.reduce(
    (acc, node) => ({ x: acc.x + node.position.x, y: acc.y + node.position.y }),
    { x: 0, y: 0 },
  );
  return { x: total.x / nodes.length - 60, y: total.y / nodes.length - 70 };
}

function normalizePosition(position: NodePosition): NodePosition {
  return {
    x: Math.max(0, Math.round(position.x)),
    y: Math.max(0, Math.round(position.y)),
  };
}

function nodeBounds(position: NodePosition): NodeBounds {
  const halfGap = nodeLayout.gap / 2;
  return {
    left: position.x - halfGap,
    top: position.y - halfGap,
    right: position.x + nodeLayout.width + halfGap,
    bottom: position.y + nodeLayout.height + halfGap,
  };
}

function overlaps(left: NodeBounds, right: NodeBounds): boolean {
  return (
    left.left < right.right &&
    left.right > right.left &&
    left.top < right.bottom &&
    left.bottom > right.top
  );
}

function positionCollides(
  id: string,
  position: NodePosition,
  nodes: Pick<KnowledgeNode, "id" | "position">[],
): boolean {
  const target = nodeBounds(position);
  return nodes.some(
    (node) => node.id !== id && overlaps(target, nodeBounds(node.position)),
  );
}

export function resolveNonOverlappingNodePosition(
  id: string,
  position: NodePosition,
  nodes: Pick<KnowledgeNode, "id" | "position">[],
): NodePosition {
  const desired = normalizePosition(position);
  if (!positionCollides(id, desired, nodes)) return desired;

  const candidates = new Map<string, NodePosition>();
  const addCandidate = (candidate: NodePosition) => {
    const normalized = normalizePosition(candidate);
    candidates.set(`${normalized.x},${normalized.y}`, normalized);
  };

  for (const node of nodes) {
    if (node.id === id) continue;
    if (!overlaps(nodeBounds(desired), nodeBounds(node.position))) continue;
    addCandidate({
      x: node.position.x + nodeLayout.width + nodeLayout.gap,
      y: desired.y,
    });
    addCandidate({
      x: node.position.x - nodeLayout.width - nodeLayout.gap,
      y: desired.y,
    });
    addCandidate({
      x: desired.x,
      y: node.position.y + nodeLayout.height + nodeLayout.gap,
    });
    addCandidate({
      x: desired.x,
      y: node.position.y - nodeLayout.height - nodeLayout.gap,
    });
  }

  for (let ring = 1; ring <= 48; ring += 1) {
    for (let xStep = -ring; xStep <= ring; xStep += 1) {
      for (let yStep = -ring; yStep <= ring; yStep += 1) {
        if (Math.max(Math.abs(xStep), Math.abs(yStep)) !== ring) continue;
        addCandidate({
          x: desired.x + xStep * (nodeLayout.width + nodeLayout.gap),
          y: desired.y + yStep * (nodeLayout.height + nodeLayout.gap),
        });
      }
    }
  }

  const sortedCandidates = Array.from(candidates.values()).sort(
    (left, right) =>
      distanceSquared(left, desired) - distanceSquared(right, desired),
  );
  return (
    sortedCandidates.find(
      (candidate) => !positionCollides(id, candidate, nodes),
    ) ?? desired
  );
}

function distanceSquared(left: NodePosition, right: NodePosition) {
  return Math.pow(left.x - right.x, 2) + Math.pow(left.y - right.y, 2);
}

export const useAppStore = create<AppState>((set, get) => ({
  doc: seedWorkspace,
  activeScreen: "case",
  selectedNodeIds: [],
  selectedEdgeIds: [],
  search: "",
  tagFilter: [],
  nodeTypeFilter: [],
  scopeMode: "sheet",
  undoStack: [],
  redoStack: [],
  saveStatus: "loading",
  autoSaveIntervalMinutes: readAutoSaveIntervalMinutes(),
  hydrate: (doc) => {
    const parsed = normalizeWorkspaceDocument(doc);
    set({
      doc: parsed,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      undoStack: [],
      redoStack: [],
      saveStatus: "saved",
      lastSavedAt: undefined,
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
  setAutoSaveIntervalMinutes: (minutes) => {
    const normalized = normalizeAutoSaveIntervalMinutes(minutes);
    writeAutoSaveIntervalMinutes(normalized);
    set({ autoSaveIntervalMinutes: normalized });
  },
  setScopeMode: (mode) => set({ scopeMode: mode }),
  setActiveProject: (projectId) => {
    commit(
      set,
      get,
      (doc) => {
        const project = doc.projects.find((item) => item.id === projectId);
        if (!project) return doc;
        const sheet =
          doc.sheets.find(
            (item) =>
              item.project_id === project.id &&
              (project.sheet_ids.length === 0 ||
                project.sheet_ids.includes(item.id)),
          ) ?? doc.sheets.find((item) => item.project_id === project.id);
        return {
          ...doc,
          active_project_id: project.id,
          active_sheet_id: sheet?.id,
          active_case_id: firstCaseIdForSheet(doc, sheet?.id),
        };
      },
      false,
    );
    set({ selectedNodeIds: [], selectedEdgeIds: [] });
  },
  setActiveSheet: (sheetId) => {
    commit(
      set,
      get,
      (doc) => {
        const sheet = doc.sheets.find((item) => item.id === sheetId);
        if (!sheet) return doc;
        return {
          ...doc,
          active_project_id: sheet.project_id,
          active_sheet_id: sheet.id,
          active_case_id: firstCaseIdForSheet(doc, sheet.id),
        };
      },
      false,
    );
    set({ selectedNodeIds: [], selectedEdgeIds: [] });
  },
  createProject: (input) => {
    const title = input.title.trim();
    if (!title) return;
    const now = nowIso();
    const projectId = createId("project");
    const sheetId = input.createInitialSheet ? createId("sheet") : undefined;
    const templateOptions = mergeTemplateSelectionOptions(
      input.templateOptions,
    );
    commit(set, get, (doc) => {
      const project = createProjectRecord({
        id: projectId,
        title,
        description: input.description?.trim() ?? "",
        tags: tagsFromInput(input.tags),
        default_sheet_template_options: templateOptions,
        sheet_ids: sheetId ? [sheetId] : [],
        created_at: now,
        updated_at: now,
      });
      const sheet = sheetId
        ? createSheetRecord({
            id: sheetId,
            project_id: project.id,
            title: input.initialSheetTitle?.trim() || `${title} Sheet`,
            description: input.description?.trim() ?? "",
            tags: tagsFromInput(input.tags),
            created_at: now,
            updated_at: now,
          })
        : undefined;
      const baseDoc = {
        ...doc,
        projects: [...doc.projects, project],
        sheets: sheet ? [...doc.sheets, sheet] : doc.sheets,
        active_project_id: project.id,
        active_sheet_id: sheet?.id,
        active_case_id: undefined,
      };
      return sheet
        ? applyTemplatesToSheet(baseDoc, sheet.id, templateOptions).doc
        : baseDoc;
    });
    set({ selectedNodeIds: [], selectedEdgeIds: [], scopeMode: "sheet" });
  },
  createSheet: (input) => {
    const title = input.title.trim();
    if (!title) return;
    const project = get().doc.projects.find(
      (item) => item.id === input.projectId,
    );
    if (!project) return;
    const now = nowIso();
    const sheet = createSheetRecord({
      project_id: project.id,
      title,
      description: input.description?.trim() ?? "",
      tags: tagsFromInput(input.tags),
      created_at: now,
      updated_at: now,
    });
    const templateOptions = mergeTemplateSelectionOptions(
      input.templateOptions,
    );
    commit(set, get, (doc) => {
      const baseDoc = {
        ...doc,
        projects: doc.projects.map((item) =>
          item.id === project.id
            ? {
                ...item,
                sheet_ids: unique([...item.sheet_ids, sheet.id]),
                updated_at: now,
              }
            : item,
        ),
        sheets: [...doc.sheets, sheet],
        active_project_id: project.id,
        active_sheet_id: sheet.id,
        active_case_id: undefined,
      };
      return applyTemplatesToSheet(baseDoc, sheet.id, templateOptions).doc;
    });
    set({ selectedNodeIds: [], selectedEdgeIds: [], scopeMode: "sheet" });
  },
  updateGlobalSettings: (patch) => {
    commit(set, get, (doc) => ({
      ...doc,
      global_settings: {
        ...doc.global_settings,
        ...patch,
        project_creation_defaults: patch.project_creation_defaults
          ? mergeTemplateSelectionOptions(patch.project_creation_defaults)
          : doc.global_settings.project_creation_defaults,
        sheet_creation_defaults: patch.sheet_creation_defaults
          ? mergeTemplateSelectionOptions(patch.sheet_creation_defaults)
          : doc.global_settings.sheet_creation_defaults,
      },
    }));
  },
  resetGlobalSettings: () => {
    commit(set, get, (doc) => ({
      ...doc,
      global_settings: defaultGlobalSettings,
    }));
  },
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
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        {
          ...doc,
          saved_views: [...doc.saved_views, view],
        },
        { savedViewIds: [view.id] },
      ),
    );
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
    commit(set, get, (doc) =>
      removeIdsFromSheets(
        {
          ...doc,
          saved_views: doc.saved_views.filter((view) => view.id !== id),
        },
        { savedViewIds: new Set([id]) },
      ),
    );
    if (get().activeSavedViewId === id) set({ activeSavedViewId: undefined });
  },
  addNode: (type) => {
    const count = get().doc.nodes.length;
    const created = createKnowledgeNode(type, {
      title: `${nodeTypeLabels[type]}ノード`,
      tags: ["下書き"],
      position: { x: 180 + (count % 8) * 40, y: 140 + (count % 6) * 52 },
    });
    created.position = resolveNonOverlappingNodePosition(
      created.id,
      created.position,
      get().doc.nodes,
    );
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        { ...doc, nodes: [...doc.nodes, created] },
        { nodeIds: [created.id] },
      ),
    );
    set({ selectedNodeIds: [created.id], selectedEdgeIds: [] });
  },
  createKnowledgeNodesFromDrafts: (drafts, attachToActiveCase = false) => {
    if (drafts.length === 0) return;
    const existingNodes = get().doc.nodes;
    const created: KnowledgeNode[] = [];
    const baseCount = existingNodes.length;

    for (const [index, draft] of drafts.entries()) {
      const nodeItem = createKnowledgeNode(draft.type, {
        title: draft.title,
        summary: draft.summary,
        description: draft.description ?? draft.summary,
        tags: draft.tags,
        confidence: draft.confidence,
        applicability: draft.applicability,
        formulas: draft.formulas,
        thresholds: draft.thresholds,
        pruning_hints: draft.pruning_hints,
        probability_role: draft.probability_role,
        base_weight: draft.base_weight,
        dynamic_weight: draft.dynamic_weight,
        prior_probability: draft.prior_probability,
        posterior_probability: draft.posterior_probability,
        lock_mode: draft.lock_mode,
        lock_value: draft.lock_value,
        distribution_family: draft.distribution_family,
        resolves_targets: draft.resolves_targets,
        expected_sign_gain: draft.expected_sign_gain,
        expected_weight_gain: draft.expected_weight_gain,
        expected_margin_gain: draft.expected_margin_gain,
        pruning_safety_change: draft.pruning_safety_change,
        observation_cost: draft.observation_cost,
        timeliness: draft.timeliness,
        source_type: "note",
        position: {
          x: 220 + ((baseCount + index) % 7) * 280,
          y: 120 + Math.floor((baseCount + index) / 7) * 190,
        },
      });
      nodeItem.position = resolveNonOverlappingNodePosition(
        nodeItem.id,
        nodeItem.position,
        [...existingNodes, ...created],
      );
      created.push(nodeItem);
    }

    const activeCaseId = findActiveCase(get().doc)?.id;
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        {
          ...doc,
          nodes: [...doc.nodes, ...created],
          cases:
            attachToActiveCase && activeCaseId
              ? doc.cases.map((caseItem) =>
                  caseItem.id === activeCaseId
                    ? {
                        ...caseItem,
                        attached_node_ids: unique([
                          ...caseItem.attached_node_ids,
                          ...created.map((node) => node.id),
                        ]),
                        lane_assignments: {
                          ...caseItem.lane_assignments,
                          ...Object.fromEntries(
                            created.map((node) => [
                              node.id,
                              inferLaneFromNodeType(node.type),
                            ]),
                          ),
                        },
                        updated_at: nowIso(),
                      }
                    : caseItem,
                )
              : doc.cases,
        },
        { nodeIds: created.map((node) => node.id) },
      ),
    );
    set({
      selectedNodeIds: created.map((node) => node.id),
      selectedEdgeIds: [],
    });
  },
  applyReadingImpactDraft: (draft, attachToActiveCase) => {
    let createdNodeIds: string[] = [];
    const effectiveDraft = {
      ...draft,
      attach_to_active_case: attachToActiveCase ?? draft.attach_to_active_case,
    };
    commit(set, get, (doc) => {
      const preview = buildReadingImpactPreview(doc, effectiveDraft);
      createdNodeIds = preview.createdNodeIds;
      return addIdsToActiveSheet(preview.nextDoc, {
        nodeIds: preview.createdNodeIds,
        edgeIds: preview.createdEdgeIds,
      });
    });
    set({
      selectedNodeIds: createdNodeIds,
      selectedEdgeIds: [],
      lastPropagationPreview: undefined,
    });
  },
  duplicateSelectedNodes: () => {
    const selected = get().doc.nodes.filter((node) =>
      get().selectedNodeIds.includes(node.id),
    );
    if (selected.length === 0) return;
    const copies: KnowledgeNode[] = [];
    for (const node of selected) {
      const copy = {
        ...node,
        id: createId("node"),
        title: `${node.title}のコピー`,
        position: { x: node.position.x + 48, y: node.position.y + 48 },
        group_id: node.group_id,
        created_at: nowIso(),
        updated_at: nowIso(),
      };
      copy.position = resolveNonOverlappingNodePosition(
        copy.id,
        copy.position,
        [...get().doc.nodes, ...copies],
      );
      copies.push(copy);
    }
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        { ...doc, nodes: [...doc.nodes, ...copies] },
        { nodeIds: copies.map((node) => node.id) },
      ),
    );
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
      return removeIdsFromSheets(
        {
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
          edges: doc.edges.filter(
            (edgeItem) => !edgesToRemove.has(edgeItem.id),
          ),
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
        },
        { nodeIds, edgeIds: edgesToRemove },
      );
    });
    set({ selectedNodeIds: [], selectedEdgeIds: [] });
  },
  groupSelectedNodes: () => {
    const selected = get().doc.nodes.filter((node) =>
      get().selectedNodeIds.includes(node.id),
    );
    if (selected.length < 2) return;
    const group = createKnowledgeNode("concept", {
      title: "新しいセクション",
      summary: "選択ノードをまとめた折りたたみセクションです。",
      tags: ["セクション"],
      position: averagePosition(selected),
      is_group: true,
    });
    group.position = resolveNonOverlappingNodePosition(
      group.id,
      group.position,
      get().doc.nodes,
    );
    const selectedIds = new Set(selected.map((node) => node.id));
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        {
          ...doc,
          nodes: [
            ...doc.nodes.map((node) =>
              selectedIds.has(node.id)
                ? { ...node, group_id: group.id, updated_at: nowIso() }
                : node,
            ),
            group,
          ],
        },
        { nodeIds: [group.id] },
      ),
    );
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
    const current = get().doc.nodes.find((node) => node.id === id);
    if (!current) return;
    const nextPosition = resolveNonOverlappingNodePosition(
      id,
      position,
      get().doc.nodes,
    );
    if (
      current.position.x === nextPosition.x &&
      current.position.y === nextPosition.y
    ) {
      return;
    }
    commit(set, get, (doc) => ({
      ...doc,
      nodes: doc.nodes.map((node) =>
        node.id === id
          ? { ...node, position: nextPosition, updated_at: nowIso() }
          : node,
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
    const edgeItem = createKnowledgeEdge({
      source,
      target,
      type,
      label: edgeTypeLabels[type],
    });
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        { ...doc, edges: [...doc.edges, edgeItem] },
        { edgeIds: [edgeItem.id] },
      ),
    );
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
    commit(set, get, (doc) =>
      removeIdsFromSheets(
        {
          ...doc,
          edges: doc.edges.filter((edgeItem) => edgeItem.id !== id),
        },
        { edgeIds: new Set([id]) },
      ),
    );
    set({
      selectedEdgeIds: get().selectedEdgeIds.filter((edgeId) => edgeId !== id),
    });
  },
  addCase: () => {
    const created = createCase({ title: "新しいケース" });
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        {
          ...doc,
          cases: [...doc.cases, created],
          active_case_id: created.id,
        },
        { caseIds: [created.id] },
      ),
    );
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
    const created = createRule({ name: "新しいルール", category: "mixed" });
    commit(set, get, (doc) =>
      addIdsToActiveSheet(
        { ...doc, rules: [...doc.rules, created] },
        { ruleIds: [created.id] },
      ),
    );
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
    commit(set, get, (doc) =>
      removeIdsFromSheets(
        {
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
        },
        { ruleIds: idSet },
      ),
    );
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
