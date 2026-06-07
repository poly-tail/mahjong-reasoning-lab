import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function read(path: string) {
  return readFileSync(resolve(root, path), "utf8");
}

describe("documentation scope", () => {
  it("documents Reading Probability Core scope and four-axis scoring", () => {
    const requirements = read("docs/requirements-definition.md");
    const specification = read("docs/detailed-specification.md");

    expect(requirements).toContain("Reading Probability Core");
    expect(requirements).toContain("Phase1非スコープ");
    expect(requirements).toContain("4軸の合計を100にする必要はありません");
    expect(specification).toContain("4軸は読みの影響射影先");
    expect(specification).toContain("卓上動態 / 他家介入読み");
  });

  it("keeps README PDF commands aligned with scripts", () => {
    const readme = read("README.md");
    const commands = [
      "scripts/render-requirements-pdf.mjs",
      "scripts/render-specification-pdf.mjs",
      "scripts/render-user-specification-pdf.mjs",
      "scripts/render-user-guide-pdf.mjs",
    ];

    for (const command of commands) {
      expect(readme).toContain(`node ${command}`);
      expect(existsSync(resolve(root, command))).toBe(true);
    }
  });
});
