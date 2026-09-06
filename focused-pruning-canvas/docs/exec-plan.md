# 実行計画

## 目的

spec.md の単一Board試作を実装し、acceptance.md のA/B/Cを検証する。

## 現状

独立した focused-pruning-canvas に実装済み。既存アプリと未コミットの .prettierignore は保全。最終check、34 unit/component、8 Chromium E2Eが成功。スクリーンショットを両サイズで目視確認済み。

## 作業項目と状態

- M1 完了：環境、参照、常設ルール、仕様、依存、コマンド、独立配置用CI。
- M2 完了：schema、参照検証、三値論理、同根集約、計算、seed、台帳、差分、原文一致とunit test。
- M3 完了：CRUD、Note階層、履歴、保存、入出力。限界サイズの往復・容量短縮を含む検証。
- M4 完了：一画面UI、Canvas、Inspector、Outline、Timeline、keyboard、保存エラーと復旧。
- M5 完了：34 unit/component、8 E2E、1440/1280画像、README、自己レビューと修正。未確認環境は下記に分離。

## 決定事項

純粋なdomain、flat snapshot/cursor、確定時の同期保存。詳細はdesign-decisions.mdを参照。仕様の計算・seed・制約は削減していない。初回実装時は既存アプリへの変更、公開、push、commitを実施していない。その後の依頼で親READMEの冒頭にも起動方法を追加。2026-09-07の依頼に基づき、試作アプリとREADMEを既存リモートのmainへコミット・pushする。以前からある親の `.prettierignore` の変更は対象に含めない。

## 検証結果

Windows PowerShell / Node v22.19.0 / npm 11.5.2。check終了0、Playwright終了0。A01–A14・B01–B10・C01–C10の対応表はacceptance.md。失敗経緯と最終日時はverification.md。

## 阻害要因

実装を妨げる要因なし。実IMEの手入力、Linux実行、独立環境のnpm ci、GitHub CIは未検証。C06の自動試験は合成イベントであり、READMEの実IME手動確認を実行済みとは扱わない。親repoの入れ子workflowは自動実行されない。

## 再開時の最初の操作

AGENTS.md、spec.md、acceptance.md、本計画を読み、verification.mdの未確認項目を確認する。通常起動はこのフォルダでnpm start。拡張依頼がある場合は先に対象IDと受入条件を追加する。
