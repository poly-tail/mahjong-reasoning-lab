# 比較痕跡ベース読みエンジン仕様

この文書は、公開格言の寄せ集めではなく、`打牌 = その局面の総合価値比較に負けた牌` という前提から他家の手牌価値レンジを更新するための仕様を整理する。
主語は牌種ではなく `比較痕跡` とし、既存の `danger`、`tenpai_readiness_score`、`hand_value_score`、`push_alert` と無理なく接続する。

## 最重要原則

- 読みの主語は `どの牌が危険か` ではなく、`なぜその牌がそのタイミングで比較負けしたか`。
- 打牌は不要牌ではなく、`ShapeValue / RoleValue / BlockValue / SafetyValue / LocalComboValue` の総合比較に負けた牌である。
- 格言は直接 `danger` に足さず、必ず `comparison_trace` feature に変換してから接続先を分ける。
- 強い役寄り、強い内外偏り、通常面子手からズレた河は、まず `alert` に留める。即 `テンパイ率` に変換しない。
- 既存 `danger_suji.py` は維持する。新規読みは `danger` を上書きせず、必要なものだけ限定橋渡しする。

## 価値軸

| axis | 意味 | 読みでの使い方 |
| --- | --- | --- |
| `ShapeValue` | 純形価値。受け入れ、良形化、くっつきやすさ | 比較の基準軸。逆行したら補助価値を疑う |
| `RoleValue` | 役価値。役牌、タンヤオ、チャンタ、混一色、七対子など | 役種断定ではなく、役レンジの重み更新に使う |
| `BlockValue` | 5ブロック都合、頭候補、ターツ過多不足、両面固定 | ターツ落とし、トイツ落とし、強ターツ外しの主説明軸 |
| `SafetyValue` | 将来安牌、押し引き、守備余地 | 内外切り、役牌残し、孤立牌比較の補助説明軸 |
| `LocalComboValue` | 局所形のコンボ数、変化数、受け入れ被り補正 | 純形価値に逆らう切り順、逆切り、色跨ぎの逆行説明に使う |

`updates_*` 列は、`捨てられた牌に勝って残った側のレンジ更新量` を示す。表記は `強上げ / 中上げ / 弱上げ / 据置 / 弱下げ / 中下げ / 強下げ` とする。

## `hand_analysis` 拡張フィールド案

| field_name | type | 意味 |
| --- | --- | --- |
| `shape_value_rank_at_discard` | `int | None` | その snapshot での候補打牌中、打牌が純形価値で何位だったか |
| `role_subsidy_flag` | `bool` | 純形に逆らってでも役価値で残された痕跡があるか |
| `block_subsidy_flag` | `bool` | 5ブロック都合、頭都合、ターツ過多整理で説明できるか |
| `safety_subsidy_flag` | `bool` | 将来安牌や押し引き都合が残存牌に乗っていたか |
| `local_combo_count` | `int` | 残存牌側の局所コンボ数、または有力変化数 |
| `comparison_trace_class` | `str` | 主説明分類。`role_subsidized_keep` など |
| `comparison_trace_features` | `tuple[str, ...]` | 同 snapshot で成立した trace 名一覧 |
| `comparison_trace_confidence` | `float` | その説明が主因である信頼度。`0.0-1.0` |

## 1. 牌理読みの feature 分類表

| feature_name | description | prior_meaning | updates_shape_value | updates_role_value | updates_block_value | updates_safety_value | updates_local_combo_value | target_output | applicability_scope | strength_weight | exception_rate | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `yakuhai_19_28_compare_prior` | 役牌・19・28 の相対価値を baseline prior として持つ | 純形は `28 > 19` が基本だが、役牌は重なり、鳴き、頭、将来安牌で逆転する | 弱上げ | 弱上げ | 据置 | 弱上げ | 据置 | `hand_value_score / yaku_axis_alert / comparison_trace_alert` | 全局面の事前分布 | 0.35 | 0.45 | 単独 trace ではなく後続 feature の説明基盤。単独加点禁止 |
| `yakuhai_vs_28_keep_trace` | `28` を先に切って役牌を残す | 役牌の補助価値が純形価値をかなり強く逆転した | 弱下げ | 強上げ | 中上げ | 弱上げ | 据置 | `hand_value_score / yaku_axis_alert / comparison_trace_alert` | 序中盤、副露前、比較対象が孤立牌に近い局面 | 0.75 | 0.30 | 役牌生牌、ドラ絡み、頭不足なら強く見る。役牌バック確定とはしない |
| `yakuhai_vs_19_keep_trace` | `19` を先に切って役牌を残す | 役牌側に一時的な役補助、頭補助、安全補助が乗っていた | 据置 | 中上げ | 弱上げ | 弱上げ | 据置 | `hand_value_score / yaku_axis_alert / comparison_trace_alert` | 序中盤、副露前、比較対象が浮き `19` | 0.55 | 0.40 | `28` 先切りよりは軽く扱う |
| `yakuhai_pair_release_trace` | 役牌トイツを落とす | 役価値より標準進行、頭充足、速度優先が勝った | 中上げ | 強下げ | 中上げ | 据置 | 据置 | `hand_value_score / tenpai_readiness_score / comparison_trace_alert` | 役牌がトイツ以上、他に頭候補がある局面 | 0.70 | 0.25 | 役牌が場に枯れている、打点不足でない、頭余りなら強い |
| `yaochu_repeat_shedding_trace` | ヤオチューを連打して処理する | 標準面子手の速度寄り進行か、役寄り要素が薄い可能性 | 弱上げ | 弱下げ | 弱上げ | 弱下げ | 据置 | `tenpai_readiness_score / hand_value_score / comparison_trace_alert` | 序盤、孤立字牌や `19` が複数回連続処理される局面 | 0.45 | 0.45 | 外残し偏重や字牌バックとは切り分ける必要がある |
| `middle_run_456_early_release_trace` | `456` の中張域を早めに処理する | 標準純形より役作り、色、チャンタ寄り、七対子寄りの可能性 | 中下げ | 中上げ | 弱上げ | 据置 | 中上げ | `yaku_axis_alert / nonstandard_shape_alert / comparison_trace_alert` | 序中盤、他に外牌や字牌が残る局面 | 0.40 | 0.55 | 即速度低下やテンパイ遠化へ変換しない。alert 止まり優先 |
| `strong_taatsu_release_trace` | 両面級や強い受け入れを持つターツを外す | 残存ブロックの質、役補助、頭事情がかなり強い | 弱下げ | 中上げ | 強上げ | 据置 | 中上げ | `hand_value_score / nonstandard_shape_alert / comparison_trace_alert` | snapshot 比較で強ターツ外しが確定できる局面 | 0.85 | 0.20 | 検出は強いが、待ち断定には使わない |
| `taatsu_release_trace` | ターツ落としで 6 ブロック以上を 5 ブロックへ整理する | 残形の質が相対的に高い、または役都合で優先形が残っている | 中上げ | 据置 | 強上げ | 据置 | 弱上げ | `danger / tenpai_readiness_score / hand_value_score / comparison_trace_alert` | snapshot 比較で代表的ターツ落としが取れる局面 | 0.80 | 0.25 | `danger` へは既存の `matagi` 補正 selector としてだけ橋渡しする |
| `pair_release_trace` | トイツ落としで頭候補や過剰ブロックを整理する | 頭が足りている、または他ブロック優位で pair が比較負けした | 弱上げ | 据置 | 中上げ | 弱下げ | 据置 | `hand_value_score / tenpai_readiness_score / comparison_trace_alert` | snapshot 比較で pair 余剰が明確な局面 | 0.70 | 0.30 | 七対子軸とは衝突しやすいので visible 河と併用する |
| `inside_to_outside_tedashi_trace` | 同色で内牌から外牌へ手出しが進む | 形固定、安全度重視、情報開示許容の可能性 | 弱下げ | 据置 | 弱上げ | 中上げ | 据置 | `danger / push_alert / comparison_trace_alert` | tedashi 順が同色で `inner -> outer` を作る局面 | 0.35 | 0.55 | `danger` へは既存の inside-outside 係数に限って橋渡しする |
| `outside_to_inside_tedashi_trace` | 同色で外牌から内牌へ手出しが進む | 柔軟性維持、変化保留、情報秘匿の可能性 | 弱上げ | 据置 | 弱上げ | 弱下げ | 弱上げ | `hand_value_score / comparison_trace_alert` | tedashi 順が同色で `outer -> inner` を作る局面 | 0.35 | 0.50 | 単独では弱い。内外 bias 累積の一部として使う |
| `reverse_cut_trace` | 通常の純形順位や visible 価値順位に逆らう切り順 | 局所コンボ保持、情報秘匿、役都合のどれかが働いた | 据置 | 据置 | 弱上げ | 据置 | 中上げ | `hand_value_score / nonstandard_shape_alert / comparison_trace_alert` | 同一スーツや近接比較で順序逆転が取れる局面 | 0.40 | 0.50 | 単独結論禁止。`LocalComboValue` の説明候補として扱う |
| `pure_shape_reversal_trace` | `3 -> 別色1` のような純形価値逆行パターン | 残された外牌側に局所コンボか役補助が埋め込まれていた | 強下げ | 中上げ | 弱上げ | 据置 | 強上げ | `hand_value_score / yaku_axis_alert / nonstandard_shape_alert / comparison_trace_alert` | スーツ跨ぎ比較や色跨ぎ逆行が取れる局面 | 0.65 | 0.45 | 牌種断定はしない。`何の補助価値が乗ったか` の分解に使う |
| `outer_keep_river_bias_trace` | 河全体で外残し傾向が強い | チャンタ、純チャン、七対子、トイトイなど通常面子手からのズレ | 中下げ | 中上げ | 据置 | 据置 | 中上げ | `yaku_axis_alert / nonstandard_shape_alert / comparison_trace_alert` | 河全体の偏りが一定閾値を超えた局面 | 0.30 | 0.60 | alert only。即テンパイ率化しない |
| `post_call_completion_tile_trace` | 鳴き後に完了牌や余剰牌がすぐ手出しされる | 副露で不足ブロックが埋まり、他の整理が先に進んだ | 弱上げ | 据置 | 強上げ | 据置 | 据置 | `danger / tenpai_readiness_score / comparison_trace_alert` | `meld_fact` と直後数打の `discard_fact` を比較できる局面 | 0.80 | 0.20 | `danger` へは既存の鳴き形補正の条件選択子としてだけ橋渡しする |
| `post_tsumogiri_break_tedashi_trace` | ツモ切り増加後に手出しが入る | 選択自由度が減ったあとで、残っていた重要選択が切られた | 据置 | 据置 | 弱上げ | 据置 | 据置 | `tenpai_readiness_score / push_alert / comparison_trace_alert` | 連続ツモ切り後に手出しへ切り替わる局面 | 0.45 | 0.35 | 既存 readiness 文書の時間変化ルールに接続する |

## 2. 読みの 4 カテゴリ

| category | 判定基準 | feature_name | 運用ルール |
| --- | --- | --- | --- |
| `Broad & Strong` | 構造検出が比較的安定し、複数局面で強く効く | `strong_taatsu_release_trace`, `taatsu_release_trace`, `pair_release_trace`, `post_call_completion_tile_trace` | `hand_value_score` と `tenpai_readiness_score` に主接続してよい。`danger` は selector bridge のみ |
| `Broad but Light` | 広く観測できるが例外も多く、補助情報向け | `yakuhai_19_28_compare_prior`, `yaochu_repeat_shedding_trace`, `inside_to_outside_tedashi_trace`, `outside_to_inside_tedashi_trace`, `reverse_cut_trace`, `post_tsumogiri_break_tedashi_trace` | 単独で大きく動かさず、累積や他 feature の文脈として使う |
| `Narrow but Sharp` | 条件が揃うと鋭いが、適用範囲が狭い | `yakuhai_vs_28_keep_trace`, `yakuhai_vs_19_keep_trace`, `yakuhai_pair_release_trace`, `pure_shape_reversal_trace` | precondition が揃ったときだけ強く更新する。役種断定には使わない |
| `Alert Only` | 有効だが即スコア化すると誤差が大きい | `middle_run_456_early_release_trace`, `outer_keep_river_bias_trace` | `yaku_axis_alert` や `nonstandard_shape_alert` 止まり。即テンパイ率化しない |

## 3. 代表的な読みの整理

| 読みパターン | 対応 feature | 比較負けの主因 | 更新すべきレンジ | してはいけない変換 | 主接続先 |
| --- | --- | --- | --- | --- | --- |
| 役牌・19・28 の比較 | `yakuhai_19_28_compare_prior` | 純形では `28 > 19` だが、役牌は `RoleValue` と `SafetyValue` で逆転しうる | 役牌の補助価値を持つ prior | `役牌残し = 役牌バック確定` にしない | `hand_value_score`, `yaku_axis_alert` |
| 役牌トイツ落とし | `yakuhai_pair_release_trace` | 役価値より頭充足と速度が勝った | 標準面子手、速度寄り | `役なしだから安全` にしない | `hand_value_score`, `tenpai_readiness_score` |
| ヤオチュー連打 | `yaochu_repeat_shedding_trace` | 標準進行が優位、役寄り補助が薄い | 通常手レンジを弱く上げる | `テンパイ確率の直上げ` をしすぎない | `tenpai_readiness_score` |
| 456 先切り | `middle_run_456_early_release_trace` | 純形速度より役・色・非標準形の優先 | `yaku axis` と非標準形 alert | `遠い = 遅い` と短絡しない | `yaku_axis_alert`, `nonstandard_shape_alert` |
| 強ターツ外し | `strong_taatsu_release_trace` | 残存ブロック質、打点補助、頭事情が強い | 高品質残形レンジ | `危険牌決め打ち` にしない | `hand_value_score` |
| ターツ落とし | `taatsu_release_trace` | 6 ブロック以上を 5 ブロックへ整理した | 残形質、速度寄り、matagi bridge | 新規格言を `danger` へ直足ししない | `tenpai_readiness_score`, `hand_value_score`, bridge to `danger` |
| トイツ落とし | `pair_release_trace` | 頭足り、または block overflow 整理 | 頭事情が整った標準手レンジ | 七対子否定の断定にしない | `hand_value_score` |
| 内→外切り | `inside_to_outside_tedashi_trace` | 形固定か安全重視か情報開示許容 | `SafetyValue` と固定度 | `即テンパイ率化` しない | `push_alert`, bridge to `danger` |
| 外→内切り | `outside_to_inside_tedashi_trace` | 柔軟性維持、変化保留、情報秘匿 | 変化余地レンジ | `役なし` とみなさない | `hand_value_score` |
| 逆切り | `reverse_cut_trace` | 局所コンボ保持か、情報を隠す比較 | `LocalComboValue` 優位レンジ | pattern だけで役断定しない | `comparison_trace_alert` |
| 28 先切り役牌残し | `yakuhai_vs_28_keep_trace` | 強い純形価値を role/block が逆転 | 役補助が濃いレンジ | `役牌重なり待ち一本` にしない | `hand_value_score`, `yaku_axis_alert` |
| 19 先切り役牌残し | `yakuhai_vs_19_keep_trace` | 軽い純形差を role/safety が逆転 | 役牌の補助価値を持つレンジ | `安全牌抱え込み` と決め打ちしない | `hand_value_score`, `yaku_axis_alert` |
| `3 -> 別色1` 型の純形価値逆行 | `pure_shape_reversal_trace` | 別色 `1` 側に local combo か role 補助があった | 非標準形か局所コンボ寄りレンジ | `チャンタ確定` にしない | `hand_value_score`, `nonstandard_shape_alert` |
| 外残し傾向の強い河 | `outer_keep_river_bias_trace` | 通常面子手からズレた全体志向 | 非標準形 alert | `テンパイ率` へ直変換しない | `yaku_axis_alert`, `nonstandard_shape_alert` |
| 鳴き後の完了牌 | `post_call_completion_tile_trace` | 副露完了で block 再配置が起きた | block 整理が進んだレンジ | `鳴いたから即危険` にしない | `tenpai_readiness_score`, bridge to `danger` |
| ツモ切り増加後の手出し | `post_tsumogiri_break_tedashi_trace` | 選択自由度低下後の重要選択露出 | 終盤寄り readiness | `即テンパイ断定` にしない | `tenpai_readiness_score`, `push_alert` |

## 4. 既存ロジックへの接続先

記号は `P = primary`, `B = limited bridge`, `A = alert only`, `- = no direct connection` とする。

| feature_name | danger | tenpai_readiness_score | hand_value_score | push_alert | yaku_axis_alert | nonstandard_shape_alert | comparison_trace_alert | bridge_rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `yakuhai_19_28_compare_prior` | - | - | P | - | A | - | P | 事前分布だけに使う |
| `yakuhai_vs_28_keep_trace` | - | - | P | - | P | - | P | 役牌が未枯れ、または頭不足時に重みを上げる |
| `yakuhai_vs_19_keep_trace` | - | - | P | - | P | - | P | `28` より軽く扱う |
| `yakuhai_pair_release_trace` | - | B | P | - | A | - | P | 標準進行への復帰として readiness を軽く上げる |
| `yaochu_repeat_shedding_trace` | - | P | B | - | A | - | P | 序盤の速度寄り更新に限定 |
| `middle_run_456_early_release_trace` | - | - | - | - | A | A | P | alert only |
| `strong_taatsu_release_trace` | - | B | P | - | - | P | P | 非標準形 alert とセットで使う |
| `taatsu_release_trace` | B | P | P | - | - | - | P | 既存 `matagi` / `taatsu-drop` selector にだけ橋渡し |
| `pair_release_trace` | - | B | P | - | - | - | P | 頭事情の更新に使う |
| `inside_to_outside_tedashi_trace` | B | - | - | A | - | - | P | 既存 inside-outside 係数への selector のみ |
| `outside_to_inside_tedashi_trace` | - | B | B | - | - | - | P | 単独で大きく動かさない |
| `reverse_cut_trace` | - | - | B | - | - | A | P | `LocalComboValue` 仮説として保持 |
| `pure_shape_reversal_trace` | - | - | P | - | A | P | P | 非標準形と局所コンボの両面で扱う |
| `outer_keep_river_bias_trace` | - | - | - | - | A | P | P | alert only |
| `post_call_completion_tile_trace` | B | P | B | - | - | - | P | 既存鳴き補正の条件選択だけに使う |
| `post_tsumogiri_break_tedashi_trace` | - | P | - | P | - | - | P | 時間変化系の readiness 補助に限定 |

## 5. 実装方針

### 5.1 手牌 snapshot から計算するもの

| 計算項目 | 内容 | 主用途 |
| --- | --- | --- |
| `candidate_discard_shape_rank` | snapshot の候補打牌を `ShapeValue` 順に並べた順位 | `shape_value_rank_at_discard` の元データ |
| `kept_vs_discard_role_delta` | 捨て牌と残存牌の `RoleValue` 差分 | 役牌残し、456 先切り、純形逆行説明 |
| `kept_vs_discard_block_delta` | 5 ブロック都合、頭候補、過剰ターツ整理の差分 | ターツ落とし、トイツ落とし、強ターツ外し |
| `kept_vs_discard_safety_delta` | 将来安牌、押し引き余地の差分 | 内外切り、役牌残しの補助説明 |
| `kept_vs_discard_local_combo_count` | 残存牌側に埋まる有力変化数、受け入れ被り補正込みコンボ数 | 逆切り、純形逆行、外残し系 |
| `comparison_trace_class` | もっとも説明力の高い軸を `role/block/safety/local_combo/mixed` で分類 | UI 表示、分析列、alert 出力 |

### 5.2 `discard_fact` / `meld_fact` / visible tiles から計算するもの

| 入力 | 計算項目 | 主用途 |
| --- | --- | --- |
| `discard_fact` | tedashi / tsumogiri 列、同色内外順、ヤオチュー連打、逆切り候補 | 河から取れる比較痕跡 |
| `discard_fact` + snapshot | ターツ落とし、トイツ落とし、強ターツ外しの確定 | `BlockValue` 主説明 feature |
| `meld_fact` + `discard_fact` | 鳴き後の完了牌、鳴き直後の block 再配置 | 副露後進行の把握 |
| visible tiles | 役牌の生牌度、枯れ具合、`19/28` の場況補正 | 役牌比較の強弱調整 |
| visible river aggregate | 外残し率、内外偏り、色偏り、ヤオチュー残存率 | alert 系の全体判定 |
| timing sequence | ツモ切り増加後の手出し、連続無選択後の break | readiness / push 補助 |

### 5.3 deterministic に近い feature

| feature_name | deterministic に近い部分 | 使い方 |
| --- | --- | --- |
| `taatsu_release_trace` | snapshot 比較で `AB -> A/B` の代表的整理が取れる | `BlockValue` 主説明として使う |
| `pair_release_trace` | snapshot 比較で `AA -> A` の整理が取れる | 頭都合の更新に使う |
| `strong_taatsu_release_trace` | 両面級や強受け入れ形の外しが明確 | 強い比較痕跡として `hand_value_score` へ寄与 |
| `yakuhai_pair_release_trace` | 役牌 pair の drop が明確 | 役価値低下と標準進行化の根拠にする |
| `post_call_completion_tile_trace` | 鳴き直後の余剰整理が系列として取れる | 副露後進行の根拠にする |

検出は deterministic に近くても、解釈は確率的である。`deterministic に取れる = 断定してよい` ではない。

### 5.4 prior / alert に留めるべき feature

| feature_name | 留める理由 | 主接続先 |
| --- | --- | --- |
| `yakuhai_19_28_compare_prior` | 事前分布であり、単独では比較痕跡にならない | `hand_value_score`, `yaku_axis_alert` |
| `middle_run_456_early_release_trace` | 例外が多く、速度推定へ直結しにくい | `yaku_axis_alert`, `nonstandard_shape_alert` |
| `outer_keep_river_bias_trace` | 河全体の偏りは役寄りと七対子寄りが混ざる | `yaku_axis_alert`, `nonstandard_shape_alert` |
| `reverse_cut_trace` | `LocalComboValue` と情報秘匿が分離しづらい | `comparison_trace_alert` |
| `inside_to_outside_tedashi_trace` | 安全重視と形固定が混ざりやすい | `push_alert`, selector bridge to `danger` |

### 5.5 direct `danger` 加点を絶対にしない feature

| feature_name | 理由 |
| --- | --- |
| `yakuhai_19_28_compare_prior` | 牌種比較の prior を危険牌加点へ直結すると格言直足しになる |
| `yakuhai_vs_28_keep_trace` | 役寄り推定と危険牌推定は別軸。役牌残しだけでは待ちが絞れない |
| `yakuhai_vs_19_keep_trace` | 同上。安全牌保持や頭保持と混ざる |
| `middle_run_456_early_release_trace` | 非標準形 alert を危険牌加点へ直結すると過大評価しやすい |
| `pure_shape_reversal_trace` | `LocalComboValue` は危険牌そのものを直接特定しない |
| `outer_keep_river_bias_trace` | 河の偏りは役レンジ alert であり、待ち牌危険度ではない |
| `reverse_cut_trace` | 切り順逆転だけでは待ちの位置情報にならない |

### 5.6 `danger` へ橋渡ししてよい feature

| feature_name | bridge 先 | 橋渡しの仕方 |
| --- | --- | --- |
| `taatsu_release_trace` | 既存 `matagi` / `taatsu-drop` | 新規加点ではなく、既存 selector の有効化条件に使う |
| `inside_to_outside_tedashi_trace` | 既存 inside-outside 係数 | 同色 `inner -> outer` の line factor 選択に限定する |
| `post_call_completion_tile_trace` | 既存鳴き形補正 | 副露後数打以内の形完了を補助条件として使う |

## 調停原則

| 競合 | prior にするもの | 調停案 |
| --- | --- | --- |
| `danger` の既存 `ターツ落とし` と comparison trace の `strong_taatsu_release_trace` | 既存 `danger` | `danger` は既存係数を維持し、新 feature は `hand_value_score` と alert 側へ出す |
| `inside_to_outside` の危険度補正と `SafetyValue` 解釈 | 既存 `danger` | `danger` は line factor、読み側は `push_alert` と `comparison_trace_alert` へ分離する |
| 役牌残しと標準進行推定の衝突 | `comparison_trace` | `hand_value_score` は役補助更新、`tenpai_readiness_score` は据置寄りにする |
| 外残し河と速度推定の衝突 | alert 側 | `yaku_axis_alert` / `nonstandard_shape_alert` 止まりで保持する |

## 次の実装単位

- `src/logic/hand_analysis.py` に `comparison_trace` 判定用 dataclass と `shape_value_rank_at_discard` 算出を追加する。
- `discard_fact` へ comparison trace 列を追加し、snapshot 比較から `taatsu/pair/strong_taatsu` を export する。
- `meld_fact` と `discard_fact` をつないで `post_call_completion_tile_trace` を算出する。
- `danger_suji.py` には新加点を足さず、既存 selector に `comparison_trace` bridge を受ける入口だけ追加する。
- UI / 分析側では `comparison_trace_alert`, `yaku_axis_alert`, `nonstandard_shape_alert` を別表示にして、`tenpai_readiness_score` と混ぜない。
