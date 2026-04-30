# 牌表現ルール

このプロジェクトでは、牌IDの使い分けを次の3層で固定する。

## 基本方針

- 描画や見え枚数カウント以外の内部処理は `tile_136` を正本にする。
- 37種変換は仕様確認用と UI 互換用の 2 系統を持つ。
- 3見え / 4見えの集計だけ 34種へ正規化する。
- 赤牌判定や将来のドラ計算は、37種ではなく `tile_136` の赤IDを基準にする。

## 136枚ID

- packet の牌IDは 0始まりの `tile_136`
- 萬子: `0..35`
- 筒子: `36..71`
- 索子: `72..107`
- 字牌: `108..135`
- 赤5萬: `16`
- 赤5筒: `52`
- 赤5索: `88`

## 37種表現

37種表現は用途ごとに 2 系統ある。

### 37種 spec

- `0..8`: 1m..9m
- `9`: 赤5m
- `10..18`: 1p..9p
- `19`: 赤5p
- `20..28`: 1s..9s
- `29`: 赤5s
- `30..36`: 東 南 西 北 白 發 中

使用箇所:

- export や仕様確認用の内部表現
- [`src/capture/state.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/state.py) の `tile136_to_tile37_spec()`

### 37種 UI

描画用のIDは `assets/tiles/{ID}.png` と一致させる。

- `1..9`: 1m..9m
- `10`: 赤5m
- `11..19`: 1p..9p
- `20`: 赤5p
- `21..29`: 1s..9s
- `30`: 赤5s
- `31..37`: 東 南 西 北 白 發 中

使用箇所:

- [`src/ui/table_renderer.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/ui/table_renderer.py)
- [`src/ui/tile_images.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/ui/tile_images.py)
- [`src/sutehai.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/sutehai.py) の `Discard.tile_id`
- [`src/capture/state.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/state.py) の `tile136_to_tile37_ui()` と `tile136_to_tile37()`

## 34種カウント

3見え / 4見えでは赤を通常5へ畳み込んで数える。

- `5` と `10` は同じ牌種
- `15` と `20` は同じ牌種
- `25` と `30` は同じ牌種

代表IDは非赤側の37種IDをそのまま使う。

- 萬子: `1..9`
- 筒子: `11..19`
- 索子: `21..29`
- 字牌: `31..37`

つまり `Visible x3/x4` では、赤5sを含む 5s が3見えでも `5s` を1枚だけ表示する。

## 現在の実装位置

- 136 -> 37 変換: [`src/capture/state.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/state.py)
  - `tile136_to_tile37_spec()`
  - `tile136_to_tile37_ui()`
  - `tile136_to_tile37()`
- 136 -> 34 変換: [`src/capture/state.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/state.py)
  - `tile136_to_tile34()`
  - `tile136_to_tile34_index()`
- raw 136 を正本に持つ state:
  - [`src/capture/state.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/state.py)
  - [`src/capture/fragment_parser.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/fragment_parser.py)
  - [`src/capture/meld_decoder.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/meld_decoder.py)
  - [`src/capture/tshark_capture.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/tshark_capture.py)
  - [`src/capture/pcap_replay.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/capture/pcap_replay.py)
- 3見え / 4見えの 34種カウント:
  - [`src/visible_tiles.py`](/c:/Users/weath/OneDrive/ドキュメント/tenhou_hojo/src/visible_tiles.py)
  - 現行 GUI 経路: `collect_visible_tile_summary()`
  - raw 136 補助経路: `collect_visible_tile_summary_from_tile136()`

## 実装メモ

- `CaptureState` の live 配列は `live_hand_tiles_136` / `live_meld_tiles_136` / `live_dora_indicator_tiles_136` を使う。
- `RoundState.melds` と `RoundState.discards` も raw `tile_136` を保持する。
- 現行 GUI の 3見え / 4見えは、`tracker` の `called=False` 捨て牌と `RoundState.melds` の full 牌を 37種へそろえて集計する。
- `live_meld_tiles_136` は packet 側で持つ副露寄与分の補助配列として残している。
- GUI へ渡す直前だけ 37種へ変換する。
- export や検証で仕様準拠の 37種が必要な場合は `tile136_to_tile37_spec()` を使う。
- CSV DB の打牌保存でも `discard_tile_136` を raw 正本として保持する。
- live capture と `.pcapng` replay はどちらも同じ raw `tile_136` 正本経路を通す。
