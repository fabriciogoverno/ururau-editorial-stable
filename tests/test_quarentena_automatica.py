import unittest

from sistema.ururau_ai_auditor.quarentena_manager import (
    registrar_falha,
    dominio_esta_bloqueado,
)

class TestQuarentenaAutomatica(unittest.TestCase):

    def test_bloqueia_apos_reincidencia(self):
        dominio = "teste-quarentena-auto.com"

        for _ in range(3):
            registrar_falha(dominio)

        self.assertTrue(
            dominio_esta_bloqueado(dominio)
        )

if __name__ == "__main__":
    unittest.main()
