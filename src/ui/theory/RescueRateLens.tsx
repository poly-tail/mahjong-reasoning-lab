import { AlertTriangle, Plus, TimerReset } from "lucide-react";
import { useMemo, useState } from "react";
import { useAppStore } from "../../app/store";
import { rescueEvents } from "../../domain/mahjongTaxonomy";
import { createRescueRateDraft } from "../../domain/mappingTemplates";
import {
  estimateRescueRate,
  type RescueRateBand,
  type RescueRateEventEstimate,
} from "../../domain/rescueRate";
import { Badge } from "../components/badge";
import { Button } from "../components/button";
import { Field, Input, Select, Textarea } from "../components/form";
import { Panel } from "../components/panel";

const timeWindows = [
  "自分の次手番まで",
  "一巡以内",
  "流局まで",
  "任意入力",
] as const;

const initialEvents: RescueRateEventEstimate[] = rescueEvents.map((event) => ({
  id: event.id,
  label: event.label,
  enabled: true,
  probability: undefined,
}));

const bandOptions: { id: RescueRateBand; label: string }[] = [
  { id: "low", label: "低い" },
  { id: "some", label: "ややある" },
  { id: "medium", label: "そこそこ" },
  { id: "high", label: "高い" },
];

export function RescueRateLens() {
  const createKnowledgeNodesFromDrafts = useAppStore(
    (state) => state.createKnowledgeNodesFromDrafts,
  );
  const [timeWindow, setTimeWindow] =
    useState<(typeof timeWindows)[number]>("一巡以内");
  const [customWindow, setCustomWindow] = useState("");
  const [events, setEvents] = useState(initialEvents);
  const [fallbackBand, setFallbackBand] = useState<RescueRateBand>("some");
  const [memo, setMemo] = useState("");

  const estimate = useMemo(
    () => estimateRescueRate(events, fallbackBand),
    [events, fallbackBand],
  );
  const windowLabel =
    timeWindow === "任意入力" && customWindow.trim()
      ? customWindow.trim()
      : timeWindow;

  const updateEvent = (
    id: string,
    patch: Partial<RescueRateEventEstimate>,
  ) => {
    setEvents((current) =>
      current.map((event) => (event.id === id ? { ...event, ...patch } : event)),
    );
  };

  const createNodes = () => {
    const draft = createRescueRateDraft(
      memo.trim() ||
        `脇救済率を ${windowLabel} の時間窓で、上限レンジ ${estimate.range_label} として扱う。`,
    );
    createKnowledgeNodesFromDrafts(draft.nodes, true);
  };

  return (
    <main className="min-h-0 flex-1 overflow-auto p-3">
      <div className="grid gap-3">
        <Panel title="脇救済率">
          <div className="grid grid-cols-[340px_1fr] gap-3 p-3">
            <div className="grid content-start gap-3">
              <Field label="時間窓">
                <Select
                  value={timeWindow}
                  onChange={(event) =>
                    setTimeWindow(event.target.value as typeof timeWindow)
                  }
                >
                  {timeWindows.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </Select>
              </Field>
              {timeWindow === "任意入力" ? (
                <Field label="任意の時間窓">
                  <Input
                    value={customWindow}
                    onChange={(event) => setCustomWindow(event.target.value)}
                    placeholder="例: 自分の危険牌選択まで"
                  />
                </Field>
              ) : null}
              <Field label="定性的な帯" hint="個別確率を入れない場合に使います。">
                <Select
                  value={fallbackBand}
                  onChange={(event) =>
                    setFallbackBand(event.target.value as RescueRateBand)
                  }
                >
                  {bandOptions.map((band) => (
                    <option key={band.id} value={band.id}>
                      {band.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="合成確率メモ">
                <Textarea
                  value={memo}
                  onChange={(event) => setMemo(event.target.value)}
                  placeholder="個別確率は厳密推定ではなく、上限レンジとして残す。"
                />
              </Field>
              <Button variant="primary" onClick={createNodes}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                関連ノードを作成
              </Button>
            </div>

            <div className="grid gap-3">
              <div className="rounded-md border border-stone-200 bg-stone-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <TimerReset
                      className="h-4 w-4 text-cyan-700"
                      aria-hidden="true"
                    />
                    <h3 className="text-sm font-semibold text-stone-950">
                      {windowLabel}
                    </h3>
                  </div>
                  <Badge tone={estimate.q_total && estimate.q_total > 0.3 ? "rose" : "cyan"}>
                    {estimate.band_label} / {estimate.range_label}
                  </Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-stone-600">
                  q_total = 1 - product(1 - q_i)。入力値がある場合だけ概算計算し、UI上では上限レンジとして扱います。
                </p>
              </div>

              <div className="grid gap-2">
                {events.map((event) => (
                  <label
                    key={event.id}
                    className="grid grid-cols-[24px_1fr_96px] items-center gap-2 rounded-md border border-stone-200 p-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={event.enabled}
                      onChange={(inputEvent) =>
                        updateEvent(event.id, {
                          enabled: inputEvent.target.checked,
                        })
                      }
                    />
                    <span className="text-stone-800">{event.label}</span>
                    <Input
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={event.probability ?? ""}
                      placeholder="0-1"
                      onChange={(inputEvent) =>
                        updateEvent(event.id, {
                          probability:
                            inputEvent.target.value === ""
                              ? undefined
                              : Number(inputEvent.target.value),
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        </Panel>

        <div className="grid grid-cols-2 gap-3">
          <Panel title="押し引きへの影響">
            <div className="grid gap-2 p-3 text-sm text-stone-700">
              <div className="rounded-md border border-stone-200 p-3">
                fold_risk を下げる方向。ただし救済イベントは独立とは限りません。
              </div>
              <div className="rounded-md border border-stone-200 p-3">
                push_value を上げる補正になり得ますが、他力期待で危険牌選択を正当化しないよう上限を置きます。
              </div>
            </div>
          </Panel>

          <Panel title="上限警告">
            <div className="grid gap-2 p-3">
              {estimate.warnings.length > 0 ? (
                estimate.warnings.map((warning) => (
                  <div
                    key={warning}
                    className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-sm leading-6 text-amber-800"
                  >
                    <AlertTriangle className="mt-0.5 h-4 w-4" aria-hidden="true" />
                    <span>{warning}</span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-stone-500">
                  現在の入力では過大評価警告はありません。
                </p>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}
