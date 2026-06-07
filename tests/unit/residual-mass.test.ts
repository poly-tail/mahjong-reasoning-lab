import { describe, expect, it } from "vitest";
import {
  buildResidualMassSummary,
  calculateResidualMass,
  createExceptionCandidateNode,
  createResidualBucketNode,
  normalizeCandidates,
  shouldBlockHardPrune,
} from "../../src/domain/residualMass";
import type { ChoiceCandidateDraft } from "../../src/domain/readingNumerics";

const candidates = (...values: number[]): ChoiceCandidateDraft[] =>
  values.map((value, index) => ({
    label: `候補${index + 1}`,
    posterior_probability: value,
  }));

describe("residual mass", () => {
  it("calculates 15% residual when candidates total 85%", () => {
    expect(calculateResidualMass(candidates(0.55, 0.2, 0.1))).toBe(0.15);
  });

  it("calculates zero residual when candidates total 100%", () => {
    expect(calculateResidualMass(candidates(0.55, 0.25, 0.2))).toBe(0);
  });

  it("warns when candidates are overallocated", () => {
    const summary = buildResidualMassSummary(candidates(0.7, 0.5));

    expect(summary.overallocated_probability).toBe(0.2);
    expect(summary.warnings).toContainEqual(
      expect.objectContaining({ code: "overallocated_probability" }),
    );
  });

  it("warns at 15% residual and blocks hard prune at 25%", () => {
    const warning = buildResidualMassSummary(candidates(0.55, 0.2, 0.1));
    const danger = buildResidualMassSummary(candidates(0.5, 0.25), undefined, [], {
      hardPrune: true,
    });

    expect(warning.warnings).toContainEqual(
      expect.objectContaining({ code: "residual_warning" }),
    );
    expect(danger.warnings).toContainEqual(
      expect.objectContaining({ code: "residual_hard_prune_warning" }),
    );
    expect(shouldBlockHardPrune(danger)).toBe(true);
  });

  it("normalizes candidates while retaining raw values", () => {
    const normalized = normalizeCandidates(candidates(0.55, 0.2, 0.1));

    expect(normalized.map((candidate) => candidate.raw_probability)).toEqual([
      0.55, 0.2, 0.1,
    ]);
    expect(
      normalized.reduce(
        (sum, candidate) => sum + (candidate.posterior_probability ?? 0),
        0,
      ),
    ).toBeCloseTo(1);
    expect(normalized[0].normalized_probability).toBeCloseTo(0.6471);
  });

  it("defaults to keep_unknown_buffer and only normalizes on explicit policy", () => {
    const keep = buildResidualMassSummary(candidates(0.55, 0.2, 0.1));
    const normalized = buildResidualMassSummary(
      candidates(0.55, 0.2, 0.1),
      "normalize_existing",
    );

    expect(keep.policy).toBe("keep_unknown_buffer");
    expect(keep.buckets[0].kind).toBe("unknown_buffer");
    expect(normalized.warnings).toContainEqual(
      expect.objectContaining({ code: "explicit_normalization" }),
    );
  });

  it("creates residual and exception nodes using existing schema fields", () => {
    const summary = buildResidualMassSummary(candidates(0.55, 0.2, 0.1));
    const residualNode = createResidualBucketNode(summary);
    const exceptionNode = createExceptionCandidateNode({
      id: "bucket_exception",
      label: "空切り",
      kind: "exception",
      probability: 0.15,
      tags: ["exception_noise"],
    });

    expect(residualNode.type).toBe("ambiguity_marker");
    expect(residualNode.tags).toContain("residual_mass");
    expect(exceptionNode.type).toBe("exception");
    expect(exceptionNode.pruning_hints).toContain("must_keep_top_k");
  });
});
