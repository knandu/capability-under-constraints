$ErrorActionPreference = 'Stop'
$portable = Join-Path $PSScriptRoot '.runtime\python.exe'
if (Test-Path -LiteralPath $portable) {
    & $portable (Join-Path $PSScriptRoot 'harness.py') @args
} else {
    & python (Join-Path $PSScriptRoot 'harness.py') @args
}
exit $LASTEXITCODE
