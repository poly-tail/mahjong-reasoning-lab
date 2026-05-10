import { describe, expect, it } from "vitest";
import { getAmbiguities } from "../../src/domain/influence";
import {
  evaluateReadingUtilities,
  replayReadingChain,
  simulatePruningAction,
} from "../../src/domain/reasoningLab";
import { seedWorkspace } from "../../src/domain/seed";
import type { PruningAction } from "../../src/domain/schema";

describe("Reasoning Lab calculations", () => {
  it("keeps sibling normalization valid after a lock action", () => {
    const action: PruningAction = {
      id: "test_hard_lock_flush",
      action_type: "hard_lock",
      target_ids: ["node_flush_mainline"],
      strength: 0.7,
      rationale: "test hard lock redistribution",
      created_at: "2026-05-05T00:00:00.000Z",
    };

    const simulation = simulatePruningAction(seedWorkspace, action);
    const total = simulation.preview_doc.nodes
      .filter((node) => node.choice_group_id === "cg_flush_read")
      .reduce((sum, node) => sum + (node.posterior_probability ?? 0), 0);

    expect(total).toBeGreaterThan(0.99);
    expect(total).toBeLessThan(1.01);
  });

  it("creates a consistent impact summary after prune", () => {
    const action: PruningAction = {
      id: "test_prune_tail",
      action_type: "hard_prune",
      target_ids: ["node_bimodal_thin_tail"],
      strength: 1,
      rationale: "test prune diff",
      created_at: "2026-05-05T00:00:00.000Z",
    };

    const simulation = simulatePruningAction(seedWorkspace, action);
    const after = simulation.after.node_probabilities.node_bimodal_thin_tail;

    expect(after).toBe(0);
    expect(simulation.impact_summary.changed_node_count).toBeGreaterThan(0);
    expect(simulation.impact_summary.delta_mass).toBeGreaterThan(0);
    expect(simulation.impact_summary.before_snapshot_id).toBe(
      simulation.before.id,
    );
  });

  it("does not overvalue selective-only utility", () => {
    const utilities = evaluateReadingUtilities(seedWorkspace);
    const narrow = utilities.find(
      (item) => item.target_id === "node_narrow_point_prune_reading",
    );
    const topMass = utilities.find(
      (item) => item.target_id === "node_top2_mass_prune_reading",
    );

    expect(narrow?.utility_score).toBeLessThan(0.2);
    expect(topMass?.utility_score).toBeGreaterThan(narrow?.utility_score ?? 0);
  });

  it("preserves the difference between mixed and unknown ambiguity", () => {
    const statuses = getAmbiguities(seedWorkspace).map((item) => item.status);

    expect(statuses).toContain("mixed");
    expect(statuses).toContain("unknown");
  });

  it("replays reading chain snapshot diffs deterministically", () => {
    const chain = seedWorkspace.reading_chains.find(
      (item) => item.id === "chain_seed_observe_lock_prune_compare",
    );
    expect(chain).toBeDefined();

    const first = replayReadingChain(seedWorkspace, chain!);
    const second = replayReadingChain(seedWorkspace, chain!);

    expect(first.steps.map((step) => step.impact_summary.delta_mass)).toEqual(
      second.steps.map((step) => step.impact_summary.delta_mass),
    );
    expect(
      first.steps.map((step) => step.impact_summary.margin_change),
    ).toEqual(second.steps.map((step) => step.impact_summary.margin_change));
  });
});
