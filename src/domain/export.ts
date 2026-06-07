import {
  PRUNING_EXPORT_SCHEMA_VERSION,
  WORKSPACE_SCHEMA_VERSION,
  normalizeWorkspaceDocument,
  normalizeWorkspaceScopes,
  pruningExportSchema,
  workspaceDocumentSchema,
  type KnowledgeEdge,
  type KnowledgeNode,
  type PruningExport,
  type WorkspaceDocument,
} from "./schema";
import {
  getChoiceGroups,
  getInferenceSubgraph,
  getPropagationOrder,
} from "./probability";
import { getInfluenceModel } from "./influence";
import { getConcentrationItems } from "./reasoningLab";

export function parseWorkspaceJson(rawJson: string): WorkspaceDocument {
  const parsed: unknown = JSON.parse(rawJson);
  return normalizeWorkspaceDocument(parsed);
}

export function serializeWorkspace(workspace: WorkspaceDocument): string {
  return JSON.stringify(
    normalizeWorkspaceScopes(workspaceDocumentSchema.parse(workspace)),
    null,
    2,
  );
}

export function createPruningSubgraphExport(
  workspace: WorkspaceDocument,
  selectedNodeIds: string[],
  selectedEdgeIds: string[],
): PruningExport {
  const explicitNodeIds = new Set(selectedNodeIds);
  const explicitEdgeIds = new Set(selectedEdgeIds);

  for (const edge of workspace.edges) {
    if (explicitEdgeIds.has(edge.id)) {
      explicitNodeIds.add(edge.source);
      explicitNodeIds.add(edge.target);
    }
  }

  const selectedNodes = workspace.nodes.filter((node) =>
    explicitNodeIds.has(node.id),
  );
  const selectedNodeIdSet = new Set(selectedNodes.map((node) => node.id));
  const selectedEdges = workspace.edges.filter((edge) => {
    return (
      explicitEdgeIds.has(edge.id) ||
      (selectedNodeIdSet.has(edge.source) && selectedNodeIdSet.has(edge.target))
    );
  });

  const relatedRuleIds = new Set<string>();
  for (const node of selectedNodes) {
    for (const ruleId of node.related_rule_ids) {
      relatedRuleIds.add(ruleId);
    }
  }

  const relatedRules = workspace.rules.filter((rule) => {
    const targetsSelected = rule.target_node_ids.some((nodeId) =>
      selectedNodeIdSet.has(nodeId),
    );
    if (targetsSelected) relatedRuleIds.add(rule.id);
    return targetsSelected || relatedRuleIds.has(rule.id);
  });

  const nodeMetadata = Object.fromEntries(
    selectedNodes.map((node) => [
      node.id,
      {
        type: node.type,
        title: node.title,
        tags: node.tags,
        confidence: node.confidence,
        applicability: node.applicability,
        pruning_hints: node.pruning_hints,
        probability_role: node.probability_role,
        choice_group_id: node.choice_group_id,
        posterior_probability: node.posterior_probability,
        prior_probability: node.prior_probability,
        lock_mode: node.lock_mode,
        distribution_family: node.distribution_family,
      },
    ]),
  );

  const pruningHints = Object.fromEntries(
    selectedNodes.map((node) => [
      node.id,
      node.pruning_hints.length > 0
        ? node.pruning_hints
        : inferHints(node, selectedEdges),
    ]),
  );

  const weightPlaceholders = Object.fromEntries(
    selectedNodes.map((node) => [
      node.id,
      {
        initial_weight: Number(node.confidence.toFixed(2)),
        rationale: `MVP placeholder from confidence for ${node.title}`,
        locked:
          node.pruning_hints.includes("hard_gate_candidate") ||
          node.type === "exception",
      },
    ]),
  );

  const inferenceSubgraph = getInferenceSubgraph({
    ...workspace,
    nodes: selectedNodes,
    edges: selectedEdges,
  });
  const choiceGroups = getChoiceGroups(inferenceSubgraph.nodes);
  const propagationOrder = getPropagationOrder(
    inferenceSubgraph.nodes,
    inferenceSubgraph.edges,
  ).order;
  const locks = Object.fromEntries(
    selectedNodes
      .filter((node) => node.lock_mode !== "none")
      .map((node) => [
        node.id,
        { lock_mode: node.lock_mode, lock_value: node.lock_value },
      ]),
  );
  const weights = Object.fromEntries(
    selectedNodes
      .filter((node) => node.probability_role !== "none")
      .map((node) => [
        node.id,
        {
          base_weight: node.base_weight,
          dynamic_weight: node.dynamic_weight,
          prior_probability: node.prior_probability,
          posterior_probability: node.posterior_probability,
        },
      ]),
  );
  const distributions = Object.fromEntries(
    selectedNodes
      .filter((node) => node.distribution_family)
      .map((node) => [
        node.id,
        {
          distribution_family: node.distribution_family,
          hysteresis_band: node.hysteresis_band,
          pruning_priority: node.pruning_priority,
        },
      ]),
  );
  const frozenNodes = selectedNodes
    .filter(
      (node) =>
        node.lock_mode === "hard" ||
        node.lock_mode === "hard_lock" ||
        node.lock_mode === "freeze_ratio" ||
        node.lock_mode === "freeze_concentration_band",
    )
    .map((node) => node.id);
  const topKConstraints = Object.fromEntries(
    selectedNodes
      .filter((node) => node.lock_mode === "keep_top_k")
      .map((node) => [
        node.choice_group_id ?? node.id,
        Math.round(node.lock_value ?? 2),
      ]),
  );
  const influenceModel = getInfluenceModel({
    ...workspace,
    nodes: selectedNodes,
    edges: selectedEdges,
  });
  const selectedWorkspace = {
    ...workspace,
    nodes: selectedNodes,
    edges: selectedEdges,
  };
  const concentrationMetrics = Object.fromEntries(
    getConcentrationItems(selectedWorkspace).map((item) => [
      item.id,
      item.metrics,
    ]),
  );

  return pruningExportSchema.parse({
    schema_version: PRUNING_EXPORT_SCHEMA_VERSION,
    exported_at: new Date().toISOString(),
    source_workspace_schema_version: WORKSPACE_SCHEMA_VERSION,
    selected_nodes: selectedNodes,
    selected_edges: selectedEdges,
    node_metadata: nodeMetadata,
    rules: relatedRules,
    pruning_hints: pruningHints,
    weight_placeholders: weightPlaceholders,
    inference_subgraph: inferenceSubgraph,
    choice_groups: choiceGroups,
    locks,
    weights,
    distributions,
    propagation_order: propagationOrder,
    frozen_nodes: frozenNodes,
    top_k_constraints: topKConstraints,
    reasoning_lab: {
      concentration_metrics: concentrationMetrics,
      pruning_actions: workspace.pruning_actions.filter((action) =>
        action.target_ids.some((id) => selectedNodeIdSet.has(id)),
      ),
      impact_summaries: workspace.impact_summaries,
      reading_utilities: workspace.reading_utilities.filter((utility) =>
        selectedNodeIdSet.has(utility.target_id),
      ),
      reading_chains: workspace.reading_chains.filter((chain) =>
        chain.steps.some((step) =>
          [...step.source_ids, ...step.target_ids].some((id) =>
            selectedNodeIdSet.has(id),
          ),
        ),
      ),
      averaging_safety: workspace.averaging_safety.filter((safety) =>
        selectedNodeIdSet.has(safety.target_id),
      ),
      teaching_logs: workspace.teaching_logs,
    },
    influence_model: {
      metrics: influenceModel.metrics,
      influence_edges: influenceModel.influence_edges,
      ambiguity_groups: influenceModel.ambiguities.map((item) => ({
        id: item.id,
        metric_id: item.metric_id,
        influence_edge_ids: item.influence_edge_ids,
        status: item.status,
        unresolved_score: item.unresolved_score,
      })),
      observation_candidates: influenceModel.observation_plan.map(
        (item) => item.node,
      ),
      pruning_suggestions: influenceModel.branch_vectors.map((vector) => ({
        branch_id: vector.branch_id,
        action: vector.prune_action,
        confidence: vector.prune_confidence,
        reason: vector.prune_reason,
      })),
    },
  });
}

function inferHints(node: KnowledgeNode, selectedEdges: KnowledgeEdge[]) {
  const outboundOverride = selectedEdges.some(
    (edge) => edge.source === node.id && edge.type === "overrides",
  );
  if (node.type === "condition") return ["hard_gate_candidate" as const];
  if (node.type === "metric") return ["score_only" as const];
  if (node.type === "exception" || outboundOverride)
    return ["override_only" as const];
  if (node.type === "heuristic" || node.tags.includes("Top-k"))
    return ["must_keep_top_k" as const];
  return ["can_prune" as const];
}

export function serializePruningExport(exportData: PruningExport): string {
  return JSON.stringify(pruningExportSchema.parse(exportData), null, 2);
}
