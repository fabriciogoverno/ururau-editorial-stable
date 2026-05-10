# Ururau Neural Engine — Script de Deploy Fase 1
# Uso: powershell -ExecutionPolicy Bypass -File DEPLOY_FASE1_NEURAL.ps1

$ErrorActionPreference = "Stop"
$base = Get-Location

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  URURAU NEURAL ENGINE — DEPLOY FASE 1" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Verifica se está na raiz do projeto
if (-not (Test-Path "$base\sistema\ururau_painel.py")) {
    Write-Host "[ERRO] Execute este script na RAIZ do ururau-editorial-stable" -ForegroundColor Red
    exit 1
}

# Cria diretórios
$dirs = @(
    "sistema\ururau_ai_auditor\nn_engine",
    "dados_ml",
    "modelos_ml"
)
foreach ($d in $dirs) {
    $p = Join-Path $base $d
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
        Write-Host "[OK] Diretorio criado: $d" -ForegroundColor Green
    }
}

# Lista de arquivos a copiar (assumindo que o ZIP foi extraído e este script está na raiz)
$map = @{
    "sistema\ururau_ai_auditor\nn_engine\__init__.py" = "sistema\ururau_ai_auditor\nn_engine\__init__.py"
    "sistema\ururau_ai_auditor\nn_engine\vectorizer.py" = "sistema\ururau_ai_auditor\nn_engine\vectorizer.py"
    "sistema\ururau_ai_auditor\nn_engine\feature_store.py" = "sistema\ururau_ai_auditor\nn_engine\feature_store.py"
    "sistema\ururau_ai_auditor\nn_engine\vector_db.py" = "sistema\ururau_ai_auditor\nn_engine\vector_db.py"
    "sistema\ururau_ai_auditor\nn_engine\anomaly_ciclo.py" = "sistema\ururau_ai_auditor\nn_engine\anomaly_ciclo.py"
    "sistema\ururau_ai_auditor\nn_engine\severity_classifier.py" = "sistema\ururau_ai_auditor\nn_engine\severity_classifier.py"
    "sistema\ururau_ai_auditor\nn_engine\fonte_bandit.py" = "sistema\ururau_ai_auditor\nn_engine\fonte_bandit.py"
    "sistema\ururau_ai_auditor\nn_engine\intervalo_optimizer.py" = "sistema\ururau_ai_auditor\nn_engine\intervalo_optimizer.py"
    "sistema\ururau_ai_auditor\nn_engine\score_adaptive.py" = "sistema\ururau_ai_auditor\nn_engine\score_adaptive.py"
    "sistema\ururau_ai_auditor\nn_engine\runner.py" = "sistema\ururau_ai_auditor\nn_engine\runner.py"
    "45_TREINAR_MODELOS.bat" = "45_TREINAR_MODELOS.bat"
    "46_STATUS_NN.bat" = "46_STATUS_NN.bat"
    "requirements_nn.txt" = "requirements_nn.txt"
}

foreach ($src in $map.Keys) {
    $dst = Join-Path $base $map[$src]
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "[OK] Copiado: $src" -ForegroundColor Green
    } else {
        Write-Host "[AVISO] Nao encontrado: $src (execute apos extrair o ZIP)" -ForegroundColor Yellow
    }
}

# Instala dependências
Write-Host "[INFO] Instalando dependencias neural..." -ForegroundColor Cyan
pip install -r "$base\requirements_nn.txt"

# Git add + commit (se git disponível)
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "[INFO] Git detectado. Adicionando arquivos..." -ForegroundColor Cyan
    git add -A
    git commit -m "feat(neural): Fase 1 Neural Engine — vectorizer, anomaly, bandit, adaptive score"
    Write-Host "[OK] Commit local criado." -ForegroundColor Green
    Write-Host "[INFO] Para subir: git push origin main" -ForegroundColor Yellow
} else {
    Write-Host "[AVISO] Git nao encontrado. Suba manualmente." -ForegroundColor Yellow
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  DEPLOY CONCLUIDO" -ForegroundColor Cyan
Write-Host "  Proximo passo: execute 45_TREINAR_MODELOS.bat" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
