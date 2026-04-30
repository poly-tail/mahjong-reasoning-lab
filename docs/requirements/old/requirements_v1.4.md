# Tenhou Hojo Helper 要件定義書 v1.4

## 1. 目的
- 天鳳の WebSocket タグデータから局状態を可能な限り正確に復元し、GUI 表示、DB 記録、後続解析に共通利用できる状態モデルを定義する。
- 特に、復号済みテキスト行から `tag` 抽出、`Event` 正規化、`GameState` 反映までを可読性優先で実装し、最終的な「牌譜完全再現」の基盤を整える。

## 2. スコープ
- GUI アプリケーション本体、牌画像の読み込みと描画、局状態の可視化、WebSocket タグ解析、CSV DB への保存を対象とする。
- TLS 復号そのもの、牌理評価、AI による判断支援、未確定仕様の断定的補完は対象外とする。

## 3. 用語
- **GameState**: 半荘単位の状態。プレイヤー情報、局一覧、raw event、unknown tag、diagnostics を保持する。
- **RoundState**: 1 局単位の状態。手牌、河、副露、ドラ、リーチ状態、結果、検証結果を保持する。
- **確定仕様**: 実装で必ず守る仕様。推定と混在させない。
- **暫定仕様**: 便宜的に扱うが、推定であることをフラグや diagnostics で明示する仕様。
- **未確定仕様**: 実装上 TODO として残し、勝手に意味付けしない仕様。
- **136牌 ID**: 通信上の牌一意 ID。0-origin を正本とし、必要に応じて 1-origin 入力を正規化する。
- **37種表現 spec**: 赤牌を含む 0..36 の内部表現。
- **37種表現 UI**: 既存 GUI と互換な 1..37 の表示表現。

## 4. システム概要
- Python 3.x、`tkinter`、`Pillow` を用いて GUI を構成する。
- `tshark` の出力や TLS 復号済み CSV/テキストを入力とし、タグ断片を `GameState` へ反映する。
- GUI は `GameState` / `CaptureState` の live 配列を読み、牌・副露・ドラ・見え牌情報を再描画する。
- DB は現時点では正本ではなく、`csv_db/` 配下の CSV 群を補助保存先として扱う。

## 5. 利用者
- 天鳳対局を振り返るプレイヤーや解析者。
- 解析器、GUI、DB スキーマを保守・拡張する開発者。

## 6. 機能要件
- **REQ-GUI-01**: タイトル `Tenhou Helper` のメインウィンドウを表示する。
- **REQ-GUI-02**: 中央の卓エリアに 4 プレイヤー分の捨て牌を同時表示する。
- **REQ-GUI-03**: 自家の手牌と自家の捨て牌が重ならないよう、別領域に表示する。
- **REQ-GUI-04**: 捨て牌は時系列順に並べ、1 段 6 枚で折り返す。
- **REQ-GUI-05**: 起動時に標準牌と赤牌の画像を読み込み、座席の向きに応じて回転表示する。
- **REQ-GUI-06**: 手出しとツモ切りを視覚的に区別して表示する。
- **REQ-GUI-07**: 卓の上下左右に 4 つのプレイヤーパネルを設け、アラート情報と `DETAIL` ボタンを表示する。
- **REQ-GUI-08**: 画面右側に 1 つの詳細情報表示スペースを設ける。
- **REQ-GUI-09**: 詳細情報表示スペースの上部には 4 見え牌エリアと 3 見え牌エリアを配置する。
- **REQ-GUI-10**: 詳細情報表示スペースの下部は、ボタン操作に応じて内容が切り替わる詳細情報エリアとする。
- **REQ-GUI-10a**: プレイヤーパネルにはプレイヤー名を表示する。
- **REQ-GUI-10b**: 各プレイヤーパネルの `DETAIL` ボタンは、共通 DETAIL 欄へそのプレイヤーの `player_profiles.user_memo` 編集画面を表示できること。
- **REQ-GUI-10c**: 共通 DETAIL 欄の表示を別ボタンで切り替えるときは、表示中のメモを保存してから前画面を閉じること。
- **REQ-GUI-11**: 中央情報枠には局数、本場、ドラ、供託本数などを表示できるようにする。
- **REQ-GUI-12**: 再描画後も UI がフリーズせず、操作を継続できるようにする。
- **REQ-DATA-01**: 内部の牌正本は raw `tile_136` とし、局状態は `GameState` / `RoundState` で管理する。
- **REQ-DATA-02**: 37種変換は `tile136_to_tile37_spec()` と `tile136_to_tile37_ui()` の 2 系統を提供する。
- **REQ-DATA-03**: `GameState` はプレイヤー情報、局一覧、current round、raw events、unknown tags、diagnostics、未確定仕様 TODO を保持する。
- **REQ-DATA-04**: `RoundState` は局情報、手牌、河、副露、ドラ、リーチ状態、結果、REINIT raw kawa、validation issues、`started_from_init_like` を保持する。
- **REQ-DATA-05**: `Discard` は `tsumogiri` の確定/推定を区別し、推定時は `is_tsumogiri_estimated=True` を持つ。
- **REQ-DATA-06**: `Meld` は raw `m`、副露種別、面子全体、手出し寄与分、加槓元参照を保持し、ポンから加槓への更新を許容する。
- **REQ-DATA-07**: 各 event は `timestamp`、`event_type`、`seat`、`tile_136`、`raw_tag`、属性辞書を保持する。
- **REQ-DATA-08**: `GameState` は `parser_mode`、`self_abs_seat`、`seat_mapping_resolved`、`players_abs`、`players_rel` を保持し、XML absolute seat と内部 relative seat の両方を追跡できること。
- **REQ-DATA-09**: `RoundState` は `oya_abs`、`oya_rel`、`initial_hands_abs_136`、`initial_hands_rel_136` を保持し、親情報と配牌を absolute/relative の両系で参照できること。
- **REQ-DATA-10**: 各 event は必要に応じて `action_delay_ms`、`delay_source`、`delay_confidence` を保持し、観戦 websocket の timing heuristic を記録できること。
- **REQ-CAP-01**: 入力は `tshark` の行出力、TLS 復号済み CSV、復号済みテキスト blob のいずれにも拡張しやすい構造にする。
- **REQ-CAP-02**: 1 行に複数タグが含まれる前提で断片抽出を行う。
- **REQ-CAP-03**: XML 風 tag、JSON wrapper、bare tag を同じ入口で正規化する。
- **REQ-CAP-04**: `INIT` は局開始イベントとして扱い、局番号、本場、供託、サイコロ、ドラ表示牌、配牌を反映する。
- **REQ-CAP-05**: `REINIT` は `INIT` と同一視せず、完全状態復元イベントとして扱う。
- **REQ-CAP-06**: `REINIT` では `hai` と `hai0..hai3` の両形式を受け付け、`hai0..hai3` を優先する。
- **REQ-CAP-07**: `REINIT.kawa` の `254` / `255` は意味を断定せず、生値列として保持する。
- **REQ-CAP-08**: `T/U/V/W` と `D/E/F/G` を seat + action に正規化する。
- **REQ-CAP-09**: `N` タグは少なくとも `chi` / `pon` / `daiminkan` / `ankan` / `kakan` を判定できること。
- **REQ-CAP-10**: `REACH step=1` は宣言、`step=2` は成立として別状態で保持する。
- **REQ-CAP-11**: `DORA`、`AGARI`、`RYUUKYOKU` を局状態に反映する。
- **REQ-CAP-12**: lowercase discard は「直前 draw と同牌なら確定ツモ切り、それ以外は推定ツモ切り」の暫定仕様として扱い、推定フラグを必ず付ける。
- **REQ-CAP-13**: 未対応タグや解釈不能データは silent failure せず、`unknown_tags` と diagnostics に保存する。
- **REQ-CAP-14**: `LN` / `REJOIN` は未確定仕様として TODO に残し、状態遷移には使わない。
- **REQ-CAP-15**: REINIT 後や読み込み完了後に局整合性チェックを実行できること。
- **REQ-CAP-16**: 入力経路として `--mock`、`.pcapng` テスト入力、live packet capture、`--xml-url` の 4 系統を提供すること。
- **REQ-CAP-17**: parser mode は `player_live`、`spectator_live`、`xml_log` を区別し、live websocket と XML log を別契約で扱うこと。
- **REQ-CAP-18**: `spectator_live` では `INITBYLOG` / `WGC` を通常の初期化系タグとして受理し、`T/U/V/W` draw tag が存在しないことを正常系として扱うこと。
- **REQ-CAP-19**: `spectator_live` では `1234D56` のような discard prefix を牌 ID とみなさず、打牌までの時間の heuristic として `action_delay_ms` に保持すること。
- **REQ-CAP-20**: `xml_log` は absolute seat ベースとして扱い、イベントパース前に `UN` を読んで `self_abs_seat` を解決し、可能なら `self_player_name` や URL 上の `tw=` も使って自己席を確定すること。
- **REQ-CAP-21**: XML では `hai`、`oya`、`TUVW`、`DEFG`、`N who`、`REACH who`、`AGARI who`、`fromWho`、`RYUUKYOKU` の seat 系情報を absolute から relative へ変換し、同時に `oya_abs` も保持すること。
- **REQ-CAP-22**: XML で `self_abs_seat` を即時確定できない場合でも silent failure せず、`seat_mapping_resolved=False` の pending 状態として保持し、後から座席対応を再解決できること。
- **REQ-CAP-27**: `player_live` / `spectator_live` では、`UN` による相対席プレイヤー名シグネチャ変更、または `TAIKYOKU.log` 切替を新半荘として扱い、in-memory state を自動初期化できること。
- **REQ-API-01**: `load_from_decrypted_lines(lines)` を提供する。
- **REQ-API-02**: `load_from_text(text)` を提供する。
- **REQ-API-03**: `export_round_summary(game_state)` を提供する。
- **REQ-API-04**: `export_discards(game_state)` を提供する。
- **REQ-API-05**: `export_event_rows(game_state)` と `export_event_csv_text(game_state)` を提供する。
- **REQ-API-06**: `load_from_decrypted_lines()` と `load_from_text()` は `parser_mode` を受け取り、必要なら観戦系へ自動昇格できること。
- **REQ-API-07**: XML 読込 API として `load_from_xml_text()` および `load_from_xml_url()` を提供し、`self_abs_seat` と `self_player_name` を指定できること。
- **REQ-API-08**: `export_round_summary()` は `parser_mode` を含み、`export_event_rows()` / `export_event_csv_text()` は delay metadata 列を出力できること。
- **REQ-DB-01**: DB は `csv_db/` ディレクトリ配下の規定 CSV 群で構成すること。
- **REQ-DB-02**: 半荘と局は `hanchan_master.csv` / `kyoku_master.csv` に保存し、打牌は `discard_fact_YYYYMM.csv` を主テーブルとして保存すること。
- **REQ-DB-02a**: 打牌主キー `discard_id` は `{kyoku_id}_{discard_indexの3桁}` 形式で保存すること。
- **REQ-DB-03**: 打牌補助情報は `discard_context_YYYYMM.csv` / `player_profiles.csv` に分離し、手牌情報は `discard_fact_YYYYMM.csv` 内で後から補完できること。
- **REQ-DB-04**: CSV writer は `init` / `reinit` / `initbylog` / `wgc` を半荘切替候補として扱い、当日相対席プレイヤー名シグネチャが変わった場合は `current_hanchan` を切り替えること。
- **REQ-OPS-01**: 局開始時や再同期時に GUI 表示内容をリセット・再構成できること。

## 7. 非機能要件
- **NFR-ENV-01**: Windows 10 以降、Python 3.x、`tkinter` が利用可能な環境を対象とする。
- **NFR-ENV-02**: 牌画像はプロジェクトのアセットディレクトリから読み込む。
- **NFR-PERF-01**: 画像ロードは起動時に完了し、打牌更新時の遅延は目立たないこと。
- **NFR-REL-01**: キャプチャ失敗、画像欠落、unknown tag、局検証失敗をログや diagnostics で診断できること。
- **NFR-REL-02**: 仕様不明部分を勝手に補完せず、未対応データは保持して継続処理すること。
- **NFR-MAINT-01**: パーサは固定位置スライスに依存せず、タグ種別追加や入力形式追加を局所変更で拡張できる構造にすること。
- **NFR-MAINT-02**: 可読性を優先し、タグ解釈・副露 decode・状態更新・DB 保存を分離すること。

## 8. データ要件
- `raw_tag` はすべての event で保持すること。
- `GameState.unknown_tags` と `GameState.diagnostics` は unknown や validation warning の追跡に使えること。
- `RoundState.reinit_kawa_raw` は `REINIT` の河 marker を含む生配列を保持すること。
- `RoundState.validation_issues` は局単位の検証結果を保持すること。
- CSV 出力はイベント単位 1 行で、`timestamp`、`tag_type`、`player`、`tile136`、`action`、`tsumogiri_flag`、`raw_tag` を持つこと。

## 9. 制約と前提
- `tshark` が所定の設定で実行できること。
- パケットの `ten` は 100 点単位の値として扱い、内部 `scores` へは実際の点数として 100 倍して保持する。
- `REINIT.kawa` marker の順序依存や lowercase discard の厳密仕様は未確定であり、確定仕様として扱わない。

## 10. 今後の拡張
- `LN` / `REJOIN` の意味確定後の状態反映。
- `REINIT` marker の意味付けと整合性検証の強化。
- DB スキーマの `GameState` / `RoundState` 対応強化。
- GUI の詳細領域に局イベント履歴や diagnostics を接続する。

## 11. スコープ外
- TLS 復号処理自体の自動化。
- AI による意思決定支援。
- 未確定仕様を断定的に補完する実装。
## 2026-04-01 Lag Marker Addendum
- **REQ-DATA-11**: discard データは `lagged(0..5)` と `lag_delay_ms` を持ち、ラグ判定結果を round state と GUI tracker の両方で保持できること。
- **REQ-CAP-23**: parser は打牌または鳴き後打牌から次の `draw` または open meld `call` までの packet arrival 差分を測定し、`>= 5ms` をラグと定義すること。`discard -> open meld call` の鳴き判断時間は打牌思考時間ではなくラグ側として扱い、live 自動判定の `lagged` は `0` または `1` のみを新規付与すること。
- **REQ-CAP-24**: pending discard は `draw` または一致する open meld `call` で解決し、それ以外のイベントでは維持すること。観戦系などで解決不能になった pending discard は未判定のまま破棄してよい。
- **REQ-GUI-13**: ラグが成立した discard には黄色丸を表示し、その位置は 4見え青丸の左隣を牌ローカル座標で回転させた位置にすること。

## 2026-04-01 Snapshot Carryover Addendum
- **REQ-CAP-25A**: `INIT` は常に新局開始として扱い、current round を無条件で初期化すること。
- **REQ-CAP-25B**: `REINIT` や `INITBYLOG` などの snapshot payload は、局キー一致だけで current round を再利用せず、`kawa0..kawa3` の visible discard 一致率がかなり高い場合にだけ再利用すること。現実装の閾値は `80%`。
- **REQ-CAP-25**: `REINIT` や `INITBYLOG` などの snapshot payload が `kawa0..kawa3` を含む場合、既存 discard 列が snapshot の prefix と一致していれば、その prefix 部分の discard metadata を引き継ぐこと。
- **REQ-DB-08**: `INIT` 系を受ける前の途中開始局も live 可視化は継続してよいが、その局は `RoundState.started_from_init_like = False` として扱い、CSV DB には保存しないこと。
- **REQ-DATA-12**: snapshot carryover では `tsumogiri`, `is_tsumogiri_estimated`, `riichi_marker_before`, `called`, `thinking_time_ms`, `thinking_time_source`, `thinking_time_before_reach_ms`, `thinking_time_before_reach_source`, `lagged(0..5)`, `lag_delay_ms`, `raw_tag` を保持すること。

## 2026-04-02 Riichi Thinking-Time Split Addendum
- **REQ-CAP-26**: parser は打牌思考時間を、通常打牌では `draw -> discard`、鳴き後打牌では `call -> discard` として保持し、`REACH step=1` が打牌前に入った場合は `draw/call -> REACH` と `REACH -> discard` の 2 区間へ分割して保持すること。
- **REQ-DATA-13**: discard データは `thinking_time_before_reach_ms` と `thinking_time_before_reach_source` を持ち、`REACH` 打牌の前半思考時間 `draw/call -> REACH` を保持できること。

## 2026-04-03 Danger Suji Heuristic Addendum
- **REQ-LOGIC-01**: 無筋危険度は筋線単位で保持し、牌ごとの numerator はその牌を含む筋線重みの合計、denominator は未解決筋線重みの合計とすること。
- **REQ-LOGIC-02**: open `chi` がある相手には待ち形別の筋線 cap を適用すること。`kanchan=0.5`, `penchan=0.5`, `ryanmen=0.6` を基本とすること。
- **REQ-LOGIC-03**: 同色の手出しが内牌帯から外牌帯へ進んだ場合は、対象中央筋を `0.7` 本として扱うこと。同 bucket 内移動には適用しないこと。
- **REQ-LOGIC-04**: `0` 本抑制を最優先とし、その後に matagi、chi cap、内牌→外牌 cap、lag 補正を適用すること。同一筋線に複数 cap が掛かる場合は最小値を採用すること。
- **REQ-GUI-14**: 自家手牌下バー、相手 `SUMMARY` の分母本数、濃い筋ランキングは同一の最終筋線重みを表示すること。

## 2026-04-02 Live Memory Addendum
- **REQ-CAP-26**: live `tshark` capture は packet 全体をメモリに溜めず、stdout を 1 行ずつ処理すること。
- **REQ-DATA-13**: `player_live` / `spectator_live` では in-memory history を bounded に保ち、`rounds` は最新 4 局、`raw_events` は最新 4096 件、`unknown_tags` と `diagnostics` は各 256 件、`chats` は 128 件まで保持すること。
- **NFR-PERF-02**: 長時間の live capture でも `GameState` が無制限に肥大化しないこと。局更新時と event 追加時の両方で上限制御を適用し、古い局は GC 可能な状態へ落とすこと。
