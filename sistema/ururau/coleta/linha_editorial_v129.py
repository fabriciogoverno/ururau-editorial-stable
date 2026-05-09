"""
linha_editorial_v129.py — Linha editorial ampliada do Ururau.

Objetivo da v129:
- Fazer os termos de Config > Termos também valerem como filtro editorial positivo.
- Dar boost a deputados estaduais, políticos relevantes do RJ e municípios estratégicos.
- Tratar fontes oficiais/políticas especiais como livres do corte de score, sem ignorar
  duplicidade, janela, link inválido ou asset.
- Permitir uma aba própria "Fontes Especiais" na configuração.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

ARQUIVO_FONTES_ESPECIAIS = Path("fontes_especiais_v129.json")
_CACHE_TERMOS_CONFIG_V12912 = None
_CACHE_TERMOS_CONFIG_MTIME_V12912 = None

TERMOS_BASE_V129 = [
  "Campos 24 Horas",
  "Folha 1 Campos",
  "Diário do Rio",
  "Diario do Rio",
  "Manchete Rio",
  "Manchete RJ",
  "Agenda do Poder",
  "Poder360",
  "G1 Norte Fluminense",
  "G1 Política",
  "G1 Politica",
  "Flamengo",
  "Clube de Regatas do Flamengo",
  "Vasco",
  "Vasco da Gama",
  "CR Vasco da Gama",
  "Botafogo",
  "Botafogo de Futebol e Regatas",
  "Fluminense",
  "Fluminense Football Club",
  "Americano de Campos",
  "Americano Futebol Clube",
  "Americano FC",
  "Goytacaz",
  "Goytacaz Futebol Clube",
  "Goitacaz",
  "Goitacaz Futebol Clube",
  "royalties",
  "licitação",
  "licitacao",
  "operação",
  "operacao",
  "investigação",
  "investigacao",
  "prisão",
  "prisao",
  "fraude",
  "orçamento",
  "orcamento",
  "eleição",
  "eleicao",
  "cassação",
  "cassacao",
  "Alerj",
  "Palácio Guanabara",
  "Palacio Guanabara",
  "Governo RJ",
  "Governo do Rio",
  "STF",
  "STJ",
  "TSE",
  "TRE-RJ",
  "TJRJ",
  "MPRJ",
  "TCE-RJ",
  "Senado",
  "Câmara dos Deputados",
  "Camara dos Deputados",
  "Gov.br",
  "Receita Federal",
  "Polícia Federal",
  "Policia Federal",
  "Ministério Público",
  "Ministerio Publico",
  "Defensoria RJ",
  "Defensoria Pública",
  "Defensoria Publica",
  "Campos dos Goytacazes",
  "São João da Barra",
  "Sao Joao da Barra",
  "São Francisco de Itabapoana",
  "Sao Francisco de Itabapoana",
  "Cardoso Moreira",
  "São Fidélis",
  "Sao Fidelis",
  "Macaé",
  "Macae",
  "Quissamã",
  "Quissama",
  "Carapebus",
  "Conceição de Macabu",
  "Conceicao de Macabu",
  "Norte Fluminense",
  "Porto do Açu",
  "Porto do Acu",
  "Baixada Campista",
  "Guarus",
  "Farol de São Thomé",
  "Farol de Sao Thome",
  "Rio de Janeiro",
  "Niterói",
  "Niteroi",
  "São Gonçalo",
  "Sao Goncalo",
  "Duque de Caxias",
  "Nova Iguaçu",
  "Nova Iguacu",
  "Belford Roxo",
  "São João de Meriti",
  "Sao Joao de Meriti",
  "Nilópolis",
  "Nilopolis",
  "Mesquita",
  "Queimados",
  "Japeri",
  "Itaguaí",
  "Itaguai",
  "Seropédica",
  "Seropedica",
  "Magé",
  "Mage",
  "Guapimirim",
  "Itaboraí",
  "Itaborai",
  "Tanguá",
  "Tangua",
  "Maricá",
  "Marica",
  "Rio Bonito",
  "Cachoeiras de Macacu",
  "Baixada Fluminense",
  "Grande Rio",
  "Região Metropolitana",
  "Regiao Metropolitana",
  "Alan Lopes",
  "Andrezinho Ceciliano",
  "Arezas",
  "Átila Nunes",
  "Atila Nunes",
  "Bebeto",
  "Brazão",
  "Brazao",
  "Bruno Dauaire",
  "Carlinhos BNH",
  "Carla Machado",
  "Carlos Macedo",
  "Carlos Minc",
  "Célia Jordão",
  "Celia Jordao",
  "Chico Machado",
  "Claudio Caiado",
  "Cláudio Caiado",
  "Dani Balbi",
  "Dani Monteiro",
  "Danniel Librelon",
  "Dionísio Lins",
  "Dionisio Lins",
  "Douglas Ruas",
  "Dr. Deodalto",
  "Dr. Pedro Ricardo",
  "Dr. Serginho",
  "Elika Takimoto",
  "Elias Jabor",
  "Felippe Poubel",
  "Filippe Soares",
  "Flávio Serafini",
  "Flavio Serafini",
  "Fred Pacheco",
  "Giovani Ratinho",
  "Giselle Monteiro",
  "Guilherme Delaroli",
  "Guilherme Schleder",
  "Gustavo Tutuca",
  "Índia Armelau",
  "India Armelau",
  "Jair Bittencourt",
  "Jari Oliveira",
  "Jorge Felippe Neto",
  "Julio Rocha",
  "Júlio Rocha",
  "Léo Vieira",
  "Leo Vieira",
  "Lucinha",
  "Luiz Paulo",
  "Marcelo Dino",
  "Márcio Canella",
  "Marcio Canella",
  "Marcio Gualberto",
  "Márcio Gualberto",
  "Marina do MST",
  "Martha Rocha",
  "Munir Neto",
  "Otoni de Paula Pai",
  "Rafael Nobre",
  "Renata Souza",
  "Renato Machado",
  "Renato Miranda",
  "Resende",
  "Ricardo Abrão",
  "Ricardo Abraão",
  "Ricardo Abrao",
  "Rodrigo Amorim",
  "Rodrigo Bacellar",
  "Rosenverg Reis",
  "Samuel Malafaia",
  "Tande Vieira",
  "Thiago Gagliasso",
  "Thiago Rangel",
  "Tia Ju",
  "Val Ceasa",
  "Valdecy da Saúde",
  "Valdecy da Saude",
  "Verônica Lima",
  "Veronica Lima",
  "Vinícius Cozzolino",
  "Vinicius Cozzolino",
  "Vitor Junior",
  "Yuri",
  "Zeidan",
  "Anthony Garotinho",
  "Rosinha Garotinho",
  "Wladimir Garotinho",
  "Cláudio Castro",
  "Claudio Castro",
  "Eduardo Paes",
  "Flávio Bolsonaro",
  "Flavio Bolsonaro",
  "Romário",
  "Romario",
  "Carlos Portinho",
  "Rodrigo Neves",
  "Capitão Nelson",
  "Capitao Nelson",
  "Netinho Reis",
  "Dudu Reina",
  "Hingo Hammes",
  "Neto",
  "Renato Cozzolino",
  "Marcelo Delaroli",
  "Ferreti",
  "Leonardo Vasconcellos",
  "Welberth Rezende",
  "Caio Vianna",
  "Washington Reis",
  "Sérgio Cabral",
  "Sergio Cabral",
  "André Ceciliano",
  "Andre Ceciliano",
  "Alexandre Ramagem",
  "Lindbergh Farias",
  "Benedita da Silva",
  "Jandira Feghali",
  "Clarissa Garotinho",
  "Garotinho",
  "Paes",
  "Bacellar",
  "Castro",
  "Coutinho",
  "Doutor Luizinho",
  "Altineu Côrtes",
  "Altineu Cortes"
]

TERMOS_AMBIGUOS_V129 = {
    "neto", "yuri", "resende", "bebeto", "romario", "romário", "paes",
    "castro", "bacellar", "ferreti", "arezaz", "arezas", "vitor junior"
}

CONTEXTO_POLITICO_RJ_V129 = {
    "alerj", "assembleia legislativa", "deputado", "deputada", "governo do rio",
    "governo rj", "palacio guanabara", "palácio guanabara", "prefeitura",
    "prefeito", "prefeita", "vereador", "vereadora", "eleicao", "eleição",
    "politica", "política", "partido", "mandato", "campos", "rio de janeiro",
    "rj", "baixada", "norte fluminense", "grande rio", "tce-rj", "mprj",
    "stf", "stj", "tse", "tre-rj", "tjrj", "senado", "camara", "câmara",
    "vasco", "flamengo", "botafogo", "fluminense", "goytacaz", "goitacaz", "americano futebol", "futebol",
}

FONTES_SCORE_LIVRE_NOMES = {
    "stf", "supremo tribunal federal", "tse", "tribunal superior eleitoral",
    "gov.br", "gov br", "senado", "senado federal", "camara", "câmara",
    "camara dos deputados", "câmara dos deputados", "stj", "superior tribunal de justiça",
    "superior tribunal de justica", "alerj", "mprj", "ministerio publico do rio",
    "ministério público do rio", "tce-rj", "tre-rj", "tjrj", "governo rj",
    "governo do rio", "defensoria rj", "defensoria publica", "defensoria pública",
    "nf noticias", "nf notícias", "nfnoticias",
}

FONTES_SCORE_LIVRE_DOMINIOS = {
    "stf.jus.br", "noticias.stf.jus.br", "tse.jus.br", "www.tse.jus.br",
    "gov.br", "www.gov.br", "senado.leg.br", "www12.senado.leg.br",
    "camara.leg.br", "www.camara.leg.br", "stj.jus.br", "res.stj.jus.br",
    "alerj.rj.gov.br", "www.alerj.rj.gov.br", "mprj.mp.br", "www.mprj.mp.br",
    "tce.rj.gov.br", "www.tce.rj.gov.br", "tre-rj.jus.br", "www.tre-rj.jus.br",
    "tjrj.jus.br", "www.tjrj.jus.br", "rj.gov.br", "www.rj.gov.br",
    "defensoria.rj.def.br",
    "nfnoticias.com.br", "www.nfnoticias.com.br",
}

FONTES_ESPECIAIS_PADRAO = [
    {"nome": "STF", "url": "https://noticias.stf.jus.br/feed/", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "TSE", "url": "https://www.tse.jus.br/rss", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "Gov.br", "url": "https://www.gov.br/rss.xml", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "Senado", "url": "https://www12.senado.leg.br/noticias/rss.xml", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "Câmara", "url": "https://www.camara.leg.br/rss/noticias.xml", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "STJ", "url": "https://res.stj.jus.br/hrestp-c-portalp/RSS.xml", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "Alerj", "url": "https://www.alerj.rj.gov.br/Noticias/rss", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "MPRJ", "url": "https://www.mprj.mp.br/rss", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "TRE-RJ", "url": "https://www.tre-rj.jus.br/comunicacao/noticias/RSS", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "TJRJ", "url": "https://www.tjrj.jus.br/web/guest/home/-/noticias/rss", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "Governo RJ", "url": "https://www.rj.gov.br/noticias/rss", "tipo": "rss", "bypass_score": True, "ativo": True},
    {"nome": "Defensoria RJ", "url": "https://defensoria.rj.def.br/rss/noticias", "tipo": "rss", "bypass_score": True, "ativo": True},
]

def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()

def _host(url: str) -> str:
    try:
        h = urlparse(str(url or "").strip()).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

def _termos_configurados() -> list[dict[str, Any]]:
    """Termos oficiais da aba Config > Termos.

    v129.12: usa cache por mtime para ficar leve, mas invalida automaticamente
    quando o usuário salva a aba Termos. Não mistura TERMOS_BASE_V129 aqui.
    """
    global _CACHE_TERMOS_CONFIG_V12912, _CACHE_TERMOS_CONFIG_MTIME_V12912
    try:
        from ururau.coleta.termos_config_v98 import carregar_termos, ARQUIVO_TERMOS
        try:
            mtime = ARQUIVO_TERMOS.stat().st_mtime if ARQUIVO_TERMOS.exists() else -1
        except Exception:
            mtime = None
        if _CACHE_TERMOS_CONFIG_V12912 is not None and _CACHE_TERMOS_CONFIG_MTIME_V12912 == mtime:
            return list(_CACHE_TERMOS_CONFIG_V12912)
        termos = carregar_termos(criar_se_ausente=True)
        _CACHE_TERMOS_CONFIG_V12912 = list(termos)
        _CACHE_TERMOS_CONFIG_MTIME_V12912 = mtime
        return termos
    except Exception:
        return []

def termos_padrao_config_v129() -> list[dict[str, Any]]:
    saida = []
    for termo in TERMOS_BASE_V129:
        nk = normalizar(termo)
        if nk in TERMOS_AMBIGUOS_V129:
            peso = 12
            obs = "termo ambíguo v129: pontua melhor com contexto político/RJ"
        elif any(x in nk for x in ("alerj", "deputad", "garotinho", "bacellar", "paes", "castro", "stf", "tse", "senado", "câmara", "camara", "governo", "mprj", "tce-rj", "tre-rj", "tjrj")):
            peso = 34
            obs = "política/RJ v129"
        elif any(x in nk for x in ("flamengo", "vasco", "botafogo", "fluminense")):
            peso = 32
            obs = "esporte estadual prioritário v129"
        elif any(x in nk for x in ("americano de campos", "americano futebol", "americano fc", "goytacaz", "goitacaz")):
            peso = 30
            obs = "esporte campista prioritário v129"
        elif any(x in nk for x in ("campos", "norte fluminense", "sao joao", "são joão", "macae", "macaé", "porto do acu", "porto do açu", "grande rio", "baixada")):
            peso = 30
            obs = "território estratégico v129"
        else:
            peso = 22
            obs = "linha editorial positiva v129"
        canal = "Política" if any(x in nk for x in ("deputad", "alerj", "governo", "prefeit", "stf", "stj", "tse", "senado", "câmara", "camara", "mprj", "tce", "tre", "tjrj", "garotinho", "bacellar", "paes", "castro")) else "Cidades"
        if any(x in nk for x in ("flamengo", "vasco", "botafogo", "fluminense", "americano de campos", "americano futebol", "americano fc", "goytacaz", "goitacaz")):
            canal = "Esportes"
        if any(x in nk for x in ("porto", "açu", "acu", "royalties", "licita")):
            canal = "Economia"
        saida.append({"termo": termo, "peso": peso, "canal": canal, "buscar": True, "ativo": True, "observacao": obs})
    return saida

def termos_positivos_editoriais_v129() -> set[str]:
    """Retorna apenas termos salvos em Config > Termos.

    v129.12: TERMOS_BASE_V129 serve para pré-preencher arquivo ausente,
    não para forçar prioridade eterna depois que o usuário remove um termo.
    """
    termos = set()
    for item in _termos_configurados():
        termo = str(item.get("termo") or "").strip()
        if termo and item.get("ativo", True):
            termos.add(normalizar(termo))
    return {t for t in termos if t}

def analisar_texto_linha_editorial_v129(titulo: str = "", resumo: str = "", fonte: str = "", url: str = "") -> dict[str, Any]:
    """Analisa prioridade editorial com base em Config > Termos.

    v129.12: a origem do selo PRIORIDADE passa a ser exclusivamente a aba
    Config > Termos. Se o usuário remover Poder360 da aba, novas pautas não
    recebem mais PRIORIDADE:Poder360 por fallback interno.
    """
    texto_original = " ".join([titulo or "", resumo or "", fonte or "", url or ""])
    texto = normalizar(texto_original)
    if not texto:
        return {"boost": 0, "termos": [], "canal": "", "motivo": "sem_texto", "origem": "termo_config"}
    contexto_ok = any(normalizar(c) in texto for c in CONTEXTO_POLITICO_RJ_V129)
    achados: list[str] = []
    boost = 0
    canal = ""

    for item in _termos_configurados():
        if not item.get("ativo", True):
            continue
        termo = str(item.get("termo") or "").strip()
        nt = normalizar(termo)
        if not nt or nt not in texto:
            continue
        if nt in TERMOS_AMBIGUOS_V129 and not contexto_ok:
            continue
        try:
            peso = int(item.get("peso") or 18)
        except Exception:
            peso = 18
        boost += max(1, min(35, peso))
        achados.append(termo)
        if not canal and item.get("canal"):
            canal = str(item.get("canal") or "")

    if not canal:
        if any(normalizar(t) in texto for t in ["alerj", "governo", "stf", "stj", "tse", "senado", "câmara", "camara", "deputado", "prefeito", "mprj", "tce-rj"]):
            canal = "Política"
        elif any(normalizar(t) in texto for t in ["flamengo", "vasco", "botafogo", "fluminense", "americano de campos", "americano futebol", "americano fc", "goytacaz", "goitacaz"]):
            canal = "Esportes"

    boost = min(45, boost)
    return {
        "boost": boost,
        "termos": achados[:18],
        "canal": canal,
        "motivo": "termo_config_ativo" if achados else "sem_termo_config",
        "origem": "termo_config",
    }

def fonte_score_livre_v129(fonte_nome: str = "", url: str = "") -> bool:
    nome = normalizar(fonte_nome)
    host = _host(url)
    if any(n and n in nome for n in FONTES_SCORE_LIVRE_NOMES):
        return True
    if host in FONTES_SCORE_LIVRE_DOMINIOS:
        return True
    if any(host.endswith("." + d) or host == d for d in FONTES_SCORE_LIVRE_DOMINIOS):
        return True
    for f in carregar_fontes_especiais_v129():
        if not f.get("ativo", True):
            continue
        if not f.get("bypass_score", True):
            continue
        fu = str(f.get("url") or "")
        fn = normalizar(f.get("nome") or "")
        if fu and (fu.strip().lower().rstrip("/") == str(url or "").strip().lower().rstrip("/")):
            return True
        if fn and fn in nome:
            return True
    return False

def carregar_fontes_especiais_v129(criar_se_ausente: bool = False) -> list[dict[str, Any]]:
    if not ARQUIVO_FONTES_ESPECIAIS.exists():
        if criar_se_ausente:
            salvar_fontes_especiais_v129(FONTES_ESPECIAIS_PADRAO)
        return list(FONTES_ESPECIAIS_PADRAO)
    try:
        data = json.loads(ARQUIVO_FONTES_ESPECIAIS.read_text(encoding="utf-8", errors="ignore"))
        brutos = data.get("fontes", data) if isinstance(data, dict) else data
        if not isinstance(brutos, list):
            brutos = []
    except Exception:
        brutos = []
    saida = []
    vistos = set()
    for item in brutos:
        if isinstance(item, str):
            item = {"url": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        nome = str(item.get("nome") or item.get("fonte_nome") or "").strip()
        if not url:
            continue
        k = url.lower().rstrip("/")
        if k in vistos:
            continue
        vistos.add(k)
        saida.append({
            "nome": nome or _host(url) or "Fonte Especial",
            "fonte_nome": nome or _host(url) or "Fonte Especial",
            "url": url,
            "tipo": str(item.get("tipo") or item.get("tipo_fonte_config_v126") or "rss"),
            "tipo_fonte_config_v126": "especial_v129",
            "bypass_score": bool(item.get("bypass_score", True)),
            "ativo": bool(item.get("ativo", True)),
        })
    return saida or list(FONTES_ESPECIAIS_PADRAO)

def salvar_fontes_especiais_v129(fontes: list[dict[str, Any]]) -> None:
    limpas = []
    vistos = set()
    for item in fontes or []:
        if isinstance(item, str):
            item = {"url": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        k = url.lower().rstrip("/")
        if k in vistos:
            continue
        vistos.add(k)
        limpas.append({
            "nome": str(item.get("nome") or item.get("fonte_nome") or _host(url) or "Fonte Especial").strip(),
            "url": url,
            "tipo": str(item.get("tipo") or "rss").strip() or "rss",
            "bypass_score": bool(item.get("bypass_score", True)),
            "ativo": bool(item.get("ativo", True)),
        })
    payload = {
        "_versao": "v129",
        "_descricao": "Fontes especiais: coletadas em tempo real e livres do corte de score. Ainda passam por deduplicação, janela e validação técnica.",
        "fontes": limpas,
    }
    ARQUIVO_FONTES_ESPECIAIS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def fontes_especiais_para_texto_v129() -> str:
    linhas = []
    for f in carregar_fontes_especiais_v129(criar_se_ausente=True):
        nome = str(f.get("nome") or "").strip()
        url = str(f.get("url") or "").strip()
        if not url:
            continue
        linhas.append(f"{nome}|{url}" if nome else url)
    return "\n".join(linhas)

def texto_para_fontes_especiais_v129(texto: str) -> list[dict[str, Any]]:
    fontes = []
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        nome = ""
        url = linha
        if "|" in linha:
            partes = [p.strip() for p in linha.split("|")]
            if len(partes) >= 2:
                nome, url = partes[0], partes[1]
        elif " " in linha and not linha.lower().startswith(("http://", "https://")):
            # tolerância para linhas tipo: STF https://...
            m = re.search(r"(https?://\S+)", linha)
            if m:
                url = m.group(1)
                nome = linha[:m.start()].strip(" -|")
        if not url.lower().startswith(("http://", "https://")):
            continue
        fontes.append({"nome": nome or _host(url) or "Fonte Especial", "url": url, "tipo": "rss", "bypass_score": True, "ativo": True})
    return fontes
