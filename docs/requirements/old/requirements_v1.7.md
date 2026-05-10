# Tenhou Hojo Helper 要件定義書 v1.7

## 1. 文書の位置づけ
- 本版は `requirements_v1.6.md` を継承し、2026-04-07 時点の DB 待ち牌保存と `Layout Tuning` window の視認性改善を反映する。
- 対象は `src/capture/storage.py`, `src/logic/hand_analysis.py`, `src/capture/csv_db_schema.py`, `src/ui/table_renderer.py` を中心とする。

## 2. 改定の主目的
- 実際の打牌後にテンパイとなる局面の待ち牌を、分析しやすい形で DB へ保存する。
- `Layout Tuning` window の下端見切れを抑え、一般的な表示サイズで全 controls を触りやすくする。
- 既存の `shanten_after_discard` 系列の互換性を保ちつつ、新列で post-discard semantics を追加する。

## 3. GUI 要件
- `REQ-GUI-21`: メイン卓画面は `LAYOUT` ボタン、または `Ctrl+Shift+L` で `Layout Tuning` window を開けること。
- `REQ-GUI-22`: tuning window は卓レイアウト調整項目を slider で提供すること。
- `REQ-GUI-23`: slider 変更は即時に現在の卓画面へ反映され、アプリ再起動までは window を閉じても session 内で維持されること。
- `REQ-GUI-24`: tuning window は `Save`, `Reset`, `Close` を持ち、`Close` は current session の preview を巻き戻さないこと。
- `REQ-GUI-25`: 保存済み値は次回起動時の初期レイアウトへ反映されること。
- `REQ-GUI-26`: tuning window の slider 群は 2 列に分割して表示し、action row は下段固定とすること。
- `REQ-GUI-27`: current control set は panel, discard, meld, player-panel summary/tile-rank まで含む現行 renderer 実装と一致すること。
- `REQ-GUI-28`: 2 列化は即時 preview、`Save / Reset / Close`、`Escape` close といった既存挙動を壊さないこと。

## 4. データ保存要件
- `REQ-DATA-18`: GUI layout tuning の保存先は `csv_db/ui_layout_tuning.json` とすること。
- `REQ-DATA-19`: 保存フォーマットは JSON とし、key 名は renderer が参照する tuning field 名と一致させること。
- `REQ-DATA-20`: 保存ファイルが存在しない、壊れている、値が不正な場合は安全に既定値へ fallback すること。
- `REQ-DATA-21`: `discard_fact` は `wait_tiles_after_discard_mspz` 列を持つこと。
- `REQ-DATA-22`: `wait_tiles_after_discard_mspz` は実際の打牌後 concealed hand がテンパイのときだけ値を持つこと。
- `REQ-DATA-23`: 待ち牌は `mspz` grouped text で保存し、例として `36m`, `258p`, `14z` の形式を許可すること。
- `REQ-DATA-24`: `shanten_after_discard` 系列は legacy column 名を維持しつつ、値は打牌前 concealed hand snapshot 基準で保持すること。
- `REQ-DATA-25`: schema migration 時は既存 CSV の行内容を保持しつつ、不足列を安全に追加できること。

## 5. 実装運用要件
- `REQ-OPS-05`: 軽微な UI 配置調整は、原則として GUI tuning で試せる状態を保つこと。
- `REQ-OPS-06`: `requirements/current.md`, `specs/current.md`, `screen_specs/current.md` は `v1.7` を指すこと。
- `REQ-OPS-07`: 手牌分析の正本ドキュメントは `docs/mahjong/logic/hand_analysis.md` とし、DB 側の待ち牌保存と同時に追従更新すること。
- `REQ-OPS-08`: 本件に関係するプロジェクト文書、ソース概要、フォルダ構成、changelog を同一更新単位で追従させること。

## 6. 非機能要件
- `NFR-MAINT-05`: tuning 値は型付きの単一設定オブジェクトへ集約し、`_build_layout()` が一貫して参照できること。
- `NFR-MAINT-06`: tuning 機能の追加によって、卓画面の redraw、`AI TOP3`、DETAIL、危険度表示の既存データ経路を破壊しないこと。
- `NFR-MAINT-07`: 打牌牌と snapshot の不整合があっても例外停止せず、待ち列は空欄 fallback できること。
- `NFR-MAINT-08`: 待ち牌列挙は concealed hand と open meld 数から再計算し、他の DB 補助列に依存しないこと。
