import { useStore } from 'zustand';
import type { BoardStore } from '../application/boardStore';
import type { Confirmation } from '../features/EditorContext';
import { createSeed } from '../seed/ponDiscardCase';
import { downloadText } from '../infrastructure/browserFiles';
import { exportJson } from '../infrastructure/jsonTransfer';

type Props = {
  store: BoardStore;
  confirm: (confirmation: Confirmation) => void;
};
export function SaveMessages({ store, confirm }: Props) {
  const state = useStore(store);
  return (
    <>
      {state.error && (
        <div className="error-banner" role="alert">
          <p>{state.error}</p>
          <div className="button-row">
            {state.envelope && (
              <button
                onClick={() => {
                  try {
                    downloadText(exportJson(state.envelope!), 'json');
                  } catch (error) {
                    state.reportError(error);
                  }
                }}
              >
                JSONで退避
              </button>
            )}
            {state.status === 'unsaved' && (
              <button onClick={state.retrySave}>保存を再試行</button>
            )}
            {(state.status === 'conflict' || state.status === 'blocked') && (
              <button
                onClick={() =>
                  confirm({
                    title: '保存データを再読込',
                    body: (
                      <p>
                        メモリの編集が保存データへ置き換わります。必要なら先にJSONで退避してください。
                      </p>
                    ),
                    onConfirm: state.reload,
                  })
                }
              >
                保存データを再読込
              </button>
            )}
            {state.importBackup && (
              <button onClick={state.restoreImportBackup}>
                import前の内容に戻す
              </button>
            )}
          </div>
        </div>
      )}
      {state.notice && (
        <div className="notice-banner" role="status">
          <span>{state.notice}</span>
          {state.rawData !== null && (
            <button onClick={() => downloadText(state.rawData!, 'txt')}>
              復旧前のrawを退避
            </button>
          )}
          <button onClick={state.dismissNotice}>閉じる</button>
        </div>
      )}
    </>
  );
}
export function RecoveryPanel({ store, confirm }: Props) {
  const state = useStore(store);
  return (
    <main className="recovery">
      <p className="eyebrow">LOCAL DATA RECOVERY</p>
      <h2>保存データを保全しています</h2>
      <p role="alert">{state.error}</p>
      <p>読み込めないデータをデモで上書きせず、自動保存を停止しています。</p>
      <div className="button-row">
        {state.rawData !== null && (
          <button onClick={() => downloadText(state.rawData!, 'txt')}>
            破損データをrawで退避
          </button>
        )}
        <button onClick={state.reload}>読込を再試行</button>
        <button
          onClick={() =>
            confirm({
              title: 'デモで明示的に復旧',
              body: (
                <p>
                  本アプリ専用の保存データを置き換えます。必要なら先にrawデータを退避してください。他アプリのデータは対象外です。
                </p>
              ),
              confirmLabel: 'デモで復旧',
              onConfirm: () => state.recover(createSeed()),
            })
          }
        >
          明示的に復旧
        </button>
      </div>
    </main>
  );
}
