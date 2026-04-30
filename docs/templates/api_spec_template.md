# 仕様書テンプレート

## 1. 文書の位置づけ
- 前版: `api_spec_v***.md`
- current pointer: `docs/specs/current.md`
- 今回の対象モジュール: `src/***/service_***.py`, `src/***/repository_***.py`, `src/***/schema_***.py`
- 非対象: `src/ui/***`, `tests/e2e/***`, `external_api/***`
- 旧版の扱い: `api_spec_v***.md` は残し、`current.md` の pointer と要約だけ更新する

## 2. 対象モジュール
| コンポーネント | 役割 | 主な責務 |
|----------------|------|----------|
| `src/***/service_***.py` | `***` ユースケースの主処理 | 入力正規化、業務ルール適用、返却 DTO 組み立て |
| `src/***/repository_***.py` | 永続化境界 | `***` 取得、`***` 保存、重複排除 |
| `src/***/schema_***.py` | 入出力 schema | request / response の shape 固定、型変換、validation |

## 3. データ構造
- 構造体 / dataclass / schema: `***Request`, `***Response`, `***Record`, `***Config`
- 主キー / 識別子: `***_id`, `version`, `source_kind`
- 派生値: `normalized_***`, `display_***`, `summary_***`

## 4. 主要 API / 関数契約
- `load_***_config()`: `json / yaml / csv` から `***Config` を構築し、不正値は fallback する
- `build_***_request()`: UI / CLI 入力を API 用 request schema へ正規化する
- `execute_***()`: `***Request` を受け、保存や描画へ渡す `***Response` を返す

## 5. 処理フロー
1. `src/***/service_***.py` が `*** input` を受ける
2. `src/***/schema_***.py` で `***Request` へ正規化する
3. `src/***/service_***.py` が `repository_***` と `rule_***` を呼ぶ
4. `***Response` を返し、必要なら `csv / json / ui state` へ反映する

## 6. 永続化 / 入出力仕様
- 保存先: `csv_db/***_***.csv`, `logs/***_***.log`, `analysis_output/***/`
- 入力形式: `CLI args`, `JSON payload`, `captured state`, `manual config`
- 出力形式: `***Response`, `CSV row`, `UI panel payload`
- fallback / error 時の扱い: `blank`, `default value`, `warning log`, `skip row`

## 7. 画面 / renderer 連携
- 画面要素: `*** PANEL`, `*** BUTTON`, `*** DETAIL WINDOW`
- 即時反映: `slider change`, `button toggle`, `auto refresh`
- 保存タイミング: `Save`, `window close`, `background sync completion`

## 8. 互換性
- legacy 名称: `legacy_***`, `*_after_discard`, `old_***_json`
- migration: `header rewrite`, `field rename`, `fallback conversion`
- 後方互換: 旧列読込は許容し、新列で再書き込みする

## 9. 関連文書
- 最新要件定義: `docs/requirements/current.md`
- 最新画面仕様: `docs/screen_specs/current.md`
- current 管理: `docs/specs/current.md`
- 関数 graph: `docs/architecture/src_call_graph.md`
- troubleshooting: `docs/operations/troubleshooting/***_***.md`
- 変更履歴: `docs/changelog.md`

## 10. 文書管理メモ
- 版上げ時に更新する `current.md`: `docs/specs/current.md`
- 旧版として残す文書: `docs/specs/api_spec_v***.md`
- graph 更新要否: `service_***` の呼び出し方向が変わったら `Yes`
- troubleshooting へ追記する運用変更: `timeout 増加`, `fallback 追加`, `manual retry 手順`
