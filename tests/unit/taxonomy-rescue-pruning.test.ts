import { describe, expect, it } from "vitest";
import {
  createDomainLensSelection,
  getLegacyAxisMapping,
  handValueAxes,
  nodeMatchesDomainLens,
} from "../../src/domain/mahjongTaxonomy";
import { getPruningLockWarnings } from "../../src/domain/pruningSafety";
import { calculateRescueRate, estimateRescueRate } from "../../src/domain/rescueRate";
import { seedWorkspace } from "../../src/domain/seed";
import type { PruningAction } from "../../src/domain/schema";

describe("mahjong taxonomy, rescue rate, and pruning safety", () => {
  it("filters domain lenses by tags and node fields", () => {
    const selection = createDomainLensSelection("rescue_rate", seedWorkspace);

    expect(selection.nodeIds.has("metric_rescue_rate")).toBe(true);
    expect(
      nodeMatchesDomainLens(
        seedWorkspace.nodes.find((node) => node.id === "metric_shape")!,
        "hand_value",
      ),
    ).toBe(true);
  });

  it("uses the canonical four hand value axes while retaining old aliases", () => {
    expect(handValueAxes.map((axis) => axis.label)).toEqual([
      "進行度・聴牌率",
      "打点",
      "待ち・形の良さ",
      "点数状況・行動閾値",
    ]);
    expect(handValueAxes.flatMap((axis) => axis.aliases)).toEqual(
      expect.arrayContaining(["speed_axis", "shape_axis", "external_modifier"]),
    );
  });

  it("maps legacy axis labels to the canonical four axes", () => {
    expect(getLegacyAxisMapping()).toEqual([
      {
        legacy: "早さ",
        current: "進行度・聴牌率",
        note: "旧『早さ』は、聴牌率・先制率・巡目に対する進行度として扱う。",
      },
      {
        legacy: "打点分布",
        current: "打点",
        note: "UI上は『打点』と表示し、内部説明ではレンジ・分布として扱う。",
      },
      {
        legacy: "形",
        current: "待ち・形の良さ",
        note: "旧『形』は、良形/愚形・待ち候補・和了しやすさ・危険牌比較まで含めて扱う。",
      },
      {
        legacy: "局面価値・行動閾値",
        current: "点数状況・行動閾値",
        note: "局面価値という抽象語ではなく、点数状況と行動閾値として表示する。",
      },
    ]);
  });

  it("calculates rescue rate with capped warnings", () => {
    expect(calculateRescueRate([0.1, 0.2])).toBe(0.28);

    const estimate = estimateRescueRate(
      [
        { id: "a", label: "a", enabled: true, probability: 0.2 },
        { id: "b", label: "b", enabled: true, probability: 0.2 },
      ],
      "low",
    );

    expect(estimate.q_total).toBe(0.36);
    expect(estimate.warnings.join(" ")).toContain("高く見積もりすぎ");
  });

  it("returns qualitative rescue rate when probabilities are empty", () => {
    const estimate = estimateRescueRate(
      [{ id: "a", label: "a", enabled: true }],
      "some",
    );

    expect(estimate.q_total).toBeUndefined();
    expect(estimate.range_label).toBe("10-20%");
  });

  it("keeps hard prune and hard lock warnings distinct", () => {
    const hardPrune: PruningAction = {
      id: "test_prune",
      action_type: "hard_prune",
      target_ids: ["node_reading_interval_spread"],
      strength: 1,
      rationale: "test",
      created_at: "2026-05-05T00:00:00.000Z",
    };
    const hardLock: PruningAction = {
      ...hardPrune,
      id: "test_lock",
      action_type: "hard_lock",
    };

    expect(getPruningLockWarnings(seedWorkspace, hardPrune).join(" ")).toContain(
      "must_keep_top_k",
    );
    expect(getPruningLockWarnings(seedWorkspace, hardLock)).toEqual([]);
  });

  it("warns on mixed or unknown influence before hard prune", () => {
    const action: PruningAction = {
      id: "test_mixed",
      action_type: "hard_prune",
      target_ids: ["node_flush_mainline"],
      strength: 1,
      rationale: "test",
      created_at: "2026-05-05T00:00:00.000Z",
    };

    expect(getPruningLockWarnings(seedWorkspace, action).join(" ")).toContain(
      "mixed/unknown influence",
    );
  });
});
