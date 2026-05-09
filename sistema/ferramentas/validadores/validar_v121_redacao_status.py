from pathlib import Path
import re
ROOT = Path.cwd()
problemas = []
status_names = "CAPTADA|TRIADA|APROVADA|EM_REDACAO|REVISADA|PRONTA|PUBLICADA|REJEITADA|BLOQUEADA|EXCLUIDA|RASCUNHO|DESCARTADA|COLETADA|PENDENTE|REPROVADA|EM_REVISAO|FALHOU|ERRO"
pat = re.compile(r"\bStatusPauta\.(" + status_names + r")\b")
for p in list((ROOT / "ururau").rglob("*.py")) + [ROOT / "ururau_painel.py"]:
    if p.exists() and "__pycache__" not in p.parts and p.name != "settings.py":
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for n, line in enumerate(txt.splitlines(), 1):
            if pat.search(line):
                problemas.append(f"{p}:{n}: {line.strip()}")
assert not problemas, "\n".join(problemas)
print("[OK] V121: nenhum StatusPauta.<status> operacional restante fora de settings.py")
