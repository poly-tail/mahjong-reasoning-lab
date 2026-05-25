import { HelpCircle } from "lucide-react";
import { Button } from "../components/button";

const guideItems = [
  ["概念定義", "concept"],
  ["観測事象", "observation / signal"],
  ["仮説", "hypothesis"],
  ["分岐候補", "branch"],
  ["比較対象群", "choice_group"],
  ["判断指標", "metric"],
  ["重み補正", "weight_modifier"],
  ["固定操作", "lock_controller"],
  ["例外", "exception / override rule"],
  ["まだ分からない点", "question / ambiguity_marker"],
  ["追加で見るべき情報", "observation_candidate"],
  ["枝刈り提案", "pruning_suggestion"],
  ["重み調整", "weight_adjustment_suggestion"],
  ["教育用説明", "teaching_log / evidence / heuristic"],
] as const;

export function MappingGuidePanel({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  if (collapsed) {
    return (
      <div
        className="absolute right-3 top-3 z-10"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <Button
          size="sm"
          onClick={onToggle}
          title="マッピングガイドを開く"
          aria-label="マッピングガイドを開く"
        >
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
          ガイド
        </Button>
      </div>
    );
  }

  return (
    <aside
      className="absolute right-3 top-3 z-10 max-h-[62%] w-80 overflow-auto rounded-md border border-stone-200 bg-white/95 shadow-lg backdrop-blur"
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      <div className="flex h-9 items-center justify-between border-b border-stone-200 px-3">
        <h3 className="text-sm font-semibold text-stone-950">
          この考察はどのノードにする？
        </h3>
        <Button
          size="sm"
          variant="ghost"
          onClick={onToggle}
          title="マッピングガイドを畳む"
          aria-label="マッピングガイドを畳む"
        >
          畳む
        </Button>
      </div>
      <div className="grid gap-1.5 p-3 text-xs">
        {guideItems.map(([label, type]) => (
          <div
            key={label}
            className="grid grid-cols-[1fr_1.3fr] gap-2 rounded border border-stone-200 px-2 py-1.5"
          >
            <span className="font-medium text-stone-800">{label}</span>
            <span className="text-stone-500">{type}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
