
from __future__ import annotations
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any
import os

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False


from ururau.config.settings import LOGIN as SETTINGS_LOGIN, SENHA as SETTINGS_SENHA


def _load_all_env_sources() -> None:
    """Carrega .env principal e o fallback de credenciais antes do envio ao CMS."""
    base_dir = Path(__file__).resolve().parents[2]
    # v47: .env.exemplo apenas como default; credenciais reais têm prioridade.
    env_defaults = [base_dir / "credenciais" / ".env.exemplo"]
    env_real = [base_dir / "credenciais" / "env_principal.env", base_dir / ".env"]
    for env_path in env_defaults:
        try:
            if env_path.exists():
                load_dotenv(env_path, override=False)
        except Exception:
            pass
    for env_path in env_real:
        try:
            if env_path.exists():
                load_dotenv(env_path, override=True)
        except Exception:
            pass


def diagnosticar_credenciais_cms() -> tuple[bool, str]:
    _load_all_env_sources()
    login = os.getenv("URURAU_LOGIN", SETTINGS_LOGIN).strip()
    senha = os.getenv("URURAU_SENHA", SETTINGS_SENHA).strip()
    if login and senha:
        return True, "Credenciais do CMS carregadas com sucesso."
    return False, (
        "Credenciais do CMS ausentes. Preencha URURAU_LOGIN e URURAU_SENHA em Config > Credenciais "
        "ou no arquivo sistema/.env. O sistema também aceita o fallback sistema/credenciais/env_principal.env."
    )

def _run_async(coro, timeout: int = 180):
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "event loop" not in str(e).lower():
            raise
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result(timeout=timeout)

def _ultimo_arquivo(pasta: str = "prints", padrao: str = "*"):
    try:
        p = Path(pasta)
        if not p.exists():
            return None
        arquivos = sorted(p.glob(padrao), key=lambda x: x.stat().st_mtime, reverse=True)
        return str(arquivos[0]) if arquivos else None
    except Exception:
        return None

def publicar_no_cms_v81(materia: Any, imagem: Any = None, publicar: bool = False, rascunho: bool = True) -> dict:
    """
    Publica/salva rascunho no CMS usando o publicador Playwright consolidado.

    Retorno:
    {
      ok, status, mensagem, url, screenshot, html_debug
    }
    """
    if publicar:
        rascunho = False

    # v46.3: recarrega todas as fontes de credenciais no momento do clique.
    _load_all_env_sources()
    LOGIN = os.getenv("URURAU_LOGIN", SETTINGS_LOGIN).strip()
    SENHA = os.getenv("URURAU_SENHA", SETTINGS_SENHA).strip()

    if not LOGIN or not SENHA:
        ok_cred, msg_cred = diagnosticar_credenciais_cms()
        return {
            "ok": False,
            "status": "erro",
            "mensagem": msg_cred if not ok_cred else "Credenciais do CMS ausentes.",
            "url": None,
            "screenshot": None,
            "html_debug": None,
        }

    try:
        from ururau.publisher.form_filler import executar_publicacao_playwright
    except Exception as e:
        return {
            "ok": False,
            "status": "erro",
            "mensagem": f"Falha ao importar form_filler: {type(e).__name__}: {e}",
            "url": None,
            "screenshot": None,
            "html_debug": None,
        }

    try:
        print(f"[v85][CMS] Envio solicitado: publicar={bool(publicar)} rascunho={bool(rascunho)} login_preenchido={bool(LOGIN)}")
        ok = bool(_run_async(executar_publicacao_playwright(materia, imagem, LOGIN, SENHA, rascunho=rascunho)))
        return {
            "ok": ok,
            "status": "publicado" if ok and not rascunho else ("rascunho" if ok else "erro"),
            "mensagem": ("Publicação direta confirmada pelo CMS." if ok and not rascunho else ("Rascunho confirmado pelo CMS." if ok else "CMS não confirmou cadastro; veja screenshot/HTML em prints.")),
            "url": None,
            "screenshot": _ultimo_arquivo("prints", "*.png"),
            "html_debug": _ultimo_arquivo("prints", "*.html"),
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "erro",
            "mensagem": f"{type(e).__name__}: {e}",
            "url": None,
            "screenshot": _ultimo_arquivo("prints", "*.png"),
            "html_debug": _ultimo_arquivo("prints", "*.html"),
        }
