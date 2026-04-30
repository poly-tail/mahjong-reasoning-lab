# Tenhou Hojo Helper 要件定義書 v1.6

## 1. 文書の位置づけ
- 本版は `requirements_v1.5.md` を継承し、2026-04-06 時点の GUI layout tuning 追加分を上書き追記する。
- 対象は `src/ui/table_renderer.py` を中心とした卓画面レイアウト調整機能であり、牌譜解析、危険度ロジック、DB 分析ロジックの意味は変更しない。

## 2. 改定の主目的
- 卓画面の余白、パネル幅、上下位置などの微調整を、都度コード編集せず GUI 上で試せるようにする。
- 調整値をその場で preview しつつ、必要な値だけを保存して次回起動時にも再利用できるようにする。
- レイアウト調整機能を renderer 内へ閉じ込め、他レイヤーへ副作用を広げない。

## 3. GUI 要件
- `REQ-GUI-21`: メイン卓画面は `LAYOUT` ボタン、または `Ctrl+Shift+L` で `Layout Tuning` window を開けること。
- `REQ-GUI-22`: tuning window は少なくとも次の調整項目を slider で提供すること。
  - top / bottom panel width
  - top / bottom panel height
  - side panel width
  - side panel height
  - detail panel width / gap / top margin
  - main left margin
  - panel-table gap
  - side panels top
  - top panel top
  - right panel margin
  - bottom panel margin
  - hand-panel gap
  - hand bottom margin
  - side discard extra height
- `REQ-GUI-23`: slider 変更は即時に現在の卓画面へ反映され、アプリ再起動までは window を閉じてもその session 内で維持されること。
- `REQ-GUI-24`: tuning window は `Save`, `Reset`, `Close` を持つこと。`Reset` はその場で既定値へ戻し、`Close` は window を閉じるだけで current session の preview を巻き戻さないこと。
- `REQ-GUI-25`: 保存済み値は次回起動時の初期レイアウトへ反映されること。

## 4. データ保存要件
- `REQ-DATA-18`: GUI layout tuning の保存先は `csv_db/ui_layout_tuning.json` とすること。
- `REQ-DATA-19`: 保存フォーマットは JSON とし、key 名は renderer が参照する tuning field 名と一致させること。
- `REQ-DATA-20`: 保存ファイルが存在しない、壊れている、値が不正な場合は安全に既定値へ fallback すること。

## 5. 実装運用要件
- `REQ-OPS-05`: 軽微な UI 配置調整は、原則として GUI tuning で試せる状態を保ち、恒常的なコード修正の前に実画面で当たりを付けられること。
- `REQ-OPS-06`: `requirements/current.md`, `specs/current.md`, `screen_specs/current.md` は `v1.6` を指すこと。

## 6. 非機能要件
- `NFR-MAINT-05`: tuning 値は型付きの単一設定オブジェクトへ集約し、`_build_layout()` が一貫して参照できること。
- `NFR-MAINT-06`: tuning 機能の追加によって、卓画面の redraw、`AI TOP3`、DETAIL、危険度表示の既存データ経路を破壊しないこと。
