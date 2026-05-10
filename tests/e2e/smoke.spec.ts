import { expect, test } from "@playwright/test";

test("loads the knowledge map and navigates primary screens", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Mahjong Reasoning Lab" }),
  ).toBeVisible();
  await expect(page.getByText("平均集中型の読み")).toBeVisible();

  await page.getByRole("button", { name: "Case Workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Case Workspace" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Rule Builder" }).click();
  await expect(
    page.getByRole("heading", { name: "Rule Builder Lite" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Probability" }).click();
  await expect(
    page.getByRole("heading", { name: "Choice Groups" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Influence" }).click();
  await expect(
    page.getByRole("heading", { name: "Metric Lens" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Reasoning Lab" }).click();
  await expect(
    page.getByRole("heading", { name: "Concentration Lens" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "JSON I/O" }).click();
  await expect(
    page.getByRole("heading", { name: "Workspace JSON" }),
  ).toBeVisible();
});
