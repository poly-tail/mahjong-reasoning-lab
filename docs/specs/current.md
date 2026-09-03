# 仕様書 現行版

> 現行版: `api_spec_v2.2.md`
> 更新日: `2026-09-03`
> 前版: `api_spec_v2.1.md`

## 現行仕様の要点

- `LiveTableSnapshot` は UI 1 回の描画用 snapshot として扱う。現在局面の構造データを持ち、heavy suji / 危険度の新入力が計算中の場合だけ、同一局の直前完了 bundle を表示用 fallback として含めてよい。
- 表示用 fallback は最新入力に対する計算結果とはみなさず、次 job の enqueue / coalescing を妨げない。手牌危険度は旧 bundle の `hand_tiles` から現在手牌へ牌 ID と同牌内の出現順で再対応付けし、対応元のない牌は棒なしとする。完了値がまだない初回は loading / 危険度棒なし、新局では fallback なしとする。stale な panel / hand / Push payload は自動打牌や alert 音声の新規判定へ使わない。
- `NagaAutoPanelData` を renderer へ渡し、南2局以降の NAGA 段位 pt 変化を下部へ表示する。
- `PlayerAlertIndicator` は panel 表示と音声判定の正本であり、panel に出ない自分側 alert は音声へ流さない。
- renderer の実 Canvas は `alert_sound_enabled = False` で初期化する。上部の `アラート音 OFF/ON` ボタンでセッション中だけ切り替え、ON 切替時は alert 遷移 latch と独立した上昇2音の確認チャイム、続いて `alert_sound_on.wav` の「サウンド、オン」音声を共有 sound worker で1回鳴らす。OFF 中も各音声経路の遷移 latch を更新して、ON 切替時に既存 alert を再生しない。
- 他家の最新打牌が `thinking_time_ms <= 2300ms` かつ 3-7 の数牌の場合、`haya` alert を出し `alert_panel_haya.wav` を鳴らす。ただし最新 event が自家打牌の場合は、表示上 `haya` が残っていても音声は鳴らさない。
- 他家の最新打牌が第一打以外で `thinking_time_ms >= 4000ms` かつ 1/2/8/9 の数牌の場合、`oso` alert を出し `alert_panel_oso.wav` を鳴らす。ただし最新 event が自家打牌の場合は、表示上 `oso` が残っていても音声は鳴らさない。
- 半荘内3局目以降の他家1段目3〜6打目では、現在局の席別平均思考時間が、過去局の `kyoku_master.seat0..3_first_row_avg_thinking_time_ms` 平均より早い場合に黄色の `早い傾向` alert を出し、`alert_panel_fast_trend.wav` を状態入場時だけ鳴らす。5局目は1〜4局目の平均を使う。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。
- player-panel 音声は同一の global discard index 内で音声 asset / kind 単位にも de-dup する。同じ `alert_panel_yellow` / `alert_panel_red` などへ解決される alert key は 1 回だけ queue し、異なる kind は同じ捨て牌でも FIFO 順に queue する。
- `LiveTableSnapshot.latest_event_type` は snapshot が参照した最新 raw event type を保持する。renderer は `wgc` / `initbylog` を受け取った場合、または Bridge map 成功で live snapshot refresh token が進んだ場合に、source と live refresh token ごとに一度だけ `alert_huuuro.wav` で「huuuro」を鳴らす。async-only refresh では同じ source を再鳴動しない。
- `Push` alert payload は seat / tile / discard_index / percentage / threshold を持ち、panel と河 `P` marker は同じ payload から決める。ただし河 `P` は各席の捨て牌 local index 0〜5では描画せず、index 6 以降だけ描画する。
- `Push` 音声は panel の 3巡保持中に繰り返さず、Push alert が有効になった最初のタイミングだけ鳴らす。
- `Remain` alert は `SUMMARY` と同じ no-temp remain 閾値で色を決める。
- `Remain` 音声は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさない。閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- 河の base river layer は full redraw 境界では `live_async_discards` tag を全削除し、`canvas.discard_render_cache_by_key` / `discard_tile_image_refs` を reset してから描き直す。cached-layout redraw では slot 単位の表示シグネチャ cache を使い、cache hit でも Canvas item tag の存在を確認してから skip する。Canvas item が消えている slot は cache hit でも再描画する。さらに最新 event が `call`、または `LiveTableSnapshot.recent_event_types` に `call` が含まれる redraw / async-only refresh 後だけ、`discard_map` に残る slot の `live_async_discards_<seat>_<index>` image item が Canvas 上に存在するかを検査し、欠けている場合は同じ refresh 内で描かず通常 redraw queue へ戻す。
- cached-layout redraw で table frame の表示署名が変わる場合、frame が持つ不透明な discard zone は既存 base river item より後に作られるため、frame 再作成前に `live_async_discards` / `live_discard_analysis_overlay` を削除し、discard render cache / image refs / overlay signature / geometry を invalidate する。同じ redraw 内で frame -> base river -> analysis overlay の順に再作成し、存在するが frame の背面に隠れた item を cache hit で skip してはならない。副露後の自動 REINIT は行わない。
- `_discard_tile_image()` は通常牌画像だけを返す。赤/茶/紫/4見え/思考時間は Canvas overlay で描画する。
- 局中の base river 履歴の正本は `GameState.live_river_store` / `CaptureState.live_river_store` とし、`RoundState.discards`、`RoundState.discard_ledger`、`tracker.discards`、renderer cache は互換 view / 派生 view / 描画補助として扱う。
- `CaptureState.live_stable_discard_map` は `LiveRiverStore` 由来で最後に安全に発行できた表示用 copy とする。同一 `LiveRiverStore.epoch` 内では短い snapshot で上書きせず、cached `LiveTableSnapshot` が古い/短い `discard_map` を返す場合だけ表示用に補強する。capture state lock が副露処理などで busy の場合も、stable copy の optimistic read だけで補強し、capture 履歴、`LiveRiverStore`、`RoundState.discards`、`tracker.discards` へは書き戻さない。
- `tracker.discards` は guarded append-only map/list であり、通常処理では append / extend と既存 discard metadata 更新だけを許す。`clear` / `pop` / `del` / 短い代入は live `INIT` または明確な別局 `REINIT` の reset context 以外では失敗する。
- `same_jun_marker_indices_by_seat` は `LiveRiverStore` 由来の全席捨て牌履歴を global discard順で照合した表示用フラグである。他家の `tedashi` を起点に、その後5回以内の捨て牌増加で同じ34種牌が切られた場合に対象slotを記録する。途中に対象seat自身の別打牌があっても窓内なら有効で、起点側のツモ切り、副露公開、ドラ表示は起点にしない。副露・ドラ表示は5打牌窓も消費しない。候補抽出はappend cacheを使い、full confirmは既存の `awaseuchi confirm` background workerで行う。
- 合わせ打ち表示は base riverを変更せず、`live_discard_analysis_overlay` 上で対象牌画像へ黄色の `合` を重ねる。
- 副露 `N` は鳴かれた捨て牌を削除せず、既存 discard の `called` / lag metadata と副露エリアだけを更新する。既存 base river がある場合、`INIT` / `REINIT` 以外の tag で `LiveRiverStore` を reset / shorten してはならない。
- `LiveTableSnapshot.latest_event_type` は従来どおり最新 event だけを表す。`recent_event_types` は snapshot publish lag で UI が `call` frame を描けず、次の discard frame として処理する場合の復元 gate に使う。
- 副露 `N` の count 不変ガードが破れた場合は、`called_discard_disappearance_guard` diagnostic と `logs/live_capture.log` に、原因分類、対象層、席、before/after count、raw tag、round identity、直前/発行 event を残す。副露直後、または recent event context に `call` が残る間に Canvas item 欠落を検知した場合は、同じ refresh 内で再描画せず通常 redraw queue へ戻し、`UI called discard canvas repair deferred` を残す。
- live `INIT` は復帰判定なしの authoritative full reset であり、既存 base river / tracker / stable discard map / round UI state を前局から引き継がない。DB async persist worker / queue は reset 対象ではなく、同一半荘の `game_id` / 卓種 / player metadata は保持する。
- 非空 `LiveRiverStore` を clear できるのは、実際の `parse_init()` 経路、confirmed different round の `parse_reinit()` 経路、または `INITBYLOG` / `WGC` snapshot が `LiveRiverStore.round_key` と明確に別 game / 別局であると証明できた場合だけである。いずれも `allow_non_empty_clear=True` を明示する。
- REINIT / WGC / INITBYLOG / browser bridge の river は visible projection として扱い、同一局または key 不明の場合は base river へ reset + seed しない。`INITBYLOG` / `WGC` は snapshot の `log` / `id` が `LiveRiverStore.round_key[0]` と異なる、または完全な `(kyoku, honba, kyotaku, oya)` tuple が異なる場合だけ `REINIT_DIFFERENT_ROUND_CONFIRMED` として非空 base river を reset + seed できる。`current_round is None` でも `LiveRiverStore` に既存 discard があり snapshot key が同一/不明なら projection-only を優先する。
- `LiveRiverStore` / `RoundState.discards` / `tracker.discards` のいずれかに既存 discard がある場合、live `INIT` 以外の live session metadata reset は `current_round` / `rounds` / `tracker.discards` / `live_stable_discard_map` を消してはならない。tracker 再構築は `LiveRiverStore` を優先し、短い `RoundState.discards` projection から画面用 river を作り直さない。
- heavy suji / 危険度 bundle の完了では async subtoken だけを進め、live async-only refresh で side panel / hand overlay / alert 表示と analysis overlay だけを差し替える。`_draw_discards()` を呼ばず、`live_async_discards` tag と table frame は削除・再描画しない。副露 `call` event または recent event context の `call` 後に配列へ残る Canvas image item 欠落を検知した場合は、async-only refresh を中断して通常 redraw へ戻す。
- DB分析 `scripts/analyze_player_shanten_thinking.py` は `discard_fact_*.csv` と `hanchan_master.csv` を読み、プレイヤー別の思考時間 x シャンテン相関と所属卓を出す。

## 関連文書

- 仕様本体: [api_spec_v2.2.md](./api_spec_v2.2.md)
- 要件定義: [../requirements/current.md](../requirements/current.md)
- 画面仕様: [../screen_specs/current.md](../screen_specs/current.md)
## 2026-07-06 alert sound duplicate suppression

- Alert sound jobs use a stable job signature. If the same sound job is already queued, or the worker has handed it to playback and it is still active, the same job is not queued again.
- When the worker takes a job from the FIFO queue, that job is removed from the queued set and tracked as active until playback returns.

## 2026-07-05 dora discard alert

- `dora`: When an opponent's latest discard is a dora tile derived from `dora_indicator_tiles`, or a red five, emit a `PlayerAlertIndicator` with a `dora:*` key and play `alert_panel_dora.wav`.
- `dora:*` is a latest-discard action alert like `haya:*` / `oso:*`; if the latest event actor is `Player.JICHA`, the indicator may remain visible but the sound is suppressed.
- This alert does not redraw or mutate the base river layer.

- CSV DB: [../reference/csv_db_design.md](../reference/csv_db_design.md)
- 性能ホットスポット: [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
