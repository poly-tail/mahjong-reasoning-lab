# 危険度ロジック

## 概要

本プロジェクトの危険度表示は、まず筋本数ベースの無筋危険度を作り、その上に鳴き補正、内牌→外牌補正、ラグ補正、見え枚数濃度補正、愚形待ち加算を重ねて求める。

- 自家手牌下の危険度バーは、最終的な牌ごとの総合危険度を丸めて表示する
- 各プレイヤーパネルの `SUMMARY` は、筋ランキングと牌別ランキングを並べて表示する
- exact safe や一時 safe によって `0` になった牌は、後段の補正で復活させない
- この文書でいう `手出し` は、明示的な例外がない限り `鳴き手出し(post-call tedashi)` を含む

## 基本定義

筋線は 6 本固定とする。

- `1-4`
- `4-7`
- `2-5`
- `5-8`
- `3-6`
- `6-9`

牌ごとの基礎無筋危険度は、対象牌が属する筋線重みの合計を、全筋線重み合計で割って % 化したものとする。

```text
牌ごとの無筋危険度 % = 対象牌が属する筋線重み合計 / 全筋線重み合計
```

## 基礎無筋危険度

### 1. 線の初期化

- 対象プレイヤーの手出し牌、リーチ後現物、一時 safe 牌から suppressor を集める
- suppressor に触れる筋線は `0.0`
- それ以外の筋線は `1.0`

### 2. またぎ筋

手出し履歴を新しい順に見て、未解決の筋線へ一度だけ重みを入れる。

- 数牌 `n` のまたぎ筋候補は `(n-2, n+1)` と `(n-1, n+2)` だけを使う
- 範囲外に出る候補は採らないため、端牌ほど本数が減る
- `1` にはまたぎ筋がなく、`2` は `1-4` だけ、`8` は `6-9` だけを持つ
- 捨てられた牌自身が `4見え` のとき、その牌をまたぐ両面形は物理的に成立しないため、対応するまたぎ筋の無筋カウントは必ず `0本` とする
- 捨てられた牌自身が `3見え` のときは残り1枚所持していないと筋が成立しないため、対応するまたぎ筋は `0.8本` として弱める

- 最新の手出しに由来するまたぎ筋: `1.0`
- 1 つ前の手出しに由来するまたぎ筋: `0.5`
- それ以前の手出しに由来するまたぎ筋: `0.3`

例:

- `4m` の手出しは `2-5m` と `3-6m` を候補にする
- `2s` の手出しは `1-4s` だけを候補にする
- `1s` の手出しはまたぎ筋候補を持たない
- `4m` 自身が `4見え` なら、その `2-5m` と `3-6m` はどちらも `0本` になる
- `4m` 自身が `3見え` なら、その `2-5m` と `3-6m` はどちらも `0.8本` 扱いになる
- その後により新しい手出しが無ければ、その 2 本は `1.0`
- さらに後続手出しで別のまたぎ候補が出れば、古い候補は `0.5` や `0.3` へ下がる
- 赤5を切ったときだけ、そのまたぎ筋 `3-6 / 4-7` はどちらも `0.25` 本として扱う。ただし赤5自身が `4見え` なら、ここも `0本` が優先される

### 3. ターツ落とし
切り順による代表例だけを扱い、同色の隣接数牌 2 枚を連続して手出しし、2 枚目も手出しだったときに `ターツ落とし` とみなす。
- その 2 枚目の手出しより前に切られていた牌のまたぎ筋は `70%` カウントとする
- これは後段の乗算補正ではなく、またぎ筋の本数決定段階で `0.7 本` に置き換える扱い
- したがって `0.5 -> 0.35` や `0.3 -> 0.21` にはせず、代表的な切り順のときは `0.7 本` を優先する

## 鳴き・手出し進行による筋補正

### チー形補正

副露チーの形から、同色の特定筋線のカウント数を減らす。

- カンチャンチー: 周辺 3 本を `50%` カウント
- ペンチャンチー: 外側隣接の 1 本を `50%` カウント
- 両面チー: 隣接の 1 本を `60%` カウント

具体例:

- `35` で `4` を鳴いて `345` にした場合、`2-5 / 3-6 / 5-8` を `50%` カウント
- `12` で `3`、または `89` で `7` を鳴いた場合、外側隣接筋を `50%` カウント
- 通常の両面チーは、食った隣の筋だけを `60%` カウント

同じ筋線に複数の補正が同時に掛かる場合は、`1.0` 本に対して倍率を重ねる。

- 例: `50%` カウントと `70%` カウントが同時に掛かるなら、その筋線は `0.35` 本として数える

### 内牌→外牌手出し補正

同色で、より内側の牌を切ったあとに外側牌へ移るときは、1 本だけ `70%` カウントにする。

- `3..7` の後に `2/8` または `1/9`
- `2/8` の後に `1/9`

例:

- `3m` の後に `1m` を切ったなら `3-6m` を `70%` カウント
- `7m` の後に `9m` を切ったなら `4-7m` を `70%` カウント
- `5 -> 3` のような同じ内側帯の移動ではこの補正を入れない
- 追加条件として、`Remain <= 16.0` の局面で `1/2/8/9` のツモ切りに `2.5秒以上` かかったときも、対応する 2 つ隣筋を同じく `70%` カウントにする

### 最終手出しの裏筋両面補正
最終手出しの代表的な裏筋両面だけを扱い、対応する筋線を乗算補正する。
- ここでいう `最終手出し` は局全体の最後の打牌ではなく、各プレイヤーごとの直近の手出しを指す
- この補正は一時的で、そのプレイヤーが次に新しい手出しをした時点で補正対象も更新される
- 裏筋は「隣の牌の筋で、かつ跨ぎ筋ではない筋」として扱う
- `5` 以外の数牌は裏筋が 1 本だけで、`5` だけは `1-4` と `6-9` の 2 本を持つ
- `1 -> 2-5`
- `2 -> 3-6`
- `3 -> 4-7`
- `4 -> 5-8`
- `5 -> 1-4` と `6-9`
- `6 -> 2-5`
- `7 -> 3-6`
- `8 -> 4-7`
- `9 -> 5-8`

補正値は `else if` として最大 1 個だけ適用する。
- 基本は `75%`
- 最終手出し牌か、その 2 つ内側の牌が `2見え` なら `65%`
- さらにその条件を満たし、最終手出し牌と対応する 2 つ内側牌の合計が `3見え以上` なら `60%`

補足:
- `5` だけは左右 2 種の裏筋両面を持つため、`1-4` 側は `3`、`6-9` 側は `7` を「2つ内側牌」として別々に判定する
- suppress 済みで `0` 本の筋はこの補正でも復活しない

## ラグ補正

前家の未鳴きラグ打牌に対して、対象プレイヤーが鳴けそうな隣接筋へ危険度上昇倍率を掛ける。

- 対象は前家の `lagged = 1` または `lagged = 3`
- `lagged = 6` は short system delay とみなし、この補正対象にしない
- `lag_delay_ms <= 1400` は補正なし
- `1400ms < lag_delay_ms < 2000ms` は対象筋線を `120%` カウント
- `2000ms <= lag_delay_ms <= 7000ms` は対象筋線を `140%` カウント
- `7000ms` 超は局外要因が混ざりやすいので補正なし
- 複数のラグ補正が同じ筋線に掛かる場合は倍率を掛け合わせる
- `0` になっている筋線は復活させない

補足:

- 高速スキップは、受けが残る鳴きスキップではなく「鳴く手ではない」「面前進行で受けも薄い」側に寄りやすいとみなす
- 将来はプレイヤー別の平均ラグ統計や、チー/ポン別傾向で閾値を調整してもよい

## 見え枚数濃度補正

補正済みの base 無筋危険度 `%` が `10%` を超える牌だけ、見えている枚数による濃度補正をさらに掛ける。

- 補正対象は愚形加算前の numerator / denominator
- 牌ごとに、全筋線へ対して「その筋線の両端 2 牌の合計見え枚数」で倍率を付ける
- このあとに numerator / denominator を再計算し、最後に愚形待ち加算を足す

筋線ごとの倍率:

- 合計 `2` 見え以下: `90%`
- 合計 `3` 見え: `110%`
- 合計 `4` 見え: `120%`
- 合計 `5` 見え以上: `130%`

例:

- `3-6m` で `3m` が 1 枚、`6m` が 2 枚見えているなら、その筋線は `110%`
- `1-4p` で `1p` が 2 枚、`4p` が 2 枚見えているなら、その筋線は `120%`

## 両面以外待ちパターン考慮総合危険度

### 基本

牌ごとの総合危険度は、補正後の無筋危険度 % に愚形待ち加算を足して作る。

- 愚形加算は分子分母の補正ではなく、無筋危険度 % に対する単純加算とする

- カンチャン: 基本 `+2.0%`
- シャンポン: 基本 `+2.0%`
- ペンチャン: `3` と `7` のみ `+2.0%`

最大で 3 パターンを同時加算する。

- ただし表示上の総合危険度は、残筋本数が `1.0` を超えている間は `100%` までに丸める
- `100%` 超えを許すのは、残筋本数が実質 1 本相当まで減った局面だけとする

### 最終手出しによるスペース補正

最終手出しが `1/9` 以外の数牌なら、その牌から中心側へ 1 つ内側、2 つ内側の牌は愚形待ちが薄くなるとみなす。

- 最終手出しが `2/3/4` なら、中心側は `+1`, `+2`
- 最終手出しが `6/7/8` なら、中心側は `-1`, `-2`
- `5` は内側方向が一意に決まらないので、この補正を入れない

この薄化は同色牌にのみ適用する。

- カンチャン加算: `2.0% -> 0.6%`
- シャンポン加算: `2.0% -> 1.0%`
- ペンチャンはこの補正対象にしない

この補正だけで `+0.0%` にしてはいけない。

- 最終手出しスペース補正は「薄化」だけを担当する
- `+0.0%` は 4 見えや 3 見えシャンポン否定など、後述の物理否定側だけで入れる

### 見え枚数による物理否定

見えている枚数で物理的に成立しない愚形パターンは `+0.0%` とする。

- 対象牌自身が 4 見えなら、その牌の愚形待ちはすべて `+0.0%`
- カンチャンは両隣の必要牌のどちらかが 4 見えなら `+0.0%`
- ペンチャンは `3` なら `1/2`、`7` なら `8/9` のどちらかが 4 見えなら `+0.0%`

例:

- `3` のカンチャン待ちは `24` が必要なので、`2` または `4` が 4 見えなら否定
- `3` のペンチャン待ちは `12` が必要なので、`1` または `2` が 4 見えなら否定

### シャンポンの見え枚数補正

シャンポンだけは対象牌そのものの見え枚数で段階的に落とす。

- 0 見え, 1 見え: `+2.0%`
- 2 見え: `+1.0%`
- 3 見え以上: `+0.0%`

最終手出しスペース補正も同時に掛かる場合は、より小さい値を採用する。

### 愚形濃度補正

対象牌の見え枚数が自分の手牌寄りに偏っている場合は、愚形濃度補正 `+1.0%` を足す。

- 対象牌が 3 見えで、そのうち 2 枚以上を自分が持っている
- 対象牌が 4 見えで、そのうち 3 枚以上を自分が持っている

ただし、対象牌の愚形パターンがすべて物理否定されているなら、この補正は足さない。

## UI 表示

### 自家手牌下バー

- 各牌ごとに、対面・上家・下家それぞれの総合危険度を丸めて表示する
- 分子表示は従来どおり筋本数ベースの raw 値を残す

### 各プレイヤーパネル

`SUMMARY` には 2 系統のランキングを出す。

- 筋ランキング: 従来どおり上位 3 本
- 牌別ランキング: 34 種牌ベースで上位 5 位

牌別ランキングの表示ルール:

- 同率は同じ順位行にまとめる
- 同率で並べる牌は最大 5 牌まで
- % は行の右側に 1 回だけ出す
- 横長パネルでは 2 件ずつ 1 行に畳む
- 縦長パネルでは 5 位まで縦積みする

## 実装ファイル

- ロジック本体: `src/logic/danger_suji.py`
- 見え枚数集計: `src/visible_tiles.py`
- 表示: `src/ui/table_renderer.py`

## 2026-04-10 Addendum
- Opponent-panel summary now exposes two denominator values: the current denominator after temporary-safe suppression and the baseline denominator with temporary-safe suppression excluded.
- The renderer displays that pair as `Remain: current/no-temp` so the panel can show both the current alert-driving count and the structural baseline at once.
- `Remain` yellow/red alert thresholds still follow the current denominator, not the baseline value.
- Player-panel alert sound is transition-driven with stable alert keys, so repeated redraw of the same remain/push condition stays silent.
- `手役傾向` alert is raised after an inner-to-outer tedashi progression continues for additional tedashi: yellow after 2 follow-up tedashi, red when the original progression started from `3..7` and reaches 2 follow-up tedashi, or when any inner-to-outer progression reaches 3 follow-up tedashi.
- `門前 N` alert is computed from the target player's kamicha discards while the target player is still closed. Count only `no-lag` and `not called` discards, deduplicate by 37-kind tile, score suited `2/8` as `+1` each and suited `3..7` as `+3` each, and reset the score to `0` as soon as the target player makes any open meld.
- `染め/対々和 UP` alert is raised when the per-suit removed-line gap on the structural `Remain` side reaches `2.5` or more across man/pin/sou.
- `両面チー3-7` alert is raised when a player makes an open ryanmen chi and the immediate post-call tedashi is a suited `3..7` tile.
- `Push` alert stays visible for `3巡` (`12` global discards). While that latch is active, a newer tedashi genbutsu against the latched push targets converts the indicator into green `Push解除`, which also persists for `3巡`. A new `Push` always overrides an active `Push解除`.
- `Push` also triggers when a player's latest discard is a discard-only shonpai honor tile on that player's `8巡目` or later, even if the normal percentage/remain threshold path does not trigger.

## 2026-04-11 River / UI Addendum
- River marker legend is now: called discard `yellow frame`, post-call tedashi `yellow frame`, lag `blue L`, pon-lag-likely `green Pl`, `3-visible` `pink marker`, awaseuchi `yellow 合`, push `purple P`, and peak thinking-time discard `red diamond`.
- In mahjong terms, awaseuchi means matching the same 34-kind tile immediately after another player's discard.
- This project's display rule uses the retained global river history: another seat's tedashi arms its tile34 for the next five discard increases, and a matching target discard receives the awaseuchi flag.
- A tsumogiri does not arm a source. The target may be tedashi or tsumogiri. Meld and dora events neither arm a source nor consume the five-discard window.
- Red-tint discard highlighting is continuous after any of these trigger points per player: suited tedashi after `Remain(no-temp) < 13`, suited tedashi from the first `inner -> outer` tedashi onward, or any tedashi from the first post-call tedashi (`thinking_time_source == "call"`) onward. River-tint priority is `4-visible purple > brown blocked-sequence > red`.
- `brown` no longer requires prior red-highlight membership. It now means: `tedashi` and the tile belongs to at least one suited `123..789` sequence that is physically denied by `4-visible`. If the tile itself is `4-visible`, purple still wins.
- In the right-side `Visible x3 / x4` detail lists, suited `3..7` tiles are additionally framed (`pink` for `x3`, `purple` for `x4`) so visible central tiles can be spotted without reading the whole row.
- Self-hand honor tiles now show their visible-count digit at the tile's top-right. The self visible-dora pill includes red dora and displays the count with full-width digits.

## 2026-04-11 Lag Marker Addendum

- Green lag markers are now a display-side `pon-lag-likely` class.
- They appear when the same 34-kind tile lags in two or more players' rivers, or when the self-hand snapshot at that discard timing cannot chi/pon the tile.
- This marker split is UI-only and does not change the danger-side lag factor inputs, which still read the canonical `lagged` flags.

## 2026-04-14 River Tint Correction

- The current river-tint renderer is no longer `red AND brown/purple`.
- `purple` now means: `tedashi` and the tile itself is `4-visible`.
- `brown` now means: `tedashi` and the tile belongs to at least one suited `123..789` sequence denied by `4-visible`.
- `red` remains the seat-latched river-highlight path exported from `danger_suji.py`.
- Priority stays `purple > brown > red`.
- `purple` / `brown` are renderer-side projections from actual visible state and do not require red-latch membership.
- Red-latch still matters because once a seat enters the red-latch state, later `tedashi` / post-call `tedashi` remain red candidates for the rest of that hand.
- Current red-latch triggers include:
  - suited `tedashi` after `Remain(no-temp) < 13`
  - suited `inner -> outer` tedashi progression
  - post-call `tedashi`
  - near-by tedashi shape break within `2` numbers in the same suit

## 2026-04-15 No-Temp / River Display Refresh

- `Remain: current/no-temp` の `no-temp` 側は、現行では公開数牌 discard を構造側 suppressor として使う。`called` は「後で鳴かれたか」の結果フラグであり、手出し / ツモ切りの別とは独立。
- river tint は引き続き `purple > brown > red` だが、`purple` / `brown` は renderer 側の tedashi-only projection であり、red-latch への所属を要求しない。
- `purple` は `tedashi` かつその牌自体が `4-visible`。
- `brown` は `tedashi` かつ、3スーツ x `123..789` の `21` 通りのうち、`4-visible` で物理否定された 3 連形にその牌が含まれている状態。
- river marker の現行表記は丸ではなく文字寄りで、lag は `L`, pon-lag-likely は `Pl`, push は `P`, 合わせ打ちは `合` を使う。

## 2026-04-11 見え枚数 / 合わせ打ち / 河 tint 補足

- `見え枚数による物理否定` は愚形加算だけの話ではなく、筋線側の補正と河の強調表示にも効く。
- 跨ぎ筋側の見え枚数ルール:
  - 捨てられた牌自身が `4見え` なら、その牌に対応する跨ぎ筋は `0本` として扱う。
  - 捨てられた牌自身が `3見え` なら、その牌に対応する跨ぎ筋は `0.8本` として扱う。
  - 赤5を切った場合の跨ぎ筋 `3-6` と `4-7` は、それぞれ `0.25本` 扱いとする。
- 本来の合わせ打ちは、他家の打牌に対して直後の打牌で同じ 34 種系の牌を切ることを指す。
- 現行アプリは `LiveRiverStore` 由来の全席捨て牌履歴をglobal discard順で保持し、他家の手出しだけを起点にする。
- 起点からその後5回以内の捨て牌増加で同じ34種牌が切られた場合、target slotへ表示用フラグを付ける。
- 途中にtarget seat自身の別打牌があっても、5打牌窓内なら起点は有効である。
- target側は手出し/ツモ切りを問わないが、起点側のツモ切りは対象外とする。
- 副露公開とドラ表示は起点にせず、5打牌窓も消費しない。
- 牌種比較は34種で行うため、赤5と通常5は同牌種として扱う。
- 合わせ打ちフラグはactual visible / inferred visibleを書き換えず、analysis overlayで対象牌画像上へ黄色の `合` を重ねる。
- `門前 N` の詳細ルール:
  - panel の対象プレイヤー `seat` に対して、score source は `kamicha = (seat - 1) % 4` の捨て牌列だけを使う。
  - `called=True` の捨て牌、鳴かれ確定ラグ、未鳴きラグは数えない。つまり no-lag の捨て牌だけを使う。
  - `tile_34` が数牌 `2..8` でない牌は `0` 点。
  - 数牌 `2/8` は 37 種類ごとに `+1`。
  - 数牌 `3..7` は 37 種類ごとに `+3`。これは画面説明上の `+1 base + 3..7 bonus +2` と同値。
  - 同じ 37 種類は 1 回だけ数えるので、同じ通常牌の重ね切りでは加点しない。
  - 赤5は通常5と別の 37 種類なので、別加点になりうる。
  - 対象プレイヤーが open meld を 1 回でも入れたら、その局の `門前 N` は `0` を返す。
  - alert 色は `3以上 = 黄`, `5以上 = 赤`。
  - ただし赤段階でも、`denominator_count_without_temporary_safe < 13.0` なら renderer は dot 色を紫へ切り替える。
- `手役傾向` の詳細ルール:
  - 判定対象は `tsumogiri=False` の数牌手出し列。`called` は除外条件ではない。
  - 同色ごとに `inside -> outside` bucket の更新を追い、より外側 bucket が後から出た時点を起点に follow-up 手出し数を数える。
  - 黄 alert は、起点打牌のあとにさらに `2` 回の手出しが続いたとき。
  - 赤 alert は、起点時点の以前最高 bucket が `3..7` 域以上で、起点後 `2` 回手出しが続いたとき、または起点後 `3` 回手出しが続いたとき。
- `染/対々和 UP` の詳細ルール:
  - 一時無筋免除を除いた `line_weights_without_temporary_safe` から萬子/筒子/索子の unresolved 本数を出す。
  - 各色の `removed_count = max(0, 6.0 - unresolved_count)` を求める。
  - `max(removed_count) - min(removed_count) >= 2.5` なら alert を立てる。
- `両面チー3-7` の詳細ルール:
  - 対象プレイヤーの open meld を見て、最新の対象 meld が `ryanmen chi` であること。
  - その後の `tsumogiri=False` の打牌で、`thinking_time_source == "call"` のものを post-call tedashi とみなす。
  - その牌が数牌 `3..7` なら alert。
- `思考時間聴牌近` の詳細ルール:
  - `tsumogiri=False`、`thinking_time_source != "call"`、`thinking_time_ms > 0` の打牌だけを抽出する。
  - 直近 `3` 件の `thinking_time_ms` が strict increase `a < b < c` なら logic 側フラグを立てる。
  - 画面表示は追加条件として panel の current `Remain <= 14.0` のときだけ出す。
- `Push` / `Push解除` の詳細ルール:
  - 対象は各プレイヤーの `latest discard` のみ。
  - その牌を synthetic self-hand `1 枚` とみなして、他 seat からの final danger percent を引く。
  - self seat `0` を含む各 target seat のうち、少なくとも 1 人で current `Remain <= 13.0` を満たし、通常は `danger >= 9.0%`、リーチ target だけは `danger >= 6.0%` なら `Push`。
  - 追加例外として、そのプレイヤーの打牌数が `8` 以上で、最新打牌が字牌かつ、それ以前の全河に同牌が 1 枚も無いなら `Push`。
  - 河の `P` と panel の `Push` は同じ起点条件と global discard index を使う。ただし河 `P` だけは各席の1段目（seat-local index 0〜5）を表示せず、2段目以降に描画する。panel 側だけ保持 / `Push解除` を加える。
  - `Push` は `3巡 = 12 global discards` 保持する。
  - 保持中 `Push` の target seat 集合と、後続最新打牌の exact-safe target seat 集合が交差し、その後続打牌が手出しなら `Push解除` に変換する。
  - `Push` 音声は河 `P` の表示対象と同じく各席の2段目以降を対象にし、3巡保持へ入った最初のタイミングだけ鳴らす。`Push解除` は無音。
- 河の赤み対象牌は、各プレイヤーごとに次のいずれかを満たした手出し:
  - `内牌 -> 外牌` が出たあとの数牌手出し全体。
  - `一時無筋免除を除いた Remain` が `13未満` になったあとの数牌手出し全体。
  - `thinking_time_source == "call"` の鳴き手出しが出たあとの手出し全体。
- 河の tint 優先順位は `紫 > 茶色 > 赤`。
  - `紫`: その牌自身が `4見え` で、かつ赤み対象牌でもある場合。
  - `茶色`: 手出し牌のうち、`123..789` x 3スーツ の `21` 通りで `4見え` により物理否定された 3 連形へ属する場合。
  - `赤`: 上記 2 条件に入らない赤み対象牌。
