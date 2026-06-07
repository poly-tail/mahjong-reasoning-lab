import { AlertTriangle, Eye, Plus, RotateCcw, Save } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import { runPropagation } from "../../domain/probability";
import {
  buildResidualMassSummary,
  formatPercent,
  residualPolicyLabel,
  type ResidualMassBucket,
  type ResidualMassPolicy,
} from "../../domain/residualMass";
import {
  buildReadingImpactPreview,
  createDefaultReadingImpactDraft,
  normalizePercentInput,
  type AxisImpactDraft,
  type ChoiceCandidateDraft,
  type ReadingImpactDraft,
} from "../../domain/readingNumerics";
import { handValueRangeAxes } from "../../domain/rangetheory";
import { lockModeLabels } from "../../domain/labels";
import { lockModes, type InfluenceSign, type LockMode } from "../../domain/schema";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";
import { ExceptionLibraryPanel } from "./ExceptionLibraryPanel";
import { ReadingDrawerSuggestionPanel } from "./ReadingDrawerSuggestionPanel";

const readingTypeOptions = [
  ["observation", "観測"],
  ["hypothesis", "仮説"],
  ["weight_modifier", "重み補正"],
  ["scenario", "シナリオ"],
  ["pruning_suggestion", "枝刈り提案"],
] as const;

const pruningOptions = [
  ["none", "何もしない"],
  ["soft_downweight", "弱める soft downweight"],
  ["hard_prune", "hard prune候補"],
  ["keep_top_k", "keep top-k"],
  ["hard_lock", "hard lock"],
  ["soft_lock", "soft lock"],
  ["freeze_ratio", "freeze ratio"],
] as const;

const residualPolicyOptions: ResidualMassPolicy[] = [
  "suggest_candidates",
  "add_to_exceptions",
  "keep_unknown_buffer",
  "normalize_existing",
  "leave_unassigned",
];

const emptyCandidates: ChoiceCandidateDraft[] = [];

const axisDescriptions: Record<AxisImpactDraft["axis_id"], string> = {
  progress_tenpai_axis: "テンパイ率、先制率、和了到達の近さを動かす読み",
  value_axis: "打点の高さ、レンジ、高打点尾部を動かす読み",
  wait_shape_quality_axis:
    "良形/愚形、待ち候補、和了しやすさ、安全度評価を動かす読み",
  score_situation_threshold_axis:
    "点棒状況、順位点、条件戦により押し引き閾値を動かす読み",
};

export function QuickReadingInputPanel() {
  const doc = useAppStore((state) => state.doc);
  const applyReadingImpactDraft = useAppStore(
    (state) => state.applyReadingImpactDraft,
  );
  const [draft, setDraft] = useState<ReadingImpactDraft>(() =>
    createExampleDraft(),
  );
  const [previewVisible, setPreviewVisible] = useState(false);

  const preview = useMemo(
    () => buildReadingImpactPreview(doc, draft),
    [doc, draft],
  );
  const propagationPreview = useMemo(
    () => runPropagation(preview.nextDoc, preview.createdNodeIds[0]),
    [preview],
  );
  const activeCase =
    doc.cases.find((caseItem) => caseItem.id === doc.active_case_id) ??
    doc.cases[0];

  const updateAxis = (
    axisId: AxisImpactDraft["axis_id"],
    patch: Partial<AxisImpactDraft>,
  ) => {
    setDraft((current) => ({
      ...current,
      axis_impacts: current.axis_impacts.map((impact) =>
        impact.axis_id === axisId ? { ...impact, ...patch } : impact,
      ),
    }));
  };

  return (
    <Panel
      title="読みを数値で反映"
      action={
        <div className="flex gap-1">
          <Button size="sm" onClick={() => setPreviewVisible(true)}>
            <Eye className="h-4 w-4" aria-hidden="true" />
            プレビュー
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={() => applyReadingImpactDraft(draft, true)}
            title={activeCase ? activeCase.title : "active caseがありません"}
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            active caseに反映
          </Button>
        </div>
      }
    >
      <div className="grid gap-3 p-3">
        <p className="text-sm leading-6 text-stone-600">
          読みをただのメモで終わらせず、4軸への影響・候補確率・枝刈り方針として反映します。
        </p>

        <div className="grid grid-cols-[1fr_180px_140px] gap-2">
          <Field label="読みタイトル">
            <Input
              value={draft.title}
              onChange={(event) =>
                setDraft((current) => ({ ...current, title: event.target.value }))
              }
              placeholder="例: 同色副露＋手出し字牌で染め本線上昇"
            />
          </Field>
          <Field label="読みタイプ">
            <Select
              value={draft.reading_type}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  reading_type: event.target
                    .value as ReadingImpactDraft["reading_type"],
                }))
              }
            >
              {readingTypeOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <PercentField
            label="確信度"
            value={draft.confidence}
            onChange={(confidence) =>
              setDraft((current) => ({ ...current, confidence }))
            }
          />
        </div>

        <Field label="読みメモ">
          <Textarea
            value={draft.memo}
            onChange={(event) =>
              setDraft((current) => ({ ...current, memo: event.target.value }))
            }
            placeholder="例: 中盤に同色副露が入り、手出し字牌が続いたため染め本線を上げる。ただし速度副露/役牌バックも残すので hard prune はしない。"
          />
        </Field>

        <section className="grid gap-2">
          <div className="text-sm font-semibold text-stone-900">4軸影響</div>
          <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
            {handValueRangeAxes.map((axis) => {
              const impact = draft.axis_impacts.find(
                (item) => item.axis_id === axis.id,
              );
              if (!impact) return null;
              return (
                <AxisImpactCard
                  key={axis.id}
                  axisId={axis.id}
                  label={axis.label}
                  description={axisDescriptions[axis.id]}
                  impact={impact}
                  onChange={(patch) => updateAxis(axis.id, patch)}
                />
              );
            })}
          </div>
        </section>

        <ChoiceGroupEditor draft={draft} onChange={setDraft} />
        <PruningPolicyEditor draft={draft} onChange={setDraft} />

        <Field label="context gate">
          <Input
            value={draft.context_gate ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                context_gate: event.target.value,
              }))
            }
            placeholder="例: 中盤 / 親番 / 南3 / 自分2着目 / 条件戦"
          />
        </Field>

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setPreviewVisible(true)}>
            <Eye className="h-4 w-4" aria-hidden="true" />
            プレビュー
          </Button>
          <Button variant="primary" onClick={() => applyReadingImpactDraft(draft, true)}>
            <Save className="h-4 w-4" aria-hidden="true" />
            active caseに反映
          </Button>
          <Button onClick={() => applyReadingImpactDraft(draft, false)}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            知識マップにだけ作成
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setDraft(createDefaultReadingImpactDraft());
              setPreviewVisible(false);
            }}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            入力をリセット
          </Button>
        </div>

        {previewVisible ? (
          <ReadingPreview
            draft={draft}
            preview={preview}
            propagationDiffs={propagationPreview.diffs}
            propagationWarnings={propagationPreview.warnings}
          />
        ) : null}
      </div>
    </Panel>
  );
}

function AxisImpactCard({
  axisId,
  label,
  description,
  impact,
  onChange,
}: {
  axisId: AxisImpactDraft["axis_id"];
  label: string;
  description: string;
  impact: AxisImpactDraft;
  onChange: (patch: Partial<AxisImpactDraft>) => void;
}) {
  return (
    <section className="rounded-md border border-stone-200 bg-stone-50 p-2">
      <div className="mb-2 flex items-start justify-between gap-2">
        <label className="flex items-center gap-2 text-sm font-semibold text-stone-950">
          <input
            type="checkbox"
            checked={impact.enabled ?? false}
            onChange={(event) => onChange({ enabled: event.target.checked })}
          />
          {label}
        </label>
        <Badge>{axisId}</Badge>
      </div>
      <p className="mb-2 text-xs leading-5 text-stone-500">{description}</p>
      <div className="grid grid-cols-2 gap-2">
        <Field label="方向">
          <Select
            value={impact.sign}
            onChange={(event) =>
              onChange({ sign: event.target.value as InfluenceSign })
            }
            disabled={!impact.enabled}
          >
            <option value="+">上げる +</option>
            <option value="-">下げる -</option>
            <option value="mixed">文脈次第 mixed</option>
            <option value="unknown">不明 unknown</option>
          </Select>
        </Field>
        <NumberField
          label="補正値"
          value={impact.dynamic_weight ?? 0}
          step="0.05"
          min={-1}
          max={1}
          disabled={!impact.enabled}
          onChange={(dynamic_weight) => onChange({ dynamic_weight })}
        />
        <PercentField
          label="影響量"
          value={impact.magnitude}
          disabled={!impact.enabled}
          onChange={(magnitude) => onChange({ magnitude })}
        />
        <PercentField
          label="軸確信度"
          value={impact.confidence}
          disabled={!impact.enabled}
          onChange={(confidence) => onChange({ confidence })}
        />
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-stone-500">メモ</summary>
        <Textarea
          className="mt-1 min-h-14"
          value={impact.note ?? ""}
          disabled={!impact.enabled}
          onChange={(event) => onChange({ note: event.target.value })}
        />
      </details>
    </section>
  );
}

function ChoiceGroupEditor({
  draft,
  onChange,
}: {
  draft: ReadingImpactDraft;
  onChange: (draft: ReadingImpactDraft) => void;
}) {
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [exceptionLibraryVisible, setExceptionLibraryVisible] = useState(false);
  const enabled = Boolean(draft.choice_group);
  const candidates = draft.choice_group?.candidates ?? emptyCandidates;
  const residualPolicy =
    draft.choice_group?.residual_policy ?? "keep_unknown_buffer";
  const residualSummary = useMemo(
    () =>
      buildResidualMassSummary(
        candidates,
        residualPolicy,
        draft.choice_group?.residual_buckets,
        { hardPrune: draft.pruning_policy.action === "hard_prune" },
      ),
    [
      candidates,
      draft.choice_group?.residual_buckets,
      draft.pruning_policy.action,
      residualPolicy,
    ],
  );

  const setChoiceGroup = (
    patch: Partial<NonNullable<ReadingImpactDraft["choice_group"]>>,
  ) => {
    onChange({
      ...draft,
      choice_group: {
        label: "読み候補群",
        normalize: false,
        residual_policy: "keep_unknown_buffer",
        residual_buckets: [],
        candidates,
        ...draft.choice_group,
        ...patch,
      },
    });
  };

  return (
    <section className="rounded-md border border-stone-200 p-3">
      <label className="flex items-center gap-2 text-sm font-semibold text-stone-950">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) =>
            onChange({
              ...draft,
              choice_group: event.target.checked
                ? {
                    label: "染め読み候補",
                    normalize: false,
                    residual_policy: "keep_unknown_buffer",
                    residual_buckets: [],
                    candidates: presetCandidates([0.55, 0.2, 0.1]),
                  }
                : undefined,
            })
          }
        />
        候補群の確率も設定する
      </label>

      {enabled && draft.choice_group ? (
        <div className="mt-3 grid gap-2">
          <div className="grid grid-cols-[1fr_180px] gap-2">
            <Field label="choice group label">
              <Input
                value={draft.choice_group.label}
                onChange={(event) => setChoiceGroup({ label: event.target.value })}
              />
            </Field>
            <label className="mt-7 flex items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                checked={draft.choice_group.normalize}
                onChange={(event) =>
                  setChoiceGroup({
                    normalize: event.target.checked,
                    residual_policy: event.target.checked
                      ? "normalize_existing"
                      : "keep_unknown_buffer",
                  })
                }
              />
              計算用正規化
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge
              tone={
                residualSummary.overallocated_probability > 0
                  ? "rose"
                  : residualSummary.residual_probability > 0
                    ? "amber"
                    : "emerald"
              }
            >
              候補合計 {formatPercent(residualSummary.raw_total)}
            </Badge>
            <Badge
              tone={
                residualSummary.residual_probability >= 0.25
                  ? "rose"
                  : residualSummary.residual_probability >= 0.15
                    ? "amber"
                    : "cyan"
              }
            >
              未配分 {formatPercent(residualSummary.residual_probability)}
            </Badge>
            <Badge
              tone={
                residualSummary.overallocated_probability > 0 ? "rose" : "stone"
              }
            >
              過剰分 {formatPercent(residualSummary.overallocated_probability)}
            </Badge>
            <PresetButton values={[0.6, 0.25, 0.15]} onApply={setChoiceGroup} />
            <PresetButton values={[0.55, 0.2, 0.1]} onApply={setChoiceGroup} />
            <PresetButton values={[0.4, 0.35, 0.25]} onApply={setChoiceGroup} />
            <Button
              size="sm"
              onClick={() =>
                setChoiceGroup({
                  candidates: presetCandidates(
                    Array.from(
                      { length: Math.max(1, candidates.length) },
                      () => 1 / Math.max(1, candidates.length),
                    ),
                  ),
                })
              }
            >
              均等
            </Button>
          </div>

          <section className="grid gap-2 rounded-md border border-stone-200 bg-stone-50 p-2">
            <div className="text-sm font-semibold text-stone-950">
              未配分の扱い
            </div>
            <div className="grid gap-1 md:grid-cols-2 xl:grid-cols-5">
              {residualPolicyOptions.map((policy) => (
                <label
                  key={policy}
                  className="flex items-start gap-2 rounded-md border border-stone-200 bg-white p-2 text-xs leading-5 text-stone-700"
                >
                  <input
                    className="mt-1"
                    type="radio"
                    name="residual-policy"
                    checked={residualPolicy === policy}
                    onChange={() =>
                      setChoiceGroup({
                        residual_policy: policy,
                        normalize: policy === "normalize_existing",
                      })
                    }
                  />
                  <span>{residualPolicyLabel(policy)}</span>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => {
                  setChoiceGroup({
                    residual_policy: "suggest_candidates",
                    normalize: false,
                  });
                  setDrawerVisible(true);
                }}
                disabled={residualSummary.residual_probability <= 0}
              >
                候補を提案
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setChoiceGroup({
                    residual_policy: "add_to_exceptions",
                    normalize: false,
                    residual_buckets: [
                      createResidualBucket(
                        "未配分からの例外候補",
                        "exception",
                        residualSummary.residual_probability,
                      ),
                    ],
                  });
                  setExceptionLibraryVisible(true);
                }}
                disabled={residualSummary.residual_probability <= 0}
              >
                例外集に入れる
              </Button>
              <Button
                size="sm"
                onClick={() =>
                  setChoiceGroup({
                    residual_policy: "keep_unknown_buffer",
                    normalize: false,
                    residual_buckets: [],
                  })
                }
                disabled={residualSummary.residual_probability <= 0}
              >
                未知バッファとして保持
              </Button>
              <Button
                size="sm"
                onClick={() =>
                  setChoiceGroup({
                    residual_policy: "normalize_existing",
                    normalize: true,
                  })
                }
                disabled={residualSummary.raw_total <= 0}
              >
                既存候補に按分
              </Button>
            </div>
          </section>

          <div className="grid gap-1.5">
            {candidates.map((candidate, index) => (
              <CandidateRow
                key={index}
                candidate={candidate}
                onChange={(next) =>
                  setChoiceGroup({
                    candidates: candidates.map((item, itemIndex) =>
                      itemIndex === index ? next : item,
                    ),
                  })
                }
                onRemove={() =>
                  setChoiceGroup({
                    candidates: candidates.filter((_, itemIndex) => itemIndex !== index),
                  })
                }
              />
            ))}
          </div>
          <Button
            size="sm"
            onClick={() =>
              setChoiceGroup({
                candidates: [
                  ...candidates,
                  { label: "新しい候補", posterior_probability: 0 },
                ],
              })
            }
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            候補を追加
          </Button>

          {residualSummary.warnings.length > 0 ? (
            <div className="grid gap-1.5">
              {residualSummary.warnings.map((warning) => (
                <div
                  key={`${warning.code}_${warning.message}`}
                  className={
                    warning.severity === "danger"
                      ? "rounded border border-rose-200 bg-rose-50 p-2 text-xs leading-5 text-rose-700"
                      : "rounded border border-amber-200 bg-amber-50 p-2 text-xs leading-5 text-amber-800"
                  }
                >
                  {warning.message}
                </div>
              ))}
            </div>
          ) : null}

          {residualPolicy === "normalize_existing" ? (
            <section className="rounded-md border border-cyan-200 bg-white p-2">
              <div className="mb-2 text-sm font-semibold text-stone-950">
                計算用正規化
              </div>
              <div className="grid gap-1 text-xs text-stone-700">
                {residualSummary.normalized_candidates.map((candidate) => (
                  <div
                    key={candidate.label}
                    className="grid grid-cols-[1fr_80px_80px] gap-2"
                  >
                    <span className="truncate">{candidate.label}</span>
                    <span>raw {formatPercent(candidate.raw_probability ?? 0)}</span>
                    <span>
                      norm {formatPercent(candidate.normalized_probability ?? 0)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs leading-5 text-stone-500">
                未配分は読み不足/例外/未知として保持し、ここでは候補比較用にだけ正規化しています。
              </p>
            </section>
          ) : null}

          {drawerVisible ? (
            <ReadingDrawerSuggestionPanel
              residualProbability={residualSummary.residual_probability}
              onAddCandidate={(candidate) => {
                const assigned = Math.min(
                  residualSummary.residual_probability,
                  candidate.posterior_probability ?? 0,
                );
                setChoiceGroup({
                  residual_policy: "suggest_candidates",
                  normalize: false,
                  candidates: [
                    ...candidates,
                    {
                      ...candidate,
                      posterior_probability: assigned,
                      base_weight: assigned,
                    },
                  ],
                });
              }}
              onAddException={(bucket) => {
                setChoiceGroup({
                  residual_policy: "add_to_exceptions",
                  normalize: false,
                  residual_buckets: [bucket],
                });
                setExceptionLibraryVisible(true);
              }}
              onKeepUnknown={() =>
                setChoiceGroup({
                  residual_policy: "keep_unknown_buffer",
                  normalize: false,
                  residual_buckets: [],
                })
              }
            />
          ) : null}

          {exceptionLibraryVisible ? (
            <ExceptionLibraryPanel
              onUseAsCandidate={(candidate) => {
                const assigned = Math.min(
                  residualSummary.residual_probability || 0.05,
                  candidate.posterior_probability ?? 0.05,
                );
                setChoiceGroup({
                  residual_policy: "suggest_candidates",
                  normalize: false,
                  candidates: [
                    ...candidates,
                    {
                      ...candidate,
                      posterior_probability: assigned,
                      base_weight: assigned,
                    },
                  ],
                });
              }}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function CandidateRow({
  candidate,
  onChange,
  onRemove,
}: {
  candidate: ChoiceCandidateDraft;
  onChange: (candidate: ChoiceCandidateDraft) => void;
  onRemove: () => void;
}) {
  return (
    <div className="grid grid-cols-[1fr_80px_90px_90px_130px_32px] gap-1.5">
      <Input
        aria-label="候補名"
        value={candidate.label}
        onChange={(event) => onChange({ ...candidate, label: event.target.value })}
      />
      <Input
        aria-label="確率%"
        type="number"
        min={0}
        max={100}
        value={Math.round((candidate.posterior_probability ?? 0) * 1000) / 10}
        onChange={(event) =>
          onChange({
            ...candidate,
            posterior_probability:
              normalizePercentInput(Number(event.target.value)) ?? 0,
          })
        }
      />
      <Input
        aria-label="base weight"
        type="number"
        step="0.05"
        value={candidate.base_weight ?? ""}
        onChange={(event) =>
          onChange({
            ...candidate,
            base_weight: optionalNumber(event.target.value),
          })
        }
      />
      <Input
        aria-label="dynamic weight"
        type="number"
        step="0.05"
        value={candidate.dynamic_weight ?? ""}
        onChange={(event) =>
          onChange({
            ...candidate,
            dynamic_weight: optionalNumber(event.target.value),
          })
        }
      />
      <Select
        aria-label="lock mode"
        value={candidate.lock_mode ?? "none"}
        onChange={(event) =>
          onChange({
            ...candidate,
            lock_mode: event.target.value as LockMode,
          })
        }
      >
        {lockModes.map((mode) => (
          <option key={mode} value={mode}>
            {lockModeLabels[mode]}
          </option>
        ))}
      </Select>
      <Button size="icon" variant="ghost" onClick={onRemove}>
        ×
      </Button>
    </div>
  );
}

function createResidualBucket(
  label: string,
  kind: ResidualMassBucket["kind"],
  probability: number,
): ResidualMassBucket {
  return {
    id: `residual_bucket_${kind}_${Date.now()}`,
    label,
    kind,
    probability,
    note: "Quick Readingの未配分UIから作成。",
    tags: ["residual_mass", kind],
  };
}

function PruningPolicyEditor({
  draft,
  onChange,
}: {
  draft: ReadingImpactDraft;
  onChange: (draft: ReadingImpactDraft) => void;
}) {
  const policy = draft.pruning_policy;
  const setPolicy = (patch: Partial<ReadingImpactDraft["pruning_policy"]>) =>
    onChange({ ...draft, pruning_policy: { ...policy, ...patch } });

  return (
    <section className="rounded-md border border-stone-200 p-3">
      <div className="mb-2 text-sm font-semibold text-stone-950">
        枝刈り/ロック方針
      </div>
      <div className="mb-2 grid gap-1 text-xs leading-5 text-stone-600">
        <div>pruning: 候補を削る/弱める</div>
        <div>lock: 候補を残したまま分布を固定する</div>
        <div>keep top-k: 1つに絞らず複数仮説を残す</div>
      </div>
      <div className="grid grid-cols-[220px_1fr] gap-2">
        <Field label="方針">
          <Select
            value={policy.action}
            onChange={(event) =>
              setPolicy({
                action: event.target
                  .value as ReadingImpactDraft["pruning_policy"]["action"],
              })
            }
          >
            {pruningOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid grid-cols-3 gap-2">
          <NumberField
            label="strength"
            value={policy.strength ?? 0}
            min={0}
            max={1}
            step="0.05"
            onChange={(strength) => setPolicy({ strength })}
          />
          <NumberField
            label="top_k"
            value={policy.top_k ?? 3}
            min={1}
            max={8}
            step="1"
            onChange={(top_k) => setPolicy({ top_k: Math.round(top_k) })}
          />
          <NumberField
            label="lock_value"
            value={policy.lock_value ?? 0}
            min={0}
            max={1}
            step="0.05"
            onChange={(lock_value) => setPolicy({ lock_value })}
          />
        </div>
      </div>
      <Field label="rationale">
        <Textarea
          value={policy.rationale}
          onChange={(event) => setPolicy({ rationale: event.target.value })}
        />
      </Field>
    </section>
  );
}

function ReadingPreview({
  draft,
  preview,
  propagationDiffs,
  propagationWarnings,
}: {
  draft: ReadingImpactDraft;
  preview: ReturnType<typeof buildReadingImpactPreview>;
  propagationDiffs: ReturnType<typeof runPropagation>["diffs"];
  propagationWarnings: string[];
}) {
  return (
    <section className="rounded-md border border-cyan-200 bg-cyan-50/40 p-3">
      <div className="mb-2 flex flex-wrap gap-2">
        <Badge tone="cyan">作成予定ノード {preview.createdNodeIds.length}</Badge>
        <Badge tone="cyan">作成予定エッジ {preview.createdEdgeIds.length}</Badge>
        <Badge>{draft.pruning_policy.action}</Badge>
      </div>
      <div className="grid gap-2">
        {preview.warnings.map((warning) => (
          <div
            key={`${warning.code}_${warning.message}`}
            className="flex gap-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{warning.message}</span>
          </div>
        ))}
        {propagationWarnings.map((warning) => (
          <div
            key={warning}
            className="rounded border border-amber-200 bg-white p-2 text-xs text-amber-800"
          >
            {warning}
          </div>
        ))}
      </div>
      <div className="mt-3 grid gap-2 text-xs text-stone-700">
        <div className="font-semibold text-stone-900">4軸影響サマリ</div>
        <div className="flex flex-wrap gap-1">
          {draft.axis_impacts
            .filter((impact) => impact.enabled)
            .map((impact) => {
              const axis = handValueRangeAxes.find(
                (item) => item.id === impact.axis_id,
              );
              return (
                <Badge key={impact.axis_id} tone="stone">
                  {axis?.label}: {impact.sign} {Math.round(impact.magnitude * 100)}%
                </Badge>
              );
            })}
        </div>
        {draft.choice_group ? (
          <div>
            <div className="font-semibold text-stone-900">choice group確率</div>
            <div className="mt-1 flex flex-wrap gap-1">
              {draft.choice_group.candidates.map((candidate) => (
                <Badge key={candidate.label}>
                  {candidate.label}{" "}
                  {Math.round((candidate.posterior_probability ?? 0) * 1000) /
                    10}
                  %
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        <div>
          <div className="font-semibold text-stone-900">伝播diff</div>
          <div className="mt-1 grid gap-1">
            {propagationDiffs.slice(0, 6).map((diff) => (
              <div key={diff.node_id} className="rounded border border-stone-200 bg-white p-1.5">
                {diff.title}: {Math.round((diff.before ?? 0) * 1000) / 10}% {"->"}{" "}
                {Math.round((diff.after ?? 0) * 1000) / 10}% / {diff.reason}
              </div>
            ))}
            {propagationDiffs.length === 0 ? (
              <div className="text-stone-500">確率差分はまだありません。</div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function PercentField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={`${label} ${Math.round(value * 100)}%`}>
      <Input
        type="range"
        min={0}
        max={100}
        value={Math.round(value * 100)}
        disabled={disabled}
        onChange={(event) =>
          onChange(normalizePercentInput(Number(event.target.value)) ?? 0)
        }
      />
    </Field>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: string;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label}>
      <Input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  );
}

function PresetButton({
  values,
  onApply,
}: {
  values: number[];
  onApply: (patch: Partial<NonNullable<ReadingImpactDraft["choice_group"]>>) => void;
}) {
  return (
    <Button size="sm" onClick={() => onApply({ candidates: presetCandidates(values) })}>
      {values.map((value) => Math.round(value * 100)).join("/")}
    </Button>
  );
}

function presetCandidates(values: number[]) {
  const labels = ["染め本線", "速度副露", "役牌バック", "染め薄い"];
  return values.map((value, index) => ({
    label: labels[index] ?? `候補${index + 1}`,
    posterior_probability: value,
    base_weight: value,
    dynamic_weight: 0,
    lock_mode: "none" as const,
    tags: ["quick_reading"],
  }));
}

function createExampleDraft() {
  const draft = createDefaultReadingImpactDraft();
  return {
    ...draft,
    title: "同色副露＋手出し字牌で染め本線上昇",
    memo: "中盤に同色副露が入り、手出し字牌が続いたため染め本線を上げる。ただし速度副露/役牌バックも残すので hard prune はしない。",
    context_gate: "中盤 / 対副露",
    axis_impacts: draft.axis_impacts.map((impact) => {
      if (impact.axis_id === "value_axis") {
        return { ...impact, enabled: true, sign: "+", magnitude: 0.25 };
      }
      if (impact.axis_id === "progress_tenpai_axis") {
        return { ...impact, enabled: true, sign: "+", magnitude: 0.1 };
      }
      if (impact.axis_id === "wait_shape_quality_axis") {
        return { ...impact, enabled: true, sign: "mixed", magnitude: 0.15 };
      }
      return { ...impact, enabled: true, sign: "+", magnitude: 0.05 };
    }),
    choice_group: {
      label: "染め読み候補",
      normalize: false,
      residual_policy: "keep_unknown_buffer",
      residual_buckets: [],
      candidates: presetCandidates([0.55, 0.2, 0.1]),
    },
    pruning_policy: {
      action: "keep_top_k",
      top_k: 3,
      strength: 0.2,
      lock_value: 0.6,
      rationale: "染め薄いと速度副露を完全には消さない。",
    },
  } satisfies ReadingImpactDraft;
}

function optionalNumber(value: string) {
  if (value.trim() === "") return undefined;
  const next = Number(value);
  return Number.isFinite(next) ? next : undefined;
}
