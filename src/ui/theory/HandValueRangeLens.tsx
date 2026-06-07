import { Gauge, HelpCircle, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import { useAppStore } from "../../app/store";
import {
  handValueAxes,
  handValueRangeAxes,
  scoreSituationThresholdFactors,
  type HandValueAxisId,
} from "../../domain/mahjongTaxonomy";
import { influenceSignLabels, nodeTypeLabels } from "../../domain/labels";
import { getMetricInfluences } from "../../domain/influence";
import type { InfluenceSign, KnowledgeNode } from "../../domain/schema";
import { Badge } from "../components/badge";
import { Panel } from "../components/panel";

const axisTags = handValueRangeAxes.reduce(
  (accumulator, axis) => {
    accumulator[axis.id] = [
      axis.id,
      axis.label,
      axis.shortLabel,
      ...axis.tags,
      ...axis.legacyAliases,
      ...axis.metricTitles,
    ];
    return accumulator;
  },
  {} as Record<HandValueAxisId, readonly string[]>,
);

const handValueMarkers = [
  "hand_value_range",
  "手牌価値",
  ...Object.values(axisTags).flat(),
];

export function HandValueRangeLens() {
  const doc = useAppStore((state) => state.doc);
  const activeCase = useAppStore((state) => {
    const workspace = state.doc;
    return (
      workspace.cases.find((item) => item.id === workspace.active_case_id) ??
      workspace.cases[0]
    );
  });

  const axisModels = useMemo(
    () =>
      handValueAxes.map((axis) => {
        const metrics = doc.nodes.filter(
          (node) =>
            node.type === "metric" && hasAnyMarker(node, axisTags[axis.id]),
        );
        const influences = metrics.flatMap((metric) =>
          getMetricInfluences(doc, metric.id),
        );
        return {
          ...axis,
          metrics,
          influences,
          summary: summarizeSigns(influences.map((item) => item.edge.sign)),
        };
      }),
    [doc],
  );

  const observationCandidates = doc.nodes.filter(
    (node) =>
      node.type === "observation_candidate" &&
      (hasAnyMarker(node, handValueMarkers) ||
        node.resolves_targets.some((targetId) =>
          axisModels.some((axis) =>
            axis.metrics.some((metric) => metric.id === targetId),
          ),
        )),
  );

  const caseNodes = activeCase
    ? doc.nodes.filter((node) => activeCase.attached_node_ids.includes(node.id))
    : [];

  return (
    <main className="min-h-0 flex-1 overflow-auto p-3">
      <div className="grid gap-3">
        <Panel title="進行度・聴牌率 / 打点 / 待ち・形の良さ / 点数状況・行動閾値のどこが動いたか">
          <div className="grid gap-3 p-3">
            <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm leading-6 text-stone-700">
              <p>
                4軸は読みの影響射影先であり、最終的な押し引き/牌選択軸ではありません。影響ウェイトは各軸を独立にどれだけ動かすかを表す0〜100の重みスコアで、4軸の合計を100にする必要はありません。
              </p>
              <p className="mt-1">
                候補確率と未配分確率は%で扱います。影響ウェイトと軸確信度は%ではなく、0〜100のスコアとして扱います。
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
              {axisModels.map((axis) => (
                <AxisCard key={axis.id} axis={axis} />
              ))}
            </div>
          </div>
        </Panel>

        <div className="grid grid-cols-[1.1fr_0.9fr] gap-3">
          <Panel title="点数状況・行動閾値で見る条件">
            <div className="grid grid-cols-3 gap-2 p-3">
              {scoreSituationThresholdFactors.map((modifier) => (
                <div
                  key={modifier.id}
                  className="rounded-md border border-stone-200 bg-stone-50 p-2"
                >
                  <div className="text-sm font-medium text-stone-900">
                    {modifier.label}
                  </div>
                  <div className="mt-1 text-xs text-stone-500">
                    {modifier.id}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="軸固定 / 条件付き推論">
            <div className="grid gap-2 p-3 text-sm text-stone-700">
              {[
                "非テンパイと仮定する",
                "愚形固定と仮定する",
                "染め本線を残す",
                "条件戦で確認優先度を上げる",
              ].map((item) => (
                <div
                  key={item}
                  className="flex items-center gap-2 rounded-md border border-stone-200 p-2"
                >
                  <Gauge className="h-4 w-4 text-cyan-700" aria-hidden="true" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="grid grid-cols-[1fr_1fr] gap-3">
          <Panel title="この局面に紐づいた手牌価値ノード">
            <div className="grid gap-2 p-3">
              {caseNodes
                .filter((node) => hasHandValueMarker(node))
                .map((node) => (
                  <NodeRow key={node.id} node={node} />
                ))}
              {caseNodes.filter((node) => hasHandValueMarker(node)).length ===
              0 ? (
                <p className="text-sm text-stone-500">
                  active case に手牌価値系ノードはまだ紐づいていません。
                </p>
              ) : null}
            </div>
          </Panel>

          <Panel title="追加観測候補">
            <div className="grid gap-2 p-3">
              {observationCandidates.slice(0, 8).map((node) => (
                <NodeRow key={node.id} node={node} />
              ))}
              {observationCandidates.length === 0 ? (
                <p className="text-sm text-stone-500">
                  4軸の解像に対応する観測候補がまだありません。
                </p>
              ) : null}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}

function AxisCard({
  axis,
}: {
  axis: {
    id: string;
    label: string;
    role: readonly string[];
    metrics: KnowledgeNode[];
    influences: ReturnType<typeof getMetricInfluences>;
    summary: InfluenceSign;
  };
}) {
  return (
    <section className="rounded-md border border-stone-200 bg-stone-50 p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-stone-950">{axis.label}</h3>
        <Badge tone={signTone(axis.summary)}>
          {influenceSignLabels[axis.summary]}
        </Badge>
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-stone-500">
        {axis.role.slice(0, 4).join(" / ")}
      </p>
      <div className="mt-3 grid gap-2">
        {axis.metrics.map((metric) => (
          <div
            key={metric.id}
            className="rounded border border-stone-200 bg-white p-2"
          >
            <div className="truncate text-sm font-medium text-stone-900">
              {metric.title}
            </div>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-stone-500">
              {metric.summary}
            </p>
          </div>
        ))}
        {axis.metrics.length === 0 ? (
          <p className="text-sm text-stone-500">
            対応する metric node がまだありません。
          </p>
        ) : null}
      </div>
      <div className="mt-3 grid gap-1.5">
        {axis.influences.slice(0, 5).map((item) => (
          <div
            key={item.edge.id}
            className="flex flex-wrap items-center gap-2 text-xs"
          >
            <span className="min-w-0 flex-1 truncate text-stone-600">
              {item.source.title}
            </span>
            <Badge tone={signTone(item.edge.sign)}>
              {item.edge.sign === "+" ? (
                <TrendingUp className="h-3 w-3" aria-hidden="true" />
              ) : item.edge.sign === "-" ? (
                <TrendingDown className="h-3 w-3" aria-hidden="true" />
              ) : (
                <HelpCircle className="h-3 w-3" aria-hidden="true" />
              )}
              {influenceSignLabels[item.edge.sign]}
            </Badge>
            <Badge tone="stone">
              影響ウェイト {formatScore(item.edge.magnitude)}
            </Badge>
            <Badge tone="stone">
              軸確信度 {formatScore(item.edge.confidence)}
            </Badge>
          </div>
        ))}
      </div>
      {axis.summary === "mixed" || axis.summary === "unknown" ? (
        <p className="mt-3 text-xs leading-5 text-amber-700">
          この軸は確定しません。不確実なものを勝手に hard prune
          しないでください。
        </p>
      ) : null}
    </section>
  );
}

function NodeRow({ node }: { node: KnowledgeNode }) {
  return (
    <div className="rounded-md border border-stone-200 p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-stone-900">
          {node.title}
        </span>
        <Badge tone="cyan">{nodeTypeLabels[node.type]}</Badge>
      </div>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-stone-500">
        {node.summary}
      </p>
      <div className="mt-1 flex flex-wrap gap-1">
        {node.tags.slice(0, 5).map((tag) => (
          <Badge key={tag}>{tag}</Badge>
        ))}
      </div>
    </div>
  );
}

function hasHandValueMarker(node: KnowledgeNode) {
  return (
    hasAnyMarker(node, axisTags.progress_tenpai_axis) ||
    hasAnyMarker(node, axisTags.value_axis) ||
    hasAnyMarker(node, axisTags.wait_shape_quality_axis) ||
    hasAnyMarker(node, axisTags.score_situation_threshold_axis) ||
    hasAnyMarker(node, ["hand_value_range", "手牌価値"])
  );
}

function hasAnyMarker(node: KnowledgeNode, markers: readonly string[]) {
  const lowerTags = node.tags.map((tag) => tag.toLowerCase());
  const haystack = [
    node.title,
    node.summary,
    node.description,
    node.notes,
    ...node.tags,
  ]
    .join(" ")
    .toLowerCase();
  return markers.some((marker) => {
    const normalized = marker.toLowerCase();
    if (/^[a-z0-9_-]+$/.test(normalized)) {
      return lowerTags.includes(normalized);
    }
    return haystack.includes(normalized);
  });
}

function summarizeSigns(signs: InfluenceSign[]): InfluenceSign {
  if (signs.length === 0) return "unknown";
  if (signs.includes("unknown")) return "unknown";
  if (signs.includes("mixed")) return "mixed";
  const hasPositive = signs.includes("+");
  const hasNegative = signs.includes("-");
  if (hasPositive && hasNegative) return "mixed";
  if (hasPositive) return "+";
  if (hasNegative) return "-";
  return "unknown";
}

function signTone(sign: InfluenceSign): "stone" | "amber" | "rose" | "emerald" {
  if (sign === "+") return "emerald";
  if (sign === "-") return "rose";
  if (sign === "mixed") return "amber";
  return "stone";
}

function formatScore(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value * 100)))}/100`;
}
