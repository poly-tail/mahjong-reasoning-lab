import Dexie, { type Table } from "dexie";
import { seedWorkspace } from "../domain/seed";
import {
  normalizeWorkspaceDocument,
  workspaceDocumentSchema,
  type WorkspaceDocument,
} from "../domain/schema";

const DOC_KEY = "primary";

type WorkspaceRecord = {
  id: string;
  doc: WorkspaceDocument;
  saved_at: string;
};

class WorkspaceDb extends Dexie {
  workspaces!: Table<WorkspaceRecord, string>;

  constructor() {
    super("mahjongKnowledgeMapWorkspace");
    this.version(1).stores({
      workspaces: "id,saved_at",
    });
  }
}

export const workspaceDb = new WorkspaceDb();

export async function loadWorkspace(): Promise<WorkspaceDocument> {
  const record = await workspaceDb.workspaces.get(DOC_KEY);
  if (!record) return seedWorkspace;
  return mergeMissingSeed(normalizeWorkspaceDocument(record.doc));
}

export async function saveWorkspace(doc: WorkspaceDocument): Promise<void> {
  const parsed = workspaceDocumentSchema.parse(doc);
  await workspaceDb.workspaces.put({
    id: DOC_KEY,
    doc: parsed,
    saved_at: new Date().toISOString(),
  });
}

export async function clearLocalWorkspace(): Promise<void> {
  await workspaceDb.workspaces.delete(DOC_KEY);
}

function mergeMissingSeed(doc: WorkspaceDocument): WorkspaceDocument {
  const nodeIds = new Set(doc.nodes.map((node) => node.id));
  const edgeIds = new Set(doc.edges.map((edge) => edge.id));
  const ruleIds = new Set(doc.rules.map((rule) => rule.id));
  const viewIds = new Set(doc.saved_views.map((view) => view.id));
  const actionIds = new Set(doc.pruning_actions.map((action) => action.id));
  const chainIds = new Set(doc.reading_chains.map((chain) => chain.id));
  const teachingIds = new Set(
    doc.teaching_logs.map((log) => `${log.case_id}:${log.action_id}`),
  );

  return workspaceDocumentSchema.parse({
    ...doc,
    nodes: [
      ...doc.nodes,
      ...seedWorkspace.nodes.filter((node) => !nodeIds.has(node.id)),
    ],
    edges: [
      ...doc.edges,
      ...seedWorkspace.edges.filter((edge) => !edgeIds.has(edge.id)),
    ],
    rules: [
      ...doc.rules,
      ...seedWorkspace.rules.filter((rule) => !ruleIds.has(rule.id)),
    ],
    saved_views: [
      ...doc.saved_views,
      ...seedWorkspace.saved_views.filter((view) => !viewIds.has(view.id)),
    ],
    pruning_actions: [
      ...doc.pruning_actions,
      ...seedWorkspace.pruning_actions.filter(
        (action) => !actionIds.has(action.id),
      ),
    ],
    impact_summaries: [
      ...doc.impact_summaries,
      ...seedWorkspace.impact_summaries.filter(
        (summary) =>
          !doc.impact_summaries.some(
            (item) =>
              item.before_snapshot_id === summary.before_snapshot_id &&
              item.after_snapshot_id === summary.after_snapshot_id,
          ),
      ),
    ],
    reading_utilities: [
      ...doc.reading_utilities,
      ...seedWorkspace.reading_utilities.filter(
        (utility) =>
          !doc.reading_utilities.some(
            (item) => item.target_id === utility.target_id,
          ),
      ),
    ],
    reading_chains: [
      ...doc.reading_chains,
      ...seedWorkspace.reading_chains.filter(
        (chain) => !chainIds.has(chain.id),
      ),
    ],
    averaging_safety: [
      ...doc.averaging_safety,
      ...seedWorkspace.averaging_safety.filter(
        (safety) =>
          !doc.averaging_safety.some(
            (item) => item.target_id === safety.target_id,
          ),
      ),
    ],
    teaching_logs: [
      ...doc.teaching_logs,
      ...seedWorkspace.teaching_logs.filter(
        (log) => !teachingIds.has(`${log.case_id}:${log.action_id}`),
      ),
    ],
  });
}
