# プレイヤー別シャンテン数・思考時間分析

更新日: `2026-05-24`

## 目的

DB の `discard_fact_*.csv` から、プレイヤーごとに「打牌後シャンテン数」と「思考時間」の関係を見る。0シャンテンは待ち選択やテンパイ後の処理で少し短くなりやすい例外として扱い、現在の標準レポートでは 1〜3シャンテンだけを相関・ランキング・グラフの対象にする。

## 実行

```powershell
python scripts/analyze_player_shanten_thinking.py
```

標準設定:

```powershell
python scripts/analyze_player_shanten_thinking.py `
  --csv-dir csv_db `
  --out-dir reports/player_shanten_thinking `
  --min-samples 80 `
  --min-shanten 1 `
  --max-shanten 3
```

## 入力

- `csv_db/discard_fact_*.csv`
- `csv_db/hanchan_master.csv`

`discard_fact` から使う主な列:

- `hanchan_id`
- `room_class_label`
- `player_name`
- `thinking_time_ms`
- `shanten_after_discard`

`hanchan_master` から所属卓を補完する列:

- `hanchan_id`
- `room_class_label`
- `seat0_player_name`
- `seat1_player_name`
- `seat2_player_name`
- `seat3_player_name`

## 指標

- `spearman_shanten_vs_log1p_thinking_s`: 1〜3シャンテンと `log1p(thinking seconds)` の Spearman 相関。負なら1シャンテン側ほど長考しやすい。
- `median_s_1_minus_3_s`: 1シャンテン中央値から3シャンテン中央値を引いた秒数。正なら1シャンテンの方が長い。
- `median_s_1_minus_2_s`
- `median_s_2_minus_3_s`
- `median_s_range_across_shanten`: 1〜3シャンテンの中央値レンジ。
- `median_s_cv_across_shanten`: 1〜3シャンテンの中央値の変動係数。
- `median_s_by_shanten_json`
- `p90_s_by_shanten_json`

## 出力

- `reports/player_shanten_thinking/index.html`
- `reports/player_shanten_thinking/player_shanten_thinking_summary.csv`
- `reports/player_shanten_thinking/overall_shanten_thinking_summary.csv`
- `reports/player_shanten_thinking/player_shanten_variability_summary.csv`
- `reports/player_shanten_thinking/player_correlation_ranking.png`
- `reports/player_shanten_thinking/player_shanten_median_heatmap.png`
- `reports/player_shanten_thinking/player_shanten_profile_lines.png`
- `reports/player_shanten_thinking/player_variability_boxplot.png`
- `reports/player_shanten_thinking/player_sample_balance.png`

HTML レポート内の画像は、クリックまたは Enter/Space キーで拡大表示できる。拡大表示は画像クリック、背景クリック、閉じるボタン、Esc キーで閉じる。

## 注意

- `thinking_time_ms < 0` は除外する。
- 標準では `shanten_after_discard` が 1〜3 以外の行を除外する。
- プレイヤー別ランキングは、サンプル数が `--min-samples` 以上、かつ 1,2,3 の3種類すべてにデータがあるプレイヤーだけを対象にする。
- 所属卓は `hanchan_master` を正本とし、欠けている場合だけ `discard_fact.room_class_label` を fallback にする。
