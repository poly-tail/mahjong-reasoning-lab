# リポジトリ横断回帰チェックリスト

この文書は、UI専用の不変条件を定義する [../screen_specs/invariants.md](../screen_specs/invariants.md) とは別に、capture から配布までの横断確認を扱う。

## 起動

- 自動テスト: `python -m compileall -q src`
- 手動確認: `python src/tenhou_hojo.py --mock`
- 期待結果: GUIが起動し、mock卓が描画される。
- 疑う箇所: `src/tenhou_hojo.py`, `src/app/main.py`, import path, runtime path。

## live capture

- 自動テスト: `tests/test_tshark_capture_interface.py`
- 手動確認: `--debug-tags` 起動、`logs/live_capture.log` の診断名を確認。
- 代表入力: `INIT`, `REINIT`, `D/E/F/G`, `N`, `DORA`, `AGARI`
- 期待結果: 通常の tshark 起動メッセージは info、真の失敗だけ error。
- 疑う箇所: `src/capture/tshark_capture.py`, TLS keylog, interface選択。

## pcap replay

- 自動テスト: `tests/test_pcap_replay.py`
- 手動確認: `python src/tenhou_hojo.py --test sample.pcapng --tls-keylog sample.keys --test-interval-ms 0`
- 期待結果: 1行は共有 parser へ1回だけ渡る。event順序が変わらない。
- 疑う箇所: `src/capture/pcap_replay.py`, `parse_tshark_output_line()`, `split_tshark_line()`。

## parser / INIT / REINIT / state更新

- 自動テスト: `tests/test_live_reinit_bootstrap.py`, `tests/test_live_snapshot_cache.py`
- 代表入力: `INIT`, 同一局 `REINIT`, `REINIT.kawa`, 副露付き `REINIT`
- 期待結果: `REINIT` は復帰snapshotとして扱い、既存局データを不要に破壊しない。
- 疑う箇所: `src/capture/fragment_parser.py`, `src/capture/state.py`, `src/app/main.py`。

## DB保存 / 旧CSV互換性

- 自動テスト: `tests/test_live_capture_agari_storage.py`, `tests/test_player_profile_storage.py`
- 期待結果: 欠落禁止イベントは保存され、旧CSVは必要時に互換補完される。
- 疑う箇所: `src/capture/storage.py`, `src/capture/csv_db_schema.py`。

## UI refresh / 河差分描画 / 副露 / 手牌

- 自動テスト: `tests/test_discard_borders.py`, `tests/test_meld_display.py`, `tests/test_hand_auto_mode.py`
- 期待結果: 河は歯抜けにならず、`P` は各席の1段目には出ず2段目以降の対象 slot では消えず、lag/手出し/ツモ切り/思考時間が後退表示しない。heavy analysis 完了時の async-only refresh は side panel / hand / analysis overlay だけを差し替え、base river / table frame を再描画しない。
- 疑う箇所: `src/ui/table_renderer.py`, `src/app/main.py`。

## danger / suji / push

- 自動テスト: `tests/test_danger_suji_*.py`, `tests/test_danger_suji_line_table.py`, `tests/test_tenpai_probability.py`, `tests/test_player_panel_alerts.py`, `tests/test_live_snapshot_cache.py`
- 期待結果: 固定 table は安定した 18 行を持ち、名前付き係数の積、legacy `line_weights` 順、base / concentrated の 34 要素 numerator と denominator が従来値に一致する。過去 Push 再生は current actor だけを構築しても返却結果と cache hit を変えない。Push、remain、red tint、safe tile の判定データがpanel/河/DBで矛盾しない。河 `P` の1段目非表示は意図的な表示 gate として扱う。同一局の heavy suji / 危険度計算中は直前完了済み panel / hand danger / analysis overlay を保持し、手牌 danger は同じ牌と同牌内の出現順で現在手牌へ対応付ける。初回だけ loading / 棒なし、新局では前局値なしとする。保持中の stale 値は自動打牌や alert 音声の新規判定へ使わない。
- 疑う箇所: `src/logic/danger_suji.py`, `src/ui/table_renderer.py`, `src/capture/storage.py`。

## Bridge / pystyle / Nodocchi / NAGA

- 自動テスト: `tests/test_tenhou_ui_bridge.py`, `tests/test_pystyle_request_history.py`, `tests/test_nodocchi_stats.py`, `tests/test_naga_analyzer.py`
- 手動確認: 外部接続はmockまたは明示環境で確認する。
- 期待結果: UI threadをblockingせず、失敗時に操作不能へ落ちない。
- 疑う箇所: `src/app/tenhou_ui_bridge_*`, `src/app/hand_recommendation_service.py`, `src/app/nodocchi_stats.py`, `src/app/naga_analyzer.py`。

## graceful shutdown

- 自動テスト: 関連thread/queueテスト
- 手動確認: GUI終了時に tshark / DB worker / background worker が残らない。
- 疑う箇所: process lifecycle, queue flush, worker stop。

## runtime data保護 / ZIP作成

- 自動テスト: `tests/test_package_workspace.py`
- 代表入力: `.secrets/`, `logs/`, `csv_db/`, `reports/`, `.pcapng`, keylog, browser state, 既存ZIP
- 期待結果: source profileでは禁止pathが入らない。runtime-backupでも秘密情報は拒否。
- 疑う箇所: `.gitignore`, `scripts/package_workspace.py`。

## docs同期

- 自動テスト: なし。
- 手動確認: 変更領域の正本文書、`docs/changelog.md`, 必要なADRを確認。
- 期待結果: 実装とdocsが同じ挙動を説明している。
- 疑う箇所: `docs/README.md`, `docs/architecture/*`, 対象仕様書。
