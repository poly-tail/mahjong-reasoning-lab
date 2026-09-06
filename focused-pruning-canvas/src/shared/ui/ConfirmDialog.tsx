import { useEffect, useRef } from 'react';
import type { Confirmation } from '../../features/EditorContext';
export function ConfirmDialog({
  confirmation,
  onClose,
}: {
  confirmation: Confirmation | null;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (confirmation && !ref.current?.open) ref.current?.showModal();
    if (!confirmation && ref.current?.open) ref.current.close();
  }, [confirmation]);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      aria-labelledby="confirm-title"
      className="confirm-dialog"
    >
      {confirmation && (
        <>
          <p className="eyebrow">操作の確認</p>
          <h2 id="confirm-title">{confirmation.title}</h2>
          <div className="confirm-body">{confirmation.body}</div>
          <div className="button-row">
            <button autoFocus onClick={onClose}>
              キャンセル
            </button>
            <button
              className="primary"
              onClick={() => {
                confirmation.onConfirm();
                onClose();
              }}
            >
              {confirmation.confirmLabel ?? '適用する'}
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}
