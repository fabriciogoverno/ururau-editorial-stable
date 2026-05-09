$ErrorActionPreference = "Stop"

Write-Host "Limpando scripts temporarios de hotfix da raiz..." -ForegroundColor Cyan

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$quarentena = Join-Path $root "sistema\documentacao\hotfixes_legacy"
New-Item -ItemType Directory -Force -Path $quarentena | Out-Null

$padroes = @(
  "HOTFIX_*.py",
  "REPARO_*.py",
  "FIX_*.py",
  "AUDITORIA_REPARO_FINAL*.py",
  "BOOTSTRAP_IMPORT_LOCAL*.ps1"
)

$movidos = @()
foreach ($padrao in $padroes) {
  Get-ChildItem -Path $root -Filter $padrao -File -ErrorAction SilentlyContinue | ForEach-Object {
    $dest = Join-Path $quarentena $_.Name
    Move-Item -Force $_.FullName $dest
    $movidos += $_.Name
  }
}

# Mantem somente BATs operacionais e a pasta sistema na raiz. Scripts temporarios ficam documentados.
$relatorio = Join-Path $quarentena "README_HOTFIXES_LEGACY.txt"
@"
Hotfixes legados movidos da raiz em $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss').

Motivo:
- estes scripts eram remendos temporarios;
- um deles tinha erro de sintaxe e quebrava a auditoria global;
- a raiz deve ficar limpa para operacao;
- a linha estavel passa a usar sistema/ururau_ai_auditor e testes de contrato.

Arquivos movidos:
$($movidos -join "`n")
"@ | Set-Content -Encoding UTF8 $relatorio

Write-Host "Movidos:" -ForegroundColor Green
$movidos | ForEach-Object { Write-Host " - $_" }

Write-Host "\nAgora rode:" -ForegroundColor Yellow
Write-Host "git status"
Write-Host "git add ."
Write-Host "git commit -m 'chore: mover hotfixes temporarios para documentacao'"
Write-Host "git push origin auditor-ia"
