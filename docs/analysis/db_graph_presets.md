# DBグラフ定義

`discard_fact` を対象にした分析グラフを、Python で再利用可能な定義として持つ仕組みの説明です。

## 目的

- 両面固定打牌のような再利用したい抽出条件を、毎回手で書き直さずに使えるようにする
- 横軸、縦軸、グラフ種類、出力先をまとめて定義できるようにする
- Codex へ毎回依頼しなくても、CLI から同じ分析を再実行できるようにする

## 関連ファイル

- 定義本体: `cli/db_graph_presets.py`
- 描画フレームワーク: `cli/db_graph_framework.py`
- 実行 CLI: `cli/plot_discard_fact_graph.py`
- 汎用 ad-hoc CLI: `cli/plot_db_graph.py`
- 既存互換ラッパー: `cli/analyze_ryanmen_fixed.py`

## 定義の構成

### 1. データセット定義

データセット定義は、`discard_fact` から動的に行を組み立てる Python 関数です。

例:

```python
def build_ryanmen_fixed_dataset(
    db_dir: Path,
    excluded_players: Sequence[str],
) -> list[dict[str, object]]:
    ...
```

ここで担当するもの:

- `ryanmen_fixed_flag = 1` のような抽出条件
- プレイヤー除外
- 欠損値の扱い
- 分析用の派生列生成

### 2. グラフ定義

グラフ定義は次を持ちます。

- どのデータセットを使うか
- グラフ種類
- `x_field`
- 必要な場合の `y_field`
- 数値フィルタ
- 出力ファイル名

対応しているグラフ種類:

- `scatter`
- `histogram`
- `discrete_bar`

### 3. 分析定義

分析定義は、複数のグラフ定義をひとまとめにして 1 つの出力ディレクトリへ書くための束です。

## 現在の既定定義

- データセット: `ryanmen_fixed_discards`
- 分析束: `ryanmen_fixed_analysis`
- グラフ:
  - `ryanmen_fixed_thinking_time_vs_shanten`
  - `ryanmen_fixed_thinking_time_distribution`
  - `ryanmen_fixed_shanten_distribution`

## 使い方

定義一覧表示:

```powershell
py -3 cli/plot_discard_fact_graph.py --list-presets
```

両面固定の分析束を実行:

```powershell
py -3 cli/plot_discard_fact_graph.py --analysis ryanmen_fixed_analysis
```

同じ preset dataset を汎用 CLI から使う例:

```powershell
py -3 cli/plot_db_graph.py `
  --dataset ryanmen_fixed_discards `
  --kind scatter `
  --x-field shanten_after_discard `
  --y-field thinking_time_ms `
  --include-regression
```

既存コマンド互換:

```powershell
py -3 cli/analyze_ryanmen_fixed.py
```

## 新しい定義の追加方法

1. `cli/db_graph_presets.py` にデータセット生成関数を追加する
2. `DATASET_DEFINITIONS` に登録する
3. `GRAPH_DEFINITIONS` にグラフ定義を追加する
4. 必要なら `ANALYSIS_DEFINITIONS` で束ねる
5. `cli/plot_discard_fact_graph.py` から実行する

## 補足

- 空欄セルは、各グラフのサンプル抽出段階で自動的に除外する
- 数値フィルタはグラフごとに設定する
- プレイヤー除外は各データセット生成関数へ渡す
- 現在の既定除外名は `パシフィック` と `s6u`
- ラグ分析 preset を作る場合は、`cli/db_graph_framework.py` の共通閾値に合わせて `lag_delay_ms > 550` を基本条件にする
