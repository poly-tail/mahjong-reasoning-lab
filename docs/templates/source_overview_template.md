# ソースコード概要テンプレート

`src/` 配下の現行実装を、責務単位で整理する。

## パッケージ構成

| パス | 役割 | 更新時の注意 |
|---|---|---|
| `src/app/` | `***` ユースケースの入口 | CLI / GUI / batch の分岐が増えたら追記する |
| `src/domain/` | `***` の業務ルール | 値オブジェクトと service の責務境界を明記する |
| `src/infrastructure/` | `csv / json / external api` 接続 | 保存先や retry 方針が変わったら更新する |
| `src/shared/` | 共通 util, constants, error | 依存逆流が起きていないか確認する |
| `src/ui/` | `*** panel`, `*** renderer`, `*** window` | 画面 contract と docs のズレを避ける |

## 主要フロー
1. `src/app/***_entry.py` が入力を受ける
2. `src/***/normalizer_***.py` が shape をそろえる
3. `src/***/service_***.py` が主処理を実行する
4. `src/infrastructure/***` または `src/ui/***` が保存 / 出力する

## 正本の置き場
- 要件 / 仕様 / 画面仕様: `docs/requirements/current.md`, `docs/specs/current.md`, `docs/screen_specs/current.md`
- 永続化モデル: `src/capture/csv_db_schema.py`, `docs/reference/csv_db_design.md`
- graph: `docs/architecture/src_call_graph.md`, `docs/graphs/src/graph_***.mmd`
- troubleshooting: `docs/operations/troubleshooting/***_***.md`

## 更新ルール
- `src/***/module_***.py` を追加 / 削除 / 改名したらこの表を更新する
- 主要フローが変わったら `docs/architecture/src_call_graph.md` も更新する
- docs とコードで用語がズレたらここを正本に寄せる
