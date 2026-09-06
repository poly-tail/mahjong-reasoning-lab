import { History } from 'lucide-react';
import { useEditor } from '../EditorContext';
import { compareBoards } from '../../domain/deltas';

export function TimelinePanel() {
  const { state } = useEditor();
  const env = state.envelope!;
  return (
    <section className="timeline" aria-label="操作履歴">
      <div className="timeline-heading">
        <h2>
          <History size={16} />
          操作履歴
        </h2>
        <span>
          {env.cursor + 1} / {env.snapshots.length}
        </span>
        <small>直近50件 / 2MiB · 保存対象は上限内の履歴</small>
      </div>
      <div className="timeline-items">
        {env.snapshots.map((snapshot, i) => {
          const deltas =
            i > 0
              ? compareBoards(env.snapshots[i - 1].document, snapshot.document)
              : [];
          const changed = [...deltas].sort(
            (a, b) => Math.abs(b.shareDelta) - Math.abs(a.shareDelta),
          )[0];
          const deltaText =
            changed && Math.abs(changed.shareDelta) > 1e-12
              ? `${snapshot.document.hypotheses.find((h) => h.id === changed.id)?.label} ${(changed.shareDelta * 100).toFixed(1)} pt`
              : '配分の変化なし';
          return (
            <button
              key={snapshot.id}
              className={`timeline-item ${i === env.cursor ? 'current' : ''} ${i > env.cursor ? 'future' : ''}`}
              aria-current={i === env.cursor ? 'step' : undefined}
              onClick={() => state.jump(i)}
            >
              <span>
                <i />
                {i === env.cursor ? '現在' : String(i + 1).padStart(2, '0')}
                <time>
                  {new Date(snapshot.timestamp).toLocaleTimeString('ja-JP', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </time>
              </span>
              <strong>{snapshot.actionLabel}</strong>
              <small>{i === 0 ? '考察の開始' : deltaText}</small>
            </button>
          );
        })}
      </div>
    </section>
  );
}
