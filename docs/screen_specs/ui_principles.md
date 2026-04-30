# UI原則

この文書は卓UIの `L1: 画面原則` を定義する。個別の見た目差分はここへ追記せず、`change_request.md` で局所的に管理する。

## 1. 画面思想

- 卓画面は `table.board` を中心とした「席アンカー型レイアウト」とする。
- 他家情報は各席方向に固定し、`toimen=上`, `kamicha=左`, `shimocha=右` の意味を崩さない。
- 自家操作は画面下辺へ寄せ、手牌判断の主導線を `hand.self` に集約する。
- 詳細表示は `panel.detail` の共有領域へ集約し、補助ビューを画面各所へ分散させない。
- responsive は「構造変更」より「縮尺調整」を優先し、卓の意味配置を維持する。
- 牌は文字列より実牌画像を優先し、牌種判断の速度を落とさない。

## 2. 編集モード

- `Layout Fix Mode`: 位置、幅、高さ、余白だけを変える。文言、色、機能、部品構成は変えない。
- `Style Fix Mode`: 色、線、フォント、強調だけを変える。矩形配置と機能は変えない。
- `Content Fix Mode`: ラベル、説明文、文言だけを変える。レイアウトと構造は変えない。
- `Structural Refactor Mode`: レイアウト契約やコンポーネント境界自体を見直す。`screen_map.md` と `invariants.md` の更新を必須にする。
- `Bug Fix Mode`: 不具合箇所だけを直す。見た目改善目的の横滑り変更は行わない。

## 3. 依頼ルール

- 変更依頼は必ず `screen_map.md` の `region/component id` を使う。
- 「少し右」「いい感じに」ではなく、「右端固定」「折り返し禁止」「A の右隣」のような制約で書く。
- 1回の依頼で触るのは原則 `2 region` または `3 component` までに絞る。
- 毎回 `対象 / 非対象 / 制約 / 完了条件` を明示する。
- 実装後は、変更した id と変更していない id を差分サマリとして残す。

## 4. コード上の基準点

- レイアウト計算の正本は `src/ui/table_renderer.py` の `TableLayout`。
- 各領域の矩形は `TableLayout.region_rects` に screen-map id 付きで集約する。
- 画面差分で新しい領域を追加した場合は、`TableLayout` と `screen_map.md` を同時に更新する。
