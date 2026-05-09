"""
termos_config_v98.py — Termos editoriais configuráveis pelo painel.

Fonte única para a aba Config > Termos. O arquivo principal é
`termos_watchlist_v98.json`, no diretório raiz do projeto.

Formato interno:
{
  "termos": [
    {"termo": "Campos dos Goytacazes", "peso": 35, "canal": "Cidades", "buscar": true, "ativo": true}
  ]
}
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

ARQUIVO_TERMOS = Path("termos_watchlist_v98.json")

try:
    from ururau.coleta.linha_editorial_v129 import termos_padrao_config_v129
    TERMOS_PADRAO: list[dict[str, Any]] = termos_padrao_config_v129()
except Exception:
    TERMOS_PADRAO: list[dict[str, Any]] = [
        {"termo": "Campos dos Goytacazes", "peso": 35, "canal": "Cidades", "buscar": True, "ativo": True, "observacao": "Prioridade local máxima"},
        {"termo": "Norte Fluminense", "peso": 30, "canal": "Estado RJ", "buscar": True, "ativo": True, "observacao": "Cobertura regional"},
        {"termo": "Porto do Açu", "peso": 30, "canal": "Economia", "buscar": True, "ativo": True, "observacao": "Economia e desenvolvimento regional"},
        {"termo": "São João da Barra", "peso": 24, "canal": "Cidades", "buscar": True, "ativo": True, "observacao": "Município estratégico"},
        {"termo": "Alerj", "peso": 26, "canal": "Política", "buscar": True, "ativo": True, "observacao": "Política estadual"},
    ]


def _norm_bool(v: Any, padrao: bool = True) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return padrao
    s = str(v).strip().lower()
    if s in {"1", "sim", "s", "true", "ativo", "yes", "y"}:
        return True
    if s in {"0", "nao", "não", "n", "false", "inativo", "no"}:
        return False
    return padrao


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def normalizar_termo(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        termo = item.strip()
        if not termo:
            return None
        return {"termo": termo, "peso": 18, "canal": "", "buscar": True, "ativo": True, "observacao": ""}
    if not isinstance(item, dict):
        return None
    termo = str(item.get("termo") or item.get("nome") or item.get("query") or "").strip()
    if not termo:
        return None
    try:
        peso = int(item.get("peso", item.get("score", 18)) or 18)
    except Exception:
        peso = 18
    peso = max(1, min(60, peso))
    return {
        "termo": termo,
        "peso": peso,
        "canal": str(item.get("canal") or item.get("editoria") or "").strip(),
        "buscar": _norm_bool(item.get("buscar", item.get("busca", True)), True),
        "ativo": _norm_bool(item.get("ativo", True), True),
        "observacao": str(item.get("observacao") or item.get("obs") or "").strip(),
    }


def carregar_termos(criar_se_ausente: bool = False) -> list[dict[str, Any]]:
    """Carrega os termos ativos da aba Config > Termos.

    v129.12: se o arquivo de termos existe, ele é a fonte oficial.
    Isto é proposital: quando o usuário remove Poder360, Agenda do Poder,
    Diário do Rio etc. da aba Termos e salva, esses termos não podem voltar
    por fallback padrão nem por cache. O fallback TERMOS_PADRAO só é usado
    quando o arquivo ainda não existe.
    """
    dados: Any = None
    arquivo_existia = ARQUIVO_TERMOS.exists()
    if arquivo_existia:
        try:
            dados = json.loads(ARQUIVO_TERMOS.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[TERMOS v98] Falha ao ler {ARQUIVO_TERMOS}: {e}")
    if dados is None:
        # Somente primeira instalação/arquivo ausente recebe a lista padrão.
        # Arquivo existente vazio continua vazio.
        termos = [] if arquivo_existia else list(TERMOS_PADRAO)
        if criar_se_ausente and not arquivo_existia:
            salvar_termos(termos)
        return termos
    brutos = dados.get("termos", dados) if isinstance(dados, dict) else dados
    if not isinstance(brutos, list):
        brutos = []
    termos: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in brutos:
        t = normalizar_termo(item)
        if not t:
            continue
        k = normalizar(t["termo"])
        if k in vistos:
            continue
        vistos.add(k)
        termos.append(t)
    return termos


def salvar_termos(termos: list[dict[str, Any]]) -> None:
    limpos: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in termos:
        t = normalizar_termo(item)
        if not t:
            continue
        k = normalizar(t["termo"])
        if k in vistos:
            continue
        vistos.add(k)
        limpos.append(t)
    payload = {
        "_versao": "v98",
        "_descricao": "Termos configuráveis pela aba Config > Termos. Usados para busca, watchlist e aumento de score editorial.",
        "termos": limpos,
    }
    ARQUIVO_TERMOS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def termos_para_texto() -> str:
    """Retorna termos em formato simples: um termo por linha.

    v111.4: a tela de configuração passa a mostrar somente o termo buscado.
    Peso/canal/observação ficam como metadados internos e não atrapalham a edição.
    O formato antigo Termo|Peso|Canal|Buscar|Obs continua aceito ao salvar.
    """
    linhas = []
    for t in carregar_termos(criar_se_ausente=True):
        termo = str(t.get("termo", "") or "").strip()
        if termo:
            linhas.append(termo)
    return "\n".join(linhas)


def texto_para_termos(texto: str) -> list[dict[str, Any]]:
    """Converte texto livre em termos.

    v111.4: o usuário pode colar apenas:
        Campos dos Goytacazes
        Norte Fluminense
    O parser também aceita o formato antigo com pipes, mas usa só o primeiro
    campo como termo. Isso evita confundir fonte RSS com termo e reduz erro.
    """
    termos: list[dict[str, Any]] = []
    try:
        from ururau.coleta.source_policy_v114 import termos_simples_padrao
        defaults = set(normalizar(t) for t in termos_simples_padrao())
    except Exception:
        defaults = set()
    try:
        from ururau.coleta.linha_editorial_v129 import termos_padrao_config_v129
        defaults.update(normalizar(t.get("termo", "")) for t in termos_padrao_config_v129())
    except Exception:
        pass
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        # Se alguém colar fonte RSS por engano na aba Termos, ignora.
        if linha.lower().startswith(("http://", "https://")):
            continue
        termo = linha.split("|", 1)[0].strip()
        if not termo:
            continue
        k = normalizar(termo)
        peso = 28 if k in defaults else 18
        canal = ""
        if any(x in k for x in ("flamengo", "vasco", "botafogo", "fluminense", "americano de campos", "americano futebol", "americano fc", "goytacaz", "goitacaz")):
            canal = "Esportes"
            peso = max(peso, 28)
        elif any(x in k for x in ("campos", "sao joao", "são joão", "norte fluminense")):
            canal = "Cidades"
        elif any(x in k for x in ("porto", "economia")):
            canal = "Economia"
        elif any(x in k for x in ("alerj", "ruas", "wladimir", "bacellar", "paes", "castro", "tce", "mprj", "stf", "stj", "tse", "senado", "camara", "câmara", "deputad", "governo", "prefeit", "garotinho", "tre-rj", "tjrj")):
            canal = "Política"
        termos.append({
            "termo": termo,
            "peso": peso,
            "canal": canal,
            "buscar": True,
            "ativo": True,
            "observacao": "termo simples v111.4",
        })
    return termos

def termos_busca() -> list[str]:
    termos = []
    vistos = set()
    for t in carregar_termos():
        if not t.get("ativo", True) or not t.get("buscar", True):
            continue
        termo = str(t.get("termo") or "").strip()
        if not termo:
            continue
        k = normalizar(termo)
        if k not in vistos:
            vistos.add(k)
            termos.append(termo)
    return termos


def analisar_texto(texto: str) -> tuple[int, list[str], str]:
    """Retorna (score_extra, termos_detectados, canal_sugerido)."""
    texto_norm = normalizar(texto)
    score = 0
    achados: list[str] = []
    canal_sugerido = ""
    for t in carregar_termos():
        if not t.get("ativo", True):
            continue
        termo = str(t.get("termo") or "").strip()
        if not termo:
            continue
        if normalizar(termo) in texto_norm:
            peso = int(t.get("peso", 18) or 18)
            score += max(1, min(60, peso))
            achados.append(termo)
            if not canal_sugerido and t.get("canal"):
                canal_sugerido = str(t.get("canal"))
    return min(score, 60), achados[:12], canal_sugerido


def atualizar_arquivos_auxiliares() -> None:
    """Sincroniza termos com arquivos já existentes para retrocompatibilidade."""
    termos = carregar_termos(criar_se_ausente=True)
    # Atualiza consultas_google_news.json preservando grupos existentes.
    p = Path("consultas_google_news.json")
    dados: dict[str, Any] = {}
    if p.exists():
        try:
            dados = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(dados, dict):
                dados = {}
        except Exception:
            dados = {}
    dados.setdefault("_versao", "v98")
    dados["termos_config_painel"] = [t["termo"] for t in termos if t.get("ativo", True) and t.get("buscar", True)]
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def invalidar_cache_editorial_v12912() -> None:
    """Limpa caches editoriais conhecidos após Salvar e Aplicar.

    O projeto tem camadas antigas que mantêm watchlists em memória.
    Esta função não remove arquivos e não altera coleta; apenas faz o próximo
    cálculo ler novamente Config > Termos.
    """
    try:
        import ururau.coleta.intel_editorial as intel
        if hasattr(intel, "_watchlists_cache"):
            intel._watchlists_cache = None
    except Exception:
        pass
    try:
        import ururau.coleta.linha_editorial_v129 as le
        if hasattr(le, "_CACHE_TERMOS_CONFIG_V12912"):
            le._CACHE_TERMOS_CONFIG_V12912 = None
        if hasattr(le, "_CACHE_TERMOS_CONFIG_MTIME_V12912"):
            le._CACHE_TERMOS_CONFIG_MTIME_V12912 = None
    except Exception:
        pass
