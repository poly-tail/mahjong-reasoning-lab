# フォルダ構成ガイドテンプレート

```text
project_root/
├─ assets/
│  ├─ samples/
│  │  └─ sample_***.png
│  └─ README.md
├─ cli/
│  ├─ render_docs_graphs.ps1
│  └─ run_***.ps1
├─ docs/
│  ├─ analysis/
│  │  └─ analysis_rule_***.md
│  ├─ graphs/
│  │  ├─ generated/
│  │  │  └─ graph_***.svg
│  │  └─ src/
│  │     └─ graph_***.mmd
│  ├─ requirements/
│  │  ├─ current.md
│  │  └─ requirements_v***.md
│  ├─ specs/
│  │  ├─ current.md
│  │  └─ api_spec_v***.md
│  ├─ screen_specs/
│  │  ├─ current.md
│  │  ├─ screen_spec_v***.md
│  │  ├─ screen_map.md
│  │  ├─ ui_principles.md
│  │  └─ invariants.md
│  ├─ templates/
│  │  ├─ requirement_template.md
│  │  ├─ api_spec_template.md
│  │  ├─ screen_spec_template.md
│  │  └─ troubleshooting_note_template.md
│  ├─ troubleshooting/
│  │  └─ issue_***.md
│  ├─ changelog.md
│  ├─ context.md
│  ├─ folder_structure.md
│  ├─ project_guide.md
│  ├─ source_overview.md
│  └─ src_call_graph.md
├─ logs/
│  └─ app_***.log
├─ src/
│  ├─ app/
│  │  └─ service_***.py
│  ├─ domain/
│  │  └─ rule_***.py
│  ├─ infrastructure/
│  │  └─ repository_***.py
│  ├─ shared/
│  │  └─ constants_***.py
│  └─ ui/
│     └─ renderer_***.py
├─ tests/
│  ├─ fixtures/
│  │  └─ sample_***.json
│  ├─ integration/
│  │  └─ test_***_flow.py
│  └─ unit/
│     └─ test_***_service.py
└─ analysis_output/
   └─ report_***.csv
```

## 役割
- `assets/`: `sample_***.png`, `fixture_***.json`, `mock_***.csv` などの静的入力
- `cli/`: graph 再生成、batch 実行、補助 export などの運用コマンド
- `docs/`: versioned docs と current pointer を含む管理文書の正本
- `docs/graphs/src/`: `graph_***.mmd` のような Mermaid 正本
- `docs/graphs/generated/`: `graph_***.svg` のような生成物
- `docs/operations/troubleshooting/`: `issue_***.md` 単位の障害記録、回避策、復旧手順
- `src/app/`: `service_***.py`, `entry_***.py` などのユースケース入口
- `src/domain/`: 業務ルール、値オブジェクト、判定ロジック
- `src/infrastructure/`: CSV / JSON / API / file system との接続
- `src/shared/`: 共通 util, constants, exceptions
- `src/ui/`: `renderer_***.py`, `window_***.py`, `panel_***.py` などの表示層
- `tests/`: `unit / integration / fixtures` に分けた検証コード
- `analysis_output/`: 一回限りの比較結果や集計 CSV

## 更新ルール
- 追加 / 削除 / 改名時: 例 `src/domain/rule_***.py` を追加したら tree と役割説明へ反映する
- docs 追従更新先: 例 `docs/architecture/source_overview.md`, `docs/architecture/project_guide.md`, `docs/architecture/folder_structure.md`
- graph 正本 / 生成物の更新要否: 例 `service_***.py` の依存先が変わったら `graph_***.mmd` と `graph_***.svg` を更新する
- `current.md` の更新要否: 例 `requirements_v***.md` や `screen_spec_v***.md` を追加したら対応する `current.md` の pointer を見直す
