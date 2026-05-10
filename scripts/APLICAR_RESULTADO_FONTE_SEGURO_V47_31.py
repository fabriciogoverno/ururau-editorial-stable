# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
import subprocess
import sys

BASE = None
for p in [Path.cwd().resolve()] + list(Path.cwd().resolve().parents):
    if (p / 'sistema').is_dir():
        BASE = p
        break
if BASE is None:
    raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')
S = BASE / 'sistema'


def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + '.bak_v47_31')
        if not b.exists():
            shutil.copy2(p, b)


def append_once(path: Path, marker: str, block: str):
    text = path.read_text(encoding='utf-8', errors='ignore')
    if marker in text:
        print('[OK] ja aplicado:', path)
        return
    backup(path)
    path.write_text(text.rstrip() + '\n\n' + block.strip() + '\n', encoding='utf-8')
    print('[OK] aplicado:', path)

BLOCK_V86 = r'''
# PATCH_V47_31_RESULTADO_FONTE_SEGURO_V86
try:
    _v4731_v86_original = extrair_artigo_v86
    def extrair_artigo_v86(url: str, texto_existente: str = '', forcar_refresh: bool = False):
        try:
            res = _v4731_v86_original(url, texto_existente=texto_existente, forcar_refresh=forcar_refresh)
            if res is None:
                return ResultadoExtracaoV86(ok=False, url_original=url, url_final=url, texto='', metodo='v86_resultado_none_v47_31', status='failed', erro='extrator retornou None')
            erro = getattr(res, 'erro', '') or ''
            if 'NoneType' in erro and 'get' in erro:
                res.erro = 'entrada invalida normalizada pelo resultado seguro v47.31'
            return res
        except Exception as e:
            texto = limpar_texto_fonte_v81(texto_existente or '')
            util = texto_util_chars(texto)
            return ResultadoExtracaoV86(ok=False, url_original=url, url_final=url, texto=texto[:8000], metodo='v86_exception_safe_v47_31', status='failed', score=0, chars=len(texto), util_chars=util, erro=f'{type(e).__name__}: {e}')
except Exception:
    pass
'''

BLOCK_V104 = r'''
# PATCH_V47_31_RESULTADO_FONTE_SEGURO_V104
try:
    _v4731_v104_original = extrair_artigo_v104
    def extrair_artigo_v104(url: str, texto_existente: str = '', titulo: str = '', forcar_refresh: bool = False):
        try:
            res = _v4731_v104_original(url, texto_existente=texto_existente, titulo=titulo, forcar_refresh=forcar_refresh)
            if res is None:
                return ResultadoExtracaoV104(ok=False, url_original=url, url_final=url, texto='', metodo='v104_resultado_none_v47_31', status='failed', erro='extrator retornou None')
            erro = getattr(res, 'erro', '') or ''
            if 'NoneType' in erro and 'get' in erro:
                res.erro = 'entrada invalida normalizada pelo resultado seguro v47.31'
            return res
        except Exception as e:
            texto = limpar_texto_fonte_v81(texto_existente or '')
            util = texto_util_chars(texto)
            return ResultadoExtracaoV104(ok=False, url_original=url, url_final=url, texto=texto[:8000], metodo='v104_exception_safe_v47_31', status='failed', score=0, chars=len(texto), util_chars=util, erro=f'{type(e).__name__}: {e}')
except Exception:
    pass
'''

v86 = S / 'ururau' / 'coleta' / 'fonte_extractor_v86.py'
v104 = S / 'ururau' / 'coleta' / 'fonte_extractor_v104.py'
append_once(v86, 'PATCH_V47_31_RESULTADO_FONTE_SEGURO_V86', BLOCK_V86)
append_once(v104, 'PATCH_V47_31_RESULTADO_FONTE_SEGURO_V104', BLOCK_V104)
for f in [v86, v104]:
    r = subprocess.run([sys.executable, '-m', 'py_compile', str(f)])
    if r.returncode != 0:
        raise SystemExit(r.returncode)
print('[V47.31] wrappers de resultado seguro aplicados e compilados')
