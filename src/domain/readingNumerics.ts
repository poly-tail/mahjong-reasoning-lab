import {
  createId,
  createKnowledgeEdge,
  createKnowledgeNode,
  inferLaneFromNodeType,
  nowIso,
} from "./factory";
import { handValueRangeAxes } from "./rangetheory";
import {
  workspaceDocumentSchema,
  type CaseLane,
  type InfluenceSign,
  type KnowledgeNode,
  type LockMode,
  type PruningHint,
  type SourceType,
  type WorkspaceDocument,
} from "./schema";
import {
  buildResidualMassSummary,
  createExceptionCandidateNode,
  createResidualBucketNode,
  normalizeCandidates as normalizeResidualCandidates,
  type ResidualMassBucket,
  type ResidualMassPolicy,
} from "./residualMass";

export type ReadingType =
  | "observation"
  | "hypothesis"
  | "weight_modifier"
  | "scenario"
  | "pruning_suggestion";

export type AxisImpactDraft = {
  axis_id: (typeof handValueRangeAxes)[number]["id"];
  sign: InfluenceSign;
  magnitude: number;
  confidence: number;
  dynamic_weight?: number;
  note?: string;
  enabled?: boolean;
};

export type ChoiceCandidateDraft = {
  label: string;
  posterior_probability?: number;
  raw_probability?: number;
  normalized_probability?: number;
  base_weight?: number;
  dynamic_weight?: number;
  lock_mode?: LockMode;
  lock_value?: number;
  tags?: string[];
};

export type ReadingImpactDraft = {
  id: string;
  title: string;
  memo: string;
  source_type: SourceType;
  reading_type: ReadingType;
  confidence: number;
  attach_to_active_case: boolean;
  choice_group?: {
    id?: string;
    label: string;
    normalize: boolean;
    residual_policy?: ResidualMassPolicy;
    residual_buckets?: ResidualMassBucket[];
    candidates: ChoiceCandidateDraft[];
  };
  axis_impacts: AxisImpactDraft[];
  pruning_policy: {
    action:
      | "none"
      | "soft_downweight"
      | "hard_prune"
      | "keep_top_k"
      | "hard_lock"
      | "soft_lock"
      | "freeze_ratio";
    strength?: number;
    top_k?: number;
    lock_value?: number;
    rationale: string;
  };
  context_gate?: string;
};

export type ReadingNumericValidationWarning = {
  code: string;
  message: string;
  severity: "info" | "warning" | "danger";
};

export type ReadingNumericParseResult = {
  confidence?: number;
  prior_probability?: number;
  posterior_probability?: number;
  base_weight?: number;
  dynamic_weight?: number;
  lock_mode?: LockMode;
  lock_value?: number;
  axis_impacts?: AxisImpactDraft[];
  pruning_action?: ReadingImpactDraft["pruning_policy"]["action"];
  warnings: string[];
};

export type ReadingImpactPreview = {
  nextDoc: WorkspaceDocument;
  warnings: ReadingNumericValidationWarning[];
  createdNodeIds: string[];
  createdEdgeIds: string[];
};

const axisMetricTitles: Record<AxisImpactDraft["axis_id"], string> =
  Object.fromEntries(
    handValueRangeAxes.map((axis) => [axis.id, axis.label]),
  ) as Record<AxisImpactDraft["axis_id"], string>;

export function createDefaultReadingImpactDraft(): ReadingImpactDraft {
  return {
    id: createId("reading_draft"),
    title: "",
    memo: "",
    source_type: "idea",
    reading_type: "observation",
    confidence: 0.65,
    attach_to_active_case: true,
    axis_impacts: handValueRangeAxes.map((axis) => ({
      axis_id: axis.id,
      sign: "unknown",
      magnitude: 0,
      confidence: 0.55,
      dynamic_weight: 0,
      note: "",
      enabled: false,
    })),
    pruning_policy: {
      action: "none",
      strength: 0.2,
      top_k: 3,
      lock_value: 0.6,
      rationale: "",
    },
    context_gate: "",
  };
}

export function normalizePercentInput(
  value: string | number,
): number | undefined {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return undefined;
    return clamp01(value > 1 ? value / 100 : value);
  }

  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const numeric = Number(trimmed.replace("%", ""));
  if (!Number.isFinite(numeric)) return undefined;
  return clamp01(trimmed.includes("%") || Math.abs(numeric) > 1 ? numeric / 100 : numeric);
}

export function validateReadingImpactDraft(
  draft: ReadingImpactDraft,
): ReadingNumericValidationWarning[] {
  const warnings: ReadingNumericValidationWarning[] = [];
  const impacts = enabledAxisImpacts(draft);
  const hasMixedOrUnknown = impacts.some(
    (impact) => impact.sign === "mixed" || impact.sign === "unknown",
  );

  if (!draft.title.trim()) {
    warnings.push({
      code: "missing_title",
      message: "読みタイトルが未入力です。",
      severity: "warning",
    });
  }

  if (draft.confidence < 0 || draft.confidence > 1) {
    warnings.push({
      code: "confidence_range",
      message: "確信度は0-100%の範囲で入力してください。",
      severity: "danger",
    });
  }

  if (draft.pruning_policy.action === "hard_prune" && hasMixedOrUnknown) {
    warnings.push({
      code: "hard_prune_with_ambiguity",
      message:
        "mixed/unknown が残る軸があります。hard prune ではなく downweight / keep top-k を検討してください。",
      severity: "danger",
    });
  }

  if (draft.pruning_policy.action === "hard_prune" && draft.confidence < 0.3) {
    warnings.push({
      code: "low_confidence_hard_prune",
      message: "確信度が低い状態で hard prune しようとしています。",
      severity: "danger",
    });
  }

  for (const impact of impacts) {
    if (impact.magnitude < 0 || impact.magnitude > 1) {
      warnings.push({
        code: "magnitude_range",
        message: `${axisMetricTitles[impact.axis_id]} の影響量は0-100%の範囲で入力してください。`,
        severity: "danger",
      });
    }
    if (impact.confidence < 0 || impact.confidence > 1) {
      warnings.push({
        code: "axis_confidence_range",
        message: `${axisMetricTitles[impact.axis_id]} の確信度は0-100%の範囲で入力してください。`,
        severity: "danger",
      });
    }
    if (impact.magnitude >= 0.8 && impact.confidence < 0.4) {
      warnings.push({
        code: "large_low_confidence_impact",
        message: "確信度が低い割に影響量が大きいです。過大反映の可能性があります。",
        severity: "warning",
      });
    }
  }

  const thresholdImpact = impacts.find(
    (impact) => impact.axis_id === "score_situation_threshold_axis",
  );
  if (
    ["scenario", "pruning_suggestion", "weight_modifier"].includes(
      draft.reading_type,
    ) &&
    !thresholdImpact
  ) {
    warnings.push({
      code: "missing_score_threshold",
      message:
        "点数状況・行動閾値が未設定です。押し引き判断ではこの軸を確認してください。",
      severity: "warning",
    });
  }

  const waitShapeImpact = impacts.find(
    (impact) => impact.axis_id === "wait_shape_quality_axis",
  );
  if (
    waitShapeImpact?.sign === "unknown" &&
    draft.memo.includes("危険牌")
  ) {
    warnings.push({
      code: "unknown_wait_shape_danger_tile",
      message:
        "待ち・形の良さが unknown です。危険牌比較を確定する前に追加観測を検討してください。",
      severity: "warning",
    });
  }

    if (draft.choice_group) {
    const residualSummary = buildResidualMassSummary(
      draft.choice_group.candidates,
      draft.choice_group.residual_policy,
      draft.choice_group.residual_buckets,
      { hardPrune: draft.pruning_policy.action === "hard_prune" },
    );
    warnings.push(
      ...residualSummary.warnings.map((warning) => ({
        code: warning.code,
        message: warning.message,
        severity: warning.severity,
      })),
    );

    const probabilities = draft.choice_group.candidates
      .map((candidate) => candidate.posterior_probability)
      .filter((value): value is number => value !== undefined);
    for (const probability of probabilities) {
      if (probability < 0 || probability > 1) {
        warnings.push({
          code: "posterior_range",
          message: "候補確率は0-100%の範囲で入力してください。",
          severity: "danger",
        });
      }
    }
    const total = probabilities.reduce((sum, value) => sum + value, 0);
    if (probabilities.length > 0 && total <= 0) {
      warnings.push({
        code: "posterior_zero_total",
        message: "候補確率の合計が0です。",
        severity: "danger",
      });
    }
    if (probabilities.length > 0 && total > 1.0001) {
      warnings.push({
        code: "posterior_total",
        message:
          "候補確率の合計が100%を超えています。値を見直してください。",
        severity: "warning",
      });
    }
    if (total > 1.2) {
      warnings.push({
        code: "posterior_large_total",
        message: "候補確率の合計が100%を大きく超えています。",
        severity: "danger",
      });
    }
  }

  return warnings;
}

export function buildReadingImpactPreview(
  doc: WorkspaceDocument,
  draft: ReadingImpactDraft,
): ReadingImpactPreview {
  const warnings = validateReadingImpactDraft(draft);
  const createdNodeIds: string[] = [];
  const createdEdgeIds: string[] = [];
  const now = nowIso();
  const nodes = [...doc.nodes];
  const edges = [...doc.edges];
  const activeCase =
    doc.cases.find((caseItem) => caseItem.id === doc.active_case_id) ??
    doc.cases[0];
  const readingNode = createReadingNode(draft, nodes.length);
  nodes.push(readingNode);
  createdNodeIds.push(readingNode.id);

  const metricIds = new Map<AxisImpactDraft["axis_id"], string>();
  for (const impact of enabledAxisImpacts(draft)) {
    const metric = findOrCreateAxisMetric(impact.axis_id, nodes);
    metricIds.set(impact.axis_id, metric.id);
    if (!doc.nodes.some((node) => node.id === metric.id)) {
      createdNodeIds.push(metric.id);
    }
    const edge = createKnowledgeEdge({
      source: readingNode.id,
      target: metric.id,
      type: "influences",
      relation_layer: "influence",
      sign: impact.sign,
      magnitude: round(impact.magnitude),
      confidence: round(impact.confidence),
      context_gate: draft.context_gate?.trim() || undefined,
      label: `${axisMetricTitles[impact.axis_id]} ${impact.sign} ${round(impact.magnitude)}`,
      notes: impact.note ?? "",
      conditional_weight: impact.dynamic_weight,
    });
    edges.push(edge);
    createdEdgeIds.push(edge.id);
  }

  if (draft.choice_group) {
    const groupId = draft.choice_group.id?.trim() || createId("choice_group");
    const residualSummary = buildResidualMassSummary(
      draft.choice_group.candidates,
      draft.choice_group.residual_policy,
      draft.choice_group.residual_buckets,
      { hardPrune: draft.pruning_policy.action === "hard_prune" },
    );
    const shouldNormalizeExisting =
      draft.choice_group.normalize ||
      draft.choice_group.residual_policy === "normalize_existing";
    const groupNode = createKnowledgeNode("choice_group", {
      title: draft.choice_group.label || "読み候補群",
      summary: `読み数値入力で作成した候補群。未配分 ${formatPercent(
        residualSummary.residual_probability,
      )}。`,
      description: [
        draft.memo,
        `raw_total=${residualSummary.raw_total}`,
        `residual_probability=${residualSummary.residual_probability}`,
        `residual_policy=${residualSummary.policy}`,
      ]
        .filter(Boolean)
        .join("\n"),
      tags: [
        "quick_reading",
        "reading",
        "probability_tree",
        "choice_group",
        "residual_mass",
        residualSummary.policy,
      ],
      confidence: draft.confidence,
      source_type: draft.source_type,
      probability_role: "control",
      choice_group_id: groupId,
      distribution_family: "categorical",
      position: nextPosition(nodes.length),
    });
    nodes.push(groupNode);
    createdNodeIds.push(groupNode.id);

    const normalized = normalizeResidualCandidates(draft.choice_group.candidates);
    const candidatesForNodes = shouldNormalizeExisting
      ? normalized
      : draft.choice_group.candidates.map((candidate, index) => ({
          ...candidate,
          raw_probability: candidate.posterior_probability ?? 0,
          normalized_probability:
            normalized[index]?.normalized_probability ??
            normalized[index]?.posterior_probability ??
            candidate.posterior_probability ??
            0,
        }));
    for (const [index, candidate] of candidatesForNodes.entries()) {
      const rawProbability =
        candidate.raw_probability ?? candidate.posterior_probability ?? 0;
      const normalizedProbability =
        candidate.normalized_probability ?? candidate.posterior_probability ?? 0;
      const storedProbability = shouldNormalizeExisting
        ? normalizedProbability
        : rawProbability;
      const node = createKnowledgeNode("hypothesis", {
        title: candidate.label || `候補${index + 1}`,
        summary: `${draft.choice_group?.label ?? "読み候補群"}の候補。raw ${formatPercent(
          rawProbability,
        )} / normalized ${formatPercent(normalizedProbability)}。`,
        description: [
          draft.memo,
          `raw_probability=${rawProbability}`,
          `normalized_probability=${normalizedProbability}`,
          shouldNormalizeExisting ? "計算用正規化を適用" : "",
        ]
          .filter(Boolean)
          .join("\n"),
        tags: [
          "quick_reading",
          "reading",
          "probability_tree",
          shouldNormalizeExisting ? "normalize_existing" : "raw_probability",
          ...(candidate.tags ?? []),
        ],
        confidence: draft.confidence,
        source_type: draft.source_type,
        probability_role: "posterior",
        choice_group_id: groupId,
        prior_probability: rawProbability,
        posterior_probability: storedProbability,
        base_weight: candidate.base_weight ?? storedProbability,
        dynamic_weight: candidate.dynamic_weight,
        lock_mode: candidate.lock_mode ?? "none",
        lock_value: candidate.lock_value,
        distribution_family: "categorical",
        propagation_policy: "normalize_siblings",
        pruning_hints: pruningHintsForPolicy(draft),
        lock_rationale: draft.pruning_policy.rationale,
        position: nextPosition(nodes.length),
      });
      nodes.push(node);
      createdNodeIds.push(node.id);
      const edge = createKnowledgeEdge({
        source: readingNode.id,
        target: node.id,
        type: "supports",
        relation_layer: "probabilistic",
        conditional_weight: 1,
        propagate_probability: false,
        label: "読み数値入力",
      });
      edges.push(edge);
      createdEdgeIds.push(edge.id);
    }

    const residualNode =
      residualSummary.residual_probability > 0 &&
      residualSummary.policy !== "normalize_existing"
        ? residualSummary.policy === "add_to_exceptions"
          ? createExceptionCandidateNode(residualSummary.buckets[0])
          : createResidualBucketNode(residualSummary)
        : undefined;
    if (residualNode) {
      const positionedResidualNode = {
        ...residualNode,
        choice_group_id: groupId,
        position: nextPosition(nodes.length),
      };
      nodes.push(positionedResidualNode);
      createdNodeIds.push(positionedResidualNode.id);
      const edge = createKnowledgeEdge({
        source: readingNode.id,
        target: positionedResidualNode.id,
        type: residualSummary.policy === "add_to_exceptions" ? "refines" : "blocks_pruning",
        relation_layer: "semantic",
        label:
          residualSummary.policy === "add_to_exceptions"
            ? "未配分から例外化"
            : "未配分バッファ",
        notes:
          "未配分確率は候補確率に自動按分せず、読み不足・例外・観測ノイズ・未知として保持する。",
      });
      edges.push(edge);
      createdEdgeIds.push(edge.id);
    }
  }

  const nextCases =
    draft.attach_to_active_case && activeCase
      ? doc.cases.map((caseItem) =>
          caseItem.id === activeCase.id
            ? {
                ...caseItem,
                attached_node_ids: unique([
                  ...caseItem.attached_node_ids,
                  ...createdNodeIds,
                ]),
                lane_assignments: {
                  ...caseItem.lane_assignments,
                  ...Object.fromEntries(
                    nodes
                      .filter((node) => createdNodeIds.includes(node.id))
                      .map((node) => [node.id, laneForCreatedNode(node)]),
                  ),
                },
                updated_at: now,
              }
            : caseItem,
        )
      : doc.cases;

  return {
    nextDoc: workspaceDocumentSchema.parse({
      ...doc,
      nodes,
      edges,
      cases: nextCases,
      updated_at: now,
    }),
    warnings,
    createdNodeIds,
    createdEdgeIds,
  };
}

export function applyReadingImpactDraftToWorkspace(
  doc: WorkspaceDocument,
  draft: ReadingImpactDraft,
): WorkspaceDocument {
  return buildReadingImpactPreview(doc, draft).nextDoc;
}

function createReadingNode(draft: ReadingImpactDraft, nodeCount: number) {
  const hints = pruningHintsForPolicy(draft);
  const lockPatch = lockPatchForPolicy(draft);
  const dynamicWeight =
    draft.pruning_policy.action === "soft_downweight"
      ? -Math.abs(draft.pruning_policy.strength ?? 0.2)
      : draft.reading_type === "weight_modifier"
        ? averageDynamicWeight(draft.axis_impacts)
        : undefined;

  return createKnowledgeNode(draft.reading_type, {
    id: createId("quick_reading"),
    title: draft.title.trim() || "読み数値入力",
    summary: summarize(draft.memo),
    description: draft.memo,
    notes: draft.pruning_policy.rationale,
    tags: unique([
      "reading",
      "quick_reading",
      "数値入力",
      ...enabledAxisImpacts(draft).map((impact) => impact.axis_id),
    ]),
    confidence: draft.confidence,
    source_type: draft.source_type,
    probability_role:
      draft.reading_type === "scenario" ||
      draft.reading_type === "pruning_suggestion"
        ? "none"
        : "posterior",
    base_weight: draft.confidence,
    dynamic_weight: dynamicWeight,
    pruning_hints: hints,
    lock_rationale: draft.pruning_policy.rationale,
    ...lockPatch,
    position: nextPosition(nodeCount),
  });
}

function findOrCreateAxisMetric(
  axisId: AxisImpactDraft["axis_id"],
  nodes: KnowledgeNode[],
) {
  const axis = handValueRangeAxes.find((item) => item.id === axisId);
  const titles = new Set<string>(
    ([axis?.label, ...(axis?.metricTitles ?? [])] as Array<string | undefined>).filter(
      (title): title is string => Boolean(title),
    ),
  );
  const existing = nodes.find(
    (node) =>
      node.type === "metric" &&
      (node.tags.includes(axisId) || titles.has(node.title)),
  );
  if (existing) return existing;

  const created = createKnowledgeNode("metric", {
    title: axisMetricTitles[axisId],
    summary: axis?.description ?? axisMetricTitles[axisId],
    description: axis?.description ?? "",
    tags: unique(["metric", "influence", "hand_value_range", axisId, ...(axis?.tags ?? [])]),
    confidence: 0.6,
    source_type: "theory",
    position: nextPosition(nodes.length),
  });
  nodes.push(created);
  return created;
}

function pruningHintsForPolicy(draft: ReadingImpactDraft): PruningHint[] {
  if (draft.pruning_policy.action === "keep_top_k") return ["must_keep_top_k"];
  if (draft.pruning_policy.action === "soft_downweight") return ["score_only"];
  if (draft.pruning_policy.action === "hard_prune") {
    return ["can_prune", "hard_gate_candidate"];
  }
  return [];
}

function lockPatchForPolicy(
  draft: ReadingImpactDraft,
): Pick<KnowledgeNode, "lock_mode"> &
  Partial<Pick<KnowledgeNode, "lock_value">> {
  if (draft.pruning_policy.action === "keep_top_k") {
    return {
      lock_mode: "keep_top_k",
      lock_value: draft.pruning_policy.top_k ?? 3,
    };
  }
  if (draft.pruning_policy.action === "hard_lock") {
    return {
      lock_mode: "hard_lock",
      lock_value: draft.pruning_policy.lock_value ?? 1,
    };
  }
  if (draft.pruning_policy.action === "soft_lock") {
    return {
      lock_mode: "soft_lock",
      lock_value: draft.pruning_policy.lock_value ?? 0.6,
    };
  }
  if (draft.pruning_policy.action === "freeze_ratio") {
    return {
      lock_mode: "freeze_ratio",
      lock_value: draft.pruning_policy.lock_value ?? 0.7,
    };
  }
  return { lock_mode: "none" };
}

function enabledAxisImpacts(draft: ReadingImpactDraft) {
  return draft.axis_impacts.filter((impact) => impact.enabled !== false);
}

function averageDynamicWeight(impacts: AxisImpactDraft[]) {
  const values = impacts
    .map((impact) => impact.dynamic_weight)
    .filter((value): value is number => value !== undefined);
  if (values.length === 0) return undefined;
  return round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function laneForCreatedNode(node: KnowledgeNode): CaseLane {
  if (["hypothesis", "branch"].includes(node.type)) return "hypothesis";
  if (["condition", "metric", "weight_modifier", "choice_group"].includes(node.type)) {
    return "condition";
  }
  if (["scenario", "pruning_suggestion", "action"].includes(node.type)) {
    return "decision";
  }
  return inferLaneFromNodeType(node.type);
}

function nextPosition(index: number) {
  return {
    x: 220 + (index % 5) * 280,
    y: 140 + Math.floor(index / 5) * 190,
  };
}

function summarize(value: string) {
  const normalized = value.trim().replace(/\s+/g, " ");
  if (!normalized) return "読み数値入力で作成したノード。";
  return normalized.length > 120 ? `${normalized.slice(0, 120)}...` : normalized;
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

function round(value: number) {
  return Math.round(value * 10000) / 10000;
}

function formatPercent(value: number) {
  return `${Math.round(value * 1000) / 10}%`;
}
