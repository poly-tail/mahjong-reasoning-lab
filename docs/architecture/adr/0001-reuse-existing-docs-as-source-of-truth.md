# ADR-0001: 既存docsを正本として再利用する

## Status

Accepted

## Context

このリポジトリには `docs/README.md`、`docs/architecture/context.md`、`docs/changelog.md`、`docs/screen_specs/current.md`、`docs/integrations/packet_capture.md` などの正本文書が既に存在する。新しい管理文書を機械的に増やすと、仕様の重複と drift が起きる。

## Decision

Codex向け作業ルールはルート `AGENTS.md` に薄く置き、詳細仕様は既存正本文書へルーティングする。変更履歴は `docs/changelog.md` を正本として維持し、重複する `CHANGELOG_FOR_CODEX.md` は作成しない。

## Alternatives considered

- 新しいCodex専用の変更履歴を作る: 既存 `docs/changelog.md` と目的が重複するため不採用。
- `AGENTS.md` に全仕様を転記する: 仕様 drift を増やすため不採用。

## Consequences

作業開始時に読む文書は増えるが、仕様の正本が分散しにくい。

## Compatibility

既存docs構成、既存変更履歴、既存テスト運用を維持する。

## Reconsideration conditions

既存docsの責務分類が破綻し、正本文書を特定できなくなった場合。

## Related tests

なし。文書運用判断。

## Related documents

- `AGENTS.md`
- `docs/README.md`
- `docs/architecture/context.md`
- `docs/changelog.md`
