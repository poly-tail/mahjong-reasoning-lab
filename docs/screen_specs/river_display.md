# 河表示仕様

updated: `2026-09-03`

## 目的

河の捨て牌、枠、marker、tint、思考時間帯、Push 反映の仕様をまとめる。v2.2 では表示仕様に加えて、base river layer と analysis overlay layer の描画責務もここへ明記する。

## 枠

| 表示 | 意味 |
| --- | --- |
| 黄色枠 | 後続の鳴きで消費された捨て牌 |
| 黄枠 | 鳴き直後の手出し |

## marker

| marker | 意味 |
| --- | --- |
| `L` | 通常 lag |
| `Pl` | pon-lag-likely。複数人 lag、または自分手牌 snapshot でチー/ポン不能な lag |
| `P` | Push alert 対象のうち、各席の2段目以降にある捨て牌 |
| `合` | 他家の手出しから5回以内の捨て牌増加で同じ34種牌を切った合わせ打ち |
| 赤ひし形 | その局で最長の思考時間 |
| ピンク丸 | 3見え |

河の `P` は、各席の捨て牌 local index 0〜5（1段目）には描画せず、index 6 以降（2段目以降）だけ描画する。Push 判定、global discard index、panel 表示、3巡保持、`Push解除` はこの表示 gate で変更しない。表示対象の更新では `Push` 音声と同じ redraw 内で `P` を表示し、音声だけ先に出る状態を避ける。

合わせ打ちの起点は他家の手出しだけとする。その後5回以内の全席捨て牌増加に同じ34種牌があればtarget slotへ表示用フラグを付ける。途中にtarget seat自身の別打牌があっても窓内なら有効とし、副露・ドラ表示は起点にも窓消費にも使わない。targetは手出し/ツモ切りを問わない。判定は保持済みriver historyから候補を作り、`awaseuchi confirm` background workerで確認する。

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

### base river redraw と overlay 更新

Canvas の base river layer は full redraw 境界では全削除・全描画する。cached-layout redraw では slot 単位の表示シグネチャ cache と Canvas item tag の存在を確認し、変化のない base 牌を再利用する。

full redraw 境界は次を必ず行う:

- `live_async_discards` tag を全削除する
- `discard_render_cache_by_key` / `discard_tile_image_refs` を reset する
- 入力 `discard_map` の全捨て牌を描き直す
- analysis overlay を別 layer として更新する。同一 signature の overlay は削除・再描画しない

cached-layout redraw では、per-slot signature が一致し、かつ `live_async_discards_<seat>_<index>` tag の image item が Canvas 上に存在する場合だけ牌描画を skip できる。tag が消えている場合は cache hit でもその slot を再描画する。副露直後の短い projection は `_draw_discards()` 前の round cache merge で保持し、通常 redraw では不要な全牌再作成を避ける。

副露 `call` event の redraw 後だけ、`discard_map` に残る slot の `live_async_discards_<seat>_<index>` image item が Canvas 上に存在するかを明示検査する。配列にはあるのに Canvas item が無い slot があれば、同じ refresh 内で描かず通常 redraw へ戻す。async-only refresh でも同じ欠け検査だけを行い、欠けがあれば通常 redraw へ戻す。副露で table frame の署名が変わる場合は、frame 内の opaque な discard zone が既存河 item の前面へ作られるため、frame 再作成前に base river / analysis overlay と描画 cache を invalidate し、同じ redraw 内で frame の後に河を全描画する。復元は表示 layer に限定し、capture 履歴や tracker へは書き戻さない。

analysis overlay だけを再描画できる条件:

- red / brown / four-visible tint が変わった
- 見え枚数 marker が変わった
- Push `P` marker が追加または削除された
- 合わせ打ちの `合` が変わった

click spec と lag marker reference spec は毎 redraw で復元する。

河配列の base river は `LiveRiverStore.snapshot_by_seat()` を正本にする。副露直後に鳴かれた牌が browser 上の河から消えても、packet 側の `N` 処理で該当 discard に `called=True` と call lag metadata を付け、履歴からは削除しない。`CaptureState.live_stable_discard_map` は最後に `LiveRiverStore` 由来で安全に発行できた表示用 copy であり、同一 `LiveRiverStore.epoch` 内では短い snapshot で上書きしない。cached `LiveTableSnapshot` が古い/短い `discard_map` を返す場合だけ表示用 `discard_map` を補強し、capture state lock が busy の場合も stable copy の optimistic read だけで補強する。capture 履歴へは書き戻さない。Bridge の `riverEntriesBySeat` は browser に見えている lossy projection であり、projection-only として別保管するだけで既存 base river へ merge しない。Bridge bootstrap は空 store の表示開始点としてだけ reset + seed でき、非空 store は clear できない。REINIT / INITBYLOG / spectator WGC の `kawa0..kawa3` は packet snapshot 側の projection として parser が扱い、同一局判定では visible river を tile34 牌種で比較する。

live async-only refresh は side panel / hand overlay / alert 表示と analysis overlay だけを更新し、通常は `_draw_discards()` を呼ばない。`partial_snapshot.discard_map` は河描画へ流し込まず、async-only refresh は `live_async_discards` 全体 tag を削除しない。async-only refresh が差し替えてよい河関連 tag は `live_discard_analysis_overlay` だけである。最新 event が `call`、または `LiveTableSnapshot.recent_event_types` に `call` が残るときに Canvas item 欠落を検知した場合は、async-only refresh を中断して通常 redraw へ戻す。

renderer の per-round cache は履歴正本ではなく、Canvas base river layer を同一局の短い projection から守る表示用 cache である。full redraw / cached-layout redraw の入力が前回表示より短い場合は、`_draw_discards()` 前に前回 slot を display-only で保持し、欠落した slot を `called=True` として黄色枠表示する。同じ牌種の `called=True` slot が後続の uncalled visible discard を消費してはいけない。保持した表示 slot は `round_state.discards` / tracker へ書き戻さない。

最新 event が `call`、または recent event context に `call` が残るときに renderer が前回より短い `discard_map` を受けて slot を保持した場合は、`UI called discard short input` を `logs/live_capture.log` へ出す。call 直後または delayed call frame の後に Canvas の既存 discard slot を削除した場合は `UI called discard stale delete` を出し、削除 key、前後 count、round identity、refresh token を残す。配列に残る slot の Canvas image item 欠落を検知して通常 redraw へ戻す場合は `UI called discard canvas repair deferred` を出し、missing key、round identity、refresh token を残す。

実際の `INIT` は `allow_non_empty_clear=True` で `LiveRiverStore` を reset + seed する。confirmed different `REINIT` も同じ opt-in を使える。INIT を取れない packet-first round、`INITBYLOG`、`WGC`、Bridge、live resync は `INIT_NEW_ROUND` authority 名義でも非空 store を clear できない。同一局の短い非空 projection は表示用 cache でも base river を短縮しない。ただし renderer cache が前回 river を保持できるのは同一 `LiveRiverStore.epoch` 内だけであり、epoch が変わったら前局 river を復活させてはいけない。

### 画像と overlay

- base river layer は牌画像本体、手出し/ツモ切り、思考時間 band、lag、`called=True` 黄色枠、リーチ棒を持つ。
- analysis overlay layer は red / brown / four-visible tint、見え枚数 marker、2段目以降の Push `P`、合わせ打ちの `合` を持つ。
- `_discard_tile_image()` は base river 用の通常牌画像と思考時間 band だけを返す。
- discard item は作成時に `live_async_discards` と `live_async_discards_<seat>_<index>` tag を付ける。
- analysis overlay item は `live_discard_analysis_overlay` tag を付ける。analysis overlay の更新で `live_async_discards` tag を削除してはいけない。

## 関連

- [alerts_and_panels.md](./alerts_and_panels.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- [../specs/current.md](../specs/current.md)
