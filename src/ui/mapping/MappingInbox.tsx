import { CheckSquare, Layers3, Link2, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  createMappingDraft,
  mappingTemplates,
  type MappingDraftNode,
  type MappingTemplateId,
} from "../../domain/mappingTemplates";
import { parseReadingNumericHints } from "../../domain/readingNumericParser";
import {
  nodeTypeLabels,
  pruningHintLabels,
  probabilityRoleLabels,
  relationLayerLabels,
} from "../../domain/labels";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";

const placeholder =
  "例: 中盤に同色副露が入り、手出し字牌が続いた場合、染め本線の打点レンジが上がる。ただし副露進行や役牌バックも残るため、染め薄い仮説を完全に消すのではなく downweight に留める。";

export function MappingInbox() {
  const createKnowledgeNodesFromDrafts = useAppStore(
    (state) => state.createKnowledgeNodesFromDrafts,
  );
  const activeCase = useAppStore((state) => {
    const doc = state.doc;
    return doc.cases.find((item) => item.id === doc.active_case_id) ?? doc.cases[0];
  });
  const [text, setText] = useState("");
  const [templateId, setTemplateId] =
    useState<MappingTemplateId>("hand_value_range");
  const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);

  const draftResult = useMemo(
    () => createMappingDraft(templateId, text),
    [templateId, text],
  );
  const numericHints = useMemo(() => parseReadingNumericHints(text), [text]);
  const allSelected =
    selectedDraftIds.length === 0
      ? draftResult.nodes
      : draftResult.nodes.filter((node) =>
          selectedDraftIds.includes(node.draft_id),
        );

  const toggleDraft = (draftId: string) => {
    setSelectedDraftIds((current) =>
      current.includes(draftId)
        ? current.filter((id) => id !== draftId)
        : [...current, draftId],
    );
  };

  const createNodes = (attachToCase: boolean) => {
    createKnowledgeNodesFromDrafts(allSelected, attachToCase);
    setSelectedDraftIds([]);
  };

  return (
    <main className="grid min-h-0 flex-1 grid-cols-[minmax(360px,0.9fr)_1.2fr] gap-3 p-3">
      <section className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="border-b border-stone-200 px-3 py-2">
          <h2 className="text-sm font-semibold text-stone-950">
            Mapping Inbox
          </h2>
          <p className="mt-1 text-xs leading-5 text-stone-500">
            ChatGPTやnoteで書いた麻雀考察を貼り、テンプレートに沿って知識ノード案へ変換します。
          </p>
        </div>
        <div className="grid gap-3 p-3">
          <Field label="考察メモを貼り付け">
            <Textarea
              className="min-h-64"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={placeholder}
            />
          </Field>
          <Field label="テンプレート">
            <Select
              value={templateId}
              onChange={(event) => {
                setTemplateId(event.target.value as MappingTemplateId);
                setSelectedDraftIds([]);
              }}
            >
              {mappingTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.label}
                </option>
              ))}
            </Select>
          </Field>
          <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm leading-6 text-stone-700">
            {
              mappingTemplates.find((template) => template.id === templateId)
                ?.description
            }
          </div>
          <NumericHintsPanel hints={numericHints} />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              onClick={() => setSelectedDraftIds([])}
              title="選択なしの場合は全下書きが作成対象です"
            >
              <Layers3 className="h-4 w-4" aria-hidden="true" />
              下書きノード案を作る
            </Button>
            <Button
              onClick={() => createNodes(false)}
              disabled={draftResult.nodes.length === 0}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              選択したノードを作成
            </Button>
            <Button
              onClick={() => createNodes(true)}
              disabled={!activeCase || draftResult.nodes.length === 0}
              title={activeCase ? activeCase.title : "ケースがありません"}
            >
              <Link2 className="h-4 w-4" aria-hidden="true" />
              ケースに紐づけて作成
            </Button>
            <Button
              variant="ghost"
              onClick={() => createNodes(false)}
              disabled={draftResult.nodes.length === 0}
            >
              知識マップにだけ作成
            </Button>
          </div>
        </div>
      </section>

      <section className="min-h-0 overflow-auto">
        <Panel
          title="下書きノード案"
          action={
            <Badge tone="cyan">
              {allSelected.length}/{draftResult.nodes.length}件
            </Badge>
          }
        >
          <div className="grid gap-3 p-3">
            <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm leading-6 text-stone-700">
              <span className="font-medium text-stone-900">要約: </span>
              {draftResult.source_summary}
            </div>
            <div className="grid gap-2">
              {draftResult.nodes.map((node) => (
                <DraftNodeCard
                  key={node.draft_id}
                  node={node}
                  selected={
                    selectedDraftIds.length === 0 ||
                    selectedDraftIds.includes(node.draft_id)
                  }
                  onToggle={() => toggleDraft(node.draft_id)}
                />
              ))}
            </div>
            <div className="rounded-md border border-stone-200 p-3">
              <h3 className="mb-2 text-sm font-semibold text-stone-900">
                relation / influence edge candidates
              </h3>
              <div className="grid gap-1 text-sm text-stone-600">
                {draftResult.edge_candidates.map((candidate) => (
                  <div key={candidate} className="flex items-center gap-2">
                    <CheckSquare
                      className="h-4 w-4 text-cyan-700"
                      aria-hidden="true"
                    />
                    <span>{candidate}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Panel>
      </section>
    </main>
  );
}

function NumericHintsPanel({
  hints,
}: {
  hints: ReturnType<typeof parseReadingNumericHints>;
}) {
  const hasHints =
    hints.confidence !== undefined ||
    hints.prior_probability !== undefined ||
    hints.posterior_probability !== undefined ||
    hints.base_weight !== undefined ||
    hints.dynamic_weight !== undefined ||
    hints.lock_mode !== undefined ||
    (hints.axis_impacts?.length ?? 0) > 0 ||
    hints.pruning_action !== undefined ||
    hints.warnings.length > 0;

  if (!hasHints) {
    return (
      <div className="rounded-md border border-stone-200 bg-white p-3 text-xs leading-5 text-stone-500">
        数値記法がある場合はここに表示します。例: p=60% confidence=0.65
        打点+0.25 進行+0.10 keep_top_k=3
      </div>
    );
  }

  return (
    <div className="rounded-md border border-cyan-200 bg-cyan-50/50 p-3">
      <div className="mb-2 text-sm font-semibold text-stone-900">
        数値ヒント
      </div>
      <div className="flex flex-wrap gap-1 text-xs">
        {hints.confidence !== undefined ? (
          <Badge>confidence {formatPercent(hints.confidence)}</Badge>
        ) : null}
        {hints.prior_probability !== undefined ? (
          <Badge>prior {formatPercent(hints.prior_probability)}</Badge>
        ) : null}
        {hints.posterior_probability !== undefined ? (
          <Badge>posterior {formatPercent(hints.posterior_probability)}</Badge>
        ) : null}
        {hints.base_weight !== undefined ? (
          <Badge>base {hints.base_weight}</Badge>
        ) : null}
        {hints.dynamic_weight !== undefined ? (
          <Badge>dynamic {hints.dynamic_weight}</Badge>
        ) : null}
        {hints.lock_mode ? <Badge>lock {hints.lock_mode}</Badge> : null}
        {hints.lock_value !== undefined ? (
          <Badge>lock value {hints.lock_value}</Badge>
        ) : null}
        {hints.pruning_action ? (
          <Badge tone="amber">{hints.pruning_action}</Badge>
        ) : null}
        {hints.axis_impacts?.map((impact) => (
          <Badge key={impact.axis_id} tone="cyan">
            {impact.axis_id} {impact.sign} {impact.magnitude}
          </Badge>
        ))}
      </div>
      {hints.warnings.length > 0 ? (
        <div className="mt-2 grid gap-1 text-xs text-amber-700">
          {hints.warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function formatPercent(value: number) {
  return `${Math.round(value * 1000) / 10}%`;
}

function DraftNodeCard({
  node,
  selected,
  onToggle,
}: {
  node: MappingDraftNode;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <article className="rounded-md border border-stone-200 bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <label className="flex min-w-0 items-start gap-2">
          <input
            className="mt-1"
            type="checkbox"
            checked={selected}
            onChange={onToggle}
          />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-stone-950">
              {node.title}
            </span>
            <span className="mt-1 block text-xs leading-5 text-stone-600">
              {node.summary}
            </span>
          </span>
        </label>
        <Badge tone="cyan">{nodeTypeLabels[node.type]}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {node.tags.slice(0, 8).map((tag) => (
          <Badge key={tag}>{tag}</Badge>
        ))}
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-stone-600">
        <span>probability: {probabilityRoleLabels[node.probability_role ?? "none"]}</span>
        <span>
          relation:{" "}
          {relationLayerLabels[node.relation_layer_candidate ?? "semantic"]}
        </span>
        <span>
          pruning:{" "}
          {node.pruning_hints?.length
            ? node.pruning_hints.map((hint) => pruningHintLabels[hint]).join(", ")
            : "なし"}
        </span>
      </div>
    </article>
  );
}
