import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import { createId } from "../../domain/factory";
import { nodeTypeLabels, ruleCategoryLabels } from "../../domain/labels";
import { ruleCategories, type RuleDefinition } from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";

function fromLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toLines(values: string[]) {
  return values.join("\n");
}

export function RuleBuilderLite() {
  const doc = useAppStore((state) => state.doc);
  const addRule = useAppStore((state) => state.addRule);
  const updateRule = useAppStore((state) => state.updateRule);
  const deleteRule = useAppStore((state) => state.deleteRule);
  const [selectedRuleId, setSelectedRuleId] = useState(doc.rules[0]?.id ?? "");
  const [targetSearch, setTargetSearch] = useState("");

  const selectedRule =
    doc.rules.find((rule) => rule.id === selectedRuleId) ?? doc.rules[0];
  const activeRuleId = selectedRule?.id ?? "";

  const candidateNodes = useMemo(() => {
    const text = targetSearch.trim().toLowerCase();
    return doc.nodes
      .filter((node) => {
        if (!text) return true;
        return [node.title, node.summary, ...node.tags]
          .join(" ")
          .toLowerCase()
          .includes(text);
      })
      .slice(0, 80);
  }, [doc.nodes, targetSearch]);

  const createAndSelectRule = () => {
    addRule();
    window.setTimeout(() => {
      const latest = useAppStore.getState().doc.rules.at(-1);
      if (latest) setSelectedRuleId(latest.id);
    }, 0);
  };

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[320px_minmax(0,1fr)] gap-3 p-3">
      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
          <h2 className="text-sm font-semibold text-stone-950">
            Rule Builder Lite
          </h2>
          <Button size="sm" onClick={createAndSelectRule}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            New
          </Button>
        </div>
        <div className="grid gap-2 p-2">
          {doc.rules.map((rule) => (
            <button
              key={rule.id}
              type="button"
              onClick={() => setSelectedRuleId(rule.id)}
              className={`rounded-lg border p-2 text-left ${
                rule.id === activeRuleId
                  ? "border-cyan-700 bg-cyan-50"
                  : "border-stone-200 bg-white hover:bg-stone-50"
              }`}
            >
              <div className="truncate text-sm font-semibold text-stone-950">
                {rule.name}
              </div>
              <div className="mt-1 flex items-center gap-1">
                <Badge tone={rule.category === "override" ? "rose" : "cyan"}>
                  {ruleCategoryLabels[rule.category]}
                </Badge>
                <Badge>{rule.target_node_ids.length} nodes</Badge>
              </div>
            </button>
          ))}
        </div>
      </aside>

      {selectedRule ? (
        <RuleEditor
          rule={selectedRule}
          candidateNodes={candidateNodes}
          targetSearch={targetSearch}
          setTargetSearch={setTargetSearch}
          updateRule={updateRule}
          deleteRule={(id) => {
            deleteRule(id);
            setSelectedRuleId("");
          }}
        />
      ) : (
        <div className="rounded-lg border border-stone-200 bg-white p-4 text-sm text-stone-600">
          ルールがありません。
        </div>
      )}
    </div>
  );
}

function RuleEditor({
  rule,
  candidateNodes,
  targetSearch,
  setTargetSearch,
  updateRule,
  deleteRule,
}: {
  rule: RuleDefinition;
  candidateNodes: { id: string; title: string; type: string; tags: string[] }[];
  targetSearch: string;
  setTargetSearch: (value: string) => void;
  updateRule: (id: string, patch: Partial<RuleDefinition>) => void;
  deleteRule: (id: string) => void;
}) {
  const patch = (patchValue: Partial<RuleDefinition>) =>
    updateRule(rule.id, patchValue);

  const toggleTarget = (nodeId: string) => {
    patch({
      target_node_ids: rule.target_node_ids.includes(nodeId)
        ? rule.target_node_ids.filter((id) => id !== nodeId)
        : [...rule.target_node_ids, nodeId],
    });
  };

  return (
    <main className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
      <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
        <h2 className="truncate text-sm font-semibold text-stone-950">
          {rule.name}
        </h2>
        <Button variant="danger" size="sm" onClick={() => deleteRule(rule.id)}>
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          削除
        </Button>
      </div>

      <div className="grid gap-3 p-3">
        <div className="grid grid-cols-[minmax(0,1fr)_220px] gap-3">
          <Field label="Name">
            <Input
              value={rule.name}
              onChange={(event) => patch({ name: event.target.value })}
            />
          </Field>
          <Field label="Category">
            <Select
              value={rule.category}
              onChange={(event) =>
                patch({
                  category: event.target.value as RuleDefinition["category"],
                })
              }
            >
              {ruleCategories.map((category) => (
                <option key={category} value={category}>
                  {ruleCategoryLabels[category]}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-3">
          <div className="grid gap-3">
            <Panel title="Hard gate">
              <Textarea
                className="min-h-28 border-0 focus:ring-0"
                value={toLines(rule.hard_gates)}
                onChange={(event) =>
                  patch({ hard_gates: fromLines(event.target.value) })
                }
              />
            </Panel>
            <Panel
              title="Soft score"
              action={
                <Button
                  size="sm"
                  onClick={() =>
                    patch({
                      soft_score_terms: [
                        ...rule.soft_score_terms,
                        {
                          id: createId("term"),
                          label: "score term",
                          weight: 0,
                          note: "",
                        },
                      ],
                    })
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Term
                </Button>
              }
            >
              <div className="grid gap-2 p-2">
                {rule.soft_score_terms.map((term) => (
                  <div
                    key={term.id}
                    className="grid grid-cols-[minmax(0,1fr)_96px_32px] gap-2 rounded-lg border border-stone-200 p-2"
                  >
                    <Input
                      value={term.label}
                      onChange={(event) =>
                        patch({
                          soft_score_terms: rule.soft_score_terms.map((item) =>
                            item.id === term.id
                              ? { ...item, label: event.target.value }
                              : item,
                          ),
                        })
                      }
                    />
                    <Input
                      type="number"
                      step="0.05"
                      value={term.weight}
                      onChange={(event) =>
                        patch({
                          soft_score_terms: rule.soft_score_terms.map((item) =>
                            item.id === term.id
                              ? { ...item, weight: Number(event.target.value) }
                              : item,
                          ),
                        })
                      }
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() =>
                        patch({
                          soft_score_terms: rule.soft_score_terms.filter(
                            (item) => item.id !== term.id,
                          ),
                        })
                      }
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </Button>
                    <Textarea
                      className="col-span-3 min-h-16"
                      value={term.note}
                      onChange={(event) =>
                        patch({
                          soft_score_terms: rule.soft_score_terms.map((item) =>
                            item.id === term.id
                              ? { ...item, note: event.target.value }
                              : item,
                          ),
                        })
                      }
                    />
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Override">
              <Textarea
                className="min-h-28 border-0 focus:ring-0"
                value={toLines(rule.override_conditions)}
                onChange={(event) =>
                  patch({ override_conditions: fromLines(event.target.value) })
                }
              />
            </Panel>
            <Panel title="Fallback">
              <Textarea
                className="min-h-24 border-0 focus:ring-0"
                value={rule.fallback_behavior}
                onChange={(event) =>
                  patch({ fallback_behavior: event.target.value })
                }
              />
            </Panel>
            <Field label="Note">
              <Textarea
                value={rule.note}
                onChange={(event) => patch({ note: event.target.value })}
              />
            </Field>
          </div>

          <aside className="rounded-lg border border-stone-200">
            <div className="border-b border-stone-200 p-2">
              <h3 className="mb-2 text-sm font-semibold text-stone-950">
                Target nodes
              </h3>
              <Input
                value={targetSearch}
                onChange={(event) => setTargetSearch(event.target.value)}
                placeholder="filter"
              />
            </div>
            <div className="max-h-[680px] overflow-auto p-2">
              <div className="grid gap-1.5">
                {candidateNodes.map((node) => (
                  <label
                    key={node.id}
                    className="flex items-start gap-2 rounded border border-stone-200 p-2 text-sm"
                  >
                    <input
                      className="mt-1"
                      type="checkbox"
                      checked={rule.target_node_ids.includes(node.id)}
                      onChange={() => toggleTarget(node.id)}
                    />
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-stone-900">
                        {node.title}
                      </span>
                      <span className="text-xs text-stone-500">
                        {
                          nodeTypeLabels[
                            node.type as keyof typeof nodeTypeLabels
                          ]
                        }
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
