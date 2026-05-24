import { useEffect, useRef, useState } from "react";
import { Box, ChevronDown, ChevronRight, Link2, Trash2 } from "lucide-react";
import { useAppStore } from "../../app/store";
import {
  edgeTypeLabels,
  nodeTypeLabels,
  pruningHintLabels,
  sourceTypeLabels,
} from "../../domain/labels";
import {
  edgeTypes,
  nodeTypes,
  pruningHints,
  sourceTypes,
  type KnowledgeEdge,
  type KnowledgeNode,
  type PruningHint,
} from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";

type Threshold = KnowledgeNode["thresholds"][number];

type RangeFieldProps = {
  label: string;
  value: number;
  onCommit: (value: number) => void;
};

function RangeField({ label, value, onCommit }: RangeFieldProps) {
  const [draft, setDraft] = useState<number | null>(null);
  const committedValue = useRef(value);
  const visibleValue = draft ?? value;

  useEffect(() => {
    committedValue.current = value;
  }, [value]);

  const commit = () => {
    if (draft === null) return;
    setDraft(null);
    const next = Number(draft.toFixed(4));
    if (next === committedValue.current) return;
    committedValue.current = next;
    onCommit(next);
  };

  return (
    <Field label={`${label} ${Math.round(visibleValue * 100)}%`}>
      <input
        aria-label={label}
        type="range"
        min="0"
        max="1"
        step="0.05"
        value={visibleValue}
        onPointerDown={() => setDraft((current) => current ?? value)}
        onKeyDown={() => setDraft((current) => current ?? value)}
        onChange={(event) => {
          setDraft(Number(event.target.value));
        }}
        onPointerUp={commit}
        onPointerCancel={commit}
        onKeyUp={commit}
        onBlur={commit}
      />
    </Field>
  );
}

function toCsv(values: string[]) {
  return values.join(", ");
}

function fromCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toLines(values: string[]) {
  return values.join("\n");
}

function fromLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function thresholdsToText(thresholds: Threshold[]) {
  return thresholds
    .map(
      (threshold) =>
        `${threshold.name}=${threshold.value}${threshold.note ? ` | ${threshold.note}` : ""}`,
    )
    .join("\n");
}

function textToThresholds(value: string): Threshold[] {
  return fromLines(value).map((line, index) => {
    const [left, note = ""] = line.split("|").map((part) => part.trim());
    const [name, thresholdValue = ""] = left
      .split("=")
      .map((part) => part.trim());
    return {
      name: name || `threshold_${index + 1}`,
      value: thresholdValue,
      note,
    };
  });
}

export function Inspector() {
  const doc = useAppStore((state) => state.doc);
  const selectedNodeIds = useAppStore((state) => state.selectedNodeIds);
  const selectedEdgeIds = useAppStore((state) => state.selectedEdgeIds);
  const updateNode = useAppStore((state) => state.updateNode);
  const updateRule = useAppStore((state) => state.updateRule);
  const updateEdge = useAppStore((state) => state.updateEdge);
  const deleteEdge = useAppStore((state) => state.deleteEdge);
  const toggleGroupCollapsed = useAppStore(
    (state) => state.toggleGroupCollapsed,
  );

  const node =
    selectedNodeIds.length === 1
      ? doc.nodes.find((item) => item.id === selectedNodeIds[0])
      : undefined;
  const edge =
    selectedEdgeIds.length === 1
      ? doc.edges.find((item) => item.id === selectedEdgeIds[0])
      : undefined;

  if (node) {
    const toggleHint = (hint: PruningHint) => {
      const next = node.pruning_hints.includes(hint)
        ? node.pruning_hints.filter((item) => item !== hint)
        : [...node.pruning_hints, hint];
      updateNode(node.id, { pruning_hints: next });
    };

    const toggleRule = (ruleId: string) => {
      const hasRule = node.related_rule_ids.includes(ruleId);
      const nextRelated = hasRule
        ? node.related_rule_ids.filter((id) => id !== ruleId)
        : [...node.related_rule_ids, ruleId];
      updateNode(node.id, { related_rule_ids: nextRelated });
      const rule = doc.rules.find((item) => item.id === ruleId);
      if (!rule) return;
      updateRule(rule.id, {
        target_node_ids: hasRule
          ? rule.target_node_ids.filter((id) => id !== node.id)
          : [...rule.target_node_ids, node.id],
      });
    };

    return (
      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
          <h2 className="truncate text-sm font-semibold text-stone-950">
            インスペクター
          </h2>
          {node.is_group ? (
            <Button size="sm" onClick={() => toggleGroupCollapsed(node.id)}>
              {node.collapsed ? (
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              ) : (
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
              )}
              {node.collapsed ? "展開" : "折りたたみ"}
            </Button>
          ) : null}
        </div>

        <div className="grid gap-3 p-3">
          <div className="flex items-center gap-2">
            <Box className="h-4 w-4 text-stone-500" aria-hidden="true" />
            <Badge tone={node.is_group ? "amber" : "cyan"}>
              {node.is_group ? "セクション" : nodeTypeLabels[node.type]}
            </Badge>
            <span className="truncate text-xs text-stone-500">{node.id}</span>
          </div>

          <Field label="タイトル">
            <Input
              value={node.title}
              onChange={(event) =>
                updateNode(node.id, { title: event.target.value })
              }
            />
          </Field>

          <div className="grid grid-cols-2 gap-2">
            <Field label="種類">
              <Select
                value={node.type}
                onChange={(event) =>
                  updateNode(node.id, {
                    type: event.target.value as KnowledgeNode["type"],
                  })
                }
              >
                {nodeTypes.map((type) => (
                  <option key={type} value={type}>
                    {nodeTypeLabels[type]}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="出典">
              <Select
                value={node.source_type}
                onChange={(event) =>
                  updateNode(node.id, {
                    source_type: event.target
                      .value as KnowledgeNode["source_type"],
                  })
                }
              >
                {sourceTypes.map((type) => (
                  <option key={type} value={type}>
                    {sourceTypeLabels[type]}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label="要約">
            <Textarea
              className="min-h-16"
              value={node.summary}
              onChange={(event) =>
                updateNode(node.id, { summary: event.target.value })
              }
            />
          </Field>
          <Field label="説明">
            <Textarea
              value={node.description}
              onChange={(event) =>
                updateNode(node.id, { description: event.target.value })
              }
            />
          </Field>

          <div className="grid grid-cols-2 gap-2">
            <RangeField
              label="確信度"
              value={node.confidence}
              onCommit={(confidence) => updateNode(node.id, { confidence })}
            />
            <RangeField
              label="再現性"
              value={node.reproducibility}
              onCommit={(reproducibility) =>
                updateNode(node.id, { reproducibility })
              }
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Field label="段階">
              <Input
                value={node.stage}
                onChange={(event) =>
                  updateNode(node.id, { stage: event.target.value })
                }
              />
            </Field>
            <Field label="主体">
              <Input
                value={node.actor}
                onChange={(event) =>
                  updateNode(node.id, { actor: event.target.value })
                }
              />
            </Field>
          </div>

          <Field label="タグ" hint="カンマ区切り">
            <Input
              value={toCsv(node.tags)}
              onChange={(event) =>
                updateNode(node.id, { tags: fromCsv(event.target.value) })
              }
            />
          </Field>
          <Field label="適用条件" hint="カンマ区切り">
            <Input
              value={toCsv(node.applicability)}
              onChange={(event) =>
                updateNode(node.id, {
                  applicability: fromCsv(event.target.value),
                })
              }
            />
          </Field>

          <Field label="式" hint="1行に1つ">
            <Textarea
              value={toLines(node.formulas)}
              onChange={(event) =>
                updateNode(node.id, { formulas: fromLines(event.target.value) })
              }
            />
          </Field>
          <Field label="閾値" hint="名前=値 | メモ">
            <Textarea
              value={thresholdsToText(node.thresholds)}
              onChange={(event) =>
                updateNode(node.id, {
                  thresholds: textToThresholds(event.target.value),
                })
              }
            />
          </Field>

          <Field label="メモ">
            <Textarea
              value={node.notes}
              onChange={(event) =>
                updateNode(node.id, { notes: event.target.value })
              }
            />
          </Field>

          <section className="grid gap-2 rounded-lg border border-stone-200 p-2">
            <h3 className="text-sm font-semibold text-stone-900">
              枝刈りヒント
            </h3>
            <div className="grid gap-1">
              {pruningHints.map((hint) => (
                <label
                  key={hint}
                  className="flex items-center gap-2 text-sm text-stone-700"
                >
                  <input
                    type="checkbox"
                    checked={node.pruning_hints.includes(hint)}
                    onChange={() => toggleHint(hint)}
                  />
                  <span>{pruningHintLabels[hint]}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="grid gap-2 rounded-lg border border-stone-200 p-2">
            <h3 className="text-sm font-semibold text-stone-900">関連ルール</h3>
            <div className="grid gap-1">
              {doc.rules.map((rule) => (
                <label
                  key={rule.id}
                  className="flex items-start gap-2 text-sm text-stone-700"
                >
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={node.related_rule_ids.includes(rule.id)}
                    onChange={() => toggleRule(rule.id)}
                  />
                  <span className="min-w-0 truncate">{rule.name}</span>
                </label>
              ))}
            </div>
          </section>
        </div>
      </aside>
    );
  }

  if (edge) {
    return (
      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
          <h2 className="truncate text-sm font-semibold text-stone-950">
            エッジインスペクター
          </h2>
          <Button
            size="sm"
            variant="danger"
            onClick={() => deleteEdge(edge.id)}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            削除
          </Button>
        </div>
        <div className="grid gap-3 p-3">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-stone-500" aria-hidden="true" />
            <span className="truncate text-xs text-stone-500">{edge.id}</span>
          </div>
          <Field label="関係">
            <Select
              value={edge.type}
              onChange={(event) =>
                updateEdge(edge.id, {
                  type: event.target.value as KnowledgeEdge["type"],
                })
              }
            >
              {edgeTypes.map((type) => (
                <option key={type} value={type}>
                  {edgeTypeLabels[type]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="ラベル">
            <Input
              value={edge.label}
              onChange={(event) =>
                updateEdge(edge.id, { label: event.target.value })
              }
            />
          </Field>
          <Field label="メモ">
            <Textarea
              value={edge.notes}
              onChange={(event) =>
                updateEdge(edge.id, { notes: event.target.value })
              }
            />
          </Field>
        </div>
      </aside>
    );
  }

  return (
    <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
      <div className="border-b border-stone-200 px-3 py-2">
        <h2 className="text-sm font-semibold text-stone-950">インスペクター</h2>
      </div>
      <div className="grid gap-3 p-3 text-sm text-stone-600">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-stone-200 p-2">
            <div className="text-xs text-stone-500">ノード</div>
            <div className="text-lg font-semibold text-stone-950">
              {doc.nodes.length}
            </div>
          </div>
          <div className="rounded-lg border border-stone-200 p-2">
            <div className="text-xs text-stone-500">エッジ</div>
            <div className="text-lg font-semibold text-stone-950">
              {doc.edges.length}
            </div>
          </div>
          <div className="rounded-lg border border-stone-200 p-2">
            <div className="text-xs text-stone-500">ルール</div>
            <div className="text-lg font-semibold text-stone-950">
              {doc.rules.length}
            </div>
          </div>
          <div className="rounded-lg border border-stone-200 p-2">
            <div className="text-xs text-stone-500">ケース</div>
            <div className="text-lg font-semibold text-stone-950">
              {doc.cases.length}
            </div>
          </div>
        </div>
        {selectedNodeIds.length + selectedEdgeIds.length > 1 ? (
          <div className="rounded-lg border border-stone-200 p-2">
            {selectedNodeIds.length}件のノード / {selectedEdgeIds.length}
            件のエッジを選択中
          </div>
        ) : null}
      </div>
    </aside>
  );
}
