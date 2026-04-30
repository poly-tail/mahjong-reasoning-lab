# ryanmen_fixed_analysis

両面固定打牌の思考時間とシャンテン数をまとめて見る分析束。

- 生成時刻: `2026-04-06 21:16:05`
- DB ディレクトリ: `C:\Users\weath\OneDrive\ドキュメント\tenhou_hojo\csv_db`
- 出力先: `analysis_output\ryanmen_fixed_tmp_verify`
- 除外プレイヤー: `パシフィック, s6u`

## データセット

- `ryanmen_fixed_discards`: `9` 行

## グラフ

- `ryanmen_fixed_thinking_time_vs_shanten` (scatter / 6件): `thinking_time_vs_shanten_scatter.svg` - 散布図を生成。
- `ryanmen_fixed_thinking_time_distribution` (histogram / 6件): `thinking_time_distribution.svg` - ヒストグラムを生成。
- `ryanmen_fixed_shanten_distribution` (discrete_bar / 9件): `shanten_distribution.svg` - カテゴリ分布グラフを生成。

## 回帰直線

### ryanmen_fixed_thinking_time_vs_shanten

- 傾き: `-269.9837`
- 切片: `3888.2227`
- 相関係数: `-0.1587`
