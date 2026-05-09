"""Testes para monitor_v111_ciclo_combinado.py (mockado)."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


class MockPauta:
    @staticmethod
    def criar(titulo="Titulo", url="https://ex.com/a", score=70, grupo="alerj", data="2026-04-30T10:00:00+00:00", texto="Texto...", chars=1500):
        return {"titulo": titulo, "url": url, "descricao": "Resumo", "dominio": "ex.com", "autor": "Autor", "data_publicacao": data, "imagem": "", "imagens": [], "texto_fonte": texto, "canal_sugerido": "Politica", "score": score, "fonte_tipo": "google_news", "termo_busca": "ALERJ", "grupo_tematico": grupo, "metodo_extracao": "trafilatura", "chars_fonte": chars, "cidade": "RJ", "regiao": "RJ"}


class TestDeduplicacao:
    def test_mantem_maior_score(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _deduplicar_mantendo_maior_score
        pautas = [MockPauta.criar(url="https://ex.com/art", score=50), MockPauta.criar(url="https://ex.com/art", score=90)]
        r = _deduplicar_mantendo_maior_score(pautas)
        assert len(r) == 1 and r[0]["score"] == 90

    def test_diferentes_urls(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _deduplicar_mantendo_maior_score
        pautas = [MockPauta.criar(url="https://ex.com/a", score=50), MockPauta.criar(url="https://ex.com/b", score=60)]
        r = _deduplicar_mantendo_maior_score(pautas)
        assert len(r) == 2

    def test_url_vazia_removida(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _deduplicar_mantendo_maior_score
        r = _deduplicar_mantendo_maior_score([MockPauta.criar(url="", score=50), MockPauta.criar(url="https://ex.com/a", score=60)])
        assert len(r) == 1


class TestFiltroTemporal:
    def test_dentro_janela(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _filtrar_janela_temporal
        agora = datetime.now(timezone.utc).isoformat()
        assert len(_filtrar_janela_temporal([MockPauta.criar(data=agora)], 4)) == 1

    def test_fora_janela(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _filtrar_janela_temporal
        assert len(_filtrar_janela_temporal([MockPauta.criar(data="2020-01-01T00:00:00+00:00")], 4)) == 0

    def test_sem_data_mantem(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _filtrar_janela_temporal
        p = MockPauta.criar(); p["data_publicacao"] = ""
        assert len(_filtrar_janela_temporal([p], 4)) == 1


class TestCamposLegados:
    def test_preenche_faltando(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _garantir_campos_legados
        p = {"titulo": "N", "url": "https://ex.com"}
        _garantir_campos_legados(p)
        assert p["titulo_origem"] == "N"
        assert p["link_origem"] == "https://ex.com"
        assert p["cleaned_source_text"] == ""
        assert p["dossie"] == {}

    def test_nao_sobrescreve(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _garantir_campos_legados
        p = {"titulo_origem": "Ja", "titulo": "N"}
        _garantir_campos_legados(p)
        assert p["titulo_origem"] == "Ja"


class TestNormalizarUrl:
    def test_www_removido(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _normalizar_url_para_chave
        assert _normalizar_url_para_chave("https://www.ex.com/art") == "ex.com/art"

    def test_query_removido(self):
        from ururau.publisher.monitor_v111_ciclo_combinado import _normalizar_url_para_chave
        assert _normalizar_url_para_chave("https://ex.com/art?utm=1") == "ex.com/art"


@pytest.mark.asyncio
async def test_ciclo_combinado_mockado():
    from ururau.publisher.monitor_v111_ciclo_combinado import coletar_ciclo_combinado_v111
    with patch("ururau.publisher.monitor_v111_ciclo_combinado.coletar_pautas_gnews_v111") as m:
        m.return_value = [MockPauta.criar(url="https://ex.com/1", score=80), MockPauta.criar(url="https://ex.com/2", score=75)]
        pautas = await coletar_ciclo_combinado_v111(grupos_ativos=["alerj"], max_por_grupo=2, max_total=10)
    assert isinstance(pautas, list)
    assert len(pautas) <= 10
    for p in pautas:
        assert "titulo" in p
        assert "url" in p
        assert p.get("score", 0) >= 65


@pytest.mark.asyncio
async def test_dry_run():
    from ururau.publisher.monitor_v111_ciclo_combinado import coletar_ciclo_combinado_dry_run
    with patch("ururau.publisher.monitor_v111_ciclo_combinado.coletar_pautas_gnews_v111") as m:
        m.return_value = [MockPauta.criar(url="https://ex.com/1", score=70)]
        pautas = await coletar_ciclo_combinado_dry_run(grupos_ativos=["alerj"])
    assert isinstance(pautas, list)
    assert len(pautas) <= 10
