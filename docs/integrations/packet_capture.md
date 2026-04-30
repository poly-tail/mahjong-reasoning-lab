# パケットキャプチャ仕様

現行実装に合わせた、パケットキャプチャまわりの責務整理です。

## 目的
- 復号済み WebSocket タグから `GameState` を復元する。
- GUI 表示、DB 保存、event CSV 出力、将来の牌譜完全再現に共通利用できる形で保持する。
- 確定仕様、暫定仕様、未確定仕様を混ぜない。

## 基本方針
- `tshark` の `websocket` フィールドから `frame.time_epoch` と `text` を読む
- `text` から複数 tag 断片を抽出する
- XML 風 tag、JSON wrapper、bare tag を同じ入口で解釈する
- packet の `tile_136` は raw 正本として保持する
- 推定ロジックは必ずフラグを持たせる
- unknown や validation failure は落とさず保持する
- 状態更新と DB 保存を分離する

## 仕様区分
### 確定仕様
- `INIT` は局開始イベント
- `REINIT` は完全状態復元イベント
- draw は `T/U/V/W`
- discard は `D/E/F/G`
- `N` は副露イベント
- `DORA`、`REACH`、`AGARI`、`RYUUKYOKU` を局状態に反映する
- `tile136_to_tile37_spec()` と `tile136_to_tile37_ui()` を両方提供する

### 暫定仕様
- lowercase discard:
  - 直前 draw と同牌なら `tsumogiri`
  - それ以外の lowercase は `risekichu_hokan_tsumogiri`
    - 離席中などで draw を直接観測できず、後続情報からツモ切り扱いへ補完した意味で使う
- `REINIT.kawa` の `255`:
  - 次の捨て牌のリーチ宣言マーカーとして扱う
- `REINIT.kawa` の `254`:
  - marker として raw 保持だけ行う
  - 意味解釈にはまだ使わない
- `hai` と `hai0..hai3`:
  - `hai0..hai3` を優先
  - なければ `hai` を自家手牌として使う

### 未確定仕様
- `LN` / `REJOIN` の意味
- `REINIT` marker の順序依存
- lowercase discard の厳密仕様
- 点数単位の正規化

## モジュール分割
### `src/capture/state.py`
- `GameState`
- `RoundState`
- `Event`
- `Discard`
- `Meld`
- `normalize_tile136_id()`
- `tile136_to_tile37_spec()`
- `tile136_to_tile37_ui()`
- 互換 alias:
  - `CaptureState`
  - `CaptureDiscard`

### `src/capture/meld_decoder.py`
- `decode_meld()`
- `N` タグの面子コードを `Meld` に変換する
- チー / ポン / 明槓 / 暗槓 / 加槓を判定する

### `src/capture/fragment_parser.py`
- `split_tshark_line()`
- `extract_tag_fragments()`
- `parse_tag_fragment()`
- `parse_fragment()`
- `parse_un()`
- `parse_init()`
- `parse_reinit()`
- `parse_draw()`
- `parse_discard()`
- `parse_n()`
- `parse_reach()`
- `parse_dora()`
- `parse_agari()`
- `parse_ryuukyoku()`
- `validate_round_state()`
- `verify_reinit_round_state()`
- `validate_game_state()`
- `load_from_decrypted_lines()`
- `load_from_text()`
- `export_round_summary()`
- `export_discards()`
- `export_event_rows()`
- `export_event_csv_text()`

### `src/capture/storage.py`
- `initialize_db()`
- `persist_event()`
- CSV DB writer と upsert を担当する
- DB には画面表示や分析に使う最小限の打牌情報だけを保存する
- schema 更新で旧ヘッダを再書き換えする場合は、元 CSV を `csv_db/old/YYYYMMDD/` に退避してから更新する

### `src/capture/tshark_capture.py`
- `build_tshark_command()`
- `parse_tshark_output_line()`
- `run_and_capture()`

### `src/capture/pcap_replay.py`
- `build_pcap_tshark_command()`
- `run_test_capture()`
- `.pcapng` を `tshark -r` と `tls.keylog_file` で読み、tag packet を一定間隔で流す

## 状態更新の要点
### `INIT`
- 新しい `RoundState` を生成する
- `seed` から局番号、本場、供託、サイコロ、ドラ表示牌を反映する
- `hai0..hai3` または `hai` から手牌を構築する

### `REINIT`
- current round を再構築する
- `m0..m3` を decode して副露状態を復元する
- `kawa0..kawa3` は raw 配列を `reinit_kawa_raw` に保持する
- `0..135` の値だけを `Discard` に展開する
- 再構築後に validation を走らせる

### draw / discard
- draw は `current_hands_136` と `last_draw_tiles_136` を更新する
- discard は `current_hands_136` から 1 枚削除し、`Discard` を追加する
- 通常打牌の思考時間は `draw -> discard`、鳴き後打牌の思考時間は `call -> discard` を `thinking_time_ms` に入れる
- `REACH step=1` が打牌前に入った場合は、`draw/call -> REACH` を `thinking_time_before_reach_ms`、`REACH -> discard` を `thinking_time_ms` に分ける
- `捨て牌 -> 鳴き(N)` の鳴き判断時間は打牌思考時間には入れず、ラグ側で扱う
- live 自動判定の初期値は `lagged = 0/1/2/6` とする
- 観戦系などで draw tag が欠ける場合は、次に観測できた discard を前打牌のラグ計測終端として扱い、そのラグ情報を前打牌へ載せる
- `5ms <= lag_delay_ms <= 550ms` の未鳴きラグは `lagged = 6` として short system delay 側へ分離する
- XML 牌譜で全員手牌が入ったあとは、`lagged = 1` だけをチー/ポン可否で `3` または `5` へ再判定する。`5` は偽ラグの可能性が高いものとして扱う
- discard event は `tsumogiri` と `is_tsumogiri_estimated` を両方持つ

### `N`
- `decode_meld()` を呼ぶ
- `RoundState.melds` へ面子 full 情報を保存する
- `consumed_tile_ids` 分だけ手牌から削除する
- open meld は鳴き元の捨て牌に `called=True` を立てる
- open meld は鳴き元の捨て牌に `lagged = 2` も同期する
- open meld に至る `捨て牌 -> call(N)` の時間は、鳴き思考時間として打牌思考時間ではなくラグ側で扱う
- `kakan` は既存のポンを差し替える

## validation / diagnostics
- `unknown_tags` は未対応 tag や parse 失敗を保持する
- `diagnostics` は warning レベルの unknown / validation issue を保持する
- `validate_round_state()` は牌 ID 範囲、meld 形状、open/closed 一致を検証する
- `verify_reinit_round_state()` は `REINIT` payload と rebuilt state の一致を検証する
- `validate_game_state()` は全局を横断して issues を集約する

## UI 連携
- `GameState.tracker` が 4 人の捨て牌表示に使われる
- `live_hand_tiles_136` が自家手牌の raw 正本として使われる
- `RoundState.melds` が鳴き表示と visible 集計の副露 full 情報に使われる
- `live_meld_tiles_136` が packet 側の副露寄与分 raw 正本として使われる
- `live_dora_indicator_tiles_136` がドラ表示牌の raw 正本として使われる
- `visible_tiles.collect_visible_tile_summary()` が `called=False` の捨て牌、自家手牌、副露 full 牌、ドラ表示牌から 3見え / 4見えを再計算する

## DB の位置づけ
- DB 保存先は `csv_db/` 配下の CSV 群
- `discard_fact_YYYYMM.csv` は打牌中心の主テーブル
- `GO type` は capture state に保持し、`hanchan_master` / `kyoku_master` / `discard_fact` へ `go_type`, `go_type_hex`, `room_class_code`, `room_class_label` を保存する
- `room_class_code` / `room_class_label` は `ippan` / `joukyuu` / `tokujou` / `houou` と `一般卓` / `上級卓` / `特上卓` / `鳳凰卓`
- `discard_fact_YYYYMM.csv` は `discard_tile_136` に加えて `discard_tile_37_text` と `tsumogiri_flag` も保存する
- `discard_id` は `{kyoku_id}_{discard_indexの3桁}` 形式で保存する
- `discard_context_YYYYMM.csv` は打牌補助情報を分離保持する
- 各席手牌は `discard_fact_YYYYMM.csv` 側へ `seat*_hand_tiles_136_json` と `seat*_hand_tiles_37_text` で保持し、どちらも打牌前 concealed hand snapshot を表す。門前なら通常 14 枚、1 副露なら 11 枚、2 副露なら 8 枚、3 副露なら 5 枚で、加槓だけは例外
- DB へ保存するのは画面表示や分析に使う最小限の情報だけで、補助的な capture 情報は runtime のみで保持する
- 現在の正本は DB ではなく `GameState`

## 現在の制約
- `LN` / `REJOIN` は TODO のまま unknown 扱い
- `REINIT` marker の意味は生値保持だけで解釈しない
- 点数単位は raw のまま保持する
- 生成 SVG は Mermaid 正本更新後に別途再生成する
## 2026-04-01 Addendum
- Input modes are now four-way:
- `--mock [1-3]`
- `--test INPUT_PCAPNG`
- live websocket packet capture
- `--xml-url URL`
- `--xml-url` is not a raw XML text input. It first tries to read `log=` from the supplied URL and fetches `https://tenhou.net/0/log/?<log_id>` directly.
- if `log=` is absent, it falls back to finding the first `log/?...` reference in the supplied page.
- the fetched XML is parsed for GUI state and also used to backfill `discard_fact` hand snapshots by matching the log date and relative-seat player-name order against an existing DB hanchan.
- `--xml-url-list URL_LIST_TXT` reads newline-delimited URLs from a text file and runs the same XML DB import path for each line without opening the GUI.
- 半荘照合に成功した場合は、入力元の URL を `hanchan_master.source_url` に保存する。
- XML URL resolution and download live in `src/capture/xml_url_loader.py`.
- Parser modes are now `player_live`, `spectator_live`, and `xml_log`.
- `spectator_live` is a separate live-websocket contract: `INITBYLOG` / `WGC` are accepted as normal bootstrap tags, draw-tag absence is expected, and numeric prefixes before `D/E/F/G` are stored as heuristic `action_delay_ms`.
- live websocket の tag 抽出は、完全な XML / JSON だけでなく、payload 内に埋め込まれた bare tag や不完全な `<INIT ...` / `<REINIT ...` のような xmlish start tag も拾う。
- `INIT` は常に新局開始として扱い、current round を無条件で初期化する。
- websocket text に `INIT` 系 tag 文字列が見えていれば、その packet を受けた時点で即座に局面初期化へ進む。
- `REINIT` / `INITBYLOG` などの snapshot payload は、局キー一致だけで current round を再利用せず、`kawa0..kawa3` の visible discard 一致率がかなり高い場合にだけ再利用する。現実装の閾値は `80%`。
- `INIT` 系を受ける前の途中開始 packet でも live 可視化は継続するが、その局は `RoundState.started_from_init_like = False` のまま扱い、CSV DB には保存しない。
- live capture は GUI とは別の background thread で動かし、tshark 1 行単位・fragment 単位の例外で thread 全体を止めない。
- GUI の live 再描画は 500ms 固定ポーリングではなく、capture state の更新トークン変化を 16ms 間隔で監視して即時反映する。
- live websocket では、`UN` の相対席プレイヤー名シグネチャが1人でも変わった時点で、既存の capture 局面をリセットして新しい卓として扱う。
- live websocket では、`UN` による相対席プレイヤー名シグネチャが変わった場合や、`TAIKYOKU.log` が別値へ切り替わった場合、in-memory state を新半荘として自動初期化する。
- `xml_log` remains absolute-seat based, while live websocket parsing remains relative-seat based.
- XML parsing must resolve `UN`, `self_abs_seat`, and `oya_abs` before converting `hai`, `oya`, `TUVW`, `DEFG`, `N who`, `AGARI who`, and `fromWho`.
