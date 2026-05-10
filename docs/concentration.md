# Concentration Lens

## 何を測っているか

choice group、枝集合、inference subgraph の確率質量の集中度を測ります。

- `entropy`: 分布の広がり。1に近いほど薄く広い。
- `top_k_mass`: 上位k枝に集まる質量。
- `peak_mass`: 最大枝の質量。
- `hhi`: 集中度。高いほど少数枝に偏る。
- `dispersion_note`: UI向けの短い解釈ラベル。

## なぜ必要か

麻雀の読みは、同じ1枝のpruneでも、削る場所が上位質量か薄いtailかで判断への影響が違います。集中度を見ることで「どこを削ると全体分布が動きやすいか」を評価できます。

## どう解釈するか

`peak_mass` や `top_k_mass` が高い枝集合では、小さなdownweightでも `dominant branch` や `projection margin` が動きやすくなります。`entropy` が高い枝集合では、単一枝を削っても影響が分散しやすいです。

## 何をやってはいけないか

高集中だから常にpruneしてよい、とは解釈しません。directional ambiguity、top-k制約、lock、分布仮定が未解決なら、Concentration Lensは警告材料であって自動切断の根拠ではありません。

## 将来 pruning-ui とどう接続するか

exportの `reasoning_lab.concentration_metrics` を pruning-ui の候補枝強調、pruning候補の優先度、weight編集初期表示に渡します。高集中枝は「要レビュー」として表示し、未解決ambiguityがある場合はprune禁止または警告にします。
