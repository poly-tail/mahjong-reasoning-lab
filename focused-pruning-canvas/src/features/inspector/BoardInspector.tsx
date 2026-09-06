import { useEditor } from '../EditorContext';
import { Field, InputField } from '../../shared/ui/FormField';
import { formText } from '../../shared/ui/formValues';

export function BoardInspector() {
  const { board, execute } = useEditor();
  return (
    <>
      <p className="eyebrow">BOARD / 考察</p>
      <h2>問いと考察を編集</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const f = new FormData(event.currentTarget);
          execute(
            {
              type: 'editBoard',
              patch: {
                title: formText(f, 'title'),
                question: formText(f, 'question'),
                classificationAssumption: formText(f, 'assumption'),
                decisionMemo: formText(f, 'decision'),
                reflectionMemo: formText(f, 'reflection'),
              },
            },
            '問いと考察を保存',
          );
        }}
      >
        <InputField
          label="考察タイトル"
          name="title"
          required
          maxLength={120}
          defaultValue={board.title}
        />
        <Field label="比較する問い">
          <textarea
            name="question"
            maxLength={4000}
            defaultValue={board.question}
          />
        </Field>
        <Field label="分類の仮定">
          <textarea
            name="assumption"
            rows={4}
            maxLength={4000}
            defaultValue={board.classificationAssumption}
          />
        </Field>
        <Field label="判断メモ">
          <textarea
            name="decision"
            maxLength={4000}
            defaultValue={board.decisionMemo}
          />
        </Field>
        <Field label="振り返り・留保">
          <textarea
            name="reflection"
            maxLength={4000}
            defaultValue={board.reflectionMemo}
          />
        </Field>
        <button className="primary" type="submit">
          問いと考察を保存
        </button>
      </form>
      <details>
        <summary>原文を追加</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const f = new FormData(event.currentTarget);
            execute(
              {
                type: 'editBoard',
                patch: {
                  sourceMaterials: [
                    ...board.sourceMaterials,
                    {
                      id: crypto.randomUUID(),
                      label: formText(f, 'label'),
                      text: formText(f, 'text'),
                    },
                  ],
                },
              },
              '原文を追加',
            );
          }}
        >
          <InputField
            label="原文の名前"
            name="label"
            maxLength={120}
            required
          />
          <Field
            label="原文の本文"
            hint="原文の合計は64,000文字まで。説明メモや要因から紐付けできます。"
          >
            <textarea name="text" required rows={6} maxLength={64000} />
          </Field>
          <button type="submit">原文を追加</button>
        </form>
      </details>
      <p className="help">
        モデル設定: scoreScale {board.modelConfig.scoreScale} / temperature{' '}
        {board.modelConfig.temperature}。JSON / 専用Markdown
        の設定値を評価へ反映します。
      </p>
    </>
  );
}
