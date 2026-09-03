# 画面仕様書 現行版

> 現行版: `screen_spec_v2.2.md`
> 更新日: `2026-09-03`
> 前版: `screen_spec_v2.1.md`

## 現行画面の要点

- 画面は卓、河、自家手牌、他家プレイヤーパネル、右詳細領域、Bridge 操作、NAGA 下部パネルで構成する。
- 画面左上の専用段に `アラート音 OFF/ON` ボタンを表示する。遅れて生成される `NAGA段位` ボタンと座標を共有しない。起動時は OFF とし、ON 切替時は音量確認用の上昇2音チャイムと「サウンド、オン」音声を1回鳴らし、ON の間だけ alert 音声を再生する。OFF 中に表示済みとなった alert は、ON 切替時に遅れて鳴らさない。
- 河は `L`, `Pl`, `P`, 合わせ打ちの `合`、最大思考時間、3見え/4見え、赤/茶/紫 tint を表示する。Push `P` は各席の1段目（捨て牌 local index 0〜5）には表示せず、2段目以降だけ表示する。
- 各席の2段目以降で `Push` 音声が鳴る更新では、同じ対象捨て牌へ `P` マークを即時表示する。
- 他家の最新打牌が `thinking_time_ms <= 2300ms` かつ 3-7 の数牌の場合、`haya` panel alert と `alert_panel_haya.wav` 音声を出す。ただし最新 event が自家打牌の場合は音声を鳴らさない。
- 他家の最新打牌が第一打以外で `thinking_time_ms >= 4000ms` かつ 1/2/8/9 の数牌の場合、`oso` panel alert と `alert_panel_oso.wav` 音声を出す。ただし最新 event が自家打牌の場合は音声を鳴らさない。
- 半荘内3局目以降、他家の1段目3〜6打目で現在局平均思考時間が過去局平均より早い場合は、黄色の `早い傾向` panel alert と `alert_panel_fast_trend.wav` 音声を出す。
- Bridge map 成功、`WGC`、`INITBYLOG` では `alert_huuuro.wav` で「huuuro」を鳴らす。同じ source / live refresh token の再描画では再鳴動しない。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。
- 同一の global discard index では同じ音声 asset / kind を 1 回だけ鳴らし、同じ捨て牌内の `alert_panel_yellow` / `alert_panel_red` など同種音声の二重再生を抑制する。異なる音声 kind は同じ捨て牌でも順番に鳴らす。
- `Push` 音声は 3巡保持中に繰り返さず、Push が有効になった最初のタイミングだけ鳴らす。
- `Remain` 音声は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさない。閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- 他家 panel の `SUMMARY` と `ALERT` は同じ remain 閾値を使う。
- 同一局の heavy suji / 危険度計算中は、他家 side panel、自家手牌の危険度棒、関連する河 analysis overlay に直前の完了済み bundle を表示し続ける。手牌が変わった場合、旧危険度は同じ牌と同牌内の出現順に再対応付けし、対応する旧牌がない牌には stale な棒を表示しない。初回計算だけ loading / 危険度棒なしとし、新局へ前局値を持ち越さない。
- 新 bundle 完了時は async-only partial refresh で side panel / hand / analysis overlay だけをまとめて差し替え、base river / table frame は再描画しない。計算中の stale 値は表示専用であり、自動打牌や alert 音声の新規判定には使わない。
- Nodocchi `STATUS` は和了率・副露率・リーチ率だけ赤字、その他は白字。
- 南2局以降、下部スペースに NAGA 段位ポイント分析の自動要約を表示する。
- 河の base river layer は full redraw 境界では全削除・全描画する。cached-layout redraw では slot 単位の表示シグネチャと Canvas item tag の存在を確認し、変化のない base 牌を再利用する。analysis overlay だけは別 layer として async-only refresh で更新する。ただし副露 `call` event、または `LiveTableSnapshot.recent_event_types` に `call` が残る redraw / async-only refresh 後だけ、配列に残る slot の Canvas image item 欠落を検知する。欠け検出時は同じ refresh 内で差分再実行せず、通常 redraw queue へ戻す。
- 河は base river layer と analysis overlay layer に分ける。base は牌画像本体、手出し/ツモ切り、思考時間、lag、`called=True` 黄色枠、リーチ棒を描く。analysis overlay は red / brown / four-visible tint、見え枚数 marker、2段目以降の Push `P`、合わせ打ちの `合` を牌画像上へ重ねる。
- 合わせ打ち表示は、他家の手出しから数えて5回以内の全席捨て牌増加で同じ34種牌が切られたslotに付ける。途中の別打牌をまたいでも窓内なら有効で、副露・ドラ表示は起点にも窓消費にも使わず、起点側のツモ切りは対象外とする。
- 副露、カン、REINIT、Bridge snapshot の直後でも、base river は `LiveRiverStore.snapshot_by_seat()` 由来の `discard_map` だけを描画する。鳴かれた捨て牌は削除せず `called=True` の黄色枠として残す。
- 副露で meld が増えて table frame を再作成するときは、opaque な discard zone が既存の河より前面に積まれないよう、base river / analysis overlay と各描画 cache を同時に invalidate し、同じ redraw 内で frame の後に河を全描画する。履歴や Canvas item が存在するだけでは可視とみなさず、frame の背面へ隠れる状態を許さない。
- renderer は round cache とは別に最後に描けた base river backup を保持する。snapshot fallback は capture state lock が busy の場合も表示用 stable copy の optimistic read で短い cached snapshot を補強する。`round_identity=None` や短い/空 projection が来ても、`LiveRiverStore.epoch` が変わるまでは backup から画面の欠落 slot を復元し、epoch 変更時だけ前局 backup を破棄する。
- 最新 event が `call`、または recent event context に `call` が残るときに短い `discard_map` を受けた場合、Canvas discard slot を削除した場合、または配列に残る slot の Canvas image item を復元した場合は `logs/live_capture.log` に UI 側の河診断を残す。

## 詳細文書

## 2026-07-06 alert sound duplicate suppression

- Alert sound jobs use a stable job signature. If the same sound job is already queued, or the worker has handed it to playback and it is still active, the same job is not queued again.
- When the worker takes a job from the FIFO queue, that job is removed from the queued set and tracked as active until playback returns.

## 2026-07-05 dora discard alert

- `dora`: When an opponent's latest discard is a dora tile derived from `dora_indicator_tiles`, or a red five, show a `dora` panel alert and play `alert_panel_dora.wav`.
- If the latest event actor is `Player.JICHA`, the `dora` indicator may remain visible but the sound is suppressed.
- This alert does not redraw or mutate the base river layer.

- 画面全体: [display_overview.md](./display_overview.md)
- 河表示: [river_display.md](./river_display.md)
- パネルとアラート: [alerts_and_panels.md](./alerts_and_panels.md)
- 操作と Bridge: [controls_and_bridge.md](./controls_and_bridge.md)
- 見え枚数 UI: [visible_counts_ui.md](./visible_counts_ui.md)
- 版付き画面仕様: [screen_spec_v2.2.md](./screen_spec_v2.2.md)

## 関連文書

- 要件定義: [../requirements/current.md](../requirements/current.md)
- 仕様書: [../specs/current.md](../specs/current.md)
- 性能ホットスポット: [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- NAGA 連携: [../integrations/naga_ptev_analyzer.md](../integrations/naga_ptev_analyzer.md)
