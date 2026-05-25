import { expect, test } from "@playwright/test";

test("runs the judgment workbench smoke flow", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "局面で考える" }),
  ).toBeVisible();
  await expect(page.getByText("この画面でできること")).toBeVisible();
  await expect(page.getByRole("heading", { name: "局面作業場" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "読みを数値で反映" }),
  ).toBeVisible();
  await page.getByLabel("読みタイトル").fill("E2E 同色副露の数値読み");
  await page.getByRole("button", { name: "プレビュー" }).first().click();
  await expect(page.getByText(/作成予定ノード/)).toBeVisible();
  await page.getByRole("button", { name: "active caseに反映" }).first().click();

  await page.getByRole("button", { name: "理論を整理する" }).click();
  await expect(
    page.getByRole("heading", { name: "理論を整理する" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mapping Inbox" })).toBeVisible();

  await page
    .getByLabel("考察メモを貼り付け")
    .fill("一巡以内の脇救済率を上限レンジとして扱い、他力期待を過大評価しない。");
  await page.getByLabel("テンプレート").selectOption("rescue_rate");
  await expect(page.getByText("脇救済イベント束")).toBeVisible();
  await page.getByRole("button", { name: "ケースに紐づけて作成" }).click();

  await page
    .getByRole("toolbar", { name: "整理モード" })
    .getByRole("button", { name: "知識マップ" })
    .click();
  const lensBar = page.getByRole("toolbar", { name: "レンズ切替" });
  await expect(lensBar.getByRole("button", { name: "全部" })).toBeVisible();
  await lensBar.getByRole("button", { name: "脇救済" }).click();
  await expect(lensBar.getByRole("button", { name: "脇救済" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByRole("button", { name: "凡例を開く" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "マッピングガイドを開く" }),
  ).toBeVisible();

  await page
    .getByRole("toolbar", { name: "整理モード" })
    .getByRole("button", { name: "手牌価値" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "進行度・聴牌率 / 打点 / 待ち・形の良さ / 点数状況・行動閾値のどこが動いたか",
    }),
  ).toBeVisible();

  await page
    .getByRole("toolbar", { name: "整理モード" })
    .getByRole("button", { name: "脇救済率" })
    .click();
  await expect(page.getByRole("heading", { name: "脇救済率" })).toBeVisible();

  await page.getByRole("button", { name: "局面で考える" }).click();
  await page.getByRole("button", { name: /判断プロセス/ }).click();
  await expect(page.getByText("洗い出し")).toBeVisible();
  await expect(page.getByText("この局面で足りない要素")).toBeVisible();

  await page.getByRole("button", { name: "確率と枝刈り" }).click();
  await expect(page.getByRole("heading", { name: "選択候補群" })).toBeVisible();
  await expect(page.getByText("E2E 同色副露の数値読み")).toBeVisible();
  const validationToolbar = page.getByRole("toolbar", { name: "検証モード" });
  await validationToolbar.getByRole("button", { name: "枝刈りラボ" }).click();
  await expect(
    page.getByRole("heading", { name: "枝刈り影響シミュレーター" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "操作の違い" })).toBeVisible();
  await validationToolbar.getByRole("button", { name: "影響モデル" }).click();
  await expect(page.getByRole("heading", { name: "指標レンズ" })).toBeVisible();

  await page.getByRole("button", { name: "読みを検証する" }).click();
  await expect(page.getByRole("heading", { name: "集中度レンズ" })).toBeVisible();
  await expect(page.getByRole("button", { name: "ロック分析" })).toBeVisible();

  await page.getByRole("button", { name: "教材化する" }).click();
  await expect(page.getByRole("heading", { name: "教育用説明" })).toBeVisible();

  await page.getByRole("button", { name: "データ管理" }).click();
  await expect(
    page.getByRole("heading", { name: "ワークスペースデータ" }),
  ).toBeVisible();
  await expect(
    page.getByRole("main").getByText("mahjong-knowledge-map.workspace.v4", {
      exact: true,
    }),
  ).toBeVisible();
});
