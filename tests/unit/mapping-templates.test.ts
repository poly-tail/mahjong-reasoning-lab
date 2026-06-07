import { describe, expect, it } from "vitest";
import { createMappingDraft } from "../../src/domain/mappingTemplates";

describe("mappingTemplates", () => {
  it("creates expected draft nodes for hand value range", () => {
    const draft = createMappingDraft(
      "hand_value_range",
      "中盤に同色副露が入り、打点レンジが上がる。",
    );

    expect(draft.nodes.map((node) => node.title)).toEqual(
      expect.arrayContaining([
        "進行度・聴牌率",
        "打点",
        "待ち・形の良さ",
        "点数状況・行動閾値",
      ]),
    );
    expect(draft.nodes.flatMap((node) => node.tags)).toEqual(
      expect.arrayContaining(["speed_axis", "shape_axis", "external_modifier"]),
    );
    expect(
      draft.nodes.some((node) => node.tags.includes("hand_value_range")),
    ).toBe(true);
  });

  it("creates rescue rate draft nodes with event bundle and observation candidate", () => {
    const draft = createMappingDraft(
      "rescue_rate",
      "一巡以内の脇救済率を見る。",
    );

    expect(draft.nodes.map((node) => node.title)).toContain("rescue_rate");
    expect(draft.nodes.map((node) => node.title)).toContain(
      "卓上動態 / 他家介入読み",
    );
    expect(draft.nodes.map((node) => node.type)).toContain(
      "probability_aggregate",
    );
    expect(draft.nodes.map((node) => node.type)).toContain(
      "observation_candidate",
    );
    expect(draft.edge_candidates.join(" ")).toContain("未配分候補");
    expect(draft.edge_candidates.join(" ")).not.toContain("push_value");
  });

  it("creates intermediate state nodes for collect through review", () => {
    const draft = createMappingDraft("intermediate_state", "判断過程を残す。");
    const tags = draft.nodes.flatMap((node) => node.tags);

    expect(tags).toEqual(
      expect.arrayContaining([
        "collect",
        "weight",
        "combine",
        "compare",
        "choose",
        "review",
      ]),
    );
  });
});
