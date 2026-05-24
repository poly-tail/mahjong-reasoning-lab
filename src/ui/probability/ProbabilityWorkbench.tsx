import {
  GitCompare,
  Network,
  Play,
  Plus,
  Save,
  Sparkles,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  distributionFamilyLabels,
  edgeTypeLabels,
  lockModeLabels,
  nodeTypeLabels,
  probabilityRoleLabels,
  propagationPolicyLabels,
  relationLayerLabels,
} from "../../domain/labels";
import {
  getChoiceGroups,
  getInferenceSubgraph,
  type PropagationPreview,
} from "../../domain/probability";
import {
  distributionFamilies,
  lockModes,
  probabilityRoles,
  propagationPolicies,
  relationLayers,
  type DistributionFamily,
  type KnowledgeEdge,
  type KnowledgeNode,
} from "../../domain/schema";
import { cn } from "../../shared/cn";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";

function numberValue(value: string, fallback?: number) {
  if (value.trim() === "") return undefined;
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

function formatProbability(value: number | undefined) {
  return value === undefined ? "-" : `${Math.round(value * 1000) / 10}%`;
}

function labelDistribution(family: DistributionFamily | undefined) {
  return family ? distributionFamilyLabels[family] : "カテゴリ分布";
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

export function ProbabilityWorkbench() {
  const doc = useAppStore((state) => state.doc);
  const selectedNodeIds = useAppStore((state) => state.selectedNodeIds);
  const selectedEdgeIds = useAppStore((state) => state.selectedEdgeIds);
  const setSelection = useAppStore((state) => state.setSelection);
  const updateNode = useAppStore((state) => state.updateNode);
  const updateEdge = useAppStore((state) => state.updateEdge);
  const createChoiceGroupFromSelection = useAppStore(
    (state) => state.createChoiceGroupFromSelection,
  );
  const runPropagationPreview = useAppStore(
    (state) => state.runPropagationPreview,
  );
  const applyPropagationPreview = useAppStore(
    (state) => state.applyPropagationPreview,
  );
  const clearPropagationPreview = useAppStore(
    (state) => state.clearPropagationPreview,
  );
  const preview = useAppStore((state) => state.lastPropagationPreview);

  const subgraph = useMemo(() => getInferenceSubgraph(doc), [doc]);
  const choiceGroups = useMemo(
    () => getChoiceGroups(subgraph.nodes),
    [subgraph.nodes],
  );
  const selectedNode =
    selectedNodeIds.length === 1
      ? doc.nodes.find((node) => node.id === selectedNodeIds[0])
      : undefined;
  const selectedEdge =
    selectedEdgeIds.length === 1
      ? doc.edges.find((edge) => edge.id === selectedEdgeIds[0])
      : undefined;
  const affected = new Set(preview?.affected_node_ids ?? []);

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[320px_minmax(0,1fr)_380px] gap-3 p-3">
      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        <div className="sticky top-0 z-10 flex min-h-10 items-center justify-between border-b border-stone-200 bg-white px-3">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-stone-500" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-stone-950">選択候補群</h2>
          </div>
          <Button
            size="sm"
            onClick={createChoiceGroupFromSelection}
            disabled={selectedNodeIds.length < 2}
            title="選択ノードから排他的候補群を作る"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            グループ化
          </Button>
        </div>

        <div className="grid gap-2 p-2">
          <div className="rounded-lg border border-stone-200 bg-stone-50 p-2 text-xs leading-5 text-stone-600">
            確率伝播は確率ロールを持つノードと確率レイヤーのエッジに限定します。
            意味ノードは原則として確率を持ちません。
          </div>
          {choiceGroups.map((group) => (
            <section
              key={group.id}
              className="rounded-lg border border-stone-200 p-2"
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-stone-950">
                    {group.id}
                  </h3>
                  <p className="text-xs text-stone-500">
                    合計 {Math.round(group.normalized_total * 1000) / 1000}
                  </p>
                </div>
                <Badge tone="cyan">
                  {labelDistribution(group.distribution_family)}
                </Badge>
              </div>
              <div className="grid gap-1.5">
                {group.node_ids.map((nodeId) => {
                  const node = doc.nodes.find((item) => item.id === nodeId);
                  if (!node) return null;
                  return (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => setSelection([node.id], [])}
                      className={cn(
                        "rounded border p-2 text-left text-sm",
                        selectedNodeIds.includes(node.id)
                          ? "border-cyan-700 bg-cyan-50"
                          : affected.has(node.id)
                            ? "border-amber-400 bg-amber-50"
                            : "border-stone-200 bg-white hover:bg-stone-50",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-stone-900">
                          {node.title}
                        </span>
                        <span className="text-xs tabular-nums text-stone-500">
                          {formatProbability(node.posterior_probability)}
                        </span>
                      </div>
                      <ProbabilityBar value={node.posterior_probability ?? 0} />
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
          {subgraph.nodes.filter((node) => !node.choice_group_id).length > 0 ? (
            <section className="rounded-lg border border-stone-200 p-2">
              <h3 className="mb-2 text-sm font-semibold text-stone-950">
                単独ノード
              </h3>
              <div className="grid gap-1.5">
                {subgraph.nodes
                  .filter((node) => !node.choice_group_id)
                  .map((node) => (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => setSelection([node.id], [])}
                      className={cn(
                        "rounded border p-2 text-left text-sm",
                        selectedNodeIds.includes(node.id)
                          ? "border-cyan-700 bg-cyan-50"
                          : affected.has(node.id)
                            ? "border-amber-400 bg-amber-50"
                            : "border-stone-200 bg-white hover:bg-stone-50",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-stone-900">
                          {node.title}
                        </span>
                        <Badge>
                          {probabilityRoleLabels[node.probability_role]}
                        </Badge>
                      </div>
                    </button>
                  ))}
              </div>
            </section>
          ) : null}
        </div>
      </aside>

      <main className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3">
        <PropagationPreviewPanel
          preview={preview}
          selectedNodeId={selectedNode?.id}
          onRun={() => runPropagationPreview(selectedNode?.id)}
          onApply={applyPropagationPreview}
          onClear={clearPropagationPreview}
        />
        <div className="grid min-h-0 grid-cols-2 gap-3">
          <DistributionPanel
            selectedNode={selectedNode}
            nodes={doc.nodes}
            updateNode={updateNode}
          />
          <ScenarioComparePanel nodes={doc.nodes} preview={preview} />
        </div>
      </main>

      <aside className="min-h-0 overflow-auto rounded-lg border border-stone-200 bg-white">
        {selectedNode ? (
          <ProbabilityInspector node={selectedNode} updateNode={updateNode} />
        ) : selectedEdge ? (
          <ProbabilityEdgeInspector
            edge={selectedEdge}
            updateEdge={updateEdge}
          />
        ) : (
          <div className="p-3 text-sm text-stone-600">
            知識マップまたは左の選択候補群からノードを1つ選択してください。
          </div>
        )}
      </aside>
    </div>
  );
}

function ProbabilityInspector({
  node,
  updateNode,
}: {
  node: KnowledgeNode;
  updateNode: (id: string, patch: Partial<KnowledgeNode>) => void;
}) {
  return (
    <>
      <div className="sticky top-0 z-10 border-b border-stone-200 bg-white px-3 py-2">
        <h2 className="truncate text-sm font-semibold text-stone-950">
          確率インスペクター
        </h2>
        <p className="truncate text-xs text-stone-500">{node.title}</p>
      </div>
      <div className="grid gap-3 p-3">
        <div className="flex flex-wrap gap-1">
          <Badge tone={node.probability_role === "none" ? "stone" : "cyan"}>
            {probabilityRoleLabels[node.probability_role]}
          </Badge>
          <Badge>{nodeTypeLabels[node.type]}</Badge>
          {node.lock_mode !== "none" ? (
            <Badge tone="amber">{lockModeLabels[node.lock_mode]}</Badge>
          ) : null}
        </div>
        <Field label="確率ロール">
          <Select
            value={node.probability_role}
            onChange={(event) =>
              updateNode(node.id, {
                probability_role: event.target
                  .value as KnowledgeNode["probability_role"],
              })
            }
          >
            {probabilityRoles.map((role) => (
              <option key={role} value={role}>
                {probabilityRoleLabels[role]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="選択候補群識別子">
          <Input
            value={node.choice_group_id ?? ""}
            onChange={(event) =>
              updateNode(node.id, {
                choice_group_id: event.target.value.trim() || undefined,
              })
            }
          />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <NumberField
            label="事前確率"
            value={node.prior_probability}
            onChange={(value) =>
              updateNode(node.id, { prior_probability: value })
            }
          />
          <NumberField
            label="事後確率"
            value={node.posterior_probability}
            onChange={(value) =>
              updateNode(node.id, { posterior_probability: value })
            }
          />
          <NumberField
            label="基本重み"
            value={node.base_weight}
            onChange={(value) => updateNode(node.id, { base_weight: value })}
          />
          <NumberField
            label="動的重み"
            value={node.dynamic_weight}
            onChange={(value) => updateNode(node.id, { dynamic_weight: value })}
          />
          <NumberField
            label="確信度"
            value={node.confidence}
            onChange={(value) =>
              updateNode(node.id, { confidence: value ?? node.confidence })
            }
          />
          <NumberField
            label="ロック値"
            value={node.lock_value}
            onChange={(value) => updateNode(node.id, { lock_value: value })}
          />
        </div>
        <Field label="ロック方式">
          <Select
            value={node.lock_mode}
            onChange={(event) =>
              updateNode(node.id, {
                lock_mode: event.target.value as KnowledgeNode["lock_mode"],
              })
            }
          >
            {lockModes.map((mode) => (
              <option key={mode} value={mode}>
                {lockModeLabels[mode]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="分布種別">
          <Select
            value={node.distribution_family ?? ""}
            onChange={(event) =>
              updateNode(node.id, {
                distribution_family: (event.target.value || undefined) as
                  | DistributionFamily
                  | undefined,
              })
            }
          >
            <option value="">なし</option>
            {distributionFamilies.map((family) => (
              <option key={family} value={family}>
                {distributionFamilyLabels[family]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="伝播方針">
          <Select
            value={node.propagation_policy}
            onChange={(event) =>
              updateNode(node.id, {
                propagation_policy: event.target
                  .value as KnowledgeNode["propagation_policy"],
              })
            }
          >
            {propagationPolicies.map((policy) => (
              <option key={policy} value={policy}>
                {propagationPolicyLabels[policy]}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <NumberField
            label="ヒステリシス"
            value={node.hysteresis_band}
            onChange={(value) =>
              updateNode(node.id, { hysteresis_band: value })
            }
          />
          <NumberField
            label="枝刈り優先度"
            value={node.pruning_priority}
            onChange={(value) =>
              updateNode(node.id, { pruning_priority: value })
            }
          />
        </div>
      </div>
    </>
  );
}

function ProbabilityEdgeInspector({
  edge,
  updateEdge,
}: {
  edge: KnowledgeEdge;
  updateEdge: (id: string, patch: Partial<KnowledgeEdge>) => void;
}) {
  return (
    <>
      <div className="sticky top-0 z-10 border-b border-stone-200 bg-white px-3 py-2">
        <h2 className="truncate text-sm font-semibold text-stone-950">
          確率エッジ
        </h2>
        <p className="truncate text-xs text-stone-500">
          {edgeTypeLabels[edge.type]}
        </p>
      </div>
      <div className="grid gap-3 p-3">
        <Field label="関係レイヤー">
          <Select
            value={edge.relation_layer}
            onChange={(event) =>
              updateEdge(edge.id, {
                relation_layer: event.target
                  .value as KnowledgeEdge["relation_layer"],
              })
            }
          >
            {relationLayers.map((layer) => (
              <option key={layer} value={layer}>
                {relationLayerLabels[layer]}
              </option>
            ))}
          </Select>
        </Field>
        <NumberField
          label="条件付き重み"
          value={edge.conditional_weight}
          onChange={(value) =>
            updateEdge(edge.id, { conditional_weight: value })
          }
        />
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <input
            type="checkbox"
            checked={edge.propagate_probability}
            onChange={(event) =>
              updateEdge(edge.id, {
                propagate_probability: event.target.checked,
              })
            }
          />
          確率を伝播する
        </label>
        <Field label="遷移ルール">
          <Textarea
            value={edge.transition_rule ?? ""}
            onChange={(event) =>
              updateEdge(edge.id, {
                transition_rule: event.target.value || undefined,
              })
            }
          />
        </Field>
        <Field label="エッジ群識別子">
          <Input
            value={edge.edge_group_id ?? ""}
            onChange={(event) =>
              updateEdge(edge.id, {
                edge_group_id: event.target.value || undefined,
              })
            }
          />
        </Field>
      </div>
    </>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
}) {
  return (
    <Field label={label}>
      <Input
        type="number"
        step="0.01"
        value={value ?? ""}
        onChange={(event) => onChange(numberValue(event.target.value, value))}
      />
    </Field>
  );
}

function PropagationPreviewPanel({
  preview,
  selectedNodeId,
  onRun,
  onApply,
  onClear,
}: {
  preview?: PropagationPreview;
  selectedNodeId?: string;
  onRun: () => void;
  onApply: () => void;
  onClear: () => void;
}) {
  return (
    <Panel
      title="伝播プレビュー"
      action={
        <div className="flex items-center gap-1">
          <Button onClick={onRun}>
            <Play className="h-4 w-4" aria-hidden="true" />
            プレビュー
          </Button>
          <Button onClick={onApply} disabled={!preview}>
            <Save className="h-4 w-4" aria-hidden="true" />
            反映
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClear}
            disabled={!preview}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      }
    >
      <div className="grid max-h-72 grid-cols-[220px_minmax(0,1fr)] gap-3 overflow-auto p-3">
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-2 text-xs leading-5 text-stone-600">
          <div className="font-semibold text-stone-900">処理順</div>
          {(
            preview?.steps ?? [
              "1 観測更新",
              "2 ゲート枝刈り",
              "3 重み補正を反映",
              "4 ロックを反映",
              "5 同階層を正規化",
              "6 下流へ伝播",
              "7 ヒステリシス / 上位候補を調整",
            ]
          ).map((step) => (
            <div key={step}>{step}</div>
          ))}
          {selectedNodeId ? (
            <div className="mt-2">変更対象: {selectedNodeId}</div>
          ) : null}
        </div>
        <div className="grid gap-2">
          {preview?.warnings.map((warning) => (
            <div
              key={warning}
              className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800"
            >
              {warning}
            </div>
          ))}
          {preview?.diffs.length ? (
            preview.diffs.map((diff) => (
              <div
                key={diff.node_id}
                className="rounded-lg border border-stone-200 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-stone-950">
                    {diff.title}
                  </span>
                  <Badge tone={diff.delta >= 0 ? "emerald" : "rose"}>
                    {diff.delta >= 0 ? "+" : ""}
                    {Math.round(diff.delta * 1000) / 10}点
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-stone-600">
                  {formatProbability(diff.before)} {"->"}{" "}
                  {formatProbability(diff.after)} / {diff.reason}
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-stone-200 p-3 text-sm text-stone-600">
              プレビューを実行すると更新前後の差分と影響ノードが表示されます。
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function DistributionPanel({
  selectedNode,
  nodes,
  updateNode,
}: {
  selectedNode?: KnowledgeNode;
  nodes: KnowledgeNode[];
  updateNode: (id: string, patch: Partial<KnowledgeNode>) => void;
}) {
  if (!selectedNode) {
    return (
      <Panel title="分布対応表示">
        <div className="p-3 text-sm text-stone-600">
          ノード選択後に分布表示を出します。
        </div>
      </Panel>
    );
  }

  const family = selectedNode.distribution_family ?? "categorical";
  const siblings = selectedNode.choice_group_id
    ? nodes.filter(
        (node) => node.choice_group_id === selectedNode.choice_group_id,
      )
    : [selectedNode];

  return (
    <Panel
      title="分布対応表示"
      action={<Badge tone="cyan">{distributionFamilyLabels[family]}</Badge>}
    >
      <div className="grid gap-3 p-3">
        {family === "categorical" ? (
          <div className="grid gap-2">
            {siblings.map((node) => (
              <div key={node.id}>
                <div className="mb-1 flex justify-between text-xs text-stone-600">
                  <span className="truncate">{node.title}</span>
                  <span>{formatProbability(node.posterior_probability)}</span>
                </div>
                <ProbabilityBar value={node.posterior_probability ?? 0} />
              </div>
            ))}
          </div>
        ) : null}

        {family === "interval" ? (
          <div className="rounded-lg border border-stone-200 p-3">
            <div className="mb-2 text-sm font-semibold text-stone-900">
              範囲バー
            </div>
            <div className="relative h-4 rounded bg-stone-100">
              <div
                className="absolute h-4 rounded bg-cyan-600"
                style={{
                  left: `${Math.min((selectedNode.prior_probability ?? 0) * 100, 100)}%`,
                  width: `${Math.max(
                    4,
                    Math.abs(
                      (selectedNode.posterior_probability ?? 0) -
                        (selectedNode.prior_probability ?? 0),
                    ) * 100,
                  )}%`,
                }}
              />
            </div>
          </div>
        ) : null}

        {family === "bimodal" || family === "multimodal" ? (
          <Field label="ピーク一覧" hint="1行に1ピーク">
            <Textarea
              value={toLines(selectedNode.formulas)}
              onChange={(event) =>
                updateNode(selectedNode.id, {
                  formulas: fromLines(event.target.value),
                })
              }
            />
          </Field>
        ) : null}

        {family === "asymmetric_tail" ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-rose-800">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              テール強調
            </div>
            <ProbabilityBar
              value={
                selectedNode.pruning_priority ??
                selectedNode.posterior_probability ??
                0
              }
              tone="rose"
            />
            <p className="mt-2 text-xs text-rose-700">
              低確率でも損失が重い枝として、枝刈り優先度を別枠で保持します。
            </p>
          </div>
        ) : null}

        {family === "mixture" ? (
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="混合の基本重み"
              value={selectedNode.base_weight}
              onChange={(value) =>
                updateNode(selectedNode.id, { base_weight: value })
              }
            />
            <NumberField
              label="混合の動的重み"
              value={selectedNode.dynamic_weight}
              onChange={(value) =>
                updateNode(selectedNode.id, { dynamic_weight: value })
              }
            />
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function ScenarioComparePanel({
  nodes,
  preview,
}: {
  nodes: KnowledgeNode[];
  preview?: PropagationPreview;
}) {
  const [scenarioA, setScenarioA] = useState<KnowledgeNode[]>();
  const [scenarioB, setScenarioB] = useState<KnowledgeNode[]>();

  const diffs = useMemo(() => {
    if (!scenarioA || !scenarioB) return [];
    const aById = new Map(scenarioA.map((node) => [node.id, node]));
    return scenarioB
      .map((node) => {
        const before = aById.get(node.id);
        if (!before) return undefined;
        const delta =
          (node.posterior_probability ?? 0) -
          (before.posterior_probability ?? 0);
        const changed =
          Math.abs(delta) > 0.0001 ||
          node.lock_mode !== before.lock_mode ||
          node.distribution_family !== before.distribution_family ||
          node.base_weight !== before.base_weight ||
          node.dynamic_weight !== before.dynamic_weight;
        if (!changed) return undefined;
        return { node, before, delta };
      })
      .filter(
        (
          item,
        ): item is {
          node: KnowledgeNode;
          before: KnowledgeNode;
          delta: number;
        } => Boolean(item),
      );
  }, [scenarioA, scenarioB]);

  return (
    <Panel
      title="シナリオ比較"
      action={
        <div className="flex gap-1">
          <Button size="sm" onClick={() => setScenarioA(nodes)}>
            <GitCompare className="h-4 w-4" aria-hidden="true" />
            比較元
          </Button>
          <Button
            size="sm"
            onClick={() =>
              setScenarioB(preview?.updated_workspace.nodes ?? nodes)
            }
          >
            <GitCompare className="h-4 w-4" aria-hidden="true" />
            比較先
          </Button>
        </div>
      }
    >
      <div className="max-h-[430px] overflow-auto p-3">
        <div className="mb-2 grid grid-cols-2 gap-2 text-xs text-stone-600">
          <div className="rounded border border-stone-200 p-2">
            比較元: {scenarioA ? "記録済み" : "未記録"}
          </div>
          <div className="rounded border border-stone-200 p-2">
            比較先: {scenarioB ? "記録済み" : "未記録"}
          </div>
        </div>
        <div className="grid gap-2">
          {diffs.length ? (
            diffs.map(({ node, before, delta }) => (
              <div
                key={node.id}
                className="rounded-lg border border-stone-200 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-stone-950">
                    {node.title}
                  </span>
                  <Badge tone={delta >= 0 ? "emerald" : "rose"}>
                    {delta >= 0 ? "+" : ""}
                    {Math.round(delta * 1000) / 10}点
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-stone-600">
                  {formatProbability(before.posterior_probability)} {"->"}{" "}
                  {formatProbability(node.posterior_probability)}
                </div>
                <div className="mt-1 text-xs text-stone-500">
                  ロック {lockModeLabels[before.lock_mode]} {"->"}{" "}
                  {lockModeLabels[node.lock_mode]}、分布{" "}
                  {before.distribution_family
                    ? distributionFamilyLabels[before.distribution_family]
                    : "-"}{" "}
                  {"->"}{" "}
                  {node.distribution_family
                    ? distributionFamilyLabels[node.distribution_family]
                    : "-"}
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-stone-200 p-3 text-sm text-stone-600">
              比較元と比較先を記録すると、ロック前後、重み変更前後、分布仮定の違いを比較できます。
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}

function ProbabilityBar({
  value,
  tone = "cyan",
}: {
  value: number;
  tone?: "cyan" | "rose";
}) {
  return (
    <div className="h-2 overflow-hidden rounded bg-stone-100">
      <div
        className={cn(
          "h-full rounded",
          tone === "rose" ? "bg-rose-600" : "bg-cyan-700",
        )}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  );
}
