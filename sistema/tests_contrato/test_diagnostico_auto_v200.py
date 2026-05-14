# -*- coding: utf-8 -*-
"""Testes V200_2: diagnostico de fonte integrado (lote + auto-cura)."""
from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class EnumerarFontesTests(unittest.TestCase):
    def test_modulo_importa(self):
        from ururau.coleta import diagnostico_auto_v200 as m
        self.assertTrue(hasattr(m, "enumerar_fontes_configuradas"))
        self.assertTrue(hasattr(m, "diagnosticar_todas_as_fontes"))
        self.assertTrue(hasattr(m, "auto_curar_fonte_v200"))
        self.assertTrue(hasattr(m, "limpar_cache_autocura"))

    def test_enumerar_devolve_lista(self):
        from ururau.coleta.diagnostico_auto_v200 import enumerar_fontes_configuradas
        fontes = enumerar_fontes_configuradas()
        self.assertIsInstance(fontes, list)
        for f in fontes:
            self.assertIn("url", f)
            self.assertIn("nome", f)
            self.assertIn("grupo", f)

    def test_enumerar_dedup_por_dominio(self):
        from ururau.coleta.diagnostico_auto_v200 import (
            enumerar_fontes_configuradas, _dominio,
        )
        fontes = enumerar_fontes_configuradas()
        dominios = [_dominio(f["url"]) for f in fontes]
        self.assertEqual(len(dominios), len(set(dominios)),
                         "ha dominios duplicados na enumeracao")


class DominioHelperTests(unittest.TestCase):
    def test_remove_www(self):
        from ururau.coleta.diagnostico_auto_v200 import _dominio
        self.assertEqual(_dominio("https://www.exemplo.com.br/feed/"), "exemplo.com.br")

    def test_sem_www(self):
        from ururau.coleta.diagnostico_auto_v200 import _dominio
        self.assertEqual(_dominio("https://girorj.com.br/x"), "girorj.com.br")


class AutoCuraCacheTests(unittest.TestCase):
    def test_autocura_desativada_por_env(self):
        from ururau.coleta.diagnostico_auto_v200 import (
            auto_curar_fonte_v200, limpar_cache_autocura,
        )
        limpar_cache_autocura()
        os.environ["URURAU_V200_AUTOCURA_COLETA"] = "0"
        try:
            r = auto_curar_fonte_v200("https://exemplo-x.com/feed")
            self.assertFalse(r["ok"])
            self.assertIn("desativada", r["motivo"])
        finally:
            os.environ.pop("URURAU_V200_AUTOCURA_COLETA", None)

    def test_limpar_cache_nao_quebra(self):
        from ururau.coleta.diagnostico_auto_v200 import limpar_cache_autocura
        limpar_cache_autocura()
        limpar_cache_autocura()


class DiagnosticarTodasComFixtureTests(unittest.TestCase):
    """Testa o batch runner com fixture controlado, sem rede real."""

    def test_batch_com_zero_fontes(self):
        from ururau.coleta import diagnostico_auto_v200 as m
        orig = m.enumerar_fontes_configuradas
        m.enumerar_fontes_configuradas = lambda: []
        try:
            resumo = m.diagnosticar_todas_as_fontes()
            self.assertEqual(resumo["total"], 0)
            self.assertEqual(resumo["funcionais"], 0)
            self.assertEqual(resumo["precisam_atencao"], 0)
            self.assertIn("relatorio_txt", resumo)
        finally:
            m.enumerar_fontes_configuradas = orig

    def test_batch_sinaliza_fonte_morta_sem_desativar(self):
        from ururau.coleta import diagnostico_auto_v200 as m
        orig_enum = m.enumerar_fontes_configuradas
        orig_diag = m.diagnosticar_e_aplicar_uma
        m.enumerar_fontes_configuradas = lambda: [
            {"url": "https://fonte-morta.test/feed", "nome": "Morta",
             "grupo": "RSS", "ativo": True},
        ]
        m.diagnosticar_e_aplicar_uma = lambda url, nome="", grupo="", **kw: {
            "url": url, "nome": nome, "grupo": grupo, "dominio": "fonte-morta.test",
            "ok": False, "aplicado": False, "estrategia": "-",
            "status": "falhou", "feeds": [], "motivo": "nenhuma estrategia funcionou",
            "avisos": [],
        }
        try:
            resumo = m.diagnosticar_todas_as_fontes()
            self.assertEqual(resumo["total"], 1)
            self.assertEqual(resumo["funcionais"], 0)
            self.assertEqual(resumo["precisam_atencao"], 1)
            txt = resumo["relatorio_txt"].lower()
            self.assertIn("sinalizar", txt)
            self.assertIn("nada foi desativado", txt)
            self.assertNotIn("fonte desativada", txt)
            self.assertNotIn("despriorizad", txt)
        finally:
            m.enumerar_fontes_configuradas = orig_enum
            m.diagnosticar_e_aplicar_uma = orig_diag

    def test_batch_conta_funcionais(self):
        from ururau.coleta import diagnostico_auto_v200 as m
        orig_enum = m.enumerar_fontes_configuradas
        orig_diag = m.diagnosticar_e_aplicar_uma
        m.enumerar_fontes_configuradas = lambda: [
            {"url": "https://ok1.test/feed", "nome": "OK1", "grupo": "RSS", "ativo": True},
            {"url": "https://ok2.test/feed", "nome": "OK2", "grupo": "RSS", "ativo": True},
        ]
        m.diagnosticar_e_aplicar_uma = lambda url, nome="", grupo="", **kw: {
            "url": url, "nome": nome, "grupo": grupo, "dominio": url,
            "ok": True, "aplicado": True, "estrategia": "rss",
            "status": "funcional_com_pauta", "feeds": [url], "motivo": "ok",
            "avisos": [],
        }
        try:
            resumo = m.diagnosticar_todas_as_fontes()
            self.assertEqual(resumo["total"], 2)
            self.assertEqual(resumo["funcionais"], 2)
            self.assertEqual(resumo["aplicados"], 2)
            self.assertEqual(resumo["precisam_atencao"], 0)
        finally:
            m.enumerar_fontes_configuradas = orig_enum
            m.diagnosticar_e_aplicar_uma = orig_diag


class CLIExisteTests(unittest.TestCase):
    def test_cli_existe_e_compila(self):
        cli = ROOT / "diagnosticar_todas_fontes_v200.py"
        self.assertTrue(cli.exists())
        ast.parse(cli.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
