import { describe, expect, it } from "vitest";
import {
  createChoiceCandidateFromDrawerItem,
  createExceptionDraftFromDrawerItem,
  createResidualBucketFromDrawerItem,
  findReadingDrawerItem,
  readingDrawerCategories,
  readingDrawerItems,
} from "../../src/domain/readingDrawer";

describe("reading drawer", () => {
  it("defines the requested reading categories", () => {
    const categoryIds = readingDrawerCategories.map((category) => category.id);

    expect(categoryIds).toEqual(
      expect.arrayContaining([
        "call_intent",
        "value_pattern",
        "wait_shape",
        "exception_noise",
      ]),
    );
    expect(readingDrawerItems.length).toBeGreaterThan(30);
  });

  it("contains concrete drawer items for core categories", () => {
    expect(findReadingDrawerItem("call_intent_速度副露")).toBeDefined();
    expect(findReadingDrawerItem("value_pattern_染め")).toBeDefined();
    expect(findReadingDrawerItem("wait_shape_待ち候補不明")).toBeDefined();
    expect(findReadingDrawerItem("exception_noise_観測ミス")).toBeDefined();
  });

  it("converts drawer items to choice candidate drafts", () => {
    const item = findReadingDrawerItem("call_intent_速度副露");
    expect(item).toBeDefined();

    const candidate = createChoiceCandidateFromDrawerItem(item!, 0.08);

    expect(candidate).toEqual(
      expect.objectContaining({
        label: "速度副露",
        posterior_probability: 0.08,
        base_weight: 0.08,
      }),
    );
    expect(candidate.tags).toEqual(
      expect.arrayContaining(["reading_drawer", "call_intent"]),
    );
  });

  it("creates exception buckets and exception draft nodes", () => {
    const item = findReadingDrawerItem("exception_noise_観測ミス");
    expect(item).toBeDefined();

    const bucket = createResidualBucketFromDrawerItem(item!, 0.05);
    const draft = createExceptionDraftFromDrawerItem(item!, 0.05);

    expect(bucket.kind).toBe("exception");
    expect(draft.type).toBe("exception");
    expect(draft.tags).toEqual(
      expect.arrayContaining(["exception", "residual_mass", "reading_drawer"]),
    );
  });
});
