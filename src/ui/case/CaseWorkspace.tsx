import { GitBranch, Link, Plus, Search, Unlink } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  laneLabels,
  nodeTypeLabels,
  ruleCategoryLabels,
} from "../../domain/labels";
import {
  caseLanes,
  type CaseData,
  type CaseLane,
  type KnowledgeNode,
} from "../../domain/schema";
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

function numeric(value: string, fallback: number) {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

const scoreSeatLabels = {
  east: "東",
  south: "南",
  west: "西",
  north: "北",
} as const;

export function CaseWorkspace() {
  const doc = useAppStore((state) => state.doc);
  const addCase = useAppStore((state) => state.addCase);
  const setActiveCase = useAppStore((state) => state.setActiveCase);
  const updateCase = useAppStore((state) => state.updateCase);
  const attachNodeToCase = useAppStore((state) => state.attachNodeToCase);
  const detachNodeFromCase = useAppStore((state) => state.detachNodeFromCase);
  const setCaseNodeLane = useAppStore((state) => state.setCaseNodeLane);
  const [nodeSearch, setNodeSearch] = useState("");

  const activeCase =
    doc.cases.find((caseItem) => caseItem.id === doc.active_case_id) ??
    doc.cases[0];

  const attachedNodes = useMemo(() => {
    if (!activeCase) return [];
    const ids = new Set(activeCase.attached_node_ids);
    return doc.nodes.filter((node) => ids.has(node.id));
  }, [activeCase, doc.nodes]);

  const candidates = useMemo(() => {
    if (!activeCase) return [];
    const attachedIds = new Set(activeCase.attached_node_ids);
    const caseText = [
      activeCase.title,
      activeCase.round,
      activeCase.riichi_status,
      activeCase.melds_summary,
      activeCase.discard_notes,
      ...activeCase.observations,
      ...activeCase.hypotheses,
    ]
      .join(" ")
      .toLowerCase();
    const searchText = nodeSearch.trim().toLowerCase();
    const attachedNeighborIds = new Set<string>();
    for (const edge of doc.edges) {
      if (attachedIds.has(edge.source)) attachedNeighborIds.add(edge.target);
      if (attachedIds.has(edge.target)) attachedNeighborIds.add(edge.source);
    }

    return doc.nodes
      .filter((node) => !attachedIds.has(node.id))
      .map((node) => {
        let score = 0;
        if (attachedNeighborIds.has(node.id)) score += 2;
        if (caseText.includes(node.title.toLowerCase())) score += 2;
        for (const tag of node.tags) {
          if (caseText.includes(tag.toLowerCase())) score += 1;
        }
        if (searchText) {
          const haystack = [
            node.title,
            node.summary,
            node.description,
            ...node.tags,
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(searchText)) score -= 10;
          else score += 3;
        }
        return { node, score };
      })
      .filter((item) => item.score > -1)
      .sort(
        (a, b) => b.score - a.score || a.node.title.localeCompare(b.node.title),
      )
      .slice(0, 12);
  }, [activeCase, doc.edges, doc.nodes, nodeSearch]);

  if (!activeCase) {
    return (
      <div className="p-4">
        <Button onClick={addCase}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          ケースを作成
        </Button>
      </div>
    );
  }

  const patchCase = (patch: Partial<CaseData>) =>
    updateCase(activeCase.id, patch);

  const toggleCaseRule = (ruleId: string) => {
    const next = activeCase.selected_rule_ids.includes(ruleId)
      ? activeCase.selected_rule_ids.filter((id) => id !== ruleId)
      : [...activeCase.selected_rule_ids, ruleId];
    patchCase({ selected_rule_ids: next });
  };

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[360px_minmax(0,1fr)_320px] gap-3 p-3">
      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
          <h2 className="text-sm font-semibold text-stone-950">局面作業場</h2>
          <Button onClick={addCase} size="sm">
            <Plus className="h-4 w-4" aria-hidden="true" />
            新規
          </Button>
        </div>
        <div className="grid gap-3 p-3">
          <Field label="ケース">
            <Select
              value={activeCase.id}
              onChange={(event) => setActiveCase(event.target.value)}
            >
              {doc.cases.map((caseItem) => (
                <option key={caseItem.id} value={caseItem.id}>
                  {caseItem.title}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="タイトル">
            <Input
              value={activeCase.title}
              onChange={(event) => patchCase({ title: event.target.value })}
            />
          </Field>
          <div className="grid grid-cols-3 gap-2">
            <Field label="局">
              <Input
                value={activeCase.round}
                onChange={(event) => patchCase({ round: event.target.value })}
              />
            </Field>
            <Field label="本場">
              <Input
                type="number"
                min={0}
                value={activeCase.honba}
                onChange={(event) =>
                  patchCase({
                    honba: numeric(event.target.value, activeCase.honba),
                  })
                }
              />
            </Field>
            <Field label="供託">
              <Input
                type="number"
                min={0}
                value={activeCase.riichi_sticks}
                onChange={(event) =>
                  patchCase({
                    riichi_sticks: numeric(
                      event.target.value,
                      activeCase.riichi_sticks,
                    ),
                  })
                }
              />
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Field label="巡目">
              <Input
                type="number"
                min={1}
                max={18}
                value={activeCase.turn}
                onChange={(event) =>
                  patchCase({
                    turn: numeric(event.target.value, activeCase.turn),
                  })
                }
              />
            </Field>
            <Field label="親">
              <Input
                value={activeCase.dealer}
                onChange={(event) => patchCase({ dealer: event.target.value })}
              />
            </Field>
            <Field label="自家">
              <Input
                value={activeCase.seat}
                onChange={(event) => patchCase({ seat: event.target.value })}
              />
            </Field>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {(["east", "south", "west", "north"] as const).map((seat) => (
              <Field key={seat} label={scoreSeatLabels[seat]}>
                <Input
                  type="number"
                  value={activeCase.scores[seat]}
                  onChange={(event) =>
                    patchCase({
                      scores: {
                        ...activeCase.scores,
                        [seat]: numeric(
                          event.target.value,
                          activeCase.scores[seat],
                        ),
                      },
                    })
                  }
                />
              </Field>
            ))}
          </div>
          <Field label="リーチ有無">
            <Input
              value={activeCase.riichi_status}
              onChange={(event) =>
                patchCase({ riichi_status: event.target.value })
              }
            />
          </Field>
          <Field label="副露数 / 副露メモ">
            <Input
              value={activeCase.melds_summary}
              onChange={(event) =>
                patchCase({ melds_summary: event.target.value })
              }
            />
          </Field>
          <Field label="捨て牌メモ">
            <Textarea
              value={activeCase.discard_notes}
              onChange={(event) =>
                patchCase({ discard_notes: event.target.value })
              }
            />
          </Field>
          <Field label="目立つ観測事象" hint="1行に1項目">
            <Textarea
              value={toLines(activeCase.observations)}
              onChange={(event) =>
                patchCase({ observations: fromLines(event.target.value) })
              }
            />
          </Field>
          <Field label="仮説メモ" hint="1行に1項目">
            <Textarea
              value={toLines(activeCase.hypotheses)}
              onChange={(event) =>
                patchCase({ hypotheses: fromLines(event.target.value) })
              }
            />
          </Field>
        </div>
      </aside>

      <main className="flex min-h-0 flex-col gap-3">
        <section className="rounded-lg border border-stone-200 bg-white">
          <div className="flex min-h-10 items-center justify-between border-b border-stone-200 px-3">
            <div className="flex items-center gap-2">
              <GitBranch
                className="h-4 w-4 text-stone-500"
                aria-hidden="true"
              />
              <h2 className="text-sm font-semibold text-stone-950">思考経路</h2>
            </div>
            <div className="flex items-center gap-2 text-sm text-stone-600">
              <span>上位候補数</span>
              <Input
                className="w-16"
                type="number"
                min={1}
                max={8}
                value={activeCase.top_k_hypotheses}
                onChange={(event) =>
                  patchCase({
                    top_k_hypotheses: numeric(
                      event.target.value,
                      activeCase.top_k_hypotheses,
                    ),
                  })
                }
              />
            </div>
          </div>
          <div className="grid min-h-[360px] grid-cols-4 gap-2 p-2">
            {caseLanes.map((lane) => (
              <CaseLaneColumn
                key={lane}
                lane={lane}
                activeCase={activeCase}
                nodes={attachedNodes.filter(
                  (node) =>
                    (activeCase.lane_assignments[node.id] ?? "hypothesis") ===
                    lane,
                )}
                allAttachedNodes={attachedNodes}
                edges={doc.edges}
                onLaneChange={(nodeId, nextLane) =>
                  setCaseNodeLane(activeCase.id, nodeId, nextLane)
                }
                onDetach={(nodeId) => detachNodeFromCase(activeCase.id, nodeId)}
              />
            ))}
          </div>
        </section>

        <div className="grid min-h-0 flex-1 grid-cols-2 gap-3">
          <Panel title="判断メモ">
            <Textarea
              className="min-h-40 border-0 focus:ring-0"
              value={activeCase.decision_note}
              onChange={(event) =>
                patchCase({ decision_note: event.target.value })
              }
            />
          </Panel>
          <Panel title="反省メモ">
            <Textarea
              className="min-h-40 border-0 focus:ring-0"
              value={activeCase.review_note}
              onChange={(event) =>
                patchCase({ review_note: event.target.value })
              }
            />
          </Panel>
        </div>
      </main>

      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="sticky top-0 z-10 border-b border-stone-200 bg-white px-3 py-2">
          <h2 className="mb-2 text-sm font-semibold text-stone-950">
            知識を関連付け
          </h2>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-stone-400" />
            <Input
              className="w-full pl-8"
              value={nodeSearch}
              onChange={(event) => setNodeSearch(event.target.value)}
              placeholder="ノード / タグ"
            />
          </div>
        </div>
        <div className="grid gap-2 p-2">
          {candidates.map(({ node, score }) => (
            <div
              key={node.id}
              className="rounded-lg border border-stone-200 p-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-stone-950">
                    {node.title}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <Badge tone="cyan">{nodeTypeLabels[node.type]}</Badge>
                    <Badge>{score}</Badge>
                  </div>
                </div>
                <Button
                  size="icon"
                  onClick={() => attachNodeToCase(activeCase.id, node.id)}
                  title="関連付け"
                >
                  <Link className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-4 text-stone-600">
                {node.summary}
              </p>
            </div>
          ))}
        </div>

        <div className="border-t border-stone-200 p-3">
          <h3 className="mb-2 text-sm font-semibold text-stone-950">
            選択ルール
          </h3>
          <div className="grid gap-2">
            {doc.rules.map((rule) => (
              <label
                key={rule.id}
                className="flex items-start gap-2 text-sm text-stone-700"
              >
                <input
                  className="mt-1"
                  type="checkbox"
                  checked={activeCase.selected_rule_ids.includes(rule.id)}
                  onChange={() => toggleCaseRule(rule.id)}
                />
                <span className="min-w-0">
                  <span className="block truncate font-medium text-stone-900">
                    {rule.name}
                  </span>
                  <span className="text-xs text-stone-500">
                    {ruleCategoryLabels[rule.category]}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function CaseLaneColumn({
  lane,
  nodes,
  allAttachedNodes,
  edges,
  onLaneChange,
  onDetach,
}: {
  lane: CaseLane;
  activeCase: CaseData;
  nodes: KnowledgeNode[];
  allAttachedNodes: KnowledgeNode[];
  edges: { source: string; target: string; type: string }[];
  onLaneChange: (nodeId: string, lane: CaseLane) => void;
  onDetach: (nodeId: string) => void;
}) {
  const attachedIds = new Set(allAttachedNodes.map((node) => node.id));

  return (
    <section className="min-w-0 rounded-lg border border-stone-200 bg-stone-50">
      <div className="border-b border-stone-200 px-2 py-2">
        <h3 className="text-sm font-semibold text-stone-950">
          {laneLabels[lane]}
        </h3>
      </div>
      <div className="grid gap-2 p-2">
        {nodes.map((node) => {
          const hasContradiction = edges.some(
            (edge) =>
              edge.type === "contradicts" &&
              ((edge.source === node.id && attachedIds.has(edge.target)) ||
                (edge.target === node.id && attachedIds.has(edge.source))),
          );
          return (
            <article
              key={node.id}
              className="rounded-lg border border-stone-200 bg-white p-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-stone-950">
                    {node.title}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <Badge tone="cyan">{nodeTypeLabels[node.type]}</Badge>
                    {hasContradiction ? <Badge tone="rose">相反</Badge> : null}
                    {node.pruning_hints.includes("must_keep_top_k") ? (
                      <Badge tone="amber">上位候補</Badge>
                    ) : null}
                  </div>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => onDetach(node.id)}
                  title="関連付けを解除"
                >
                  <Unlink className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-4 text-stone-600">
                {node.summary}
              </p>
              <Select
                className="mt-2 w-full"
                value={lane}
                onChange={(event) =>
                  onLaneChange(node.id, event.target.value as CaseLane)
                }
              >
                {caseLanes.map((item) => (
                  <option key={item} value={item}>
                    {laneLabels[item]}
                  </option>
                ))}
              </Select>
            </article>
          );
        })}
      </div>
    </section>
  );
}
