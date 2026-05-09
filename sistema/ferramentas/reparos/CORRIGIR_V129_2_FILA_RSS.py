# -*- coding: utf-8 -*-
"""
CORRIGIR_V129_2_FILA_RSS.py

Correção automática v129.2:
1) restaura Fontes RSS caso a v129.1 tenha deixado apenas o fallback de 4 fontes;
2) remove das Fontes RSS apenas as fontes que estão exatamente em Fontes Especiais;
3) apaga __pycache__ para forçar o Python a usar o painel.py corrigido;
4) não mexe em coleta, IA, hidratação, publicação nem WhatsApp.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent

FONTES_RSS_COMPLETAS_V127 = [
  {
    "url": "https://mancheterj.com/portal/feed/",
    "nome": "Manchete RJ",
    "canal_forcado": "",
    "ativo": True
  },
  {
    "url": "https://campos.rj.gov.br/rss",
    "nome": "Prefeitura de Campos",
    "canal_forcado": "",
    "ativo": True
  },
  {
    "url": "https://campos24horas.com.br/portal/feed/",
    "nome": "Campos 24 Horas",
    "canal_forcado": "",
    "ativo": True
  },
  {
    "url": "https://j3news.com/feed/",
    "nome": "J3 News",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 1,
    "max_por_link": 5
  },
  {
    "url": "https://www.portalviu.com.br/feed",
    "nome": "Portal Viu",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 2,
    "max_por_link": 5
  },
  {
    "url": "https://sfnoticias.com.br/feed",
    "nome": "SF Notícias",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 3,
    "max_por_link": 5
  },
  {
    "url": "https://odebateon.com.br/feed/",
    "nome": "O Debate",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 4,
    "max_por_link": 5
  },
  {
    "url": "https://cliquediario.com.br/feed",
    "nome": "Clique Diário",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 5,
    "max_por_link": 5
  },
  {
    "url": "https://parahybano.com.br/feed/",
    "nome": "O Parahybano",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 6,
    "max_por_link": 5
  },
  {
    "url": "https://rjnewsnoticias.com.br/feed/",
    "nome": "RJ News Notícias",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 7,
    "max_por_link": 5
  },
  {
    "url": "https://www.jornaldesabado.com.br/feed/",
    "nome": "Jornal de Sábado",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 8,
    "max_por_link": 5
  },
  {
    "url": "https://prensadebabel.com.br/feed/",
    "nome": "Prensa de Babel",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 9,
    "max_por_link": 5
  },
  {
    "url": "https://agendadopoder.com.br/feed/",
    "nome": "Agenda do Poder",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 10,
    "max_por_link": 5
  },
  {
    "url": "https://diariodorio.com/feed/",
    "nome": "Diário do Rio",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 11,
    "max_por_link": 5
  },
  {
    "url": "https://girorj.com.br/feed/",
    "nome": "Giro RJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 12,
    "max_por_link": 5
  },
  {
    "url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
    "nome": "Agência Brasil",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 13,
    "max_por_link": 5
  },
  {
    "url": "https://g1.globo.com/rss/g1/politica/",
    "nome": "G1 Política",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 14,
    "max_por_link": 5
  },
  {
    "url": "https://admin.cnnbrasil.com.br/feed/",
    "nome": "CNN Brasil",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 15,
    "max_por_link": 5
  },
  {
    "url": "https://feeds.folha.uol.com.br/poder/rss091.xml",
    "nome": "Folha Poder",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 16,
    "max_por_link": 5
  },
  {
    "url": "https://www.uol.com.br/vueland/api/?loadComponent=XmlFeedRss",
    "nome": "UOL",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 17,
    "max_por_link": 5
  },
  {
    "url": "https://www12.senado.leg.br/noticias/rss.xml",
    "nome": "Senado",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 18,
    "max_por_link": 5
  },
  {
    "url": "https://noticias.stf.jus.br/feed/",
    "nome": "STF",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 19,
    "max_por_link": 5
  },
  {
    "url": "https://res.stj.jus.br/hrestp-c-portalp/RSS.xml",
    "nome": "STJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 20,
    "max_por_link": 5
  },
  {
    "url": "https://www.tse.jus.br/rss",
    "nome": "TSE",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 21,
    "max_por_link": 5
  },
  {
    "url": "https://www.rj.gov.br/noticias/rss",
    "nome": "Governo RJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 22,
    "max_por_link": 5
  },
  {
    "url": "https://www.mprj.mp.br/rss",
    "nome": "MPRJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 23,
    "max_por_link": 5
  },
  {
    "url": "https://www.poder360.com.br/feed/",
    "nome": "Poder360",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 24,
    "max_por_link": 5
  },
  {
    "url": "https://odia.ig.com.br/rss.xml",
    "nome": "O Dia",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 25,
    "max_por_link": 5
  },
  {
    "url": "https://rss.bs.vibra.digital/feed.xml?site=portal&size=10",
    "nome": "Band",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 26,
    "max_por_link": 5
  },
  {
    "url": "https://www.tre-rj.jus.br/comunicacao/noticias/RSS",
    "nome": "TRE-RJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 27,
    "max_por_link": 5
  },
  {
    "url": "https://www.metropoles.com/feed",
    "nome": "Metrópoles",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 28,
    "max_por_link": 5
  },
  {
    "url": "https://mancheterio.com.br/feed/",
    "nome": "Manchete Rio",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 31,
    "max_por_link": 5
  },
  {
    "url": "https://www.camara.leg.br/rss/noticias.xml",
    "nome": "Câmara",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 32,
    "max_por_link": 5
  },
  {
    "url": "https://www.gov.br/rss.xml",
    "nome": "Gov.br",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 33,
    "max_por_link": 5
  },
  {
    "url": "https://www.alerj.rj.gov.br/Noticias/rss",
    "nome": "Governo RJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 34,
    "max_por_link": 5
  },
  {
    "url": "https://www.tjrj.jus.br/web/guest/home/-/noticias/rss",
    "nome": "TJRJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 35,
    "max_por_link": 5
  },
  {
    "url": "https://defensoria.rj.def.br/rss/noticias",
    "nome": "Defensoria RJ",
    "canal_forcado": "",
    "ativo": True,
    "tipo_coleta": "rss",
    "ordem": 36,
    "max_por_link": 5
  }
]

def _norm_url(u: str) -> str:
    return str(u or "").strip().lower().rstrip("/")

def _norm_nome(n: str) -> str:
    n = unicodedata.normalize("NFKD", str(n or ""))
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", n.lower()).strip()

def _carregar_especiais() -> list[dict]:
    caminhos = [
        BASE / "fontes_especiais_v129.json",
        BASE / "configuracoes" / "fontes_especiais_v129.json",
    ]
    for p in caminhos:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("fontes", []) or []
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f"[v129.2][reparo] aviso: falha ao ler {p}: {e}")
    return []

def _filtrar_sem_especiais(fontes: list[dict], especiais: list[dict]) -> tuple[list[dict], list[dict]]:
    urls = {_norm_url(e.get("url")) for e in especiais if e.get("url")}
    nomes = {_norm_nome(e.get("nome") or e.get("fonte_nome")) for e in especiais if (e.get("nome") or e.get("fonte_nome"))}
    limpas, removidas = [], []
    for f in fontes:
        u = _norm_url(f.get("url"))
        n = _norm_nome(f.get("nome") or f.get("fonte_nome"))
        if (u and u in urls) or (n and n in nomes):
            removidas.append(f)
        else:
            limpas.append(f)
    return limpas, removidas

def _ler_lista(p: Path) -> list[dict]:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _precisa_reparar(p: Path, especiais: list[dict]) -> bool:
    data = _ler_lista(p)
    if len(data) <= 4:
        return True
    _, removidas = _filtrar_sem_especiais(data, especiais)
    return bool(removidas)

def main() -> int:
    especiais = _carregar_especiais()
    fontes, removidas = _filtrar_sem_especiais(FONTES_RSS_COMPLETAS_V127, especiais)
    caminhos = [
        BASE / "fontes_rss.json",
        BASE / "configuracoes" / "fontes_rss.json",
        BASE / "config" / "fontes_rss.json",
    ]
    alterados = 0
    for p in caminhos:
        p.parent.mkdir(parents=True, exist_ok=True)
        if _precisa_reparar(p, especiais):
            p.write_text(json.dumps(fontes, ensure_ascii=False, indent=2), encoding="utf-8")
            alterados += 1
            print(f"[v129.2][reparo] {p.name} restaurado: {len(fontes)} RSS comuns; {len(removidas)} especiais fora do RSS.")
        else:
            print(f"[v129.2][reparo] {p.name} preservado.")
    for pyc in [BASE / "ururau" / "ui" / "__pycache__", BASE / "ururau" / "coleta" / "__pycache__"]:
        if pyc.exists():
            shutil.rmtree(pyc, ignore_errors=True)
            print(f"[v129.2][reparo] cache removido: {pyc}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
