from __future__ import annotations
import os, re
from pathlib import Path
from typing import Any
_INSTALLED=False
_ORIG_TEXT_GET=None
_ORIG_TK_MAINLOOP=None
URL_RE=re.compile(r"https?://[^\s|]+", re.I)
def _env_bool(key:str, default:bool=True)->bool:
    v=os.getenv(key)
    return default if v is None else str(v).strip().lower() in {"1","true","yes","sim","on"}
def _strip_ordem(line:str)->str:
    return re.sub(r"^\s*\d+\s*[\.\-\|\)]?\s*", "", (line or "").strip()).strip()
def _extract_url(line:str)->str:
    line=_strip_ordem(line)
    if "|" in line: line=line.split("|",1)[0].strip()
    m=URL_RE.search(line)
    return m.group(0).strip() if m else ""
def _is_xml(url:str)->bool:
    low=(url or "").lower(); return "sitemap" in low
def _nome_por_url(url:str)->str:
    try:
        from ururau.config.fontes_config_url_simples_v117 import nome_por_url
        return nome_por_url(url)
    except Exception: pass
    try:
        from urllib.parse import urlparse
        host=urlparse(url).netloc.lower().replace("www.","")
        mapa={"j3news.com":"J3 News","portalviu.com.br":"Portal Viu","sfnoticias.com.br":"SF Notícias","odebateon.com.br":"O Debate","cliquediario.com.br":"Clique Diário","parahybano.com.br":"O Parahybano","rjnewsnoticias.com.br":"RJ News Notícias","jornaldesabado.com.br":"Jornal de Sábado","prensadebabel.com.br":"Prensa de Babel","agendadopoder.com.br":"Agenda do Poder","diariodorio.com":"Diário do Rio","girorj.com.br":"Giro RJ","campos24horas.com.br":"Campos 24 Horas","g1.globo.com":"G1","cnnbrasil.com.br":"CNN Brasil","poder360.com.br":"Poder360","odia.ig.com.br":"O Dia","agenciabrasil.ebc.com.br":"Agência Brasil","camara.leg.br":"Câmara dos Deputados","senado.leg.br":"Senado Federal"}
        for k,v in mapa.items():
            if k in host: return v
        return (host.split(".")[0] if host else "Fonte").replace("-"," ").title()
    except Exception: return "Fonte"
def _urls_from_text(text:str, *, include_xml:bool=False)->list[str]:
    urls=[]; seen=set()
    for line in (text or "").splitlines():
        url=_extract_url(line)
        if not url: continue
        if _is_xml(url) and not include_xml: continue
        key=url.rstrip("/")
        if key not in seen:
            seen.add(key); urls.append(url)
    return urls
def _xml_from_text(text:str)->list[str]:
    return [u for u in _urls_from_text(text, include_xml=True) if _is_xml(u)]
def _internal_save_text(text:str)->str:
    return "\n".join(f"{url}|{_nome_por_url(url)}|" for url in _urls_from_text(text))
def _visual_text(text:str)->str:
    return "\n".join(_urls_from_text(text))
def _register_xmls(text:str)->None:
    xmls=_xml_from_text(text)
    if not xmls or not _env_bool("URURAU_XML_SITEMAP_ATIVO", True): return
    try:
        path=Path(os.getenv("URURAU_XML_SITEMAP_CONFIG","fontes_xml_sitemap_vfinal.txt"))
        existing=[]
        if path.exists(): existing=[x.strip() for x in path.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
        seen={x.rstrip("/") for x in existing}; changed=False
        for url in xmls:
            key=url.rstrip("/")
            if key not in seen:
                seen.add(key); existing.append(url); changed=True
        if changed:
            path.write_text("\n".join(existing)+"\n", encoding="utf-8")
            print(f"[CONFIG_V118] XML/Sitemap movido para {path}: {len(xmls)} link(s)")
    except Exception as exc: print(f"[CONFIG_V118][AVISO] falha ao registrar XML/Sitemap: {exc}")
def _has_rss_label_nearby(widget:Any)->bool:
    try:
        parent=widget.master
        for _ in range(7):
            if parent is None: return False
            for child in parent.winfo_children():
                try: text=str(child.cget("text"))
                except Exception: text=""
                low=text.lower()
                if "fontes rss" in low or "formato rss" in low or ("rss" in low and "url" in low): return True
            parent=parent.master
    except Exception: pass
    return False
def _looks_like_rss_text(text:str)->bool:
    lines=[x for x in (text or "").splitlines() if x.strip()]
    if not lines: return False
    hits=0
    for line in lines:
        url=_extract_url(line)
        if url and any(tok in url.lower() for tok in ("/feed","rss","sitemap",".xml","g1.globo","agenciabrasil")): hits+=1
    return hits >= max(1, min(3, len(lines)))
def _ensure_blank_lines(widget:Any, min_lines:int=80)->None:
    try:
        raw=_ORIG_TEXT_GET(widget,"1.0","end-1c") if _ORIG_TEXT_GET else ""
        lines=raw.count("\n")+1 if raw else 1
        if lines<min_lines: widget.insert("end","\n"*(min_lines-lines))
    except Exception: pass
def _normalize_visible(widget:Any)->None:
    try:
        raw=_ORIG_TEXT_GET(widget,"1.0","end-1c") if _ORIG_TEXT_GET else widget.get("1.0","end-1c")
        _register_xmls(raw); visual=_visual_text(raw); current="\n".join(_urls_from_text(raw))
        if "|" in raw or re.search(r"^\s*\d+\s*[\.\-\|\)]", raw, flags=re.M) or visual!=current:
            widget.delete("1.0","end")
            if visual: widget.insert("1.0",visual)
        _ensure_blank_lines(widget)
    except Exception as exc: print(f"[CONFIG_V118][AVISO] normalização visual falhou: {exc}")
def _line_count(widget:Any)->int:
    try:
        raw=_ORIG_TEXT_GET(widget,"1.0","end-1c") if _ORIG_TEXT_GET else ""
        return max(80, raw.count("\n")+1)
    except Exception: return 80
def _redraw_gutter(widget:Any)->None:
    try:
        canvas=getattr(widget,"_ururau_gutter_v118",None)
        if canvas is None: return
        canvas.delete("all"); canvas.configure(bg="#10203f", highlightthickness=0)
        for i in range(1,_line_count(widget)+1):
            info=widget.dlineinfo(f"{i}.0")
            if info is None: continue
            y=info[1]; canvas.create_text(34,y+8,text=str(i),fill="#8fb7ff",anchor="e",font=("Consolas",9))
    except Exception: pass
def _install_on_text(widget:Any)->None:
    try:
        if getattr(widget,"_ururau_rss_config_v118",False): return
        widget._ururau_rss_config_v118=True
        import tkinter as tk
        widget.configure(padx=54, wrap="none")
        gutter=tk.Canvas(widget,width=48,bd=0,highlightthickness=0,relief="flat",bg="#10203f")
        gutter.place(x=0,y=0,width=48,relheight=1); gutter.lift(); widget._ururau_gutter_v118=gutter
        _normalize_visible(widget)
        def refresh(_event=None): _normalize_visible(widget); widget.after_idle(lambda:_redraw_gutter(widget))
        def redraw_only(_event=None): widget.after_idle(lambda:_redraw_gutter(widget))
        widget.bind("<KeyRelease>",refresh,add="+"); widget.bind("<<Paste>>",lambda e: widget.after(80,refresh),add="+")
        widget.bind("<ButtonRelease-1>",redraw_only,add="+"); widget.bind("<MouseWheel>",redraw_only,add="+"); widget.bind("<Configure>",redraw_only,add="+")
        widget.after(100,refresh)
        print("[CONFIG_V118] campo Fontes RSS convertido para numeração fixa lateral")
    except Exception as exc: print(f"[CONFIG_V118][AVISO] não conseguiu instalar no Text: {exc}")
def _scan(root:Any)->None:
    try:
        import tkinter as tk
        if isinstance(root, tk.Text):
            raw=_ORIG_TEXT_GET(root,"1.0","end-1c") if _ORIG_TEXT_GET else ""
            if _has_rss_label_nearby(root) or _looks_like_rss_text(raw): _install_on_text(root)
        for child in root.winfo_children(): _scan(child)
    except Exception: pass
def _loop(root:Any)->None:
    try: _scan(root); root.after(1200, lambda:_loop(root))
    except Exception: pass
def _patch_text_get()->None:
    global _ORIG_TEXT_GET
    import tkinter as tk
    if _ORIG_TEXT_GET is not None: return
    _ORIG_TEXT_GET=tk.Text.get
    def get_wrapper(self,*args,**kwargs):
        text=_ORIG_TEXT_GET(self,*args,**kwargs)
        if getattr(self,"_ururau_rss_config_v118",False): return _internal_save_text(text)
        return text
    tk.Text.get=get_wrapper
def instalar_config_rss_linhas_fixas_v118()->None:
    global _INSTALLED,_ORIG_TK_MAINLOOP
    if _INSTALLED: return
    _INSTALLED=True
    if not _env_bool("URURAU_CONFIG_RSS_LINHAS_FIXAS_ATIVO", True): print("[CONFIG_V118] linhas fixas desativadas por env"); return
    import tkinter as tk
    _patch_text_get()
    if _ORIG_TK_MAINLOOP is None:
        _ORIG_TK_MAINLOOP=tk.Tk.mainloop
        def mainloop_wrapper(self,*args,**kwargs):
            try: _loop(self); print("[CONFIG_V118] numeração fixa lateral ativa no Config RSS")
            except Exception as exc: print(f"[CONFIG_V118][AVISO] loop visual não iniciado: {exc}")
            return _ORIG_TK_MAINLOOP(self,*args,**kwargs)
        tk.Tk.mainloop=mainloop_wrapper
    print("[CONFIG_V118] patch carregado")
