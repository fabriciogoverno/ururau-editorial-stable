import unittest

from sistema.ururau_ai_auditor.quarentena_manager import (
    obter_config,
)

class TestConfigQuarentena(unittest.TestCase):

    def test_config_padrao(self):

        config = obter_config()

        self.assertTrue(
            config.get("quarentena_ativa")
        )

        self.assertEqual(
            config.get("limite_reincidencia"),
            3
        )

        self.assertTrue(
            config.get("auto_bloqueio_reincidencia")
        )

if __name__ == "__main__":
    unittest.main()
