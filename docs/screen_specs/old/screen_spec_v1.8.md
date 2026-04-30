# 画面仕様書 v1.8

## 1. 文書の位置づけ
- 本版は `screen_spec_v1.7.md` を継承し、2026-04-09 時点の direct drag preview と `AI TOP3` 保存タイミングを追記する。

## 2. 画面要素

### 2.1 `LAYOUT` ボタン
- 役割は従来どおり `Layout Tuning` window を開くこと。

### 2.2 `Layout Tuning` window
- slider 群、`Save`, `Reset`, `Close`, status text を持つ non-modal window とする。
- window open 中は卓上 preview も編集対象であることを説明文で明示する。

### 2.3 Direct Drag Preview
- `Layout Tuning` window が開いている間だけ、`PANEL`, `DISCARD`, `MELD` の draggable component に dashed outline と label を重ねて表示する。
- pointer down は component rect 内でのみ受け付ける。
- drag 中は status text に component 名と `dx`, `dy` を表示する。
- release 後も current session preview は残り、`Save` 実行で永続化される。

## 3. 振る舞い
- drag preview は盤面外へ出ず、detail / center / hand などの固定領域や他 component と極端に重ならないよう自動解決する。
- `Reset` は slider と drag offset の両方を既定値へ戻す。
- `Close` は window を閉じるだけで current session preview を破棄しない。
- `Save` は current preview を `csv_db/ui_layout_tuning.json` へ保存し、次回起動時の初期値にする。

## 4. `AI TOP3` 表示との関係
- `AI TOP3` パネルの見た目自体は v1.5 から変えない。
- ただし panel が visible の間に top3 が取得できていれば、次の自家打牌 row へその表示内容を保存できる。
- panel 非表示中は新規 POST を行わない従来ルールを維持する。

## 5. 影響範囲外
- 牌画像 asset 切替、danger 計算、DETAIL 内容、capture 状態そのものは本件で変えない。
