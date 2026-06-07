import { Ban, Link, Plus } from "lucide-react";
import { useMemo } from "react";
import { useAppStore } from "../../app/store";
import { classifyExceptionScope } from "../../domain/projectSheets";
import { formatPercent } from "../../domain/residualMass";
import type { ChoiceCandidateDraft } from "../../domain/readingNumerics";
import type { KnowledgeNode } from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";

export function ExceptionLibraryPanel({
  onUseAsCandidate,
}: {
  onUseAsCandidate?: (candidate: ChoiceCandidateDraft) => void;
}) {
  const doc = useAppStore((state) => state.doc);
  const attachNodeToCase = useAppStore((state) => state.attachNodeToCase);
  const updateNode = useAppStore((state) => state.updateNode);
  const activeCase =
    doc.cases.find((caseItem) => caseItem.id === doc.active_case_id) ??
    doc.cases[0];
  const exceptions = useMemo(
    () =>
      doc.nodes
        .filter(
          (node) =>
            (node.type === "exception" ||
              node.tags.some((tag) =>
                ["exception", "residual_mass", "reading_drawer"].includes(tag),
              )) &&
            !node.tags.includes("disabled_exception"),
        )
        .sort((a, b) => {
          const scopeDiff =
            scopeRank(classifyExceptionScope(doc, a.id)) -
            scopeRank(classifyExceptionScope(doc, b.id));
          return scopeDiff || b.updated_at.localeCompare(a.updated_at);
        }),
    [doc],
  );

  return (
    <section className="grid gap-3 rounded-md border border-stone-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-stone-950">例外集</h3>
          <p className="mt-1 text-xs leading-5 text-stone-600">
            未配分から出た例外候補を保存し、次回以降の候補提案に使います。
          </p>
        </div>
        <Badge tone={exceptions.length > 0 ? "amber" : "stone"}>
          {exceptions.length}件
        </Badge>
      </div>

      <div className="grid max-h-72 gap-2 overflow-auto">
        {exceptions.map((node) => (
          <ExceptionCard
            key={node.id}
            node={node}
            scope={classifyExceptionScope(doc, node.id)}
            caseCount={countCases(doc.cases, node.id)}
            isAttached={Boolean(
              activeCase?.attached_node_ids.includes(node.id),
            )}
            onAttach={() => {
              if (activeCase) attachNodeToCase(activeCase.id, node.id);
            }}
            onUseAsCandidate={() =>
              onUseAsCandidate?.({
                label: node.title,
                posterior_probability:
                  node.posterior_probability ?? node.base_weight ?? 0,
                base_weight: node.base_weight,
                lock_mode: "none",
                tags: ["exception", "residual_mass", "exception_library"],
              })
            }
            onDisable={() =>
              updateNode(node.id, {
                tags: Array.from(new Set([...node.tags, "disabled_exception"])),
              })
            }
          />
        ))}
        {exceptions.length === 0 ? (
          <div className="rounded-md border border-dashed border-stone-300 p-3 text-sm leading-6 text-stone-500">
            例外候補はまだありません。Quick
            Readingの未配分UIから「例外集に入れる」を選ぶと、反映時に例外ノードとして保存されます。
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ExceptionCard({
  node,
  scope,
  caseCount,
  isAttached,
  onAttach,
  onUseAsCandidate,
  onDisable,
}: {
  node: KnowledgeNode;
  scope: "sheet" | "project" | "workspace";
  caseCount: number;
  isAttached: boolean;
  onAttach: () => void;
  onUseAsCandidate: () => void;
  onDisable: () => void;
}) {
  const probability = node.posterior_probability ?? node.base_weight;
  const axes = node.tags.filter((tag) =>
    [
      "progress_tenpai_axis",
      "value_axis",
      "wait_shape_quality_axis",
      "score_situation_threshold_axis",
    ].includes(tag),
  );

  return (
    <article className="grid gap-2 rounded-md border border-stone-200 p-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-stone-950">
            {node.title}
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-stone-600">
            {node.description || node.summary}
          </p>
        </div>
        {probability !== undefined ? (
          <Badge tone="amber">{formatPercent(probability)}</Badge>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1">
        <Badge tone="cyan">{node.type}</Badge>
        <Badge>
          {scope === "sheet"
            ? "Sheet例外"
            : scope === "project"
              ? "Project例外"
              : "Global例外"}
        </Badge>
        <Badge>出現ケース {caseCount}</Badge>
        <Badge>最終利用 {node.updated_at.slice(0, 10)}</Badge>
        {axes.map((axis) => (
          <Badge key={axis}>{axis}</Badge>
        ))}
        {node.pruning_hints.map((hint) => (
          <Badge key={hint} tone="amber">
            {hint}
          </Badge>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={isAttached} onClick={onAttach}>
          <Link className="h-4 w-4" aria-hidden="true" />
          この局面に追加
        </Button>
        <Button size="sm" variant="ghost" onClick={onUseAsCandidate}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          候補提案に使う
        </Button>
        <Button size="sm" variant="ghost" onClick={onDisable}>
          <Ban className="h-4 w-4" aria-hidden="true" />
          無効化
        </Button>
      </div>
    </article>
  );
}

function countCases(
  cases: { attached_node_ids: string[] }[],
  nodeId: string,
): number {
  return cases.filter((caseItem) => caseItem.attached_node_ids.includes(nodeId))
    .length;
}

function scopeRank(scope: "sheet" | "project" | "workspace"): number {
  if (scope === "sheet") return 0;
  if (scope === "project") return 1;
  return 2;
}
