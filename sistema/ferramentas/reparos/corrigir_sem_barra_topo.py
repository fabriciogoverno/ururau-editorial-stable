# coding: utf-8
from pathlib import Path
import re
import shutil
import time
import py_compile
import zipfile
import hashlib

BASE = Path.cwd()
painel_list = list(BASE.rglob("ururau/ui/painel.py"))

if not painel_list:
    raise SystemExit("ERRO: nao achei ururau/ui/painel.py dentro desta pasta.")

PAINEL = painel_list[0]
print(f"[INFO] painel.py encontrado em: {PAINEL}")

backup_dir = PAINEL.parent / "_backup_sem_barra_topo"
backup_dir.mkdir(exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")
shutil.copy2(PAINEL, backup_dir / f"painel.py.bak_{stamp}")

txt = PAINEL.read_text(encoding="utf-8", errors="ignore")

# Reduz altura da toolbar caso ela tenha sido aumentada pela barra
txt = txt.replace(
    'tb = tk.Frame(self, bg="#11112a", height=88)',
    'tb = tk.Frame(self, bg="#11112a", height=58)'
)

txt = txt.replace(
    'grupo_principal_outer.pack(side="left", padx=(10, 8), pady=(5, 4), anchor="n")',
    'grupo_principal_outer.pack(side="left", padx=(10, 8), pady=8)'
)

txt = txt.replace(
    'grupo_secundario.pack(side="left", padx=(4, 0), pady=8, anchor="n")',
    'grupo_secundario.pack(side="left", padx=(4, 0), pady=8)'
)

# Remove blocos de barra/mensagem superior
padroes = [
    r'\n\s*hdr_flow = tk\.Frame\(grupo_principal_outer,.*?self\._topo_progress_lbl\.pack\(.*?\)\n',
    r'\n\s*hdr_flow = tk\.Frame\(self,.*?self\._topo_progress_lbl\.pack\(.*?\)\n',
    r'\n\s*self\._topo_progresso_valor = 0.*?self\._topo_progress_lbl\.pack\(.*?\)\n',
]

removidos = 0
for p in padroes:
    txt, n = re.subn(p, "\n", txt, count=1, flags=re.S)
    removidos += n

# Status volta a atualizar só o rodapé
txt, n_status = re.subn(
    r'    def _set_status\(self, msg: str\):\n.*?(?=    # ── Carregamento)',
    '    def _set_status(self, msg: str):\n'
    '        self.after(0, lambda: self._status_lbl.config(text=msg))\n\n',
    txt,
    count=1,
    flags=re.S
)

PAINEL.write_text(txt, encoding="utf-8")
py_compile.compile(str(PAINEL), doraise=True)

print(f"[OK] barra/mensagens do topo removidas. Blocos removidos: {removidos}")
print(f"[OK] _set_status simplificado: {n_status}")
print("[OK] painel.py validado sem erro de sintaxe")

zip_final = BASE.parent / "URURAU_V46_4_FINAL_SEM_BARRA_TOPO.zip"
if zip_final.exists():
    zip_final.unlink()

with zipfile.ZipFile(zip_final, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in BASE.rglob("*"):
        if f.is_file():
            zf.write(f, f.relative_to(BASE))

sha = hashlib.sha256(zip_final.read_bytes()).hexdigest()
print(f"[OK] ZIP criado em: {zip_final}")
print(f"SHA256: {sha}")
print("")
print("AGORA RODE:")
print(".\\INICIAR.bat")
print("")
print("SE NAO EXISTIR, RODE:")
print(".\\RODAR_TUDO.bat")
