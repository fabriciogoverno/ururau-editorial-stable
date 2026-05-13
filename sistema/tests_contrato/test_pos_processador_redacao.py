# -*- coding: utf-8 -*-
"""Testes do pos-processador de redacao (caso real do GPT-4 mini).

Spec do usuario (13/05/2026): texto repetido, titulo cortado em R$ 13
sem 'bilhoes', aspas tipograficas mal aplicadas, pontuacao quebrada.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.editorial.pos_processador_redacao import (
    aplicar_metricas_seo_google,
    deduplicar_frases_repetidas,
    corrigir_aspas_tipograficas,
    corrigir_pontuacao_solta,
    garantir_titulo_seo_completo,
    normalizar_tags,
)


# ─────────────── Fixture: o pacote real do GPT-4 mini ────────────────────

def _pacote_gpt_quebrado() -> dict:
    return {
        "titulo_seo": "Governo detalha subsídio de até R$ 0,89 por litro para gasolina e custo total de R$ 13",
        "titulo_capa": "Governo detalha subsídio de até R$ 0,89 por litro",
        "subtitulo_curto": "Ministro Bruno Moretti afirma medidas custarão R$ 13 bilhões",
        "legenda_curta": "Coletiva no Planalto na quarta-feira",
        "retranca": "Economia",
        "tags": "gasolina, subsidio, combustiveis, planalto",
        "fonte": "Giro RJ",
        "credito_foto": "Foto: Divulgação/Planalto",
        "corpo_materia": (
            "O ministro do Planejamento e Orçamento, Bruno Moretti, informou que, "
            "com o novo subsídio para gasolina anunciado pelo governo nesta quarta-feira "
            "(dia 13), o impacto das medidas implementadas pelo Executivo "
            "O ministro do Planejamento e Orçamento, Bruno Moretti, informou que, "
            "com o novo subsídio para gasolina anunciado pelo governo nesta quarta-feira "
            "(dia 13), o impacto das medidas implementadas pelo Executivo para conter a "
            "alta dos combustíveis chega a cerca de R$ 13 bilhões.\n\n"
            "Durante a entrevista coletiva realizada para a subsídio da gasolina, "
            "Moretti fez um balanço do custo das medidas que foram anunciadas até "
            "aqui pelo governo Lula em reação aos impactos da guerra no Irã. , As "
            "subvenções até aqui, todas elas juntas tem um limite de R$ 10 bilhões.\n\n"
            "A desoneração do diesel a cada mês nos custa R$ 1,7 bilhão, QAV "
            "(querosene de aviação) e biodiesel têm um valor somado de centenas de "
            "milhões."
        ),
    }


_FONTE = (
    "Bruno Moretti, ministro do Planejamento, disse na coletiva: as medidas para "
    "conter a alta dos combustiveis chegam a R$ 13 bilhoes. Subsidio de ate R$ 0,89."
)


# ─────────────────────── Funcoes isoladas ─────────────────────────────────

class TestFuncoesIsoladas(unittest.TestCase):

    def test_deduplicar_frases_repetidas_caso_real(self):
        texto = (
            "O ministro X informou que A. "
            "O ministro X informou que A. "
            "Em seguida B."
        )
        out, n = deduplicar_frases_repetidas(texto)
        # Apenas UMA das duas frases identicas sobrevive
        self.assertEqual(out.count("O ministro X informou que A"), 1, out)
        self.assertGreaterEqual(n, 1)
        self.assertIn("Em seguida B", out)

    def test_corrigir_aspas_tipograficas(self):
        s = '“teste” isso aqui ‘outro’ caso'
        out = corrigir_aspas_tipograficas(s)
        self.assertIn('"teste"', out)
        self.assertIn("'outro'", out)
        self.assertNotIn("“", out)
        self.assertNotIn("”", out)

    def test_corrigir_pontuacao_solta(self):
        s = "frase 1 , , frase 2 . . texto  com  dois espacos"
        out = corrigir_pontuacao_solta(s)
        # so uma virgula, normalizada
        self.assertNotIn(",,", out)
        self.assertNotIn(", ,", out)
        self.assertNotIn("  ", out)

    def test_titulo_seo_completa_unidade_a_partir_do_contexto(self):
        titulo = "Governo detalha subsídio de até R$ 0,89 e custo de R$ 13"
        ctx = "O custo total chega a R$ 13 bilhões segundo o ministro."
        out = garantir_titulo_seo_completo(titulo, max_chars=89, contexto_corpo=ctx)
        # 'R$ 13' isolado deve virar 'R$ 13 bilhoes'
        self.assertTrue(
            "bilhões" in out or "bilhoes" in out,
            f"titulo nao foi completado: {out!r}"
        )

    def test_titulo_seo_remove_preposicao_orfa(self):
        titulo = "Governo aprova medida de"
        out = garantir_titulo_seo_completo(titulo, max_chars=30)
        self.assertFalse(out.endswith("de"))
        self.assertEqual(out, "Governo aprova medida")

    def test_normalizar_tags_remove_hashtag(self):
        out = normalizar_tags("#camara #seguranca #campos")
        self.assertNotIn("#", out)
        self.assertIn(",", out)

    def test_normalizar_tags_preserva_virgulas(self):
        out = normalizar_tags("camara, seguranca, campos")
        self.assertEqual(out.count(","), 2)


# ─────────────────────── Pipeline completo ────────────────────────────────

class TestAplicarMetricasSEOCaseRealGPT(unittest.TestCase):
    def setUp(self):
        self.pacote = _pacote_gpt_quebrado()
        self.resultado = aplicar_metricas_seo_google(
            self.pacote, fonte_texto=_FONTE,
            palavra_chave="subsidio gasolina",
        )
        self.corrigido = self.resultado["pacote"]

    def test_remove_frase_repetida_no_lead(self):
        # corpo nao tem mais a frase duplicada
        corpo = self.corrigido["corpo_materia"]
        n_ocorrencias = corpo.count(
            "O ministro do Planejamento e Orçamento, Bruno Moretti, informou que"
        )
        self.assertLessEqual(
            n_ocorrencias, 1,
            f"frase repetida ainda aparece {n_ocorrencias}x no corpo"
        )

    def test_titulo_seo_inclui_unidade_bilhoes(self):
        t = self.corrigido["titulo_seo"]
        self.assertTrue(
            "bilhões" in t or "bilhoes" in t,
            f"titulo SEO sem 'bilhoes': {t!r}"
        )
        self.assertLessEqual(len(t), 89)

    def test_credito_foto_sem_prefixo_foto(self):
        cf = self.corrigido["credito_foto"]
        self.assertFalse(cf.lower().startswith("foto"))
        self.assertFalse(cf.lower().startswith("imagem"))

    def test_aspas_no_corpo_sao_retas(self):
        corpo = self.corrigido["corpo_materia"]
        self.assertNotIn("“", corpo)
        self.assertNotIn("”", corpo)
        self.assertNotIn("‘", corpo)
        self.assertNotIn("’", corpo)

    def test_pontuacao_sem_virgula_duplicada(self):
        corpo = self.corrigido["corpo_materia"]
        self.assertNotIn(",,", corpo)
        # ', ,' tipico do caso real
        self.assertNotIn(", ,", corpo)

    def test_correcoes_listadas_em_diagnostico(self):
        self.assertGreater(len(self.resultado["correcoes"]), 0)
        # devem ter pelo menos: dedup, normalizou_credito_foto
        corr_str = " ".join(self.resultado["correcoes"])
        self.assertIn("deduplicou", corr_str)
        self.assertIn("credito_foto", corr_str)

    def test_lead_5w_identificado_no_diagnostico(self):
        lead = self.resultado["diagnostico"]["lead_5w"]
        # quem (Bruno Moretti), quando (quarta-feira/dia 13), o_que (informou)
        self.assertTrue(lead["cobertura"]["quem"])
        self.assertTrue(lead["cobertura"]["quando"])
        self.assertTrue(lead["cobertura"]["o_que"])


# ─────────────────────── Politica anti-bloqueio ───────────────────────────

class TestNuncaDescarta(unittest.TestCase):
    def test_pos_processador_nunca_remove_campos(self):
        # mesmo com pacote 'horrivel', todos os campos sobrevivem
        p = _pacote_gpt_quebrado()
        r = aplicar_metricas_seo_google(p, fonte_texto=_FONTE)
        for k in p.keys():
            self.assertIn(k, r["pacote"], f"campo {k} desapareceu")

    def test_pos_processador_em_pacote_vazio_nao_levanta(self):
        # vazio nao deve quebrar
        r = aplicar_metricas_seo_google({}, fonte_texto="")
        self.assertIsInstance(r["pacote"], dict)
        self.assertEqual(r["correcoes"], [])

    def test_pos_processador_em_pacote_invalido_nao_levanta(self):
        r = aplicar_metricas_seo_google(None, fonte_texto="")
        self.assertIsNone(r["pacote"])
        self.assertEqual(r["correcoes"], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
