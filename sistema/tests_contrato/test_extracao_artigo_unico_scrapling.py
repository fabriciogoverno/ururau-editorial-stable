# -*- coding: utf-8 -*-
"""Testes do extrator de artigo unico + detector multiassunto.

spec_scrapling_artigo_unico_sem_mistura §11.
Fixture principal: caso real RJNEWS da escala 6x1.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.coleta.extrator_artigo_unico import (
    validar_extracao_artigo_unico,
    detectar_multiassunto,
    detectar_titulos_relacionados,
    score_coerencia_titulo_corpo,
    canonical_corresponde,
    boilerplate_no_texto,
)
from ururau.editorial.validador_boilerplate import detectar_boilerplate


# ─────────────────── Fixtures: caso real RJNEWS ──────────────────────────

URL_RJNEWS = (
    "https://www.rjnewsnoticias.com.br/noticia/22767/"
    "governo-e-camara-fecham-acordo-para-fim-da-6x1-e-40-horas-semanais.html"
)
TITULO_RJNEWS = (
    "Governo e Camara fecham acordo para fim da 6x1 e 40 horas semanais"
)


def _fonte_rjnews_contaminada() -> str:
    """O texto que o usuario reportou ver no painel — agregado do site."""
    return (
        "IST em adolescentes preocupa especialistas. Casos de infeccoes "
        "sexualmente transmissiveis cresceram trinta por cento. Camara "
        "Municipal de Macae aprovou ontem o projeto que cria a Secretaria de "
        "Mobilidade. Obra no bairro Capelinha em Carapebus foi paralisada na "
        "semana passada. Caminhada da Fe reuniu mais de quinhentos fieis. "
        "Equinor Brasil anuncia novo investimento de tres bilhoes. TSE "
        "confirma uso da urna eletronica em todas as etapas do pleito. Para "
        "recuperar a senha digite seu e-mail. Enviaremos um codigo. "
        "Participe ativamente do nosso portal. Comente, de e receba likes. "
        "Marque nosso portal como fonte preferencial. Projeto de Lei 4177/19 "
        "sobre simplificacao tributaria. Simplesmente Kids estreia em junho. "
        "Filme A Versao da Lei chega aos cinemas. Receba as principais "
        "noticias em seu e-mail. © 2026 RJNEWS. Todos os direitos reservados."
    )


def _fonte_rjnews_limpa() -> str:
    """O texto correto do artigo da PEC."""
    return (
        "O Governo e a Camara dos Deputados fecharam um acordo para a tramitacao "
        "da PEC que poe fim a escala 6x1 e implementa a jornada de 40 horas "
        "semanais. A proposta passa a ter prazo definido na Comissao Especial.\n\n"
        "Segundo o presidente da Camara, Hugo Motta, o texto sera relatado "
        "pelo deputado Leo Prates. O ministro do Trabalho, Luiz Marinho, "
        "participou da negociacao final.\n\n"
        "A nova jornada prevista e a escala 5x2, com cinco dias trabalhados "
        "e dois de folga, totalizando 40 horas semanais. A mudanca atende "
        "demanda historica do movimento sindical.\n\n"
        "O acordo preve um periodo de transicao para adaptar empresas e "
        "contratos. A votacao da PEC esta prevista para o segundo semestre."
    )


def _fonte_body_inteiro_com_rodape() -> str:
    return (
        "A prefeitura inaugurou nova escola municipal em Campos. A unidade "
        "atende cem alunos no contraturno. O prefeito participou da "
        "cerimonia na manha de quarta-feira.\n\n"
        "Leia tambem\n"
        "Caminhada da Fe reune fieis no centro\n"
        "Equinor anuncia novo poco em Macae\n"
        "TSE confirma urna eletronica\n\n"
        "Para recuperar a senha digite seu e-mail\n"
        "Enviaremos um codigo\n"
        "© 2026"
    )


# ─────────────────────────────── Testes ──────────────────────────────────

class TestExtracaoArtigoUnicoRJNEWS(unittest.TestCase):

    def test_rjnews_6x1_nao_mistura_ist_macae_tse_login(self):
        """Caso real do spec: a fonte contaminada NAO pode aprovar."""
        r = validar_extracao_artigo_unico(
            _fonte_rjnews_contaminada(),
            titulo_pauta=TITULO_RJNEWS,
            url_pauta=URL_RJNEWS,
            canonical_url=URL_RJNEWS,
            og_url=URL_RJNEWS,
            estrategia="fallback_densidade",
        )
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["status"], "multiassunto")
        # padroes de portal/login devem estar entre os boilerplate detectados
        bps = set(r["boilerplate"])
        self.assertTrue({"recuperar_senha", "digite_email"} & bps,
                        f"boilerplate detectado: {bps}")

    def test_rejeita_texto_com_varios_assuntos(self):
        r = validar_extracao_artigo_unico(
            _fonte_rjnews_contaminada(),
            titulo_pauta=TITULO_RJNEWS, url_pauta=URL_RJNEWS,
        )
        self.assertTrue(r["multiassunto"])
        self.assertLess(r["score_coerencia"], 0.4)

    def test_rejeita_body_inteiro_com_login_rodape_relacionadas(self):
        r = validar_extracao_artigo_unico(
            _fonte_body_inteiro_com_rodape(),
            titulo_pauta="Prefeitura inaugura escola em Campos",
            url_pauta="https://exemplo.com/escola",
        )
        self.assertFalse(r["ok"])
        # tem login E relacionadas E rodape -> multi ou boilerplate
        self.assertIn(r["status"], {"multiassunto", "boilerplate"})

    def test_aceita_articlebody_jsonld_coerente(self):
        r = validar_extracao_artigo_unico(
            _fonte_rjnews_limpa(),
            titulo_pauta=TITULO_RJNEWS,
            url_pauta=URL_RJNEWS,
            canonical_url=URL_RJNEWS,
            og_url=URL_RJNEWS,
            estrategia="jsonld_articlebody",
        )
        self.assertTrue(r["ok"], f"motivo={r['motivo']}")
        self.assertEqual(r["status"], "ok")
        self.assertGreater(r["score_coerencia"], 0.6)

    def test_rejeita_canonical_mismatch_para_home(self):
        # canonical aponta para a home (sem path), nao para o artigo
        r = validar_extracao_artigo_unico(
            _fonte_rjnews_limpa(),
            titulo_pauta=TITULO_RJNEWS,
            url_pauta=URL_RJNEWS,
            canonical_url="https://www.rjnewsnoticias.com.br/",
            og_url="https://www.rjnewsnoticias.com.br/",
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "canonical_mismatch")

    def test_reextrai_com_estrategia_alternativa_apos_contaminacao(self):
        # primeiro: fallback de densidade entrega contaminado
        r1 = validar_extracao_artigo_unico(
            _fonte_rjnews_contaminada(), titulo_pauta=TITULO_RJNEWS,
            url_pauta=URL_RJNEWS, estrategia="fallback_densidade",
        )
        self.assertFalse(r1["ok"])
        # segunda tentativa: estrategia article-body -> texto limpo
        r2 = validar_extracao_artigo_unico(
            _fonte_rjnews_limpa(), titulo_pauta=TITULO_RJNEWS,
            url_pauta=URL_RJNEWS, canonical_url=URL_RJNEWS, og_url=URL_RJNEWS,
            estrategia="jsonld_articlebody",
        )
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["estrategia"], "jsonld_articlebody")

    def test_nao_grava_cleaned_source_text_quando_multiassunto(self):
        # POLITICA ATUALIZADA (12/05/2026): em vez de bloquear, o hidratador
        # tenta REEXTRAIR pelo HTML original (extracao_limpa_v200). Se ainda
        # falhar, marca aviso_extracao (NAO contaminada) e PRESERVA o texto.
        # Quem decide e o usuario no Redigir.
        painel = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # Estado novo deve estar presente
        self.assertIn("aviso_extracao", painel)
        # Hidratador chama o extrator limpo antes de marcar aviso
        self.assertIn("extracao_limpa_v200", painel)
        self.assertIn("extrair_article_de_html", painel)
        # E o status atual nao mais usa contaminada como bloqueio terminal
        # (o status pode existir mas o caminho passa por askyesno).
        self.assertIn("REEXTRACAO", painel)

    def test_pauta_contaminada_permanece_na_fila(self):
        # painel marca status auxiliar mas mantem a pauta utilizavel (sem
        # mudar status principal). Verificacao via grep estatico.
        painel = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # status principal nao deve virar 'descartada' nesse caminho
        bloco = painel[
            painel.find("status_fonte_v105\"] = \"contaminada\""):
            painel.find("status_fonte_v105\"] = \"contaminada\"") + 1500
        ]
        for proibido in ("descartada", "marcar_descartada(", "excluir_pauta("):
            self.assertNotIn(proibido, bloco, f"trecho proibido '{proibido}' apos contaminada")

    def test_redigir_bloqueia_fonte_contaminada_sem_descartar(self):
        # POLITICA ATUALIZADA: Redigir nao bloqueia automaticamente.
        # Em vez disso, mostra messagebox.askyesno e pede autorizacao.
        painel = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("Aviso de extracao", painel)
        self.assertIn("Continuar mesmo assim", painel)
        self.assertIn("askyesno", painel)

    def test_detecta_titulos_relacionados_no_meio_da_fonte(self):
        # texto com 3+ titulos curtos isolados intercalados
        txt = (
            "Camara aprova projeto na quarta-feira.\n\n"
            "Caminhada da Fe Reune Cinco Mil\n\n"
            "A unidade de saude reabriu na segunda. O atendimento e gratuito.\n\n"
            "Equinor Anuncia Investimento Novo\n\n"
            "TSE Confirma Urna Eletronica\n\n"
            "O prefeito visitou a obra ontem."
        )
        rels = detectar_titulos_relacionados(txt)
        self.assertGreaterEqual(len(rels), 1)

    def test_detector_multiassunto_funciona_com_assuntos_de_editorias_diferentes(self):
        r = detectar_multiassunto(
            _fonte_rjnews_contaminada(),
            titulo_pauta=TITULO_RJNEWS,
            slug_url="governo-e-camara-fecham-acordo-para-fim-da-6x1",
        )
        self.assertTrue(r["multiassunto"], r)
        self.assertLess(r["score_coerencia"], 0.4)

    def test_diagnostico_extracao_url_gera_relatorio(self):
        # roda em modo offline com texto vindo de arquivo
        import importlib.util, tempfile, os
        tmp = Path(tempfile.mkdtemp())
        fpath = tmp / "fonte.txt"
        fpath.write_text(_fonte_rjnews_limpa(), encoding="utf-8")
        # patch sys.argv e captura print
        path = SISTEMA / "diagnosticar_extracao_url.py"
        spec = importlib.util.spec_from_file_location("diag_ex", path)
        mod = importlib.util.module_from_spec(spec)
        old_argv = sys.argv[:]
        sys.argv = [
            "diagnosticar_extracao_url",
            "--url", URL_RJNEWS,
            "--titulo", TITULO_RJNEWS,
            "--canonical", URL_RJNEWS,
            "--og", URL_RJNEWS,
            "--texto-arq", str(fpath),
        ]
        out_capturada = []
        from unittest import mock
        try:
            with mock.patch("builtins.print", lambda *a, **kw: out_capturada.append(a[0] if a else "")):
                rc = spec.loader.exec_module(mod) or mod.main()
        finally:
            sys.argv = old_argv
        joined = "\n".join(str(x) for x in out_capturada)
        self.assertIn(URL_RJNEWS, joined)
        self.assertIn("score_coerencia", joined)


# ─────────────── Validadores auxiliares ──────────────────────────────────

class TestValidadoresAuxiliares(unittest.TestCase):
    def test_score_coerencia_alto_para_texto_alinhado(self):
        s = score_coerencia_titulo_corpo(
            "Camara aprova projeto de seguranca em Campos",
            "A Camara aprovou o projeto de seguranca em Campos dos Goytacazes."
            " Vereadores votaram. A medida segue para sancao."
        )
        self.assertGreater(s, 0.5)

    def test_score_coerencia_baixo_para_texto_desalinhado(self):
        s = score_coerencia_titulo_corpo(
            "Camara aprova fim da escala 6x1 na PEC do governo",
            "IST em adolescentes preocupa. Caminhada da Fe reune fieis. "
            "TSE confirma urna eletronica."
        )
        self.assertLess(s, 0.4)

    def test_canonical_corresponde_tolera_amp_e_www(self):
        r = canonical_corresponde(
            "https://www.rjnewsnoticias.com.br/noticia/22767/x.html",
            canonical_url="https://rjnewsnoticias.com.br/noticia/22767/x",
            og_url="https://rjnewsnoticias.com.br/amp/noticia/22767/x.html",
        )
        self.assertTrue(r["ok"], r)

    def test_canonical_corresponde_rejeita_home(self):
        r = canonical_corresponde(
            "https://rjnewsnoticias.com.br/noticia/22767/x.html",
            canonical_url="https://rjnewsnoticias.com.br/",
        )
        self.assertFalse(r["ok"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
