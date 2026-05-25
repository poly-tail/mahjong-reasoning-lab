# Pruning vs Node Lock

Pruning と Node Lock は別の操作です。

## Pruning

Pruning は候補空間を縮める操作です。

- `hard_prune`: 候補を削る
- `soft_downweight`: 候補を消さずに弱める
- `keep_top_k`: 1つに絞らず上位候補を残す

`mixed` / `unknown` influence が残る場合や、`must_keep_top_k` が付いた候補は、hard pruneではなく downweight や keep top-k を優先します。

## Node Lock

Node Lock は候補を残したまま、確率や戦略分布を固定する操作です。

- `hard_lock`
- `soft_lock`
- `freeze_ratio`
- `freeze_concentration_band`

ロックは「消す」操作ではありません。比較条件を固定し、他の不確実部分を見るための操作です。

## Warning Rules

Reasoning Lab は次のとき警告します。

- `mixed` / `unknown` influence が残る対象を hard prune しようとした
- `must_keep_top_k` の対象を hard prune しようとした
- top-k mass が低く、候補が薄く広いのに1枝だけ削ろうとした
- hard lock / freeze ratio 中のノードへ再正規化や枝刈りが衝突しそうな操作をした
