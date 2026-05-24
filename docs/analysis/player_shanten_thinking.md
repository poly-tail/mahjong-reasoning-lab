# プレイヤー別シャンテン思考時間分析

更新日: `2026-05-24`

## 目的

DB の `discard_fact_*.csv` から、プレイヤーごとに「打牌後シャンテン数」と「思考時間」の関係を見る。相関だけでなく、シャンテン別中央値のばらつきも出し、プレイヤーごとの癖を比較する。

## 実行

```powershell
python scripts/analyze_player_shanten_thinking.py
```

主な option:

```powershell
python scripts/analyze_player_shanten_thinking.py `
  --csv-dir csv_db `
  --out-dir reports/player_shanten_thinking `
  --min-samples 40 `
  --max-shanten 4
```

## 入力

- `csv_db/discard_fact_*.csv`
- `csv_db/hanchan_master.csv`

`discard_fact` から使う列:

- `discard_id`
- `hanchan_id`
- `room_class_label`
- `player_rel_seat`
- `player_name`
- `tsumogiri_flag`
- `thinking_time_ms`
- `shanten_after_discard`

`hanchan_master` から使う列:

- `hanchan_id`
- `room_class_label`
- `seat0_player_name`
- `seat1_player_name`
- `seat2_player_name`
- `seat3_player_name`

## 所属卓

所属卓は `hanchan_master` を正本にする。

1. `seat0..3_player_name` を縦持ちに変換する。
2. `player_name + hanchan_id` で重複除去する。
3. `room_class_label` の件数を player ごとに集計する。
4. 最頻卓を `table_affiliation` として出す。

`hanchan_master` に情報がない場合だけ、`discard_fact` 側の `room_class_label` を fallback として使う。

## 指標

- `spearman_shanten_vs_thinking_s`
- `spearman_shanten_vs_log1p_thinking_s`
- `pearson_shanten_vs_log1p_thinking_s`
- `thinking_median_s`
- `median_s_range_across_shanten`
- `median_s_cv_across_shanten`
- `near_ready_delta_s`
- `median_s_by_shanten_json`
- `p90_s_by_shanten_json`

## 出力

- `player_shanten_thinking_summary.csv`
- `player_shanten_thinking_report.html`
- player 別 scatter / median line PNG

HTML report には次を含める。

- negative correlation が強い player
- positive correlation が強い player
- シャンテン別中央値のばらつきが大きい player
- 所属卓と半荘数

## 注意

- `thinking_time_ms < 0` は除外する。
- `shanten_after_discard` が空、または `max_shanten` 外の行は除外する。
- サンプル数とシャンテン bin 数が閾値未満の player はランキング対象外にする。
