import { useRef } from 'react';
import {
  Undo2,
  Redo2,
  FilePlus2,
  RotateCcw,
  Download,
  Upload,
} from 'lucide-react';
import { useEditor, type Density } from '../EditorContext';
import { createSeed, emptyBoard } from '../../seed/ponDiscardCase';
import { exportJson, importJson } from '../../infrastructure/jsonTransfer';
import {
  exportMarkdown,
  importMarkdown,
} from '../../infrastructure/markdownTransfer';
import { downloadText, readFile } from '../../infrastructure/browserFiles';

export function Toolbar() {
  const editor = useEditor();
  const { state, execute, confirm, setDensity, density, select } = editor;
  const input = useRef<HTMLInputElement>(null);
  function exportFile(format: 'json' | 'md') {
    try {
      if (state.envelope)
        downloadText(
          format === 'json'
            ? exportJson(state.envelope)
            : exportMarkdown(state.envelope),
          format,
        );
    } catch (error) {
      state.reportError(error);
    }
  }
  function replace(demo: boolean) {
    confirm({
      title: demo ? 'デモへ戻しますか' : '空のBoardを作成しますか',
      body: (
        <p>
          現在の考察を{demo ? 'デモ' : '問いと残余枝だけのBoard'}
          へ置き換えます。履歴に一操作として残り、Undoできます。
        </p>
      ),
      onConfirm: () => {
        const document = demo
          ? createSeed()
          : emptyBoard(crypto.randomUUID(), crypto.randomUUID());
        if (
          execute(
            { type: 'replace', document },
            demo ? 'デモへ戻す' : '空のBoardを作成',
          )
        )
          select({ kind: 'board', id: document.id });
      },
    });
  }
  return (
    <div className="toolbar" aria-label="編集ツールバー">
      <div className="tool-group">
        <button
          aria-label="Undo"
          disabled={!state.envelope || state.envelope.cursor === 0}
          onClick={state.undo}
        >
          <Undo2 size={16} />
        </button>
        <button
          aria-label="Redo"
          disabled={
            !state.envelope ||
            state.envelope.cursor === state.envelope.snapshots.length - 1
          }
          onClick={state.redo}
        >
          <Redo2 size={16} />
        </button>
      </div>
      <div className="tool-group">
        <button onClick={() => replace(false)}>
          <FilePlus2 size={15} />
          新規
        </button>
        <button onClick={() => replace(true)}>
          <RotateCcw size={14} />
          デモへ戻す
        </button>
      </div>
      <div className="tool-group">
        <button onClick={() => exportFile('json')}>
          <Download size={14} />
          JSON
        </button>
        <button onClick={() => exportFile('md')}>
          <Download size={14} />
          Markdown
        </button>
        <button onClick={() => input.current?.click()}>
          <Upload size={14} />
          読込
        </button>
        <input
          ref={input}
          className="visually-hidden"
          aria-label="JSONまたは専用Markdownを読み込む"
          type="file"
          accept=".json,.md,.markdown,application/json,text/markdown"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = '';
            if (!file) return;
            void readFile(file)
              .then((raw) => {
                const envelope = /\.md$|\.markdown$/i.test(file.name)
                  ? importMarkdown(raw)
                  : importJson(raw);
                confirm({
                  title: 'ファイルの履歴へ置換',
                  body: (
                    <>
                      <p>
                        「{envelope.snapshots[envelope.cursor].document.title}
                        」の履歴 {envelope.snapshots.length}{' '}
                        件へ置き換えます。現在の履歴とは統合しません。
                      </p>
                      <p>
                        Markdown本文の編集は復元に反映されず、埋込データが正本です。
                      </p>
                      <button onClick={() => exportFile('json')}>
                        現在の内容を先にJSONで退避
                      </button>
                    </>
                  ),
                  confirmLabel: '読み込みを適用',
                  onConfirm: () => {
                    state.importEnvelope(envelope);
                    select({
                      kind: 'board',
                      id: envelope.snapshots[envelope.cursor].document.id,
                    });
                  },
                });
              })
              .catch(state.reportError);
          }}
        />
      </div>
      <div className="density-control" role="group" aria-label="表示密度">
        {(
          [
            ['conclusion', '結論'],
            ['standard', '標準'],
            ['expanded', '全展開'],
          ] as [Density, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            aria-pressed={density === value}
            onClick={() => setDensity(value)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
