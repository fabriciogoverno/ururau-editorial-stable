from __future__ import annotations

# PATCH_V47_20_DICT_ATTR_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_20 import compat_obj as _v4720_compat_obj, getv as _v4720_getv, get_bool as _v4720_get_bool, get_score as _v4720_get_score
except Exception:
    def _v4720_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4720_get_bool(o,k,d=False): return bool(_v4720_getv(o,k,d))
    def _v4720_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4720_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4720_compat_obj(o): return o

# PATCH_V47_18_DICT_SCORE_COMPAT
# PATCH_V47_18_DICT_SCORE_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

try:
    from ururau.fixes.v121_status_guard import aplicar_status_guard_v121
    aplicar_status_guard_v121()
except Exception as _e_v121_status:
    print(f"[V121][STATUS][AVISO] guard não aplicado: {_e_v121_status}")



try:
    from ururau.editorial.openai_motor_patch_v2 import aplicar_patch_openai_motor_v2
    aplicar_patch_openai_motor_v2()
except Exception as _e_motor_v2:
    print(f"[MOTOR_V2][AVISO] patch não aplicado: {_e_motor_v2}")

try:
    from ururau.editorial.editoria_runtime_patch_v117 import aplicar_patch_editoria_contextual_v117
    aplicar_patch_editoria_contextual_v117()
except Exception as _e_editoria_v117:
    print(f"[EDITORIA_V117][AVISO] patch não aplicado: {_e_editoria_v117}")


import json
import os
import re
import threading
import time
import unicodedata
from urllib.parse import urlparse
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
from typing import Optional, TYPE_CHECKING

from ururau.config.settings import (
    LIMIAR_RISCO_MAXIMO,
    MODELO_OPENAI,
    StatusPauta,
    CANAIS_RODIZIO,
    CANAIS_CMS,
)

# Cor para pautas excluídas (tom apagado/cinza)
_COR_ITEM_EXCLUIDA = "#1a1a1a"
from ururau.core.database import get_db
from ururau.editorial.risco import analisar_risco, resumo_risco
from ururau.editorial.copydesk import detectar_problemas
from ururau.coleta.datas_v99 import (
    dentro_da_janela,
    janela_publicacao_horas,
    parse_data_br_ou_iso,
)
from ururau.ui.fonte_preview_v107 import (
    exibir_imagem_fonte as _v107_exibir_imagem_fonte,
    formatar_texto_fonte as _v107_formatar_texto_fonte,
    notificar_imagem_atualizada as _v107_notificar_imagem_atualizada,
)

if TYPE_CHECKING:
    from openai import OpenAI
    from ururau.core.database import Database

# v129.12: limpeza automática segura de cache em thread leve.
try:
    def _rodar_limpeza_cache_v12912_async():
        try:
            from ururau.fixes.cache_limpeza_v12912 import executar_limpeza_automatica_segura_v12912
            executar_limpeza_automatica_segura_v12912()
        except Exception as _e_cache_v12912:
            print(f"[CACHE v129.12] limpeza não aplicada: {_e_cache_v12912}")
    threading.Thread(target=_rodar_limpeza_cache_v12912_async, daemon=True).start()
except Exception:
    pass


# ── Paleta visual ─────────────────────────────────────────────────────────────

COR_FUNDO    = "#0f0f1a"   # fundo principal — quase preto azulado
COR_PAINEL   = "#1a1a2e"   # painéis e barras
COR_DESTAQUE = "#7c3aed"   # roxo vibrante — ações principais
COR_TEXTO    = "#e2e8f0"   # texto principal
COR_VERDE    = "#22c55e"
COR_AMARELO  = "#eab308"
COR_VERMELHO = "#ef4444"
COR_CINZA    = "#64748b"
COR_AZUL     = "#0ea5e9"
COR_ROXO     = "#8b5cf6"
COR_LARANJA  = "#f97316"
COR_CIANO    = "#06b6d4"

# Cor do logo Ururau — vermelho vinho extraído do ícone oficial
COR_LOGO     = "#87322f"

# Cores alternadas para as linhas da fila
_COR_ITEM_PAR   = "#131325"   # linha par   — azul muito escuro
_COR_ITEM_IMPAR = "#1c1c35"   # linha ímpar — ligeiramente mais claro

FONTE_MONO    = ("Courier New", 10)
FONTE_TITULO  = ("Helvetica", 13, "bold")
FONTE_NORMAL  = ("Helvetica", 11)
FONTE_PEQUENA = ("Helvetica", 9)
FONTE_ITEM    = ("Segoe UI", 10)          # fonte principal dos itens da fila
FONTE_ITEM_T  = ("Segoe UI", 10, "bold")  # título do item
FONTE_META    = ("Segoe UI", 8)           # metadados (fonte, data)


def _hex_to_rgb(cor: str) -> tuple[int, int, int]:
    cor = (cor or "#000000").lstrip("#")
    if len(cor) != 6:
        return (0, 0, 0)
    return tuple(int(cor[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def _misturar_cor(c1: str, c2: str, fator: float = 0.5) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex((
        r1 + (r2 - r1) * fator,
        g1 + (g2 - g1) * fator,
        b1 + (b2 - b1) * fator,
    ))


def _escurecer(cor: str, fator: float = 0.18) -> str:
    return _misturar_cor(cor, "#000000", fator)


def _clarear(cor: str, fator: float = 0.18) -> str:
    return _misturar_cor(cor, "#ffffff", fator)


def _icone_botao_toolbar(texto: str) -> str:
    mapa = {
        "Coletar": "◉",
        "Redigir": "✎",
        "Copydesk": "✓",
        "Preview": "◉",
        "Publicar": "➤",
        "Descartar": "⌫",
        "Exportar": "⇩",
    }
    return mapa.get(texto, "")


def _criar_botao_premium(parent, texto: str, cmd, cor: str, *, largura: int = 12, pady: int = 8):
    """Botão com aparência premium, mais encorpado e com hover leve."""
    borda = tk.Frame(parent, bg=_clarear(cor, 0.20), bd=0, highlightthickness=1, highlightbackground=_clarear(cor, 0.32))
    fill = tk.Frame(borda, bg=cor, bd=0)
    fill.pack(fill="both", expand=True, padx=2, pady=2)
    icone = _icone_botao_toolbar(texto)
    rotulo = f"{icone}  {texto}" if icone else texto
    btn = tk.Button(
        fill,
        text=rotulo,
        command=cmd,
        bg=cor,
        activebackground=_clarear(cor, 0.12),
        fg="white",
        activeforeground="white",
        relief="flat",
        bd=0,
        padx=16,
        pady=pady,
        width=largura,
        cursor="hand2",
        font=("Segoe UI", 11, "bold"),
        highlightthickness=0,
    )
    btn.pack(fill="both", expand=True)

    normal_bg = cor
    normal_fill = cor
    hover_bg = _clarear(cor, 0.10)
    pressed_bg = _escurecer(cor, 0.12)
    hover_border = _clarear(cor, 0.40)
    normal_border = _clarear(cor, 0.20)

    def _on_enter(_=None):
        fill.configure(bg=hover_bg)
        btn.configure(bg=hover_bg, activebackground=hover_bg)
        borda.configure(bg=hover_border, highlightbackground=hover_border)

    def _on_leave(_=None):
        fill.configure(bg=normal_fill)
        btn.configure(bg=normal_bg, activebackground=_clarear(cor, 0.12))
        borda.configure(bg=normal_border, highlightbackground=normal_border)

    def _on_press(_=None):
        fill.configure(bg=pressed_bg)
        btn.configure(bg=pressed_bg, activebackground=pressed_bg)

    def _on_release(_=None):
        _on_enter()

    for widget in (borda, fill, btn):
        widget.bind("<Enter>", _on_enter)
        widget.bind("<Leave>", _on_leave)
        widget.bind("<ButtonPress-1>", _on_press)
        widget.bind("<ButtonRelease-1>", _on_release)

    return borda, btn


def _base_sistema_absoluta() -> Path:
    """Retorna a pasta sistema sem depender do diretório de execução do .bat/.vbs."""
    try:
        # painel.py fica em sistema/ururau/ui/painel.py
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd()


def _parse_env_simples_abs(env_path: Path) -> dict[str, str]:
    dados: dict[str, str] = {}
    try:
        if not env_path.exists():
            return dados
        for linha in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave:
                dados[chave] = valor
    except Exception:
        pass
    return dados


def _ler_env_cms_com_fallback() -> dict[str, str]:
    """
    Lê credenciais do CMS de forma absoluta e determinística.

    Correção v47.1: o envio ao CMS fazia uma pré-checagem usando Path('.env')
    e Path('credenciais/...'), dependentes do diretório atual. Em alguns atalhos
    o painel abria fora da pasta sistema, então a tela Config salvava corretamente,
    mas o botão Enviar ao CMS não encontrava URURAU_LOGIN/URURAU_SENHA.

    Prioridade correta: .env.exemplo apenas default; env_principal e .env real
    sobrescrevem; variáveis já carregadas em os.environ têm prioridade máxima
    depois do botão Salvar e Aplicar.
    """
    import os as _os
    base = _base_sistema_absoluta()
    env_paths = [
        base / "credenciais" / ".env.exemplo",
        base / "credenciais" / "env_principal.env",
        base / ".env",
    ]
    envs: dict[str, str] = {}
    for env_path in env_paths:
        envs.update(_parse_env_simples_abs(env_path))

    # O botão Salvar e Aplicar atualiza os.environ na sessão atual.
    # Se o usuário salvou sem reiniciar o painel, essa deve ser a fonte final.
    for chave in (
        "URURAU_LOGIN", "URURAU_SENHA", "URURAU_ASSINATURA",
        "SITE_LOGIN_URL", "SITE_NOVA_URL", "OPENAI_API_KEY", "OPENAI_MODEL",
    ):
        valor = (_os.environ.get(chave) or "").strip()
        if valor:
            envs[chave] = valor
    return envs


def _inferir_progresso_topo(msg: str, atual: int = 0) -> int:
    t = (msg or "").lower()
    if not t:
        return atual
    if any(k in t for k in ("erro", "falha", "bloqueado", "bloqueada")):
        return max(atual, 100)
    if any(k in t for k in ("pronto", "conclu", "[ok]", "publicado", "rascunho salvo")):
        return 100
    if "colet" in t:
        return max(atual, 18 if "inici" in t else 32)
    if any(k in t for k in ("redig", "gerando", "materia gerada")):
        return max(atual, 55)
    if "copydesk" in t:
        return max(atual, 72)
    if "preview" in t:
        return max(atual, 82)
    if any(k in t for k in ("cms", "publica", "enviando")):
        return max(atual, 92)
    if any(k in t for k in ("atualizando", "carregando")):
        return max(atual, 12)
    return atual

_STATUS_COR = {
    'captada':    COR_CINZA,
    'triada':     "#38bdf8",
    'aprovada':   COR_VERDE,
    getattr(StatusPauta, 'EM_REDACAO', 'em_redacao'): COR_AMARELO,
    'revisada':   "#a78bfa",
    'pronta':     COR_VERDE,
    'publicada':  "#10b981",
    'rejeitada':  COR_VERMELHO,
    'reprovada':  COR_VERMELHO,
    'bloqueada':  COR_VERMELHO,
    'baixo_score': '#f59e0b',
}

_BADGE_IMG = {
    "aprovada":   "IMG-OK",
    "sem_imagem": "SEM-IMG",
    "pendente":   "IMG-...",
    "erro":       "IMG-ERR",
}

_ITEM_H = 86  # altura em px por item na lista virtualizada


_TITULOS_GENERICOS_V129_1 = {
    "", "a hora", "home", "inicio", "início", "ultimas", "últimas", "noticias", "notícias",
    "redacao", "redação", "geral", "colunas", "coluna", "politica", "política", "economia",
    "brasil", "mundo", "rio", "rj", "plantao", "plantão", "sem titulo", "sem título",
}

# v129.5: calculado depois da função _norm_titulo_v129_1.
_TITULOS_GENERICOS_NORM_V129_5 = None

def _norm_titulo_v129_1(txt: str) -> str:
    # v129.5: robusto. Nunca pode derrubar a renderização da fila.
    try:
        txt = unicodedata.normalize("NFKD", str(txt or ""))
        txt = "".join(c for c in txt if not unicodedata.combining(c))
    except Exception:
        txt = str(txt or "")
    txt = re.sub(r"[^a-zA-Z0-9]+", " ", txt).strip().lower()
    return re.sub(r"\s+", " ", txt)

def _limpar_titulo_visual_v129_1(txt: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", str(txt or ""))
    txt = re.sub(r"\s+", " ", txt).strip(" \t\r\n-|•—–")
    return txt

def _titulo_generico_v129_1(txt: str) -> bool:
    # v129.5: não pode lançar exceção. Se falhar, retorna False e deixa renderizar.
    try:
        t = _limpar_titulo_visual_v129_1(txt)
        n = _norm_titulo_v129_1(t)
        global _TITULOS_GENERICOS_NORM_V129_5
        if _TITULOS_GENERICOS_NORM_V129_5 is None:
            _TITULOS_GENERICOS_NORM_V129_5 = {_norm_titulo_v129_1(x) for x in _TITULOS_GENERICOS_V129_1}
        if n in _TITULOS_GENERICOS_NORM_V129_5:
            return True
        if len(t) < 8:
            return True
        if len(t.split()) <= 2 and t.upper() == t and len(t) <= 18:
            return True
        return False
    except Exception:
        return False

def _slug_para_titulo_v129_1(url: str) -> str:
    try:
        from urllib.parse import urlparse, unquote
        path = unquote(urlparse(str(url or "")).path or "")
        slug = path.strip("/").split("/")[-1]
        slug = re.sub(r"\.(html?|ghtm|shtml|php)$", "", slug, flags=re.I)
        slug = re.sub(r"[-_]+", " ", slug).strip()
        if not slug or _titulo_generico_v129_1(slug):
            return ""
        return slug[:1].upper() + slug[1:]
    except Exception:
        return ""

def _titulo_visual_v129_1(p: dict) -> str:
    """Título robusto para a fila. Evita cards de baixo score com rótulos genéricos como 'A HORA'."""
    if not isinstance(p, dict):
        return "Sem título identificado"
    campos_titulo = [
        "_v129_titulo_visual", "titulo_origem", "titulo", "title", "headline",
        "og_title", "og:title", "meta_title", "titulo_extraido", "titulo_fonte",
    ]
    for campo in campos_titulo:
        val = _limpar_titulo_visual_v129_1(p.get(campo, ""))
        if val and not _titulo_generico_v129_1(val):
            return val[:180]
    campos_resumo = ["resumo_origem", "resumo", "description", "descricao", "subtitulo", "lead", "summary"]
    for campo in campos_resumo:
        val = _limpar_titulo_visual_v129_1(p.get(campo, ""))
        if val and not _titulo_generico_v129_1(val):
            # usa a primeira frase ou os primeiros 150 caracteres como título de avaliação
            val = re.split(r"(?<=[.!?])\s+", val)[0].strip() or val
            return val[:150]
    slug = _slug_para_titulo_v129_1(p.get("link_origem") or p.get("url") or "")
    if slug:
        return slug[:150]
    return "Sem título identificado"


# ── Prioridade visual v129.12 ───────────────────────────────────────────────

def _termos_config_ativos_set_v12912() -> set[str]:
    try:
        from ururau.coleta.termos_config_v98 import carregar_termos, normalizar
        return {normalizar(str(t.get("termo") or "")) for t in carregar_termos(criar_se_ausente=True) if t.get("ativo", True) and str(t.get("termo") or "").strip()}
    except Exception:
        return set()

def _filtrar_termos_prioridade_ativos_v12912(termos) -> list[str]:
    if isinstance(termos, str):
        termos = [termos]
    try:
        from ururau.coleta.termos_config_v98 import normalizar
        ativos = _termos_config_ativos_set_v12912()
        saida = []
        vistos = set()
        for t in termos or []:
            st = str(t or "").strip()
            nt = normalizar(st)
            if st and nt in ativos and nt not in vistos:
                saida.append(st)
                vistos.add(nt)
        return saida
    except Exception:
        return [str(t) for t in (termos or []) if str(t).strip()]


# ── Widget: fila virtualizada ─────────────────────────────────────────────────

class FilaPautas(tk.Frame):
    """Fila de pautas v129.9 em Canvas puro.

    Esta versão elimina quase todos os widgets por card. A fila passa a desenhar
    linhas leves diretamente no Canvas, mantendo apenas os dados em memória.
    Isso evita travamentos causados por centenas de Frames/Labels/Buttons sendo
    destruídos e recriados durante coleta, hidratação de texto e imagem.
    """

    _BUFFER = 6
    _ROW_H = max(78, _ITEM_H)

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, bg=_COR_ITEM_PAR, **kwargs)
        self._on_select = on_select
        self._on_select_callback = on_select
        self._on_gerar_callback = lambda p: None
        self._on_abrir_callback = lambda p: None
        self._on_descartar_callback = None
        self._on_selecao_mudou = None
        self._on_reativar_callback = None
        self._on_aprovar_baixo_score_callback = None
        self._on_reprovar_baixo_score_callback = None

        self._itens: list[dict] = []
        self._uids_cache: list[str] = []
        self._sel_idx: Optional[int] = None
        self._selecionados: set[str] = set()
        self._modo_selecao = False
        self._hit_actions: list[tuple[float, float, float, float, str, int]] = []
        self._redraw_after_id = None
        self._last_width = 1

        self._canvas = tk.Canvas(self, bg=_COR_ITEM_PAR, highlightthickness=0, bd=0)
        self._sb = tk.Scrollbar(self, orient="vertical", command=self._sb_cmd)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._canvas.configure(takefocus=True)
        self._canvas.bind("<Configure>", self._on_canvas_cfg)
        self._canvas.bind("<MouseWheel>", self._scroll)
        self._canvas.bind("<Button-4>", self._scroll)
        self._canvas.bind("<Button-5>", self._scroll)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Up>", self._nav_cima)
        self._canvas.bind("<Down>", self._nav_baixo)
        self._canvas.bind("<Return>", self._nav_enter)
        self._canvas.bind("<space>", self._nav_enter)
        self._canvas.bind("<Prior>", self._nav_pgup)
        self._canvas.bind("<Next>", self._nav_pgdn)
        self._canvas.bind("<Home>", self._nav_home)
        self._canvas.bind("<End>", self._nav_end)
        self._canvas.bind("<Delete>", self._nav_delete)

    # ── utilidades internas ────────────────────────────────────────────────

    def _uid(self, p: dict, idx: int = 0) -> str:
        return str(p.get("uid") or p.get("_uid") or p.get("link_origem") or p.get("url") or idx)

    def _total_h(self) -> int:
        return max(1, len(self._itens) * self._ROW_H)

    def _fonte(self, p: dict) -> str:
        return str(p.get("fonte_nome") or p.get("fonte") or p.get("nome_fonte") or "")

    def _titulo(self, p: dict) -> str:
        try:
            return _titulo_visual_v129_1(p)
        except Exception:
            return str(p.get("titulo_origem") or p.get("titulo") or p.get("headline") or p.get("link_origem") or p.get("url") or "Sem título identificado")[:180]

    def _termos_prioridade(self, p: dict) -> list[str]:
        # v129.12: selo PRIORIDADE só pode refletir termos ativos em Config > Termos.
        # Se uma pauta antiga ficou com _v129_termos_positivos=Poder360 em memória,
        # mas Poder360 foi removido e salvo, o selo some imediatamente.
        termos = p.get("_v129_termos_positivos") or p.get("_v129_termos_prioridade") or []
        return _filtrar_termos_prioridade_ativos_v12912(termos)

    def _badge_textos(self, p: dict) -> list[tuple[str, str, str]]:
        status = str(p.get("status") or "")
        canal = str(p.get("canal_forcado") or p.get("canal") or "")
        st_fonte = str(p.get("status_fonte_v105") or ("ok" if p.get("cleaned_source_text") else "pendente")).lower()
        termos = self._termos_prioridade(p)
        badges = []
        cor_status = _STATUS_COR.get(status, COR_CINZA)
        if status:
            badges.append((status.upper()[:12], cor_status, "#000000"))
        if canal:
            badges.append((canal[:16], "#0f2740", COR_CIANO))
        if termos:
            badges.append((f"PRIORIDADE: {termos[0][:24]}", "#0f766e", "#ccfbf1"))
        if st_fonte == "ok":
            badges.append(("TXT OK", "#14532d", "#86efac"))
        elif st_fonte in ("buscando", "pendente"):
            badges.append(("TXT...", "#1e3a5f", "#7dd3fc"))
        elif st_fonte == "aguardando_429":
            badges.append(("TXT 429", "#78350f", "#fde68a"))
        elif st_fonte == "curta":
            badges.append(("TXT CURTO", "#92400e", "#fde68a"))
        else:
            badges.append(("TXT Ø", "#7f1d1d", "#fecaca"))
        sc_risco = p.get("score_risco", 0) or 0
        if sc_risco >= LIMIAR_RISCO_MAXIMO:
            badges.append(("RISCO", COR_VERMELHO, "white"))
        elif sc_risco >= 30:
            badges.append(("REVISAR", "#92400e", "#fde68a"))
        if p.get("urgente"):
            badges.append(("URGENTE", "#7c2d12", "#fed7aa"))
        return badges

    def _request_redraw(self, delay: int = 16):
        try:
            if self._redraw_after_id is not None:
                return
            self._redraw_after_id = self.after(delay, self._redraw_visible)
        except Exception:
            self._redraw_visible()

    # ── API pública ────────────────────────────────────────────────────────

    def popular(self, itens: list[dict]):
        """Atualiza dados sem destruir a interface.

        A fila preserva o item visível no topo como âncora. Assim, quando novas
        pautas entram acima por ordenação cronológica, a leitura não salta.
        """
        itens = list(itens or [])
        old = self._itens
        old_uids = [self._uid(p, i) for i, p in enumerate(old)]
        new_uids = [self._uid(p, i) for i, p in enumerate(itens)]
        if new_uids == self._uids_cache:
            # Mesmo conjunto/ordem. Ainda pode ter mudado status/texto; redesenho leve.
            self._itens = itens
            self._request_redraw(80)
            return

        # Âncora visual: UID no topo da viewport e offset dentro da linha.
        anchor_uid = None
        anchor_offset = 0.0
        try:
            top_y = float(self._canvas.canvasy(0))
            top_idx = int(max(0, min(len(old) - 1, top_y // self._ROW_H))) if old else 0
            if old:
                anchor_uid = self._uid(old[top_idx], top_idx)
                anchor_offset = top_y - (top_idx * self._ROW_H)
        except Exception:
            anchor_uid = None

        # Preserva seleção por UID.
        sel_uid = None
        try:
            if self._sel_idx is not None and 0 <= self._sel_idx < len(old):
                sel_uid = self._uid(old[self._sel_idx], self._sel_idx)
        except Exception:
            sel_uid = None

        self._itens = itens
        self._uids_cache = new_uids
        self._canvas.configure(scrollregion=(0, 0, max(1, self._canvas.winfo_width()), self._total_h()))

        if sel_uid and sel_uid in new_uids:
            self._sel_idx = new_uids.index(sel_uid)
        elif self._sel_idx is not None and self._sel_idx >= len(itens):
            self._sel_idx = None

        # Restaura âncora depois que a scrollregion mudou.
        if anchor_uid and anchor_uid in new_uids and len(itens) > 0:
            try:
                new_idx = new_uids.index(anchor_uid)
                y = max(0.0, (new_idx * self._ROW_H) + anchor_offset)
                self._canvas.yview_moveto(min(1.0, y / max(1, self._total_h())))
            except Exception:
                pass

        self._request_redraw(1)

    def set_callbacks(self, on_select, on_gerar, on_descartar=None,
                      on_selecao_mudou=None, on_reativar=None, on_aprovar_baixo_score=None,
                      on_reprovar_baixo_score=None, on_abrir=None):
        # v129.11: on_select é exclusivamente seleção/detalhe da pauta.
        # Abertura de preview é callback separado, acionado apenas por botão específico.
        self._on_select_callback = on_select
        self._on_select = on_select
        self._on_gerar_callback = on_gerar
        self._on_abrir_callback = on_abrir or (lambda p: None)
        self._on_descartar_callback = on_descartar
        self._on_selecao_mudou = on_selecao_mudou
        self._on_reativar_callback = on_reativar
        self._on_aprovar_baixo_score_callback = on_aprovar_baixo_score
        self._on_reprovar_baixo_score_callback = on_reprovar_baixo_score

    def get_uids_selecionados(self) -> list[str]:
        return list(self._selecionados)

    def limpar_selecao(self):
        self._selecionados.clear()
        self._modo_selecao = False
        self._request_redraw(1)
        if self._on_selecao_mudou:
            self._on_selecao_mudou(0)

    def selecionar_todos_visiveis(self):
        self._selecionados = {self._uid(p, i) for i, p in enumerate(self._itens) if not p.get("_separador_coleta_v123")}
        self._modo_selecao = True
        self._request_redraw(1)
        if self._on_selecao_mudou:
            self._on_selecao_mudou(len(self._selecionados))

    def get_selecionado(self) -> Optional[dict]:
        if self._sel_idx is not None and 0 <= self._sel_idx < len(self._itens):
            return self._itens[self._sel_idx]
        return None

    def focar(self):
        self._canvas.focus_set()

    # ── desenho ────────────────────────────────────────────────────────────

    def _on_canvas_cfg(self, _=None):
        self._last_width = max(1, self._canvas.winfo_width())
        self._canvas.configure(scrollregion=(0, 0, self._last_width, self._total_h()))
        self._request_redraw(1)

    def _sb_cmd(self, *args):
        self._canvas.yview(*args)
        self._request_redraw(1)

    def _scroll(self, e):
        if getattr(e, "num", None) == 4:
            self._canvas.yview_scroll(-3, "units")
        elif getattr(e, "num", None) == 5:
            self._canvas.yview_scroll(3, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (getattr(e, "delta", 0) / 120)), "units")
        self._request_redraw(1)
        return "break"

    def _redraw_visible(self):
        self._redraw_after_id = None
        c = self._canvas
        try:
            w = max(1, c.winfo_width())
            h = max(1, c.winfo_height())
            total_h = self._total_h()
            c.configure(scrollregion=(0, 0, w, total_h))
            top = float(c.canvasy(0))
            bottom = top + h
            ini = max(0, int(top // self._ROW_H) - self._BUFFER)
            fim = min(len(self._itens) - 1, int(bottom // self._ROW_H) + self._BUFFER)
            c.delete("row")
            self._hit_actions = []
            if not self._itens:
                return
            for idx in range(ini, fim + 1):
                self._draw_row(idx, w)
        except Exception as e:
            try:
                c.delete("row")
                c.create_text(10, 10, anchor="nw", text=f"Erro visual na fila: {e}", fill="#fecaca", tags="row")
            except Exception:
                pass

    def _draw_badge(self, x, y, text, bg, fg):
        c = self._canvas
        txt = str(text)
        width = max(38, min(190, 8 * len(txt) + 12))
        c.create_rectangle(x, y, x + width, y + 17, fill=bg, outline=bg, tags="row")
        c.create_text(x + 6, y + 8, anchor="w", text=txt, fill=fg, font=("Segoe UI", 7, "bold"), tags="row")
        return x + width + 5

    def _draw_button(self, x1, y1, x2, y2, text, bg, fg, action, idx):
        c = self._canvas
        c.create_rectangle(x1, y1, x2, y2, fill=bg, outline=bg, tags="row")
        c.create_text((x1+x2)/2, (y1+y2)/2, text=text, fill=fg, font=("Segoe UI", 8, "bold"), tags="row")
        self._hit_actions.append((x1, y1, x2, y2, action, idx))

    def _draw_row(self, idx: int, w: int):
        p = self._itens[idx]
        y = idx * self._ROW_H
        status = str(p.get("status") or "")
        uid = self._uid(p, idx)
        sep = bool(p.get("_separador_coleta_v123"))
        selecionado = idx == self._sel_idx
        termos = self._termos_prioridade(p)

        if sep:
            bg = "#071528"
            border = "#22d3ee"
        elif selecionado:
            bg = "#3b1f6e"
            border = "#8b5cf6"
        elif status == "excluida":
            bg = _COR_ITEM_EXCLUIDA
            border = COR_CINZA
        elif status == "baixo_score":
            bg = "#2a1644"
            border = "#f59e0b"
        elif termos:
            bg = "#102a36"
            border = "#14b8a6"
        else:
            bg = _COR_ITEM_PAR if idx % 2 == 0 else _COR_ITEM_IMPAR
            border = "#334155"

        c = self._canvas
        c.create_rectangle(0, y, w, y + self._ROW_H - 1, fill=bg, outline=bg, tags="row")
        c.create_rectangle(0, y, 4, y + self._ROW_H - 1, fill=border, outline=border, tags="row")

        if sep:
            titulo = str(p.get("titulo_origem") or "Coleta")
            sub = str(p.get("_subtitulo_separador_v123") or "Separador visual.")
            c.create_text(18, y + 22, anchor="w", text=titulo, fill="#67e8f9", font=("Segoe UI", 10, "bold"), tags="row")
            c.create_text(18, y + 46, anchor="w", text=sub, fill="#94a3b8", font=("Segoe UI", 8), tags="row")
            return

        # Checkbox
        checked = uid in self._selecionados
        c.create_rectangle(13, y + 34, 25, y + 46, fill=("#1e3a5f" if checked else bg), outline="#94a3b8", tags="row")
        if checked:
            c.create_text(19, y + 40, text="✓", fill="#7dd3fc", font=("Segoe UI", 8, "bold"), tags="row")

        x = 38
        for text, bbg, ffg in self._badge_textos(p)[:6]:
            if x > max(250, w - 260):
                break
            x = self._draw_badge(x, y + 8, text, bbg, ffg)

        # Ações à direita
        if status == "excluida":
            self._draw_button(w - 112, y + 7, w - 24, y + 26, "↩ Reativar", "#374151", "#d1d5db", "reativar", idx)
        elif status == "baixo_score":
            self._draw_button(w - 206, y + 7, w - 116, y + 26, "✕ Reprovar", "#7f1d1d", "#fecaca", "reprovar_baixo", idx)
            self._draw_button(w - 106, y + 7, w - 24, y + 26, "✓ Aprovar", "#92400e", "#fde68a", "aprovar_baixo", idx)
        elif p.get("materia"):
            self._draw_button(w - 126, y + 7, w - 24, y + 26, "✓ Ver Matéria", "#14532d", "#86efac", "abrir", idx)
        else:
            self._draw_button(w - 92, y + 7, w - 24, y + 26, "▶ Gerar", "#1e3a5f", "#7dd3fc", "gerar", idx)

        # Título e metadados
        titulo = self._titulo(p)
        # Corte visual simples para evitar cálculo pesado de wrap por widget.
        max_chars = max(45, int((w - 90) / 7.2))
        if len(titulo) > max_chars:
            titulo = titulo[:max_chars - 1] + "…"
        c.create_text(38, y + 38, anchor="w", text=titulo, fill=("#ffffff" if selecionado else COR_TEXTO), font=("Segoe UI", 10, "bold" if selecionado else "normal"), tags="row")

        fonte = self._fonte(p)[:28]
        data_pub = str(p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or "")[:16]
        meta = "  ·  ".join([x for x in [fonte, ("Publicado: " + data_pub if data_pub else "")] if x])
        if meta:
            c.create_text(38, y + 61, anchor="w", text=meta, fill=COR_CINZA, font=FONTE_META, tags="row")
        c.create_line(0, y + self._ROW_H - 1, w, y + self._ROW_H - 1, fill="#2a2a4a", tags="row")

    # ── ações/seleção ──────────────────────────────────────────────────────

    def _on_click(self, e):
        self._canvas.focus_set()
        x = float(self._canvas.canvasx(e.x))
        y = float(self._canvas.canvasy(e.y))
        idx = int(y // self._ROW_H)
        if idx < 0 or idx >= len(self._itens):
            return "break"
        for x1, y1, x2, y2, action, aidx in list(self._hit_actions):
            if aidx == idx and x1 <= x <= x2 and y1 <= y <= y2:
                self._executar_acao(action, idx)
                return "break"
        if 8 <= x <= 32:
            self._toggle_checkbox(idx)
            return "break"
        self._selecionar(idx)
        return "break"

    def _toggle_checkbox(self, idx: int):
        try:
            p = self._itens[idx]
            uid = self._uid(p, idx)
            if uid in self._selecionados:
                self._selecionados.remove(uid)
            else:
                self._selecionados.add(uid)
            self._modo_selecao = bool(self._selecionados)
            if self._on_selecao_mudou:
                self._on_selecao_mudou(len(self._selecionados))
            self._request_redraw(1)
        except Exception:
            pass

    def _executar_acao(self, action: str, idx: int):
        """Executa somente a ação clicada no Canvas.

        v129.10: o clique no corpo da pauta deve apenas selecionar e carregar o
        painel Detalhe/Fonte. A ação de preview ficou restrita ao botão de ação
        e, mesmo nele, não abre modal se a matéria ainda não foi gerada: apenas
        seleciona a pauta. Isso restaura o contrato da fila antiga e evita o
        alerta incorreto "Sem matéria gerada" ao clicar no card.
        """
        self._selecionar(idx, chamar_callback=False)
        p = self._itens[idx]
        if action == "reativar" and self._on_reativar_callback:
            self.after(10, lambda p=p: self._on_reativar_callback(p))
        elif action == "aprovar_baixo" and self._on_aprovar_baixo_score_callback:
            self.after(10, lambda p=p: self._on_aprovar_baixo_score_callback(p))
        elif action == "reprovar_baixo" and self._on_reprovar_baixo_score_callback:
            self.after(10, lambda p=p: self._on_reprovar_baixo_score_callback(p))
        elif action == "abrir":
            # Botão de preview: primeiro mantém o painel de detalhe sincronizado,
            # depois chama a rotina de preview. O clique comum no card nunca passa por aqui.
            try:
                self.after(1, lambda p=p: self._on_select(p))
            except Exception:
                pass
            try:
                self.after(20, lambda p=p: self._on_abrir_callback(p))
            except Exception:
                pass
        elif action == "gerar":
            try:
                self.after(1, lambda p=p: self._on_select(p))
            except Exception:
                pass
            self.after(20, lambda p=p: self._on_gerar_callback(p))
        else:
            self.after(10, lambda p=p: self._on_select(p))

    def _selecionar(self, idx: int, chamar_callback: bool = True):
        if idx is None or idx < 0 or idx >= len(self._itens):
            return
        self._sel_idx = idx
        self._request_redraw(1)
        if chamar_callback:
            try:
                self._on_select(self._itens[idx])
            except Exception:
                pass

    # Compatibilidade com métodos antigos usados por navegação/botões
    def _on_btn_acao(self, idx: int):
        p = self._itens[idx]
        if p.get("status") == "excluida":
            self._executar_acao("reativar", idx)
        elif p.get("status") == "baixo_score":
            self._executar_acao("aprovar_baixo", idx)
        elif p.get("materia"):
            self._executar_acao("abrir", idx)
        else:
            self._executar_acao("gerar", idx)

    def _on_btn_reprovar_baixo_score(self, idx: int):
        self._executar_acao("reprovar_baixo", idx)

    # ── teclado ────────────────────────────────────────────────────────────

    def _nav_cima(self, _=None):
        if not self._itens:
            return "break"
        novo = (len(self._itens) - 1) if self._sel_idx is None else max(0, self._sel_idx - 1)
        self._selecionar(novo)
        self._scroll_para_visivel(novo)
        return "break"

    def _nav_baixo(self, _=None):
        if not self._itens:
            return "break"
        novo = 0 if self._sel_idx is None else min(len(self._itens) - 1, self._sel_idx + 1)
        self._selecionar(novo)
        self._scroll_para_visivel(novo)
        return "break"

    def _nav_enter(self, _=None):
        idx = self._sel_idx
        if idx is None or idx >= len(self._itens):
            return "break"
        # Enter/Espaço mantém o comportamento operacional: se houver matéria
        # gerada, tenta abrir preview; se não houver, gera. O clique comum no
        # corpo do card continua sendo apenas seleção.
        self._executar_acao("abrir" if self._itens[idx].get("materia") else "gerar", idx)
        return "break"

    def _nav_pgup(self, _=None):
        if not self._itens:
            return "break"
        novo = max(0, (self._sel_idx or 0) - 7)
        self._selecionar(novo)
        self._scroll_para_visivel(novo)
        return "break"

    def _nav_pgdn(self, _=None):
        if not self._itens:
            return "break"
        novo = min(len(self._itens) - 1, (self._sel_idx if self._sel_idx is not None else -1) + 7)
        self._selecionar(novo)
        self._scroll_para_visivel(novo)
        return "break"

    def _nav_home(self, _=None):
        if self._itens:
            self._selecionar(0)
            self._canvas.yview_moveto(0)
            self._request_redraw(1)
        return "break"

    def _nav_end(self, _=None):
        if self._itens:
            idx = len(self._itens) - 1
            self._selecionar(idx)
            self._scroll_para_visivel(idx)
        return "break"

    def _nav_delete(self, _=None):
        if self._sel_idx is not None and self._on_descartar_callback:
            try:
                self._on_descartar_callback(self._itens[self._sel_idx], self._sel_idx)
            except Exception:
                pass
        return "break"

    def _scroll_para_visivel(self, idx: int):
        if not self._itens:
            return
        total = self._total_h()
        item_top = idx * self._ROW_H
        item_bot = item_top + self._ROW_H
        y_top = float(self._canvas.canvasy(0))
        y_bot = y_top + max(1, self._canvas.winfo_height())
        if item_top < y_top:
            self._canvas.yview_moveto(max(0.0, item_top / total))
        elif item_bot > y_bot:
            self._canvas.yview_moveto(max(0.0, (item_bot - self._canvas.winfo_height()) / total))
        self._request_redraw(1)


# ── Painel principal ───────────────────────────────────────────────────────────

class PainelUrurau(tk.Tk):
    """Interface principal do sistema Ururau — v21."""

    def __init__(self, db: "Database" = None, client: "OpenAI" = None,
                 modelo: str = MODELO_OPENAI):
        super().__init__()
        self.db     = db or get_db()
        self.client = client
        self.modelo = modelo
        self._pautas_cache: list[dict] = []
        self._pauta_sel: Optional[dict] = None
        self._carregando_aba   = False
        self._carregando_lista = False
        # v129.8: debouncer global de refresh da fila. Evita que coleta,
        # hidratação textual e imagem chamem reload do banco a cada pequeno evento.
        self._v1298_refresh_after_id = None
        self._v1298_last_refresh = 0.0

        # v105/v106: fila persistente de hidratação da fonte.
        # Texto da fonte é prioridade operacional; imagem fica em segundo plano,
        # mas volta a ser processada automaticamente logo depois do texto OK.
        self._hidratar_lock = threading.RLock()
        self._hidratar_jobs = []  # lista de dicts: {pauta, uid, prioridade, run_at, motivo}
        self._hidratar_inflight = set()
        self._hidratar_worker_started = False
        self._hidratar_domain_cooldown = {}
        self._hidratar_stop = False

        # v106: fila própria para imagem. Separar texto e imagem evita travar a
        # extração textual, mas não deixa o sistema parar de buscar foto.
        self._imagem_lock = threading.RLock()
        self._imagem_jobs = []
        self._imagem_inflight = set()
        self._imagem_worker_started = False
        self._imagem_stop = False

        self._configurar_janela()
        self._construir_interface()
        self._carregar_pautas()
        self._v105_iniciar_hidratador()
        self._v106_iniciar_imagem_worker()

        # v94: ao abrir o sistema, iniciar coleta automática em segundo plano,
        # sem chamar método inexistente e sem travar a construção da janela.
        self._auto_coleta_v94_iniciada = False
        self._coleta_em_andamento = False
        if self._env_bool("URURAU_V92_AUTO_COLETAR_AO_ABRIR", "1"):
            self.after(1200, self._auto_coleta_v94)

    def _env_bool(self, chave: str, padrao: str = "0") -> bool:
        return os.getenv(chave, padrao).lower() in ("1", "true", "sim", "yes", "s")

    def _env_int(self, chave: str, padrao: int) -> int:
        try:
            return int(os.getenv(chave, str(padrao)) or str(padrao))
        except Exception:
            return padrao


    # ── Hidratação persistente da fonte (v105) ───────────────────────────────

    def _v105_min_chars_fonte(self) -> int:
        return self._env_int("URURAU_V108_MIN_TEXTO_FONTE_OK", self._env_int("URURAU_V105_MIN_CHARS_FONTE_OK", self._env_int("URURAU_V104_MIN_CHARS_ARTIGO", 900)))

    def _v105_uid_pauta(self, pauta: dict) -> str:
        return str(pauta.get("uid") or pauta.get("_uid") or "")

    def _v105_texto_fonte_util(self, pauta: dict) -> tuple[bool, int, str]:
        # fix/auditoria-fila-scrapling-v136: contrato oficial de texto da fonte.
        # Cadeia canonica: cleaned_source_text -> v134 -> texto_fonte -> v105 -> raw -> dossie.
        # Nao sobrescreve texto valido com vazio (regra garantida em set_source_text).
        try:
            from ururau.core.source_text_contract import get_source_text, texto_util_chars as _tuc, min_valid as _mv
            texto = get_source_text(pauta) or pauta.get("fonte_aba_texto") or pauta.get("leitura_fonte_texto") or ""
            util = int(_tuc(str(texto)))
            # Respeita o minimo do projeto (default 900 nesta base) se for maior que 550.
            minimo = max(int(_mv()), int(self._v105_min_chars_fonte()))
            return util >= minimo, util, str(texto or "")
        except Exception:
            # Fallback inline (modo defensivo): preserva o comportamento anterior
            # caso o contrato nao esteja disponivel por algum motivo de import.
            texto = (
                pauta.get("cleaned_source_text") or pauta.get("fonte_aba_texto") or
                pauta.get("leitura_fonte_texto") or pauta.get("dossie") or pauta.get("texto_fonte") or ""
            )
            try:
                from ururau.coleta.limpeza_texto_v81 import texto_util_chars
                util = int(texto_util_chars(str(texto)))
            except Exception:
                util = len(str(texto or "").strip())
            return util >= self._v105_min_chars_fonte(), util, str(texto or "")

    def _v105_parse_pauta_db(self, row: dict) -> dict:
        d = dict(row or {})
        try:
            extra = json.loads(d.get("dados_json") or "{}")
            if isinstance(extra, dict):
                d.update(extra)
        except Exception:
            pass
        if d.get("uid") and not d.get("_uid"):
            d["_uid"] = d.get("uid")
        return d

    def _v105_carregar_pauta_uid(self, uid: str) -> dict | None:
        if not uid:
            return None
        try:
            row = self.db.buscar_pauta(uid)
            if row:
                return self._v105_parse_pauta_db(row)
        except Exception:
            return None
        return None

    def _v105_iniciar_hidratador(self):
        if self._hidratar_worker_started:
            return
        self._hidratar_worker_started = True
        threading.Thread(target=self._v105_hidratador_loop, daemon=True).start()
        print("[v105][FONTE] Hidratador persistente iniciado; texto tem prioridade sobre imagem.")

    # ── Imagem automática em baixa prioridade (v106) ───────────────────────────

    def _v106_uid_pauta(self, pauta: dict) -> str:
        return str(pauta.get("uid") or pauta.get("_uid") or "")

    def _v106_imagem_ok(self, pauta: dict) -> bool:
        caminho = str(pauta.get("imagem_caminho") or "").strip()
        if caminho:
            try:
                return Path(caminho).exists()
            except Exception:
                return True
        return str(pauta.get("imagem_status") or "").lower() == "aprovada"

    def _v106_iniciar_imagem_worker(self):
        if self._imagem_worker_started:
            return
        self._imagem_worker_started = True
        threading.Thread(target=self._v106_imagem_loop, daemon=True).start()
        print("[v106][IMG] Worker automático iniciado; imagem roda depois do texto.")

    def _v106_agendar_imagem(self, pauta: dict, motivo: str = "texto_ok", delay: float = 0.0, prioridade: bool = False):
        """Agenda busca/processamento de imagem sem bloquear a hidratação textual."""
        if not pauta:
            return
        if os.getenv("URURAU_V106_AUTO_IMAGEM_APOS_TEXTO", "1").strip().lower() in ("0", "false", "nao", "não"):
            return
        if self._v106_imagem_ok(pauta):
            return
        uid = self._v106_uid_pauta(pauta)
        link = str(pauta.get("link_origem") or "").strip()
        if not uid and not link:
            return
        fonte_ok, util, _ = self._v105_texto_fonte_util(pauta)
        if not fonte_ok and not pauta.get("imagem_url") and not pauta.get("imagem_url_rss"):
            return
        key = uid or link
        job = {
            "uid": uid,
            "link": link,
            "pauta": dict(pauta),
            "run_at": time.time() + max(0.0, float(delay or 0.0)),
            "prioridade": 0 if prioridade else 1,
            "motivo": motivo,
        }
        with self._imagem_lock:
            if key in self._imagem_inflight:
                return
            for j in self._imagem_jobs:
                if (j.get("uid") or j.get("link")) == key:
                    return
            self._imagem_jobs.append(job)
            self._imagem_jobs.sort(key=lambda j: (j.get("prioridade", 1), j.get("run_at", 0)))
        print(f"[v106][IMG] agendada ({motivo}): {(pauta.get('titulo_origem') or '')[:80]}")

    def _v106_pop_imagem_job(self) -> dict | None:
        now = time.time()
        with self._imagem_lock:
            self._imagem_jobs.sort(key=lambda j: (j.get("prioridade", 1), j.get("run_at", 0)))
            for i, job in enumerate(self._imagem_jobs):
                if job.get("run_at", 0) <= now:
                    return self._imagem_jobs.pop(i)
        return None

    def _v106_imagem_loop(self):
        while not getattr(self, "_imagem_stop", False):
            try:
                job = self._v106_pop_imagem_job()
                if not job:
                    time.sleep(1.0)
                    continue
                uid = job.get("uid") or ""
                pauta = self._v105_carregar_pauta_uid(uid) if uid else None
                if not pauta:
                    pauta = dict(job.get("pauta") or {})
                if self._v106_imagem_ok(pauta):
                    continue
                fonte_ok, util, _ = self._v105_texto_fonte_util(pauta)
                if not fonte_ok and not pauta.get("imagem_url") and not pauta.get("imagem_url_rss"):
                    self._v106_agendar_imagem(pauta, motivo="aguardando_texto", delay=45)
                    continue
                self._v106_buscar_imagem_auto(pauta, origem=job.get("motivo") or "worker")
                time.sleep(float(os.getenv("URURAU_V106_INTERVALO_ENTRE_IMAGENS", "2.5") or "2.5"))
            except Exception as e:
                print(f"[v106][IMG] erro no worker: {e}")
                time.sleep(2.0)

    def _v106_buscar_imagem_auto(self, pauta: dict, origem: str = "worker"):
        uid = self._v106_uid_pauta(pauta)
        link = str(pauta.get("link_origem") or "").strip()
        key = uid or link
        if not key:
            return False
        with self._imagem_lock:
            if key in self._imagem_inflight:
                return None
            self._imagem_inflight.add(key)
        try:
            url_preferida = str(pauta.get("imagem_url") or pauta.get("imagem_url_rss") or "").strip()
            if url_preferida:
                try:
                    from ururau.imaging.processamento import baixar_imagem, processar_imagem, validar_imagem
                    from ururau.config.settings import PASTA_IMAGENS
                    caminho_original = baixar_imagem(url_preferida, PASTA_IMAGENS, uid)
                    if caminho_original:
                        caminho_final = processar_imagem(caminho_original, uid, PASTA_IMAGENS)
                        if caminho_final:
                            ok_final, info_final = validar_imagem(caminho_final)
                            if ok_final:
                                pauta["imagem_status"] = "aprovada"
                                pauta["imagem_caminho"] = caminho_final
                                pauta["imagem_url"] = url_preferida
                                pauta["imagem_credito"] = pauta.get("imagem_credito") or "Reprodução"
                                pauta["imagem_estrategia"] = "rss_ou_fonte_v106"
                                self.db.salvar_pauta(pauta)
                                try:
                                    self.db.salvar_imagem(uid, {
                                        "caminho_imagem": caminho_final,
                                        "caminho_original": caminho_original,
                                        "url_imagem": url_preferida,
                                        "credito_foto": pauta.get("imagem_credito") or "Reprodução",
                                        "estrategia_imagem": "rss_ou_fonte_v106",
                                        "score_imagem": 1,
                                        "dimensoes_origem": f"{info_final.get('largura', 0)}x{info_final.get('altura', 0)}",
                                    })
                                except Exception:
                                    pass
                                print(f"[v107][IMG] OK via URL prévia ({origem}): {(pauta.get('titulo_origem') or '')[:80]}")
                                _v107_notificar_imagem_atualizada(self, pauta)
                                self.after(0, self._carregar_pautas)
                                return True
                except Exception as e:
                    print(f"[v106][IMG] URL prévia falhou: {e}")

            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            if not uid:
                uid = _uid_para_pauta(link, pauta.get("titulo_origem", ""))
                pauta["_uid"] = uid
            pauta["imagem_status"] = "buscando"
            self.db.salvar_pauta(pauta)
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            res = wf.etapa_imagem(uid, pauta)
            if res and getattr(res, "caminho_imagem", ""):
                pauta["imagem_status"] = "aprovada"
                pauta["imagem_caminho"] = res.caminho_imagem
                pauta["imagem_url"] = getattr(res, "url_imagem", "")
                pauta["imagem_credito"] = getattr(res, "credito_foto", "") or "Reprodução"
                pauta["imagem_estrategia"] = getattr(res, "estrategia_imagem", "") or "pipeline"
                self.db.salvar_pauta(pauta)
                print(f"[v107][IMG] OK via pipeline ({origem}): {(pauta.get('titulo_origem') or '')[:80]}")
                _v107_notificar_imagem_atualizada(self, pauta)
                self.after(0, self._carregar_pautas)
                return True
            # v47.4: imagem é etapa posterior ao texto e não deve desistir no primeiro erro.
            tent_img = int(pauta.get("imagem_tentativas_v106") or 0) + 1
            pauta["imagem_tentativas_v106"] = tent_img
            max_img = self._env_int("URURAU_V106_MAX_TENTATIVAS_IMAGEM", 8)
            hard_img = self._env_int("URURAU_V47_IMAGEM_HARD_CAP_TENTATIVAS", 32)
            persistir_img = str(os.getenv("URURAU_V47_IMAGEM_TENTAR_ATE_OK", "1")).strip().lower() not in {"0", "false", "nao", "não", "off"}
            if tent_img < max_img or (persistir_img and tent_img < hard_img):
                pauta["imagem_status"] = "pendente_retry"
                self.db.salvar_pauta(pauta)
                atraso = self._env_int("URURAU_V47_IMAGEM_RETRY_SEG", 900)
                self._v106_agendar_imagem(pauta, motivo=f"retry_imagem_{tent_img}", delay=atraso)
                print(f"[v106][IMG] sem imagem; retry agendado ({tent_img}/{hard_img}) ({origem}): {(pauta.get('titulo_origem') or '')[:80]}")
                return False
            pauta["imagem_status"] = "sem_imagem_max_tentativas"
            self.db.salvar_pauta(pauta)
            print(f"[v106][IMG] sem imagem após limite ({tent_img}/{hard_img}) ({origem}): {(pauta.get('titulo_origem') or '')[:80]}")
            return False
        finally:
            with self._imagem_lock:
                self._imagem_inflight.discard(key)

    def _v105_agendar_hidratacao(self, pauta: dict, prioridade: bool = False, motivo: str = "fila", delay: float = 0.0):
        if not pauta:
            return
        uid = self._v105_uid_pauta(pauta)
        link = str(pauta.get("link_origem") or "").strip()
        if not uid and not link:
            return
        ok, util, _ = self._v105_texto_fonte_util(pauta)
        if ok:
            return
        job = {
            "uid": uid,
            "link": link,
            "pauta": dict(pauta),
            "prioridade": 0 if prioridade else 1,
            "run_at": time.time() + max(0.0, float(delay or 0.0)),
            "motivo": motivo,
        }
        key = uid or link
        with self._hidratar_lock:
            # evita acumular muitas entradas idênticas; prioridade clicada substitui fila normal.
            kept = []
            for j in self._hidratar_jobs:
                if (j.get("uid") or j.get("link")) == key:
                    if prioridade and j.get("prioridade", 1) > 0:
                        continue
                    if not prioridade:
                        return
                kept.append(j)
            kept.append(job)
            kept.sort(key=lambda j: (j.get("prioridade", 1), j.get("run_at", 0)))
            self._hidratar_jobs = kept
        if prioridade:
            self._set_status("Fonte priorizada: buscando texto completo...")
        print(f"[v105][FONTE] agendada ({'prioridade' if prioridade else 'fila'} | {motivo}): {(pauta.get('titulo_origem') or '')[:90]}")

    def _v105_pop_job(self) -> dict | None:
        now = time.time()
        with self._hidratar_lock:
            self._hidratar_jobs.sort(key=lambda j: (j.get("prioridade", 1), j.get("run_at", 0)))
            for i, job in enumerate(self._hidratar_jobs):
                if job.get("run_at", 0) <= now:
                    return self._hidratar_jobs.pop(i)
        return None

    def _v105_hidratador_loop(self):
        while not getattr(self, "_hidratar_stop", False):
            try:
                job = self._v105_pop_job()
                if not job:
                    time.sleep(0.8)
                    continue
                uid = job.get("uid") or ""
                pauta = self._v105_carregar_pauta_uid(uid) if uid else None
                if not pauta:
                    pauta = dict(job.get("pauta") or {})
                ok, _util, _txt = self._v105_texto_fonte_util(pauta)
                if ok:
                    continue
                self._v105_hidratar_pauta(pauta, origem=job.get("motivo") or "worker", atualizar_ui=False)
                time.sleep(float(os.getenv("URURAU_V105_INTERVALO_ENTRE_FONTES", "1.2") or "1.2"))
            except Exception as e:
                print(f"[v105][FONTE] erro no hidratador: {e}")
                time.sleep(2.0)

    def _v105_hidratar_pauta(self, pauta: dict, origem: str = "worker", forcar: bool = False, atualizar_ui: bool = False):
        uid = self._v105_uid_pauta(pauta)
        link = str(pauta.get("link_origem") or "").strip()
        key = uid or link
        if not key:
            return None
        ok, util_atual, _txt = self._v105_texto_fonte_util(pauta)
        if ok and not forcar:
            if atualizar_ui:
                self.after(0, lambda: self._v105_mostrar_fonte_cache(pauta))
            return True
        host = ""
        try:
            host = urlparse(link).netloc.lower().replace("www.", "")
        except Exception:
            host = ""
        with self._hidratar_lock:
            cooldown = float(self._hidratar_domain_cooldown.get(host, 0) or 0) if host else 0
            if cooldown and cooldown > time.time() and not forcar:
                espera = int(cooldown - time.time())
                pauta["status_fonte_v105"] = "aguardando_429"
                pauta["fonte_erro_v105"] = f"domínio em cooldown por 429; nova tentativa em {espera}s"
                try:
                    self.db.salvar_pauta(pauta)
                except Exception:
                    pass
                self._v105_agendar_hidratacao(pauta, prioridade=False, motivo="cooldown_429", delay=max(espera, 15))
                return False
            if key in self._hidratar_inflight:
                return None
            self._hidratar_inflight.add(key)
        try:
            pauta["status_fonte_v105"] = "buscando"
            pauta["fonte_tentativas_v105"] = int(pauta.get("fonte_tentativas_v105") or 0) + 1
            try:
                self.db.salvar_pauta(pauta)
            except Exception:
                pass
            if atualizar_ui:
                self.after(0, lambda: self._v105_status_fonte_ui("Buscando texto completo...", COR_AMARELO))
            from ururau.coleta.leitura_fonte import ler_fonte_pauta
            res = ler_fonte_pauta(pauta, forcar_refresh=forcar)
            txt = (getattr(res, "texto_limpo", "") or "").strip()
            try:
                from ururau.coleta.limpeza_texto_v81 import texto_util_chars
                util = int(texto_util_chars(txt))
            except Exception:
                util = len(txt)
            min_ok = self._v105_min_chars_fonte()
            if getattr(res, "sucesso", False) and util >= min_ok:
                self._injetar_fonte_longa_v96(pauta, txt, origem=f"v105_{origem}")
                pauta["status_fonte_v105"] = "ok"
                pauta["fonte_chars_v105"] = util
                pauta["fonte_erro_v105"] = ""
                pauta["fonte_url_final_v105"] = getattr(res, "url", "") or link
                try:
                    self.db.salvar_pauta(pauta)
                except Exception:
                    pass
                print(f"[v106][FONTE] OK {util} chars ({origem}): {(pauta.get('titulo_origem') or '')[:80]}")
                # fix/auditoria-fila-scrapling-v136 + spec_claudio_hidratacao_continua:
                # ao terminar uma hidratacao com sucesso, agenda re-aplicacao do
                # filtro/ordem para que a pauta suba para o grupo "TXT OK" no topo.
                # Debounce de 800ms para nao redesenhar a UI em rajada.
                try:
                    if hasattr(self, "_v200_refresh_debounce_after_id"):
                        try:
                            self.after_cancel(self._v200_refresh_debounce_after_id)
                        except Exception:
                            pass
                    self._v200_refresh_debounce_after_id = self.after(
                        800, lambda: self._carregar_pautas(forcar=False)
                    )
                except Exception as _e_v200:
                    print(f"[FILA][CANONICO][AVISO] refresh pos-hidratacao falhou: {_e_v200}")
                # v106: depois do texto OK, agenda imagem automaticamente em baixa prioridade.
                try:
                    img_url = str(getattr(res, "imagem_url", "") or "").strip()
                    if img_url and not pauta.get("imagem_url"):
                        pauta["imagem_url"] = img_url
                        pauta["imagem_url_rss"] = img_url
                        if not pauta.get("imagem_credito"):
                            pauta["imagem_credito"] = "Reprodução"
                        self.db.salvar_pauta(pauta)
                    self._v106_agendar_imagem(pauta, motivo=f"texto_ok:{origem}", delay=float(os.getenv("URURAU_V106_DELAY_IMAGEM_APOS_TEXTO", "1.5") or "1.5"))
                except Exception as _e_img:
                    print(f"[v106][IMG] aviso ao agendar depois do texto: {_e_img}")
                if atualizar_ui:
                    self.after(0, lambda: self._v105_mostrar_resultado_fonte(pauta, res, txt, util))
                return True
            erro = str(getattr(res, "erro", "") or f"texto insuficiente ({util}/{min_ok})")
            if "429" in erro or "Too Many Requests" in erro:
                pausa = self._env_int("URURAU_V105_COOLDOWN_429_SEG", 180)
                if host:
                    with self._hidratar_lock:
                        self._hidratar_domain_cooldown[host] = time.time() + pausa
                status = "aguardando_429"
                delay = pausa
            else:
                status = "curta" if util > 0 else "falhou"
                delay = min(300, 20 * int(pauta.get("fonte_tentativas_v105") or 1))
            pauta["status_fonte_v105"] = status
            pauta["fonte_chars_v105"] = util
            pauta["fonte_erro_v105"] = erro[:300]
            try:
                self.db.salvar_pauta(pauta)
            except Exception:
                pass
            # v47.4: texto completo é prioridade editorial. A tentativa normal sobe para 12,
            # e, se ativado, continua em rechecagens espaçadas até o limite duro.
            max_t = self._env_int("URURAU_V105_MAX_TENTATIVAS_FONTE", 12)
            hard_cap = self._env_int("URURAU_V47_TEXTO_HARD_CAP_TENTATIVAS", 48)
            persistir = str(os.getenv("URURAU_V47_TEXTO_TENTAR_ATE_OK", "1")).strip().lower() not in {"0", "false", "nao", "não", "off"}
            tentativas = int(pauta.get("fonte_tentativas_v105") or 0)
            try:
                pauta["fonte_percentual_v105"] = max(0, min(99, int((float(util) / max(1, float(min_ok))) * 100)))
            except Exception:
                pauta["fonte_percentual_v105"] = 0
            if tentativas < max_t:
                self._v105_agendar_hidratacao(pauta, prioridade=False, motivo=f"retry_{status}", delay=delay)
            elif persistir and tentativas < hard_cap:
                longo = self._env_int("URURAU_V47_TEXTO_RETRY_LONGO_SEG", 1800)
                pauta["status_fonte_v105"] = f"{status}_retry_longo"
                try:
                    self.db.salvar_pauta(pauta)
                except Exception:
                    pass
                self._v105_agendar_hidratacao(pauta, prioridade=False, motivo=f"retry_longo_{status}", delay=longo)
            print(f"[v105][FONTE] {status.upper()} {util} chars ({pauta.get('fonte_percentual_v105', 0)}% da meta); {erro[:120]} | {(pauta.get('titulo_origem') or '')[:80]}")
            if atualizar_ui:
                self.after(0, lambda e=erro, u=util, st=status: self._v105_status_fonte_ui(f"{st}: {u} chars — {e[:80]}", COR_VERMELHO if st != "aguardando_429" else COR_AMARELO))
            return False
        finally:
            with self._hidratar_lock:
                self._hidratar_inflight.discard(key)

    def _v105_status_fonte_ui(self, texto: str, cor: str):
        try:
            self._lbl_leitura_status.config(text=texto, fg=cor)
            self._escrever(self._leitura_txt, texto)
        except Exception:
            pass

    def _v105_mostrar_fonte_cache(self, pauta: dict):
        ok, util, texto = self._v105_texto_fonte_util(pauta)
        if not ok:
            return
        self._lbl_leitura_status.config(text=f"Fonte OK em cache: {util} chars", fg=COR_VERDE)
        if not _v107_exibir_imagem_fonte(self, pauta, pendente="[imagem agendada depois do texto]"):
            self._v106_agendar_imagem(pauta, motivo="fonte_cache", delay=1.5)
        self._escrever(self._leitura_txt, _v107_formatar_texto_fonte(pauta, texto, max_chars=16000))

    def _v105_mostrar_resultado_fonte(self, pauta: dict, resultado, texto: str, util: int):
        try:
            status_txt = f"Fonte OK: {util} chars | {len(getattr(resultado, 'termos_destacados', []) or [])} termos"
            self._lbl_leitura_status.config(text=status_txt, fg=COR_VERDE)
            termos = getattr(resultado, "termos_destacados", []) or []
            self._lbl_leitura_termos.config(text=("Termos: " + " · ".join(termos[:12])) if termos else "")
            intel_header = ""
            intel = getattr(resultado, "intel_log", "") or ""
            if intel and intel != "sem sinais extras":
                intel_header = f"\n{'─'*60}\nINTEL EDITORIAL: {intel}\n{'─'*60}\n\n"
            texto_formatado = _v107_formatar_texto_fonte(pauta, texto, resultado=resultado, max_chars=16000)
            self._escrever(self._leitura_txt, intel_header + texto_formatado)
            if not _v107_exibir_imagem_fonte(self, pauta, pendente="[imagem agendada após texto]"):
                self._v106_agendar_imagem(pauta, motivo="resultado_fonte", delay=1.5)
        except Exception:
            pass

    def _auto_coleta_v94(self):
        """Dispara a coleta progressiva ao abrir o painel, uma única vez."""
        if self._auto_coleta_v94_iniciada:
            return
        self._auto_coleta_v94_iniciada = True
        try:
            self._set_status("v100: auto coleta iniciada ao abrir o painel...")
            print("[v100] Auto coleta iniciada ao abrir o painel.")
            self._acao_coletar(silencioso=True)
        except Exception as e:
            print(f"[v100] Auto coleta não iniciada: {e}")
            self._set_status(f"v100: auto coleta não iniciada: {e}")

    def _configurar_janela(self):
        self.title("Ururau — Robô Editorial v108")
        self.geometry("1440x900")
        self.minsize(1024, 700)
        self.configure(bg=COR_FUNDO)
        self.option_add("*Font", FONTE_NORMAL)

        try:
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except Exception:
                pass
            style.configure("TNotebook", background=COR_FUNDO, borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background="#10182a",
                foreground=COR_TEXTO,
                padding=(22, 11),
                font=("Segoe UI", 11, "bold"),
                borderwidth=1,
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#1d4ed8"), ("active", "#172554")],
                foreground=[("selected", "white"), ("active", "white")],
            )
            style.configure(
                "Ururau.Top.Horizontal.TProgressbar",
                troughcolor="#0b1220",
                background=COR_VERDE,
                darkcolor=COR_VERDE,
                lightcolor=COR_VERDE,
                bordercolor="#20304a",
                thickness=12,
            )
        except Exception:
            pass

        # ── Ícone da janela (logo oficial Ururau) ─────────────────────────────
        try:
            from pathlib import Path
            _ico = Path(__file__).parent.parent.parent / "ururau_atalho_icon.ico"
            if _ico.exists():
                self.iconbitmap(str(_ico))
        except Exception:
            pass  # fallback silencioso se .ico não for suportado no SO

        # ── Teclas de atalho globais ──────────────────────────────────────────
        # F5 = Atualizar lista (com feedback visual no status)
        def _f5(_=None):
            if hasattr(self, "_acao_atualizar_geral_v132"):
                self._acao_atualizar_geral_v132()
            else:
                self._set_status("Atualizando lista...")
                self.after(50, self._carregar_pautas)
        self.bind("<F5>", _f5)
        # Ctrl+W = Redigir matéria
        self.bind("<Control-w>", lambda _: self._acao_redigir())
        # v66: Ctrl+R agora abre o Copydesk (Revisao item-a-item),
        # ja que o painel de Revisao foi removido.
        self.bind("<Control-r>", lambda _: self._acao_copydesk())
        # Ctrl+P = Preview
        self.bind("<Control-p>", lambda _: self._acao_preview())
        # Ctrl+B = Buscar imagem
        self.bind("<Control-b>", lambda _: self._acao_buscar_imagem())
        # Ctrl+G = Coletar (Get) novas pautas
        self.bind("<Control-g>", lambda _: self._acao_coletar())
        # Ctrl+D = Descartar pauta (com diálogo de motivo)
        self.bind("<Control-d>", lambda _: self._acao_descartar())
        # Delete = Descarte rápido (confirmação simples, sem motivo)
        self.bind("<Delete>",    lambda _: self._descartar_via_tecla())
        # Ctrl+M = Manual (adicionar pauta — mantido no menu secundário)
        self.bind("<Control-m>", lambda _: self._acao_manual())
        # Ctrl+Shift+P = Publicar
        self.bind("<Control-P>", lambda _: self._acao_publicar())
        # Ctrl+K = Copydesk
        self.bind("<Control-k>", lambda _: self._acao_copydesk())
        # Ctrl+L = Console (Log)
        self.bind("<Control-l>", lambda _: self._toggle_console())
        # Escape = foca a fila de pautas (atalho rápido para voltar à lista)
        self.bind("<Escape>",    lambda _: self._focar_fila())

        # Monitor
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_robo = None
        # Console log widget (será criado em _construir_console)
        self._console_txt = None
        self._console_visible = False

    # ── Interface ─────────────────────────────────────────────────────────────

    def _construir_interface(self):
        self._construir_toolbar()
        self._construir_corpo()
        self._construir_console()
        self._construir_statusbar()
        # Redireciona stdout para o widget de console
        self._redirecionar_stdout()
        # v132: console interno fica disponível, mas oculto por padrão.
        # Abra pelo botão Console quando precisar ver o log.
        # self.after(100, self._toggle_console)

    def _construir_toolbar(self):
        tb = tk.Frame(self, bg="#11112a", height=58)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        # ── Logo: ícone + nome na cor oficial do logo ─────────────────────────
        logo_frame = tk.Frame(tb, bg="#11112a")
        logo_frame.pack(side="left", padx=(8, 4), pady=4)

        # Tenta carregar o ícone como imagem pequena (24×24) ao lado do nome
        try:
            from PIL import Image, ImageTk
            from pathlib import Path
            _ico_path = Path(__file__).parent.parent.parent / "ururau_atalho_icon.ico"
            if _ico_path.exists():
                _img = Image.open(str(_ico_path)).resize((28, 28), Image.LANCZOS)
                _photo = ImageTk.PhotoImage(_img)
                _ico_lbl = tk.Label(logo_frame, image=_photo, bg="#11112a")
                _ico_lbl.image = _photo   # mantém referência para evitar GC
                _ico_lbl.pack(side="left", padx=(0, 4))
        except Exception:
            pass  # sem Pillow ou ícone: apenas o texto

        tk.Label(logo_frame, text="URURAU", bg="#11112a", fg=COR_LOGO,
                 font=("Helvetica", 15, "bold")).pack(side="left")
        tk.Label(logo_frame, text="Editorial", bg="#11112a",
                 fg="#94a3b8", font=("Helvetica", 8, "bold")).pack(
                     side="left", padx=(4, 0), pady=(6, 0))
        def _btn_atualizar():
            if hasattr(self, "_acao_atualizar_geral_v132"):
                self._acao_atualizar_geral_v132()
            else:
                self._set_status("Atualizando lista...")
                self.after(50, self._carregar_pautas)

        grupo_principal_outer = tk.Frame(tb, bg="#11112a")
        grupo_principal_outer.pack(side="left", padx=(10, 8), pady=8)

        grupo_principal = tk.Frame(grupo_principal_outer, bg="#11112a")
        grupo_principal.pack(side="top", fill="x")

        for texto, cmd, cor in [
            ("Coletar", self._acao_coletar, "#f59e0b"),
            ("Redigir", self._acao_redigir, "#2563eb"),
            ("Copydesk", self._acao_copydesk, COR_ROXO),
            ("Preview", self._acao_preview, "#1d4ed8"),
            ("Publicar", self._acao_publicar, COR_VERDE),
            ("Descartar", self._acao_descartar, COR_VERMELHO),
            ("Exportar", self._acao_exportar, "#0f5cc0"),
        ]:
            wrap, _ = _criar_botao_premium(grupo_principal, texto, cmd, cor, largura=12, pady=8)
            wrap.pack(side="left", padx=5, pady=(0, 2))

        grupo_secundario = tk.Frame(tb, bg="#11112a")
        grupo_secundario.pack(side="left", padx=(4, 0), pady=8)
        for texto, cmd, cor in [
            ("Atualizar F5", _btn_atualizar, "#334155"),
            ("Historico", self._acao_historico, "#334155"),
            ("Stats", self._acao_estatisticas, "#1e293b"),
            ("Config", self._acao_configuracoes, "#1e293b"),
        ]:
            tk.Button(grupo_secundario, text=texto, command=cmd, bg=cor, fg="#dbeafe",
                      activebackground=_clarear(cor, 0.10), activeforeground="white",
                      relief="flat", padx=8, pady=5, cursor="hand2",
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=2)

        # Botão Monitor (toggle)
        self._btn_monitor = tk.Button(grupo_secundario, text="Monitor OFF",
                                       command=self._toggle_monitor,
                                       bg="#374151", fg="#d1d5db",
                                       activebackground="#475569", activeforeground="white",
                                       relief="flat", padx=8, pady=5, cursor="hand2",
                                       font=("Segoe UI", 9, "bold"))
        self._btn_monitor.pack(side="left", padx=2)
        # Botão Console (toggle log interno)
        self._btn_console = tk.Button(grupo_secundario, text="Console",
                                       command=self._toggle_console,
                                       bg="#1c1c35", fg="#cbd5e1",
                                       activebackground="#334155", activeforeground="white",
                                       relief="flat", padx=8, pady=5, cursor="hand2",
                                       font=("Segoe UI", 9, "bold"))
        self._btn_console.pack(side="left", padx=2)
        # Botão de atalhos de teclado
        tk.Button(grupo_secundario, text="⌨ Atalhos", command=self._mostrar_atalhos,
                  bg="#1c1c35", fg="#cbd5e1",
                  activebackground="#334155", activeforeground="white",
                  relief="flat", padx=8, pady=5, cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=2)

        self._lbl_stats = tk.Label(tb, text="", bg=COR_PAINEL,
                                   fg=COR_CINZA, font=FONTE_PEQUENA)
        self._lbl_stats.pack(side="right", padx=10)


    def _atualizar_stats_async(self):
        def _t():
            try:
                # fix/auditoria-fila-scrapling-v136: usa contadores oficiais
                # (excluem baixo_score de "Pautas" e separam descartadas/bloqueadas).
                # Fallback para estatisticas() se a versao do DB nao tiver os contadores.
                try:
                    c = self.db.contadores_dashboard()
                    txt = (f"Pautas: {c['pautas_ativas']}  |  "
                           f"Publicadas: {c['publicadas']}  |  "
                           f"Materias: {c['materias']}  |  "
                           f"Baixo score: {c['baixo_score']}")
                except Exception:
                    s = self.db.estatisticas()
                    txt = (f"Pautas: {s['total_pautas']}  |  "
                           f"Publicadas: {s['total_publicadas']}  |  "
                           f"Materias: {s['total_materias']}")
                def _update_stats_safe():
                    try:
                        if hasattr(self, "_lbl_stats") and self._lbl_stats.winfo_exists():
                            self._lbl_stats.config(text=txt)
                    except Exception:
                        pass
                self.after(0, _update_stats_safe)
            except Exception:
                pass
        threading.Thread(target=_t, daemon=True).start()

    def _construir_corpo(self):
        self._paned = ttk.PanedWindow(self, orient="horizontal")
        self._paned.pack(fill="both", expand=True, padx=6, pady=4)

        # fl é o contêiner pai do lado esquerdo — guarda referência para o PainelRevisao
        fl = tk.Frame(self._paned, bg=COR_PAINEL)
        self._frame_lista_pai = fl   # referência para PainelRevisao
        self._paned.add(fl, weight=1)

        # _frame_lista é o sub-frame que contém a fila de pautas
        # (será oculto quando o PainelRevisao estiver ativo)
        self._frame_lista = tk.Frame(fl, bg=COR_PAINEL)
        self._frame_lista.pack(fill="both", expand=True)
        self._construir_lista(self._frame_lista)

        # Painel de revisão (criado sob demanda)
        self._painel_revisao_widget = None
        self._faixa_revisao = None

        fd = tk.Frame(self._paned, bg=COR_PAINEL)
        self._frame_detalhe = fd   # referência para _mostrar_acoes_revisao
        self._paned.add(fd, weight=1)
        self._construir_detalhe(fd)
        self.after(150, self._ajustar_divisor)

    def _focar_fila(self):
        """Devolve o foco para a fila de pautas (tecla Esc)."""
        try:
            self._fila.focar()
        except Exception:
            pass

    def _mostrar_atalhos(self):
        """Exibe janela com todos os atalhos de teclado disponíveis."""
        win = tk.Toplevel(self)
        win.title("Atalhos de Teclado")
        win.geometry("420x480")
        win.configure(bg=COR_FUNDO)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="⌨  Atalhos de Teclado", bg=COR_FUNDO,
                 fg=COR_DESTAQUE, font=("Helvetica", 13, "bold")).pack(pady=(16, 8))

        atalhos = [
            ("FILA DE PAUTAS", None),
            ("↑ / ↓",         "Navegar entre pautas"),
            ("Enter / Espaço", "Abrir preview (ou gerar matéria)"),
            ("Page Up",        "Avança 5 pautas acima"),
            ("Page Down",      "Avança 5 pautas abaixo"),
            ("Home",           "Primeira pauta da lista"),
            ("End",            "Última pauta da lista"),
            ("",               ""),
            ("AÇÕES GLOBAIS",  None),
            ("F5",             "Atualizar lista de pautas"),
            ("Ctrl + G",       "Coletar novas pautas (Get)"),
            ("Ctrl + R",       "Redigir matéria da pauta selecionada"),
            ("Ctrl + K",       "Copydesk (revisão com IA)"),
            ("Ctrl + P",       "Preview — editar e escolher imagem"),
            ("Ctrl + Shift+P", "Publicar no CMS"),
            ("Ctrl + B",       "Buscar imagem automática"),
            ("Ctrl + M",       "Adicionar pauta manualmente"),
            ("Delete",          "Descartar pauta (confirmação rápida, sem motivo)"),
            ("Ctrl + D",       "Descartar pauta (com campo de motivo)"),
            ("Ctrl + L",       "Mostrar/ocultar Console de log"),
            ("Esc",            "Devolver foco à fila de pautas"),
        ]

        frame = tk.Frame(win, bg=COR_PAINEL, padx=20, pady=12)
        frame.pack(fill="both", expand=True, padx=16, pady=4)

        for tecla, descricao in atalhos:
            if descricao is None:
                # Cabeçalho de seção
                tk.Label(frame, text=tecla, bg=COR_PAINEL, fg=COR_CIANO,
                         font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(8, 2))
                tk.Frame(frame, bg="#3a3a5c", height=1).pack(fill="x", pady=2)
            elif tecla == "":
                tk.Label(frame, text="", bg=COR_PAINEL, height=1).pack()
            else:
                row = tk.Frame(frame, bg=COR_PAINEL)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=tecla, bg="#16213e", fg=COR_AMARELO,
                         font=("Courier New", 9, "bold"),
                         width=18, anchor="w", padx=4).pack(side="left")
                tk.Label(row, text=descricao, bg=COR_PAINEL, fg=COR_TEXTO,
                         font=("Helvetica", 9), anchor="w").pack(side="left", padx=8)

        tk.Button(win, text="Fechar", command=win.destroy,
                  bg=COR_DESTAQUE, fg="white", relief="flat",
                  padx=16, pady=4, cursor="hand2",
                  font=("Helvetica", 10, "bold")).pack(pady=12)

    def _ajustar_divisor(self):
        try:
            w = self._paned.winfo_width()
            if w > 100:
                self._paned.sashpos(0, w // 2)
        except Exception:
            pass

    def _construir_lista(self, frame):
        # ── Título ────────────────────────────────────────────────────────────
        tk.Label(frame, text="Fila de Pautas", bg=COR_PAINEL,
                 fg=COR_TEXTO, font=FONTE_TITULO, anchor="w").pack(
                     fill="x", padx=8, pady=4)

        # ── Linha de filtros ──────────────────────────────────────────────────
        ff = tk.Frame(frame, bg=COR_PAINEL)
        ff.pack(fill="x", padx=8, pady=2)
        tk.Label(ff, text="Status:", bg=COR_PAINEL, fg=COR_CINZA,
                 font=FONTE_PEQUENA).pack(side="left")
        self._filtro_var = tk.StringVar(value="todos")
        # v132: Status úteis/realmente usados no fluxo atual.
        _vals_filtro = [
            "todos", "captada", "baixo_score", "em_redacao", "revisada",
            "pronta", "publicada", "rejeitada", "bloqueada", "── excluídas ──"
        ]
        cb = ttk.Combobox(ff, textvariable=self._filtro_var,
                          values=_vals_filtro,
                          state="readonly", width=14)
        cb.pack(side="left", padx=2)
        cb.bind("<<ComboboxSelected>>", lambda _: self._aplicar_filtro())
        tk.Label(ff, text="Busca:", bg=COR_PAINEL, fg=COR_CINZA,
                 font=FONTE_PEQUENA).pack(side="left", padx=(6, 2))
        self._busca_var = tk.StringVar()
        tk.Entry(ff, textvariable=self._busca_var, bg=COR_FUNDO, fg=COR_TEXTO,
                 insertbackground=COR_TEXTO, font=FONTE_PEQUENA,
                 width=14).pack(side="left")
        self._busca_var.trace_add("write", lambda *_: self._agendar_aplicar_filtro_v129_6())
        self._lbl_contagem = tk.Label(ff, text="", bg=COR_PAINEL,
                                      fg=COR_CINZA, font=FONTE_PEQUENA)
        self._lbl_contagem.pack(side="right")

        # ── Barra de ações em lote ────────────────────────────────────────────
        fb = tk.Frame(frame, bg="#0d0d20")
        fb.pack(fill="x", padx=8, pady=(0, 2))

        tk.Button(fb, text="☑ Selec. Todos", command=self._selecionar_todos,
                  bg="#1e293b", fg="#94a3b8", relief="flat", padx=6, pady=2,
                  cursor="hand2", font=("Helvetica", 8)).pack(side="left", padx=1)
        tk.Button(fb, text="☐ Limpar", command=self._limpar_selecao,
                  bg="#1e293b", fg="#94a3b8", relief="flat", padx=6, pady=2,
                  cursor="hand2", font=("Helvetica", 8)).pack(side="left", padx=1)

        self._btn_excluir_sel = tk.Button(
            fb, text="🗑 Excluir Selecionadas (0)",
            command=self._acao_excluir_selecionadas,
            bg="#4b0505", fg="#fca5a5", relief="flat", padx=6, pady=2,
            cursor="hand2", font=("Helvetica", 8, "bold"), state="disabled")
        self._btn_excluir_sel.pack(side="left", padx=(8, 1))

        tk.Button(fb, text="🗑 Excluir TUDO visível",
                  command=self._acao_excluir_tudo,
                  bg="#3b0000", fg="#ef4444", relief="flat", padx=6, pady=2,
                  cursor="hand2", font=("Helvetica", 8)).pack(side="left", padx=1)

        tk.Button(fb, text="🧹 Limpar Lista",
                  command=self._acao_limpar_lista,
                  bg="#1a2a1a", fg="#86efac", relief="flat", padx=6, pady=2,
                  cursor="hand2", font=("Helvetica", 8)).pack(side="left", padx=(12, 1))

        tk.Label(frame,
                 text="📷=imagem ok  ⋯=pendente  ⚠=risco alto  🔥=urgente  "
                      "✓ Ver=abrir preview quando já houver matéria  ✓ Aprovar=liberar baixo score  ✕ Reprovar=bloquear baixo score  PRIORIDADE=termo de interesse  ☑=selecionar p/ excluir",
                 bg=COR_PAINEL, fg=COR_CINZA,
                 font=("Helvetica", 7)).pack(anchor="w", padx=8)

        self._fila = FilaPautas(frame, on_select=self._ao_selecionar)
        self._fila.set_callbacks(
            # v129.11: clique no corpo da pauta só seleciona e carrega Detalhe/Fonte.
            on_select=self._ao_selecionar,
            on_gerar=self._acao_gerar_item,
            on_descartar=self._descartar_rapido,
            on_selecao_mudou=self._ao_mudar_selecao,
            on_reativar=self._acao_reativar_pauta,
            on_aprovar_baixo_score=self._acao_aprovar_baixo_score_v129,
            on_reprovar_baixo_score=self._acao_reprovar_baixo_score_v129_1,
            # Preview só é disparado por botão próprio quando houver matéria gerada.
            on_abrir=self._acao_preview_direto,
        )
        self._fila.pack(fill="both", expand=True, padx=4, pady=4)

    def _v126_atualizar_diagnostico_coleta(self, texto: str):
        """v127: guarda diagnóstico só em memória e atualiza a aba Config > Diagnóstico, se aberta."""
        try:
            texto = texto or "Sem diagnóstico disponível."
            self._diagnostico_coleta_sessao_v127 = texto
            hist = getattr(self, "_diagnostico_coleta_historico_v127", None)
            if hist is None:
                hist = []
                self._diagnostico_coleta_historico_v127 = hist
            hist.append(texto)
            if len(hist) > 20:
                del hist[:-20]
            cfg = getattr(self, "_config_widget", None)
            if cfg and hasattr(cfg, "_atualizar_diagnostico_v127"):
                cfg._atualizar_diagnostico_v127(texto, hist)
        except Exception as e:
            print(f"[v127][DIAGNOSTICO] falha ao atualizar memória/UI: {e}")

    def _construir_detalhe(self, frame):
        tk.Label(frame, text="Detalhe da Pauta", bg=COR_PAINEL,
                 fg=COR_TEXTO, font=FONTE_TITULO, anchor="w").pack(
                     fill="x", padx=8, pady=4)
        nb = ttk.Notebook(frame)
        nb.pack(fill="both", expand=True, padx=8, pady=4)
        self._notebook = nb
        nb.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)
        self._aba_info      = self._nova_aba(nb, "Info")
        self._aba_checagem  = self._nova_aba(nb, "Checagem")
        self._aba_risco     = self._nova_aba(nb, "Risco")
        self._aba_materia   = self._nova_aba(nb, "Materia")
        self._aba_auditoria = self._nova_aba(nb, "Auditoria")
        # ── Aba Leitura da Fonte (v43) ───────────────────────────────────────
        self._aba_leitura_frame = tk.Frame(nb, bg=COR_FUNDO)
        nb.add(self._aba_leitura_frame, text="📄 Fonte")
        self._idx_aba_leitura = nb.index("end") - 1
        self._construir_aba_leitura(self._aba_leitura_frame)
        # ── Aba Monitor integrada ────────────────────────────────────────────
        f_monitor = tk.Frame(nb, bg=COR_FUNDO)
        nb.add(f_monitor, text="🤖 Monitor")
        self._aba_monitor_widget = AbaMonitor(f_monitor, self.db, self.client,
                                              self.modelo,
                                              cb_robo_atualizado=self._cb_monitor_atualizado)
        self._aba_monitor_widget.pack(fill="both", expand=True)
        # ── Aba Preview inline ───────────────────────────────────────────────
        self._aba_preview_frame = tk.Frame(nb, bg=COR_FUNDO)
        nb.add(self._aba_preview_frame, text="✏ Preview")
        self._idx_aba_preview = nb.index("end") - 1
        # ── Aba Config inline ────────────────────────────────────────────────
        self._aba_config_frame = tk.Frame(nb, bg=COR_FUNDO)
        nb.add(self._aba_config_frame, text="⚙ Config")
        self._idx_aba_config = nb.index("end") - 1

    def _nova_aba(self, nb, titulo):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text=titulo)
        st = scrolledtext.ScrolledText(f, bg="#16213e", fg=COR_TEXTO,
                                        font=FONTE_MONO, borderwidth=0,
                                        state="disabled", wrap="word")
        st.pack(fill="both", expand=True)
        return st

    def _ao_trocar_aba(self, _=None):
        if not self._pauta_sel or self._carregando_aba:
            return
        idx   = self._notebook.index("current")
        pauta = self._pauta_sel
        # Aba Leitura da Fonte (idx=5): carrega conteúdo da fonte
        if idx == self._idx_aba_leitura:
            self._carregar_aba_leitura(pauta)
            return
        # Abas Monitor(6), Preview(7) e Config(8) não usam _escrever
        if idx > self._idx_aba_leitura:
            return
        self._carregando_aba = True

        def _t():
            try:
                fns = [self._calcular_info, self._calcular_checagem,
                       self._calcular_risco, self._calcular_materia,
                       self._calcular_auditoria]
                abas = [self._aba_info, self._aba_checagem,
                        self._aba_risco, self._aba_materia, self._aba_auditoria]
                if 0 <= idx < len(fns):
                    txt = fns[idx](pauta)
                    self.after(0, lambda: self._escrever(abas[idx], txt))
            finally:
                self.after(0, lambda: setattr(self, "_carregando_aba", False))
        threading.Thread(target=_t, daemon=True).start()

    def _construir_console(self):
        """Painel de console interno — exibe print() do sistema em tempo real."""
        self._console_frame = tk.Frame(self, bg="#050510", height=320)
        # Não empacota por padrão — toggle visibilidade
        hdr = tk.Frame(self._console_frame, bg="#0a0a1a", height=24)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="▶ Console interno", bg="#0a0a1a", fg="#64748b",
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=8)
        tk.Button(hdr, text="Limpar", command=self._limpar_console,
                  bg="#0a0a1a", fg="#475569", relief="flat",
                  font=("Segoe UI", 7), padx=4, pady=0,
                  cursor="hand2").pack(side="right", padx=4)
        self._console_txt = scrolledtext.ScrolledText(
            self._console_frame, bg="#050510", fg="#94a3b8",
            font=("Courier New", 8), state="disabled",
            wrap="word", height=14)
        self._console_txt.pack(fill="both", expand=True)
        self._console_txt.tag_configure("ok",   foreground="#86efac")
        self._console_txt.tag_configure("err",  foreground="#fca5a5")
        self._console_txt.tag_configure("warn", foreground="#fde68a")
        self._console_txt.tag_configure("info", foreground="#94a3b8")

    def _toggle_console(self):
        """Mostra/esconde o painel de console."""
        self._console_visible = not self._console_visible
        if self._console_visible:
            # Empacota antes da statusbar
            self._console_frame.pack(fill="x", side="bottom", before=self._statusbar_frame)
            self._btn_console.config(bg="#1c4532", fg="#86efac")
        else:
            self._console_frame.pack_forget()
            self._btn_console.config(bg="#1c1c35", fg="#64748b")

    def _limpar_console(self):
        if self._console_txt:
            self._console_txt.config(state="normal")
            self._console_txt.delete("1.0", "end")
            self._console_txt.config(state="disabled")

    def _append_console(self, texto: str):
        """Adiciona linha ao console interno com coloração automática."""
        if not self._console_txt:
            return
        try:
            tag = "info"
            tl = texto.lower()
            if "[ok]" in tl or "ok]" in tl or "sucesso" in tl or "✓" in tl:
                tag = "ok"
            elif "erro" in tl or "error" in tl or "[xx]" in tl or "falha" in tl or "✗" in tl:
                tag = "err"
            elif "aviso" in tl or "warn" in tl or "⚠" in tl or "bloq" in tl:
                tag = "warn"
            self._console_txt.config(state="normal")
            self._console_txt.insert("end", texto.rstrip() + "\n", tag)
            self._console_txt.see("end")
            self._console_txt.config(state="disabled")
        except Exception:
            pass

    def _redirecionar_stdout(self):
        """Redireciona sys.stdout para o widget de console + terminal original."""
        import sys
        painel = self
        orig_stdout = sys.stdout
        orig_stderr = sys.stderr

        class _Tee:
            def __init__(self, orig):
                self._orig = orig
            def write(self, msg):
                if msg and msg.strip():
                    try:
                        painel.after(0, lambda m=msg: painel._append_console(m))
                    except Exception:
                        pass
                try:
                    self._orig.write(msg)
                except Exception:
                    pass
            def flush(self):
                try:
                    self._orig.flush()
                except Exception:
                    pass

        sys.stdout = _Tee(orig_stdout)
        sys.stderr = _Tee(orig_stderr)

    def _construir_statusbar(self):
        sb = tk.Frame(self, bg="#0a0a1a", height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._statusbar_frame = sb
        # Barra de status com indicador colorido
        self._status_dot = tk.Label(sb, text="●", bg="#0a0a1a", fg=COR_VERDE,
                                    font=("Helvetica", 8))
        self._status_dot.pack(side="left", padx=(8, 2))
        self._status_lbl = tk.Label(sb, text="Pronto. (F5 para atualizar)",
                                    bg="#0a0a1a", fg="#94a3b8",
                                    font=("Segoe UI", 9), anchor="w")
        self._status_lbl.pack(side="left")

    def _set_status(self, msg: str):
        self.after(0, lambda: self._status_lbl.config(text=msg))

    # ── Carregamento ──────────────────────────────────────────────────────────

    def _carregar_pautas(self, forcar: bool = False):
        # v129.8: durante coleta/hidratação/imagem, dezenas de chamadas para
        # recarregar a fila chegavam quase juntas. Isso fazia a tela pular.
        # Coalescemos essas chamadas; F5 ou refresh final podem forçar.
        if self._carregando_lista:
            return
        try:
            min_ms = int(os.getenv("URURAU_V1298_DB_REFRESH_MS", "6000") or "2500")
            min_ms = max(500, min(8000, min_ms))
        except Exception:
            min_ms = 6000
        agora = time.monotonic()
        if (not forcar) and getattr(self, "_coleta_em_andamento", False):
            decorrido = (agora - float(getattr(self, "_v1298_last_refresh", 0.0) or 0.0)) * 1000.0
            if decorrido < min_ms:
                if getattr(self, "_v1298_refresh_after_id", None) is None:
                    atraso = int(max(250, min_ms - decorrido))
                    self._v1298_refresh_after_id = self.after(atraso, lambda: self._carregar_pautas(forcar=True))
                return
        self._v1298_refresh_after_id = None
        self._v1298_last_refresh = agora
        self._carregando_lista = True
        self._set_status("Carregando pautas...")
        threading.Thread(target=self._carregar_thread, daemon=True).start()

    def _carregar_thread(self):
        try:
            # fix/auditoria-fila-scrapling-v136: usa query oficial em vez de SQL
            # solto. Mantem ordenacao por captacao DESC, exclui publicadas/descartadas/
            # bloqueadas, e ja desempacota dados_json para o cache.
            try:
                cache = self.db.query_fila_ativa(incluir_baixo_score=True, limite=500)
            except Exception as _e_qfa:
                print(f"[FILA][CANONICO][AVISO] query_fila_ativa indisponivel ({_e_qfa}); usando fallback legado.")
                conn = self.db._conectar()
                try:
                    rows = conn.execute(
                        "SELECT uid, titulo_origem, status, urgente, "
                        "score_editorial, dados_json, fonte_nome, "
                        "captada_em, atualizada_em "
                        "FROM pautas ORDER BY atualizada_em DESC LIMIT 500"
                    ).fetchall()
                    cache = []
                    for row in rows:
                        d = dict(row)
                        try:
                            extra = json.loads(d.get("dados_json") or "{}")
                            d.update(extra)
                        except Exception:
                            pass
                        cache.append(d)
                finally:
                    conn.close()
            # fix/auditoria-fila-scrapling-v136: a conexao SQLite vivia aqui apenas
            # para a query bruta. Agora a query oficial roda em query_fila_ativa.
            # Mantemos try/finally para nao quebrar a indentacao do bloco janela.
            try:
                # v99: a fila mostra somente matérias publicadas dentro da janela
                # editorial configurada, em horário de Brasília, mais recentes primeiro.
                # Não usa captada_em para aprovar pauta antiga: a regra é publicação na fonte.
                janela_h = janela_publicacao_horas(4)
                filtrar_4h = os.getenv("URURAU_V99_FILA_APENAS_ULTIMAS_HORAS", "1").strip() != "0"

                def _dt_pub_pauta(p: dict):
                    return (
                        parse_data_br_ou_iso(p.get("_data_pub_ordem") or "")
                        or parse_data_br_ou_iso(p.get("data_pub_fonte_br") or "")
                        or parse_data_br_ou_iso(p.get("data_pub_fonte") or "")
                    )

                if filtrar_4h:
                    cache_filtrada = []
                    for p in cache:
                        dt_pub = _dt_pub_pauta(p)
                        ok, motivo, idade_h = dentro_da_janela(dt_pub)
                        forcar_visivel_v12914 = bool(
                            p.get("_v12914_forcar_visivel_fila")
                            or (p.get("_coletor_especial") in {"mancheterj_v12914", "mancheterj_v12913"} and p.get("_excecao_fora_janela_v123"))
                        )
                        if ok or (forcar_visivel_v12914 and os.getenv("URURAU_V12914_EXIBIR_EXCECOES_FILA", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}):
                            p["_idade_pub_horas_v99"] = round(float(idade_h), 2) if idade_h is not None else 0
                            if not ok:
                                p["_v12914_visivel_por_excecao"] = True
                                p["_oculta_fila_v99"] = ""
                            cache_filtrada.append(p)
                        else:
                            p["_oculta_fila_v99"] = motivo
                    cache = cache_filtrada

                def _chave_data(p: dict) -> str:
                    # v47.4: publicação da fonte; se ausente, usa captura/atualização.
                    dt_pub = _dt_pub_pauta(p)
                    if dt_pub:
                        return dt_pub.strftime("%Y-%m-%d %H:%M:%S")
                    dt_cap = parse_data_br_ou_iso(p.get("captada_em") or "") or parse_data_br_ou_iso(p.get("atualizada_em") or "")
                    if dt_cap:
                        return dt_cap.strftime("%Y-%m-%d %H:%M:%S")
                    return ""

                cache.sort(key=_chave_data, reverse=True)
            finally:
                pass  # conn ja nao e necessario; query_fila_ativa fechou.

            def _ok():
                self._pautas_cache    = cache
                self._carregando_lista = False
                self._aplicar_filtro()
                # fix/auditoria-fila-scrapling-v136 + spec_claudio_hidratacao_continua:
                # enfileirar TODAS as pautas sem texto valido. Antes, o default era
                # cache[:50] e o usuario relatou que so as primeiras 50 hidratavam
                # sozinhas; ele precisava clicar nas demais. Agora hidrata em rajadas
                # mas continua respeitando o cooldown por dominio do _v105_hidratar_pauta.
                limite = self._env_int("URURAU_V105_MAX_ENFILEIRAR_POR_REFRESH", 999)
                count_pendentes = 0
                for _p in cache:
                    try:
                        _ok_txt, _util_txt, _ = self._v105_texto_fonte_util(_p)
                    except Exception:
                        _ok_txt = False
                    if not _ok_txt:
                        if count_pendentes >= limite:
                            break
                        count_pendentes += 1
                        self._v105_agendar_hidratacao(_p, prioridade=False, motivo="refresh_fila")
                    else:
                        try:
                            if not self._v106_imagem_ok(_p):
                                self._v106_agendar_imagem(_p, motivo="refresh_fila_texto_ok", delay=3.0)
                        except Exception:
                            pass
                if count_pendentes:
                    print(f"[FILA][CANONICO] enfileiradas {count_pendentes} pauta(s) sem texto valido para hidratacao automatica.")
                self._atualizar_stats_async()
                self._set_status(f"{len(cache)} pautas na fila — ordem: mais recentes primeiro; texto completo em hidratação persistente; imagem depois do texto. (F5/Atualizar recarrega e aplica fontes)")
            self.after(0, _ok)
        except Exception as e:
            self._carregando_lista = False
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f"Erro ao carregar: {msg}"))


    def _v123_inserir_separadores_coleta(self, itens: list[dict]) -> list[dict]:
        """Insere barras visuais Coleta N - horário sem virar pauta real."""
        if os.getenv("URURAU_V123_SEPARAR_COLETAS_NA_FILA", "1").strip().lower() in ("0", "false", "nao", "não"):
            return itens
        if not itens:
            return itens

        labels: list[str] = []
        counts: dict[str, int] = {}

        def _label(p: dict) -> str:
            label = str(p.get("coleta_lote_label_v123") or "").strip()
            if label:
                return label
            # Pautas antigas, antes da v123, ficam agrupadas sem afetar a lógica nova.
            return "Coletas anteriores"

        for p in itens:
            label = _label(p)
            counts[label] = counts.get(label, 0) + 1
            if label not in labels:
                labels.append(label)

        saida: list[dict] = []
        ultimo = None
        for p in itens:
            label = _label(p)
            if label != ultimo:
                qtd = counts.get(label, 0)
                saida.append({
                    "_separador_coleta_v123": True,
                    "uid": "sep:v123:" + label,
                    "_uid": "sep:v123:" + label,
                    "titulo_origem": f"{label} — {qtd} pauta(s)",
                    "_subtitulo_separador_v123": "Separador visual. A numeração não interfere nas pautas nem na publicação.",
                    "status": "_separador",
                })
                ultimo = label
            saida.append(p)
        return saida



    def _texto_busca_pauta_v127(self, p: dict) -> str:
        """Texto pesquisável da fila: título + rodapé exibido + fonte + data + origem."""
        campos = [
            "titulo_origem", "titulo",
            "fonte_nome", "fonte", "nome_fonte",
            "origem", "origem_feed", "_v94_contexto_coleta",
            "link_origem", "url", "link",
            "data_pub_fonte", "data_pub_fonte_br", "publicado_em", "data_publicacao",
            "canal_forcado", "canal", "canal_sugerido",
            "termo_busca_v127", "termo_busca_v108",
        ]
        partes = []
        for c in campos:
            v = p.get(c)
            if v is not None:
                partes.append(str(v))
        # Replica o rodapé visual: "Fonte · Publicado: data".
        fonte = p.get("fonte_nome") or p.get("fonte") or p.get("nome_fonte") or ""
        data = p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or p.get("publicado_em") or ""
        if fonte or data:
            partes.append(f"{fonte} · Publicado: {data}")
        texto = " ".join(partes).lower()
        try:
            import unicodedata
            texto_sem_acento = unicodedata.normalize("NFKD", texto)
            texto_sem_acento = "".join(ch for ch in texto_sem_acento if not unicodedata.combining(ch))
            return texto + " " + texto_sem_acento
        except Exception:
            return texto



    def _agendar_aplicar_filtro_v129_6(self, atraso_ms: int = 180):
        """Debounce da busca/filtro para evitar redesenho por tecla ou por rajadas."""
        try:
            job = getattr(self, "_v129_6_filtro_after_id", None)
            if job:
                self.after_cancel(job)
        except Exception:
            pass
        try:
            self._v129_6_filtro_after_id = self.after(atraso_ms, self._aplicar_filtro)
        except Exception:
            self._aplicar_filtro()

    def _aplicar_filtro(self):
        filtro = self._filtro_var.get()
        busca  = self._busca_var.get().lower().strip()
        busca_norm = busca
        try:
            import unicodedata
            busca_norm = unicodedata.normalize("NFKD", busca_norm)
            busca_norm = "".join(ch for ch in busca_norm if not unicodedata.combining(ch))
        except Exception:
            pass
        def _match_busca_v127(p: dict) -> bool:
            if not busca:
                return True
            texto = self._texto_busca_pauta_v127(p)
            return busca in texto or busca_norm in texto

        # Modo "excluídas": mostra apenas status=excluida
        if filtro == "── excluídas ──":
            filtradas = [
                p for p in self._pautas_cache
                if p.get("status") == 'excluida'
                and _match_busca_v127(p)
            ]
        elif filtro == "todos":
            # "todos" exclui excluídas e, na v84, também oculta bloqueadas por falta de texto.
            # Elas continuam acessíveis pelo filtro específico "bloqueada".
            import os as _os
            ocultar_bloqueadas = _os.getenv("URURAU_V84_OCULTAR_BLOQUEADAS_PADRAO", "1").lower() in ("1", "true", "sim", "yes", "s")
            filtradas = [
                p for p in self._pautas_cache
                if p.get("status") not in ('excluida', 'reprovada')
                and (not ocultar_bloqueadas or p.get("status") != 'bloqueada')
                and _match_busca_v127(p)
            ]
        else:
            filtradas = [
                p for p in self._pautas_cache
                if p.get("status") == filtro
                and _match_busca_v127(p)
            ]
        # v129: itens de baixo score ficam auditáveis, mas separados no fim da fila.
        if filtro == "todos":
            normais_v129 = [p for p in filtradas if p.get("status") != "baixo_score"]
            baixo_v129 = [p for p in filtradas if p.get("status") == "baixo_score"]
            filtradas_v123 = self._v123_inserir_separadores_coleta(normais_v129)
            if baixo_v129:
                filtradas_v123.append({
                    "_separador_coleta_v123": True,
                    "uid": "sep:v129:baixo_score",
                    "_uid": "sep:v129:baixo_score",
                    "titulo_origem": f"Baixo score para avaliação — {len(baixo_v129)} pauta(s)",
                    "_subtitulo_separador_v123": "Matérias coletadas, mas barradas pelo score. Use ✓ Aprovar para devolver à fila normal ou ✕ Reprovar para bloquear.",
                    "status": "_separador",
                })
                filtradas_v123.extend(baixo_v129)
        else:
            filtradas_v123 = self._v123_inserir_separadores_coleta(filtradas)
        # v129.6: não limpar _uids_cache aqui. Limpar esse cache forçava
        # reconstrução total da lista a cada pauta coletada, deixando a fila
        # lenta, pulando e aparentemente travada.
        try:
            self._fila.popular(filtradas_v123)
        except Exception as e:
            # v129.5: falha visual não pode ocultar a existência das pautas.
            self._set_status(f"Erro visual ao renderizar fila: {e}")
        total_visivel = len([p for p in filtradas if not p.get("_separador_coleta_v123")])
        self._lbl_contagem.config(text=f"{total_visivel}")
        try:
            total_cache = len([p for p in self._pautas_cache if p.get("status") not in ("excluida", "reprovada")])
            if hasattr(self, "_lbl_stats") and self._lbl_stats.winfo_exists():
                self._lbl_stats.config(text=f"Pautas: {total_cache}  |  Publicadas: 0  |  Materias: 0")
        except Exception:
            pass

    def _ao_selecionar(self, pauta: dict):
        """Seleciona pauta e restaura a integração antiga com Detalhe/Fonte.

        v129.10: a fila em Canvas continua leve, mas o clique no corpo do card
        volta a executar o fluxo original da v127: selecionar pauta, ativar a
        aba Fonte e carregar texto/imagem da fonte. O trabalho pesado continua
        no hidratador; a tela recebe placeholder imediato para não parecer vazia.
        """
        self._pauta_sel = pauta
        self._set_status(f"Selecionado: {(pauta.get('titulo_origem') or '')[:60]} — Fonte priorizada")
        try:
            self._notebook.select(self._idx_aba_leitura)
        except Exception:
            pass
        try:
            self._v105_agendar_hidratacao(pauta, prioridade=True, motivo="clicada")
        except Exception:
            pass
        try:
            self._carregar_aba_leitura(pauta, forcar=False)
        except Exception as e:
            try:
                self._set_status(f"Falha ao carregar detalhe da pauta: {e}")
            except Exception:
                pass

    # ── Conteúdo das abas ─────────────────────────────────────────────────────

    def _escrever(self, txt, conteudo):
        txt.config(state="normal")
        txt.delete("1.0", "end")
        txt.insert("end", conteudo)
        txt.config(state="disabled")

    def _calcular_info(self, p: dict) -> str:
        sc = p.get("score_risco", 0) or 0
        alerta = (" [BLOQUEADO]" if sc >= LIMIAR_RISCO_MAXIMO
                  else (" [REVISAR]" if sc >= 30 else ""))
        return (
            f"TITULO          : {p.get('titulo_origem', '')}\n"
            f"STATUS          : {p.get('status', '')}\n"
            f"CANAL           : {p.get('canal_forcado') or p.get('canal', '')}\n"
            f"FONTE           : {p.get('fonte_nome', '')}\n"
            f"PUBLICADO FONTE : {p.get('data_pub_fonte') or '(nao disponivel)'} (horário de Brasília)\n"
            f"LINK            : {p.get('link_origem', '')}\n"
            f"UID             : {p.get('uid') or p.get('_uid', '')}\n"
            f"\nSCORE EDITORIAL : {p.get('score_editorial', 0)}\n"
            f"SCORE RISCO     : {sc}/100{alerta}\n"
            f"URGENTE         : {'Sim' if p.get('urgente') else 'Nao'}\n"
            f"\nIMAGEM STATUS   : {p.get('imagem_status', 'pendente')}\n"
            f"IMAGEM ESTRAT.  : {p.get('imagem_estrategia', '')}\n"
            f"IMAGEM CAMINHO  : {p.get('imagem_caminho', '')}\n"
            f"\nCAPTADA EM      : {p.get('captada_em', '')}\n"
            f"ATUALIZADA EM   : {p.get('atualizada_em', '')}\n"
            f"\nRESUMO:\n{p.get('resumo_origem', '')}\n"
        )

    def _calcular_checagem(self, p: dict) -> str:
        link  = p.get("link_origem", "")
        uid   = p.get("uid") or p.get("_uid", "")
        titulo = p.get("titulo_origem", "")
        linhas = ["=" * 60, "  CHECAGEM ANTI-REPETICAO E INTEGRIDADE", "=" * 60, ""]
        try:
            status_banco = self.db.classificar_pauta(link, uid)
            linhas.append(f"Status no banco  : {status_banco}")
            ja_pub     = self.db.pauta_ja_publicada(link, uid)
            descartada = self.db.pauta_foi_descartada(link, uid)
            similar    = self.db.titulo_similar_ja_publicado(titulo) if titulo else None
            linhas.append(f"{'[OK]' if not ja_pub else '[XX]'} Ja publicada    : {'SIM' if ja_pub else 'Nao'}")
            linhas.append(f"{'[OK]' if not descartada else '[XX]'} Descartada      : {'SIM' if descartada else 'Nao'}")
            linhas.append(f"[XX] Titulo similar:\n   -> '{similar[:70]}'" if similar
                          else "[OK] Sem titulo similar recente")
            img_st = p.get("imagem_status", "pendente")
            linhas.append(f"\n{'[OK]' if img_st == 'aprovada' else '[..]'} Imagem : {img_st}")
            if p.get("imagem_caminho"):
                linhas.append(f"   Arquivo : {p.get('imagem_caminho')}")
            md = _parse_materia(p)
            tem = bool(md and md.get("conteudo"))
            linhas.append(f"\n{'[OK]' if tem else '[..]'} Materia gerada : {'Sim' if tem else 'Nao'}")
            if tem:
                probs = detectar_problemas(md)
                if probs:
                    linhas += [f"\n[AVIS] Checklist ({len(probs)} problemas):"] + [f"   - {x}" for x in probs]
                else:
                    linhas.append("[OK] Checklist: OK")
            linhas.append("\n" + "-" * 60)
            bloqs = []
            if ja_pub: bloqs.append("Ja publicada no CMS")
            if descartada: bloqs.append("Descartada anteriormente")
            if similar: bloqs.append("Titulo similar publicado (72h)")
            sc = p.get("score_risco", 0) or 0
            if sc >= LIMIAR_RISCO_MAXIMO:
                bloqs.append(f"Score risco {sc}/100 acima de {LIMIAR_RISCO_MAXIMO}")
            if not p.get("_intel_protocolo_ok", True):
                bloqs.append("Protocolo de verdade: revisar cargo/fato antes de publicar")
            if bloqs:
                linhas += ["[BLOQ] PUBLICACAO REQUER CONFIRMACAO:"] + [f"   * {b}" for b in bloqs]
            else:
                linhas.append("[OK] PAUTA APTA PARA PUBLICACAO")

            # ── Intel editorial (v43) ─────────────────────────────────────────
            intel_log = p.get("_intel_log", "")
            score_intel = p.get("_score_intel_adicional", 0) or 0
            watchlists = p.get("_intel_watchlists") or []
            if score_intel > 0 or intel_log:
                linhas.append("\n" + "─" * 60)
                linhas.append("  INTEL EDITORIAL (v43)")
                linhas.append("─" * 60)
                linhas.append(f"Score adicional  : +{score_intel}")
                if intel_log:
                    linhas.append(f"Sinais detectados: {intel_log}")
                if watchlists:
                    linhas.append(f"Watchlists       : {', '.join(watchlists[:6])}")
                if p.get("_intel_triangulacao"):
                    linhas.append("[★] TRIANGULACAO REGIONAL ATIVA")
                if p.get("_intel_urgencia"):
                    linhas.append("[⚡] URGENCIA DETECTADA")
                if not p.get("_intel_protocolo_ok", True):
                    linhas.append("[⚠] PROTOCOLO DE VERDADE: REVISAR ANTES DE PUBLICAR")

            # ── Auditoria IA v44 ──────────────────────────────────────────────
            md = _parse_materia(p)
            aud_aprovada  = (md or {}).get("auditoria_aprovada", None)
            aud_bloqueada = (md or {}).get("auditoria_bloqueada", None)
            aud_erros     = (md or {}).get("auditoria_erros", [])
            aud_status    = (md or {}).get("status_pipeline", "")
            viol_fat      = (md or {}).get("violacoes_factuais", [])
            nome_fonte    = (md or {}).get("nome_da_fonte", "")
            credito_foto  = (md or {}).get("creditos_da_foto", "")

            if aud_aprovada is not None:
                linhas.append("\n" + "─" * 60)
                linhas.append("  AUDITORIA IA v44")
                linhas.append("─" * 60)
                aud_icone = "[OK]" if aud_aprovada else "[XX]"
                linhas.append(f"{aud_icone} Aprovada       : {'SIM' if aud_aprovada else 'NAO'}")
                linhas.append(f"     Status      : {aud_status.upper() if aud_status else '-'}")
                if nome_fonte:
                    linhas.append(f"     Nome fonte  : {nome_fonte}")
                if credito_foto:
                    linhas.append(f"     Cred. foto  : {credito_foto}")
                if viol_fat:
                    linhas.append("[BLOQ] VIOLACOES FACTUAIS:")
                    for v in viol_fat[:4]:
                        linhas.append(f"   * {v}")
                if aud_erros:
                    linhas.append("[AVIS] Erros da auditoria:")
                    for e_txt in aud_erros[:4]:
                        linhas.append(f"   - {e_txt}")
                if aud_bloqueada:
                    linhas.append("[BLOQ] PUBLICACAO BLOQUEADA PELA AUDITORIA IA")
                else:
                    linhas.append("[OK] Auditoria liberou para o fluxo configurado")
        except Exception as e:
            linhas.append(f"Erro ao checar: {e}")
        return "\n".join(linhas)

    def _calcular_risco(self, p: dict) -> str:
        md = _parse_materia(p)
        if not md or not md.get("conteudo"):
            return "Materia ainda nao gerada."
        try:
            return resumo_risco(analisar_risco(
                md["conteudo"], canal=p.get("canal_forcado") or p.get("canal", "")))
        except Exception as e:
            return f"Erro ao analisar risco: {e}"

    def _calcular_materia(self, p: dict) -> str:
        md = _parse_materia(p)
        if not md:
            return "Materia nao gerada ainda."
        alt      = md.get("titulos_alternativos") or []
        alt_capa = md.get("titulos_capa_alternativos") or []
        linhas = [
            f"TITULO SEO    : {md.get('titulo', '')}",
            f"TITULO CAPA   : {md.get('titulo_capa', '')}",
            f"SUBTITULO     : {md.get('subtitulo', '')}",
            f"LEGENDA FOTO  : {md.get('legenda', '')}",
            f"RETRANCA      : {md.get('retranca', '')}",
            f"SLUG          : {md.get('slug', '')}",
            f"TAGS          : {md.get('tags', '')}",
            f"META DESC     : {md.get('meta_description', '')}",
            f"RESUMO CURTO  : {md.get('resumo_curto', '')}",
            f"CHAMADA SOCIAL: {md.get('chamada_social', '')}",
        ]
        if md.get("nome_da_fonte"):
            linhas += [f"NOME FONTE    : {md.get('nome_da_fonte', '')}"]
        if md.get("creditos_da_foto"):
            linhas += [f"CRED. FOTO    : {md.get('creditos_da_foto', '')}"]
        if md.get("estrutura_decisao"):
            linhas += [f"ESTRUTURA     : {md.get('estrutura_decisao', '')}"]
        # Auditoria v44
        aud_status = md.get("status_pipeline", "")
        aud_ok     = md.get("auditoria_aprovada", None)
        if aud_status:
            icone = "[OK]" if aud_ok else "[XX]"
            linhas += [f"AUDITORIA IA  : {icone} {aud_status.upper()}"]
            viol = md.get("violacoes_factuais", [])
            if viol:
                linhas += ["  Violações factuais:"] + [f"    * {v}" for v in viol[:3]]
        if alt:
            linhas += ["\nTITULOS ALTERNATIVOS:"] + [f"  {i}. {t}" for i, t in enumerate(alt[:3], 1)]
        if alt_capa:
            linhas += ["\nTITULOS CAPA ALTERNATIVOS:"] + [f"  {i}. {t}" for i, t in enumerate(alt_capa[:3], 1)]
        linhas += ["", "-" * 60, md.get("conteudo", "")]
        return "\n".join(linhas)

    def _calcular_auditoria(self, p: dict) -> str:
        uid = p.get("uid") or p.get("_uid", "")
        if not uid:
            return "UID nao disponivel."
        try:
            conn = self.db._conectar()
            try:
                rows = conn.execute(
                    "SELECT timestamp, acao, detalhe, sucesso "
                    "FROM auditoria WHERE pauta_uid=? ORDER BY id ASC",
                    (uid,)).fetchall()
            finally:
                conn.close()
            linhas = ["=" * 60, f"  AUDITORIA — {uid}", "=" * 60, ""]
            for r in rows:
                linhas.append(f"[{r['timestamp']}] {'[OK]' if r['sucesso'] else '[XX]'} "
                              f"{r['acao']:<26} {r['detalhe']}")
            if not rows:
                linhas.append("Nenhum registro de auditoria.")
            return "\n".join(linhas)
        except Exception as e:
            return f"Erro ao carregar auditoria: {e}"

    # ── Aba Leitura da Fonte (v43) ────────────────────────────────────────────

    def _construir_aba_leitura(self, frame: tk.Frame):
        """Monta a aba '📄 Fonte' com imagem + área de texto + botão de atualizar."""
        # Toolbar
        tb = tk.Frame(frame, bg=COR_PAINEL)
        tb.pack(fill="x", padx=6, pady=(4, 0))
        tk.Label(tb, text="📄 Leitura da Fonte Original",
                 bg=COR_PAINEL, fg=COR_TEXTO,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=4)
        self._btn_leitura_refresh = tk.Button(
            tb, text="↺ Recarregar", bg="#1e3a5f", fg="#7dd3fc",
            font=("Segoe UI", 8), relief="flat", padx=8, cursor="hand2",
            command=self._leitura_refresh)
        self._btn_leitura_refresh.pack(side="right", padx=4)
        self._lbl_leitura_status = tk.Label(
            tb, text="", bg=COR_PAINEL, fg=COR_CINZA,
            font=("Segoe UI", 8))
        self._lbl_leitura_status.pack(side="right", padx=8)

        # Painel lateral: imagem + termos (ao lado esquerdo)
        painel_lateral = tk.Frame(frame, bg=COR_FUNDO, width=330)
        painel_lateral.pack(side="left", fill="y", padx=(6, 0), pady=4)
        painel_lateral.pack_propagate(False)

        # Imagem da fonte
        self._leitura_img_frame = tk.Frame(painel_lateral, bg="#0d0d14",
                                           relief="flat", bd=1, height=200)
        self._leitura_img_frame.pack(fill="x", padx=4, pady=(4, 2))
        self._leitura_img_frame.pack_propagate(False)
        self._lbl_leitura_imagem = tk.Label(
            self._leitura_img_frame, text="",
            bg="#0d0d14", fg=COR_CINZA, anchor="center")
        self._lbl_leitura_imagem.pack(expand=True, fill="both")
        self._leitura_photo_ref = None  # mantém referência para evitar GC

        # Termos detectados
        self._lbl_leitura_termos = tk.Label(
            painel_lateral, text="", bg=COR_FUNDO, fg=COR_VERDE,
            font=("Segoe UI", 8), anchor="nw", wraplength=310, justify="left")
        self._lbl_leitura_termos.pack(fill="x", padx=6, pady=(2, 0))

        # Área de texto principal (ocupa o resto)
        self._leitura_txt = scrolledtext.ScrolledText(
            frame, bg="#101018", fg=COR_TEXTO,
            font=FONTE_MONO, borderwidth=0,
            state="disabled", wrap="word")
        self._leitura_txt.pack(side="left", fill="both", expand=True, padx=6, pady=4)
        self._leitura_txt.tag_configure("destaque", foreground="#fde68a",
                                        background="#451a03")
        self._leitura_txt.tag_configure("intel", foreground="#86efac")

    def _obter_texto_aba_fonte_v96(self) -> str:
        """Retorna o texto atualmente exibido na aba Fonte, quando houver."""
        try:
            if not getattr(self, "_leitura_txt", None):
                return ""
            txt = self._leitura_txt.get("1.0", "end").strip()
            if not txt or txt.startswith("Buscando texto") or txt.startswith("Não foi possível"):
                return ""
            if "INTEL EDITORIAL:" in txt:
                partes = txt.split("────────────────────────────────────────────────────────────")
                if len(partes) >= 3:
                    txt = partes[-1].strip()
            return txt.strip()
        except Exception:
            return ""

    def _injetar_fonte_longa_v96(self, pauta: dict, texto: str, origem: str = "aba_fonte") -> bool:
        """Grava texto longo da fonte na pauta e na matéria associada."""
        texto = (texto or "").strip()
        try:
            from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
            texto = limpar_texto_artigo_v101(texto, titulo=(pauta or {}).get("titulo_origem", ""), max_chars=16000)
        except Exception:
            pass
        if not pauta or len(texto) < 300:
            return False
        atual = (pauta.get("cleaned_source_text") or pauta.get("texto_fonte") or pauta.get("dossie") or "").strip()
        if len(texto) <= len(atual):
            return False
        pauta["_fonte_aba_texto"] = texto
        pauta["fonte_aba_texto"] = texto
        pauta["leitura_fonte_texto"] = texto
        pauta["cleaned_source_text"] = texto
        pauta["raw_source_text"] = texto
        pauta["original_source_text"] = texto
        pauta["texto_fonte"] = texto[:12000]
        pauta["dossie"] = texto[:12000]
        pauta["extraction_status"] = "ok"
        pauta["extraction_method"] = origem
        try:
            md = _parse_materia(pauta) or {}
            if md:
                md["_fonte_aba_texto"] = texto
                md["fonte_aba_texto"] = texto
                md["leitura_fonte_texto"] = texto
                md["cleaned_source_text"] = texto
                md["raw_source_text"] = texto
                md["original_source_text"] = texto
                md["texto_fonte"] = texto[:12000]
                md["dossie"] = texto[:12000]
                pauta["materia"] = md
                uid = pauta.get("uid") or pauta.get("_uid")
                if uid:
                    self.db.salvar_materia(uid, md)
            self.db.salvar_pauta(pauta)
        except Exception as e:
            print(f"[v96] aviso: não consegui persistir fonte longa ({origem}): {e}")
        return True

    def _leitura_refresh(self):
        """Recarrega texto da fonte da pauta selecionada (ignora cache)."""
        if self._pauta_sel:
            self._carregar_aba_leitura(self._pauta_sel, forcar=True)

    def _carregar_aba_leitura(self, pauta: dict, forcar: bool = False):
        """v105: busca primeiro o texto da fonte. Imagem fica em segundo plano."""
        try:
            ok, util, texto = self._v105_texto_fonte_util(pauta)
            if ok and not forcar:
                self._lbl_leitura_status.config(text=f"Fonte OK: {util} chars", fg=COR_VERDE)
                if not _v107_exibir_imagem_fonte(self, pauta, pendente="[imagem agendada depois do texto]"):
                    self._v106_agendar_imagem(pauta, motivo="abrir_fonte_com_texto", delay=1.0, prioridade=True)
                self._escrever(self._leitura_txt, _v107_formatar_texto_fonte(pauta, texto, max_chars=16000))
                return
        except Exception:
            pass
        self._lbl_leitura_status.config(text="Buscando texto completo...", fg=COR_AMARELO)
        self._escrever(self._leitura_txt, "Buscando texto da fonte original em modo persistente v105...")
        _v107_exibir_imagem_fonte(self, pauta, pendente="[imagem depois do texto]")
        # Prioriza também no worker; a chamada abaixo tem trava anti-concorrência.
        self._v105_agendar_hidratacao(pauta, prioridade=True, motivo="aba_fonte", delay=0)
        threading.Thread(
            target=lambda: self._v105_hidratar_pauta(pauta, origem="aba_fonte", forcar=forcar, atualizar_ui=True),
            daemon=True,
        ).start()

    # ── Thread helper ─────────────────────────────────────────────────────────

    def _em_thread(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    # ── Coletar ───────────────────────────────────────────────────────────────

    def _acao_coletar(self, silencioso: bool = False):
        if getattr(self, "_coleta_em_andamento", False):
            self._set_status("Coleta já em andamento; aguarde a conclusão.")
            print("[v100] Pedido de coleta ignorado: outra coleta já está em andamento.")
            return
        if not silencioso:
            if not messagebox.askyesno("Coletar Pautas",
                "Iniciar coleta progressiva v100?\n\n"
                "As pautas entram na lista por fases, enquanto a busca ainda continua."):
                return
        self._coleta_em_andamento = True
        self._set_status("Coletando pautas recentes em modo progressivo v100...")
        self._em_thread(self._coletar_thread)

    def _v1303_pauta_tem_interesse_minimo(self, pauta: dict, score: int = 0, canal: str = "", bypass_score: bool = False) -> tuple[bool, str]:
        """v130.3: decide se uma pauta de score baixo pode entrar pela cota mínima.

        A regra não libera lixo editorial: mantém janela, deduplicação, ruído, links inválidos
        e assets. Só permite completar a cota mínima por fonte quando houver sinal claro
        de interesse para o Ururau: fonte regional prioritária, termo da linha editorial,
        tema policial/factual, política pública, município/região estratégica ou esporte local/RJ.
        """
        if bypass_score:
            return True, "bypass_score_fonte_especial"
        try:
            if int(score or 0) >= self._env_int("URURAU_V92_SCORE_MINIMO_LISTA", 55):
                return True, "score_acima_minimo"
        except Exception:
            pass
        texto = " ".join([
            str(pauta.get("titulo_origem") or pauta.get("titulo") or ""),
            str(pauta.get("resumo_origem") or pauta.get("resumo") or ""),
            str(pauta.get("fonte_nome") or pauta.get("nome_fonte") or pauta.get("fonte") or ""),
            str(pauta.get("link_origem") or pauta.get("url") or pauta.get("link") or ""),
        ])
        try:
            ntexto = unicodedata.normalize("NFKD", texto)
            ntexto = "".join(c for c in ntexto if not unicodedata.combining(c)).lower()
            ntexto = re.sub(r"\s+", " ", ntexto)
        except Exception:
            ntexto = texto.lower()

        fonte_txt = str(pauta.get("fonte_nome") or pauta.get("nome_fonte") or pauta.get("fonte") or "")
        try:
            nfonte = unicodedata.normalize("NFKD", fonte_txt)
            nfonte = "".join(c for c in nfonte if not unicodedata.combining(c)).lower()
            nfonte = re.sub(r"\s+", " ", nfonte)
        except Exception:
            nfonte = fonte_txt.lower()

        fontes_regionais_prioritarias = (
            "nf noticias", "nfnoticias", "campos 24 horas", "prefeitura de campos",
            "j3 news", "portal viu", "sf noticias", "o debate", "rj news",
            "o parahybano", "jornal de sabado", "prensa de babel", "clique diario",
        )
        if any(f in nfonte or f in ntexto for f in fontes_regionais_prioritarias):
            return True, "fonte_regional_prioritaria"

        try:
            from ururau.coleta.linha_editorial_v129 import analisar_texto_linha_editorial_v129
            analise = analisar_texto_linha_editorial_v129(
                pauta.get("titulo_origem", "") or pauta.get("titulo", ""),
                pauta.get("resumo_origem", "") or pauta.get("resumo", ""),
                pauta.get("fonte_nome", "") or pauta.get("nome_fonte", ""),
                pauta.get("link_origem", "") or pauta.get("url", ""),
            )
            if int(analise.get("boost", 0) or 0) > 0:
                return True, "termo_config_linha_editorial"
        except Exception:
            pass

        padroes = (
            # factual policial/segurança
            "policia", "policial", "prisao", "preso", "presa", "criminos", "arma", "armas",
            "tiro", "tiros", "troca de tiros", "trafico", "drogas", "apreend", "operacao",
            "homicidio", "assassin", "roubo", "furto", "arrombamento", "acidente", "br-101",
            # política, justiça, gestão pública
            "prefeitura", "camara", "vereador", "deputado", "governo", "alerj", "palacio guanabara",
            "stf", "stj", "tse", "tre-rj", "tjrj", "mprj", "tce-rj", "senado", "licitacao",
            "fraude", "investigacao", "orcamento", "cassacao", "eleicao", "royalties",
            # território de interesse
            "campos", "goytacazes", "guarus", "farol de sao thome", "sao joao da barra",
            "sao francisco de itabapoana", "cardoso moreira", "sao fidelis", "macae", "quissama",
            "carapebus", "conceicao de macabu", "norte fluminense", "porto do acu", "baixada campista",
            # esporte local/RJ
            "flamengo", "vasco", "botafogo", "fluminense", "americano", "goytacaz", "goitacaz",
        )
        for p in padroes:
            if p in ntexto:
                return True, f"padrao_interesse:{p}"

        if str(canal or "").strip().lower() in {"política", "politica", "polícia", "policia", "cidades", "economia", "esportes"}:
            # Canal sozinho só vale com algum sinal territorial ou institucional no texto.
            if any(x in ntexto for x in ("rj", "rio de janeiro", "campos", "macae", "norte fluminense", "alerj", "prefeitura", "camara")):
                return True, f"canal_com_contexto:{canal}"
        return False, "sem_sinal_editorial_minimo"

    def _v94_salvar_lote_progressivo(
        self,
        lote: list[dict],
        resumo_total: dict,
        contagem_fonte: dict,
        limites: dict,
        contexto: str,
        bypass_score: bool = False,
    ) -> int:
        """Pontua, filtra e salva um lote pequeno, atualizando a fila durante a coleta.

        v128: a lógica de coleta/fila foi preservada. A única adição é a geração de
        métricas objetivas do funil para o diagnóstico técnico expandido.
        """
        stats_v128 = {
            "contexto": contexto,
            "brutas": len(lote or []),
            "apos_deduplicacao_local": 0,
            "duplicadas_no_lote": 0,
            "ja_na_fila": 0,
            "publicadas": 0,
            "descartadas_banco": 0,
            "similares_banco": 0,
            "similares_site": 0,
            "aprovadas_banco": 0,
            "fora_janela": 0,
            "descartadas_ruido": 0,
            "score_baixo": 0,
            "bypass_score": 0,
            "baixo_score_review": 0,
            "cota_minima_interesse": 0,
            "gnews_desligado": 0,
            "url_imagem_ou_asset": 0,
            "candidatas_pos_filtro": 0,
            "limite_por_fonte": 0,
            "falhas_salvar": 0,
            "enviadas_fila": 0,
            "primeira_materia_encontrada": "",
            "primeira_materia_enviada": "",
        }
        try:
            if lote:
                stats_v128["primeira_materia_encontrada"] = (lote[0].get("titulo_origem") or lote[0].get("titulo") or lote[0].get("link_origem") or "")[:220]
            self._v128_diag_lotes = getattr(self, "_v128_diag_lotes", {}) or {}
            self._v128_diag_lotes[contexto] = stats_v128
        except Exception:
            pass
        if not lote:
            return 0
        try:
            from ururau.coleta.rss import deduplicar, filtrar_contra_banco
            from ururau.coleta.scoring import calcular_score_editorial, classificar_canal
            from ururau.coleta.ururau_check import filtrar_contra_site_ururau
            from ururau.config.settings import LIMIAR_RELEVANCIA_PUBLICAR
        except Exception as e:
            stats_v128["erro_importacao_filtros"] = str(e)
            print(f"[v100][{contexto}] falha ao importar filtros: {e}")
            return 0

        try:
            lote_dedup_v128 = deduplicar(lote)
            stats_v128["apos_deduplicacao_local"] = len(lote_dedup_v128 or [])
            stats_v128["duplicadas_no_lote"] = max(0, len(lote or []) - len(lote_dedup_v128 or []))
            novas, resumo = filtrar_contra_banco(lote_dedup_v128, self.db)
            stats_v128["ja_na_fila"] = int(resumo.get("em_fila", 0) or 0)
            stats_v128["publicadas"] = int(resumo.get("publicadas", 0) or 0)
            stats_v128["descartadas_banco"] = int(resumo.get("descartadas", 0) or 0)
            stats_v128["similares_banco"] = int(resumo.get("similares", 0) or 0)
            stats_v128["aprovadas_banco"] = int(resumo.get("aprovadas", 0) or 0)
            novas, removidas_site = filtrar_contra_site_ururau(novas, db=self.db)
            stats_v128["similares_site"] = int(removidas_site or 0)
        except Exception as e:
            stats_v128["erro_filtragem"] = str(e)
            print(f"[v100][{contexto}] falha na filtragem: {e}")
            return 0

        for k in ("total", "publicadas", "descartadas", "em_fila", "similares", "aprovadas"):
            resumo_total[k] = resumo_total.get(k, 0) + int(resumo.get(k, 0) or 0)
        resumo_total["similares"] = resumo_total.get("similares", 0) + int(removidas_site or 0)

        score_minimo = self._env_int("URURAU_V92_SCORE_MINIMO_LISTA", max(55, LIMIAR_RELEVANCIA_PUBLICAR))
        max_por_fonte = limites["max_por_fonte"]
        max_total = limites["max_total"]
        refresh_a_cada = max(1, limites["refresh_a_cada"])

        candidatos: list[dict] = []
        baixo_score_review_v129: list[dict] = []
        for pauta in novas:
            try:
                # v99: garantia extra. Mesmo que algum coletor antigo retorne pauta
                # fora da janela, ela não entra na fila.
                dt_pub_v99 = (
                    parse_data_br_ou_iso(pauta.get("_data_pub_ordem") or "")
                    or parse_data_br_ou_iso(pauta.get("data_pub_fonte_br") or "")
                    or parse_data_br_ou_iso(pauta.get("data_pub_fonte") or "")
                )
                ok_janela, motivo_janela, idade_janela = dentro_da_janela(dt_pub_v99)
                if not ok_janela:
                    permitir_excecao_final_v123 = (
                        pauta.get("_excecao_fora_janela_v123")
                        and os.getenv("URURAU_RSS_COLETAR_1_FORA_JANELA", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
                    )
                    if permitir_excecao_final_v123:
                        print(f"[v123][JANELA][EXCECAO] mantendo pauta fora da janela ({motivo_janela}, idade={idade_janela:.2f}h): {(pauta.get('titulo_origem') or '')[:90]}")
                    else:
                        print(f"[v100][JANELA] ignorada ({motivo_janela}, idade={idade_janela:.2f}h, limite={janela_publicacao_horas()}h): {(pauta.get('titulo_origem') or '')[:90]}")
                        stats_v128["fora_janela"] = stats_v128.get("fora_janela", 0) + 1
                        continue
                pauta["_idade_pub_horas_v99"] = round(float(idade_janela), 2)

                link = (pauta.get("link_origem") or "").lower()
                if "news.google.com" in link and not self._env_bool("URURAU_V92_USAR_GNEWS", "0"):
                    stats_v128["gnews_desligado"] = stats_v128.get("gnews_desligado", 0) + 1
                    continue
                if any(x in link for x in ("googleusercontent.com", "gstatic.com", "ggpht.com", "ytimg.com")):
                    stats_v128["url_imagem_ou_asset"] = stats_v128.get("url_imagem_ou_asset", 0) + 1
                    continue
                if link.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico")):
                    stats_v128["url_imagem_ou_asset"] = stats_v128.get("url_imagem_ou_asset", 0) + 1
                    continue

                try:
                    from ururau.coleta.source_policy_v114 import deve_ignorar_pauta as _v114_deve_ignorar_pauta
                    ignorar_v114, motivo_v114 = _v114_deve_ignorar_pauta(
                        pauta.get("titulo_origem", ""),
                        pauta.get("resumo_origem", ""),
                        pauta.get("link_origem", ""),
                        pauta.get("fonte_nome", ""),
                    )
                    if ignorar_v114:
                        print(f"[v111.4][RUIDO] descartada antes da fila ({motivo_v114}): {(pauta.get('titulo_origem') or '')[:90]}")
                        stats_v128["descartadas_ruido"] = stats_v128.get("descartadas_ruido", 0) + 1
                        continue
                except Exception:
                    pass

                sc = int(calcular_score_editorial(pauta) or 0)
                canal = pauta.get("canal_forcado")
                if not canal:
                    canal, _conf_canal, _pts_canal = classificar_canal(
                        pauta.get("titulo_origem", ""), pauta.get("resumo_origem", "")
                    )
                if canal == "Politica":
                    canal = "Política"
                pauta["score_editorial"] = sc
                pauta["canal_forcado"] = canal
                pauta["_v94_listagem_rapida"] = True
                pauta["_v94_precisa_hidratar"] = True
                pauta["_v94_contexto_coleta"] = contexto
                pauta["_v94_motivo"] = "listada antes da hidratação completa"
                bypass_v129 = False
                motivo_bypass_v129 = ""
                try:
                    from ururau.coleta.linha_editorial_v129 import fonte_score_livre_v129
                    bypass_v129 = bool(
                        bypass_score
                        or pauta.get("bypass_score")
                        or pauta.get("_v1304_rss_regional_prioritario")
                        or pauta.get("regional_prioritaria")
                        or fonte_score_livre_v129(
                            pauta.get("fonte_nome", "") or pauta.get("nome_fonte", ""),
                            pauta.get("link_origem", "") or pauta.get("url", ""),
                        )
                    )
                    if bypass_v129:
                        motivo_bypass_v129 = "fonte_especial_ou_oficial_v129"
                except Exception:
                    bypass_v129 = bool(bypass_score)
                    motivo_bypass_v129 = "fonte_especial_v129"

                if sc >= score_minimo or bypass_v129:
                    if bypass_v129 and sc < score_minimo:
                        pauta["_v129_bypass_score"] = True
                        pauta["_v129_motivo_bypass"] = motivo_bypass_v129
                        pauta["_v94_motivo"] = "fonte especial/oficial v129: bypass de score"
                        stats_v128["bypass_score"] = stats_v128.get("bypass_score", 0) + 1
                    candidatos.append(pauta)
                else:
                    min_por_fonte_v1303 = self._env_int("URURAU_V1303_MIN_POR_FONTE_FUNCIONAL", 2)
                    usar_cota_v1303 = self._env_bool("URURAU_V1303_COTA_MINIMA_INTERESSE", "1")
                    tem_interesse_v1303, motivo_interesse_v1303 = self._v1303_pauta_tem_interesse_minimo(
                        pauta, score=sc, canal=canal, bypass_score=bypass_v129
                    )
                    if usar_cota_v1303 and len(candidatos) < min_por_fonte_v1303 and tem_interesse_v1303:
                        pauta["_v1303_promovida_cota_minima"] = True
                        pauta["_v1303_motivo_cota_minima"] = motivo_interesse_v1303
                        pauta["_v94_motivo"] = f"cota mínima de fonte funcional/interesse v130.3: {motivo_interesse_v1303}"
                        stats_v128["cota_minima_interesse"] = stats_v128.get("cota_minima_interesse", 0) + 1
                        candidatos.append(pauta)
                    else:
                        stats_v128["score_baixo"] = stats_v128.get("score_baixo", 0) + 1
                        if len(baixo_score_review_v129) < self._env_int("URURAU_V129_BAIXO_SCORE_MAX_POR_LOTE", 5):
                            p_baixo = dict(pauta)
                            p_baixo["status"] = "baixo_score"
                            p_baixo["_v129_baixo_score_review"] = True
                            p_baixo["_v129_titulo_original_rss"] = p_baixo.get("titulo_origem") or p_baixo.get("titulo") or ""
                            p_baixo["_v129_titulo_visual"] = _titulo_visual_v129_1(p_baixo)
                            if _titulo_generico_v129_1(p_baixo.get("titulo_origem", "")):
                                p_baixo["titulo_origem"] = p_baixo["_v129_titulo_visual"]
                            p_baixo["_v129_score_minimo"] = score_minimo
                            p_baixo["_v129_motivo_baixo_score"] = f"score {sc} < mínimo {score_minimo}"
                            p_baixo["_v94_motivo"] = "baixo score para avaliação manual"
                            baixo_score_review_v129.append(p_baixo)
            except Exception as e:
                print(f"[v100][SCORING] {e}")

        # v99: salvar/atualizar progressivamente pelas mais recentes primeiro;
        # score continua sendo filtro, não a ordem principal da fila.
        def _ordem_candidato_v99(p: dict) -> str:
            dtp = (
                parse_data_br_ou_iso(p.get("_data_pub_ordem") or "")
                or parse_data_br_ou_iso(p.get("data_pub_fonte_br") or "")
                or parse_data_br_ou_iso(p.get("data_pub_fonte") or "")
            )
            return dtp.strftime("%Y-%m-%d %H:%M:%S") if dtp else ""

        candidatos.sort(key=_ordem_candidato_v99, reverse=True)
        stats_v128["candidatas_pos_filtro"] = len(candidatos)
        inseridas = 0
        for pauta in candidatos:
            if resumo_total.get("inseridas", 0) >= max_total:
                break
            nome_fonte = pauta.get("fonte_nome") or pauta.get("nome_fonte") or "desconhecida"
            if contagem_fonte.get(nome_fonte, 0) >= max_por_fonte:
                resumo_total["ignoradas_fonte"] = resumo_total.get("ignoradas_fonte", 0) + 1
                stats_v128["limite_por_fonte"] = stats_v128.get("limite_por_fonte", 0) + 1
                continue
            try:
                # v123: marca pauta com o lote de coleta atual para separar visualmente na fila.
                try:
                    lote_v123 = getattr(self, "_v123_lote_atual", None)
                    if isinstance(lote_v123, dict):
                        pauta.update(lote_v123)
                except Exception:
                    pass
                pauta["status"] = 'captada'
                self.db.salvar_pauta(pauta)
                contagem_fonte[nome_fonte] = contagem_fonte.get(nome_fonte, 0) + 1
                inseridas += 1
                stats_v128["enviadas_fila"] = inseridas
                resumo_total["inseridas"] = resumo_total.get("inseridas", 0) + 1
                titulo = pauta.get("titulo_origem", "")[:90]
                if not stats_v128.get("primeira_materia_enviada"):
                    stats_v128["primeira_materia_enviada"] = titulo
                print(f"[v100][FILA] entrou ({contexto}): {titulo}")
                # v105/v106: entrou na fila, entra automaticamente na fila de busca de texto completo.
                self._v105_agendar_hidratacao(pauta, prioridade=False, motivo=f"nova_pauta:{contexto}")
                # Se o RSS já trouxe texto integral, a pauta já entra como TXT OK e a imagem é agendada.
                try:
                    _ok_txt, _util_txt, _ = self._v105_texto_fonte_util(pauta)
                    if _ok_txt:
                        self._v106_agendar_imagem(pauta, motivo=f"rss_pre_texto:{contexto}", delay=2.0)
                except Exception:
                    pass
                total = resumo_total.get("inseridas", 0)
                if total == 1 or total % refresh_a_cada == 0:
                    self.after(0, self._carregar_pautas)
                    self.after(0, lambda n=total: self._set_status(f"v100: {n} pautas recentes já entraram; coleta continua..."))
            except Exception as e:
                stats_v128["falhas_salvar"] = stats_v128.get("falhas_salvar", 0) + 1
                print(f"[v100][FILA] falha ao salvar pauta: {e}")
        # v129: se a fonte encontrou pautas, mas nenhuma entrou por score,
        # salva uma amostra auditável no fim da fila como "baixo_score".
        if inseridas == 0 and baixo_score_review_v129 and self._env_bool("URURAU_V129_BAIXO_SCORE_AUDITAVEL", "1"):
            salvas_baixo = 0
            for pauta_baixo in baixo_score_review_v129:
                try:
                    try:
                        lote_v123 = getattr(self, "_v123_lote_atual", None)
                        if isinstance(lote_v123, dict):
                            pauta_baixo.update(lote_v123)
                    except Exception:
                        pass
                    self.db.salvar_pauta(pauta_baixo)
                    salvas_baixo += 1
                except Exception as e:
                    print(f"[v129][BAIXO_SCORE] falha ao salvar amostra: {e}")
            if salvas_baixo:
                stats_v128["baixo_score_review"] = salvas_baixo
                self.after(0, self._carregar_pautas)
                print(f"[v129][BAIXO_SCORE] {salvas_baixo} pauta(s) listada(s) para avaliação em {contexto}")
        stats_v128["enviadas_fila"] = inseridas
        return inseridas

    def _v128_diag_lote(self, contexto: str) -> dict:
        """Retorna métricas do último lote processado por _v94_salvar_lote_progressivo."""
        try:
            return dict((getattr(self, "_v128_diag_lotes", {}) or {}).get(contexto, {}) or {})
        except Exception:
            return {}

    def _coletar_thread(self):
        """
        v100 — coleta rápida em fases, com atualização progressiva real.

        Fases padrão:
        1. RSS fonte por fonte, salvando lotes imediatamente.
        2. Fontes oficiais por lote próprio.
        3. Google News apenas se habilitado no .env.
        4. Source Hunter pesado apenas se habilitado no .env.
        """
        resumo_total = {
            "total": 0, "publicadas": 0, "descartadas": 0, "em_fila": 0,
            "similares": 0, "aprovadas": 0, "inseridas": 0, "ignoradas_fonte": 0,
        }
        try:
            import os
            from collections import defaultdict
            from ururau.coleta.rss import (
                coletar_rss, coletar_google_news,
                obter_termos_google_news, obter_termos_radar_audiencia_v88,
                coletar_source_hunter_premium_v88,
            )
            from ururau.coleta.google_news_scraper_v108 import coletar_google_news_termos_v108


            limites = {
                "max_por_fonte": self._env_int("URURAU_V92_MAX_POR_FONTE", 10),
                "max_total": self._env_int("URURAU_V92_MAX_SALVAR_RAPIDO", 250),
                "refresh_a_cada": self._env_int("URURAU_V92_REFRESH_A_CADA", 3),
            }
            contagem_fonte: dict[str, int] = defaultdict(int)
            auditoria_v126 = None

            # v123: cada clique em Coletar gera um lote visual separado na fila.
            try:
                seq_path = Path("data") / "coleta_seq_v123.txt"
                seq_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    seq_atual = int(seq_path.read_text(encoding="utf-8", errors="ignore").strip() or "0") + 1
                except Exception:
                    seq_atual = 1
                seq_path.write_text(str(seq_atual), encoding="utf-8")
                hora_lote = time.strftime("%H:%M")
                self._v123_lote_atual = {
                    "coleta_lote_id_v123": f"coleta_{seq_atual}_{int(time.time())}",
                    "coleta_lote_ordem_v123": seq_atual,
                    "coleta_lote_hora_v123": hora_lote,
                    "coleta_lote_label_v123": f"Coleta {seq_atual} - {hora_lote}",
                }
                print(f"[v123][COLETA] iniciado lote: {self._v123_lote_atual['coleta_lote_label_v123']}")
            except Exception as _e_lote_v123:
                print(f"[v123][COLETA] aviso lote não criado: {_e_lote_v123}")
                self._v123_lote_atual = None

            fontes = _carregar_fontes_rss()
            try:
                from ururau.coleta.coleta_auditoria_v126 import AuditoriaColetaV126
                lote_label_v126 = ""
                if isinstance(getattr(self, "_v123_lote_atual", None), dict):
                    lote_label_v126 = self._v123_lote_atual.get("coleta_lote_label_v123") or ""
                auditoria_v126 = AuditoriaColetaV126(lote_label_v126)
            except Exception as _e_auditoria_v126:
                print(f"[v126][DIAGNOSTICO] auditoria indisponível: {_e_auditoria_v126}")
                auditoria_v126 = None

            print(f"[v100] Coleta rápida em fases: {len(fontes)} fonte(s) RSS configurada(s).")
            self.after(0, lambda: self._set_status("v100: fase 1/5 — RSS fonte por fonte..."))

            for idx, fonte in enumerate(fontes, start=1):
                if resumo_total["inseridas"] >= limites["max_total"]:
                    break
                nome = fonte.get("nome") or fonte.get("url") or f"fonte {idx}"
                self.after(0, lambda i=idx, total=len(fontes), n=nome: self._set_status(f"v100: RSS {i}/{total} — {n}"))
                try:
                    # v131: se esta fonte RSS tem perfil operacional testado pelo Diagnóstico,
                    # a coleta efetiva fica na fase AutoFontes v131.3 para evitar parser errado/duplicidade.
                    try:
                        from ururau.coleta.auto_perfil_fontes_v131 import perfil_ativo_para_url_v131
                        if perfil_ativo_para_url_v131(str(fonte.get("url") or "")):
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=idx, nome=nome, url=fonte.get("url") or "", tipo="rss_config_auto_v131",
                                    encontradas=0, enviadas_fila=0,
                                    observacao="RSS configurado, mas coletado por perfil operacional AutoFontes v131.3 para evitar duplicidade."
                                )
                            continue
                    except Exception:
                        pass
                    # v129.13: Manchete RJ tem diagnóstico próprio e funciona melhor por /portal/feed/,
                    # com fallback para WP API/sitemap/HTML. Não mexe nos demais RSS.
                    url_fonte_v12913 = str(fonte.get("url") or "").lower()
                    nome_fonte_v12913 = str(nome or "").lower()
                    if "mancheterj.com" in url_fonte_v12913 or nome_fonte_v12913.strip() == "manchete rj":
                        from ururau.coleta.adapters.mancheterj_v12913 import (
                            coletar_mancheterj_v12913, obter_diagnostico_mancheterj_v12913
                        )
                        lote = coletar_mancheterj_v12913(max_itens=self._env_int("URURAU_MANCHETERJ_MAX_ITENS", 10))
                        contexto_mjrj_v12913 = f"RSS: {nome}"
                        inseridas_v126 = self._v94_salvar_lote_progressivo(lote, resumo_total, contagem_fonte, limites, contexto_mjrj_v12913)
                        if inseridas_v126:
                            try:
                                self.after(250, lambda: self._carregar_pautas(forcar=True))
                            except Exception:
                                pass
                        if auditoria_v126:
                            diag_mjrj = self._v128_diag_lote(contexto_mjrj_v12913)
                            diag_mjrj["mancheterj_detalhe_v12913"] = obter_diagnostico_mancheterj_v12913()
                            auditoria_v126.registrar(
                                ordem=idx,
                                nome=nome,
                                url=fonte.get("url") or "",
                                tipo="rss_especial_mancheterj_v12914",
                                encontradas=len(lote or []),
                                enviadas_fila=inseridas_v126,
                                observacao="Manchete RJ v129.14: /portal/feed/ -> /portal/rss/ -> raiz -> WP API -> sitemap/HTML, com exibição garantida na fila.",
                                diagnostico=diag_mjrj,
                            )
                    else:
                        try:
                            lote = coletar_rss([fonte], incluir_oficiais=False)
                        except TypeError:
                            lote = coletar_rss([fonte])
                        inseridas_v126 = self._v94_salvar_lote_progressivo(lote, resumo_total, contagem_fonte, limites, f"RSS: {nome}")
                        if auditoria_v126:
                            auditoria_v126.registrar(
                                ordem=idx,
                                nome=nome,
                                url=fonte.get("url") or "",
                                tipo=fonte.get("tipo_fonte_config_v126") or "rss",
                                encontradas=len(lote or []),
                                enviadas_fila=inseridas_v126,
                                observacao="RSS processado com diagnóstico v128 do funil de entrada.",
                                diagnostico=self._v128_diag_lote(f"RSS: {nome}"),
                            )
                except Exception as e:
                    print(f"[v100][RSS] falha em {nome}: {e}")
                    if auditoria_v126:
                        auditoria_v126.registrar(
                            ordem=idx,
                            nome=nome,
                            url=fonte.get("url") or "",
                            tipo=fonte.get("tipo_fonte_config_v126") or "rss",
                            encontradas=0,
                            enviadas_fila=0,
                            erro=str(e),
                        )


            # v131: AutoFontes — perfis operacionais gerados pelo Diagnóstico de Fonte.
            # Uma fonte só entra aqui se o diagnóstico tiver sido convertido em perfil e testado com pauta real.
            try:
                from ururau.coleta.auto_perfil_fontes_v131 import coletar_todos_perfis_v131
                perfis_v131 = coletar_todos_perfis_v131()
                if perfis_v131 and resumo_total["inseridas"] < limites["max_total"]:
                    self.after(0, lambda: self._set_status("v132.5: fase AutoFontes — fontes autoadequadas pelo diagnóstico..."))
                    print(f"[v131][AUTOFONTES] {len(perfis_v131)} perfil(is) operacional(is) carregado(s).")
                    for pidx_v131, (perfil_v131, lote_v131, stats_v131) in enumerate(perfis_v131, start=1):
                        if resumo_total["inseridas"] >= limites["max_total"]:
                            break
                        nome_v131 = perfil_v131.get("nome") or perfil_v131.get("dominio") or f"AutoFonte {pidx_v131}"
                        url_v131 = (perfil_v131.get("feeds") or [perfil_v131.get("root") or ""])[0]
                        contexto_v131 = f"AutoFonte v131.3: {nome_v131}"
                        bypass_v131 = bool(perfil_v131.get("bypass_score") or perfil_v131.get("grupo") in ("Regionais", "Especiais"))
                        try:
                            inseridas_v131 = self._v94_salvar_lote_progressivo(
                                lote_v131, resumo_total, contagem_fonte, limites, contexto_v131, bypass_score=bypass_v131
                            )
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=650 + pidx_v131,
                                    nome=nome_v131,
                                    url=url_v131,
                                    tipo=f"auto_v131_{str(perfil_v131.get('grupo') or 'rss').lower()}",
                                    encontradas=len(lote_v131 or []),
                                    enviadas_fila=inseridas_v131,
                                    observacao=(
                                        f"Autoadequação v132.5: perfil gerado/testado pelo Diagnóstico de Fonte; "
                                        f"parser={stats_v131.get('parser')}; brutas={stats_v131.get('brutas')}; "
                                        f"titulo_link={stats_v131.get('titulo_link')}; aceitas={stats_v131.get('aceitas')}."
                                    ),
                                    diagnostico=self._v128_diag_lote(contexto_v131),
                                )
                        except Exception as e_v131_item:
                            print(f"[v131][AUTOFONTES] falha em {nome_v131}: {e_v131_item}")
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=650 + pidx_v131, nome=nome_v131, url=url_v131,
                                    tipo="auto_v131", encontradas=0, enviadas_fila=0, erro=str(e_v131_item)
                                )
            except Exception as e_v131:
                print(f"[v131][AUTOFONTES] fase ignorada por erro: {e_v131}")

            # v130.5: Regionais em aba própria.
            # Usam parser RSS normal, mas com boost/cota e bypass de score baixo.
            try:
                fontes_regionais_v1305 = _carregar_regionais_v1305()
                if fontes_regionais_v1305 and resumo_total["inseridas"] < limites["max_total"]:
                    self.after(0, lambda: self._set_status("v130.5: fase Regionais — sites locais prioritários..."))
                    print(f"[v130.5][REGIONAIS] {len(fontes_regionais_v1305)} regional(is) configurado(s).")
                    for ridx, fonte_reg in enumerate(fontes_regionais_v1305, start=1):
                        if resumo_total["inseridas"] >= limites["max_total"]:
                            break
                        if fonte_reg.get("ativo", True) is False:
                            continue
                        nome_reg = fonte_reg.get("nome") or fonte_reg.get("fonte_nome") or fonte_reg.get("url") or f"Regional {ridx}"
                        url_reg = str(fonte_reg.get("url") or "")
                        # v131: se esta fonte já tem perfil operacional testado pelo Diagnóstico,
                        # a coleta efetiva ocorre na fase AutoFontes, evitando duplicidade e parser errado.
                        try:
                            from ururau.coleta.auto_perfil_fontes_v131 import perfil_ativo_para_url_v131
                            if perfil_ativo_para_url_v131(url_reg):
                                if auditoria_v126:
                                    auditoria_v126.registrar(
                                        ordem=700 + ridx, nome=nome_reg, url=url_reg, tipo="regional_config_v1305",
                                        encontradas=0, enviadas_fila=0,
                                        observacao="Regional configurado, mas coletado por perfil operacional AutoFontes v131.3 para evitar duplicidade."
                                    )
                                continue
                        except Exception:
                            pass
                        # Campos 24 Horas já tem coletor especial próprio e mais completo. Mantemos visível em Regionais,
                        # mas a coleta efetiva fica na etapa 900 para evitar duplicidade.
                        if "campos24horas.com.br" in url_reg.lower():
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=700 + ridx, nome=nome_reg, url=url_reg, tipo="regional_config_v1305",
                                    encontradas=0, enviadas_fila=0,
                                    observacao="Regional configurado, mas coletado pelo adaptador especial Campos 24 Horas na etapa própria para evitar duplicidade.",
                                )
                            continue
                        try:
                            fonte_reg = dict(fonte_reg)
                            fonte_reg["regional_prioritaria"] = True
                            fonte_reg["bypass_score"] = True
                            fonte_reg["tipo"] = fonte_reg.get("tipo") or "regional_v1305"
                            fonte_reg["tipo_coleta"] = fonte_reg.get("tipo_coleta") or "regional_v1305"
                            # v130.6: NF Notícias tem RSS válido, mas o parser regional genérico
                            # vinha retornando 0 itens. Usa adaptador XML direto e mantém a aba Regionais.
                            stats_nf_v1306 = None
                            stats_auto_v1325 = None
                            perfil_auto_v1325 = None
                            if ("nfnoticias.com.br" in url_reg.lower()) or ("nf notícias" in str(nome_reg).lower()) or ("nf noticias" in str(nome_reg).lower()) or ("nfnoticias" in str(nome_reg).lower()):
                                try:
                                    from ururau.coleta.adapters.nfnoticias_v1306 import coletar_nfnoticias_v1306
                                    lote_reg, stats_nf_v1306 = coletar_nfnoticias_v1306()
                                    print(f"[v130.6][NF] parser={stats_nf_v1306.get('parser')} rss_items={stats_nf_v1306.get('rss_items')} aceitas={stats_nf_v1306.get('aceitas')} url={stats_nf_v1306.get('url_usada')}")
                                except Exception as e_nf_v1306:
                                    print(f"[v130.6][NF] adaptador falhou; tentando RSS genérico: {e_nf_v1306}")
                                    try:
                                        lote_reg = coletar_rss([fonte_reg], incluir_oficiais=False)
                                    except TypeError:
                                        lote_reg = coletar_rss([fonte_reg])
                            else:
                                stats_auto_v1325 = None
                                perfil_auto_v1325 = None
                                usar_auto_v1325 = (
                                    str(fonte_reg.get("tipo_coleta") or "").lower().startswith("auto")
                                    or bool(fonte_reg.get("perfil_v131_id"))
                                    or bool(fonte_reg.get("diagnostico_v131"))
                                    or "tribunanf.com.br" in url_reg.lower()
                                    or "expressorio.com.br" in url_reg.lower()
                                )
                                if usar_auto_v1325:
                                    try:
                                        from ururau.coleta.auto_perfil_fontes_v131 import coletar_url_auto_v1325
                                        lote_reg, stats_auto_v1325, perfil_auto_v1325 = coletar_url_auto_v1325(url_reg, nome_reg, grupo="Regionais")
                                        print(f"[v132.5][REGIONAL-AUTO] {nome_reg}: parser={stats_auto_v1325.get('parser')} brutas={stats_auto_v1325.get('brutas')} titulo_link={stats_auto_v1325.get('titulo_link')} aceitas={stats_auto_v1325.get('aceitas')}")
                                    except Exception as e_auto_v1325:
                                        print(f"[v132.5][REGIONAL-AUTO] falhou em {nome_reg}; tentando RSS genérico: {e_auto_v1325}")
                                        stats_auto_v1325 = None
                                        try:
                                            lote_reg = coletar_rss([fonte_reg], incluir_oficiais=False)
                                        except TypeError:
                                            lote_reg = coletar_rss([fonte_reg])
                                else:
                                    try:
                                        lote_reg = coletar_rss([fonte_reg], incluir_oficiais=False)
                                    except TypeError:
                                        lote_reg = coletar_rss([fonte_reg])
                            contexto_reg = f"Regional: {nome_reg}"
                            inseridas_reg = self._v94_salvar_lote_progressivo(
                                lote_reg, resumo_total, contagem_fonte, limites, contexto_reg, bypass_score=True
                            )
                            if auditoria_v126:
                                tipo_registro_v1325 = "regional_nfnoticias_v1306" if stats_nf_v1306 else ("auto_v1325_regionais" if locals().get("stats_auto_v1325") else "regional_v1305")
                                obs_registro_v1325 = (
                                    f"NF Notícias v130.6: RSS direto; parser={stats_nf_v1306.get('parser')}; rss_items={stats_nf_v1306.get('rss_items')}; titulo_link={stats_nf_v1306.get('titulo_link')}; fora_janela={stats_nf_v1306.get('fora_janela')}; aceitas={stats_nf_v1306.get('aceitas')}."
                                    if stats_nf_v1306 else
                                    (f"AutoFontes v132.5 aplicado a Regional: parser={stats_auto_v1325.get('parser')}; brutas={stats_auto_v1325.get('brutas')}; titulo_link={stats_auto_v1325.get('titulo_link')}; aceitas={stats_auto_v1325.get('aceitas')}; feeds={stats_auto_v1325.get('feeds_testados_v1325')}." if locals().get("stats_auto_v1325") else
                                     "Regional v130.5: site local prioritário; parser RSS normal, boost/cota regional e livre do corte de score baixo.")
                                )
                                auditoria_v126.registrar(
                                    ordem=700 + ridx, nome=nome_reg, url=url_reg,
                                    tipo=tipo_registro_v1325,
                                    encontradas=len(lote_reg or []), enviadas_fila=inseridas_reg,
                                    observacao=obs_registro_v1325,
                                    diagnostico=self._v128_diag_lote(contexto_reg),
                                )
                        except Exception as e:
                            print(f"[v130.5][REGIONAIS] falha em {nome_reg}: {e}")
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=700 + ridx, nome=nome_reg, url=url_reg, tipo="regional_v1305",
                                    encontradas=0, enviadas_fila=0, erro=str(e),
                                )
            except Exception as e:
                print(f"[v130.5][REGIONAIS] fase ignorada por erro: {e}")


            # v129: fontes especiais configuradas em aba própria.
            # Entram em fase separada e não são bloqueadas por score baixo.
            try:
                fontes_especiais_v129 = _carregar_fontes_especiais_v129()
                if fontes_especiais_v129 and resumo_total["inseridas"] < limites["max_total"]:
                    self.after(0, lambda: self._set_status("v129: fase Fontes Especiais — coleta com bypass de score..."))
                    print(f"[v129][ESPECIAIS] {len(fontes_especiais_v129)} fonte(s) especial(is) configurada(s).")
                    for eidx, fonte_esp in enumerate(fontes_especiais_v129, start=1):
                        if resumo_total["inseridas"] >= limites["max_total"]:
                            break
                        if fonte_esp.get("ativo", True) is False:
                            continue
                        nome_esp = fonte_esp.get("nome") or fonte_esp.get("fonte_nome") or fonte_esp.get("url") or f"Especial {eidx}"
                        try:
                            nome_esp_norm_v1304 = str(nome_esp or "").lower()
                            url_esp_norm_v1304 = str(fonte_esp.get("url") or "").lower()
                            # v130.4: NF Notícias é fonte regional prioritária por RSS normal,
                            # não Fonte Especial institucional genérica. Se o usuário a mantiver
                            # por engano em Fontes Especiais, usar o parser RSS normal e auditar como
                            # rss_regional_prioritario_v1304, preservando bypass/cota mínima.
                            if ("nfnoticias.com.br" in url_esp_norm_v1304) or ("nf notícias" in nome_esp_norm_v1304) or ("nf noticias" in nome_esp_norm_v1304) or ("nfnoticias" in nome_esp_norm_v1304):
                                fonte_nf_v1304 = dict(fonte_esp)
                                fonte_nf_v1304["nome"] = "NF Notícias"
                                fonte_nf_v1304["tipo"] = "rss_regional_prioritario_v1304"
                                fonte_nf_v1304["tipo_coleta"] = "rss_regional_prioritario_v1304"
                                fonte_nf_v1304["regional_prioritaria"] = True
                                fonte_nf_v1304["bypass_score"] = True
                                try:
                                    lote_esp = coletar_rss([fonte_nf_v1304], incluir_oficiais=False)
                                except TypeError:
                                    lote_esp = coletar_rss([fonte_nf_v1304])
                                contexto_nf_v1304 = "RSS Regional Prioritário: NF Notícias"
                                inseridas_esp_v129 = self._v94_salvar_lote_progressivo(
                                    lote_esp, resumo_total, contagem_fonte, limites,
                                    contexto_nf_v1304, bypass_score=True
                                )
                            else:
                                try:
                                    lote_esp = coletar_rss([fonte_esp], incluir_oficiais=True)
                                except TypeError:
                                    lote_esp = coletar_rss([fonte_esp])
                                contexto_nf_v1304 = f"Especial: {nome_esp}"
                                inseridas_esp_v129 = self._v94_salvar_lote_progressivo(
                                    lote_esp, resumo_total, contagem_fonte, limites,
                                    contexto_nf_v1304, bypass_score=True
                                )
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=800 + eidx,
                                    nome=nome_esp,
                                    url=fonte_esp.get("url") or "",
                                    tipo=("rss_regional_prioritario_v1304" if ("nfnoticias.com.br" in str(fonte_esp.get("url") or "").lower() or "nf noticias" in str(nome_esp or "").lower() or "nf notícias" in str(nome_esp or "").lower() or "nfnoticias" in str(nome_esp or "").lower()) else "especial_v129"),
                                    encontradas=len(lote_esp or []),
                                    enviadas_fila=inseridas_esp_v129,
                                    observacao=("NF Notícias v130.4: RSS regional prioritário pelo parser normal, livre do corte de score e com cota mínima." if ("nfnoticias.com.br" in str(fonte_esp.get("url") or "").lower() or "nf noticias" in str(nome_esp or "").lower() or "nf notícias" in str(nome_esp or "").lower() or "nfnoticias" in str(nome_esp or "").lower()) else "Fonte Especial v129: livre do corte de score; mantém deduplicação, janela e validação técnica."),
                                    diagnostico=self._v128_diag_lote(contexto_nf_v1304),
                                )
                        except Exception as e:
                            print(f"[v129][ESPECIAIS] falha em {nome_esp}: {e}")
                            if auditoria_v126:
                                auditoria_v126.registrar(
                                    ordem=800 + eidx,
                                    nome=nome_esp,
                                    url=fonte_esp.get("url") or "",
                                    tipo="especial_v129",
                                    encontradas=0,
                                    enviadas_fila=0,
                                    erro=str(e),
                                )
            except Exception as e:
                print(f"[v129][ESPECIAIS] fase ignorada: {e}")

            # v126: fonte especial Campos 24 Horas.
            # Usa RSS real em /portal/feed/ e categorias; sitemap fica como fallback genérico abaixo.
            try:
                usar_campos24_v126 = self._env_bool("URURAU_V126_CAMPOS24_ESPECIAL_ATIVO", "1")
                if usar_campos24_v126 and resumo_total["inseridas"] < limites["max_total"]:
                    from ururau.coleta.fonte_registry_v126 import configs_incluem_campos24_v126
                    if configs_incluem_campos24_v126(fontes):
                        self.after(0, lambda: self._set_status("v126: Campos 24 Horas — RSS /portal/feed/ + categorias..."))
                        from ururau.coleta.adapters.campos24horas_v126 import coletar_campos24horas_v126
                        lote_campos24_v126 = coletar_campos24horas_v126()
                        inseridas_campos24_v126 = self._v94_salvar_lote_progressivo(
                            lote_campos24_v126, resumo_total, contagem_fonte, limites, "Campos 24 Horas"
                        )
                        if auditoria_v126:
                            auditoria_v126.registrar(
                                ordem=900,
                                nome="Campos 24 Horas",
                                url="https://campos24horas.com.br/portal/feed/",
                                tipo="especial_campos24",
                                encontradas=len(lote_campos24_v126 or []),
                                enviadas_fila=inseridas_campos24_v126,
                                observacao="Coletor especial v126 preservado; v128 adicionou contadores por endpoint.",
                                diagnostico={**self._v128_diag_lote("Campos 24 Horas"), "campos24_detalhe": __import__("ururau.coleta.adapters.campos24horas_v126", fromlist=["obter_diagnostico_campos24_v128"]).obter_diagnostico_campos24_v128()},
                            )
            except Exception as e:
                print(f"[CAMPOS24 v126] falha ignorada: {e}")
                if auditoria_v126:
                    auditoria_v126.registrar(
                        ordem=900,
                        nome="Campos 24 Horas",
                        url="https://campos24horas.com.br/portal/feed/",
                        tipo="especial_campos24",
                        encontradas=0,
                        enviadas_fila=0,
                        erro=str(e),
                    )

            # v123: fase XML/Sitemap — usa fontes_xml_sitemap_vfinal.txt, ex.: Campos 24 Horas.
            if resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v123: fase XML/Sitemap — lendo sitemaps configurados..."))
                try:
                    from ururau.coleta.sitemap_xml_coletor_v123 import coletar_sitemaps_configurados_v123
                    lote_xml = coletar_sitemaps_configurados_v123()
                    print(f"[XML/SITEMAP v124] lote integrado ao botão Coletar: {len(lote_xml)} pauta(s) bruta(s)")
                    inseridas_xml_v126 = self._v94_salvar_lote_progressivo(
                        lote_xml, resumo_total, contagem_fonte, limites, "XML/Sitemap"
                    )
                    if auditoria_v126:
                        auditoria_v126.registrar(
                            ordem=901,
                            nome="XML/Sitemap configurado",
                            url="fontes_xml_sitemap_vfinal.txt",
                            tipo="xml_sitemap",
                            encontradas=len(lote_xml or []),
                            enviadas_fila=inseridas_xml_v126,
                            observacao="Sitemaps processados em lote com diagnóstico v128 por sitemap e funil.",
                            diagnostico={**self._v128_diag_lote("XML/Sitemap"), "sitemap_detalhe": __import__("ururau.coleta.sitemap_xml_coletor_v123", fromlist=["obter_diagnostico_sitemap_v128"]).obter_diagnostico_sitemap_v128()},
                        )
                except Exception as e:
                    print(f"[XML/SITEMAP v123] falha ignorada: {e}")
                    if auditoria_v126:
                        auditoria_v126.registrar(
                            ordem=901,
                            nome="XML/Sitemap configurado",
                            url="fontes_xml_sitemap_vfinal.txt",
                            tipo="xml_sitemap",
                            encontradas=0,
                            enviadas_fila=0,
                            erro=str(e),
                        )

            if resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v100: fase 2/5 — fontes oficiais..."))
                try:
                    try:
                        oficiais = coletar_rss([], incluir_oficiais=True)
                    except TypeError:
                        oficiais = []
                    self._v94_salvar_lote_progressivo(oficiais, resumo_total, contagem_fonte, limites, "RSS oficiais")
                except Exception as e:
                    print(f"[v100][RSS-OFICIAL] falha ignorada: {e}")

            # v127: Busca por Termos explícita, após fontes RSS/XML/especiais.
            # Usa Config > Termos, Google News RSS oficial e janela padrão de 24h.
            usar_busca_termos_v127 = self._env_bool("URURAU_V127_BUSCA_TERMOS_ATIVA", "1")
            if usar_busca_termos_v127 and resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v127: fase Termos — buscando termos configurados nas últimas 24h..."))
                try:
                    from ururau.coleta.termos_busca_v127 import coletar_busca_termos_v127
                    lote_termos_v127 = coletar_busca_termos_v127()
                    inseridas_termos_v127 = self._v94_salvar_lote_progressivo(
                        lote_termos_v127, resumo_total, contagem_fonte, limites, "Busca por Termos v127"
                    )
                    if auditoria_v126:
                        auditoria_v126.registrar(
                            ordem=950,
                            nome="Busca por Termos",
                            url="Config > Termos",
                            tipo="termos",
                            encontradas=len(lote_termos_v127 or []),
                            enviadas_fila=inseridas_termos_v127,
                            observacao="Busca por termos via Google News RSS oficial com diagnóstico v128 por termo.",
                            diagnostico={**self._v128_diag_lote("Busca por Termos v127"), "termos_detalhe": __import__("ururau.coleta.termos_busca_v127", fromlist=["obter_diagnostico_termos_v128"]).obter_diagnostico_termos_v128()},
                        )
                except Exception as e:
                    print(f"[TERMOS v127] falha; tentando legado v108: {e}")
                    try:
                        lote_gnews_v108 = coletar_google_news_termos_v108()
                        inseridas_gnews_v108 = self._v94_salvar_lote_progressivo(
                            lote_gnews_v108, resumo_total, contagem_fonte, limites, "GNews Termos legado v109"
                        )
                        if auditoria_v126:
                            auditoria_v126.registrar(
                                ordem=950,
                                nome="Busca por Termos",
                                url="Config > Termos",
                                tipo="termos",
                                encontradas=len(lote_gnews_v108 or []),
                                enviadas_fila=inseridas_gnews_v108,
                                observacao="Fallback legado v108/v109 executado.",
                                diagnostico=self._v128_diag_lote("GNews Termos legado v109"),
                            )
                    except Exception as e2:
                        print(f"[TERMOS v127] fallback legado também falhou: {e2}")
                        if auditoria_v126:
                            auditoria_v126.registrar(
                                ordem=950,
                                nome="Busca por Termos",
                                url="Config > Termos",
                                tipo="termos",
                                encontradas=0,
                                enviadas_fila=0,
                                erro=str(e2),
                            )
            elif not usar_busca_termos_v127:
                print("[TERMOS v127] Busca por termos desligada: URURAU_V127_BUSCA_TERMOS_ATIVA=0")

            usar_gnews = self._env_bool("URURAU_V92_USAR_GNEWS", "0")
            if usar_gnews and resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v100: fase 3/4 — Google News leve..."))
                termos_fb = [
                    "Rio de Janeiro", "RJ polícia", "RJ política", "RJ economia",
                    "governo RJ", "Campos dos Goytacazes", "Norte Fluminense",
                    "Porto do Açu", "ALERJ",
                ]
                termos_gnews = obter_termos_google_news(termos_fb)
                try:
                    termos_radar = obter_termos_radar_audiencia_v88()
                    if termos_radar:
                        termos_gnews = list(dict.fromkeys(list(termos_gnews) + list(termos_radar)))
                except Exception as e:
                    print(f"[v100][RADAR] falha: {e}")
                max_por_termo = self._env_int("URURAU_V92_GNEWS_MAX_POR_TERMO", 2)
                for termo in termos_gnews[:12]:
                    if resumo_total["inseridas"] >= limites["max_total"]:
                        break
                    try:
                        lote = coletar_google_news([termo], max_por_termo=max_por_termo)
                        self._v94_salvar_lote_progressivo(lote, resumo_total, contagem_fonte, limites, f"GNews: {termo}")
                    except Exception as e:
                        print(f"[v100][GNEWS] falha em {termo}: {e}")
            else:
                print("[v100] Google News desligado por padrão; não gera ruído com news.google.com.")

            # v105: Bing News Search API opcional (legal/pago) com sortBy=date/freshness.
            usar_bing = self._env_bool("URURAU_V105_USAR_BING_NEWS", "0")
            if usar_bing and resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v105: fase extra — Bing News Search API..."))
                try:
                    from ururau.coleta.bing_news_v105 import coletar_bing_news_v105
                    try:
                        termos_bing = obter_termos_google_news([
                            "Rio de Janeiro", "Campos dos Goytacazes", "Norte Fluminense", "Alerj"
                        ])
                    except Exception:
                        termos_bing = ["Rio de Janeiro", "Campos dos Goytacazes", "Alerj"]
                    lote_bing = coletar_bing_news_v105(termos_bing[:12], max_por_termo=self._env_int("URURAU_V105_BING_COUNT", 5))
                    self._v94_salvar_lote_progressivo(lote_bing, resumo_total, contagem_fonte, limites, "Bing News v105")
                except Exception as e:
                    print(f"[BING v105] falha ignorada: {e}")
            elif not usar_bing:
                print("[BING v105] Desligado por padrão. Ative URURAU_V105_USAR_BING_NEWS=1 e defina BING_NEWS_API_KEY.")

            # v111.4: Source Hunter Plus operacional no painel.
            # Diferente do Source Hunter pesado antigo, este coleta RSS/feeds alternativos/homepages
            # com cooldown, deduplicação e hidratação, e usa principalmente fontes produtivas.
            usar_plus_hunter = self._env_bool("URURAU_PLUS_SOURCE_HUNTER", "1")
            if usar_plus_hunter and resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v111.4: fase extra — Source Hunter Plus operacional..."))
                try:
                    from ururau.coleta.source_discovery_plus_v112 import coletar_source_hunter_plus_v112_sync
                    lote_plus = coletar_source_hunter_plus_v112_sync(
                        max_fontes=self._env_int("URURAU_PLUS_MAX_FONTES", 100),
                        max_por_fonte=self._env_int("URURAU_PLUS_MAX_POR_FONTE", 8),
                        max_total=self._env_int("URURAU_PLUS_MAX_TOTAL", 100),
                        hidratar=self._env_bool("URURAU_PLUS_HIDRATAR_FONTES", "1"),
                    )
                    self._v94_salvar_lote_progressivo(lote_plus, resumo_total, contagem_fonte, limites, "Source Hunter Plus v111.4")
                except Exception as e:
                    print(f"[v111.4][SOURCE_PLUS] falha ignorada: {e}")

            usar_hunter_lento = self._env_bool("URURAU_V92_SOURCE_HUNTER_LENTO", "0")
            if usar_hunter_lento and resumo_total["inseridas"] < limites["max_total"]:
                self.after(0, lambda: self._set_status("v100: fase 4/4 — Source Hunter pesado..."))
                try:
                    premium = coletar_source_hunter_premium_v88()
                    self._v94_salvar_lote_progressivo(premium, resumo_total, contagem_fonte, limites, "Source Hunter")
                except Exception as e:
                    print(f"[v100][SOURCE_HUNTER] falha ignorada: {e}")
            else:
                print("[v100] Source Hunter pesado desligado por padrão.")

            self.after(0, self._carregar_pautas)
            msg = (
                f"Coleta v110 concluída. "
                f"Brutas: {resumo_total.get('total', 0)} | "
                f"Listadas agora: {resumo_total.get('inseridas', 0)} | "
                f"Já publicadas: {resumo_total.get('publicadas', 0)} | "
                f"Descartadas: {resumo_total.get('descartadas', 0)} | "
                f"Em fila: {resumo_total.get('em_fila', 0)} | "
                f"Similares/Site: {resumo_total.get('similares', 0)} | "
                f"Limite por fonte: {resumo_total.get('ignoradas_fonte', 0)}"
            )
            self.after(0, lambda: self._set_status(f"v110: coleta concluída — {resumo_total.get('inseridas', 0)} pautas listadas"))
            print("[v100][RESUMO]", msg)

            # v127: diagnóstico fica apenas na sessão e aparece em Config > Diagnóstico.
            try:
                if auditoria_v126:
                    diag_v126 = auditoria_v126.resumo_texto()
                    print("[v127][DIAGNOSTICO]\n" + diag_v126)
                    self.after(0, lambda d=diag_v126: self._v126_atualizar_diagnostico_coleta(d))
            except Exception as _e_diag_v126:
                print(f"[v127][DIAGNOSTICO] falha ao atualizar: {_e_diag_v126}")

            if self._env_bool("URURAU_V92_MOSTRAR_POPUP_COLETA", "0"):
                self.after(0, lambda m=msg: messagebox.showinfo("Coleta v100", m))

        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f"Erro na coleta v100: {msg}"))
            self.after(0, lambda msg=msg: messagebox.showerror("Erro na coleta v100", msg))
        finally:
            self._coleta_em_andamento = False
            try:
                self.after(300, lambda: self._carregar_pautas(forcar=True))
            except Exception:
                pass

    # ── Redigir ───────────────────────────────────────────────────────────────

    def _acao_redigir(self):
        if not self._pauta_sel:
            messagebox.showwarning("Redigir", "Selecione uma pauta primeiro."); return
        # fix/auditoria-fila-scrapling-v136: guard oficial do Redigir.
        # Bloqueia: separador, publicada/descartada/bloqueada/reprovada,
        # baixo_score nao aprovado, e item de "lixo editorial" (gols/charge/etc).
        # A validacao de >=550 chars uteis acontece dentro de _redigir_thread,
        # apos rehidratacao explicita; aqui filtramos o que NUNCA deve passar.
        try:
            from ururau.core.source_text_contract import eh_lixo_editorial
            ps = dict(self._pauta_sel or {})
            if ps.get("_separador_coleta_v123") or str(ps.get("status") or "").lower() == "_separador":
                messagebox.showwarning("Redigir", "Item selecionado e um separador visual, nao uma pauta."); return
            st = str(ps.get("status") or "").lower()
            if st in {"publicada","publicado","descartada","descartado","rejeitada","rejeitado",
                      "bloqueada","bloqueado","reprovada","reprovado","excluida","excluido"}:
                messagebox.showwarning("Redigir", f"Pauta esta com status '{st}' e nao pode ser redigida."); return
            if st == "baixo_score" and not (ps.get("aprovada_baixo_score") or ps.get("aprovada")):
                messagebox.showwarning("Redigir",
                    "Esta pauta esta em baixo score e ainda nao foi aprovada. "
                    "Use Aprovar antes de Redigir."); return
            lixo, motivo = eh_lixo_editorial(ps)
            if lixo and motivo not in {"baixo_score", "quarentena"}:
                messagebox.showwarning("Redigir",
                    f"Pauta classificada como lixo editorial ({motivo}). "
                    "Use Aprovar manualmente se quiser forcar o Redigir."); return
        except Exception as _e_guard:
            print(f"[REDIGIR][GUARD][AVISO] guard nao aplicado: {_e_guard}")
        # v46.7: permite fallback local, mas avisa claramente no painel.
        if not self.client:
            aviso = "IA OpenAI indisponível: redigindo por fallback local e marcando diagnóstico."
            print(f"[REDACAO][IA][AVISO] {aviso}")
            try:
                self._set_status(aviso)
                self._append_console(f"[IA][AVISO] {aviso}")
            except Exception:
                pass
        pauta = self._pauta_sel
        link  = pauta.get("link_origem", "")
        uid   = pauta.get("uid") or pauta.get("_uid", "")
        if self.db.pauta_ja_publicada(link, uid):
            messagebox.showerror("Bloqueado", "Esta pauta ja foi publicada."); return
        if self.db.pauta_foi_descartada(link, uid):
            messagebox.showerror("Bloqueado", "Esta pauta foi descartada."); return
        similar = self.db.titulo_similar_ja_publicado(pauta.get("titulo_origem", ""))
        if similar:
            if not messagebox.askyesno("Titulo similar",
                f"Publicado recentemente:\n'{similar[:80]}'\nRedigir mesmo assim?"):
                return
        fonte_aberta = self._obter_texto_aba_fonte_v96()
        if fonte_aberta:
            self._injetar_fonte_longa_v96(pauta, fonte_aberta, origem="aba_fonte_antes_redigir")
        self._set_status(f"Redigindo: {(pauta.get('titulo_origem') or '')[:50]}...")
        self._em_thread(self._redigir_thread, pauta)

    def _redigir_thread(self, pauta: dict):
        try:
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            uid = (pauta.get("uid") or pauta.get("_uid") or
                   _uid_para_pauta(pauta.get("link_origem", ""), pauta.get("titulo_origem", "")))
            pauta["_uid"] = uid
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            if not wf.etapa_gate_antiduplicacao(uid, pauta, modo="redigir"):
                self.after(0, lambda: self._set_status("Pauta bloqueada pelo gate."))
                self.after(0, self._carregar_pautas)
                return
            wf.etapa_coleta_texto(uid, pauta)
            try:
                fonte_atual = pauta.get("cleaned_source_text") or pauta.get("dossie") or pauta.get("texto_fonte") or ""
                if len(str(fonte_atual).strip()) < 1000:
                    from ururau.coleta.leitura_fonte import ler_fonte_pauta
                    res_v96 = ler_fonte_pauta(pauta, forcar_refresh=False)
                    if getattr(res_v96, "sucesso", False) and len((res_v96.texto_limpo or "").strip()) > len(str(fonte_atual)):
                        self._injetar_fonte_longa_v96(pauta, res_v96.texto_limpo, origem="leitura_fonte_antes_redacao")
                        wf.etapa_coleta_texto(uid, pauta)
            except Exception as _e_v96:
                print(f"[v96] hidratação antes da redação falhou: {_e_v96}")
            # v105: não redigir a partir de snippet/RSS. Fonte textual precisa estar OK.
            try:
                ok_fonte_v105, util_fonte_v105, _ = self._v105_texto_fonte_util(pauta)
                if not ok_fonte_v105:
                    res_h = self._v105_hidratar_pauta(pauta, origem="redigir", forcar=True, atualizar_ui=False)
                    ok_fonte_v105, util_fonte_v105, _ = self._v105_texto_fonte_util(pauta)
                if not ok_fonte_v105:
                    self.after(0, lambda u=util_fonte_v105: self._set_status(f"Redação bloqueada: fonte insuficiente ({u} chars úteis)."))
                    self.after(0, lambda: messagebox.showwarning("Fonte insuficiente", "A fonte ainda não entregou texto completo suficiente. A matéria não será gerada por snippet."))
                    return
            except Exception as _e_v105_redigir:
                print(f"[v105][REDIGIR] aviso ao validar fonte: {_e_v105_redigir}")
            wf.etapa_imagem(uid, pauta)
            materia = wf.etapa_redacao(uid, pauta)
            if materia:
                materia = wf.etapa_pacote_editorial(uid, materia)
                wf.etapa_verificacao_risco(uid, pauta, materia)
                wf.etapa_persistir_materia(uid, pauta, materia)
                try:
                    gj_ia = dict(getattr(materia, "generated_article_json", {}) or {})
                    modo_ia = getattr(materia, "modo_geracao", "") or gj_ia.get("modo_geracao") or "sem_telemetria_ia"
                    status_ia = getattr(materia, "ia_status", "") or gj_ia.get("ia_status") or "sem_telemetria_ia"
                    origem_ia = getattr(materia, "ia_texto_final_origem", "") or gj_ia.get("ia_texto_final_origem") or ("openai" if modo_ia == "openai_gpt4mini" else "fallback_local")
                    openai_status = getattr(materia, "ia_openai_status", "") or gj_ia.get("ia_openai_status") or ""
                    extra_openai = f" | OpenAI: {openai_status}" if openai_status and openai_status != status_ia else ""
                    msg_ia = f"Redação concluída | IA: {modo_ia} / {status_ia} | origem={origem_ia}{extra_openai}"
                except Exception:
                    msg_ia = "Redação concluída | IA: sem diagnóstico"
                self.after(0, lambda msg_ia=msg_ia: self._set_status(msg_ia))
                self.after(0, lambda msg_ia=msg_ia: messagebox.showinfo(
                    "Redacao Concluida", f"Materia gerada. {msg_ia}. Use Preview antes de publicar."))
            else:
                self.after(0, lambda: self._set_status("Falha na redacao [XX]"))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f"Erro na redacao: {msg}"))
            self.after(0, lambda msg=msg: messagebox.showerror("Erro na redacao", msg))

    # ── Copydesk ──────────────────────────────────────────────────────────────

    def _acao_copydesk(self):
        """
        v66: Copydesk agora abre JanelaCopydeskItem (revisao item-por-item).
        Substitui o antigo painel "Revisao" e a janela de diff side-by-side.
        Cada campo do pacote editorial e revisado separadamente:
        accept/reject/edit/ok por campo + paragrafo a paragrafo no corpo.
        """
        if not self._pauta_sel:
            messagebox.showwarning("Copydesk", "Selecione uma pauta primeiro.")
            return
        md = _parse_materia(self._pauta_sel)
        fonte_aberta = self._obter_texto_aba_fonte_v96()
        if fonte_aberta:
            self._injetar_fonte_longa_v96(self._pauta_sel, fonte_aberta, origem="aba_fonte_antes_copydesk")
            md = _parse_materia(self._pauta_sel)
        if md:
            fonte_pauta = (self._pauta_sel.get("cleaned_source_text") or self._pauta_sel.get("dossie") or self._pauta_sel.get("texto_fonte") or "")
            fonte_md = (md.get("cleaned_source_text") or md.get("dossie") or md.get("texto_fonte") or "")
            if len(str(fonte_pauta)) > len(str(fonte_md)):
                for _k in ("_fonte_aba_texto", "fonte_aba_texto", "leitura_fonte_texto", "cleaned_source_text", "raw_source_text", "original_source_text", "texto_fonte", "dossie"):
                    if self._pauta_sel.get(_k):
                        md[_k] = self._pauta_sel.get(_k)
                self._pauta_sel["materia"] = md
        if not md or not (md.get("conteudo") or md.get("corpo_materia")):
            messagebox.showwarning(
                "Copydesk",
                "Esta pauta nao tem materia gerada. Use 'Redigir' antes do Copydesk."
            )
            return
        try:
            from ururau.ui.copydesk_painel import JanelaCopydeskItem
        except Exception as e:
            messagebox.showerror("Copydesk indisponivel", str(e))
            return
        try:
            JanelaCopydeskItem(
                self, self._pauta_sel, md,
                db=self.db, client=self.client, modelo=self.modelo,
                on_salvar=self._ao_salvar_copydesk_item,
            )
            self._set_status("Copydesk aberto - revise cada campo e clique 'Salvar mudancas'.")
        except Exception as e:
            messagebox.showerror("Erro ao abrir Copydesk", str(e))

    def _ao_salvar_copydesk_item(self, pauta: dict, md_novo: dict, historico: list):
        """Callback apos JanelaCopydeskItem salvar. Persiste matéria e recarrega painel."""
        try:
            uid = pauta.get("uid") or pauta.get("_uid") or self._pauta_sel.get("uid") or self._pauta_sel.get("_uid")
            if uid:
                md_novo.setdefault("status", "rascunho")
                self.db.salvar_materia(uid, md_novo)
                pauta["materia"] = md_novo
                pauta["_uid"] = uid
                pauta["status"] = "revisada"
                self.db.salvar_pauta(pauta)
                self._set_status(f"Copydesk salvo no banco: {len(historico)} alteracao(oes).")
            else:
                self._set_status(f"Copydesk salvo apenas em memória: {len(historico)} alteracao(oes).")
        except Exception as e:
            messagebox.showerror("Erro ao salvar Copydesk", str(e))
            return
        self._carregar_pautas()

    # legacy - mantem caminho antigo (diff) acessivel via _acao_copydesk_legacy
    def _acao_copydesk_legacy(self):
        if not self._pauta_sel:
            messagebox.showwarning("Copydesk", "Selecione uma pauta primeiro.")
            return
        if not self.client:
            messagebox.showerror("Erro", "Cliente OpenAI nao configurado.")
            return
        md = _parse_materia(self._pauta_sel)
        if not md or not md.get("conteudo"):
            messagebox.showwarning("Copydesk", "Esta pauta nao tem materia gerada.")
            return
        self._set_status("Executando copydesk com IA (aguarde)...")
        self._em_thread(self._copydesk_thread, self._pauta_sel)

    def _copydesk_thread(self, pauta: dict):
        """Roda pipeline_copydesk em background, depois abre JanelaCopydesk no main thread."""
        try:
            from ururau.editorial.copydesk import pipeline_copydesk, detectar_problemas, limpar_local
            md_orig = dict(_parse_materia(pauta))
            canal   = pauta.get("canal_forcado") or pauta.get("canal", "Brasil e Mundo")
            mapa    = md_orig.get("mapa_evidencias")
            # Cria uma cópia para o pipeline não alterar o original
            md_copia = dict(md_orig)
            rev, probs = pipeline_copydesk(md_copia, canal, mapa, self.client, self.modelo)
            def _abrir():
                self._set_status("Copydesk pronto — revisando proposta...")
                JanelaCopydesk(self, pauta, md_orig, rev, probs, self.db,
                               self._ao_aceitar_copydesk)
            self.after(0, _abrir)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f"Erro no copydesk: {msg}"))
            self.after(0, lambda msg=msg: messagebox.showerror("Erro no Copydesk", msg))

    def _ao_aceitar_copydesk(self, pauta: dict, md_rev: dict, probs: list):
        """Callback chamado quando o editor aceita (total ou parcialmente) o copydesk."""
        uid = pauta.get("uid") or pauta.get("_uid", "")
        if uid:
            self.db.salvar_materia(uid, md_rev)
            self.db.log_auditoria(uid, "copydesk_visual", f"{len(probs)} prob(s) residuais")
        self._set_status(f"Copydesk aplicado [OK] — {len(probs)} problema(s) residual(is)")
        self._carregar_pautas()

    # ── Monitor 24h ───────────────────────────────────────────────────────────

    def _toggle_monitor(self):
        """Navega para a aba Monitor integrada ao painel."""
        # Encontra o índice da aba Monitor e seleciona
        nb = self._notebook
        for idx in range(nb.index("end")):
            if "Monitor" in nb.tab(idx, "text"):
                nb.select(idx)
                break

    def _cb_monitor_atualizado(self, robo, thread):
        """Chamado pela AbaMonitor quando o robô é iniciado ou parado."""
        self._monitor_robo   = robo
        self._monitor_thread = thread
        self._atualizar_btn_monitor()
        if robo and robo.ativo:
            self._monitor_status_tick()

    def _atualizar_btn_monitor(self):
        ativo = bool(self._monitor_robo and self._monitor_robo.ativo)
        if ativo:
            n = self._monitor_robo.publicacoes_na_hora
            self._btn_monitor.config(
                text=f"Monitor ON ({n}/h)",
                bg="#065f46", fg="#34d399")
        else:
            self._btn_monitor.config(
                text="Monitor OFF",
                bg="#374151", fg="#9ca3af")

    def _monitor_status_tick(self):
        """Atualiza botão a cada 60s enquanto monitor ativo."""
        if not (self._monitor_robo and self._monitor_robo.ativo):
            return
        self._atualizar_btn_monitor()
        self.after(60_000, self._monitor_status_tick)

    # ── Preview ───────────────────────────────────────────────────────────────

    def _acao_preview(self):
        if not self._pauta_sel:
            messagebox.showwarning("Preview", "Selecione uma pauta primeiro."); return
        md = _parse_materia(self._pauta_sel)
        if not md or not md.get("conteudo"):
            messagebox.showwarning("Preview", "Sem materia gerada. Use Redigir primeiro."); return
        self._abrir_preview_inline(self._pauta_sel, md)

    def _ao_salvar_preview(self, pauta: dict, md: dict):
        uid = pauta.get("uid") or pauta.get("_uid", "")
        if uid:
            self.db.salvar_materia(uid, md)
            self.db.log_auditoria(uid, "edicao_manual_preview", "Conteudo editado via preview")
            # Atualiza o dict da pauta em memória para que _publicar_thread use o md salvo
            pauta["materia"] = md
            # Atualiza também em _pautas_cache
            for p in self._pautas_cache:
                if (p.get("uid") or p.get("_uid")) == uid:
                    p["materia"] = md
                    break
            self._set_status("Materia atualizada via preview [OK]")
            self.after(0, self._carregar_pautas)

    def _acao_preview_direto(self, pauta: dict):
        """Abre preview diretamente de um item clicado na fila (botão ✓ Ver Matéria)."""
        md = _parse_materia(pauta)
        if not md or not md.get("conteudo"):
            messagebox.showwarning("Preview", "Sem matéria gerada. Use 'Gerar' primeiro.")
            return
        self._abrir_preview_inline(pauta, md)

    def _acao_gerar_item(self, pauta: dict):
        """Dispara redação de um item clicado na fila (botão ▶ Gerar)."""
        self._pauta_sel = pauta
        self._acao_redigir()

    # ── Imagem ────────────────────────────────────────────────────────────────

    def _acao_buscar_imagem(self):
        if not self._pauta_sel:
            messagebox.showwarning("Imagem", "Selecione uma pauta primeiro."); return
        pauta = self._pauta_sel
        if not messagebox.askyesno("Buscar Imagem",
            f"{(pauta.get('titulo_origem') or '')[:60]}\n\n"
            f"Imagem atual: {pauta.get('imagem_status', 'pendente')}\n"
            "Refazer busca de imagem?"):
            return
        self._set_status("Buscando imagem...")
        self._em_thread(self._buscar_imagem_thread, pauta)

    def _buscar_imagem_thread(self, pauta: dict):
        try:
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            uid = (pauta.get("uid") or pauta.get("_uid") or
                   _uid_para_pauta(pauta.get("link_origem", ""), pauta.get("titulo_origem", "")))
            pauta["_uid"] = uid
            wf  = WorkflowPublicacao(self.db, self.client, self.modelo)
            res = wf.etapa_imagem(uid, pauta)
            if res and res.caminho_imagem:
                msg = f"Imagem obtida!\nEstrategia: {res.estrategia_imagem}\nArquivo: {Path(res.caminho_imagem).name}"
                self.after(0, lambda: messagebox.showinfo("Imagem", msg))
                self.after(0, lambda: self._set_status("Imagem atualizada [OK]"))
            else:
                self.after(0, lambda: messagebox.showwarning("Imagem", "Nao foi possivel obter imagem."))
                self.after(0, lambda: self._set_status("Sem imagem"))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f"Erro na imagem: {msg}"))
            self.after(0, lambda msg=msg: messagebox.showerror("Erro na Imagem", msg))

    # ── Publicar ──────────────────────────────────────────────────────────────

    def _acao_publicar(self, rascunho: bool = True):
        if not self._pauta_sel:
            messagebox.showwarning("Publicar", "Selecione uma pauta primeiro."); return
        pauta = self._pauta_sel
        link  = pauta.get("link_origem", "")
        uid   = pauta.get("uid") or pauta.get("_uid", "")
        if self.db.pauta_ja_publicada(link, uid):
            messagebox.showerror("Bloqueado", "Esta pauta ja foi publicada no CMS."); return

        md = _parse_materia(pauta)
        if not md or not md.get("conteudo"):
            messagebox.showerror("Sem Materia", "Nao tem materia gerada. Use Redigir primeiro."); return

        env_cms = _ler_env_cms_com_fallback()
        if not (env_cms.get("URURAU_LOGIN", "").strip() and env_cms.get("URURAU_SENHA", "").strip()):
            messagebox.showerror(
                "Credenciais do CMS",
                "As credenciais do CMS nao foram encontradas.\n\n"
                "Preencha URURAU_LOGIN e URURAU_SENHA em Config > Credenciais.\n"
                "O sistema agora le credenciais por caminho absoluto em sistema/.env e sistema/credenciais/env_principal.env."
            )
            try:
                self._abrir_config_inline()
            except Exception:
                pass
            return

        # ── Gate can_publish(): verifica se o artigo pode ser publicado ───────
        # Esta verificação é obrigatória em TODOS os caminhos de publicação.
        # Sem ela, artigos reprovados pela auditoria editorial poderiam ser publicados.
        from ururau.publisher.workflow import can_publish as _gate
        artigo_gate = {**pauta, **md}
        ok_pub, motivo_pub = _gate(artigo_gate)
        publicacao_forcada = False
        if not ok_pub:
            # Artigo não aprovado — permite aprovação manual explícita pelo editor no Preview.
            if not messagebox.askyesno(
                "Publicação bloqueada — can_publish() = False",
                f"⚠ Este artigo NÃO passou no gate editorial:\n\n"
                f"{motivo_pub}\n\n"
                f"Deseja forçar o envio assim mesmo?\n"
                f"(Só faça isso se você aprovou manualmente.)"
            ):
                return
            publicacao_forcada = True
            # Registra que o editor forçou a publicação
            self.db.log_auditoria(uid, "publicacao_forcada",
                                  f"can_publish=False | {motivo_pub[:80]}")

        # v85: se o editor escolheu Publicar no Preview, marca aprovação manual
        # para o workflow não bloquear antes de chamar o CMS.
        if not rascunho:
            publicacao_forcada = True
            agora = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            md["approved_by"] = "editor_preview"
            md["approved_at"] = agora
            md["manual_approval_reason"] = "Editor selecionou modo Publicar no Preview do painel Ururau."
            md["forcar_publicacao_manual"] = True
            md["aprovacao_manual_editor"] = True
            pauta["forcar_publicacao_manual"] = True
            pauta["aprovacao_manual_editor"] = True

        img_st = pauta.get("imagem_status", "pendente")
        if img_st != "aprovada":
            if not messagebox.askyesno("Imagem nao aprovada",
                f"Imagem com status '{img_st}'.\nEnviar mesmo assim?"):
                return
        sc = pauta.get("score_risco", 0) or 0
        if sc >= LIMIAR_RISCO_MAXIMO:
            if not messagebox.askyesno("Risco Alto",
                f"Score de risco {sc}/100 (limite {LIMIAR_RISCO_MAXIMO}).\nEnviar mesmo assim?"):
                return

        modo_txt = "como RASCUNHO (não publica ao vivo)" if rascunho else "DIRETAMENTE (publicara ao vivo!)"
        if not messagebox.askyesno("Confirmar",
            f"Enviar {modo_txt}:\n'{(pauta.get('titulo_origem') or '')[:70]}'\n"
            f"Canal: {pauta.get('canal_forcado') or pauta.get('canal', '')} | Risco: {sc}/100"):
            return
        self._set_status("Enviando para o CMS...")
        self._em_thread(self._publicar_thread, pauta, md, rascunho)

    def _publicar_thread(self, pauta: dict, md: dict, rascunho: bool = True):
        """Envia ao CMS — chama etapa_publicacao() com controle de rascunho."""
        try:
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            from ururau.core.models import Materia, ImagemDados
            uid = (pauta.get("uid") or pauta.get("_uid") or
                   _uid_para_pauta(pauta.get("link_origem", ""), pauta.get("titulo_origem", "")))
            pauta["_uid"] = uid
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            if not wf.etapa_gate_antiduplicacao(uid, pauta, modo="publicar"):
                self.after(0, lambda: messagebox.showerror("Bloqueado", "Ja publicada no CMS."))
                return
            # Garante link_origem e fonte_nome no md antes de construir Materia
            if not md.get("link_origem"):
                md["link_origem"] = pauta.get("link_origem", "")
            if not md.get("fonte_nome"):
                md["fonte_nome"] = pauta.get("fonte_nome", "")
            canal_pauta = pauta.get("canal_forcado") or pauta.get("canal", "Brasil e Mundo")
            if not md.get("canal"):
                md["canal"] = canal_pauta
            # Reconstrói objeto Materia
            try:
                materia = Materia.from_dict(md)
                # Sobrescreve campos críticos com valores da pauta (fallback robusto)
                if not materia.link_origem:
                    materia.link_origem = pauta.get("link_origem", "")
                if not materia.fonte_nome:
                    materia.fonte_nome = pauta.get("fonte_nome", "")
                if not materia.canal:
                    materia.canal = canal_pauta
            except Exception:
                materia = Materia(
                    titulo=md.get("titulo", ""),
                    titulo_capa=md.get("titulo_capa", ""),
                    subtitulo=md.get("subtitulo", ""),
                    legenda=md.get("legenda", ""),
                    retranca=md.get("retranca", ""),
                    conteudo=md.get("conteudo", ""),
                    slug=md.get("slug", ""),
                    tags=md.get("tags", ""),
                    meta_description=md.get("meta_description", ""),
                    canal=canal_pauta,
                    score_risco=pauta.get("score_risco", 0) or 0,
                    resumo_curto=md.get("resumo_curto", ""),
                    chamada_social=md.get("chamada_social", ""),
                    link_origem=pauta.get("link_origem", ""),
                    fonte_nome=pauta.get("fonte_nome", ""),
                )
            # v85: preserva aprovação manual do Preview no objeto Materia.
            try:
                if md.get("forcar_publicacao_manual") or pauta.get("forcar_publicacao_manual"):
                    materia.approved_by = md.get("approved_by") or "editor_preview"
                    materia.approved_at = md.get("approved_at") or __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    materia.manual_approval_reason = md.get("manual_approval_reason") or "Editor aprovou manualmente no Preview."
                    materia.status_validacao = "aprovado"
                    materia.auditoria_bloqueada = False
                    materia.status_publicacao_sugerido = "publicar_direto" if not rascunho else "salvar_rascunho"
                    materia.status_pipeline = "publicar_direto" if not rascunho else "salvar_rascunho"
                    setattr(materia, "forcar_publicacao_manual", True)
                    setattr(materia, "aprovacao_manual_editor", True)
            except Exception:
                pass

            # Reconstrói imagem
            imagem = None
            if pauta.get("imagem_caminho"):
                try:
                    imagem = ImagemDados(
                        caminho_imagem=pauta.get("imagem_caminho", ""),
                        url_imagem=pauta.get("imagem_url", ""),
                        credito_foto=pauta.get("imagem_credito", ""),
                        estrategia_imagem=pauta.get("imagem_estrategia", ""),
                    )
                except Exception:
                    pass
            sucesso = wf.etapa_publicacao(uid, pauta, materia, imagem, rascunho=rascunho)
            if sucesso:
                modo = "Rascunho salvo no CMS!" if rascunho else "Materia publicada ao vivo!"
                self.after(0, lambda: self._set_status(f"{'Rascunho salvo' if rascunho else 'Publicado'} [OK]"))
                self.after(0, lambda: messagebox.showinfo(
                    "Rascunho Salvo" if rascunho else "Publicado", modo))
            else:
                detalhe = ""
                try:
                    r = getattr(wf, "ultimo_resultado_cms", None) or {}
                    detalhe = r.get("mensagem") or r.get("erro") or ""
                    if r.get("screenshot"):
                        detalhe += f"\nScreenshot: {r.get('screenshot')}"
                    if r.get("html_debug"):
                        detalhe += f"\nHTML: {r.get('html_debug')}"
                except Exception:
                    detalhe = ""
                if not detalhe:
                    detalhe = "O workflow bloqueou antes do CMS ou o CMS não confirmou o cadastro. Veja logs/prints."
                self.after(0, lambda: self._set_status("Falha no envio ao CMS"))
                self.after(0, lambda detalhe=detalhe: messagebox.showerror("Falha no CMS",
                    "Nao foi possivel enviar ao CMS.\n\n" + detalhe))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f"Erro no envio: {msg}"))
            self.after(0, lambda msg=msg: messagebox.showerror("Erro", msg))

    # ── Revisão editorial ─────────────────────────────────────────────────────
    # v66: O painel de Revisão (ui/revisao.py) foi REMOVIDO da toolbar.
    # A revisao agora acontece de duas formas:
    #   1. Preview (botao Preview na toolbar) - editor ve o resultado pronto
    #      e edita inline antes de "Enviar ao CMS" / "Publicar!".
    #   2. Copydesk (botao Copydesk na toolbar / Ctrl+K / Ctrl+R) - revisao
    #      item-a-item com sugestoes de IA, accept/reject/edit por campo e por
    #      paragrafo do corpo.
    # Este metodo continua existindo para nao quebrar codigo legado mas redireciona
    # ao Copydesk, que e a ferramenta correta de revisao item-por-item.

    def _acao_revisao(self):
        """v66: redireciona para Copydesk (revisao item-por-item com IA)."""
        try:
            self._set_status("Painel 'Revisao' foi substituido pelo Copydesk (v66).")
        except Exception:
            pass
        return self._acao_copydesk()

    def _ao_selecionar_revisao(self, pauta: dict):
        """
        Callback quando o usuário clica "Abrir revisão" em um item do PainelRevisao.
        Popula o painel de detalhes à direita e adiciona ações de revisão na aba Auditoria.
        """
        from ururau.ui.revisao import (
            _parse_materia as _rpm, montar_texto_erros,
            _can_publish_artigo, _status_validacao_da_materia,
        )
        self._pauta_sel = pauta
        self._set_status(f"Revisão: {(pauta.get('titulo_origem') or '')[:60]}")

        # Mostra detalhes normais nas abas existentes
        self._ao_trocar_aba()

        # Sobrescreve a aba Auditoria com visão de erros agrupados por categoria
        md = _rpm(pauta)
        txt_erros = montar_texto_erros(md)

        def _atualizar_aba_auditoria():
            # Adiciona header de revisão e erros agrupados
            uid = pauta.get("uid") or pauta.get("_uid", "")
            try:
                conn = self.db._conectar()
                try:
                    rows = conn.execute(
                        "SELECT timestamp, acao, detalhe, sucesso "
                        "FROM auditoria WHERE pauta_uid=? ORDER BY id ASC",
                        (uid,)).fetchall()
                finally:
                    conn.close()
                linhas_aud = [f"[{r['timestamp']}] {'[OK]' if r['sucesso'] else '[XX]'} "
                              f"{r['acao']:<26} {r['detalhe']}" for r in rows]
            except Exception:
                linhas_aud = []

            conteudo = (
                "╔══════════════════════════════════════════════════════╗\n"
                "║          REVISÃO EDITORIAL — ERROS AGRUPADOS         ║\n"
                "╚══════════════════════════════════════════════════════╝\n\n"
                + txt_erros
                + "\n\n" + "═" * 56 + "\n"
                + "HISTÓRICO DE AUDITORIA\n"
                + "═" * 56 + "\n"
                + ("\n".join(linhas_aud) if linhas_aud else "(sem registros)")
            )
            self._escrever(self._aba_auditoria, conteudo)

            # Adiciona botões de ação na aba Auditoria (ou statusbar)
            self._mostrar_acoes_revisao(pauta)

        self.after(0, _atualizar_aba_auditoria)

    def _mostrar_acoes_revisao(self, pauta: dict):
        """
        Exibe uma faixa de ações de revisão no painel de detalhes.
        Aparece abaixo do título da matéria, acima das abas.
        As ações são removidas quando o usuário volta para a fila normal.
        """
        from ururau.ui.revisao import (
            _parse_materia as _rpm, _can_publish_artigo,
            PainelRevisao as _PR,
        )

        # Remove faixa anterior se existir
        if hasattr(self, "_faixa_revisao") and self._faixa_revisao:
            try:
                self._faixa_revisao.destroy()
            except Exception:
                pass

        md = _rpm(pauta) or {}
        ok_pub, motivo_pub = _can_publish_artigo(pauta, md)

        # Cria um PainelRevisao headless para acesso às ações
        # v63 fix: armazena self (PainelUrurau, que é tk.Tk) como _parent
        # para que _get_parent() retorne um Tk widget válido em messagebox/Toplevel.
        _pr = _PR.__new__(_PR)
        _pr.db = self.db
        _pr.client = self.client
        _pr.modelo = self.modelo
        _pr._parent = self

        # Frame de ações (insere entre o título e o notebook)
        faixa = tk.Frame(self._frame_detalhe, bg="#0d0d20", pady=3)
        self._faixa_revisao = faixa

        # Insere a faixa ANTES do notebook (repack)
        faixa.pack(fill="x", before=self._notebook, padx=8)

        tk.Label(faixa, text="⚙ Ações de Revisão:", bg="#0d0d20",
                 fg=COR_AMARELO, font=FONTE_PEQUENA).pack(side="left", padx=6)

        def _corrigir():
            _pr.corrigir_pendencias(pauta, callback_ok=lambda: self._ao_selecionar_revisao(pauta))
        tk.Button(faixa, text="🔧 Corrigir pendências", command=_corrigir,
                  bg="#1e3a5f", fg=COR_CIANO, relief="flat",
                  font=FONTE_PEQUENA, padx=6, pady=2, cursor="hand2"
                  ).pack(side="left", padx=2)

        def _editar():
            _pr.abrir_edicao(pauta, callback_salvo=lambda: self._ao_selecionar_revisao(pauta))
        tk.Button(faixa, text="✏ Editar", command=_editar,
                  bg="#1e3a5f", fg=COR_AZUL, relief="flat",
                  font=FONTE_PEQUENA, padx=6, pady=2, cursor="hand2"
                  ).pack(side="left", padx=2)

        # Publicar — desabilitado se not can_publish
        pub_cor   = COR_VERDE if ok_pub else COR_CINZA
        pub_state = "normal" if ok_pub else "disabled"
        pub_tip   = "" if ok_pub else motivo_pub[:60]

        def _publicar():
            _pr.publicar_revisao(pauta, on_publicar=lambda p: self._acao_publicar())
        btn_pub = tk.Button(faixa, text="🚀 Publicar", command=_publicar,
                            bg="#0d2a1a" if ok_pub else "#1a1a2e",
                            fg=pub_cor, relief="flat",
                            font=FONTE_PEQUENA, padx=6, pady=2,
                            cursor="hand2" if ok_pub else "arrow",
                            state=pub_state)
        btn_pub.pack(side="left", padx=2)
        if not ok_pub and pub_tip:
            # Tooltip simples
            _tip = tk.Label(faixa, text=f"⚠ {pub_tip}", bg="#0d0d20",
                            fg=COR_VERMELHO, font=FONTE_PEQUENA, wraplength=280)
            _tip.pack(side="left", padx=4)

        # Menu "Mais" com ações secundárias
        def _mais():
            menu = tk.Menu(self, tearoff=0, bg=COR_PAINEL, fg=COR_TEXTO,
                           activebackground=COR_DESTAQUE, activeforeground="white")

            def _revisar_ia():
                _pr.revisar_com_ia(pauta, callback_ok=lambda: self._ao_selecionar_revisao(pauta))
            menu.add_command(label="🤖 Revisar com IA", command=_revisar_ia)

            def _aprovar_manual():
                _pr.aprovar_manualmente(pauta, callback_ok=lambda: self._ao_selecionar_revisao(pauta))
            menu.add_command(label="✔ Aprovar manualmente", command=_aprovar_manual)

            menu.add_separator()

            def _comparar_fonte():
                self._notebook.select(self._idx_aba_leitura)
            menu.add_command(label="📄 Comparar com fonte", command=_comparar_fonte)

            def _manter_rascunho():
                uid = pauta.get("uid") or pauta.get("_uid","")
                if uid:
                    self.db.log_auditoria(uid, "manter_rascunho", "Editor manteve como rascunho")
                messagebox.showinfo("Rascunho", "Matéria mantida como rascunho.", parent=self)
            menu.add_command(label="📌 Manter como rascunho", command=_manter_rascunho)

            def _adicionar_manual():
                self._acao_manual()
            menu.add_separator()
            menu.add_command(label="➕ Adicionar pauta manual", command=_adicionar_manual)

            menu.tk_popup(faixa.winfo_rootx(), faixa.winfo_rooty() + faixa.winfo_height())

        tk.Button(faixa, text="Mais ▾", command=_mais,
                  bg="#1e293b", fg=COR_CINZA, relief="flat",
                  font=FONTE_PEQUENA, padx=6, pady=2, cursor="hand2"
                  ).pack(side="right", padx=4)

    # ── Manual (preservado — acessível via Ctrl+M e menu Mais) ────────────────

    def _acao_manual(self):
        dlg = tk.Toplevel(self)
        dlg.title("Adicionar Pauta Manual")
        dlg.geometry("580x470")
        dlg.configure(bg=COR_FUNDO)
        dlg.grab_set()
        dlg.resizable(False, False)
        campos = {}
        for label, key, multi in [("Titulo *","titulo",False),("Link *","link",False),
                                   ("Fonte","fonte",False),("Resumo","resumo",True)]:
            tk.Label(dlg, text=label, bg=COR_FUNDO, fg=COR_TEXTO,
                     font=FONTE_NORMAL).pack(anchor="w", padx=16, pady=4)
            w = (tk.Text(dlg, height=4, bg=COR_PAINEL, fg=COR_TEXTO,
                         font=FONTE_MONO, insertbackground=COR_TEXTO) if multi
                 else tk.Entry(dlg, bg=COR_PAINEL, fg=COR_TEXTO,
                               font=FONTE_MONO, insertbackground=COR_TEXTO))
            w.pack(fill="x", padx=16)
            campos[key] = w
        tk.Label(dlg, text="Canal", bg=COR_FUNDO, fg=COR_TEXTO,
                 font=FONTE_NORMAL).pack(anchor="w", padx=16, pady=4)
        cb_c = ttk.Combobox(dlg, values=CANAIS_RODIZIO, font=FONTE_MONO,
                            state="normal", width=30)
        cb_c.pack(fill="x", padx=16)
        campos["canal"] = cb_c
        lbl_av = tk.Label(dlg, text="", bg=COR_FUNDO, fg=COR_AMARELO,
                          font=FONTE_PEQUENA, wraplength=520)
        lbl_av.pack(padx=16, pady=4)
        def check_link(_=None):
            lk = campos["link"].get().strip()
            if lk:
                s = self.db.classificar_pauta(lk)
                lbl_av.config(text=f"[AVIS] URL ja existe: {s}" if s != "nova" else "[OK] URL nova")
        campos["link"].bind("<FocusOut>", check_link)
        def salvar():
            from ururau.publisher.workflow import _uid_para_pauta
            titulo = campos["titulo"].get().strip()
            link   = campos["link"].get().strip()
            if not titulo or not link:
                messagebox.showerror("Erro", "Titulo e link sao obrigatorios.", parent=dlg); return
            if self.db.pauta_ja_publicada(link):
                messagebox.showerror("Ja publicada", "Link ja publicado.", parent=dlg); return
            uid = _uid_para_pauta(link, titulo)
            self.db.salvar_pauta({
                "_uid": uid, "titulo_origem": titulo, "link_origem": link,
                "fonte_nome": campos["fonte"].get().strip() or "Manual",
                "canal_forcado": cb_c.get().strip(),
                "resumo_origem": campos["resumo"].get("1.0","end").strip(),
                "status": 'captada', "score_editorial": 50,
                "imagem_status": "pendente",
            })
            self.db.log_auditoria(uid, "pauta_manual", titulo[:80])
            dlg.destroy()
            self._carregar_pautas()
            self._set_status("Pauta manual adicionada [OK]")
        tk.Button(dlg, text="Salvar Pauta", command=salvar, bg=COR_VERDE,
                  fg="white", font=FONTE_TITULO, relief="flat",
                  padx=14, pady=6, cursor="hand2").pack(pady=12)

    # ── Descartar ─────────────────────────────────────────────────────────────

    def _acao_descartar(self):
        """Descarte com diálogo de motivo (botão Descartar na toolbar / Ctrl+D)."""
        if not self._pauta_sel:
            messagebox.showwarning("Descartar", "Selecione uma pauta primeiro."); return
        p   = self._pauta_sel
        uid = p.get("uid") or p.get("_uid", "")
        if not uid:
            messagebox.showerror("Erro", "UID nao encontrado."); return
        motivo = simpledialog.askstring("Descartar",
            f"Motivo (opcional):\n'{(p.get('titulo_origem') or '')[:70]}'", parent=self)
        if motivo is None:
            return
        self.db.marcar_descartada(uid, motivo or "Descarte manual", pauta=p)
        self._set_status(f"Descartada: {(p.get('titulo_origem') or '')[:40]}")
        self._carregar_pautas()

    def _descartar_rapido(self, pauta: dict, idx: int = -1):
        """
        Descarte rápido via tecla Delete na fila.

        Dupla garantia: além de atualizar status no banco, registra o link
        em 'links_bloqueados' para que NUNCA volte em coletas futuras,
        mesmo que a pauta não tivesse sido formalmente salva no banco antes.
        """
        uid   = pauta.get("uid") or pauta.get("_uid", "")
        titulo = _titulo_visual_v129_1(pauta)[:80]
        link   = pauta.get("link_origem", "")

        # Gera uid a partir do link se não existir (pauta recém-coletada sem salvar)
        if not uid and link:
            import hashlib
            uid = hashlib.md5(f"{link}{titulo}".encode()).hexdigest()[:16]
            pauta["_uid"] = uid

        ok = messagebox.askyesno(
            "Descartar pauta",
            f"Descartar esta pauta?\n\n«{titulo}»\n\n"
            "Ela não voltará a ser captada.",
            default="yes",
            parent=self,
        )
        if not ok:
            self._fila.focar()
            return

        # Persistência DUPLA: tabela pautas + links_bloqueados
        self.db.marcar_descartada(uid, "Descarte rápido (Del)", pauta=pauta)
        self._set_status(f"Descartada: {titulo[:50]}")

        # Remove da cache local para atualização imediata sem recarregar tudo
        self._pautas_cache = [p for p in self._pautas_cache
                              if (p.get("uid") or p.get("_uid")) != uid]
        self._aplicar_filtro()   # repopula a fila com o item removido

        # Seleciona o próximo item no mesmo índice (ou o anterior se era o último)
        itens_visiveis = self._fila._itens
        if itens_visiveis:
            novo_idx = min(idx, len(itens_visiveis) - 1)
            self._fila._selecionar(novo_idx)
            self._fila._scroll_para_visivel(novo_idx)
        self._fila.focar()

    def _descartar_via_tecla(self):
        """
        Delete global: só aciona o descarte rápido se o foco não estiver em
        um campo de texto (Entry, Text, ScrolledText, Combobox) para não
        interferir com edição normal.
        """
        widget_foco = self.focus_get()
        if widget_foco is None:
            return
        # Não aciona em campos de texto/edição
        ignorar = (tk.Entry, tk.Text, scrolledtext.ScrolledText, ttk.Combobox)
        if isinstance(widget_foco, ignorar):
            return
        # Delega ao descarte rápido se há pauta selecionada
        if self._pauta_sel:
            idx = self._fila._sel_idx or 0
            self._descartar_rapido(self._pauta_sel, idx)

    # ── Exclusão em lote ──────────────────────────────────────────────────────

    def _ao_mudar_selecao(self, qtd: int):
        """Callback da FilaPautas: atualiza botão de exclusão selecionadas."""
        if qtd > 0:
            self._btn_excluir_sel.config(
                text=f"🗑 Excluir Selecionadas ({qtd})",
                state="normal", bg="#7f0000", fg="#fca5a5"
            )
        else:
            self._btn_excluir_sel.config(
                text="🗑 Excluir Selecionadas (0)",
                state="disabled", bg="#4b0505", fg="#fca5a5"
            )

    def _selecionar_todos(self):
        """Marca todos os itens visíveis na fila com checkbox."""
        self._fila.selecionar_todos_visiveis()

    def _limpar_selecao(self):
        """Desmarca todos os checkboxes."""
        self._fila.limpar_selecao()

    def _acao_excluir_selecionadas(self):
        """Exclui todas as pautas marcadas com checkbox."""
        uids = self._fila.get_uids_selecionados()
        if not uids:
            return
        ok = messagebox.askyesno(
            "Excluir pautas selecionadas",
            f"Excluir {len(uids)} pauta(s) selecionada(s)?\n\n"
            "Elas ficarão ocultas na fila normal e não serão recaptadas.\n"
            "Você pode ver e recuperar excluídas pelo filtro '── excluídas ──' no Status.",
            parent=self,
        )
        if not ok:
            return
        # Monta lista (uid, link, titulo) a partir do cache
        uid_set = set(uids)
        uid_map = {p.get("uid") or p.get("_uid", ""): p for p in self._pautas_cache}
        lote = []
        for uid in uids:
            p = uid_map.get(uid, {})
            lote.append((uid, p.get("link_origem", ""), (p.get("titulo_origem") or "")[:200]))

        # Persiste no banco
        self.db.excluir_pautas_em_lote(lote)

        # Remove imediatamente do cache local — sem precisar de F5
        self._pautas_cache = [
            p for p in self._pautas_cache
            if (p.get("uid") or p.get("_uid", "")) not in uid_set
        ]
        self._fila.limpar_selecao()
        self._aplicar_filtro()
        n = len(uids)
        self._set_status(f"✓ {n} pauta(s) excluída(s). Use filtro '── excluídas ──' para recuperar.")

    def _acao_excluir_tudo(self):
        """Exclui todas as pautas atualmente visíveis na fila filtrada."""
        itens = list(self._fila._itens)   # cópia antes de limpar
        if not itens:
            messagebox.showinfo("Excluir tudo", "A fila está vazia.", parent=self)
            return
        filtro = self._filtro_var.get()
        ok = messagebox.askyesno(
            "Excluir TUDO visível",
            f"Excluir as {len(itens)} pauta(s) atualmente visíveis na fila?\n\n"
            f"Filtro atual: «{filtro}»\n"
            "Elas ficarão ocultas e não serão recaptadas.\n"
            "Você pode recuperá-las pelo filtro '── excluídas ──'.",
            parent=self,
        )
        if not ok:
            return
        lote = [
            (p.get("uid") or p.get("_uid", ""),
             p.get("link_origem", ""),
             (p.get("titulo_origem") or "")[:200])
            for p in itens
        ]
        uid_excluidos = {t[0] for t in lote}

        # Persiste no banco
        self.db.excluir_pautas_em_lote(lote)

        # Remove imediatamente do cache local
        self._pautas_cache = [
            p for p in self._pautas_cache
            if (p.get("uid") or p.get("_uid", "")) not in uid_excluidos
        ]
        self._aplicar_filtro()
        self._set_status(f"✓ {len(lote)} pauta(s) excluída(s). Use filtro '── excluídas ──' para recuperar.")

    def _acao_limpar_lista(self):
        """
        Limpa a lista imediatamente recarregando do banco.
        Garante que exclusões persistidas apareçam sem restart.
        """
        self._pautas_cache = []
        self._fila.popular([])
        self._set_status("Recarregando lista...")
        self._carregar_pautas()

    def _acao_reativar_pauta(self, pauta: dict):
        """Reativa uma pauta excluída: volta para 'captada'."""
        uid   = pauta.get("uid") or pauta.get("_uid", "")
        titulo = (pauta.get("titulo_origem") or "")[:60]
        link   = pauta.get("link_origem", "")
        ok = messagebox.askyesno(
            "Reativar pauta",
            f"Reativar esta pauta?\n\n«{titulo}»\n\n"
            "Ela voltará à fila normal com status 'captada'.",
            parent=self,
        )
        if not ok:
            return
        self.db.reativar_pauta(uid, link)
        # Atualiza no cache local imediatamente
        for p in self._pautas_cache:
            if (p.get("uid") or p.get("_uid", "")) == uid:
                p["status"] = "captada"
                break
        self._aplicar_filtro()
        self._set_status(f"✓ Reativada: {titulo}")


    def _acao_aprovar_baixo_score_v129(self, pauta: dict):
        """v129: aprova manualmente uma pauta de baixo score e a devolve à fila normal."""
        uid = pauta.get("uid") or pauta.get("_uid", "")
        titulo = (pauta.get("titulo_origem") or "")[:80]
        if not uid:
            messagebox.showerror("Baixo score", "UID não encontrado para aprovar a pauta.", parent=self)
            return
        ok = messagebox.askyesno(
            "Aprovar baixo score",
            f"Aprovar esta pauta para a fila normal?\n\n«{titulo}»\n\n"
            "Ela mudará de 'baixo_score' para 'captada'.",
            parent=self,
        )
        if not ok:
            return
        try:
            self.db.atualizar_status_pauta(uid, "captada")
        except Exception:
            # fallback: salva novamente o JSON da pauta como captada
            try:
                pauta["status"] = "captada"
                pauta["_v129_aprovada_manual_baixo_score"] = True
                self.db.salvar_pauta(pauta)
            except Exception as e:
                messagebox.showerror("Baixo score", f"Falha ao aprovar: {e}", parent=self)
                return
        for p in self._pautas_cache:
            if (p.get("uid") or p.get("_uid", "")) == uid:
                p["status"] = "captada"
                p["_v129_aprovada_manual_baixo_score"] = True
                break
        self._aplicar_filtro()
        self._set_status(f"✓ Baixo score aprovado para fila: {titulo[:60]}")

    def _acao_reprovar_baixo_score_v129_1(self, pauta: dict):
        """v129.1: reprova uma pauta de baixo score e bloqueia o link para não reaparecer."""
        uid = pauta.get("uid") or pauta.get("_uid", "")
        titulo = _titulo_visual_v129_1(pauta)[:100]
        link = pauta.get("link_origem") or pauta.get("url") or ""
        if not uid:
            messagebox.showerror("Baixo score", "UID não encontrado para reprovar a pauta.", parent=self)
            return
        ok = messagebox.askyesno(
            "Reprovar baixo score",
            f"Reprovar esta pauta e bloquear o link para não voltar?\n\n«{titulo}»",
            parent=self,
        )
        if not ok:
            return
        try:
            self.db.atualizar_status_pauta(uid, "reprovada")
            try:
                self.db.bloquear_link(link, uid, titulo, motivo="reprovada_baixo_score_v129_1")
            except Exception:
                pass
            try:
                self.db.log_auditoria(uid, "reprovar_baixo_score", "Reprovada manualmente na seção Baixo Score", sucesso=True)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Baixo score", f"Falha ao reprovar: {e}", parent=self)
            return
        for p in self._pautas_cache:
            if (p.get("uid") or p.get("_uid", "")) == uid:
                p["status"] = "reprovada"
                p["_v129_reprovada_manual_baixo_score"] = True
                break
        self._aplicar_filtro()
        self._set_status(f"✕ Baixo score reprovado e bloqueado: {titulo[:60]}")

    # ── Histórico ─────────────────────────────────────────────────────────────

    def _acao_historico(self):
        dlg = tk.Toplevel(self)
        dlg.title("Historico")
        dlg.geometry("960x580")
        dlg.configure(bg=COR_FUNDO)
        tk.Label(dlg, text="Historico de Publicacoes", bg=COR_FUNDO,
                 fg=COR_TEXTO, font=FONTE_TITULO).pack(padx=12, pady=8, anchor="w")
        txt = scrolledtext.ScrolledText(dlg, bg="#16213e", fg=COR_TEXTO,
                                         font=FONTE_MONO, wrap="none")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        def _t():
            try:
                conn = self.db._conectar()
                try:
                    rows = conn.execute(
                        "SELECT titulo_origem, status, captada_em, atualizada_em, canal, fonte_nome "
                        "FROM pautas WHERE status IN ('publicada','pronta','revisada') "
                        "ORDER BY atualizada_em DESC LIMIT 200").fetchall()
                finally:
                    conn.close()
                linhas = [f"{'DATA':<20} {'STATUS':<12} {'CANAL':<16} {'FONTE':<18} TITULO",
                          "-" * 100]
                for r in rows:
                    data = (r["atualizada_em"] or r["captada_em"] or "")[:19]
                    linhas.append(f"{data:<20} {(r['status'] or ''):<12} "
                                  f"{(r['canal'] or ''):<16} {(r['fonte_nome'] or ''):<18} "
                                  f"{(r['titulo_origem'] or '')[:60]}")
                conteudo = "\n".join(linhas) if rows else "Nenhuma publicacao encontrada."
                self.after(0, lambda: (txt.insert("1.0", conteudo), txt.config(state="disabled")))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda msg=msg: (txt.insert("1.0", f"Erro: {msg}"), txt.config(state="disabled")))
        threading.Thread(target=_t, daemon=True).start()

    # ── Estatísticas ──────────────────────────────────────────────────────────

    def _acao_estatisticas(self):
        dlg = tk.Toplevel(self)
        dlg.title("Estatisticas")
        dlg.geometry("720x540")
        dlg.configure(bg=COR_FUNDO)
        tk.Label(dlg, text="Estatisticas", bg=COR_FUNDO,
                 fg=COR_TEXTO, font=FONTE_TITULO).pack(padx=12, pady=8, anchor="w")
        txt = scrolledtext.ScrolledText(dlg, bg="#16213e", fg=COR_TEXTO,
                                         font=FONTE_MONO, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        def _t():
            try:
                s = self.db.estatisticas()
                conn = self.db._conectar()
                try:
                    por_st = conn.execute("SELECT status, COUNT(*) n FROM pautas GROUP BY status ORDER BY n DESC").fetchall()
                    por_c  = conn.execute("SELECT canal, COUNT(*) n FROM pautas GROUP BY canal ORDER BY n DESC LIMIT 15").fetchall()
                    por_f  = conn.execute("SELECT fonte_nome, COUNT(*) n FROM pautas GROUP BY fonte_nome ORDER BY n DESC LIMIT 15").fetchall()
                    hoje   = conn.execute("SELECT COUNT(*) n FROM pautas WHERE date(captada_em)=date('now')").fetchone()["n"]
                    sem    = conn.execute("SELECT COUNT(*) n FROM pautas WHERE captada_em>=datetime('now','-7 days')").fetchone()["n"]
                finally:
                    conn.close()
                linhas = ["="*50,"  RESUMO GERAL","="*50,
                          f"Total pautas     : {s.get('total_pautas',0)}",
                          f"Total publicadas : {s.get('total_publicadas',0)}",
                          f"Total materias   : {s.get('total_materias',0)}",
                          f"Captadas hoje    : {hoje}",
                          f"Captadas (7d)    : {sem}",
                          "","="*50,"  POR STATUS","="*50]
                for r in por_st:
                    linhas.append(f"  {(r['status'] or 'N/A'):<22}: {r['n']}")
                linhas += ["","="*50,"  POR CANAL","="*50]
                for r in por_c:
                    linhas.append(f"  {(r['canal'] or 'N/A'):<24}: {r['n']}")
                linhas += ["","="*50,"  POR FONTE","="*50]
                for r in por_f:
                    linhas.append(f"  {(r['fonte_nome'] or 'N/A'):<24}: {r['n']}")
                c = "\n".join(linhas)
                self.after(0, lambda: (txt.insert("1.0", c), txt.config(state="disabled")))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda msg=msg: (txt.insert("1.0", f"Erro: {msg}"), txt.config(state="disabled")))
        threading.Thread(target=_t, daemon=True).start()

    # ── Exportar ──────────────────────────────────────────────────────────────

    def _acao_exportar(self):
        if not self._pauta_sel:
            messagebox.showwarning("Exportar", "Selecione uma pauta primeiro."); return
        md = _parse_materia(self._pauta_sel)
        if not md or not md.get("conteudo"):
            messagebox.showwarning("Exportar", "Sem materia gerada."); return
        p = self._pauta_sel
        default = f"materia_{(p.get('titulo_origem') or 'pauta')[:40]}.txt".replace("/","_").replace("\\","_")
        caminho = filedialog.asksaveasfilename(
            title="Salvar Materia", defaultextension=".txt", initialfile=default,
            filetypes=[("Texto","*.txt"),("Todos","*.*")])
        if not caminho:
            return
        try:
            linhas = [
                f"TITULO SEO    : {md.get('titulo','')}",
                f"TITULO CAPA   : {md.get('titulo_capa','')}",
                f"SUBTITULO     : {md.get('subtitulo','')}",
                f"LEGENDA FOTO  : {md.get('legenda','')}",
                f"RETRANCA      : {md.get('retranca','')}",
                f"SLUG          : {md.get('slug','')}",
                f"TAGS          : {md.get('tags','')}",
                f"META DESC     : {md.get('meta_description','')}",
                f"RESUMO CURTO  : {md.get('resumo_curto','')}",
                f"CHAMADA SOCIAL: {md.get('chamada_social','')}",
                f"CANAL         : {md.get('canal') or p.get('canal_forcado') or p.get('canal','')}",
                f"FONTE ORIGEM  : {p.get('fonte_nome','')}",
                f"PUBLICADO FONTE : {p.get('data_pub_fonte','')} (horário de Brasília)",
                f"LINK ORIGEM   : {p.get('link_origem','')}",
                "", "=" * 70, "", md.get("conteudo",""),
            ]
            Path(caminho).write_text("\n".join(linhas), encoding="utf-8")
            messagebox.showinfo("Exportado", f"Salvo em:\n{caminho}")
            self._set_status(f"Exportado: {Path(caminho).name}")
        except Exception as e:
            messagebox.showerror("Erro ao Exportar", str(e))

    # ── Configurações ─────────────────────────────────────────────────────────

    def _acao_configuracoes(self):
        self._abrir_config_inline()

    # ── Preview inline ────────────────────────────────────────────────────────

    def _abrir_preview_inline(self, pauta: dict, md: dict):
        """Monta o conteúdo de preview dentro da aba '✏ Preview' do notebook."""
        frame = self._aba_preview_frame
        # Destroi conteúdo anterior
        for w in frame.winfo_children():
            w.destroy()

        # Armazena referências para uso nos callbacks
        self._prev_pauta = pauta
        self._prev_md    = dict(md)

        rascunho_var = tk.BooleanVar(value=True)
        canal_inicial = (
            md.get("canal") or
            pauta.get("canal_forcado") or
            pauta.get("canal") or
            "Brasil e Mundo"
        )
        canal_var = tk.StringVar(value=canal_inicial)

        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(frame, bg=COR_PAINEL, height=50)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="✏ Preview e Edição",
                 bg=COR_PAINEL, fg=COR_TEXTO,
                 font=("Helvetica", 11, "bold")).pack(side="left", padx=10)

        def _salvar_inline():
            m = _coletar_prev()
            self._prev_md = m
            self._ao_salvar_preview(self._prev_pauta, m)
            messagebox.showinfo("Salvo", "Edições salvas!")

        def _salvar_e_pub_inline():
            m = _coletar_prev()
            self._ao_salvar_preview(self._prev_pauta, m)
            rascunho = rascunho_var.get()
            self._pauta_sel = self._prev_pauta
            self.after(100, lambda: self._acao_publicar(rascunho=rascunho))

        tk.Button(tb, text="Salvar Edições", command=_salvar_inline,
                  bg=COR_AZUL, fg="white", relief="flat", padx=8, pady=3,
                  cursor="hand2", font=("Helvetica", 9, "bold")).pack(side="right", padx=4, pady=8)
        tk.Button(tb, text="Enviar ao CMS", command=_salvar_e_pub_inline,
                  bg=COR_VERDE, fg="white", relief="flat", padx=8, pady=3,
                  cursor="hand2", font=("Helvetica", 9, "bold")).pack(side="right", padx=4, pady=8)
        tk.Button(tb, text="CopyDesk IA", command=self._preview_copydesk_v132 if hasattr(self, "_preview_copydesk_v132") else self._acao_copydesk,
                  bg=COR_ROXO, fg="white", relief="flat", padx=8, pady=3,
                  cursor="hand2", font=("Helvetica", 9, "bold")).pack(side="right", padx=4, pady=8)

        # Toggle rascunho/publicar
        modo_frame = tk.Frame(tb, bg="#1e293b", padx=6, pady=3)
        modo_frame.pack(side="right", padx=6, pady=8)
        tk.Label(modo_frame, text="Modo:", bg="#1e293b", fg=COR_CINZA,
                 font=("Helvetica", 8)).pack(side="left")
        tk.Radiobutton(modo_frame, text="Rascunho", variable=rascunho_var, value=True,
                       bg="#1e293b", fg=COR_AMARELO, selectcolor="#374151",
                       activebackground="#1e293b", activeforeground=COR_AMARELO,
                       font=("Helvetica", 8, "bold")).pack(side="left", padx=3)
        tk.Radiobutton(modo_frame, text="Publicar!", variable=rascunho_var, value=False,
                       bg="#1e293b", fg=COR_VERMELHO, selectcolor="#374151",
                       activebackground="#1e293b", activeforeground=COR_VERMELHO,
                       font=("Helvetica", 8, "bold")).pack(side="left", padx=3)

        # ── Corpo: paned left/right ───────────────────────────────────────────
        paned = ttk.PanedWindow(frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=4, pady=2)

        left = tk.Frame(paned, bg=COR_PAINEL)
        paned.add(left, weight=3)

        # Imagem
        img_hdr = tk.Frame(left, bg=COR_PAINEL)
        img_hdr.pack(fill="x", padx=6, pady=(4, 2))
        tk.Label(img_hdr, text="Imagem", bg=COR_PAINEL, fg=COR_TEXTO,
                 font=FONTE_TITULO).pack(side="left")

        lbl_img = tk.Label(left, bg="#16213e", fg=COR_CINZA,
                           text="Carregando...", width=38, height=8,
                           font=FONTE_PEQUENA)
        lbl_img.pack(padx=6, pady=2, fill="x")

        img_st = pauta.get("imagem_status", "pendente")
        tk.Label(left, text=f"Status: {img_st}", bg=COR_PAINEL,
                 fg=(COR_VERDE if img_st == "aprovada" else COR_AMARELO),
                 font=("Helvetica", 8, "bold")).pack(padx=6, anchor="w")
        ic = pauta.get("imagem_caminho", "")
        tk.Label(left, text=Path(ic).name if ic else "(sem imagem)",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA,
                 wraplength=280).pack(padx=6, anchor="w")

        tk.Frame(left, bg="#3a3a5c", height=1).pack(fill="x", padx=6, pady=3)

        # Metadados com scroll
        meta_canvas = tk.Canvas(left, bg=COR_PAINEL, highlightthickness=0)
        meta_sb = tk.Scrollbar(left, orient="vertical", command=meta_canvas.yview)
        meta_canvas.configure(yscrollcommand=meta_sb.set)
        meta_sb.pack(side="right", fill="y")
        meta_canvas.pack(side="left", fill="both", expand=True, padx=(6, 0))
        meta_inner = tk.Frame(meta_canvas, bg=COR_PAINEL)
        _meta_window = meta_canvas.create_window((0, 0), window=meta_inner, anchor="nw")
        meta_inner.bind("<Configure>",
                        lambda e: meta_canvas.configure(scrollregion=meta_canvas.bbox("all")))
        meta_canvas.bind("<Configure>",
                         lambda e, w=_meta_window: meta_canvas.itemconfigure(w, width=max(0, e.width - 4)))
        meta_canvas.bind("<MouseWheel>",
                         lambda e: meta_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        tk.Label(meta_inner, text="Metadados (editáveis):", bg=COR_PAINEL,
                 fg=COR_CINZA, font=FONTE_PEQUENA).pack(anchor="w", pady=2)
        self._prev_mvars: dict[str, tk.StringVar] = {}

        # Campos com limite de caracteres: (label, key, limite_max ou None)
        _campos_meta = [
            ("Titulo SEO",     "titulo",        90),
            ("Titulo Capa",    "titulo_capa",   60),
            ("Subtitulo",      "subtitulo",     200),
            ("Legenda Foto",   "legenda",       100),
            ("Retranca",       "retranca",      None),
            ("Slug",           "slug",          None),
            ("Tags",           "tags",          None),
            ("Chamada Social", "chamada_social", None),
        ]
        for lbl_t, key, limite in _campos_meta:
            hrow = tk.Frame(meta_inner, bg=COR_PAINEL)
            hrow.pack(fill="x", pady=(3, 0))
            tk.Label(hrow, text=lbl_t+":", bg=COR_PAINEL, fg=COR_CINZA,
                     font=("Helvetica", 8), anchor="w").pack(side="left")
            if limite:
                lbl_cnt = tk.Label(hrow, text=f"0/{limite}", bg=COR_PAINEL,
                                   fg=COR_CINZA, font=("Helvetica", 7))
                lbl_cnt.pack(side="right")
            v = tk.StringVar(value=self._prev_md.get(key, ""))
            e = tk.Entry(meta_inner, textvariable=v, bg="#16213e", fg=COR_TEXTO,
                         insertbackground=COR_TEXTO, font=("Courier New", 9),
                         relief="flat")
            e.pack(fill="x")
            self._prev_mvars[key] = v
            # Contador ao vivo com cor: verde=ok, amarelo=próximo, vermelho=excedido
            if limite:
                def _fazer_cb(var=v, lbl=lbl_cnt, lim=limite):
                    def _cb(*_):
                        n = len(var.get())
                        lbl.config(
                            text=f"{n}/{lim}",
                            fg=(COR_VERMELHO if n > lim
                                else COR_AMARELO if n > lim * 0.9
                                else COR_VERDE))
                    return _cb
                cb = _fazer_cb()
                v.trace_add("write", cb)
                cb()  # atualiza imediatamente com o valor atual

        sc = pauta.get("score_risco", 0) or 0
        tk.Label(meta_inner, text=f"Score Risco: {sc}/100", bg=COR_PAINEL,
                 fg=(COR_VERMELHO if sc >= LIMIAR_RISCO_MAXIMO
                     else COR_AMARELO if sc >= 30 else COR_VERDE),
                 font=("Helvetica", 8, "bold")).pack(pady=3, anchor="w")

        tk.Frame(meta_inner, bg="#3a3a5c", height=1).pack(fill="x", pady=3)
        tk.Label(meta_inner, text="Canal (editoria):", bg=COR_PAINEL, fg=COR_CINZA,
                 font=("Helvetica", 8), anchor="w").pack(fill="x", pady=(2, 0))
        canal_cb = ttk.Combobox(meta_inner, textvariable=canal_var,
                                values=CANAIS_CMS, state="normal",
                                font=("Courier New", 9))
        canal_cb.pack(fill="x")
        tk.Label(meta_inner, text="↑ Editoria que aparecerá no CMS",
                 bg=COR_PAINEL, fg=COR_CINZA,
                 font=("Helvetica", 7)).pack(anchor="w")

        # Painel direito: conteúdo
        right = tk.Frame(paned, bg=COR_PAINEL)
        paned.add(right, weight=5)
        tk.Label(right, text="Conteúdo (Ctrl+Z = desfazer)", bg=COR_PAINEL,
                 fg=COR_TEXTO, font=FONTE_TITULO).pack(padx=6, pady=3, anchor="w")
        self._prev_txt = tk.Text(right, bg="#16213e", fg=COR_TEXTO,
                                 insertbackground=COR_TEXTO,
                                 font=("Courier New", 10), wrap="word",
                                 relief="flat", padx=6, pady=6, undo=True)
        self._prev_txt.pack(fill="both", expand=True, padx=6, pady=3)
        bar = tk.Frame(right, bg=COR_PAINEL)
        bar.pack(fill="x", padx=6, pady=2)
        self._prev_lbl_chars = tk.Label(bar, text="", bg=COR_PAINEL,
                                        fg=COR_CINZA, font=FONTE_PEQUENA)
        self._prev_lbl_chars.pack(side="right")

        def _contar(_=None):
            n = len(self._prev_txt.get("1.0", "end-1c"))
            self._prev_lbl_chars.config(
                text=f"{n} caracteres",
                fg=COR_VERDE if 2000 <= n <= 6200 else COR_AMARELO)

        self._prev_txt.bind("<KeyRelease>", _contar)
        self._prev_txt.insert("1.0", self._prev_md.get("conteudo", ""))
        _contar()

        def _coletar_prev() -> dict:
            m = dict(self._prev_md)
            for k, v in self._prev_mvars.items():
                m[k] = v.get().strip()
            m["conteudo"] = self._prev_txt.get("1.0", "end-1c").strip()
            canal_escolhido = canal_var.get().strip()
            if canal_escolhido:
                m["canal"] = canal_escolhido
                self._prev_pauta["canal_forcado"] = canal_escolhido
            # Garante link_origem no md
            if not m.get("link_origem"):
                m["link_origem"] = self._prev_pauta.get("link_origem", "")
            return m

        # Carrega imagem em background
        def _load_img_inline():
            c = pauta.get("imagem_caminho", "")
            if not c:
                lbl_img.config(text="Nenhuma imagem associada."); return
            p2 = Path(c)
            if not p2.exists():
                p2 = Path("imagens") / p2.name
            if not p2.exists():
                lbl_img.config(text=f"Não encontrada:\n{c}"); return
            try:
                from PIL import Image, ImageTk
                img = Image.open(p2)
                img.thumbnail((320, 200), Image.LANCZOS)
                ftk = ImageTk.PhotoImage(img)
                self._prev_ftk = ftk
                lbl_img.config(image=ftk, text="", width=img.width, height=img.height)
            except ImportError:
                lbl_img.config(text=f"Pillow não instalado.\n{p2.name}")
            except Exception as ex:
                lbl_img.config(text=f"Erro:\n{ex}")

        frame.after(200, _load_img_inline)

        # Seleciona a aba Preview
        self._notebook.select(self._idx_aba_preview)

    # ── Config inline ─────────────────────────────────────────────────────────

    def _abrir_config_inline(self):
        """Monta o conteúdo de configurações dentro da aba '⚙ Config'."""
        frame = self._aba_config_frame
        for w in frame.winfo_children():
            w.destroy()

        # Reutiliza JanelaConfiguracoes mas incorporada num frame, não Toplevel
        cfg_widget = _ConfigWidget(frame, self.db, owner=self)
        self._config_widget = cfg_widget
        cfg_widget.pack(fill="both", expand=True)

        self._notebook.select(self._idx_aba_config)


# ── Janela Preview ────────────────────────────────────────────────────────────

class JanelaPreview(tk.Toplevel):

    def __init__(self, parent, pauta, md, db, cb_salvar, cb_publicar):
        super().__init__(parent)
        self._pauta    = pauta
        self._md       = dict(md)
        self._db       = db
        self._cb_s     = cb_salvar
        self._cb_p     = cb_publicar
        self._rascunho = tk.BooleanVar(value=True)  # padrão: salvar como rascunho
        # Canal: usa o canal já definido na matéria ou pauta, fallback "Brasil e Mundo"
        canal_inicial = (
            md.get("canal") or
            pauta.get("canal_forcado") or
            pauta.get("canal") or
            "Brasil e Mundo"
        )
        self._canal_var = tk.StringVar(value=canal_inicial)
        self.title(f"Preview — {(pauta.get('titulo_origem') or '')[:60]}")
        self.geometry("1160x820")
        self.configure(bg=COR_FUNDO)
        self.grab_set()
        self.resizable(True, True)
        self._build()

    def _build(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self, bg=COR_PAINEL, height=56)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="Preview e Edicao", bg=COR_PAINEL, fg=COR_TEXTO,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=12)

        # Botões de ação
        tk.Button(tb, text="Fechar", command=self.destroy,
                  bg=COR_CINZA, fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2", font=("Helvetica", 10, "bold")).pack(side="right", padx=4, pady=8)
        tk.Button(tb, text="Salvar Edicoes", command=self._salvar,
                  bg=COR_AZUL, fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2", font=("Helvetica", 10, "bold")).pack(side="right", padx=4, pady=8)
        tk.Button(tb, text="Enviar ao CMS", command=self._salvar_e_pub,
                  bg=COR_VERDE, fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2", font=("Helvetica", 10, "bold")).pack(side="right", padx=4, pady=8)

        # Toggle rascunho/publicar
        modo_frame = tk.Frame(tb, bg="#1e293b", padx=6, pady=3)
        modo_frame.pack(side="right", padx=8, pady=8)
        tk.Label(modo_frame, text="Modo:", bg="#1e293b", fg=COR_CINZA,
                 font=("Helvetica", 8)).pack(side="left")
        tk.Radiobutton(modo_frame, text="Rascunho", variable=self._rascunho, value=True,
                       bg="#1e293b", fg=COR_AMARELO, selectcolor="#374151",
                       activebackground="#1e293b", activeforeground=COR_AMARELO,
                       font=("Helvetica", 9, "bold")).pack(side="left", padx=4)
        tk.Radiobutton(modo_frame, text="Publicar!", variable=self._rascunho, value=False,
                       bg="#1e293b", fg=COR_VERMELHO, selectcolor="#374151",
                       activebackground="#1e293b", activeforeground=COR_VERMELHO,
                       font=("Helvetica", 9, "bold")).pack(side="left", padx=4)

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        left = tk.Frame(paned, bg=COR_PAINEL)
        paned.add(left, weight=3)

        # ── Seção de imagem ───────────────────────────────────────────────────
        img_hdr = tk.Frame(left, bg=COR_PAINEL)
        img_hdr.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(img_hdr, text="Imagem", bg=COR_PAINEL, fg=COR_TEXTO,
                 font=FONTE_TITULO).pack(side="left")
        # Botões de imagem inline
        tk.Button(img_hdr, text="📁 Escolher arquivo",
                  command=self._escolher_imagem_arquivo,
                  bg="#1e3a5f", fg="#7dd3fc", relief="flat",
                  padx=5, pady=1, cursor="hand2",
                  font=("Segoe UI", 7, "bold")).pack(side="right", padx=2)
        tk.Button(img_hdr, text="🔍 Buscar por tema",
                  command=self._buscar_imagem_tema,
                  bg="#1e293b", fg=COR_CIANO, relief="flat",
                  padx=5, pady=1, cursor="hand2",
                  font=("Segoe UI", 7, "bold")).pack(side="right", padx=2)

        self._lbl_img = tk.Label(left, bg="#16213e", fg=COR_CINZA,
                                  text="Carregando...", width=40, height=10,
                                  font=FONTE_PEQUENA)
        self._lbl_img.pack(padx=8, pady=4, fill="x")
        img_st = self._pauta.get("imagem_status", "pendente")
        self._lbl_img_status = tk.Label(left, text=f"Status: {img_st}", bg=COR_PAINEL,
                 fg=(COR_VERDE if img_st == "aprovada" else COR_AMARELO),
                 font=("Helvetica", 9, "bold"))
        self._lbl_img_status.pack(padx=8, anchor="w")
        self._lbl_img_nome = tk.Label(left,
                     text=Path(self._pauta["imagem_caminho"]).name if self._pauta.get("imagem_caminho") else "(sem imagem)",
                     bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA,
                     wraplength=320)
        self._lbl_img_nome.pack(padx=8, anchor="w")

        tk.Frame(left, bg="#3a3a5c", height=1).pack(fill="x", padx=8, pady=4)

        # ── Metadados editáveis (com scroll) ─────────────────────────────────
        meta_canvas = tk.Canvas(left, bg=COR_PAINEL, highlightthickness=0)
        meta_sb = tk.Scrollbar(left, orient="vertical", command=meta_canvas.yview)
        meta_canvas.configure(yscrollcommand=meta_sb.set)
        meta_sb.pack(side="right", fill="y")
        meta_canvas.pack(side="left", fill="both", expand=True, padx=(8, 0))
        meta_inner = tk.Frame(meta_canvas, bg=COR_PAINEL)
        _meta_window = meta_canvas.create_window((0, 0), window=meta_inner, anchor="nw")
        meta_inner.bind("<Configure>",
                        lambda e: meta_canvas.configure(scrollregion=meta_canvas.bbox("all")))
        meta_canvas.bind("<Configure>",
                         lambda e, w=_meta_window: meta_canvas.itemconfigure(w, width=max(0, e.width - 4)))
        meta_canvas.bind("<MouseWheel>",
                         lambda e: meta_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        tk.Label(meta_inner, text="Metadados (editaveis):", bg=COR_PAINEL,
                 fg=COR_CINZA, font=FONTE_PEQUENA).pack(anchor="w", pady=2)
        self._mvars: dict[str, tk.StringVar] = {}
        _campos_jpreview = [
            ("Titulo SEO",     "titulo",        90),
            ("Titulo Capa",    "titulo_capa",   60),
            ("Subtitulo",      "subtitulo",     200),
            ("Legenda Foto",   "legenda",       100),
            ("Retranca",       "retranca",      None),
            ("Slug",           "slug",          None),
            ("Tags",           "tags",          None),
            ("Chamada Social", "chamada_social", None),
        ]
        for lbl, key, limite in _campos_jpreview:
            hrow = tk.Frame(meta_inner, bg=COR_PAINEL)
            hrow.pack(fill="x", pady=(3, 0))
            tk.Label(hrow, text=lbl+":", bg=COR_PAINEL, fg=COR_CINZA,
                     font=("Helvetica", 8), anchor="w").pack(side="left")
            if limite:
                lbl_cnt = tk.Label(hrow, text=f"0/{limite}", bg=COR_PAINEL,
                                   fg=COR_CINZA, font=("Helvetica", 7))
                lbl_cnt.pack(side="right")
            v = tk.StringVar(value=self._md.get(key, ""))
            tk.Entry(meta_inner, textvariable=v, bg="#16213e", fg=COR_TEXTO,
                     insertbackground=COR_TEXTO, font=("Courier New", 9),
                     relief="flat").pack(fill="x")
            self._mvars[key] = v
            if limite:
                def _fazer_cb_jp(var=v, lbl=lbl_cnt, lim=limite):
                    def _cb(*_):
                        n = len(var.get())
                        lbl.config(
                            text=f"{n}/{lim}",
                            fg=(COR_VERMELHO if n > lim
                                else COR_AMARELO if n > lim * 0.9
                                else COR_VERDE))
                    return _cb
                cb = _fazer_cb_jp()
                v.trace_add("write", cb)
                cb()
        sc = self._pauta.get("score_risco", 0) or 0
        tk.Label(meta_inner, text=f"Score Risco: {sc}/100", bg=COR_PAINEL,
                 fg=(COR_VERMELHO if sc >= LIMIAR_RISCO_MAXIMO
                     else COR_AMARELO if sc >= 30 else COR_VERDE),
                 font=("Helvetica", 9, "bold")).pack(pady=4, anchor="w")

        # ── Canal editorial ───────────────────────────────────────────────────
        tk.Frame(meta_inner, bg="#3a3a5c", height=1).pack(fill="x", pady=4)
        tk.Label(meta_inner, text="Canal (editoria):", bg=COR_PAINEL, fg=COR_CINZA,
                 font=("Helvetica", 8), anchor="w").pack(fill="x", pady=(2, 0))
        canal_cb = ttk.Combobox(meta_inner, textvariable=self._canal_var,
                                values=CANAIS_CMS, state="normal",
                                font=("Courier New", 9))
        canal_cb.pack(fill="x")
        tk.Label(meta_inner, text="↑ Editoria que aparecerá no CMS",
                 bg=COR_PAINEL, fg=COR_CINZA,
                 font=("Helvetica", 7)).pack(anchor="w")

        right = tk.Frame(paned, bg=COR_PAINEL)
        paned.add(right, weight=5)
        tk.Label(right, text="Conteudo (Ctrl+Z = desfazer)", bg=COR_PAINEL,
                 fg=COR_TEXTO, font=FONTE_TITULO).pack(padx=8, pady=4, anchor="w")
        self._txt = tk.Text(right, bg="#16213e", fg=COR_TEXTO,
                            insertbackground=COR_TEXTO,
                            font=("Courier New", 10), wrap="word",
                            relief="flat", padx=8, pady=8, undo=True)
        self._txt.pack(fill="both", expand=True, padx=8, pady=4)
        bar = tk.Frame(right, bg=COR_PAINEL)
        bar.pack(fill="x", padx=8, pady=2)
        self._lbl_chars = tk.Label(bar, text="", bg=COR_PAINEL,
                                   fg=COR_CINZA, font=FONTE_PEQUENA)
        self._lbl_chars.pack(side="right")
        self._txt.bind("<KeyRelease>", self._contar)
        self._txt.insert("1.0", self._md.get("conteudo", ""))
        self._contar()
        self.after(300, self._load_img)

    def _contar(self, _=None):
        n = len(self._txt.get("1.0", "end-1c"))
        self._lbl_chars.config(
            text=f"{n} caracteres",
            fg=COR_VERDE if 2000 <= n <= 6200 else COR_AMARELO)

    def _load_img(self):
        c = self._pauta.get("imagem_caminho", "")
        if not c:
            self._lbl_img.config(text="Nenhuma imagem associada.\nUse os botões acima para adicionar."); return
        p = Path(c)
        if not p.exists():
            p = Path("imagens") / p.name
        if not p.exists():
            self._lbl_img.config(text=f"Imagem nao encontrada:\n{c}"); return
        try:
            from PIL import Image, ImageTk
            img = Image.open(p)
            img.thumbnail((360, 240), Image.LANCZOS)
            self._ftk = ImageTk.PhotoImage(img)
            self._lbl_img.config(image=self._ftk, text="",
                                  width=img.width, height=img.height)
        except ImportError:
            self._lbl_img.config(text=f"Pillow nao instalado.\n{p.name}")
        except Exception as e:
            self._lbl_img.config(text=f"Erro ao exibir:\n{e}")

    def _escolher_imagem_arquivo(self):
        """Permite ao usuário escolher uma imagem do computador."""
        from tkinter import filedialog
        caminho = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.gif *.bmp"),
                       ("Todos", "*.*")],
            parent=self)
        if not caminho:
            return
        p = Path(caminho)
        # Copia para a pasta de imagens do sistema
        import shutil
        pasta_img = Path("imagens")
        pasta_img.mkdir(exist_ok=True)
        destino = pasta_img / p.name
        try:
            shutil.copy2(caminho, destino)
        except Exception:
            destino = p  # usa o caminho original se não conseguir copiar
        self._pauta["imagem_caminho"] = str(destino)
        self._pauta["imagem_status"]  = "aprovada"
        self._pauta["imagem_credito"] = "Arquivo local"
        # Atualiza UI
        self._lbl_img_status.config(text="Status: aprovada", fg=COR_VERDE)
        self._lbl_img_nome.config(text=p.name)
        self._load_img()
        # Salva no banco
        uid = self._pauta.get("uid") or self._pauta.get("_uid", "")
        if uid:
            self._db.salvar_pauta({**self._pauta, "_uid": uid})
        messagebox.showinfo("Imagem carregada", f"Imagem '{p.name}' selecionada!", parent=self)

    def _buscar_imagem_tema(self):
        """Abre janela para buscar imagem por tema/palavra-chave."""
        # Sugere o título da matéria como tema inicial
        titulo = self._md.get("titulo", "") or self._pauta.get("titulo_origem", "")
        # Pega as primeiras palavras relevantes como sugestão
        import re
        palavras = re.findall(r'\b[A-Z][a-z]+\b|\b[a-z]{4,}\b', titulo)
        sugestao = " ".join(palavras[:4]) if palavras else titulo[:40]

        tema = simpledialog.askstring(
            "Buscar Imagem por Tema",
            f"Digite o tema para buscar imagens:\n\n"
            f"Exemplo: 'Polícia Rio de Janeiro operação'\n\n"
            f"Sugestão baseada na matéria:",
            initialvalue=sugestao,
            parent=self)
        if not tema:
            return

        self._lbl_img.config(text=f"🔍 Buscando: '{tema}'...")
        self.update()
        threading.Thread(target=self._buscar_imagem_tema_thread,
                         args=(tema,), daemon=True).start()

    def _buscar_imagem_tema_thread(self, tema: str):
        """Executa a busca de imagem em background."""
        try:
            from ururau.imaging.busca import buscar_imagem_bing, buscar_imagem_wikimedia
            from ururau.imaging.processamento import processar_imagem
            uid = self._pauta.get("uid") or self._pauta.get("_uid", "busca_manual")

            imagem = None
            # Tenta Bing primeiro
            try:
                imagem = buscar_imagem_bing(tema, uid)
            except Exception:
                pass
            # Fallback: Wikimedia
            if not imagem:
                try:
                    imagem = buscar_imagem_wikimedia(tema, uid)
                except Exception:
                    pass

            if imagem and imagem.caminho_imagem:
                self._pauta["imagem_caminho"]    = imagem.caminho_imagem
                self._pauta["imagem_status"]     = "aprovada"
                self._pauta["imagem_url"]        = imagem.url_imagem
                self._pauta["imagem_credito"]    = imagem.credito_foto
                self._pauta["imagem_estrategia"] = imagem.estrategia_imagem
                self.after(0, self._load_img)
                self.after(0, lambda: self._lbl_img_status.config(text="Status: aprovada", fg=COR_VERDE))
                self.after(0, lambda: self._lbl_img_nome.config(
                    text=Path(imagem.caminho_imagem).name))
                # Salva no banco
                if uid and uid != "busca_manual":
                    self._db.salvar_imagem(uid, imagem.to_dict())
                    self._db.salvar_pauta({**self._pauta, "_uid": uid})
                self.after(0, lambda: messagebox.showinfo(
                    "Imagem encontrada",
                    f"Imagem encontrada para '{tema}'!\n"
                    f"Estratégia: {imagem.estrategia_imagem}", parent=self))
            else:
                self.after(0, lambda: self._lbl_img.config(
                    text=f"Nenhuma imagem encontrada para:\n'{tema}'\n\nTente outro tema."))
                self.after(0, lambda: messagebox.showwarning(
                    "Sem imagem",
                    f"Não foi possível encontrar imagem para '{tema}'.\n"
                    f"Tente um tema diferente ou use 'Escolher arquivo'.",
                    parent=self))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._lbl_img.config(text=f"Erro na busca:\n{msg}"))
            self.after(0, lambda msg=msg: messagebox.showerror("Erro", msg, parent=self))

    def _coletar(self):
        m = dict(self._md)
        for k, v in self._mvars.items():
            m[k] = v.get().strip()
        m["conteudo"] = self._txt.get("1.0", "end-1c").strip()
        # Canal selecionado manualmente pelo editor
        canal_escolhido = self._canal_var.get().strip()
        if canal_escolhido:
            m["canal"] = canal_escolhido
            # Propaga para a pauta também, para o workflow usar corretamente
            self._pauta["canal_forcado"] = canal_escolhido
        return m

    def _salvar(self):
        m = self._coletar()
        self._md = m
        self._cb_s(self._pauta, m)
        messagebox.showinfo("Salvo", "Edicoes salvas!", parent=self)

    def _salvar_e_pub(self):
        m = self._coletar()
        self._cb_s(self._pauta, m)
        rascunho = self._rascunho.get()
        self.destroy()
        self.master.after(300, lambda: self._cb_p(rascunho=rascunho))


# ── Aba Monitor (integrada ao painel principal) ───────────────────────────────

class AbaMonitor(tk.Frame):
    """
    Painel de controle do Robô de Monitoramento 24h integrado como aba.

    Substitui JanelaMonitor (Toplevel) — tudo dentro do notebook de detalhes.
    Permite configurar e iniciar/parar o robô sem sair do painel.
    Exibe log ao vivo das atividades do robô.
    """

    def __init__(self, parent, db, client, modelo,
                 robo_existente=None, cb_robo_atualizado=None):
        super().__init__(parent, bg=COR_FUNDO)
        self._db             = db
        self._client         = client
        self._modelo         = modelo
        self._robo           = robo_existente
        self._thread         = None
        self._cb_atualizado  = cb_robo_atualizado or (lambda r, t: None)
        self._log_ultimas    = 0   # contador para leitura incremental do log
        self._build()
        self.after(500, self._tick)

    def _build(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self, bg="#11112a", height=46)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="🤖 Robô de Monitoramento 24h",
                 bg="#11112a", fg=COR_DESTAQUE,
                 font=("Helvetica", 11, "bold")).pack(side="left", padx=10)

        self._btn_stop = tk.Button(tb, text="■  PARAR",
                                   command=self._parar,
                                   bg="#7f1d1d", fg="#fca5a5",
                                   relief="flat", padx=10, pady=3,
                                   cursor="hand2",
                                   font=("Helvetica", 9, "bold"),
                                   state="disabled")
        self._btn_stop.pack(side="right", padx=4, pady=6)

        self._btn_start = tk.Button(tb, text="▶  INICIAR MONITOR",
                                    command=self._iniciar,
                                    bg="#14532d", fg="#86efac",
                                    relief="flat", padx=10, pady=3,
                                    cursor="hand2",
                                    font=("Helvetica", 9, "bold"))
        self._btn_start.pack(side="right", padx=4, pady=6)

        # ── Status banner ─────────────────────────────────────────────────────
        self._banner = tk.Frame(self, bg="#1c1c35", height=32)
        self._banner.pack(fill="x")
        self._banner.pack_propagate(False)
        self._lbl_status = tk.Label(self._banner, text="● INATIVO",
                                    bg="#1c1c35", fg=COR_CINZA,
                                    font=("Segoe UI", 10, "bold"))
        self._lbl_status.pack(side="left", padx=10)
        self._lbl_contagem = tk.Label(self._banner, text="",
                                      bg="#1c1c35", fg=COR_CINZA,
                                      font=("Segoe UI", 8))
        self._lbl_contagem.pack(side="left", padx=8)

        # ── Configurações ─────────────────────────────────────────────────────
        cfg = tk.LabelFrame(self, text="Configurações", bg=COR_FUNDO, fg=COR_TEXTO,
                            font=("Segoe UI", 8, "bold"), padx=8, pady=4)
        cfg.pack(fill="x", padx=8, pady=4)

        from ururau.config.settings import (
            INTERVALO_ENTRE_CICLOS_SEGUNDOS,
            MAX_PUBLICACOES_MONITORAMENTO_POR_HORA,
        )

        row1 = tk.Frame(cfg, bg=COR_FUNDO)
        row1.pack(fill="x")
        tk.Label(row1, text="Intervalo entre ciclos (seg):",
                 bg=COR_FUNDO, fg=COR_TEXTO,
                 font=("Segoe UI", 8), width=28, anchor="w").pack(side="left")
        self._var_intervalo = tk.StringVar(value=str(INTERVALO_ENTRE_CICLOS_SEGUNDOS))
        tk.Entry(row1, textvariable=self._var_intervalo,
                 bg="#16213e", fg=COR_VERDE, insertbackground=COR_TEXTO,
                 font=("Courier New", 9), width=7, relief="flat").pack(side="left", padx=6)
        tk.Label(row1, text=f"(≈{INTERVALO_ENTRE_CICLOS_SEGUNDOS//60}min)",
                 bg=COR_FUNDO, fg=COR_CINZA, font=("Segoe UI", 7)).pack(side="left")

        row2 = tk.Frame(cfg, bg=COR_FUNDO)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Máx. matérias por hora:",
                 bg=COR_FUNDO, fg=COR_TEXTO,
                 font=("Segoe UI", 8), width=28, anchor="w").pack(side="left")
        self._var_max_hora = tk.StringVar(value=str(MAX_PUBLICACOES_MONITORAMENTO_POR_HORA))
        tk.Entry(row2, textvariable=self._var_max_hora,
                 bg="#16213e", fg=COR_VERDE, insertbackground=COR_TEXTO,
                 font=("Courier New", 9), width=7, relief="flat").pack(side="left", padx=6)

        row3 = tk.Frame(cfg, bg=COR_FUNDO)
        row3.pack(fill="x")
        self._var_publicar = tk.BooleanVar(value=False)
        tk.Checkbutton(row3, text="Publicar diretamente no CMS",
                       variable=self._var_publicar,
                       bg=COR_FUNDO, fg=COR_TEXTO, selectcolor="#1e3a5f",
                       activebackground=COR_FUNDO, activeforeground=COR_TEXTO,
                       font=("Segoe UI", 8)).pack(side="left")

        # ── Log ao vivo ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=COR_FUNDO)
        hdr.pack(fill="x", padx=8, pady=(4, 0))
        tk.Label(hdr, text="Log ao vivo:", bg=COR_FUNDO, fg=COR_CINZA,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Button(hdr, text="Limpar", command=self._limpar_log,
                  bg="#1e293b", fg=COR_CINZA, relief="flat",
                  font=("Segoe UI", 7), padx=6, pady=1,
                  cursor="hand2").pack(side="right")

        self._log_txt = scrolledtext.ScrolledText(self, bg="#080818", fg="#94a3b8",
                                                   font=("Courier New", 8),
                                                   state="disabled", wrap="word")
        self._log_txt.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self._log_txt.tag_configure("ok",   foreground="#86efac")
        self._log_txt.tag_configure("err",  foreground="#fca5a5")
        self._log_txt.tag_configure("info", foreground="#94a3b8")
        self._log_txt.tag_configure("warn", foreground="#fde68a")

        # Lê log existente
        self.after(300, self._ler_log_arquivo)

    # ── Log ───────────────────────────────────────────────────────────────────

    def _ler_log_arquivo(self):
        """Carrega as últimas 80 linhas do monitor.log."""
        log_path = Path("logs") / "monitor.log"
        if not log_path.exists():
            self._append_log("(nenhum log anterior encontrado)", "info")
            return
        try:
            linhas = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            ultimas = linhas[-80:]
            self._log_ultimas = len(linhas)
            for ln in ultimas:
                self._append_log(ln, self._tag_linha(ln))
        except Exception as e:
            self._append_log(f"Erro ao ler log: {e}", "err")

    def _tag_linha(self, ln: str) -> str:
        if "[OK]" in ln or "OK" in ln:
            return "ok"
        if "ERROR" in ln or "ERRO" in ln or "[XX]" in ln:
            return "err"
        if "WARNING" in ln or "AVISO" in ln or "WARN" in ln:
            return "warn"
        return "info"

    def _append_log(self, texto: str, tag: str = "info"):
        self._log_txt.config(state="normal")
        self._log_txt.insert("end", texto + "\n", tag)
        self._log_txt.see("end")
        self._log_txt.config(state="disabled")

    def _limpar_log(self):
        self._log_txt.config(state="normal")
        self._log_txt.delete("1.0", "end")
        self._log_txt.config(state="disabled")

    # ── Controles ─────────────────────────────────────────────────────────────

    def _iniciar(self):
        # v79: o monitor não exige mais OPENAI_API_KEY. Sem cliente, usa fallback local.
        if not self._client:
            self._append_log("[Monitor v79] OPENAI_API_KEY ausente: usando fallback local sem IA.", "warn")
        if self._robo and self._robo.ativo:
            messagebox.showinfo("Monitor", "O monitor já está ativo.")
            return
        try:
            intervalo = int(self._var_intervalo.get())
            max_hora  = int(self._var_max_hora.get())
        except ValueError:
            messagebox.showerror("Erro", "Valores inválidos nos campos.")
            return
        publicar = self._var_publicar.get()

        from ururau.publisher.monitor import MonitorRobo
        self._robo = MonitorRobo(
            db=self._db,
            client=self._client,
            modelo=self._modelo,
            intervalo_segundos=intervalo,
            max_por_hora=max_hora,
            publicar_no_cms=publicar,
        )
        def _run():
            try:
                self._robo.iniciar()
            except Exception as e:
                msg = str(e)
                self.after(0, lambda msg=msg: self._append_log(f"[ERRO] {msg}", "err"))
            finally:
                self.after(0, self._atualizar_ui)
        self._thread = threading.Thread(target=_run, daemon=True, name="MonitorRobo")
        self._thread.start()
        self._atualizar_ui()
        self._cb_atualizado(self._robo, self._thread)
        self._append_log(
            f"[Monitor] Iniciado. Intervalo={intervalo}s Max/hora={max_hora} "
            f"CMS={'SIM' if publicar else 'NAO'}", "ok")

    def _parar(self):
        if self._robo:
            self._robo.parar()
        self._atualizar_ui()
        self._cb_atualizado(self._robo, self._thread)
        self._append_log("[Monitor] Parado pelo usuário.", "warn")

    def _atualizar_ui(self):
        ativo = bool(self._robo and self._robo.ativo)
        if ativo:
            n = self._robo.publicacoes_na_hora
            self._lbl_status.config(
                text=f"● ATIVO — {n} matéria(s) publicadas na última hora",
                fg=COR_VERDE)
            self._btn_start.config(state="disabled")
            self._btn_stop.config(state="normal")
        else:
            self._lbl_status.config(text="● INATIVO", fg=COR_CINZA)
            self._btn_start.config(state="normal")
            self._btn_stop.config(state="disabled")

    def _tick(self):
        """Atualiza UI e log incrementalmente a cada 20s."""
        try:
            self._atualizar_ui()
            # Lê novas linhas do log desde a última leitura
            log_path = Path("logs") / "monitor.log"
            if log_path.exists():
                try:
                    linhas = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if len(linhas) > self._log_ultimas:
                        novas = linhas[self._log_ultimas:]
                        self._log_ultimas = len(linhas)
                        for ln in novas:
                            self._append_log(ln, self._tag_linha(ln))
                except Exception:
                    pass
        except Exception:
            pass
        # Agenda próximo tick apenas se o widget ainda existe
        try:
            self.after(20_000, self._tick)
        except Exception:
            pass


# ── Janela Monitor 24h (mantida para compatibilidade) ─────────────────────────

class JanelaMonitor(tk.Toplevel):
    """
    Painel de controle do Robô de Monitoramento 24h.

    Permite configurar e iniciar/parar o robô sem sair do painel principal.
    Exibe log ao vivo das atividades do robô.
    """

    def __init__(self, parent, db, client, modelo,
                 robo_existente=None, cb_robo_atualizado=None):
        super().__init__(parent)
        self._db             = db
        self._client         = client
        self._modelo         = modelo
        self._robo           = robo_existente
        self._thread         = None
        self._cb_atualizado  = cb_robo_atualizado or (lambda r, t: None)
        self.title("Robô de Monitoramento 24h")
        self.geometry("780x600")
        self.configure(bg=COR_FUNDO)
        self.resizable(True, True)
        self._build()
        self._tick()

    def _build(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self, bg="#11112a", height=50)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="🤖 Robô de Monitoramento 24h",
                 bg="#11112a", fg=COR_DESTAQUE,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=12)

        self._btn_start = tk.Button(tb, text="▶  INICIAR MONITOR",
                                    command=self._iniciar,
                                    bg="#14532d", fg="#86efac",
                                    relief="flat", padx=12, pady=4,
                                    cursor="hand2",
                                    font=("Helvetica", 10, "bold"))
        self._btn_start.pack(side="right", padx=4, pady=8)

        self._btn_stop = tk.Button(tb, text="■  PARAR",
                                   command=self._parar,
                                   bg="#7f1d1d", fg="#fca5a5",
                                   relief="flat", padx=12, pady=4,
                                   cursor="hand2",
                                   font=("Helvetica", 10, "bold"),
                                   state="disabled")
        self._btn_stop.pack(side="right", padx=4, pady=8)

        # ── Status banner ─────────────────────────────────────────────────────
        self._banner = tk.Frame(self, bg="#1c1c35", height=38)
        self._banner.pack(fill="x")
        self._banner.pack_propagate(False)
        self._lbl_status = tk.Label(self._banner, text="● INATIVO",
                                    bg="#1c1c35", fg=COR_CINZA,
                                    font=("Segoe UI", 11, "bold"))
        self._lbl_status.pack(side="left", padx=12)
        self._lbl_contagem = tk.Label(self._banner, text="",
                                      bg="#1c1c35", fg=COR_CINZA,
                                      font=("Segoe UI", 9))
        self._lbl_contagem.pack(side="left", padx=12)

        # ── Configurações ─────────────────────────────────────────────────────
        cfg = tk.LabelFrame(self, text="Configurações", bg=COR_FUNDO, fg=COR_TEXTO,
                            font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        cfg.pack(fill="x", padx=10, pady=6)

        from ururau.config.settings import (
            INTERVALO_ENTRE_CICLOS_SEGUNDOS,
            MAX_PUBLICACOES_MONITORAMENTO_POR_HORA,
        )

        row1 = tk.Frame(cfg, bg=COR_FUNDO)
        row1.pack(fill="x")
        tk.Label(row1, text="Intervalo entre ciclos (segundos):",
                 bg=COR_FUNDO, fg=COR_TEXTO,
                 font=("Segoe UI", 9), width=36, anchor="w").pack(side="left")
        self._var_intervalo = tk.StringVar(value=str(INTERVALO_ENTRE_CICLOS_SEGUNDOS))
        tk.Entry(row1, textvariable=self._var_intervalo,
                 bg="#16213e", fg=COR_VERDE, insertbackground=COR_TEXTO,
                 font=("Courier New", 10), width=8, relief="flat").pack(side="left", padx=8)
        tk.Label(row1, text=f"(atual: {INTERVALO_ENTRE_CICLOS_SEGUNDOS//60}min)",
                 bg=COR_FUNDO, fg=COR_CINZA, font=("Segoe UI", 8)).pack(side="left")

        row2 = tk.Frame(cfg, bg=COR_FUNDO)
        row2.pack(fill="x", pady=4)
        tk.Label(row2, text="Máximo de matérias por hora:",
                 bg=COR_FUNDO, fg=COR_TEXTO,
                 font=("Segoe UI", 9), width=36, anchor="w").pack(side="left")
        self._var_max_hora = tk.StringVar(value=str(MAX_PUBLICACOES_MONITORAMENTO_POR_HORA))
        tk.Entry(row2, textvariable=self._var_max_hora,
                 bg="#16213e", fg=COR_VERDE, insertbackground=COR_TEXTO,
                 font=("Courier New", 10), width=8, relief="flat").pack(side="left", padx=8)

        row3 = tk.Frame(cfg, bg=COR_FUNDO)
        row3.pack(fill="x")
        self._var_publicar = tk.BooleanVar(value=False)
        tk.Checkbutton(row3, text="Publicar diretamente no CMS (além de salvar rascunho local)",
                       variable=self._var_publicar,
                       bg=COR_FUNDO, fg=COR_TEXTO, selectcolor="#1e3a5f",
                       activebackground=COR_FUNDO, activeforeground=COR_TEXTO,
                       font=("Segoe UI", 9)).pack(side="left")

        # ── Log ao vivo ───────────────────────────────────────────────────────
        tk.Label(self, text="Log ao vivo:", bg=COR_FUNDO, fg=COR_CINZA,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=10)
        self._log_txt = scrolledtext.ScrolledText(self, bg="#080818", fg="#94a3b8",
                                                   font=("Courier New", 8),
                                                   state="disabled", wrap="word",
                                                   height=14)
        self._log_txt.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._log_txt.tag_configure("ok",   foreground="#86efac")
        self._log_txt.tag_configure("err",  foreground="#fca5a5")
        self._log_txt.tag_configure("info", foreground="#94a3b8")
        self._log_txt.tag_configure("warn", foreground="#fde68a")

        # Lê log existente
        self.after(200, self._ler_log_arquivo)

    # ── Log ───────────────────────────────────────────────────────────────────

    def _ler_log_arquivo(self):
        """Carrega as últimas linhas do monitor.log."""
        log_path = Path("logs") / "monitor.log"
        if not log_path.exists():
            self._append_log("(nenhum log anterior encontrado)", "info")
            return
        try:
            linhas = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            ultimas = linhas[-60:]  # últimas 60 linhas
            for ln in ultimas:
                tag = "ok" if "[OK]" in ln else ("err" if "ERROR" in ln or "ERRO" in ln
                      else ("warn" if "WARNING" in ln or "AVISO" in ln else "info"))
                self._append_log(ln, tag)
        except Exception as e:
            self._append_log(f"Erro ao ler log: {e}", "err")

    def _append_log(self, texto: str, tag: str = "info"):
        self._log_txt.config(state="normal")
        self._log_txt.insert("end", texto + "\n", tag)
        self._log_txt.see("end")
        self._log_txt.config(state="disabled")

    # ── Controles ─────────────────────────────────────────────────────────────

    def _iniciar(self):
        # v79: o monitor não exige mais OPENAI_API_KEY. Sem cliente, usa fallback local.
        if not self._client:
            self._append_log("[Monitor v79] OPENAI_API_KEY ausente: usando fallback local sem IA.", "warn")
        if self._robo and self._robo.ativo:
            messagebox.showinfo("Monitor", "O monitor já está ativo.", parent=self)
            return
        try:
            intervalo = int(self._var_intervalo.get())
            max_hora  = int(self._var_max_hora.get())
        except ValueError:
            messagebox.showerror("Erro", "Valores inválidos nos campos.", parent=self)
            return
        publicar = self._var_publicar.get()

        from ururau.publisher.monitor import MonitorRobo
        self._robo = MonitorRobo(
            db=self._db,
            client=self._client,
            modelo=self._modelo,
            intervalo_segundos=intervalo,
            max_por_hora=max_hora,
            publicar_no_cms=publicar,
        )
        def _run():
            try:
                self._robo.iniciar()
            except Exception as e:
                msg = str(e)
                self.after(0, lambda msg=msg: self._append_log(f"[ERRO] {msg}", "err"))
            finally:
                self.after(0, self._atualizar_ui)
        self._thread = threading.Thread(target=_run, daemon=True, name="MonitorRobo")
        self._thread.start()
        self._atualizar_ui()
        self._cb_atualizado(self._robo, self._thread)
        self._append_log(
            f"Monitor iniciado. Intervalo={intervalo}s Max/hora={max_hora} "
            f"CMS={'SIM' if publicar else 'NAO'}", "ok")

    def _parar(self):
        if self._robo:
            self._robo.parar()
        self._atualizar_ui()
        self._cb_atualizado(self._robo, self._thread)
        self._append_log("Monitor parado pelo usuário.", "warn")

    def _atualizar_ui(self):
        ativo = bool(self._robo and self._robo.ativo)
        if ativo:
            n = self._robo.publicacoes_na_hora
            self._lbl_status.config(
                text=f"● ATIVO — {n} matéria(s) na última hora",
                fg=COR_VERDE)
            self._btn_start.config(state="disabled")
            self._btn_stop.config(state="normal")
        else:
            self._lbl_status.config(text="● INATIVO", fg=COR_CINZA)
            self._btn_start.config(state="normal")
            self._btn_stop.config(state="disabled")

    def _tick(self):
        """Atualiza UI e log a cada 30s enquanto janela está aberta."""
        try:
            self._atualizar_ui()
            # Appenda novas linhas do log se houver
            log_path = Path("logs") / "monitor.log"
            if log_path.exists():
                try:
                    linhas = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if linhas:
                        self._append_log(linhas[-1], "info")
                except Exception:
                    pass
        except Exception:
            pass
        self.after(30_000, self._tick)


# ── Janela Copydesk Visual ────────────────────────────────────────────────────

class JanelaCopydesk(tk.Toplevel):
    """
    Copydesk visual interativo.

    Mostra lado a lado:
      - Esquerda: texto ORIGINAL (não editável)
      - Direita:  texto PROPOSTO pela IA (editável)

    Lista de problemas detectados no topo.
    Botões: Aceitar Tudo | Aceitar Proposto | Rejeitar | Fechar.

    Diff linha a linha colorido para facilitar revisão.
    """

    # Cores do diff
    _COR_ADD    = "#14532d"   # fundo linha nova (verde escuro)
    _COR_DEL    = "#450a0a"   # fundo linha removida (vermelho escuro)
    _COR_ADD_FG = "#86efac"
    _COR_DEL_FG = "#fca5a5"
    _COR_EQ_FG  = COR_CINZA

    def __init__(self, parent, pauta, md_original, md_proposto, problemas, db, cb_aceitar):
        super().__init__(parent)
        self._pauta      = pauta
        self._md_orig    = dict(md_original)
        self._md_prop    = dict(md_proposto)
        self._probs      = list(problemas)
        self._db         = db
        self._cb_aceitar = cb_aceitar
        titulo_pauta     = (pauta.get("titulo_origem") or "")[:60]
        self.title(f"Copydesk Visual — {titulo_pauta}")
        self.geometry("1300x820")
        self.configure(bg=COR_FUNDO)
        self.grab_set()
        self.resizable(True, True)
        self._build()
        self.after(100, self._preencher_diff)

    def _build(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self, bg=COR_PAINEL, height=50)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="COPYDESK VISUAL", bg=COR_PAINEL, fg=COR_DESTAQUE,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=12)
        for txt, cmd, cor in [
            ("Aceitar Proposto e Salvar", self._aceitar_proposto, COR_VERDE),
            ("Manter Original",           self._manter_original,  COR_CINZA),
            ("Fechar sem salvar",          self.destroy,            "#374151"),
        ]:
            tk.Button(tb, text=txt, command=cmd, bg=cor, fg="white",
                      relief="flat", padx=10, pady=4, cursor="hand2",
                      font=("Helvetica", 9, "bold")).pack(side="right", padx=4, pady=8)

        # ── Problemas detectados ──────────────────────────────────────────────
        pf = tk.Frame(self, bg="#1c1c2e")
        pf.pack(fill="x", padx=8, pady=4)
        lbl_t = ("Sem problemas residuais detectados." if not self._probs
                 else f"{len(self._probs)} problema(s) detectado(s) — revise antes de aceitar:")
        cor_t  = COR_VERDE if not self._probs else COR_AMARELO
        tk.Label(pf, text=lbl_t, bg="#1c1c2e", fg=cor_t,
                 font=("Helvetica", 9, "bold")).pack(anchor="w", padx=8, pady=2)
        for prob in self._probs[:8]:
            tk.Label(pf, text=f"  ▸ {prob}", bg="#1c1c2e", fg=COR_AMARELO,
                     font=("Helvetica", 8), anchor="w").pack(fill="x", padx=12)
        if len(self._probs) > 8:
            tk.Label(pf, text=f"  ... e mais {len(self._probs)-8} problema(s).",
                     bg="#1c1c2e", fg=COR_CINZA, font=("Helvetica", 8)).pack(anchor="w", padx=12)

        # ── Área principal ────────────────────────────────────────────────────
        main = tk.Frame(self, bg=COR_FUNDO)
        main.pack(fill="both", expand=True, padx=8, pady=4)

        # Metadados — comparação
        meta_frame = tk.Frame(main, bg=COR_PAINEL)
        meta_frame.pack(fill="x", pady=(0, 4))
        tk.Label(meta_frame, text="METADADOS (Original → Proposto)",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=("Helvetica", 9, "bold")).pack(
                     anchor="w", padx=8, pady=4)
        self._meta_txt = scrolledtext.ScrolledText(meta_frame, bg="#16213e", fg=COR_TEXTO,
                                                    font=("Courier New", 8), height=7,
                                                    state="disabled", wrap="word")
        self._meta_txt.pack(fill="x", padx=8, pady=2)
        self._meta_txt.tag_configure("add", foreground=self._COR_ADD_FG, background=self._COR_ADD)
        self._meta_txt.tag_configure("del", foreground=self._COR_DEL_FG, background=self._COR_DEL)
        self._meta_txt.tag_configure("eq",  foreground=self._COR_EQ_FG)
        self._meta_txt.tag_configure("lbl", foreground=COR_ROXO, font=("Courier New", 8, "bold"))

        # Conteúdo — diff side-by-side
        paned = ttk.PanedWindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True, pady=4)

        lf = tk.Frame(paned, bg=COR_PAINEL)
        paned.add(lf, weight=1)
        tk.Label(lf, text="ORIGINAL", bg=COR_PAINEL, fg=COR_VERMELHO,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", padx=8, pady=4)
        self._txt_orig = scrolledtext.ScrolledText(lf, bg="#16213e", fg=COR_TEXTO,
                                                    font=("Courier New", 9), wrap="word",
                                                    state="disabled", relief="flat", padx=6, pady=6)
        self._txt_orig.pack(fill="both", expand=True, padx=4, pady=2)
        self._txt_orig.tag_configure("del", foreground=self._COR_DEL_FG, background=self._COR_DEL)
        self._txt_orig.tag_configure("eq",  foreground="#94a3b8")

        rf = tk.Frame(paned, bg=COR_PAINEL)
        paned.add(rf, weight=1)
        tk.Label(rf, text="PROPOSTO (editável)", bg=COR_PAINEL, fg=COR_VERDE,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", padx=8, pady=4)
        self._txt_prop = tk.Text(rf, bg="#16213e", fg=COR_TEXTO,
                                  insertbackground=COR_TEXTO,
                                  font=("Courier New", 9), wrap="word",
                                  relief="flat", padx=6, pady=6, undo=True)
        self._txt_prop.pack(fill="both", expand=True, padx=4, pady=2)
        self._txt_prop.tag_configure("add", foreground=self._COR_ADD_FG, background=self._COR_ADD)
        self._txt_prop.tag_configure("eq",  foreground="#94a3b8")

        # Scrollbar sincronizada (best-effort)
        self._txt_orig.bind("<MouseWheel>", self._sync_scroll_orig)
        self._txt_prop.bind("<MouseWheel>", self._sync_scroll_prop)

        # Contador de chars
        bar = tk.Frame(rf, bg=COR_PAINEL)
        bar.pack(fill="x", padx=4)
        self._lbl_chars = tk.Label(bar, text="", bg=COR_PAINEL,
                                   fg=COR_CINZA, font=FONTE_PEQUENA)
        self._lbl_chars.pack(side="right")
        self._txt_prop.bind("<KeyRelease>", self._contar)

    # ── Preenchimento ─────────────────────────────────────────────────────────

    def _preencher_diff(self):
        """Preenche ambos os painéis com diff colorido."""
        import difflib
        orig_body = self._md_orig.get("conteudo", "")
        prop_body = self._md_prop.get("conteudo", "")

        orig_linhas = orig_body.splitlines()
        prop_linhas = prop_body.splitlines()

        matcher = difflib.SequenceMatcher(None, orig_linhas, prop_linhas, autojunk=False)

        # Painel original
        self._txt_orig.config(state="normal")
        self._txt_orig.delete("1.0", "end")
        # Painel proposto
        self._txt_prop.config(state="normal")
        self._txt_prop.delete("1.0", "end")

        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == "equal":
                for ln in orig_linhas[i1:i2]:
                    self._txt_orig.insert("end", ln + "\n", "eq")
                for ln in prop_linhas[j1:j2]:
                    self._txt_prop.insert("end", ln + "\n", "eq")
            elif opcode == "replace":
                for ln in orig_linhas[i1:i2]:
                    self._txt_orig.insert("end", ln + "\n", "del")
                for ln in prop_linhas[j1:j2]:
                    self._txt_prop.insert("end", ln + "\n", "add")
            elif opcode == "delete":
                for ln in orig_linhas[i1:i2]:
                    self._txt_orig.insert("end", ln + "\n", "del")
            elif opcode == "insert":
                for ln in prop_linhas[j1:j2]:
                    self._txt_prop.insert("end", ln + "\n", "add")

        self._txt_orig.config(state="disabled")
        self._contar()

        # Metadados
        self._meta_txt.config(state="normal")
        self._meta_txt.delete("1.0", "end")
        campos_meta = ["titulo", "titulo_capa", "subtitulo", "legenda",
                       "retranca", "slug", "tags", "meta_description",
                       "resumo_curto", "chamada_social"]
        for campo in campos_meta:
            v_orig = str(self._md_orig.get(campo, "") or "").strip()
            v_prop = str(self._md_prop.get(campo, "") or "").strip()
            self._meta_txt.insert("end", f"{campo:<22}: ", "lbl")
            if v_orig == v_prop:
                self._meta_txt.insert("end", v_orig[:120] + "\n", "eq")
            else:
                self._meta_txt.insert("end", f"[-] {v_orig[:80]}\n", "del")
                self._meta_txt.insert("end", " " * 24 + f"[+] {v_prop[:80]}\n", "add")
        self._meta_txt.config(state="disabled")

    def _contar(self, _=None):
        n = len(self._txt_prop.get("1.0", "end-1c"))
        from ururau.config.settings import MIN_CARACTERES_MATERIA, MAX_CARACTERES_MATERIA
        cor = (COR_VERDE if MIN_CARACTERES_MATERIA <= n <= MAX_CARACTERES_MATERIA
               else COR_AMARELO)
        self._lbl_chars.config(text=f"{n} chars", fg=cor)

    # ── Sync scroll ───────────────────────────────────────────────────────────

    def _sync_scroll_orig(self, e):
        delta = int(-1 * (e.delta / 120))
        self._txt_prop.yview_scroll(delta, "units")

    def _sync_scroll_prop(self, e):
        delta = int(-1 * (e.delta / 120))
        self._txt_orig.yview_scroll(delta, "units")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _aceitar_proposto(self):
        """Aceita o texto proposto (com as edições manuais feitas pelo usuário)."""
        md_final = dict(self._md_prop)
        # Usa o conteúdo do painel editável (pode ter ajustes manuais)
        md_final["conteudo"] = self._txt_prop.get("1.0", "end-1c").strip()
        self._cb_aceitar(self._pauta, md_final, self._probs)
        messagebox.showinfo("Copydesk Aceito",
            f"Revisão salva!\n{len(self._probs)} problema(s) residual(is).",
            parent=self)
        self.destroy()

    def _manter_original(self):
        """Fecha sem salvar nada — mantém o original."""
        if messagebox.askyesno("Manter Original",
                "Fechar sem aplicar o copydesk?\nO texto original será mantido.",
                parent=self):
            self.destroy()


# ── Widget de Configurações (Frame — usado inline no notebook) ────────────────

class _ConfigWidget(tk.Frame):
    """
    Versão Frame (não Toplevel) do painel de configurações.
    Pode ser incorporado diretamente numa aba do notebook.
    """

    def __init__(self, parent, db=None, owner=None):
        super().__init__(parent, bg=COR_FUNDO)
        self._db = db
        self._owner = owner
        self._build()
        self._carregar_valores()

    def _build(self):
        tb = tk.Frame(self, bg=COR_PAINEL, height=44)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="⚙ Configurações", bg=COR_PAINEL, fg=COR_DESTAQUE,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=10)
        tk.Button(tb, text="Salvar e Aplicar", command=self._salvar,
                  bg=COR_VERDE, fg="white", relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  font=("Helvetica", 9, "bold")).pack(side="right", padx=6, pady=6)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=4)
        self._nb = nb
        self._criar_aba_rss(nb)
        self._criar_aba_xml_sitemap(nb)
        self._criar_aba_fontes_especiais_v129(nb)
        self._criar_aba_regionais_v1305(nb)
        self._criar_aba_termos(nb)
        self._criar_aba_params(nb)
        self._criar_aba_creds(nb)
        self._criar_aba_diagnostico_v127(nb)

    def _criar_aba_rss(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="RSS")
        tk.Label(f, text="Formato RSS: cole apenas as URLs. A coluna fixa à esquerda mostra a prioridade. Canal/editoria é definido pelo robô.",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(padx=8, pady=4, anchor="w")
        from ururau.ui.url_priority_grid_v120 import URLPriorityGridV120
        self._txt_rss = URLPriorityGridV120(f, mode="rss", bg="#16213e", fg=COR_TEXTO,
                                   insertbackground=COR_TEXTO,
                                   font=("Courier New", 9), wrap="none",
                                   relief="flat", padx=6, pady=6)
        self._txt_rss.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(f, text="+ Adicionar linha",
                  command=self._txt_rss.add_blank_url_line,
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=8)


    def _criar_aba_xml_sitemap(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="XML/Sitemap")
        tk.Label(f, text="XML/Sitemap: cole sitemaps, uma URL por linha. A coluna fixa à esquerda mostra a prioridade.",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(padx=8, pady=4, anchor="w")
        tk.Label(f, text="Use aqui links como https://campos24horas.com.br/noticia/sitemap.xml. Feeds RSS em XML, como feed.xml/rss.xml, ficam em RSS.",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA, wraplength=760).pack(padx=8, anchor="w")
        from ururau.ui.url_priority_grid_v120 import URLPriorityGridV120
        self._txt_xml = URLPriorityGridV120(f, mode="sitemap", bg="#16213e", fg=COR_TEXTO,
                                            insertbackground=COR_TEXTO,
                                            font=("Courier New", 9), wrap="none",
                                            relief="flat", padx=6, pady=6)
        self._txt_xml.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(f, text="+ Adicionar linha",
                  command=self._txt_xml.add_blank_url_line,
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=8)

    def _criar_aba_fontes_especiais_v129(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Especiais")
        tk.Label(
            f,
            text="Especiais: órgãos e fontes institucionais, uma por linha no formato Nome|URL. Entram em coleta própria e não são bloqueadas por score baixo.",
            bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL, wraplength=880, justify="left"
        ).pack(padx=8, pady=4, anchor="w")
        tk.Label(
            f,
            text="Continuam valendo deduplicação, janela de publicação, link inválido e bloqueio de assets/imagens.",
            bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA, wraplength=880, justify="left"
        ).pack(padx=8, anchor="w")
        self._txt_especiais_v129 = tk.Text(
            f, bg="#16213e", fg=COR_TEXTO, insertbackground=COR_TEXTO,
            font=("Courier New", 9), wrap="none", relief="flat", padx=6, pady=6
        )
        self._txt_especiais_v129.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(
            f, text="+ Adicionar fonte especial",
            command=lambda: self._txt_especiais_v129.insert("end", "\nNova fonte|https://"),
            bg=COR_AZUL, fg="white", relief="flat",
            padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA
        ).pack(side="left", padx=8)


    def _criar_aba_regionais_v1305(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Regionais")
        tk.Label(
            f,
            text="Regionais: sites locais relevantes para Campos/Norte Fluminense. Formato Nome|URL. Usam parser RSS normal, boost regional, cota mínima e não caem facilmente por score baixo.",
            bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL, wraplength=880, justify="left"
        ).pack(padx=8, pady=4, anchor="w")
        tk.Label(
            f,
            text="Não use esta aba para órgãos oficiais. Órgãos oficiais ficam em Especiais. RJ News Notícias não foi incluído como regional por padrão.",
            bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA, wraplength=880, justify="left"
        ).pack(padx=8, anchor="w")
        self._txt_regionais_v1305 = tk.Text(
            f, bg="#16213e", fg=COR_TEXTO, insertbackground=COR_TEXTO,
            font=("Courier New", 9), wrap="none", relief="flat", padx=6, pady=6
        )
        self._txt_regionais_v1305.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(
            f, text="+ Adicionar regional",
            command=lambda: self._txt_regionais_v1305.insert("end", "\nNovo regional|https://"),
            bg=COR_AZUL, fg="white", relief="flat",
            padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA
        ).pack(side="left", padx=8)


    def _criar_aba_termos(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Termos")
        tk.Label(f, text="Formato v111.4: um termo por linha. Ex.: Campos dos Goytacazes",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(padx=8, pady=4, anchor="w")
        tk.Label(f, text="O sistema busca exatamente estes termos. Prioridade/canal são calculados automaticamente pelo motor.",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA).pack(padx=8, anchor="w")
        self._txt_termos = tk.Text(f, bg="#16213e", fg=COR_TEXTO,
                                   insertbackground=COR_TEXTO,
                                   font=("Courier New", 9), wrap="none",
                                   relief="flat", padx=6, pady=6)
        self._txt_termos.pack(fill="both", expand=True, padx=8, pady=8)
        bf = tk.Frame(f, bg=COR_PAINEL)
        bf.pack(fill="x", padx=8, pady=4)
        tk.Button(bf, text="+ Adicionar termo",
                  command=lambda: self._txt_termos.insert("end", "\nNovo termo"),
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left")


    def _criar_aba_diagnostico_v127(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Diagnóstico")
        tk.Label(
            f,
            text="Diagnóstico da última coleta da sessão. Mostra fontes que não enviaram pauta para a fila, sem ocupar espaço na Fila de Pautas.",
            bg=COR_PAINEL,
            fg=COR_TEXTO,
            font=FONTE_NORMAL,
            wraplength=900,
            justify="left",
        ).pack(padx=8, pady=4, anchor="w")

        bf = tk.Frame(f, bg=COR_PAINEL)
        bf.pack(fill="x", padx=8, pady=(0, 4))
        tk.Button(
            bf,
            text="Atualizar diagnóstico",
            command=self._carregar_diagnostico_v127,
            bg=COR_AZUL,
            fg="white",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=FONTE_PEQUENA,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            bf,
            text="Exportar TXT",
            command=self._exportar_diagnostico_v127,
            bg=COR_VERDE,
            fg="white",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=FONTE_PEQUENA,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            bf,
            text="Limpar diagnóstico da sessão",
            command=self._limpar_diagnostico_v127,
            bg="#7f1d1d",
            fg="white",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=FONTE_PEQUENA,
        ).pack(side="left")

        self._txt_diagnostico_v127 = scrolledtext.ScrolledText(
            f,
            bg="#16213e",
            fg=COR_TEXTO,
            insertbackground=COR_TEXTO,
            font=("Courier New", 9),
            wrap="word",
            relief="flat",
            padx=8,
            pady=8,
        )
        self._txt_diagnostico_v127.pack(fill="both", expand=True, padx=8, pady=8)
        self._carregar_diagnostico_v127()

    def _atualizar_diagnostico_v127(self, texto: str, historico=None):
        box = getattr(self, "_txt_diagnostico_v127", None)
        if not box:
            return
        historico = historico or []
        if historico:
            conteudo = "\\n\\n" + ("=" * 80) + "\\n\\n"
            conteudo = conteudo.join(historico[-10:])
        else:
            conteudo = texto or "Ainda não há diagnóstico desta sessão."
        box.config(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", conteudo)
        box.config(state="normal")

    def _carregar_diagnostico_v127(self):
        owner = getattr(self, "_owner", None)
        texto = ""
        hist = []
        if owner is not None:
            texto = getattr(owner, "_diagnostico_coleta_sessao_v127", "") or ""
            hist = getattr(owner, "_diagnostico_coleta_historico_v127", []) or []
        if not texto and not hist:
            texto = "Ainda não há diagnóstico desta sessão. Após clicar em Coletar, o resultado aparecerá aqui."
        self._atualizar_diagnostico_v127(texto, hist)

    def _exportar_diagnostico_v127(self):
        texto = ""
        box = getattr(self, "_txt_diagnostico_v127", None)
        if box:
            texto = box.get("1.0", "end").strip()
        if not texto:
            messagebox.showwarning("Diagnóstico", "Não há diagnóstico para exportar.")
            return
        try:
            import time as _time
            nome = f"diagnostico_coleta_{_time.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
            path = filedialog.asksaveasfilename(
                title="Exportar diagnóstico da coleta",
                defaultextension=".txt",
                initialfile=nome,
                filetypes=[("Texto", "*.txt"), ("Todos os arquivos", "*.*")],
            )
            if not path:
                return
            Path(path).write_text(texto, encoding="utf-8")
            messagebox.showinfo("Diagnóstico", f"Diagnóstico exportado:\\n{path}")
        except Exception as e:
            messagebox.showerror("Erro ao exportar", str(e))

    def _limpar_diagnostico_v127(self):
        owner = getattr(self, "_owner", None)
        if owner is not None:
            owner._diagnostico_coleta_sessao_v127 = ""
            owner._diagnostico_coleta_historico_v127 = []
        self._atualizar_diagnostico_v127("Diagnóstico limpo nesta sessão.", [])


    def _criar_aba_params(self, nb):
        outer = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(outer, text="Parâmetros")
        canvas = tk.Canvas(outer, bg=COR_PAINEL, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame = tk.Frame(canvas, bg=COR_PAINEL)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._param_vars: dict[str, tk.StringVar] = {}
        for key, desc, padrao in [
            ("LIMIAR_RELEVANCIA_PUBLICAR","Relevância mínima (0-100)","28"),
            ("LIMIAR_RISCO_MAXIMO","Risco máximo","70"),
            ("MIN_CARACTERES_MATERIA","Min. caracteres","2000"),
            ("MAX_CARACTERES_MATERIA","Max. caracteres","6200"),
            ("MAX_PUBLICACOES_POR_CICLO","Max. publicações por ciclo","3"),
            ("INTERVALO_ENTRE_CICLOS_SEGUNDOS","Intervalo ciclos (seg)","1800"),
            ("URURAU_V127_BUSCA_TERMOS_ATIVA","Busca por Termos v127 (1/0)","1"),
            ("URURAU_V127_TERMOS_JANELA_HORAS","Termos v127: janela horas","24"),
            ("URURAU_V127_TERMOS_MAX_POR_TERMO","Termos v127: max por termo","4"),
            ("URURAU_V108_GNEWS_TERMOS","Google News por Termos legado (1/0)","1"),
            ("URURAU_V108_GNEWS_MAX_TERMOS_POR_CICLO","GNews: max termos por ciclo","20"),
            ("URURAU_V108_GNEWS_MAX_RESULTADOS_POR_TERMO","GNews: max resultados por termo","3"),
            ("URURAU_V108_GNEWS_MIN_PESO_TERMO","GNews: peso mínimo do termo","18"),
            ("URURAU_V108_USAR_TRAFILATURA_FALLBACK","Fallback trafilatura/readability (1/0)","1"),
            ("URURAU_V108_MIN_TEXTO_FONTE_OK","Fonte OK: mínimo caracteres úteis","1200"),
            ("HEADLESS","Headless (true/false)","false"),
        ]:
            row = tk.Frame(frame, bg=COR_PAINEL)
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=desc+":", bg=COR_PAINEL, fg=COR_TEXTO,
                     font=FONTE_PEQUENA, width=42, anchor="w").pack(side="left")
            v = tk.StringVar(value=padrao)
            tk.Entry(row, textvariable=v, bg="#16213e", fg=COR_VERDE,
                     insertbackground=COR_TEXTO, font=("Courier New", 9),
                     width=20, relief="flat").pack(side="left", padx=6)
            self._param_vars[key] = v

    def _criar_aba_creds(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Credenciais")
        tk.Label(f, text="Não compartilhe o .env. Dados ficam apenas localmente.",
                 bg=COR_PAINEL, fg=COR_AMARELO, font=FONTE_PEQUENA).pack(padx=10, pady=6, anchor="w")
        self._cred_vars: dict[str, tk.StringVar] = {}
        for key, label, senha in [
            ("OPENAI_API_KEY","Chave OpenAI (sk-...)",False),
            ("URURAU_LOGIN","Login do CMS",False),
            ("URURAU_SENHA","Senha do CMS",True),
            ("URURAU_ASSINATURA","Assinatura das matérias",False),
            ("SITE_LOGIN_URL","URL de login do CMS",False),
            ("SITE_NOVA_URL","URL de nova notícia",False),
        ]:
            tk.Label(f, text=label+":", bg=COR_PAINEL, fg=COR_TEXTO,
                     font=FONTE_NORMAL, anchor="w").pack(padx=10, pady=3, anchor="w")
            v = tk.StringVar()
            tk.Entry(f, textvariable=v, bg="#16213e", fg=COR_VERDE,
                     insertbackground=COR_TEXTO, font=("Courier New", 9),
                     relief="flat", show="*" if senha else "").pack(fill="x", padx=10)
            self._cred_vars[key] = v

    def _carregar_valores(self):
        env = _ler_env_atual()
        for key, v in {**self._param_vars, **self._cred_vars}.items():
            if key in env:
                v.set(env[key])
        fontes = _carregar_fontes_rss()
        try:
            self._txt_rss.insert("1.0", "\n".join(f.get("url", "") for f in fontes))
        except Exception:
            self._txt_rss.insert("1.0", "\n".join(f.get("url", "") for f in fontes))
        if hasattr(self, "_txt_xml"):
            try:
                p_xml = Path("fontes_xml_sitemap_vfinal.txt")
                if p_xml.exists():
                    self._txt_xml.insert("1.0", p_xml.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
        if hasattr(self, "_txt_especiais_v129"):
            self._txt_especiais_v129.insert("1.0", _carregar_fontes_especiais_v129_texto())
        if hasattr(self, "_txt_regionais_v1305"):
            self._txt_regionais_v1305.insert("1.0", _carregar_regionais_v1305_texto())
        if hasattr(self, "_txt_termos"):
            self._txt_termos.insert("1.0", _carregar_termos_v98_texto())

    def _salvar(self):
        try:
            novos: dict[str, str] = {}
            for k, v in {**self._param_vars, **self._cred_vars}.items():
                val = v.get().strip()
                if val:
                    novos[k] = val
            _atualizar_env(novos)
            from ururau.config.fontes_config_url_simples_v120 import fontes_para_json, sitemap_para_lista
            fontes, xmls_colados_no_rss = fontes_para_json(self._txt_rss.get("1.0", "end"))
            xmls_config = sitemap_para_lista(self._txt_xml.get("1.0", "end")) if hasattr(self, "_txt_xml") else []
            xmls = []
            vistos_xml = set()
            for x in list(xmls_config) + list(xmls_colados_no_rss):
                if x and x not in vistos_xml:
                    xmls.append(x)
                    vistos_xml.add(x)
            p_xml = Path("fontes_xml_sitemap_vfinal.txt")
            p_xml.write_text("\n".join(xmls) + ("\n" if xmls else ""), encoding="utf-8")
            print(f"[CONFIG v120] XML/Sitemap salvo: {len(xmls)} link(s)")
            qtd_especiais_v129 = 0
            if hasattr(self, "_txt_especiais_v129"):
                qtd_especiais_v129 = _salvar_fontes_especiais_v129_texto(self._txt_especiais_v129.get("1.0", "end"))
                print(f"[CONFIG v129] especiais salvos: {qtd_especiais_v129} item(ns)")
            qtd_regionais_v1305 = 0
            if hasattr(self, "_txt_regionais_v1305"):
                qtd_regionais_v1305 = _salvar_regionais_v1305_texto(self._txt_regionais_v1305.get("1.0", "end"))
                print(f"[CONFIG v130.5] regionais salvos: {qtd_regionais_v1305} item(ns)")
            fontes, removidas_especiais_rss_v129_1 = _filtrar_fontes_rss_sem_especiais_v129_1(fontes)
            fontes, removidas_regionais_rss_v1305 = _filtrar_fontes_rss_sem_regionais_v1305(fontes)
            Path("fontes_rss.json").write_text(
                json.dumps(fontes, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[CONFIG v130.5] RSS salvo sem duplicar Especiais/Regionais: {len(fontes)} item(ns); removidas_especiais={len(removidas_especiais_rss_v129_1)}; removidas_regionais={len(removidas_regionais_rss_v1305)}")
            self._txt_rss.delete("1.0", "end")
            self._txt_rss.insert("1.0", "\n".join(f["url"] for f in fontes))
            if hasattr(self, "_txt_xml"):
                self._txt_xml.delete("1.0", "end")
                self._txt_xml.insert("1.0", "\n".join(xmls))
            qtd_termos = 0
            if hasattr(self, "_txt_termos"):
                qtd_termos = _salvar_termos_v98_texto(self._txt_termos.get("1.0", "end"))
                print(f"[CONFIG v100] termos_watchlist_v98.json salvo: {qtd_termos} termo(s)")
            try:
                from ururau.config import settings as _s
                _s.recarregar()
            except Exception:
                pass
            messagebox.showinfo("Salvo",
                f"{len(novos)} parâmetros no .env\n{len(fontes)} fontes RSS\n{len(xmls)} XML/Sitemap\n{qtd_especiais_v129} fontes especiais\n{qtd_termos} termos de watchlist/busca")
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", str(e))


# ── Janela Configurações ──────────────────────────────────────────────────────

class JanelaConfiguracoes(tk.Toplevel):
    """
    4 abas: Fontes RSS | Parametros | Credenciais | Producao
    A aba Producao permite editar briefing editorial, instrucoes por canal,
    termos proibidos de IA e parametros de formato — tudo integrado ao
    house_style.py e aplicado imediatamente em memoria.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configuracoes do Ururau")
        self.geometry("940x740")
        self.configure(bg=COR_FUNDO)
        self.grab_set()
        self.resizable(True, True)
        self._build()
        self._carregar_valores()

    def _build(self):
        tb = tk.Frame(self, bg=COR_PAINEL, height=48)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="Configuracoes", bg=COR_PAINEL, fg=COR_DESTAQUE,
                 font=("Helvetica", 13, "bold")).pack(side="left", padx=12)
        tk.Button(tb, text="Salvar e Aplicar", command=self._salvar,
                  bg=COR_VERDE, fg="white", relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  font=("Helvetica", 10, "bold")).pack(side="right", padx=8, pady=8)
        tk.Button(tb, text="Fechar sem salvar", command=self.destroy,
                  bg=COR_CINZA, fg="white", relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  font=("Helvetica", 10, "bold")).pack(side="right", padx=4, pady=8)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._nb = nb
        self._criar_aba_rss(nb)
        self._criar_aba_xml_sitemap(nb)
        self._criar_aba_fontes_especiais_v129(nb)
        self._criar_aba_regionais_v1305(nb)
        self._criar_aba_termos(nb)
        self._criar_aba_params(nb)
        self._criar_aba_creds(nb)
        self._criar_aba_producao(nb)
        self._criar_aba_estilo(nb)
        tk.Label(self,
                 text="Parametros: aplicados imediatamente. "
                      "Credenciais: proximo reinicio. "
                      "Producao: salva em house_style.py e aplica imediatamente.",
                 bg=COR_FUNDO, fg=COR_AMARELO, font=FONTE_PEQUENA,
                 wraplength=900).pack(pady=4, padx=8)

    # ── RSS ───────────────────────────────────────────────────────────────────

    def _criar_aba_rss(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="RSS")
        tk.Label(f, text="Formato RSS: cole apenas as URLs. A coluna fixa à esquerda mostra a prioridade. Canal/editoria é definido pelo robô.",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(padx=8, pady=4, anchor="w")
        tk.Label(f, text="Ex: https://g1.globo.com/rss/g1/rio-de-janeiro/  (sem Nome|Canal)",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA).pack(padx=8, anchor="w")
        from ururau.ui.url_priority_grid_v120 import URLPriorityGridV120
        self._txt_rss = URLPriorityGridV120(f, mode="rss", bg="#16213e", fg=COR_TEXTO,
                                   insertbackground=COR_TEXTO,
                                   font=("Courier New", 9), wrap="none",
                                   relief="flat", padx=6, pady=6)
        self._txt_rss.pack(fill="both", expand=True, padx=8, pady=8)
        bf = tk.Frame(f, bg=COR_PAINEL)
        bf.pack(fill="x", padx=8, pady=4)
        tk.Button(bf, text="+ Adicionar linha",
                  command=self._txt_rss.add_blank_url_line,
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left")
        tk.Label(bf,
                 text="A editoria NÃO vem da fonte. O robô classifica pelo título/texto da matéria.",
                 bg=COR_PAINEL, fg=COR_CINZA,
                 font=FONTE_PEQUENA, wraplength=720).pack(side="left", padx=8)

    # ── Parâmetros ────────────────────────────────────────────────────────────


    def _criar_aba_xml_sitemap(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="XML/Sitemap")
        tk.Label(f, text="XML/Sitemap: cole sitemaps, uma URL por linha. A coluna fixa à esquerda mostra a prioridade.",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(padx=8, pady=4, anchor="w")
        tk.Label(f, text="Use aqui links como https://campos24horas.com.br/noticia/sitemap.xml. Feeds RSS em XML, como feed.xml/rss.xml, ficam em RSS.",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA, wraplength=760).pack(padx=8, anchor="w")
        from ururau.ui.url_priority_grid_v120 import URLPriorityGridV120
        self._txt_xml = URLPriorityGridV120(f, mode="sitemap", bg="#16213e", fg=COR_TEXTO,
                                            insertbackground=COR_TEXTO,
                                            font=("Courier New", 9), wrap="none",
                                            relief="flat", padx=6, pady=6)
        self._txt_xml.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(f, text="+ Adicionar linha",
                  command=self._txt_xml.add_blank_url_line,
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=8)

    def _criar_aba_fontes_especiais_v129(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Especiais")
        tk.Label(
            f,
            text="Especiais: órgãos e fontes institucionais, uma por linha no formato Nome|URL. Entram em coleta própria e não são bloqueadas por score baixo.",
            bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL, wraplength=880, justify="left"
        ).pack(padx=8, pady=4, anchor="w")
        tk.Label(
            f,
            text="Continuam valendo deduplicação, janela de publicação, link inválido e bloqueio de assets/imagens.",
            bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA, wraplength=880, justify="left"
        ).pack(padx=8, anchor="w")
        self._txt_especiais_v129 = tk.Text(
            f, bg="#16213e", fg=COR_TEXTO, insertbackground=COR_TEXTO,
            font=("Courier New", 9), wrap="none", relief="flat", padx=6, pady=6
        )
        self._txt_especiais_v129.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Button(
            f, text="+ Adicionar fonte especial",
            command=lambda: self._txt_especiais_v129.insert("end", "\nNova fonte|https://"),
            bg=COR_AZUL, fg="white", relief="flat",
            padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA
        ).pack(side="left", padx=8)


    def _criar_aba_termos(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Termos")
        tk.Label(f, text="Formato v111.4: um termo por linha. Ex.: Campos dos Goytacazes",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(padx=8, pady=4, anchor="w")
        tk.Label(f, text="Usado em três pontos: consultas de busca, watchlist editorial e aumento de score na fila.",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA).pack(padx=8, anchor="w")
        self._txt_termos = tk.Text(f, bg="#16213e", fg=COR_TEXTO,
                                   insertbackground=COR_TEXTO,
                                   font=("Courier New", 9), wrap="none",
                                   relief="flat", padx=6, pady=6)
        self._txt_termos.pack(fill="both", expand=True, padx=8, pady=8)
        bf = tk.Frame(f, bg=COR_PAINEL)
        bf.pack(fill="x", padx=8, pady=4)
        tk.Button(bf, text="+ Adicionar termo",
                  command=lambda: self._txt_termos.insert("end", "\nNovo termo"),
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left")


    def _criar_aba_diagnostico_v127(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Diagnóstico")
        tk.Label(
            f,
            text="Diagnóstico da última coleta da sessão. Mostra fontes que não enviaram pauta para a fila, sem ocupar espaço na Fila de Pautas.",
            bg=COR_PAINEL,
            fg=COR_TEXTO,
            font=FONTE_NORMAL,
            wraplength=900,
            justify="left",
        ).pack(padx=8, pady=4, anchor="w")

        bf = tk.Frame(f, bg=COR_PAINEL)
        bf.pack(fill="x", padx=8, pady=(0, 4))
        tk.Button(
            bf,
            text="Atualizar diagnóstico",
            command=self._carregar_diagnostico_v127,
            bg=COR_AZUL,
            fg="white",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=FONTE_PEQUENA,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            bf,
            text="Exportar TXT",
            command=self._exportar_diagnostico_v127,
            bg=COR_VERDE,
            fg="white",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=FONTE_PEQUENA,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            bf,
            text="Limpar diagnóstico da sessão",
            command=self._limpar_diagnostico_v127,
            bg="#7f1d1d",
            fg="white",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=FONTE_PEQUENA,
        ).pack(side="left")

        self._txt_diagnostico_v127 = scrolledtext.ScrolledText(
            f,
            bg="#16213e",
            fg=COR_TEXTO,
            insertbackground=COR_TEXTO,
            font=("Courier New", 9),
            wrap="word",
            relief="flat",
            padx=8,
            pady=8,
        )
        self._txt_diagnostico_v127.pack(fill="both", expand=True, padx=8, pady=8)
        self._carregar_diagnostico_v127()

    def _atualizar_diagnostico_v127(self, texto: str, historico=None):
        box = getattr(self, "_txt_diagnostico_v127", None)
        if not box:
            return
        historico = historico or []
        if historico:
            conteudo = "\\n\\n" + ("=" * 80) + "\\n\\n"
            conteudo = conteudo.join(historico[-10:])
        else:
            conteudo = texto or "Ainda não há diagnóstico desta sessão."
        box.config(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", conteudo)
        box.config(state="normal")

    def _carregar_diagnostico_v127(self):
        owner = getattr(self, "_owner", None)
        texto = ""
        hist = []
        if owner is not None:
            texto = getattr(owner, "_diagnostico_coleta_sessao_v127", "") or ""
            hist = getattr(owner, "_diagnostico_coleta_historico_v127", []) or []
        if not texto and not hist:
            texto = "Ainda não há diagnóstico desta sessão. Após clicar em Coletar, o resultado aparecerá aqui."
        self._atualizar_diagnostico_v127(texto, hist)

    def _exportar_diagnostico_v127(self):
        texto = ""
        box = getattr(self, "_txt_diagnostico_v127", None)
        if box:
            texto = box.get("1.0", "end").strip()
        if not texto:
            messagebox.showwarning("Diagnóstico", "Não há diagnóstico para exportar.")
            return
        try:
            import time as _time
            nome = f"diagnostico_coleta_{_time.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
            path = filedialog.asksaveasfilename(
                title="Exportar diagnóstico da coleta",
                defaultextension=".txt",
                initialfile=nome,
                filetypes=[("Texto", "*.txt"), ("Todos os arquivos", "*.*")],
            )
            if not path:
                return
            Path(path).write_text(texto, encoding="utf-8")
            messagebox.showinfo("Diagnóstico", f"Diagnóstico exportado:\\n{path}")
        except Exception as e:
            messagebox.showerror("Erro ao exportar", str(e))

    def _limpar_diagnostico_v127(self):
        owner = getattr(self, "_owner", None)
        if owner is not None:
            owner._diagnostico_coleta_sessao_v127 = ""
            owner._diagnostico_coleta_historico_v127 = []
        self._atualizar_diagnostico_v127("Diagnóstico limpo nesta sessão.", [])


    def _criar_aba_params(self, nb):
        outer = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(outer, text="Parametros")
        canvas = tk.Canvas(outer, bg=COR_PAINEL, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame = tk.Frame(canvas, bg=COR_PAINEL)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._param_vars: dict[str, tk.StringVar] = {}
        grupos = [
            ("Limiares Editoriais", [
                ("LIMIAR_RELEVANCIA_PUBLICAR","Relevancia minima para publicar (0-100)","28"),
                ("LIMIAR_RELEVANCIA_URGENTE", "Limiar para pauta urgente (0-100)","52"),
                ("LIMIAR_RISCO_MAXIMO",       "Risco maximo (bloqueia acima)","70"),
            ]),
            ("Texto e Conteudo", [
                ("OPENAI_MODEL",            "Modelo de IA","gpt-4.1-mini"),
                ("MIN_CARACTERES_MATERIA",  "Min. caracteres","2000"),
                ("ALVO_CARACTERES_MATERIA", "Alvo de caracteres","3400"),
                ("MAX_CARACTERES_MATERIA",  "Max. caracteres","6200"),
                ("MAX_FONTES_APURACAO",     "Max. fontes por apuracao","4"),
            ]),
            ("Imagem", [
                ("QUALIDADE_JPEG_FINAL",          "Qualidade JPEG (1-95)","95"),
                ("MIN_LARGURA_IMAGEM_PUBLICAVEL", "Largura minima (px)","500"),
                ("MIN_ALTURA_IMAGEM_PUBLICAVEL",  "Altura minima (px)","350"),
                ("USAR_PLAYWRIGHT_IMAGEM",        "Usar Playwright (true/false)","true"),
                ("USAR_BING_IMAGEM",              "Usar Bing fallback (true/false)","true"),
                ("MAX_CANDIDATAS_IMAGEM",         "Max. candidatas de imagem","25"),
            ]),
            ("Publicacao e Ciclos", [
                ("MAX_PUBLICACOES_POR_CICLO",       "Max. publicacoes por ciclo","3"),
                ("MAX_PUBLICACOES_POR_CANAL",       "Max. por canal por ciclo","1"),
                ("INTERVALO_ENTRE_CICLOS_SEGUNDOS", "Intervalo ciclos (seg)","1800"),
                ("JANELA_ANTIDUPLICACAO_HORAS",     "Janela anti-duplicacao (h)","48"),
                ("URURAU_V100_JANELA_PUBLICACAO_HORAS","Janela de publicacao para fila (h)","4"),
                ("URURAU_V100_REJEITAR_SEM_DATA_PUBLICACAO","Rejeitar pauta sem data (1/0)","1"),
                ("URURAU_V92_SCORE_MINIMO_LISTA",     "Score minimo para listar","55"),
                ("URURAU_V92_MAX_SALVAR_RAPIDO",      "Max. pautas na coleta rapida","40"),
                ("URURAU_V92_MAX_POR_FONTE",          "Max. pautas por fonte","6"),
                ("MAX_CANDIDATAS_AVALIADAS",        "Max. candidatas avaliadas por ciclo","24"),
            ]),
            ("Google News e Fonte v108", [
                ("URURAU_V108_GNEWS_TERMOS", "Google News por Termos (1/0)","1"),
                ("URURAU_V108_GNEWS_JANELA_HORAS", "Janela Google News por termos (h)","4"),
                ("URURAU_V108_GNEWS_MAX_TERMOS_POR_CICLO", "Max. termos por ciclo","20"),
                ("URURAU_V108_GNEWS_MAX_RESULTADOS_POR_TERMO", "Max. resultados por termo","3"),
                ("URURAU_V108_GNEWS_MIN_PESO_TERMO", "Peso mínimo para buscar termo","18"),
                ("URURAU_V108_USAR_TRAFILATURA_FALLBACK", "Usar trafilatura/readability (1/0)","1"),
                ("URURAU_V108_MIN_TEXTO_FONTE_OK", "Fonte OK: mínimo caracteres úteis","1200"),
            ]),
            ("Playwright", [
                ("HEADLESS","Rodar sem janela visivel (true/false)","false"),
                ("SLOW_MO", "Delay entre acoes Playwright (ms)","150"),
            ]),
        ]
        for titulo_g, params in grupos:
            tk.Label(frame, text=titulo_g, bg=COR_PAINEL, fg=COR_ROXO,
                     font=("Helvetica", 11, "bold")).pack(anchor="w", padx=12, pady=8)
            for key, desc, padrao in params:
                row = tk.Frame(frame, bg=COR_PAINEL)
                row.pack(fill="x", padx=12, pady=2)
                tk.Label(row, text=desc, bg=COR_PAINEL, fg=COR_TEXTO,
                         font=FONTE_PEQUENA, width=48, anchor="w").pack(side="left")
                v = tk.StringVar(value=padrao)
                tk.Entry(row, textvariable=v, bg="#16213e", fg=COR_VERDE,
                         insertbackground=COR_TEXTO, font=("Courier New", 9),
                         width=22, relief="flat").pack(side="left", padx=8)
                self._param_vars[key] = v
            tk.Frame(frame, bg="#3a3a5c", height=1).pack(fill="x", padx=12, pady=4)

    # ── Credenciais ───────────────────────────────────────────────────────────

    def _criar_aba_creds(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Credenciais")
        tk.Label(f, text="Nao compartilhe o .env. Dados ficam apenas localmente.",
                 bg=COR_PAINEL, fg=COR_AMARELO, font=FONTE_PEQUENA).pack(padx=12, pady=8, anchor="w")
        self._cred_vars: dict[str, tk.StringVar] = {}
        for key, label, senha in [
            ("OPENAI_API_KEY",   "Chave da OpenAI (sk-...)",   False),
            ("URURAU_LOGIN",     "Login do CMS Ururau",        False),
            ("URURAU_SENHA",     "Senha do CMS Ururau",        True),
            ("URURAU_ASSINATURA","Assinatura das materias",    False),
            ("SITE_LOGIN_URL",   "URL de login do CMS",        False),
            ("SITE_NOVA_URL",    "URL de nova noticia no CMS", False),
        ]:
            tk.Label(f, text=label+":", bg=COR_PAINEL, fg=COR_TEXTO,
                     font=FONTE_NORMAL, anchor="w").pack(padx=12, pady=4, anchor="w")
            v = tk.StringVar()
            tk.Entry(f, textvariable=v, bg="#16213e", fg=COR_VERDE,
                     insertbackground=COR_TEXTO, font=("Courier New", 10),
                     relief="flat", show="*" if senha else "").pack(fill="x", padx=12)
            self._cred_vars[key] = v

    # ── Produção ──────────────────────────────────────────────────────────────

    def _criar_aba_producao(self, nb):
        """
        Aba Producao: sub-abas para editar todos os parametros de producao
        de texto: Briefing Editorial, Instrucoes por Canal, Termos Proibidos,
        Formato e Estrutura. Tudo integrado ao house_style.py.
        """
        outer = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(outer, text="Producao")
        sub = ttk.Notebook(outer)
        sub.pack(fill="both", expand=True, padx=4, pady=4)
        self._prod_txt: dict[str, tk.Text] = {}

        # Sub-aba: Briefing Editorial
        self._criar_sub_txt(sub, "Briefing Editorial", "briefing",
            "Briefing injetado em TODOS os prompts de geracao.\n"
            "Define tom, regras e proibicoes para toda a producao de texto.")

        # Sub-aba: Por Canal
        fc = tk.Frame(sub, bg=COR_PAINEL)
        sub.add(fc, text="Por Canal")
        tk.Label(fc, text="Instrucao editorial especifica para cada canal:",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_PEQUENA).pack(anchor="w", padx=8, pady=4)
        cr = tk.Frame(fc, bg=COR_PAINEL)
        cr.pack(fill="x", padx=8, pady=2)
        self._canal_var = tk.StringVar(value=CANAIS_RODIZIO[0])
        ttk.Combobox(cr, textvariable=self._canal_var,
                     values=CANAIS_RODIZIO, state="readonly",
                     width=24).pack(side="left")
        tk.Button(cr, text="Carregar", command=self._load_canal,
                  bg=COR_AZUL, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=6)
        tk.Button(cr, text="Salvar este canal", command=self._save_canal,
                  bg=COR_VERDE, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=2)
        tk.Button(cr, text="+ Novo canal", command=self._novo_canal,
                  bg=COR_ROXO, fg="white", relief="flat",
                  padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=2)
        tk.Label(fc, text="Instrucao (injetada no prompt para este canal):",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA).pack(anchor="w", padx=8, pady=2)
        self._txt_canal = tk.Text(fc, bg="#16213e", fg=COR_TEXTO,
                                  insertbackground=COR_TEXTO,
                                  font=("Courier New", 9), wrap="word",
                                  relief="flat", padx=6, pady=6, height=10)
        self._txt_canal.pack(fill="both", expand=True, padx=8, pady=4)
        self._load_canal()

        # Sub-aba: Termos Proibidos
        self._criar_sub_txt(sub, "Termos Proibidos", "termos_ia",
            "Um termo por linha (minusculas).\n"
            "Detectados automaticamente no texto gerado e sinalizados para revisao.")

        # Sub-aba: Formato e Estrutura
        ff = tk.Frame(sub, bg=COR_PAINEL)
        sub.add(ff, text="Formato e Estrutura")
        tk.Label(ff, text="Parametros de formato e estrutura do texto gerado:",
                 bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL).pack(anchor="w", padx=12, pady=8)
        self._fmt_vars: dict[str, tk.StringVar] = {}
        for key, desc, pad in [
            ("URURAU_ASSINATURA",    "Assinatura padrao das materias",   "Fabricio Freitas"),
            ("MIN_CARACTERES_MATERIA","Minimo de caracteres por materia","2000"),
            ("ALVO_CARACTERES_MATERIA","Alvo de caracteres por materia", "3400"),
            ("MAX_CARACTERES_MATERIA", "Maximo de caracteres por materia","6200"),
            ("MAX_FONTES_APURACAO",    "Max. fontes citadas por apuracao","4"),
        ]:
            row = tk.Frame(ff, bg=COR_PAINEL)
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=desc+":", bg=COR_PAINEL, fg=COR_TEXTO,
                     font=FONTE_PEQUENA, width=42, anchor="w").pack(side="left")
            v = tk.StringVar(value=pad)
            tk.Entry(row, textvariable=v, bg="#16213e", fg=COR_VERDE,
                     insertbackground=COR_TEXTO, font=("Courier New", 9),
                     width=26, relief="flat").pack(side="left", padx=8)
            self._fmt_vars[key] = v

        tk.Label(ff,
                 text="Instrucao adicional global (adicionada ao final de todo prompt de geracao):",
                 bg=COR_PAINEL, fg=COR_CINZA,
                 font=FONTE_PEQUENA).pack(anchor="w", padx=12, pady=(12, 2))
        self._txt_extra = tk.Text(ff, bg="#16213e", fg=COR_TEXTO,
                                  insertbackground=COR_TEXTO,
                                  font=("Courier New", 9), wrap="word",
                                  relief="flat", padx=6, pady=6, height=6)
        self._txt_extra.pack(fill="both", expand=True, padx=12, pady=4)

    def _criar_aba_estilo(self, nb):
        """
        Aba Estilo de Escrita: criterios editoriais personalizados.

        Permite ao editor:
        1. Escrever diretrizes positivas (como deve ser escrito)
        2. Escrever exclusões (formas que não deve usar)
        3. Exemplos de parágrafos de referência

        Tudo injetado no prompt de redação como instrução adicional.
        """
        outer = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(outer, text="✍ Estilo de Escrita")

        # Cabeçalho explicativo
        tk.Label(outer,
                 text="Diretrizes personalizadas de estilo — injetadas em todo prompt de geração de matéria.\n"
                      "Escreva como se estivesse instruindo um repórter: o que fazer, o que evitar, exemplos.",
                 bg=COR_PAINEL, fg=COR_AMARELO, font=FONTE_PEQUENA,
                 wraplength=860, justify="left").pack(anchor="w", padx=12, pady=(8, 4))

        sub = ttk.Notebook(outer)
        sub.pack(fill="both", expand=True, padx=4, pady=4)

        # Sub-aba 1: Diretrizes positivas
        f1 = tk.Frame(sub, bg=COR_PAINEL)
        sub.add(f1, text="Diretrizes (o que fazer)")
        tk.Label(f1,
                 text="Descreva o estilo desejado. Ex: 'Use sempre o nome completo na primeira menção.'\n"
                      "'Priorize verbos no passado para fatos confirmados.' Uma instrução por linha.",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA,
                 wraplength=840, justify="left").pack(anchor="w", padx=8, pady=4)
        self._txt_estilo_positivo = tk.Text(f1, bg="#16213e", fg="#86efac",
                                             insertbackground=COR_TEXTO,
                                             font=("Courier New", 9), wrap="word",
                                             relief="flat", padx=6, pady=6)
        self._txt_estilo_positivo.pack(fill="both", expand=True, padx=8, pady=4)

        # Sub-aba 2: Exclusões e proibições
        f2 = tk.Frame(sub, bg=COR_PAINEL)
        sub.add(f2, text="Exclusões (o que evitar)")
        tk.Label(f2,
                 text="Formas de escrita que você considera ruins ou inadequadas para o portal.\n"
                      "Ex: 'Não abra matéria com pergunta retórica.' 'Evite lide com mais de 3 linhas.'",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA,
                 wraplength=840, justify="left").pack(anchor="w", padx=8, pady=4)
        self._txt_estilo_negativo = tk.Text(f2, bg="#16213e", fg="#fca5a5",
                                             insertbackground=COR_TEXTO,
                                             font=("Courier New", 9), wrap="word",
                                             relief="flat", padx=6, pady=6)
        self._txt_estilo_negativo.pack(fill="both", expand=True, padx=8, pady=4)

        # Sub-aba 3: Exemplos de referência
        f3 = tk.Frame(sub, bg=COR_PAINEL)
        sub.add(f3, text="Exemplos de Referência")
        tk.Label(f3,
                 text="Cole aqui parágrafos de matérias que considera bem escritas.\n"
                      "A IA usará como referência de tom e ritmo — não como conteúdo a copiar.",
                 bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA,
                 wraplength=840, justify="left").pack(anchor="w", padx=8, pady=4)
        self._txt_estilo_exemplos = tk.Text(f3, bg="#16213e", fg="#93c5fd",
                                             insertbackground=COR_TEXTO,
                                             font=("Courier New", 9), wrap="word",
                                             relief="flat", padx=6, pady=6)
        self._txt_estilo_exemplos.pack(fill="both", expand=True, padx=8, pady=4)

        # Botão de ajuda
        tk.Label(outer,
                 text="💡 Dica: Quanto mais específicas e concretas as diretrizes, melhor o resultado. "
                      "Evite instruções vagas como 'escreva bem'. Prefira: 'Use vírgula antes de 'mas' quando a oração for longa.'",
                 bg=COR_PAINEL, fg=COR_CINZA,
                 font=("Helvetica", 7), wraplength=860, justify="left").pack(anchor="w", padx=12, pady=4)

    def _criar_sub_txt(self, nb, titulo, chave, desc):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text=titulo)
        tk.Label(f, text=desc, bg=COR_PAINEL, fg=COR_CINZA,
                 font=FONTE_PEQUENA, wraplength=860,
                 justify="left").pack(anchor="w", padx=8, pady=4)
        txt = tk.Text(f, bg="#16213e", fg=COR_TEXTO,
                      insertbackground=COR_TEXTO,
                      font=("Courier New", 9), wrap="word",
                      relief="flat", padx=6, pady=6)
        txt.pack(fill="both", expand=True, padx=8, pady=4)
        self._prod_txt[chave] = txt

    def _load_canal(self, _=None):
        canal = self._canal_var.get()
        try:
            from ururau.config.house_style import INSTRUCAO_POR_CANAL
            instrucao = INSTRUCAO_POR_CANAL.get(canal, "")
        except Exception:
            instrucao = ""
        self._txt_canal.delete("1.0", "end")
        self._txt_canal.insert("1.0", instrucao)

    def _save_canal(self):
        canal    = self._canal_var.get()
        instrucao = self._txt_canal.get("1.0", "end").strip()
        try:
            from ururau.config import house_style as hs
            hs.INSTRUCAO_POR_CANAL[canal] = instrucao
            messagebox.showinfo("Salvo",
                f"Canal '{canal}' atualizado em memoria.\n"
                "Clique 'Salvar e Aplicar' para persistir no arquivo.", parent=self)
        except Exception as e:
            messagebox.showerror("Erro", str(e), parent=self)

    def _novo_canal(self):
        nome = simpledialog.askstring("Novo Canal", "Nome do canal:", parent=self)
        if not nome:
            return
        nome = nome.strip()
        try:
            from ururau.config import house_style as hs
            if nome not in hs.INSTRUCAO_POR_CANAL:
                hs.INSTRUCAO_POR_CANAL[nome] = "Escreva em formato de noticia jornalistica objetiva."
            self._canal_var.set(nome)
            self._load_canal()
            messagebox.showinfo("Canal criado",
                f"Canal '{nome}' criado. Clique 'Salvar e Aplicar' para persistir.",
                parent=self)
        except Exception as e:
            messagebox.showerror("Erro", str(e), parent=self)

    # ── Carregar valores ──────────────────────────────────────────────────────

    def _carregar_valores(self):
        env = _ler_env_atual()
        for key, v in {**self._param_vars, **self._cred_vars, **self._fmt_vars}.items():
            if key in env:
                v.set(env[key])
        fontes = _carregar_fontes_rss()
        try:
            self._txt_rss.insert("1.0", "\n".join(f.get("url", "") for f in fontes))
        except Exception:
            self._txt_rss.insert("1.0", "\n".join(f.get("url", "") for f in fontes))
        if hasattr(self, "_txt_xml"):
            try:
                p_xml = Path("fontes_xml_sitemap_vfinal.txt")
                if p_xml.exists():
                    self._txt_xml.insert("1.0", p_xml.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
        if hasattr(self, "_txt_especiais_v129"):
            self._txt_especiais_v129.insert("1.0", _carregar_fontes_especiais_v129_texto())
        if hasattr(self, "_txt_regionais_v1305"):
            self._txt_regionais_v1305.insert("1.0", _carregar_regionais_v1305_texto())
        if hasattr(self, "_txt_termos"):
            self._txt_termos.insert("1.0", _carregar_termos_v98_texto())
        try:
            from ururau.config.house_style import BRIEFING_EDITORIAL, TERMOS_IA_PROIBIDOS
            self._prod_txt["briefing"].insert("1.0", BRIEFING_EDITORIAL.strip())
            self._prod_txt["termos_ia"].insert("1.0", "\n".join(TERMOS_IA_PROIBIDOS))
        except Exception:
            pass
        extra = env.get("URURAU_INSTRUCAO_EXTRA", "")
        if extra:
            self._txt_extra.insert("1.0", extra)
        # Carregar estilo de escrita
        try:
            env2 = _ler_env_atual()
            pos = env2.get("URURAU_ESTILO_POSITIVO", "")
            neg = env2.get("URURAU_ESTILO_NEGATIVO", "")
            ex  = env2.get("URURAU_ESTILO_EXEMPLOS", "")
            if pos:
                self._txt_estilo_positivo.insert("1.0", pos)
            if neg:
                self._txt_estilo_negativo.insert("1.0", neg)
            if ex:
                self._txt_estilo_exemplos.insert("1.0", ex)
        except Exception:
            pass

    # ── Salvar ────────────────────────────────────────────────────────────────

    def _salvar(self):
        try:
            novos: dict[str, str] = {}
            for k, v in {**self._param_vars, **self._cred_vars, **self._fmt_vars}.items():
                val = v.get().strip()
                if val:
                    novos[k] = val
            extra = self._txt_extra.get("1.0", "end").strip()
            if extra:
                novos["URURAU_INSTRUCAO_EXTRA"] = extra
            # Estilo de escrita
            estilo_pos = self._txt_estilo_positivo.get("1.0", "end").strip()
            estilo_neg = self._txt_estilo_negativo.get("1.0", "end").strip()
            estilo_ex  = self._txt_estilo_exemplos.get("1.0", "end").strip()
            if estilo_pos:
                novos["URURAU_ESTILO_POSITIVO"] = estilo_pos
            if estilo_neg:
                novos["URURAU_ESTILO_NEGATIVO"] = estilo_neg
            if estilo_ex:
                novos["URURAU_ESTILO_EXEMPLOS"] = estilo_ex
            _atualizar_env(novos)

            # Fontes RSS
            from ururau.config.fontes_config_url_simples_v120 import fontes_para_json, sitemap_para_lista
            fontes, xmls_colados_no_rss = fontes_para_json(self._txt_rss.get("1.0", "end"))
            xmls_config = sitemap_para_lista(self._txt_xml.get("1.0", "end")) if hasattr(self, "_txt_xml") else []
            xmls = []
            vistos_xml = set()
            for x in list(xmls_config) + list(xmls_colados_no_rss):
                if x and x not in vistos_xml:
                    xmls.append(x)
                    vistos_xml.add(x)
            p_xml = Path("fontes_xml_sitemap_vfinal.txt")
            p_xml.write_text("\n".join(xmls) + ("\n" if xmls else ""), encoding="utf-8")
            print(f"[CONFIG v120] XML/Sitemap salvo: {len(xmls)} link(s)")
            qtd_especiais_v129 = 0
            if hasattr(self, "_txt_especiais_v129"):
                qtd_especiais_v129 = _salvar_fontes_especiais_v129_texto(self._txt_especiais_v129.get("1.0", "end"))
                print(f"[CONFIG v129] especiais salvos: {qtd_especiais_v129} item(ns)")
            qtd_regionais_v1305 = 0
            if hasattr(self, "_txt_regionais_v1305"):
                qtd_regionais_v1305 = _salvar_regionais_v1305_texto(self._txt_regionais_v1305.get("1.0", "end"))
                print(f"[CONFIG v130.5] regionais salvos: {qtd_regionais_v1305} item(ns)")
            fontes, removidas_especiais_rss_v129_1 = _filtrar_fontes_rss_sem_especiais_v129_1(fontes)
            fontes, removidas_regionais_rss_v1305 = _filtrar_fontes_rss_sem_regionais_v1305(fontes)
            Path("fontes_rss.json").write_text(
                json.dumps(fontes, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[CONFIG v130.5] RSS salvo sem duplicar Especiais/Regionais: {len(fontes)} item(ns); removidas_especiais={len(removidas_especiais_rss_v129_1)}; removidas_regionais={len(removidas_regionais_rss_v1305)}")
            self._txt_rss.delete("1.0", "end")
            self._txt_rss.insert("1.0", "\n".join(f["url"] for f in fontes))
            if hasattr(self, "_txt_xml"):
                self._txt_xml.delete("1.0", "end")
                self._txt_xml.insert("1.0", "\n".join(xmls))
            qtd_termos = 0
            if hasattr(self, "_txt_termos"):
                qtd_termos = _salvar_termos_v98_texto(self._txt_termos.get("1.0", "end"))
                print(f"[CONFIG v100] termos_watchlist_v98.json salvo: {qtd_termos} termo(s)")

            # House style
            self._salvar_house_style()

            from ururau.config import settings as _s
            _s.recarregar()

            messagebox.showinfo("Salvo",
                f"{len(novos)} parametros no .env\n"
                f"{len(fontes)} fontes RSS\n"
                f"{len(xmls)} XML/Sitemap\n"
                f"{qtd_especiais_v129} especiais\n"
                f"{qtd_regionais_v1305} regionais\n"
                f"{qtd_termos} termos de watchlist/busca\n"
                "Producao aplicada. Credenciais no proximo reinicio.", parent=self)
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", str(e), parent=self)

    def _salvar_house_style(self):
        """v47.2: salva regras editoriais em JSON, não reescreve house_style.py."""
        try:
            from ururau.editorial.regras_editoriais import atualizar_briefing_e_termos, recarregar_regras_editoriais
            from ururau.config import house_style as hs
            novo_briefing = self._prod_txt["briefing"].get("1.0", "end").strip()
            termos_raw = self._prod_txt["termos_ia"].get("1.0", "end").strip()
            termos = [t.strip() for t in termos_raw.splitlines() if t.strip()]
            atualizar_briefing_e_termos(novo_briefing, termos)
            recarregar_regras_editoriais()
            try:
                hs.BRIEFING_EDITORIAL = "\n" + novo_briefing + "\n"
                hs.TERMOS_IA_PROIBIDOS = termos
            except Exception:
                pass
            print("[CONFIG v47.2] regras editoriais salvas em config/regras_editoriais.json")
        except Exception as e:
            print(f"[CONFIG] Aviso ao salvar regras_editoriais.json: {e}")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_materia(pauta: dict) -> Optional[dict]:
    m = pauta.get("materia")
    if isinstance(m, dict):
        return m
    if isinstance(m, str):
        try:
            return json.loads(m)
        except Exception:
            pass
    return None



def _carregar_termos_v98_texto() -> str:
    try:
        from ururau.coleta.termos_config_v98 import termos_para_texto
        return termos_para_texto()
    except Exception as e:
        print(f"[TERMOS v98] Falha ao carregar termos: {e}")
        return "Campos dos Goytacazes|35|Cidades|1|Prioridade local máxima\nAlerj|26|Política|1|Política estadual\nPorto do Açu|30|Economia|1|Economia regional"


def _salvar_termos_v98_texto(texto: str) -> int:
    from ururau.coleta.termos_config_v98 import (
        texto_para_termos, salvar_termos, atualizar_arquivos_auxiliares,
        invalidar_cache_editorial_v12912,
    )
    termos = texto_para_termos(texto)
    salvar_termos(termos)
    atualizar_arquivos_auxiliares()
    invalidar_cache_editorial_v12912()
    print(f"[CONFIG v129.12] termos salvos; cache editorial/prioridade invalidado ({len(termos)} termo(s))")
    return len(termos)


def _norm_url_especial_v129_1(url: str) -> str:
    return str(url or "").strip().lower().rstrip("/")

def _host_especial_v129_1(url: str) -> str:
    try:
        from urllib.parse import urlparse
        h = (urlparse(str(url or "")).netloc or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

def _norm_nome_especial_v129_1(nome: str) -> str:
    nome = unicodedata.normalize("NFKD", str(nome or ""))
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", nome.lower()).strip()

def _filtrar_fontes_rss_sem_especiais_v129_1(fontes: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    v129.2: Fonte Especial vence RSS sem apagar fonte comum por engano.

    Regra corrigida:
    - remove/ignora do RSS apenas quando houver URL EXATA igual à Fonte Especial; ou
    - nome EXATO igual à Fonte Especial.
    - não remove por domínio/host, porque isso derrubava fontes funcionais do mesmo domínio
      ou fazia a configuração cair no fallback de 4 feeds.
    """
    try:
        especiais = _carregar_fontes_especiais_v129()
    except Exception:
        especiais = []
    urls = {_norm_url_especial_v129_1(e.get("url")) for e in especiais if e.get("url")}
    nomes = {_norm_nome_especial_v129_1(e.get("nome") or e.get("fonte_nome")) for e in especiais if (e.get("nome") or e.get("fonte_nome"))}
    limpas, removidas = [], []
    for f in fontes or []:
        u = _norm_url_especial_v129_1(f.get("url"))
        n = _norm_nome_especial_v129_1(f.get("nome") or f.get("fonte_nome"))
        if (u and u in urls) or (n and n in nomes):
            f2 = dict(f)
            f2["_v129_2_ignorada_rss"] = "cadastrada_em_fontes_especiais"
            removidas.append(f2)
            continue
        limpas.append(f)
    return limpas, removidas

def _carregar_fontes_especiais_v129() -> list[dict]:
    try:
        from ururau.coleta.linha_editorial_v129 import carregar_fontes_especiais_v129
        return carregar_fontes_especiais_v129(criar_se_ausente=True)
    except Exception as e:
        print(f"[ESPECIAIS v129] Falha ao carregar fontes especiais: {e}")
        return []


def _carregar_fontes_especiais_v129_texto() -> str:
    try:
        from ururau.coleta.linha_editorial_v129 import fontes_especiais_para_texto_v129
        return fontes_especiais_para_texto_v129()
    except Exception as e:
        print(f"[ESPECIAIS v129] Falha ao carregar texto: {e}")
        return ""


def _salvar_fontes_especiais_v129_texto(texto: str) -> int:
    from ururau.coleta.linha_editorial_v129 import texto_para_fontes_especiais_v129, salvar_fontes_especiais_v129
    fontes = texto_para_fontes_especiais_v129(texto)
    salvar_fontes_especiais_v129(fontes)
    return len(fontes)


# ── Regionais v130.5 ─────────────────────────────────────────────────────────

def _regionais_v1305_path() -> Path:
    try:
        return Path(__file__).resolve().parents[2] / "regionais_v1305.json"
    except Exception:
        return Path("regionais_v1305.json")

def _regionais_v1305_default() -> list[dict]:
    # RJ News Notícias não entra por padrão como regional, conforme regra editorial solicitada.
    return [
        {"nome": "Campos 24 Horas", "url": "https://campos24horas.com.br/portal/feed/", "ativo": True, "prioridade": "maxima", "regiao": "Campos/Norte Fluminense"},
        {"nome": "NF Notícias", "url": "https://www.nfnoticias.com.br/rss/", "ativo": True, "prioridade": "alta", "regiao": "Campos/Norte Fluminense", "tipo": "regional_v1305", "tipo_coleta": "regional_v1305", "bypass_score": True, "regional_prioritaria": True, "min_por_fonte": 2},
        {"nome": "J3 News", "url": "https://j3news.com/feed/", "ativo": True, "prioridade": "alta", "regiao": "Campos/Norte Fluminense"},
        {"nome": "Portal Viu", "url": "https://www.portalviu.com.br/feed", "ativo": True, "prioridade": "alta", "regiao": "Campos/Norte Fluminense"},
        {"nome": "SF Notícias", "url": "https://sfnoticias.com.br/feed", "ativo": True, "prioridade": "alta", "regiao": "Norte Fluminense"},
        {"nome": "O Debate", "url": "https://odebateon.com.br/feed/", "ativo": True, "prioridade": "media", "regiao": "Norte Fluminense"},
        {"nome": "O Parahybano", "url": "https://parahybano.com.br/feed/", "ativo": True, "prioridade": "media", "regiao": "São João da Barra"},
        {"nome": "Prefeitura de Campos", "url": "https://campos.rj.gov.br/rss", "ativo": True, "prioridade": "alta", "regiao": "Campos"},
    ]

def _texto_para_regionais_v1305(texto: str) -> list[dict]:
    fontes = []
    for linha in str(texto or "").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) >= 2:
            nome, url = partes[0], partes[1]
            regiao = partes[2] if len(partes) >= 3 else "Campos/Norte Fluminense"
            prioridade = partes[3] if len(partes) >= 4 else "alta"
        else:
            url = partes[0]
            nome = url
            regiao = "Campos/Norte Fluminense"
            prioridade = "alta"
        if not url:
            continue
        f = {"nome": nome or url, "url": url, "ativo": True, "regiao": regiao, "prioridade": prioridade,
             "tipo": "regional_v1305", "tipo_coleta": "regional_v1305", "bypass_score": True,
             "regional_prioritaria": True, "min_por_fonte": 2}
        fontes.append(f)
    return fontes

def _regionais_para_texto_v1305(fontes: list[dict]) -> str:
    linhas = []
    for f in fontes or []:
        nome = f.get("nome") or f.get("fonte_nome") or ""
        url = f.get("url") or ""
        regiao = f.get("regiao") or "Campos/Norte Fluminense"
        prioridade = f.get("prioridade") or "alta"
        if url:
            linhas.append(f"{nome}|{url}|{regiao}|{prioridade}")
    return "\n".join(linhas)

def _carregar_regionais_v1305(criar_se_ausente: bool = True) -> list[dict]:
    p = _regionais_v1305_path()
    try:
        if not p.exists() and criar_se_ausente:
            p.write_text(json.dumps(_regionais_v1305_default(), ensure_ascii=False, indent=2), encoding="utf-8")
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, list):
                return [dict(f, regional_prioritaria=True, bypass_score=True, tipo=f.get("tipo") or "regional_v1305", tipo_coleta=f.get("tipo_coleta") or "regional_v1305") for f in data if isinstance(f, dict) and f.get("url")]
    except Exception as e:
        print(f"[REGIONAIS v130.5] Falha ao carregar: {e}")
    return _regionais_v1305_default()

def _carregar_regionais_v1305_texto() -> str:
    return _regionais_para_texto_v1305(_carregar_regionais_v1305(criar_se_ausente=True))

def _salvar_regionais_v1305_texto(texto: str) -> int:
    fontes = _texto_para_regionais_v1305(texto)
    p = _regionais_v1305_path()
    p.write_text(json.dumps(fontes, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(fontes)

def _filtrar_fontes_rss_sem_regionais_v1305(fontes: list[dict]) -> tuple[list[dict], list[dict]]:
    try:
        regionais = _carregar_regionais_v1305(criar_se_ausente=True)
    except Exception:
        regionais = []
    urls = {_norm_url_especial_v129_1(e.get("url")) for e in regionais if e.get("url")}
    nomes = {_norm_nome_especial_v129_1(e.get("nome") or e.get("fonte_nome")) for e in regionais if (e.get("nome") or e.get("fonte_nome"))}
    limpas, removidas = [], []
    for f in fontes or []:
        u = _norm_url_especial_v129_1(f.get("url"))
        n = _norm_nome_especial_v129_1(f.get("nome") or f.get("fonte_nome"))
        if (u and u in urls) or (n and n in nomes):
            f2 = dict(f)
            f2["_v1305_ignorada_rss"] = "cadastrada_em_regionais"
            removidas.append(f2)
            continue
        limpas.append(f)
    return limpas, removidas


def _fontes_rss_default_v129_2() -> list[dict]:
    """Lista completa de RSS restaurada da v127. Usada só como fallback/reparo."""
    return [
        {
            "url": "https://mancheterj.com/portal/feed/",
            "nome": "Manchete RJ",
            "canal_forcado": "",
            "ativo": True
        },
        {
            "url": "https://campos.rj.gov.br/rss",
            "nome": "Prefeitura de Campos",
            "canal_forcado": "",
            "ativo": True
        },
        {
            "url": "https://campos24horas.com.br/portal/feed/",
            "nome": "Campos 24 Horas",
            "canal_forcado": "",
            "ativo": True
        },
        {
            "url": "https://j3news.com/feed/",
            "nome": "J3 News",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 1,
            "max_por_link": 5
        },
        {
            "url": "https://www.portalviu.com.br/feed",
            "nome": "Portal Viu",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 2,
            "max_por_link": 5
        },
        {
            "url": "https://sfnoticias.com.br/feed",
            "nome": "SF Notícias",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 3,
            "max_por_link": 5
        },
        {
            "url": "https://odebateon.com.br/feed/",
            "nome": "O Debate",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 4,
            "max_por_link": 5
        },
        {
            "url": "https://cliquediario.com.br/feed",
            "nome": "Clique Diário",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 5,
            "max_por_link": 5
        },
        {
            "url": "https://parahybano.com.br/feed/",
            "nome": "O Parahybano",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 6,
            "max_por_link": 5
        },
        {
            "url": "https://rjnewsnoticias.com.br/feed/",
            "nome": "RJ News Notícias",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 7,
            "max_por_link": 5
        },
        {
            "url": "https://www.jornaldesabado.com.br/feed/",
            "nome": "Jornal de Sábado",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 8,
            "max_por_link": 5
        },
        {
            "url": "https://prensadebabel.com.br/feed/",
            "nome": "Prensa de Babel",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 9,
            "max_por_link": 5
        },
        {
            "url": "https://agendadopoder.com.br/feed/",
            "nome": "Agenda do Poder",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 10,
            "max_por_link": 5
        },
        {
            "url": "https://diariodorio.com/feed/",
            "nome": "Diário do Rio",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 11,
            "max_por_link": 5
        },
        {
            "url": "https://girorj.com.br/feed/",
            "nome": "Giro RJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 12,
            "max_por_link": 5
        },
        {
            "url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
            "nome": "Agência Brasil",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 13,
            "max_por_link": 5
        },
        {
            "url": "https://g1.globo.com/rss/g1/politica/",
            "nome": "G1 Política",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 14,
            "max_por_link": 5
        },
        {
            "url": "https://admin.cnnbrasil.com.br/feed/",
            "nome": "CNN Brasil",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 15,
            "max_por_link": 5
        },
        {
            "url": "https://feeds.folha.uol.com.br/poder/rss091.xml",
            "nome": "Folha Poder",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 16,
            "max_por_link": 5
        },
        {
            "url": "https://www.uol.com.br/vueland/api/?loadComponent=XmlFeedRss",
            "nome": "UOL",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 17,
            "max_por_link": 5
        },
        {
            "url": "https://www12.senado.leg.br/noticias/rss.xml",
            "nome": "Senado",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 18,
            "max_por_link": 5
        },
        {
            "url": "https://noticias.stf.jus.br/feed/",
            "nome": "STF",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 19,
            "max_por_link": 5
        },
        {
            "url": "https://res.stj.jus.br/hrestp-c-portalp/RSS.xml",
            "nome": "STJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 20,
            "max_por_link": 5
        },
        {
            "url": "https://www.tse.jus.br/rss",
            "nome": "TSE",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 21,
            "max_por_link": 5
        },
        {
            "url": "https://www.rj.gov.br/noticias/rss",
            "nome": "Governo RJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 22,
            "max_por_link": 5
        },
        {
            "url": "https://www.mprj.mp.br/rss",
            "nome": "MPRJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 23,
            "max_por_link": 5
        },
        {
            "url": "https://www.poder360.com.br/feed/",
            "nome": "Poder360",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 24,
            "max_por_link": 5
        },
        {
            "url": "https://odia.ig.com.br/rss.xml",
            "nome": "O Dia",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 25,
            "max_por_link": 5
        },
        {
            "url": "https://rss.bs.vibra.digital/feed.xml?site=portal&size=10",
            "nome": "Band",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 26,
            "max_por_link": 5
        },
        {
            "url": "https://www.tre-rj.jus.br/comunicacao/noticias/RSS",
            "nome": "TRE-RJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 27,
            "max_por_link": 5
        },
        {
            "url": "https://www.metropoles.com/feed",
            "nome": "Metrópoles",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 28,
            "max_por_link": 5
        },
        {
            "url": "https://mancheterio.com.br/feed/",
            "nome": "Manchete Rio",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 29,
            "max_por_link": 5
        },
        {
            "url": "https://www.camara.leg.br/rss/noticias.xml",
            "nome": "Câmara",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 30,
            "max_por_link": 5
        },
        {
            "url": "https://www.gov.br/rss.xml",
            "nome": "Gov.br",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 31,
            "max_por_link": 5
        },
        {
            "url": "https://www.alerj.rj.gov.br/Noticias/rss",
            "nome": "Alerj",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 32,
            "max_por_link": 5
        },
        {
            "url": "https://www.tjrj.jus.br/web/guest/home/-/noticias/rss",
            "nome": "TJRJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 33,
            "max_por_link": 5
        },
        {
            "url": "https://defensoria.rj.def.br/rss/noticias",
            "nome": "Defensoria RJ",
            "canal_forcado": "",
            "ativo": True,
            "tipo_coleta": "rss",
            "ordem": 34,
            "max_por_link": 5
        },
    ]


def _ler_fontes_rss_de_arquivo_v129_2(p: Path) -> list[dict]:
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{p} não contém uma lista JSON")
    return data


def _carregar_fontes_rss() -> list[dict]:
    """
    v129.2: carregamento robusto das Fontes RSS.

    Corrige o bug da v129.1:
    - faltava import unicodedata, quebrando a leitura e derrubando a UI no fallback de 4 fontes;
    - o fallback de 4 fontes foi substituído pela lista completa restaurada da v127;
    - busca o arquivo também pela raiz do sistema, não só pelo diretório atual.
    """
    # V47.7: usa carregamento unificado antes do fallback legado.
    # Isso soma fontes da raiz, config/, configuracoes/ e fontes_links.json sem apagar nada.
    try:
        from ururau.coleta.config_unificada import carregar_fontes_rss_unificadas
        data_unificada = carregar_fontes_rss_unificadas()
        if len(data_unificada) > 4:
            try:
                from ururau.coleta.fonte_registry_v126 import normalizar_fontes_config_v126
                data_unificada = normalizar_fontes_config_v126(data_unificada, tipo_padrao="rss")
            except Exception:
                pass
            fontes_filtradas, removidas = _filtrar_fontes_rss_sem_especiais_v129_1(data_unificada)
            if removidas:
                print(f"[v47.7][RSS] {len(removidas)} item(ns) ignorado(s) por estarem em Especiais.")
            fontes_filtradas, removidas_regionais = _filtrar_fontes_rss_sem_regionais_v1305(fontes_filtradas)
            if removidas_regionais:
                print(f"[v47.7][RSS] {len(removidas_regionais)} item(ns) ignorado(s) por estarem em Regionais.")
            print(f"[v47.7][RSS] fontes unificadas carregadas: {len(fontes_filtradas)}")
            return fontes_filtradas
    except Exception as e_unif:
        print(f"[v47.7][RSS] carregamento unificado indisponível; usando fallback legado: {e_unif}")

    candidatos = []
    try:
        candidatos.append(Path("fontes_rss.json"))
        base_sistema = Path(__file__).resolve().parents[2]
        candidatos.extend([
            base_sistema / "fontes_rss.json",
            base_sistema / "configuracoes" / "fontes_rss.json",
            base_sistema / "config" / "fontes_rss.json",
        ])
    except Exception:
        candidatos.append(Path("fontes_rss.json"))

    ultimo_erro = None
    for p in candidatos:
        try:
            if not p.exists():
                continue
            data = _ler_fontes_rss_de_arquivo_v129_2(p)
            if len(data) <= 4:
                print(f"[v129.2][RSS][AVISO] {p} tem somente {len(data)} fonte(s); tentando próxima fonte ou fallback completo.")
                continue
            try:
                from ururau.coleta.fonte_registry_v126 import normalizar_fontes_config_v126
                data = normalizar_fontes_config_v126(data, tipo_padrao="rss")
            except Exception:
                pass
            fontes_filtradas, removidas = _filtrar_fontes_rss_sem_especiais_v129_1(data)
            if removidas:
                print(f"[v130.5][RSS] {len(removidas)} item(ns) ignorado(s) no RSS por estarem em Especiais.")
            fontes_filtradas, removidas_regionais = _filtrar_fontes_rss_sem_regionais_v1305(fontes_filtradas)
            if removidas_regionais:
                print(f"[v130.5][RSS] {len(removidas_regionais)} item(ns) ignorado(s) no RSS por estarem em Regionais.")
            return fontes_filtradas
        except Exception as e:
            ultimo_erro = e
            print(f"[v129.2][RSS] Falha ao carregar {p}: {e}")

    if ultimo_erro:
        print(f"[v129.2][RSS] usando fallback completo da v127 após erro: {ultimo_erro}")
    else:
        print("[v129.2][RSS] usando fallback completo da v127; arquivo fontes_rss.json não encontrado.")
    fallback = _fontes_rss_default_v129_2()
    try:
        fallback, removidas = _filtrar_fontes_rss_sem_especiais_v129_1(fallback)
        if removidas:
            print(f"[v130.5][RSS] fallback removeu {len(removidas)} item(ns) por Especiais.")
        fallback, removidas_regionais = _filtrar_fontes_rss_sem_regionais_v1305(fallback)
        if removidas_regionais:
            print(f"[v130.5][RSS] fallback removeu {len(removidas_regionais)} item(ns) por Regionais.")
    except Exception:
        pass
    return fallback


def _base_sistema_v47() -> Path:
    """Retorna a pasta sistema, independente do diretório atual do .bat."""
    return Path(__file__).resolve().parents[2]


def _env_paths_v47() -> tuple[Path, Path, Path]:
    base = _base_sistema_v47()
    return (
        base / "credenciais" / ".env.exemplo",
        base / "credenciais" / "env_principal.env",
        base / ".env",
    )


def _parse_env_file_v47(env_path: Path) -> dict[str, str]:
    dados: dict[str, str] = {}
    if not env_path.exists():
        return dados
    for linha in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        dados[chave.strip()] = valor.strip().strip('"').strip("'")
    return dados


def _ler_env_atual() -> dict[str, str]:
    # v47: ler primeiro defaults e por último o .env real, para o real vencer.
    res: dict[str, str] = {}
    exemplo, env_principal, env_real = _env_paths_v47()
    for env_path in [exemplo, env_principal, env_real]:
        res.update(_parse_env_file_v47(env_path))
    return res


def _atualizar_env(novos: dict[str, str]):
    exemplo, env_principal, env_real = _env_paths_v47()
    env_paths = [env_principal, env_real]
    atuais = _ler_env_atual()
    atuais.update({str(k): str(v).strip() for k, v in (novos or {}).items() if str(v).strip()})

    ordem = [
        "OPENAI_API_KEY", "OPENAI_MODEL", "URURAU_LOGIN", "URURAU_SENHA", "URURAU_ASSINATURA",
        "SITE_LOGIN_URL", "SITE_NOVA_URL", "URURAU_PUBLICACAO_REAL_CONFIRMADA",
        "HEADLESS", "SLOW_MO", "INTERVALO_ENTRE_CICLOS_SEGUNDOS",
        "MAX_PUBLICACOES_MONITORAMENTO_POR_HORA", "MAX_PUBLICACOES_POR_CICLO", "MAX_PUBLICACOES_POR_CANAL",
        "JANELA_BUSCA_MAXIMA_HORAS", "JANELA_PRIORIDADE_ULTIMA_HORA", "JANELA_ANTIDUPLICACAO_HORAS",
        "LIMIAR_RELEVANCIA_PUBLICAR", "LIMIAR_RISCO_MAXIMO", "SCORE_MONITOR_DIRETO_IMEDIATO",
        "SCORE_MONITOR_DIRETO_CONFIANCA", "SCORE_MONITOR_PAINEL_PRIORIDADE", "ARQUIVO_DB",
        "PASTA_IMAGENS", "PASTA_PRINTS", "PASTA_LOGS", "QUALIDADE_JPEG_FINAL",
    ]
    linhas = []
    usados = set()
    for chave in ordem:
        if chave in atuais:
            linhas.append(f"{chave}={atuais[chave]}")
            usados.add(chave)
    for chave in sorted(k for k in atuais if k not in usados):
        linhas.append(f"{chave}={atuais[chave]}")
    conteudo = "\n".join(linhas).rstrip() + "\n"
    for env_path in env_paths:
        try:
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(conteudo, encoding="utf-8")
        except Exception:
            pass
    # Atualiza o processo atual para o botão Salvar e Aplicar ter efeito imediato.
    try:
        import os as _os_v47
        for chave, valor in atuais.items():
            _os_v47.environ[str(chave)] = str(valor)
    except Exception:
        pass

# v130: integra aba Config > Diagnóstico de Fonte usando motor interno seguro.
try:
    from ururau.ui.diagnostico_fontes_tab_v130 import aplicar_patch_v130 as _aplicar_diag_fontes_v130
    _aplicar_diag_fontes_v130(globals())
    print("[v130] Diagnóstico interno de fontes integrado ao painel.")
except Exception as _e_diag_fontes_v130:
    print(f"[v130][AVISO] Diagnóstico de fontes não integrado: {_e_diag_fontes_v130}")


# v132: reorganização de Config, atualização útil e fluxo Preview -> CopyDesk.
try:
    from ururau.ui.patch_v132_organizacao_fluxo import aplicar_patch_v132 as _aplicar_patch_v132
    _aplicar_patch_v132(globals())
except Exception as _e_patch_v132:
    print(f"[v132][AVISO] patch de organização/fluxo não aplicado: {_e_patch_v132}")


# V43 Premium: AppShell visual modular, fonte única, status de fontes e memória operacional.
try:
    from ururau.ui.patch_v43_premium import aplicar_patch_v43 as _aplicar_patch_v43
    _aplicar_patch_v43(globals())
except Exception as _e_patch_v43:
    print(f"[V43][AVISO] patch premium não aplicado: {_e_patch_v43}")


# V44 LAYOUT ULTRALEVE PREMIUM: virtualizacao incremental, console ampliado,
# status sem corte e rings cacheados. Aplicado SEMPRE depois do patch v43.
try:
    from ururau.ui.patch_v44_layout_ultraleve import aplicar_patch_v44 as _aplicar_patch_v44
    _aplicar_patch_v44(globals())
except Exception as _e_patch_v44:
    print(f"[V44][AVISO] patch layout ultraleve nao aplicado: {_e_patch_v44}")


# V45 REDESIGN VISUAL PREMIUM: novo header, fila com cards premium,
# detalhe estilizado, console terminal. Roda DEPOIS de V43+V44.
try:
    from ururau.ui.patch_v45_redesign import aplicar_patch_v45 as _aplicar_patch_v45
    _aplicar_patch_v45(globals())
except Exception as _e_patch_v45:
    print(f"[V45][AVISO] redesign nao aplicado: {_e_patch_v45}")

# V46 LAYOUT DEFINITIVO PREMIUM: header continuo, botoes premium,
# fila com quebra de linha e sidebar operacional em 3 colunas.
try:
    from ururau.ui.patch_v46_layout_definitivo import aplicar_patch_v46 as _aplicar_patch_v46
    _aplicar_patch_v46(globals())
except Exception as _e_patch_v46:
    print(f"[V46][AVISO] layout definitivo nao aplicado: {_e_patch_v46}")
# v47.4 — F5 real, mensagens operacionais, fila cronológica e diagnóstico aplicado
try:
    from ururau.ui.patch_v47_4_operacional import aplicar_patch_v47_4
    aplicar_patch_v47_4(globals())
except Exception as _e_v47_4:
    print(f"[v47.4] Patch operacional não aplicado: {_e_v47_4}")


# v47.6 — Monitor 24h contínuo, rascunho CMS padrão, intervalo obedecido e sem instância duplicada
try:
    from ururau.ui.patch_v47_6_monitor_24h import aplicar_patch_v47_6
    aplicar_patch_v47_6(globals())
except Exception as _e_v47_6:
    print(f"[v47.6] Patch do monitor 24h não aplicado: {_e_v47_6}")

# v47.12 — SEO real, navegação da fila e extração persistente premium
try:
    from ururau.ui.patch_v47_12_premium_operacional import aplicar_patch_v47_12
    aplicar_patch_v47_12(globals())
except Exception as _e_v47_12:
    print(f"[v47.12] Patch premium operacional não aplicado: {_e_v47_12}")

# PATCH_V47_13_UI_PREMIUM
try:
    import tkinter as _tk_v4713
except Exception:
    _tk_v4713 = None

def _v4713_tem_texto_util(pauta):
    try:
        if not isinstance(pauta, dict): return False
        texto = pauta.get('texto_fonte') or pauta.get('fonte_texto') or pauta.get('texto_extraido') or pauta.get('corpo_fonte') or pauta.get('corpo') or ''
        return len(str(texto).strip()) >= 900
    except Exception: return False

def _v4713_score_visual(pauta):
    if not _v4713_tem_texto_util(pauta): return '--'
    for k in ('seo_score','qualidade_ia','score_qualidade','score_editorial','score'):
        try:
            v=pauta.get(k)
            if v is not None and str(v).strip()!='': return str(int(float(v)))
        except Exception: pass
    return '--'

def _v4713_ordenar_pautas_cronologico(pautas):
    def key(p):
        if not isinstance(p, dict): return ''
        return str(p.get('data_pub_fonte') or p.get('published') or p.get('data_publicacao') or p.get('created_at') or p.get('coletado_em') or '')
    try: return sorted(list(pautas or []), key=key, reverse=True)
    except Exception: return pautas

def _v4713_bind_fila_navegacao(widget, callback=None):
    if widget is None: return
    def move(delta):
        try:
            cur = widget.curselection()
            size = widget.size()
            idx = (cur[0] if cur else 0) + delta
            idx = max(0, min(size-1, idx))
            widget.selection_clear(0, 'end'); widget.selection_set(idx); widget.activate(idx); widget.see(idx); widget.focus_set()
            if callback: callback(None)
            return 'break'
        except Exception: return None
    try:
        widget.bind('<Down>', lambda e: move(1))
        widget.bind('<Up>', lambda e: move(-1))
        widget.bind('<Next>', lambda e: move(8))
        widget.bind('<Prior>', lambda e: move(-8))
        widget.bind('<Home>', lambda e: move(-999999))
        widget.bind('<End>', lambda e: move(999999))
        widget.configure(highlightthickness=2, highlightbackground='#7c3aed', highlightcolor='#7c3aed', exportselection=False)
    except Exception: pass

def _v4713_f5_operacional(app=None):
    funcs=['_carregar_pautas','carregar_pautas','atualizar_fila','refresh','_refresh']
    alvo = app if app is not None else globals().get('self')
    for name in funcs:
        try:
            fn=getattr(alvo,name,None)
            if callable(fn):
                try: fn(forcar=True)
                except TypeError: fn()
        except Exception: pass
    try:
        print('[V47.13] F5 operacional: fila recarregada e pautas pendentes reenfileiradas para extração.')
    except Exception: pass

# v47.15 — Monitor 24h corrigido dentro do painel: rascunho CMS real e defaults do monitor
try:
    from ururau.ui.patch_v47_15_monitor_painel import aplicar_patch_v47_15
    aplicar_patch_v47_15(globals())
except Exception as _e_v47_15:
    print(f"[v47.15] Patch monitor painel não aplicado: {_e_v47_15}")


# v47.22 — parada segura do monitor no painel
try:
    from ururau.ui.patch_v47_22_monitor_stop_painel import aplicar_patch_v47_22
    aplicar_patch_v47_22(globals())
except Exception as _e_v47_22:
    print(f'[v47.22] Patch stop monitor não aplicado: {_e_v47_22}')


# v47.23 - parada segura monitor painel
try:
    from ururau.ui.patch_v47_23_monitor_stop_painel import aplicar_patch_v47_23
    aplicar_patch_v47_23(globals())
except Exception as _e_v47_23:
    print(f'[v47.23] patch stop monitor nao aplicado: {_e_v47_23}')


# v47.25 — integridade pauta/fonte/materia no Redigir e Preview
try:
    from ururau.ui.patch_v47_25_integridade_redacao import aplicar_patch_v47_25
    aplicar_patch_v47_25(globals())
except Exception as _e_v47_25:
    print(f'[v47.25] patch integridade redacao nao aplicado: {_e_v47_25}')


# v47.26 — fonte correta antes da IA
try:
    from ururau.ui.patch_v47_26_fonte_antes_ia import aplicar_patch_v47_26
    aplicar_patch_v47_26(globals())
except Exception as _e_v47_26:
    print(f'[v47.26] patch fonte antes IA nao aplicado: {_e_v47_26}')


# v47.27 — bloqueia preview contaminado ja persistido
try:
    from ururau.ui.patch_v47_27_preview_guard import aplicar_patch_v47_27
    aplicar_patch_v47_27(globals())
except Exception as _e_v47_27:
    print(f'[v47.27] patch preview contaminado nao aplicado: {_e_v47_27}')

# v47.32 — aba Auditor IA integrada ao painel principal
try:
    from ururau.ui.patch_auditor_ia_tab_v47_32 import aplicar_patch_auditor_ia_tab_v47_32
    aplicar_patch_auditor_ia_tab_v47_32(globals())
except Exception as _e_v47_32:
    print(f'[v47.32] patch Auditor IA nao aplicado: {_e_v47_32}')

