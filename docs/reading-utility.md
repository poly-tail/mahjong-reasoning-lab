# Reading Utility

## 何を測っているか

読み、signal、observation candidate、rule が実際にどれだけ価値を持ったかを測ります。

- `selective_pruning_ratio`
- `global_impact_score`
- `concentration_shift`
- `projected_margin_gain`
- `ambiguity_reduction`
- `resolution_gain`
- `cost_estimate`
- `utility_score`

## なぜ必要か

狭い一点だけ削る読みは、見た目には鋭くても判断をほぼ動かさないことがあります。上位確率質量に効く読み、ambiguityを大きく減らす観測、projection marginを動かす読みを優先したいからです。

## どう解釈するか

`utility_score` は単独の正解率ではなく、集中度、分布差分、曖昧性解消、コストの合成指標です。`selective_pruning_ratio` が低く `global_impact_score` も低い場合、狭い読みを過大評価しないようにします。

## 何をやってはいけないか

utilityを勝敗結果と同一視しません。実戦結果はサンプル偏りを含みます。特に選択バイアスがある場合、utility badgeだけでルールを強化しないでください。

## 将来 pruning-ui とどう接続するか

`reasoning_lab.reading_utilities` を pruning-ui の候補排序、downweight提案、観測計画の優先度に渡します。pruning-ui側では実測ログと照合し、utility式を後で差し替えられるようにします。
