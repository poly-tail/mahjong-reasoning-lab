# プロジェクトガイド

更新日: `2026-05-10`

## 目的

天鳳補助ツールは、live packet capture / replay / XML / Tenhou UI Bridge / AI 推奨を 1 つのデスクトップツールへ統合することを目的とします。

## 主な入口

- `src/tenhou_hojo.py`: 互換エントリ
- `src/app/main.py`: アプリ全体の起動・分岐・連携
- `src/ui/table_renderer.py`: 画面描画本体
- `src/app/nodocchi_stats.py`: Nodocchi プレイヤー成績の取得・整形
- `src/visible_tiles.py`: 実見え枚数の集計
- `src/logic/danger_suji.py`: remain / push / tint のロジック

## 表示と責務

### 実見え枚数

- 担当: `src/visible_tiles.py`
- 入力: 手牌 / 捨て牌 / 晒し牌 / ドラ表示牌

### 推測見え枚数

- 担当: `src/ui/table_renderer.py`
- canvas ごとの常駐ワーカー 1 本で処理
- 実見え枚数は読み取り専用

### 合わせ打ち

- 担当: `src/ui/table_renderer.py`
- 公開イベントのみを使って provisional / confirm を分ける

## 今回の更新点

- 相手パネルの `STATUS` から Nodocchi 鳳凰卓4人打ち成績を取得し、右詳細領域に表示できるようにした
- Nodocchi 取得は renderer から分離した adapter で処理し、UI thread へは canvas queue で戻す
- 麻雀ドメイン文書を `docs/mahjong/theory`, `logic`, `reference`, `research` に再構成した

## 更新時の同期先

- 画面仕様: `docs/screen_specs/`
- 要件 / 仕様: `docs/requirements/`, `docs/specs/`
- グラフ: `docs/graphs/src/`, `docs/graphs/generated/`
- 更新履歴: `docs/changelog.md`
