import { describe, expect, it } from "vitest";
import { resolveNonOverlappingNodePosition } from "../../src/app/store";

describe("node layout collision handling", () => {
  it("keeps a free node position unchanged", () => {
    const nodes = [
      { id: "node_a", position: { x: 0, y: 0 } },
      { id: "node_b", position: { x: 420, y: 0 } },
    ];

    expect(
      resolveNonOverlappingNodePosition("node_b", { x: 420, y: 0 }, nodes),
    ).toEqual({ x: 420, y: 0 });
  });

  it("moves a dropped node to the nearest non-overlapping slot", () => {
    const nodes = [
      { id: "node_a", position: { x: 0, y: 0 } },
      { id: "node_b", position: { x: 420, y: 0 } },
    ];

    expect(
      resolveNonOverlappingNodePosition("node_b", { x: 0, y: 0 }, nodes),
    ).toEqual({ x: 0, y: 196 });
  });

  it("normalizes off-canvas and fractional positions", () => {
    const nodes = [{ id: "node_a", position: { x: 0, y: 0 } }];

    expect(
      resolveNonOverlappingNodePosition(
        "node_b",
        { x: -10.4, y: 240.6 },
        nodes,
      ),
    ).toEqual({ x: 0, y: 241 });
  });
});
