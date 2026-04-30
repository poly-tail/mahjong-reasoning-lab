# Tenhou Hojo Helper API仕様書 v1.3
> 2026-03-31 時点の仕様。パケットキャプチャ入力は、固定位置切り出しではなく、時刻付きテキスト出力と XML 断片抽出を前提とする。

## 1. 目的
- `tshark` によるパケットキャプチャ結果から、対局状態をできるだけ多く構造化して保持する。
- GUI 描画、詳細情報表示、後続の DB 保存、将来の解析拡張に使える入力状態を整備する。
- 現行実装よりも多くの変数、配列、辞書へ情報を格納する設計方針を定義する。

## 2. 基本方針
- `line[12:15]` のような固定位置切り出しは採用しない。
- `tshark` の `frame.time_epoch` を必ず取得し、イベント時刻の基準とする。
- ペイロードは 1 行 1 タグ前提ではなく、1 行に複数タグが含まれる前提で扱う。
- XML 断片を正規表現で抽出し、タグごとに XML パースまたは短縮タグパースを行う。
- 未解釈タグや不明断片も破棄せず、後で分析できるよう保持する。

## 3. `tshark` 入力仕様
### 3.1 出力形式
- `-T fields` を使用する。
- 表示フィルタは `-Y "websocket"` を使う。
- 最低限、以下のフィールドを取得する。
  - `frame.time_epoch`
  - `text`
- live capture では interface 指定で `tshark` を起動する。
- test replay では `tshark -r INPUT_PCAPNG -o tls.keylog_file:...` を使い、`.pcapng` を TLS 復号しながら読む。

### 3.2 行の解釈
- 1 行は `frame.time_epoch` と `text` フィールドの組として扱う。
- 区切りはタブを前提とする。
- `text` フィールド内に複数タグ断片が出る可能性を考慮する。
- test replay では HTML/XML tag を含む packet だけを入力対象とし、指定ミリ秒ごとに順番に流す。

## 4. パース仕様
### 4.1 断片抽出
- ペイロード文字列から XML 断片を正規表現で抽出する。
- 想定する基本パターンは `(<[^<>]+?>)` とする。

### 4.2 対応タグ
- 構造タグ:
  - `<INIT>`
  - `<UN>`
  - `<GO>`
  - `<TAIKYOKU>`
  - `<DORA>`
  - `<REACH>`
  - `<N>`
  - `<AGARI>`
  - `<RYUUKYOKU>`
- 短縮タグ:
  - ツモ系: 自家は `<Tnn/>`、他家は `<U/>`, `<V/>`, `<W/>` の形でも現れる
  - 打牌系: `<Dnn/>`, `<Enn/>`, `<Fnn/>`, `<Gnn/>`
- 補助タグ:
  - `CHAT`
  - `SAY`
  - `CHATMESSAGE`
- 未対応タグは `unknown_tags` として保持する。

### 4.3 短縮タグの扱い
- `T/U/V/W` は座席別のツモ系イベント候補として扱う。
- `D/E/F/G` は座席別の打牌系イベント候補として扱う。
- ただし、実キャプチャ上の意味差異は取り違えの可能性があるため、`raw_tag` を必ず保持する。

## 5. 状態モデル
### 5.1 `PlayerInfo`
- `seat`
- `name`
- `dan`
- `rate`
- `sex`

### 5.2 `CaptureDiscard`
- `tile_136`
- `tsumogiri`
- `called`
- `raw_tag`

### 5.3 `Meld`
- `meld_id`
- `actor`
- `type`: `chi` / `pon` / `kan_open` / `kan_closed` / `kan_added`
- `from_player`: `self` / `shimocha` / `toimen` / `kamicha`
- `target_tile_136`
- `target_tile_37`
- `tiles_136`
- `tiles_37`
- `consumed_from_hand_136`
- `opened`
- `source_meld_id`
- `called_index`
- `rotate_index`
- `event_index`
- `raw_m`

### 5.4 `Event`
- `timestamp`
- `delta_time`
- `event_type`
- `seat`
- `tile_136`
- `raw_tag`
- `attrs`

### 5.5 `RoundState`
- `kyoku_index`
- `honba`
- `riichi_sticks`
- `oya`
- `scores`
- `dora_indicators_136`
- `initial_hands_136`
- `discards`
- `draws`
- `melds`
- `reach_declared`
- `reach_accepted`
- `raw_init_attrs`

### 5.6 `CaptureState`
- `players`
- `rounds`
- `current_round`
- `events`
- `chats`
- `unknown_tags`
- `tracker`
- `live_hand_tiles_136`
- `live_meld_tiles_136`
- `live_dora_indicator_tiles_136`
- `last_timestamp`

## 6. 保持する情報
- プレイヤー情報:
  - 名前
  - 段位
  - レート
  - 性別候補
- 局情報:
  - 局番号
  - 本場
  - 供託
  - 親
  - 点数
  - ドラ表示牌
  - 初期配牌
- 行動情報:
  - ツモ
  - 打牌
  - リーチ宣言
  - リーチ成立
  - 鳴き
  - 和了
  - 流局
- 補助情報:
  - チャット系タグ
  - 未解釈タグ
  - 元タグ文字列
  - イベント間差分時間

## 7. イベント反映ルール
- `INIT`
  - 新しい `RoundState` を生成する。
  - `seed` から局番号、本場、供託を取得する。
  - `ten` から点数を取得する。
  - `oya` を保持する。
  - `hai0` から `hai3` を初期配牌として保持する。
- `UN`
  - `n0` から `n3` をプレイヤー名として保持する。
  - `dan`、`rate`、`sx` を各座席へ展開する。
- `DORA`
  - ドラ表示牌を `dora_indicators_136` に追加する。
- `REACH`
  - `step=1` は宣言、`step=2` は成立として別管理する。
- `N`
  - `m` を `capture.meld_decoder.decode_meld()` で `Meld` へ完全デコードする。
  - `RoundState.melds` には面子の full 情報を保持する。
  - `CaptureState.live_meld_tiles_136` には packet 側で使う副露寄与分だけを保持する。
  - 鳴き元の捨て牌には `called` フラグを立てる。
- 短縮タグ
  - ツモは `draws[seat]` に保持する。
  - 打牌は `discards[seat]` に `CaptureDiscard` 構造として保持する。

## 8. 136牌から37種牌への変換
- 変換関数を用意し、描画直前だけ `tile_136` から `tile_37` を生成する。
- `tile_136` は 0-origin とし、萬子 `0-35`、筒子 `36-71`、索子 `72-107`、字牌 `108-135` を使う。
- 赤牌は別 ID として扱う。
- 赤5は `16`、`52`、`88` を使う。
- `tile_37` は牌画像 `1.png` から `37.png` の番号と一致させる。
- 現行 GUI の 3見え / 4見え集計は、`called=False` の捨て牌・自家手牌・副露 full 牌・ドラ表示牌を 34種へ正規化して数える。
- 萬子は `1..9` と赤5萬 `10`、筒子は `11..19` と赤5筒 `20`、索子は `21..29` と赤5索 `30`、字牌は `31..37` を使う。
- 34種カウントでは `5` と `10`、`15` と `20`、`25` と `30` を同じ牌種として数える。
- 右側の `Visible x3` / `Visible x4` では、34種代表値の通常牌画像だけを表示し、赤5と通常5を並べない。
- 鳴かれた捨て牌は捨て牌側集計から除外し、副露側の full 牌で数えることで二重計上を避ける。

## 9. 既知の注意点
- `text` フィールド内に不要文字列が混ざる可能性がある。
- 1 パケットに複数タグが入る可能性がある。
- `D/E/F/G` と `T/U/V/W` の対応は実キャプチャで確認済み。
- 対局パケットでは、自家ツモは `Txx`、他家ツモは `U` / `V` / `W` 単体で現れることがある。
- `N` タグの `m` 符号は現行実装でチー / ポン / 明カン / 暗カン / 加カンをデコードする。
- `meld_code & 0x20` 系の特殊面子は未対応で `None` 扱い。
- 固定位置切り出しは `tshark` の出力変化に弱いため採用しない。

## 10. 実装方針
- 現行の実装本体は `src/capture/` 配下に分割している。
  - Capture Layer: `src/capture/tshark_capture.py` と `src/capture/pcap_replay.py`
  - Parse Layer: `src/capture/fragment_parser.py` と `src/capture/meld_decoder.py`
  - State Layer: `src/capture/state.py`
  - Storage Layer: `src/capture/storage.py`
- `src/packet_capture.py` は旧 import 互換ラッパーとして残す。
- live capture と `.pcapng` replay は、どちらも `parse_tshark_output_line()` を共有して同じ state 更新経路を通す。
- 内部の正本は raw `tile_136` とし、描画時だけ 37種へ、3見え / 4見え集計時だけ 34種へ変換する。
- DB 保存は `CaptureState` や `Event` を基に行う。

## 11. 変更履歴
- v1.0: 初期描画仕様
- v1.1: データモデルとテスト方針を追加
- v1.2: `SutehaiTracker`、`tshark`、SQLite 連携を追加
- v1.3: 卓面 UI、プレイヤーパネル、詳細情報表示スペースを追加
- v1.3追記: パケットキャプチャ入力を固定位置切り出しから構造化パース前提へ拡張
