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
│  │  ├─ src_call_graph.md
│  │  └─ adr/
│  ├─ mahjong/
│  │  ├─ README.md
│  │  ├─ theory/
│  │  │  ├─ README.md
│  │  │  ├─ 01-block-theory.md
│  │  │  ├─ decision-flow.md
│  │  │  └─ glossary.md
│  │  ├─ logic/
│  │  │  ├─ README.md
│  │  │  ├─ hand_analysis.md
│  │  │  ├─ mahjong_danger.md
│  │  │  └─ opponent_tenpai_readiness.md
│  │  ├─ reference/
│  │  │  ├─ README.md
│  │  │  ├─ mahjong_rule.md
│  │  │  ├─ mahjong_call_rules.md
│  │  │  └─ hand_analysis_terms.md
│  │  └─ research/
│  │     ├─ README.md
│  │     └─ mahjong_research_full_v8.md
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
│  │  ├─ code_review.md
│  │  ├─ regression_checklist.md
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
  - `docs/architecture/adr/`: 互換性や責務境界に関わる設計判断
- `docs/mahjong/`: 麻雀ドメイン文書の親フォルダ
  - `docs/mahjong/theory/`: 牌効率、手組み、鳴き効率などの学習用セオリー
  - `docs/mahjong/logic/`: 実装に接続する危険度、シャンテン、読みなどの判断ロジック
  - `docs/mahjong/reference/`: ルール、鳴き可否、用語などの基礎参照
  - `docs/mahjong/research/`: 研究メモ、会話要約、仮説整理
- `docs/integrations/`: 外部サイト、外部 UI、packet capture、bridge など実装連携の説明
- `docs/reference/`: 牌 ID、DB 列、固定用語のような静的参照資料
- `docs/operations/`: トラブルシュート、復旧手順、rollback メモ
  - `docs/operations/regression_checklist.md`: capture / DB / UI / 配布を横断する回帰確認
  - `docs/operations/code_review.md`: review 観点、重大度、確度分類
- `docs/analysis/`: DB 分析や検証用の補助文書
- `docs/requirements/`, `docs/specs/`, `docs/screen_specs/`: 版管理された正式仕様

## src 配置方針
- `src/app/`: 起動分岐、mock 選択、ウィンドウ設定、AI 連携、Tenhou UI Bridge transport
- `src/capture/`: live `tshark`、`.pcapng` replay、HTML/XML 断片解析、面子デコード、state 更新、live base river store、CSV DB 保存
- `src/logic/`: 実コードとしての麻雀判断ロジック
- `src/ui/`: 卓面描画、牌画像、layout tuning、detail UI
- `src/old/`: 廃止予定または旧試作

## 代表ファイル
- `docs/README.md`: docs 全体の入口
- `docs/architecture/project_guide.md`: 全体像と主要データ構造
- `docs/architecture/source_overview.md`: `src/` の責務一覧
- `docs/architecture/src_call_graph.md`: 関数 / モジュールの主経路
- `docs/architecture/adr/README.md`: ADR の入口
- `docs/mahjong/theory/README.md`: 牌効率・手組み理論の入口
- `docs/mahjong/logic/mahjong_danger.md`: 危険度ロジックの正本
- `docs/mahjong/logic/hand_analysis.md`: シャンテン / 待ち牌ロジックの正本
- `docs/mahjong/reference/mahjong_call_rules.md`: 鳴き可否とラグ判定の正本
- `docs/mahjong/research/mahjong_research_full_v8.md`: 麻雀研究メモの最新版
- `docs/integrations/packet_capture.md`: packet capture / parser 契約の説明
- `docs/integrations/tenhou_ui_bridge.md`: local app と Chrome Extension の責務分離
- `docs/reference/csv_db_design.md`: CSV DB schema と列説明
- `docs/operations/troubleshooting/live_capture.md`: live capture の復旧手順
- `docs/operations/regression_checklist.md`: 横断回帰チェックリスト
- `docs/operations/code_review.md`: コードレビュー規則

## 保守ルール
- 新規文書を追加するときは、まず置き場所を `architecture / mahjong / integrations / reference / operations / analysis` のどれに属するかで決める
- `docs/mahjong/` に追加するときは、さらに `theory / logic / reference / research` のどれかに分類する
- 1 つの文書に「麻雀ルール」と「外部連携仕様」を混在させない
- `src/` の主要構成や import 経路が変わったら `source_overview.md` と `src_call_graph.md` も更新する
- Bridge や capture などの接続点が変わったら `docs/integrations/` の該当文書を更新する
- 牌 ID、DB 列、固定ラベルなどの静的説明は `docs/reference/` に寄せる

## 2026-04-11 Reorganization Addendum
- 旧 `docs/logic/` は廃止し、麻雀ロジックは `docs/mahjong/`、外部連携や UI 実行ブリッジは `docs/integrations/` へ分離した
- 旧 docs 直下に散っていた構成説明は `docs/architecture/`、静的参照は `docs/reference/`、運用メモは `docs/operations/` へ移した
- 今後は「どの情報をどの責務で保守するか」を先に決めてから新規文書を足す

## 2026-05-10 Mahjong Domain Addendum
- 旧 `docs/mahjong-theory/` は `docs/mahjong/theory/` へ移動し、麻雀ドメイン文書のトップ階層を `docs/mahjong/` に統一した
- 旧 `docs/mahjong/*.md` の直置き文書は、内容に応じて `logic/`、`reference/`、`research/` へ分割した
- `docs/mahjong/logic/` は実装正本、`docs/mahjong/theory/` は学習セオリー、`docs/mahjong/research/` は未昇格の研究メモとして扱う
