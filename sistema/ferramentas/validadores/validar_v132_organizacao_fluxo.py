from pathlib import Path
import py_compile

base = Path(__file__).resolve().parent
arquivos = [
    base / 'ururau' / 'ui' / 'painel.py',
    base / 'ururau' / 'ui' / 'diagnostico_fontes_tab_v130.py',
    base / 'ururau' / 'ui' / 'patch_v132_organizacao_fluxo.py',
    base / 'ururau' / 'ui' / 'copydesk_painel.py',
]
for arq in arquivos:
    py_compile.compile(str(arq), doraise=True)

root = base.parent
raiz_arquivos = [p.name for p in root.iterdir() if p.is_file()]
permitidos = {'INICIAR.bat', 'INSTALAR.bat', 'RODAR_TUDO.bat', 'VALIDAR.bat'}
extras = [x for x in raiz_arquivos if x not in permitidos]
assert not extras, f'Arquivos extras na raiz: {extras}'

painel = (base / 'ururau' / 'ui' / 'painel.py').read_text(encoding='utf-8')
assert 'patch_v132_organizacao_fluxo' in painel
assert 'self.after(100, self._toggle_console)' not in painel
assert 'Imagem",       self._acao_buscar_imagem' not in painel

patch = (base / 'ururau' / 'ui' / 'patch_v132_organizacao_fluxo.py').read_text(encoding='utf-8')
assert 'Fontes / Links' in patch
assert '_acao_atualizar_geral_v132' in patch
assert '_preview_copydesk_v132' in patch

print('[OK] v132 organização/fluxo validada.')
