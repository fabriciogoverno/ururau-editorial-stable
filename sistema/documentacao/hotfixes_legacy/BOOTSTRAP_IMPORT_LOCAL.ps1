param(
  [string]$ProjectPath = "C:\Users\fabri\Downloads\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL",
  [string]$RepoUrl = "https://github.com/fabriciogoverno/ururau-editorial-stable.git"
)

$ErrorActionPreference = "Stop"

Write-Host "Ururau Editorial Stable - importador local" -ForegroundColor Cyan
Write-Host "Projeto: $ProjectPath"

if (!(Test-Path $ProjectPath)) {
  throw "Pasta do projeto nao encontrada: $ProjectPath"
}

Set-Location $ProjectPath

# Garante .gitignore seguro antes de qualquer add.
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
  git init
}

git branch -M main

$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
  git remote add origin $RepoUrl
} else {
  git remote set-url origin $RepoUrl
}

Write-Host "Conferindo arquivos sensiveis que NAO devem entrar..." -ForegroundColor Yellow
$blocked = git status --porcelain --ignored | Select-String -Pattern "credenciais|env_principal|\.env|ururau\.db|sistema/data|logs|\.zip"
if ($blocked) {
  Write-Host "Itens sensiveis/ignorados detectados. Isso e esperado se aparecerem como ignorados." -ForegroundColor Yellow
  $blocked | ForEach-Object { Write-Host $_ }
}

git add .

Write-Host "Status antes do commit:" -ForegroundColor Cyan
git status --short

Write-Host "Se aparecer credencial, .env, banco ou logs acima, cancele agora com Ctrl+C." -ForegroundColor Red
Read-Host "Pressione ENTER para confirmar o commit seguro"

git commit -m "baseline: importar versao local sem dados sensiveis"
git push -u origin main

# Cria branch de trabalho.
git checkout -B auditor-ia
git push -u origin auditor-ia

Write-Host "Importacao concluida. Branch auditor-ia pronta." -ForegroundColor Green
