import { useMemo, useState } from "react";
import {
  BarChart3,
  BookOpen,
  GitCompare,
  LockKeyhole,
  Route,
  SearchCheck,
  Sigma,
  Waves,
} from "lucide-react";
import { useAppStore } from "../../app/store";
import { getMetricInfluences, getInfluenceModel } from "../../domain/influence";
import { getInferenceSubgraph } from "../../domain/probability";
import {
  buildTeachingLogs,
  estimateAveragingSafety,
  evaluateReadingUtilities,
  getConcentrationItems,
  replayReadingChain,
  simulatePruningAction,
} from "../../domain/reasoningLab";
import {
  lockModes,
  pruningActionTypes,
  type KnowledgeNode,
  type LockMode,
  type PruningAction,
  type PruningActionType,
} from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";

const tabs = [
  { id: "graph", label: "Graph View", icon: Route },
  { id: "metric", label: "Metric Lens", icon: SearchCheck },
  { id: "concentration", label: "Concentration Lens", icon: BarChart3 },
  { id: "pruning", label: "Pruning Lab", icon: GitCompare },
  { id: "lock", label: "Lock Analysis", icon: LockKeyhole },
  { id: "ambiguity", label: "Ambiguity / Observation Planner", icon: Waves },
  { id: "chain", label: "Reading Chain Timeline", icon: Sigma },
  { id: "education", label: "Educational Explanation Panel", icon: BookOpen },
] as const;

type TabId = (typeof tabs)[number]["id"];

const lockOptions = lockModes.filter(
  (mode) => !["hard", "soft"].includes(mode),
);

export function ReasoningLab() {
  const doc = useAppStore((state) => state.doc);
  const updateNode = useAppStore((state) => state.updateNode);
  const recordReasoningLabSimulation = useAppStore(
    (state) => state.recordReasoningLabSimulation,
  );
  const [activeTab, setActiveTab] = useState<TabId>("concentration");
  const inference = useMemo(() => getInferenceSubgraph(doc), [doc]);
  const influence = useMemo(() => getInfluenceModel(doc), [doc]);
  const concentration = useMemo(() => getConcentrationItems(doc), [doc]);
  const utilities = useMemo(() => evaluateReadingUtilities(doc), [doc]);
  const averagingSafety = useMemo(() => estimateAveragingSafety(doc), [doc]);
  const teachingLogs = useMemo(() => buildTeachingLogs(doc), [doc]);
  const [metricId, setMetricId] = useState(
    influence.metrics[0]?.id ?? "metric_fold_risk",
  );
  const [targetId, setTargetId] = useState(
    inference.nodes[0]?.id ?? doc.nodes[0]?.id ?? "",
  );
  const [actionType, setActionType] =
    useState<PruningActionType>("soft_downweight");
  const [strength, setStrength] = useState(0.35);
  const [rationale, setRationale] = useState(
    "読みの影響をbefore/afterで確認する。",
  );
  const action = useMemo<PruningAction | undefined>(() => {
    if (!targetId) return undefined;
    return {
      id: `lab_${actionType}_${targetId}_${String(strength).replace(".", "_")}`,
      action_type: actionType,
      target_ids: [targetId],
      strength,
      rationale,
      created_at: new Date().toISOString(),
    };
  }, [actionType, rationale, strength, targetId]);
  const simulation = useMemo(
    () => (action ? simulatePruningAction(doc, action) : undefined),
    [action, doc],
  );
  const selectedMetricInfluences = useMemo(
    () => getMetricInfluences(doc, metricId),
    [doc, metricId],
  );

  const renderTab = () => {
    if (activeTab === "graph") {
      return (
        <GraphViewTab
          semanticCount={doc.nodes.length - inference.nodes.length}
          inferenceCount={inference.nodes.length}
          influenceCount={influence.influence_edges.length}
          concentrationCount={concentration.length}
        />
      );
    }
    if (activeTab === "metric") {
      return (
        <MetricLensTab
          metrics={influence.metrics}
          metricId={metricId}
          setMetricId={setMetricId}
          influences={selectedMetricInfluences}
          branchVectors={influence.branch_vectors}
        />
      );
    }
    if (activeTab === "concentration") {
      return (
        <ConcentrationLensTab items={concentration} docNodes={doc.nodes} />
      );
    }
    if (activeTab === "pruning") {
      return (
        <PruningLabTab
          nodes={inference.nodes}
          actionType={actionType}
          setActionType={setActionType}
          targetId={targetId}
          setTargetId={setTargetId}
          strength={strength}
          setStrength={setStrength}
          rationale={rationale}
          setRationale={setRationale}
          simulation={simulation}
          onSave={() => {
            if (!simulation) return;
            recordReasoningLabSimulation(
              simulation.action,
              simulation.impact_summary,
            );
          }}
        />
      );
    }
    if (activeTab === "lock") {
      return (
        <LockAnalysisTab
          nodes={inference.nodes}
          safety={averagingSafety}
          updateNode={updateNode}
        />
      );
    }
    if (activeTab === "ambiguity") {
      return <AmbiguityTab influence={influence} />;
    }
    if (activeTab === "chain") {
      return <ReadingChainTab doc={doc} />;
    }
    return (
      <EducationTab
        logs={teachingLogs}
        utilities={utilities}
        nodes={doc.nodes}
      />
    );
  };

  return (
    <main className="grid min-h-0 flex-1 grid-cols-[260px_1fr] gap-3 p-3">
      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white p-2">
        <div className="px-2 py-2">
          <h2 className="text-sm font-semibold text-stone-950">
            Mahjong Reasoning Lab
          </h2>
          <p className="mt-1 text-xs leading-5 text-stone-500">
            probability mass, pruning impact, lock, ambiguity, chain replay を
            同じworkspace上で比較します。
          </p>
        </div>
        <div className="grid gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <Button
                key={tab.id}
                variant={activeTab === tab.id ? "primary" : "ghost"}
                className="justify-start"
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                <span className="truncate">{tab.label}</span>
              </Button>
            );
          })}
        </div>
      </aside>
      <section className="min-h-0 overflow-auto">{renderTab()}</section>
    </main>
  );
}

function GraphViewTab({
  semanticCount,
  inferenceCount,
  influenceCount,
  concentrationCount,
}: {
  semanticCount: number;
  inferenceCount: number;
  influenceCount: number;
  concentrationCount: number;
}) {
  return (
    <div className="grid gap-3">
      <Panel title="Layer Separation">
        <div className="grid grid-cols-4 gap-3 p-3">
          <Stat label="Semantic nodes" value={semanticCount} />
          <Stat label="Inference nodes" value={inferenceCount} tone="cyan" />
          <Stat label="Influence edges" value={influenceCount} tone="amber" />
          <Stat
            label="Concentration sets"
            value={concentrationCount}
            tone="emerald"
          />
        </div>
      </Panel>
      <Panel title="MVP Boundary">
        <div className="grid gap-2 p-3 text-sm leading-6 text-stone-700">
          <p>
            Knowledge Graph は概念や根拠の地図、Probabilistic Inference Layer は
            choice-group tree + DAG、Directional Influence Layer は
            metricへのsigned influenceとして分けています。
          </p>
          <p>
            Reasoning Lab は派生計算の比較ビューです。一般の循環確率グラフや
            ベイズネット完全実装はまだ扱いません。
          </p>
        </div>
      </Panel>
    </div>
  );
}

function MetricLensTab({
  metrics,
  metricId,
  setMetricId,
  influences,
  branchVectors,
}: {
  metrics: KnowledgeNode[];
  metricId: string;
  setMetricId: (id: string) => void;
  influences: ReturnType<typeof getMetricInfluences>;
  branchVectors: ReturnType<typeof getInfluenceModel>["branch_vectors"];
}) {
  return (
    <div className="grid gap-3">
      <Panel title="Metric Lens">
        <div className="grid gap-3 p-3">
          <Field label="metric">
            <Select
              value={metricId}
              onChange={(event) => setMetricId(event.target.value)}
            >
              {metrics.map((metric) => (
                <option key={metric.id} value={metric.id}>
                  {metric.title}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid gap-2">
            {influences.map((item) => (
              <div
                key={item.edge.id}
                className="grid gap-2 rounded-md border border-stone-200 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-stone-900">
                    {item.source.title}
                  </span>
                  <div className="flex items-center gap-1">
                    <Badge tone={signTone(item.edge.sign)}>
                      sign {item.edge.sign}
                    </Badge>
                    <Badge>magnitude {format(item.edge.magnitude)}</Badge>
                    <Badge>conf {format(item.edge.confidence)}</Badge>
                  </div>
                </div>
                <p className="text-xs leading-5 text-stone-500">
                  context: {formatContext(item.edge.context_gate)} / mode:{" "}
                  {item.edge.combination_mode}
                </p>
                <Progress value={Math.min(1, Math.abs(item.signed_score))} />
              </div>
            ))}
          </div>
        </div>
      </Panel>
      <Panel title="Branch Vector Summary">
        <div className="grid gap-2 p-3">
          {branchVectors.map((vector) => (
            <div
              key={vector.branch_id}
              className="grid grid-cols-[1.2fr_1fr_1fr_1fr] items-center gap-3 rounded-md border border-stone-200 p-3 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{vector.title}</div>
                <div className="text-xs text-stone-500">
                  dominant {vector.dominant_direction}, conflicts{" "}
                  {vector.conflict_count}
                </div>
              </div>
              <Progress value={1 - vector.uncertainty} />
              <Badge tone={vector.prune_action === "prune" ? "rose" : "cyan"}>
                {vector.prune_action}
              </Badge>
              <span className="truncate text-xs text-stone-500">
                {vector.prune_reason}
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function ConcentrationLensTab({
  items,
  docNodes,
}: {
  items: ReturnType<typeof getConcentrationItems>;
  docNodes: KnowledgeNode[];
}) {
  const nodeById = new Map(docNodes.map((node) => [node.id, node]));
  return (
    <Panel title="Concentration Lens">
      <div className="grid gap-3 p-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="grid gap-3 rounded-md border border-stone-200 p-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="truncate text-sm font-semibold text-stone-900">
                    {item.title}
                  </h3>
                  <Badge tone="cyan">{item.scope}</Badge>
                </div>
                <p className="mt-1 text-xs text-stone-500">
                  {item.impact_prediction}
                </p>
              </div>
              <Badge tone={item.metrics.hhi > 0.42 ? "amber" : "emerald"}>
                {item.metrics.dispersion_note}
              </Badge>
            </div>
            <div className="grid grid-cols-4 gap-2">
              <MetricBox label="entropy" value={item.metrics.entropy} />
              <MetricBox label="top_k_mass" value={item.metrics.top_k_mass} />
              <MetricBox label="peak_mass" value={item.metrics.peak_mass} />
              <MetricBox label="hhi" value={item.metrics.hhi} />
            </div>
            <div className="grid gap-1.5">
              {item.node_ids.map((id) => {
                const node = nodeById.get(id);
                const value = node?.posterior_probability ?? 0;
                return (
                  <div
                    key={id}
                    className="grid grid-cols-[180px_1fr_56px] items-center gap-2 text-xs"
                  >
                    <span className="truncate text-stone-700">
                      {node?.title ?? id}
                    </span>
                    <Progress value={value} />
                    <span className="text-right tabular-nums">
                      {format(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function PruningLabTab({
  nodes,
  actionType,
  setActionType,
  targetId,
  setTargetId,
  strength,
  setStrength,
  rationale,
  setRationale,
  simulation,
  onSave,
}: {
  nodes: KnowledgeNode[];
  actionType: PruningActionType;
  setActionType: (type: PruningActionType) => void;
  targetId: string;
  setTargetId: (id: string) => void;
  strength: number;
  setStrength: (value: number) => void;
  rationale: string;
  setRationale: (value: string) => void;
  simulation?: ReturnType<typeof simulatePruningAction>;
  onSave: () => void;
}) {
  return (
    <div className="grid gap-3">
      <Panel title="Pruning Impact Simulator">
        <div className="grid grid-cols-[320px_1fr] gap-3 p-3">
          <div className="grid content-start gap-3">
            <Field label="action">
              <Select
                value={actionType}
                onChange={(event) =>
                  setActionType(event.target.value as PruningActionType)
                }
              >
                {pruningActionTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="target">
              <Select
                value={targetId}
                onChange={(event) => setTargetId(event.target.value)}
              >
                {nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.title}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="strength"
              hint="keep_top_kでは整数扱い、それ以外は0-1の強さとして扱います。"
            >
              <Input
                type="number"
                step="0.05"
                min="0"
                value={strength}
                onChange={(event) => setStrength(Number(event.target.value))}
              />
            </Field>
            <Field label="rationale">
              <Textarea
                value={rationale}
                onChange={(event) => setRationale(event.target.value)}
              />
            </Field>
            <Button variant="primary" onClick={onSave} disabled={!simulation}>
              Save diff log
            </Button>
          </div>
          {simulation ? (
            <SimulationSummary simulation={simulation} nodes={nodes} />
          ) : null}
        </div>
      </Panel>
    </div>
  );
}

function LockAnalysisTab({
  nodes,
  safety,
  updateNode,
}: {
  nodes: KnowledgeNode[];
  safety: ReturnType<typeof estimateAveragingSafety>;
  updateNode: (id: string, patch: Partial<KnowledgeNode>) => void;
}) {
  const safetyById = new Map(safety.map((item) => [item.target_id, item]));
  return (
    <Panel title="Node Lock / Regime Freeze Analysis">
      <div className="grid gap-2 p-3">
        {nodes.map((node) => {
          const item =
            safetyById.get(node.choice_group_id ?? "") ??
            safetyById.get(node.id);
          return (
            <div
              key={node.id}
              className="grid grid-cols-[1.1fr_160px_120px_1.2fr] items-center gap-3 rounded-md border border-stone-200 p-3"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-stone-900">
                  {node.title}
                </div>
                <div className="mt-1 flex gap-1">
                  <Badge tone="cyan">
                    p {format(node.posterior_probability ?? 0)}
                  </Badge>
                  <Badge>{node.choice_group_id ?? "standalone"}</Badge>
                </div>
              </div>
              <Select
                value={node.lock_mode}
                onChange={(event) =>
                  updateNode(node.id, {
                    lock_mode: event.target.value as LockMode,
                  })
                }
              >
                {lockOptions.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </Select>
              <Input
                type="number"
                step="0.05"
                value={node.lock_value ?? ""}
                placeholder="value"
                onChange={(event) =>
                  updateNode(node.id, {
                    lock_value:
                      event.target.value === ""
                        ? undefined
                        : Number(event.target.value),
                  })
                }
              />
              <div className="min-w-0">
                <Badge
                  tone={
                    item?.label === "safe"
                      ? "emerald"
                      : item?.label === "unsafe"
                        ? "rose"
                        : "amber"
                  }
                >
                  averaging {item?.label ?? "unknown"}
                </Badge>
                <p className="mt-1 truncate text-xs text-stone-500">
                  {item?.reasons.join(" / ") ?? "no estimator target"}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function AmbiguityTab({
  influence,
}: {
  influence: ReturnType<typeof getInfluenceModel>;
}) {
  return (
    <div className="grid gap-3">
      <Panel title="Ambiguity Panel">
        <div className="grid gap-2 p-3">
          {influence.ambiguities.map((item) => (
            <div
              key={item.id}
              className="grid grid-cols-[160px_1fr_220px] items-center gap-3 rounded-md border border-stone-200 p-3"
            >
              <div>
                <Badge tone={item.status === "unknown" ? "stone" : "amber"}>
                  {item.status}
                </Badge>
                <div className="mt-1 text-xs text-stone-500">
                  unresolved {format(item.unresolved_score)}
                </div>
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {item.metric_title}
                </div>
                <div className="truncate text-xs text-stone-500">
                  {item.source_titles.join(" / ")}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                <Badge tone={item.prune_candidate ? "emerald" : "stone"}>
                  prune候補
                </Badge>
                <Badge tone={item.downweight_candidate ? "amber" : "stone"}>
                  downweight候補
                </Badge>
                <Badge
                  tone={item.observe_candidate_ids.length ? "cyan" : "stone"}
                >
                  observe候補 {item.observe_candidate_ids.length}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Observation Planner">
        <div className="grid gap-2 p-3">
          {influence.observation_plan.map((item) => (
            <div
              key={item.node.id}
              className="grid grid-cols-[1fr_140px_140px_140px] items-center gap-3 rounded-md border border-stone-200 p-3 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{item.node.title}</div>
                <div className="truncate text-xs text-stone-500">
                  resolves {item.target_titles.join(" / ")}
                </div>
              </div>
              <MetricBox
                label="sign_gain"
                value={item.node.expected_sign_gain ?? 0}
              />
              <MetricBox
                label="margin_gain"
                value={item.node.expected_margin_gain ?? 0}
              />
              <MetricBox
                label="safety_change"
                value={item.node.pruning_safety_change ?? 0}
              />
            </div>
          ))}
          {influence.observation_plan.length === 0 ? (
            <p className="text-sm text-stone-500">
              observation_candidate がまだありません。
            </p>
          ) : null}
        </div>
      </Panel>
    </div>
  );
}

function ReadingChainTab({
  doc,
}: {
  doc: Parameters<typeof replayReadingChain>[0];
}) {
  const [chainId, setChainId] = useState(doc.reading_chains[0]?.id ?? "");
  const chain = doc.reading_chains.find((item) => item.id === chainId);
  const replay = useMemo(
    () => (chain ? replayReadingChain(doc, chain) : undefined),
    [chain, doc],
  );

  return (
    <Panel title="Reading Chain Timeline">
      <div className="grid gap-3 p-3">
        <Field label="chain">
          <Select
            value={chainId}
            onChange={(event) => setChainId(event.target.value)}
          >
            {doc.reading_chains.map((item) => (
              <option key={item.id} value={item.id}>
                {item.summary || item.id}
              </option>
            ))}
          </Select>
        </Field>
        {replay?.steps.map((step, index) => (
          <div
            key={step.step_id}
            className="grid grid-cols-[56px_1fr_220px] gap-3 rounded-md border border-stone-200 p-3"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-md border border-cyan-200 bg-cyan-50 text-sm font-semibold text-cyan-800">
              {index + 1}
            </div>
            <div className="min-w-0">
              <div className="font-medium text-stone-900">{step.step_id}</div>
              <p className="mt-1 text-sm leading-5 text-stone-600">
                {step.rationale}
              </p>
              <p className="mt-1 text-xs text-stone-500">
                dominant {step.impact_summary.dominant_branch_change}
              </p>
            </div>
            <div className="grid gap-1 text-xs">
              <span>delta_mass {format(step.impact_summary.delta_mass)}</span>
              <span>changed {step.impact_summary.changed_node_count}</span>
              <span>margin {format(step.impact_summary.margin_change)}</span>
            </div>
          </div>
        ))}
        {!chain ? (
          <p className="text-sm text-stone-500">
            reading_chain seed がありません。
          </p>
        ) : null}
      </div>
    </Panel>
  );
}

function EducationTab({
  logs,
  utilities,
  nodes,
}: {
  logs: ReturnType<typeof buildTeachingLogs>;
  utilities: ReturnType<typeof evaluateReadingUtilities>;
  nodes: KnowledgeNode[];
}) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return (
    <div className="grid gap-3">
      <Panel title="Educational Explanation Panel">
        <div className="grid gap-2 p-3">
          {logs.map((log) => (
            <div
              key={`${log.case_id}_${log.action_id}`}
              className="grid gap-2 rounded-md border border-stone-200 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-stone-900">
                  {log.explanation_short}
                </h3>
                <div className="flex flex-wrap gap-1">
                  {log.key_terms.map((term) => (
                    <Badge key={term} tone="cyan">
                      {term}
                    </Badge>
                  ))}
                </div>
              </div>
              <p className="text-sm leading-6 text-stone-600">
                {log.explanation_full}
              </p>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Reading Utility Drill-down">
        <div className="grid gap-2 p-3">
          {utilities.slice(0, 8).map((utility) => (
            <div
              key={utility.target_id}
              className="grid grid-cols-[1fr_96px_96px_96px_96px] items-center gap-3 rounded-md border border-stone-200 p-3 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">
                  {nodeById.get(utility.target_id)?.title ?? utility.target_id}
                </div>
                <div className="truncate text-xs text-stone-500">
                  selective {format(utility.selective_pruning_ratio)} / cost{" "}
                  {format(utility.cost_estimate)}
                </div>
              </div>
              <MetricBox label="utility" value={utility.utility_score} />
              <MetricBox label="global" value={utility.global_impact_score} />
              <MetricBox
                label="ambiguity"
                value={utility.ambiguity_reduction}
              />
              <MetricBox label="margin" value={utility.projected_margin_gain} />
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function SimulationSummary({
  simulation,
  nodes,
}: {
  simulation: ReturnType<typeof simulatePruningAction>;
  nodes: KnowledgeNode[];
}) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const changed = Object.keys(simulation.after.node_probabilities)
    .map((id) => {
      const before = simulation.before.node_probabilities[id] ?? 0;
      const after = simulation.after.node_probabilities[id] ?? 0;
      return { id, before, after, delta: after - before };
    })
    .filter((item) => Math.abs(item.delta) > 0.0001)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 8);

  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-4 gap-2">
        <MetricBox
          label="delta_mass"
          value={simulation.impact_summary.delta_mass}
        />
        <MetricBox
          label="changed"
          value={simulation.impact_summary.changed_node_count}
        />
        <MetricBox
          label="ambiguity"
          value={simulation.impact_summary.ambiguity_change}
        />
        <MetricBox
          label="margin"
          value={simulation.impact_summary.margin_change}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ProbabilitySnapshot
          title="Before"
          snapshot={simulation.before}
          nodes={nodes}
        />
        <ProbabilitySnapshot
          title="After"
          snapshot={simulation.after}
          nodes={nodes}
        />
      </div>
      <div className="grid gap-1.5 rounded-md border border-stone-200 p-3">
        <div className="text-sm font-medium">Waterfall movement summary</div>
        {changed.map((item) => (
          <div
            key={item.id}
            className="grid grid-cols-[160px_1fr_64px] items-center gap-2 text-xs"
          >
            <span className="truncate">
              {nodeById.get(item.id)?.title ?? item.id}
            </span>
            <Progress value={Math.min(1, Math.abs(item.delta) * 3)} />
            <span className="text-right tabular-nums">
              {item.delta > 0 ? "+" : ""}
              {format(item.delta)}
            </span>
          </div>
        ))}
        <p className="text-xs text-stone-500">
          {simulation.impact_summary.dominant_branch_change}
        </p>
      </div>
    </div>
  );
}

function ProbabilitySnapshot({
  title,
  snapshot,
  nodes,
}: {
  title: string;
  snapshot: ReturnType<typeof simulatePruningAction>["before"];
  nodes: KnowledgeNode[];
}) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const ranked = Object.entries(snapshot.node_probabilities)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  return (
    <div className="grid gap-2 rounded-md border border-stone-200 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <Badge>margin {format(snapshot.margin)}</Badge>
      </div>
      {ranked.map(([id, value]) => (
        <div
          key={id}
          className="grid grid-cols-[120px_1fr_48px] items-center gap-2 text-xs"
        >
          <span className="truncate">{nodeById.get(id)?.title ?? id}</span>
          <Progress value={value} />
          <span className="text-right tabular-nums">{format(value)}</span>
        </div>
      ))}
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "stone",
}: {
  label: string;
  value: number;
  tone?: "stone" | "cyan" | "amber" | "emerald";
}) {
  return (
    <div className="rounded-md border border-stone-200 p-3">
      <div className="text-xs text-stone-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-stone-950">
        {value}
      </div>
      <Badge tone={tone}>active</Badge>
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-stone-200 bg-stone-50 px-2 py-1.5">
      <div className="truncate text-[11px] text-stone-500">{label}</div>
      <div className="text-sm font-semibold tabular-nums text-stone-900">
        {format(value)}
      </div>
    </div>
  );
}

function Progress({ value }: { value: number }) {
  const width = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="h-2 overflow-hidden rounded-full bg-stone-200">
      <div
        className="h-full rounded-full bg-cyan-700"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function signTone(sign: string): "stone" | "amber" | "rose" | "emerald" {
  if (sign === "+") return "emerald";
  if (sign === "-") return "rose";
  if (sign === "mixed") return "amber";
  return "stone";
}

function format(value: number) {
  return Number.isFinite(value) ? value.toFixed(3) : "0.000";
}

function formatContext(context: unknown) {
  if (Array.isArray(context)) return context.join(", ");
  if (typeof context === "string") return context;
  return "none";
}
