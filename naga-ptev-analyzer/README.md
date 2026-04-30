# NAGA ptEV Analyzer

NAGAの段位ポイントアナライザを、自分のログイン済みブラウザセッションで照会・保存・分析するためのローカルツールです。

このツールは認証回避をしません。通常のブラウザで自分のアカウントにログインし、Playwright の `storage_state` を `.secrets/` に保存して、そのセッションを再利用します。

## できること

- Playwrightで手動ログインし、ローカルに `storage_state` を保存する
- NAGA段位ポイントアナライザのページを開き、照会エンドポイントとレスポンス形状を確認する
- 指定した局面を問い合わせ、raw JSONを保存する
- base / ron / tsumo / ryukyoku の分岐を型付きモデルへ変換する
- 順位確率から段位ptEVを計算する
- CSVへ出力する
- 入力局面サンプルを生成し、順位確率近似モデル用データセットを収集する
- 学習用CSVを作成し、簡易モデルを学習・評価・可視化する
- CLIまたはStreamlitで結果を確認する

## 注意事項

- 自分のログイン済みセッションだけを使ってください
- 認証回避、制限回避、CAPTCHA回避、第三者アカウント利用はしないでください
- 無制御な大量アクセスは禁止です
- 収集時は `--limit` を付け、`--sleep-sec` は1秒以上にしてください
- HTTP 403 / 429 / 5xx、またはJSON statusの 403 / 429 / 5xx 相当が出た場合、収集は即停止します
- `.secrets/`、`storage_state`、cookie、CSRF、`.env`、raw JSONはGit管理しないでください
- CLIはcookie、CSRF、Windows資格情報、`storage_state` の中身を標準出力へ出しません
- `out/raw/` は個人の解析レスポンスを含むため、基本的に非公開データとして扱ってください

## セットアップ

リポジトリ直下から実行する場合:

```powershell
cd naga-ptev-analyzer
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
python -m playwright install chromium
```

ワークスペース直下から実行する場合は、`PYTHONPATH` を指定しても動かせます。

```powershell
$env:PYTHONPATH="$PWD\naga-ptev-analyzer\src"
python -m naga_ptev.cli --help
```

## 初回ログイン

```powershell
python -m naga_ptev.cli login --storage .secrets/naga_state.json
```

ブラウザが表示されます。通常どおりログインし、NAGA段位ポイントアナライザのページが使えることを確認してから、ターミナルへ戻ってEnterを押してください。

保存先:

- `.secrets/naga_state.json`

`.secrets/` はGit管理しないでください。

## Windows資格情報へログイン情報を保存する場合

平文 `.env` を避けたい場合は、OSの資格情報ストアに保存できます。

```powershell
python -m naga_ptev.cli store-login
```

保存状態の確認:

```powershell
python -m naga_ptev.cli login-status
```

保存した資格情報の削除:

```powershell
python -m naga_ptev.cli clear-login
```

資格情報が保存されている場合、`storage_state` が存在しない時や期限切れの時に自動ログインを試みます。ただし、追加認証や確認が出た場合は自動では突破しません。その場合は再度 `login` を実行して、開いたブラウザで手動確認してください。

## `.env` を使う場合

ローカル `.env` に以下を置くこともできます。

```text
NAGA_NICONICO_MAIL_TEL=your_niconico_mail_or_tel
NAGA_NICONICO_PASSWORD=your_niconico_password
```

`.env` は絶対にGit管理しないでください。読み込み順は以下です。

1. プロセス環境変数
2. OS資格情報ストア
3. カレントディレクトリ、ワークスペース、`storage_state` 付近の `.env`

## 単発照会

### Probe

ログイン状態、エンドポイント候補、レスポンス取得状況を確認します。

```powershell
python -m naga_ptev.cli probe --storage .secrets/naga_state.json --kyoku 2 --honba 0 --kyotaku 0 --scores 250,250,250,250
```

出力にはCSRF値そのものは出さず、見つかったかどうかだけを表示します。

### Query

指定局面を問い合わせてraw JSONを保存します。

```powershell
python -m naga_ptev.cli query --storage .secrets/naga_state.json --kyoku 2 --honba 0 --kyotaku 0 --scores 250,250,250,250 --out out/raw/sample.json
```

自動保存分も `out/raw/` に残ります。

### Analyze

問い合わせ結果をパースし、CSVへ出力します。

```powershell
python -m naga_ptev.cli analyze --storage .secrets/naga_state.json --kyoku 2 --honba 0 --kyotaku 0 --scores 250,250,250,250 --out out/csv/analysis.csv
```

処理内容:

1. 指定局面を問い合わせる
2. base / ron / tsumo / ryukyoku をパースする
3. 順位確率とptEVを計算する
4. CSVへ保存する
5. コンソールに概要を表示する

### 供託+1比較

```powershell
python -m naga_ptev.cli compare-kyotaku --storage .secrets/naga_state.json --kyoku 2 --honba 0 --kyotaku 0 --scores 250,250,250,250 --add 1 --out out/csv/compare_kyotaku.csv
```

現在局面と `kyotaku + add` の局面をそれぞれ問い合わせ、順位確率とptEVの差をCSVに保存します。

## データ収集とモデル作成

順位確率近似モデルを作るための実行手順です。最初は必ず少量で試してください。

### 1. 入力局面サンプルCSVを作成する

ここではまだNAGAへ問い合わせません。段位ポイントアナライザに投げる入力局面の一覧CSVだけを作ります。

例: 境界重点の入力局面を1000件作る。

```powershell
python -m naga_ptev.cli generate-samples --method boundary --limit 1000 --out out/samples/boundary.csv
```

指定できる `--method`:

- `grid`: 基本的な格子サンプル
- `random`: ランダムサンプル
- `boundary`: 1着/2着、3着/4着などの順位境界を厚くしたサンプル
- `south_round_boundary`: 南場、特に南2・南3を厚くしたサンプル。南4は対象外
- `kyotaku_comparison`: 供託+1の影響を見るためのサンプル

出力CSVには `KyokuState` の一覧が保存されます。基本対象は東1〜南3、つまり `kyoku=0..6` です。南4/オーラスの `kyoku=7` は生成しません。スコアはseat順を保持し、勝手にソートしません。

### 2. NAGAへ問い合わせてデータを取得する

ここで実際に、作成済みの入力局面CSVをもとにNAGA段位ポイントアナライザへ順次問い合わせます。

最初は必ず少量で試してください。例: 100件だけ問い合わせて保存する。

```powershell
python -m naga_ptev.cli collect-dataset --samples out/samples/boundary.csv --storage .secrets/naga_state.json --sleep-sec 1.2 --limit 100 --resume
```

取得結果の出力:

- 収集状態DB: `out/collector.sqlite`
- 成功raw JSON: `out/raw/{state_hash}.json`
- 失敗ログJSON: `out/raw/{state_hash}.error.json`

重要なオプション:

- `--resume`: 既存DBを使って中断再開する
- `--limit`: 今回の最大取得件数
- `--sleep-sec`: リクエスト間隔。1.0未満を指定しても内部で1.0以上に補正します

収集器は `state_hash` で重複排除します。既に成功済みの局面は再問い合わせしません。HTTP 403 / 429 / 5xx、またはJSON statusの 403 / 429 / 5xx 相当が返った場合は、その時点で即停止します。

### 3. 中断した問い合わせ収集を再開する

前回の続きから、未取得または失敗扱いの局面をさらに100件問い合わせる例です。

```powershell
python -m naga_ptev.cli collect-dataset --samples out/samples/boundary.csv --storage .secrets/naga_state.json --sleep-sec 1.2 --limit 100 --resume
```

`out/collector.sqlite` の `states` テーブルで `success` になっている局面はスキップされます。つまり、同じ `state_hash` の局面を成功後に再問い合わせしないための再開コマンドです。

### 4. 学習用データセットを作る

```powershell
python -m naga_ptev.cli build-dataset --db out/collector.sqlite --out out/dataset/base_predictions.csv
```

出力:

- `out/dataset/base_predictions.csv`
- `out/dataset/branch_predictions.csv`

1レコードは「局面 × seat」です。目的変数は以下です。

- `p1`
- `p2`
- `p3`
- `p4`
- `ptev_default`

`ptev_default` は順位点 `[75, 30, 0, -105]` と順位確率の内積です。

### 5. モデルを学習する

例: HistGradientBoostingで学習する。

```powershell
python -m naga_ptev.cli train-model --dataset out/dataset/base_predictions.csv --model histgb --out artifacts/models/
```

指定できる `--model`:

- `histgb`
- `rf`
- `ridge`
- `lightgbm`

`lightgbm` はLightGBMがインストール済みの場合だけ使えます。`ridge` は `scikit-learn` がない環境でも簡易numpy実装へフォールバックします。

出力:

- `artifacts/models/model.pkl`
- `artifacts/models/feature_columns.json`

予測後の順位確率は0未満をclipし、合計が1になるように正規化します。ptEVは正規化後の順位確率から再計算します。

### 6. モデルを評価する

```powershell
python -m naga_ptev.cli evaluate-model --dataset out/dataset/base_predictions.csv --model artifacts/models/model.pkl --out out/eval/
```

出力:

- `out/eval/metrics.json`
- `out/eval/errors.csv`

評価指標:

- `MAE p1`
- `MAE p2`
- `MAE p3`
- `MAE p4`
- `max error p1` から `p4`
- `ptEV MAE`
- `ptEV max error`
- kyoku別エラー
- current_rank別エラー
- score gap bucket別エラー
- rank boundary付近のエラー

分割方法を変える場合:

```powershell
python -m naga_ptev.cli evaluate-model --dataset out/dataset/base_predictions.csv --model artifacts/models/model.pkl --out out/eval/ --split kyoku_holdout
```

指定できる `--split`:

- `random`
- `kyoku_holdout`
- `south_round_holdout`

### 7. グラフを作る

```powershell
python -m naga_ptev.cli plot-model --dataset out/dataset/base_predictions.csv --pred out/eval/errors.csv --out out/plots/
```

保存先:

- `out/plots/`

グラフ内の文字は英語です。作成されるグラフ:

- `gap_to_1st` vs `p1` by `kyoku`
- `gap_to_4th` vs `p4` by `kyoku`
- actual vs predicted ptEV
- residual heatmap by kyoku and score gap bucket
- ptEV curve by current rank
- kyotaku effect curve
- honba effect curve
- oorasu condition curve

## 推奨実行順

初回の小規模確認:

```powershell
cd naga-ptev-analyzer
.\.venv\Scripts\activate

python -m naga_ptev.cli login --storage .secrets/naga_state.json
python -m naga_ptev.cli generate-samples --method boundary --limit 100 --out out/samples/boundary_100.csv
python -m naga_ptev.cli collect-dataset --samples out/samples/boundary_100.csv --storage .secrets/naga_state.json --sleep-sec 1.2 --limit 100 --resume
python -m naga_ptev.cli build-dataset --db out/collector.sqlite --out out/dataset/base_predictions.csv
python -m naga_ptev.cli train-model --dataset out/dataset/base_predictions.csv --model ridge --out artifacts/models/
python -m naga_ptev.cli evaluate-model --dataset out/dataset/base_predictions.csv --model artifacts/models/model.pkl --out out/eval/
python -m naga_ptev.cli plot-model --dataset out/dataset/base_predictions.csv --pred out/eval/errors.csv --out out/plots/
```

問題がなければ、`generate-samples --limit` と `collect-dataset --limit` を少しずつ増やしてください。

## Streamlit UI

```powershell
python -m naga_ptev.cli ui
```

または:

```powershell
python -m streamlit run src/naga_ptev/ui_streamlit.py
```

UIで確認できるもの:

- kyoku / honba / kyotaku / scores 入力
- 順位点設定
- baseline ptEV と順位確率
- ron / tsumo / ryukyoku テーブル
- 3900直撃候補
- 満貫ツモ候補
- 供託+1比較
- CSVダウンロード
- Plotlyグラフ

## テスト

```powershell
pytest
```

ワークスペース直下からNAGA関連だけ確認する場合:

```powershell
$env:PYTHONPATH="$PWD\naga-ptev-analyzer\src"
python -m pytest naga-ptev-analyzer\tests
```

## Windowsメモ

インストール後にWindows側のポリシーでパッケージDLLがブロックされた場合は、対象パッケージを unblock してから再実行してください。

```powershell
Get-ChildItem -Path "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\Lib\site-packages\pandas" -Recurse -File | Unblock-File
```
