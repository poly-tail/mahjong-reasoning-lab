import { createId, createKnowledgeNode } from "./factory";
import type { MappingDraftNode } from "./mappingTemplates";
import type { ChoiceCandidateDraft } from "./readingNumerics";
import type { KnowledgeNode } from "./schema";

export type ResidualMassPolicy =
  | "suggest_candidates"
  | "add_to_exceptions"
  | "keep_unknown_buffer"
  | "normalize_existing"
  | "leave_unassigned";

export type ResidualMassBucket = {
  id: string;
  label: string;
  kind:
    | "unrecalled_candidate"
    | "exception"
    | "observation_noise"
    | "unknown_buffer";
  probability: number;
  note?: string;
  tags: string[];
};

export type ResidualMassSuggestion = {
  id: string;
  label: string;
  probability: number;
  bucket_kind: ResidualMassBucket["kind"];
  action: ResidualMassPolicy;
  note: string;
};

export type ResidualMassWarning = {
  code: string;
  message: string;
  severity: "info" | "warning" | "danger";
};

export type ResidualMassSummary = {
  raw_total: number;
  residual_probability: number;
  overallocated_probability: number;
  policy: ResidualMassPolicy;
  normalized_candidates: ChoiceCandidateDraft[];
  buckets: ResidualMassBucket[];
  suggestions: ResidualMassSuggestion[];
  warnings: ResidualMassWarning[];
  hard_prune_requested: boolean;
};

export type ResidualMassChoiceGroupSummary = {
  id: string;
  label: string;
  node_ids: string[];
  residual_node_ids: string[];
  summary: ResidualMassSummary;
};

const epsilon = 0.000001;

export function calculateResidualMass(
  candidates: ChoiceCandidateDraft[],
): number {
  const rawTotal = calculateRawTotal(candidates);
  return round(Math.max(0, 1 - rawTotal));
}

export function normalizeCandidates(
  candidates: ChoiceCandidateDraft[],
): ChoiceCandidateDraft[] {
  const rawTotal = calculateRawTotal(candidates);
  if (rawTotal <= epsilon) {
    return candidates.map((candidate) => ({
      ...candidate,
      raw_probability: candidate.posterior_probability ?? 0,
      normalized_probability: candidate.posterior_probability ?? 0,
    }));
  }

  return candidates.map((candidate) => {
    const raw = clampProbability(candidate.posterior_probability ?? 0);
    const normalized = round(raw / rawTotal);
    return {
      ...candidate,
      raw_probability: raw,
      normalized_probability: normalized,
      posterior_probability: normalized,
    };
  });
}

export function buildResidualMassSummary(
  candidates: ChoiceCandidateDraft[],
  policy: ResidualMassPolicy = "keep_unknown_buffer",
  buckets: ResidualMassBucket[] = [],
  options: { hardPrune?: boolean } = {},
): ResidualMassSummary {
  const rawTotal = calculateRawTotal(candidates);
  const residual = calculateResidualMass(candidates);
  const overallocated = round(Math.max(0, rawTotal - 1));
  const normalizedCandidates = normalizeCandidates(candidates);
  const effectiveBuckets =
    residual > epsilon
      ? buckets.length > 0
        ? normalizeBuckets(buckets, residual)
        : [createDefaultBucket(policy, residual)]
      : [];
  const suggestions = createResidualSuggestions(
    residual,
    policy,
    effectiveBuckets,
  );
  const baseSummary: ResidualMassSummary = {
    raw_total: round(rawTotal),
    residual_probability: residual,
    overallocated_probability: overallocated,
    policy,
    normalized_candidates: normalizedCandidates,
    buckets: effectiveBuckets,
    suggestions,
    warnings: [],
    hard_prune_requested: Boolean(options.hardPrune),
  };

  return {
    ...baseSummary,
    warnings: validateResidualMass(baseSummary),
  };
}

export function validateResidualMass(
  summary: ResidualMassSummary,
): ResidualMassWarning[] {
  const warnings: ResidualMassWarning[] = [];
  const residual = summary.residual_probability;

  if (summary.overallocated_probability > epsilon) {
    warnings.push({
      code: "overallocated_probability",
      severity:
        summary.overallocated_probability >= 0.2 ? "danger" : "warning",
      message:
        "候補確率の合計が100%を超えています。過剰分を削るか、入力値を見直してください。",
    });
  }

  if (residual >= 0.25) {
    warnings.push({
      code: "residual_hard_prune_warning",
      severity: "danger",
      message:
        "未配分が大きいため、この候補群でのhard pruneは危険です。候補追加または未知バッファ保持を推奨します。",
    });
  } else if (residual >= 0.15) {
    warnings.push({
      code: "residual_warning",
      severity: "warning",
      message:
        "未配分が大きめです。まだ候補化していない読み、例外パターン、観測ノイズが残っている可能性があります。hard pruneは非推奨です。",
    });
  } else if (residual > 0.05) {
    warnings.push({
      code: "residual_info",
      severity: "info",
      message:
        "未配分確率があります。読み不足、例外、観測ノイズ、未知バッファとして扱えます。",
    });
  }

  if (summary.hard_prune_requested && residual > epsilon) {
    warnings.push({
      code: "hard_prune_with_residual_mass",
      severity: residual >= 0.25 ? "danger" : "warning",
      message:
        "未配分確率が残っています。hard pruneではなくkeep top-k/downweightを検討してください。",
    });
  }

  if (summary.policy === "normalize_existing" && residual > epsilon) {
    warnings.push({
      code: "explicit_normalization",
      severity: "info",
      message:
        "既存候補への按分は計算用正規化です。raw probabilityは読み不足/例外/未知として残して確認してください。",
    });
  }

  return warnings;
}

export function shouldBlockHardPrune(summary: ResidualMassSummary): boolean {
  return summary.warnings.some(
    (warning) =>
      warning.severity === "danger" ||
      warning.code === "hard_prune_with_residual_mass",
  );
}

export function createResidualBucketNode(
  summary: ResidualMassSummary,
): KnowledgeNode {
  const bucket = summary.buckets[0] ?? createDefaultBucket(summary.policy, 0);
  return createKnowledgeNode("ambiguity_marker", {
    id: createId("residual_mass"),
    title: bucket.label || "未配分確率",
    summary: `choice groupに未配分確率 ${formatPercent(
      bucket.probability,
    )} が残っています。`,
    description: [
      `raw_total: ${summary.raw_total}`,
      `residual_probability: ${summary.residual_probability}`,
      `policy: ${summary.policy}`,
      bucket.note ? `note: ${bucket.note}` : "",
    ]
      .filter(Boolean)
      .join("\n"),
    tags: unique([
      "residual_mass",
      bucket.kind,
      "unknown",
      ...bucket.tags,
    ]),
    confidence: 0.35,
    posterior_probability: bucket.probability,
    base_weight: bucket.probability,
    source_type: "note",
    pruning_hints: ["must_keep_top_k"],
    position: { x: 120, y: 120 },
  });
}

export function createExceptionCandidateNode(
  bucket: ResidualMassBucket,
): KnowledgeNode {
  return createKnowledgeNode("exception", {
    id: createId("exception"),
    title: bucket.label || "未配分からの例外候補",
    summary: `未配分確率 ${formatPercent(bucket.probability)} から保存した例外候補。`,
    description:
      bucket.note ??
      "候補群の100%未満部分から切り出した例外/観測ノイズ候補です。",
    tags: unique(["exception", "residual_mass", "reading_drawer", ...bucket.tags]),
    confidence: 0.35,
    posterior_probability: bucket.probability,
    base_weight: bucket.probability,
    source_type: "note",
    pruning_hints: ["must_keep_top_k"],
    position: { x: 120, y: 120 },
  });
}

export function createExceptionCandidateDraft(
  bucket: ResidualMassBucket,
): MappingDraftNode {
  return {
    draft_id: bucket.id || createId("exception_draft"),
    title: bucket.label || "未配分からの例外候補",
    type: "exception",
    tags: unique(["exception", "residual_mass", "reading_drawer", ...bucket.tags]),
    summary: `未配分確率 ${formatPercent(bucket.probability)} から保存した例外候補。`,
    description:
      bucket.note ??
      "候補群の100%未満部分から切り出した例外/観測ノイズ候補です。",
    confidence: 0.35,
    pruning_hints: ["must_keep_top_k"],
    probability_role: "posterior",
    base_weight: bucket.probability,
    posterior_probability: bucket.probability,
    lock_mode: "keep_top_k",
    lock_value: 3,
    distribution_family: "categorical",
  };
}

export function residualPolicyLabel(policy: ResidualMassPolicy): string {
  const labels: Record<ResidualMassPolicy, string> = {
    suggest_candidates: "具体候補を提案する",
    add_to_exceptions: "例外集に入れる",
    keep_unknown_buffer: "未知バッファとして保持する",
    normalize_existing: "既存候補へ按分する",
    leave_unassigned: "いったん未配分のまま残す",
  };
  return labels[policy];
}

export function residualBucketKindLabel(
  kind: ResidualMassBucket["kind"],
): string {
  const labels: Record<ResidualMassBucket["kind"], string> = {
    unrecalled_candidate: "未想起候補",
    exception: "例外",
    observation_noise: "観測ノイズ",
    unknown_buffer: "未知バッファ",
  };
  return labels[kind];
}

export function getResidualMassChoiceGroups(
  nodes: KnowledgeNode[],
): ResidualMassChoiceGroupSummary[] {
  const groupIds = new Set(
    nodes
      .map((node) => node.choice_group_id)
      .filter((id): id is string => Boolean(id)),
  );

  return Array.from(groupIds)
    .map((groupId) => {
      const groupNodes = nodes.filter((node) => node.choice_group_id === groupId);
      const control = groupNodes.find((node) => node.type === "choice_group");
      const residualNodes = groupNodes.filter(
        (node) => node.type !== "choice_group" && node.tags.includes("residual_mass"),
      );
      const candidates = groupNodes
        .filter(
          (node) =>
            !node.tags.includes("residual_mass") &&
            node.probability_role !== "control",
        )
        .map((node) => ({
          label: node.title,
          posterior_probability:
            node.prior_probability ?? node.posterior_probability ?? 0,
          base_weight: node.base_weight,
          dynamic_weight: node.dynamic_weight,
          lock_mode: node.lock_mode,
          lock_value: node.lock_value,
          tags: node.tags,
        }));
      const buckets = residualNodes.map(nodeToBucket);
      const policy = inferPolicyFromBuckets(buckets, residualNodes);
      return {
        id: groupId,
        label: control?.title ?? groupId,
        node_ids: groupNodes
          .filter((node) => !node.tags.includes("residual_mass"))
          .map((node) => node.id),
        residual_node_ids: residualNodes.map((node) => node.id),
        summary: buildResidualMassSummary(candidates, policy, buckets),
      };
    })
    .filter(
      (item) =>
        item.summary.residual_probability > epsilon ||
        item.summary.overallocated_probability > epsilon ||
        item.residual_node_ids.length > 0,
    )
    .sort((a, b) => b.summary.residual_probability - a.summary.residual_probability);
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

function calculateRawTotal(candidates: ChoiceCandidateDraft[]): number {
  return round(
    candidates.reduce(
      (sum, candidate) =>
        sum + clampProbability(candidate.posterior_probability ?? 0),
      0,
    ),
  );
}

function nodeToBucket(node: KnowledgeNode): ResidualMassBucket {
  const kind = node.tags.includes("exception")
    ? "exception"
    : node.tags.includes("observation_noise")
      ? "observation_noise"
      : node.tags.includes("unrecalled_candidate")
        ? "unrecalled_candidate"
        : "unknown_buffer";
  return {
    id: node.id,
    label: node.title,
    kind,
    probability: clampProbability(
      node.posterior_probability ?? node.base_weight ?? node.confidence ?? 0,
    ),
    note: node.description || node.summary,
    tags: node.tags,
  };
}

function inferPolicyFromBuckets(
  buckets: ResidualMassBucket[],
  nodes: KnowledgeNode[],
): ResidualMassPolicy {
  if (nodes.some((node) => node.tags.includes("normalize_existing"))) {
    return "normalize_existing";
  }
  if (buckets.some((bucket) => bucket.kind === "exception")) {
    return "add_to_exceptions";
  }
  if (buckets.some((bucket) => bucket.kind === "unrecalled_candidate")) {
    return "suggest_candidates";
  }
  if (buckets.some((bucket) => bucket.kind === "observation_noise")) {
    return "leave_unassigned";
  }
  return "keep_unknown_buffer";
}

function createDefaultBucket(
  policy: ResidualMassPolicy,
  probability: number,
): ResidualMassBucket {
  if (policy === "suggest_candidates") {
    return {
      id: createId("residual_bucket"),
      label: "未想起候補",
      kind: "unrecalled_candidate",
      probability,
      note: "まだ候補化していない読みとして候補提案を使う。",
      tags: ["residual_mass", "unrecalled_candidate"],
    };
  }
  if (policy === "add_to_exceptions") {
    return {
      id: createId("residual_bucket"),
      label: "未配分からの例外候補",
      kind: "exception",
      probability,
      note: "例外集に保存し、次回以降の候補提案に使う。",
      tags: ["residual_mass", "exception"],
    };
  }
  if (policy === "leave_unassigned") {
    return {
      id: createId("residual_bucket"),
      label: "未配分のまま保持",
      kind: "observation_noise",
      probability,
      note: "観測ノイズや入力保留として明示的に残す。",
      tags: ["residual_mass", "observation_noise"],
    };
  }
  return {
    id: createId("residual_bucket"),
    label: "未知バッファ",
    kind: "unknown_buffer",
    probability,
    note: "未知・読み不足・例外の可能性として残す。",
    tags: ["residual_mass", "unknown_buffer"],
  };
}

function normalizeBuckets(
  buckets: ResidualMassBucket[],
  residual: number,
): ResidualMassBucket[] {
  const total = buckets.reduce(
    (sum, bucket) => sum + clampProbability(bucket.probability),
    0,
  );
  if (total <= epsilon) return buckets;
  const scale = residual / total;
  return buckets.map((bucket) => ({
    ...bucket,
    probability: round(clampProbability(bucket.probability) * scale),
    tags: unique(["residual_mass", bucket.kind, ...bucket.tags]),
  }));
}

function createResidualSuggestions(
  residual: number,
  policy: ResidualMassPolicy,
  buckets: ResidualMassBucket[],
): ResidualMassSuggestion[] {
  if (residual <= epsilon) return [];
  return buckets.map((bucket) => ({
    id: createId("residual_suggestion"),
    label: bucket.label,
    probability: bucket.probability,
    bucket_kind: bucket.kind,
    action: policy,
    note:
      bucket.note ??
      "未配分を候補、例外、観測ノイズ、未知バッファのどれとして扱うか確認してください。",
  }));
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function clampProbability(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function round(value: number): number {
  return Math.round(value * 10000) / 10000;
}
