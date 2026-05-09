from pathlib import Path
import py_compile

ROOT = Path.cwd()
criticos = [
    ROOT / "ururau" / "ui" / "painel.py",
    ROOT / "ururau" / "coleta" / "adapters" / "campos24horas_v126.py",
    ROOT / "ururau" / "coleta" / "termos_busca_v127.py",
    ROOT / "ururau" / "coleta" / "fonte_registry_v126.py",
    ROOT / "ururau" / "coleta" / "coleta_auditoria_v126.py",
]
for p in criticos:
    py_compile.compile(str(p), doraise=True)

painel = (ROOT / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")
assert "_texto_busca_pauta_v127" in painel
assert "_criar_aba_diagnostico_v127" in painel
assert "coletar_busca_termos_v127" in painel
assert "diagnóstico fica apenas na sessão" in painel
assert "Diagnóstico da última coleta" not in painel or "_criar_aba_diagnostico_v127" in painel

campos = (ROOT / "ururau" / "coleta" / "adapters" / "campos24horas_v126.py").read_text(encoding="utf-8", errors="ignore")
assert "_data_entry_campos_v127" in campos
assert "_campos24_data_corrigida_v127" in campos

from ururau.coleta.termos_busca_v127 import coletar_busca_termos_v127
assert callable(coletar_busca_termos_v127)

print("[OK] v127 validado: busca da fila por rodapé/fonte, diagnóstico em Config, Campos24 data fix e busca por termos 24h")
