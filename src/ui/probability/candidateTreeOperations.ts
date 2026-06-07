import type { PruningActionType } from "../../domain/schema";

export type CandidateTreeOperation = {
  action_type: PruningActionType;
  label: string;
  assistiveLabel: string;
  icon: "cut" | "downweight" | "topk" | "fix" | "ratio" | "concentration";
};

export const candidateTreeOperations: CandidateTreeOperation[] = [
  {
    action_type: "hard_prune",
    label: "枝を切る",
    assistiveLabel: "強制除外",
    icon: "cut",
  },
  {
    action_type: "soft_downweight",
    label: "枝を弱める",
    assistiveLabel: "重みを下げる",
    icon: "downweight",
  },
  {
    action_type: "keep_top_k",
    label: "有力枝を残す",
    assistiveLabel: "上位候補を保持",
    icon: "topk",
  },
  {
    action_type: "hard_lock",
    label: "枝を固定する",
    assistiveLabel: "強く固定",
    icon: "fix",
  },
  {
    action_type: "freeze_ratio",
    label: "比率を固定する",
    assistiveLabel: "枝の比率を固定",
    icon: "ratio",
  },
  {
    action_type: "freeze_concentration_band",
    label: "集中度を固定する",
    assistiveLabel: "枝の集中度を固定",
    icon: "concentration",
  },
];
