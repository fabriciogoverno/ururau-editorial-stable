# -*- coding: utf-8 -*-
"""
HOTFIX_PAINEL_MONITOR_V47_15.py
Faz o Monitor 24h funcionar corretamente DENTRO DO PAINEL.

Correções:
- botão Iniciar da aba Monitor passa a iniciar em RASCUNHO CMS real por padrão;
- checkbox "Publicar diretamente" só muda para modo direto quando marcado;
- aplica os mesmos defaults dos BATs dentro do processo do painel;
- corrige log do painel para não mostrar CMS=NAO quando o modo é rascunho;
- permite parar e reiniciar pelo painel em ponto seguro;
- cria validador específico.

Uso:
  python HOTFIX_PAINEL_MONITOR_V47_15.py
  .\13_VALIDAR_MONITOR_PAINEL_V47_15.bat
  .\02_ABRIR_PAINEL.bat
"""
from pathlib import Path
import shutil, subprocess, sys


def detectar_base() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "sistema").is_dir():
        return cwd
    if cwd.name.lower() == "sistema" and (cwd / "ururau").is_dir():
        return cwd.parent
    for p in [cwd] + list(cwd.parents):
        if (p / "sistema").is_dir():
            return p
    raise SystemExit("ERRO: rode este hotfix na raiz do projeto, no mesmo nível da pasta sistema.")

BASE = detectar_base()
S = BASE / "sistema"
print("[V47.15] Projeto:", BASE)


def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_15")
        if not b.exists():
            try:
                shutil.copy2(p, b)
            except Exception as e:
                print("[WARN] backup falhou", p, e)


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    backup(p)
    p.write_text(content, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def bat(name: str, content: str):
    write(BASE / name, content.replace("\n", "\r\n"))

# 1) Patch real da aba Monitor dentro do painel.
patch_file = S / "ururau" / "ui" / "patch_v47_15_monitor_painel.py"
write(patch_file, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, threading
from pathlib import Path


def _sistema_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == 'sistema':
            return parent
    return Path.cwd()


def _cfg() -> dict:
    try:
        p = _sistema_root() / 'config' / 'monitor_24h.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except Exception:
        return {}


def _int_cfg(name: str, default: int) -> int:
    try:
        c = _cfg()
        v = c.get(name)
        if v is None:
            for sec in ('coleta','extracao','gates_monitor_24h','seo'):
                sub = c.get(sec) or {}
                if isinstance(sub, dict) and name in sub:
                    v = sub.get(name); break
        return int(v) if int(v) > 0 else int(default)
    except Exception:
        return int(default)


def _set_env_monitor_painel():
    env = {
        'URURAU_MONITOR_MODO_CMS': 'rascunho',
        'URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR': '1',
        'URURAU_PUBLICAR_DIRETO': '0',
        'URURAU_CMS_PUBLICACAO_DIRETA': '0',
        'SCORE_MIN_MONITOR': str(_int_cfg('score_minimo_monitor', 35)),
        'URURAU_MONITOR_SCORE_MINIMO': str(_int_cfg('score_minimo_monitor', 35)),
        'URURAU_SCORE_MINIMO_RASCUNHO': str(_int_cfg('score_minimo_rascunho', 35)),
        'URURAU_SCORE_MINIMO_DIRETA': str(_int_cfg('seo_minimo_publicacao_direta', 90)),
        'URURAU_MIN_CHARS_FONTE_MONITOR': str(_int_cfg('min_chars_fonte_gnews', 350)),
        'URURAU_GNEWS_JANELA_HORAS': str(_int_cfg('janela_horas_google_news', 12)),
        'URURAU_V111_GNEWS_JANELA_HORAS': str(_int_cfg('janela_horas_google_news', 12)),
        'URURAU_V111_SCORE_MINIMO_PAUTA': str(_int_cfg('score_minimo_gnews', 35)),
        'URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO': str(_int_cfg('max_resultados_gnews_por_termo', 6)),
        'URURAU_V111_GNEWS_MIN_CHARS_FONTE': str(_int_cfg('min_chars_fonte_gnews', 350)),
        'URURAU_V111_GNEWS_INTEGRADO': '1',
        'URURAU_V111_USAR_EXTRACAO_COMPLETA': '1',
        'URURAU_V111_USAR_CICLO_COMBINADO': '1',
        'URURAU_V110_MONITOR_GNEWS_LEGADO': '1',
        'URURAU_V108_GNEWS_TERMOS': '1',
        'URURAU_SOURCE_HUNTER_ATIVO': '1',
        'URURAU_AUTOFONTES_V131_ATIVO': '1',
        'URURAU_AUTO_DIAGNOSTICO_FONTE': '1',
        'URURAU_MONITOR_USAR_FILA_PAINEL': '1',
    }
    for k, v in env.items():
        os.environ[str(k)] = str(v)
    try:
        from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers
        try:
            aplicar_defaults_scrapers(forcar=True)
        except TypeError:
            aplicar_defaults_scrapers()
    except Exception:
        pass


def aplicar_patch_v47_15(ns: dict):
    AbaMonitor = ns.get('AbaMonitor')
    if AbaMonitor is None:
        print('[V47.15][AVISO] AbaMonitor não encontrada; patch não aplicado.')
        return

    def _append_safe(self, msg, tag='info'):
        try:
            self._append_log(msg, tag)
        except Exception:
            try: print(msg)
            except Exception: pass

    def _iniciar_v47_15(self):
        from tkinter import messagebox
        _set_env_monitor_painel()

        if not getattr(self, '_client', None):
            _append_safe(self, '[Monitor] OPENAI_API_KEY ausente: usando fallback local identificado.', 'warn')

        robo_atual = getattr(self, '_robo', None)
        th_atual = getattr(self, '_thread', None)
        if robo_atual and getattr(robo_atual, 'ativo', False):
            messagebox.showinfo('Monitor', 'O monitor já está ativo no painel.', parent=self)
            return
        if th_atual and getattr(th_atual, 'is_alive', lambda: False)():
            messagebox.showinfo('Monitor', 'O ciclo anterior ainda está finalizando. Aguarde alguns segundos e tente novamente.', parent=self)
            return

        try:
            intervalo = int(getattr(self, '_var_intervalo').get())
        except Exception:
            intervalo = _int_cfg('intervalo_normal_segundos', 180)
        try:
            max_hora = int(getattr(self, '_var_max_hora').get())
        except Exception:
            max_hora = _int_cfg('max_publicacoes_hora', 24)

        publicar_direto = False
        try:
            publicar_direto = bool(getattr(self, '_var_publicar').get())
        except Exception:
            publicar_direto = False

        modo_cms = 'direto' if publicar_direto else 'rascunho'
        permitir_direta = bool(publicar_direto)

        # Se o usuário marcou direta, o monitor ainda passa pelos gates do próprio monitor.
        # Se não marcou, sempre salva/cadastra rascunho CMS, nunca LOCAL/BANCO.
        from ururau.publisher.monitor import MonitorRobo
        self._robo = MonitorRobo(
            db=getattr(self, '_db', None),
            client=getattr(self, '_client', None),
            modelo=getattr(self, '_modelo', None),
            intervalo_segundos=intervalo,
            max_por_hora=max_hora,
            publicar_no_cms=True,
            permitir_publicacao_direta=permitir_direta,
            modo_cms=modo_cms,
            intervalo_sem_pauta_segundos=intervalo,
        )

        def _run():
            try:
                self._robo.iniciar()
            except Exception as e:
                msg = str(e)
                try:
                    self.after(0, lambda msg=msg: _append_safe(self, f'[ERRO MONITOR] {msg}', 'err'))
                except Exception:
                    print('[ERRO MONITOR]', msg)
            finally:
                try: self.after(0, self._atualizar_ui)
                except Exception: pass

        self._thread = threading.Thread(target=_run, daemon=True, name='MonitorRoboPainelV4715')
        self._thread.start()
        try: self._atualizar_ui()
        except Exception: pass
        try: self._cb_atualizado(self._robo, self._thread)
        except Exception: pass

        if modo_cms == 'rascunho':
            _append_safe(self, f'[Monitor Painel V47.15] Iniciado em RASCUNHO CMS real. Intervalo={intervalo}s Sem pauta={intervalo}s Max/hora={max_hora} Score rascunho={os.environ.get("SCORE_MIN_MONITOR")}.', 'ok')
            _append_safe(self, '[Monitor Painel V47.15] Nada será publicado ao vivo; matérias aprováveis serão enviadas como rascunho para revisão.', 'warn')
        else:
            _append_safe(self, f'[Monitor Painel V47.15] Iniciado em modo DIRETO solicitado. Direta ainda depende de gates, SEO e segurança. Intervalo={intervalo}s.', 'warn')

    def _parar_v47_15(self):
        robo = getattr(self, '_robo', None)
        if robo:
            try: robo.parar()
            except Exception: pass
        try: self._atualizar_ui()
        except Exception: pass
        try: self._cb_atualizado(getattr(self, '_robo', None), getattr(self, '_thread', None))
        except Exception: pass
        _append_safe(self, '[Monitor Painel V47.15] Parada solicitada. O ciclo atual será fechado em ponto seguro; depois o botão Iniciar poderá ser usado novamente.', 'warn')

    def _atualizar_ui_v47_15(self):
        ativo = bool(getattr(self, '_robo', None) and getattr(self._robo, 'ativo', False))
        try:
            if ativo:
                n = getattr(self._robo, 'publicacoes_na_hora', 0)
                modo = getattr(self._robo, 'modo_cms', 'rascunho').upper()
                self._lbl_status.config(text=f'● ATIVO — modo {modo} — {n} processada(s)/h', fg='#22c55e')
                self._btn_start.config(state='disabled')
                self._btn_stop.config(state='normal')
            else:
                self._lbl_status.config(text='● INATIVO — pronto para iniciar em RASCUNHO CMS', fg='#9ca3af')
                self._btn_start.config(state='normal')
                self._btn_stop.config(state='disabled')
        except Exception:
            pass

    AbaMonitor._iniciar = _iniciar_v47_15
    AbaMonitor._parar = _parar_v47_15
    AbaMonitor._atualizar_ui = _atualizar_ui_v47_15
    print('[V47.15] Monitor do painel corrigido: RASCUNHO CMS real, defaults aplicados e log coerente.')
''')

# 2) Injeta o patch no final do painel.py depois dos patches antigos.
painel = S / "ururau" / "ui" / "painel.py"
texto = read(painel)
backup(painel)
bloco = """

# v47.15 — Monitor 24h corrigido dentro do painel: rascunho CMS real e defaults do monitor
try:
    from ururau.ui.patch_v47_15_monitor_painel import aplicar_patch_v47_15
    aplicar_patch_v47_15(globals())
except Exception as _e_v47_15:
    print(f"[v47.15] Patch monitor painel não aplicado: {_e_v47_15}")
"""
if "patch_v47_15_monitor_painel" not in texto:
    painel.write_text(texto.rstrip() + bloco, encoding="utf-8")
    print("[OK] patch importado em painel.py")
else:
    print("[OK] painel.py já importava patch v47.15")

# 3) Restaura launchers corretos.
bat("02_ABRIR_PAINEL.bat", '@echo off\ncd /d "%~dp0sistema"\npython ururau_painel.py\npause\n')
bat("03_ABRIR_PAINEL_COM_LOG_VISIVEL.bat", '@echo off\ncd /d "%~dp0sistema"\npython ururau_painel.py\npause\n')

# 4) Validador.
val = S / "ferramentas" / "validadores" / "VALIDAR_MONITOR_PAINEL_V47_15.py"
write(val, r'''# -*- coding: utf-8 -*-
from pathlib import Path
import sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
patch=ROOT/'ururau'/'ui'/'patch_v47_15_monitor_painel.py'
painel=ROOT/'ururau'/'ui'/'painel.py'
ok(patch.exists(),'patch_v47_15_monitor_painel.py existe')
t=patch.read_text(encoding='utf-8') if patch.exists() else ''
ok('modo_cms=modo_cms' in t,'MonitorRobo recebe modo_cms explícito')
ok('publicar_no_cms=True' in t,'Monitor do painel usa CMS real para rascunho')
ok('RASCUNHO CMS real' in t,'log de rascunho CMS real existe')
p=painel.read_text(encoding='utf-8') if painel.exists() else ''
ok('patch_v47_15_monitor_painel' in p,'painel.py importa patch v47.15')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO MONITOR PAINEL V47.15 OK')
''')
bat("13_VALIDAR_MONITOR_PAINEL_V47_15.bat", '@echo off\ncd /d "%~dp0sistema"\npython ferramentas\\validadores\\VALIDAR_MONITOR_PAINEL_V47_15.py\npause\n')

# 5) Compilar arquivos críticos.
for p in [patch_file, painel, val]:
    try:
        subprocess.run([sys.executable, "-m", "py_compile", str(p)], check=False)
    except Exception as e:
        print("[WARN] compile", p, e)

print("\n[V47.15] Hotfix do monitor no painel aplicado.")
print("Rode agora:")
print("  .\\13_VALIDAR_MONITOR_PAINEL_V47_15.bat")
print("  .\\02_ABRIR_PAINEL.bat")
print("No painel: aba Monitor > deixe 'Publicar diretamente no CMS' DESMARCADO > Iniciar.")
