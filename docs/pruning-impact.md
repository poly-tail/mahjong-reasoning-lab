# Pruning Impact

## 何を測っているか

`hard_prune`、`soft_downweight`、`hard_lock`、`soft_lock`、`keep_top_k`、`freeze_ratio`、`freeze_concentration_band` の before/after 差分を測ります。

- before / after probability distribution
- `delta_mass`
- `changed_node_count`
- `dominant_branch_change`
- `ambiguity_change`
- `margin_change`
- `vector_delta_by_metric`

## なぜ必要か

「この読みは有効か」は、枝を切った事実ではなく、分布と判断指標がどれだけ動いたかで評価します。薄い枝だけを削っても、全体判断が動かないなら utility は低い可能性があります。

## どう解釈するか

`delta_mass` が大きいほど確率質量の再配分が大きいです。`dominant_branch_change` が変わる場合は判断の主枝が入れ替わっています。`vector_delta_by_metric` は fold_risk / win_rate / safety などの射影差分です。

## 何をやってはいけないか

`delta_mass` だけで良し悪しを決めません。方向性が `mixed` や `unknown` のままなら、動いた差分が正しいとは限りません。MVPは一般循環グラフや完全ベイズ更新を扱いません。

## 将来 pruning-ui とどう接続するか

exportの `reasoning_lab.pruning_actions` と `reasoning_lab.impact_summaries` を pruning-ui 側のシミュレーション履歴として渡します。pruning-uiでは同じactionを再計算し、差分が再現するかを検証できます。
