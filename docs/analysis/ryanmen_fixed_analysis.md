# 両面固定打牌分析

`discard_fact_YYYYMM.csv` から `ryanmen_fixed_flag = 1` の打牌だけを集計し、思考時間とシャンテン数の傾向を可視化するための分析手順。

## 目的

- 両面固定打牌の `thinking_time_ms` 分布を見る
- 両面固定打牌の `shanten_after_discard` 分布を見る
- `thinking_time_ms` と `shanten_after_discard` の散布図と回帰直線を見る

## 前提フィルタ

- `ryanmen_fixed_flag = 1` の行のみ集計する
- `player_name = パシフィック` と `player_name = s6u` は集計対象外
- `thinking_time_ms` が空欄の行は思考時間系プロットから除外する
- `shanten_after_discard` が空欄の行はシャンテン系プロットから除外する
- 散布図と回帰直線は、`thinking_time_ms` と `shanten_after_discard` の両方が入っている行のみ使う
- DB分析の共通外れ値ルールに従い、思考時間系は `900 < thinking_time_ms < 8000` のみ使う

## 実行方法

```powershell
py -3 cli/analyze_ryanmen_fixed.py
```

任意の DB ディレクトリや追加除外名を指定する場合:

```powershell
py -3 cli/analyze_ryanmen_fixed.py `
  --db-dir .\csv_db `
  --output-dir .\analysis_output\ryanmen_fixed `
  --exclude-player sample_name
```

軸や条件や派生列をその場で変えて見たい場合は、`cli/plot_db_graph.py` と [db_graph_tool.md](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/analysis/db_graph_tool.md) を使う。

## 出力物

標準出力:

- 出力先ディレクトリの通知

出力ファイル:

- `analysis_output/ryanmen_fixed/thinking_time_vs_shanten_scatter.svg`
  - 両面固定打牌の散布図
  - `shanten_after_discard` を横軸
  - `thinking_time_ms` を縦軸
  - 回帰直線つき
- `analysis_output/ryanmen_fixed/thinking_time_distribution.svg`
  - 両面固定打牌の思考時間ヒストグラム
- `analysis_output/ryanmen_fixed/shanten_distribution.svg`
  - 両面固定打牌のシャンテン数分布
- `analysis_output/ryanmen_fixed/summary.md`
  - サンプル数
  - 平均 / 中央値 / 最小 / 最大
  - 回帰係数
  - シャンテン別の平均思考時間

## 備考

- 対象データが空のグラフは生成しない
- その場合は `summary.md` に未生成であることを記録する
- 列名 `shanten_after_discard` は legacy 名だが、値は打牌前手牌 snapshot に対するシャンテン数
