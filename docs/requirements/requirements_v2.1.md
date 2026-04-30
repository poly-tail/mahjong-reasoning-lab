# 要件定義 v2.1

updated: `2026-04-21`

## 1. コア要件

- live capture / replay / XML import の 3 経路を同じ renderer へ流せること
- Tenhou UI Bridge を使ったブラウザ操作連携を維持すること
- 画面更新を止めやすい処理は常駐 worker または background 実行へ逃がすこと

## 2. 見え枚数

- actual visible は `手牌 + 捨て牌 + 晒し牌 + ドラ表示牌` のみで数える
- actual visible は lag 推測や awaseuchi 推測の影響を受けない
- inferred visible は renderer 側の常駐 worker 1 本で処理する
- inferred visible は actual visible を書き換えない
- UI 上の合算表示は `4見え` を上限とする

## 3. 画面表示

- `AI TOP3` は `pt + 和了率` を表示する
- `AI TOP3` 直下に `総計` 状況表を置く
- `上家 / 対面 / 下家` の状況表は各相手の河と副露の間へ置く
- 自家の `2見え以下字牌` 一覧は、自河の中央固定ではなく自副露帯寄りに少し下げて表示する
- 河の記号は `L`, `Pl`, `P` を使う
- tint 優先順位は `purple > brown > red` とする

## 4. 状況表

- `上家 / 対面 / 下家 / 総計` の 4 面を表示する
- 各相手面は `M123, M456, M789, P123, P456, P789, S123, S456, S789, 字` の 10 block を持つ
- manual input の範囲は `-4 .. +4`
- 左 click は `+1`、右 click は `-1`
- `総計` は 3 面平均の read-only 表示とする
- `Σ` は 10 block 合計、`Σ/n` は `0.0` の数牌セル数で割った値とする

## 5. 自動化

- `pystyle ON` 中は `自動和了 ON` / `鳴き無し ON` / `リーチ優先` を守る
- 推奨応答が未到着または失敗時は turn-start 基準の fallback を使う
- Bridge snapshot は `1 in-flight + pending 1` の制御を守る

## 6. ドキュメント同期

変更時は最低でも次を同期する。

- `docs/specs/api_spec_v2.1.md`
- `docs/screen_specs/display_overview.md`
- `docs/screen_specs/river_display.md`
- `docs/screen_specs/alerts_and_panels.md`
- `docs/screen_specs/controls_and_bridge.md`
- `docs/screen_specs/visible_counts_ui.md`
- `docs/architecture/project_guide.md`
- `docs/architecture/src_call_graph.md`
- `docs/changelog.md`

## 7. 配布・保存

- Python 依存は `requirements.txt` で再現できること
- ドキュメントグラフは `scripts/render_docs_graphs.py` で再生成できること
- 状態保存用 ZIP は `scripts/package_workspace.py` で再作成できること
