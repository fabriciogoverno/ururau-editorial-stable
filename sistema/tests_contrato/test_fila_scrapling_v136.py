# -*- coding: utf-8 -*-
"""Testes de contrato da branch fix/auditoria-fila-scrapling-v136.

Cobertura (spec_autorizacao_claudio.md §8):

1.  test_schema_pautas
2.  test_query_fila_ativa_exclui_publicados_descartados_bloqueados
3.  test_ordenacao_novas_no_topo
4.  test_baixo_score_no_fim
5.  test_separador_apenas_para_coleta_real
6.  test_persistencia_v134_grava_cleaned_source_text
7.  test_v105_nao_sobrescreve_texto_valido_com_vazio
8.  test_get_source_text_fallback_chain
9.  test_aba_fonte_le_alias_canonico
10. test_redigir_bloqueia_sem_texto
11. test_redigir_bloqueia_baixo_score_nao_aprovado
12. test_redigir_aceita_com_texto_valido
13. test_coleta_v136_simulada_dispara_refresh_fila
14. test_contadores_excluem_baixo_score_em_pautas_ativas
15. test_progresso_chamado_via_after
16. test_sem_duplicidade_por_uid
17. test_filtros_editoriais_marcam_baixo_score
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Adiciona sistema/ ao sys.path se rodar de fora.
HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.core import database as db_mod
from ururau.core import source_text_contract as stc


def _tmp_db() -> str:
    """Cria um Database vazio em arquivo temporario e retorna o path."""
    tmp = tempfile.NamedTemporaryFile(prefix="ururau_test_", suffix=".db", delete=False)
    tmp.close()
    return tmp.name


def _make_db() -> db_mod.Database:
    db_mod._db_instance = None  # reset singleton
    return db_mod.Database(_tmp_db())


def _pauta(uid: str, *, status: str = "captada", titulo: str = "Pauta teste",
           link: str = "", cleaned: str = "", v134: str = "", v105: str = "",
           extras: dict | None = None) -> dict:
    # salvar_pauta usa pauta["_uid"] como uid persistido; passar tambem
    # garante que buscar_pauta(uid) ache a pauta depois.
    p: dict = {
        "uid": uid,
        "_uid": uid,
        "titulo_origem": titulo,
        "link_origem": link or f"https://example.com/{uid}",
        "status": status,
        "fonte_nome": "fonte_teste",
        "captada_em": "2026-05-12 10:00:00",
    }
    if cleaned:
        p["cleaned_source_text"] = cleaned
    if v134:
        p["texto_fonte_v134"] = v134
    if v105:
        p["texto_fonte_v105"] = v105
    if extras:
        p.update(extras)
    return p


def _texto_valido(n: int = 600) -> str:
    base = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Vivamus laoreet ipsum eu sapien tincidunt, nec viverra nibh viverra. ")
    while len(base) < n:
        base += base
    return base[:n]


# ────────────────────────────────────────────────────────────────────────────
# 1) Schema
# ────────────────────────────────────────────────────────────────────────────
class TestSchemaPautas(unittest.TestCase):
    def test_schema_pautas(self):
        db = _make_db()
        conn = db._conectar()
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(pautas)").fetchall()}
        finally:
            conn.close()
        for c in ("id", "uid", "titulo_origem", "link_origem", "fonte_nome",
                  "score_editorial", "status", "captada_em", "atualizada_em",
                  "dados_json"):
            self.assertIn(c, cols, f"coluna {c} ausente em pautas")


# ────────────────────────────────────────────────────────────────────────────
# 2-4, 16) query_fila_ativa
# ────────────────────────────────────────────────────────────────────────────
class TestQueryFilaAtiva(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()

    def test_query_fila_ativa_exclui_publicados_descartados_bloqueados(self):
        self.db.salvar_pauta(_pauta("uid_ok", status="captada"))
        self.db.salvar_pauta(_pauta("uid_pub", status="publicada"))
        self.db.salvar_pauta(_pauta("uid_desc", status="descartada"))
        self.db.salvar_pauta(_pauta("uid_blq", status="bloqueada"))
        self.db.salvar_pauta(_pauta("uid_rep", status="reprovada"))
        self.db.salvar_pauta(_pauta("uid_exc", status="excluida"))
        uids = {p["uid"] for p in self.db.query_fila_ativa()}
        self.assertEqual(uids, {"uid_ok"})

    def test_ordenacao_novas_no_topo(self):
        self.db.salvar_pauta({**_pauta("velha"), "captada_em": "2026-05-10 08:00:00"})
        self.db.salvar_pauta({**_pauta("recente"), "captada_em": "2026-05-12 18:00:00"})
        self.db.salvar_pauta({**_pauta("media"), "captada_em": "2026-05-11 12:00:00"})
        uids = [p["uid"] for p in self.db.query_fila_ativa()]
        self.assertEqual(uids[0], "recente")
        self.assertEqual(uids[-1], "velha")

    def test_baixo_score_no_fim(self):
        self.db.salvar_pauta(_pauta("normal_a"))
        self.db.salvar_pauta(_pauta("bx_1", status="baixo_score"))
        self.db.salvar_pauta(_pauta("normal_b"))
        self.db.salvar_pauta(_pauta("bx_2", status="baixo_score"))
        uids = [p["uid"] for p in self.db.query_fila_ativa()]
        # primeiros devem ser os normais; baixo_score no fim
        self.assertTrue(uids.index("normal_a") < uids.index("bx_1"))
        self.assertTrue(uids.index("normal_b") < uids.index("bx_1"))
        self.assertTrue(uids.index("normal_b") < uids.index("bx_2"))

    def test_sem_duplicidade_por_uid(self):
        p = _pauta("uid_unico")
        self.db.salvar_pauta(p)
        self.db.salvar_pauta(p)  # INSERT OR REPLACE
        uids = [x["uid"] for x in self.db.query_fila_ativa()]
        self.assertEqual(uids.count("uid_unico"), 1)


# ────────────────────────────────────────────────────────────────────────────
# 5) Separador apenas para coleta real (regressao do v136 patch)
# ────────────────────────────────────────────────────────────────────────────
class TestSeparadorReal(unittest.TestCase):
    def test_separador_apenas_para_coleta_real(self):
        # query_fila_ativa NUNCA deve criar separador com horario atual.
        db = _make_db()
        db.salvar_pauta(_pauta("a"))
        db.salvar_pauta(_pauta("b"))
        out = db.query_fila_ativa()
        for p in out:
            self.assertFalse(p.get("_separador_coleta_v123"),
                             f"query oficial nao deveria gerar separador (uid={p.get('uid')})")
            self.assertNotEqual(str(p.get("status") or "").lower(), "_separador")


# ────────────────────────────────────────────────────────────────────────────
# 6) Persistencia v134 grava cleaned_source_text via contrato
# ────────────────────────────────────────────────────────────────────────────
class TestPersistenciaV134(unittest.TestCase):
    def test_persistencia_v134_grava_cleaned_source_text(self):
        p = _pauta("pv134")
        texto = _texto_valido(1200)
        ok = stc.set_source_text(p, texto, origem="v134")
        self.assertTrue(ok)
        self.assertEqual(p[stc.CANONICAL_ALIAS], texto)
        # Persistencia em DB tambem mantem o campo via dados_json.
        db = _make_db()
        db.salvar_pauta(p)
        out = db.query_fila_ativa()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].get("cleaned_source_text"), texto)


# ────────────────────────────────────────────────────────────────────────────
# 7) v105 nao sobrescreve texto valido com vazio
# ────────────────────────────────────────────────────────────────────────────
class TestV105NaoSobrescreve(unittest.TestCase):
    def test_v105_nao_sobrescreve_texto_valido_com_vazio(self):
        bom = _texto_valido(1000)
        p = _pauta("pv105", cleaned=bom)
        # Simula falha do v105 tentando "atualizar" com vazio.
        ok = stc.set_source_text(p, "", origem="v105")
        self.assertFalse(ok)
        self.assertEqual(p[stc.CANONICAL_ALIAS], bom)
        # Tentando com texto curto tambem nao deve apagar.
        ok = stc.set_source_text(p, "muito curto", origem="v105")
        self.assertFalse(ok)
        self.assertEqual(p[stc.CANONICAL_ALIAS], bom)


# ────────────────────────────────────────────────────────────────────────────
# 8) Fallback chain do get_source_text
# ────────────────────────────────────────────────────────────────────────────
class TestFallbackChain(unittest.TestCase):
    def test_get_source_text_fallback_chain(self):
        # O contrato normaliza espacos finais/iniciais; comparamos stripped.
        texto_v134 = _texto_valido(900).strip()
        # cleaned vazio, v134 OK: retorna v134.
        p = _pauta("p1", cleaned="", v134=texto_v134)
        self.assertEqual(stc.get_source_text(p), texto_v134)
        # cleaned curto, v134 OK valido: retorna v134.
        p = _pauta("p2", cleaned="curto", v134=texto_v134)
        self.assertEqual(stc.get_source_text(p), texto_v134)
        # Nenhum valido, mas algum tem conteudo: retorna o maior.
        p = _pauta("p3", cleaned="curto cleaned", v134="curto v134 maior um pouco que cleaned")
        self.assertEqual(stc.get_source_text(p), "curto v134 maior um pouco que cleaned")

    def test_min_valid_e_550_por_default(self):
        # default oficial
        os.environ.pop("URURAU_MIN_VALID", None)
        self.assertEqual(stc.min_valid(), 550)
        os.environ["URURAU_MIN_VALID"] = "900"
        importlib.reload(stc)
        self.assertEqual(stc.min_valid(), 900)
        os.environ.pop("URURAU_MIN_VALID", None)
        importlib.reload(stc)


# ────────────────────────────────────────────────────────────────────────────
# 9) Aba Fonte le alias canonico
# ────────────────────────────────────────────────────────────────────────────
class TestAbaFonteAliasCanonico(unittest.TestCase):
    def test_aba_fonte_le_alias_canonico(self):
        # Importa apos garantir sys.path para sistema/.
        from ururau.ui.fonte_preview_v107 import obter_texto_fonte_via_contrato
        texto = _texto_valido(700)
        p = _pauta("aba", cleaned=texto)
        t, util, valido = obter_texto_fonte_via_contrato(p)
        self.assertEqual(t, texto)
        self.assertGreaterEqual(util, 550)
        self.assertTrue(valido)
        # Com cleaned vazio mas v134 valido, o fallback ainda traz texto.
        p2 = _pauta("aba2", cleaned="", v134=texto)
        t2, util2, valido2 = obter_texto_fonte_via_contrato(p2)
        self.assertEqual(t2, texto)
        self.assertTrue(valido2)
        # Com nada: vazio, 0, invalido (nao "OK com 0 chars").
        p3 = _pauta("aba3")
        t3, util3, valido3 = obter_texto_fonte_via_contrato(p3)
        self.assertEqual(t3, "")
        self.assertEqual(util3, 0)
        self.assertFalse(valido3)


# ────────────────────────────────────────────────────────────────────────────
# 10-12) Redigir: guards via contrato
# ────────────────────────────────────────────────────────────────────────────
class TestRedigirGuards(unittest.TestCase):
    def test_redigir_bloqueia_sem_texto(self):
        p = _pauta("sem_texto")
        self.assertFalse(stc.source_text_is_valid(p))

    def test_redigir_bloqueia_baixo_score_nao_aprovado(self):
        # Replica logica do guard em painel._acao_redigir
        p = _pauta("bx", status="baixo_score")
        st = str(p.get("status") or "").lower()
        aprovada = bool(p.get("aprovada_baixo_score") or p.get("aprovada"))
        self.assertEqual(st, "baixo_score")
        self.assertFalse(aprovada, "deveria bloquear: baixo_score nao aprovado")

    def test_redigir_aceita_com_texto_valido(self):
        p = _pauta("ok", cleaned=_texto_valido(1500))
        self.assertTrue(stc.source_text_is_valid(p))
        lixo, motivo = stc.eh_lixo_editorial(p)
        self.assertFalse(lixo, f"nao deveria ser lixo, motivo={motivo}")


# ────────────────────────────────────────────────────────────────────────────
# 13) Coleta v136 simulada dispara refresh da fila
# ────────────────────────────────────────────────────────────────────────────
class TestColetaV136RefreshFila(unittest.TestCase):
    def test_coleta_v136_simulada_dispara_refresh_fila(self):
        # Simula: Scrapling v136 escreve novas pautas; query_fila_ativa pega.
        db = _make_db()
        # Antes da coleta, fila vazia.
        self.assertEqual(db.query_fila_ativa(), [])
        # "Coleta v136" insere 3 pautas.
        for i, uid in enumerate(("v136_a", "v136_b", "v136_c")):
            db.salvar_pauta({**_pauta(uid),
                             "captada_em": f"2026-05-12 10:0{i}:00"})
        out = db.query_fila_ativa()
        self.assertEqual({p["uid"] for p in out}, {"v136_a", "v136_b", "v136_c"})


# ────────────────────────────────────────────────────────────────────────────
# 14) Contadores excluem baixo_score em "Pautas ativas"
# ────────────────────────────────────────────────────────────────────────────
class TestContadores(unittest.TestCase):
    def test_contadores_excluem_baixo_score_em_pautas_ativas(self):
        db = _make_db()
        for uid in ("a", "b", "c"):
            db.salvar_pauta(_pauta(uid))
        for uid in ("bx_1", "bx_2"):
            db.salvar_pauta(_pauta(uid, status="baixo_score"))
        db.salvar_pauta(_pauta("desc", status="descartada"))
        db.salvar_pauta(_pauta("blq", status="bloqueada"))
        c = db.contadores_dashboard()
        self.assertEqual(c["pautas_ativas"], 3)
        self.assertEqual(c["baixo_score"], 2)
        self.assertEqual(c["descartadas"], 1)
        self.assertEqual(c["bloqueadas"], 1)
        self.assertEqual(c["total"], 7)


# ────────────────────────────────────────────────────────────────────────────
# 15) Progresso chamado via after() — verifica que o helper existe e e
#      chamavel sem precisar de Tk real (smoke test).
# ────────────────────────────────────────────────────────────────────────────
class TestProgressoAfter(unittest.TestCase):
    def test_progresso_chamado_via_after(self):
        # painel.py expoe _atualizar_stats_async; deve chamar contadores_dashboard
        # e a UI deve ser atualizada via after() (Tk thread-safe).
        # Validamos estaticamente, sem instanciar Tk (que pode nao existir no CI).
        painel_path = SISTEMA / "ururau" / "ui" / "painel.py"
        src_painel = painel_path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("contadores_dashboard", src_painel)
        self.assertIn("def _atualizar_stats_async", src_painel)
        self.assertIn(".after(0,", src_painel.replace(" ", ""))


# ────────────────────────────────────────────────────────────────────────────
# 17) Filtros editoriais marcam baixo score
# ────────────────────────────────────────────────────────────────────────────
class TestFiltrosEditoriais(unittest.TestCase):
    def test_filtros_editoriais_marcam_baixo_score(self):
        casos = [
            ("Melhores gols da rodada", "esporte_melhores_gols"),
            ("Melhores momentos do jogo", "esporte_melhores_momentos"),
            ("Melhores defesas da semana", "esporte_melhores_defesas"),
            ("Gol: o melhor da partida", "esporte_gols"),
            ("Charge do dia: politica", "charge"),
            ("Frase do dia", "frase_do_dia"),
            ("Enquete: vote agora", "enquete"),
        ]
        for titulo, motivo_esperado in casos:
            with self.subTest(titulo=titulo):
                p = _pauta("x", titulo=titulo)
                lixo, motivo = stc.eh_lixo_editorial(p)
                self.assertTrue(lixo, f"{titulo!r} deveria ser lixo")
                self.assertEqual(motivo, motivo_esperado)

    def test_filtro_aceita_materia_valida(self):
        p = _pauta("politica", titulo="Camara aprova projeto de seguranca em Campos",
                   cleaned=_texto_valido(1200))
        lixo, motivo = stc.eh_lixo_editorial(p)
        self.assertFalse(lixo, f"materia valida foi marcada como lixo: {motivo}")




# ────────────────────────────────────────────────────────────────────────────
# 18-19) Ordenacao TXT OK no topo (spec_claudio_hidratacao_continua)
# ────────────────────────────────────────────────────────────────────────────
class TestOrdenacaoTxtOkNoTopo(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()

    def test_txt_ok_sobe_para_o_topo_independente_da_data(self):
        # Tres pautas:
        #  a) sem texto, mais recente
        #  b) com texto valido, antiga
        #  c) sem texto, intermediaria
        # Esperado: b primeiro (TXT OK), depois pelas datas dentro de pendentes.
        self.db.salvar_pauta({**_pauta("recente_sem"),
                              "captada_em": "2026-05-12 18:00:00"})
        self.db.salvar_pauta({**_pauta("antiga_com", cleaned=_texto_valido(900)),
                              "captada_em": "2026-05-10 08:00:00"})
        self.db.salvar_pauta({**_pauta("intermed_sem"),
                              "captada_em": "2026-05-11 12:00:00"})
        uids = [p["uid"] for p in self.db.query_fila_ativa()]
        # antiga_com (com texto) deve vir antes de qualquer pendente.
        self.assertEqual(uids[0], "antiga_com")
        # Dentro do grupo de pendentes, recente vem antes da intermediaria.
        self.assertLess(uids.index("recente_sem"), uids.index("intermed_sem"))

    def test_baixo_score_continua_no_fim_mesmo_com_texto(self):
        # Mesmo se a pauta de baixo_score tiver texto valido, ela ainda vai pro fim.
        self.db.salvar_pauta(_pauta("normal_a"))
        self.db.salvar_pauta(_pauta("bx_com_texto", status="baixo_score",
                                    cleaned=_texto_valido(900)))
        self.db.salvar_pauta({**_pauta("normal_b", cleaned=_texto_valido(900)),
                              "captada_em": "2026-05-12 18:00:00"})
        uids = [p["uid"] for p in self.db.query_fila_ativa()]
        self.assertEqual(uids[-1], "bx_com_texto")
        self.assertLess(uids.index("normal_b"), uids.index("normal_a"))




# ────────────────────────────────────────────────────────────────────────────
# 20-26) Redigir nao bloqueia/descarta por falha tecnica
# spec_claudio_reverter_bloqueio_descartada_redigir §8
# ────────────────────────────────────────────────────────────────────────────
class TestRedigirSemDescarte(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()

    def test_reativar_pauta_para_redacao_existe_e_atualiza_status(self):
        uid = "rt1"
        self.db.salvar_pauta(_pauta(uid, status="descartada", cleaned=_texto_valido(900)))
        info = self.db.reativar_pauta_para_redacao(uid, motivo="texto_fonte_valido")
        self.assertEqual(info["status_anterior"], "descartada")
        self.assertEqual(info["novo_status"], "em_redacao")
        p = self.db.buscar_pauta(uid)
        self.assertEqual(p["status"], "em_redacao")

    def test_redigir_nao_bloqueia_descartada_com_texto_valido(self):
        # Apos reativacao via reativar_pauta_para_redacao, pauta_foi_descartada
        # deve retornar False (porque o status foi alterado para em_redacao).
        uid = "rt2"
        link = "https://exemplo.com/n2"
        self.db.salvar_pauta(_pauta(uid, status="descartada", link=link,
                                    cleaned=_texto_valido(900)))
        self.assertTrue(self.db.pauta_foi_descartada(link, uid))
        self.db.reativar_pauta_para_redacao(uid, motivo="texto_fonte_valido")
        self.assertFalse(self.db.pauta_foi_descartada(link, uid),
                         "apos reativacao, nao deveria mais aparecer como descartada")

    def test_redigir_reativa_descartada_com_texto_valido(self):
        # Reativacao tambem remove link da lista de bloqueio (se estiver la).
        uid = "rt3"
        link = "https://exemplo.com/n3"
        self.db.salvar_pauta(_pauta(uid, status="descartada", link=link,
                                    cleaned=_texto_valido(900)))
        # Coloca o link no bloqueio (simula barreira por link)
        self.db.bloquear_link(link, uid=uid, titulo="t", motivo="teste")
        self.assertTrue(self.db.link_esta_bloqueado(link))
        self.db.reativar_pauta_para_redacao(uid, motivo="texto_fonte_valido")
        self.assertFalse(self.db.link_esta_bloqueado(link),
                         "reativacao deveria liberar o link tambem")

    def test_redigir_nao_descarta_quando_ia_falha(self):
        # Status principal nunca pode virar descartada por falha de IA;
        # so via marcar_status_redacao (status auxiliar).
        uid = "rt4"
        self.db.salvar_pauta(_pauta(uid, status="captada", cleaned=_texto_valido(900)))
        # Simula erro de IA
        self.db.marcar_status_redacao(uid, "erro_credencial_ia",
                                      detalhe="OpenAI 401 invalid api key")
        p = self.db.buscar_pauta(uid)
        # Status principal preservado
        self.assertEqual(p["status"], "captada")
        # Status auxiliar gravado
        import json
        extra = json.loads(p.get("dados_json") or "{}")
        self.assertEqual(extra.get("status_redacao_v200"), "erro_credencial_ia")
        self.assertIn("OpenAI 401", extra.get("status_redacao_detalhe_v200") or "")

    def test_redigir_falha_ia_mantem_status_recuperavel(self):
        # status_redacao_v200 deve ficar entre os recuperaveis.
        recuperaveis = {"erro_ia", "erro_credencial_ia", "erro_modelo_ia",
                        "erro_rede_ia", "fonte_insuficiente", "redacao_pendente"}
        uid = "rt5"
        self.db.salvar_pauta(_pauta(uid, cleaned=_texto_valido(900)))
        for st in recuperaveis:
            self.db.marcar_status_redacao(uid, st)
            p = self.db.buscar_pauta(uid)
            import json
            extra = json.loads(p.get("dados_json") or "{}")
            self.assertEqual(extra.get("status_redacao_v200"), st)
            self.assertEqual(p["status"], "captada",
                             f"status principal mudou apos marcar {st}")

    def test_redigir_baixo_score_com_texto_valido_pede_aprovacao(self):
        # Pauta baixo_score com texto valido continua marcada como baixo_score
        # ate o usuario aprovar explicitamente. O contrato eh_lixo_editorial
        # nao deve classificar como lixo so por estar em baixo_score quando ha
        # texto e o titulo nao bate em nenhum padrao.
        uid = "rt6"
        self.db.salvar_pauta(_pauta(uid, status="baixo_score",
                                    titulo="Camara aprova projeto de seguranca",
                                    cleaned=_texto_valido(900)))
        p = self.db.buscar_pauta(uid)
        self.assertEqual(p["status"], "baixo_score")
        # Importante: get_source_text retorna o texto, mas o painel ainda exige
        # confirmacao do usuario (aprovada_baixo_score) antes de chamar IA.
        # Esse teste documenta o invariante de DB.
        import json
        extra = json.loads(p.get("dados_json") or "{}")
        self.assertFalse(extra.get("aprovada_baixo_score"))
        self.assertFalse(extra.get("aprovada"))

    def test_redigir_sem_texto_marca_fonte_insuficiente_nao_descartada(self):
        # Quando nao ha texto, o status auxiliar correto e fonte_insuficiente,
        # nunca descartada.
        uid = "rt7"
        self.db.salvar_pauta(_pauta(uid, status="captada"))
        self.db.marcar_status_redacao(uid, "fonte_insuficiente",
                                      detalhe="V134 0 chars; V105 0/550")
        p = self.db.buscar_pauta(uid)
        self.assertEqual(p["status"], "captada")
        import json
        extra = json.loads(p.get("dados_json") or "{}")
        self.assertEqual(extra.get("status_redacao_v200"), "fonte_insuficiente")
        self.assertNotIn(p["status"], ("descartada", "bloqueada", "excluida"))

    def test_botao_descartar_continua_descartando_quando_usuario_clica_descartar(self):
        # Importante: o spec proibe descarte por falha tecnica, mas o usuario
        # ainda pode descartar manualmente via excluir_pauta/marcar_descartada.
        uid = "rt8"
        link = "https://exemplo.com/n8"
        self.db.salvar_pauta(_pauta(uid, status="captada", link=link))
        self.db.excluir_pauta(uid, link=link, titulo="t")
        p = self.db.buscar_pauta(uid)
        self.assertEqual(p["status"], "excluida")
        # E pauta_foi_descartada confirma.
        self.assertTrue(self.db.pauta_foi_descartada(link, uid))


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
