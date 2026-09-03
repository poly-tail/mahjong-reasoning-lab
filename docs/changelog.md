# 変更履歴

## 記録ルール

今後のエントリでは、既存形式を維持しつつ必要に応じて `変更対象`、`変更概要`、`変更理由`、`維持すべき既存ニュアンス`、`意図的に変更した挙動`、`変更していない主要挙動`、`回帰テスト`、`性能への影響`、`関連ADR` を含める。過去エントリは一括で書き換えない。

## 2026-09-03 現行版 checkpoint の文書・配布安全性同期
- CH-240: CH-238 / CH-239 の実装に対し、requirements / API spec / screen spec と関連する architecture / operations / 麻雀ロジック文書の参照・DTO・音声契約を最終同期した。source checkpoint には runtime CSV DB、player profile、分析 report を含めず、`.pytest_tmp*/` と `.7z` archive を ignore / source package 除外へ追加して、旧 `template_workspace.7z` を削除した。河診断ログの2テストは一時ログ先を明示し、製品ロジックを変えずに全テストを通るようfixtureを補完した。回帰テストは `tests/test_package_workspace.py` と `tests/test_discard_borders.py`。既存の live capture、筋・危険度計算式、表示閾値は変更していない。

## 2026-09-03 heavy suji / 危険度計算中の直前表示保持
- CH-239: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_snapshot_cache.py`, `tests/test_hand_auto_mode.py` と requirements / API spec / screen spec の current・v2.2 正本、`alerts_and_panels.md`, `invariants.md`, `performance_hotspots.md`, `live_rendering.md`, `regression_checklist.md`, `data_structures.md`, `project_guide.md` を更新した。変更前は同一局でも heavy suji / 危険度の input signature が変わると直前の完了済み bundle を表示 fallback に使わず、計算完了まで他家 side panel を loading 表示、自家手牌の危険度棒を空表示へ戻していた。変更後は同じ `round_identity` の直前完了 bundle を panel / hand danger / 関連 analysis overlay の表示専用 fallback として保持し、手牌 danger は bundle の旧 `hand_tiles` から現在手牌へ牌 ID と同牌内の出現順で再対応付けし、最新 job の enqueue と `1 in-flight + pending 1` coalescing は継続する。完了済み bundle がない初回だけ loading / 危険度棒なしを許容し、新局へ前局 bundle は持ち越さない。新 bundle 完了前に async-only token を fast snapshot として先行公開せず、完了した heavy snapshot が既存 fast snapshot を置き換えてから、side panel / hand / analysis overlay だけを partial refresh する。保持中の stale 値は自動打牌や alert 音声の新規判定へ使わず、base river / table frame、danger / Push / Remain の計算式と閾値、河 `P` の1段目非表示は変更していない。回帰テストは `test_async_live_table_snapshot_provider_defers_async_only_token_until_heavy_publish`, `test_fast_live_table_snapshot_remaps_previous_hand_danger_for_same_round`, `test_fast_live_table_snapshot_does_not_reuse_analysis_across_rounds`, `test_request_live_suji_bundle_reuses_previous_same_round_bundle_as_fallback`, `test_request_live_suji_bundle_does_not_reuse_previous_bundle_across_rounds`, `test_build_live_table_snapshot_keeps_previous_bundle_after_lag_metadata_changes`, `test_build_live_table_snapshot_remaps_fallback_danger_to_current_hand`, `test_betaori_auto_waits_for_current_hand_danger_bundle`。中間 loading / 空表示による tagged region の削除・再描画を避けるだけで heavy 計算量と責務境界は増やさず、ADR 更新は不要。

## 2026-09-03 河Push Pマークの1段目非表示
- CH-238: `src/ui/table_renderer.py`, `tests/test_discard_borders.py` と requirements / API spec / screen spec の current・v2.2 正本、関連ガイド・トラブルシュートを更新した。変更前は global discard index が Push marker 対象なら、各席の河の1段目にも `P` を描画していた。変更後は seat-local index 0〜5（1段目）を表示対象外とし、index 6 以降（2段目以降）だけ `P` を描画する。overlay signature もこの表示 gate 適用後の marker 有無を使うため、非表示の1段目 Push だけでは overlay を不要に再作成せず、global index が local index と異なる2段目以降の marker 追加も検出する。Push 判定、global discard index の照合、panel 表示、3巡保持、`Push解除` は変更していない。Push 音声は従来から2段目以降だけが対象であり、対象 row では音声と `P` の同一 redraw 反映を維持する。回帰テストは `tests/test_discard_borders.py::DiscardBorderKindTest::test_push_discard_marker_starts_from_second_river_row`, `tests/test_discard_borders.py::DiscardBorderKindTest::test_push_discard_marker_applies_local_row_gate_before_global_index_match`, `tests/test_discard_borders.py::DiscardBorderKindTest::test_discard_overlay_signature_uses_visible_push_marker_state` と既存の `tests/test_player_panel_alerts.py::PlayerPanelAlertTest::test_player_panel_push_sound_waits_until_second_river_row`。描画 hot path への追加は整数比較1回で、ADR 更新は不要。

## 2026-08-18 アラート音 ON 確認チャイム・言語音声
- CH-237: `src/ui/table_renderer.py`, `assets/audio/alert_sound_on.wav`, `assets/audio/alert_sound_preview.html`, `tests/test_alert_sound_toggle.py` と requirements / API spec / screen spec の current・v2.2 正本を更新し、`アラート音 OFF` から `ON` へ切り替えた瞬間に音量確認用の上昇2音チャイムと「サウンド、オン」の言語音声を1回鳴らすようにした。Windows では既存の共有 alert-sound worker から `988Hz / 80ms`、`1319Hz / 120ms` を順番に再生し、その後 `alert_sound_on.wav` を同期再生する。`winsound` 非対応環境では Canvas bell へフォールバックする。OFF 切替時は鳴らさず、確認音声は self / player panel / meld dora / Bridge 系の alert transition latch、FIFO、表示判定を変更しない。描画 hot path と責務境界は変わらず、ADR 更新は不要。

## 2026-08-18 本番画面のアラート音ボタン座標衝突修正
- CH-236: `src/ui/table_renderer.py`, `tests/test_alert_sound_toggle.py`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/controls_and_bridge.md` を更新した。変更前は `アラート音 OFF/ON` と、本番起動後に `src/app/main.py` が遅延生成する `NAGA段位` が同じ `(82, 64)` を使い、後者が前者を覆っていた。変更後はアラート音ボタンを画面左上の専用段 `(8, 92)` へ移し、生成時に前面へ上げる。音声の初期値 OFF、セッション内切替、全音声経路の gate、OFF 中の遷移 latch 更新は変更していない。回帰テストでは左上座標と NAGA 座標が異なることを固定する。描画 hot path と責務境界は変わらず、ADR 更新は不要。

## 2026-08-08 アラート音 ON/OFF ボタン
- CH-235: `src/ui/table_renderer.py`, `tests/test_alert_sound_toggle.py` と requirements / API spec / screen spec の current・v2.2 正本を更新し、上部操作列へ `アラート音 OFF/ON` ボタンを追加した。変更前は起動直後から既存条件どおり alert 音声が再生され、画面から一括停止できなかった。変更後は実 Canvas の音声設定を毎回 OFF で初期化し、ON の間だけ self、他家 panel、副露ドラ、Bridge / WGC / INITBYLOG の全 alert 音声を再生する。OFF 中も alert kind / key / count / source token の latch を更新するため、ON 切替時に表示済み alert は遅延再生しない。既存の alert 表示、判定閾値、音声優先度、FIFO queue、重複抑止、音声 asset は変更していない。設定は永続化せず次回起動時は再び OFF。回帰テストは `tests/test_alert_sound_toggle.py`, `tests/test_self_hand_alert.py`, `tests/test_player_panel_alerts.py`。描画 hot path への追加処理は bool 参照のみで、ADR 更新は不要。

## 2026-07-26 合わせ打ち履歴判定・「合」表示
- CH-234: `src/ui/table_renderer.py`, `tests/test_discard_borders.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/architecture/visible_count_pipeline.md`, `docs/mahjong/reference/hand_analysis_terms.md`, `docs/mahjong/logic/mahjong_danger.md`, `docs/changelog.md` を更新し、`LiveRiverStore` 由来の全席捨て牌履歴から合わせ打ちを再検知するようにした。変更前は打牌・副露公開・ドラ表示によるvisible increaseをseatの次打牌だけでone-shot照合していた。変更後は他家の手出しだけを起点に、その後5回以内のglobal discard増加で同じ34種牌が切られたtarget slotへ表示用フラグを付ける。途中の別打牌をまたいでも窓内なら有効で、起点側のツモ切り、副露、ドラ表示は起点にせず、副露・ドラ表示は窓も消費しない。targetは手出し/ツモ切りを問わない。既存のappend cacheと `awaseuchi confirm` background workerを維持し、黄丸を牌画像上の黄色い `合` へ変更した。base river、actual/inferred visible、DB schema、capture履歴は変更していない。回帰テストは `tests/test_discard_borders.py`, `tests/test_live_snapshot_cache.py`, `tests/test_hand_auto_mode.py`, `tests/test_render_analysis_split_contract.py`, `tests/test_discard_render_capture_separation.py`。


## 2026-07-26 cached table-frame river z-order invalidation
- CH-233: `src/ui/table_renderer.py`, `tests/test_render_layer_split_regression.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、副露後に手動 REINIT で河が戻る原因を Canvas stacking order まで追跡した。cached-layout redraw で meld 変更により table frame を再作成すると、不透明な discard zone rectangle が既存 base river item より後に生成されて河を覆う一方、`_draw_discards()` は既存 item の tag と表示 signature が残るため cache hit として skip していた。REINIT は render cache を空にして全 slot を frame より後に作り直すため症状だけを解消していた。修正後は table frame cache miss を base river / analysis overlay の invalidation 境界とし、frame 再作成前に両 layer と discard cache / image refs / overlay signature / geometry を破棄し、同じ redraw 内で frame -> base river -> analysis overlay の順に再作成する。副露後の自動 REINIT 応急処置は撤去した。Capture 履歴、`LiveRiverStore`、`called=True` 黄色枠、frame cache hit 時の per-slot 再利用、async-only refresh が base river を直接描かない挙動は変更していない。回帰テストは `tests/test_render_layer_split_regression.py::test_table_frame_redraw_invalidates_cached_discard_layers`, `tests/test_render_layer_split_regression.py::test_cached_layout_frame_redraw_invalidates_discards_before_repaint`。

## 2026-07-21 async repair defer and overlay signature cache
- CH-232: `src/ui/table_renderer.py`, `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、async-only refresh 中に副露後 Canvas item 欠けを見つけてもその場で `_draw_discards()` を差分再実行せず、`False` を返して通常 redraw queue へ戻すようにした。通常 redraw 末尾の副露修復保険も即時 `_draw_discards()` 再実行をやめ、欠け検知を診断したうえで redraw queue へ coalesce する。Tkinter Canvas の別スレッド描画は行わず、base river 修復は既存のメインスレッド redraw 経路へ合流させる。あわせて `live_discard_analysis_overlay` に signature cache を追加し、red / brown / four-visible tint、見え枚数 marker、Push `P`、同順合わせ打ち marker が変わらない redraw では overlay tag を削除・再描画しない。河の base / analysis overlay 分離、`called=True` 黄色枠、capture 履歴へ書き戻さない挙動は変更していない。回帰テストは `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`。
## 2026-07-21 cached river liveness lookup
- CH-231: `src/ui/table_renderer.py`, `src/app/main.py`, `tests/test_discard_borders.py`, `docs/analysis/performance_hotspots.md`, `docs/changelog.md` を更新し、cached-layout redraw の base river item 生存確認を slot ごとの `find_withtag` 連打から、`live_async_discards` parent tag の1回走査で作る image item tag set 参照へ変更した。あわせて副露 `call` recent context の保持件数を 64 件から 8 件へ短縮し、補修 gate が局面後半まで残り続けないようにした。河の base / analysis overlay 分離、`called=True` 黄色枠、副露直後だけ欠け slot を復元する挙動、capture 履歴へ書き戻さない挙動は変更していない。回帰テストは `tests/test_discard_borders.py`。

## 2026-07-19 called discard delayed frame repair gate
- CH-230: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、snapshot publish lag により UI が副露 `call` frame を描けず、次の `discard` frame として処理した場合でも副露後復元 gate が閉じないようにした。`LiveTableSnapshot.latest_event_type` は最新 event のまま維持し、新設の `recent_event_types` に `call` が残る間だけ `UI called discard short input` / `UI called discard stale delete` / `UI called discard canvas repair` の副露 context として扱う。capture 履歴、`LiveRiverStore`、`RoundState.discards`、`tracker.discards` の count 不変条件、async-only refresh が通常 base river を描かない挙動は変更していない。回帰テストは `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`。

## 2026-07-19 live stable discard restore lock contention
- CH-229: `src/app/main.py`, `tests/test_live_snapshot_cache.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、capture state lock が副露処理などで busy の瞬間に cached `LiveTableSnapshot` へ逃げても、`CaptureState.live_stable_discard_map` の表示用 copy を optimistic read して短い `discard_map` を補強するようにした。stable copy は引き続き `LiveRiverStore` 由来の表示用 fallback であり、capture 履歴、`LiveRiverStore`、`RoundState.discards`、`tracker.discards` へは書き戻さない。回帰テストは `tests/test_live_snapshot_cache.py`。

## 2026-07-18 called discard canvas repair
- CH-228: `src/ui/table_renderer.py`, `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、副露 `call` event の redraw / async-only refresh 後だけ Canvas base river item の欠落を検知して復元するようにした。`discard_map` には slot が残っているのに `live_async_discards_<seat>_<index>` tag の image item が Canvas 上に無い場合、`_draw_discards()` を差分再実行して欠けた slot を復元する。欠けが無い通常 redraw では何もしない。async-only refresh は引き続き base river tag を削除しないが、副露直後の欠落検知時だけ復元経路を許可する。復元時は `UI called discard canvas repair` を `logs/live_capture.log` へ出す。回帰テストは `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`。

## 2026-07-18 live stable discard snapshot restore
- CH-227: `src/app/main.py`, `tests/test_live_snapshot_cache.py`, `tests/test_render_analysis_split_contract.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、cached `LiveTableSnapshot` が古い/短い `discard_map` を返す経路でも、最後に `LiveRiverStore` 由来で発行できた `CaptureState.live_stable_discard_map` から同一 `LiveRiverStore.epoch` 内の表示用 `discard_map` を補強するようにした。stable map は capture 履歴へ書き戻さず、同一局内では短い snapshot で上書きされない。副露 `N` による `LiveRiverStore` / `RoundState.discards` / `tracker.discards` の count 不変、renderer の Canvas item 生存確認、async-only refresh が base river を描かない挙動は変更していない。復元時は `Live snapshot stable discard restore` を `logs/live_capture.log` へ出す。回帰テストは `tests/test_live_snapshot_cache.py`, `tests/test_render_analysis_split_contract.py`。

## 2026-07-16 discard base layer cache validation
- CH-226: `src/ui/table_renderer.py`, `tests/test_discard_base_layer_full_redraw_contract.py`, `tests/test_discard_borders.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/screen_specs/display_overview.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/changelog.md` を更新し、cached-layout redraw で base river layer を毎回全削除・全描画しないようにした。full redraw 境界では従来どおり `live_async_discards` tag と discard render cache を reset するが、cached-layout redraw では slot 単位の表示 signature と Canvas item tag の image item 生存確認が両方成立した場合だけ base 牌を skip する。Canvas item が消えている slot は cache hit でも再描画するため、副露後に Canvas item だけが消えて戻らない経路は閉じたままにする。副露時の `LiveRiverStore` / `RoundState.discards` / `tracker.discards` の count 不変、短い projection を `_merge_discard_map_with_round_cache()` で `called=True` 表示保持する挙動、analysis overlay の async-only refresh 分離は変更していない。回帰テストは `tests/test_discard_base_layer_full_redraw_contract.py`, `tests/test_discard_borders.py`。

## 2026-07-15 per-discard sound kind gate
- CH-225: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/changelog.md` を更新し、player-panel 音声を同一 global discard index 内で音声 asset / kind 単位に de-dup するようにした。`alert_panel_yellow` / `alert_panel_red` など同じ音声へ解決される alert key は同じ捨て牌内で 1 回だけ queue し、異なる音声 kind は引き続き同じ捨て牌でも FIFO へ積む。既存の exact job pending / active 重複抑制、Remain の白→黄 gate、Push の保持 window、自家打牌時の action alert 抑制は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-15 Remain sound gate state preservation
- CH-224: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/changelog.md` を更新し、同一局扱いの round identity / wrapper 変化で `_reset_round_ui_state()` が呼ばれても、player-panel 音声 gate の状態を保持するようにした。Remain 音声は引き続き no-temp remain が白/通常状態から黄色閾値へ入った最初のタイミングだけ鳴らし、閾値内の再描画や同一局 UI reset では再鳴動しない。新局 reset、Push/haya/oso/dora/huuuro 音声 gate、Remain alert の表示色は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-14 discard base layer full redraw
- CH-223: `src/ui/table_renderer.py`, `tests/test_discard_base_layer_full_redraw_contract.py`, `tests/test_discard_borders.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/screen_specs/display_overview.md`, `docs/screen_specs/README.md`, `docs/analysis/performance_hotspots.md`, `docs/changelog.md` を更新し、捨て牌本体の Canvas base river layer を `_draw_discards()` 呼び出しごとに `live_async_discards` 全削除、`discard_render_cache_by_key` / `discard_tile_image_refs` reset、入力 `discard_map` の全描画へ切り替えた。副露後に `LiveRiverStore` が短くなっていないのに Canvas item だけが消え、signature cache により再描画が skip される経路を閉じるための変更で、analysis overlay は引き続き別 layer として再描画する。async-only refresh は `_draw_discards()` を呼ばず、`live_async_discards` tag も削除しない。parser、`LiveRiverStore`、`RoundState.discards`、`tracker.discards` の副露 `N` 処理は変更していない。回帰テストは `tests/test_discard_base_layer_full_redraw_contract.py`, `tests/test_discard_borders.py`, `tests/test_live_river_store.py`, `tests/test_live_river_store_authoritative_boundaries.py`, `tests/test_spectator_live_river_key_gate_regression.py`。

## 2026-07-10 remain white-to-yellow sound gate
- CH-222: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/changelog.md` を更新し、Remain 系音声を no-temp remain が白/通常状態から黄色閾値へ入った時だけ鳴らすようにした。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化、白/通常状態から赤/紫へ直接入る変化では鳴らさない。Remain alert の表示色、`SUMMARY` と `ALERT` の no-temp remain 閾値、Push/haya/oso/dora/huuuro 音声 gate、共有 alert sound worker は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-10 Bridge/WGC/INITBYLOG huuuro alert
- CH-221: `src/ui/table_renderer.py`, `assets/audio/alert_huuuro.wav`, `assets/audio/alert_sound_preview.html`, `tests/test_player_panel_alerts.py`, `tests/test_bridge_shortcuts.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/changelog.md` を更新し、Bridge map 成功、`WGC`、`INITBYLOG` のいずれかで `alert_huuuro.wav` による「huuuro」音声を鳴らすようにした。`WGC` / `INITBYLOG` は `LiveTableSnapshot.latest_event_type`、Bridge は map 成功後に `table_snapshot_reinit_action` が返した live refresh token を source として扱い、同じ source / live refresh token の redraw や async-only refresh では再鳴動しない。共有 alert sound worker、FIFO、同一 job pending / active 重複抑制、player-panel alert 音声 gate、河描画は変更していない。回帰テストは `tests/test_player_panel_alerts.py` と `tests/test_bridge_shortcuts.py`。

## 2026-07-10 called discard disappearance diagnostics
- CH-220: `src/capture/fragment_parser.py`, `src/ui/table_renderer.py`, `tests/test_live_river_store.py`, `tests/test_discard_borders.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/screen_specs/river_display.md`, `docs/operations/troubleshooting/live_capture.md`, `docs/analysis/performance_hotspots.md`, `docs/changelog.md` を更新し、副露 `N` 直後に `LiveRiverStore` / `RoundState.discards` / `tracker.discards` の count 不変ガードが破れた場合、`called_discard_disappearance_guard` diagnostic と `logs/live_capture.log` に、原因分類、対象層、席、before/after count、raw tag、round identity、直前/発行 event を残すようにした。renderer 側でも最新 event が `call` のときに短い `discard_map` を受けて base river slot を保持した場合は `UI called discard short input`、Canvas slot を削除した場合は `UI called discard stale delete` を live log へ出す。副露時の捨て牌保持、`called=True` / lag metadata 更新、base river reset 境界、DB schema は変更していない。回帰テストは `tests/test_live_river_store.py` と `tests/test_discard_borders.py`。

## 2026-07-08 first-row fast trend alert
- CH-219: `src/capture/state.py`, `src/capture/csv_db_schema.py`, `src/capture/storage.py`, `src/app/main.py`, `src/ui/table_renderer.py`, `assets/audio/alert_panel_fast_trend.wav`, `assets/audio/alert_sound_preview.html`, `tests/test_live_capture_agari_storage.py`, `tests/test_live_snapshot_cache.py`, `tests/test_player_panel_alerts.py`, `docs/reference/csv_db_design.md`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/changelog.md` を更新し、半荘内3局目以降の他家1段目3〜6打目で現在局平均思考時間が過去局平均より早い場合に、黄色の `早い傾向` panel alert と `alert_panel_fast_trend.wav` 音声を出すようにした。`kyoku_master` には `seat0..3_first_row_avg_thinking_time_ms` を追加し、各局・各席の1段目平均思考時間を保存する。音声は同じ状態の再描画では鳴らさず、条件外へ戻ったあと再入場した場合だけ再度鳴らす。河本体、Push/Remain/haya/oso/dora の既存音声 gate、base river reset 境界は変更していない。回帰テストは `tests/test_live_capture_agari_storage.py`, `tests/test_live_snapshot_cache.py`, `tests/test_player_panel_alerts.py`。

## 2026-07-08 INITBYLOG spectator voice alert
- CH-218: `src/app/main.py`, `src/ui/table_renderer.py`, `assets/audio/alert_spectator_mode.wav`, `assets/audio/alert_sound_preview.html`, `tests/test_live_snapshot_cache.py`, `tests/test_player_panel_alerts.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/changelog.md` を更新し、`INITBYLOG` 受信時に `alert_spectator_mode.wav` で「観戦モード」を鳴らすようにした。`LiveTableSnapshot.latest_event_type` は最新 raw event type だけを renderer へ渡し、`RoundState.snapshot_event_type` のような持続 snapshot label は音声判定に使わない。音声は live refresh token ごとに一度だけ鳴らし、async-only refresh や同じ token の再描画では再鳴動しない。WGC / REINIT / river reset / projection-only の既存挙動は変更していない。回帰テストは `tests/test_live_snapshot_cache.py` と `tests/test_player_panel_alerts.py`。

## 2026-07-07 spectator live river key gate
- CH-217: `src/capture/fragment_parser.py`, `tests/test_spectator_live_river_key_gate_regression.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/analysis/performance_hotspots.md`, `docs/changelog.md` を更新し、spectator `INITBYLOG` / `WGC` の snapshot key gate を調整した。非空 `LiveRiverStore` がある場合でも、snapshot の `log` / `id` が `LiveRiverStore.round_key[0]` と異なる、または完全な `(kyoku, honba, kyotaku, oya)` tuple が異なる場合は confirmed different round として `REINIT_DIFFERENT_ROUND_CONFIRMED` + `allow_non_empty_clear=True` で reset + seed する。同一/不明 key の `INITBYLOG` / `WGC`、browser / Bridge projection、packet-first / live resync は引き続き projection-only または append-only とし、base river を短縮しない。副露 `N` の metadata-only 更新、renderer / snapshot builder が `LiveRiverStore` 由来の base river を描画する責務、DB schema は変更していない。回帰テストは `tests/test_spectator_live_river_key_gate_regression.py`。

## 2026-07-07 player alert sound transition gate
- CH-216: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/changelog.md` を更新し、Push 音声に per-seat の global-discard window を追加した。Push alert row が一瞬空になったり `push:<discard_index>` が保持中に更新された場合でも、最初に鳴らした Push の `discard_index + PLAYER_PUSH_ALERT_PERSIST_DISCARD_WINDOW` までは同じ席の Push を再鳴動しない。自家打牌タイミングで Push 音声をミュートした場合も同じ window を消費し、保持期間中の後追い再生を防ぐ。Remain の閾値入退場、FIFO queue、同一 job pending / active 重複抑制、自家打牌時の音声抑制、河 `P` marker 表示は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。
- CH-215: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md` を更新し、player-panel alert 音声の transition gate を明確化した。`Push` は panel 上で 3巡保持されても、Push family が有効になった最初のタイミングだけ鳴らし、保持中の再描画や `push:<discard_index>` 更新では再鳴動しない。`Remain` は no-temp remain が黄色・赤・紫の各閾値へ入ったタイミングだけ鳴らし、同じ閾値内の再描画では鳴らさない。閾値外または弱い閾値へ戻ったあと再び同じ閾値へ入った場合は再度鳴らす。FIFO queue、同一 job pending / active 重複抑制、自家打牌時の Push / haya / oso / dora 音声抑制、河 `P` marker 表示は維持した。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-06 live river strict reset gate
- CH-214: `src/capture/live_river_store.py`, `src/capture/state.py`, `src/capture/fragment_parser.py`, `src/app/main.py`, `tests/test_live_river_non_authoritative_reset_guard.py`, `tests/test_live_river_store.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/analysis/performance_hotspots.md`, `docs/screen_specs/river_display.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、非空 `LiveRiverStore` の clear を authority 名だけでは許さず、`allow_non_empty_clear=True` の明示 opt-in に限定した。opt-in を付けるのは実際の `parse_init()` と confirmed different round の `parse_reinit()` だけで、bridge / WGC / INITBYLOG / packet-first / live resync は `INIT_NEW_ROUND` 名義でも非空 base river を消せない。`_reset_live_hanchan_state()` は reset 拒否時も処理を継続し、`blocked_live_river_reset` diagnostic を残す挙動を維持した。回帰テストは `tests/test_live_river_non_authoritative_reset_guard.py` と `tests/test_live_river_store.py`。

## 2026-07-06 alert sound duplicate suppression
- CH-213: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md` を更新し、alert sound queue に同一 job signature の pending / playing 管理を追加した。同じ alert key の音声 job がすでに queue 内にある、または worker が再生処理へ渡している間は再投入しない。worker が job を取り出した時点で pending から外し、再生完了までは active として重複を抑制する。FIFO queue で重なった別 alert を順番再生する挙動、自家打牌時の `haya` / `oso` / `dora` 音声抑制、同じ `PlayerAlertIndicator.key` の再描画抑制は維持した。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-05 alert sound FIFO queue
- CH-212: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md` を更新し、複数の音声 alert が同じタイミングで発生した場合に上限付き queue から古い音を捨てず、共有 alert-sound worker の FIFO queue へ順番に積むようにした。WAV asset の `winsound.PlaySound` は worker 上で同期再生し、後続音が前の音を中断しない。Player panel では同時に複数の新規 alert 候補がある場合、高優先度順にすべて queue する。同じ alert key の再描画抑制、自家打牌時の `haya` / `oso` / `dora` 音声抑制、UI thread で再生しない方針は維持した。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-05 dora discard voice alert
- CH-211: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `assets/audio/alert_panel_dora.wav`, `assets/audio/alert_sound_preview.html`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md` を更新し、他家の最新打牌がドラ表示牌由来のドラ、または赤5の場合に `dora` player-panel alert と `alert_panel_dora.wav` 音声を出すようにした。`dora:*` は `haya` / `oso` と同じ latest-discard action alert として扱い、最新 event が自家打牌の場合は表示上残っていても音声を鳴らさない。河本体、base river layer、副露時の捨て牌保持ロジックは変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-05 自家打牌時の timed alert 音声抑制
- CH-210: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/requirements/current.md`, `docs/requirements/requirements_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md` を更新し、最新 event が自家打牌の場合は `haya` / `oso` の player-panel 音声を鳴らさないようにした。表示用 `PlayerAlertIndicator` は従来どおり panel に残せるが、音声 gate で `latest_discard_actor_seat == JICHA` の更新を stale opponent action として扱う。自家打牌以外での `haya` / `oso` 条件、Push の既存自家打牌音声抑制、河描画と base river 層は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-04 guarded tracker discard history
- CH-209: `src/sutehai.py`, `src/capture/state.py`, `src/capture/fragment_parser.py`, `src/app/main.py`, `tests/test_live_river_store.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_live_snapshot_cache.py`, `tests/test_bridge_table_snapshot_import.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、`tracker.discards` を通常の `dict[Player, list]` から guarded append-only map/list へ変更した。通常処理では append / extend と既存 discard metadata 更新だけを許し、`clear` / `pop` / `del` / 短い代入は `INIT` (`init_new_round`) または明確な別局 `REINIT` (`reinit_different_round`) の reset context 以外では例外にする。`_rebuild_tracker_from_round()` と `_rebuild_tracker_from_live_river_store()` は tracker を一度空にせず、既存 slot 更新と tail append だけで同期する。`reset_live_session()` は `LiveRiverStore` だけでなく `RoundState.discards` / `tracker.discards` も見て、既存 discard があれば live `INIT` 以外では round/tracker/stable river を消さない。Bridge browser snapshot も既存 discard が `RoundState` または tracker に残っていれば bootstrap せず projection-only とする。副露 `N` は引き続き既存 discard の `called` / lag metadata と副露エリアだけを更新する。

## 2026-07-04 authoritative INIT full reset
- CH-208: `src/capture/state.py`, `src/capture/fragment_parser.py`, `tests/test_live_river_store.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、live `INIT` は復帰判定なしの authoritative full reset として扱うようにした。`LiveRiverStore` に既存 discard があっても、`parse_init()` は round/table live state を強制 reset し、`current_round` / `rounds` / `tracker.discards` / `live_stable_discard_map` / base river を前局から引き継がない。DB 書き込みは既存の async persist worker / queue に分離されたまま触らず、`game_id` / 卓種 / player metadata は同一半荘の DB 行と source_url を壊さないため保持する。副露 `N` と同一局・別局不明 `REINIT` / WGC / INITBYLOG projection は引き続き捨て牌を削除・短縮しない。回帰テストは `tests/test_live_river_store.py`。

## 2026-07-04 live river derived-view reset guard
- CH-207: `src/capture/state.py`, `src/capture/fragment_parser.py`, `tests/test_live_river_store.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、`LiveRiverStore` に既存 discard がある場合は `reset_live_session()` が `current_round` / `rounds` / `tracker.discards` / `live_stable_discard_map` を消さないようにした。あわせて `_rebuild_tracker_from_round()` は非空 `LiveRiverStore` がある場合に必ず store から tracker を再構築し、短い `RoundState.discards` projection で画面用 discard view を短縮しない。副露 `N` では引き続き捨て牌 count を変えず、既存 discard の `called` / lag metadata と副露エリアだけを更新する。LiveRiverStore の destructive reset 境界は `INIT_NEW_ROUND` と明確な別局 `REINIT_DIFFERENT_ROUND_CONFIRMED` のまま。回帰テストは `tests/test_live_river_store.py`。

## 2026-07-04 base river render backup 復元
- CH-206: `src/ui/table_renderer.py`, `tests/test_live_river_renderer_epoch_barrier.py`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/analysis/performance_hotspots.md` を更新し、通常の `round_discard_map_cache` が round UI state reset で空になっても、最後に描けた base river を `base_river_render_backup_map` として `LiveRiverStore.epoch` 境界まで保持するようにした。`round_identity=None` や短い/空 projection が来た場合はこの backup から display-only で欠落 slot を復元し、復元した slot は `called=True` 表示にする。epoch が変わった場合は INIT / 明確な別局 REINIT の authoritative reset とみなし、前局 backup は使わない。CaptureState / LiveRiverStore / tracker の正史、analysis overlay、async-only refresh の責務は変更していない。回帰テストは `tests/test_live_river_renderer_epoch_barrier.py`。

## 2026-07-03 LiveRiverStore manual reset hard barrier
- CH-205: `src/capture/live_river_store.py`, `src/capture/fragment_parser.py`, `tests/test_live_river_store.py`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、既存 base river が非空の場合は `MANUAL_USER_RESET` authority でも `LiveRiverStore` を reset できないようにした。`UN` / `TAIKYOKU` 由来の `_reset_live_hanchan_state()` は river reset がブロックされた場合でも live session metadata の再初期化を継続し、診断に `blocked_live_river_reset` を残す。`INIT_NEW_ROUND` と明確な別局 `REINIT_DIFFERENT_ROUND_CONFIRMED` は引き続き既存 river を消せる唯一の authoritative boundary とする。副露 `N` の処理本体、base river 描画、analysis overlay、音声 alert は変更していない。回帰テストは `tests/test_live_river_store.py`。

## 2026-07-03 副露時の捨て牌不変 hard guard
- CH-204: `src/capture/fragment_parser.py`, `src/app/main.py`, `tests/test_live_river_store.py`, `tests/test_live_river_store_authoritative_boundaries.py`, `tests/test_live_reinit_bootstrap.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md` を更新し、既存 base river がある場合は `INIT` / `REINIT` 以外の tag で `LiveRiverStore` epoch reset や捨て牌 count 短縮を禁止した。副露 `N` では `LiveRiverStore` / `RoundState.discards` / `tracker.discards` の count 変更を禁止し、許す変更を既存 discard の `called` / lag metadata と副露エリア更新だけにした。WGC / INITBYLOG / Browser Bridge / INIT なし packet-first は既存 river がある限り reset + seed せず projection-only または append-only として扱う。河本体の描画責務、analysis overlay、音声 alert は変更していない。

## 2026-07-03 oso 遅切り音声アラート
- CH-203: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `assets/audio/alert_panel_oso.wav`, `assets/audio/alert_sound_preview.html`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md` を更新し、他家の最新打牌が第一打以外で `thinking_time_ms >= 4000ms` かつ 1/2/8/9 の数牌の場合に `oso` panel alert / 音声を出すようにした。字牌・3-7・第一打・4000ms 未満は対象外。既存の transition-driven alert sound gate と worker queue を使うため、同じ alert key の再描画では再生しない。河本体の再描画や base river layer の責務は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-03 orphan LiveRiverStore projection guard
- CH-202: `src/capture/fragment_parser.py`, `src/app/main.py`, `tests/test_live_river_orphan_projection_regression.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md` を更新し、`current_round is None` でも `LiveRiverStore` に既存 discard がある場合は REINIT / WGC / INITBYLOG / browser bridge river を projection-only として扱うようにした。reset + seed を許すのは snapshot の完全 round key が `LiveRiverStore.round_key` と明確に異なる場合だけで、snapshot key が不完全な場合は base river を保持する。`build_live_round_identity()` も `current_round is None` で `("river_epoch", epoch, live_river_store.round_key)` を返すようにし、renderer/cache が orphan river を新局 reset と誤認しないようにした。副露 `N`、analysis overlay、async-only refresh の責務は変更していない。回帰テストは `tests/test_live_river_orphan_projection_regression.py`。

## 2026-07-03 LiveRiverStore epoch 内の空 projection 防御
- CH-201: `src/ui/table_renderer.py`, `tests/test_live_river_renderer_epoch_barrier.py` を更新し、renderer の base river cache continuity は `LiveRiverStore.epoch` が両方取れる場合に epoch 一致を最優先するようにした。同一 epoch 内では WGC / REINIT / browser bridge などで logical identity や wrapper が変わっても同じ base river とみなし、空または短い projection で前回 base river を消さず called 表示として保持する。epoch が変わった場合は INIT / 明確な別局 REINIT の authoritative reset として前局 base river を保持しない。async-only refresh、analysis overlay、LiveRiverStore / tracker / RoundState の正史境界は変更していない。回帰テストは `tests/test_live_river_renderer_epoch_barrier.py`。

## 2026-07-03 haya 早切り音声アラート
- CH-200: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `assets/audio/alert_panel_haya.wav`, `assets/audio/alert_sound_preview.html`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/alerts_and_panels.md` を更新し、他家の最新打牌が `thinking_time_ms <= 2300ms` かつ 3-7 の数牌の場合に `haya` panel alert / 音声を出すようにした。赤5は 5 として扱い、字牌・1/2/8/9・2300ms 超過は対象外。既存の transition-driven alert sound gate と worker queue を使うため、同じ alert の再描画では再生しない。河本体の再描画や base river layer の責務は変更していない。回帰テストは `tests/test_player_panel_alerts.py`。

## 2026-07-03 hanchan_master source_url 復元
- CH-199: `src/capture/storage.py`, `tests/test_live_capture_agari_storage.py`, `docs/reference/csv_db_design.md` を更新し、live capture の `hanchan_master.source_url` が空になる経路を修正した。`TAIKYOKU.log` / `state.game_id` に Tenhou log id がある場合は `https://tenhou.net/0/?log=...` として新規 hanchan row に保存し、INIT 時点で log id が未到着だった既存 row も後続の DB 対象イベントで空 `source_url` を backfill する。既存の非空 `source_url` と XML import で明示された URL は保持する。回帰テストは `tests/test_live_capture_agari_storage.py`。

## 2026-07-02 LiveRiverStore authoritative reset 境界
- CH-198: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_river_epoch_boundaries.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_live_snapshot_cache.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md` を更新し、base river の描画 identity に `LiveRiverStore.epoch` を含めた。`build_live_round_identity()` は `("river_epoch", epoch, logical_round_identity)` を返し、renderer の `_same_round_discard_cache_identity()` / `_merge_discard_map_with_round_cache()` は epoch が変わったら同一 logical round でも前局 river を保持しない。同一 epoch 内の短い projection は引き続き display-only で保持する。これにより副露・WGC・browser projection の短縮防御を維持しつつ、INIT / 明確な別局 REINIT / bootstrap reset 後に前局 river が renderer cache から復活しない。回帰テストは `tests/test_live_river_epoch_boundaries.py` と関連 live river / renderer cache テスト。
- CH-197: `src/app/main.py`, `src/capture/fragment_parser.py`, `tests/test_live_river_store.py`, `tests/test_live_river_store_authoritative_boundaries.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md` を更新し、`LiveRiverStore` の authoritative reset / seed 境界を明確化した。通常 `INIT`、明確に別局の `REINIT`、同一局再利用できない `INITBYLOG` / `WGC`、Bridge bootstrap / 新局扱い、INIT 欠落時の packet-first round では `LiveRiverStore` を reset + seed する。同一局 `INITBYLOG` / `WGC` / REINIT / Bridge projection は projection-only とし、base river を短縮しない。Bridge bootstrap は browser snapshot から作った `bootstrap_discards` を `RoundState` 互換 mirror と `LiveRiverStore` の両方へ seed し、tracker は `LiveRiverStore` から再構築する。回帰テストは `tests/test_live_river_store_authoritative_boundaries.py`, `tests/test_live_river_store.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_render_capture_separation.py`, `tests/test_called_discard_hard_barrier.py`, `tests/test_same_round_init_wgc_call_preservation.py`, `tests/test_called_discard_same_kind_projection_merge.py`。

## 2026-07-01 副露時の描画/キャプチャ分離強化
- CH-196: `src/capture/live_river_store.py`, `src/capture/state.py`, `src/capture/fragment_parser.py`, `src/app/main.py`, `tests/test_live_river_store.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_render_capture_separation.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md`, `docs/architecture/source_overview.md`, `docs/architecture/folder_structure.md` を更新し、live base river の正史を `RoundState` 内から `GameState.live_river_store` / `CaptureState.live_river_store` へ移した。`LiveRiverStore` は `RoundState` 差し替えや `reset_live_session()` では消えず、reset は `INIT_NEW_ROUND`、`REINIT_DIFFERENT_ROUND_CONFIRMED`、`MANUAL_USER_RESET` の明示 authority に限定する。通常打牌は store へ append、副露 `N` は store 上の既存 discard へ `called=True` / lag metadata を付けるだけにし、`REINIT` / `WGC` / `INITBYLOG` / Bridge browser river は projection-only として別保管し、同一局または別局不明では base river へ merge / append しない。live snapshot / visible summary / render discard map は `LiveRiverStore.snapshot_by_seat()` 由来にし、tracker / `RoundState.discards` / renderer cache は派生 view / 互換 view / 描画補助に限定した。回帰テストは `tests/test_live_river_store.py`, `tests/test_round_discard_ledger.py`, `tests/test_called_discard_hard_barrier.py`, `tests/test_same_round_init_wgc_call_preservation.py`, `tests/test_called_discard_same_kind_projection_merge.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`, `tests/test_discard_render_capture_separation.py`, `tests/test_hand_auto_mode.py`, `tests/test_player_panel_alerts.py`。
- CH-195: `src/capture/discard_ledger.py`, `src/capture/state.py`, `src/capture/fragment_parser.py`, `src/app/main.py`, `src/capture/storage.py`, `tests/test_round_discard_ledger.py`, `docs/specs/current.md`, `docs/integrations/packet_capture.md` を更新し、局中の捨て牌履歴正本を `RoundDiscardLedger` へ移した。`RoundState.discards` は互換 view として残すが、初期化後の dict 置換、席リストの clear / del / 短縮代入を拒否し、通常打牌は ledger append、副露 `N` は既存 discard の `called=True` / `lagged=2` metadata 更新だけに制限する。`REINIT` / `INITBYLOG` / `WGC` の `kawa` は visible projection として `apply_discard_projection_non_destructive()` に通し、既存履歴を短縮せず、欠落 slot は `called=True` として保持し、projection tail だけ append する。Bridge 起動直後 bootstrap は新規 round への append に変更し、分析用 clone の一時削除は shared state ではなく clone ledger の manual reset で再構成する。描画 layer / analysis overlay / DB schema は変更していない。回帰テストは `tests/test_round_discard_ledger.py`, `tests/test_called_discard_hard_barrier.py`, `tests/test_same_round_init_wgc_call_preservation.py`, `tests/test_called_discard_same_kind_projection_merge.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `tests/test_render_analysis_split_contract.py`, `tests/test_discard_render_capture_separation.py`, `tests/test_hand_auto_mode.py`, `tests/test_player_panel_alerts.py`。
- CH-194: `src/ui/table_renderer.py`, `src/app/main.py`, `src/capture/fragment_parser.py`, `tests/test_called_discard_hard_barrier.py`, `tests/test_same_round_init_wgc_call_preservation.py`, `tests/test_discard_borders.py`, `tests/test_live_snapshot_cache.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、副露時に短い visible projection が一気に base river layer を消す経路へ hard barrier を追加した。`INIT` / `INITBYLOG` / `WGC` wrapper は underlying round id が同じなら同一局として扱い、wrapper 変化だけでは base river cache / live discard history を切らない。identity 判定に失敗しても、前回 base river があり現在入力が短い非空 `discard_map` なら同一局疑いとして display-only merge し、`current_total == 0` かつ identity が変わった場合だけ新局初期 reset を許す。packet 先行で current round の kyoku / honba / oya が未確定のまま REINIT / WGC が来た場合も、既に discard があれば new round へせず current round を再利用する。analysis overlay 分離、async-only refresh で `_draw_discards()` を呼ばない挙動、DB schema、副露時に `round_state.discards` / `tracker.discards` を削除・短縮しない挙動は変更していない。回帰テストは `tests/test_called_discard_hard_barrier.py`, `tests/test_same_round_init_wgc_call_preservation.py`, `tests/test_discard_borders.py`, `tests/test_live_snapshot_cache.py`。
- CH-193: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_render_layer_split_regression.py`, `tests/test_live_snapshot_cache.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、WGC / INITBYLOG wrapper 付き `round_identity` が同一局の base river cache を別局扱いで破棄する経路を修正した。`_same_round_discard_cache_identity()` / `_same_live_discard_history_round()` は underlying round id が同じ WGC / INITBYLOG wrapper 変化を同一局として扱い、cached-layout redraw でも `_draw_discards()` 前に `_merge_discard_map_with_round_cache()` で短い projection を display-only 保持へ正規化する。`INIT` は引き続き `REINIT` より強い強制リセット境界として扱い、INIT 前の UI cache を復帰元にしない。analysis overlay 分離、async-only refresh で `_draw_discards()` を呼ばない挙動、DB schema、副露時に捨て牌配列を削除・短縮しない挙動は変更していない。回帰テストは `tests/test_render_layer_split_regression.py`, `tests/test_live_snapshot_cache.py`。
- CH-192: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_render_analysis_split_contract.py`, `tests/test_discard_borders.py`, `tests/test_live_snapshot_cache.py`, `tests/test_hand_auto_mode.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md` を更新し、河描画を base river layer と analysis overlay layer に分離した。base は牌画像本体、手出し/ツモ切り、思考時間、lag、`called=True` 黄色枠、リーチ棒だけを持ち、red / brown / four-visible tint、見え枚数 marker、Push `P`、同順合わせ打ち marker は `live_discard_analysis_overlay` tag の overlay として重ねる。async-only refresh は `_draw_discards()` を呼ばず `_draw_discard_analysis_overlays()` だけで河位置連動の計算結果を更新する。suji / red tint worker job は共有 `CaptureState` ではなく `LiveAnalysisSnapshot` を持ち、worker-local facade で計算する。`build_live_table_snapshot()` / `build_fast_live_table_snapshot()` から UI stable river を tracker / capture state へ戻す経路を切った。副露 event で捨て牌配列を削除・短縮・再構築する挙動、DB schema、`called=True` 黄色枠表示は変更していない。回帰テストは `tests/test_render_analysis_split_contract.py`, `tests/test_discard_borders.py`, `tests/test_live_snapshot_cache.py`, `tests/test_hand_auto_mode.py`。
- CH-191: `src/ui/table_renderer.py`, `src/capture/fragment_parser.py`, `tests/test_discard_render_capture_separation.py`, `tests/test_discard_borders.py`, `tests/test_called_discard_same_kind_projection_merge.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、副露時に河の base layer が短い projection で消される経路をさらに分離した。REINIT / INITBYLOG / spectator WGC の `kawa` 同一局判定は exact 136 ID ではなく tile34 牌種で比較し、spectator snapshot でも同一局なら existing round を再利用して `round_state.discards` を短縮しない。renderer の per-round cache は履歴正本ではないが、同一局の full redraw に短い `discard_map` が来た場合は display-only で前回表示 slot を保持し、欠落 slot を `called=True` 黄色枠として残す。同じ牌種の保持済み `called=True` slot は後続 uncalled visible discard を消費しない。live snapshot builder / worker / Bridge import / DB schema は履歴補完元にしていない。回帰テストは `tests/test_discard_render_capture_separation.py`, `tests/test_called_discard_same_kind_projection_merge.py`, `tests/test_discard_borders.py`, `tests/test_live_snapshot_cache.py`。

## 2026-06-30 副露時の捨て牌正本化
- CH-190: `src/ui/table_renderer.py`, `src/capture/fragment_parser.py`, `tests/test_hand_auto_mode.py`, `tests/test_discard_borders.py`, `tests/test_called_discard_same_kind_projection_merge.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.2.md`, `docs/screen_specs/river_display.md`, `docs/analysis/performance_hotspots.md`, `docs/integrations/packet_capture.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、suji / red tint / visible count / push alert などの live async-only refresh が `_draw_discards()` を呼ばないようにした。async-only refresh は `LiveAsyncRenderState.discard_map` を維持し、`partial_snapshot.discard_map` を河描画へ流し込まず、`live_async_discards` 全体 tag も削除しない。鳴かれた捨て牌の表示枠は黄色へ変更し、`N` 処理では exact 136 ID がずれた場合も同種牌の最後の未鳴き discard を metadata-only で `called=True` / `lagged=2` にする。副露 event で捨て牌リストを削除・短縮する挙動、Bridge projection / REINIT projection を描画履歴へ merge する挙動、DB schema は変更していない。回帰テストは `tests/test_hand_auto_mode.py`, `tests/test_discard_borders.py`, `tests/test_called_discard_same_kind_projection_merge.py`。
- CH-189: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `docs/specs/current.md`, `docs/specs/api_spec_v2.2.md`, `docs/integrations/packet_capture.md`, `docs/analysis/performance_hotspots.md`, `docs/operations/troubleshooting/live_rendering.md` を更新し、`INIT` を `REINIT` より強い強制リセット境界として固定した。`INIT` wrapper 付き round identity から同じ局キーの `REINIT` / 通常 snapshot へ移る場合も、`INIT` 前の renderer cache / stable discard map / cached snapshot を復帰元にしない。`REINIT` 同士の同一局判定、`round_state.discards` 正本、Bridge projection 非 merge、DB schema は変更していない。回帰テストは `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`。
- CH-188: `src/app/main.py`, `src/capture/state.py`, `src/ui/table_renderer.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `tests/test_called_discard_same_kind_projection_merge.py` を更新し、副露 / カン後の河欠落対策を「補完」から「正本分離」へ切り替えた。`round_state.discards[seat]` を局中の唯一の捨て牌履歴正本とし、Bridge `riverEntriesBySeat` は既存局では `browser_visible_river_projection` へ別保管するだけで、`round_state.discards` や tracker を reset / rebuild / merge しない。live snapshot は lock 下でコピーした `RoundState` から表示用 tracker を再構築し、worker / renderer cache / cached snapshot / stable map は捨て牌履歴を修復しない。renderer の per-round cache は現在入力を保存するだけにし、短い `discard_map` を長い履歴へ戻す責務を持たない。回帰テストは Bridge 既存局 metadata-only import、round_state 由来の heavy / fast snapshot、renderer cache 非補修、同種牌 called gap の非混入。

## 2026-06-21 副露時の河表示保持
- CH-180: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_snapshot_cache.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_discard_borders.py` を更新し、`N` / REINIT / Bridge snapshot 直後に live の河配列が一時的に短くなっても、同一局の前回 `discard_map` を安定コピーとして保持するよう修正した。heavy snapshot と fast snapshot の両方で前回河へ live tail を合成し、Bridge snapshot の prefix 判定では鳴かれた捨て牌を除外して比較する。同一局リセットでは Canvas の捨て牌 render cache と画像参照も保持し、短い河入力が来た瞬間に既表示スロットを削除しない。既存の差分描画、`called` 赤枠、Push / lag marker の仕様は維持する。回帰テストは `tests/test_live_snapshot_cache.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_discard_borders.py`。
- CH-181: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py` を更新し、`INIT` wrapper 付き round identity から同じ `round_id` の REINIT / 通常 snapshot へ移る場合も同一局の河履歴として扱うよう修正した。副露 / カンで卓フレームの full redraw が走る場合も、Canvas を clear する直前に per-round cache で短い `discard_map` を補完する。repeated `INIT` は従来通り別局扱いで cache を破棄する。回帰テストは `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `tests/test_live_reinit_bootstrap.py`。
- CH-182: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py` を更新し、副露後 snapshot で鳴かれた捨て牌が河の途中から抜けるケースを復元対象にした。cache 側の `called=True` スロットを current 側の欠落 gap として扱い、後続牌が再採番されても tile 種で照合して `called` 牌を戻す。回帰テストは heavy / fast live snapshot と renderer per-round cache の gap 復元。
- CH-183: `src/capture/state.py`, `src/app/main.py`, `tests/test_live_snapshot_cache.py` を更新し、`CaptureState.live_stable_discard_map` を局内の単調増加 river store として追加した。heavy / fast snapshot は `cached_live_table_snapshot` より先にこの lock 付き退避 store を参照し、壊れた短い `discard_map` が来ても描画用 `discard_map` を store から復元する。live session reset では store を clear し、新しい round identity では上書きする。回帰テストは cached snapshot が欠落しても stable store から復元するケース。
- CH-184: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py` を更新し、Tenhou UI Bridge の `riverEntriesBySeat` を現在ブラウザに表示されている河の sparse projection として扱うよう修正した。`_import_tenhou_ui_bridge_table_snapshot()` は `round_state.discards[seat]` を snapshot で直接上書きせず、`_merge_bridge_snapshot_discards_with_previous_history()` で同一局の full history とマージする。鳴かれた `called=True` 捨て牌は保持し、非 `called` 牌の不一致は履歴保持せず snapshot へフォールバックする。renderer / live snapshot 側の gap 復元も `called=True` の slot だけを保持対象に限定した。回帰テストは bridge の head / middle gap / shorter snapshot / non-called mismatch / import 統合、live snapshot の non-called mismatch、renderer cache の non-called mismatch。
- CH-185: `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py` を更新し、Bridge 可視河から鳴かれ牌が消えたタイミングが packet `N` の `called=True` 反映より先行する race に対応した。前回 full history の非 `called` slot が current projection から抜け、後続の visible 河が tile 種で整合する場合、または前方 prefix が一致したうえで最後の未鳴き slot だけが抜けた場合は、その slot を `called=True` / `lagged=2` として保持する。単独 slot の完全置換や複数の未鳴き slot が整合せず抜ける場合は従来どおり現在 snapshot 側へフォールバックする。回帰テストは Bridge import の未反映 `called` gap、live snapshot / renderer cache の inferred called gap と multi mismatch reject。
- CH-186: `src/app/main.py`, `src/capture/fragment_parser.py`, `src/ui/table_renderer.py`, `tests/test_bridge_table_snapshot_import.py`, `tests/test_live_snapshot_cache.py`, `tests/test_discard_borders.py`, `tests/test_live_reinit_bootstrap.py`, `tests/test_hand_auto_mode.py` を更新し、同一局の捨て牌履歴を strict append-only projection merge に統一した。Bridge `riverEntriesBySeat` / REINIT `kawa` / renderer cache の current projection に前回 full history の捨て牌が存在しない場合、その前回 slot は枚数や整合条件に関わらず `called=True` / `lagged=2` として保持し、未消費の visible tail を後ろへ append する。例として前回 `[A]` / snapshot `[B]` は `[A(called), B]`、前回 `[A,B]` / snapshot `[B,C]` は `[A(called), B, C]`、前回 `[A,B]` / snapshot `[C,D]` は `[A(called), B(called), C, D]` になる。回帰テストは Bridge import、REINIT `kawa`、live stable store、renderer per-round cache、live async redraw の append-only gap 復元。
- CH-187: `src/app/main.py`, `src/capture/fragment_parser.py`, `src/ui/table_renderer.py`, `tests/test_called_discard_same_kind_projection_merge.py` を更新し、append-only projection merge で保持済み `called=True` slot が、同じ牌種の uncalled visible slot を誤って消費しないよう修正した。可視 projection には鳴かれ済み slot は存在しないため、前回 `[A(called)]` / projection `[A(uncalled)]` は `[A(called), A(uncalled)]` として保持する。current 側も明示的に `called=True` の場合だけ、同じ called slot として消費する。回帰テストは Bridge / REINIT / live stable / renderer cache の同種牌 gap と、authoritative called current の消費ケース。

## 2026-06-20 保守ルール・source ZIP安全化・capture replay更新
- CH-177: `AGENTS.md`, `docs/architecture/adr/*`, `docs/operations/regression_checklist.md`, `docs/operations/code_review.md`, `.github/pull_request_template.md` を追加し、既存docsを正本として再利用するCodex作業ルール、ADR運用、横断回帰チェック、レビュー分類、PR確認項目を整備した。既存 `docs/changelog.md` を変更履歴の正本として維持し、重複するCodex専用changelogは作成しない。
- CH-178: `scripts/package_workspace.py`, `.gitignore`, `tests/test_package_workspace.py`, `docs/operations/other_environment_setup.md` を更新し、既定の `source` ZIPから秘密情報、Cookie state、token、TLS keylog、ログ、runtime CSV DB、分析出力、pcap、既存ZIP、Python cacheを除外するよう変更した。runtime data退避は `runtime-backup` profileで明示指定されたpathだけを対象にし、秘密情報は常に拒否する。
- CH-179: `src/capture/tshark_capture.py`, `src/capture/pcap_replay.py`, `tests/test_tshark_capture_interface.py`, `tests/test_pcap_replay.py`, `docs/integrations/packet_capture.md` を更新し、timestampなし tshark runtime outputを `info` / `warning` / `error` に分類するよう変更した。pcap replayは事前tag抽出をやめ、共有 `parse_tshark_output_line()` の戻り値で処理有無を判定することで、同じlineのsplit/fragment extraction二重実行を避ける。DB schema、UI表示、parserのevent順序仕様は変更していない。

## 2026-05-24 v2.2 画面仕様・性能・分析更新
- CH-170: `src/ui/table_renderer.py` を更新し、河を座席 + 捨て牌 index の表示シグネチャで差分描画するよう変更した。`Push` 判定で音が鳴る更新では同じ捨て牌へ `P` マークを即時反映し、変化した牌だけ Canvas tag 単位で差し替える。
- CH-171: discard path の色付き `PhotoImage` 合成を廃止し、通常牌画像 + Canvas overlay で赤/茶/紫/4見え/思考時間 band を描画するよう変更した。discard item は作成時に `tags=` を付け、後付け `find_all()` タグ付けを使わない。
- CH-172: プレイヤーパネルの `SUMMARY` と `ALERT` の remain 色基準を統一し、panel に出ない自分側 remain / Push 系 alert は音声対象外にした。Remain 音声 key は `r-red` など `r` 付きへ変更した。
- CH-173: Nodocchi `STATUS` 表示で和了率・副露率・リーチ率だけ赤字、その他の数値を白字にした。
- CH-174: 南2局以降、下部スペースに NAGA 段位ポイント分析の主要な和了・放銃・流局 pt 変化を自動表示する `NagaAutoPanelData` 経路を追加した。
- CH-175: `scripts/analyze_player_shanten_thinking.py` を追加し、DB からプレイヤー別の思考時間 x シャンテン数の相関とばらつきを集計し、`hanchan_master` 由来の所属卓も出力できるようにした。
- CH-176: `docs/requirements/current.md`, `docs/specs/current.md`, `docs/screen_specs/current.md` を v2.2 へ更新し、河表示、パネル/アラート、性能ホットスポット、NAGA 連携、DB分析、CSV DB 設計、README を現行仕様へ同期した。

## 2026-05-10 STATUS 成績表示・麻雀文書再構成
- CH-167: `src/app/nodocchi_stats.py`, `src/ui/table_renderer.py`, `tests/test_nodocchi_stats.py` を追加・更新し、相手パネルの `STATUS` から Nodocchi 鳳凰卓4人打ち成績を取得して右詳細領域に表示できるようにした。取得は background thread と canvas queue で UI thread に戻し、同一プレイヤーは cache して多重リクエストを避ける。失敗時・データなし時も `Nodocchiで開く` 外部リンクを残す。
- CH-168: `docs/mahjong-theory/` を `docs/mahjong/theory/` へ統合し、旧 `docs/mahjong/*.md` を `logic/`, `reference/`, `research/` に再分類した。`docs/mahjong/README.md` と各サブフォルダ README を追加し、学習セオリー、実装ロジック、基礎参照、研究メモの棲み分けを明文化した。
- CH-169: `docs/requirements/current.md`, `docs/requirements/requirements_v2.1.md`, `docs/specs/current.md`, `docs/specs/api_spec_v2.1.md`, `docs/screen_specs/current.md`, `docs/screen_specs/screen_spec_v2.1.md`, `docs/screen_specs/alerts_and_panels.md`, `docs/architecture/*` を更新し、STATUS 成績表示と麻雀文書再構成を現行 docs へ同期した。

## 2026-04-23 Push 表示条件同期修正
- CH-164: `src/ui/table_renderer.py`, `tests/test_player_panel_alerts.py`, `tests/test_discard_borders.py`, `docs/screen_specs/alerts_and_panels.md`, `docs/mahjong/logic/mahjong_danger.md` を更新し、相手パネルの `Push` と河の `P` が同じ latest-discard 条件で点灯するよう揃えた。従来の卓全体現打牌ゲートで panel `Push` が落ちていたケースを解消しつつ、panel 側だけ `3巡` 保持と `Push解除` を継続する。
- CH-165: `src/logic/danger_suji.py`, `src/ui/table_renderer.py`, `src/capture/storage.py`, `tests/test_player_panel_alerts.py`, `tests/test_discard_borders.py` を更新し、`Push` の実効閾値を payload 化した。通常は `9%`、対象にリーチ者が含まれる成立だけ `6%` で `Push` / 河の `P` / agari snapshot alert を出す。
- CH-166: `src/visible_tiles.py`, `tests/test_discard_borders.py`, `docs/mahjong/logic/mahjong_danger.md`, `docs/screen_specs/river_display.md` を更新し、茶色 tint を「その牌を通る全形が塞がる」判定から、「3スーツ x 123..789 の 21 通りのうち 4見えで物理否定された 3 連形へ属する手出し牌」判定へ変更した。牌自身が `4見え` の場合は引き続き紫が優先する。

## 2026-04-21 自家字牌表示・文書運用更新
- CH-161: `src/ui/table_renderer.py` と `tests/test_player_panel_alerts.py` を更新し、自家の `2見え以下字牌` 一覧を自河中央ではなく自副露帯寄りへ少し下げて表示するようにした。表示ラベルも `字牌2見え以下` に統一した。
- CH-162: `README.md`, `docs/README.md`, `docs/requirements/*`, `docs/specs/*`, `docs/screen_specs/*`, `docs/architecture/*`, `docs/operations/*` を更新し、今回の表示変更、再生成手順、他環境セットアップ手順を日本語で整理した。
- CH-163: `requirements.txt`, `scripts/render_docs_graphs.py`, `scripts/package_workspace.py`, `docs/graphs/src/*.mmd` を追加・更新し、依存導入、Mermaid 図再生成、ワークスペース ZIP 化を再実行できるようにした。

## 2026-04-17 Live Suji フォールバック署名更新
- CH-160: `src/app/main.py`, `tests/test_live_snapshot_cache.py`, `tests/test_player_panel_alerts.py` を更新し、live の suji bundle fallback を入力署名一致時だけ再利用するようにした。これにより、lag metadata など public round state が更新された直後に、古い bundle の `門前 N` や push 系 panel 値が一瞬残って新しい lag marker と矛盾する状態を避ける。あわせて `門前 N` が lagged source discard を数えないことをテストで固定した。

## 2026-04-17 手動 Bridge 打牌復旧
- CH-159: `src/app/tenhou_ui_bridge_client.py`, `src/app/main.py`, `src/ui/table_renderer.py`, `tests/test_tenhou_ui_bridge.py`, `tests/test_bridge_shortcuts.py` を更新し、manual の手牌クリック / 右クリック打牌が live capture の一時的な 1 枚遅れで止まりやすかった問題を緩和した。manual discard は non-actionable な visible hand count を strict に拒否せず `handIndex` だけ送れるようにし、右クリック `ツモ切り` は contiguous な click spec が `count % 3 == 1` のときに「draw だけまだ見えていない」ケースとして次 slot を補完するようにした。AUTO 側の strict visible hand guard は維持した。

## 2026-04-17 Bridge 再起動優先度整理
- CH-158: `README.md`, `docs/operations/live_startup_checklist.md`, `docs/operations/troubleshooting/live_capture.md` に、`Bridge heuristic ctrls=0` が出ているときは bridge 側切り分けとしての app 再起動優先度が低い一方、`tshark` / TLS keylog / capture thread の再初期化や `--tshark-interface` 変更では app 再起動がまだ有効であることを追記した。

## 2026-04-17 Bridge heuristic 状態整理
- CH-157: `README.md`, `docs/operations/live_startup_checklist.md`, `docs/operations/troubleshooting/live_capture.md` に、`Bridge heuristic ctrls=0` が確認している範囲を追記した。これは browser-side bridge が `ui_snapshot` を返し、heuristic 座標で天鳳ページを操作できる見込みがあり、visible action button が 0 個であることを示す一方、live capture 正常や可視化 app 側の牌表示更新までは保証しないことを明記した。

## 2026-04-17 ライブ起動チェックリスト追加
- CH-156: `docs/operations/live_startup_checklist.md` を新設し、通常運用の起動順、起動直後に stdout/stderr で `Tenhou UI Bridge listening ...` と `TShark runtime message: Capturing on 'Wi-Fi'` 系を確認すること、`loopback` / `ETW` / `0 packets captured` を異常サインとして扱うこと、`SYNC` 後の bridge status の読み方を 1 枚に整理した。README / `docs/README.md` / `docs/operations/README.md` / `docs/integrations/tenhou_ui_bridge.md` / `docs/operations/troubleshooting/live_capture.md` から辿れるようにした。

## 2026-04-17 キャプチャインターフェース選択改善
- CH-155: live capture が固定 `tshark` interface index に依存して loopback / ETW reader を掴み、bridge は生きていても可視化アプリの牌表示だけ更新されない問題を緩和した。`src/capture/tshark_capture.py` に non-loopback adapter 優先の interface 自動選択を追加し、`src/app/main.py` から `--tshark-interface` で明示指定できるようにした。README と `docs/operations/troubleshooting/live_capture.md` にも、`Bridge heuristic ctrls=0` と牌表示なしが同時に起きたときは capture interface を疑うこと、`tshark -D` で index を確認して override する手順を追記した。

## 2026-04-17 起動順整理
- CH-154: `README.md`, `docs/integrations/tenhou_ui_bridge.md`, `docs/operations/troubleshooting/live_capture.md`, `src/app/main.py` を更新し、Tenhou UI Bridge の起動順を「初回だけ extension を読み込み、その後の通常運用は `ローカル app -> ブラウザで extension 有効確認 -> 天鳳ページを開く/リロード`」に明確化した。ブラウザ本体の先後は本質ではなく、必須条件は `app 起動後` に天鳳ページを開くかリロードすることだと文書と起動時標準エラーへ明記した。

## 2026-04-17 Bridge 状態表示整理
- CH-153: `README.md` と `docs/operations/troubleshooting/live_capture.md` に、bridge status label の読み方を追記した。`Bridge connected` は Chrome extension とローカル app 間の transport 接続だけを示し天鳳ページ準備完了ではないこと、`SYNC` 後に `Bridge globals|canvas_detect|heuristic ctrls=N` が出れば `tenhouReady = true` で bridge 実行可能なこと、`Bridge tab not ready` / `Bridge ERR ...` の切り分け方、および Chrome 再起動時は extension reload より先に `天鳳タブをリロード -> SYNC` を試す運用を明文化した。

## 2026-04-15 画面仕様再編
- CH-152: `docs/screen_specs/` を再編し、現行の画面仕様を `display_overview.md`, `river_display.md`, `alerts_and_panels.md`, `controls_and_bridge.md`, `visible_counts_ui.md` の 5 文書へ分割した。旧 `rendered_display_guide.md` と `alert_flag_reference.md` は互換用の案内ページへ変更し、`README`, `project_guide`, `source_overview`, `requirements_v2.1`, `api_spec_v2.1`, `visible_count_pipeline`, `data_structures`, `pystyle_auto_mode`, `suji_temp_no_temp_logic` を現行仕様へ揃えた。

## 2026-04-12 Tenhou UI Bridge probe 競合対応
- CH-147: Windows で `TenhouUiBridgeServer` が同じ port に二重 bind できてしまい、`app.tenhou_ui_bridge_probe` を本アプリと同時に実行すると単に timeout して原因が見えにくい問題を修正した。Windows では `SO_EXCLUSIVEADDRUSE` を使って bridge port を fail-fast にし、`tenhou_ui_bridge_probe.py` の bind / timeout error も「本アプリを止めてから standalone probe を使うこと」が分かる文面へ更新した。README と `docs/integrations/tenhou_ui_bridge.md` にも、probe CLI は本アプリと同時使用しないことを追記した。
- CH-148: `extension/content-bridge.js` から page load 時に `ENSURE_LOCAL_WS` を service worker へ送るよう更新し、`app first -> 天鳳ページ reload` と `probe first -> page reload` のどちらでも localhost WebSocket reconnect が走りやすいようにした。`extension/service-worker.js` に対応 handler を追加し、README と `docs/integrations/tenhou_ui_bridge.md` の standalone probe 手順も `page reload` 前提へ更新した。
- CH-149: `extension/main-ui-bridge.js` の `tenhouReady` 判定と `discard_by_index` 座標計算を拡張し、`window.U / W / Q / kc` が page-global に見えない current Tenhou variant でも、標準卓の canvas 比率から自家手牌帯を推定する `heuristic` fallback で動けるようにした。`ui_snapshot` には `layoutMode` と `missingGlobals` も返すよう更新し、README と `docs/integrations/tenhou_ui_bridge.md` の `tenhouReady` 説明も同期した。
- CH-150: `AUTO` が同一手牌で `pystyle` 取得失敗後に黙ったまま止まりやすい問題を修正した。`src/ui/table_renderer.py` で AUTO 時の recommendation retry を追加し、`HandRecommendationPanelData.is_loading` を渡して retry と loading を分離した。AUTO candidate 判定も `turn_index` / `wall_tiles_remaining` / `remaining_wall` の軽いズレは許容し、同一局・同一 dora・同一 meld 文脈なら `heuristic` bridge でも自動打牌へ進めるよう更新した。
- CH-151: ローカル可視化 app 側に手動 bridge UI を追加した。自家手牌 click は `discard_by_index`、`SYNC` と visible control button は `ui_snapshot` / `click_control` を使い、`AUTO` も可能なら同じ `discard_by_index` 経路を優先する。bridge status label と visible control row を root window へ追加し、packet capture 側の局面認識と browser-side UI 実行を個別に切り分けやすくした。

## 2026-04-12 Tenhou UI Bridge 起動メモ
- CH-146: `README.md` と `docs/integrations/tenhou_ui_bridge.md` に、`AUTO` は Chrome extension を事前に読み込んだ前提で動くこと、`hand_auto_discard_action` は app 起動時に自動配線されること、推奨起動順は `ローカル app -> extension 有効確認 -> 天鳳ページを開く/リロード -> AUTO ON` であることを追記した。`AUTO ERR` の典型原因と `ui_snapshot` による切り分け手順も明記した。

## 2026-04-11 Tenhou UI Bridge 追加
- CH-144: 既存のローカル可視化アプリへ `Tenhou UI Bridge` を統合し、`src/app/tenhou_ui_bridge_protocol.py` / `tenhou_ui_bridge_server.py` / `tenhou_ui_bridge_client.py` を追加した。Chrome 側は `extension/manifest.json`, `service-worker.js`, `content-bridge.js`, `main-ui-bridge.js` を追加し、ローカル app が packet capture から判断した `discard_by_index` / `click_control` / `ui_snapshot` / `ping` を localhost WebSocket 経由で MV3 service worker へ渡して天鳳 UI 実行だけを担当させる構成へ整理した。
- CH-145: `tmp_web/tenhou_ui_bridge_mock.html`, `tmp_web/tenhou_ui_bridge_mock.js`, `src/app/tenhou_ui_bridge_mock_server.py`, `src/app/tenhou_ui_bridge_probe.py` を追加し、mock page と one-shot probe CLI で Tenhou UI Bridge の end-to-end 動作確認ができるようにした。あわせて bridge 関連ソースへ責務境界コメントを増やし、`docs/integrations/tenhou_ui_bridge.md`, `README.md`, `docs/architecture/source_overview.md`, `docs/architecture/project_guide.md`, `docs/architecture/folder_structure.md`, `docs/architecture/src_call_graph.md` を更新した。

## 2026-04-11 レイアウト調整更新
- CH-143: `LAYOUT` の `Reset` 基準を現行保存レイアウトへ更新し、`csv_db/ui_layout_tuning.json` を `layout_schema_version = 2` の保存形式へ整理した。副露帯 width は `side_meld_width` / `top_meld_width` / `bottom_meld_width` を正本とし、対面と自分の Meld 幅を別々に調整できるよう更新した。`AI TOP3` は `LAYOUT` open 中の direct drag 対象へ追加し、visible slider からは obsolete `Top meld min width`, `AI TOP3 X`, `AI TOP3 Y` を外した。要件 / API spec / screen spec の current pointer も `v2.1` へ更新した。

## 2026-04-09 アガリ危険度 DB 追加
- CH-115: 和了イベントを `agari_fact_YYYYMM.csv` として保存し、`winner / fromWho / machi / deal_in_discard_id` に加えて、ロン時の筋危険度推定 `%` を `estimated_danger_percent` へ記録するよう更新した。ロンの `%` は放銃牌を河へ加えた後の `0%` 化を避けるため、対象打牌を round 状態から一時的に外した「放銃直前」相当の条件で算出する。自家放銃は pre-discard hand snapshot ベース、他家放銃は対象牌 1 枚の synthetic 推定として保存する。

## 2026-04-10 pystyle 副露手・自家アラート更新
- CH-116: `AI TOP3` ボタン位置を「ツモ牌表示時の右寄せ位置」で常に固定し、draw の有無で左右へ跳ねないよう更新した。あわせて、pystyle request は open-hand を正しく扱えるよう、自家の副露を `melds[]` として POST しつつ concealed hand 枚数 + meld 枚数の合計が `14` のときに計算するよう修正した。
- CH-117: 自家手牌右の `AI TOP3` ボタンさらに右へ `SELF` alert 欄を追加し、pystyle の 1 位期待値が `600` 未満のとき赤丸付き `LOW EV` を出すよう更新した。自家に open meld がある場合は 1 位期待値へ `0.8` を掛けた値で判定し、期待値回復時または round token が変わった局開始時には alert を消す。
- CH-118: 鳴き後の次ツモで自手 draw を二重加算して `concealed + meld = 15` 扱いになる不具合を修正した。renderer の `hand_tiles` は draw 済み表示手牌を保持しているため、AI request / safe-rank 生成も同じ解釈へ揃え、末尾 draw が既に含まれている局面では `hand_draw_tile` を再追加しない。
- CH-119: CSV DB schema を整理し、`go_type` / `go_type_hex` / `room_class_code` / `kyoku_info` は保存列から削除して `room_class_label` のみ残すよう更新した。旧 CSV を読み込む際は、必要なら legacy の `go_type` / `go_type_hex` / `source_url` から `room_class_label` を補完しつつ、新 schema へ rewrite できる。
- CH-120: pystyle の `total` 判定を「concealed + 各 meld を常に 3 枚ぶん」で数えるよう修正した。これで chi / pon / daiminkan / ankan / kakan のいずれでも、門前からの実効減少量に合わせて `14 枚打牌前` 判定できる。あわせて `LOW EV` の `0.8` 補正条件を `is_open` ベースへ明示化し、暗槓のみでは補正せず、明槓と加槓は副露扱いで補正する。
- CH-121: `SELF` alert を 3 段階化し、赤 `LOW EV` は alert-only EV `<600`、黄 `EV<800` は raw pystyle EV `<800`、緑 `HIGH EV` は raw pystyle EV `>=3000` で出し分けるよう更新した。`AI TOP3` パネルの期待値表示は raw のまま維持し、短音は none→active または alert kind 変更時だけ鳴る。
- CH-122: 他家プレイヤーパネルの alert でも短音を鳴らすよう更新した。`Remain` / `Push` alert は stable key ベースで新規発生時や段階変化時だけ鳴り、`Remain` 表示は `current/no-temp` に拡張して一時 safe を除いた baseline 本数も併記する。
- CH-123: `requirements_v1.9.md`, `api_spec_v1.9.md`, `screen_spec_v1.9.md` を追加し、current pointer と `project_guide.md`, `source_overview.md`, `pystyle_simulator_protocol.md`, `mahjong_danger.md` を 2026-04-10 時点の実装へ同期した。
- CH-124: 手牌 preview tool を `template_workspace` から本体プロジェクトへ移し、`cli/render_hand_preview.py` と `src/app/hand_preview_tool.py` を正本配置にした。画像出力の既定先は `analysis_output/hand_previews/` とし、`discard_id` 指定時は `discard_fact_*.csv` の打牌前手牌 snapshot をそのまま画像化する。

## 2026-04-09 サイドパネルアラート配置
- CH-106: 上家 / 下家の縦長プレイヤーパネルでも `ALERT` 欄が実際に表示されるよう、縦長パネルの summary / alert / buttons 配分に最小高さ補正を追加した。既存の `ui_layout_tuning.json` を保持したままでも、`ALERT` に最低 3 行分の描画余地と `BUTTONS` の全ボタン領域を両立する。

## 2026-04-09 副露自動フィット
- CH-107: 副露帯に収まりきらない面子を単純に打ち切っていた描画を修正し、2副露目以降も表示できるよう副露牌と面子間 gap を帯サイズへ自動縮小するよう更新した。横帯・縦帯の両方で、現在の `LAYOUT` 値を維持したまま全副露を優先表示する。

## 2026-04-09 AI TOP3 ボタン調整
- CH-108: 自家手牌右の `AI TOP3` ボタン位置を `LAYOUT` tuning で調整できるよう、`AI TOP3 X` / `AI TOP3 Y` を追加した。ボタンを動かすと popup も追従し、保存済み tuning では初期位置を少し右寄せにした。

## 2026-04-09 Push アラート席対応
- CH-109: `Push` alert を単なる `%` 値ではなく `seat / tile / discard_index / percentage` 付き payload として renderer へ渡すよう更新した。panel 側は payload 内の `seat` と自席が一致する場合だけ紫 alert を表示し、ラベルも `Push 5m 12.3%` のように対象打牌を併記する。

## 2026-04-09 自家鳴き手牌枚数修正
- CH-110: 自家の `chi / pon / kan` 後に手牌右端の draw marker が残って 1 枚多く見える問題を修正した。`N` 処理で consumed 牌除去後に `last_draw_tiles_136[seat]` を必ず `None` へ戻し、副露後は concealed hand だけを表示する。

## 2026-04-09 live 再描画状態同期
- CH-104: `DETAIL` / `LAYOUT` 操作中の即時 redraw と live capture thread の共有 state 読み書きが競合し、`tracker.discards` や round snapshot を途中状態で UI が走査して live 更新が止まったように見える問題を修正した。`CaptureState` に live lock を追加し、capture 側は parser mutation を lock 配下で実行、renderer 側は 1 redraw ごとに lock 下で immutable snapshot を組み立てて描画するよう更新した。あわせて refresh token poll の例外も握りつぶさず再スケジュール継続する。

## 2026-04-09 プレイヤーアラートドット
- CH-105: 他家パネルの `ALERT` 欄を実データ化し、`Remain` が `8.0` 未満で黄丸、`6.0` 未満で赤丸を表示するよう更新した。あわせて、無筋 + 愚形補正込みで最新打牌が `9%` 以上の危険牌になった他家には紫丸を追加表示する。紫丸は最新打牌ベース、Remain の黄/赤丸は現時点の `Remain` 値に追従して出し分ける。

## 2026-04-09 詳細メモ DB 分離
- CH-103: `DETAIL` メモの read/write が `hanchan_master` / `kyoku_master` の header migration や別スレッドの DB 書き換えに巻き込まれないよう、`load_player_profile()` / `save_player_profile_user_memo()` は `player_profiles` だけを bootstrap するよう更新した。あわせて memo load 失敗時も editor 自体は開き、status に error を出したまま再入力できるようにした。

## 2026-04-09 卓種別 DB 追加
- CH-102: `GO.type` の卓種 bitmask を capture state へ保持し、`hanchan_master` / `kyoku_master` / `discard_fact` に `go_type`, `go_type_hex`, `room_class_code`, `room_class_label` を保存するよう更新した。`source_url` に `gm-XXXX` がある既存 CSV は schema rewrite 時に卓種列を backfill する。

## 2026-04-09 REINIT 危険度メタデータ
- CH-101: `REINIT` / `INITBYLOG` の append-only snapshot carry-over で、共有 prefix の discard metadata は従来どおり再利用しつつ、snapshot-only tail discard は `estimated tsumogiri` として初期化するよう更新した。これにより、REINIT 復元後の exact-safe は新旧の既捨て牌を正しく含み、追加分が未知の手出しとして筋 suppressor / またぎ / 一時 safe を過剰更新しない。

## 2026-04-09 完全安全牌拡張
- CH-100: 危険度ロジックの exact-safe 定義を修正し、相手自身の既捨て牌も `0%` 扱いに含めるよう更新した。従来どおり、リーチ後に卓上で通った牌と一時 safe 牌も exact-safe とし、筋線 suppressor と exact-safe の役割は分離したまま維持する。

## 2026-04-09 レイアウト保存修正
- CH-099: `Layout Tuning` の direct drag 保存処理を修正し、再描画時の resolved offset で `component_offsets` を自動上書きしないよう更新した。`Save` は現行 tuning snapshot をそのまま保存し、drag 開始位置だけ現在表示中の resolved offset を使うため、`DISCARD KAMI` を含む side discard panel の調整が次回起動後も保持される。

## 2026-04-09 側副露高さ範囲
- CH-098: `Layout Tuning` の `Side meld height` をさらに長く調整できるよう、`side_meld_height` の slider 最大値を引き上げた。実効上限が `Side discard height` にも抑えられるため、あわせて `side_discard_height` の最大値も同方向へ拡張した。

## 2026-04-09 AI TOP3 履歴
- CH-097: `AI TOP3` パネル表示中に取得した top3 を `(round_id, next_discard_index, hand_key)` 単位で cache し、次の自家打牌 row の `discard_fact.pystyle_top1..3_*` へ保存するよう更新した。`discard_fact` 再 upsert 時も既存の非空 top3 列は blank で消さない。

## 2026-04-09 レイアウトドラッグ
- CH-096: `Layout Tuning` window を開いている間、卓上の `PANEL` / `DISCARD` / `MELD` 矩形を直接ドラッグして preview できるよう更新した。drag offset は `component_offsets` として `csv_db/ui_layout_tuning.json` へ保存し、board 内 clamp と固定領域・component 間の non-overlap 解決を行う。

## 2026-04-07 テンプレート文書運用
- CH-095: `docs/templates/` と `template_workspace/docs/` を更新し、versioned docs の旧版保持、`current.md` pointer 管理、関数 / モジュール graph の正本 / 生成物運用、troubleshooting、analysis、changelog の住み分けを汎用テンプレとして明文化した。`current_doc_template.md`, `troubleshooting_note_template.md`, `source_overview_template.md`, `src_call_graph_template.md` も追加した。

## 2026-04-07 レイアウト調整ラベル
- CH-094: `Layout Tuning` window の `side_discard_extra_height` slider ラベルを `Side discard height` へ変更し、左右河高さの調整項目として分かりやすくした。現行仕様書 `screen_spec_v1.7.md` と `api_spec_v1.7.md` の表記も合わせて更新した。

## 2026-04-07 文書更新
- CH-093: `requirements_v1.7.md`, `api_spec_v1.7.md`, `screen_spec_v1.7.md` を追加し、`wait_tiles_after_discard_mspz` と `Layout Tuning` window の 2 列化を current 正本へ反映した。`project_guide.md`, `source_overview.md`, `folder_structure.md`, `context.md`, `src_call_graph.md`, `docs/mahjong/logic/hand_analysis.md` も合わせて更新した。

## 2026-04-07 テンプレートワークスペース
- CH-092: `docs/templates/` の管理ドキュメント雛形を拡充し、他案件へそのままコピーできる `template_workspace/` を新設した。workspace には `docs/`, `src/`, `tests/`, `assets/`, `cli/`, `logs/`, `analysis_output/` の雛形と Mermaid graph 用の最小セットを含めた。

## 2026-04-07 レイアウト調整範囲
- CH-090: `LAYOUT` tuning の slider 可動域を広げ、パネル寸法、捨て牌牌サイズ、捨て牌スペース、副露帯、副露牌サイズ、プレイヤーパネル配分、tile rank 行間と牌サイズを従来より大きく伸縮できるよう更新した。内部 clamp も同時に広げ、UI 上の最大値・最小値が描画側で頭打ちにならないよう揃えた。

## 2026-04-07 レイアウト調整粒度
- CH-089: `LAYOUT` tuning に、捨て牌牌画像スケール、上下/左右の捨て牌スペース、副露牌画像スケール、上下副露帯高さ、左右副露最小幅、上副露最小幅、プレイヤーパネルの summary/alert 比率、summary 本文上端、tile rank サイズと行間を追加し、preview のまま卓上各領域をより細かく調整できるよう更新した。

## 2026-04-07 比較痕跡読み追加
- CH-088: 比較痕跡ベースで他家読みを整理する `docs/mahjong/logic/comparison_trace_reading_engine.md` を追加し、`ShapeValue / RoleValue / BlockValue / SafetyValue / LocalComboValue` の 5 軸、feature 分類表、4 カテゴリ分類、既存 `danger` / `tenpai_readiness_score` / `hand_value_score` / alert 群への接続先、`danger` へ direct 加点しない原則と限定 bridge 条件を文書化した。あわせて `folder_structure.md`、`project_guide.md`、`source_overview.md`、`opponent_tenpai_readiness.md` の参照導線を同期した。

## 2026-04-04 危険度切り順補足
- CH-087: 卓レイアウトの主要寸法と余白を GUI から微調整できる `LAYOUT` ボタンと tuning window を追加し、slider 変更を即時 preview、`Save` で `csv_db/ui_layout_tuning.json` へ保存して次回起動時も再利用できるよう更新した。
- CH-086: 危険度ロジックに、代表的な切り順ベースの補正を追加した。`ターツ落とし` はまたぎ筋の本数決定段階で `0.7 本` を優先し、最終手出しの `裏筋両面` は `75% / 65% / 60%` の `else if` 乗算補正として同色筋線へ適用するよう更新した。あわせて `mahjong_danger.md`、`project_guide.md`、`source_overview.md` の説明も同期した。
## 2026-04-04 ラグ危険度補足
- CH-085: 危険度ロジックのラグ補正を、安全寄り `0.75` 倍ではなく時間帯別の危険度上昇補正へ置き換え、`1400ms超-2000ms未満` は `120%`、`2000ms-7000ms` は `140%` を掛けるよう更新した。あわせて、base 無筋危険度が `10%` を超える牌だけ、筋線両端の見え枚数合計に応じた `90% / 110% / 120% / 130%` の濃度補正を numerator / denominator 両方へ掛け、そのあとで愚形加算を足すようにした。

## 2026-04-03 ラグフラグ補足
- CH-084: `lag_delay_ms <= 550` の未鳴きラグを新規 `lagged = 6` として分離し、live parser・XML 側再判定・DB分析前提・関連仕様文書を同期更新した。実際に鳴かれた打牌は引き続き `lagged = 2` を維持する。

## 2026-04-03 危険筋文書更新
- CH-081: 鳴き形による筋本数補正と内牌→外牌手出し補正について、要件定義・仕様書・画面仕様・ソースコードコメント・Mermaid グラフを同期更新した。

## 2026-04-03 ライブキャプチャ切り分け追加
- CH-080: live capture 無反応の事例を `docs/operations/troubleshooting/live_capture.md` に記録した。2026-04-03 の原因は parser / GUI ではなく browser の既存 TLS session と keylog 不一致で、browser 完全再起動で復旧した。単独 `tshark` command、`--debug-tags`、`logs/live_capture.log` の見方も同文書へ追加した。

## 2026-04-02 ライブメモリ対策
- CH-072: 画面横幅を半分程度まで狭めたときだけ、牌画像サイズと卓レイアウト主要幅を連動縮小するようにし、通常幅では従来レイアウトを維持したまま対面プレイヤーパネル文字が消えにくいよう調整した。
- CH-073: 牌画像の基準サイズを少し小さくし、盤面表示全体で余白を取りやすいよう微調整した。
- CH-074: `INIT` で局が切り替わったときは、共通 DETAIL 欄などの一時 UI 状態も新局向けに初期化するようにした。
- CH-075: `INIT` は無条件で新局初期化とし、`REINIT` / `INITBYLOG` だけを `kawa` の visible discard 一致率が `80%` 以上のときに current round 再利用するよう整理した。
- CH-076: `UN` の相対席プレイヤー名シグネチャが1人でも変わった時点で、既存の live capture 局面を必ずリセットするようにした。
- CH-077: `INIT` 系を受ける前の途中開始局でも live 可視化は継続しつつ、`started_from_init_like = False` の局は `player_profiles` を含めて CSV DB へ一切保存しないようにした。
- CH-078: websocket payload の tag extraction を強化し、埋め込み bare tag や不完全な `<INIT ...` / `<REINIT ...` も mapping して、`INIT` 系 tag が見えた時点で即座に局面初期化へ進めるようにした。
- CH-079: live capture は GUI と別 thread のまま、line / fragment 単位の例外で止まらないようにし、GUI は `live_update_sequence` の変化を見て即時再描画するよう更新した。
- CH-071: プレイヤーパネル内の相対位置ラベル表示を外し、危険度ランキング文字列は省略記号付きで枠内に収まるように描画を調整した。
- CH-070: `discard_id` を `{kyoku_id}_{discard_indexの3桁}` 形式へ変更し、既存 CSV も新形式へ移行するよう更新した。
- CH-069: 共通 DETAIL 欄を各プレイヤーパネルのボタンで切り替える形へ整理し、プレイヤーパネルへプレイヤー名を追加した。`DETAIL` ボタンは `player_profiles.user_memo` を共通欄内で編集でき、別表示へ切り替える前に保存するよう更新した。
- CH-068: 跨ぎ筋補正を「その手出しのあとに同プレイヤーの手出しが何回入ったか」で `1.0 -> 0.5 -> 0.3` に減衰する形へ揃え、赤5未見え特例を外した。あわせて自家手牌下の分子本数表示を小数第1位へ揃えた。
- CH-066: 危険度ロジックに、前席の未鳴きラグ牌から次席向けの隣筋安全補正を追加し、ラグ牌の隣数牌にかかる筋線へ `0.75` を掛けるよう更新した。補正は筋線重み自体に掛かるため、分子分母の両方へ効く。
- CH-065: 自家手牌画像に、上家・対面・下家の危険度 `%` から計算した「少なくとも1人に当たる側の確率」色補正を追加し、`1 - (1-p1)(1-p2)(1-p3)` を `5% -> 70%` の `無加工 -> 黄色 -> 赤` で反映するよう更新した。
- CH-067: 手牌下の本数表示を撤去し、相手プレイヤーパネルの `SUMMARY` に分母側本数（残り筋本数）と濃い筋ランキングベスト3を `3-6m 0.5 3%` 形式で表示し、対面パネルは横長専用の3列レイアウトで枠内に収めるよう更新した。
- CH-064: 無筋バーの跨ぎ筋補正を `1.0 / 0.5 / 0.3` に更新した。
- CH-063: 無筋バーの一時免除とリーチ後安全牌判定を、対象プレイヤー本人の河ベースの筋計算へ卓全体の打牌窓を重ねる形へ修正し、他家打牌も条件付きで `0%` / 筋 suppression に効くよう更新した。
- CH-062: 無筋バーで、相手が既に切っている牌そのものは常に `0%` としつつ、筋線を潰す牌は `手出し / リーチ宣言牌 / 直近アンカー以後の打牌` に限定する一時免除ロジックへ更新した。
- CH-061: 無筋バーの算出を筋線重みベースへ変更し、牌ごとの危険度を「その牌が含まれる筋線重みの合計 / 全未解消筋線重み合計」で出すよう修正した。
- CH-060: 無筋バーの跨ぎ筋補正について、字牌を含む手出し順全体で新しさが減衰するよう修正し、字牌手出しでも直前の数牌手出しの重みが `1.0 -> 0.5 -> 0.3` と落ちるようにした。
- CH-059: `kyoku_id` を `{半荘ID}_{kyoku_info}` 形式へ変更し、`discard_id` も追従させた。既存 CSV も current schema へ移行した。
- CH-058: DB 初期化や DB 書き込みが失敗しても packet parse と可視化更新は継続するようにし、DB 障害で live 更新が止まらないようにした。
- CH-057: CSV DB を再整理し、`discard_hands` を廃止して手牌 snapshot を `discard_fact` へ統合、打牌時刻を秒精度へ変更し、`kyoku_master` に4人のプレイヤー名と親名を追加した。
- CH-056: CSV DB の schema 更新で旧ヘッダから再書き換えする場合、元ファイルを `csv_db/old/YYYYMMDD/` へ退避してから更新する運用と実装を追加した。
- CH-055: 自家手牌下の筋危険度バーを少し長くし、`30%` 以上で最大長に達する表示へ変更したうえで、`上家 / 対面 / 下家` 順の数値 `%` も併記するようにした。
- CH-054: CSV DB の保存列を見直し、画面表示や分析で使わない補助列は runtime 専用へ戻して、永続化対象を最小限に整理した。
- CH-053: live ラグ自動判定の出力を `0/1` に揃え、`3以上` は XML 牌譜入力または手入力だけで付与する前提へ DB/仕様文書を更新した。
- CH-052: 管理ドキュメント上で、打牌思考時間を `draw -> discard` / `call -> discard` / `REACH -> discard` に整理し、`discard -> call(N)` の鳴き判断時間はラグ側で扱うことを明記した。
- CH-051: live parser が `UN` の相対席プレイヤー名シグネチャ変更や `TAIKYOKU.log` 切替を新半荘として検知し、in-memory state と CSV writer の半荘 context を自動切替するようにした。
- CH-050: 筋本数の base 無筋判定を筋線単位へ修正し、`6m` のような捨て牌があれば `3-6m` と `6-9m` の両筋線を無筋カウントから外すようにした。
- CH-049: `REACH` 打牌の思考時間を `draw/call -> REACH` と `REACH -> discard` に分割し、前半区間を牌画像の下2/4〜1/4帯へ `無加工 → 緑 → 黄色 → 赤` で追加表示するようにした。
- CH-048: 自家手牌の筋本数危険度表示を `%` テキストから 3 本の色バーへ変更し、上家=青、対面=黄色、下家=緑で長さ表示に統一した。
- CH-039: live `tshark` capture のメモリ肥大化対策として packet を逐次処理し、`player_live` / `spectator_live` の `GameState` 履歴を `rounds=4`, `raw_events=4096`, `unknown_tags=256`, `diagnostics=256`, `chats=128` に制限。
- CH-040: live / replay capture の tshark payload 取得を `websocket.payload.text` 優先へ変更し、`text` フィールド由来の `Timestamps,` 前置きや長文 truncation で `UN` / `REINIT` が壊れる問題を修正。任意プレイヤーの capture でも player metadata と手牌 snapshot が復元されるようにした。
- CH-041: 筋ベースの危険度ロジックを `src/logic/danger_suji.py` へ分離し、跨ぎ筋補正つきの `%` 指標を自家手牌の各牌の下へ表示。ロジック文書 `docs/mahjong/logic/mahjong_danger.md` を追加。
- CH-042: DB の現行仕様書を CSV DB 前提へ再同期し、`パケット解析.md` を現在の `docs/integrations/packet_capture.md` 系統へつながる capture 仕様文書として整理した。関連する current / v1.4 文書の参照先も更新。
- CH-043: 思考時間の牌色補正を全体緑寄せから、牌画像の下半分だけにかかる黄→赤グラデーションへ変更した。
- CH-044: 思考時間の色遷移を `無加工 → 黄色 → 赤` へ調整し、上家下家でも回転前牌画像基準で同じルールになるよう明文化した。
- CH-045: 思考時間の色補正は `7秒` で赤到達となるよう上限時間を延長した。
- CH-046: 思考時間の色補正範囲を牌画像の下半分から下1/4へ縮小した。
- CH-047: 思考時間の色遷移を `無加工 → 緑 → 黄色 → 赤` へ再調整した。

| 日付 | 変更 ID | 対象 | 概要 | 作成者 | 備考 |
|------|---------|------|------|--------|------|
| 2026-04-03 | CH-081 | 実装/文書 | 鳴き形別の筋本数 cap と内牌→外牌手出し補正の計算順序を管理文書へ明記し、`danger_suji` のコメントと Mermaid グラフを更新 | codex | `requirements/current.md` `requirements_v1.4.md` `specs/current.md` `api_spec_v1.4.md` `screen_specs/current.md` `screen_spec_v1.0.md` `source_overview.md` `project_guide.md` `src_call_graph.md` `danger_suji.py` `docs/graphs/src/*.mmd` |
| 2026-04-02 | CH-079 | 実装/文書 | live capture は GUI と別 thread のまま、line / fragment 単位の例外で止まらないようにし、GUI は `live_update_sequence` の変化を見て即時再描画するよう更新 | codex | `state.py` `tshark_capture.py` `pcap_replay.py` `main.py` `table_renderer.py` と関連仕様文書を更新 |
| 2026-04-02 | CH-078 | 実装/文書 | websocket payload の tag extraction を強化し、埋め込み bare tag や不完全な `<INIT ...` / `<REINIT ...` も mapping して、`INIT` 系 tag が見えた時点で即座に局面初期化へ進めるよう更新 | codex | `fragment_parser.py` と関連仕様文書を更新 |
| 2026-04-02 | CH-077 | 実装/文書 | `INIT` 系を受ける前の途中開始局でも live 可視化は継続しつつ、`started_from_init_like = False` の局は CSV DB へ保存しないよう更新 | codex | `state.py` `fragment_parser.py` `storage.py` と関連仕様文書を更新 |
| 2026-04-02 | CH-075 | 実装/文書 | `INIT` は無条件で新局初期化とし、`REINIT` / `INITBYLOG` だけを `kawa` の visible discard 一致率が `80%` 以上のときに current round 再利用するよう整理 | codex | `fragment_parser.py` と関連仕様文書を更新 |
| 2026-04-02 | CH-074 | 実装/文書 | `INIT` で局が切り替わったとき、共通 DETAIL 欄などの一時 UI 状態も新局向けに初期化するよう更新 | codex | `table_renderer.py` `main.py` `changelog.md` を更新 |
| 2026-04-02 | CH-073 | 実装/文書 | 牌画像の基準サイズを少し小さくし、盤面表示全体で余白を取りやすいよう微調整 | codex | `tile_images.py` `changelog.md` を更新 |
| 2026-04-02 | CH-072 | 実装/文書 | 画面横幅を半分程度まで狭めたときだけ牌画像サイズと卓レイアウトを連動縮小し、通常幅では従来レイアウトを維持したまま対面パネル文字が消えにくいよう調整 | codex | `table_renderer.py` `tile_images.py` `screen_specs/current.md` などを更新 |
| 2026-04-02 | CH-071 | 実装/文書 | プレイヤーパネル内の相対位置ラベルを撤去し、危険度ランキング文字列が枠外へはみ出さないよう描画を調整 | codex | `table_renderer.py` `screen_specs/current.md` `specs/current.md` などを更新 |
| 2026-04-02 | CH-070 | 実装/文書 | `discard_id` を `{kyoku_id}_{discard_indexの3桁}` 形式へ変更し、既存 CSV も新形式へ移行 | codex | `csv_db_schema.py` `storage.py` `csv_db_design.md` などを更新 |
| 2026-04-02 | CH-059 | 実装/文書 | `kyoku_id` を `{半荘ID}_{kyoku_info}` 形式へ変更し、`discard_id` も追従させて既存 CSV を移行 | codex | `csv_db_schema.py` `storage.py` `csv_db_design.md` `api_spec_v1.4.md` を更新 |
| 2026-04-02 | CH-058 | 実装 | DB 初期化や書き込みが失敗しても packet parse と GUI 更新は継続するようにして、DB 障害で live 更新が止まらないようにした | codex | `tshark_capture.py` `pcap_replay.py` を更新 |
| 2026-04-02 | CH-057 | 実装/文書 | CSV DB を再整理し、`discard_hands` 廃止、手牌 snapshot の `discard_fact` 統合、打牌時刻の秒精度化、`kyoku_master` のプレイヤー名追加を実施 | codex | `csv_db_schema.py` `storage.py` `csv_db_design.md` などを更新 |
| 2026-04-02 | CH-056 | 実装/文書 | CSV DB の schema 更新時に、旧 CSV を `csv_db/old/YYYYMMDD/` へ退避してから現行ヘッダへ書き換えるようにした | codex | `storage.py` `csv_db_design.md` `パケットキャプチャ仕様.md` などを更新 |
| 2026-04-02 | CH-055 | 実装/文書 | 自家手牌下の筋危険度バーを延長し、`30%` 以上で最大長、`上家 / 対面 / 下家` 順の数値 `%` 併記へ変更 | codex | `table_renderer.py` `mahjong_danger.md` `screen_specs/current.md` などを更新 |
| 2026-04-02 | CH-054 | 実装/文書 | CSV DB の保存列を最小化し、画面表示や分析で使わない補助列を runtime 専用へ戻した | codex | `csv_db_schema.py` `storage.py` `csv_db_design.md` `api_spec_v1.4.md` などを更新 |
| 2026-04-02 | CH-053 | 実装/文書 | live ラグ自動判定を `0/1` に揃え、`3以上` は XML/手入力だけで付与する前提へ DB 出力と文書を更新 | codex | `fragment_parser.py` `csv_db_design.md` `specs/current.md` `api_spec_v1.4.md` などを更新 |
| 2026-04-02 | CH-052 | 文書 | 打牌思考時間とリーチ前半思考時間の定義、および `discard -> call(N)` をラグ側で扱う境界を管理文書へ反映 | codex | `csv_db_design.md` `パケットキャプチャ仕様.md` `specs/current.md` `api_spec_v1.4.md` `requirements/current.md` などを更新 |
| 2026-04-02 | CH-051 | 実装/文書 | `UN` 相対席プレイヤー名シグネチャ変更や `TAIKYOKU.log` 切替で live in-memory state と CSV writer の半荘 context を自動切替 | codex | `fragment_parser.py` `state.py` `storage.py` と関連文書を更新 |
| 2026-04-02 | CH-050 | 実装/文書 | base 無筋判定を筋線単位へ修正し、`6m` 捨てなら `3-6m` と `6-9m` を無筋カウントから除外 | codex | `danger_suji.py` `mahjong_danger.md` `source_overview.md` を更新 |
| 2026-04-02 | CH-049 | 実装/文書 | `REACH` 打牌の思考時間を前半 `draw/call -> REACH` と後半 `REACH -> discard` に分割し、前半を下2/4〜1/4帯へ追加表示 | codex | `fragment_parser.py` `state.py` `tile_images.py` `table_renderer.py` と関連文書を更新 |
| 2026-04-02 | CH-048 | 実装/文書 | 自家手牌の筋本数危険度表示を `%` テキストから 3 本の色バーへ変更し、上家=青、対面=黄色、下家=緑で長さ表示に統一 | codex | `main.py` `table_renderer.py` `mahjong_danger.md` `screen_specs/current.md` などを更新 |
| 2026-04-02 | CH-047 | 実装/文書 | 思考時間の色遷移を `無加工 → 緑 → 黄色 → 赤` に再調整 | codex | `table_renderer.py` `screen_specs/current.md` `source_overview.md` を更新 |
| 2026-04-02 | CH-046 | 実装/文書 | 思考時間の色補正範囲を牌画像の下半分から下1/4へ変更 | codex | `tile_images.py` `table_renderer.py` `screen_specs/current.md` `source_overview.md` を更新 |
| 2026-04-02 | CH-045 | 実装/文書 | 思考時間の下半分色補正の上限時間を `5秒` から `7秒` へ変更し、`7秒` で赤到達に調整 | codex | `table_renderer.py` `screen_specs/current.md` `source_overview.md` を更新 |
| 2026-04-02 | CH-044 | 実装/文書 | 思考時間の色遷移を `無加工 → 黄色 → 赤` に調整し、回転前牌画像基準のルールを仕様へ明記 | codex | `table_renderer.py` `screen_specs/current.md` `source_overview.md` を更新 |
| 2026-04-02 | CH-043 | 実装/文書 | 思考時間の牌色補正を、牌全体の緑補正から、下半分だけの黄→赤グラデーションへ変更 | codex | `tile_images.py` `table_renderer.py` `docs/screen_specs/current.md` `docs/architecture/source_overview.md` を更新 |
| 2026-04-02 | CH-042 | 文書/運用 | DB 関連文書を CSV DB 前提へ再同期し、capture 仕様文書を現行の `docs/integrations/packet_capture.md` 系統へ整理 | codex | `csv_db_design.md` `source_overview.md` `project_guide.md` `requirements/current.md` `specs/current.md` などを更新 |
| 2026-04-01 | CH-036 | 陞ｳ貅ｯ・｣繝ｻ隴√・蠍・| live capture / replay 共通の `--tls-keylog` を追加し、既定の TLS keylog パスを `C:\tmp\tls.keys` に変更。`--help` に全実行モードの例を追加 | codex | `tshark_capture.py` / `app/main.py` と関連ドキュメントを更新 |
| 2026-04-01 | CH-035 | 繝峨く繝･繝｡繝ｳ繝・ | 牌番号資料として 136種系 / 37種系 / `〇.png` 対応表を新規ドキュメント化 | codex | `docs/reference/tile_id_reference.md` を追加 |
| 2026-04-01 | CH-033 | 螳溯｣・譁・嶌 | live websocket parser を `player_live` / `spectator_live` / `xml_log` に分離し、観戦 `INITBYLOG` / `WGC` と discard prefix delay heuristic を normal path に統合 | codex | `fragment_parser.py` / `state.py` と関連ドキュメントを更新 |
| 2026-04-01 | CH-034 | 螳溯｣・譁・嶌 | `--test` replay に `--test-tls-keylog` を追加し、`.pcapng` と TLS keylog を別引数で指定してオフライン復号テストできるようにした | codex | `pcap_replay.py` / `app/main.py` と関連ドキュメントを更新 |
| 2025-10-27 | CH-001 | 要件 v1.0→v1.1 | 要件文言を整理し、責務表現を簡潔化 | codex | `docs/requirements/requirements_v1.1.md` を追加 |
| 2025-10-27 | CH-002 | 仕様 v1.0→v1.1 | データモデル、エラー方針、テスト観点を整理 | codex | `docs/specs/api_spec_v1.1.md` を追加 |
| 2025-10-27 | CH-003 | 要件 v1.1→v1.2 | パケット取得と DB 永続化の要件を追加 | codex | `docs/requirements/requirements_v1.2.md` を追加 |
| 2025-10-27 | CH-004 | 仕様 v1.1→v1.2 | `SutehaiTracker`、`tshark`、SQLite 記録仕様を追加 | codex | `docs/specs/api_spec_v1.2.md` を追加 |
| 2026-03-22 | CH-005 | 要件/仕様 v1.2→v1.3 | 卓中心 UI、プレイヤーパネル、詳細情報表示スペースを定義 | codex | `docs/requirements/requirements_v1.3.md` と `docs/specs/api_spec_v1.3.md` を追加 |
| 2026-03-29 | CH-006 | 実装/文書 | パケット処理を `packet_capture.py` と `html_xml_parser.py` に分離し、現行文書を更新 | codex | 現在の `docs/integrations/packet_capture.md` の方針を反映 |
| 2026-03-29 | CH-007 | 文書 | `src` 配下の関数名付き呼び出し関係を `docs/architecture/src_call_graph.md` として追加 | codex | 今後の継続管理対象 |
| 2026-03-29 | CH-008 | 文書/運用 | 呼び出し関係図を Mermaid 正本から画像再生成する運用へ変更 | codex | `cli/render_src_call_graph.ps1` を追加 |
| 2026-03-29 | CH-009 | 実装/文書 | `--mock` なし起動を `tshark` バックグラウンドキャプチャ開始へ変更 | codex | GUI は定期再描画で追従 |
| 2026-03-29 | CH-010 | 実装/文書 | 3見え/4見え集計を `visible_tiles.py`、画面描画を `table_view.py` へ分離 | codex | `LoadImage.py` は互換ラッパー化 |
| 2026-03-29 | CH-011 | 実装/文書 | `app/` `capture/` `ui/` パッケージへ再編し、旧トップレベルを互換ラッパー化 | codex | `state.py` `fragment_parser.py` `storage.py` `tshark_capture.py` `table_renderer.py` `tile_images.py` などへ分割 |
| 2026-03-29 | CH-012 | 実装/文書 | 副露 `N` タグを `capture.meld_decoder` でデコードし、3見え/4見え集計へ副露寄与分を接続 | codex | ポン/チー/明カンの食い牌は捨て牌側と二重計上しない |
| 2026-03-29 | CH-013 | 実装/文書 | 中央局情報パネルの `DORA` 領域にドラ表示牌画像を表示するよう変更 | codex | 通常起動と `--mock` の両方で `dora_indicator_tiles` を表示 |
| 2026-03-29 | CH-014 | 実装/文書 | mock 牌データを unique な 136 牌 ID ベースへ変更し、赤5の枚数制約と 34種集計の正規化を修正 | codex | `visible_tiles.tile37_to_tile34()` の赤5 folding も修正 |
| 2026-03-29 | CH-015 | 実装/文書 | `tile_136` を 0-origin 前提へ戻し、赤5の packet ID を `16` `52` `88` に修正 | codex | `tile136_to_tile37()` と mock allocator の基準値を再調整 |
| 2026-03-29 | CH-016 | 実装/文書 | `--mock` の正本データを `MOCK_*_136` に整理し、UI 渡し直前だけ 37種表現へ変換する構成へ修正 | codex | `main.py` と `mock_data.py` の役割分離、互換 alias 維持 |
| 2026-03-29 | CH-017 | 文書 | 全体像と主要データ構造をまとめた `docs/architecture/project_guide.md` を追加 | codex | README から参照可能に更新 |
| 2026-03-29 | CH-018 | 実装/文書 | `--mock` を固定 83 枚の `tile_136` 入力へ簡素化し、自家手牌13枚・ドラ表2枚・各家捨て牌17枚へ整理 | codex | allocator 廃止、固定入力 + 検証へ変更 |
| 2026-03-29 | CH-019 | 実装/文書 | 論理 37種ID と `assets/tiles` の画像番号ずれを吸収する変換を UI に追加 | codex | 赤牌表示崩れと 34種表示の誤描画を修正 |
| 2026-03-29 | CH-020 | 実装/文書 | 37種ID の正本定義を牌画像番号へ統一し、赤5を `10` `20` `30`、3見え/4見え集計を compact 34種へ分離 | codex | `tile_136 -> tile_37`、34種 folding、詳細表示、関連文書を再整合 |
| 2026-03-29 | CH-021 | 実装/文書 | 34種カウントの代表IDを通常牌側の 37種ID に統一し、`5/10` `15/20` `25/30` を同種として数える形へ簡素化 | codex | `Visible x3/x4` 描画から中間変換を外し、説明文書も同じ表現へ更新 |
| 2026-03-29 | CH-022 | 実装/文書 | `--mock [1-3]` を追加し、1/2/3 パターンでドラ表枚数を切り替えられるように変更 | codex | 数字省略時は 1 パターン目、既存モックは 2 パターン目として維持 |
| 2026-03-29 | CH-023 | 実装 | mock 1 / 3 の捨て牌配列を全面的に入れ替え、3 パターンの見た目差が出るように調整 | codex | 枚数条件と 136 牌 ID 制約は維持、既存配列は 2 パターン目として保持 |
| 2026-03-29 | CH-024 | 実装 | `--test INPUT_PCAPNG` と `--test-interval-ms` を追加し、TLS 復号済み `.pcapng` の tag packet replay を実装 | codex | `src/capture/pcap_replay.py` を追加し、起動導線・仕様書・呼び出しグラフを更新 |
| 2026-03-29 | CH-025 | 実装/文書 | 主要ソースコードへ日本語コメントを追加し、構成・画面・牌表現・README を最新実装へ追従 | codex | `src/app/*` `src/capture/*` `src/ui/tile_images.py` `src/visible_tiles.py` と関連ドキュメントを更新 |
| 2026-03-31 | CH-026 | 実装/文書 | `table_renderer.py` と `mock_data.py` の残存英語コメントを日本語化し、mock 3パターン・`Meld` 構造・raw136正本方針を API/ガイド文書へ追記 | codex | `docs/architecture/project_guide.md` `docs/architecture/source_overview.md` `docs/specs/api_spec_v1.3.md` を現行実装へ再同期 |
| 2026-03-31 | CH-027 | 実装/文書 | 鳴き表示帯、鳴かれ捨て牌の青マーカー、visible 集計の `called` 除外、mock の鳴き/捨て牌整合検証を現行文書へ反映 | codex | `collect_visible_tile_summary()` と副露 full 牌基準へ再同期 |
| 2026-03-31 | CH-028 | 実装/文書 | 捨て牌の赤枠を `called` 表示へ切り替え、4見えの捨て牌と自家手牌に青い丸印を付けるルールへ変更 | codex | 手出し/ツモ切りの明暗ルールは維持 |
| 2026-03-31 | CH-029 | 実装/文書 | `Visible x3` / `Visible x4` の固定グリッドを 1 行 8 枚・最大 3 行へ拡張 | codex | 詳細パネル内の visible セクション高さ配分も調整 |
| 2026-04-01 | CH-030 | 要件/仕様 v1.3→v1.4 | WebSocket タグ解析を `GameState` / `RoundState` 正本、`REINIT` 完全復元、推定フラグ管理、validation/export API 前提へ更新 | codex | `docs/requirements/requirements_v1.4.md` と `docs/specs/api_spec_v1.4.md` を追加 |
| 2026-04-01 | CH-031 | 文書/運用 | パーサ関連文書を v1.4 実装へ同期し、確定/暫定/未確定仕様の分離ルールを `context.md` と補助文書へ反映 | codex | `docs/architecture/source_overview.md` `docs/architecture/project_guide.md` `docs/architecture/src_call_graph.md` `docs/reference/tile_representation.md` `docs/architecture/folder_structure.md` `docs/integrations/packet_capture.md` `docs/architecture/context.md` を更新 |
| 2026-04-01 | CH-032 | 実装/文書 | `--xml-url URL` による本チャン XML 入力を追加し、viewer URL から `log/?...` を解決して XML 牌譜を読み込めるように変更 | codex | `src/capture/xml_url_loader.py` と GUI/文書を更新 |
| 2026-04-01 | CH-037 | 実装/文書 | 打牌から次の `draw` または一致する open meld `call` までの packet arrival 差分が 5ms 以上なら discard をラグ牌として記録し、4見え青丸の左隣へ黄色丸を回転追従で描画 | codex | `fragment_parser.py` / `state.py` / `sutehai.py` / `table_renderer.py` と仕様・要件追補を更新 |
| 2026-04-01 | CH-038 | 実装/文書 | `REINIT` / `INITBYLOG` snapshot の `kawa` が既存 discard 列の prefix を含むとき、手出し/ツモ切りとラグ等の discard metadata を引き継いで差分だけ追加するよう更新 | codex | `fragment_parser.py` と仕様・要件 addendum を更新 |
# 2026-04-03 分析/ロジック文書更新
- CH-082: added `docs/analysis/db_analysis_rules.md` for DB-side baseline filters and `docs/mahjong/logic/opponent_tenpai_readiness.md` for opponent tenpai-readiness logic notes.

## 2026-04-03 v1.5 文書更新
- CH-083: `requirements_v1.5.md`, `api_spec_v1.5.md`, `screen_spec_v1.5.md` を追加し、`current.md` 群を v1.5 へ切り替えた。管理文書として `project_guide.md`, `source_overview.md`, `folder_structure.md`, `src_call_graph.md` も同期更新した。
## 2026-04-07 打牌待ち列追加
- CH-091: `discard_fact` に `wait_tiles_after_discard_mspz` を追加し、実際の打牌後手牌がテンパイなら待ち牌を `mspz` grouped text で保存するようにした。既存 CSV は schema migration で新列へ自動更新される。

## 2026-04-09 牌ランク 0 除外
- CH-111: `Tile rank` が `0.0%` の牌まで候補に含めていたため、既に現物になった牌や表示上ゼロの牌が上位欄に残る問題を修正した。ランキング生成時に、最終表示へ丸めた後も `> 0.0` の牌だけを残すよう更新した。

## 2026-04-09 Push アラート現打牌ゲート
- CH-112: `Push` alert を「各プレイヤーの最新打牌」から常時出し続けるのではなく、場の最新打牌と一致する相手の最新打牌にだけ出すよう更新した。これにより、自家打牌や他家の新打牌を挟んだあとに古い opponent alert が残って見えるズレを防ぐ。

## 2026-04-09 安全手パネル順位
- CH-113: 各他家パネルの `SUMMARY` に、自手から見たその相手への安全牌ランキングを追加した。上パネルは `Line / Safe hand / Tile rank` の 3 列、左右パネルは `Safe hand` を短く差し込む構成にし、表示順位は自手に存在する牌種だけを危険度の低い順でまとめて出す。

## 2026-04-09 安全手 live 手牌同期
- CH-114: `Safe hand` ランキングを panel summary payload の派生 count ではなく、描画中の現在手牌とその per-tile danger bar データから直接再生成するよう更新した。これにより、直前に切った牌が `Safe hand` に残る 1 手遅れ表示を防ぐ。

## 2026-04-11 河マーカー / アラート同期
- CH-125: `pon` の copy 解釈を修正し、上家ポンでも `called_tile_id` と `consumed_tile_ids` が正しく self hand から 2 枚減るよう更新した。あわせて、鳴かれた post-riichi 現物は exact-safe `0%` を維持しつつ筋 suppressor からは除外するよう危険度ロジックを修正した。
- CH-126: pystyle / self-alert 周りを整理し、`draw` の無い post-discard fallback 局面では直前に取得した pre-discard 結果を再利用するよう更新した。`LOW EV` 音は 1 局 1 回、`HIGH EV` は無音、visible dora pill は赤ドラ込みかつ全角数字表示にした。
- CH-127: player-panel alert を拡張し、`Push` は 3 巡保持、手出し現物が出たら緑 `Push解除` へ切り替え、自分に対して押したケースや `8巡目以降の字牌ションパイ` でも発火するよう更新した。加えて `門前`, `思考時間聴牌近`, `染め/対々和 UP`, `両面チー3-7` を追加した。
- CH-128: 河まわりの marker / tint を更新し、`lag=青丸`, `3見え=ピンク丸`, `4見え=紫丸`, `同順合わせ打ち=黄丸`, `最大思考時間=赤ひし形` を表示するよう更新した。`Visible x3/x4` の右詳細では数牌 `3..7` だけをピンク / 紫枠で囲み、self hand の字牌には見え枚数を右上表示する。
- CH-129: same-jun の定義を「先に同じ牌を切った人の次打牌まで」に統一し、マークは後から合わせた discard の側だけへ付けるよう更新した。renderer 実装も active-window 方式へ変更し、same-jun hit 時の redraw stall を避けた。
- CH-130: 合わせ打ち判定を再定義し、「前回自分の打牌から今回までに visible count が増えた牌を切ったか」で見るよう更新した。増加要因には打牌、鳴きで新たに晒された牌、ドラ表を含み、手出し / ツモ切りは区別しない。
- CH-131: 合わせ打ち marker の最終条件を public visible-count ベースへ整理し、private な配牌 / 自摸は除外、自分自身の打牌や self-exposed meld では self flag を立てない one-shot 判定に統一した。あわせて live renderer が使う tracker discard に `round_discard_index` / `event_index` を保持し、`REINIT` 後も marker 順序が崩れないよう修正した。`docs/operations/troubleshooting/live_capture.md` には `tls.keys` が「今の websocket 接続そのもの」の secret を含んでいないと後起動では復号できない前提を追記し、player-panel label は `染/対々 UP` に短縮した。
- CH-132: 表示系文書を整理し、`docs/screen_specs/alert_flag_reference.md` を追加した。画面仕様 / 要件 / API spec の current pointer を `v2.0` へ更新し、`SELF`, visible dora pill, player-panel alerts, river markers / tint, `Visible x3/x4` 補助枠, self-hand honor visible counts をひとまとまりの screen-side reference として管理するよう変更した。
- CH-133: 版管理された要件 / API spec / 画面仕様の旧版ファイルを、それぞれ `docs/requirements/old/`, `docs/specs/old/`, `docs/screen_specs/old/` へ移動した。最新版 `v2.0` と `current.md` 群だけを各フォルダ直下に残し、継承パスと管理ドキュメント参照も `old/` 前提へ更新した。
- CH-134: `門前 N` の赤段階について、一時免除を考慮しない `Remain < 13.0` では dot 色を赤から紫へ切り替えるよう更新した。alert key と音優先度はそのまま維持し、表示だけを紫強調へ変更した。
- CH-135: 合わせ打ち marker は renderer 側で refresh token 単位に cache し、live snapshot が保持する round events も `dora` 公開分だけへ絞って、marker 計算が redraw ごとに全 event stream を組み直さないよう更新した。あわせて河の赤 tint 条件を拡張し、`鳴き手出し` が出た以降の手出しも赤み対象へ追加した。
## 2026-04-11 プレイヤーパネル線表示
- CH-136: 各他家パネルの `SUMMARY` 内 `Line` 表示を文字列から実牌画像ベースへ変更し、両端牌を小牌画像で並べたうえで `line weight`, `%`, そのスートの残筋本数 (`m/p/s`) を同じ行へ併記するよう更新した。logic 側は renderer 向けに構造化された `top_line_summaries` payload を持ち、renderer 側は旧 `top_line_labels` からも後方互換で復元できる。
- CH-137: 他家プレイヤーパネルの `Line` / `Safe hand` / `危険ランク` の行ピッチを同系統に揃え、fallback の `KAMI` / `SHIMO` / `TOIMEN` 名は panel 本文では描かないよう更新した。fallback 名が隠れる局面では `Remain` と各ランキング見出し/行も上へ詰めて、summary 領域の縦余白を減らす。
- CH-138: 他家プレイヤーパネルの `BUTTONS` を `DETAIL` / `STATUS` / `プレイヤー補正` の 3 つへ整理し、未実装 2 ボタンは placeholder として共通 detail area を占有するだけにした。長いラベルでも縦横パネル内に収まるよう、ボタン文字列は幅に合わせて省略表示する。
- CH-139: 他家プレイヤーパネルに `SCORE` セクションを追加し、自家基準の点差 (`自家差`) を常時表示するよう更新した。あわせて点差の下に `条件表示` ボタンを置き、共通 detail area では placeholder として切り替えられるようにした。
- CH-140: 河のラグ marker 色を調整し、単独ラグは従来どおり青丸、同一牌で `2人以上` がラグっているケースは緑丸で表示するよう更新した。
- CH-141: 河の緑ラグ marker を `pon-lag-likely` 扱いへ広げ、同一牌で `2人以上` ラグっているケースに加えて、その打牌時点の自分手牌 snapshot ではチー/ポンできない lag も緑丸に寄せるよう更新した。共通 detail area には `青丸` / `緑丸` の切替ボタンを追加し、それぞれの意味をトグルで確認できるようにした。
- CH-142: 対面の横長プレイヤーパネル `SUMMARY` について、本文の開始位置を少し上へ詰め、`Remain` と各ランキング列がより上寄せで表示されるよう調整した。
