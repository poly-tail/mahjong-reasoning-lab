# 例外集

例外集は、未配分確率から出た例外候補を保存し、次回以降の候補提案に使うための補助パネルです。

UI は `src/ui/reading/ExceptionLibraryPanel.tsx` です。Quick Reading の未配分 UI と Case Workspace から開けます。

## 保存するもの

既存 schema に `exception` type があるため、新しい node type は追加しません。

例外ノードは次の形で保存します。

- `type: exception`
- `tags: ["exception", "residual_mass", "reading_drawer"]`
- `confidence`: 低めの初期値
- `posterior_probability` / `base_weight`: 未配分から割り当てた確率
- `pruning_hints: ["must_keep_top_k"]`

## 使い方

- この局面に追加: active case に attach します。
- 候補提案に使う: Quick Reading の候補群に candidate として戻します。
- 無効化: `disabled_exception` tag を付け、通常一覧から外します。

## 昇格と保留

例外を候補に昇格する条件:

- 同じ例外が複数ケースで繰り返し出る
- 4軸のどれに効くか説明できる
- default probability を置ける程度に再現性がある

未知バッファに残す条件:

- 観測ミス、記憶違い、河のノイズの可能性が強い
- 例外として命名すると過学習になりそう
- hard prune を避けるための注意情報として残せば十分

例外から新しい読みテンプレートを作る場合は、例外ノードの description を典型メモとして使い、reading drawer item か mapping template へ昇格します。
