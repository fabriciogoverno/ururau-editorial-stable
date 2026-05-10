import unittest

from sistema.ururau_ai_auditor.fonte_validada import validar_resultado_fonte

class TestFonte403(unittest.TestCase):

    def test_bloqueia_403(self):

        resultado = {
            "status": 403,
            "texto": "",
            "url": "https://site.com"
        }

        validado = validar_resultado_fonte(resultado)

        self.assertFalse(validado["ok"])

if __name__ == "__main__":
    unittest.main()
