import type {
  Project,
  Sheet,
  WorkspaceDocument,
  WorkspaceScopeMode,
} from "./schema";

export type ScopedWorkspace = WorkspaceDocument & {
  nodes: WorkspaceDocument["nodes"];
  edges: WorkspaceDocument["edges"];
  cases: WorkspaceDocument["cases"];
  rules: WorkspaceDocument["rules"];
  saved_views: WorkspaceDocument["saved_views"];
};

export function getActiveProject(doc: WorkspaceDocument): Project | undefined {
  return (
    doc.projects.find((project) => project.id === doc.active_project_id) ??
    doc.projects[0]
  );
}

export function getActiveSheet(doc: WorkspaceDocument): Sheet | undefined {
  return (
    doc.sheets.find((sheet) => sheet.id === doc.active_sheet_id) ??
    doc.sheets.find((sheet) => sheet.project_id === doc.active_project_id) ??
    doc.sheets[0]
  );
}

export function getProjectSheets(
  doc: WorkspaceDocument,
  projectId = getActiveProject(doc)?.id,
): Sheet[] {
  if (!projectId) return [];
  return doc.sheets.filter((sheet) => sheet.project_id === projectId);
}

export function getScopedIds(
  doc: WorkspaceDocument,
  scope: WorkspaceScopeMode,
): {
  nodeIds: Set<string>;
  edgeIds: Set<string>;
  caseIds: Set<string>;
  ruleIds: Set<string>;
  savedViewIds: Set<string>;
} {
  if (scope === "workspace") {
    return {
      nodeIds: new Set(doc.nodes.map((node) => node.id)),
      edgeIds: new Set(doc.edges.map((edge) => edge.id)),
      caseIds: new Set(doc.cases.map((caseItem) => caseItem.id)),
      ruleIds: new Set(doc.rules.map((rule) => rule.id)),
      savedViewIds: new Set(doc.saved_views.map((view) => view.id)),
    };
  }

  const sheets =
    scope === "sheet"
      ? [getActiveSheet(doc)].filter((sheet): sheet is Sheet => Boolean(sheet))
      : getProjectSheets(doc);
  return {
    nodeIds: new Set(sheets.flatMap((sheet) => sheet.node_ids)),
    edgeIds: new Set(sheets.flatMap((sheet) => sheet.edge_ids)),
    caseIds: new Set(sheets.flatMap((sheet) => sheet.case_ids)),
    ruleIds: new Set(sheets.flatMap((sheet) => sheet.rule_ids)),
    savedViewIds: new Set(sheets.flatMap((sheet) => sheet.saved_view_ids)),
  };
}

export function getScopedWorkspace(
  doc: WorkspaceDocument,
  scope: WorkspaceScopeMode,
): ScopedWorkspace {
  const ids = getScopedIds(doc, scope);
  const nodes = doc.nodes.filter((node) => ids.nodeIds.has(node.id));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = doc.edges.filter(
    (edge) =>
      ids.edgeIds.has(edge.id) &&
      nodeIds.has(edge.source) &&
      nodeIds.has(edge.target),
  );
  return {
    ...doc,
    nodes,
    edges,
    cases: doc.cases.filter((caseItem) => ids.caseIds.has(caseItem.id)),
    rules: doc.rules.filter((rule) => ids.ruleIds.has(rule.id)),
    saved_views: doc.saved_views.filter((view) =>
      ids.savedViewIds.has(view.id),
    ),
  };
}

export function getProjectNodeIds(doc: WorkspaceDocument): Set<string> {
  return getScopedIds(doc, "project").nodeIds;
}

export function classifyNodeScope(
  doc: WorkspaceDocument,
  nodeId: string,
): "sheet" | "project" | "workspace" {
  const activeSheet = getActiveSheet(doc);
  if (activeSheet?.node_ids.includes(nodeId)) return "sheet";
  if (getProjectNodeIds(doc).has(nodeId)) return "project";
  return "workspace";
}

export function classifyReadingDrawerItemScope(
  doc: WorkspaceDocument,
  itemId: string,
): "sheet" | "project" | "workspace" {
  const activeSheet = getActiveSheet(doc);
  if (activeSheet?.reading_drawer_item_ids.includes(itemId)) return "sheet";
  if (
    getProjectSheets(doc).some((sheet) =>
      sheet.reading_drawer_item_ids.includes(itemId),
    )
  ) {
    return "project";
  }
  return "workspace";
}

export function classifyExceptionScope(
  doc: WorkspaceDocument,
  nodeId: string,
): "sheet" | "project" | "workspace" {
  const activeSheet = getActiveSheet(doc);
  if (activeSheet?.exception_node_ids.includes(nodeId)) return "sheet";
  if (
    getProjectSheets(doc).some((sheet) =>
      sheet.exception_node_ids.includes(nodeId),
    )
  ) {
    return "project";
  }
  return "workspace";
}

export function addIdsToSheet(
  doc: WorkspaceDocument,
  sheetId: string | undefined,
  ids: {
    nodeIds?: string[];
    edgeIds?: string[];
    caseIds?: string[];
    ruleIds?: string[];
    savedViewIds?: string[];
    readingDrawerItemIds?: string[];
    exceptionNodeIds?: string[];
    residualGroupIds?: string[];
  },
): WorkspaceDocument {
  if (!sheetId) return doc;
  return {
    ...doc,
    sheets: doc.sheets.map((sheet) =>
      sheet.id === sheetId
        ? {
            ...sheet,
            node_ids: unique([...sheet.node_ids, ...(ids.nodeIds ?? [])]),
            edge_ids: unique([...sheet.edge_ids, ...(ids.edgeIds ?? [])]),
            case_ids: unique([...sheet.case_ids, ...(ids.caseIds ?? [])]),
            rule_ids: unique([...sheet.rule_ids, ...(ids.ruleIds ?? [])]),
            saved_view_ids: unique([
              ...sheet.saved_view_ids,
              ...(ids.savedViewIds ?? []),
            ]),
            reading_drawer_item_ids: unique([
              ...sheet.reading_drawer_item_ids,
              ...(ids.readingDrawerItemIds ?? []),
            ]),
            exception_node_ids: unique([
              ...sheet.exception_node_ids,
              ...(ids.exceptionNodeIds ?? []),
            ]),
            residual_group_ids: unique([
              ...sheet.residual_group_ids,
              ...(ids.residualGroupIds ?? []),
            ]),
          }
        : sheet,
    ),
  };
}

export function addIdsToActiveSheet(
  doc: WorkspaceDocument,
  ids: Parameters<typeof addIdsToSheet>[2],
): WorkspaceDocument {
  return addIdsToSheet(doc, getActiveSheet(doc)?.id, ids);
}

export function removeIdsFromSheets(
  doc: WorkspaceDocument,
  ids: {
    nodeIds?: Set<string>;
    edgeIds?: Set<string>;
    caseIds?: Set<string>;
    ruleIds?: Set<string>;
    savedViewIds?: Set<string>;
  },
): WorkspaceDocument {
  return {
    ...doc,
    sheets: doc.sheets.map((sheet) => ({
      ...sheet,
      node_ids: ids.nodeIds
        ? sheet.node_ids.filter((id) => !ids.nodeIds?.has(id))
        : sheet.node_ids,
      edge_ids: ids.edgeIds
        ? sheet.edge_ids.filter((id) => !ids.edgeIds?.has(id))
        : sheet.edge_ids,
      case_ids: ids.caseIds
        ? sheet.case_ids.filter((id) => !ids.caseIds?.has(id))
        : sheet.case_ids,
      rule_ids: ids.ruleIds
        ? sheet.rule_ids.filter((id) => !ids.ruleIds?.has(id))
        : sheet.rule_ids,
      saved_view_ids: ids.savedViewIds
        ? sheet.saved_view_ids.filter((id) => !ids.savedViewIds?.has(id))
        : sheet.saved_view_ids,
    })),
  };
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}
