# CSV DB 管理ドキュメント

## 1. 位置づけ

このファイルは、現行の CSV ベース DB の管理ドキュメントです。
保存先、主キー、各 CSV の役割、保存カラム、schema 更新時の退避ルールをここで管理します。

## 2. 基本方針

- DB 保存先は `csv_db/`
- 複数 CSV をまとめて 1 つの論理 DB として扱う
- DB に保存するのは、画面表示や分析で使う情報だけ
- capture の補助情報や内部導出値は runtime のみで持つ
- 現在の正本は DB ではなく `GameState` / `RoundState`

## 3. 保存先

- 保存先ディレクトリ: `csv_db/`
- 定義元: `src/capture/csv_db_schema.py`
- 定数: `CSV_DB_DIRNAME = "csv_db"`

## 4. DB を構成するファイル

### 4.1 単独ファイル

- `hanchan_master.csv`
- `kyoku_master.csv`
- `player_profiles.csv`

### 4.2 月別分割ファイル

- `discard_fact_YYYYMM.csv`
- `discard_context_YYYYMM.csv`

例:

- `discard_fact_202604.csv`
- `discard_context_202604.csv`

## 5. イベントと時刻

### 5.1 `timestamp`

packet 到着時刻ベースのイベント絶対時刻。

### 5.2 `delta_time`

`delta_time` は「正規化イベント列全体で見た 1 つ前のイベントからの経過時間」であり、思考時間ではない。

### 5.3 秒とミリ秒の使い分け

DB では、ミリ秒が必要なのは次だけ。

- `thinking_time_ms`
- `thinking_time_before_reach_ms`
- `lag_delay_ms`

それ以外の時刻は秒精度で扱う。

### 5.4 `thinking_time_ms`

打牌思考時間。打牌エントリに紐づく。

- 通常打牌: `draw -> discard`
- 鳴き後打牌: `call -> discard`
- `REACH` 打牌: `REACH -> discard`

### 5.5 `thinking_time_before_reach_ms`

`REACH` 打牌の前半区間。

- `draw/call -> REACH`

### 5.6 鳴き思考時間

`discard -> call(N)` は打牌思考時間には入れない。この区間はラグ側で扱う。

## 6. ラグ情報

ラグ情報は打牌に紐づく。DB 保存対象は次の 2 項目。

- `lagged`
- `lag_delay_ms`

### 6.1 `lagged`

- `0`: ラグ情報なし
- `1`: ラグあり。本ラグか偽ラグか未確定
- `2`: 実際に鳴かれた
- `3`: 鳴きは可能だったが実際には鳴かれなかった
- `4`: 欠番。現行実装では使わない
- `5`: 偽ラグの可能性が高い
- `6`: `550ms` 以下の短時間ラグ。通信遅延、アプリ遅延、capture 観測ずれなどの system delay 寄りとして分離する

### 6.2 live 自動判定

live 自動判定で新規付与するのは `0` / `1` / `2` / `6`。

- 打牌後、次の `draw` または当該牌を拾った open meld `call` までの時間を測る
- draw が packet 上で見えない経路では、次に観測できた discard 時刻をその打牌のラグ計測終端として使う
- 差分が `5ms` 以上かつ `550ms` 以下なら `lagged = 6`
- 差分が `550ms` を超えるなら `lagged = 1`
- それ以外は `lagged = 0`
- その後に open meld で実際に鳴かれた打牌は、時間差に関係なく `lagged = 2` へ更新する

`3` と `5` は XML 牌譜入力または手入力でしか付与しない。

### 6.3 XML 後の偽ラグ判定

- XML 牌譜で全員の手牌を `discard_fact` へ補完したあと、`lagged = 1` の行を再判定する
- `lagged = 6` は short system delay 扱いなので、この再判定対象に入れない
- ここでいう全員には自分も含む
- 下家がチー可能、または打牌者以外の誰かがポン可能なら `lagged = 3`
- 誰もチーもポンもできないなら `lagged = 5`
- 判定ルールの詳細は `docs/mahjong/mahjong_call_rules.md` を参照する

## 7. 主キー設計

### 7.1 `hanchan_id`

`hanchan_id` は 14 文字。

- 通常: `YYYYMMDDHHMMSS`
- `INITBYLOG` フォールバック: 秒の末尾 1 桁を `k` に置換
- 例: `2026040212345k`

### 7.2 同一半荘判定

同一半荘判定シグネチャ:

`YYYYMMDD|0=<seat0_name>|1=<seat1_name>|2=<seat2_name>|3=<seat3_name>`

このシグネチャは DB に保存しない。`hanchan_id` の日付部と `seat0..3_player_name` から runtime で再構成する。

### 7.3 `kyoku_info`

`kyoku_info` は 4 桁文字列。

- 前半 2 桁: `seed[0]`
- 後半 2 桁: `seed[1]`

### 7.4 `kyoku_id`

`kyoku_id = hanchan_id + "_" + kyoku_info`

`kyoku_id` は秒までであり、ミリ秒は含めない。

### 7.5 `discard_id`

`discard_id = kyoku_id + "_" + discard_index(3 桁)`

`discard_index` は `discard_id` に含めるので、DB カラムとしては別保存しない。

例: `kyoku_id = 20260402123456_0001` の 5 打目は `discard_id = 20260402123456_0001_005`

### 7.6 INIT 系を踏まない途中開始局

live 可視化は、`INIT` / `REINIT` / `INITBYLOG` / `WGC` をまだ受けていない途中開始局でも継続する。

ただし DB 保存対象は、`RoundState.started_from_init_like = True` の局だけとする。

- `INIT` で新規開始した局は保存対象
- `REINIT` / `INITBYLOG` / `WGC` で新規 bootstrap した局も保存対象
- draw / discard / `N` などから自動生成された途中開始局は、可視化だけ行い CSV には保存しない

## 8. テーブル定義

### 8.1 `hanchan_master.csv`

1 半荘につき 1 行。

カラム:

- `hanchan_id`
- `go_type`
- `go_type_hex`
- `room_class_code`
- `room_class_label`
- `seat0_player_name`
- `seat1_player_name`
- `seat2_player_name`
- `seat3_player_name`
- `source_url`

補足:

- XML / URL リスト import で既存半荘を識別できた場合は、その入力元 URL を `source_url` に保存する
- `go_type` は Tenhou `GO.type` の整数 bitmask、`go_type_hex` は URL の `gm-XXXX` に合わせた 4 桁 hex 表記
- `room_class_code` / `room_class_label` は現行では `ippan` / `joukyuu` / `tokujou` / `houou` と `一般卓` / `上級卓` / `特上卓` / `鳳凰卓`

### 8.2 `kyoku_master.csv`

1 局につき 1 行。

カラム:

- `kyoku_id`
- `hanchan_id`
- `go_type`
- `go_type_hex`
- `room_class_code`
- `room_class_label`
- `kyoku_info`
- `honba`
- `kyotaku`
- `oya_rel`
- `seat0_player_name`
- `seat1_player_name`
- `seat2_player_name`
- `seat3_player_name`
- `oya_player_name`

補足:

- `kyoku_id = hanchan_id + "_" + kyoku_info`
- `kyoku_index` は `kyoku_info` に含まれるので DB には保存しない
- 卓種列は `hanchan_master` と同値を局 row に冗長保持する

### 8.3 `discard_fact_YYYYMM.csv`

1 打牌につき 1 行。打牌中心の主テーブル。

カラム:

- `discard_id`
- `kyoku_id`
- `hanchan_id`
- `go_type`
- `go_type_hex`
- `room_class_code`
- `room_class_label`
- `kyoku_info`
- `player_rel_seat`
- `player_name`
- `discard_tile_136`
- `discard_tile_37_text`
- `tsumogiri_flag`
- `discard_epoch_s`
- `thinking_time_ms`
- `thinking_time_before_reach_ms`
- `lagged`
- `lag_delay_ms`
- `seat0_hand_tiles_136_json`
- `seat1_hand_tiles_136_json`
- `seat2_hand_tiles_136_json`
- `seat3_hand_tiles_136_json`
- `seat0_hand_tiles_37_text`
- `seat1_hand_tiles_37_text`
- `seat2_hand_tiles_37_text`
- `seat3_hand_tiles_37_text`
- `shanten_after_discard`
- `shanten_normal_after_discard`
- `shanten_chiitoitsu_after_discard`
- `wait_tiles_after_discard_mspz`
- `ryanmen_fixed_flag`
- `pystyle_top1_tile_37_text`
- `pystyle_top1_expected_value_text`
- `pystyle_top2_tile_37_text`
- `pystyle_top2_expected_value_text`
- `pystyle_top3_tile_37_text`
- `pystyle_top3_expected_value_text`

補足:

- 打牌時刻は秒精度の `discard_epoch_s`
- 卓種列は打牌集計で毎回 `hanchan_master` join をしなくてよいよう `discard_fact` にも冗長保持する
- `discard_tile_37_text` は `3p` / `7m` / `r5p` のような文字列表現
- `tsumogiri_flag` は `tedashi` / `tsumogiri` / `risekichu_hokan_tsumogiri`
- `risekichu_hokan_tsumogiri` は、離席中などで draw を直接観測できず、後続情報からツモ切り扱いへ補完したケースを表す
- 手牌情報は `discard_hands` に分けず、このテーブルへ統合する
- `seat*_hand_tiles_136_json` は打牌前の concealed hand snapshot を入れる。門前なら通常 14 枚、1 副露なら 11 枚、2 副露なら 8 枚、3 副露なら 5 枚で、加槓だけは例外的に同じ段のまま
- `seat*_hand_tiles_37_text` はその same snapshot を 136 ID 昇順の `33m 22p 11s 77z` のような plain text にしたもの
- `shanten_after_discard` は列名だけ legacy のまま残しているが、値は打牌前手牌 snapshot に対する総合シャンテン数
- `shanten_normal_after_discard` / `shanten_chiitoitsu_after_discard` も同じく打牌前手牌 snapshot の内訳
- `wait_tiles_after_discard_mspz` は実際の打牌牌を snapshot から 1 枚抜いたあとの手牌がテンパイなら、その待ちを `36m` / `258p` / `14z` のような `mspz` grouped text で入れる
- 国士無双シャンテンは内部計算では使うが、`discard_fact` の保存列には持たない
- 副露済み手牌では七対子の列は空欄にする
- `ryanmen_fixed_flag = 1` は `223 -> 23` や `788 -> 78` のような両面固定打牌
- `pystyle_top1..3_*` は `AI TOP3` パネルが visible の間に取得できた top3 表示履歴で、自家打牌 row にだけ入る
- `pystyle_top*_tile_37_text` は UI と同じ compact tile text、`pystyle_top*_expected_value_text` は UI と同じ `1234pt` 形式
- live capture では自家 `seat0_*` だけを埋め、他家は空文字で保存する
- 後から XML / 観戦データで各 `seat*_hand_tiles_136_json` と `seat*_hand_tiles_37_text` を補完する
- XML 補完時、自家 `seat0_*` は live ですでに値がある場合は上書きしない

### 8.4 `discard_context_YYYYMM.csv`

打牌時点の局面補助情報。局面 JSON を分けて保存する。

カラム:

- `discard_id`
- `kyoku_id`
- `scores_json`
- `reach_state_json`
- `dora_indicators_136_json`
- `melds_by_seat_json`
- `rivers_by_seat_136_json`
- `visible_tile_counts_34_json`

補足:

- `discard_id` に `discard_index` が含まれるので、別の `discard_index` 列は持たない
- 副露情報や河など、局面全体に近い情報は `discard_context` に寄せる

### 8.5 `player_profiles.csv`

プレイヤー単位のメモテーブル。

カラム:

- `player_name`
- `user_memo`
- `analysis_memo`

運用:

- `user_memo` は GUI の共通 DETAIL 欄から編集する想定
- 各プレイヤーパネルの `DETAIL` ボタンで該当プレイヤーの `user_memo` を開く
- DETAIL 欄を別表示へ切り替えるときは、現在の `user_memo` を保存してから閉じる

## 9. DB に保存しない主な情報

次のような項目は runtime や GUI では使っても CSV には保存しない。

- `raw_tag`
- `source_kind`
- `discard_tile_34`
- `riichi_marker_before`
- `discard_called`
- `discard_time_text`
- `discard_offset_ms_from_hanchan_start`
- `thinking_time_source`
- `thinking_time_before_reach_source`
- `same_day_player_signature`
- `seed_json`
- `initial_scores_json`
- `initial_dora_indicators_136_json`
- `hand_known`
- `hand_source`
- `updated_at_epoch_ms`

## 10. XML / 観戦データによる後補完

ライブキャプチャ後に XML 牌譜や観戦データで上書きする主対象は `discard_fact_YYYYMM.csv` の手牌列。

- `seat0_hand_tiles_136_json`
- `seat1_hand_tiles_136_json`
- `seat2_hand_tiles_136_json`
- `seat3_hand_tiles_136_json`
- `seat0_hand_tiles_37_text`
- `seat1_hand_tiles_37_text`
- `seat2_hand_tiles_37_text`
- `seat3_hand_tiles_37_text`

XML 牌譜は偽ラグ判定にも使う。

- live の `lagged = 1` をそのまま確定扱いしない
- `lagged = 6` は short system delay として別扱いにする
- 鳴き可能なら `3`
- 偽ラグの可能性が高いなら `5`

## 11. 互換読込と退避

旧 schema の CSV も reader 側で互換的に読めるようにしている。

- 旧ヘッダを含む CSV も読み込める
- 新ヘッダで再書き込みされるタイミングで列は整理される
- 現行 schema の正本は `src/capture/csv_db_schema.py`

### 11.1 schema 更新時の退避

DB のカラム構成が更新され、旧ヘッダから現行ヘッダへ再書き換えが必要になった場合、元ファイルは先に退避する。

- 退避先は `csv_db/old/YYYYMMDD/`
- `YYYYMMDD` は退避実行日
- 同名ファイルが同日に既にある場合は連番サフィックスを付ける

### 11.2 廃止テーブル

現行 schema で使わなくなった CSV も `csv_db/old/YYYYMMDD/` に退避する。

現時点の対象:

- `discard_hands_YYYYMM.csv`

## 12. 実装上の補足

- schema 定義: `src/capture/csv_db_schema.py`
- CSV writer / upsert: `src/capture/storage.py`
- 正本 state: `src/capture/state.py`
- tag 解析と打牌生成: `src/capture/fragment_parser.py`

## 13. 現在の制約

- `REINIT` の河に最初から載っている過去打牌は、元の個別打牌時刻が packet 上に無い場合がある
- そのため、過去打牌の真の時刻を完全には復元できないケースがある
- DB は補助用途であり、完全再構成の唯一正本ではない
