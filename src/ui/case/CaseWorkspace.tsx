import {
  AlertTriangle,
  GitBranch,
  Link,
  Plus,
  Search,
  SlidersHorizontal,
  Unlink,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  laneLabels,
  lockModeLabels,
  nodeTypeLabels,
  probabilityRoleLabels,
  pruningHintLabels,
  ruleCategoryLabels,
} from "../../domain/labels";
import { decisionPipelineSteps } from "../../domain/mahjongTaxonomy";
import {
  classifyNodeScope,
  getActiveSheet,
  getProjectNodeIds,
} from "../../domain/projectSheets";
import {
  caseLanes,
  type CaseData,
  type CaseLane,
  type KnowledgeNode,
  type KnowledgeEdge,
} from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";
import { ExceptionLibraryPanel } from "../reading/ExceptionLibraryPanel";
import { QuickReadingInputPanel } from "../reading/QuickReadingInputPanel";
import { ResidualMassSummaryPanel } from "./ResidualMassSummaryPanel";

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

type CaseViewMode = "lanes" | "pipeline";

export function CaseWorkspace() {
  const doc = useAppStore((state) => state.doc);
  const addCase = useAppStore((state) => state.addCase);
  const setActiveCase = useAppStore((state) => state.setActiveCase);
  const updateCase = useAppStore((state) => state.updateCase);
  const attachNodeToCase = useAppStore((state) => state.attachNodeToCase);
  const detachNodeFromCase = useAppStore((state) => state.detachNodeFromCase);
  const setCaseNodeLane = useAppStore((state) => state.setCaseNodeLane);
  const setScreen = useAppStore((state) => state.setScreen);
  const setSelection = useAppStore((state) => state.setSelection);
  const duplicateSelectedNodes = useAppStore(
    (state) => state.duplicateSelectedNodes,
  );
  const [nodeSearch, setNodeSearch] = useState("");
  const [viewMode, setViewMode] = useState<CaseViewMode>("lanes");
  const [exceptionLibraryVisible, setExceptionLibraryVisible] = useState(false);
  const activeSheet = getActiveSheet(doc);
  const activeSheetCaseIds = useMemo(
    () => new Set(activeSheet?.case_ids ?? []),
    [activeSheet],
  );
  const orderedCases = useMemo(() => {
    const sheetCases = doc.cases.filter((caseItem) =>
      activeSheetCaseIds.has(caseItem.id),
    );
    const otherCases = doc.cases.filter(
      (caseItem) => !activeSheetCaseIds.has(caseItem.id),
    );
    return [...sheetCases, ...otherCases];
  }, [activeSheetCaseIds, doc.cases]);

  const activeCase =
    orderedCases.find(
      (caseItem) =>
        caseItem.id === doc.active_case_id &&
        (activeSheetCaseIds.size === 0 || activeSheetCaseIds.has(caseItem.id)),
    ) ?? orderedCases[0];

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
    const activeSheetNodeIds = new Set(activeSheet?.node_ids ?? []);
    const projectNodeIds = getProjectNodeIds(doc);
    for (const edge of doc.edges) {
      if (attachedIds.has(edge.source)) attachedNeighborIds.add(edge.target);
      if (attachedIds.has(edge.target)) attachedNeighborIds.add(edge.source);
    }

    return doc.nodes
      .filter((node) => !attachedIds.has(node.id))
      .map((node) => {
        let score = 0;
        if (activeSheetNodeIds.has(node.id)) score += 4;
        else if (projectNodeIds.has(node.id)) score += 2;
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
        return { node, score, scope: classifyNodeScope(doc, node.id) };
      })
      .filter((item) => item.score > -1)
      .sort(
        (a, b) => b.score - a.score || a.node.title.localeCompare(b.node.title),
      )
      .slice(0, 12);
  }, [activeCase, activeSheet, doc, nodeSearch]);

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
    <div className="grid min-h-0 flex-1 grid-cols-[360px_minmax(0,1fr)_320px] gap-3 overflow-hidden p-3">
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
              {orderedCases.map((caseItem) => (
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

      <main className="flex min-h-0 flex-col gap-3 overflow-y-auto overflow-x-hidden pr-1">
        <QuickReadingInputPanel />

        <section className="rounded-lg border border-stone-200 bg-white">
          <div className="flex min-h-10 items-center justify-between border-b border-stone-200 px-3">
            <div className="flex items-center gap-2">
              <GitBranch
                className="h-4 w-4 text-stone-500"
                aria-hidden="true"
              />
              <h2 className="text-sm font-semibold text-stone-950">思考経路</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-stone-600">
              <div className="flex rounded-md border border-stone-300 bg-white p-0.5">
                <Button
                  size="sm"
                  variant={viewMode === "lanes" ? "primary" : "ghost"}
                  onClick={() => setViewMode("lanes")}
                  aria-pressed={viewMode === "lanes"}
                >
                  4列
                </Button>
                <Button
                  size="sm"
                  variant={viewMode === "pipeline" ? "primary" : "ghost"}
                  onClick={() => setViewMode("pipeline")}
                  aria-pressed={viewMode === "pipeline"}
                >
                  <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                  判断プロセス
                </Button>
              </div>
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
          {viewMode === "lanes" ? (
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
                  onDetach={(nodeId) =>
                    detachNodeFromCase(activeCase.id, nodeId)
                  }
                />
              ))}
            </div>
          ) : (
            <DecisionPipelineBoard
              activeCase={activeCase}
              nodes={attachedNodes}
              edges={doc.edges}
              onDetach={(nodeId) => detachNodeFromCase(activeCase.id, nodeId)}
            />
          )}
        </section>

        <MissingElementsPanel
          activeCase={activeCase}
          nodes={attachedNodes}
          edges={doc.edges}
        />

        <ResidualMassSummaryPanel
          nodes={attachedNodes}
          onAddCandidate={(groupId) => {
            setSelection(
              attachedNodes
                .filter((node) => node.choice_group_id === groupId)
                .map((node) => node.id),
              [],
            );
          }}
          onOpenExceptionLibrary={() =>
            setExceptionLibraryVisible((value) => !value)
          }
          onKeepUnknown={(groupId) => {
            setSelection(
              attachedNodes
                .filter(
                  (node) =>
                    node.choice_group_id === groupId &&
                    node.tags.includes("residual_mass"),
                )
                .map((node) => node.id),
              [],
            );
          }}
        />

        {exceptionLibraryVisible ? <ExceptionLibraryPanel /> : null}

        <NumericReadingSummaryPanel
          nodes={attachedNodes}
          edges={doc.edges}
          onOpenProbability={(nodeId) => {
            setSelection([nodeId], []);
            setScreen("probability");
          }}
          onDuplicate={(nodeId) => {
            setSelection([nodeId], []);
            duplicateSelectedNodes();
          }}
        />

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
          {candidates.map(({ node, score, scope }) => (
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
                    <Badge>
                      {scope === "sheet"
                        ? "Sheet"
                        : scope === "project"
                          ? "Project"
                          : "Global"}
                    </Badge>
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

function DecisionPipelineBoard({
  activeCase,
  nodes,
  edges,
  onDetach,
}: {
  activeCase: CaseData;
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
  onDetach: (nodeId: string) => void;
}) {
  const grouped = decisionPipelineSteps.map((step) => ({
    ...step,
    nodes: nodes.filter((node) =>
      nodeMatchesPipelineStep(node, step.id, edges, activeCase),
    ),
  }));

  return (
    <div className="grid min-h-[360px] grid-cols-6 gap-2 p-2">
      {grouped.map((step) => (
        <section
          key={step.id}
          className="min-w-0 rounded-lg border border-stone-200 bg-stone-50"
        >
          <div className="border-b border-stone-200 px-2 py-2">
            <h3 className="text-sm font-semibold text-stone-950">
              {step.label}
            </h3>
          </div>
          <div className="grid gap-2 p-2">
            {step.nodes.map((node) => (
              <PipelineNodeCard
                key={`${step.id}_${node.id}`}
                node={node}
                edges={edges}
                onDetach={onDetach}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function PipelineNodeCard({
  node,
  edges,
  onDetach,
}: {
  node: KnowledgeNode;
  edges: KnowledgeEdge[];
  onDetach: (nodeId: string) => void;
}) {
  const influences = edges.filter(
    (edge) =>
      edge.relation_layer === "influence" &&
      (edge.source === node.id || edge.target === node.id),
  );
  const probability =
    node.posterior_probability ?? node.prior_probability ?? node.base_weight;

  return (
    <article className="rounded-lg border border-stone-200 bg-white p-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-stone-950">
            {node.title}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge tone="cyan">{nodeTypeLabels[node.type]}</Badge>
            {probability !== undefined ? (
              <Badge>p {formatProbability(probability)}</Badge>
            ) : null}
            {node.probability_role !== "none" ? (
              <Badge>{probabilityRoleLabels[node.probability_role]}</Badge>
            ) : null}
            {node.lock_mode !== "none" ? (
              <Badge tone="amber">{lockModeLabels[node.lock_mode]}</Badge>
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
      <div className="mt-2 flex flex-wrap gap-1">
        {node.tags.slice(0, 4).map((tag) => (
          <Badge key={tag}>{tag}</Badge>
        ))}
        {node.pruning_hints.map((hint) => (
          <Badge key={hint} tone="amber">
            {pruningHintLabels[hint]}
          </Badge>
        ))}
      </div>
      {influences.length > 0 ? (
        <p className="mt-2 truncate text-xs text-stone-500">
          influence:{" "}
          {influences
            .slice(0, 3)
            .map((edge) => `${edge.sign} ${edge.label || edge.type}`)
            .join(" / ")}
        </p>
      ) : null}
    </article>
  );
}

function MissingElementsPanel({
  activeCase,
  nodes,
  edges,
}: {
  activeCase: CaseData;
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}) {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const caseInfluenceEdges = edges.filter(
    (edge) =>
      nodeIds.has(edge.source) &&
      nodeIds.has(edge.target) &&
      edge.relation_layer === "influence",
  );
  const missing = [
    [
      "仮説がない",
      activeCase.hypotheses.length === 0 &&
        !nodes.some((node) => ["hypothesis", "branch"].includes(node.type)),
    ],
    ["metricがない", !nodes.some((node) => node.type === "metric")],
    ["choice groupがない", !nodes.some((node) => node.type === "choice_group")],
    ["top-kが未設定", activeCase.top_k_hypotheses < 2],
    ["判断メモがない", activeCase.decision_note.trim().length === 0],
    ["反省メモがない", activeCase.review_note.trim().length === 0],
    [
      "mixed/unknown influence が残っている",
      caseInfluenceEdges.some(
        (edge) => edge.sign === "mixed" || edge.sign === "unknown",
      ),
    ],
    [
      "hard prune されそうだが ambiguity が高い",
      nodes.some((node) =>
        node.pruning_hints.includes("hard_gate_candidate"),
      ) &&
        caseInfluenceEdges.some(
          (edge) => edge.sign === "mixed" || edge.sign === "unknown",
        ),
    ],
    [
      "読みメモはあるが数値がない",
      nodes.some(
        (node) =>
          node.tags.includes("reading") &&
          node.probability_role === "none" &&
          node.base_weight === undefined &&
          node.dynamic_weight === undefined &&
          node.posterior_probability === undefined,
      ),
    ],
    [
      "数値はあるが4軸影響がない",
      nodes.some((node) => hasNumericFields(node)) &&
        !caseInfluenceEdges.some((edge) =>
          nodes.some((node) => node.id === edge.source),
        ),
    ],
    [
      "choice groupに属していない仮説が複数ある",
      nodes.filter(
        (node) =>
          ["hypothesis", "branch"].includes(node.type) && !node.choice_group_id,
      ).length > 1,
    ],
    [
      "choice groupに未配分/過剰分がある",
      choiceGroupTotals(nodes).some((total) => Math.abs(total - 1) > 0.001),
    ],
    [
      "軸確信度が低いのに影響ウェイトが大きい",
      caseInfluenceEdges.some(
        (edge) => edge.confidence <= 0.4 && edge.magnitude >= 0.6,
      ),
    ],
  ].filter(([, active]) => active);

  return (
    <Panel title="この局面で足りない要素">
      <div className="flex flex-wrap gap-2 p-3">
        {missing.length > 0 ? (
          missing.map(([label]) => (
            <Badge key={label as string} tone="amber">
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              {label}
            </Badge>
          ))
        ) : (
          <span className="text-sm text-stone-500">
            主要な判断要素は揃っています。
          </span>
        )}
      </div>
    </Panel>
  );
}

function NumericReadingSummaryPanel({
  nodes,
  edges,
  onOpenProbability,
  onDuplicate,
}: {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
  onOpenProbability: (nodeId: string) => void;
  onDuplicate: (nodeId: string) => void;
}) {
  const numericReadings = nodes.filter(
    (node) =>
      node.tags.some((tag) =>
        [
          "quick_reading",
          "reading",
          "weight_modifier",
          "hand_value_range",
          "probability_tree",
        ].includes(tag),
      ) &&
      (node.probability_role !== "none" || hasNumericFields(node)),
  );

  return (
    <Panel title="数値反映済みの読み">
      <div className="grid gap-2 p-3">
        {numericReadings.length === 0 ? (
          <p className="text-sm text-stone-500">
            active case に数値反映済みの読みはまだありません。
          </p>
        ) : (
          numericReadings.slice(0, 6).map((node) => {
            const influences = edges.filter(
              (edge) =>
                edge.source === node.id && edge.relation_layer === "influence",
            );
            return (
              <article
                key={node.id}
                className="rounded-md border border-stone-200 p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-stone-950">
                      {node.title}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge>{Math.round(node.confidence * 100)}%</Badge>
                      {node.prior_probability !== undefined ? (
                        <Badge>
                          prior {formatProbability(node.prior_probability)}
                        </Badge>
                      ) : null}
                      {node.posterior_probability !== undefined ? (
                        <Badge>
                          posterior{" "}
                          {formatProbability(node.posterior_probability)}
                        </Badge>
                      ) : null}
                      {node.base_weight !== undefined ? (
                        <Badge>base {node.base_weight}</Badge>
                      ) : null}
                      {node.dynamic_weight !== undefined ? (
                        <Badge>dyn {node.dynamic_weight}</Badge>
                      ) : null}
                      {node.lock_mode !== "none" ? (
                        <Badge tone="amber">
                          {lockModeLabels[node.lock_mode]}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      size="sm"
                      onClick={() => onOpenProbability(node.id)}
                    >
                      確率画面で調整
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onDuplicate(node.id)}
                    >
                      複製
                    </Button>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {node.pruning_hints.map((hint) => (
                    <Badge key={hint} tone="amber">
                      {pruningHintLabels[hint]}
                    </Badge>
                  ))}
                  {influences.map((edge) => (
                    <Badge key={edge.id} tone="cyan">
                      {edge.label ||
                        `${edge.sign} 影響ウェイト ${formatScore(edge.magnitude)}`}
                    </Badge>
                  ))}
                </div>
              </article>
            );
          })
        )}
      </div>
    </Panel>
  );
}

function nodeMatchesPipelineStep(
  node: KnowledgeNode,
  stepId: string,
  edges: KnowledgeEdge[],
  activeCase: CaseData,
) {
  const hasInfluence = edges.some(
    (edge) =>
      edge.relation_layer === "influence" &&
      (edge.source === node.id || edge.target === node.id),
  );
  const hasTag = (values: string[]) =>
    values.some((value) => node.tags.includes(value));

  if (stepId === "collect") {
    return ["observation", "question", "evidence", "signal"].includes(
      node.type,
    );
  }
  if (stepId === "weight") {
    return (
      ["weight_modifier", "heuristic", "metric"].includes(node.type) ||
      hasInfluence ||
      hasTag(["weight", "weight-modifier"])
    );
  }
  if (stepId === "combine") {
    return (
      ["probability_aggregate", "metric"].includes(node.type) ||
      hasTag(["combine", "probability_tree"])
    );
  }
  if (stepId === "compare") {
    return (
      ["choice_group", "branch", "hypothesis", "scenario"].includes(
        node.type,
      ) || hasTag(["compare", "choice-group"])
    );
  }
  if (stepId === "choose") {
    return (
      node.type === "action" ||
      activeCase.lane_assignments[node.id] === "decision" ||
      hasTag(["choose"])
    );
  }
  return (
    node.type === "evidence" ||
    node.reading_utility_ids.length > 0 ||
    hasTag(["review", "teaching", "training", "レビュー", "反省"])
  );
}

function formatProbability(value: number) {
  return Number.isFinite(value) ? `${Math.round(value * 1000) / 10}%` : "0%";
}

function formatScore(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value * 100)))}/100`;
}

function hasNumericFields(node: KnowledgeNode) {
  return (
    node.base_weight !== undefined ||
    node.dynamic_weight !== undefined ||
    node.posterior_probability !== undefined ||
    node.prior_probability !== undefined ||
    node.lock_mode !== "none"
  );
}

function choiceGroupTotals(nodes: KnowledgeNode[]) {
  const totals = new Map<string, number>();
  for (const node of nodes) {
    if (!node.choice_group_id) continue;
    totals.set(
      node.choice_group_id,
      (totals.get(node.choice_group_id) ?? 0) +
        (node.posterior_probability ?? 0),
    );
  }
  return Array.from(totals.values());
}
