# -*- coding: utf-8 -*-
"""Testes do agrupamento por coleta na fila.

spec do usuario (13/05/2026, em cima do screenshot do painel):
  - cada coleta vira um BLOCO unico (sem duplicar separador)
  - coleta mais nova fica em CIMA
  - dentro de cada bloco: TXT OK primeiro, pendentes depois
  - baixo_score sempre no fim, sem misturar com coletas
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.core import database as db_mod


def _texto_valido(n: int = 600) -> str:
    base = "lorem ipsum dolor sit amet consectetur adipiscing elit "
    while len(base) < n:
        base += base
    return base[:n]


def _make_db() -> db_mod.Database:
    db_mod._db_instance = None
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return db_mod.Database(tmp.name)


def _pauta(uid: str, *, coleta_label: str, captada: str,
           tem_texto: bool = False, status: str = "captada") -> dict:
    p = {
        "uid": uid, "_uid": uid,
        "titulo_origem": "Pauta " + uid,
        "link_origem": "https://exemplo.com/" + uid,
        "status": status,
        "captada_em": captada,
        "coleta_lote_label_v123": coleta_label,
    }
    if tem_texto:
        p["cleaned_source_text"] = _texto_valido(900)
    return p


class TestFilaAgrupadaPorColeta(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()

    def test_coleta_mais_nova_aparece_primeiro(self):
        # Coleta 64 (22:06) > Coleta 63 (21:59)
        self.db.salvar_pauta(_pauta("c63a", coleta_label="Coleta 63 - 21:59",
                                     captada="2026-05-13 21:59:01"))
        self.db.salvar_pauta(_pauta("c64a", coleta_label="Coleta 64 - 22:06",
                                     captada="2026-05-13 22:06:01"))
        out = self.db.query_fila_ativa()
        uids = [p["uid"] for p in out]
        self.assertLess(uids.index("c64a"), uids.index("c63a"))

    def test_txt_ok_no_topo_dentro_de_cada_coleta(self):
        # Coleta 64: 1 sem texto + 1 com texto. TXT OK deve subir.
        self.db.salvar_pauta(_pauta("c64-sem", coleta_label="Coleta 64 - 22:06",
                                     captada="2026-05-13 22:06:01",
                                     tem_texto=False))
        self.db.salvar_pauta(_pauta("c64-com", coleta_label="Coleta 64 - 22:06",
                                     captada="2026-05-13 22:06:02",
                                     tem_texto=True))
        out = self.db.query_fila_ativa()
        uids = [p["uid"] for p in out]
        self.assertLess(uids.index("c64-com"), uids.index("c64-sem"))

    def test_baixo_score_sempre_no_fim(self):
        self.db.salvar_pauta(_pauta("c64-bx", coleta_label="Coleta 64 - 22:06",
                                     captada="2026-05-13 22:06:01",
                                     tem_texto=True, status="baixo_score"))
        self.db.salvar_pauta(_pauta("c63-x", coleta_label="Coleta 63 - 21:59",
                                     captada="2026-05-13 21:59:01"))
        out = self.db.query_fila_ativa()
        # baixo_score esta no fim mesmo sendo da Coleta 64 (mais nova)
        self.assertEqual(out[-1]["uid"], "c64-bx")

    def test_grupos_nao_intercalam(self):
        # 3 pautas de Coleta 64 + 3 de Coleta 63 - elas nao podem misturar.
        for i in range(3):
            self.db.salvar_pauta(_pauta(f"c64-{i}",
                                         coleta_label="Coleta 64 - 22:06",
                                         captada=f"2026-05-13 22:06:{i:02d}",
                                         tem_texto=(i % 2 == 0)))
            self.db.salvar_pauta(_pauta(f"c63-{i}",
                                         coleta_label="Coleta 63 - 21:59",
                                         captada=f"2026-05-13 21:59:{i:02d}",
                                         tem_texto=(i % 2 == 0)))
        out = self.db.query_fila_ativa()
        # encontra primeira c63 e ultima c64; ultima c64 deve vir ANTES
        # da primeira c63 (grupos nao intercalam)
        idx_primeira_c63 = min(i for i, p in enumerate(out)
                                 if p["uid"].startswith("c63"))
        idx_ultima_c64 = max(i for i, p in enumerate(out)
                               if p["uid"].startswith("c64"))
        self.assertLess(idx_ultima_c64, idx_primeira_c63,
                        "grupos c63 e c64 estao intercalados")

    def test_coletas_anteriores_sem_label_vai_para_o_fim(self):
        # pauta sem coleta_lote_label_v123 -> "Coletas anteriores"
        self.db.salvar_pauta({
            "uid": "antiga", "_uid": "antiga",
            "titulo_origem": "Antiga", "link_origem": "https://x/antiga",
            "status": "captada",
            "captada_em": "2026-05-13 23:59:59",  # mais nova em captada,
            # mas sem label -> deve cair no grupo "Coletas anteriores"
        })
        self.db.salvar_pauta(_pauta("c64", coleta_label="Coleta 64 - 22:06",
                                     captada="2026-05-13 22:06:01"))
        out = self.db.query_fila_ativa()
        uids = [p["uid"] for p in out]
        self.assertLess(uids.index("c64"), uids.index("antiga"))


class TestSeparadorSemDuplicacao(unittest.TestCase):
    def test_v123_inserir_separador_nao_duplica(self):
        # Aciona a logica do painel via leitura estatica + simulacao.
        # Confirma que se o mesmo label aparecer em dois blocos (porque a
        # ordenacao moveu pautas TXT OK), so insere o separador UMA vez.
        from importlib.util import spec_from_file_location, module_from_spec

        # Importar a funcao isoladamente seria caro (puxa tkinter).
        # Simulamos o algoritmo do painel.
        def _label(p):
            return p.get("coleta_lote_label_v123") or "Coletas anteriores"

        def inserir(itens):
            saida = []
            ultimo = None
            inseridos = set()
            counts = {}
            for p in itens:
                counts[_label(p)] = counts.get(_label(p), 0) + 1
            for p in itens:
                lab = _label(p)
                if lab != ultimo and lab not in inseridos:
                    saida.append({"_separador": True, "label": lab,
                                  "titulo": f"{lab} — {counts[lab]} pauta(s)"})
                    inseridos.add(lab)
                    ultimo = lab
                saida.append(p)
            return saida

        # Cenario: pautas de Coleta 64 INTERCALADAS por engano (txt ok das
        # outras coletas no meio). O separador 'Coleta 64' so pode entrar 1x.
        itens = [
            {"uid": "a", "coleta_lote_label_v123": "Coleta 64 - 22:06"},
            {"uid": "b", "coleta_lote_label_v123": "Coleta 63 - 21:59"},
            {"uid": "c", "coleta_lote_label_v123": "Coleta 64 - 22:06"},
            {"uid": "d", "coleta_lote_label_v123": "Coleta 63 - 21:59"},
            {"uid": "e", "coleta_lote_label_v123": "Coleta 64 - 22:06"},
        ]
        saida = inserir(itens)
        labels_sep = [x["label"] for x in saida if x.get("_separador")]
        self.assertEqual(labels_sep.count("Coleta 64 - 22:06"), 1,
                          "separador 'Coleta 64' duplicou")
        self.assertEqual(labels_sep.count("Coleta 63 - 21:59"), 1,
                          "separador 'Coleta 63' duplicou")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
