# Troubleshooting Note Template

## 1. 事象
- 症状: `*** BUTTON` を押すと `*** panel` が空になる
- 影響範囲: `live capture`, `mock mode`, `csv export`
- 発生日: `20**-**-**`

## 2. 前提 / 再現条件
- 環境: `Windows **`, `Python 3.**`, `csv_db schema v***`
- 入力条件: `***_fact_YYYYMM.csv` に `legacy_***` header が混在
- 再現手順: `1. app 起動 -> 2. *** load -> 3. *** button click`

## 3. 原因候補
- 仮説 1: `module_***.py` が `blank` を `None` として扱っている
- 仮説 2: `renderer_***.py` の overlap clamp が `*** rect` を潰している

## 4. 切り分け手順
1. `logs/***_***.log` と `csv_db/***_fact_YYYYMM.csv` を確認する
2. `tests/fixtures/***` で再現条件を固定する
3. 暫定回避の有効性を `mock / live / replay` で確認する

## 5. 暫定回避
- 回避策: `legacy_***` を `current schema` へ migration 後に再起動する
- 残る制約: `*** panel` は復旧するが `*** memo` は再入力が必要

## 6. 恒久対応
- 修正方針: `storage_***.py` に fallback migration を追加し、`renderer_***.py` の clamp を見直す
- 追従更新する文書: `docs/specs/api_spec_v***.md`, `docs/source_overview.md`, `docs/changelog.md`

## 7. 関連文書
- requirements / specs / screen specs: `docs/requirements/current.md`, `docs/specs/current.md`, `docs/screen_specs/current.md`
- changelog: `docs/changelog.md`
- 関連 issue / ticket: `issue_***`, `ticket_***`
