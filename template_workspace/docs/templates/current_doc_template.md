# 文書 Current テンプレート

> 現在版の例: `requirements_v1.7.md`, `api_spec_v2.1.md`, `screen_spec_v***.md`

## 役割
- このファイルは最新 pointer と要約だけを置く
- 全文の正本は versioned file に置く
- 旧版ファイルは削除せず残す

## 概要
- 文書種別: `requirements` / `specs` / `screen_specs`
- 現在版: `requirements_v***.md`
- 施行日: `20**-**-**`
- 前版: `requirements_v***.md`
- 変更理由: `*** flow 追加`, `*** column 変更`, `*** UI 整理`

## 主な内容
- 現在版の要点 1: `***` を `***` として定義し直した
- 現在版の要点 2: `*** screen` と `*** API` の対応を追加した

## version history
| version | file | date | summary |
|---------|------|------|---------|
| v1.0 | `document_v1.0.md` | `20**-**-**` | 初版 |
| v1.1 | `document_v1.1.md` | `20**-**-**` | `*** field` 追加 |
| v*** | `document_v***.md` | `20**-**-**` | `*** behavior` 更新 |

## 更新ルール
1. 新版の versioned file を `document_v***.md` として追加する
2. この `current.md` を最新 file 名へ差し替える
3. 関連する `current.md` と `docs/changelog.md` を更新する
4. 旧版の行は history へ残す
