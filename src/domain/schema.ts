import { z } from "zod";

export const WORKSPACE_SCHEMA_VERSION = "mahjong-knowledge-map.workspace.v4";
export const LEGACY_WORKSPACE_SCHEMA_VERSIONS = [
  "mahjong-knowledge-map.workspace.v1",
  "mahjong-knowledge-map.workspace.v2",
  "mahjong-knowledge-map.workspace.v3",
] as const;
export const PRUNING_EXPORT_SCHEMA_VERSION = "pruning-ui.subgraph.v4";

export const nodeTypes = [
  "concept",
  "signal",
  "condition",
  "metric",
  "heuristic",
  "exception",
  "scenario",
  "action",
  "evidence",
  "question",
  "hypothesis",
  "branch",
  "choice_group",
  "observation",
  "weight_modifier",
  "lock_controller",
  "distribution_assumption",
  "probability_aggregate",
  "observation_candidate",
  "ambiguity_marker",
  "pruning_suggestion",
  "weight_adjustment_suggestion",
] as const;

export const edgeTypes = [
  "supports",
  "contradicts",
  "refines",
  "triggers",
  "overrides",
  "applies_to",
  "measured_by",
  "exported_as",
  "influences",
  "resolves",
  "weakens",
  "strengthens",
  "disambiguates",
  "blocks_pruning",
  "enables_pruning",
] as const;

export const sourceTypes = [
  "idea",
  "note",
  "replay",
  "stats",
  "theory",
] as const;

export const caseLanes = [
  "observation",
  "hypothesis",
  "condition",
  "decision",
] as const;

export const ruleCategories = [
  "hard_gate",
  "soft_score",
  "override",
  "fallback",
  "mixed",
] as const;

export const pruningHints = [
  "can_prune",
  "must_keep_top_k",
  "hard_gate_candidate",
  "score_only",
  "override_only",
] as const;

export const probabilityRoles = [
  "none",
  "prior",
  "posterior",
  "control",
] as const;

export const lockModes = [
  "none",
  "hard",
  "soft",
  "keep_top_k",
  "freeze_ratio",
  "hard_lock",
  "soft_lock",
  "freeze_concentration_band",
] as const;

export const distributionFamilies = [
  "categorical",
  "interval",
  "bimodal",
  "multimodal",
  "asymmetric_tail",
  "mixture",
] as const;

export const propagationPolicies = [
  "none",
  "normalize_siblings",
  "multiply_downstream",
  "gated",
] as const;

export const relationLayers = [
  "semantic",
  "probabilistic",
  "influence",
] as const;

export const influenceSigns = ["+", "-", "mixed", "unknown"] as const;

export const combinationModes = [
  "additive",
  "multiplicative",
  "override",
] as const;

export const pruningActionTypes = [
  "hard_prune",
  "soft_downweight",
  "hard_lock",
  "soft_lock",
  "keep_top_k",
  "freeze_ratio",
  "freeze_concentration_band",
] as const;

export const readingChainStepTypes = [
  "observation",
  "hypothesis_split",
  "lock",
  "pruning",
  "weight_update",
  "direction_update",
  "observation_request",
  "fallback",
  "compare",
] as const;

export const averagingSafetyLabels = ["safe", "caution", "unsafe"] as const;

export const templateKeys = [
  "tile_efficiency",
  "tile_count",
  "yaku",
  "abstract_reading",
] as const;

export const workspaceScopeModes = ["sheet", "project", "workspace"] as const;

export const nodeTypeSchema = z.enum(nodeTypes);
export const edgeTypeSchema = z.enum(edgeTypes);
export const sourceTypeSchema = z.enum(sourceTypes);
export const caseLaneSchema = z.enum(caseLanes);
export const ruleCategorySchema = z.enum(ruleCategories);
export const pruningHintSchema = z.enum(pruningHints);
export const probabilityRoleSchema = z.enum(probabilityRoles);
export const lockModeSchema = z.enum(lockModes);
export const distributionFamilySchema = z.enum(distributionFamilies);
export const propagationPolicySchema = z.enum(propagationPolicies);
export const relationLayerSchema = z.enum(relationLayers);
export const influenceSignSchema = z.enum(influenceSigns);
export const combinationModeSchema = z.enum(combinationModes);
export const pruningActionTypeSchema = z.enum(pruningActionTypes);
export const readingChainStepTypeSchema = z.enum(readingChainStepTypes);
export const averagingSafetyLabelSchema = z.enum(averagingSafetyLabels);
export const templateKeySchema = z.enum(templateKeys);
export const workspaceScopeModeSchema = z.enum(workspaceScopeModes);

export const templateSelectionOptionsSchema = z.object({
  tile_efficiency: z.boolean().default(true),
  tile_count: z.boolean().default(true),
  yaku: z.boolean().default(true),
  abstract_reading: z.boolean().default(true),
});

export const globalSettingsSchema = z.object({
  project_creation_defaults: templateSelectionOptionsSchema.default({
    tile_efficiency: true,
    tile_count: true,
    yaku: true,
    abstract_reading: true,
  }),
  sheet_creation_defaults: templateSelectionOptionsSchema.default({
    tile_efficiency: true,
    tile_count: true,
    yaku: true,
    abstract_reading: true,
  }),
  create_empty_project_by_default: z.boolean().default(false),
  create_empty_sheet_by_default: z.boolean().default(false),
});

export const defaultTemplateSelectionOptions = {
  tile_efficiency: true,
  tile_count: true,
  yaku: true,
  abstract_reading: true,
} satisfies TemplateSelectionOptions;

export const defaultGlobalSettings = {
  project_creation_defaults: defaultTemplateSelectionOptions,
  sheet_creation_defaults: defaultTemplateSelectionOptions,
  create_empty_project_by_default: false,
  create_empty_sheet_by_default: false,
} satisfies GlobalSettings;

export const xyPositionSchema = z.object({
  x: z.number(),
  y: z.number(),
});

export const thresholdSchema = z.object({
  name: z.string(),
  value: z.string(),
  note: z.string().default(""),
});

export const contextGateSchema = z.union([z.string(), z.array(z.string())]);

export const knowledgeNodeSchema = z.object({
  id: z.string().min(1),
  type: nodeTypeSchema,
  title: z.string().min(1),
  summary: z.string().default(""),
  description: z.string().default(""),
  tags: z.array(z.string()).default([]),
  confidence: z.number().min(0).max(1).default(0.5),
  applicability: z.array(z.string()).default([]),
  stage: z.string().default("unspecified"),
  actor: z.string().default("全員"),
  source_type: sourceTypeSchema.default("idea"),
  reproducibility: z.number().min(0).max(1).default(0.5),
  notes: z.string().default(""),
  formulas: z.array(z.string()).default([]),
  thresholds: z.array(thresholdSchema).default([]),
  related_rule_ids: z.array(z.string()).default([]),
  pruning_hints: z.array(pruningHintSchema).default([]),
  reading_utility_ids: z.array(z.string()).default([]),
  probability_role: probabilityRoleSchema.default("none"),
  choice_group_id: z.string().optional(),
  concentration_group_id: z.string().optional(),
  base_weight: z.number().optional(),
  dynamic_weight: z.number().optional(),
  posterior_probability: z.number().min(0).max(1).optional(),
  prior_probability: z.number().min(0).max(1).optional(),
  lock_mode: lockModeSchema.default("none"),
  lock_value: z.number().optional(),
  lock_rationale: z.string().default(""),
  distribution_family: distributionFamilySchema.optional(),
  propagation_policy: propagationPolicySchema.default("none"),
  hysteresis_band: z.number().min(0).max(1).optional(),
  pruning_priority: z.number().optional(),
  resolves_targets: z.array(z.string()).default([]),
  expected_sign_gain: z.number().optional(),
  expected_weight_gain: z.number().optional(),
  expected_margin_gain: z.number().optional(),
  pruning_safety_change: z.number().optional(),
  observation_cost: z.number().optional(),
  timeliness: z.number().min(0).max(1).optional(),
  position: xyPositionSchema,
  group_id: z.string().optional(),
  is_group: z.boolean().default(false),
  collapsed: z.boolean().default(false),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const knowledgeEdgeSchema = z.object({
  id: z.string().min(1),
  source: z.string().min(1),
  target: z.string().min(1),
  type: edgeTypeSchema,
  label: z.string().default(""),
  notes: z.string().default(""),
  relation_layer: relationLayerSchema.default("semantic"),
  conditional_weight: z.number().optional(),
  transition_rule: z.string().optional(),
  propagate_probability: z.boolean().default(false),
  edge_group_id: z.string().optional(),
  sign: influenceSignSchema.default("unknown"),
  magnitude: z.number().min(0).default(0),
  confidence: z.number().min(0).max(1).default(0.5),
  context_gate: contextGateSchema.optional(),
  combination_mode: combinationModeSchema.default("additive"),
  ambiguity_group_id: z.string().optional(),
  evidence_refs: z.array(z.string()).default([]),
  note: z.string().optional(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const scoreTermSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  weight: z.number().default(0),
  note: z.string().default(""),
});

export const ruleSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  category: ruleCategorySchema,
  target_node_ids: z.array(z.string()).default([]),
  hard_gates: z.array(z.string()).default([]),
  soft_score_terms: z.array(scoreTermSchema).default([]),
  override_conditions: z.array(z.string()).default([]),
  fallback_behavior: z.string().default(""),
  note: z.string().default(""),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const scoresSchema = z.object({
  east: z.number().default(25000),
  south: z.number().default(25000),
  west: z.number().default(25000),
  north: z.number().default(25000),
});

export const caseSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  round: z.string().default("東1局"),
  honba: z.number().int().min(0).default(0),
  riichi_sticks: z.number().int().min(0).default(0),
  turn: z.number().int().min(1).max(18).default(6),
  scores: scoresSchema,
  dealer: z.string().default("east"),
  seat: z.string().default("south"),
  riichi_status: z.string().default("なし"),
  melds_summary: z.string().default(""),
  discard_notes: z.string().default(""),
  observations: z.array(z.string()).default([]),
  hypotheses: z.array(z.string()).default([]),
  attached_node_ids: z.array(z.string()).default([]),
  selected_rule_ids: z.array(z.string()).default([]),
  lane_assignments: z.record(z.string(), caseLaneSchema).default({}),
  top_k_hypotheses: z.number().int().min(1).max(8).default(3),
  decision_note: z.string().default(""),
  review_note: z.string().default(""),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const savedViewSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  search: z.string().default(""),
  tag_filter: z.array(z.string()).default([]),
  node_type_filter: z.array(nodeTypeSchema).default([]),
  created_at: z.string().datetime(),
});

export const projectSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().default(""),
  tags: z.array(z.string()).default([]),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  default_sheet_template_options: templateSelectionOptionsSchema.default(
    defaultTemplateSelectionOptions,
  ),
  sheet_ids: z.array(z.string()).default([]),
  archived: z.boolean().default(false),
});

export const sheetSchema = z.object({
  id: z.string().min(1),
  project_id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().default(""),
  tags: z.array(z.string()).default([]),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  node_ids: z.array(z.string()).default([]),
  edge_ids: z.array(z.string()).default([]),
  case_ids: z.array(z.string()).default([]),
  rule_ids: z.array(z.string()).default([]),
  saved_view_ids: z.array(z.string()).default([]),
  reading_drawer_item_ids: z.array(z.string()).default([]),
  exception_node_ids: z.array(z.string()).default([]),
  residual_group_ids: z.array(z.string()).default([]),
  template_source: z
    .object({
      created_from_template: z.boolean().default(false),
      enabled_template_keys: z.array(templateKeySchema).default([]),
    })
    .optional(),
  archived: z.boolean().default(false),
});

export const concentrationMetricsSchema = z.object({
  entropy: z.number(),
  top_k_mass: z.number(),
  peak_mass: z.number(),
  hhi: z.number(),
  dispersion_note: z.string().default(""),
});

export const pruningActionSchema = z.object({
  id: z.string().min(1),
  action_type: pruningActionTypeSchema,
  target_ids: z.array(z.string()).default([]),
  strength: z.number().min(0).default(1),
  rationale: z.string().default(""),
  created_at: z.string().datetime(),
});

export const impactSummarySchema = z.object({
  before_snapshot_id: z.string().min(1),
  after_snapshot_id: z.string().min(1),
  delta_mass: z.number(),
  changed_node_count: z.number().int().min(0),
  dominant_branch_change: z.string().default(""),
  ambiguity_change: z.number(),
  margin_change: z.number(),
  vector_delta_by_metric: z.record(z.string(), z.number()).default({}),
  notes: z.string().default(""),
});

export const readingUtilitySchema = z.object({
  target_id: z.string().min(1),
  selective_pruning_ratio: z.number().min(0).max(1),
  global_impact_score: z.number().min(0),
  concentration_shift: z.number(),
  residual_mass_before: z.number().min(0).max(1).default(0),
  residual_mass_after: z.number().min(0).max(1).default(0),
  residual_reduction: z.number().default(0),
  exception_candidates_added: z.number().int().min(0).default(0),
  unknown_buffer_remaining: z.number().min(0).max(1).default(0),
  projected_margin_gain: z.number(),
  ambiguity_reduction: z.number(),
  resolution_gain: z.number().default(0),
  cost_estimate: z.number().min(0),
  utility_score: z.number(),
});

export const readingChainStepSchema = z.object({
  id: z.string().min(1),
  step_type: readingChainStepTypeSchema,
  source_ids: z.array(z.string()).default([]),
  target_ids: z.array(z.string()).default([]),
  before_snapshot_id: z.string().default(""),
  after_snapshot_id: z.string().default(""),
  rationale: z.string().default(""),
  note: z.string().default(""),
});

export const readingChainSchema = z.object({
  id: z.string().min(1),
  case_id: z.string().min(1),
  steps: z.array(readingChainStepSchema).default([]),
  summary: z.string().default(""),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const averagingSafetySchema = z.object({
  target_id: z.string().min(1),
  score: z.number().min(0).max(1),
  label: averagingSafetyLabelSchema,
  reasons: z.array(z.string()).default([]),
});

export const teachingLogSchema = z.object({
  case_id: z.string().min(1),
  action_id: z.string().min(1),
  explanation_short: z.string().default(""),
  explanation_full: z.string().default(""),
  key_terms: z.array(z.string()).default([]),
  created_at: z.string().datetime(),
});

export const workspaceDocumentSchema = z.object({
  schema_version: z.literal(WORKSPACE_SCHEMA_VERSION),
  projects: z.array(projectSchema).default([]),
  sheets: z.array(sheetSchema).default([]),
  active_project_id: z.string().optional(),
  active_sheet_id: z.string().optional(),
  global_settings: globalSettingsSchema.default(defaultGlobalSettings),
  nodes: z.array(knowledgeNodeSchema),
  edges: z.array(knowledgeEdgeSchema),
  cases: z.array(caseSchema),
  rules: z.array(ruleSchema),
  saved_views: z.array(savedViewSchema).default([]),
  pruning_actions: z.array(pruningActionSchema).default([]),
  impact_summaries: z.array(impactSummarySchema).default([]),
  reading_utilities: z.array(readingUtilitySchema).default([]),
  reading_chains: z.array(readingChainSchema).default([]),
  averaging_safety: z.array(averagingSafetySchema).default([]),
  teaching_logs: z.array(teachingLogSchema).default([]),
  active_case_id: z.string().optional(),
  updated_at: z.string().datetime(),
});

export const pruningExportSchema = z.object({
  schema_version: z.literal(PRUNING_EXPORT_SCHEMA_VERSION),
  exported_at: z.string().datetime(),
  source_workspace_schema_version: z.literal(WORKSPACE_SCHEMA_VERSION),
  selected_nodes: z.array(knowledgeNodeSchema),
  selected_edges: z.array(knowledgeEdgeSchema),
  node_metadata: z.record(
    z.string(),
    z.object({
      type: nodeTypeSchema,
      title: z.string(),
      tags: z.array(z.string()),
      confidence: z.number(),
      applicability: z.array(z.string()),
      pruning_hints: z.array(pruningHintSchema),
      probability_role: probabilityRoleSchema,
      choice_group_id: z.string().optional(),
      posterior_probability: z.number().optional(),
      prior_probability: z.number().optional(),
      lock_mode: lockModeSchema,
      distribution_family: distributionFamilySchema.optional(),
    }),
  ),
  rules: z.array(ruleSchema),
  pruning_hints: z.record(z.string(), z.array(pruningHintSchema)),
  weight_placeholders: z.record(
    z.string(),
    z.object({
      initial_weight: z.number(),
      rationale: z.string(),
      locked: z.boolean(),
    }),
  ),
  inference_subgraph: z.object({
    nodes: z.array(knowledgeNodeSchema),
    edges: z.array(knowledgeEdgeSchema),
  }),
  choice_groups: z.array(
    z.object({
      id: z.string(),
      node_ids: z.array(z.string()),
      normalized_total: z.number(),
      distribution_family: distributionFamilySchema.optional(),
    }),
  ),
  locks: z.record(
    z.string(),
    z.object({
      lock_mode: lockModeSchema,
      lock_value: z.number().optional(),
    }),
  ),
  weights: z.record(
    z.string(),
    z.object({
      base_weight: z.number().optional(),
      dynamic_weight: z.number().optional(),
      prior_probability: z.number().optional(),
      posterior_probability: z.number().optional(),
    }),
  ),
  distributions: z.record(
    z.string(),
    z.object({
      distribution_family: distributionFamilySchema.optional(),
      hysteresis_band: z.number().optional(),
      pruning_priority: z.number().optional(),
    }),
  ),
  propagation_order: z.array(z.string()),
  frozen_nodes: z.array(z.string()),
  top_k_constraints: z.record(z.string(), z.number()),
  reasoning_lab: z.object({
    concentration_metrics: z.record(z.string(), concentrationMetricsSchema),
    pruning_actions: z.array(pruningActionSchema),
    impact_summaries: z.array(impactSummarySchema),
    reading_utilities: z.array(readingUtilitySchema),
    reading_chains: z.array(readingChainSchema),
    averaging_safety: z.array(averagingSafetySchema),
    teaching_logs: z.array(teachingLogSchema),
  }),
  influence_model: z.object({
    metrics: z.array(knowledgeNodeSchema),
    influence_edges: z.array(knowledgeEdgeSchema),
    ambiguity_groups: z.array(
      z.object({
        id: z.string(),
        metric_id: z.string(),
        influence_edge_ids: z.array(z.string()),
        status: z.enum(["mixed", "unknown", "conflicting"]),
        unresolved_score: z.number(),
      }),
    ),
    observation_candidates: z.array(knowledgeNodeSchema),
    pruning_suggestions: z.array(
      z.object({
        branch_id: z.string(),
        action: z.enum(["prune", "downweight", "keep", "observe"]),
        confidence: z.number(),
        reason: z.string(),
      }),
    ),
  }),
});

export type NodeType = (typeof nodeTypes)[number];
export type EdgeType = (typeof edgeTypes)[number];
export type SourceType = (typeof sourceTypes)[number];
export type CaseLane = (typeof caseLanes)[number];
export type RuleCategory = (typeof ruleCategories)[number];
export type PruningHint = (typeof pruningHints)[number];
export type ProbabilityRole = (typeof probabilityRoles)[number];
export type LockMode = (typeof lockModes)[number];
export type DistributionFamily = (typeof distributionFamilies)[number];
export type PropagationPolicy = (typeof propagationPolicies)[number];
export type RelationLayer = (typeof relationLayers)[number];
export type InfluenceSign = (typeof influenceSigns)[number];
export type CombinationMode = (typeof combinationModes)[number];
export type PruningActionType = (typeof pruningActionTypes)[number];
export type ReadingChainStepType = (typeof readingChainStepTypes)[number];
export type AveragingSafetyLabel = (typeof averagingSafetyLabels)[number];
export type TemplateKey = (typeof templateKeys)[number];
export type WorkspaceScopeMode = (typeof workspaceScopeModes)[number];
export type TemplateSelectionOptions = z.infer<
  typeof templateSelectionOptionsSchema
>;
export type GlobalSettings = z.infer<typeof globalSettingsSchema>;
export type KnowledgeNode = z.infer<typeof knowledgeNodeSchema>;
export type KnowledgeEdge = z.infer<typeof knowledgeEdgeSchema>;
export type RuleDefinition = z.infer<typeof ruleSchema>;
export type CaseData = z.infer<typeof caseSchema>;
export type SavedView = z.infer<typeof savedViewSchema>;
export type Project = z.infer<typeof projectSchema>;
export type Sheet = z.infer<typeof sheetSchema>;
export type ConcentrationMetrics = z.infer<typeof concentrationMetricsSchema>;
export type PruningAction = z.infer<typeof pruningActionSchema>;
export type ImpactSummary = z.infer<typeof impactSummarySchema>;
export type ReadingUtility = z.infer<typeof readingUtilitySchema>;
export type ReadingChainStep = z.infer<typeof readingChainStepSchema>;
export type ReadingChain = z.infer<typeof readingChainSchema>;
export type AveragingSafety = z.infer<typeof averagingSafetySchema>;
export type TeachingLog = z.infer<typeof teachingLogSchema>;
export type WorkspaceDocument = z.infer<typeof workspaceDocumentSchema>;
export type PruningExport = z.infer<typeof pruningExportSchema>;

export function normalizeWorkspaceDocument(input: unknown): WorkspaceDocument {
  const raw =
    input &&
    typeof input === "object" &&
    "schema_version" in input &&
    LEGACY_WORKSPACE_SCHEMA_VERSIONS.includes(
      (input as { schema_version?: string }).schema_version as never,
    )
      ? {
          ...(input as Record<string, unknown>),
          schema_version: WORKSPACE_SCHEMA_VERSION,
        }
      : input;
  return normalizeWorkspaceScopes(workspaceDocumentSchema.parse(raw));
}

export function normalizeWorkspaceScopes(
  doc: WorkspaceDocument,
): WorkspaceDocument {
  const now = new Date().toISOString();
  const hasProjects = doc.projects.length > 0;
  const hasSheets = doc.sheets.length > 0;
  const defaultProjectId = doc.active_project_id ?? "project_default";
  const defaultSheetId = doc.active_sheet_id ?? "sheet_default";
  const projects = hasProjects
    ? doc.projects
    : [
        projectSchema.parse({
          id: defaultProjectId,
          title: "Default Project",
          description:
            "既存workspaceを後方互換のために移行したデフォルトProject。",
          tags: ["default_project", "migration"],
          created_at: doc.updated_at ?? now,
          updated_at: doc.updated_at ?? now,
          default_sheet_template_options:
            doc.global_settings.sheet_creation_defaults,
          sheet_ids: [defaultSheetId],
        }),
      ];
  const sheets = hasSheets
    ? doc.sheets
    : [
        sheetSchema.parse({
          id: defaultSheetId,
          project_id: projects[0]?.id ?? defaultProjectId,
          title: "Default Sheet",
          description:
            "既存nodes / edges / cases / rules / saved viewsを移行したデフォルトSheet。",
          tags: ["default_sheet", "migration"],
          created_at: doc.updated_at ?? now,
          updated_at: doc.updated_at ?? now,
          node_ids: doc.nodes.map((node) => node.id),
          edge_ids: doc.edges.map((edge) => edge.id),
          case_ids: doc.cases.map((caseItem) => caseItem.id),
          rule_ids: doc.rules.map((rule) => rule.id),
          saved_view_ids: doc.saved_views.map((view) => view.id),
          exception_node_ids: doc.nodes
            .filter(
              (node) =>
                node.type === "exception" || node.tags.includes("exception"),
            )
            .map((node) => node.id),
          residual_group_ids: Array.from(
            new Set(
              doc.nodes
                .map((node) => node.choice_group_id)
                .filter((id): id is string => Boolean(id)),
            ),
          ),
          template_source: {
            created_from_template: false,
            enabled_template_keys: [],
          },
        }),
      ];

  const projectIds = new Set(projects.map((project) => project.id));
  const activeProjectId =
    doc.active_project_id && projectIds.has(doc.active_project_id)
      ? doc.active_project_id
      : projects[0]?.id;
  const sheetsWithValidProject = sheets.map((sheet) => ({
    ...sheet,
    project_id: projectIds.has(sheet.project_id)
      ? sheet.project_id
      : (activeProjectId ?? projects[0]?.id ?? defaultProjectId),
  }));
  const sheetIds = new Set(sheetsWithValidProject.map((sheet) => sheet.id));
  const activeSheetId =
    doc.active_sheet_id && sheetIds.has(doc.active_sheet_id)
      ? doc.active_sheet_id
      : activeProjectId
        ? sheetsWithValidProject.find(
            (sheet) => sheet.project_id === activeProjectId,
          )?.id
        : sheetsWithValidProject[0]?.id;
  const normalizedSheets =
    sheetsWithValidProject.length > 0
      ? assignOrphansToSheet(doc, sheetsWithValidProject, activeSheetId)
      : sheetsWithValidProject;
  const normalizedProjects = projects.map((project) => ({
    ...project,
    sheet_ids: unique([
      ...project.sheet_ids.filter((id) => sheetIds.has(id)),
      ...normalizedSheets
        .filter((sheet) => sheet.project_id === project.id)
        .map((sheet) => sheet.id),
    ]),
  }));

  return workspaceDocumentSchema.parse({
    ...doc,
    projects: normalizedProjects,
    sheets: normalizedSheets,
    active_project_id: activeProjectId,
    active_sheet_id: activeSheetId,
    global_settings: globalSettingsSchema.parse(doc.global_settings),
  });
}

function assignOrphansToSheet(
  doc: WorkspaceDocument,
  sheets: Sheet[],
  targetSheetId?: string,
): Sheet[] {
  if (!targetSheetId) return sheets;
  const sheet = sheets.find((item) => item.id === targetSheetId) ?? sheets[0];
  if (!sheet) return sheets;
  const assignedNodeIds = new Set(sheets.flatMap((item) => item.node_ids));
  const assignedEdgeIds = new Set(sheets.flatMap((item) => item.edge_ids));
  const assignedCaseIds = new Set(sheets.flatMap((item) => item.case_ids));
  const assignedRuleIds = new Set(sheets.flatMap((item) => item.rule_ids));
  const assignedViewIds = new Set(
    sheets.flatMap((item) => item.saved_view_ids),
  );
  const orphanNodeIds = doc.nodes
    .map((node) => node.id)
    .filter((id) => !assignedNodeIds.has(id));
  const orphanEdgeIds = doc.edges
    .map((edge) => edge.id)
    .filter((id) => !assignedEdgeIds.has(id));
  const orphanCaseIds = doc.cases
    .map((caseItem) => caseItem.id)
    .filter((id) => !assignedCaseIds.has(id));
  const orphanRuleIds = doc.rules
    .map((rule) => rule.id)
    .filter((id) => !assignedRuleIds.has(id));
  const orphanViewIds = doc.saved_views
    .map((view) => view.id)
    .filter((id) => !assignedViewIds.has(id));

  if (
    orphanNodeIds.length +
      orphanEdgeIds.length +
      orphanCaseIds.length +
      orphanRuleIds.length +
      orphanViewIds.length ===
    0
  ) {
    return sheets;
  }

  return sheets.map((item) =>
    item.id === sheet.id
      ? {
          ...item,
          node_ids: unique([...item.node_ids, ...orphanNodeIds]),
          edge_ids: unique([...item.edge_ids, ...orphanEdgeIds]),
          case_ids: unique([...item.case_ids, ...orphanCaseIds]),
          rule_ids: unique([...item.rule_ids, ...orphanRuleIds]),
          saved_view_ids: unique([...item.saved_view_ids, ...orphanViewIds]),
        }
      : item,
  );
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

export function selectedTemplateKeys(
  options: TemplateSelectionOptions,
): TemplateKey[] {
  return templateKeys.filter((key) => options[key]);
}

export function templateOptionsFromKeys(
  keys: readonly TemplateKey[],
): TemplateSelectionOptions {
  const keySet = new Set(keys);
  return {
    tile_efficiency: keySet.has("tile_efficiency"),
    tile_count: keySet.has("tile_count"),
    yaku: keySet.has("yaku"),
    abstract_reading: keySet.has("abstract_reading"),
  };
}

export function emptyTemplateSelectionOptions(): TemplateSelectionOptions {
  return {
    tile_efficiency: false,
    tile_count: false,
    yaku: false,
    abstract_reading: false,
  };
}

export function allTemplateSelectionOptions(): TemplateSelectionOptions {
  return {
    tile_efficiency: true,
    tile_count: true,
    yaku: true,
    abstract_reading: true,
  };
}

export function mergeTemplateSelectionOptions(
  options?: Partial<TemplateSelectionOptions>,
): TemplateSelectionOptions {
  return templateSelectionOptionsSchema.parse({
    ...defaultTemplateSelectionOptions,
    ...options,
  });
}
