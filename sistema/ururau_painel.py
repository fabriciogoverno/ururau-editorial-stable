"""
ururau_painel.py - Ponto de entrada do painel editorial Ururau v99 datas Brasília.

Inicializa configuracoes, banco de dados, cliente OpenAI e lanca a GUI.

v63: Tratamento robusto de erros + log em arquivo para diagnosticar
quando o painel fecha sozinho. Se algo falhar, o erro vai aparecer no
console E em logs/painel_inicializacao.log.
"""
from __future__ import annotations

try:
    from ururau.fixes.v121_status_guard import aplicar_status_guard_v121
    aplicar_status_guard_v121()
except Exception as _e_v121_status:
    print(f"[V121][STATUS][AVISO] guard não aplicado: {_e_v121_status}")



import os
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Garante que o diretorio do projeto esteja no PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _log_arquivo(msg: str):
    """Loga em arquivo (mesmo se o console fechar)."""
    try:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_dir / "painel_inicializacao.log", "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _imprimir(msg: str):
    """Imprime no console e loga em arquivo."""
    print(msg, flush=True)
    _log_arquivo(msg)


def _erro_fatal(titulo: str, detalhes: str):
    """
    Mostra erro fatal em messagebox (se tk disponivel) e console.
    Garante que o usuario VEJA o erro mesmo se o console fechar.
    """
    _imprimir(f"\n{'='*60}\n[ERRO FATAL] {titulo}\n{'='*60}\n{detalhes}\n")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            f"Ururau v99 - {titulo}",
            f"{titulo}\n\n{detalhes}\n\n"
            f"Mais detalhes em: logs/painel_inicializacao.log",
        )
        root.destroy()
    except Exception as _e:
        _imprimir(f"[AVISO] Nao foi possivel mostrar messagebox: {_e}")


def main():
    _imprimir("=" * 60)
    _imprimir(f"URURAU v99 datas Brasília e janela 4h - Iniciando painel ({datetime.now().isoformat(timespec='seconds')})")
    _imprimir(f"Diretorio: {BASE_DIR}")
    _imprimir(f"Python: {sys.version}")
    _imprimir(f"Executavel: {sys.executable}")
    _imprimir("=" * 60)

    # Carrega .env com prioridade segura de credenciais.
    try:
        from dotenv import load_dotenv
        for _env_path, _override in [
            (BASE_DIR / "credenciais" / ".env.exemplo", False),
            (BASE_DIR / "credenciais" / "env_principal.env", True),
            (BASE_DIR / ".env", True),
        ]:
            if _env_path.exists():
                load_dotenv(_env_path, override=_override)
        _imprimir("[OK] .env carregado com prioridade segura")
    except ImportError:
        _imprimir("[AVISO] python-dotenv ausente. Continuando com variaveis do sistema.")


    # Patches v117: motor GPT rigoroso + editoria contextual
    try:
        from ururau.editorial.openai_motor_patch_v2 import aplicar_patch_openai_motor_v2
        aplicar_patch_openai_motor_v2()
        _imprimir("[OK] Motor GPT Spec V2 ativo")
    except Exception as _e_motor_v2:
        _imprimir(f"[MOTOR_V2][AVISO] patch não aplicado: {_e_motor_v2}")
    try:
        from ururau.editorial.editoria_runtime_patch_v117 import aplicar_patch_editoria_contextual_v117
        aplicar_patch_editoria_contextual_v117()
        _imprimir("[OK] Editoria contextual v117 ativa")
    except Exception as _e_editoria_v117:
        _imprimir(f"[EDITORIA_V117][AVISO] patch não aplicado: {_e_editoria_v117}")

    # Imports do pacote
    try:
        from ururau.config.settings import (
            OPENAI_API_KEY,
            MODELO_OPENAI,
            ARQUIVO_DB,
            PASTA_IMAGENS,
            PASTA_PRINTS,
            PASTA_LOGS,
            validate_openai_config,
        )
        from ururau.core.database import get_db
        _imprimir("[OK] Modulos do pacote importados")
    except ImportError as e:
        _erro_fatal(
            "Falha ao importar modulos do pacote ururau",
            f"Erro: {e}\n\nStack:\n{traceback.format_exc()}\n\n"
            "Possiveis causas:\n"
            "1. Voce nao esta executando do diretorio do projeto.\n"
            "2. Dependencias nao foram instaladas - rode INSTALAR.bat.\n"
            "3. Algum arquivo .py do pacote esta corrompido.",
        )
        sys.exit(3)
    except Exception as e:
        _erro_fatal(
            "Erro inesperado ao importar settings",
            f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
        sys.exit(4)

    # Cria pastas
    try:
        for pasta in (PASTA_IMAGENS, PASTA_PRINTS, PASTA_LOGS):
            Path(pasta).mkdir(parents=True, exist_ok=True)
        _imprimir("[OK] Pastas criadas")
    except Exception as e:
        _imprimir(f"[AVISO] Falha ao criar pastas: {e}")

    # Banco de dados
    try:
        db = get_db(ARQUIVO_DB)
        _imprimir(f"[OK] Banco de dados aberto: {ARQUIVO_DB}")
    except Exception as e:
        _erro_fatal(
            "Falha ao abrir banco de dados",
            f"Arquivo: {ARQUIVO_DB}\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
        sys.exit(5)

    # Cliente OpenAI
    # v46.8: criação do cliente não é tratada como prova de IA funcionando.
    # A prova real fica registrada quando a primeira chamada ao modelo retorna
    # openai_ok; falhas 401/429/timeout/JSON inválido aparecem em logs/ia_diagnostico.*.
    client = None
    try:
        from ururau.ia.diagnostico import registrar_evento_ia
    except Exception:
        registrar_evento_ia = None

    validacao_ia = validate_openai_config(OPENAI_API_KEY, MODELO_OPENAI)
    if not validacao_ia.ok:
        _imprimir(f"[IA][AVISO] OpenAI indisponivel na inicializacao: {validacao_ia.codigo or validacao_ia.reason}. O sistema usara fallback local identificado.")
        if registrar_evento_ia:
            registrar_evento_ia(
                etapa="startup_openai_config",
                status=validacao_ia.codigo or validacao_ia.reason or "openai_config_invalid",
                modelo=MODELO_OPENAI,
                provider="openai",
                mensagem=validacao_ia.reason or "Configuração OpenAI inválida.",
                sucesso=False,
            )
    else:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            _imprimir(f"[OK] Cliente OpenAI criado (modelo: {MODELO_OPENAI}). A chamada real sera diagnosticada em logs/ia_diagnostico.log")
            if registrar_evento_ia:
                registrar_evento_ia(
                    etapa="startup_openai_config",
                    status="openai_client_created",
                    modelo=MODELO_OPENAI,
                    provider="openai",
                    mensagem="Cliente OpenAI criado; validação real ocorrerá na primeira chamada do modelo.",
                    sucesso=True,
                )
        except ImportError:
            _imprimir("[IA][AVISO] Biblioteca 'openai' nao instalada. IA desativada; fallback local identificado.")
            if registrar_evento_ia:
                registrar_evento_ia("startup_openai_config", "openai_library_missing", modelo=MODELO_OPENAI, provider="openai", mensagem="Biblioteca openai ausente.", sucesso=False)
        except Exception as e:
            _imprimir(f"[IA][AVISO] Falha ao criar cliente OpenAI: {e}. Fallback local identificado.")
            if registrar_evento_ia:
                registrar_evento_ia("startup_openai_config", "openai_client_creation_failed", modelo=MODELO_OPENAI, provider="openai", mensagem=str(e), sucesso=False)

    # Lanca a interface grafica
    try:
        _imprimir("[INFO] Importando UI...")
        from ururau.ui.painel import PainelUrurau
        _imprimir("[INFO] Construindo PainelUrurau...")
        app = PainelUrurau(db=db, client=client, modelo=MODELO_OPENAI)
        _imprimir("[OK] Painel construido. Entrando no mainloop()...")
        app.mainloop()
        _imprimir("[INFO] Painel encerrado normalmente.")
    except Exception as e:
        _erro_fatal(
            "Falha ao construir/abrir o painel",
            f"{type(e).__name__}: {e}\n\nStack completo:\n{traceback.format_exc()}",
        )
        sys.exit(6)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        _erro_fatal(
            "Erro nao tratado em main()",
            f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
        sys.exit(99)
