# -*- coding: utf-8 -*-
"""V47.28 - corrige SyntaxError no CMS Playwright.

Erro-alvo:
  SyntaxError: from __future__ imports must occur at the beginning of the file
  arquivo: sistema/ururau/publisher/cms_playwright_v81.py

Causa:
  hotfixes anteriores inseriram código antes de `from __future__ import annotations`.
  Python exige que imports __future__ venham logo após shebang/encoding/docstring.

Uso:
  python REPARO_CMS_FUTURE_IMPORT_V47_28.py
  .\28_VALIDAR_CMS_FUTURE_IMPORT_V47_28.bat
  .\02_ABRIR_PAINEL.bat
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys

cwd = Path.cwd().resolve()
BASE = None
for p in [cwd] + list(cwd.parents):
    if (p / "sistema").is_dir():
        BASE = p
        break
if BASE is None:
    raise SystemExit("ERRO: rode na raiz do projeto, acima da pasta sistema.")
S = BASE / "sistema"
print("[V47.28] base:", BASE)


def rd(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def bk(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_28")
        if not b.exists():
            shutil.copy2(p, b)


def wr(p: Path, c: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    bk(p)
    p.write_text(c, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))


def bat(name: str, c: str):
    wr(BASE / name, c.replace("\n", "\r\n"))


def find_insert_after_future_header(text: str) -> int:
    """Retorna posição segura depois de shebang/encoding/docstring/imports __future__."""
    lines = text.splitlines(True)
    i = 0
    # shebang, encoding, comentários iniciais e linhas vazias
    while i < len(lines):
        s = lines[i].strip()
        if i == 0 and s.startswith("#!"):
            i += 1
            continue
        if re.match(r"#.*coding[:=]\s*[-\w.]+", s):
            i += 1
            continue
        if s == "" or s.startswith("#"):
            i += 1
            continue
        break
    # docstring de módulo
    if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
        quote = '"""' if lines[i].lstrip().startswith('"""') else "'''"
        if lines[i].count(quote) >= 2 and lines[i].strip() != quote:
            i += 1
        else:
            i += 1
            while i < len(lines):
                if quote in lines[i]:
                    i += 1
                    break
                i += 1
    # linhas vazias e imports __future__
    while i < len(lines):
        s = lines[i].strip()
        if s == "" or s.startswith("from __future__ import"):
            i += 1
            continue
        break
    return sum(len(x) for x in lines[:i])


def strip_bad_prefix_before_coding_or_future(text: str) -> str:
    """Remove patch solto antes do cabeçalho real, preservando o arquivo original."""
    if "from __future__ import" not in text:
        return text
    first_future = text.find("from __future__ import")
    prefix = text[:first_future]
    # Se antes do future há código executável de patch, tenta voltar ao começo real do arquivo.
    suspicious = any(tok in prefix for tok in ["PATCH_V47", "try:", "except Exception", "import os as", "_v47", "def "])
    if not suspicious:
        return text
    # Preferir início por encoding/docstring/import future mais antigo.
    idx_coding = text.find("# -*- coding")
    if idx_coding > 0:
        return text[idx_coding:]
    idx_future_line = text.rfind("\n", 0, first_future)
    if idx_future_line >= 0:
        # mantém somente de `from __future__` em diante quando o prefixo era patch inválido.
        return text[idx_future_line + 1:]
    return text[first_future:]


def fix_future_import_file(path: Path) -> bool:
    if not path.exists():
        return False
    original = rd(path)
    text = strip_bad_prefix_before_coding_or_future(original)

    # Remove linhas __future__ duplicadas e reinsere uma única no lugar correto.
    lines = text.splitlines(True)
    future_lines = [ln for ln in lines if ln.strip().startswith("from __future__ import")]
    if future_lines:
        # preserva somente annotations; se houver outras, junta em uma linha estável.
        names = []
        for ln in future_lines:
            part = ln.strip().replace("from __future__ import", "").strip()
            for name in part.split(','):
                name = name.strip()
                if name and name not in names:
                    names.append(name)
        if not names:
            names = ["annotations"]
        lines = [ln for ln in lines if not ln.strip().startswith("from __future__ import")]
        text = ''.join(lines)
        idx = find_insert_after_future_header(text)
        text = text[:idx] + "from __future__ import " + ", ".join(names) + "\n" + text[idx:]

    if text != original:
        wr(path, text)
        return True
    print("[OK] sem alteração:", path.relative_to(BASE))
    return False

# Corrige arquivo-alvo e, por segurança, qualquer publisher que tenha sido patchado com future fora do lugar.
targets = [
    S / "ururau" / "publisher" / "cms_playwright_v81.py",
    S / "ururau" / "publisher" / "workflow.py",
    S / "ururau" / "publisher" / "monitor.py",
]

for t in targets:
    fix_future_import_file(t)

# Validador.
bat("28_VALIDAR_CMS_FUTURE_IMPORT_V47_28.bat", r'''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\publisher\cms_playwright_v81.py
python -m py_compile ururau\publisher\workflow.py
python -m py_compile ururau\publisher\monitor.py
echo VALIDACAO CMS FUTURE IMPORT V47.28 OK
pause
''')

# Compilação imediata.
falhas = []
for t in targets:
    if t.exists():
        r = subprocess.run([sys.executable, "-m", "py_compile", str(t)])
        if r.returncode != 0:
            falhas.append(str(t))

if falhas:
    print("\n[ERRO] Ainda há falha de compilação:")
    for f in falhas:
        print(" -", f)
    sys.exit(1)

print("\n[V47.28] aplicado.")
print("Rode:")
print("  .\\28_VALIDAR_CMS_FUTURE_IMPORT_V47_28.bat")
print("  .\\02_ABRIR_PAINEL.bat")
