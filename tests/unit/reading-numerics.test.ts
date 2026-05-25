import { describe, expect, it } from "vitest";
import { parseReadingNumericHints } from "../../src/domain/readingNumericParser";
import {
  applyReadingImpactDraftToWorkspace,
  buildReadingImpactPreview,
  createDefaultReadingImpactDraft,
} from "../../src/domain/readingNumerics";
import { seedWorkspace } from "../../src/domain/seed";

describe("reading numeric parser", () => {
  it("parses quick numeric notation", () => {
    const parsed = parseReadingNumericHints(
      "染め本線 p=60% confidence=0.65 打点+0.25 進行+0.10 keep_top_k=3",
    );

    expect(parsed.posterior_probability).toBe(0.6);
    expect(parsed.confidence).toBe(0.65);
    expect(parsed.lock_mode).toBe("keep_top_k");
    expect(parsed.lock_value).toBe(3);
    expect(parsed.axis_impacts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          axis_id: "value_axis",
          sign: "+",
          magnitude: 0.25,
        }),
        expect.objectContaining({
          axis_id: "progress_tenpai_axis",
          sign: "+",
          magnitude: 0.1,
        }),
      ]),
    );
  });

  it("parses percent axis values and mixed or unknown signs", () => {
    const parsed = parseReadingNumericHints(
      "聴牌率+15% 待ち・形=mixed 点数状況=unknown",
    );

    expect(parsed.axis_impacts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          axis_id: "progress_tenpai_axis",
          magnitude: 0.15,
        }),
        expect.objectContaining({
          axis_id: "wait_shape_quality_axis",
          sign: "mixed",
        }),
        expect.objectContaining({
          axis_id: "score_situation_threshold_axis",
          sign: "unknown",
        }),
      ]),
    );
  });
});

describe("reading numerics", () => {
  it("creates a default draft with four axes", () => {
    const draft = createDefaultReadingImpactDraft();

    expect(draft.axis_impacts.map((impact) => impact.axis_id)).toEqual([
      "progress_tenpai_axis",
      "value_axis",
      "wait_shape_quality_axis",
      "score_situation_threshold_axis",
    ]);
  });

  it("applies a reading draft to workspace nodes, edges, and active case", () => {
    const draft = createDefaultReadingImpactDraft();
    draft.title = "同色副露読み";
    draft.memo = "同色副露と手出し字牌で染め本線を上げる。";
    draft.axis_impacts = draft.axis_impacts.map((impact) =>
      impact.axis_id === "value_axis"
        ? { ...impact, enabled: true, sign: "+", magnitude: 0.25 }
        : { ...impact, enabled: false },
    );
    draft.choice_group = {
      label: "染め読み候補",
      normalize: true,
      candidates: [
        { label: "染め本線", posterior_probability: 0.55 },
        { label: "染め薄い", posterior_probability: 0.25 },
        { label: "速度副露", posterior_probability: 0.2 },
      ],
    };
    draft.pruning_policy = {
      action: "keep_top_k",
      top_k: 2,
      rationale: "複数候補を残す。",
    };

    const preview = buildReadingImpactPreview(seedWorkspace, draft);
    const next = applyReadingImpactDraftToWorkspace(seedWorkspace, draft);
    const readingNode = next.nodes.find((node) => node.title === "同色副露読み");
    const candidates = next.nodes.filter(
      (node) => node.choice_group_id && node.tags.includes("quick_reading"),
    );

    expect(readingNode).toEqual(
      expect.objectContaining({
        confidence: draft.confidence,
        lock_mode: "keep_top_k",
        lock_value: 2,
      }),
    );
    expect(preview.createdEdgeIds.length).toBeGreaterThan(0);
    expect(next.edges).toContainEqual(
      expect.objectContaining({
        source: readingNode?.id,
        relation_layer: "influence",
        sign: "+",
        magnitude: 0.25,
      }),
    );
    expect(candidates.reduce((sum, node) => sum + (node.posterior_probability ?? 0), 0)).toBe(1);
    expect(next.cases.find((caseItem) => caseItem.id === next.active_case_id)?.attached_node_ids).toContain(
      readingNode?.id,
    );
  });

  it("warns on mixed or unknown hard prune", () => {
    const draft = createDefaultReadingImpactDraft();
    draft.title = "危険な枝刈り";
    draft.pruning_policy.action = "hard_prune";
    draft.axis_impacts = draft.axis_impacts.map((impact) =>
      impact.axis_id === "wait_shape_quality_axis"
        ? { ...impact, enabled: true, sign: "unknown", magnitude: 0.4 }
        : { ...impact, enabled: false },
    );

    expect(buildReadingImpactPreview(seedWorkspace, draft).warnings).toContainEqual(
      expect.objectContaining({ code: "hard_prune_with_ambiguity" }),
    );
  });
});
