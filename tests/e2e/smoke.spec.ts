import { expect, test } from "@playwright/test";

test("loads the knowledge map and navigates primary screens", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "局面で考える" }),
  ).toBeVisible();
  await expect(page.getByText("この画面でできること")).toBeVisible();
  await expect(page.getByRole("heading", { name: "局面作業場" })).toBeVisible();

  await page.getByRole("button", { name: "知識を作る" }).click();
  await expect(page.getByRole("heading", { name: "知識を作る" })).toBeVisible();
  await expect(page.getByText("平均集中型の読み")).toBeVisible();

  const lensBar = page.getByRole("toolbar", { name: "レンズ切替" });
  await expect(lensBar.getByRole("button", { name: "意味" })).toBeVisible();
  await lensBar.getByRole("button", { name: "確率" }).click();
  await expect(lensBar.getByRole("button", { name: "確率" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await lensBar.getByRole("button", { name: "全部" }).click();
  await expect(lensBar.getByRole("button", { name: "全部" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.getByRole("button", { name: "凡例を畳む" }).click();
  await expect(page.getByRole("button", { name: "凡例を開く" })).toBeVisible();
  await page.getByRole("button", { name: "凡例を開く" }).click();

  const visibleNodeCount = page.getByText(/件のノードを表示/);
  const readVisibleNodeCount = async () => {
    const text = await visibleNodeCount.textContent();
    return Number(text?.match(/\d+/)?.[0] ?? 0);
  };
  const initialNodeCount = await readVisibleNodeCount();

  await page.getByRole("button", { name: "ノードパレットを畳む" }).click();
  await expect(
    page.getByRole("button", { name: "ノードパレットを開く" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "ノードパレットを開く" }).click();
  await expect(
    page.getByRole("button", { name: "ノードパレットを畳む" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "インスペクターを畳む" }).click();
  await expect(
    page.getByRole("button", { name: "インスペクターを開く" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "インスペクターを開く" }).click();
  await expect(
    page.getByRole("button", { name: "インスペクターを畳む" }),
  ).toBeVisible();

  const dragStart = await page
    .locator(".react-flow__node-knowledgeNode")
    .evaluateAll((nodes) => {
      for (const node of nodes) {
        const rect = node.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const topElement = document.elementFromPoint(x, y);
        if (topElement?.closest(".react-flow__node-knowledgeNode") === node) {
          return { x, y };
        }
      }
      return null;
    });
  if (!dragStart) throw new Error("Knowledge map node was not draggable.");
  await page.mouse.move(dragStart.x, dragStart.y);
  await page.mouse.down();
  await page.mouse.move(dragStart.x + 80, dragStart.y + 80, {
    steps: 6,
  });
  await expect(page.getByTestId("drop-preview")).toBeVisible();
  await page.mouse.up();
  await expect(page.getByTestId("drop-preview")).toHaveCount(0);

  await page.getByTitle("概念を追加").click();
  await expect.poll(readVisibleNodeCount).toBe(initialNodeCount + 1);

  await page.keyboard.press("Control+Z");
  await expect.poll(readVisibleNodeCount).toBe(initialNodeCount);

  await page.keyboard.press("Control+Y");
  await expect.poll(readVisibleNodeCount).toBe(initialNodeCount + 1);

  await expect(page.getByText("未保存")).toBeVisible();
  await expect(page.getByLabel("自動保存")).toHaveValue("5");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText(/保存済み/)).toBeVisible();

  await page.getByTitle("概念を追加").click();
  await expect.poll(readVisibleNodeCount).toBe(initialNodeCount + 2);
  await page.keyboard.press("Control+S");
  await expect(page.getByText(/保存済み/)).toBeVisible();

  const confidenceSlider = page.getByRole("slider", { name: "確信度" });
  await expect(confidenceSlider).toBeVisible();
  const sliderBox = await confidenceSlider.boundingBox();
  if (!sliderBox) throw new Error("Confidence slider was not measurable.");
  await page.mouse.move(sliderBox.x + sliderBox.width * 0.25, sliderBox.y + 8);
  await page.mouse.down();
  await page.mouse.move(sliderBox.x + sliderBox.width * 0.75, sliderBox.y + 8, {
    steps: 4,
  });
  await expect(confidenceSlider).toBeVisible();
  await page.mouse.up();
  await expect(confidenceSlider).toBeVisible();

  await page.getByRole("button", { name: "局面で考える" }).click();
  await expect(page.getByRole("heading", { name: "局面作業場" })).toBeVisible();

  await page.getByRole("button", { name: "知識を作る" }).click();
  await page
    .getByRole("toolbar", { name: "作成モード" })
    .getByRole("button", { name: "ルール作成" })
    .click();
  await expect(
    page.getByRole("heading", { name: "ルール作成ライト" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "枝刈りを検証する" }).click();
  await expect(page.getByRole("heading", { name: "選択候補群" })).toBeVisible();

  const validationToolbar = page.getByRole("toolbar", { name: "検証モード" });
  await validationToolbar.getByRole("button", { name: "影響モデル" }).click();
  await expect(page.getByRole("heading", { name: "指標レンズ" })).toBeVisible();

  await validationToolbar.getByRole("button", { name: "枝刈りラボ" }).click();
  await expect(
    page.getByRole("heading", { name: "枝刈り影響シミュレーター" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "読みを説明する" }).click();
  await expect(
    page.getByRole("heading", { name: "集中度レンズ" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "読み筋タイムライン" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "データ管理" }).click();
  await expect(
    page.getByRole("heading", { name: "ワークスペースデータ" }),
  ).toBeVisible();
});
