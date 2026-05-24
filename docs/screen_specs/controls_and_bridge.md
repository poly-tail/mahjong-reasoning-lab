# 操作系と Bridge

updated: `2026-05-24`

## アプリ側ボタン

主な操作:

- `AI TOP3`
- `SELF`
- `NAGA段位`
- `pystyle`
- `ベタオリ`
- `自動理牌`
- `自動和了`
- `ツモ切り`
- `鳴きなし`
- visible control 群

## 自家手牌クリック

- 左クリックは `discard_by_index` を使う。
- 右クリックは skip/pass 系 visible control を優先する。
- visible skip/pass がない場合は右端 slot の `ツモ切り` 補助として扱う。
- AUTO は strict visible hand guard を維持し、manual は live capture の軽い 1 枚遅れを許容する。

## Bridge snapshot

- `ui_snapshot` は browser 側の ready state、visible control、toggle 状態を取得する。
- snapshot は `1 in-flight + pending 1` で coalescing する。
- `SYNC` は operator が明示的に snapshot を取り直す入口。

## Bridge command

| command | 用途 |
| --- | --- |
| `discard_by_index` | 自家手牌 index 打牌 |
| `click_control` | browser visible control の click |
| `ui_snapshot` | browser UI 状態取得 |
| `ping` | 接続確認 |

## NAGA 操作

- `NAGA段位` ボタンは現在局面を NAGA ptEV analyzer へ渡す。
- popup は全体、3900直撃、満貫ツモ候補の section を切り替えられる。
- 南2以降は同じ query state を使い、下部パネルへ自動要約を出す。

## 障害時の見方

- `Bridge connected` は app と extension の transport 接続であり、天鳳操作可能を保証しない。
- `Bridge globals|canvas_detect|heuristic ctrls=N` が出ている場合、browser 側 heuristic は動作している。
- 打牌や control click 後は forced follow-up snapshot を使い、表示状態を追従させる。
