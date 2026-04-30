# 画面仕様書 v1.7

## 1. 文書の位置づけ
- 本版は `screen_spec_v1.6.md` を継承し、`Layout Tuning` window の視認性改善と現行 control set の整理を反映する。
- 基本の卓面構成と region contract は既存 `screen_map.md` / `ui_principles.md` / `invariants.md` に従う。

## 2. 画面要素

### 2.1 `LAYOUT` ボタン
- 表示位置: 卓 canvas 左上。
- 見た目: 小型の矩形ボタン、ラベルは `LAYOUT`。
- 役割: `Layout Tuning` window を開く。
- shortcut: `Ctrl+Shift+L` でも同じ window を開く。

### 2.2 `Layout Tuning` window
- 種別: `Toplevel` の補助 window。
- 役割: 卓の主要寸法と余白を slider で調整する。
- 再オープン時: 既存 window がある場合は新規生成せず、前面へ出す。

## 3. window 構成
- 説明文 1 行
- control area
  - 左列: 前半の tuning controls
  - 右列: 後半の tuning controls
  - 各 row は `label + slider + current value`
- action row
  - `Save`
  - `Reset`
  - `Close`
  - status text

## 4. 現行 tuning controls
- panel 系
  - top / bottom panel width
  - top / bottom panel height
  - side panel width
  - side panel height
  - detail panel width
  - detail panel gap
  - detail panel top
  - main left margin
  - panel-table gap
  - side panels top
  - top panel top
  - right panel margin
  - bottom panel margin
  - hand-panel gap
  - hand bottom margin
- discard 系
  - discard tile scale
  - top / bottom discard width
  - top / bottom discard height
  - side discard width
  - side discard height
- meld 系
  - meld tile scale
  - top / bottom meld height
  - side meld min width
  - top meld min width
- player-panel 系
  - panel summary top
  - top summary ratio
  - top alert ratio
  - side summary ratio
  - side alert ratio
  - panel tile-rank scale
  - top tile-rank row gap
  - side tile-rank row gap

## 5. 挙動
- slider 変更は即時に卓全体の再描画へ反映する。
- window を閉じても current session の preview は維持する。
- `Reset` はその session の値を既定値へ戻し、その場で再描画する。
- `Save` は current value を `csv_db/ui_layout_tuning.json` へ保存し、次回起動時の初期値にする。
- `Escape` は tuning window を閉じる。

## 6. 視認性要件
- 2 列配置によって、主要な display size で action row が window 下端に隠れにくいこと。
- `LAYOUT` ボタンは卓内容の視認性を極端に阻害しない左上小サイズに留める。
- tuning window は modal ではなく、卓画面を見ながら slider を調整できること。

## 7. 影響範囲
- 本機能が変更するのは renderer のレイアウト計算のみ。
- 牌画像 asset 切替、危険度計算、`AI TOP3` の request / response、DETAIL 内容、capture 状態は変えない。
- button / tuning window は補助 UI であり、`TableLayout.region_rects` の卓面 region 契約には含めない。
