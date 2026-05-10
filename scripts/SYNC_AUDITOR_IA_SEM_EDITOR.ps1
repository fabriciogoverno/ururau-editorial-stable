param(
  [string]$RepoPath = "C:\Users\fabri\Downloads\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL"
)

$ErrorActionPreference = "Stop"

function Run-Git {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
  & git @Args
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Args -join ' ') falhou com codigo $LASTEXITCODE"
  }
}

if (!(Test-Path $RepoPath)) {
  throw "Repositorio local nao encontrado: $RepoPath"
}

Set-Location $RepoPath

# Nunca usar Vim por acidente.
Run-Git config --global core.editor "notepad"

Write-Host "Sincronizando main e auditor-ia sem abrir editor..." -ForegroundColor Cyan

Run-Git fetch origin
Run-Git checkout main
Run-Git pull origin main
Run-Git checkout auditor-ia
Run-Git pull origin auditor-ia
Run-Git merge main --no-edit
Run-Git push origin auditor-ia

Write-Host "Sincronizacao concluida sem editor interativo." -ForegroundColor Green
Run-Git status --short
