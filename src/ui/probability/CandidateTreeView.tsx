import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Eye,
  GitBranch,
  Lock,
  Scissors,
  SlidersHorizontal,
  TrendingDown,
  Undo2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import {
  getActiveProject,
  getActiveSheet,
  getScopedWorkspace,
} from "../../domain/projectSheets";
import { getChoiceGroups, getInferenceSubgraph } from "../../domain/probability";
import {
  formatPercent,
  getResidualMassChoiceGroups,
  type ResidualMassChoiceGroupSummary,
} from "../../domain/residualMass";
import {
  type KnowledgeEdge,
  type KnowledgeNode,
  type PruningActionType,
  type TemplateKey,
  type WorkspaceScopeMode,
} from "../../domain/schema";
import { cn } from "../../shared/cn";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Panel } from "../components/panel";
import {
  candidateTreeOperations,
  type CandidateTreeOperation,
} from "./candidateTreeOperations";

type CandidateBranch = {
  id: string;
  kind: "candidate" | "residual" | "exception" | "template" | "unknown";
  groupId?: string;
  groupLabel: string;
  title: string;
  summary: string;
  probability?: number;
  rawProbability?: number;
  computedProbability?: number;
  confidence?: number;
  node?: KnowledgeNode;
  residual?: ResidualMassChoiceGroupSummary;
  influenceEdges: KnowledgeEdge[];
  observations: KnowledgeNode[];
  exceptions: KnowledgeNode[];
  templateKey?: TemplateKey;
  dotted?: boolean;
  warning?: boolean;
  fixed?: boolean;
};

type CandidateGroup = {
  id: string;
  label: string;
  branches: CandidateBranch[];
  residual?: CandidateBranch;
};

const scopeOptions: {
  mode: WorkspaceScopeMode;
  label: string;
  description: string;
}[] = [
  {
    mode: "sheet",
    label: "現在のシート",
    description: "active Sheet の枝だけ",
  },
  {
    mode: "project",
    label: "現在のプロジェクト",
    description: "active Project 配下の枝",
  },
  {
    mode: "workspace",
    label: "ワークスペース全体",
    description: "全体の枝",
  },
];

const templateBranchLabels: Record<TemplateKey, string> = {
  tile_efficiency: "牌理の枝",
  tile_count: "枚数の枝",
  yaku: "手役の枝",
  abstract_reading: "抽象的な読みの枝",
};

const signLabels: Record<KnowledgeEdge["sign"], string> = {
  "+": "上げる",
  "-": "下げる",
  mixed: "mixed",
  unknown: "unknown",
};

const operationIcon = {
  cut: Scissors,
  downweight: TrendingDown,
  topk: GitBranch,
  fix: Lock,
  ratio: SlidersHorizontal,
  concentration: SlidersHorizontal,
} satisfies Record<CandidateTreeOperation["icon"], typeof GitBranch>;

export function CandidateTreeView() {
  const doc = useAppStore((state) => state.doc);
  const scopeMode = useAppStore((state) => state.scopeMode);
  const setScopeMode = useAppStore((state) => state.setScopeMode);
  const [selectedBranchId, setSelectedBranchId] = useState<string>();
  const [selectedOperation, setSelectedOperation] =
    useState<PruningActionType>("soft_downweight");

  const model = useMemo(() => buildCandidateTreeModel(doc, scopeMode), [
    doc,
    scopeMode,
  ]);
  const selectedBranch =
    model.branches.find((branch) => branch.id === selectedBranchId) ??
    model.branches[0];
  const operation = candidateTreeOperations.find(
    (item) => item.action_type === selectedOperation,
  );
  const warnings = selectedBranch
    ? getOperationWarnings(selectedBranch, selectedOperation)
    : [];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-3">
      <Panel className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-3 p-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-cyan-700" aria-hidden="true" />
              <h2 className="text-base font-semibold text-stone-950">
                候補木ビュー
              </h2>
              <Badge tone="cyan">{model.rootLabel}</Badge>
            </div>
            <p className="mt-1 max-w-4xl text-sm leading-6 text-stone-600">
              読み候補、候補確率、4軸影響、未展開の枝、例外の枝置き場を、
              内部グラフから枝構造として投影します。枝操作は反映前確認で差分を見てから扱います。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1">
            {scopeOptions.map((option) => (
              <Button
                key={option.mode}
                size="sm"
                variant={scopeMode === option.mode ? "primary" : "secondary"}
                onClick={() => setScopeMode(option.mode)}
                aria-pressed={scopeMode === option.mode}
                title={option.description}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>
      </Panel>

      <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_220px] gap-3">
        <div className="grid min-h-0 grid-cols-[340px_minmax(0,1fr)_330px] gap-3">
          <Panel title="候補木" className="min-h-0 overflow-hidden">
            <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden p-3 pr-2">
              <TreeRoot model={model} />
              <div className="mt-3 grid gap-2">
                {model.groups.map((group) => (
                  <details key={group.id} open className="group">
                    <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md border border-stone-200 bg-stone-50 px-2 py-1.5 text-sm font-semibold text-stone-900">
                      <GitBranch
                        className="h-4 w-4 text-stone-500"
                        aria-hidden="true"
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {group.label}
                      </span>
                      <Badge>{group.branches.length}枝</Badge>
                    </summary>
                    <div className="ml-3 mt-2 grid gap-2 border-l border-stone-200 pl-3">
                      {[
                        ...group.branches,
                        ...(group.residual ? [group.residual] : []),
                      ].map((branch) => (
                        <BranchButton
                          key={branch.id}
                          branch={branch}
                          selected={selectedBranch?.id === branch.id}
                          onSelect={() => setSelectedBranchId(branch.id)}
                        />
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          </Panel>

          <Panel title="選択した枝" className="min-h-0 overflow-hidden">
            <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden p-3 pr-2">
              {selectedBranch ? (
                <BranchDetail branch={selectedBranch} />
              ) : (
                <EmptyState label="表示できる枝がありません。" />
              )}
            </div>
          </Panel>

          <Panel title="枝操作" className="min-h-0 overflow-hidden">
            <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden p-3 pr-2">
              <div className="grid gap-2">
                {candidateTreeOperations.map((item) => {
                  const Icon = operationIcon[item.icon];
                  return (
                    <Button
                      key={item.action_type}
                      className="h-auto justify-start px-3 py-2 text-left"
                      variant={
                        selectedOperation === item.action_type
                          ? "primary"
                          : item.action_type === "hard_prune"
                            ? "danger"
                            : "secondary"
                      }
                      data-operation={item.action_type}
                      onClick={() => setSelectedOperation(item.action_type)}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span className="grid min-w-0">
                        <span>{item.label}</span>
                        <span className="text-xs opacity-80">
                          {item.assistiveLabel}
                        </span>
                      </span>
                    </Button>
                  );
                })}
              </div>

              <div className="mt-3 grid gap-2 border-t border-stone-200 pt-3">
                <Button className="justify-start">
                  <Archive className="h-4 w-4" aria-hidden="true" />
                  未展開の枝に送る
                </Button>
                <Button className="justify-start">
                  <Archive className="h-4 w-4" aria-hidden="true" />
                  例外の枝置き場に送る
                </Button>
                <Button className="justify-start">
                  <GitBranch className="h-4 w-4" aria-hidden="true" />
                  読みの枝候補から追加
                </Button>
              </div>

              <div className="mt-3 rounded-md border border-stone-200 bg-stone-50 p-2 text-xs leading-5 text-stone-600">
                未展開の枝やmixed/unknownが残る場合は、枝を切る前に枝を弱める、
                または有力枝を残す操作を検討してください。
              </div>
            </div>
          </Panel>
        </div>

        <Panel title="反映前確認" className="min-h-0 overflow-hidden">
          <div className="grid h-full min-h-0 grid-cols-[1fr_1fr_1.15fr] gap-3 overflow-y-auto overflow-x-hidden p-3 pr-2">
            <PreviewCard
              title="反映前の枝"
              rows={[
                ["対象", selectedBranch?.title ?? "-"],
                ["候補確率", formatMaybePercent(selectedBranch?.probability)],
                ["影響スコア", formatImpactSummary(selectedBranch)],
                ["未展開の枝", formatResidualRelation(selectedBranch)],
              ]}
            />
            <PreviewCard
              title="反映後の見込み"
              rows={[
                ["操作", operation?.label ?? "-"],
                ["補助", operation?.assistiveLabel ?? "-"],
                ["枝数変化", selectedOperation === "hard_prune" ? "-1" : "0"],
                [
                  "確率変化",
                  selectedOperation === "soft_downweight"
                    ? "対象枝を弱める"
                    : "反映時に再計算",
                ],
              ]}
            />
            <div className="min-h-0 overflow-y-auto rounded-md border border-stone-200 bg-white p-2">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-stone-950">
                <Eye className="h-4 w-4 text-cyan-700" aria-hidden="true" />
                警告と確認
              </div>
              <div className="grid gap-2">
                {warnings.length ? (
                  warnings.map((warning) => (
                    <div
                      key={warning}
                      className="flex gap-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs leading-5 text-amber-800"
                    >
                      <AlertTriangle
                        className="mt-0.5 h-4 w-4 shrink-0"
                        aria-hidden="true"
                      />
                      <span>{warning}</span>
                    </div>
                  ))
                ) : (
                  <div className="flex gap-2 rounded border border-emerald-200 bg-emerald-50 p-2 text-xs leading-5 text-emerald-800">
                    <CheckCircle2
                      className="mt-0.5 h-4 w-4 shrink-0"
                      aria-hidden="true"
                    />
                    <span>現在の選択では重大な警告はありません。</span>
                  </div>
                )}
                <div className="mt-1 flex flex-wrap gap-2">
                  <Button size="sm">
                    <Eye className="h-4 w-4" aria-hidden="true" />
                    反映前確認
                  </Button>
                  <Button size="sm" variant="primary">
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    反映する
                  </Button>
                  <Button size="sm" variant="ghost">
                    <Undo2 className="h-4 w-4" aria-hidden="true" />
                    元に戻す
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function buildCandidateTreeModel(
  doc: ReturnType<typeof useAppStore.getState>["doc"],
  scopeMode: WorkspaceScopeMode,
) {
  const activeCase = doc.cases.find((item) => item.id === doc.active_case_id);
  const activeSheet = getActiveSheet(doc);
  const activeProject = getActiveProject(doc);
  const scopedDoc = getScopedWorkspace(doc, scopeMode);
  const subgraph = getInferenceSubgraph(scopedDoc);
  const nodeById = new Map(scopedDoc.nodes.map((node) => [node.id, node]));
  const influenceEdges = scopedDoc.edges.filter(
    (edge) => edge.relation_layer === "influence",
  );
  const residualGroups = getResidualMassChoiceGroups(scopedDoc.nodes);
  const residualByGroupId = new Map(
    residualGroups.map((group) => [group.id, group]),
  );
  const exceptions = scopedDoc.nodes.filter(isExceptionNode);
  const groups: CandidateGroup[] = getChoiceGroups(subgraph.nodes).map(
    (group) => {
      const members = group.node_ids
        .map((id) => nodeById.get(id))
        .filter((node): node is KnowledgeNode => Boolean(node))
        .filter((node) => node.probability_role !== "control");
      const groupExceptions = exceptions.filter(
        (node) =>
          node.choice_group_id === group.id ||
          node.tags.includes(group.id) ||
          node.description.includes(group.id),
      );
      const branches = members.map((node) =>
        nodeToBranch({
          node,
          groupId: group.id,
          groupLabel: groupLabel(group.id, nodeById),
          influenceEdges,
          scopedNodes: scopedDoc.nodes,
          exceptions: groupExceptions,
        }),
      );
      const residual = residualByGroupId.get(group.id);
      return {
        id: group.id,
        label: groupLabel(group.id, nodeById),
        branches,
        residual: residual
          ? residualToBranch(residual, groupLabel(group.id, nodeById))
          : undefined,
      };
    },
  );

  const groupedNodeIds = new Set(groups.flatMap((group) => group.branches.map((branch) => branch.node?.id)));
  const standaloneBranches = subgraph.nodes
    .filter((node) => !node.choice_group_id && node.probability_role !== "control")
    .filter((node) => !isExceptionNode(node))
    .filter((node) => !groupedNodeIds.has(node.id))
    .map((node) =>
      nodeToBranch({
        node,
        groupId: "standalone",
        groupLabel: "単独の枝",
        influenceEdges,
        scopedNodes: scopedDoc.nodes,
        exceptions: [],
      }),
    );

  if (standaloneBranches.length > 0) {
    groups.push({
      id: "standalone",
      label: "単独の枝",
      branches: standaloneBranches,
    });
  }

  const exceptionBranches = exceptions.map((node) =>
    nodeToBranch({
      node,
      groupId: "exceptions",
      groupLabel: "例外の枝置き場",
      influenceEdges,
      scopedNodes: scopedDoc.nodes,
      exceptions: [],
      kind: "exception",
    }),
  );
  if (exceptionBranches.length > 0) {
    groups.push({
      id: "exceptions",
      label: "例外の枝置き場",
      branches: exceptionBranches,
    });
  }

  const templateBranches = getTemplateKeysInScope(scopedDoc.nodes, activeSheet)
    .map((key) => templateToBranch(key, scopedDoc.nodes, influenceEdges))
    .filter((branch): branch is CandidateBranch => Boolean(branch));
  if (templateBranches.length > 0) {
    groups.unshift({
      id: "templates",
      label: "初期テンプレートの枝",
      branches: templateBranches,
    });
  }

  const rootLabel =
    sanitizeDisplayText(activeCase?.title) ??
    sanitizeDisplayText(activeSheet?.title) ??
    sanitizeDisplayText(activeProject?.title) ??
    "読み候補";
  const branches = groups.flatMap((group) => [
    ...group.branches,
    ...(group.residual ? [group.residual] : []),
  ]);

  return {
    rootLabel,
    groups,
    branches,
    scopedDoc,
  };
}

function TreeRoot({
  model,
}: {
  model: ReturnType<typeof buildCandidateTreeModel>;
}) {
  const branchCount = model.branches.length;
  const residualCount = model.branches.filter(
    (branch) => branch.kind === "residual" || branch.kind === "unknown",
  ).length;
  const exceptionCount = model.branches.filter(
    (branch) => branch.kind === "exception",
  ).length;
  return (
    <div className="rounded-md border border-cyan-200 bg-cyan-50 p-2">
      <div className="flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-cyan-700" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-cyan-950">
            {model.rootLabel}
          </div>
          <div className="text-xs text-cyan-700">候補木の根</div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1 text-center text-xs">
        <div className="rounded bg-white/70 p-1">
          <div className="font-semibold text-stone-950">{branchCount}</div>
          <div className="text-stone-500">枝</div>
        </div>
        <div className="rounded bg-white/70 p-1">
          <div className="font-semibold text-stone-950">{residualCount}</div>
          <div className="text-stone-500">未展開</div>
        </div>
        <div className="rounded bg-white/70 p-1">
          <div className="font-semibold text-stone-950">{exceptionCount}</div>
          <div className="text-stone-500">例外</div>
        </div>
      </div>
    </div>
  );
}

function BranchButton({
  branch,
  selected,
  onSelect,
}: {
  branch: CandidateBranch;
  selected: boolean;
  onSelect: () => void;
}) {
  const probability = branch.probability ?? branch.computedProbability ?? 0;
  const confidence = branch.confidence ?? 0.5;
  const primary = primaryInfluence(branch.influenceEdges);
  const tone = primaryTone(primary?.sign);
  const borderWidth = Math.max(2, Math.min(8, Math.round(probability * 10)));
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "rounded-md border bg-white p-2 text-left text-sm transition-colors",
        selected
          ? "border-cyan-700 ring-2 ring-cyan-100"
          : "border-stone-200 hover:bg-stone-50",
        branch.dotted && "border-dashed",
      )}
      style={{
        borderLeftWidth: `${borderWidth}px`,
        borderLeftColor: branch.dotted
          ? "#94a3b8"
          : primary?.sign === "-"
            ? "#e11d48"
            : primary?.sign === "mixed"
              ? "#d97706"
              : primary?.sign === "unknown"
                ? "#78716c"
                : "#0e7490",
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="truncate font-semibold text-stone-950">
              {branch.title}
            </span>
            {branch.warning ? (
              <AlertTriangle
                className="h-4 w-4 shrink-0 text-amber-600"
                aria-label="警告"
              />
            ) : null}
            {branch.fixed ? (
              <Lock
                className="h-4 w-4 shrink-0 text-stone-500"
                aria-label="固定中"
              />
            ) : null}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge tone={tone}>{primary ? signLabels[primary.sign] : "影響なし"}</Badge>
            {branch.kind === "residual" || branch.kind === "unknown" ? (
              <Badge>未展開の枝</Badge>
            ) : null}
            {branch.kind === "exception" ? <Badge tone="amber">例外</Badge> : null}
            {branch.kind === "template" ? <Badge tone="emerald">初期枝</Badge> : null}
          </div>
        </div>
        <span className="shrink-0 text-xs tabular-nums text-stone-600">
          {formatMaybePercent(branch.probability)}
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded bg-stone-100">
        <div
          className={cn(
            "h-full rounded",
            primary?.sign === "-"
              ? "bg-rose-600"
              : primary?.sign === "mixed"
                ? "bg-amber-500"
                : primary?.sign === "unknown"
                  ? "bg-stone-500"
                  : "bg-cyan-700",
          )}
          style={{
            width: `${Math.max(4, Math.min(100, probability * 100))}%`,
            opacity: Math.max(0.35, Math.min(1, confidence)),
          }}
        />
      </div>
    </button>
  );
}

function BranchDetail({ branch }: { branch: CandidateBranch }) {
  const primary = primaryInfluence(branch.influenceEdges);
  return (
    <div className="grid gap-3">
      <div className="rounded-md border border-stone-200 bg-stone-50 p-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-stone-950">
              {branch.title}
            </h3>
            <p className="mt-1 text-sm leading-6 text-stone-600">
              {branch.summary || "要約はまだありません。"}
            </p>
          </div>
          <Badge tone={branch.kind === "exception" ? "amber" : "cyan"}>
            {branch.groupLabel}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <MetricTile label="入力確率" value={formatMaybePercent(branch.rawProbability)} />
        <MetricTile
          label="計算後確率"
          value={formatMaybePercent(branch.computedProbability)}
        />
        <MetricTile
          label="候補確率"
          value={formatMaybePercent(branch.probability)}
        />
        <MetricTile label="軸確信度" value={formatScore(branch.confidence)} />
      </div>

      <section className="rounded-md border border-stone-200 p-3">
        <div className="mb-2 text-sm font-semibold text-stone-950">
          4軸影響
        </div>
        {branch.influenceEdges.length ? (
          <div className="grid gap-2">
            {branch.influenceEdges.map((edge) => (
              <InfluenceRow key={edge.id} edge={edge} />
            ))}
          </div>
        ) : (
          <EmptyState label="この枝に直接つながる4軸影響はまだありません。" />
        )}
        {primary ? (
          <div className="mt-2 text-xs leading-5 text-stone-500">
            主に動く軸: {sanitizeDisplayText(primary.targetLabel)}
          </div>
        ) : null}
      </section>

      <section className="rounded-md border border-stone-200 p-3">
        <div className="mb-2 text-sm font-semibold text-stone-950">
          根拠・関連枝
        </div>
        <RelatedList
          label="観測"
          nodes={branch.observations}
          empty="関連する観測枝はまだありません。"
        />
        <RelatedList
          label="例外"
          nodes={branch.exceptions}
          empty="関連する例外枝はまだありません。"
        />
        <div className="mt-2 text-xs leading-5 text-stone-600">
          未展開の枝との関係: {formatResidualRelation(branch)}
        </div>
      </section>

      <section className="rounded-md border border-stone-200 p-3">
        <div className="mb-1 text-sm font-semibold text-stone-950">
          操作履歴
        </div>
        <p className="text-xs leading-5 text-stone-600">
          このビューでは履歴を反映前確認として表示します。実データへ保存する操作は既存の
          Reasoning Lab / 確率編集で扱います。
        </p>
      </section>
    </div>
  );
}

function InfluenceRow({ edge }: { edge: KnowledgeEdge }) {
  const label = edge.label || edge.target;
  return (
    <div className="rounded border border-stone-200 p-2">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="truncate font-medium text-stone-900">
          {sanitizeDisplayText(label)}
        </span>
        <Badge tone={primaryTone(edge.sign)}>{signLabels[edge.sign]}</Badge>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-2 text-xs text-stone-600">
        <span>影響スコア {formatScore(edge.magnitude)}</span>
        <span>軸確信度 {formatScore(edge.confidence)}</span>
      </div>
    </div>
  );
}

function RelatedList({
  label,
  nodes,
  empty,
}: {
  label: string;
  nodes: KnowledgeNode[];
  empty: string;
}) {
  return (
    <div className="mb-2">
      <div className="text-xs font-semibold text-stone-500">{label}</div>
      {nodes.length ? (
        <div className="mt-1 flex flex-wrap gap-1">
          {nodes.slice(0, 6).map((node) => (
            <Badge key={node.id}>{sanitizeDisplayText(node.title)}</Badge>
          ))}
        </div>
      ) : (
        <div className="mt-1 text-xs text-stone-500">{empty}</div>
      )}
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-stone-200 bg-white p-2">
      <div className="text-xs text-stone-500">{label}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums text-stone-950">
        {value}
      </div>
    </div>
  );
}

function PreviewCard({
  title,
  rows,
}: {
  title: string;
  rows: [string, string][];
}) {
  return (
    <div className="min-h-0 overflow-y-auto rounded-md border border-stone-200 bg-white p-2">
      <div className="mb-2 text-sm font-semibold text-stone-950">{title}</div>
      <div className="grid gap-1.5">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="grid grid-cols-[92px_minmax(0,1fr)] gap-2 rounded bg-stone-50 px-2 py-1.5 text-xs"
          >
            <span className="text-stone-500">{label}</span>
            <span className="truncate font-medium text-stone-900">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-md border border-dashed border-stone-300 bg-stone-50 p-3 text-sm text-stone-500">
      {label}
    </div>
  );
}

function nodeToBranch({
  node,
  groupId,
  groupLabel,
  influenceEdges,
  scopedNodes,
  exceptions,
  kind = "candidate",
}: {
  node: KnowledgeNode;
  groupId: string;
  groupLabel: string;
  influenceEdges: KnowledgeEdge[];
  scopedNodes: KnowledgeNode[];
  exceptions: KnowledgeNode[];
  kind?: CandidateBranch["kind"];
}): CandidateBranch {
  const edges = influenceEdges.filter(
    (edge) => edge.source === node.id || edge.target === node.id,
  );
  const observations = relatedNodes(node, scopedNodes, [
    "observation",
    "observation_candidate",
    "evidence",
  ]);
  const hasUnknown =
    node.tags.some((tag) => tag.includes("unknown")) ||
    edges.some((edge) => edge.sign === "mixed" || edge.sign === "unknown");
  return {
    id: `${kind}:${node.id}`,
    kind: hasUnknown && kind === "candidate" ? "unknown" : kind,
    groupId,
    groupLabel,
    title: sanitizeDisplayText(node.title),
    summary: sanitizeDisplayText(node.summary || node.description),
    probability: node.posterior_probability ?? node.prior_probability,
    rawProbability: node.prior_probability,
    computedProbability: node.posterior_probability,
    confidence: node.confidence,
    node,
    influenceEdges: edges,
    observations,
    exceptions,
    dotted: hasUnknown,
    warning:
      hasUnknown ||
      node.pruning_hints.includes("must_keep_top_k") ||
      isFixed(node),
    fixed: isFixed(node),
  };
}

function residualToBranch(
  residual: ResidualMassChoiceGroupSummary,
  groupLabel: string,
): CandidateBranch {
  return {
    id: `residual:${residual.id}`,
    kind: "residual",
    groupId: residual.id,
    groupLabel,
    title: "未展開の枝",
    summary:
      "未配分確率として残っている候補漏れ、例外、観測ノイズ、未知の枝です。",
    probability: residual.summary.residual_probability,
    rawProbability: residual.summary.raw_total,
    computedProbability: residual.summary.residual_probability,
    confidence: 0.35,
    residual,
    influenceEdges: [],
    observations: [],
    exceptions: [],
    dotted: true,
    warning: residual.summary.residual_probability > 0.05,
  };
}

function templateToBranch(
  key: TemplateKey,
  nodes: KnowledgeNode[],
  influenceEdges: KnowledgeEdge[],
): CandidateBranch | undefined {
  const templateNodes = nodes.filter((node) =>
    node.tags.includes(`template:${key}`),
  );
  if (templateNodes.length === 0) return undefined;
  const root =
    templateNodes.find((node) => node.tags.includes("template_root")) ??
    templateNodes[0];
  const nodeIds = new Set(templateNodes.map((node) => node.id));
  const edges = influenceEdges.filter(
    (edge) => nodeIds.has(edge.source) || nodeIds.has(edge.target),
  );
  return {
    id: `template:${key}`,
    kind: "template",
    groupId: "templates",
    groupLabel: "初期テンプレートの枝",
    title: templateBranchLabels[key],
    summary: sanitizeDisplayText(root?.summary || root?.description),
    probability: root?.posterior_probability,
    rawProbability: root?.prior_probability,
    computedProbability: root?.posterior_probability,
    confidence: root?.confidence ?? 0.6,
    node: root,
    influenceEdges: edges,
    observations: templateNodes.filter((node) =>
      ["observation", "observation_candidate"].includes(node.type),
    ),
    exceptions: templateNodes.filter(isExceptionNode),
    templateKey: key,
    dotted: key === "abstract_reading",
    warning: key === "abstract_reading",
  };
}

function groupLabel(groupId: string, nodeById: Map<string, KnowledgeNode>) {
  const direct = nodeById.get(groupId);
  const control = Array.from(nodeById.values()).find(
    (node) =>
      node.type === "choice_group" &&
      (node.id === groupId || node.tags.includes(groupId)),
  );
  return sanitizeDisplayText(direct?.title ?? control?.title ?? groupId);
}

function relatedNodes(
  node: KnowledgeNode,
  nodes: KnowledgeNode[],
  types: KnowledgeNode["type"][],
) {
  return nodes.filter(
    (candidate) =>
      candidate.id !== node.id &&
      types.includes(candidate.type) &&
      (candidate.related_rule_ids.some((id) =>
        node.related_rule_ids.includes(id),
      ) ||
        candidate.tags.some((tag) => node.tags.includes(tag)) ||
        node.description.includes(candidate.id) ||
        candidate.description.includes(node.id)),
  );
}

function getTemplateKeysInScope(
  nodes: KnowledgeNode[],
  activeSheet?: ReturnType<typeof getActiveSheet>,
): TemplateKey[] {
  const keys = new Set<TemplateKey>(
    activeSheet?.template_source?.enabled_template_keys ?? [],
  );
  for (const node of nodes) {
    for (const tag of node.tags) {
      if (!tag.startsWith("template:")) continue;
      const key = tag.slice("template:".length);
      if (isTemplateKey(key)) keys.add(key);
    }
  }
  return Array.from(keys);
}

function isTemplateKey(value: string): value is TemplateKey {
  return (
    value === "tile_efficiency" ||
    value === "tile_count" ||
    value === "yaku" ||
    value === "abstract_reading"
  );
}

function isExceptionNode(node: KnowledgeNode) {
  return node.type === "exception" || node.tags.includes("exception");
}

function isFixed(node: KnowledgeNode) {
  return node.lock_mode !== "none" && node.lock_mode !== "keep_top_k";
}

function primaryInfluence(edges: KnowledgeEdge[]) {
  const sorted = [...edges].sort(
    (left, right) => (right.magnitude ?? 0) - (left.magnitude ?? 0),
  );
  const edge = sorted[0];
  if (!edge) return undefined;
  return {
    sign: edge.sign,
    targetLabel: edge.label || edge.target,
  };
}

function primaryTone(sign?: KnowledgeEdge["sign"]) {
  if (sign === "-") return "rose";
  if (sign === "mixed") return "amber";
  if (sign === "unknown" || !sign) return "stone";
  return "cyan";
}

function getOperationWarnings(
  branch: CandidateBranch,
  operation: PruningActionType,
) {
  const warnings: string[] = [];
  if (operation !== "hard_prune") {
    return warnings;
  }
  if (
    branch.influenceEdges.some(
      (edge) => edge.sign === "mixed" || edge.sign === "unknown",
    ) ||
    branch.kind === "unknown"
  ) {
    warnings.push(
      "mixed/unknownが残る軸があります。枝を切るのではなく、枝を弱める / 有力枝を残すを検討してください。",
    );
  }
  if (
    branch.residual?.summary.residual_probability ||
    branch.groupLabel === "未展開の枝"
  ) {
    warnings.push(
      "未展開の枝が残っています。候補漏れや例外を確認してから枝操作を反映してください。",
    );
  }
  if (branch.node?.pruning_hints.includes("must_keep_top_k")) {
    warnings.push(
      "有力枝を残す制約がある枝です。枝を切る操作と矛盾しないか確認してください。",
    );
  }
  if (branch.fixed) {
    warnings.push(
      "固定中の枝です。枝を切る前に固定状態と比率の扱いを確認してください。",
    );
  }
  if ((branch.confidence ?? 1) <= 0.4) {
    warnings.push(
      "軸確信度が低い枝です。過大反映の可能性があります。",
    );
  }
  return warnings;
}

function formatMaybePercent(value: number | undefined) {
  return value === undefined ? "-" : formatPercent(value);
}

function formatScore(value: number | undefined) {
  return value === undefined ? "-" : `${Math.round(value * 100)}/100`;
}

function formatImpactSummary(branch: CandidateBranch | undefined) {
  if (!branch || branch.influenceEdges.length === 0) return "-";
  const top = [...branch.influenceEdges].sort(
    (left, right) => right.magnitude - left.magnitude,
  )[0];
  return `${formatScore(top.magnitude)} ${signLabels[top.sign]}`;
}

function formatResidualRelation(branch: CandidateBranch | undefined) {
  if (!branch) return "-";
  if (branch.kind === "residual" || branch.kind === "unknown") {
    return `${branch.title} ${formatMaybePercent(branch.probability)}`;
  }
  if (branch.residual) {
    return `${formatPercent(branch.residual.summary.residual_probability)} 残り`;
  }
  return "直接の未展開枝なし";
}

function sanitizeDisplayText(value: string | undefined): string {
  if (!value) return "";
  return value
    .replace(/hard[_\s-]?prune/giu, "枝を切る")
    .replace(/soft[_\s-]?downweight/giu, "枝を弱める")
    .replace(/downweight/giu, "枝を弱める")
    .replace(/keep[_\s-]?top[_\s-]?k/giu, "有力枝を残す")
    .replace(/hard[_\s-]?lock/giu, "強く固定")
    .replace(/soft[_\s-]?lock/giu, "ゆるく固定")
    .replace(/freeze[_\s-]?ratio/giu, "枝の比率を固定")
    .replace(
      /freeze[_\s-]?concentration[_\s-]?band/giu,
      "枝の集中度を固定",
    )
    .replace(/residual[_\s-]?mass/giu, "未展開の枝")
    .replace(/unknown[_\s-]?buffer/giu, "未知の枝")
    .replace(/Reading Drawer/giu, "読みの枝候補")
    .replace(/Exception Library/giu, "例外の枝置き場")
    .replace(/\block\b/giu, "固定");
}
