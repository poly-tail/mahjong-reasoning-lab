import { Download, FileUp, RefreshCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  createPruningSubgraphExport,
  parseWorkspaceJson,
  serializePruningExport,
  serializeWorkspace,
} from "../../domain/export";
import { getScopedIds } from "../../domain/projectSheets";
import {
  PRUNING_EXPORT_SCHEMA_VERSION,
  WORKSPACE_SCHEMA_VERSION,
  type WorkspaceScopeMode,
} from "../../domain/schema";
import { downloadJson, readFileAsText } from "../../infrastructure/files";
import { Button } from "../components/button";
import { Field, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";

function stamp() {
  return new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
}

type SubgraphExportScope = WorkspaceScopeMode | "selection";

export function ImportExportPanel() {
  const doc = useAppStore((state) => state.doc);
  const selectedNodeIds = useAppStore((state) => state.selectedNodeIds);
  const selectedEdgeIds = useAppStore((state) => state.selectedEdgeIds);
  const importDocument = useAppStore((state) => state.importDocument);
  const resetToSeed = useAppStore((state) => state.resetToSeed);
  const [importText, setImportText] = useState("");
  const [message, setMessage] = useState("");
  const [subgraphScope, setSubgraphScope] =
    useState<SubgraphExportScope>("selection");

  const workspaceJson = useMemo(() => serializeWorkspace(doc), [doc]);
  const subgraphSelection = useMemo(() => {
    if (subgraphScope === "selection") {
      return { nodeIds: selectedNodeIds, edgeIds: selectedEdgeIds };
    }
    const ids = getScopedIds(doc, subgraphScope);
    return {
      nodeIds: Array.from(ids.nodeIds),
      edgeIds: Array.from(ids.edgeIds),
    };
  }, [doc, selectedEdgeIds, selectedNodeIds, subgraphScope]);
  const pruningJson = useMemo(() => {
    if (
      subgraphSelection.nodeIds.length === 0 &&
      subgraphSelection.edgeIds.length === 0
    ) {
      return "";
    }
    return serializePruningExport(
      createPruningSubgraphExport(
        doc,
        subgraphSelection.nodeIds,
        subgraphSelection.edgeIds,
      ),
    );
  }, [doc, subgraphSelection]);

  const importFromText = () => {
    try {
      importDocument(parseWorkspaceJson(importText));
      setMessage("ワークスペースデータを取り込みました。");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "取り込みに失敗しました。",
      );
    }
  };

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_420px] gap-3 p-3">
      <main className="grid min-h-0 gap-3">
        <Panel title="ワークスペースデータ">
          <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2 text-sm text-stone-600">
            <span>{WORKSPACE_SCHEMA_VERSION}</span>
            <Button
              onClick={() =>
                downloadJson(
                  `mahjong-knowledge-workspace-${stamp()}.json`,
                  workspaceJson,
                )
              }
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              全体を出力
            </Button>
          </div>
          <Textarea
            className="h-[330px] rounded-none border-0 font-mono text-xs focus:ring-0"
            value={workspaceJson}
            readOnly
          />
        </Panel>

        <Panel title="枝刈り画面向けサブグラフ出力">
          <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2 text-sm text-stone-600">
            <span>
              {PRUNING_EXPORT_SCHEMA_VERSION} /{" "}
              {subgraphSelection.nodeIds.length}
              件のノード、{subgraphSelection.edgeIds.length}件のエッジ
            </span>
            <Select
              className="ml-2 w-40"
              value={subgraphScope}
              onChange={(event) =>
                setSubgraphScope(event.target.value as SubgraphExportScope)
              }
            >
              <option value="selection">選択範囲</option>
              <option value="sheet">active Sheet</option>
              <option value="project">active Project</option>
              <option value="workspace">Workspace</option>
            </Select>
            <Button
              disabled={!pruningJson}
              onClick={() =>
                downloadJson(`pruning-subgraph-${stamp()}.json`, pruningJson)
              }
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              選択範囲を出力
            </Button>
          </div>
          <Textarea
            className="h-[260px] rounded-none border-0 font-mono text-xs focus:ring-0"
            value={
              pruningJson ||
              "知識マップでノードまたはエッジを選択すると、サブグラフ出力が生成されます。"
            }
            readOnly
          />
        </Panel>
      </main>

      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="border-b border-stone-200 px-3 py-2">
          <h2 className="text-sm font-semibold text-stone-950">
            取り込み / 初期化
          </h2>
        </div>
        <div className="grid gap-3 p-3">
          <Field label="ワークスペースデータを取り込み">
            <Textarea
              className="min-h-80 font-mono text-xs"
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Button onClick={importFromText} disabled={!importText.trim()}>
              <FileUp className="h-4 w-4" aria-hidden="true" />
              テキスト取り込み
            </Button>
            <label className="inline-flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-stone-300 bg-white px-2.5 text-sm font-medium text-stone-800 hover:bg-stone-100">
              <FileUp className="h-4 w-4" aria-hidden="true" />
              ファイル
              <input
                className="hidden"
                type="file"
                accept="application/json,.json"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  const text = await readFileAsText(file);
                  setImportText(text);
                  try {
                    importDocument(parseWorkspaceJson(text));
                    setMessage(`${file.name}を取り込みました。`);
                  } catch (error) {
                    setMessage(
                      error instanceof Error
                        ? error.message
                        : "取り込みに失敗しました。",
                    );
                  }
                }}
              />
            </label>
          </div>
          <Button variant="danger" onClick={resetToSeed}>
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            初期データに戻す
          </Button>
          {message ? (
            <div className="rounded-lg border border-stone-200 bg-stone-50 p-2 text-sm text-stone-700">
              {message}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
