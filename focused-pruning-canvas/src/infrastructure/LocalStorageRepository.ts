import type { Repository, Result } from '../application/ports';
import { importJson } from './jsonTransfer';
export const STORAGE_KEY = 'focused-pruning-canvas.v1';
type StoragePort = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
export class LocalStorageRepository implements Repository {
  constructor(private readonly getStorage: () => StoragePort) {}
  load(): Result<string | null> {
    try {
      return { ok: true, value: this.getStorage().getItem(STORAGE_KEY) };
    } catch (error) {
      return this.failure(error);
    }
  }
  save(raw: string, expectedRaw: string | null): Result<void> {
    try {
      importJson(raw);
      const storage = this.getStorage();
      // Exact raw comparison also checks the revision and catches deletion/corruption.
      if (storage.getItem(STORAGE_KEY) !== expectedRaw)
        return {
          ok: false,
          kind: 'conflict',
          error:
            '他タブの更新を検出しました。自動保存を停止しました。先にexportしてから再読込してください',
        };
      storage.setItem(STORAGE_KEY, raw);
      return { ok: true, value: undefined };
    } catch (error) {
      return this.failure(error);
    }
  }
  removeOwnData(expectedRaw: string | null): Result<void> {
    try {
      const storage = this.getStorage();
      if (storage.getItem(STORAGE_KEY) !== expectedRaw)
        return {
          ok: false,
          kind: 'conflict',
          error: '復旧前に別の更新がありました。再読込してください',
        };
      storage.removeItem(STORAGE_KEY);
      return { ok: true, value: undefined };
    } catch (error) {
      return this.failure(error);
    }
  }
  private failure(error: unknown): Result<never> {
    return {
      ok: false,
      kind: 'storage',
      error: `保存領域にアクセスできません (${error instanceof Error ? error.message : String(error)})。メモリの内容をJSONで退避してください`,
    };
  }
}
