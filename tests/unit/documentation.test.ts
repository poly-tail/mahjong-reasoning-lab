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
    expect(requirements).toContain("候補木ビュー");
    expect(requirements).toContain("未展開の枝");
    expect(specification).toContain("4軸は読みの影響射影先");
    expect(specification).toContain("卓上動態 / 他家介入読み");
    expect(specification).toContain("候補木ビュー");
    expect(specification).toContain("例外の枝置き場");
    expect(requirements).toContain("観点横断補正時の未展開・例外確率");
    expect(requirements).toContain("4軸影響スコアを候補確率100%空間に混ぜない");
    expect(specification).toContain("横断補正後重み");
    expect(specification).toContain(
      "抽象読みだけで既存候補を自動的に大きく切りません",
    );
  });

  it("documents the current screen map and non-mutating scaffold boundaries", () => {
    const screen = read("docs/screen-specification.md");
    const requirements = read("docs/requirements-definition.md");
    const detailed = read("docs/detailed-specification.md");

    for (const label of [
      "局面で考える",
      "理論を整理する",
      "確率と枝刈り",
      "読みを検証する",
      "教材化する",
      "データ管理",
    ]) {
      expect(screen).toContain(label);
    }

    expect(screen).toContain(
      "現行の候補木ビューは投影・選択・警告プレビューです",
    );
    expect(screen).toContain(
      "Project / Globalへの永続ルーティングは将来接続です",
    );
    expect(requirements).toContain(
      "候補木から同じstore actionへ接続することは将来要件です",
    );
    expect(detailed).toContain("workspace mutationを接続していません");
  });

  it("documents the current Project and Sheet schema", () => {
    const schema = read("docs/schema.md");

    expect(schema).toContain("`projects`");
    expect(schema).toContain("`sheets`");
    expect(schema).toContain("`global_settings`");
    expect(schema).toContain("`scopeMode` is not a top-level field");
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
