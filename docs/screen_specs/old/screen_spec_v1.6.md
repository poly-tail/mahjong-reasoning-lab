# 画面仕様書 v1.6

## 1. 文書の位置づけ
- 本版は `screen_spec_v1.5.md` を継承し、卓レイアウトを GUI から調整する補助 UI を追加定義する。
- 基本の卓面構成と region contract は既存 `screen_map.md` / `ui_principles.md` / `invariants.md` に従う。

## 2. 追加画面要素

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
- `label + slider + current value` の 3 列構成
- action row
  - `Save`
  - `Reset`
  - `Close`
  - status text

## 4. slider 対象
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
- side discard extra height

## 5. 挙動
- slider 変更は即時に卓全体の再描画へ反映する。
- window を閉じても current session の preview は維持する。
- `Reset` はその session の値を既定値へ戻し、その場で再描画する。
- `Save` は current value を `csv_db/ui_layout_tuning.json` へ保存し、次回起動時の初期値にする。
- `Escape` は tuning window を閉じる。

## 6. 影響範囲
- 本機能が変更するのは renderer のレイアウト計算のみ。
- 牌画像そのものの asset 切替、危険度計算、`AI TOP3` の request / response、DETAIL 内容、capture 状態は変えない。
- button / tuning window は補助 UI であり、`TableLayout.region_rects` の卓面 region 契約には含めない。

## 7. 既存卓面との関係
- `LAYOUT` ボタンは卓内容の視認性を極端に阻害しない左上小サイズに留める。
- tuning window は modal ではなく、卓画面を見ながら slider を調整できる。
- 既存の DETAIL / `AI TOP3` / player panel / discard river の表示内容は保ったまま、位置と余白のみ再計算される。
