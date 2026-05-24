# DB グラフツール

更新日: `2026-05-24`

## 目的

CSV DB から任意の列を選び、散布図、箱ひげ、折れ線、ヒストグラム、カテゴリ棒グラフを出す。主な CLI は `cli/plot_db_graph.py`。

## 基本コマンド

```powershell
py -3 cli/plot_db_graph.py --list-datasets
py -3 cli/plot_db_graph.py --dataset discard_fact_all --list-fields
```

## 主な dataset

- `discard_fact_all`: `discard_fact_*.csv` をまとめて読む。
- `ryanmen_fixed_discards`: 両面固定系の preset dataset。

## 主な graph kind

- `scatter`
- `scatter_ci`
- `boxplot`
- `line`
- `histogram`
- `discrete_bar`

## where / derive

`--where` は複数指定でき、すべて AND で適用する。

```powershell
--where "thinking_time_ms is not None"
--where "thinking_time_ms > 900"
--where "thinking_time_ms < 8000"
```

`--derive` は `name=expr` 形式。

```powershell
--derive "thinking_time_sec=thinking_time_ms / 1000"
--derive "is_fast=1 if thinking_time_ms < 2000 else 0"
```

## 例

### シャンテン数と思考時間

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind scatter `
  --x-field shanten_after_discard `
  --y-field thinking_time_ms `
  --where "thinking_time_ms is not None" `
  --include-regression
```

### ラグ時間ヒストグラム

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind histogram `
  --where "lag_delay_ms is not None" `
  --where "lag_delay_ms > 550" `
  --x-field lag_delay_ms `
  --x-bin-width 100
```

## プレイヤー別シャンテン思考時間分析

プレイヤーごとの相関やばらつきは専用スクリプトを使う。

```powershell
python scripts/analyze_player_shanten_thinking.py
```

出力:

- `reports/player_shanten_thinking/player_shanten_thinking_summary.csv`
- `reports/player_shanten_thinking/player_shanten_thinking_report.html`
- player 別 PNG

詳細: [player_shanten_thinking.md](./player_shanten_thinking.md)

## 出力

指定がない場合、`analysis_output/custom_graphs/` に SVG と summary markdown を生成する。
