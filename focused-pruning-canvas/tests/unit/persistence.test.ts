import { describe, expect, it } from 'vitest';
import {
  LocalStorageRepository,
  STORAGE_KEY,
} from '../../src/infrastructure/LocalStorageRepository';
import { createBoardStore } from '../../src/application/boardStore';
import { createSeed } from '../../src/seed/ponDiscardCase';
import { createEnvelope, currentDocument } from '../../src/application/history';
import type { Envelope } from '../../src/domain/model';

function fixture(raw: string | null = null) {
  const values = new Map<string, string>([['unrelated-app', 'safe']]);
  if (raw !== null) values.set(STORAGE_KEY, raw);
  let fail = false;
  let writes = 0;
  let ids = 0;
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      if (fail) throw new DOMException('quota', 'QuotaExceededError');
      writes++;
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
  };
  const repository = new LocalStorageRepository(() => storage);
  const metadata = (actionLabel: string) => ({
    id: `snap-${++ids}`,
    revision: `rev-${ids}`,
    timestamp: '2026-09-05T00:00:00.000Z',
    actionLabel,
  });
  return {
    values,
    repository,
    metadata,
    make: () => createBoardStore(repository, createSeed, metadata),
    fail: () => {
      fail = true;
    },
    writes: () => writes,
  };
}
describe('B08–10 storage failure, recovery, multi-tab and imports', () => {
  it('initializes once; reload and two application mounts do not grow history or resave', () => {
    const f = fixture();
    const first = f.make();
    const second = f.make();
    expect(f.writes()).toBe(1);
    expect(first.getState().envelope).toEqual(second.getState().envelope);
    first.getState().reload();
    expect(f.writes()).toBe(1);
    first.getState().execute({ type: 'weaken', id: 'H1' }, '弱める');
    const next = f.make();
    expect(
      currentDocument(next.getState().envelope!).hypotheses[0].manualAdjustment,
    ).toBe(-1);
  });
  it('corrupt data is not overwritten; explicit recovery affects only own key', () => {
    const f = fixture('{corrupt');
    const s = f.make();
    expect(s.getState().envelope).toBeNull();
    expect(s.getState().status).toBe('blocked');
    expect(s.getState().rawData).toBe('{corrupt');
    expect(f.values.get(STORAGE_KEY)).toBe('{corrupt');
    expect(f.writes()).toBe(0);
    s.getState().recover(createSeed());
    expect(s.getState().status).toBe('saved');
    expect(f.values.get('unrelated-app')).toBe('safe');
  });
  it('quota failure preserves edited in-memory data; invalid imports leave all data alone', () => {
    const f = fixture();
    const s = f.make();
    const oldRaw = f.values.get(STORAGE_KEY);
    const before = s.getState().envelope;
    s.getState().importEnvelope({ bad: true } as unknown as Envelope);
    expect(s.getState().envelope).toBe(before);
    expect(f.values.get(STORAGE_KEY)).toBe(oldRaw);
    f.fail();
    s.getState().execute({ type: 'weaken', id: 'H1' }, '弱める');
    expect(s.getState().status).toBe('unsaved');
    expect(f.values.get(STORAGE_KEY)).toBe(oldRaw);
    expect(
      currentDocument(s.getState().envelope!).hypotheses[0].manualAdjustment,
    ).toBe(-1);
  });
  it('storage acquisition security failure is caught', () => {
    const repo = new LocalStorageRepository(() => {
      throw new DOMException('denied', 'SecurityError');
    });
    expect(repo.load().ok).toBe(false);
    const s = createBoardStore(repo, createSeed, () => ({
      id: 'id',
      revision: 'rev',
      timestamp: '2026-09-05T00:00:00.000Z',
      actionLabel: 'x',
    }));
    expect(s.getState().status).toBe('blocked');
    expect(s.getState().error).toContain('denied');
  });
  it('revision is checked before write, and storage events pause further writes', () => {
    const f = fixture();
    const a = f.make(),
      b = f.make();
    a.getState().execute({ type: 'weaken', id: 'H1' }, 'a');
    const raw = f.values.get(STORAGE_KEY);
    b.getState().execute({ type: 'weaken', id: 'H3' }, 'b');
    expect(b.getState().status).toBe('conflict');
    expect(f.values.get(STORAGE_KEY)).toBe(raw);
    b.getState().externalChange(raw ?? null);
    b.getState().execute({ type: 'weaken', id: 'H4' }, 'c');
    expect(f.values.get(STORAGE_KEY)).toBe(raw);
  });
  it('successful import replaces history; failed save keeps import backup and revert', () => {
    const f = fixture(),
      s = f.make();
    const imported = createEnvelope(createSeed(), {
      ...f.metadata('import'),
      id: 'import-snapshot',
    });
    imported.snapshots[0].document.title = 'import title';
    s.getState().importEnvelope(imported);
    expect(s.getState().envelope?.snapshots[0].id).toBe('import-snapshot');
    const before = s.getState().envelope!;
    f.fail();
    const next = structuredClone(imported);
    next.snapshots[0].document.title = 'failed save';
    s.getState().importEnvelope(next);
    expect(s.getState().importBackup).toEqual(before);
    expect(s.getState().status).toBe('unsaved');
    s.getState().restoreImportBackup();
    expect(currentDocument(s.getState().envelope!).title).toBe('import title');
  });
});
