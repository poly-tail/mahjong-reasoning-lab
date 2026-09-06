import { test, expect, type Page } from '@playwright/test';
import { STORAGE_KEY } from '../../src/infrastructure/LocalStorageRepository';
const pane = (page: Page) =>
  page.getByRole('complementary', { name: 'インスペクター' });
const outline = (page: Page) =>
  page.getByRole('complementary', { name: 'アウトライン' });
const current = (page: Page) =>
  page.evaluate((key) => {
    const env = JSON.parse(localStorage.getItem(key)!);
    return {
      doc: env.snapshots[env.cursor].document,
      cursor: env.cursor,
      count: env.snapshots.length,
    };
  }, STORAGE_KEY);
const errorsByPage = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page, context }) => {
  const errors: string[] = [];
  errorsByPage.set(page, errors);
  const track = (p: Page) => {
    p.on('pageerror', (e) => errors.push(e.message));
    p.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text());
    });
  };
  track(page);
  context.on('page', track);
  await page.goto('/');
  await expect(
    page.getByRole('status').filter({ hasText: '保存済み' }),
  ).toBeVisible();
});
test.afterEach(async ({ page }) => {
  expect(errorsByPage.get(page) ?? []).toEqual([]);
});
test('C06 C07 synthetic browser IME, text undo and scoped structural Tab', async ({
  page,
}) => {
  await outline(page)
    .getByRole('button', { name: '近くの対子・雀頭固定のラベルを編集' })
    .click();
  const label = outline(page).getByRole('textbox', { name: '項目ラベル' });
  await label.evaluate((e) =>
    e.dispatchEvent(
      new CompositionEvent('compositionstart', { bubbles: true }),
    ),
  );
  await label.fill('変換中');
  await label.evaluate((e) =>
    e.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Enter',
        isComposing: true,
        bubbles: true,
      }),
    ),
  );
  expect((await current(page)).count).toBe(1);
  expect((await current(page)).doc.hypotheses).toHaveLength(5);
  await label.evaluate((e) =>
    e.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })),
  );
  await label.press('Escape');
  expect((await current(page)).doc.hypotheses[0].label).toBe(
    '近くの対子・雀頭固定',
  );
  await outline(page).getByLabel('メモの構造編集').check();
  const note = outline(page).getByRole('button', {
    name: '後続観測',
    exact: true,
  });
  await note.focus();
  await note.press('Tab');
  await expect(note).toBeFocused();
  expect(
    (await current(page)).doc.notes.find((n: { id: string }) => n.id === 'N6')
      .parentNoteId,
  ).toBe('N2');
  await note.press('Shift+Tab');
  await expect(note).toBeFocused();
  expect(
    (await current(page)).doc.notes.find((n: { id: string }) => n.id === 'N6')
      .parentNoteId,
  ).toBeNull();
  await note.press('Escape');
  await expect(outline(page).getByLabel('メモの構造編集')).not.toBeChecked();
  await note.press('Tab');
  await expect(note).not.toBeFocused();
  await outline(page)
    .getByRole('button', {
      name: '関連牌構成率を対子固定支持と評価',
      exact: true,
    })
    .click();
  const before = await current(page);
  const confidence = pane(page).getByRole('spinbutton', {
    name: '根拠信頼度',
    exact: false,
  });
  await confidence.fill('');
  await expect(confidence).toHaveValue('');
  await confidence.fill('0.6');
  await pane(page).getByRole('button', { name: '要因の変更を保存' }).click();
  expect(await current(page)).toEqual(before);
  const name = pane(page).getByLabel('要因名', { exact: true });
  await name.fill('文字の編集中');
  await name.press('Control+z');
  expect((await current(page)).cursor).toBe(before.cursor);
});
test('B08 failed import and cancelled valid replacement preserve the current document and history', async ({
  page,
}) => {
  const before = await current(page);
  const raw = await page.evaluate(
    (key) => localStorage.getItem(key)!,
    STORAGE_KEY,
  );
  const input = page.getByLabel('JSONまたは専用Markdownを読み込む');
  await input.setInputFiles({
    name: 'bad.json',
    mimeType: 'application/json',
    buffer: Buffer.from('{broken'),
  });
  await expect(page.getByRole('alert')).toContainText('JSONを読み取れません');
  expect(await current(page)).toEqual(before);
  await input.setInputFiles({
    name: 'valid.json',
    mimeType: 'application/json',
    buffer: Buffer.from(raw),
  });
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'キャンセル' })
    .click();
  expect(await current(page)).toEqual(before);
  expect(
    await page.evaluate((key) => localStorage.getItem(key), STORAGE_KEY),
  ).toBe(raw);
});
test('B09 corrupt data raw export and explicit recovery preserve unrelated storage', async ({
  page,
}) => {
  await page.evaluate((key) => {
    localStorage.setItem('unrelated-app', 'keep');
    localStorage.setItem(key, '{corrupt');
  }, STORAGE_KEY);
  await page.reload();
  await expect(
    page.getByRole('heading', { name: '保存データを保全しています' }),
  ).toBeVisible();
  expect(
    await page.evaluate((key) => localStorage.getItem(key), STORAGE_KEY),
  ).toBe('{corrupt');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '破損データをrawで退避' }).click();
  expect((await download).suggestedFilename()).toBe(
    'focused-pruning-canvas.txt',
  );
  await page.getByRole('button', { name: '明示的に復旧', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'デモで復旧' })
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: '保存済み' }),
  ).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('unrelated-app'))).toBe(
    'keep',
  );
});
test('B10 real second-tab update pauses autosave until reload', async ({
  page,
  context,
}) => {
  const second = await context.newPage();
  await second.goto('/');
  await expect(
    second.getByRole('status').filter({ hasText: '保存済み' }),
  ).toBeVisible();
  await pane(page).getByRole('button', { name: '弱める', exact: true }).click();
  await expect(second.getByRole('alert')).toContainText('他タブ更新');
  const raw = await page.evaluate(
    (key) => localStorage.getItem(key),
    STORAGE_KEY,
  );
  await pane(second)
    .getByRole('button', { name: '弱める', exact: true })
    .click();
  expect(
    await second.evaluate((key) => localStorage.getItem(key), STORAGE_KEY),
  ).toBe(raw);
  await second.getByRole('button', { name: '保存データを再読込' }).click();
  await second
    .getByRole('dialog')
    .getByRole('button', { name: '適用する' })
    .click();
  await expect(
    second.getByRole('status').filter({ hasText: '保存済み' }),
  ).toBeVisible();
  await second.close();
});
