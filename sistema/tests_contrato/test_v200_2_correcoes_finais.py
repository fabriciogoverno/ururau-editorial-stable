# -*- coding: utf-8 -*-
"""Testes V200_2: correções finais de mistura, parágrafo único e blocklist."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# permite rodar standalone: python -m unittest sistema/tests_contrato/test_v200_2_correcoes_finais.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class BlocklistFontesV200Tests(unittest.TestCase):
    def test_band_mls_bloqueada(self):
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        bloq, motivo = eh_url_bloqueada(
            "https://www.band.com.br/esportes/futebol/mls-melhores-gols/rss"
        )
        self.assertTrue(bloq)
        # V200_2: agora a secao de esportes inteira do band e bloqueada
        self.assertIn("band", motivo.lower())

    def test_al_ittihad_damac_bloqueada(self):
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        bloq, _ = eh_url_bloqueada(
            "https://www.band.com.br/esportes/futebol/al-ittihad-damac-2025"
        )
        self.assertTrue(bloq)

    def test_charge_aroeira_bloqueada(self):
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        bloq, _ = eh_url_bloqueada(
            "https://exemplo.com/charge-do-aroeira/feed"
        )
        self.assertTrue(bloq)

    def test_url_normal_nao_bloqueada(self):
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        bloq, _ = eh_url_bloqueada("https://g1.globo.com/rss/g1/rj/")
        self.assertFalse(bloq)

    def test_extra_via_env(self):
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        os.environ["URURAU_V200_BLOCKLIST_EXTRA"] = "exemplo-quebrado.com/rss"
        try:
            bloq, motivo = eh_url_bloqueada(
                "https://exemplo-quebrado.com/rss/secao"
            )
            self.assertTrue(bloq)
            self.assertIn("env_extra", motivo)
        finally:
            del os.environ["URURAU_V200_BLOCKLIST_EXTRA"]

    def test_timeout_reduzido_senado(self):
        from ururau.coleta.fontes_blocklist_v200 import (
            timeout_recomendado_para_dominio,
        )
        self.assertEqual(
            timeout_recomendado_para_dominio("https://www12.senado.leg.br/rss/x"),
            8,
        )

    def test_timeout_padrao_outros(self):
        from ururau.coleta.fontes_blocklist_v200 import (
            timeout_recomendado_para_dominio,
        )
        self.assertEqual(
            timeout_recomendado_para_dominio("https://g1.globo.com/x", default=20),
            20,
        )


class TermosProibidosRemoverTests(unittest.TestCase):
    def test_remove_o_caso_evidencia(self):
        from ururau.editorial.pos_processador_redacao import remover_termos_proibidos
        texto = ("O ministro X assinou o documento. O caso evidencia que o "
                 "governo precisa avancar. A populacao aguarda.")
        out, rem = remover_termos_proibidos(texto)
        self.assertNotIn("caso evidencia", out.lower())
        self.assertTrue(rem)

    def test_remove_vale_destacar(self):
        from ururau.editorial.pos_processador_redacao import remover_termos_proibidos
        texto = "Vale destacar que a obra começa amanhã."
        out, rem = remover_termos_proibidos(texto)
        self.assertNotIn("vale destacar", out.lower())
        self.assertTrue(rem)

    def test_remove_travessao(self):
        from ururau.editorial.pos_processador_redacao import remover_termos_proibidos
        texto = "O ministro — que estava em Brasília — confirmou a obra."
        out, _ = remover_termos_proibidos(texto)
        self.assertNotIn("—", out)


class DividirParagrafoUnicoTests(unittest.TestCase):
    def test_divide_em_4_paragrafos(self):
        from ururau.editorial.pos_processador_redacao import dividir_paragrafo_unico
        # corpo grande em parágrafo único com 8 sentenças
        sentencas = [
            "Uma jovem foi atendida no posto. ",
            "O caso aconteceu na tarde de ontem. ",
            "Ela tinha pedido refeição via aplicativo. ",
            "O entregador deixou as caixas. ",
            "Ao abrir, encontrou pedras. ",
            "A defesa do consumidor foi acionada. ",
            "O aplicativo respondeu ao caso. ",
            "A investigacao continua.",
        ]
        texto = "".join(sentencas)
        out = dividir_paragrafo_unico(texto, alvo_paragrafos=4)
        pars = [p for p in out.split("\n\n") if p.strip()]
        self.assertGreaterEqual(len(pars), 2)

    def test_nao_altera_ja_bem_dividido(self):
        from ururau.editorial.pos_processador_redacao import dividir_paragrafo_unico
        texto = "Um. Dois.\n\nTres. Quatro.\n\nCinco. Seis.\n\nSete. Oito."
        out = dividir_paragrafo_unico(texto, alvo_paragrafos=4)
        self.assertEqual(out, texto)


class CorrigirCorpoMotorV2Tests(unittest.TestCase):
    def test_pipeline_completo(self):
        from ururau.editorial.pos_processador_redacao import corrigir_corpo_motor_v2
        corpo = ("O ministro confirmou a obra na sexta. O caso evidencia a "
                 "necessidade de mais investimentos. Vale destacar que o valor "
                 "passa de R$ 50 milhoes. A obra deve comecar em janeiro. "
                 "A populacao acompanha de perto.")
        out, correcoes = corrigir_corpo_motor_v2(corpo)
        self.assertNotIn("caso evidencia", out.lower())
        self.assertNotIn("vale destacar", out.lower())
        self.assertTrue(any("termos_proibidos" in c for c in correcoes))


class AuditoriaIdadeNaoReprova(unittest.TestCase):
    def test_idade_de_pessoa_nao_reprova(self):
        from ururau.editorial.auditoria_factual_v81 import auditar_factualmente
        fonte = "A jovem do bairro centro pediu uma refeição pelo aplicativo."
        materia = {
            "titulo": "Estagiária recebe pedras",
            "conteudo": ("A estagiária de 20 anos abriu a embalagem e "
                         "encontrou pedras dentro. Ela tem 20 anos e mora "
                         "no Méier."),
        }
        out = auditar_factualmente(materia, fonte)
        # 20 nao deve aparecer em claims_sem_evidencia
        claims = out.get("claims_sem_evidencia", [])
        for c in claims:
            self.assertNotIn(" 20", c)


if __name__ == "__main__":
    unittest.main()
