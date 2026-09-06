import { createStore } from 'zustand/vanilla';
import type { BoardDocument, Envelope } from '../domain/model';
import type { Command } from '../domain/commands';
import { parseEnvelope } from '../domain/validation';
import type { Repository } from './ports';
import {
  commit,
  createEnvelope,
  moveCursor,
  type CommandMetadata,
} from './history';

export type SaveStatus = 'saved' | 'unsaved' | 'blocked' | 'conflict';
export interface BoardState {
  envelope: Envelope | null;
  status: SaveStatus;
  error: string | null;
  notice: string | null;
  rawData: string | null;
  importBackup: Envelope | null;
  execute(command: Command, label: string): boolean;
  undo(): void;
  redo(): void;
  jump(cursor: number): void;
  retrySave(): void;
  reload(): void;
  recover(document: BoardDocument): void;
  importEnvelope(envelope: Envelope): void;
  restoreImportBackup(): void;
  externalChange(raw: string | null): void;
  reportError(error: unknown): void;
  dismissNotice(): void;
}
export function createBoardStore(
  repository: Repository,
  initial: () => BoardDocument,
  metadata: (label: string) => CommandMetadata,
) {
  let lastRaw: string | null = null;
  let paused = false;
  const message = (error: unknown) =>
    error instanceof Error ? error.message : String(error);
  const store = createStore<BoardState>((set, get) => {
    function persist(envelope: Envelope): boolean {
      if (paused) {
        set({
          envelope,
          status: get().status === 'conflict' ? 'conflict' : 'blocked',
        });
        return false;
      }
      const next = { ...envelope, revision: metadata('保存').revision };
      const raw = JSON.stringify(parseEnvelope(next));
      const result = repository.save(raw, lastRaw);
      if (result.ok) {
        lastRaw = raw;
        set({ envelope: next, status: 'saved', error: null });
        return true;
      }
      paused = result.kind === 'conflict';
      set({
        envelope: next,
        status: paused ? 'conflict' : 'unsaved',
        error: result.error,
      });
      return false;
    }
    function reload(): void {
      const result = repository.load();
      if (!result.ok) {
        paused = true;
        set({ status: 'blocked', error: result.error });
        return;
      }
      lastRaw = result.value;
      if (result.value === null) {
        paused = false;
        try {
          persist(createEnvelope(initial(), metadata('デモを開始')));
          set({ rawData: null, importBackup: null });
        } catch (error) {
          get().reportError(error);
        }
        return;
      }
      try {
        const envelope = parseEnvelope(JSON.parse(result.value) as unknown);
        paused = false;
        set({
          envelope,
          status: 'saved',
          error: null,
          rawData: null,
          importBackup: null,
        });
      } catch (error) {
        paused = true;
        set({
          status: 'blocked',
          error: `保存データを復元できません。自動保存を停止しています。${message(error)}`,
          rawData: result.value,
        });
      }
    }
    function jump(cursor: number): void {
      const envelope = get().envelope;
      if (!envelope) return;
      const next = moveCursor(envelope, cursor);
      if (next !== envelope) persist(next);
    }
    return {
      envelope: null,
      status: 'blocked',
      error: null,
      notice: null,
      rawData: null,
      importBackup: null,
      execute(command, label) {
        const envelope = get().envelope;
        if (!envelope) return false;
        try {
          const result = commit(envelope, command, metadata(label));
          if (result.envelope === envelope) return true;
          persist(result.envelope);
          if (result.trimmed)
            set({
              notice:
                '保存対象は件数・容量内の直近履歴です。50件 / 2MiB の上限に合わせて古い履歴を短縮しました。現在の本文は保全しています。',
            });
          return true;
        } catch (error) {
          set({ error: message(error) });
          return false;
        }
      },
      undo() {
        const e = get().envelope;
        if (e) jump(e.cursor - 1);
      },
      redo() {
        const e = get().envelope;
        if (e) jump(e.cursor + 1);
      },
      jump,
      retrySave() {
        const e = get().envelope;
        if (e && !paused) persist(e);
      },
      reload,
      recover(document) {
        try {
          const envelope = createEnvelope(document, metadata('明示的に復旧'));
          const removed = repository.removeOwnData(lastRaw);
          if (!removed.ok) {
            set({ error: removed.error });
            return;
          }
          paused = false;
          lastRaw = null;
          persist(envelope);
          set({
            notice:
              '明示的な復旧を実行しました。元のrawデータはこの画面を離れるまで退避できます。',
          });
        } catch (error) {
          set({ error: message(error) });
        }
      },
      importEnvelope(input) {
        try {
          const envelope = parseEnvelope(input);
          const backup = get().envelope;
          set({ importBackup: backup });
          if (persist(envelope))
            set({
              importBackup: null,
              notice:
                'ファイルの履歴へ置き換えました。以前の履歴とは統合していません。',
            });
        } catch (error) {
          set({ error: message(error) });
        }
      },
      restoreImportBackup() {
        const backup = get().importBackup;
        if (backup) {
          persist(backup);
          set({
            importBackup: null,
            notice:
              'import直前の内容へ戻しました。保存状態を確認してください。',
          });
        }
      },
      externalChange(raw) {
        if (raw !== lastRaw) {
          paused = true;
          set({
            status: 'conflict',
            error:
              '他タブ更新を検出しました。自動保存を停止中です。現在の編集をJSONで退避してから、保存データを再読込してください。',
          });
        }
      },
      reportError(error) {
        set({ error: message(error) });
      },
      dismissNotice() {
        set({ notice: null });
      },
    };
  });
  store.getState().reload();
  return store;
}
export type BoardStore = ReturnType<typeof createBoardStore>;
