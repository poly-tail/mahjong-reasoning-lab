# analysis docs

分析ルール、フィルタ条件、グラフ preset、比較メモなどを置く。

## 置くもの
- 再利用できる分析前提
- 定常的に使うフィルタ条件
- 比較観点、集計ルール、読み方

## 置かないもの
- 一回限りの比較結果
- raw export
- 実験途中の一時メモ

## 運用
- 再利用できる前提だけを正本化する
- one-shot の結果は `analysis_output/` 側へ置く
- 分析ルールが実装契約へ影響するなら requirements / specs / changelog も更新する
