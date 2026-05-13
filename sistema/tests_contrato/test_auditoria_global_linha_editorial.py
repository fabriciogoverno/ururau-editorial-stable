# -*- coding: utf-8 -*-
"""Testes da auditoria global da linha editorial + boilerplate.

spec_auditoria_global_linha_editorial_ururau §17-§18.
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

from ururau.editorial.validador_boilerplate import (
    limpar_boilerplate_fonte, detectar_boilerplate,
    fonte_tem_boilerplate_critico,
)
from ururau.editorial.validador_copydesk import (
    auditar_copydesk, validar_tudo_antes_de_salvar,
)
from ururau.editorial.linha_editorial_ururau import (
    build_prompt_redigir, build_prompt_copydesk,
)
from ururau.editorial.regras_editoriais_ururau import (
    TERMOS_PROIBIDOS_UNIFICADOS, detectar_termos_proibidos,
)
from ururau.editorial.validador_factual import auditar_fidelidade


# ─────────────── Fixtures com fontes contaminadas (§18) ───────────────────

def _fonte_login_topo() -> str:
    return (
        "Login\n"
        "Tudo em um so lugar para voce personalizar seu acesso\n"
        "Leia uma selecao especial\n"
        "\n"
        "A Camara aprovou na quarta-feira o projeto de seguranca. "
        "O texto segue agora para sancao do prefeito Wladimir Garotinho. "
        "Vereadores avaliam que a medida atende demanda regional antiga e "
        "que o investimento previsto e de cerca de tres milhoes de reais. "
        "A votacao terminou apos duas horas de debate no plenario municipal. "
        "Tres oposicionistas votaram contra a proposta apresentada."
    )


def _fonte_newsletter_meio() -> str:
    return (
        "A operacao policial cumpriu cinco mandados em Goytacazes na manha de "
        "quarta-feira. Um homem foi preso em flagrante por suspeita de trafico. "
        "Newsletter\n"
        "Receba no seu e-mail nossas materias mais lidas\n"
        "\n"
        "O suspeito foi conduzido para a delegacia da regiao. Material "
        "apreendido inclui balanca e embalagens. A apuracao indica que a "
        "casa funcionava como ponto de venda."
    )


def _fonte_leia_tambem() -> str:
    return (
        "A Camara aprovou a criacao da nova secretaria municipal. "
        "Leia tambem\n"
        "A votacao reuniu vinte vereadores no plenario. Apos duas horas "
        "de debate, o texto foi aprovado por dezessete votos a tres. "
        "Veja tambem\n"
        "O prefeito ja sinalizou que sancionara a lei na sexta-feira."
    )


def _fonte_publicidade_inline() -> str:
    return (
        "O time vence o classico no Maracana. Continua apos a publicidade. "
        "O jogador autor do gol marcou aos vinte e dois minutos do segundo "
        "tempo. O treinador comemorou a vitoria na entrevista coletiva."
    )


def _fonte_data_solta() -> str:
    return (
        "Atualizado em 12/05/2026 as 15h30\n"
        "Publicado em 12/05/2026\n"
        "\n"
        "A prefeitura anunciou novo programa de reforma de escolas. "
        "Serao seis unidades atendidas no primeiro semestre. O investimento "
        "previsto e de quatro milhoes de reais. As obras comecam em junho."
    )


def _fonte_legenda_misturada() -> str:
    return (
        "Foto: divulgacao\n"
        "O hospital municipal recebeu equipamentos novos para a UTI. "
        "Foram doze monitores cardiacos e seis ventiladores pulmonares. "
        "Reproducao: Secretaria de Saude\n"
        "A entrega ocorreu na manha de terca-feira na unidade central."
    )


def _fonte_acesso_personalizado() -> str:
    return (
        "Tudo em um so lugar para voce personalizar seu acesso\n"
        "Assine\n"
        "Cadastre-se\n"
        "\n"
        "A Justica determinou a soltura do suspeito em audiencia de custodia. "
        "A decisao foi tomada na tarde de segunda-feira pela 1a Vara Criminal. "
        "O homem foi preso na sexta apos investigacao da Policia Civil."
    )


def _fonte_rodape() -> str:
    return (
        "A prefeitura iniciou obras de drenagem em tres bairros. "
        "Os trabalhos vao ate o fim de julho.\n"
        "Compartilhe\n"
        "Termos de uso\n"
        "Politica de privacidade\n"
        "Cookies"
    )


def _fonte_relacionados_fim() -> str:
    return (
        "A escola municipal foi inaugurada em Campos dos Goytacazes. "
        "A unidade atendera trezentos alunos no contraturno. "
        "O prefeito participou da cerimonia.\n"
        "Relacionadas\n"
        "Materia 1\n"
        "Materia 2"
    )


def _fonte_policial_suspeita() -> str:
    return (
        "O homem e suspeito de envolvimento em assalto a banco. "
        "A apuracao indica que ele participou da acao como motorista. "
        "A Policia Civil investiga o caso e procura outros dois envolvidos. "
        "Ate o momento ninguem foi formalmente acusado pelo crime."
    )


def _fonte_politica_denuncia() -> str:
    return (
        "O vereador foi denunciado pelo Ministerio Publico por improbidade. "
        "A denuncia aponta uso indevido de verba publica em 2024. "
        "A defesa nega as acusacoes e diz que vai recorrer. "
        "A Justica ainda nao recebeu a denuncia formalmente."
    )


def _fonte_servico_horario() -> str:
    return (
        "A unidade de saude do Centro abrira em horario estendido na sabado. "
        "O atendimento sera das 8h as 17h, com vacinacao contra a dengue. "
        "Sao necessarios documento de identidade e cartao SUS. "
        "Sera priorizado o publico a partir dos 50 anos."
    )


_FIXTURES = {
    "login_topo": _fonte_login_topo,
    "newsletter_meio": _fonte_newsletter_meio,
    "leia_tambem": _fonte_leia_tambem,
    "publicidade_inline": _fonte_publicidade_inline,
    "data_solta": _fonte_data_solta,
    "legenda_misturada": _fonte_legenda_misturada,
    "acesso_personalizado": _fonte_acesso_personalizado,
    "rodape": _fonte_rodape,
    "relacionados_fim": _fonte_relacionados_fim,
    "policial_suspeita": _fonte_policial_suspeita,
    "politica_denuncia": _fonte_politica_denuncia,
    "servico_horario": _fonte_servico_horario,
}


def _pacote_bom_para(fonte: str) -> dict:
    return {
        "titulo_seo": "Camara aprova projeto em Campos dos Goytacazes",
        "subtitulo_curto": "Texto segue agora para sancao",
        "titulo_capa": "Camara aprova projeto",
        "legenda_curta": "Vereadores votaram em plenario",
        "retranca": "Politica",
        "tags": "camara, campos, politica",
        "fonte": "Camara Municipal",
        "credito_foto": "Reproducao",
        "corpo_materia": (
            "A Camara aprovou a proposta na quarta-feira.\n\n"
            "O texto segue agora para sancao do prefeito.\n\n"
            "Vereadores avaliam que a medida atende demanda regional antiga.\n\n"
            "A votacao terminou apos duas horas de debate."
        ),
    }


# ─────────────────────────── Testes principais ────────────────────────────

class TestAuditoriaGlobal(unittest.TestCase):
    def test_auditoria_global_encontra_regras_editoriais(self):
        # diagnostico carrega os modulos canonicos.
        from ururau.editorial import (
            linha_editorial_ururau, regras_editoriais_ururau,
            validador_factual, validador_seo, validador_copydesk,
            validador_boilerplate,
        )
        # arquivos canonicos existem
        self.assertTrue(Path(linha_editorial_ururau.__file__).exists())
        self.assertTrue(Path(validador_boilerplate.__file__).exists())

    def test_nao_ha_regras_duplicadas_conflitantes(self):
        # motor_gpt_spec_v2.TERMOS_PROIBIDOS delega para o canonico.
        from ururau.editorial.motor_gpt_spec_v2 import TERMOS_PROIBIDOS
        self.assertEqual(list(TERMOS_PROIBIDOS), list(TERMOS_PROIBIDOS_UNIFICADOS))


# ──────────────── Boilerplate em 12 fixtures contaminadas ─────────────────

class TestBoilerplateDeteccaoLimpeza(unittest.TestCase):
    def test_redigir_remove_boilerplate(self):
        for nome, gen in _FIXTURES.items():
            with self.subTest(fixture=nome):
                texto = gen()
                limp = limpar_boilerplate_fonte(texto)
                # Algum padrao deve ter sido removido em todas as fixtures
                # (todas tem pelo menos um trecho de lixo).
                self.assertGreaterEqual(
                    limp["chars_antes"], limp["chars_depois"],
                    f"texto deveria diminuir ou ficar igual em {nome}"
                )
                if nome in ("login_topo", "newsletter_meio", "leia_tambem",
                             "data_solta", "legenda_misturada",
                             "acesso_personalizado", "rodape",
                             "relacionados_fim"):
                    self.assertGreater(
                        limp["chars_antes"], limp["chars_depois"],
                        f"esperado remocao real em {nome}"
                    )

    def test_redigir_bloqueia_fonte_com_boilerplate(self):
        # Fonte 99% boilerplate -> critico.
        crit = (
            "Login\nCadastre-se\nAssine\nNewsletter\nReceba no seu e-mail\n"
            "Tudo em um so lugar para voce personalizar seu acesso\n"
            "Leia tambem\nVeja tambem\nCompartilhe\nCookies\n"
            "Termos de uso\nPolitica de privacidade\n"
            "Atualizado em 12/05/2026\n"
        )
        self.assertTrue(fonte_tem_boilerplate_critico(crit))

    def test_copydesk_detecta_boilerplate(self):
        # Boilerplate no corpo da materia gerada vai para pipeline.
        p = _pacote_bom_para("")
        p["corpo_materia"] += "\n\nLeia tambem\n\nCompartilhe esta materia"
        pipe = validar_tudo_antes_de_salvar(p, _fonte_login_topo())
        self.assertFalse(pipe["ok"])
        self.assertIn("BOILERPLATE_NA_MATERIA",
                      " ".join(pipe["problemas"]))


class TestPipelineFontesContaminadas(unittest.TestCase):
    def test_pipeline_aceita_pacote_limpo_com_fonte_relativamente_limpa(self):
        # Fonte com pouco boilerplate -> pacote bom passa.
        p = _pacote_bom_para("")
        pipe = validar_tudo_antes_de_salvar(p, _fonte_servico_horario())
        # texto da fonte tem pouco boilerplate -> nao critico
        self.assertEqual(
            pipe["etapas"]["fonte_limpa"]["ok"], True,
            f"fonte_limpa deveria ser True em servico_horario; pipe={pipe}"
        )

    def test_pipeline_bloqueia_fonte_majoritariamente_boilerplate(self):
        crit = (
            "Login\nCadastre-se\nAssine\nNewsletter\nReceba no seu e-mail\n"
            "Tudo em um so lugar para voce personalizar seu acesso\n"
            "Leia tambem\nVeja tambem\nCompartilhe\nCookies\n"
            "Termos de uso\nPolitica de privacidade\n"
        )
        p = _pacote_bom_para("")
        pipe = validar_tudo_antes_de_salvar(p, crit)
        self.assertFalse(pipe["ok"])
        self.assertIn("FONTE_COM_BOILERPLATE_CRITICO", pipe["problemas"])


# ──────────────── Testes editoriais (anti-alucinacao reforcados) ──────────

class TestRedigirEditorial(unittest.TestCase):
    def test_redigir_preserva_fatos_da_fonte(self):
        fonte = _fonte_login_topo()
        p = _pacote_bom_para(fonte)
        aud = auditar_fidelidade(p["corpo_materia"], fonte)
        self.assertTrue(aud["ok"], aud)

    def test_redigir_nao_inventa_data(self):
        aud = auditar_fidelidade(
            "A reuniao foi em 30/02/2030.", _fonte_servico_horario()
        )
        self.assertFalse(aud["ok"])

    def test_redigir_nao_inventa_nome(self):
        aud = auditar_fidelidade(
            "Maria Sebastiana Aparecida do Vale falou na sessao.",
            _fonte_servico_horario(),
        )
        self.assertFalse(aud["ok"])

    def test_redigir_nao_inventa_aspas(self):
        aud = auditar_fidelidade(
            'O secretario disse: "vamos privatizar todo o servico publico ja".',
            _fonte_servico_horario(),
        )
        self.assertFalse(aud["ok"])

    def test_redigir_nao_inverte_cronologia(self):
        # Se data do gerado nao esta na fonte, sinaliza.
        aud = auditar_fidelidade(
            "A votacao terminou em janeiro de 2027.", _fonte_login_topo()
        )
        self.assertFalse(aud["ok"])

    def test_redigir_tem_paragrafos_reais(self):
        p = _pacote_bom_para("")
        self.assertGreaterEqual(p["corpo_materia"].count("\n\n"), 2)

    def test_redigir_nao_aceita_paragrafo_unico(self):
        p = _pacote_bom_para("")
        p["corpo_materia"] = "Tudo num paragrafo so de bom tamanho aqui."
        from ururau.editorial.validador_seo import validar_seo_editorial
        v = validar_seo_editorial(p)
        self.assertFalse(v["ok"])

    def test_redigir_nao_aceita_termos_proibidos(self):
        p = _pacote_bom_para("")
        p["corpo_materia"] += "\n\nVale destacar que o caso reacende o debate."
        from ururau.editorial.validador_seo import validar_seo_editorial
        v = validar_seo_editorial(p)
        self.assertFalse(v["ok"])
        self.assertTrue(detectar_termos_proibidos(p["corpo_materia"]))

    def test_redigir_titulo_seo_ate_89(self):
        p = _pacote_bom_para("")
        p["titulo_seo"] = "x" * 95
        from ururau.editorial.validador_seo import validar_seo_editorial
        v = validar_seo_editorial(p)
        self.assertFalse(v["ok"])

    def test_redigir_titulo_capa_ate_60(self):
        p = _pacote_bom_para("")
        p["titulo_capa"] = "x" * 70
        from ururau.editorial.validador_seo import validar_seo_editorial
        v = validar_seo_editorial(p)
        self.assertFalse(v["ok"])

    def test_redigir_tags_separadas_por_virgula(self):
        p = _pacote_bom_para("")
        p["tags"] = "#camara #saude"
        from ururau.editorial.validador_seo import validar_seo_editorial
        v = validar_seo_editorial(p)
        self.assertFalse(v["ok"])


# ──────────────── Copydesk anti-alucinacao com fixtures ────────────────────

class TestCopydeskAntiAlucinacao(unittest.TestCase):
    def test_copydesk_detecta_data_inventada(self):
        p = _pacote_bom_para("")
        p["corpo_materia"] += "\n\nA proxima reuniao sera em 30/02/2030."
        aud = auditar_copydesk(p, _fonte_servico_horario())
        self.assertFalse(aud["copydesk_ok"])
        self.assertIn(
            "IA_INSERIU_DATA_INEXISTENTE",
            aud["subauditorias"]["factual"]["erro_tipos"],
        )

    def test_copydesk_detecta_nome_inventado(self):
        p = _pacote_bom_para("")
        p["corpo_materia"] += "\n\nMaria Sebastiana do Vale Almeida assinou."
        aud = auditar_copydesk(p, _fonte_servico_horario())
        self.assertFalse(aud["copydesk_ok"])
        self.assertIn(
            "IA_ALUCINOU_FATO_NAO_PRESENTE_NA_FONTE",
            aud["subauditorias"]["factual"]["erro_tipos"],
        )

    def test_copydesk_detecta_aspas_inventadas(self):
        p = _pacote_bom_para("")
        p["corpo_materia"] += ('\n\nO secretario disse: "vou fechar todos os '
                                'hospitais privados em uma semana".')
        aud = auditar_copydesk(p, _fonte_servico_horario())
        self.assertFalse(aud["copydesk_ok"])
        self.assertIn(
            "IA_INSERIU_ASPAS_INEXISTENTES",
            aud["subauditorias"]["factual"]["erro_tipos"],
        )

    def test_copydesk_corrige_sem_inventar(self):
        # pacote totalmente compativel com a fonte passa pelo copydesk
        aud = auditar_copydesk(_pacote_bom_para(""), _fonte_login_topo())
        self.assertTrue(aud["copydesk_ok"], aud["problemas"])

    def test_copydesk_bloqueia_se_nao_consegue_corrigir(self):
        p = _pacote_bom_para("")
        p["corpo_materia"] = (
            "A reuniao — em meio a polemica — foi em 30/02/2030. "
            "Reforca a importancia da medida."
        )
        aud = auditar_copydesk(p, _fonte_login_topo())
        self.assertFalse(aud["copydesk_ok"])
        self.assertTrue(aud["motivo_bloqueio"])


# ──────────────── Diagnostico sem duplicacao ──────────────────────────────

class TestDiagnosticoSemDuplicacao(unittest.TestCase):
    def test_diagnostico_linha_editorial_sem_duplicacao(self):
        # roda o diagnostico via import dinamico e checa as chaves novas
        import importlib.util
        path = SISTEMA / "diagnosticar_linha_editorial_ia.py"
        spec = importlib.util.spec_from_file_location("diag_ed", path)
        mod = importlib.util.module_from_spec(spec)
        from unittest import mock
        with mock.patch("builtins.print"):
            spec.loader.exec_module(mod)
            out = mod.main()
        self.assertIn("regras_duplicadas", out)
        self.assertIn("regras_conflitantes", out)
        self.assertIn("boilerplate_filter_ativo", out)
        self.assertEqual(out["regras_duplicadas"], 0)
        self.assertEqual(out["regras_conflitantes"], 0)
        self.assertTrue(out["boilerplate_filter_ativo"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
