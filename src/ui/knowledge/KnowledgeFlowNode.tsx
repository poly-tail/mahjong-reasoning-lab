import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { Layers, LockKeyhole, Split, Star } from "lucide-react";
import {
  labelTag,
  nodeTypeLabels,
  probabilityRoleLabels,
} from "../../domain/labels";
import type { KnowledgeNode } from "../../domain/schema";
import { cn } from "../../shared/cn";
import { Badge } from "../components/badge";

export type KnowledgeFlowNodeType = Node<KnowledgeNode, "knowledgeNode">;

const typeTone: Record<KnowledgeNode["type"], string> = {
  concept: "border-cyan-300 bg-cyan-50",
  signal: "border-amber-300 bg-amber-50",
  condition: "border-emerald-300 bg-emerald-50",
  metric: "border-lime-300 bg-lime-50",
  heuristic: "border-violet-300 bg-violet-50",
  exception: "border-rose-300 bg-rose-50",
  scenario: "border-sky-300 bg-sky-50",
  action: "border-orange-300 bg-orange-50",
  evidence: "border-stone-300 bg-stone-50",
  question: "border-fuchsia-300 bg-fuchsia-50",
  hypothesis: "border-cyan-500 bg-cyan-50",
  branch: "border-blue-400 bg-blue-50",
  choice_group: "border-indigo-400 bg-indigo-50",
  observation: "border-amber-400 bg-amber-50",
  weight_modifier: "border-teal-400 bg-teal-50",
  lock_controller: "border-rose-400 bg-rose-50",
  distribution_assumption: "border-purple-400 bg-purple-50",
  probability_aggregate: "border-emerald-400 bg-emerald-50",
  observation_candidate: "border-amber-500 bg-amber-50",
  ambiguity_marker: "border-fuchsia-500 bg-fuchsia-50",
  pruning_suggestion: "border-rose-500 bg-rose-50",
  weight_adjustment_suggestion: "border-teal-500 bg-teal-50",
};

export function KnowledgeFlowNode({
  data,
  selected,
}: NodeProps<KnowledgeFlowNodeType>) {
  const icon = data.is_group ? (
    <Layers className="h-3.5 w-3.5" aria-hidden="true" />
  ) : data.pruning_hints.includes("must_keep_top_k") ? (
    <Split className="h-3.5 w-3.5" aria-hidden="true" />
  ) : data.pruning_hints.includes("hard_gate_candidate") ? (
    <LockKeyhole className="h-3.5 w-3.5" aria-hidden="true" />
  ) : (
    <Star className="h-3.5 w-3.5" aria-hidden="true" />
  );

  return (
    <div
      className={cn(
        "min-h-24 w-60 rounded-lg border bg-white p-2 text-left shadow-sm transition-shadow",
        typeTone[data.type],
        selected && "ring-2 ring-cyan-600",
        data.is_group && "border-dashed bg-white",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-cyan-700" />
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-cyan-700"
      />
      <div className="mb-1 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="text-stone-700">{icon}</span>
          <Badge
            tone={
              data.type === "exception"
                ? "rose"
                : data.is_group
                  ? "amber"
                  : "cyan"
            }
          >
            {data.is_group ? "セクション" : nodeTypeLabels[data.type]}
          </Badge>
        </div>
        <span className="shrink-0 text-xs tabular-nums text-stone-500">
          {data.probability_role !== "none" &&
          data.posterior_probability !== undefined
            ? `P ${Math.round(data.posterior_probability * 100)}%`
            : `${Math.round(data.confidence * 100)}%`}
        </span>
      </div>
      <div className="line-clamp-2 text-sm font-semibold leading-5 text-stone-950">
        {data.title}
      </div>
      <p className="mt-1 line-clamp-2 text-xs leading-4 text-stone-600">
        {data.summary}
      </p>
      <div className="mt-2 flex flex-wrap gap-1">
        {data.probability_role !== "none" ? (
          <Badge tone="emerald" className="max-w-28 truncate">
            {probabilityRoleLabels[data.probability_role]}
          </Badge>
        ) : null}
        {data.tags.slice(0, 3).map((tag) => (
          <Badge key={tag} className="max-w-28 truncate">
            {labelTag(tag)}
          </Badge>
        ))}
      </div>
    </div>
  );
}
