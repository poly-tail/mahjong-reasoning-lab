# 性能ホットスポット

更新日: `2026-09-03`

## 現在の重点

UI の重さは主に次の層で見る。

1. `side_panels`
2. `discards`
3. visible / suji / push / same-jun の派生計算
4. background thread の多重起動
5. Bridge / NAGA / Nodocchi の外部問い合わせ

## `discards`

### 以前の問題と現在の判断

- 河を描き直すたびに最大 `4人 x 18枚` を全描画していた。
- `_discard_tile_image()` が赤/茶/紫/4見え/思考時間の組み合わせごとに色付き `PhotoImage` を作っていた。
- Canvas item を作った後に `find_all()` で差分取得し、後付け tag を付けていた。

副露直後の表示正しさは round cache merge、Canvas item 生存確認、layer invalidation 境界で守る。base river layer は full redraw 境界では全削除するが、cached-layout redraw では per-slot signature cache を使い、変化のない base 牌を再利用する。ただし meld などで table frame の署名が変わる場合、frame の opaque な discard zone が既存河を前面から覆うため、base river / analysis overlay と描画 cache を invalidate し、同じ redraw 内で frame の後に全河を作り直す。analysis overlay / side panel / hand overlay の async-only refresh は通常 base river を触らない。副露 `call` event 後に配列へ残る slot の Canvas image item 欠落を検知した場合も、その場では描かず通常 redraw queue へ戻す。

### 現行対策

- full redraw 境界では `live_async_discards` tag を全削除し、`discard_render_cache_by_key` / `discard_tile_image_refs` を reset してから、入力 `discard_map` の全捨て牌を描き直す。
- cached-layout redraw では per-slot signature cache を使う。cache hit でも Canvas item tag の image item が存在することを確認し、item が無い slot は再描画する。生存確認は `live_async_discards` parent tag を1回走査して image item tag set を作り、slot ごとの `find_withtag` 連打を避ける。
- 副露 `call` event、または `LiveTableSnapshot.recent_event_types` に `call` が残る redraw / async-only refresh 後だけ、`discard_map` に残る slot の Canvas image item 生存を明示検査する。欠けがある場合は同じ refresh 内で描かず通常 redraw queue へ戻す。table frame cache hit では既存河を再利用し、cache miss のときだけ base river / analysis overlay を全再作成するため、通常 redraw の全牌再作成には戻さない。
- click spec と lag marker reference spec は毎回復元する。
- 捨て牌履歴の base river 正本は `LiveRiverStore` に置く。live snapshot builder は `LiveRiverStore.snapshot_by_seat()` から `discard_map` を作り、renderer cache から履歴を補完しない。`CaptureState.live_stable_discard_map` は `LiveRiverStore` 由来で最後に安全に発行できた表示用 copy としてだけ使い、同一 `LiveRiverStore.epoch` 内では短い snapshot で上書きしない。cached `LiveTableSnapshot` が古い/短い場合は stable copy で表示用 `discard_map` を補強し、capture state lock が busy の場合も stable copy の optimistic read だけで補強するが、capture 履歴へは書き戻さない。Bridge `riverEntriesBySeat` は projection-only として別保管し、既存 base river へ merge しない。Bridge bootstrap は空 store の表示開始点としてだけ reset + seed でき、非空 store は `INIT_NEW_ROUND` 名義でも clear できない。renderer cache は履歴正本ではないが、同一局の full redraw に短い `discard_map` が来た場合は Canvas base river layer を display-only で保持する。さらに通常の round cache が reset されても、最後に描けた base river backup を `LiveRiverStore.epoch` 境界まで保持し、`round_identity=None` や短い/空 projection では画面の欠落 slot を backup から復元する。
- suji / red tint / visible count / push alert の async-only refresh は通常 side panel / hand overlay / alert 表示と `live_discard_analysis_overlay` だけを更新し、`_draw_discards()` を呼ばない。`partial_snapshot.discard_map` は河描画へ渡さない。例外は副露直後、または snapshot lag で latest event が次の discard に進んでも recent event context に `call` が残る場合の Canvas item 欠落検知時だけで、この場合は async-only refresh を中断して通常 redraw queue へ戻す。
- heavy suji / 危険度の最新 input signature が計算中でも、同一局の直前完了 bundle を side panel / hand / analysis overlay の表示 fallback として保持する。手牌 danger は旧 bundle の `hand_tiles` から現在手牌へ牌 ID と同牌内の出現順で再対応付けする。loading summary や空の危険度配列による中間 redraw を避け、bundle 完了時だけ async subtoken を進めて対象 layer を partial refresh する。base river / table frame は触らない。
- stale bundle は描画継続専用であり、自動打牌や alert 音声の新規判定へ流さない。完了値がない初回と `round_identity` が変わる新局では fallback を使わない。
- 実際の `INIT` は `allow_non_empty_clear=True` で `LiveRiverStore` を reset + seed する。confirmed different `REINIT` も同じ opt-in を使える。`INITBYLOG` / `WGC` は snapshot の `log` / `id` または完全な `(kyoku, honba, kyotaku, oya)` tuple が `LiveRiverStore.round_key` と明確に異なる場合だけ、同じ opt-in で非空 store を reset + seed できる。INIT を取れない packet-first round、同一/不明 key の `INITBYLOG` / `WGC`、Bridge、live resync は非空 store を clear できず、projection-only または append-only に倒す。cached-layout redraw は `_draw_discards()` 前に `_merge_discard_map_with_round_cache()` を通すため、短い非空 projection だけで base river layer を短縮しない。ただし短い river の保持は同一 `LiveRiverStore.epoch` 内だけに限定し、epoch が変わったら前局 cache を破棄する。
- 副露直後の捨て牌消失診断ログは、parser count guard 違反時、または最新 event / recent event context に `call` がある renderer short-input / stale-delete / canvas-repair 検出時だけ出す。Canvas repair defer は副露直後または delayed call frame 後だけ active slot の tag 生存を見て、欠けがある場合だけ通常 redraw queue へ戻す。
- `_discard_tile_image()` は base river 用の通常牌画像と思考時間 band だけを返す。
- red / brown / four-visible tint、見え枚数 marker、Push `P`、合わせ打ちの `合` は analysis overlay layer で描画する。同一 signature の overlay は削除・再描画しない。
- 合わせ打ちは `LiveRiverStore` 由来の全席discard履歴をappend順で再利用する。直近5捨て牌だけをdequeへ保持して候補抽出し、候補がある状態だけ不変event streamを既存の `awaseuchi confirm` workerへ渡す。副露・ドラ表示は5打牌窓に入れない。
- discard item は作成時に `tags=` を渡す。

### slow log

`UI discards slow` は次を出す。

- `cache_before`
- `items_after`
- `active`
- `drawn`
- `skipped`
- `changed`
- `stale_deleted`
- phase breakdown

## `suji / danger / push`

重くなりやすい処理:

- 牌ごとに同じ 18 筋線へ見え枚数濃度補正を掛け直し、numerator / denominator を再集計する処理
- 過去 Push 回数の各 prefix で、実際の discard actor 以外も含む全 actor の profile を構築する処理

現行対策:

- 各 target seat / `include_temporary_safe` mode の筋計算は、固定 18 行の immutable `SujiLineTable` を 1 回構築する。rule family ごとの係数列を残したまま、raw / base / concentrated の denominator と 34 要素 numerator を先に集計し、候補牌ごとは strict `> 10%` gate で配列を選ぶだけにする。
- table は build-local derived state とし、公開 `OpponentSujiDangerProfile` や `RoundState` / `_danger_suji_runtime_cache` へ追加しない。濃度投影は `line_weights + visible_counts_34` を完全keyとする上限512件のpure memoで再利用する。入力値が変われば必ず別keyになり、cross-refresh の row mutation / event invalidation は導入しない。
- `_historical_push_count_by_seat()` は各 prefix の discard actor だけを `build_latest_discard_push_alert_percentages()` の内部対象へ渡す。従来の全 actor 評価から不要な profile 構築だけを除き、返却値と既存の履歴 result cache は維持する。

2026-09-03 の同一プロセス paired benchmark（synthetic 4-seat round、I/O なし、変更前 `219423d` と CH-241 を交互に 9 回実行した中央値）:

| global discards | 変更前 | CH-241 | 短縮率 |
| ---: | ---: | ---: | ---: |
| 16 | 29.145 ms | 20.053 ms | 31.2% |
| 32 | 47.984 ms | 28.720 ms | 40.1% |
| 48 | 71.073 ms | 39.421 ms | 44.5% |
| 64 | 98.224 ms | 52.577 ms | 46.5% |
| 72 | 113.793 ms | 60.361 ms | 47.0% |

32 打牌では profile build が `219 -> 84`、実質 line 計算が `235 -> 100`、concentration の候補牌ごとの 18 行再走査が `902 -> 0` となった。時間値はローカル比較用であり CI の固定閾値にはしない。

同じ32打牌局面の単発31回中央値では、profile 1件が `0.1891 -> 0.2720 ms`、legacy map 1件が `0.0940 -> 0.1817 ms`、latest Push 1件が `1.8671 -> 2.6253 ms` と、それぞれ table materialize 分だけ遅くなった。局所差は1回あたり1ms未満であり、heavy bundle 全体では候補牌再走査と履歴 actor の削減が上回る。今後この局所経路を増やす場合は再計測する。

既知の未解決事項:

- panel の no-temp line table 構築経路は `visible_counts_34` を伝播していない。これは今回以前からの数値挙動であり、意味保存のため本変更では補正しない。
- heavy suji input signature は、危険度ロジックが参照する `Discard.riichi_marker_before` と `Meld.called_tile_id` をまだ含まない。今回の table は cross-refresh cache ではないため、この既存 freshness debt は別の signature 修正と回帰テストで扱う。

## `side_panels`

重くなりやすい処理:

- `SUMMARY` の line ranking
- safe hand ranking
- 危険ランク描画
- Nodocchi `STATUS`
- player memo / detail image

現行対策:

- side panel signature cache を持ち、変化がない場合は描画を再利用する。
- heavy suji / 危険度 worker の pending 中は直前完了 bundle の signature を維持し、placeholder への差し替えで既存 panel を消して描き直さない。
- Nodocchi は background thread + canvas queue へ逃がす。
- font measure は canvas-local cache を使う。
- slow log で phase breakdown を出す。

## background thread

常時多重起動を避ける対象:

- live suji bundle
- live red tint
- inferred visible
- awaseuchi confirm
- pystyle fetch
- Nodocchi status fetch
- NAGA query / NAGA auto query
- alert audio

方針:

- 同一 key の in-flight を持つ。
- `1 in-flight + pending 1` で十分なものは coalescing する。
- UI refresh token を background 完了だけで増やし続けない。

## 調査手順

1. stdout / 診断ログで `UI redraw slow`, `UI side_panels slow`, `UI discards slow` を見る。
2. `phases=[...]` の上位を見る。
3. `discards` では cached-layout redraw で `skipped` が増えているかを見る。full redraw 直後や実打牌 slot では `drawn` が増えるが、同一入力の再描画で `drawn` が入力牌数に近いままなら cache validation / layout identity を疑う。
4. `side_panels` では signature cache が hit しているかを見る。
5. `BG ... xN` が増え続ける場合は worker in-flight 管理を疑う。

## 計測単位

性能改善時は「速くなったはず」で終わらせず、同じ入力条件で次を分けて測る。

- tshark外部process待ち時間
- line split
- payload field選択
- fragment extraction
- fragment parse
- state mutation
- `state_lock` 取得待ち時間
- `state_lock` 保持時間
- DB snapshot作成
- DB queue待ち時間
- DB書込み
- live snapshot複製
- visible summary
- suji / danger / push
- UI redraw
- discard描画
- side panel描画

計測は `time.perf_counter_ns()` などの monotonic 高分解能時計を使い、1 packet ごとの同期ログではなく集計値として `count`, `total`, `mean`, `p50`, `p95`, `max` を低頻度に出す。実機計測できない場合は数値を記載せず、fixture、手順、未取得理由だけを残す。

parser-only benchmark では sleep と DB を無効化し、parser+state、DB込み、UI込みの結果と混ぜない。

## 関連

- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../screen_specs/alerts_and_panels.md](../screen_specs/alerts_and_panels.md)
- [../specs/current.md](../specs/current.md)
- [../operations/regression_checklist.md](../operations/regression_checklist.md)
