# src 呼び出し関係テンプレート

Mermaid 正本と生成物の管理ルールを書く文書。

## 正本
- `docs/graphs/src/graph_***_flow.mmd`
- `docs/graphs/src/graph_***_dependency.mmd`

## 生成物
- `docs/graphs/generated/graph_***_flow.svg`
- `docs/graphs/generated/graph_***_dependency.svg`

## 生成コマンド
```powershell
./cli/render_docs_graphs.ps1
```

## graph 一覧
| graph | 目的 | 更新トリガー |
|-------|------|--------------|
| `graph_***_flow` | `input -> normalize -> save` の主経路を示す | `service_***` の呼び出し先変更 |
| `graph_***_dependency` | `module_***.py` 間の依存方向を示す | package 分割、責務移動、import 変更 |

## 更新ルール
- 主要フロー、責務分割、依存方向が変わったら Mermaid 正本を更新する
- Mermaid 更新後は生成物も再生成する
- `docs/architecture/source_overview.md` と説明がズレないように保つ
