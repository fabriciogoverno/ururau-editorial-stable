import unittest

from sistema.ururau_ai_auditor.quarentena_manager import (
    bloquear_dominio,
    dominio_esta_bloqueado,
)

class TestBloqueioManual(unittest.TestCase):

    def test_bloqueio_manual(self):
        dominio = "manual-block-test.com"

        bloquear_dominio(dominio)

        self.assertTrue(
            dominio_esta_bloqueado(dominio)
        )

if __name__ == "__main__":
    unittest.main()
