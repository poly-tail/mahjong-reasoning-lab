import { edgeTypeLabels, lockModeLabels, relationLayerLabels } from "../../domain/labels";
import { edgeTypes, influenceSigns, lockModes, pruningHints, type EdgeType } from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";

export function LegendPanel({
  collapsed,
  onToggle,
  edgeColors,
}: {
  collapsed: boolean;
  onToggle: () => void;
  edgeColors: Record<EdgeType, string>;
}) {
  if (collapsed) {
    return (
      <div
        className="absolute bottom-3 left-14 z-10"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <Button
          size="sm"
          onClick={onToggle}
          title="凡例を開く"
          aria-label="凡例を開く"
        >
          凡例
        </Button>
      </div>
    );
  }

  return (
    <aside
      className="absolute bottom-3 left-14 z-10 max-h-[68%] w-80 overflow-auto rounded-md border border-stone-200 bg-white/95 shadow-lg backdrop-blur"
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      <div className="flex h-9 items-center justify-between border-b border-stone-200 px-3">
        <h3 className="text-sm font-semibold text-stone-950">凡例</h3>
        <Button
          size="sm"
          variant="ghost"
          onClick={onToggle}
          title="凡例を畳む"
          aria-label="凡例を畳む"
        >
          畳む
        </Button>
      </div>

      <div className="grid gap-3 p-3 text-xs text-stone-600">
        <div>
          <h4 className="mb-1 font-semibold text-stone-800">
            線種とレイヤ
          </h4>
          <div className="grid gap-1.5">
            <LegendLine label={relationLayerLabels.semantic} description="意味関係" />
            <LegendLine
              label={relationLayerLabels.probabilistic}
              description="確率伝播対象"
              dashed="8 4"
            />
            <LegendLine
              label={relationLayerLabels.influence}
              description="指標への方向付き影響"
              dashed="3 4"
            />
          </div>
        </div>

        <div>
          <h4 className="mb-1 font-semibold text-stone-800">線色</h4>
          <div className="grid grid-cols-2 gap-1.5">
            {edgeTypes.map((type) => (
              <div key={type} className="flex min-w-0 items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: edgeColors[type] }}
                />
                <span className="truncate">{edgeTypeLabels[type]}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h4 className="mb-1 font-semibold text-stone-800">sign</h4>
          <div className="flex flex-wrap gap-1">
            {influenceSigns.map((sign) => (
              <Badge key={sign}>{sign}</Badge>
            ))}
          </div>
        </div>

        <div>
          <h4 className="mb-1 font-semibold text-stone-800">lock mode</h4>
          <div className="flex flex-wrap gap-1">
            {lockModes.map((mode) => (
              <Badge key={mode} tone={mode === "none" ? "stone" : "cyan"}>
                {lockModeLabels[mode]}
              </Badge>
            ))}
          </div>
        </div>

        <div>
          <h4 className="mb-1 font-semibold text-stone-800">
            pruning hints
          </h4>
          <div className="flex flex-wrap gap-1">
            {pruningHints.map((hint) => (
              <Badge key={hint}>{hint}</Badge>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

function LegendLine({
  label,
  description,
  dashed,
}: {
  label: string;
  description: string;
  dashed?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <svg className="h-3 w-14 shrink-0" viewBox="0 0 56 12" aria-hidden="true">
        <line
          x1="2"
          y1="6"
          x2="54"
          y2="6"
          stroke="#0e7490"
          strokeWidth="2"
          strokeDasharray={dashed}
          strokeLinecap="round"
        />
      </svg>
      <span className="font-medium text-stone-800">{label}</span>
      <span className="text-stone-500">{description}</span>
    </div>
  );
}
