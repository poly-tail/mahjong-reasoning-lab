# DBグラフツール

`discard_fact` を対象に、列指定、where 条件、派生列をその場で与えて各種グラフを出力する CLI の説明です。

対象コマンド:

- `cli/plot_db_graph.py`

## 目的

- DB の特定列をそのまま X 軸 / Y 軸に使う
- `where` 条件で対象行を絞る
- `name=expr` 形式の派生列をその場で作る
- `ryanmen_fixed_discards` のような preset dataset もそのまま使う
- 散布図、回帰直線付き散布図、信頼区間付き散布図、箱ひげ図、線グラフ、ヒストグラム、カテゴリ棒グラフを出す

## 対応グラフ種類

- `scatter`
  - 通常の散布図
  - `--include-regression` を付けると回帰直線を重ねる
- `scatter_ci`
  - 生の散布点に加えて、X ごとの平均点と信頼区間を重ねる
  - `--x-bin-width` を指定すると、numeric X を区間化してから平均と信頼区間を作る
  - `--include-regression` で回帰直線も重ねられる
- `boxplot`
  - X ごとに Y の分布を箱ひげ図で出す
  - ひげは `min/max`
- `line`
  - 折れ線グラフ
  - `--line-aggregation raw|mean|median|sum|count|min|max`
- `histogram`
  - 1 列の数値分布
  - `--x-bin-width` をビン幅として使う
- `discrete_bar`
  - 1 列のカテゴリ件数集計

## データセット

### 1. 生データセット

- `discard_fact_all`
  - `discard_fact_*.csv` をそのまままとめて読む
  - 既定では `パシフィック` と `s6u` は除外

### 2. preset データセット

既存の preset dataset もそのまま使えます。

例:

- `ryanmen_fixed_discards`

利用可能 dataset 一覧:

```powershell
py -3 cli/plot_db_graph.py --list-datasets
```

## 条件と派生列

### where 条件

`--where` は複数回指定でき、すべて AND で適用されます。

例:

```powershell
--where "thinking_time_ms is not None"
--where "thinking_time_ms > 900"
--where "thinking_time_ms < 8000"
```

ラグ分析では、まず次を入れる。

```powershell
--where "lag_delay_ms is not None"
--where "lag_delay_ms > 550"
```

### 派生列

`--derive` は `name=expr` 形式です。複数回指定すると上から順に評価され、後ろの式から前の派生列を参照できます。

例:

```powershell
--derive "thinking_time_sec=thinking_time_ms / 1000"
--derive "is_fast=1 if thinking_time_ms < 2000 else 0"
```

## 式で使える主な関数

- `num(value)`
  - 数値に寄せる。空欄は `None`
- `flag(value)`
  - `1`, `true`, `yes`, `on` などを真として扱う
- `text(value)`
  - 文字列化
- `coalesce(a, b, c, ...)`
  - 最初の非空値を返す
- `contains(value, part)`
- `startswith(value, prefix)`
- `endswith(value, suffix)`
- `abs`, `min`, `max`, `round`, `len`, `sum`, `ceil`, `floor`

加えて、四則演算、比較、`and/or/not`、三項演算子 `a if cond else b` が使えます。

## フィールド一覧確認

現在の dataset に `where` と `derive` を掛けた後のフィールド一覧を確認できます。

```powershell
py -3 cli/plot_db_graph.py `
  --dataset ryanmen_fixed_discards `
  --derive "thinking_time_sec=thinking_time_ms / 1000" `
  --list-fields
```

## 例

### 1. 両面固定打牌の散布図 + 回帰直線

```powershell
py -3 cli/plot_db_graph.py `
  --dataset ryanmen_fixed_discards `
  --kind scatter `
  --x-field shanten_after_discard `
  --y-field thinking_time_ms `
  --include-regression
```

### 2. 生データから思考時間を秒にした派生列で散布図

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind scatter `
  --derive "thinking_time_sec=thinking_time_ms / 1000" `
  --where "thinking_time_ms is not None" `
  --where "thinking_time_ms > 900" `
  --where "thinking_time_ms < 8000" `
  --x-field shanten_after_discard `
  --y-field thinking_time_sec `
  --include-regression
```

### 3. 両面固定打牌のシャンテン別箱ひげ図

```powershell
py -3 cli/plot_db_graph.py `
  --dataset ryanmen_fixed_discards `
  --kind boxplot `
  --x-field shanten_after_discard `
  --y-field thinking_time_ms
```

### 4. シャンテン別件数の線グラフ

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind line `
  --x-field shanten_after_discard `
  --line-aggregation count
```

### 5. 信頼区間付き散布図

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind scatter_ci `
  --where "thinking_time_ms is not None" `
  --where "thinking_time_ms > 900" `
  --where "thinking_time_ms < 8000" `
  --x-field shanten_after_discard `
  --y-field thinking_time_ms `
  --ci-confidence 0.95
```

### 6. numeric X を区間化して信頼区間付き散布図

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind scatter_ci `
  --x-field thinking_time_ms `
  --y-field shanten_after_discard `
  --x-bin-width 500
```

### 7. ラグ時間のヒストグラム

```powershell
py -3 cli/plot_db_graph.py `
  --dataset discard_fact_all `
  --kind histogram `
  --where "lag_delay_ms is not None" `
  --where "lag_delay_ms > 550" `
  --x-field lag_delay_ms `
  --x-bin-width 100
```

## 出力

出力先を指定しない場合は `analysis_output/custom_graphs/` に自動ファイル名で SVG を作ります。

同時に、同名の `*_summary.md` も生成します。そこには次を残します。

- 実行時刻
- dataset 名
- graph kind
- X 軸 / Y 軸
- where 条件
- 派生列
- サンプル数
- 回帰直線の係数
- 利用可能フィールド一覧

## 補足

- `scatter_ci` の信頼区間は正規近似
- `boxplot` のひげは `min/max`
- `line` は `raw` 以外では X ごとに集計してから結ぶ
- preset dataset を使う場合、もとの dataset 側の抽出条件のあとに `where` と `derive` がかかる
- ラグ分析では、`docs/analysis/lag_analysis.md` の前提どおり `lag_delay_ms > 550` を基本条件にする
