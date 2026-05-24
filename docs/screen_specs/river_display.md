# 河表示仕様

updated: `2026-05-24`

## 目的

河の捨て牌、枠、marker、tint、思考時間帯、Push 反映の仕様をまとめる。v2.2 では表示仕様に加えて、差分描画の前提もここへ明記する。

## 枠

| 表示 | 意味 |
| --- | --- |
| 赤枠 | 後続の鳴きで消費された捨て牌 |
| 黄枠 | 鳴き直後の手出し |

## marker

| marker | 意味 |
| --- | --- |
| `L` | 通常 lag |
| `Pl` | pon-lag-likely。複数人 lag、または自分手牌 snapshot でチー/ポン不能な lag |
| `P` | Push alert 対象の捨て牌 |
| 黄丸 | 同順合わせ打ち |
| 赤ひし形 | その局で最長の思考時間 |
| ピンク丸 | 3見え |

`Push` 音声が鳴る更新では、同じ redraw 内で `P` を表示する。音声だけ先に出し、marker が遅れて出る状態は避ける。

## tint

優先順位は `4見え > 茶 > 赤 > なし`。

| tint | 条件 |
| --- | --- |
| 紫 | 捨て牌自身が 4見え |
| 茶 | 4見えにより物理的に否定された 3連形に属する手出し牌 |
| 赤 | remain / no-temp remain / post-call tedashi など危険寄り条件 |

思考時間は tint とは別の band として描画する。

## 思考時間 band

- post-reach 側の思考時間と pre-reach 側の思考時間を別 band として持つ。
- 色段階は緑、青、黄、赤、紫。
- 離席完了打牌は思考時間 band を出さない。

## 描画実装

### 差分描画

Canvas は `(seat, local_index)` ごとに表示シグネチャを持つ。

再描画する条件:

- tile id / draw type が変わった
- 位置、サイズ、anchor が変わった
- called / lag / riichi / thinking time が変わった
- tint / marker / border が変わった
- Push marker が追加または削除された

変わらない牌は描画をスキップする。ただし click spec と lag marker reference spec は毎 redraw で復元する。

### 画像と overlay

- `_discard_tile_image()` は通常牌画像だけを返す。
- 赤/茶/紫/4見え/思考時間は Canvas rectangle overlay で描画する。
- discard item は作成時に `live_async_discards` と `live_async_discards_<seat>_<index>` tag を付ける。

## 関連

- [alerts_and_panels.md](./alerts_and_panels.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- [../specs/current.md](../specs/current.md)
