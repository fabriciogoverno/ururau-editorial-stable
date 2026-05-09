# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestMonitorStop(unittest.TestCase):
    def test_modulo_stop_existe(self):
        import ururau.publisher.monitor_stop_v47_23 as stop
        self.assertTrue(hasattr(stop, "instalar_stop_guard"))

    def test_guard_instala_metodos(self):
        from ururau.publisher.monitor_stop_v47_23 import instalar_stop_guard

        class FakeMonitor:
            def __init__(self):
                self.ativo = True

            def parar(self):
                pass

            def iniciar(self):
                pass

            def _executar_ciclo(self, n=1):
                return {"ok": True}

        instalar_stop_guard(FakeMonitor)
        self.assertTrue(hasattr(FakeMonitor, "deve_parar_v4723"))
        m = FakeMonitor()
        m.parar()
        self.assertTrue(m.deve_parar_v4723())


if __name__ == "__main__":
    unittest.main()
