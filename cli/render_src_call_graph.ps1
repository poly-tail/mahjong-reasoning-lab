param(
    [string]$InputDir = "docs/graphs/src",
    [string]$OutputDir = "docs/graphs/generated"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$inputPath = Join-Path $repoRoot $InputDir
$outputPath = Join-Path $repoRoot $OutputDir

if (-not (Test-Path $inputPath)) {
    throw "入力ディレクトリが見つかりません: $inputPath"
}

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

$graphFiles = Get-ChildItem -Path $inputPath -Filter *.mmd | Sort-Object Name
if (-not $graphFiles) {
    throw "Mermaid ソースが見つかりません: $inputPath"
}

foreach ($graphFile in $graphFiles) {
    $outputFile = Join-Path $outputPath ($graphFile.BaseName + ".svg")
    Write-Host "生成中 $($graphFile.Name) -> $outputFile"
    & npx.cmd -y @mermaid-js/mermaid-cli -i $graphFile.FullName -o $outputFile
    if ($LASTEXITCODE -ne 0) {
        throw "Mermaid 図の生成に失敗しました: $($graphFile.FullName)"
    }
}

Write-Host "$($graphFiles.Count) 件の図を $outputPath に生成しました"
