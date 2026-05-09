# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestWorkflowFonteValidada(unittest.TestCase):
    def test_workflow_tem_gate_fonte_validada_instalado(self):
        from ururau.publisher.workflow import WorkflowPublicacao
        self.assertTrue(
            getattr(WorkflowPublicacao, "_v4729_fonte_validada_instalado", False),
            "WorkflowPublicacao precisa carregar o gate FonteValidada V47.29",
        )

    def test_modulo_patch_existe(self):
        from ururau.publisher.workflow_fonte_validada_v47_29 import instalar_workflow_fonte_validada_v47_29
        self.assertTrue(callable(instalar_workflow_fonte_validada_v47_29))


if __name__ == "__main__":
    unittest.main()
