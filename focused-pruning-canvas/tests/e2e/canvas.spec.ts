import { test, expect, type Page } from '@playwright/test';
import { STORAGE_KEY } from '../../src/infrastructure/LocalStorageRepository';

const inspector = (page: Page) =>
  page.getByRole('complementary', { name: 'インスペクター' });
const outline = (page: Page) =>
  page.getByRole('complementary', { name: 'アウトライン' });
const diagnostics = new WeakMap<Page, string[]>();
async function documentState(page: Page) {
  return page.evaluate((key) => {
    const env = JSON.parse(localStorage.getItem(key)!);
    return {
      document: env.snapshots[env.cursor].document,
      cursor: env.cursor,
      count: env.snapshots.length,
    };
  }, STORAGE_KEY);
}
async function selectFactor(page: Page, label: string) {
  await outline(page).getByRole('button', { name: label, exact: true }).click();
  await expect(
    inspector(page).getByRole('heading', { name: label, exact: true }),
  ).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  diagnostics.set(page, errors);
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/');
  await expect(
    page.getByRole('status').filter({ hasText: '保存済み' }),
  ).toBeVisible();
  test.info().annotations.push({
    type: 'console-check',
    description: 'pageerror / console.error monitored',
  });
});
test.afterEach(async ({ page }) => {
  expect(diagnostics.get(page) ?? []).toEqual([]);
});
test('C01 C02 C08 initial model, reasons, screenshots at both viewports', async ({
  page,
}) => {
  await expect(
    inspector(page).getByRole('heading', { name: '両面固定', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('相対配分（未校正）', { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText('主枝の太さ ∝ √配分（非線形）')).toBeVisible();
  await expect(
    page
      .locator('.react-flow__node[data-id="H1"]')
      .getByText('58.2%', { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator('.react-flow__node[data-id="H5"]')
      .getByText('13.0%', { exact: true }),
  ).toBeVisible();
  await expect(
    inspector(page).getByRole('button', { name: 'prune', exact: true }),
  ).toBeDisabled();
  await expect(inspector(page).getByText('なぜ薄いか')).toBeVisible();
  await inspector(page).getByText('同根抑制', { exact: false }).first().click();
  await expect(
    inspector(page)
      .getByText(/同根抑制: 構成自由度不足/)
      .first(),
  ).toBeVisible();
  await inspector(page)
    .getByText('何なら復活するか / 成立条件', { exact: true })
    .click();
  await expect(
    inspector(page).getByText('AND', { exact: true }).first(),
  ).toBeVisible();
  await inspector(page).getByText('根拠原文', { exact: false }).first().click();
  await expect(
    inspector(page)
      .getByText(/ポン出しがポン出し牌近くの対子固定が多い/)
      .first(),
  ).toBeVisible();
  await inspector(page).evaluate((element) => {
    element.querySelector('.inspector-body')!.scrollTop = 0;
  });
  await page.screenshot({
    path: 'test-results/canvas-1440x900.png',
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(
    page.getByRole('navigation', { name: 'ペイン切替' }),
  ).toBeVisible();
  await expect(inspector(page)).toBeVisible();
  await page.getByRole('button', { name: '全体を表示', exact: true }).click();
  await page.screenshot({
    path: 'test-results/canvas-1280x800.png',
    fullPage: true,
  });
  await page
    .getByRole('navigation')
    .getByRole('button', { name: 'アウトライン', exact: true })
    .click();
  await expect(outline(page)).toBeVisible();
  await page
    .getByRole('navigation')
    .getByRole('button', { name: 'インスペクター', exact: true })
    .click();
  await expect(inspector(page)).toBeVisible();
  await expect(outline(page)).toBeHidden();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
test('C03 C09 factor scenario, stable viewport, timeline, undo/redo/reload', async ({
  page,
}) => {
  const node = page.locator('.react-flow__node[data-id="H2"]');
  await expect(node).toBeVisible();
  const initialPosition = await node.getAttribute('style');
  const viewport = await page
    .locator('.react-flow__viewport')
    .getAttribute('style');
  await selectFactor(page, '聴牌している');
  await inspector(page).getByLabel('要因の状態').selectOption('present');
  await inspector(page)
    .getByRole('button', { name: '要因の変更を保存' })
    .click();
  await selectFactor(page, '3飜以上の高打点が見込める');
  await inspector(page).getByLabel('要因の状態').selectOption('present');
  await inspector(page)
    .getByRole('button', { name: '要因の変更を保存' })
    .click();
  expect(await node.getAttribute('style')).toBe(initialPosition);
  expect(
    await page.locator('.react-flow__viewport').getAttribute('style'),
  ).toBe(viewport);
  expect((await documentState(page)).cursor).toBe(2);
  await expect(
    page
      .getByRole('region', { name: '操作履歴' })
      .getByText('3飜以上の高打点が見込めるを変更', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  expect(
    (await documentState(page)).document.factors.find(
      (f: { id: string }) => f.id === 'F6',
    ).state,
  ).toBe('absent');
  await page.getByRole('button', { name: 'Redo', exact: true }).click();
  await page.reload();
  expect(
    (await documentState(page)).document.factors.find(
      (f: { id: string }) => f.id === 'F6',
    ).state,
  ).toBe('present');
  expect((await documentState(page)).cursor).toBe(2);
});
test('C04 empty board authoring, hierarchy, JSON and Markdown import/export through UI', async ({
  page,
}) => {
  await page.getByRole('button', { name: '新規', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '適用する' })
    .click();
  await inspector(page).getByLabel('比較する問い').fill('自分の仮説は何か');
  await inspector(page)
    .getByRole('button', { name: '問いと考察を保存' })
    .click();
  await outline(page)
    .getByRole('button', { name: '仮説を追加', exact: true })
    .click();
  await inspector(page).getByText('仮説の編集', { exact: true }).click();
  await inspector(page)
    .getByLabel('仮説名', { exact: true })
    .fill('自分の仮説');
  await inspector(page)
    .getByRole('button', { name: '仮説の変更を保存' })
    .click();
  await outline(page)
    .getByRole('button', { name: '要因を追加', exact: true })
    .click();
  await inspector(page)
    .getByLabel('要因名', { exact: true })
    .fill('自分の観察');
  await inspector(page).getByLabel('要因の状態').selectOption('present');
  await inspector(page)
    .getByRole('button', { name: '要因の変更を保存' })
    .click();
  await inspector(page)
    .getByLabel('接続先の仮説')
    .selectOption({ label: '自分の仮説' });
  await inspector(page)
    .getByRole('button', { name: '接続を追加', exact: true })
    .click();
  await outline(page)
    .getByRole('button', { name: '自分の仮説にメモを追加', exact: true })
    .click();
  await inspector(page).getByLabel('メモのタイトル').fill('親の説明');
  await inspector(page).getByLabel('メモの本文').fill('数値に混ぜない説明');
  await inspector(page)
    .getByRole('button', { name: 'メモの変更を保存' })
    .click();
  await inspector(page).getByRole('button', { name: '子メモを追加' }).click();
  await inspector(page).getByLabel('メモのタイトル').fill('子の説明');
  await inspector(page)
    .getByRole('button', { name: 'メモの変更を保存' })
    .click();
  const authored = await documentState(page);
  expect(authored.document.effects).toHaveLength(1);
  expect(authored.document.notes[1].parentNoteId).toBe(
    authored.document.notes[0].id,
  );
  for (const format of ['JSON', 'Markdown']) {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: format, exact: true }).click();
    const downloaded = await downloadPromise;
    const path = await downloaded.path();
    expect(path).toBeTruthy();
    await page.getByRole('button', { name: 'デモへ戻す', exact: true }).click();
    await page
      .getByRole('dialog')
      .getByRole('button', { name: '適用する' })
      .click();
    const fs = await import('node:fs/promises');
    await page.getByLabel('JSONまたは専用Markdownを読み込む').setInputFiles({
      name: format === 'Markdown' ? 'board.md' : 'board.json',
      mimeType: format === 'Markdown' ? 'text/markdown' : 'application/json',
      buffer: await fs.readFile(path!),
    });
    await page
      .getByRole('dialog')
      .getByRole('button', { name: '読み込みを適用' })
      .click();
    expect((await documentState(page)).document).toEqual(authored.document);
    expect((await documentState(page)).cursor).toBe(authored.cursor);
  }
});
test('C05 protected buttons and normal prune preview, cancel and restore', async ({
  page,
}) => {
  await outline(page)
    .getByRole('button', { name: '近くの対子・雀頭固定', exact: true })
    .click();
  const before = await documentState(page);
  await inspector(page)
    .getByRole('button', { name: 'prune', exact: true })
    .click();
  await expect(
    page.getByRole('dialog').getByRole('columnheader', { name: '変更後' }),
  ).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'キャンセル' })
    .click();
  expect(await documentState(page)).toEqual(before);
  await inspector(page)
    .getByRole('button', { name: 'prune', exact: true })
    .click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'pruneを適用' })
    .click();
  await expect(
    inspector(page).getByText('手動pruneで計算対象外', { exact: true }),
  ).toBeVisible();
  await inspector(page)
    .getByRole('button', { name: '復元', exact: true })
    .click();
  expect((await documentState(page)).document).toEqual(before.document);
});
