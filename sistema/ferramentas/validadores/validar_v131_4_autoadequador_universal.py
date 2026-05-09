from pathlib import Path
import importlib.util

base = Path(__file__).resolve().parent
mod_path = base / 'ururau' / 'coleta' / 'auto_perfil_fontes_v131.py'
text = mod_path.read_text(encoding='utf-8')
required = [
    '_enriquecer_solucao_do_diagnostico_v1314',
    '_sucesso_tecnico_v1314',
    'auto_universal_cascata',
    'funcional_sem_pauta_na_janela',
    'v131.4',
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit(f'Marcadores ausentes: {missing}')
compile(mod_path.read_text(encoding='utf-8'), str(mod_path), 'exec')
compile((base / 'ururau' / 'coleta' / 'aplicador_diagnostico_v130.py').read_text(encoding='utf-8'), str(base / 'ururau' / 'coleta' / 'aplicador_diagnostico_v130.py'), 'exec')
print('[OK] v131.4 validada: Autoadequador Universal de Fontes ativo.')
