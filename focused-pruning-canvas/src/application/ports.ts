export type Result<T> =
  | { ok: true; value: T }
  | { ok: false; error: string; kind: 'storage' | 'conflict' };
export interface Repository {
  load(): Result<string | null>;
  save(raw: string, expectedRaw: string | null): Result<void>;
  removeOwnData(expectedRaw: string | null): Result<void>;
}
