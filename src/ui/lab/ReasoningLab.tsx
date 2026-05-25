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
import {
  averagingSafetyLabels,
  combinationModeLabels,
  influenceSignLabels,
  lockModeLabels,
  pruningActionTypeLabels,
} from "../../domain/labels";
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
  { id: "graph", label: "グラフ表示", icon: Route },
  { id: "metric", label: "指標レンズ", icon: SearchCheck },
  { id: "concentration", label: "集中度レンズ", icon: BarChart3 },
  { id: "pruning", label: "枝刈りラボ", icon: GitCompare },
  { id: "lock", label: "ロック分析", icon: LockKeyhole },
  { id: "ambiguity", label: "曖昧性 / 観測計画", icon: Waves },
  { id: "chain", label: "読み筋タイムライン", icon: Sigma },
  { id: "education", label: "教育用説明", icon: BookOpen },
] as const;

type TabId = (typeof tabs)[number]["id"];
export type ReasoningLabScope = "all" | "pruning" | "explanation";

const tabIdsByScope: Record<ReasoningLabScope, TabId[]> = {
  all: tabs.map((tab) => tab.id),
  pruning: ["pruning", "lock", "ambiguity"],
  explanation: ["concentration", "chain", "education"],
};

function defaultTabForScope(scope: ReasoningLabScope, initialTab?: TabId) {
  const tabIds = tabIdsByScope[scope];
  return initialTab && tabIds.includes(initialTab) ? initialTab : tabIds[0];
}

const lockOptions = lockModes.filter(
  (mode) => !["hard", "soft"].includes(mode),
);

const pruneActionLabels = {
  prune: "枝刈り",
  downweight: "弱める",
  keep: "保持",
  observe: "観測",
} as const;

const metricLabels: Record<string, string> = {
  entropy: "エントロピー",
  top_k_mass: "上位候補質量",
  peak_mass: "ピーク質量",
  hhi: "集中度",
  delta_mass: "質量差分",
  changed: "変更数",
  ambiguity: "曖昧性",
  margin: "余裕度",
  sign_gain: "方向改善",
  margin_gain: "余裕度改善",
  safety_change: "安全度変化",
  utility: "有用度",
  global: "全体影響",
};

const concentrationScopeLabels: Record<string, string> = {
  choice_group: "選択候補群",
  concentration_group: "集中度グループ",
  inference_subgraph: "推論サブグラフ",
};

const ambiguityStatusLabels: Record<string, string> = {
  mixed: "混合",
  unknown: "不明",
  conflicting: "衝突",
};

export function ReasoningLab({
  scope = "all",
  initialTab,
}: {
  scope?: ReasoningLabScope;
  initialTab?: TabId;
}) {
  const doc = useAppStore((state) => state.doc);
  const updateNode = useAppStore((state) => state.updateNode);
  const recordReasoningLabSimulation = useAppStore(
    (state) => state.recordReasoningLabSimulation,
  );
  const [activeTab, setActiveTab] = useState<TabId>(() =>
    defaultTabForScope(scope, initialTab),
  );
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
  const [rationale, setRationale] =
    useState("読みの影響を適用前後で確認する。");
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
  const visibleTabs = useMemo(() => {
    const visibleIds = new Set(tabIdsByScope[scope]);
    return tabs.filter((tab) => visibleIds.has(tab.id));
  }, [scope]);
  const fallbackTab = defaultTabForScope(scope, initialTab);
  const effectiveActiveTab = tabIdsByScope[scope].includes(activeTab)
    ? activeTab
    : fallbackTab;

  const renderTab = () => {
    if (effectiveActiveTab === "graph") {
      return (
        <GraphViewTab
          semanticCount={doc.nodes.length - inference.nodes.length}
          inferenceCount={inference.nodes.length}
          influenceCount={influence.influence_edges.length}
          concentrationCount={concentration.length}
        />
      );
    }
    if (effectiveActiveTab === "metric") {
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
    if (effectiveActiveTab === "concentration") {
      return (
        <ConcentrationLensTab items={concentration} docNodes={doc.nodes} />
      );
    }
    if (effectiveActiveTab === "pruning") {
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
    if (effectiveActiveTab === "lock") {
      return (
        <LockAnalysisTab
          nodes={inference.nodes}
          safety={averagingSafety}
          updateNode={updateNode}
        />
      );
    }
    if (effectiveActiveTab === "ambiguity") {
      return <AmbiguityTab influence={influence} />;
    }
    if (effectiveActiveTab === "chain") {
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
          <h2 className="text-sm font-semibold text-stone-950">麻雀思考ラボ</h2>
          <p className="mt-1 text-xs leading-5 text-stone-500">
            確率質量、枝刈り影響、ロック、曖昧性、読み筋再生を同じワークスペース上で比較します。
          </p>
        </div>
        <div className="grid gap-1">
          {visibleTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <Button
                key={tab.id}
                variant={effectiveActiveTab === tab.id ? "primary" : "ghost"}
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
      <Panel title="レイヤー分離">
        <div className="grid grid-cols-4 gap-3 p-3">
          <Stat label="意味ノード" value={semanticCount} />
          <Stat label="推論ノード" value={inferenceCount} tone="cyan" />
          <Stat label="影響エッジ" value={influenceCount} tone="amber" />
          <Stat
            label="集中度セット"
            value={concentrationCount}
            tone="emerald"
          />
        </div>
      </Panel>
      <Panel title="試作版の境界">
        <div className="grid gap-2 p-3 text-sm leading-6 text-stone-700">
          <p>
            知識グラフは概念や根拠の地図、確率推論レイヤーは選択候補群の木と有向非巡回グラフ、
            方向付き影響レイヤーは指標への符号付き影響として分けています。
          </p>
          <p>
            思考ラボは派生計算の比較ビューです。一般の循環確率グラフや
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
      <Panel title="指標レンズ">
        <div className="grid gap-3 p-3">
          <Field label="指標">
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
                      方向 {influenceSignLabels[item.edge.sign]}
                    </Badge>
                    <Badge>影響量 {format(item.edge.magnitude)}</Badge>
                    <Badge>確信度 {format(item.edge.confidence)}</Badge>
                  </div>
                </div>
                <p className="text-xs leading-5 text-stone-500">
                  文脈: {formatContext(item.edge.context_gate)} / 合成:{" "}
                  {combinationModeLabels[item.edge.combination_mode]}
                </p>
                <Progress value={Math.min(1, Math.abs(item.signed_score))} />
              </div>
            ))}
          </div>
        </div>
      </Panel>
      <Panel title="枝ベクトル要約">
        <div className="grid gap-2 p-3">
          {branchVectors.map((vector) => (
            <div
              key={vector.branch_id}
              className="grid grid-cols-[1.2fr_1fr_1fr_1fr] items-center gap-3 rounded-md border border-stone-200 p-3 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{vector.title}</div>
                <div className="text-xs text-stone-500">
                  主方向 {influenceSignLabels[vector.dominant_direction]}、衝突{" "}
                  {vector.conflict_count}
                </div>
              </div>
              <Progress value={1 - vector.uncertainty} />
              <Badge tone={vector.prune_action === "prune" ? "rose" : "cyan"}>
                {pruneActionLabels[vector.prune_action]}
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
    <Panel title="集中度レンズ">
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
                  <Badge tone="cyan">
                    {concentrationScopeLabels[item.scope] ?? item.scope}
                  </Badge>
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
              <MetricBox
                label={metricLabels.entropy}
                value={item.metrics.entropy}
              />
              <MetricBox
                label={metricLabels.top_k_mass}
                value={item.metrics.top_k_mass}
              />
              <MetricBox
                label={metricLabels.peak_mass}
                value={item.metrics.peak_mass}
              />
              <MetricBox label={metricLabels.hhi} value={item.metrics.hhi} />
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
      <Panel title="枝刈り影響シミュレーター">
        <div className="grid grid-cols-[320px_1fr] gap-3 p-3">
          <div className="grid content-start gap-3">
            <Field label="操作">
              <Select
                value={actionType}
                onChange={(event) =>
                  setActionType(event.target.value as PruningActionType)
                }
              >
                {pruningActionTypes.map((type) => (
                  <option key={type} value={type}>
                    {pruningActionTypeLabels[type]}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="対象">
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
              label="強さ"
              hint="上位候補保持では整数扱い、それ以外は0-1の強さとして扱います。"
            >
              <Input
                type="number"
                step="0.05"
                min="0"
                value={strength}
                onChange={(event) => setStrength(Number(event.target.value))}
              />
            </Field>
            <Field label="根拠">
              <Textarea
                value={rationale}
                onChange={(event) => setRationale(event.target.value)}
              />
            </Field>
            <Button variant="primary" onClick={onSave} disabled={!simulation}>
              差分ログを保存
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
    <Panel title="ノードロック / 状態固定分析">
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
                    確率 {format(node.posterior_probability ?? 0)}
                  </Badge>
                  <Badge>{node.choice_group_id ?? "単独"}</Badge>
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
                    {lockModeLabels[mode]}
                  </option>
                ))}
              </Select>
              <Input
                type="number"
                step="0.05"
                value={node.lock_value ?? ""}
                placeholder="値"
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
                  平均化{" "}
                  {item?.label ? averagingSafetyLabels[item.label] : "不明"}
                </Badge>
                <p className="mt-1 truncate text-xs text-stone-500">
                  {item?.reasons.join(" / ") ?? "推定対象なし"}
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
      <Panel title="曖昧性パネル">
        <div className="grid gap-2 p-3">
          {influence.ambiguities.map((item) => (
            <div
              key={item.id}
              className="grid grid-cols-[160px_1fr_220px] items-center gap-3 rounded-md border border-stone-200 p-3"
            >
              <div>
                <Badge tone={item.status === "unknown" ? "stone" : "amber"}>
                  {ambiguityStatusLabels[item.status] ?? item.status}
                </Badge>
                <div className="mt-1 text-xs text-stone-500">
                  未解決度 {format(item.unresolved_score)}
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
                  枝刈り候補
                </Badge>
                <Badge tone={item.downweight_candidate ? "amber" : "stone"}>
                  弱め候補
                </Badge>
                <Badge
                  tone={item.observe_candidate_ids.length ? "cyan" : "stone"}
                >
                  観測候補 {item.observe_candidate_ids.length}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="観測計画">
        <div className="grid gap-2 p-3">
          {influence.observation_plan.map((item) => (
            <div
              key={item.node.id}
              className="grid grid-cols-[1fr_140px_140px_140px] items-center gap-3 rounded-md border border-stone-200 p-3 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{item.node.title}</div>
                <div className="truncate text-xs text-stone-500">
                  解消対象 {item.target_titles.join(" / ")}
                </div>
              </div>
              <MetricBox
                label={metricLabels.sign_gain}
                value={item.node.expected_sign_gain ?? 0}
              />
              <MetricBox
                label={metricLabels.margin_gain}
                value={item.node.expected_margin_gain ?? 0}
              />
              <MetricBox
                label={metricLabels.safety_change}
                value={item.node.pruning_safety_change ?? 0}
              />
            </div>
          ))}
          {influence.observation_plan.length === 0 ? (
            <p className="text-sm text-stone-500">観測候補がまだありません。</p>
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
    <Panel title="読み筋タイムライン">
      <div className="grid gap-3 p-3">
        <Field label="読み筋">
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
                主枝 {step.impact_summary.dominant_branch_change}
              </p>
            </div>
            <div className="grid gap-1 text-xs">
              <span>質量差分 {format(step.impact_summary.delta_mass)}</span>
              <span>変更数 {step.impact_summary.changed_node_count}</span>
              <span>余裕度 {format(step.impact_summary.margin_change)}</span>
            </div>
          </div>
        ))}
        {!chain ? (
          <p className="text-sm text-stone-500">
            読み筋の初期データがありません。
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
      <Panel title="教育用説明">
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
      <Panel title="読み有用度の詳細">
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
                  選択枝刈り {format(utility.selective_pruning_ratio)} / コスト{" "}
                  {format(utility.cost_estimate)}
                </div>
              </div>
              <MetricBox
                label={metricLabels.utility}
                value={utility.utility_score}
              />
              <MetricBox
                label={metricLabels.global}
                value={utility.global_impact_score}
              />
              <MetricBox
                label={metricLabels.ambiguity}
                value={utility.ambiguity_reduction}
              />
              <MetricBox
                label={metricLabels.margin}
                value={utility.projected_margin_gain}
              />
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
          label={metricLabels.delta_mass}
          value={simulation.impact_summary.delta_mass}
        />
        <MetricBox
          label={metricLabels.changed}
          value={simulation.impact_summary.changed_node_count}
        />
        <MetricBox
          label={metricLabels.ambiguity}
          value={simulation.impact_summary.ambiguity_change}
        />
        <MetricBox
          label={metricLabels.margin}
          value={simulation.impact_summary.margin_change}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ProbabilitySnapshot
          title="適用前"
          snapshot={simulation.before}
          nodes={nodes}
        />
        <ProbabilitySnapshot
          title="適用後"
          snapshot={simulation.after}
          nodes={nodes}
        />
      </div>
      <div className="grid gap-1.5 rounded-md border border-stone-200 p-3">
        <div className="text-sm font-medium">変化量の要約</div>
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
        <Badge>余裕度 {format(snapshot.margin)}</Badge>
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
      <Badge tone={tone}>有効</Badge>
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
  return "なし";
}
