# -*- coding: utf-8 -*-
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

arquivos = [
    ROOT / "INICIAR.bat",
    ROOT / "RODAR_TUDO.bat",
    ROOT / "INSTALAR.bat",
    BASE / "INICIAR.bat",
    BASE / "RODAR_TUDO.bat",
    BASE / "INICIAR_OCULTO.bat",
    BASE / "INICIAR_SILENCIOSO.vbs",
    BASE / "INSTALAR.bat",
]
for arq in arquivos:
    assert arq.exists(), f"Arquivo ausente: {arq}"

for arq in arquivos:
    txt = arq.read_text(encoding="utf-8", errors="ignore").lower()
    if arq.name.lower() != "iniciar_console.bat":
        assert "pause" not in txt, f"Ainda existe pause em {arq}"

assert "wscript.exe //b" in (ROOT / "RODAR_TUDO.bat").read_text(encoding="utf-8", errors="ignore").lower()
assert "pythonw.exe" in (BASE / "INICIAR_OCULTO.bat").read_text(encoding="utf-8", errors="ignore").lower()
print("[OK] v132.3 launcher automático sem ENTER validado.")
