# API / 管理仕様 v2.2

更新日: `2026-09-03`

## 1. Runtime snapshot

### `LiveTableSnapshot`

UI 1 回の描画で使う局面 snapshot。DB row ではなく、capture state から renderer へ渡す表示用構造である。

主な内容:

- 手牌、捨て牌、副露、ドラ表示牌
- `VisibleTileSummary`
- `VisibleTileInferenceSummary`
- 他家プレイヤーパネル用 summary / alert payload
- `push_marker_alert_percentages`
- `same_jun_marker_indices_by_seat`
- `table_situation_auto_scores_by_seat`
- `NagaAutoPanelData`
- `latest_event_type`
- `recent_event_types`
- `suji_analysis_is_current`

`same_jun_marker_indices_by_seat` はDB列ではなく、保持済みの全席 `discard_map` から作る表示用の seat -> local discard index 集合である。起点は他家の `DrawType.TEDASHI` だけとし、その後5回以内のglobal discard増加で同じ34種牌が切られた場合にtarget slotを追加する。targetは手出し/ツモ切りを問わない。副露・ドラ表示は起点にも窓消費にも使わない。rendererはappend済みevent streamを保持し、候補があるときだけ不変snapshotを `awaseuchi confirm` background workerへ渡す。結果はTk threadで回収し、analysis overlayの `合` 表示へ反映する。

live の `discard_map` は `GameState.live_river_store` / `CaptureState.live_river_store` の `snapshot_by_seat()` から作る。`RoundState.discards[seat]`、`RoundState.discard_ledger`、`tracker.discards`、renderer cache は互換 view / 派生 view / 描画補助であり、base river の正史ではない。`CaptureState.live_stable_discard_map` は `LiveRiverStore` 由来で最後に安全に発行できた表示用 copy であり、同一 `LiveRiverStore.epoch` 内の短い snapshot では上書きしない。cached `LiveTableSnapshot` が古い/短い `discard_map` を返す場合だけ、表示用 `discard_map` を stable copy で補強する。capture state lock が副露処理などで busy の場合も、stable copy の optimistic read だけで補強する。snapshot builder は stable copy を tracker / capture history へ戻さず、tracker は必要時に `live_river_store` から再構築する。`latest_event_type` は最新 event だけを表し、`recent_event_types` は snapshot publish lag により UI が `call` frame を描けない場合でも副露後復元 gate を開くための直近 event context として使う。
`tracker.discards` は guarded append-only map/list であり、通常処理では append / extend と既存 discard metadata 更新だけを許す。`clear` / `pop` / `del` / 短い代入は live `INIT` または明確な別局 `REINIT` の reset context 以外では失敗する。

`INIT` は新局境界として `LiveRiverStore` を reset + seed する。`REINIT` は明確に別局と確認された場合だけ reset + seed できる。非空 `LiveRiverStore` を clear できるのは、実際の `parse_init()` 経路、confirmed different round の `parse_reinit()` 経路、または `INITBYLOG` / `WGC` snapshot が `LiveRiverStore.round_key` と明確に別 game / 別局であると証明できた場合だけである。いずれも `allow_non_empty_clear=True` を明示する。`INITBYLOG` / `WGC` / browser bridge の river は visible projection として扱い、既存 base river がある場合は原則 projection-only とする。`INITBYLOG` / `WGC` は snapshot の `log` / `id` が `LiveRiverStore.round_key[0]` と異なる、または完全な `(kyoku, honba, kyotaku, oya)` tuple が異なる場合だけ `REINIT_DIFFERENT_ROUND_CONFIRMED` として非空 base river を reset + seed できる。`current_round is None` でも `LiveRiverStore` に既存 discard があり snapshot key が同一/不明なら projection-only を優先する。

### Heavy suji / 危険度の表示 fallback

`LiveSujiComputationBundle` は `hand_tiles`、`hand_danger_percentages`、`opponent_suji_panel_summaries`、`player_push_alert_percentages`、`player_alert_indicators_by_seat` を同じ入力からまとめて算出した完了単位である。

- `LiveTableSnapshot.suji_analysis_is_current` は、snapshot に載せた heavy bundle が現在の input signature に対する完了値のときだけ `True` とする。同一局の表示 fallback、fast snapshot、初回 loading は `False` とし、renderer は `False` の値を自動打牌や alert 音声の新規判定へ使わない。
- 最新 input signature の bundle が pending / in-flight の間は、同じ `round_identity` の直前完了 bundle を表示用 fallback として `LiveTableSnapshot` へ載せる。input signature が古いことだけを理由に loading summary や空の危険度配列へ置き換えない。手牌危険度は bundle の `hand_tiles` から現在の手牌へ牌 ID と同牌内の出現順で再対応付けし、対応元がない牌は空 metric とする。
- fallback は current bundle ではなく、最新 job の enqueue / `1 in-flight + pending 1` coalescing を止めない。stale な値は panel、手牌危険度棒、関連 analysis overlay の表示だけに使い、自動打牌や alert 音声の新規判定へ渡さない。
- 同一局に完了 bundle がまだない初回だけ `is_loading=True` と危険度棒なしを許容する。`round_identity` が変わる新局では前局 bundle を持ち越さない。
- bundle 完了時は refresh token の async subtoken を進め、side panel / hand / analysis overlay を async-only partial refresh でまとめて差し替える。base river の `_draw_discards()` と table frame の再描画は行わない。

既存 base river がある場合、`INIT` / `REINIT` 以外の tag は `LiveRiverStore` を reset / shorten してはならない。副露 `N` は `LiveRiverStore` / `RoundState.discards` / `tracker.discards` の count を変えず、既存 discard の `called` / lag metadata と副露エリアだけを更新する。
副露 `N` の count 不変ガードが破れた場合は、`called_discard_disappearance_guard` diagnostic と `logs/live_capture.log` に、原因分類、対象層、席、before/after count、raw tag、round identity、直前/発行 event を残す。副露 `call` event、または `recent_event_types` に `call` が残る redraw / async-only refresh 後だけ、`discard_map` に残る slot の `live_async_discards_<seat>_<index>` image item が Canvas 上に存在するかを検査する。欠けていれば同じ refresh 内では `_draw_discards()` を差分再実行せず、通常 redraw queue へ戻す。defer 時は `UI called discard canvas repair deferred` を `logs/live_capture.log` へ出す。table frame の cache miss は base river / analysis overlay の明示 invalidation 境界とし、opaque な discard zone の背面に既存 slot を残さない。
live `INIT` は復帰判定なしの authoritative full reset であり、既存 base river / tracker / stable discard map / round UI state を前局から引き継がない。DB async persist worker / queue は reset 対象ではなく、同一半荘の `game_id` / 卓種 / player metadata は保持する。
`LiveRiverStore` / `RoundState.discards` / `tracker.discards` のいずれかに既存 discard がある場合、live `INIT` 以外の live session metadata reset は `current_round` / `rounds` / `tracker.discards` / `live_stable_discard_map` を消してはならない。tracker 再構築は `LiveRiverStore` を優先し、短い `RoundState.discards` projection から画面用 river を作り直さない。

live async-only refresh は通常 side panel / hand overlay / alert 表示と analysis overlay だけを更新し、`_draw_discards()` を呼ばず、`live_async_discards` tag と table frame も削除しない。`partial_snapshot.discard_map` は renderer の河描画へ流し込まない。副露 `call` event または recent event context の `call` 後に配列へ残る Canvas image item 欠落を検知した場合は、async-only refresh を中断して通常 redraw へ戻す。

## 2. Alert payload

### `PlayerAlertIndicator`

他家 panel の `ALERT` に出す 1 行。音声判定もこの構造を正本にする。

主な属性:

- `color`: `yellow`, `red`, `purple`, `green` などの意味色
- `label`: UI 表示ラベル
- `key`: 音声重複防止と優先度判定に使う安定キー

音声仕様:

- `create_canvas()` は `alert_sound_enabled` を `False` で初期化する。`アラート音 OFF/ON` ボタンはこの Canvas 状態を切り替え、ON 切替時だけ alert 遷移 latch と独立した上昇2音の確認チャイム、続いて `alert_sound_on.wav` の「サウンド、オン」音声を共有 sound worker で1回鳴らす。OFF 中は self / player panel / meld dora / Bridge・WGC・INITBYLOG の全音声出力を抑止するが、それぞれの alert kind、key、count、source token の latch は更新し、ON 切替直後に表示済み alert を遅延再生しない。設定は永続化せず、次回起動時は再び OFF とする。
- `haya`: 他家の最新打牌が `thinking_time_ms <= 2300ms` かつ 3-7 の数牌の場合に `PlayerAlertIndicator` として出し、`alert_panel_haya.wav` を鳴らす。赤5は 5 として扱い、字牌・1/2/8/9・2300ms 超過は対象外。同じ `haya:*` key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `haya` が残っていても音声は鳴らさない。
- `oso`: 他家の最新打牌が第一打以外で `thinking_time_ms >= 4000ms` かつ 1/2/8/9 の数牌の場合に `PlayerAlertIndicator` として出し、`alert_panel_oso.wav` を鳴らす。字牌・3-7・第一打・4000ms 未満は対象外。同じ `oso:*` key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `oso` が残っていても音声は鳴らさない。
- `早い傾向`: 半荘内3局目以降、他家の1段目3〜6打目で現在局の席別平均思考時間が過去局の1段目平均より早い場合に、`key="first_row_fast_trend:active"` の黄色 `PlayerAlertIndicator` として出し、`alert_panel_fast_trend.wav` を鳴らす。同じ状態の再描画では再生せず、条件外へ戻ったあと再入場した場合は再度鳴らす。過去局平均は `kyoku_master.seat0..3_first_row_avg_thinking_time_ms` と live state の半荘内履歴から作る。
- `Bridge` / `WGC` / `INITBYLOG`: Bridge map 成功で live snapshot refresh token が進んだ場合、または `LiveTableSnapshot.latest_event_type` が `wgc` / `initbylog` の場合、source と live refresh token ごとに一度だけ `alert_huuuro.wav` で「huuuro」を鳴らす。async-only refresh は同じ live token とみなし、同じ source を再鳴動しない。
- panel に出ない alert は鳴らさない。
- 自分側の remain / push は鳴らさない。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。
- player-panel 音声は同一の global discard index 内で音声 asset / kind 単位にも de-dup する。同じ `alert_panel_yellow` / `alert_panel_red` などへ解決される alert key は 1 回だけ queue し、異なる kind は同じ捨て牌でも FIFO 順に queue する。
- `Remain` は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` 音声を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさず、閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- `Push` は局後半の対象打牌にだけ鳴らす。panel の `Push` は 3巡保持するが、音声は保持期間の最初の Push 入場時だけ鳴らし、保持中の再描画や Push key 更新では鳴らさない。

### Alert sound duplicate suppression

- Alert sound jobs use a stable job signature. If the same sound job is already queued, or the worker has handed it to playback and it is still active, the same job is not queued again.
- When the worker takes a job from the FIFO queue, that job is removed from the queued set and tracked as active until playback returns.

### Dora discard alert

- `dora`: When an opponent's latest discard is a dora tile derived from `dora_indicator_tiles`, or a red five, emit a `PlayerAlertIndicator` with a `dora:*` key and play `alert_panel_dora.wav`.
- `dora:*` is a latest-discard action alert like `haya:*` / `oso:*`; if the latest event actor is `Player.JICHA`, the indicator may remain visible but the sound is suppressed.
- This alert does not redraw or mutate the base river layer.

### First-row fast trend alert

- `kyoku_master.csv` has `seat0_first_row_avg_thinking_time_ms` through `seat3_first_row_avg_thinking_time_ms`.
- Each value is the average `thinking_time_ms` over that seat's first river row, defined as the first 6 discards in that round. Missing/unusable values remain blank.
- Live `CaptureState.first_row_thinking_avg_history_by_seat` keeps the current hanchan's completed-round values so the snapshot builder can merge `早い傾向` into `player_alert_indicators_by_seat` without waiting for the suji worker.
- The alert does not mutate the base river layer or discard history.

### Push payload

`Push` は seat ごとの payload として renderer へ渡す。

- `seat`
- `tile`
- `discard_index`
- `percentage`
- `threshold_percent`
- `kind`

panel の `Push` と河の `P` は同じ global discard index を参照する。ただし河の表示には seat-local row gate を適用し、各席の local index 0〜5（1段目）には `P` を描画せず、index 6 以降（2段目以降）だけ描画する。panel 表示、3巡保持、`Push解除` はこの表示 gate の影響を受けない。

## 3. 河描画

### Base river redraw

`src/ui/table_renderer.py` は、full redraw 境界では base river layer を作り直す。

- `live_async_discards` tag を全削除する
- `discard_render_cache_by_key` / `discard_tile_image_refs` を reset する
- 入力 `discard_map` の全捨て牌を描画する
- analysis overlay は別 layer として再描画する

cached-layout redraw では `_draw_discards()` が既存の slot item を再利用できる。表示シグネチャが一致しても、`live_async_discards_<seat>_<local_index>` tag の image item が Canvas 上に存在することを確認してから skip する。item が無い場合は cache hit でもその slot を再描画する。副露 `call` event の redraw / async-only refresh 後には同じ Canvas item 生存確認を明示的に行い、欠けた場合は通常 redraw queue へ戻す。table frame を再作成する場合は item の存在確認だけでは不十分なため、frame 描画前に base river / analysis overlay と描画 cache を削除し、frame 描画後に全 slot を再作成する。

### Canvas state

`src/ui/table_renderer.py` は Canvas に次を保持する。

- `discard_render_cache_by_key`: `(seat, local_index) -> render_signature`。cached-layout redraw の base 牌 skip 判定に使う。full redraw 境界、UI scale 変更、新局 reset では reset する。
- `last_discard_render_stats`: `active`, `drawn`, `skipped`, `changed`, `stale_deleted`
- `discard_base_tile_image_cache`: discard scale が変わる場合の通常牌画像 cache

### 表示シグネチャ

表示シグネチャには、少なくとも次を含める。

- 座席、捨て牌 local index、tile id、draw type
- 位置、anchor、画像サイズ、bounds
- called / lag / riichi / thinking time
- tint kind、thinking time band step
- marker 有無、lag marker kind、1段目抑制を反映した Push marker 有無
- border kind

base river layer は、シグネチャ一致と Canvas item 生存確認の両方が成立する場合だけ牌描画を skip できる。click spec と lag marker reference spec は毎 redraw で復元する。

### Canvas tags

discard item は作成時に次の tag を持つ。

- `live_async_discards`
- `live_async_discards_<seat>_<local_index>`

full redraw は `live_async_discards` 全体を削除する。cached-layout redraw は通常、必要な slot tag だけを差し替える。ただし table frame の cache miss では `live_frame` の不透明な discard zone が既存河を覆うため、`live_async_discards` と `live_discard_analysis_overlay` を削除して各描画 cache を reset し、frame の後に河を全描画する。async-only refresh は base river tag を削除せず、通常は `live_discard_analysis_overlay` だけを差し替える。副露 `call` event 後に配列へ残る Canvas image item 欠落を検知した場合は async-only refresh を中断し、通常 redraw queue へ戻す。

## 4. 牌画像と overlay

`_discard_tile_image()` は通常牌画像だけを返す。色付き `PhotoImage` の合成は discard path では行わない。

Canvas overlay:

- red: remain / push 系の危険寄り tint
- brown: 4見えで物理否定された 3連形に属する手出し牌
- four_visible: 牌自身が 4見え
- thinking time band: post-reach / pre-reach の思考時間帯

overlay は seat 回転後の画像 bounds へ矩形として重ねる。

## 5. NAGA 段位ポイント分析

### `NagaAutoPanelData`

renderer へ渡す下部自動表示用 DTO。

- `visible`
- `title_text`
- `lines`
- `status_kind`: `waiting`, `loading`, `ready`, `error`

南2局以降、`src/app/main.py` が `naga-ptev-analyzer` の結果から次を抽出する。

- 現状 ptEV
- 主要な和了候補
- 主要な放銃候補
- 流局候補の best / worst

## 6. Nodocchi STATUS

`src/app/nodocchi_stats.py` が Nodocchi API の取得と整形を担当し、renderer は detail view として表示する。

表示色:

- 和了率: 赤字
- 副露率: 赤字
- リーチ率: 赤字
- その他: 白字

取得は background thread で行い、同一プレイヤーの連打は cache / in-flight set で抑止する。

## 7. DB分析

### `scripts/analyze_player_shanten_thinking.py`

入力:

- `csv_db/discard_fact_*.csv`
- `csv_db/hanchan_master.csv`

主な出力:

- `player_shanten_thinking_summary.csv`
- `player_shanten_thinking_report.html`
- プレイヤー別 scatter / median line の PNG

所属卓:

- `hanchan_master` の `seat0..3_player_name` と `room_class_label` を melt して集計する。
- 同一 `hanchan_id` はプレイヤーごとに重複除去する。
- `hanchan_master` に該当がない場合だけ discard row 側の `room_class_label` を fallback 表示する。

## 8. CSV DB

現行保存の卓種正本は `room_class_label`。legacy の `go_type`, `go_type_hex`, `room_class_code` は読み取り補完対象であり、新規分析では `room_class_label` を優先する。

## 9. 同期対象

この仕様を変えたら、最低限次を同時に更新する。

- [../requirements/current.md](../requirements/current.md)
- [../screen_specs/current.md](../screen_specs/current.md)
- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../screen_specs/alerts_and_panels.md](../screen_specs/alerts_and_panels.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- [../analysis/player_shanten_thinking.md](../analysis/player_shanten_thinking.md)
- [../changelog.md](../changelog.md)
