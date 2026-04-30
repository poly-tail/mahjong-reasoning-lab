# Tenhou Hojo Helper API仕様書 v1.4
> 2026-04-01 時点の仕様。局状態復元パーサは「確定仕様」「暫定仕様」「未確定仕様」を分離し、推定値は必ずフラグ管理する。

## 1. 目的
- 復号済み WebSocket タグから、局状態・捨て牌・副露・リーチ・和了/流局までを `GameState` へ反映する。
- GUI、DB、検証、将来の牌譜再現に共通利用できる状態モデルと API を定義する。

## 2. 設計原則
- 固定位置スライスでタグを読む実装は採用しない。
- raw `tile_136` を内部正本とし、必要な時だけ 34種/37種へ変換する。
- 推定ロジックは確定仕様として扱わず、必ず event attrs や dataclass フィールドで明示する。
- 未対応タグや不明データは silent failure せず、`unknown_tags` と diagnostics に保存する。
- `INIT` と `REINIT` は別イベントとして扱い、`REINIT` は完全状態復元として実装する。

## 3. 入力仕様
### 3.1 受け付ける入力
- `load_from_decrypted_lines(lines)`:
  - `tshark` の `frame.time_epoch<TAB>text`
  - 復号済み CSV
  - 断片だけを並べた生テキスト行
- `load_from_text(text)`:
  - 複数行の復号済みテキスト blob

### 3.2 `tshark` 前提
- `frame.time_epoch` と `text` フィールドを使う。
- 1 行に複数タグが含まれる前提で処理する。
- live capture と `.pcapng` replay は同じ `parse_tshark_output_line()` / `parse_fragment()` 経路を共有する。

### 3.3 復号済み CSV
- `payload_text_url_decoded` と `approx_time_epoch` を持つ形式を受け付ける。
- `direction=s2c` が存在する場合は、server-to-client を正本入力とする。

## 4. タグ断片抽出と正規化
### 4.1 断片抽出
- `extract_tag_fragments()` が payload から複数断片を抽出する。
- XML 風 tag のみでなく、JSON wrapper や bare tag も処理対象に含める。

### 4.2 `parse_tag_fragment(fragment)`
- XML として解釈できる場合:
  - `tag_name`
  - `attrs`
  - `source_format="xml"`
- JSON object の場合:
  - `tag` を `tag_name`
  - それ以外を `attrs`
  - `source_format="json"`
- それ以外:
  - fragment 全体を `tag_name`
  - `source_format="bare"`

### 4.3 対応タグ
- 構造タグ:
  - `UN`
  - `GO`
  - `TAIKYOKU`
  - `INIT`
  - `REINIT`
  - `DORA`
  - `REACH`
  - `N`
  - `AGARI`
  - `RYUUKYOKU`
- 短縮タグ:
  - draw: `T/U/V/W`
  - discard: `D/E/F/G`
- 補助タグ:
  - `CHAT`
  - `SAY`
  - `CHATMESSAGE`
- 未確定タグ:
  - `LN`
  - `REJOIN`

## 5. 牌表現
### 5.1 136牌
- 内部正本は 0-origin の `tile_136`
- 萬子 `0..35`
- 筒子 `36..71`
- 索子 `72..107`
- 字牌 `108..135`
- 赤5萬 `16`
- 赤5筒 `52`
- 赤5索 `88`

### 5.2 正規化と変換 API
- `normalize_tile136_id(tile_136, one_based=False)`:
  - 1-origin 入力を 0-origin へ寄せるための補助関数
- `tile136_to_tile37_spec(tile_136)`:
  - 0..36 の仕様表現
- `tile136_to_tile37_ui(tile_136)`:
  - 1..37 の既存 UI 互換表現
- `tile136_to_tile37(tile_136)`:
  - 現行 UI 互換のエイリアス

## 6. データモデル
### 6.1 `PlayerInfo`
- `seat`
- `name`
- `dan`
- `rate`
- `sx`

### 6.2 `Event`
- `timestamp`
- `event_type`
- `seat`
- `raw_tag`
- `tile_136`
- `attrs`
- `delta_time`
- `thinking_time_ms`
- `thinking_time_source`
- `thinking_time_before_reach_ms`
- `thinking_time_before_reach_source`

`thinking_time_ms` は打牌に紐づく最終区間の思考時間を表す。
通常打牌では `draw -> discard`、鳴き後打牌では `call -> discard`、`REACH` 打牌では `REACH -> discard` を入れる。

### 6.3 `Discard`
- `tile_136`
- `tile_34`
- `tile_37`
- `tsumogiri`
- `is_tsumogiri_estimated`
- `riichi_marker_before`
- `raw_tag`
- `called`
- `thinking_time_ms`
- `thinking_time_source`
- `thinking_time_before_reach_ms`
- `thinking_time_before_reach_source`
- `tsumogiri_flag`:
  - `tedashi`
  - `tsumogiri`
  - `risekichu_hokan_tsumogiri`

`thinking_time_before_reach_ms` は `REACH` 打牌の前半区間 `draw/call -> REACH` を表す。
`discard -> call(N)` の鳴き判断時間は `Discard` の打牌思考時間には入れず、鳴き元打牌のラグ側で扱う。

### 6.4 `Meld`
- `who`
- `raw_m`
- `meld_type`
- `tile_34`
- `tile_37`
- `from_who`
- `consumed_tile_ids`
- `called_tile_id`
- `is_open`
- `upgraded_from`
- `tiles_136`
- `tiles_34`
- `tiles_37`
- `meld_id`
- `event_index`

### 6.5 `RoundState`
- `kyoku_index`
- `honba`
- `kyotaku`
- `dice_1_minus_1`
- `dice_2_minus_1`
- `oya`
- `scores`
- `dora_indicators_136`
- `initial_hands_136`
- `current_hands_136`
- `discards`
- `melds`
- `reach_state`
- `events`
- `draws`
- `last_draw_tiles_136`
- `pending_riichi_markers`
- `raw_init_attrs`
- `raw_reinit_attrs`
- `result`
- `reinit_kawa_raw`
- `validation_issues`

### 6.6 `GameState`
- `players`
- `game_id`
- `rounds`
- `current_round`
- `raw_events`
- `unknown_tags`
- `tracker`
- `live_hand_tiles_136`
- `live_meld_tiles_136`
- `live_dora_indicator_tiles_136`
- `chats`
- `diagnostics`
- `unresolved_spec_todos`
- `last_timestamp`
- `self_seat`

### 6.7 互換エイリアス
- `CaptureState = GameState`
- `CaptureDiscard = Discard`

## 7. タグ別反映ルール
### 7.1 `UN`
- プレイヤー名は URL decode して保持する。
- `dan` / `rate` / `sx` を seat ごとに展開する。
- live parser では、相対席プレイヤー名シグネチャが変わった `UN` を別半荘または別視点への切替とみなし、既存の in-memory round/tracker/live state を自動初期化してから新 metadata を適用する。

### 7.2 `INIT`
- 新しい `RoundState` を生成する。
- `seed` から局番号、本場、供託、サイコロ、ドラ表示牌を取得する。
- `ten` は 100 点単位の値として解釈し、`scores` へは 100 倍した実際の点数を保持する。
- `hai0..hai3` があれば全座席の初期手牌として扱う。
- `hai` だけの場合は `self_seat` の手牌として扱う。

### 7.3 `REINIT`
- `INIT` と同一視しない。
- current round をスナップショットで再構築する。
- 手牌:
  - `hai0..hai3` を優先
  - なければ `hai` を自家手牌として採用
- 副露:
  - `m0..m3` を decode して各 seat の meld 群を再構築
- 河:
  - `kawa0..kawa3` は raw 配列を `reinit_kawa_raw` に保持
  - `0..135` の通常牌だけを `Discard` として `RoundState.discards` に展開
  - `254` / `255` は marker とみなし、生値保持だけ行う
- 検証:
  - `verify_reinit_round_state()` で hand / raw kawa / visible discard / meld raw code の一致を確認
  - `validate_round_state()` で構造検証を行い、issues を diagnostics に積む

### 7.4 draw `T/U/V/W`
- seat 対応:
  - `T` -> 0
  - `U` -> 1
  - `V` -> 2
  - `W` -> 3
- `current_hands_136[seat]` へ追加する。
- `last_draw_tiles_136[seat]` を更新する。

### 7.5 discard `D/E/F/G`
- seat 対応:
  - `D` -> 0
  - `E` -> 1
  - `F` -> 2
  - `G` -> 3
- `Discard` を生成し `RoundState.discards[seat]` に追加する。
- `current_hands_136[seat]` から同牌を 1 枚削除する。
- `pending_riichi_markers[seat]` を `riichi_marker_before` として消費する。
- 通常打牌では `thinking_time_ms = draw -> discard`、鳴き後打牌では `thinking_time_ms = call -> discard` とする。
- `REACH` が入った打牌では `thinking_time_before_reach_ms = draw/call -> REACH`、`thinking_time_ms = REACH -> discard` とする。

### 7.6 lowercase discard の暫定仕様
- 直前 draw と同牌:
  - `tsumogiri=True`
  - `is_tsumogiri_estimated=False`
- それ以外で tag が lowercase:
  - `tsumogiri=True`
  - `is_tsumogiri_estimated=True`
- それ以外:
  - `tsumogiri=False`
  - `is_tsumogiri_estimated=False`

### 7.7 `N`
- `decode_meld(who, m)` を呼ぶ。
- `meld_type` は少なくとも `chi` / `pon` / `daiminkan` / `ankan` / `kakan` を返す。
- `pon -> kakan` は既存 meld を置き換える。
- 手牌からは `consumed_tile_ids` 分だけ削除する。
- open meld のみ、鳴き元の捨て牌へ `called=True` を立てる。
- `discard -> open meld call` の鳴き判断時間は打牌思考時間ではなく、鳴き元打牌のラグとして扱う。

### 7.8 `REACH`
- `step=1`:
  - `reach_state[seat] = "declared"`
  - `pending_riichi_markers[seat] = True`
  - 次打牌の思考時間を `draw/call -> REACH` と `REACH -> discard` に分割する
- `step=2`:
  - `reach_state[seat] = "accepted"`
- `ten` があれば 100 点単位の値として `scores` を更新する。

### 7.9 `DORA`
- `hai` を `dora_indicators_136` に追加する。

### 7.10 `AGARI`
- `round_state.result = {"type": "agari", "data": ...}` として保存する。
- `who == fromWho` のとき `is_tsumo=True` を補助付与する。

### 7.11 `RYUUKYOKU`
- `round_state.result = {"type": "ryuukyoku", "data": ...}` として保存する。

### 7.12 `TAIKYOKU`
- `log` があれば `game_id` に保持する。
- live parser では `log` が既存 `game_id` と異なる場合、新半荘として in-memory state を自動初期化する。

## 8. unknown / diagnostics 方針
- `LN` / `REJOIN` は `unknown_tag` event として保存する。
- parse 失敗や未対応 tag は `_record_unknown()` で:
  - `unknown_tags`
  - `diagnostics`
  - `raw_events`
  に残す。
- `logger.warning()` で unknown を必ず出力する。

## 9. 検証 API
- `validate_round_state(round_state) -> list[str]`
- `verify_reinit_round_state(round_state, attrs, self_seat=...) -> list[str]`
- `validate_game_state(game_state) -> list[str]`

## 10. export API
- `export_round_summary(game_state)`:
  - 局数、点数、ドラ、reach state、discard count、meld type、result、validation issues を返す
- `export_discards(game_state)`:
  - current round の `Discard` 一覧を seat ごとに返す
- `export_event_rows(game_state)`:
  - `timestamp`
  - `tag_type`
  - `player`
  - `tile136`
  - `action`
  - `tsumogiri_flag`
  - `raw_tag`
- `export_event_csv_text(game_state)`:
  - 上記 rows を CSV 文字列化する

## 11. DB 永続化
- DB 保存先は `csv_db/` ディレクトリとする
- `hanchan_master.csv`:
  - 半荘単位の主テーブル
  - `hanchan_id` と相対席プレイヤー名だけを保存する
- `kyoku_master.csv`:
  - 局単位の主テーブル
  - `kyoku_id = hanchan_id + "_" + kyoku_info` と局識別に必要な局情報、4人のプレイヤー名、親プレイヤー名を保存する
- `discard_fact_YYYYMM.csv`:
  - 打牌単位の主テーブル
  - `discard_id = kyoku_id + "_" + discard_index(3桁)` を主キーに、`discard_tile_136`、秒精度の打牌時刻、思考時間、ラグ状態値、各席手牌 snapshot を保存する
- `discard_context_YYYYMM.csv`:
  - 打牌時点の点数、リーチ状態、ドラ、副露、河、見え牌集計を保存する
- `player_profiles.csv`:
  - プレイヤー単位のメモを保存する
  - `user_memo` は GUI の共通 DETAIL 欄から編集する
  - 各プレイヤーパネルの `DETAIL` ボタンは対象プレイヤーの `user_memo` を開く
- `raw_tag`、`thinking_time_source`、`discard_tile_34/37` などの補助情報は runtime のみで持ち、DB には保存しない
- schema 更新で旧ヘッダから現行ヘッダへ再書き換えする場合、元 CSV は `csv_db/old/YYYYMMDD/` に退避してから更新する
- 現時点の DB は正本ではなく、補助ログ用途である

## 12. 未確定仕様
- `LN` / `REJOIN` の意味
- `REINIT.kawa` marker の順序依存
- lowercase discard の厳密仕様
- 点数単位の正規化

## 13. 互換公開
- `src/tenhou_hojo.py` は以下を再公開する:
  - `load_from_decrypted_lines`
  - `load_from_text`
  - `parse_tag_fragment`
  - `export_round_summary`
  - `export_discards`
  - `export_event_rows`
  - `export_event_csv_text`
  - `validate_round_state`
  - `validate_game_state`
  - `normalize_tile136_id`
  - `tile136_to_tile37_spec`
  - `tile136_to_tile37_ui`

## 2026-04-01 Addendum
- Parser modes are `player_live`, `spectator_live`, and `xml_log`.
- `load_from_decrypted_lines(lines, parser_mode="player_live")` and `load_from_text(text, parser_mode="player_live")` accept an explicit live parser mode while still allowing auto-promotion into `spectator_live`.
- `spectator_live` treats `INITBYLOG` / `WGC` as normal bootstrap tags, does not require draw tags, and interprets numeric prefixes before `D/E/F/G` as heuristic `Event.action_delay_ms`.
- `player_live` / `spectator_live` の live parser は、`UN` の相対席プレイヤー名シグネチャ変更または `TAIKYOKU.log` 切替を新半荘として扱い、in-memory state を初期化する。
- `Event` now carries `action_delay_ms`, `delay_source`, and `delay_confidence`.
- `xml_log` remains the absolute-seat parser path. XML logs must resolve `UN`, `self_abs_seat`, and `oya_abs` before absolute-seat values are mapped into the internal relative-seat model.

## 2026-04-01 Lag Marker Addendum
- discard レコードは `lagged(0..5)` と `lag_delay_ms` を持つ。
- parser は打牌または鳴き後打牌から次の `draw` または一致する open meld `call` までの packet arrival 差分を測定し、`>= 5ms` をラグとみなす。
- live 自動判定で新規に付与する `lagged` は `0` または `1` だけで、`3` 以上は XML 牌譜入力または手入力でしか付与しない。
- `discard -> open meld call` の区間は鳴き思考時間を兼ねるが、`thinking_time_ms` ではなくラグ側の概念として扱う。
- ラグ判定は pending discard を `draw` または open meld `call` で解決して確定し、解決不能な pending discard は未判定のまま破棄する。
- GUI はラグ discard に黄色丸を付与し、その位置は 4見え青丸の左隣を牌ローカル座標で回転させた位置とする。

## 2026-04-01 Snapshot Carryover Addendum
- `INIT` は常に新局開始として扱い、current round を無条件で初期化する。
- `REINIT` / `INITBYLOG` などの snapshot payload は、局キー一致だけで current round を再利用せず、`kawa0..kawa3` の visible discard 一致率がかなり高い場合だけ再利用する。現実装の閾値は `80%`。
- `INIT` 系を受ける前の途中開始 packet でも live 可視化は継続するが、その局は `RoundState.started_from_init_like = False` として扱い、CSV DB には保存しない。
- `REINIT` / `INITBYLOG` が `kawa0..kawa3` を含む場合、既存 discard 列が新 snapshot の prefix と一致していれば、その prefix 部分の discard metadata を再利用する。
- 再利用対象は `tsumogiri`, `is_tsumogiri_estimated`, `riichi_marker_before`, `called`, `thinking_time_ms`, `thinking_time_source`, `thinking_time_before_reach_ms`, `thinking_time_before_reach_source`, `lagged(0..5)`, `lag_delay_ms`, `raw_tag` とする。
- snapshot による追加 discard 差分は新規 discard として末尾へ追加する。

## 2026-04-03 Danger Suji Heuristic Addendum
- `danger_suji._build_weighted_suji_line_map(round_state, seat)` の計算順序は `suppress -> matagi -> chi/inside-outside caps -> lag factor` で固定する。
- `danger_suji._chi_wait_shape(meld)` は `chi` を `kanchan` / `penchan` / `ryanmen` に分類し、`_chi_line_caps()` が筋線 cap を返す。
- `danger_suji._inside_to_outside_line_caps(round_state, seat)` は同色 tedashi 履歴を `outer / middle / inner` bucket で見て、内側から外側へ進んだときだけ `0.7` cap を返す。
- `danger_suji.build_opponent_suji_danger_profile(round_state, seat)` は最終筋線重みを両端牌へ配賦し、牌単位 danger と `corrected_musuji_count` を構築する。
- `danger_suji.build_opponent_suji_panel_summary(round_state, seat)` は `SUMMARY` 用に同じ筋線重みから `denominator_count` と top 3 line label を生成する。
- `danger_suji.build_hand_tile_suji_danger_metrics(state, hand_tiles_136)` は上記 profile を使って各牌へ `{percentage, numerator_count, denominator_count}` を返す。

## 2026-04-02 Live Memory Addendum
- live capture は `tshark` の `stdout` を行単位で逐次処理する。
- `player_live` / `spectator_live` では in-memory history を bounded に保つ。保持上限は `rounds=4`, `raw_events=4096`, `unknown_tags=256`, `diagnostics=256`, `chats=128`。
- `xml_log` では full history を保持するため bounded pruning を適用しない。
