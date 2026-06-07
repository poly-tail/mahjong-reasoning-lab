import { AlertTriangle, Eye, Gauge } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  combinationModeLabels,
  edgeTypeLabels,
  influenceSignLabels,
} from "../../domain/labels";
import {
  getInfluenceModel,
  getMetricInfluences,
  type AmbiguityItem,
  type BranchVector,
  type ObservationPlanItem,
} from "../../domain/influence";
import type { InfluenceSign, KnowledgeEdge } from "../../domain/schema";
import { cn } from "../../shared/cn";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Select } from "../components/form";
import { Panel } from "../components/panel";

const signTone: Record<InfluenceSign, "emerald" | "rose" | "amber" | "stone"> =
  {
    "+": "emerald",
    "-": "rose",
    mixed: "amber",
    unknown: "stone",
  };

const ambiguityStatusLabels: Record<AmbiguityItem["status"], string> = {
  mixed: "混合",
  unknown: "不明",
  conflicting: "衝突",
};

const pruneActionLabels: Record<BranchVector["prune_action"], string> = {
  prune: "枝刈り",
  downweight: "弱める",
  keep: "保持",
  observe: "観測",
};

export function InfluenceWorkbench() {
  const doc = useAppStore((state) => state.doc);
  const setSelection = useAppStore((state) => state.setSelection);
  const selectedNodeIds = useAppStore((state) => state.selectedNodeIds);
  const model = useMemo(() => getInfluenceModel(doc), [doc]);
  const [metricId, setMetricId] = useState(model.metrics[0]?.id ?? "");

  const activeMetricId = model.metrics.some((metric) => metric.id === metricId)
    ? metricId
    : (model.metrics[0]?.id ?? "");
  const metricInfluences = useMemo(
    () => getMetricInfluences(doc, activeMetricId),
    [activeMetricId, doc],
  );

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[330px_minmax(0,1fr)_400px] gap-3 p-3">
      <MetricLens
        metrics={model.metrics}
        metricId={activeMetricId}
        setMetricId={setMetricId}
        influences={metricInfluences}
        selectedNodeIds={selectedNodeIds}
        setSelection={setSelection}
      />
      <main className="grid min-h-0 grid-rows-[minmax(0,1fr)_330px] gap-3">
        <AmbiguityPanel
          ambiguities={model.ambiguities}
          setSelection={setSelection}
        />
        <BranchVectorSummary
          vectors={model.branch_vectors}
          metrics={model.metrics}
          setSelection={setSelection}
        />
      </main>
      <ObservationPlanner
        items={model.observation_plan}
        ambiguities={model.ambiguities}
        setSelection={setSelection}
      />
    </div>
  );
}

function MetricLens({
  metrics,
  metricId,
  setMetricId,
  influences,
  selectedNodeIds,
  setSelection,
}: {
  metrics: { id: string; title: string }[];
  metricId: string;
  setMetricId: (id: string) => void;
  influences: ReturnType<typeof getMetricInfluences>;
  selectedNodeIds: string[];
  setSelection: (nodeIds: string[], edgeIds: string[]) => void;
}) {
  return (
    <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
      <div className="sticky top-0 z-10 border-b border-stone-200 bg-white px-3 py-2">
        <div className="mb-2 flex items-center gap-2">
          <Gauge className="h-4 w-4 text-stone-500" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-stone-950">指標レンズ</h2>
        </div>
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
      </div>
      <div className="grid gap-2 p-2">
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-2 text-xs leading-5 text-stone-600">
          方向はノード属性ではなく、この指標へ向かう影響エッジの属性です。
          同じ起点でも指標や文脈で逆方向を持てます。
        </div>
        {influences.map((item) => (
          <button
            key={item.edge.id}
            type="button"
            onClick={() =>
              setSelection([item.source.id, item.metric.id], [item.edge.id])
            }
            className={cn(
              "rounded-lg border p-2 text-left",
              selectedNodeIds.includes(item.source.id)
                ? "border-cyan-700 bg-cyan-50"
                : "border-stone-200 bg-white hover:bg-stone-50",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-stone-950">
                  {item.source.title}
                </div>
                <div className="mt-1 text-xs text-stone-500">
                  {edgeTypeLabels[item.edge.type]} /{" "}
                  {combinationModeLabels[item.edge.combination_mode]}
                </div>
              </div>
              <Badge tone={signTone[item.edge.sign]}>
                {influenceSignLabels[item.edge.sign]}
              </Badge>
            </div>
            <InfluenceBar edge={item.edge} />
            <div className="mt-1 text-xs text-stone-600">
              影響ウェイト {formatScore(item.edge.magnitude)} / 軸確信度{" "}
              {formatScore(item.edge.confidence)}
            </div>
            <ContextLine edge={item.edge} />
          </button>
        ))}
      </div>
    </aside>
  );
}

function AmbiguityPanel({
  ambiguities,
  setSelection,
}: {
  ambiguities: AmbiguityItem[];
  setSelection: (nodeIds: string[], edgeIds: string[]) => void;
}) {
  return (
    <Panel
      title="曖昧性パネル"
      action={
        <div className="flex items-center gap-1 text-xs text-stone-500">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          {ambiguities.length}
        </div>
      }
    >
      <div className="max-h-full overflow-auto p-3">
        <div className="grid gap-2">
          {ambiguities.length ? (
            ambiguities.map((item) => (
              <article
                key={item.id}
                className="rounded-lg border border-stone-200 p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-stone-950">
                      {item.metric_title}
                    </h3>
                    <p className="mt-1 text-xs text-stone-600">
                      {item.source_titles.join(" / ")}
                    </p>
                  </div>
                  <Badge
                    tone={
                      item.status === "conflicting"
                        ? "rose"
                        : item.status === "mixed"
                          ? "amber"
                          : "stone"
                    }
                  >
                    {ambiguityStatusLabels[item.status]}
                  </Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.prune_candidate ? (
                    <Badge tone="emerald">枝刈り候補</Badge>
                  ) : null}
                  {item.downweight_candidate ? (
                    <Badge tone="amber">弱め候補</Badge>
                  ) : null}
                  {item.observe_candidate_ids.length ? (
                    <Badge tone="cyan">観測候補</Badge>
                  ) : null}
                  {!item.prune_candidate && item.status !== "unknown" ? (
                    <Badge tone="rose">枝刈り警告</Badge>
                  ) : null}
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-stone-600">
                  <span>未解決度 {item.unresolved_score.toFixed(2)}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setSelection([], item.influence_edge_ids)}
                  >
                    エッジ
                  </Button>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-lg border border-stone-200 p-3 text-sm text-stone-600">
              混合 / 不明 / 衝突している影響はありません。
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function BranchVectorSummary({
  vectors,
  metrics,
  setSelection,
}: {
  vectors: BranchVector[];
  metrics: { id: string; title: string }[];
  setSelection: (nodeIds: string[], edgeIds: string[]) => void;
}) {
  return (
    <Panel title="枝ベクトル要約">
      <div className="h-full overflow-auto p-3">
        <div className="grid gap-2">
          {vectors.map((vector) => (
            <article
              key={vector.branch_id}
              className="rounded-lg border border-stone-200 p-2"
            >
              <div className="flex items-start justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setSelection([vector.branch_id], [])}
                  className="min-w-0 truncate text-left text-sm font-semibold text-stone-950"
                >
                  {vector.title}
                </button>
                <Badge tone={signTone[vector.dominant_direction]}>
                  {influenceSignLabels[vector.dominant_direction]}
                </Badge>
              </div>
              <div className="mt-2 grid grid-cols-4 gap-1">
                {metrics.slice(0, 8).map((metric) => {
                  const score = vector.metric_scores[metric.id] ?? 0;
                  return (
                    <div
                      key={metric.id}
                      className="rounded border border-stone-200 p-1"
                    >
                      <div className="truncate text-[11px] text-stone-500">
                        {metric.title}
                      </div>
                      <div
                        className={cn(
                          "text-xs font-semibold tabular-nums",
                          score > 0.05
                            ? "text-emerald-700"
                            : score < -0.05
                              ? "text-rose-700"
                              : "text-stone-500",
                        )}
                      >
                        {score.toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge
                  tone={vector.prune_action === "prune" ? "rose" : "stone"}
                >
                  {pruneActionLabels[vector.prune_action]}
                </Badge>
                <Badge>不確実性 {vector.uncertainty.toFixed(2)}</Badge>
                <Badge>衝突 {vector.conflict_count}</Badge>
                <Badge>{Math.round(vector.prune_confidence * 100)}%</Badge>
              </div>
              <p className="mt-1 text-xs text-stone-600">
                {vector.prune_reason}
              </p>
            </article>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function ObservationPlanner({
  items,
  ambiguities,
  setSelection,
}: {
  items: ObservationPlanItem[];
  ambiguities: AmbiguityItem[];
  setSelection: (nodeIds: string[], edgeIds: string[]) => void;
}) {
  const unresolvedTargets = new Set(
    ambiguities.flatMap((item) => item.observe_candidate_ids),
  );
  return (
    <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
      <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
        <div className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-stone-500" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-stone-950">観測計画</h2>
        </div>
        <Badge tone="cyan">効果/コスト</Badge>
      </div>
      <div className="grid gap-2 p-2">
        {items.map((item) => (
          <article
            key={item.node.id}
            className={cn(
              "rounded-lg border p-2",
              unresolvedTargets.has(item.node.id)
                ? "border-cyan-300 bg-cyan-50"
                : "border-stone-200 bg-white",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <button
                type="button"
                onClick={() => setSelection([item.node.id], [])}
                className="min-w-0 truncate text-left text-sm font-semibold text-stone-950"
              >
                {item.node.title}
              </button>
              <Badge tone="emerald">{item.gain_cost_ratio.toFixed(2)}</Badge>
            </div>
            <p className="mt-1 text-xs leading-4 text-stone-600">
              {item.node.summary}
            </p>
            <div className="mt-2 grid grid-cols-3 gap-1 text-xs text-stone-600">
              <div className="rounded border border-stone-200 p-1">
                方向 {item.node.expected_sign_gain?.toFixed(2) ?? "-"}
              </div>
              <div className="rounded border border-stone-200 p-1">
                重み {item.node.expected_weight_gain?.toFixed(2) ?? "-"}
              </div>
              <div className="rounded border border-stone-200 p-1">
                コスト {item.node.observation_cost?.toFixed(2) ?? "-"}
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {item.target_titles.map((title) => (
                <Badge key={title}>{title}</Badge>
              ))}
            </div>
          </article>
        ))}
      </div>
    </aside>
  );
}

function InfluenceBar({ edge }: { edge: KnowledgeEdge }) {
  const width = Math.max(
    2,
    Math.min(100, edge.magnitude * edge.confidence * 100),
  );
  const color =
    edge.sign === "+"
      ? "bg-emerald-600"
      : edge.sign === "-"
        ? "bg-rose-600"
        : edge.sign === "mixed"
          ? "bg-amber-500"
          : "bg-stone-400";
  return (
    <div className="mt-2 h-2 overflow-hidden rounded bg-stone-100">
      <div
        className={cn("h-full rounded", color)}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function ContextLine({ edge }: { edge: KnowledgeEdge }) {
  if (!edge.context_gate) return null;
  const value = Array.isArray(edge.context_gate)
    ? edge.context_gate.join(", ")
    : edge.context_gate;
  return <div className="mt-1 text-xs text-stone-500">文脈: {value}</div>;
}

function formatScore(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value * 100)))}/100`;
}
