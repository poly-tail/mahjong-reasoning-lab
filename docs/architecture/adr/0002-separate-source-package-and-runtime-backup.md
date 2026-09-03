# ADR-0002: source配布ZIPとruntime backupを分離する

## Status

Accepted

## Context

`scripts/package_workspace.py` は workspace 全体を列挙してZIP化していたため、source配布に `logs/`、`csv_db/`、既存ZIP、pcap、TLS keylog、Cookie state などの runtime data や秘密情報が混入する可能性があった。

## Decision

既定profileを `source` とし、秘密情報、runtime data、ログ、CSV DB、分析出力、pcap、keylog、browser state、Python cache、既存ZIPを除外する。`runtime-backup` は明示指定された workspace 内 path だけを対象にし、秘密情報は常に拒否する。

## Alternatives considered

- 既存の全workspace ZIPを維持する: 秘密情報とruntime dataの混入リスクが高いため不採用。
- runtime backupにも自動で `csv_db/` や `logs/` を含める: 明示性が低いため不採用。

## Consequences

source配布は安全側になる。runtime backupが必要な場合は、含めたいpathを明示する必要がある。

## Compatibility

既定の実行コマンドは引き続きZIPを作成するが、内容はsource配布用に限定される。実データは削除・移動しない。

## Reconsideration conditions

配布要件としてruntime data同梱が必要になった場合。ただし秘密情報は引き続き除外する。

## Related tests

- `tests/test_package_workspace.py`

## Related documents

- `scripts/package_workspace.py`
- `docs/operations/regression_checklist.md`
- `docs/changelog.md`
