import {
  createKnowledgeEdge,
  createKnowledgeNode,
  createProject,
  createSheet,
  nowIso,
} from "./factory";
import { getReadingDrawerItems } from "./readingDrawer";
import { addIdsToSheet } from "./projectSheets";
import {
  selectedTemplateKeys,
  templateOptionsFromKeys,
  type KnowledgeEdge,
  type KnowledgeNode,
  type Project,
  type Sheet,
  type TemplateKey,
  type TemplateSelectionOptions,
  type WorkspaceDocument,
} from "./schema";

type TemplateAxis = {
  id: string;
  title: string;
  summary: string;
  position: { x: number; y: number };
};

export type TemplateCatalogEntry = {
  key: TemplateKey;
  label: string;
  description: string;
  drawerCategories: string[];
  tags: string[];
};

export type TemplateApplicationResult = {
  doc: WorkspaceDocument;
  appliedKeys: TemplateKey[];
  skippedKeys: TemplateKey[];
  createdNodeIds: string[];
  createdEdgeIds: string[];
};

export const templateDisplayNames: Record<TemplateKey, string> = {
  tile_efficiency: "牌理",
  tile_count: "枚数",
  yaku: "手役",
  abstract_reading: "抽象的な読み",
};

const axisCatalog: TemplateAxis[] = [
  {
    id: "progress_tenpai_axis",
    title: "進行度・聴牌率",
    summary: "シャンテン、聴牌率、速度変化を受ける読みの投影軸。",
    position: { x: 80, y: 40 },
  },
  {
    id: "value_axis",
    title: "打点",
    summary: "役、ドラ、手役移行、打点レンジを受ける読みの投影軸。",
    position: { x: 80, y: 220 },
  },
  {
    id: "wait_shape_quality_axis",
    title: "待ち・形の良さ",
    summary: "受け入れ、良形率、形の伸びを受ける読みの投影軸。",
    position: { x: 80, y: 400 },
  },
  {
    id: "score_situation_threshold_axis",
    title: "点数状況・行動閾値",
    summary: "順位、供託、本場、局収支の閾値を受ける読みの投影軸。",
    position: { x: 80, y: 580 },
  },
];

const catalog: TemplateCatalogEntry[] = [
  {
    key: "tile_efficiency",
    label: templateDisplayNames.tile_efficiency,
    description:
      "形、受け入れ、待ち変化をReading Probability Coreの初期材料として置く。推奨打牌は含めない。",
    drawerCategories: ["wait_shape", "progress_pattern"],
    tags: ["tile_efficiency", "shape", "ukeire", "reading_probability_core"],
  },
  {
    key: "tile_count",
    label: templateDisplayNames.tile_count,
    description:
      "見え枚数、山残り、ワンチャンス、ノーチャンスを候補確率と例外候補の初期材料として置く。",
    drawerCategories: ["danger_safety", "exception_noise"],
    tags: [
      "tile_count",
      "visible_tiles",
      "wall_read",
      "reading_probability_core",
    ],
  },
  {
    key: "yaku",
    label: templateDisplayNames.yaku,
    description:
      "手役、打点、ドラ、役牌バックを打点軸と進行軸へ投影する初期材料として置く。",
    drawerCategories: ["value_pattern", "score_threshold"],
    tags: ["yaku", "hand_value", "dora", "reading_probability_core"],
  },
  {
    key: "abstract_reading",
    label: templateDisplayNames.abstract_reading,
    description:
      "副露意図、傾向、場況、他家介入、mixed/unknownをReasoning Labで扱う初期材料として置く。",
    drawerCategories: [
      "call_intent",
      "table_dynamics",
      "player_tendency",
      "exception_noise",
    ],
    tags: ["abstract_reading", "unknown", "mixed", "reading_probability_core"],
  },
];

export function getTemplateCatalog(): TemplateCatalogEntry[] {
  return catalog;
}

export function createTemplateNodes(
  sheetId: string,
  key: TemplateKey,
): KnowledgeNode[] {
  const entry = catalog.find((item) => item.key === key);
  if (!entry) return [];
  const baseTags = [
    "template_source",
    "reading_probability_core",
    `template:${key}`,
    entry.label,
  ];
  return [
    ...axisCatalog.map((axis) =>
      createKnowledgeNode("metric", {
        id: axisId(sheetId, axis.id),
        title: axis.title,
        summary: axis.summary,
        tags: unique([...baseTags, "canonical_axis", axis.id]),
        confidence: 0.65,
        source_type: "theory",
        position: axis.position,
      }),
    ),
    ...templateSpecificNodes(sheetId, key, baseTags),
  ];
}

export function createTemplateEdges(
  sheetId: string,
  key: TemplateKey,
): KnowledgeEdge[] {
  const specs = edgeSpecs(sheetId, key);
  return specs.map((spec) =>
    createKnowledgeEdge({
      id: `tpl_${sheetId}_${key}_${spec.source}_${spec.target}`,
      source: spec.source,
      target: spec.target,
      type: "influences",
      label: "影響ウェイト",
      relation_layer: "influence",
      sign: spec.sign,
      magnitude: spec.magnitude,
      confidence: spec.confidence,
      notes:
        "影響ウェイトは0-100スコアとして表示し、内部では0-1で保持する。推奨打牌、push/fold、EV判定は含めない。",
    }),
  );
}

export function createTemplateReadingDrawerItems(key: TemplateKey): string[] {
  const entry = catalog.find((item) => item.key === key);
  if (!entry) return [];
  return getReadingDrawerItems()
    .filter((item) => entry.drawerCategories.includes(item.category))
    .slice(0, 12)
    .map((item) => item.id);
}

export function createTemplateExceptionCandidates(
  sheetId: string,
  key: TemplateKey,
): KnowledgeNode[] {
  return createTemplateNodes(sheetId, key).filter(
    (node) => node.type === "exception" || node.type === "ambiguity_marker",
  );
}

export function applyTemplatesToSheet(
  doc: WorkspaceDocument,
  sheetId: string,
  options: TemplateSelectionOptions | TemplateKey[],
  settings: { force?: boolean } = {},
): TemplateApplicationResult {
  const requestedKeys = Array.isArray(options)
    ? options
    : selectedTemplateKeys(options);
  const sheet = doc.sheets.find((item) => item.id === sheetId);
  if (!sheet || requestedKeys.length === 0) {
    return {
      doc,
      appliedKeys: [],
      skippedKeys: requestedKeys,
      createdNodeIds: [],
      createdEdgeIds: [],
    };
  }

  const alreadyApplied = new Set(
    sheet.template_source?.enabled_template_keys ?? [],
  );
  const keysToApply = requestedKeys.filter(
    (key) => settings.force || !alreadyApplied.has(key),
  );
  const skippedKeys = requestedKeys.filter((key) => !keysToApply.includes(key));
  const existingNodeIds = new Set(doc.nodes.map((node) => node.id));
  const existingEdgeIds = new Set(doc.edges.map((edge) => edge.id));
  const createdNodes = keysToApply
    .flatMap((key) => createTemplateNodes(sheetId, key))
    .filter((node) => !existingNodeIds.has(node.id));
  const createdEdges = keysToApply
    .flatMap((key) => createTemplateEdges(sheetId, key))
    .filter((edge) => !existingEdgeIds.has(edge.id));
  const drawerItemIds = keysToApply.flatMap(createTemplateReadingDrawerItems);
  const exceptionNodeIds = createdNodes
    .filter(
      (node) => node.type === "exception" || node.type === "ambiguity_marker",
    )
    .map((node) => node.id);
  const residualGroupIds = keysToApply.map(
    (key) => `tpl_${sheetId}_${key}_residual`,
  );
  const now = nowIso();
  const enabledKeys = uniqueTemplateKeys([
    ...(sheet.template_source?.enabled_template_keys ?? []),
    ...keysToApply,
  ]);
  const nextDoc = addIdsToSheet(
    {
      ...doc,
      nodes: [...doc.nodes, ...createdNodes],
      edges: [...doc.edges, ...createdEdges],
      sheets: doc.sheets.map((item) =>
        item.id === sheetId
          ? {
              ...item,
              updated_at: now,
              template_source: {
                created_from_template: enabledKeys.length > 0,
                enabled_template_keys: enabledKeys,
              },
            }
          : item,
      ),
    },
    sheetId,
    {
      nodeIds: createdNodes.map((node) => node.id),
      edgeIds: createdEdges.map((edge) => edge.id),
      readingDrawerItemIds: drawerItemIds,
      exceptionNodeIds,
      residualGroupIds,
    },
  );

  return {
    doc: nextDoc,
    appliedKeys: keysToApply,
    skippedKeys,
    createdNodeIds: createdNodes.map((node) => node.id),
    createdEdgeIds: createdEdges.map((edge) => edge.id),
  };
}

export function applyTemplatesToProject(
  doc: WorkspaceDocument,
  projectId: string,
  options: TemplateSelectionOptions | TemplateKey[],
): TemplateApplicationResult {
  const project = doc.projects.find((item) => item.id === projectId);
  const targetSheetId =
    project?.sheet_ids.find((id) =>
      doc.sheets.some((sheet) => sheet.id === id),
    ) ?? doc.sheets.find((sheet) => sheet.project_id === projectId)?.id;
  if (!targetSheetId) {
    return {
      doc,
      appliedKeys: [],
      skippedKeys: Array.isArray(options)
        ? options
        : selectedTemplateKeys(options),
      createdNodeIds: [],
      createdEdgeIds: [],
    };
  }
  return applyTemplatesToSheet(doc, targetSheetId, options);
}

export function createProjectWithOptionalSheet(input: {
  title: string;
  description?: string;
  tags?: string[];
  createInitialSheet: boolean;
  templateOptions: TemplateSelectionOptions;
}): { project: Project; sheet?: Sheet } {
  const sheetId = input.createInitialSheet
    ? `sheet_${cryptoSafeId()}`
    : undefined;
  const project = createProject({
    id: `project_${cryptoSafeId()}`,
    title: input.title,
    description: input.description,
    tags: input.tags,
    default_sheet_template_options: input.templateOptions,
    sheet_ids: sheetId ? [sheetId] : [],
  });
  const sheet = sheetId
    ? createSheet({
        id: sheetId,
        project_id: project.id,
        title: `${input.title} Sheet`,
        description: input.description,
        tags: input.tags,
      })
    : undefined;
  return { project, sheet };
}

function templateSpecificNodes(
  sheetId: string,
  key: TemplateKey,
  baseTags: string[],
): KnowledgeNode[] {
  const root = (title: string, summary: string, y = 80) =>
    createKnowledgeNode("concept", {
      id: templateNodeId(sheetId, key, "root"),
      title,
      summary,
      description:
        "Reading Probability Coreの初期材料。推奨打牌、push/fold、EV判定、最終アクションは含めない。",
      tags: unique([...baseTags, "template_root"]),
      confidence: 0.6,
      source_type: "theory",
      position: { x: 420, y },
    });

  if (key === "tile_efficiency") {
    return [
      root(
        "牌理テンプレート",
        "形、受け入れ、待ち変化を4軸へ投影する初期材料。",
      ),
      createKnowledgeNode("observation_candidate", {
        id: templateNodeId(sheetId, key, "good_shape_shift"),
        title: "良形変化候補",
        summary: "良形化、くっつき、変化残りを待ち・形の良さへ投影する。",
        tags: unique([...baseTags, "wait_shape", "shape_change"]),
        confidence: 0.58,
        position: { x: 720, y: 120 },
      }),
      createKnowledgeNode("hypothesis", {
        id: templateNodeId(sheetId, key, "tenpai_speed"),
        title: "聴牌速度仮説",
        summary: "受け入れ枚数やシャンテン戻しを進行度・聴牌率へ投影する。",
        tags: unique([...baseTags, "progress", "ukeire"]),
        confidence: 0.56,
        position: { x: 720, y: 300 },
      }),
      createKnowledgeNode("ambiguity_marker", {
        id: templateNodeId(sheetId, key, "unknown_buffer"),
        title: "形変化unknown buffer",
        summary: "形の伸びが読み切れない部分をmixed/unknownとして残す。",
        tags: unique([...baseTags, "unknown", "residual"]),
        confidence: 0.45,
        position: { x: 720, y: 480 },
      }),
    ];
  }

  if (key === "tile_count") {
    return [
      root(
        "枚数テンプレート",
        "見え枚数、山残り、壁、ワンチャンスを初期材料にする。",
      ),
      createKnowledgeNode("observation_candidate", {
        id: templateNodeId(sheetId, key, "visible_count"),
        title: "見え枚数観測",
        summary: "見え枚数と残り枚数を待ち・形、進行度へ投影する。",
        tags: unique([...baseTags, "visible_tiles", "remaining_tiles"]),
        confidence: 0.6,
        position: { x: 720, y: 120 },
      }),
      createKnowledgeNode("hypothesis", {
        id: templateNodeId(sheetId, key, "wall_one_chance"),
        title: "壁/ワンチャンス仮説",
        summary: "壁、ワンチャンス、ノーチャンスを例外候補として残す。",
        tags: unique([...baseTags, "wall", "one_chance", "no_chance"]),
        confidence: 0.54,
        position: { x: 720, y: 300 },
      }),
      createKnowledgeNode("exception", {
        id: templateNodeId(sheetId, key, "count_exception"),
        title: "枚数読み例外候補",
        summary: "見え枚数だけで確定しない例外をException Libraryへ残す。",
        tags: unique([...baseTags, "exception", "residual"]),
        confidence: 0.48,
        pruning_hints: ["override_only"],
        position: { x: 720, y: 480 },
      }),
    ];
  }

  if (key === "yaku") {
    return [
      root("手役テンプレート", "手役、打点、ドラ、役牌バックを4軸へ投影する。"),
      createKnowledgeNode("hypothesis", {
        id: templateNodeId(sheetId, key, "value_tail"),
        title: "高打点尾部仮説",
        summary: "低頻度でも打点が大きい候補を打点軸に残す。",
        tags: unique([...baseTags, "value", "tail"]),
        confidence: 0.56,
        position: { x: 720, y: 120 },
      }),
      createKnowledgeNode("hypothesis", {
        id: templateNodeId(sheetId, key, "yakuhai_back"),
        title: "役牌バック仮説",
        summary: "副露手役と速度を進行度・打点へ同時に投影する。",
        tags: unique([...baseTags, "yakuhai", "call_intent"]),
        confidence: 0.55,
        position: { x: 720, y: 300 },
      }),
      createKnowledgeNode("exception", {
        id: templateNodeId(sheetId, key, "yaku_exception"),
        title: "染め/ドラ例外候補",
        summary: "染め、ドラ絡み、赤受けを過小評価しないための例外候補。",
        tags: unique([...baseTags, "exception", "dora", "flush"]),
        confidence: 0.5,
        pruning_hints: ["override_only"],
        position: { x: 720, y: 480 },
      }),
    ];
  }

  return [
    root(
      "抽象的な読みテンプレート",
      "意図、傾向、場況、他家介入、unknownを初期材料にする。",
    ),
    createKnowledgeNode("hypothesis", {
      id: templateNodeId(sheetId, key, "call_intent"),
      title: "副露意図仮説",
      summary: "速度、副露目的、役バック、ブロックをmixed込みで投影する。",
      tags: unique([...baseTags, "call_intent", "mixed"]),
      confidence: 0.52,
      position: { x: 720, y: 120 },
    }),
    createKnowledgeNode("probability_aggregate", {
      id: templateNodeId(sheetId, key, "side_intervention"),
      title: "他家介入仮説",
      summary: "他家和了、放銃、流局接近などの介入で読みを揺らす。",
      tags: unique([...baseTags, "table_dynamics", "residual"]),
      confidence: 0.5,
      position: { x: 720, y: 300 },
    }),
    createKnowledgeNode("ambiguity_marker", {
      id: templateNodeId(sheetId, key, "unknown_residual"),
      title: "未配分unknown候補",
      summary: "mixed/unknownの軸をhard pruneせずdownweight/keep top-kへ残す。",
      tags: unique([...baseTags, "unknown", "keep_top_k", "reasoning_lab"]),
      confidence: 0.44,
      pruning_hints: ["must_keep_top_k"],
      position: { x: 720, y: 480 },
    }),
  ];
}

function edgeSpecs(sheetId: string, key: TemplateKey) {
  const node = (name: string) => templateNodeId(sheetId, key, name);
  const axis = (name: string) => axisId(sheetId, name);
  if (key === "tile_efficiency") {
    return [
      spec(
        node("good_shape_shift"),
        axis("wait_shape_quality_axis"),
        "+",
        0.72,
        0.66,
      ),
      spec(node("tenpai_speed"), axis("progress_tenpai_axis"), "+", 0.68, 0.62),
      spec(
        node("unknown_buffer"),
        axis("wait_shape_quality_axis"),
        "unknown",
        0.35,
        0.38,
      ),
    ];
  }
  if (key === "tile_count") {
    return [
      spec(
        node("visible_count"),
        axis("wait_shape_quality_axis"),
        "+",
        0.62,
        0.62,
      ),
      spec(
        node("visible_count"),
        axis("progress_tenpai_axis"),
        "mixed",
        0.44,
        0.55,
      ),
      spec(
        node("wall_one_chance"),
        axis("score_situation_threshold_axis"),
        "mixed",
        0.38,
        0.46,
      ),
    ];
  }
  if (key === "yaku") {
    return [
      spec(node("value_tail"), axis("value_axis"), "+", 0.78, 0.64),
      spec(node("yakuhai_back"), axis("progress_tenpai_axis"), "+", 0.48, 0.56),
      spec(
        node("yaku_exception"),
        axis("score_situation_threshold_axis"),
        "mixed",
        0.52,
        0.46,
      ),
    ];
  }
  return [
    spec(node("call_intent"), axis("progress_tenpai_axis"), "mixed", 0.58, 0.5),
    spec(
      node("side_intervention"),
      axis("score_situation_threshold_axis"),
      "mixed",
      0.56,
      0.48,
    ),
    spec(
      node("unknown_residual"),
      axis("wait_shape_quality_axis"),
      "unknown",
      0.36,
      0.4,
    ),
    spec(node("unknown_residual"), axis("value_axis"), "unknown", 0.32, 0.38),
  ];
}

function spec(
  source: string,
  target: string,
  sign: KnowledgeEdge["sign"],
  magnitude: number,
  confidence: number,
) {
  return { source, target, sign, magnitude, confidence };
}

function axisId(sheetId: string, axis: string): string {
  return `tpl_${sheetId}_${axis}`;
}

function templateNodeId(
  sheetId: string,
  key: TemplateKey,
  name: string,
): string {
  return `tpl_${sheetId}_${key}_${name}`;
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function uniqueTemplateKeys(values: TemplateKey[]): TemplateKey[] {
  return selectedTemplateKeys(templateOptionsFromKeys(values));
}

function cryptoSafeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}_${Math.random().toString(36).slice(2)}`;
}
