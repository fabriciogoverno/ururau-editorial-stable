# -*- coding: utf-8 -*-
"""Hotfix V47.13: restaura funções analisar_risco e resumo_risco exigidas pelo painel."""
from pathlib import Path
import subprocess, sys

def detectar_base():
    cwd = Path.cwd().resolve()
    if (cwd / 'sistema').is_dir():
        return cwd
    if cwd.name.lower() == 'sistema' and (cwd / 'ururau').is_dir():
        return cwd.parent
    for p in [cwd] + list(cwd.parents):
        if (p / 'sistema').is_dir():
            return p
    raise SystemExit('ERRO: rode este hotfix na raiz do projeto, no mesmo nível da pasta sistema.')

base = detectar_base()
sistema = base / 'sistema'
risco = sistema / 'ururau' / 'editorial' / 'risco.py'
risco.parent.mkdir(parents=True, exist_ok=True)
conteudo = r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import re, unicodedata
from typing import Any, Dict

def _norm(t):
    t=unicodedata.normalize('NFKD', str(t or '')).encode('ascii','ignore').decode().lower()
    return re.sub(r'\s+',' ',t).strip()

def _texto(materia_or_texto):
    if isinstance(materia_or_texto, dict):
        return ' '.join(str(materia_or_texto.get(k,'') or '') for k in ['titulo','subtitulo','descricao','corpo','texto','conteudo','fonte_texto','texto_fonte'])
    return str(materia_or_texto or '')

def _score(texto, termos, peso=12):
    n=_norm(texto); hits=[t for t in termos if t in n]
    return min(100, len(hits)*peso), hits

def analisar_risco_detalhado(materia_or_texto: Any) -> Dict[str, Any]:
    texto=_texto(materia_or_texto)
    des,h1=_score(texto, ['boato','fake news','suposto print','mensagem atribuida','sem confirmacao','viralizou','nao confirmado'], 18)
    vies,h2=_score(texto, ['absurdo','vergonha','escandalo sem precedentes','inacreditavel','chocante','descaso','caos'], 18)
    sens,h3=_score(texto, ['chocante','bomba','urgente!','veja video','revoltante','nao vai acreditar','viral'], 16)
    sen,h4=_score(texto, ['morte','homicidio','estupro','menor','crianca','adolescente','cadaver','trafico','prisao','arma','tiro','violencia'], 10)
    geral=max(des,vies,sens,sen)
    nivel='baixo' if geral<30 else 'medio' if geral<60 else 'alto'
    return {
        'score_risco': geral,
        'risco_desinformacao': des,
        'vies_editorial': vies,
        'sensacionalismo': sens,
        'conteudo_sensivel': sen,
        'nivel_risco': nivel,
        'alertas_risco': h1+h2+h3+h4,
        'detalhes': {'desinformacao':h1,'vies_editorial':h2,'sensacionalismo':h3,'conteudo_sensivel':h4}
    }

def analisar_risco(materia_or_texto: Any, *args, **kwargs) -> Dict[str, Any]:
    """Compatibilidade com o painel antigo: retorna análise de risco detalhada."""
    return analisar_risco_detalhado(materia_or_texto)

def resumo_risco(materia_or_texto: Any, *args, **kwargs) -> str:
    """Compatibilidade com o painel antigo: resumo textual curto."""
    r = analisar_risco_detalhado(materia_or_texto)
    score = r.get('score_risco', 0)
    nivel = r.get('nivel_risco', 'baixo')
    alertas = r.get('alertas_risco') or []
    if not alertas:
        return f'Risco {score}/100 ({nivel}); sem alerta lexical relevante.'
    return f"Risco {score}/100 ({nivel}); alertas: {', '.join(map(str, alertas[:6]))}"
'''
risco.write_text(conteudo, encoding='utf-8')
print('[OK] risco.py corrigido:', risco)
subprocess.run([sys.executable, '-m', 'compileall', '-q', str(risco)], check=False)
print('[OK] Agora rode: .\\02_ABRIR_PAINEL.bat')
