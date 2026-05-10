import unittest

from sistema.ururau_ai_auditor.fonte_validada import validar_resultado_fonte

class TestFonte429(unittest.TestCase):

    def test_bloqueia_429(self):

        resultado = {
            "status": 429,
            "texto": "",
            "url": "https://site.com"
        }

        validado = validar_resultado_fonte(resultado)

        self.assertFalse(validado["ok"])

if __name__ == "__main__":
    unittest.main()
