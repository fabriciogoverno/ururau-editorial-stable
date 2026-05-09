"""
ururau_monitor.py — Robô de monitoramento 24h do Ururau.

Modos de CMS v47.3:
  local    : processa e salva apenas no banco/local; não abre o CMS.
  rascunho : envia ao CMS como rascunho, com o checkbox
             "Não publicar a notícia agora. Salvar como rascunho!" marcado.
  direto   : permite publicação ao vivo somente se TODAS as confirmações e gates passarem.

Uso seguro:
    python ururau_monitor.py --modo-cms rascunho
    python ururau_monitor.py --modo-cms local
    python ururau_monitor.py --modo-cms direto

Compatibilidade:
    python ururau_monitor.py --publicar  # alias legado para --modo-cms direto
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# ── Garante que o diretório do projeto esteja no PYTHONPATH ──────────────────
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── Carrega .env antes de qualquer import do pacote ──────────────────────────
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

# Defaults primeiro, credenciais reais depois. Isso replica a política central.
for _env_path, _override in (
    (BASE_DIR / "credenciais" / ".env.exemplo", False),
    (BASE_DIR / "credenciais" / "env_principal.env", True),
    (BASE_DIR / ".env", True),
):
    try:
        if _env_path.exists():
            load_dotenv(_env_path, override=_override)
    except Exception:
        pass


@dataclass
class MonitorModo:
    modo_cms: str
    usar_cms: bool
    permitir_publicacao_direta: bool
    descricao: str


def _bool_env(nome: str, default: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _carregar_modo_padrao_config() -> str:
    """Lê sistema/config/monitor_24h.json; se faltar, usa rascunho por segurança operacional."""
    cfg_path = BASE_DIR / "config" / "monitor_24h.json"
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        modo = str(data.get("modo_cms_padrao") or "rascunho").strip().lower()
        if modo in {"local", "rascunho", "direto"}:
            return modo
    except Exception:
        pass
    return "rascunho"



def _carregar_config_monitor_24h() -> dict:
    cfg_path = BASE_DIR / "config" / "monitor_24h.json"
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _int_config(data: dict, chave: str, default: int) -> int:
    try:
        val = int(data.get(chave, default))
        return val if val > 0 else default
    except Exception:
        return default


def _aplicar_defaults_operacionais_monitor(data: dict) -> None:
    """
    Aplica defaults de capacidade do monitor no ambiente sem sobrescrever .env real.

    Objetivo: manter RSS, AutoFontes, Google News v111, fallback legado e hidratação
    disponíveis por padrão quando o arquivo config/monitor_24h.json permitir.
    """
    coleta = data.get("coleta") if isinstance(data.get("coleta"), dict) else {}

    def _bool_text(valor, default=False):
        if valor is None:
            valor = default
        return "1" if bool(valor) else "0"

    defaults = {
        "URURAU_V111_GNEWS_INTEGRADO": _bool_text(coleta.get("google_news_integrado_v111"), True),
        "URURAU_V111_USAR_EXTRACAO_COMPLETA": _bool_text(coleta.get("hidratar_google_news"), True),
        "URURAU_V111_USAR_CICLO_COMBINADO": _bool_text(coleta.get("ciclo_combinado_v111"), True),
        "URURAU_V110_MONITOR_GNEWS_LEGADO": _bool_text(coleta.get("google_news_legado_fallback"), True),
        "URURAU_V108_GNEWS_TERMOS": _bool_text(coleta.get("google_news_rss_legado_fallback"), True),
        "URURAU_SOURCE_HUNTER_ATIVO": _bool_text(coleta.get("source_hunter"), True),
        "URURAU_AUTOFONTES_V131_ATIVO": _bool_text(coleta.get("autofontes_v131"), True),
        "URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO": str(int(coleta.get("max_resultados_gnews_por_termo", 3) or 3)),
        "URURAU_V111_SCORE_MINIMO_PAUTA": str(int(coleta.get("score_minimo_gnews", 65) or 65)),
        "URURAU_V111_GNEWS_JANELA_HORAS": str(int(coleta.get("janela_horas_gnews", 4) or 4)),
        "URURAU_V111_GNEWS_MIN_CHARS_FONTE": str(int(coleta.get("min_chars_fonte_gnews", 500) or 500)),
    }
    respeitar_env = str(os.getenv("URURAU_MONITOR_RESPEITAR_ENV_COLETA", "0")).strip().lower() in {"1", "true", "sim", "yes", "s", "on"}
    for chave, valor in defaults.items():
        if respeitar_env:
            os.environ.setdefault(chave, valor)
        else:
            os.environ[chave] = valor
    try:
        from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers
        aplicar_defaults_scrapers(forcar=True)
    except Exception:
        pass

def _resolver_modo(args: argparse.Namespace) -> MonitorModo:
    # --publicar continua funcionando, mas agora é tratado explicitamente como modo direto.
    if getattr(args, "publicar", False):
        modo = "direto"
    elif getattr(args, "rascunho_cms", False):
        modo = "rascunho"
    else:
        modo = (args.modo_cms or os.getenv("URURAU_MONITOR_MODO_CMS") or _carregar_modo_padrao_config()).strip().lower()

    aliases = {
        "draft": "rascunho", "rascunhos": "rascunho", "cms_rascunho": "rascunho",
        "live": "direto", "aovivo": "direto", "ao_vivo": "direto", "publicar": "direto",
        "off": "local", "sem_cms": "local", "local_sem_cms": "local",
    }
    modo = aliases.get(modo, modo)
    if modo not in {"local", "rascunho", "direto"}:
        print(f"[MONITOR] Modo CMS inválido: {modo!r}. Use: local, rascunho ou direto.")
        sys.exit(2)

    if modo == "local":
        return MonitorModo(modo, False, False, "APENAS LOCAL/BANCO — não abre CMS")
    if modo == "rascunho":
        return MonitorModo(modo, True, False, "RASCUNHO CMS — checkbox de rascunho marcado")
    return MonitorModo(modo, True, True, "PUBLICAÇÃO AO VIVO — exige confirmação e gates completos")


def _criar_pastas():
    from ururau.config.settings import PASTA_IMAGENS, PASTA_PRINTS, PASTA_LOGS
    for pasta in (PASTA_IMAGENS, PASTA_PRINTS, PASTA_LOGS):
        Path(pasta).mkdir(parents=True, exist_ok=True)


def _criar_client_openai():
    """
    OpenAI é preferencial, mas não é bloqueante.
    Se a chave estiver ausente/inválida, o robô usa redação local conservadora.
    """
    from ururau.config.settings import OPENAI_API_KEY, MODELO_OPENAI, validate_openai_config

    validacao = validate_openai_config(OPENAI_API_KEY, MODELO_OPENAI)
    if not validacao.ok:
        print("[MONITOR] OpenAI indisponível. O robô seguirá com fallback local.")
        print(f"[MONITOR] Motivo: {validacao.reason} | Código: {validacao.codigo}")
        return None

    try:
        from openai import OpenAI
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception as exc:
        print(f"[MONITOR] Não foi possível criar cliente OpenAI ({exc}). Usando fallback local.")
        return None


def _validar_modo_cms(modo: MonitorModo) -> None:
    """Valida o ambiente conforme o modo. Rascunho não exige confirmação de publicação direta."""
    if not modo.usar_cms:
        return

    if modo.modo_cms == "rascunho":
        from ururau.publisher.cms_playwright_v81 import diagnosticar_credenciais_cms
        ok, msg = diagnosticar_credenciais_cms()
        if not ok:
            print("[MONITOR] Modo rascunho CMS bloqueado: credenciais ausentes.")
            print(f"[MONITOR] {msg}")
            print("[MONITOR] Use --modo-cms local para processar sem CMS ou preencha sistema/credenciais/env_principal.env.")
            sys.exit(2)
        return

    # Modo direto: confirmação forte. O gate editorial final ainda roda antes de cada envio.
    from ururau.publisher.producao_v78 import validar_ambiente_publicacao_real
    gate_env = validar_ambiente_publicacao_real()
    confirmacao_forte = str(os.getenv("URURAU_PUBLICACAO_REAL_CONFIRMADA", "")).strip().upper() == "SIM"
    flag_direta = _bool_env("URURAU_PUBLICAR_DIRETO", False) or _bool_env("URURAU_CMS_PUBLICACAO_DIRETA", False)
    if not gate_env.aprovado or not confirmacao_forte or not flag_direta:
        print("[MONITOR] Publicação ao vivo bloqueada por configuração de segurança:")
        for motivo in gate_env.motivos:
            print(f"  - {motivo}")
        if not confirmacao_forte:
            print("  - URURAU_PUBLICACAO_REAL_CONFIRMADA precisa estar como SIM")
        if not flag_direta:
            print("  - URURAU_PUBLICAR_DIRETO=1 ou URURAU_CMS_PUBLICACAO_DIRETA=1 precisa estar habilitado")
        print("[MONITOR] Para operação segura, use: python ururau_monitor.py --modo-cms rascunho")
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="Robô de monitoramento editorial Ururau 24h")
    parser.add_argument("--modo-cms", choices=["local", "rascunho", "direto"], default=None,
                        help="Destino do monitor: local, rascunho ou direto. Padrão: config/monitor_24h.json ou URURAU_MONITOR_MODO_CMS.")
    parser.add_argument("--rascunho-cms", action="store_true",
                        help="Atalho para --modo-cms rascunho")
    parser.add_argument("--publicar", action="store_true",
                        help="Compatibilidade legada: alias para --modo-cms direto")
    parser.add_argument("--intervalo", type=int, default=None,
                        help="Intervalo entre ciclos em segundos (padrão: .env ou 1800)")
    parser.add_argument("--max-hora", type=int, default=None,
                        help="Máx. publicações/cadastros por hora (padrão: .env ou 4)")
    parser.add_argument("--ciclo-unico", action="store_true",
                        help="Executa um único ciclo e sai (útil para testes)")
    args = parser.parse_args()

    _criar_pastas()
    modo = _resolver_modo(args)
    _validar_modo_cms(modo)

    from ururau.config.settings import (
        ARQUIVO_DB, MODELO_OPENAI,
        INTERVALO_ENTRE_CICLOS_SEGUNDOS,
        MAX_PUBLICACOES_MONITORAMENTO_POR_HORA,
    )
    from ururau.core.database import get_db
    from ururau.publisher.monitor import MonitorRobo

    db     = get_db(ARQUIVO_DB)
    client = _criar_client_openai()

    cfg_monitor = _carregar_config_monitor_24h()
    _aplicar_defaults_operacionais_monitor(cfg_monitor)
    intervalo   = args.intervalo or _int_config(cfg_monitor, "intervalo_normal_segundos", INTERVALO_ENTRE_CICLOS_SEGUNDOS)
    intervalo_sem_pauta = _int_config(cfg_monitor, "intervalo_sem_pauta_segundos", intervalo)
    max_hora    = args.max_hora  or _int_config(cfg_monitor, "max_materias_por_hora", MAX_PUBLICACOES_MONITORAMENTO_POR_HORA)

    print(f"""
╔══════════════════════════════════════════════════╗
║       URURAU — ROBÔ DE MONITORAMENTO 24h         ║
╠══════════════════════════════════════════════════╣
║  Intervalo : {intervalo}s ({intervalo//60}min)
║  Max/hora  : {max_hora} matérias
║  CMS       : {modo.descricao}
║  Modo      : {modo.modo_cms}
║  Direta    : {'HABILITADA' if modo.permitir_publicacao_direta else 'BLOQUEADA'}
║  Ctrl+C    : parar com segurança
╚══════════════════════════════════════════════════╝
""")

    robo = MonitorRobo(
        db=db,
        client=client,
        modelo=MODELO_OPENAI,
        intervalo_segundos=intervalo,
        max_por_hora=max_hora,
        publicar_no_cms=modo.usar_cms,
        permitir_publicacao_direta=modo.permitir_publicacao_direta,
        modo_cms=modo.modo_cms,
        intervalo_sem_pauta_segundos=intervalo_sem_pauta,
    )

    if args.ciclo_unico:
        print("[MONITOR] Modo ciclo único...")
        robo._executar_ciclo(1)
        return

    try:
        robo.iniciar()
    except KeyboardInterrupt:
        print("\n[MONITOR] Interrompido pelo usuário.")
        robo.parar()


if __name__ == "__main__":
    main()

# PATCH_V47_13_MONITOR_DEFAULTS
try:
    from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers
    aplicar_defaults_scrapers(globals().get('logger'))
except Exception:
    pass
