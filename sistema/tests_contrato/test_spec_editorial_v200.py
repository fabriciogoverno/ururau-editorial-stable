# -*- coding: utf-8 -*-
"""Suite de testes do spec_regras_editoriais_gpt4mini_ururau.md secao 52.

V200_65 (Fase 6 do plano editorial).

12 cenarios obrigatorios + utilitarios. NAO faz chamada real ao OpenAI -
testa apenas a logica dos validadores ja construidos:
  - validador_pos_gpt_v200
  - validador_apuracao_v200
  - regras_editoriais (detectar_termos_ia)
  - quality_gates (monitor_autopub_check, calculate_quality_score)
  - auditoria_factual_v81

Como rodar (Windows):
  cd C:\\Users\\fabri\\Downloads\\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL\\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL
  python -m pytest sistema\\tests_contrato\\test_spec_editorial_v200.py -v

Ou sem pytest:
  python sistema\\tests_contrato\\test_spec_editorial_v200.py
"""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path

# Garante import de sistema/ururau
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ============================================================================
# Utilitarios: materia mock
# ============================================================================

def materia_ok() -> dict:
    """Materia bem formada que deve passar em todos os gates."""
    return {
        "titulo": "Selecao Brasileira anuncia 26 convocados para Copa do Mundo",
        "titulo_seo": "Selecao Brasileira anuncia 26 convocados para Copa do Mundo 2026",
        "titulo_capa": "Selecao anuncia 26 convocados",
        "subtitulo": "Lista oficial sera divulgada nesta segunda no Rio",
        "corpo_materia": (
            "A Confederacao Brasileira de Futebol anuncia nesta segunda-feira a lista "
            "de 26 convocados para a Copa do Mundo de 2026. O evento ocorre no Museu "
            "do Amanha, no Rio de Janeiro.\n\n"
            "A relacao inclui jogadores que atuam na Europa e no Brasil. A expectativa "
            "gira em torno da presenca do atacante Neymar, do Santos.\n\n"
            "Ancelotti afirmou que tem quase todos os nomes definidos, restando apenas "
            "duas vagas para anuncio na coletiva."
        ),
        "tags": "Selecao Brasileira, Copa do Mundo 2026, Neymar, CBF, Esportes, Convocacao",
        "retranca": "Esportes",
        "meta_description": (
            "Selecao Brasileira divulga nesta segunda-feira os 26 jogadores convocados "
            "para a Copa do Mundo 2026 no Museu do Amanha, com expectativa sobre Neymar."
        ),
        "fonte": "CBF",
        "credito_foto": "Agencia Brasil",
    }


# ============================================================================
# 12 cenarios do spec sec.52
# ============================================================================

class SpecEditorialV200(unittest.TestCase):

    # ---------- TESTE 1: Fonte vazia ----------
    def test_01_fonte_vazia_bloqueia(self):
        """Sem texto-fonte util, validador apuracao deve aceitar (nada a verificar)
        mas auditoria_factual_v81 reprova por chars_uteis < 500."""
        try:
            from ururau.editorial.auditoria_factual_v81 import auditar_factualmente
        except Exception as e:
            self.skipTest(f"auditoria_factual_v81 indisponivel: {e}")
        m = materia_ok()
        r = auditar_factualmente(m, texto_fonte="")
        self.assertLess(r.get("score", 100), 90, "Fonte vazia deveria reduzir score")
        self.assertEqual(r.get("status", ""), "reprovado",
                         f"Esperado reprovado, veio {r.get('status')}")

    # ---------- TESTE 2: RSS snippet curto ----------
    def test_02_rss_snippet_bloqueia(self):
        """Snippet RSS curto (~150 chars) reprova por fonte insuficiente."""
        try:
            from ururau.editorial.auditoria_factual_v81 import auditar_factualmente
        except Exception as e:
            self.skipTest(f"auditoria_factual_v81 indisponivel: {e}")
        snippet = (
            "Selecao Brasileira anuncia 26 convocados para a Copa do Mundo 2026 "
            "em evento nesta segunda-feira no Museu do Amanha."
        )
        m = materia_ok()
        r = auditar_factualmente(m, texto_fonte=snippet)
        self.assertEqual(r.get("status"), "reprovado",
                         f"Snippet RSS deveria reprovar, veio {r.get('status')}")

    # ---------- TESTE 3: Titulo SEO acima de 89 chars ----------
    def test_03_titulo_seo_longo_bloqueia(self):
        """Titulo SEO > 89 chars deve gerar bloqueio no validador_pos_gpt."""
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        m = materia_ok()
        m["titulo_seo"] = "Titulo " + ("muito longo " * 12) + "para a Copa 2026"
        self.assertGreater(len(m["titulo_seo"]), 89)
        r = validar_pos_gpt(m)
        self.assertEqual(r["status"], "BLOQUEADO",
                         f"Esperado BLOQUEADO, veio {r['status']}. Motivos: {r.get('motivos_bloqueio')}")
        self.assertIn("limites_titulo", r.get("etapa_que_bloqueou", ""))

    # ---------- TESTE 4: Titulo de capa acima de 60 chars ----------
    def test_04_titulo_capa_longo_bloqueia(self):
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        m = materia_ok()
        m["titulo_capa"] = "Titulo de capa absurdamente extenso que deveria estourar o limite imposto"
        self.assertGreater(len(m["titulo_capa"]), 60)
        r = validar_pos_gpt(m)
        self.assertEqual(r["status"], "BLOQUEADO")

    # ---------- TESTE 5: Termo IA proibido ----------
    def test_05_termo_ia_bloqueia(self):
        """Materia com 'acende o alerta' deve bloquear no validador_pos_gpt."""
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        m = materia_ok()
        m["corpo_materia"] = m["corpo_materia"] + "\n\nO caso acende o alerta para a importancia da unidade tatica do treinador."
        r = validar_pos_gpt(m)
        self.assertEqual(r["status"], "BLOQUEADO",
                         f"Esperado BLOQUEADO por termo IA, veio {r['status']}")
        self.assertTrue(
            any("termo" in m.lower() or "termos_ia" in m.lower() for m in r["motivos_bloqueio"]),
            f"Bloqueio deveria mencionar termos_ia. Motivos: {r['motivos_bloqueio']}",
        )

    # ---------- TESTE 6: Detector de termos IA da matriz ----------
    def test_06_detector_termos_ia_lista_canonica(self):
        """detectar_termos_ia deve achar termos do spec sec.29 na matriz."""
        try:
            from ururau.editorial.regras_editoriais import (
                detectar_termos_ia, obter_termos_ia_proibidos,
            )
        except Exception as e:
            self.skipTest(f"regras_editoriais indisponivel: {e}")
        amostras = [
            "acende o alerta",
            "vale lembrar",
            "cabe destacar",
            "reforça o compromisso",
            "diante desse cenário",
        ]
        termos = [t.lower() for t in obter_termos_ia_proibidos()]
        for a in amostras:
            self.assertIn(a, termos, f"Termo {a!r} deveria estar na matriz")
        # detector deve achar quando o termo aparece
        achados = detectar_termos_ia(
            "Texto comum. O caso acende o alerta para todos. Vale lembrar do passado."
        )
        self.assertGreaterEqual(len(achados), 2,
                                f"Deveria achar acende o alerta + vale lembrar, achou {achados}")

    # ---------- TESTE 7: Travessao alerta ----------
    def test_07_travessao_alerta(self):
        """Travessao no corpo gera ALERTA (nao bloqueia, copydesk remove)."""
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        m = materia_ok()
        m["corpo_materia"] = m["corpo_materia"] + "\n\nO tecnico — que tem larga experiencia — definira a lista hoje."
        r = validar_pos_gpt(m)
        # Esperado: alerta (nao bloqueio fatal por travessao)
        self.assertTrue(
            any("travessao" in a.lower() or "—" in a for a in r["alertas"]),
            f"Esperado alerta de travessao. Alertas: {r['alertas']}",
        )

    # ---------- TESTE 8: Tags fora do limite ----------
    def test_08_tags_fora_limite(self):
        """Tags > 12 ou < 5: validador_pos_gpt sinaliza."""
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        m = materia_ok()
        m["tags"] = "Brasil"  # apenas 1 tag (abaixo de 5)
        r = validar_pos_gpt(m)
        # Tags < 5 = alerta (nao fatal). > 12 = fatal.
        self.assertTrue(
            any("tags" in a.lower() for a in r["alertas"]) or r["status"] != "APROVADO",
            f"Tags=1 deveria gerar alerta ou rascunho. Status={r['status']} Alertas={r['alertas']}",
        )

    # ---------- TESTE 9: Retranca acima do limite ----------
    def test_09_retranca_longa(self):
        """Retranca com mais de 3 palavras deve bloquear."""
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        m = materia_ok()
        m["retranca"] = "Politica Estadual Rio de Janeiro"  # 5 palavras
        r = validar_pos_gpt(m)
        self.assertEqual(r["status"], "BLOQUEADO",
                         f"Retranca de 5 palavras deveria bloquear")

    # ---------- TESTE 10: Apuracao tratada como confirmacao oficial ----------
    def test_10_apuracao_vs_oficial_bloqueia(self):
        """V200_62: fonte de apuracao + materia de confirmacao SEM atribuicao = BLOQUEIO."""
        try:
            from ururau.editorial.validador_apuracao_v200 import validar_atribuicao_apuracao
        except Exception as e:
            self.skipTest(f"validador_apuracao indisponivel: {e}")
        fonte = (
            "Ancelotti entrou em contato com Neymar nesta segunda-feira. "
            "A informacao foi divulgada por Leo Dias no Melhor da Tarde."
        )
        m = {
            "corpo_materia": (
                "Ancelotti confirmou nesta segunda-feira a convocacao de Neymar "
                "para a Copa 2026. O contato encerra as duvidas sobre o atacante."
            ),
        }
        r = validar_atribuicao_apuracao(fonte, m)
        self.assertEqual(r["status"], "BLOQUEIO",
                         f"Esperado BLOQUEIO. Veio {r['status']}. Motivo: {r.get('motivo')}")

    # ---------- TESTE 11: Apuracao COM atribuicao correta passa ----------
    def test_11_apuracao_com_atribuicao_passa(self):
        """V200_62: mesma fonte + materia com 'segundo apurou a coluna' = OK."""
        try:
            from ururau.editorial.validador_apuracao_v200 import validar_atribuicao_apuracao
        except Exception as e:
            self.skipTest(f"validador_apuracao indisponivel: {e}")
        fonte = (
            "Ancelotti entrou em contato com Neymar nesta segunda-feira. "
            "A informacao foi divulgada por Leo Dias no Melhor da Tarde."
        )
        m = {
            "corpo_materia": (
                "Segundo apurou a coluna do Leo Dias no Melhor da Tarde, Ancelotti "
                "teria entrado em contato com Neymar nesta segunda-feira. A informacao "
                "foi divulgada pelo programa de TV. A convocacao oficial sera anunciada hoje."
            ),
        }
        r = validar_atribuicao_apuracao(fonte, m)
        self.assertEqual(r["status"], "OK",
                         f"Esperado OK. Veio {r['status']}. Motivo: {r.get('motivo')}")

    # ---------- TESTE 12: Gates da matriz central ----------
    def test_12_gates_lendo_da_matriz(self):
        """V200_64: quality_gates le limites do regras_editoriais.json."""
        try:
            from ururau.editorial.quality_gates import _carregar_limites_da_matriz_v200_64
        except Exception as e:
            self.skipTest(f"quality_gates indisponivel: {e}")
        lim = _carregar_limites_da_matriz_v200_64()
        # Spec sec.37 (monitor)
        self.assertEqual(lim["score_qualidade_monitor_min"], 92)
        self.assertEqual(lim["coverage_monitor_min"], 0.90)
        self.assertEqual(lim["score_risco_max"], 10)
        # Spec sec.38 (panel)
        self.assertEqual(lim["score_qualidade_panel_min"], 90)
        self.assertEqual(lim["coverage_panel_min"], 0.85)

    # ---------- BONUS: Materia OK passa em todos os gates ----------
    def test_99_materia_ok_aprovada(self):
        """Sanidade: materia bem formada deve sair APROVADO."""
        try:
            from ururau.editorial.validador_pos_gpt_v200 import validar_pos_gpt
        except Exception as e:
            self.skipTest(f"validador_pos_gpt indisponivel: {e}")
        r = validar_pos_gpt(materia_ok())
        self.assertEqual(r["status"], "APROVADO",
                         f"Materia OK deveria aprovar. Motivos: {r.get('motivos_bloqueio')}")
        self.assertGreaterEqual(r["score_final"], 80)


# ============================================================================
# Runner standalone (sem pytest)
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
