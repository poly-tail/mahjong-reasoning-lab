param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "python command not found. Install Python or run the graph command from another environment."
}

& $python.Source (Join-Path $repoRoot "scripts/render_docs_graphs.py") @Args
exit $LASTEXITCODE
