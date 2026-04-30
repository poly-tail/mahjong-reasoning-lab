# 変更履歴テンプレート

## 使い方
- addendum を追記型で追加し、旧記録は上書きしない
- versioned docs を追加したら `current.md` 更新も同じ addendum で残す
- graph 更新、troubleshooting 追記、運用変更も必要なら記録する
- docs のみの変更でも、管理ルールが変わるなら残す

## 20**-**-** Addendum
- `CH-***`: `*** panel` の挙動を更新し、`docs/screen_specs/screen_spec_v***.md` と `docs/specs/api_spec_v***.md` を追従更新した
- `CH-***`: `csv_db/***_fact_YYYYMM.csv` の `*** column` を追加し、migration を有効化した

| 日付 | 変更 ID | 種別 | 概要 | 実施者 | 影響ファイル |
|------|---------|------|------|--------|--------------|
| `20**-**-**` | `CH-***` | `docs` | `current.md` pointer 更新 | `name_***` | `docs/specs/current.md` |
| `20**-**-**` | `CH-***` | `feat` | `*** panel` 追加 | `name_***` | `src/ui/***_renderer.py` |
| `20**-**-**` | `CH-***` | `fix` | `legacy_***` migration 修正 | `name_***` | `src/***/storage_***.py` |
