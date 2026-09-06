import { useEditor } from '../EditorContext';
export function SourceReferences({ refs }: { refs: string[] }) {
  const { board } = useEditor();
  return (
    <details>
      <summary>
        根拠原文 <span>{refs.length}</span>
      </summary>
      {refs.length === 0 ? (
        <p className="help">
          原文の紐付けなし。問いの編集から原文を追加できます。
        </p>
      ) : (
        refs.map((id) => {
          const s = board.sourceMaterials.find((s) => s.id === id);
          return s ? (
            <div key={id}>
              <h4>{s.label}</h4>
              <p className="source-text">{s.text}</p>
            </div>
          ) : null;
        })
      )}
      <p className="help">
        思考素材として保全しています。麻雀理論・頻度は未検証。「246から2か4切り」は要確認。
      </p>
    </details>
  );
}
