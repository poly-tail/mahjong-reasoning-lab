# 画面マップ

この文書は卓UIの `L2: 画面構造定義` を表す。ID は差分指示とコードレビューでそのまま使う。

## 画面単位

- `table.board`: 卓全体。`src/ui/table_renderer.py` の `TableLayout.page_id` と対応する。

## 領域

- `board.center_square`: 中央卓の正方形ベース領域
- `panel.player.toimen`: 対面の横長プレイヤーパネル
- `panel.player.kamicha`: 上家の縦長プレイヤーパネル
- `panel.player.shimocha`: 下家の縦長プレイヤーパネル
- `panel.detail`: 右側の共有詳細パネル
- `panel.detail.visible3`: 3見え一覧
- `panel.detail.visible4`: 4見え一覧
- `panel.detail.content`: 詳細本文。`DETAIL / STATUS / プレイヤー補正 / 条件表示 / lag marker details` の共有表示先
- `panel.round_center`: ドラ表示と局情報の中央パネル
- `panel.bottom.reserve`: 画面下辺の予約帯。現在は描画契約だけ持つ
- `hand.self`: 自家手牌 strip
- `meld.toimen`: 対面の副露帯
- `meld.kamicha`: 上家の副露帯
- `meld.shimocha`: 下家の副露帯
- `meld.jicha`: 自家の副露帯
- `discard.toimen`: 対面河
- `discard.kamicha`: 上家河
- `discard.shimocha`: 下家河
- `discard.jicha`: 自家河

## 構成要素

- `panel.player.*.summary`: 各プレイヤーパネルの `SUMMARY` セクション
- `panel.player.*.alert`: 各プレイヤーパネルの `ALERT` セクション
- `panel.player.*.buttons`: 各プレイヤーパネルの `BUTTONS` セクション
- `button.player.detail`
- `button.player.status`
- `button.player.adjustment`
- `button.player.score_condition`
- `detail.visible3.grid`
- `detail.visible4.grid`
- `detail.player_memo.editor`
- `detail.player_status.summary`
- `detail.player_status.nodocchi_link`
- `detail.placeholder.message`
- `hand.ai_top3.button`
- `hand.ai_top3.panel`
- `hand.self.alert`
- `hand.self.visible_dora`
- `hand.self.honor_visible_count`
- `hand.danger_bars`
- `discard.*.marker_cluster`
- `discard.*.thinking_band`
- `discard.*.peak_thinking_marker`
- `discard.*.riichi_marker`
- `detail.visible*.tile_flag_border`
- `round.dora.indicators`
- `round.info.text`

## 制約ラベル

- `seat-anchored`: 席方向の意味を変えない
- `fixed-right-detail`: 詳細パネルは右端固定
- `shared-detail-area`: 詳細ビューは `panel.detail.content` を共有する
- `centered-bottom-hand`: `hand.self` は下辺中央基準
- `river-grid-6x3`: 河は 6列 x 3行 の上限を維持
- `meld-band`: 副露は専用帯に閉じ込める
- `tile-image-first`: 牌情報は実牌画像を優先する
- `scale-first-responsive`: responsive は縮尺優先で扱う

## コード対応

- `src/ui/table_renderer.py` の `_build_layout()` が上記 region の矩形を計算する。
- `TableLayout.region_rects` は、この文書の region id と1対1で対応する。
- 新しい region を追加したときは、ここへ id を追記してから差分編集対象に含める。
