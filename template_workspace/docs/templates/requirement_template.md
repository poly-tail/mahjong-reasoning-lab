# 要件定義書テンプレート

## 1. 文書の位置づけ
- 本版が継承する前版: `requirements_v***.md`
- current pointer: `docs/requirements/current.md`
- 今回の改定対象: `*** workflow`, `*** screen`, `*** persistence`
- 今回触らない範囲: `login`, `billing`, `legacy import`
- 旧版の扱い: 旧版は残し、`current.md` だけ最新を向ける

## 2. 改定の主目的
- 目的 1: `***` 操作を `N step` から `M step` へ短縮する
- 目的 2: `***` 情報の保存粒度を `row` 単位まで上げる
- 目的 3: `*** panel` の視認性と再利用性を両立する

## 3. 機能要件
- **REQ-FUNC-01**: `*** input` を受けたら `*** result` を `1 action` で返せること
- **REQ-FUNC-02**: `*** state` 変更時に `*** panel` が再描画されること
- **REQ-FUNC-03**: `*** export` 実行時に `csv / json / log` のいずれかを選べること

## 4. 画面 / UX 要件
- **REQ-GUI-01**: `*** BUTTON` は `top-right / left-toolbar / context menu` のいずれかに固定表示すること
- **REQ-GUI-02**: `*** PANEL` は `open / close / reset / save` の操作結果が即時に見えること

## 5. データ要件
- **REQ-DATA-01**: `***_fact` は `***_id`, `source_kind`, `captured_at` を持つこと
- **REQ-DATA-02**: `legacy_***` を読む場合でも現行 schema に正規化して保存すること

## 6. 運用要件
- **REQ-OPS-01**: `docs/changelog.md` と `docs/***/current.md` を同時更新すること
- **REQ-OPS-02**: `*** failure` 発生時の暫定回避を `docs/troubleshooting/***_***.md` に残すこと

## 7. 非機能要件
- **NFR-MAINT-01**: `*** logic` は `module_***.py` 単位で責務分離すること
- **NFR-QUALITY-01**: `*** validation` が失敗した行でも全体処理を止めず `warning` で継続できること

## 8. 制約と前提
- 制約: `Tkinter / CSV / local file only`, `network optional`, `legacy header coexistence`
- 前提: `project_root/docs/`, `project_root/src/`, `project_root/tests/` が存在する

## 9. 関連文書
- 最新仕様書: `docs/specs/current.md`
- 最新画面仕様書: `docs/screen_specs/current.md`
- current 管理: `docs/requirements/current.md`
- troubleshooting: `docs/troubleshooting/***_***.md`
- 変更履歴: `docs/changelog.md`

## 10. 文書管理メモ
- 版上げ時に更新する `current.md`: `docs/requirements/current.md`
- 旧版として残す要件書: `docs/requirements/requirements_v***.md`
- 関連仕様の版上げ要否: `API`, `screen spec`, `project guide` を確認する
