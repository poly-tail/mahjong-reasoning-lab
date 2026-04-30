# GitHub upload and push

このメモは、現在のローカル Git リポジトリを GitHub の非公開リポジトリへアップロードし、その後の変更を push するための手順です。

## 初回だけ必要な手順

GitHub CLI にログインします。

```powershell
gh auth login
```

選択肢は通常、以下で問題ありません。

```text
GitHub.com
HTTPS
Login with a web browser
```

ログイン後、GitHub に private リポジトリを作成して、現在のローカルリポジトリを push します。

```powershell
gh repo create tenhou_hojo --private --source . --remote origin --push
```

`--private` は GitHub 上にリポジトリを作る初回だけ指定します。次回以降の `git push` では不要です。

## 次回以降の更新手順

変更状況を確認します。

```powershell
git status
```

変更をステージします。

```powershell
git add -A
```

コミットします。

```powershell
git commit -m "変更内容を書く"
```

GitHub に push します。

```powershell
git push
```

## リモート設定の確認

初回 push 後に、`origin` が設定されているか確認できます。

```powershell
git remote -v
```

`origin  https://github.com/.../tenhou_hojo.git` のように表示されれば、次回以降は通常の `git push` で同じ private リポジトリへ送信されます。

