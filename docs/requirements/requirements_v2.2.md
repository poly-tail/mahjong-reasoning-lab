# 要件定義 v2.2

updated: `2026-05-24`

## 1. 目的

天鳳の live / replay / XML 局面を、補助判断・自動操作・分析へつなげるローカル支援 UI として維持する。v2.2 では、直近で追加した alert 音声、NAGA 自動表示、Nodocchi STATUS、河描画高速化、DB分析の要件を正本化する。

## 2. 表示要件

- 画面は卓、河、他家プレイヤーパネル、自家手牌、詳細領域、Bridge 操作、NAGA 下部パネルで構成する。
- 他家プレイヤーパネルは `SUMMARY`, `ALERT`, `SCORE`, `BUTTONS` を持つ。
- `SUMMARY` の `Remain current/no-temp` と `ALERT` の黄色・赤・紫は同じ no-temp remain 閾値を使う。
- Nodocchi `STATUS` では和了率・副露率・リーチ率を赤字、その他の成績値を白字にする。
- 河は赤枠、黄枠、`L`, `Pl`, `P`, 同順合わせ打ち、最大思考時間、3見え/4見え、赤/茶/紫 tint を同時に表現できる。
- 南2局以降は NAGA 段位ポイント分析を自動取得し、主要な放銃・和了・流局の pt 変化を最下部へ短く表示する。

## 3. 音声要件

- 音声は画面に表示される他家 alert を起点に鳴らす。
- 自分側の残り筋や、プレイヤーパネルに出ない Push / Remain 系 alert は音声対象外とする。
- `Push` 音声と河の `P` マークは同一更新で反映し、音だけ先行しない。
- `Remain` 音声は `r-red`, `r-yellow`, `r-purple` のように `r` を先頭へ付けた読みを使う。
- 音声再生は専用 worker queue で行い、UI thread を止めない。

## 4. 性能要件

- 河は最大 4人 x 18枚を毎回全描画しない。座席 + 捨て牌 index の表示シグネチャが変化した牌だけ描画し直す。
- 色付き牌のための `PhotoImage` 合成は discard path で行わない。通常牌画像を使い、色は Canvas overlay で重ねる。
- discard path の Canvas item は作成時に `tags=` を付ける。
- `side_panels` と `discards` は slow log に phase breakdown を残し、重い処理のランキングを取れるようにする。
- full redraw、UI scale 変更、round reset、manual reinit では河描画 cache を明示的に破棄する。

## 5. 分析要件

- `discard_fact_*.csv` と `hanchan_master.csv` から、プレイヤーごとのシャンテン数と思考時間の相関を集計できること。
- 分析結果にはプレイヤー名、サンプル数、シャンテン別中央値、相関、ばらつき、所属卓を含める。
- 所属卓は `hanchan_master` の座席名と `room_class_label` から集計し、discard row 側の卓種は fallback として扱う。
- 出力は CSV / HTML / PNG を `reports/player_shanten_thinking/` 以下へ保存する。

## 6. データ要件

- `hanchan_master` は半荘単位の卓種、プレイヤー名、source URL を保持する。
- `discard_fact_YYYYMM` は打牌、思考時間、シャンテン、危険度、pystyle top3、agari snapshot を月別に保持する。
- 古い CSV から読める legacy 列は必要に応じて補完するが、現行保存は `room_class_label` を正本とする。

## 7. 運用要件

- 仕様変更時は `docs/requirements/current.md`, `docs/specs/current.md`, `docs/screen_specs/current.md`, `docs/changelog.md` を同期する。
- 画面表示の変更は `docs/screen_specs/*.md` へ、DB分析の変更は `docs/analysis/*.md` へ反映する。
- Push 前提、Remain 閾値、NAGA 自動表示、河描画 cache はテストで固定する。
