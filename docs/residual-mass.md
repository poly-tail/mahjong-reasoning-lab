# 未配分確率

choice group の候補確率合計が100%未満のとき、その差分を「未配分確率」として扱います。

未配分は単なる入力ミスではありません。まだ候補化していない読み、例外パターン、観測ノイズ、未知バッファを表す情報です。

## raw と normalized

- `raw_probability`: 入力時点の候補確率です。候補合計が85%なら85%のまま保持します。
- `normalized_probability`: 既存候補だけで比較するための計算用正規化です。55/20/10なら64.7/23.5/11.8になります。

自動で100%へ按分すると、読み不足や例外の存在を隠します。そのため、既存候補への按分はユーザーが明示的に「既存候補に按分」を選んだときだけ行います。

## 扱い

Quick Reading では未配分を次のどれかとして選びます。

- 具体候補を提案する
- 例外集に入れる
- 未知バッファとして保持する
- 既存候補へ按分する
- いったん未配分のまま残す

デフォルトは未知バッファです。未知バッファは候補正規化には入れず、UIとノード上に残します。

## 警告

- 5%超: info
- 15%以上: warning
- 25%以上: hard prune warning
- 未配分がある状態で `hard_prune` を選ぶ: warning

表示コピー:

> 未配分確率が残っています。これは未想起候補・例外・観測ノイズ・未知を含む可能性があります。hard pruneではなくkeep top-k/downweightを検討してください。

## 実装

Domain logic は `src/domain/residualMass.ts` にあります。

永続化は既存 schema v4 のノードフィールドで行います。

- 未知バッファ: `type: ambiguity_marker`
- 例外候補: `type: exception`
- tags: `residual_mass`, `unknown_buffer`, `exception`, `reading_drawer`
- pruning hints: `must_keep_top_k`

`reading_utilities` には後方互換の default 付きで次を追加しています。

- `residual_mass_before`
- `residual_mass_after`
- `residual_reduction`
- `exception_candidates_added`
- `unknown_buffer_remaining`
