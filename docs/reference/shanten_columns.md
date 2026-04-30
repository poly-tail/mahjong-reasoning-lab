# シャンテン列の意味

`discard_fact` のシャンテン関連列は、列名に `after_discard` を含むが、保存値の基準時点は完全には一致していない。

## 命名上の注意

- `shanten_*_after_discard` は legacy 列名で、実際の値は打牌前 concealed hand snapshot 基準
- `wait_tiles_after_discard_mspz` だけは実際の打牌後手牌基準
- そのため `after_discard` という語だけで読むと誤解しやすい
- 実務上は `shanten_*_after_discard = pre-discard snapshot value` と読んだほうが正確

## 列ごとの意味

| 列名 | 実際の基準時点 | 値の意味 | 空欄条件 | 補足 |
|---|---|---|---|---|
| `shanten_after_discard` | 打牌前 | 通常形 / 七対子 / 国士無双のうち有効値の最小 | 手牌 snapshot 不明、牌数不整合 | 列名だけ legacy |
| `shanten_normal_after_discard` | 打牌前 | 通常形シャンテン数 | 手牌 snapshot 不明、牌数不整合 | 副露数は `14 / 11 / 8 / 5 / 2` から逆算 |
| `shanten_chiitoitsu_after_discard` | 打牌前 | 七対子シャンテン数 | 手牌 snapshot 不明、または副露あり | 七対子は門前専用 |
| `wait_tiles_after_discard_mspz` | 打牌後 | 実際に切った 1 枚を除いた後の手牌がテンパイなら、その待ち牌 | 非テンパイ、snapshot と打牌牌が不整合 | `36m`, `258p`, `14z` のような `mspz` grouped text |

## DB に保存しないもの

- `kokushi` は `ShantenBreakdown.kokushi` として内部計算する
- ただし `discard_fact` には `shanten_kokushi_after_discard` 列を持たない
- 国士内訳が必要なら、再計算で取得する前提にする

## 例

### 例 1: 門前 14 枚の打牌前 snapshot

- 打牌前 hand: `233m 456p 789s 11z 67m`
- `shanten_after_discard = 1`
- `shanten_normal_after_discard = 1`
- `shanten_chiitoitsu_after_discard = 4`

### 例 2: 実打牌後だけを見る列

- 打牌前 hand: `233m 456p 789s 11z 67m`
- 打牌: `3m`
- 打牌後 hand がテンパイでなければ `wait_tiles_after_discard_mspz = ""`
- 打牌後 hand がテンパイなら `wait_tiles_after_discard_mspz = "***m"` のように保存する

## 推奨の読み方

- 分析時: `shanten_*_after_discard` を「打牌前 snapshot 列」として扱う
- 実打牌後の意味で使いたいときは `wait_tiles_after_discard_mspz` と混同しない
- 命名変更は互換性コストが高いため、現状は doc で補う
