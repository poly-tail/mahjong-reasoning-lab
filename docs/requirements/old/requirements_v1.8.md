# Tenhou Hojo Helper 要件定義書 v1.8

## 1. 文書の位置づけ
- 本版は `requirements_v1.7.md` を継承し、2026-04-09 時点の `LAYOUT` 直接ドラッグ調整と `AI TOP3` 履歴保存を追記する。
- 主対象モジュールは `src/ui/table_renderer.py`, `src/app/main.py`, `src/capture/state.py`, `src/capture/storage.py` とする。

## 2. 改定の主眼
- `Layout Tuning` window を開いている間、卓上の `PANEL` / `DISCARD` / `MELD` 矩形を直接ドラッグして preview できること。
- ドラッグ結果は盤面外へ出ず、固定領域や他の draggable component と極端に重ならない形へ自動解決されること。
- `AI TOP3` パネル表示中に取得した top3 を、次の自家打牌 row の `discard_fact.pystyle_top1..3_*` として保存できること。

## 3. GUI 要件
- `REQ-GUI-29`: `Layout Tuning` window が開いている間だけ、卓上に draggable overlay を表示して `PANEL TOIMEN`, `PANEL KAMI`, `PANEL SHIMO`, 各家 `DISCARD`, 各家 `MELD` を直接ドラッグできること。
- `REQ-GUI-30`: drag 中の preview は `detail`, `center`, `hand`, `bottom panel` などの固定領域と盤面境界を守りつつ解決すること。
- `REQ-GUI-31`: drag release は current session preview を保持するだけで、永続化は `Save` 実行時に限ること。
- `REQ-GUI-32`: `Reset` は slider 値だけでなく per-component drag offset も既定値へ戻すこと。
- `REQ-GUI-33`: status label は drag 対象名と `dx`, `dy` を表示し、`preview only` と `saved` を区別できること。

## 4. データ要件
- `REQ-DATA-26`: `csv_db/ui_layout_tuning.json` は既存 tuning field に加えて `component_offsets` を保持できること。
- `REQ-DATA-27`: `component_offsets` は component key ごとの `(dx, dy)` translation を表し、load 時に clamp / normalize されること。
- `REQ-DATA-28`: `CaptureState` は `AI TOP3` 表示結果を `(round_id, next_discard_index, hand_key)` 単位で一時保持できること。
- `REQ-DATA-29`: `discard_fact` の自家打牌 row では `pystyle_top1_tile_37_text`, `pystyle_top1_expected_value_text`, `pystyle_top2_*`, `pystyle_top3_*` を保持できること。
- `REQ-DATA-30`: live sync で同じ `discard_fact` row を再 upsert しても、既に保存済みの非空 `pystyle_top*` 列は blank で上書きしないこと。

## 5. 運用要件
- `REQ-OPS-09`: `requirements/current.md`, `specs/current.md`, `screen_specs/current.md` は `v1.8` を指すこと。
- `REQ-OPS-10`: 2026-04-09 の addendum として `docs/changelog.md`, `docs/architecture/project_guide.md`, `docs/architecture/source_overview.md`, `docs/architecture/src_call_graph.md` を同期すること。

## 6. 保守要件
- `NFR-MAINT-09`: drag preview 追加によって既存 slider tuning, DETAIL, `AI TOP3`, danger 表示の redraw 経路を壊さないこと。
- `NFR-MAINT-10`: `AI TOP3` 履歴キャッシュは live session reset 時に破棄され、局またぎで誤混入しないこと。
- `NFR-MAINT-11`: `AI TOP3` 履歴保存は既存の 14 枚手前提を変えず、取得できなかった局面では空欄のままにすること。
