import { Library, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import {
  createChoiceCandidateFromDrawerItem,
  createResidualBucketFromDrawerItem,
  readingDrawerCategories,
  readingDrawerItems,
  type ReadingDrawerCategory,
  type ReadingDrawerItem,
} from "../../domain/readingDrawer";
import { formatPercent, type ResidualMassBucket } from "../../domain/residualMass";
import type { ChoiceCandidateDraft } from "../../domain/readingNumerics";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Input } from "../components/form";

export function ReadingDrawerSuggestionPanel({
  residualProbability,
  onAddCandidate,
  onAddException,
  onKeepUnknown,
}: {
  residualProbability: number;
  onAddCandidate: (candidate: ChoiceCandidateDraft) => void;
  onAddException: (bucket: ResidualMassBucket) => void;
  onKeepUnknown: () => void;
}) {
  const [category, setCategory] = useState<ReadingDrawerCategory | "all">("all");
  const [query, setQuery] = useState("");
  const items = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return readingDrawerItems.filter((item) => {
      const categoryMatch = category === "all" || item.category === category;
      if (!categoryMatch) return false;
      if (!normalized) return true;
      return [item.label, item.description, item.category, ...item.tags]
        .join(" ")
        .toLowerCase()
        .includes(normalized);
    });
  }, [category, query]);

  const allocateProbability = (item: ReadingDrawerItem) =>
    Math.min(
      residualProbability,
      item.default_probability && item.default_probability > 0
        ? item.default_probability
        : residualProbability,
    );

  return (
    <section className="grid gap-3 rounded-md border border-cyan-200 bg-cyan-50/40 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-stone-950">候補提案</h3>
          <p className="mt-1 text-xs leading-5 text-stone-600">
            未配分 {formatPercent(residualProbability)} を読みの引き出しから候補化します。
          </p>
        </div>
        <Button size="sm" onClick={onKeepUnknown}>
          <Library className="h-4 w-4" aria-hidden="true" />
          未知バッファへ
        </Button>
      </div>

      <div className="flex flex-wrap gap-1">
        <Button
          size="sm"
          variant={category === "all" ? "primary" : "secondary"}
          onClick={() => setCategory("all")}
        >
          全部
        </Button>
        {readingDrawerCategories.map((item) => (
          <Button
            key={item.id}
            size="sm"
            variant={category === item.id ? "primary" : "secondary"}
            onClick={() => setCategory(item.id)}
            title={item.description}
          >
            {item.label}
          </Button>
        ))}
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-stone-400" />
        <Input
          className="w-full pl-8"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="候補を検索"
        />
      </div>

      <div className="grid max-h-80 gap-2 overflow-auto">
        {items.slice(0, 16).map((item) => {
          const probability = allocateProbability(item);
          return (
            <article
              key={item.id}
              className="grid gap-2 rounded-md border border-stone-200 bg-white p-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1">
                    <h4 className="text-sm font-semibold text-stone-950">
                      {item.label}
                    </h4>
                    <Badge tone="cyan">
                      {formatPercent(probability)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-stone-600">
                    {item.description}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {item.axis_impacts?.map((impact) => (
                  <Badge key={`${item.id}_${impact.axis_id}`} tone="stone">
                    {impact.axis_id} {impact.sign} 影響ウェイト{" "}
                    {formatScore(impact.magnitude)}
                  </Badge>
                ))}
                {item.caution ? <Badge tone="amber">{item.caution}</Badge> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() =>
                    onAddCandidate(
                      createChoiceCandidateFromDrawerItem(item, probability),
                    )
                  }
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  候補に追加
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    onAddException(
                      createResidualBucketFromDrawerItem(item, probability),
                    )
                  }
                >
                  例外集に追加
                </Button>
              </div>
            </article>
          );
        })}
        {items.length === 0 ? (
          <p className="text-sm text-stone-500">一致する候補がありません。</p>
        ) : null}
      </div>
    </section>
  );
}

function formatScore(value: number) {
  return `${Math.max(0, Math.min(100, Math.round(value * 100)))}/100`;
}
