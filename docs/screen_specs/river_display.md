# 河表示仕様

updated: `2026-04-23`

この文書は、河の枠、記号、tint、awaseuchi の表示ルールをまとめます。

## 枠

| 表示 | 意味 |
| --- | --- |
| 赤枠 | called discard |
| 黄枠 | post-call tedashi |

## 記号

| 記号 | 意味 |
| --- | --- |
| `L` | 通常 lag |
| `Pl` | pon-lag-likely |
| `P` | Push 対象の最新打牌 |

## 色付け

優先順位は `purple > brown > red > none`。

- purple: 対象牌そのものが `4見え`
- brown: `123..789` x 3スーツ の `21` 通りで、`4見え` により物理否定された 3 連形へ属する手出し牌
- red: remain / no-temp remain / post-call tedashi などの危険寄り条件

## 合わせ打ち

- provisional は直近 7 公開イベントだけを見る
- confirm worker は provisional hit がある時だけ動く
- private 情報は使わない

## 関連

- [display_overview.md](./display_overview.md)
- [visible_counts_ui.md](./visible_counts_ui.md)
