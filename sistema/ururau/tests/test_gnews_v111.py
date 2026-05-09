"""
Testes da integração Google News v111 / v110 teste.

Rodar:
    python -m pytest ururau/tests/test_gnews_v111.py -q

Todos os testes usam mock; não fazem acesso à internet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


class FakeIntegrado:
    def __init__(self, *args, **kwargs):
        self.aliases = {"aliases": {"porto do açu": ["porto do acu", "porto açu", "prumo logística"]}}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def coletar_por_termos_config(self, *args, **kwargs):
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "titulo": "Porto do Açu anuncia novo investimento",
                "descricao": "Resumo da pauta",
                "url": "https://exemplo.com/noticia-1",
                "dominio": "exemplo.com",
                "autor": "Redação",
                "data_publicacao": now,
                "imagem": "https://exemplo.com/foto.jpg",
                "imagens": ["https://exemplo.com/foto.jpg"],
                "texto_fonte": "Texto completo " * 150,
                "canal_sugerido": "Economia",
                "score": 91,
                "fonte_tipo": "google_news",
                "termo_busca": "Porto do Açu",
                "metodo_extracao": "trafilatura",
                "chars_fonte": 2100,
                "cidade": "São João da Barra",
                "regiao": "Norte Fluminense",
            }
        ]

    async def coletar_por_termo_livre(self, termo, max_resultados=10, janela=4):
        return await self.coletar_por_termos_config()

    async def coletar_grupo_tematico(self, grupo, max_por_grupo=5, janela=4):
        return await self.coletar_por_termos_config()

    async def extrair_fonte_completa(self, url, min_chars=1200):
        texto = "Parágrafo de teste. " * 100
        return {
            "texto": texto,
            "autor": "Redação",
            "data": datetime.now(timezone.utc).isoformat(),
            "imagens": ["https://exemplo.com/foto.jpg"],
            "metodo": "trafilatura",
            "chars": len(texto),
            "url": url,
            "suficiente": len(texto) >= min_chars,
        }

    def resolver_aliases(self, termo):
        if termo.lower() == "porto do açu":
            return ["porto do açu", "porto do acu", "porto açu", "prumo logística"]
        return [termo]

    def filtrar_janela_temporal(self, pautas, horas):
        return pautas

    def deduplicar_por_url(self, pautas):
        seen = set()
        out = []
        for p in pautas:
            if p["url"] in seen:
                continue
            seen.add(p["url"])
            out.append(p)
        return out


@pytest.fixture(autouse=True)
def patch_integrado(monkeypatch):
    import ururau.coleta.gnews_v111_integrado as mod

    monkeypatch.setattr(mod, "GoogleNewsIntegrado", FakeIntegrado)
    monkeypatch.setattr(mod, "ScraperConfig", lambda **kwargs: object())
    monkeypatch.setenv("URURAU_V111_GNEWS_JANELA_HORAS", "4")
    monkeypatch.setenv("URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO", "3")
    monkeypatch.setenv("URURAU_V111_GNEWS_MIN_CHARS_FONTE", "1200")
    yield


@pytest.mark.asyncio
async def test_coletar_pautas_gnews_v111_retorna_lista_de_dicts():
    from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111

    pautas = await coletar_pautas_gnews_v111()
    assert isinstance(pautas, list)
    assert pautas
    assert isinstance(pautas[0], dict)


@pytest.mark.asyncio
async def test_pauta_tem_campos_obrigatorios():
    from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111

    pauta = (await coletar_pautas_gnews_v111())[0]
    obrigatorios = {
        "titulo",
        "descricao",
        "url",
        "dominio",
        "autor",
        "data_publicacao",
        "imagem",
        "imagens",
        "texto_fonte",
        "canal_sugerido",
        "score",
        "fonte_tipo",
        "termo_busca",
        "metodo_extracao",
        "chars_fonte",
        "cidade",
        "regiao",
        # Campos legados exigidos pelo monitor:
        "titulo_origem",
        "link_origem",
        "resumo_origem",
        "fonte_nome",
        "canal_forcado",
        "_uid",
    }
    assert obrigatorios.issubset(set(pauta.keys()))


@pytest.mark.asyncio
async def test_score_entre_0_e_100():
    from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111

    pauta = (await coletar_pautas_gnews_v111())[0]
    assert 0 <= int(pauta["score"]) <= 100


@pytest.mark.asyncio
async def test_extrair_fonte_v111_retorna_suficiente():
    from ururau.coleta.gnews_v111_integrado import extrair_fonte_v111

    res = await extrair_fonte_v111("https://exemplo.com/noticia")
    assert isinstance(res, dict)
    assert "suficiente" in res
    assert "texto" in res
    assert "metodo" in res


def test_aliases_expandidos():
    fake = FakeIntegrado()
    aliases = fake.resolver_aliases("porto do açu")
    assert "porto do acu" in aliases
    assert "prumo logística" in aliases


def test_janela_temporal_local_filtra_antiga():
    from ururau.coleta.gnews_v111_integrado import _filtrar_janela_temporal_local

    nova = {"url": "https://a.com/1", "data_publicacao": datetime.now(timezone.utc).isoformat()}
    velha = {"url": "https://a.com/2", "data_publicacao": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()}
    out = _filtrar_janela_temporal_local([nova, velha], horas=4)
    assert nova in out
    assert velha not in out


def test_deduplicacao_remove_urls_duplicadas():
    from ururau.coleta.gnews_v111_integrado import _deduplicar_por_url_local

    pautas = [
        {"url": "https://exemplo.com/a?x=1"},
        {"url": "https://exemplo.com/a"},
        {"url": "https://exemplo.com/b"},
    ]
    out = _deduplicar_por_url_local(pautas)
    assert len(out) == 2
