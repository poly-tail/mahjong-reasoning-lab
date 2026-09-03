# ライブ描画トラブルシュート・対策履歴

最終更新: 2026-09-03

## 2026-09-03 heavy suji / 危険度計算中の表示保持

症状: 河、手牌、副露などの即時データが進んだ直後、heavy suji / 危険度 worker の完了を待つ間に他家 side panel が `Remain: ...` へ戻り、自家手牌の危険度棒も一時的に消える。

原因:

- 完了済み `LiveSujiComputationBundle` が同一局でも最新 input signature と異なる場合、表示 fallback として採用していなかった。
- fast snapshot は手牌状態が変わると `hand_danger_percentages` を空にしていた。
- その中間 payload が side panel / hand の表示 signature を変え、既存 Canvas item を loading / 空表示で置き換えていた。

対策:

- 同一 `round_identity` の直前完了 bundle を、次の bundle が pending / in-flight の間も表示専用 fallback として保持する。
- fallback の手牌危険度は旧 `hand_tiles` から現在手牌へ牌 ID と同牌内の出現順で再対応付けし、対応元のない牌には空 metric を置く。
- input signature が古い fallback は current result とみなさず、最新 job の enqueue と `1 in-flight + pending 1` coalescing を継続する。
- 新 bundle 完了時は async subtoken を進め、side panel / hand / analysis overlay だけを async-only partial refresh でまとめて差し替える。base river / table frame は削除・再描画しない。
- stale bundle は自動打牌や alert 音声の新規判定へ使わない。保持または再表示だけで音声 transition を発生させない。

境界:

- 完了値がまだない初回計算だけ loading / 危険度棒なしを許容する。
- 新局では前局 bundle を持ち越さない。
- 計算中は現在の河・手牌と直前完了分析が一時的にずれるが、空白に戻すより直前情報の継続表示を優先する意図的な表示仕様である。

確認:

- `test_async_live_table_snapshot_provider_defers_async_only_token_until_heavy_publish`
- `test_fast_live_table_snapshot_remaps_previous_hand_danger_for_same_round`
- `test_fast_live_table_snapshot_does_not_reuse_analysis_across_rounds`
- `test_request_live_suji_bundle_reuses_previous_same_round_bundle_as_fallback`
- `test_request_live_suji_bundle_does_not_reuse_previous_bundle_across_rounds`
- `test_build_live_table_snapshot_keeps_previous_bundle_after_lag_metadata_changes`
- `test_build_live_table_snapshot_remaps_fallback_danger_to_current_hand`
- `test_betaori_auto_waits_for_current_hand_danger_bundle`

## 2026-07-26 cached table-frame river z-order invalidation

症状: 副露の瞬間に既存の捨て牌が複数見えなくなり、画面上の REINIT ボタンを押すと戻る。

2026-08-05 追記（原因の要約）: 副露データや河履歴が消えたのではなく、副露で meld が増えた際の table frame 再作成に対して、河 layer のキャッシュ無効化が連動していなかったことが原因。後から生成された不透明な discard zone が既存の河牌を前面から覆った一方、河牌側は Canvas item と表示 signature が残っていたため cache hit となり、再描画されず「消えた」ように見えていた。REINIT で戻ったのは、履歴を復元したからではなく、render cache が空になって河牌が frame より後に作り直され、z-order が正常化したため。

原因:

- `LiveRiverStore` / snapshot / renderer cache の河配列は縮んでおらず、Canvas image item 自体も残っていた。
- cached-layout redraw で meld が変わると table frame cache が miss し、`_draw_table_frame()` が opaque な discard zone rectangle を新規作成する。
- Tk Canvas は後から作った item が前面に来るため、新しい discard zone が既存の base river item を覆った。
- 直後の `_draw_discards()` は既存 slot の表示 signature と Canvas image tag が有効なため cache hit と判定し、背面に隠れた牌を再作成しなかった。
- 手動 REINIT は discard render cache / image refs を空にし、全 slot を table frame より後に作り直すため、重なり順だけが正常化していた。

対策:

- table frame cache miss を base river / analysis overlay の invalidation 境界とする。
- frame 再作成前に `live_async_discards` / `live_discard_analysis_overlay` と discard render cache / image refs / overlay signature / geometry を破棄する。
- 同じ redraw 内で `table_frame -> base river -> analysis overlay` の順に再作成する。
- frame cache hit の通常 redraw は per-slot cache を維持する。副露後の自動 REINIT は行わない。

確認:

- `test_table_frame_redraw_invalidates_cached_discard_layers`
- `test_cached_layout_frame_redraw_invalidates_discards_before_repaint`
## 2026-07-01 strict render/capture split

- Base river layer と analysis overlay layer を分ける。red / brown / four-visible tint、見え枚数 marker、Push `P`、同順合わせ打ちは `live_discard_analysis_overlay` tag だけで差し替える。
- async-only refresh は通常 `_draw_discards()` を呼ばず、`_draw_discard_analysis_overlays()` だけで河位置連動の計算結果を更新する。`live_async_discards` tag が async-only で delete されている場合は regress。副露直後の Canvas item 欠落検知時は async-only refresh を中断して通常 redraw へ戻す。
- full redraw 境界だけが `live_async_discards` 全体 tag を削除し、cached-layout redraw は per-slot signature と Canvas item tag の生存確認で変化のない base 牌を再利用する。Canvas item が消えていれば cache hit でもその slot を再描画する。
- 副露 `call` event の redraw / async-only refresh 後だけ、`discard_map` に残る slot の Canvas image item 欠落を明示検査する。redraw / async-only 経路とも、欠けを見つけた時点で同じ refresh 内の `_draw_discards()` 差分再実行は行わず、通常 redraw queue へ戻して `UI called discard canvas repair deferred` を `logs/live_capture.log` へ出す。
- suji / red tint worker job は共有 `CaptureState` を持たず、`LiveAnalysisSnapshot` だけを持つ。worker-local facade から計算し、tracker / capture state / base river layer へ書き戻さない。
- REINIT / INITBYLOG / spectator WGC の `kawa` 同一局判定は exact 136 ID ではなく tile34 牌種で比較する。
- spectator WGC / INITBYLOG でも同一局と判定できる場合は existing round を再利用し、`round_state.discards` を短縮しない。
- renderer の per-round cache は履歴復元元ではないが、同一局の full redraw に短い `discard_map` が来た場合は Canvas base river layer を display-only で保持する。projection から消えた slot は `called=True` 黄色枠として残し、`round_state.discards` / tracker へ書き戻さない。
- `INIT` / `INITBYLOG` / `WGC` wrapper 付き `round_identity` は underlying round id が同じなら同一局の projection として扱い、base river cache を破棄しない。cached-layout redraw でも `_draw_discards()` 前に `_merge_discard_map_with_round_cache()` を通す。identity 判定に失敗しても、前回 base river があり現在入力が短い非空 `discard_map` なら同一局疑いとして display-only merge する。`current_total == 0` かつ identity が変わった場合だけ、新局初期 reset として扱ってよい。
- `called=True` の保持 slot は、同じ牌種の後続 uncalled visible discard を消費しない。

## 2026-07-18 cached snapshot の stable discard restore

- `CaptureState.live_stable_discard_map` は、最後に `LiveRiverStore` 由来で安全に発行できた表示用 `discard_map` copy として使う。
- 同一 `LiveRiverStore.epoch` 内では、短い snapshot で stable map を上書きしない。
- cached `LiveTableSnapshot` が古い/短い `discard_map` を返す場合だけ、stable map で表示用 `discard_map` を補強する。
- capture state lock が副露処理中などで busy の場合も、stable copy の optimistic read だけで短い cached snapshot を補強する。
- stable map は `LiveRiverStore` / `RoundState.discards` / `tracker.discards` へ書き戻さない。
- 復元時は `logs/live_capture.log` に `Live snapshot stable discard restore` を出す。

## 2026-07-18 called discard Canvas item repair

- `LiveRiverStore` / snapshot の配列に残っているのに Canvas item だけ消えるケースを、副露 `call` event 後だけ検知する。
- snapshot publish lag で UI が `call` frame を描けず、次の `discard` frame として処理する場合がある。このため `LiveTableSnapshot.recent_event_types` に `call` が残る間も副露直後の復元 context として扱う。
- 検査対象は `discard_map` に存在する最大18枚/席の `live_async_discards_<seat>_<index>` image item。
- 欠けがなければ何もしない。redraw 経路で欠けがあれば `_draw_discards()` を差分再実行し、既存 cache hit slot は skip しつつ欠けた slot だけ戻す。async-only 経路では欠けを見つけた時点で通常 redraw へ戻す。
- async-only refresh は引き続き `live_async_discards` 全体 tag を削除せず、欠け検知時も base river を直接復元しない。通常 redraw へ戻して既存の base river 描画経路に合流する。
- 通常 redraw queue へ戻す時は `UI called discard canvas repair deferred` に missing key、round identity、refresh token を残す。直接修復 helper の `UI called discard canvas repair` は production refresh path では使わない。

## 2026-06-30 async-only refresh と副露河保持

- live async-only refresh は通常 side panel / hand overlay / alert 表示だけを更新し、`_draw_discards()` を呼ばない。副露直後の Canvas item 欠落検知時は async-only refresh を中断して通常 redraw へ戻す。
- async-only refresh では `partial_snapshot.discard_map` を河描画へ流し込まず、`LiveAsyncRenderState.discard_map` の既存コピーを維持する。
- `live_async_discards` 全体 tag を削除できるのは full redraw だけ。cached-layout redraw の個別 slot 差し替えは通常の河描画経路に限定する。
- `N` 処理は鳴かれた discard の削除・短縮を行わず、exact 136 ID がずれても同種牌の最後の未鳴き discard を metadata-only で `called=True` / `lagged=2` にする。
- 鳴かれた捨て牌は黄色枠として表示する。

ライブ対局中の卓描画、捨て牌、サイドパネル、アラート表示まわりの調査メモ。
特に「描画を止めない」「捨て牌を歯抜けにしない」「サイドパネルをチカチカさせない」ための対策履歴を残す。

## 現行結論: 捨て牌履歴の正本

2026-07-01 時点では、副露 / カン後の河欠落対策を capture 履歴正本と renderer 表示保護に分けて扱う。

- `GameState.live_river_store` / `CaptureState.live_river_store` を live base river の捨て牌履歴正本にする。`RoundState.discards[seat]`、`RoundState.discard_ledger`、`tracker.discards` は互換 / 派生 view であり、正史ではない。
- `tracker.discards` は guarded append-only map/list であり、通常処理では `clear` / `pop` / `del` / 短い代入を拒否する。許可される reset context は live `INIT` と明確な別局 `REINIT` だけ。
- `N` 処理は鳴かれた discard を削除せず、`called=True` と call lag metadata を付ける。
- Bridge `riverEntriesBySeat` は browser に見えている lossy projection なので、既存局では `LiveRiverStore.store_projection_only(BROWSER_BRIDGE)` と `RoundState.browser_visible_river_projection` に別保管し、`live_river_store` / `round_state.discards` へ merge しない。
- REINIT / WGC / INITBYLOG の `kawa` は同一局または別局不明なら projection-only とし、base river へ merge / append しない。非空 base river を reset できるのは、実際の `parse_init()` と confirmed different round の `parse_reinit()` が `allow_non_empty_clear=True` を明示した場合だけである。bridge / WGC / INITBYLOG / packet-first / live resync は `INIT_NEW_ROUND` authority 名義でも非空 river を消せない。
- live `INIT` は復帰判定なしの authoritative full reset として扱い、既存 base river / tracker / stable discard map / round UI state を前局から引き継がない。DB async persist worker / queue は reset 対象ではなく、同一半荘の `game_id` / 卓種 / player metadata は保持する。
- live snapshot builder は `LiveRiverStore.snapshot_by_seat()` から表示用 `discard_map` を作る。worker thread は `LiveAnalysisSnapshot` だけを読み、共有 `CaptureState` を持たない。
- renderer の per-round cache は履歴復元元ではない。`CaptureState.live_stable_discard_map` は `LiveRiverStore` 由来で最後に安全に発行できた表示用 copy であり、同一 `LiveRiverStore.epoch` 内で cached snapshot が古い/短い `discard_map` を返す場合だけ表示用 `discard_map` を補強する。renderer の per-round cache は同一局の full redraw に短い `discard_map` が来た場合だけ、Canvas base river layer を display-only で保持する。
- `LiveRiverStore` / `RoundState.discards` / `tracker.discards` のいずれかに既存 discard がある場合、live `INIT` 以外の `reset_live_session()` は `current_round` / `rounds` / `tracker.discards` / `live_stable_discard_map` を消さない。`_rebuild_tracker_from_round()` も store を優先し、短い `RoundState.discards` projection から tracker を短縮しない。
- `INIT` は capture state の局開始境界である。ただし renderer の base river cache / live discard history 判定では `INIT` wrapper そのものだけを reset 根拠にしない。空の `discard_map` を伴う identity 変化は新局初期 reset として扱えるが、短い非空 projection は同一局疑いとして保持する。
- 2026-06-19 から 2026-06-26 の stable store / capture history 補完は履歴として残すが、現行の `live_stable_discard_map` は `LiveRiverStore` 由来 copy の表示用補強に限定する。renderer per-round cache は履歴補完ではなく表示短縮防止だけに限定する。

## 対象

- `src/app/main.py`
  - `LiveTableSnapshot`
  - `build_live_table_snapshot`
  - `build_fast_live_table_snapshot`
  - `AsyncLiveTableSnapshotProvider`
- `src/ui/table_renderer.py`
  - `create_canvas`
  - `_render_table`
  - `_render_table_using_cached_layout_if_possible`
  - `_redraw_live_async_regions_if_possible`
  - `_draw_discards`
  - `_redraw_side_panels_if_needed`
- 関連テスト
  - `tests/test_live_snapshot_cache.py`
  - `tests/test_discard_borders.py`
  - `tests/test_player_panel_alerts.py`

## 症状

### 1. ライブ描画が重く止まる

- 巡目が進むと画面更新が数秒止まる。
- 捨て牌更新まで重いsnapshot計算待ちに巻き込まれる。
- `logs/live_capture.log` に `Live snapshot publish lag` が継続して出る。

### 2. 捨て牌が歯抜けになる

- 序盤に出ていたはずの河牌が途中で消える。
- スクショ上では、同じ河の中で一部スロットだけ空白になる。
- 最初は `PhotoImage` 参照解放を疑ったが、主因は別。

### 3. サイドパネル、特にアラートがチカチカする

- 後追いsnapshotの合間でアラート表示が一瞬消える。
- `player_alert_indicators_by_seat` が `非空 -> 空 -> 非空` と揺れ、side panel signatureが変わって再描画される。

### 4. 2段目以降のPマークが消える

- 現行仕様では、河の `P` は各席の1段目（捨て牌 local index 0〜5）には表示しない。
- Push判定があり、local index 6 以降の対象牌にも `P` が出ない場合だけ描画障害として調査する。

## 原因メモ

### snapshot publish lag

正式snapshotは以下をまとめて持つ。

- `discard_map`
- 赤tint
- 筋/Remain
- Push alert
- player alert indicators
- 同巡/合わせ打ち
- table situation score

この正式snapshotのpublishが遅れると、UIが古いsnapshotを使い続ける。
描画だけ先に進めたい場面でも、重い計算が混ざると河更新まで遅れる。

### 歯抜けの主因

原因は捨て牌配列の参照解放ではなく、短い `discard_map` が描画に入った時の削除処理。

差分描画では `_draw_discards()` が前回描画済みの `(seat, local_index)` を `discard_render_cache_by_key` に持つ。
今回の `discard_map` に存在しないキーは stale として削除していた。

さらに、フル再描画では次の流れでより強く発生する。

1. snapshot publish が遅れる。
2. 一瞬短い `discard_map` が来る。
3. そのタイミングで `_render_table()` のフル再描画に入る。
4. `_LIVE_ASYNC_DISCARD_TAG` を全消しする。
5. `_reset_discard_render_cache()` で河描画キャッシュも消す。
6. 短い `discard_map` だけで描き直す。
7. 前回描画済みだった序盤牌が戻らず、歯抜けに見える。

差分描画だけで stale delete を保守的にしても、フル再描画経路では全消し後に短い入力で描くので不十分だった。

### サイドパネル点滅の主因

`_redraw_side_panels_if_needed()` はsignature一致なら再利用するが、signatureに以下が含まれる。

- `opponent_suji_panel_summaries`
- `player_push_alert_percentages`
- `player_alert_indicators_by_seat`
- safe rank labels
- visible summary

後追いsnapshotの合間でアラートが空になるとsignatureが変わり、side panelが消して描き直される。
アラート自体も一瞬消えるため、チカチカして見える。

## 対策履歴

### 2026-06-19: fast snapshot導入

目的: 重い正式snapshotを待たず、描画に必要な最低限を先に出す。

実装:

- `build_fast_live_table_snapshot()` を追加。
- `AsyncLiveTableSnapshotProvider.current_snapshot()` は `latest_fast_snapshot` を優先。
- fast snapshotは以下をライブから即時反映する。
  - 河
  - 手牌
  - 副露
  - ドラ
  - 局情報
  - 手出し/ツモ切り
  - 思考時間
  - ラグ情報
- 以下は同一局なら前回正式snapshot値を持ち越し、後追いで更新。
  - 筋/Remain
  - 赤tint
  - Push alert
  - player alert indicators
  - table situation score
  - 同巡/合わせ打ち

確認:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_live_snapshot_cache.py
```

### 2026-06-19: fast snapshotの河を「安定prefix + ライブ直近tail」に変更

目的: ライブ河が一瞬短くなっても、既に安定している古い河を消さない。

実装:

- `LIVE_FAST_DIRECT_DISCARD_TAIL_COUNT = 3`
- `_merge_stable_snapshot_discards_with_live_tail()`
- `_merge_snapshot_discard_map_with_live_tail()`

方針:

- 古い捨て牌は正式snapshot側を維持。
- 直近3枚だけライブtracker側で上書き/追記。
- ライブ河が短い場合、同一局なら正式snapshot側を残す。

確認:

- `test_fast_live_table_snapshot_preserves_stable_discards_when_live_is_shorter`
- `test_fast_live_table_snapshot_uses_live_tail_for_recent_discard_metadata`

### 2026-06-19: Pマークの1段目抑制を撤廃

> この節は当時の対策履歴。2026-09-03 の表示仕様変更で、各席の1段目を非表示にする local row gate を意図的に再導入した。現行境界は `test_push_discard_marker_starts_from_second_river_row` と `test_push_discard_marker_applies_local_row_gate_before_global_index_match` で固定する。

目的: Push判定がある捨て牌なら、河の1段目でもPを表示する。

原因:

- `_should_draw_push_discard_marker()` に「local indexが1段目なら描かない」条件が残っていた。
- global discard indexではPush判定対象でも、1段目だと表示されなかった。

対策:

- local row gateを撤廃。
- global discard indexがmarker対象なら表示。

当時の確認（現行テストでは置換済み）:

- `test_push_discard_marker_draws_on_any_river_row`
- `test_push_discard_marker_uses_global_index_without_local_row_gate`

### 2026-06-19: 差分描画中のstale deleteを保守化

目的: 差分描画中に短い `discard_map` が来ても、前回描画済みの河牌を消さない。

実装:

- `_draw_discards()` で前回cacheの席別枚数と今回入力の席別枚数を比較。
- 今回の席別河が前回より短い場合、stale keyを削除せず保持。
- `last_discard_render_stats["stale_retained"]` を追加。

確認:

- `test_draw_discards_retains_stale_slots_when_live_river_temporarily_shortens`

注意:

- これは差分描画では効く。
- ただしフル再描画では先にタグ全消しされるため、この対策だけでは不十分。

### 2026-06-19: フル再描画前に前回描画済み河で補完

目的: フル再描画で短い `discard_map` が来ても、全消し後に短い河だけで描き直さない。

実装:

- `_discard_list_for_player()`
- `_merge_discard_map_with_previous_render_state()`
- 通常再描画前の `dynamic_discard_map` に補完を適用。
- 現行の `_redraw_live_async_regions_if_possible()` は河を再描画しない。async-only refresh は `LiveAsyncRenderState.discard_map` を維持し、side panel / hand overlay / alert 表示だけを更新する。
- 新局リセット時は `canvas.live_async_render_state = None` にして前局河の混入を防ぐ。

方針:

- 今回の河が前回描画済み河より短い場合、前回の残りスロットを補う。
- 補完した場合、`visible_summary` も補完後の河から再計算する。
- 新局では補完元を破棄する。

確認:

- `test_merge_discard_map_with_previous_render_state_fills_short_full_redraw_input`

### 2026-06-19: 局内河保持マップを追加し、REINITでは破棄しない

目的: `live_async_render_state` が落ちるフル再描画や手動再描画でも、一局中の河データを失わない。

実装:

- `canvas.round_discard_map_cache` を追加。
- `_merge_discard_map_with_round_cache()` で描画前に必ず局内保持マップへマージ。
- 入力 `discard_map` が保持済み河より短い場合、保持済みの末尾を補完して河を縮めない。
- 同じslotの牌なら、手出し/ツモ切り、思考時間、ラグなどの新しいメタ情報は現在入力で上書きする。
- `_round_discard_cache_identity()` で `round_identity` から `snapshot_bootstrap_sequence` を除外し、同一論理局の `REINIT` では保持マップを破棄しない。
- 論理局が変わる `INIT` では `_reset_round_ui_state()` により保持マップをクリアする。

方針:

- `REINIT` は復帰スナップショットなので破壊イベントとして扱わない。
- 復帰後に来るpacket情報は、既存河に追加・上書きしていく。
- UI描画キャッシュや重い計算キャッシュのリセットと、河データの寿命を分離する。

確認:

- `test_merge_discard_map_with_round_cache_survives_missing_render_state`
- `test_round_discard_cache_identity_ignores_reinit_bootstrap_sequence`

### 2026-06-19: サイドパネルアラートの空白ラッチ

目的: 後追いsnapshotの合間でアラートが一瞬空になっても、パネルをチカチカさせない。

実装:

- `PLAYER_ALERT_INDICATOR_EMPTY_HOLD_DISCARD_COUNT = 3`
- `_resolve_player_alert_indicators_for_render()`

方針:

- 非空アラートが来たら即更新。
- 短い空入力なら直近の非空アラート表示を保持。
- `latest_global_discard_index` が保持窓を超えたら空表示を受け入れる。
- 新局ではラッチをリセット。

確認:

- `test_player_panel_alert_indicators_hold_through_short_empty_gap`
- `test_player_panel_alert_indicators_clear_after_empty_gap_window`

### 2026-06-20: REINIT短縮snapshotで河配列を縮めない

目的: パケットで捕まえた打牌配列を描画優先で保持し、短い `REINIT`/復帰snapshotで一局中の河を歯抜けにしない。

原因:

- 通常の `D/E/F/G` 打牌は `round_state.discards[seat]` と `state.tracker.discards[Player(seat)]` に即時appendされていた。
- ただし後続の `REINIT` が現在より短い `kawa0..kawa3` を持つと、同局判定で別round扱いになったり、snapshot側で既存河を置き換えたりしていた。
- その結果、描画側が保持していても上流の河配列/trackerが短くなり、序盤の捨て牌が消えることがあった。

対策:

- `_snapshot_can_reuse_current_round()` で「snapshotが現在河の短いprefix」の場合も同局として扱う。
- `_merge_snapshot_discards_with_previous_history()` で、短いsnapshotや既存prefixと合わないsnapshotは既存のパケット捕捉済み河を保持する。
- 伸びているsnapshotだけを既存履歴へ安全に重ね、描画に必要な河・手出し/ツモ切り・思考時間・ラグ情報を先に守る。

確認:

- `tests/test_live_reinit_bootstrap.py::LiveReinitBootstrapTest::test_reinit_shorter_kawa_does_not_shrink_packet_captured_discards`

### 2026-06-26: 副露/カン後のprojection差分をappend-only化

目的: Bridge `riverEntriesBySeat` や REINIT `kawa` が、鳴かれた捨て牌を抜いた可視河だけを返しても、同一局の `round_state.discards` / renderer cache から既存捨て牌を消さない。

対策:

- 同一局の previous full history を正とし、current projection に存在しない previous discard は `called=True` / `lagged=2` として保持する。
- current projection 側でまだ消費していない visible tail は、保持した previous discard の後ろへ append する。
- `previous=[A]`, `projection=[B]` は `[A(called), B]`、`previous=[A,B]`, `projection=[B,C]` は `[A(called), B, C]`、`previous=[A,B]`, `projection=[C,D]` は `[A(called), B(called), C, D]` になる。
- 同じ局キーの `REINIT` は result 前なら現在roundを再利用し、`kawa` projection を full history の置換として扱わない。

### 2026-06-26: called済みslotが同種の次捨て牌を消費しないよう修正

症状: 前回履歴の `A(called)` の後に、可視 projection が同種の `A(uncalled)` を返すと、tile 種一致で同じ slot と誤認し、後者が append されず河から消える。

対策:

- 保持済み `called=True` slot は、projection 上の uncalled 同種牌を消費しない。
- current/projection 側も明示的に `called=True` の場合だけ同一 called slot として消費する。
- Bridge / REINIT `kawa` / live stable merge / renderer per-round cache で同じ規則に揃えた。

確認:

- `test_bridge_snapshot_merge_appends_visible_tail_after_single_omitted_discard`
- `test_bridge_snapshot_merge_marks_all_mismatched_previous_and_appends_snapshot`
- `test_reinit_projection_appends_visible_tail_after_single_omitted_discard`
- `test_redraw_live_async_regions_keeps_render_state_discard_map`
- `tests/test_called_discard_same_kind_projection_merge.py`

### 2026-06-20: INITなしpacket-first描画を優先

目的: `INIT`/`REINIT` が落ちた、またはまだ来ていない状態でも、捕まえた打牌・副露・リーチ・ドラ情報を一局内の描画配列へ先に入れる。

原因:

- `D/E/F/G` は `INIT` なしでも `ensure_round()` で暫定roundに入り、tracker経由で描画できていた。
- ただし暫定roundの描画identityが全て `((None, None, None, None), 0)` になり、局境界や描画キャッシュの扱いが弱かった。
- 局終了後に次局 `INIT` が落ちた場合、次の打牌がresult済みの前局に混ざり、trackerにも前局の河が残る可能性があった。
- 自己打牌のclient送信パケットは、手牌snapshotが無いと `no_current_round`/`tile_not_in_current_hand` で描画配列に入らなかった。

対策:

- `RoundState.provisional_round_sequence` を追加し、`INIT` なし暫定roundにも安定した描画identityを付ける。
- `draw/discard/call/reach/dora` は、前局がresult済みなら `INIT` を待たず新しい暫定roundを作り、trackerの局内河をクリアしてから追加する。
- 自己打牌client送信パケットは、手牌snapshotが無い暫定roundでは描画優先でappendし、後続のserver echoで既存どおり確定マージする。

確認:

- `test_discard_without_init_builds_drawable_provisional_round`
- `test_discard_after_result_without_init_starts_new_provisional_round`
- `test_client_discard_request_without_init_draws_provisionally`

### 2026-06-20: 局途中の河配列は縮めない

目的: 一局が終わるまでは、描画済み/パケット捕捉済みの河配列を短いsnapshotで縮めない。

追加原因:

- `REINIT` に `kawa` が全く無い、または一部席の `kawaN` が欠けると、runtime reset後にその席の `round_state.discards` が空になる余地があった。
- ブラウザtable snapshot importは `reset_live_session()` で全消ししてから作り直すため、同局中に短いriver snapshotが来ると tracker まで短くなり得た。

対策:

- `REINIT` が同じ局キーかつresult前で `kawa` を持たない場合は、別round扱いにせず現在roundを維持する。
- `REINIT` の `kawaN` が欠けた席は、reset前の `previous_discards` をそのまま戻す。
- ブラウザtable snapshot importは、同局中または短いsnapshotが既存河prefixである場合、既存の長い河を保持してから tracker を再構築する。

確認:

- `test_reinit_without_kawa_does_not_clear_packet_captured_discards`
- `test_reinit_missing_one_seat_kawa_does_not_clear_that_seat`
- `test_same_round_shorter_snapshot_keeps_packet_captured_river`

### 2026-06-20: 次局INITでは河配列とUIキャッシュを初期化

目的: 局途中の保持ガードは `REINIT`/短いsnapshotだけに効かせ、次局の `INIT` では前局河を残さない。

対策:

- `parse_init()` は新しい `RoundState` を作り、`previous_discards=None` のまま tracker を再構築するため、前局河を引き継がない。
- `RoundState.snapshot_event_type` を追加し、空 `INIT` でも `INIT` 由来だと判別できるようにする。
- 局情報が欠けた `INIT` は `("init", snapshot_bootstrap_sequence)` をlogical identityに含め、UIの河キャッシュを前局と同一扱いにしない。

確認:

- `test_init_after_packet_first_round_clears_previous_discards`
- `test_bare_init_changes_live_identity_to_drop_previous_ui_cache`
- `test_round_discard_cache_identity_keeps_bare_init_sequence`

### 2026-06-21: 同一局キーのINITでもUI河cacheを完全reset

症状: `INIT` packet 後に `round_state.discards` と `tracker.discards` は空になっているのに、描画側で前局の捨て牌が復活することがある。

原因:

- `build_live_round_identity()` は `INIT` と `REINIT` のどちらも `(round_id, bootstrap_sequence)` にしていた。
- UI側の `_round_discard_cache_identity()` は `REINIT` 復帰で河を保持するために `bootstrap_sequence` を落として比較する。
- そのため、同じ `round_id`/seed で `INIT` が再度来た場合、UI側では同一局扱いになり、空の `discard_map` に前回の `round_discard_map_cache` を合成していた。

対策:

- `build_live_round_identity()` で `snapshot_event_type in {"init", "initbylog", "wgc"}` の場合は、論理identity側にも `snapshot_bootstrap_sequence` を含める。
- `INIT` は強制リセットとして扱うため、`INIT` wrapper 付き identity から後続 `REINIT` / 通常 snapshot へ移る場合も UI 河 cache は引き継がない。
- spectator系 `INITBYLOG/WGC` でも `snapshot_event_type` を埋め、同じ境界判定を使えるようにする。

確認:

- `test_repeated_init_for_same_seed_drops_previous_ui_cache_identity`
- `test_round_discard_cache_identity_keeps_repeated_init_sequence_for_same_round`
- `test_same_round_discard_cache_identity_rejects_init_to_reinit_round`

### 2026-06-20: snapshot境界でtrackerをround_stateから補修

目的: パケットキャプチャ済みの河が `LiveRiverStore` に残っている限り、描画用の派生 view が短くなっても局途中では描画を欠落させない。

原因:

- 旧実装ではライブ描画の `LiveTableSnapshot.discard_map` を `state.tracker.discards` から作っていた。
- 現行実装では `LiveRiverStore` が base river 正本で、`round_state.discards[seat]` と `tracker.discards` は互換 / 派生 view にすぎない。
- この派生 view がズレると、正本には捨て牌があるのに、描画には短い `discard_map` が渡る。
- その状態で通常描画/差分描画に入ると、以前見えていた序盤の捨て牌スロットが消える。

対策:

- snapshot作成時の表示用 `discard_map` は `LiveRiverStore.snapshot_by_seat()` から作る。
- `_rebuild_tracker_from_round()` は `LiveRiverStore` が非空なら store から tracker を再構築し、短い `RoundState.discards` から tracker を短縮しない。
- 補修時は `mark_live_update()` して、短い古い `cached_live_table_snapshot` をそのまま返さない。
- `_read_live_snapshot_cache_state_locked()` と `_snapshot_live_capture_state()` の両方で正本由来の河を読むため、通常snapshotとfast snapshotの両方に効く。
- `RoundState` や browser projection の方が短いケースでは縮めない。局途中は保持優先で、次局 `INIT` または明確な別局 `REINIT` の作り直しに任せる。

確認:

- `test_fast_live_table_snapshot_repairs_short_tracker_from_round_discards`
- `test_build_live_table_snapshot_repairs_short_tracker_from_round_discards`
- `test_build_live_table_snapshot_ignores_cached_short_tracker_after_round_repair`

### 2026-06-21: 鳴き時のフル再描画で捨て牌を先に戻す

症状: チー/ポン/カンの瞬間に、これまで見えていた捨て牌が一気に消えるように見える。

切り分け:

- `parse_n()` の副露処理では、呼ばれた1枚を `called=True` にするだけで、`round_state.discards` と `tracker.discards` は縮まない。
- `build_live_round_identity()` も副露数では変わらないため、鳴き自体を別局扱いしているわけではない。
- ただし、鳴きで副露表示・見え枚数・アラートが同時に変わるとフル再描画に入りやすい。
- フル再描画は最初に `live_async_discards` タグを消し、その後に重いサイドパネル更新を挟んでから捨て牌を描いていた。
- そのため、実データは残っていても、描画順のせいで河が空白になる時間が表に出る。

対策:

- `_render_table()` のフル再描画順を変更し、`table_frame -> discards -> side_panels` の順で描く。
- サイドパネルやアラートの後追い計算より、卓フレームと河の復旧を優先する。
- パーサ側にも、鳴きで `round_state` / `tracker` / snapshot の河が縮まない回帰テストを追加する。

確認:

- `test_full_render_draws_discards_before_side_panels`
- `test_open_call_marks_called_discard_without_shrinking_live_river`

### 2026-06-21: 鳴き時のcached-layout再描画でも捨て牌を先に戻す

症状: full redraw側を直しても、副露の瞬間に捨て牌が消えるように見えることがある。

原因:

- 通常運用では `_render_table()` ではなく、前回レイアウトを再利用する `_render_table_using_cached_layout_if_possible()` に入ることが多い。
- full redraw側は `table_frame -> discards -> side_panels` に直していたが、cached-layout側はまだ `side_panels -> table_frame -> discards` の順だった。
- 副露は meld/frame/side panel/alert を同時に変えやすく、cached-layout側でサイドパネル処理が先に走ると、河復旧が後回しになって空白時間が出る。

対策:

- `_render_table_using_cached_layout_if_possible()` も `table_frame -> discards -> side_panels` の順に統一する。
- 副露ゾーンや卓フレームの更新直後に河を描き、アラート/サイドパネル更新は後段に回す。

確認:

- `test_cached_layout_draws_discards_before_side_panels`

### 2026-06-21: 復帰map後のライブcapture反映漏れ

症状: ブラウザ卓snapshotで復帰した直後、以後のライブpacketが `CaptureState` には入るのに、描画側が古いsnapshot provider/tokenを見続けて反映されないことがある。

切り分け:

- `_import_tenhou_ui_bridge_table_snapshot()` 後に `D56` を流すと、`state.tracker.discards[Player.JICHA]` と `build_live_table_snapshot()` の `discard_map` は伸びる。
- つまり packet capture -> parser -> live state までは復帰後も動いている。
- 一方、bridge background queue の `kind="map"` 成功分岐は feedback/retry状態だけ更新し、`table_snapshot_reinit_action` を呼んでいなかった。
- `bridge_status_tick` 側で map 結果を drain した場合も、map成功そのものから描画更新要求が出ないため、復帰前の provider token に留まる経路があった。

対策:

- map成功時に `_force_live_snapshot_refresh_after_bridge_map()` を呼び、`table_snapshot_reinit_action` で live snapshot cache/provider を即再初期化する。
- 返ってきた refresh token を `current_refresh_token` と `bridge_snapshot_source_refresh_token` に反映し、bridgeのui_snapshot再取得判定も復帰後の状態へ進める。
- map成功ハンドラ自身から `redraw_action()` を呼び、status tick経由で処理されても描画更新要求が落ちないようにする。

確認:

- `test_drain_bridge_background_result_queue_reinits_live_snapshot_after_map_success`
- `test_live_packet_after_bridge_snapshot_extends_imported_round`

## ログ確認ポイント

### snapshot遅延

```text
Live snapshot publish lag: stale_for=...
Live snapshot build slow: ...
```

これが連続する場合、正式snapshotが描画に追いついていない。
fast snapshotと前回描画済み河の補完で見た目は守り、重い計算は後追いにする。

### 捨て牌描画

```text
UI discards slow: ... stale_deleted=N stale_retained=M ...
UI discards cache repair: missing_image_refs=... missing_image_items=...
```

- `stale_retained > 0`
  - 短い河入力を検出し、前回描画済みスロットを保持した。
- `stale_deleted > 0`
  - 通常の河短縮、新局、REINIT、呼ばれ牌などの可能性を確認する。
- `missing_image_refs/items > 0`
  - Canvas itemまたはPhotoImage参照の復旧描画が走った。

## 現時点の判断

- 捨て牌歯抜けは、`PhotoImage` の参照解放単独ではなく、短い `discard_map` が入った状態での描画削除/全消し再描画が主因。
- 正式snapshotのpublish lagがあるため、描画に使う河は「前回安定状態 + 直近ライブ情報」で保護する必要がある。
- サイドパネルはsignatureに重い後追い情報を含むため、アラートの空白入力をそのまま描画に通すとチカチカする。

## 検証コマンド

関連範囲:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_discard_borders.py tests/test_player_panel_alerts.py tests/test_hand_auto_mode.py tests/test_live_snapshot_cache.py
```

全体:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests
```

2026-06-19時点の確認:

- 関連範囲: `231 passed`
- 全体: `495 passed`

2026-06-20時点の確認:

- 関連範囲: `255 passed`
- 全体: `517 passed`

2026-06-21時点の確認:

- 関連範囲: `223 passed`
- 全体: `519 passed`

2026-06-21復帰後ライブ反映修正時点の確認:

- bridge/import targeted: `42 passed`
- 復帰・snapshot・捨て牌描画関連: `163 passed`
- 全体: `521 passed`

2026-06-21 INIT完全reset修正時点の確認:

- INIT/捨て牌描画 targeted: `93 passed`
- 復帰・snapshot・bridge関連: `165 passed`
- 全体: `523 passed`

2026-06-21 副露cached-layout再描画修正時点の確認:

- 副露/捨て牌描画 targeted: `137 passed`
- 復帰・snapshot・bridge関連: `209 passed`
- 全体: `524 passed`

## 今後の追加調査候補

- `Live snapshot publish lag` が長時間続く時の worker詰まり箇所をさらに分解する。
- `stale_retained` が多発する局面をログから拾い、どの入力源が短い河を出しているか確認する。
- サイドパネルsignatureから、表示に直接関係しない後追い値をさらに分離できるか検討する。
- フル再描画回数が多い場合、`_cached_layout_skip_reason()` と runtime guard reason をログ集計する。
