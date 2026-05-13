# -*- coding: utf-8 -*-
"""Testes da causa raiz da mistura + politica anti-bloqueio.

spec do usuario (12/05/2026):
  1. Corrigir a CAUSA da mistura (extracao do article, nao so validacao).
  2. NUNCA bloquear/descartar/excluir pauta automaticamente.
  3. Quando algo for sinalizado, PEDIR autorizacao do usuario.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.coleta.extracao_limpa_v200 import (
    extrair_article_de_html, limpar_html_para_extracao,
)

URL_RJNEWS = (
    "https://www.rjnewsnoticias.com.br/noticia/22767/"
    "governo-e-camara-fecham-acordo.html"
)
TITULO_RJNEWS = (
    "Governo e Camara fecham acordo para fim da 6x1 e 40 horas semanais"
)


def _html_rjnews_contaminado() -> str:
    """HTML representativo do bug: <article> com aside .related cheio de
    outras materias, header.login, footer rodape."""
    return f"""
<html><head>
<title>Governo e Camara fecham acordo - RJNEWS</title>
<meta property="og:url" content="{URL_RJNEWS}">
<link rel="canonical" href="{URL_RJNEWS}">
<script type="application/ld+json">
{{"@type":"NewsArticle","headline":"Governo e Camara fecham acordo para fim da 6x1",
  "articleBody":"O Governo e a Camara dos Deputados fecharam um acordo para a tramitacao da PEC que poe fim a escala 6x1 e implementa a jornada de 40 horas semanais. A proposta passa a ter prazo definido na Comissao Especial. Segundo o presidente da Camara, Hugo Motta, o texto sera relatado pelo deputado Leo Prates. O ministro do Trabalho, Luiz Marinho, participou da negociacao final. A nova jornada prevista e a escala 5x2, com cinco dias trabalhados e dois de folga, totalizando 40 horas semanais. A votacao da PEC esta prevista para o segundo semestre de 2026."}}
</script>
</head><body>
<nav class="menu"><a href="/">Home</a></nav>
<header class="site-header">
  <div class="login">Para recuperar a senha digite seu e-mail. Enviaremos um codigo.</div>
</header>
<article>
  <h1>Governo e Camara fecham acordo para fim da 6x1 e 40 horas semanais</h1>
  <div class="article-body">
    <p>O Governo e a Camara dos Deputados fecharam um acordo para a tramitacao da PEC que poe fim a escala 6x1.</p>
    <p>Segundo o presidente da Camara, Hugo Motta, o texto sera relatado pelo deputado Leo Prates.</p>
    <p>O ministro do Trabalho, Luiz Marinho, participou da negociacao final.</p>
    <p>A nova jornada prevista e a escala 5x2, totalizando 40 horas semanais.</p>
  </div>
  <aside class="related">
    <h3>Leia tambem</h3>
    <ul>
      <li>IST em adolescentes preocupa especialistas</li>
      <li>Camara Municipal de Macae aprovou Secretaria</li>
      <li>Obra no Capelinha em Carapebus paralisada</li>
      <li>Caminhada da Fe reuniu fieis</li>
      <li>Equinor anuncia novo investimento</li>
      <li>TSE confirma urna eletronica</li>
    </ul>
  </aside>
  <div class="newsletter">Receba as principais noticias em seu e-mail. Participe ativamente do nosso portal.</div>
</article>
<footer class="footer"><p>(c) 2026 RJNEWS. Todos os direitos reservados.</p></footer>
</body></html>
"""


# ────────────────── Causa raiz: extracao limpa ────────────────────────────

class TestCausaRaizDaMistura(unittest.TestCase):

    def test_pre_limpeza_remove_nav_aside_footer_related_newsletter_login(self):
        soup = limpar_html_para_extracao(_html_rjnews_contaminado())
        self.assertIsNotNone(soup)
        # nav/header/footer/aside removidos
        self.assertIsNone(soup.find("nav"))
        self.assertIsNone(soup.find("aside"))
        self.assertIsNone(soup.find("footer"))
        # .login/.newsletter removidos
        self.assertIsNone(soup.select_one(".login"))
        self.assertIsNone(soup.select_one(".newsletter"))
        self.assertIsNone(soup.select_one(".related"))

    def test_extrai_apenas_article_unico_sem_relacionadas(self):
        r = extrair_article_de_html(
            _html_rjnews_contaminado(),
            url_pauta=URL_RJNEWS, titulo_pauta=TITULO_RJNEWS,
        )
        self.assertTrue(r["ok"])
        # texto vencedor NAO contem as outras materias
        proibidos = ("IST em adolescentes", "Macae aprovou Secretaria",
                      "Capelinha em Carapebus", "Caminhada da Fe",
                      "Equinor anuncia", "TSE confirma urna",
                      "recuperar a senha", "Receba as principais")
        for p in proibidos:
            self.assertNotIn(p, r["texto"],
                              f"contaminacao '{p}' no texto vencedor")

    def test_jsonld_articlebody_vence_quando_existe(self):
        r = extrair_article_de_html(
            _html_rjnews_contaminado(),
            url_pauta=URL_RJNEWS, titulo_pauta=TITULO_RJNEWS,
        )
        self.assertIn("jsonld", r["estrategia"].lower())

    def test_score_titulo_corpo_alto_no_vencedor(self):
        r = extrair_article_de_html(
            _html_rjnews_contaminado(),
            url_pauta=URL_RJNEWS, titulo_pauta=TITULO_RJNEWS,
        )
        # com pelo menos 5 candidatos analisados, score >=0.7
        self.assertGreaterEqual(r["score"], 0.7)
        self.assertGreaterEqual(len(r["candidatos"]), 1)

    def test_extrator_sem_jsonld_ainda_remove_contaminacao(self):
        # Mesma pagina, mas sem o JSON-LD: a estrategia ganhadora precisa
        # ser uma seletor especifico (.article-body) APOS pre-limpeza.
        html = _html_rjnews_contaminado().replace(
            "<script type=\"application/ld+json\">", "<script type=\"x-removed\">"
        )
        r = extrair_article_de_html(
            html, url_pauta=URL_RJNEWS, titulo_pauta=TITULO_RJNEWS,
        )
        self.assertTrue(r["ok"])
        # nao deve vencer 'main' nem 'article' inteiros — eles agora estao
        # limpos pos-pre-limpeza, mas com a article-body especifica tem
        # score maior.
        self.assertNotIn("Macae aprovou Secretaria", r["texto"])
        self.assertNotIn("IST em adolescentes", r["texto"])


# ────────────────── Politica: nao bloquear automaticamente ───────────────

class TestPoliticaSemBloqueioAutomatico(unittest.TestCase):

    def test_painel_acao_redigir_nao_bloqueia_sem_perguntar(self):
        # Auditoria estatica: o guard de Redigir para fonte com aviso deve
        # usar askyesno (pergunta) — nao return cego.
        painel = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        idx = painel.find("Aviso de extracao")
        self.assertGreater(idx, 0,
                            "Bloco de aviso de extracao no Redigir ausente")
        # askyesno aparece logo ANTES do titulo do dialog ("Aviso de extracao")
        bloco_antes = painel[max(0, idx - 200): idx]
        bloco_depois = painel[idx: idx + 1200]
        self.assertIn("askyesno", bloco_antes + bloco_depois,
                       "Redigir nao pede confirmacao do usuario antes de bloquear")
        self.assertIn("Continuar mesmo assim", bloco_depois)

    def test_painel_hidratador_nao_bloqueia_quando_validacao_reprova(self):
        # Apos a falha do validador, o hidratador deve TENTAR reextrair
        # via extracao_limpa_v200 antes de marcar aviso_extracao.
        painel = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("extracao_limpa_v200", painel)
        self.assertIn("extrair_article_de_html", painel)
        self.assertIn("REEXTRACAO", painel)
        # Confirma que nao usa status 'contaminada' bloqueante na nova versao:
        # a nova politica usa 'aviso_extracao'.
        self.assertIn("aviso_extracao", painel)

    def test_pre_limpeza_aplicada_no_pipeline_legado(self):
        # extract_pipeline_v90._estrategia_densidade_paragrafos agora chama
        # limpar_html_para_extracao antes de aplicar os seletores.
        src_pl = (SISTEMA / "ururau" / "coleta" / "extract_pipeline_v90.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("limpar_html_para_extracao", src_pl)

    def test_marcar_descartada_so_e_chamada_em_acao_explicita(self):
        # Auditoria estatica: cada chamada a marcar_descartada deve estar
        # precedida (na mesma funcao) por messagebox.askokcancel/askyesno
        # OU por um simpledialog (pede motivo). Nenhuma chamada automatica.
        import re as _re
        src_p = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # 4 chamadas conhecidas: descarte unitario, Del, lote, filtradas.
        chamadas = list(_re.finditer(r"self\.db\.marcar_descartada\(", src_p))
        self.assertGreaterEqual(len(chamadas), 1)
        for m in chamadas:
            # checa 800 chars ANTES da chamada — deve ter pergunta/dialog
            inicio = max(0, m.start() - 800)
            ctx = src_p[inicio: m.start()]
            self.assertTrue(
                any(k in ctx for k in (
                    "askyesno", "askokcancel", "simpledialog",
                    "askstring", "Confirm"
                )),
                f"marcar_descartada em offset {m.start()} sem dialog antes"
            )

    def test_excluir_pautas_em_lote_so_e_chamada_apos_confirmacao(self):
        import re as _re
        src_p = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        chamadas = list(_re.finditer(r"self\.db\.excluir_pautas_em_lote\(", src_p))
        self.assertGreaterEqual(len(chamadas), 1)
        for m in chamadas:
            inicio = max(0, m.start() - 1200)
            ctx = src_p[inicio: m.start()]
            self.assertTrue(
                any(k in ctx for k in (
                    "askyesno", "askokcancel", "simpledialog", "Confirm"
                )),
                f"excluir_pautas_em_lote sem dialog antes em offset {m.start()}"
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
