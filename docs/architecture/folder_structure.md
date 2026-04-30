# フォルダ構成ガイド

この文書は「どの情報をどこへ置くか」の正本です。特に `docs/` は役割で分け、麻雀ロジック、実装連携、構成説明、参照資料、運用メモを混ぜないことを原則にします。

```text
tenhou_hojo/
├─ assets/
├─ cli/
├─ csv_db/
├─ logs/
├─ analysis_output/
├─ docs/
│  ├─ README.md
│  ├─ architecture/
│  │  ├─ README.md
│  │  ├─ context.md
│  │  ├─ folder_structure.md
│  │  ├─ project_guide.md
│  │  ├─ source_overview.md
│  │  └─ src_call_graph.md
│  ├─ mahjong/
│  │  ├─ README.md
│  │  ├─ comparison_trace_reading_engine.md
│  │  ├─ hand_analysis.md
│  │  ├─ hand_analysis_terms.md
│  │  ├─ mahjong_call_rules.md
│  │  ├─ mahjong_danger.md
│  │  ├─ mahjong_rule.md
│  │  └─ opponent_tenpai_readiness.md
│  ├─ integrations/
│  │  ├─ README.md
│  │  ├─ packet_capture.md
│  │  ├─ pystyle_simulator_protocol.md
│  │  └─ tenhou_ui_bridge.md
│  ├─ reference/
│  │  ├─ README.md
│  │  ├─ csv_db_design.md
│  │  ├─ shanten_columns.md
│  │  ├─ tile_id_reference.md
│  │  └─ tile_representation.md
│  ├─ operations/
│  │  ├─ README.md
│  │  ├─ rollback_log.md
│  │  └─ troubleshooting/
│  │     └─ live_capture.md
│  ├─ analysis/
│  ├─ graphs/
│  ├─ requirements/
│  ├─ screen_specs/
│  ├─ specs/
│  ├─ templates/
│  └─ changelog.md
├─ extension/
├─ tmp_web/
├─ src/
│  ├─ app/
│  ├─ capture/
│  ├─ logic/
│  ├─ ui/
│  └─ old/
├─ tests/
├─ template_workspace/
└─ README.md
```

## docs 配置方針
- `docs/architecture/`: プロジェクト全体の構成、責務分離、呼び出し関係、保守ルール
- `docs/mahjong/`: 麻雀用語、ルール、危険度、読みロジックなどの非 UI 麻雀知識
- `docs/integrations/`: 外部サイト、外部 UI、packet capture、bridge など実装連携の説明
- `docs/reference/`: 牌 ID、DB 列、固定用語のような静的参照資料
- `docs/operations/`: トラブルシュート、復旧手順、rollback メモ
- `docs/analysis/`: DB 分析や検証用の補助文書
- `docs/requirements/`, `docs/specs/`, `docs/screen_specs/`: 版管理された正式仕様

## src 配置方針
- `src/app/`: 起動分岐、mock 選択、ウィンドウ設定、AI 連携、Tenhou UI Bridge transport
- `src/capture/`: live `tshark`、`.pcapng` replay、HTML/XML 断片解析、面子デコード、state 更新、CSV DB 保存
- `src/logic/`: 実コードとしての麻雀判断ロジック
- `src/ui/`: 卓面描画、牌画像、layout tuning、detail UI
- `src/old/`: 廃止予定または旧試作

## 代表ファイル
- `docs/README.md`: docs 全体の入口
- `docs/architecture/project_guide.md`: 全体像と主要データ構造
- `docs/architecture/source_overview.md`: `src/` の責務一覧
- `docs/architecture/src_call_graph.md`: 関数 / モジュールの主経路
- `docs/mahjong/mahjong_danger.md`: 危険度ロジックの正本
- `docs/mahjong/hand_analysis.md`: シャンテン / 待ち牌ロジックの正本
- `docs/integrations/packet_capture.md`: packet capture / parser 契約の説明
- `docs/integrations/tenhou_ui_bridge.md`: local app と Chrome Extension の責務分離
- `docs/reference/csv_db_design.md`: CSV DB schema と列説明
- `docs/operations/troubleshooting/live_capture.md`: live capture の復旧手順

## 保守ルール
- 新規文書を追加するときは、まず置き場所を `architecture / mahjong / integrations / reference / operations / analysis` のどれに属するかで決める
- 1 つの文書に「麻雀ルール」と「外部連携仕様」を混在させない
- `src/` の主要構成や import 経路が変わったら `source_overview.md` と `src_call_graph.md` も更新する
- Bridge や capture などの接続点が変わったら `docs/integrations/` の該当文書を更新する
- 牌 ID、DB 列、固定ラベルなどの静的説明は `docs/reference/` に寄せる

## 2026-04-11 Reorganization Addendum
- 旧 `docs/logic/` は廃止し、麻雀ロジックは `docs/mahjong/`、外部連携や UI 実行ブリッジは `docs/integrations/` へ分離した
- 旧 docs 直下に散っていた構成説明は `docs/architecture/`、静的参照は `docs/reference/`、運用メモは `docs/operations/` へ移した
- 今後は「どの情報をどの責務で保守するか」を先に決めてから新規文書を足す
