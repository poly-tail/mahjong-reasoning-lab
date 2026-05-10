import { describe, expect, it } from "vitest";
import { createPruningSubgraphExport } from "../../src/domain/export";
import {
  getAmbiguities,
  getBranchVectors,
  getObservationPlan,
} from "../../src/domain/influence";
import { runPropagation } from "../../src/domain/probability";
import { seedWorkspace } from "../../src/domain/seed";
import { workspaceDocumentSchema } from "../../src/domain/schema";

describe("workspace schema and pruning export", () => {
  it("validates the seed workspace", () => {
    const parsed = workspaceDocumentSchema.parse(seedWorkspace);

    expect(parsed.nodes.length).toBeGreaterThan(20);
    expect(parsed.rules.map((rule) => rule.id)).toContain(
      "rule_push_pull_gate",
    );
    expect(parsed.active_case_id).toBe("case_seed_push_pull");
  });

  it("exports selected subgraphs with related rules and weight placeholders", () => {
    const exported = createPruningSubgraphExport(
      seedWorkspace,
      ["node_hard_gate"],
      [],
    );

    expect(exported.schema_version).toBe("pruning-ui.subgraph.v4");
    expect(exported.selected_nodes.map((node) => node.id)).toContain(
      "node_hard_gate",
    );
    expect(exported.rules.map((rule) => rule.id)).toContain(
      "rule_push_pull_gate",
    );
    expect(exported.pruning_hints.node_hard_gate).toContain(
      "hard_gate_candidate",
    );
    expect(
      exported.weight_placeholders.node_hard_gate.initial_weight,
    ).toBeGreaterThan(0);
  });

  it("exports inference layer fields for probabilistic subgraphs", () => {
    const exported = createPruningSubgraphExport(
      seedWorkspace,
      ["node_flush_mainline", "node_flush_thin", "node_flush_denied"],
      [],
    );

    expect(exported.inference_subgraph.nodes.length).toBeGreaterThanOrEqual(3);
    expect(exported.choice_groups.map((group) => group.id)).toContain(
      "cg_flush_read",
    );
    expect(exported.weights.node_flush_mainline.base_weight).toBeGreaterThan(0);
    expect(exported.distributions.node_flush_mainline.distribution_family).toBe(
      "categorical",
    );
    expect(
      exported.reasoning_lab.concentration_metrics.cg_flush_read,
    ).toBeDefined();
  });

  it("normalizes choice groups in the propagation preview", () => {
    const preview = runPropagation(seedWorkspace, "node_flush_mainline");
    const flushNodes = preview.updated_workspace.nodes.filter(
      (node) => node.choice_group_id === "cg_flush_read",
    );
    const total = flushNodes.reduce(
      (sum, node) => sum + (node.posterior_probability ?? 0),
      0,
    );

    expect(total).toBeGreaterThan(0.99);
    expect(total).toBeLessThan(1.01);
    expect(preview.diffs.length).toBeGreaterThan(0);
  });

  it("models signed influence on edges and separates mixed from unknown", () => {
    const ambiguities = getAmbiguities(seedWorkspace);
    const statuses = ambiguities.map((item) => item.status);

    expect(statuses).toContain("mixed");
    expect(statuses).toContain("unknown");
    expect(
      seedWorkspace.edges.find(
        (edge) => edge.id === "edge_unsuji_tedashi_fold_risk",
      )?.sign,
    ).toBe("+");
  });

  it("summarizes branch vectors and observation candidate gain/cost", () => {
    const vectors = getBranchVectors(seedWorkspace);
    const observationPlan = getObservationPlan(seedWorkspace);

    expect(
      vectors.some((vector) => vector.branch_id === "node_flush_mainline"),
    ).toBe(true);
    expect(observationPlan.map((item) => item.node.id)).toContain(
      "obs_candidate_tedashi_jihai_renda",
    );
    expect(observationPlan[0]?.gain_cost_ratio).toBeGreaterThan(1);
  });
});
