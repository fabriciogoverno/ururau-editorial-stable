# -*- coding: utf-8 -*-
"""Testes de contrato para IA real e regras editoriais.

spec_claudio_ia_real_gpt4mini_regras_editoriais §16.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.ia import ia_service
from ururau.ia import regras_editoriais_validador as REV


def _instalar_openai_fake(modelo: str = "gpt-4.1-mini", request_id: str = "resp_x",
                          conteudo: dict | None = None):
    """Injeta um modulo fake `openai` em sys.modules para testes sem o SDK.

    Retorna o MagicMock OpenAI() instalado, ja configurado para devolver
    `conteudo` como JSON na chave choices[0].message.content.
    """
    import sys, json as _json
    fake_openai = mock.MagicMock()
    fake_resp = mock.MagicMock()
    fake_resp.id = request_id
    fake_resp.model = modelo
    fake_resp.choices = [mock.MagicMock()]
    fake_resp.choices[0].message.content = _json.dumps(conteudo or {
        "titulo_seo": "Titulo seo de teste com tamanho razoavel ok",
        "subtitulo_curto": "Subtitulo objetivo",
        "titulo_capa": "Titulo de capa teste",
        "legenda_curta": "Legenda factual",
        "retranca": "Policia",
        "tags": "policia, campos, seguranca",
        "fonte": "Fonte Teste",
        "credito_foto": "Reproducao",
        "corpo_materia": "Paragrafo 1.\n\nParagrafo 2.\n\nParagrafo 3.\n\nParagrafo 4.",
    })
    fake_client = mock.MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp
    fake_openai.OpenAI.return_value = fake_client
    sys.modules["openai"] = fake_openai
    return fake_openai, fake_client


def _desinstalar_openai_fake():
    import sys
    sys.modules.pop("openai", None)




# ──────────────────────────── ia_service ────────────────────────────────
class TestIaServiceContratoRetorno(unittest.TestCase):
    def setUp(self):
        # garante chave ausente para nao chamar OpenAI de verdade
        self._keys = {
            k: os.environ.pop(k, None)
            for k in ("OPENAI_API_KEY", "OPENAI_MODEL", "MODELO_OPENAI")
        }

    def tearDown(self):
        for k, v in self._keys.items():
            if v is not None:
                os.environ[k] = v

    def test_ia_service_retorna_ia_chamada(self):
        # Sem chave: ia_chamada=False, mas o contrato de retorno e estavel.
        res = ia_service.executar_ia_redigir({"uid": "t1"}, "x" * 1000)
        for k in ("ok", "ia_chamada", "modelo", "endpoint", "request_id",
                  "response_id", "prompt_chars", "resposta_chars",
                  "erro_tipo", "erro_msg", "conteudo", "fallback_sem_ia",
                  "publicar_bloqueado", "acao"):
            self.assertIn(k, res, f"campo {k} ausente")
        self.assertFalse(res["ia_chamada"])
        self.assertEqual(res["erro_tipo"], "credencial_ausente")

    def test_ia_service_redige_chave(self):
        os.environ["OPENAI_API_KEY"] = "sk-test-abcdefghij1234567890"
        importlib.reload(ia_service)
        diag = ia_service.diagnosticar_ia()
        # Nunca a chave completa.
        self.assertNotIn("sk-test-abcdefghij1234567890", json.dumps(diag))
        self.assertIn("...", diag["api_key_redacted"])

    def test_redigir_nao_conclui_sem_ia(self):
        # Quando OPENAI_API_KEY ausente, executar_ia_redigir nao deve marcar ok=True.
        importlib.reload(ia_service)
        res = ia_service.executar_ia_redigir({"uid": "t2"}, "fonte " * 200)
        self.assertFalse(res["ok"])
        self.assertFalse(res["ia_chamada"])
        self.assertTrue(res["publicar_bloqueado"])

    def test_redigir_chama_ia_real(self):
        # Simula chamada real bem-sucedida injetando modulo openai fake.
        os.environ["OPENAI_API_KEY"] = "sk-test-abc1234567890def"
        importlib.reload(ia_service)
        _instalar_openai_fake(modelo="gpt-4.1-mini", request_id="resp_123")
        try:
            res = ia_service.executar_ia_redigir({"uid": "tr"}, "fonte real " * 200)
        finally:
            _desinstalar_openai_fake()
        self.assertTrue(res["ia_chamada"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["modelo"], "gpt-4.1-mini")
        self.assertEqual(res["request_id"], "resp_123")
        self.assertFalse(res["publicar_bloqueado"])

    def test_copydesk_chama_ia_real(self):
        os.environ["OPENAI_API_KEY"] = "sk-test-abc1234567890def"
        importlib.reload(ia_service)
        _instalar_openai_fake(modelo="gpt-4.1-mini", request_id="cd_123")
        try:
            res = ia_service.executar_ia_copydesk({"corpo_materia": "..."})
        finally:
            _desinstalar_openai_fake()
        self.assertTrue(res["ia_chamada"])
        self.assertEqual(res["acao"], "copydesk")

    def test_copydesk_nao_conclui_sem_ia(self):
        for k in ("OPENAI_API_KEY",):
            os.environ.pop(k, None)
        importlib.reload(ia_service)
        res = ia_service.executar_ia_copydesk({"corpo_materia": "x"})
        self.assertFalse(res["ia_chamada"])
        self.assertTrue(res["publicar_bloqueado"])

    def test_redigir_nao_salva_fallback_como_final(self):
        importlib.reload(ia_service)
        # publicar_bloqueado=True quando ia_chamada=False, ent
        res = ia_service.executar_ia_redigir({"uid": "fb"}, "x" * 700)
        self.assertTrue(res["publicar_bloqueado"])
        self.assertFalse(res["ia_chamada"])

    def test_redigir_mensagem_informa_modelo(self):
        # O codigo do painel deve mencionar o modelo na mensagem de sucesso.
        painel = (SISTEMA / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("Redacao concluida com IA", painel)
        self.assertIn("Modelo:", painel)
        # E nao deve mais ter a mensagem antiga.
        self.assertNotIn("Materia gerada com fonte validada antes da IA", painel)


# ──────────────────────────── prompts ──────────────────────────────────
class TestPromptsObrigatorios(unittest.TestCase):
    def test_prompt_contem_regras_editoriais(self):
        # Agora o prompt e montado por linha_editorial_ururau.build_prompt_redigir.
        # Verifica chaves estaveis da nova base.
        prompt = ia_service._build_prompt_sistema(pauta={"titulo_origem":"x"}, fonte_texto="x")
        for chave in ("nao invente", "investiga", "titulo_seo", "JSON",
                       "termos proibidos", "anti-alucinacao"):
            self.assertIn(chave.lower(), prompt.lower(),
                          f"prompt nao menciona regra: {chave}")

    def test_prompt_exige_json_obrigatorio(self):
        prompt = ia_service._build_prompt_sistema()
        for chave in REV.CAMPOS_OBRIGATORIOS:
            self.assertIn(chave, prompt, f"prompt nao cita campo {chave}")


# ──────────────────────────── validador editorial ──────────────────────
def _pacote_ok() -> dict:
    return {
        "titulo_seo": "Camara aprova projeto de seguranca em Campos dos Goytacazes",
        "subtitulo_curto": "Texto agora segue para sancao",
        "titulo_capa": "Camara aprova seguranca em Campos",
        "legenda_curta": "Vereadores votaram em plenario",
        "retranca": "Politica",
        "tags": "camara, seguranca, campos",
        "fonte": "NF Noticias",
        "credito_foto": "Reproducao",
        "corpo_materia": (
            "A Camara aprovou na quarta-feira um projeto sobre seguranca "
            "publica em Campos.\n\n"
            "A votacao terminou apos duas horas de debate no plenario.\n\n"
            "O texto segue agora para sancao do prefeito.\n\n"
            "Vereadores avaliam que a medida atende uma demanda regional."
        ),
    }


class TestValidadorEditorial(unittest.TestCase):
    def test_validador_titulo_seo_89(self):
        p = _pacote_ok()
        p["titulo_seo"] = "x" * 95
        r = REV.validar_pacote_editorial(p)
        self.assertFalse(r["ok"])
        self.assertTrue(any("titulo_seo_excede" in e for e in r["erros"]))

    def test_validador_titulo_capa_60(self):
        p = _pacote_ok()
        p["titulo_capa"] = "x" * 70
        r = REV.validar_pacote_editorial(p)
        self.assertFalse(r["ok"])
        self.assertTrue(any("titulo_capa_excede" in e for e in r["erros"]))

    def test_validador_retranca_1_a_3_palavras(self):
        for retranca, esperado_ok in [
            ("Policia", True),
            ("Policia federal", True),
            ("Policia federal Campos", True),
            ("", False),
            ("Policia federal Campos Goytacazes", False),
        ]:
            p = _pacote_ok()
            p["retranca"] = retranca
            r = REV.validar_pacote_editorial(p)
            if esperado_ok:
                self.assertNotIn(
                    "retranca_fora_1_a_3_palavras:" + str(len(retranca.split())),
                    " ".join(r["erros"])
                )
            else:
                self.assertTrue(any("retranca" in e for e in r["erros"]),
                                f"retranca '{retranca}' deveria falhar")

    def test_validador_minimo_4_paragrafos(self):
        p = _pacote_ok()
        p["corpo_materia"] = "so um paragrafo curto\n\noutro paragrafo"
        r = REV.validar_pacote_editorial(p)
        self.assertFalse(r["ok"])
        self.assertTrue(any("abaixo_de_4_paragrafos" in e for e in r["erros"]))

    def test_validador_nao_aceita_paragrafo_unico(self):
        p = _pacote_ok()
        p["corpo_materia"] = "tudo num paragrafo so sem quebra de linha"
        r = REV.validar_pacote_editorial(p)
        self.assertFalse(r["ok"])
        self.assertTrue(any("paragrafo_unico_ou_vazio" in e for e in r["erros"]))

    def test_validador_nao_aceita_travessao(self):
        p = _pacote_ok()
        p["corpo_materia"] += "\n\nOutro paragrafo - com travessao — que e proibido."
        r = REV.validar_pacote_editorial(p)
        self.assertFalse(r["ok"])
        self.assertIn("travessao_no_corpo", r["erros"])

    def test_validador_bloqueia_termos_proibidos(self):
        p = _pacote_ok()
        p["corpo_materia"] = (
            "A votacao chama atencao e vale destacar que reacende o debate.\n\n"
            "Em meio a polemica, a populacao fica em alerta.\n\n"
            "Vale ressaltar que autoridades seguem acompanhando.\n\n"
            "O caso reforca a importancia do debate."
        )
        r = REV.validar_pacote_editorial(p)
        self.assertFalse(r["ok"])
        self.assertGreater(len(r["termos_proibidos_encontrados"]), 0)

    def test_validador_pacote_completo_aceita(self):
        r = REV.validar_pacote_editorial(_pacote_ok())
        self.assertTrue(r["ok"], f"erros inesperados: {r['erros']}")


# ──────────────────────────── credenciais ──────────────────────────────
class TestDiagnosticoCredenciais(unittest.TestCase):
    def test_diagnostico_credenciais_sem_vazar_chave(self):
        # Importa o diagnostico e roda mockando os.getenv.
        import importlib.util
        path = SISTEMA / "diagnosticar_credenciais_ia_cms.py"
        spec = importlib.util.spec_from_file_location("diag_cred", path)
        mod = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-supersegredoabsoluto1234567890"}, clear=False):
            with mock.patch("builtins.print") as mp:
                spec.loader.exec_module(mod)
                out = mod.main()
        chave = out["ambiente_processo"]["OPENAI_API_KEY"]["valor_redigido"]
        self.assertNotIn("supersegredoabsoluto", chave)
        self.assertIn("...", chave)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
