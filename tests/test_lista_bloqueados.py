import unittest

from sistema.ururau_ai_auditor.quarentena_manager import (
    registrar_falha,
    obter_bloqueados,
)

class TestListaBloqueados(unittest.TestCase):

    def test_lista_bloqueados_retorna_set(self):
        dominio = "lista-block-test.com"

        for _ in range(3):
            registrar_falha(dominio)

        bloqueados = obter_bloqueados()

        self.assertIsInstance(
            bloqueados,
            set
        )

        self.assertIn(
            dominio,
            bloqueados
        )

if __name__ == "__main__":
    unittest.main()
