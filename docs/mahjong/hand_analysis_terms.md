# 手牌用語

`src/logic/hand_analysis.py` は、打牌前 hand snapshot からシャンテン数と待ち候補を出し、`discard_fact` の 1 行がどの局面だったかを後から追えるようにする。

## シャンテン数

- `concealed hand`: 入力元となる 34 種または raw 136 ID の手牌。鳴きは別管理。
- `shanten_after_discard`: legacy の最小シャンテン。通常形 / 七対子 / 国士のうち最小のもの。
- `shanten_normal_after_discard`: 通常形シャンテン。
- `shanten_chiitoitsu_after_discard`: 七対子シャンテン。
- `kokushi`: 国士シャンテンは `ShantenBreakdown.kokushi` で計算するが、`discard_fact` には専用列を持たない。

### 命名の考え方

- `after_discard` は「その打牌をしたあとの手牌」を基準にする。
- 実値は `shanten_*_after_discard` と `wait_tiles_after_discard_mspz` を組で読む。
- 列の詳細は [shanten_columns.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/reference/shanten_columns.md) を参照。

## 打牌種別用語

- `ツモ切り`:
  - その巡目に自分が引いてきた牌を、そのまま切る打牌。
  - 実装上は主に `tsumogiri=True` で表現する。

- `手出し`:
  - `ツモ切り` ではない打牌の総称。
  - このプロジェクトでは、`鳴き手出し` を必ず包含する。
  - つまり「手出し」と書いてある箇所は、明示的な例外がない限り `鳴き手出しを含む非ツモ切り打牌全体` を指す。

- `鳴き手出し` / `post-call tedashi`:
  - チー / ポン / 加槓などの鳴きの直後に行う手出し。
  - 用語上は `手出し` の部分集合。
  - 画面表示では黄枠の `post-call tedashi`、危険度ロジックでは `thinking_time_source == "call"` を伴う手出しとして扱うことが多い。

- `鳴かれた牌` / `called discard`:
  - 後で他家にチー / ポン / 大明槓された捨て牌。
  - これは `手出し` / `ツモ切り` と別軸の結果フラグであり、`鳴かれた手出し` と `鳴かれたツモ切り` の両方がありうる。

## 両面候補

この文書では、次のような形を両面候補としてみなす。

- 打牌前に `AAB` または `ABB` の 3 枚形がある。
- `A` と `B` は同一色の連続牌。
- その 3 枚形から 1 枚切ると `AB` の 2 枚形が残る。
- 残る `AB` は `23` または `78` のような数牌両面で、`12` と `89` のペンチャンは含めない。
- 残る `AB` の両外に牌が 1 枚ずつあっても、`1223` や `2234` のように 3 連形へ吸収される形はここでは両面候補に含めない。

例:

- 両面候補: `223m -> 23m`, `233m -> 23m`, `788m -> 78m`
- 両面候補ではない: `122m -> 12m`, `899m -> 89m`, `1223m -> 123m`, `2234m -> 234m`

## 危険度読み用語

- 跨ぎ筋:
  - 数牌 `n` の手出しに対して、`(n-2, n+1)` と `(n-1, n+2)` の筋線だけを跨ぎ筋候補として警戒する読み。
  - 端に寄るほど候補は減る。`2s` の跨ぎ筋は `1-4s` の 1 本だけ、`1s` の跨ぎ筋はない。
  - このプロジェクトでは [mahjong_danger.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/mahjong/mahjong_danger.md) の跨ぎ筋ルールを使い、最新手出しほど重く、古い候補ほど軽く扱う。
  - 赤5切りだけは `3-6` と `4-7` を各 `0.25本` として弱く数える。

- 裏筋:
  - 隣の牌の筋で、かつ跨ぎ筋ではない筋を警戒する読み。
  - `4` の裏筋は `5-8` の 1 本、`2` の裏筋は `3-6` の 1 本、`1` の裏筋は `2-5` の 1 本。
  - 裏筋は `5` 以外では必ず 1 本だけで、`5` だけが `1-4` と `6-9` の 2 本を持つ。
  - このプロジェクトでは「最終手出しの裏筋両面補正」として、対応する筋線に乗算補正を掛ける。
  - 見え枚数が多いほど補正は弱くなり、完全に物理否定される形は採らない。

- 合わせ打ち:
  - 本来の意味では、他家の打牌に対して直後の打牌で同じ 34 種系の牌を重ねて切ること。
  - ただし本プロジェクトの river marker は、本来の用語より広い条件で黄丸を付ける。
  - marker 条件は「あるプレイヤーが前回の自分の打牌から今回の打牌までの間に、見え枚数が増えた同牌種を今回切ったか」で判定する。
  - 見え枚数の増加には、公開情報として増えた他家の打牌、自他の鳴きで新たに晒された牌、ドラ表になった牌を含む。
  - 配牌や自分のツモ牌のような private 情報は数えない。
  - 自分自身の打牌では自分自身の flag を立てず、自分自身の鳴きで晒した牌でも self flag は立てない。
  - ただし、鳴きで食った牌は相手打牌由来なので、その相手打牌の時点で caller 側の flag 候補になりうる。
  - 各プレイヤーの flag はそのプレイヤーの次の打牌で判定し、そこで消える one-shot として扱う。
  - 手出しかツモ切りかは問わず、前回自分の打牌より後に visible increase が入っていれば marker 対象にする。

## DB 出力

`src/capture/storage.py` では、`discard_fact` の行生成時に次を行う。

- 打牌前 hand snapshot からシャンテン数を計算する。
- 打牌後 hand snapshot を使って両面候補を判定する。
- live capture では、その時点の snapshot に対して後から再計算できるよう情報を残す。

## 関連文書

- [hand_analysis.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/mahjong/hand_analysis.md): シャンテン数と両面候補の仕様。
- [shanten_columns.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/reference/shanten_columns.md): `discard_fact` のシャンテン列定義。
- [mahjong_danger.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/mahjong/mahjong_danger.md): 跨ぎ筋、裏筋、見え枚数補正、河 marker の危険度仕様。
- [db_analysis_rules.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/analysis/db_analysis_rules.md): DB 分析時の前提。
- [opponent_tenpai_readiness.md](c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/docs/mahjong/opponent_tenpai_readiness.md): 打牌から聴牌近さを読む側の整理。
