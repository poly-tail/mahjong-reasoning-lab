import { AlertTriangle, Library, Plus, ShieldQuestion } from "lucide-react";
import {
  formatPercent,
  getResidualMassChoiceGroups,
  residualBucketKindLabel,
  residualPolicyLabel,
  shouldBlockHardPrune,
} from "../../domain/residualMass";
import type { KnowledgeNode } from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Panel } from "../components/panel";

export function ResidualMassSummaryPanel({
  nodes,
  onAddCandidate,
  onOpenExceptionLibrary,
  onKeepUnknown,
}: {
  nodes: KnowledgeNode[];
  onAddCandidate: (groupId: string) => void;
  onOpenExceptionLibrary: () => void;
  onKeepUnknown: (groupId: string) => void;
}) {
  const groups = getResidualMassChoiceGroups(nodes);

  return (
    <Panel title="未配分確率サマリ">
      <div className="grid gap-2 p-3">
        {groups.length === 0 ? (
          <p className="text-sm text-stone-500">
            active case内に未配分確率が残るchoice groupはありません。
          </p>
        ) : (
          groups.map((group) => {
            const summary = group.summary;
            const blockHardPrune = shouldBlockHardPrune(summary);
            return (
              <article
                key={group.id}
                className="grid gap-2 rounded-md border border-stone-200 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-semibold text-stone-950">
                      {group.label}
                    </h3>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge>合計 {formatPercent(summary.raw_total)}</Badge>
                      <Badge
                        tone={
                          summary.residual_probability >= 0.25
                            ? "rose"
                            : summary.residual_probability >= 0.15
                              ? "amber"
                              : "cyan"
                        }
                      >
                        未配分 {formatPercent(summary.residual_probability)}
                      </Badge>
                      <Badge>{residualPolicyLabel(summary.policy)}</Badge>
                      {blockHardPrune ? (
                        <Badge tone="rose">
                          <AlertTriangle
                            className="h-3 w-3"
                            aria-hidden="true"
                          />
                          hard prune非推奨
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="grid gap-1 text-xs leading-5 text-stone-600">
                  {summary.buckets.map((bucket) => (
                    <div
                      key={bucket.id}
                      className="flex flex-wrap items-center gap-1"
                    >
                      <Badge tone="stone">
                        {residualBucketKindLabel(bucket.kind)}
                      </Badge>
                      <span>{bucket.label}</span>
                      <span>{formatPercent(bucket.probability)}</span>
                    </div>
                  ))}
                  {summary.warnings.map((warning) => (
                    <div
                      key={`${group.id}_${warning.code}`}
                      className={
                        warning.severity === "danger"
                          ? "text-rose-700"
                          : "text-amber-700"
                      }
                    >
                      {warning.message}
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => onAddCandidate(group.id)}>
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    候補を追加
                  </Button>
                  <Button size="sm" variant="ghost" onClick={onOpenExceptionLibrary}>
                    <Library className="h-4 w-4" aria-hidden="true" />
                    例外集を開く
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onKeepUnknown(group.id)}
                  >
                    <ShieldQuestion className="h-4 w-4" aria-hidden="true" />
                    未知として保持
                  </Button>
                </div>
              </article>
            );
          })
        )}
      </div>
    </Panel>
  );
}
