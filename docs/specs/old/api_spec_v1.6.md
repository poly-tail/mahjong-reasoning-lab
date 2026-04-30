# Tenhou Hojo Helper API / 実装仕様 v1.6

## 1. 文書の位置づけ
- 本版は `api_spec_v1.5.md` を継承し、2026-04-06 に追加した GUI layout tuning の実装契約を定義する。
- 対象モジュールは主に `src/ui/table_renderer.py` であり、capture / logic / DB schema の public contract は変更しない。

## 2. 対象モジュール
- `src/ui/table_renderer.py`
- `docs/requirements/requirements_v1.6.md`
- `docs/screen_specs/screen_spec_v1.6.md`

## 3. データ構造

### 3.1 `LayoutTuningSettings`
- 卓レイアウトの主要寸法と余白を保持する dataclass とする。
- 少なくとも以下の field を持つ。
  - `detail_panel_width`
  - `detail_panel_gap`
  - `detail_top_margin`
  - `horizontal_panel_width`
  - `horizontal_panel_height`
  - `vertical_panel_width`
  - `vertical_panel_height`
  - `main_left_margin`
  - `panel_table_gap_extra`
  - `panel_top_margin`
  - `top_panel_top_margin`
  - `right_panel_right_margin`
  - `bottom_margin`
  - `hand_gap_margin`
  - `hand_bottom_margin`
  - `side_discard_extra_height`

### 3.2 `LayoutTuningControlSpec`
- tuning window の slider 定義を表す immutable dataclass とする。
- `field_name`, `label`, `min_value`, `max_value`, `resolution` を持つ。

## 4. 永続化仕様
- `_layout_tuning_settings_path()` は `csv_db/ui_layout_tuning.json` を返す。
- `_load_layout_tuning_settings()` は JSON を読み、読込失敗時は既定値を返す。
- `_save_layout_tuning_settings()` は current tuning を JSON へ保存する。
- `_normalize_layout_tuning_settings()` は欠損値、不正値、型ぶれを既定値へ補正する。
- JSON key は `LayoutTuningSettings` の field 名と 1 対 1 で対応する。

## 5. GUI / renderer 連携仕様
- `create_canvas()` は `board_canvas.layout_tuning_settings` を初期化し、`LAYOUT` ボタンと `Ctrl+Shift+L` shortcut を登録する。
- tuning window は `Toplevel` とし、同時に複数生成しない。既存 window がある場合は再利用して前面へ出す。
- slider 変更は `handle_layout_tuning_change()` を通して current session の tuning 値へ反映し、直ちに `redraw()` を呼ぶ。
- `Save` は JSON 永続化、`Reset` は dataclass 既定値への復帰、`Close` は window の破棄のみを行う。
- window を閉じても current session の tuning 値は保持される。再起動時には保存済み値のみが初期値として復元される。

## 6. レイアウト計算仕様
- `_render_table()` は keyword-only 引数 `layout_tuning` を受け取り、そのまま `_build_layout()` へ渡す。
- `_build_layout()` は `layout_tuning` を `LayoutTuningSettings` として正規化し、responsive / non-responsive の両分岐で主要寸法計算へ反映する。
- tuning は panel 幅、高さ、margin、gap、side discard extra height にのみ効かせ、牌内容、危険度、AI 推奨データには影響させない。

## 7. 非対象
- `capture.fragment_parser.py`, `capture.storage.py`, `logic.danger_suji.py`, `logic.hand_analysis.py` のアルゴリズム契約は本版で変更しない。
- `TableLayout.region_rects` への新規 region id 追加は本件の必須要件ではない。`LAYOUT` ボタンと tuning window は renderer 補助 UI として扱う。
