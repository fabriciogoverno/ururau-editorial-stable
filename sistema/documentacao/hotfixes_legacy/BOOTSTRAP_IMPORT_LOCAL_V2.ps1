param(
  [string]$ProjectPath = "C:\Users\fabri\Downloads\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL",
  [string]$RepoUrl = "https://github.com/fabriciogoverno/ururau-editorial-stable.git"
)

$ErrorActionPreference = "Stop"

function Run-Git {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
  & git @Args
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Args -join ' ') falhou com codigo $LASTEXITCODE"
  }
}

Write-Host "Ururau Editorial Stable - importador local V2" -ForegroundColor Cyan
Write-Host "Projeto: $ProjectPath"

if (!(Test-Path $ProjectPath)) {
  throw "Pasta do projeto nao encontrada: $ProjectPath"
}

Set-Location $ProjectPath

@'
.env
*.env
**/.env
**/.env.local
credenciais/
sistema/credenciais/
**/env_principal.env
data/
sistema/data/
*.db
*.sqlite
*.sqlite3
logs/
sistema/logs/
*.log
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
venv/
.venv/
env/
ENV/
node_modules/
*.tmp
*.bak
*.bak_*
*.zip
*.rar
*.7z
.wwebjs_auth/
.wwebjs_cache/
playwright-report/
test-results/
sistema/data/imagens/
sistema/data/prints/
ghostwriter_images/
Thumbs.db
desktop.ini
'@ | Set-Content -Encoding UTF8 .gitignore

if (!(Test-Path .git)) {
  Run-Git init
}

Run-Git branch -M main

$hasOrigin = $false
try {
  $originUrl = & git remote get-url origin 2>$null
  if ($LASTEXITCODE -eq 0 -and $originUrl) { $hasOrigin = $true }
} catch {
  $hasOrigin = $false
}

if ($hasOrigin) {
  Run-Git remote set-url origin $RepoUrl
} else {
  Run-Git remote add origin $RepoUrl
}

Write-Host "Conferindo status antes do commit..." -ForegroundColor Cyan
& git status --short

Write-Host "\nATENCAO: se aparecer credenciais, env_principal, .env, ururau.db, logs ou data/imagens, cancele agora com Ctrl+C." -ForegroundColor Red
Read-Host "Pressione ENTER para confirmar que o status esta seguro"

Run-Git add .

Write-Host "\nArquivos preparados para commit:" -ForegroundColor Cyan
& git status --short

Write-Host "\nUltima chance: confirme que nenhum segredo entrou no commit." -ForegroundColor Red
Read-Host "Pressione ENTER para criar commit e enviar ao GitHub"

# Se nao houver mudancas, nao falha.
$changes = & git status --porcelain
if ($changes) {
  Run-Git commit -m "baseline: importar versao local sem dados sensiveis"
} else {
  Write-Host "Nenhuma mudanca para commit." -ForegroundColor Yellow
}

Run-Git push -u origin main

Run-Git checkout -B auditor-ia
Run-Git push -u origin auditor-ia

Write-Host "\nImportacao concluida. Branch auditor-ia pronta." -ForegroundColor Green
