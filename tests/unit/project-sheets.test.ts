import { readFileSync } from "node:fs";
import { describe, expect, it, beforeEach } from "vitest";
import { useAppStore } from "../../src/app/store";
import { getScopedIds } from "../../src/domain/projectSheets";
import { seedWorkspace } from "../../src/domain/seed";
import {
  normalizeWorkspaceDocument,
  type TemplateSelectionOptions,
} from "../../src/domain/schema";
import {
  applyTemplatesToSheet,
  getTemplateCatalog,
} from "../../src/domain/templateCatalog";

const tileEfficiencyOnly: TemplateSelectionOptions = {
  tile_efficiency: true,
  tile_count: false,
  yaku: false,
  abstract_reading: false,
};

describe("project and sheet workspace scope", () => {
  beforeEach(() => {
    useAppStore.setState({
      doc: seedWorkspace,
      selectedNodeIds: [],
      selectedEdgeIds: [],
      search: "",
      tagFilter: [],
      nodeTypeFilter: [],
      scopeMode: "sheet",
      undoStack: [],
      redoStack: [],
    });
  });

  it("migrates a v4 workspace without project fields into default project and sheet", () => {
    const { projects, sheets, ...legacyBase } = seedWorkspace;
    const legacy: Record<string, unknown> = { ...legacyBase };
    delete legacy.active_project_id;
    delete legacy.active_sheet_id;
    delete legacy.global_settings;
    expect(projects.length).toBeGreaterThan(0);
    expect(sheets.length).toBeGreaterThan(0);

    const migrated = normalizeWorkspaceDocument({
      ...legacy,
    });

    expect(migrated.projects[0]?.title).toBe("Default Project");
    expect(migrated.sheets[0]?.title).toBe("Default Sheet");
    expect(migrated.sheets[0]?.node_ids.length).toBe(migrated.nodes.length);
    expect(migrated.sheets[0]?.case_ids).toContain(migrated.active_case_id);
    expect(migrated.global_settings.project_creation_defaults.yaku).toBe(true);
  });

  it("exposes the four Reading Probability Core templates", () => {
    expect(getTemplateCatalog().map((template) => template.label)).toEqual([
      "牌理",
      "枚数",
      "手役",
      "抽象的な読み",
    ]);
  });

  it("applies selected templates to a sheet once by default", () => {
    const sheetId = seedWorkspace.active_sheet_id!;
    const first = applyTemplatesToSheet(
      seedWorkspace,
      sheetId,
      tileEfficiencyOnly,
    );
    const second = applyTemplatesToSheet(
      first.doc,
      sheetId,
      tileEfficiencyOnly,
    );

    expect(first.appliedKeys).toEqual(["tile_efficiency"]);
    expect(first.createdNodeIds.length).toBeGreaterThan(0);
    expect(second.createdNodeIds).toEqual([]);
    expect(second.skippedKeys).toEqual(["tile_efficiency"]);
    expect(
      second.doc.sheets.find((sheet) => sheet.id === sheetId)?.template_source
        ?.enabled_template_keys,
    ).toEqual(["tile_efficiency"]);
  });

  it("creates a new sheet with selected templates and attaches new cases to it", () => {
    const projectId = seedWorkspace.active_project_id!;
    useAppStore.getState().createSheet({
      projectId,
      title: "枚数検討",
      templateOptions: tileEfficiencyOnly,
    });

    const createdSheet = useAppStore
      .getState()
      .doc.sheets.find((sheet) => sheet.title === "枚数検討");
    expect(createdSheet?.template_source?.enabled_template_keys).toEqual([
      "tile_efficiency",
    ]);
    expect(createdSheet?.node_ids.length).toBeGreaterThan(0);

    useAppStore.getState().addCase();
    const state = useAppStore.getState();
    const activeSheet = state.doc.sheets.find(
      (sheet) => sheet.id === state.doc.active_sheet_id,
    );
    expect(activeSheet?.id).toBe(createdSheet?.id);
    expect(activeSheet?.case_ids).toContain(state.doc.active_case_id);
  });

  it("returns scoped ids for sheet, project, and workspace", () => {
    const sheet = getScopedIds(seedWorkspace, "sheet");
    const project = getScopedIds(seedWorkspace, "project");
    const workspace = getScopedIds(seedWorkspace, "workspace");

    expect(sheet.nodeIds.size).toBeGreaterThan(0);
    expect(project.nodeIds.size).toBeGreaterThanOrEqual(sheet.nodeIds.size);
    expect(workspace.nodeIds.size).toBeGreaterThanOrEqual(project.nodeIds.size);
  });

  it("documents that four axis impact weights do not need to total 100", () => {
    const text = readFileSync("docs/quick-reading-input.md", "utf8");
    expect(text).toContain("4軸の合計を100にする必要はありません");
  });
});
