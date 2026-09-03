# CSV DB 設計

更新日: `2026-05-24`

## 基本方針

- 保存先は `csv_db/`。
- 定義元は `src/capture/csv_db_schema.py`。
- runtime 正本は `GameState` / `RoundState` / `CaptureState` であり、CSV は分析と後続参照のための永続化。
- 現行の卓種正本は `room_class_label`。legacy の `go_type`, `go_type_hex`, `room_class_code`, `kyoku_info` は読み取り補完対象。

## ファイル

### 単独ファイル

- `hanchan_master.csv`
- `kyoku_master.csv`
- `player_profiles.csv`

### 月別ファイル

- `discard_fact_YYYYMM.csv`
- `discard_context_YYYYMM.csv`
- `agari_fact_YYYYMM.csv`

## `hanchan_master.csv`

1 半荘 1 行。

カラム:

- `hanchan_id`
- `room_class_label`
- `seat0_player_name`
- `seat1_player_name`
- `seat2_player_name`
- `seat3_player_name`
- `source_url`

用途:

- URL import 済み半荘の同定
- XML import 時の player signature 照合
- プレイヤー別分析での所属卓集計

- live capture では `TAIKYOKU.log` / `state.game_id` から `https://tenhou.net/0/?log=...` を `source_url` へ保存する。INIT 時点で log id が未到着の場合も、後続の DB 対象イベントで空の `source_url` を backfill する。

## `kyoku_master.csv`

1 局 1 行。

カラム:

- `kyoku_id`
- `hanchan_id`
- `room_class_label`
- `honba`
- `kyotaku`
- `oya_rel`
- `seat0_player_name`
- `seat1_player_name`
- `seat2_player_name`
- `seat3_player_name`
- `oya_player_name`
- `seat0_first_row_avg_thinking_time_ms`
- `seat1_first_row_avg_thinking_time_ms`
- `seat2_first_row_avg_thinking_time_ms`
- `seat3_first_row_avg_thinking_time_ms`

`seat0..3_first_row_avg_thinking_time_ms` は、各席の当該局の1段目（席ごとの先頭6打牌）に記録された `thinking_time_ms` の平均値を ms 単位で保存する。まだ打牌がない、または有効な思考時間がない席は空欄にする。

## `discard_fact_YYYYMM.csv`

1 打牌 1 行。

主なカラム:

- `discard_id`
- `kyoku_id`
- `hanchan_id`
- `room_class_label`
- `player_rel_seat`
- `player_name`
- `discard_tile_136`
- `discard_tile_37_text`
- `tsumogiri_flag`
- `discard_epoch_s`
- `thinking_time_ms`
- `thinking_time_before_reach_ms`
- `lagged`
- `lag_delay_ms`
- `seat0..3_hand_tiles_136_json`
- `seat0..3_hand_tiles_37_text`
- `shanten_after_discard`
- `shanten_normal_after_discard`
- `shanten_chiitoitsu_after_discard`
- `wait_tiles_after_discard_mspz`
- `ryanmen_fixed_flag`
- `pystyle_top1..3_tile_37_text`
- `pystyle_top1..3_expected_value_text`

分析例:

- 打牌後シャンテン数と思考時間
- ラグ時間分布
- pystyle top3 の履歴
- プレイヤー別傾向

## `discard_context_YYYYMM.csv`

打牌時点の場況 snapshot。

カラム:

- `discard_id`
- `kyoku_id`
- `scores_json`
- `reach_state_json`
- `dora_indicators_136_json`
- `melds_by_seat_json`
- `rivers_by_seat_136_json`
- `visible_tile_counts_34_json`

## `agari_fact_YYYYMM.csv`

和了イベント 1 件 1 行。

主なカラム:

- `agari_id`
- `kyoku_id`
- `hanchan_id`
- `room_class_label`
- `winner_rel_seat`
- `winner_name`
- `from_rel_seat`
- `from_name`
- `is_tsumo`
- `winning_tile_136`
- `winning_tile_37_text`
- `deal_in_discard_id`
- `estimated_danger_percent`
- `danger_estimate_source`
- `agari_state_snapshot_json`

## ID

- `hanchan_id`: `YYYYMMDDHHMMSS`。`INITBYLOG` fallback は末尾 1 桁を `k` にする。
- `kyoku_id`: `hanchan_id + "_" + kyoku_info`
- `discard_id`: `kyoku_id + "_" + discard_index(3桁)`

## 所属卓集計

`scripts/analyze_player_shanten_thinking.py` は `hanchan_master` を使って player ごとの所属卓を出す。

処理:

1. `seat0..3_player_name` を縦持ちにする。
2. `player_name + hanchan_id` で重複除去する。
3. `room_class_label` の件数を集計する。
4. 最頻卓を `table_affiliation` として出力する。

## schema 変更時

- `src/capture/csv_db_schema.py` を正本として更新する。
- legacy optional columns は `src/capture/storage.py` で互換読み取りする。
- 変更後は `docs/specs/current.md` と本ファイルを更新する。
