@echo off
chcp 65001 >nul
title Ururau - Instalar navegadores do Scrapling (v200_2)
cd /d "%~dp0"

echo ============================================================
echo  INSTALACAO DOS NAVEGADORES DO SCRAPLING - URURAU v200_2
echo ------------------------------------------------------------
echo  O 'scrapling install' direto nao funciona porque o comando
echo  nao esta no PATH e o pacote nao tem __main__.
echo  A forma CORRETA (do README oficial do Scrapling) e chamar
echo  scrapling.cli.install pelo proprio Python. E o que este
echo  .bat faz, com 3 fallbacks.
echo ============================================================
echo.

echo [1/3] Tentando: scrapling.cli.install (metodo oficial)...
python -c "from scrapling.cli import install; install([], standalone_mode=False)"
if %ERRORLEVEL%==0 (
    echo.
    echo [OK] Navegadores do Scrapling instalados via scrapling.cli.install.
    goto :fim
)

echo.
echo [2/3] Fallback: executavel scrapling.exe na pasta Scripts do usuario...
set "SCR=%APPDATA%\Python\Python314\Scripts\scrapling.exe"
if exist "%SCR%" (
    "%SCR%" install
    if %ERRORLEVEL%==0 (
        echo.
        echo [OK] Navegadores instalados via %SCR%.
        goto :fim
    )
)

echo.
echo [3/3] Fallback: playwright install chromium (Scrapling usa Chromium)...
python -m playwright install chromium
if %ERRORLEVEL%==0 (
    echo.
    echo [OK] Chromium do Playwright instalado - o Scrapling consegue usar.
    goto :fim
)

echo.
echo [ERRO] Nenhum dos 3 metodos funcionou. Copie a tela inteira e mande
echo        para analise. Pode ser que o scrapling[fetchers] nao tenha
echo        sido instalado por completo - rode antes:
echo        pip install "scrapling[fetchers]^>=0.3.0"
goto :fim

:fim
echo.
echo ============================================================
echo  Concluido. Agora abra o painel (03_ABRIR_PAINEL_COM_LOG_VISIVEL.bat)
echo  e rode uma coleta. No log, procure as linhas:
echo    [LEITURA_FONTE][SCRAPLING] OK ... chars via scrapling_...
echo  Se aparecerem, o Scrapling esta funcionando.
echo ============================================================
pause
