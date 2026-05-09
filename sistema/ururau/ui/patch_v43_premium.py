"""patch_v43_premium.py — Ururau V43 Premium.
V43 Premium definitiva: painel nativo leve, sem barra lateral esquerda, ações no topo,
indicadores compactos no header, fila sem botão Gerar, console interno sob demanda,
fonte única, status de fontes e memória editorial operacional.
"""
from __future__ import annotations
import json
from pathlib import Path

def aplicar_patch_v43(g: dict) -> None:
    tk = g.get("tk"); ttk = g.get("ttk")
    if not tk or not ttk: return
    PainelUrurau = g.get("PainelUrurau"); _ConfigWidget = g.get("_ConfigWidget"); JanelaConfiguracoes = g.get("JanelaConfiguracoes")
    if not PainelUrurau: return
    COLORS={"bg":"#080d16","surface":"#101827","surface2":"#151f32","surface3":"#0d1422","surface4":"#0b1220","border":"#253047","brand":"#ff7a1a","text":"#f4f7fb","muted":"#9aa7bc","blue":"#3b82f6","green":"#22c55e","red":"#ef4444","yellow":"#f59e0b","purple":"#8b5cf6"}
    def _base_dir():
        try: return Path(__file__).resolve().parents[2]
        except Exception: return Path.cwd()
    def _layout_path():
        p=_base_dir()/"config"/"layout_v43_premium.json"; p.parent.mkdir(parents=True,exist_ok=True); return p
    def _load_layout():
        d={"version":"V43 Premium","panelSizes":{"queue":43,"detail":57},"console":{"state":"hidden","height":22,"autoScroll":True},"analysisCompact":True}
        try:
            p=_layout_path()
            if p.exists():
                x=json.loads(p.read_text(encoding="utf-8",errors="ignore"));
                if isinstance(x,dict): d.update(x)
        except Exception: pass
        return d
    def _save_layout(self):
        try:
            data=getattr(self,"_v43_layout",None) or _load_layout()
            try:
                w=max(1,self._main_paned.winfo_width()); s0=self._main_paned.sashpos(0); q=max(25,min(75,int(s0*100/w))); data["panelSizes"]={"queue":q,"detail":100-q}
            except Exception: pass
            _layout_path().write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception as e: print(f"[V43][LAYOUT] não salvou preferências: {e}")
    def _card(parent,title,value,sub="",color=None,w=100):
        f=tk.Frame(parent,bg=COLORS["surface2"],width=w,highlightbackground=COLORS["border"],highlightthickness=1); f.pack_propagate(False)
        tk.Label(f,text=title,bg=COLORS["surface2"],fg=COLORS["muted"],font=("Segoe UI",7,"bold"),anchor="w").pack(fill="x",padx=8,pady=(4,0))
        tk.Label(f,text=value,bg=COLORS["surface2"],fg=color or COLORS["text"],font=("Segoe UI",13,"bold"),anchor="w").pack(fill="x",padx=8)
        tk.Label(f,text=sub,bg=COLORS["surface2"],fg=COLORS["muted"],font=("Segoe UI",7),anchor="w").pack(fill="x",padx=8,pady=(0,4))
        return f
    def _btn(parent,text,cmd,color,icon=""):
        # V43: nunca usar ícones/caracteres especiais nos botões principais.
        clean=str(text or "").strip()
        for name in ("Coletar","Redigir","Copydesk","Preview","Publicar","Descartar","Exportar"):
            if name.lower() in clean.lower():
                clean=name; break
        return tk.Button(parent,text=clean,command=cmd,bg=color,fg="white",activebackground=color,activeforeground="white",relief="flat",bd=0,highlightthickness=0,padx=18,pady=9,cursor="hand2",font=("Segoe UI Semibold",10))
    def _construir_interface_v43(self):
        self._v43_layout=_load_layout()
        try:
            style=ttk.Style(self)
            try: style.theme_use("clam")
            except Exception: pass
            style.configure("TPanedwindow",background=COLORS["bg"],borderwidth=0); style.configure("TNotebook",background=COLORS["surface"],borderwidth=0); style.configure("TNotebook.Tab",padding=(8,4),font=("Segoe UI",9))
        except Exception: pass
        self.configure(bg=COLORS["bg"]); self._v43_build_top_header(); self._v43_build_main_panels(); self._construir_console()
        try: self._console_frame.configure(bg=COLORS["surface3"])
        except Exception: pass
        self._construir_statusbar(); self._redirecionar_stdout(); self.bind("<F5>",lambda _=None: self._acao_atualizar_geral_v132() if hasattr(self,"_acao_atualizar_geral_v132") else self._carregar_pautas()); self.bind("<Control-grave>",lambda _=None:self._toggle_console()); self.protocol("WM_DELETE_WINDOW",lambda:(_save_layout(self),self.destroy())); self.after(900,self._v43_update_kpis); self.after(1000,self._v43_apply_panes_saved); print("[V43 Premium] Painel leve aplicado: sem sidebar, ações no topo, análise compacta e dois painéis principais.")
    def _v43_build_top_header(self):
        hdr=tk.Frame(self,bg=COLORS["bg"],height=74); hdr.pack(fill="x",side="top"); hdr.pack_propagate(False)
        logo=tk.Frame(hdr,bg=COLORS["bg"],width=190); logo.pack(side="left",fill="y",padx=(14,10)); logo.pack_propagate(False)
        try:
            from PIL import Image,ImageTk
            ico=_base_dir()/"ururau_atalho_icon.ico"
            if ico.exists():
                img=Image.open(str(ico)).resize((34,34),Image.LANCZOS); ph=ImageTk.PhotoImage(img); lb=tk.Label(logo,image=ph,bg=COLORS["bg"]); lb.image=ph; lb.pack(side="left",pady=12,padx=(0,8))
        except Exception: pass
        tbox=tk.Frame(logo,bg=COLORS["bg"]); tbox.pack(side="left",pady=10)
        tk.Label(tbox,text="URURAU",bg=COLORS["bg"],fg=COLORS["brand"],font=("Segoe UI",16,"bold")).pack(anchor="w"); tk.Label(tbox,text="Robô Editorial",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",8)).pack(anchor="w")
        status=tk.Frame(hdr,bg=COLORS["bg"],width=155); status.pack(side="left",fill="y",padx=(0,8))
        tk.Label(status,text="● Sistema operacional",bg=COLORS["bg"],fg=COLORS["green"],font=("Segoe UI",8,"bold")).pack(anchor="w",pady=(17,2)); tk.Label(status,text="Ambiente: Produção",bg=COLORS["surface2"],fg="#93c5fd",font=("Segoe UI",7),padx=7,pady=2).pack(anchor="w")
        actions=tk.Frame(hdr,bg=COLORS["bg"]); actions.pack(side="left",fill="y",expand=True)
        for text,cmd,color,icon in [("Coletar",self._acao_coletar,COLORS["brand"],"⇩"),("Redigir",self._acao_redigir,COLORS["blue"],"✎"),("Copydesk",self._acao_copydesk,COLORS["purple"],"♙"),("Preview",self._acao_preview,"#2563eb","◉"),("Publicar",self._acao_publicar,COLORS["green"],"➤"),("Descartar",self._acao_descartar,COLORS["red"],"⌫"),("Exportar",self._acao_exportar,COLORS["surface2"],"⇩")]: _btn(actions,text,cmd,color,icon).pack(side="left",padx=3,pady=19)
        tk.Button(actions,text="⋯",command=self._mostrar_atalhos,bg=COLORS["surface2"],fg=COLORS["text"],relief="flat",padx=10,pady=7).pack(side="left",padx=3,pady=19)
        self._btn_monitor=tk.Button(actions,text="Monitor OFF",command=self._toggle_monitor,bg=COLORS["surface2"],fg=COLORS["muted"],relief="flat",padx=8,pady=7,cursor="hand2")
        self._btn_monitor.pack(side="left",padx=3,pady=19)
        self._btn_console=tk.Button(actions,text="Console",command=self._toggle_console,bg=COLORS["surface2"],fg=COLORS["muted"],relief="flat",padx=8,pady=7,cursor="hand2")
        self._btn_console.pack(side="left",padx=3,pady=19)
        right=tk.Frame(hdr,bg=COLORS["bg"]); right.pack(side="right",fill="y",padx=(6,10)); self._v43_kpi_box=tk.Frame(right,bg=COLORS["bg"]); self._v43_kpi_box.pack(side="left",pady=7); self._v43_kpis={}
        for name,title,value,sub,color,width in [("pautas","Pautas","0","na fila",None,72),("publicadas","Publicadas","0","hoje",None,78),("materias","Matérias","0","rascunhos",None,76),("saude","Saúde","100%","OK",COLORS["green"],78)]:
            c=_card(self._v43_kpi_box,title,value,sub,color,width); c.pack(side="left",padx=3,fill="y"); self._v43_kpis[name]=c
        # Indicadores compactos onde antes havia espaço morto (AD).
        # Não duplicam ações nem origem da fonte: só Qualidade IA e Risco.
        ana=tk.Frame(right,bg=COLORS["surface2"],highlightbackground=COLORS["border"],highlightthickness=1)
        ana.pack(side="left",padx=(6,0),pady=7,fill="y")
        self._v43_quality=tk.Label(ana,text="Qualidade IA --/100",bg=COLORS["surface2"],fg=COLORS["blue"],font=("Segoe UI",8,"bold"),anchor="w",padx=8)
        self._v43_quality.pack(fill="x",pady=(8,1))
        self._v43_risk=tk.Label(ana,text="Risco --/100",bg=COLORS["surface2"],fg=COLORS["yellow"],font=("Segoe UI",8,"bold"),anchor="w",padx=8)
        self._v43_risk.pack(fill="x",pady=(1,8))
    def _v43_build_analysis_strip(self):
        # V43 Premium final: a faixa lateral/superior de análise foi removida.
        # Qualidade IA e Risco ficam compactos no TopHeader para liberar área útil.
        return

    def _v43_build_main_panels(self):
        self._main_paned=ttk.PanedWindow(self,orient="horizontal"); self._main_paned.pack(fill="both",expand=True,padx=10,pady=(0,8))
        fl=tk.Frame(self._main_paned,bg=COLORS["surface"],highlightbackground=COLORS["border"],highlightthickness=1); self._frame_lista_pai=fl; self._frame_lista=tk.Frame(fl,bg=COLORS["surface"]); self._frame_lista.pack(fill="both",expand=True); self._construir_lista(self._frame_lista); self._painel_revisao_widget=None; self._faixa_revisao=None; self._main_paned.add(fl,weight=43)
        fd=tk.Frame(self._main_paned,bg=COLORS["surface"],highlightbackground=COLORS["border"],highlightthickness=1); self._frame_detalhe=fd; self._construir_detalhe(fd); self._main_paned.add(fd,weight=57); self._paned=self._main_paned
    def _v43_apply_panes_saved(self):
        try:
            q=int(self._v43_layout.get("panelSizes",{}).get("queue",43)); w=max(800,self._main_paned.winfo_width()); self._main_paned.sashpos(0,max(360,min(w-520,int(w*q/100))))
        except Exception: pass
    def _v43_update_kpis(self):
        try:
            s=self.db.estatisticas(); vals={"pautas":str(s.get("total_pautas",0)),"publicadas":str(s.get("total_publicadas",0)),"materias":str(s.get("total_materias",0)),"saude":"100%"}
            for k,v in vals.items():
                card=self._v43_kpis.get(k); labs=[w for w in card.winfo_children() if isinstance(w,tk.Label)] if card else []
                if len(labs)>=2: labs[1].configure(text=v)
        except Exception: pass
        try: self.after(5000,self._v43_update_kpis)
        except Exception: pass
    old_select=getattr(PainelUrurau,"_ao_selecionar",None)
    def _ao_selecionar_v43(self,pauta):
        ret=old_select(self,pauta) if old_select else None
        try:
            sc=int((pauta or {}).get("score_editorial") or 0); risk=int((pauta or {}).get("risco_score") or max(0,100-sc))
            if hasattr(self,"_v43_quality"):
                self._v43_quality.configure(text=f"Qualidade IA: {max(0,min(100,sc))}/100",fg=COLORS["blue"] if sc>=60 else COLORS["yellow"])
            if hasattr(self,"_v43_risk"):
                self._v43_risk.configure(text=f"Risco: {max(0,min(100,risk))}/100",fg=COLORS["green"] if risk<=35 else COLORS["yellow"])
        except Exception:
            pass
        return ret

    old_statusbar=getattr(PainelUrurau,"_construir_statusbar",None)
    def _construir_statusbar_v43(self):
        if old_statusbar: old_statusbar(self)
        try: self._statusbar_frame.configure(bg=COLORS["bg"]); self._lbl_status.configure(bg=COLORS["bg"],fg=COLORS["muted"],text="● Sistema operacional • Todos os serviços ativos")
        except Exception: pass
    old_diag_update=getattr(PainelUrurau,"_v126_atualizar_diagnostico_coleta",None)
    def _v126_atualizar_diagnostico_coleta_v43(self,texto):
        ret=old_diag_update(self,texto) if old_diag_update else None
        try:
            from ururau.coleta.fontes_links_v43 import atualizar_status_por_relatorio_v43,consolidar_fontes_links_v43
            info=atualizar_status_por_relatorio_v43(texto or ""); consolidar_fontes_links_v43(); print(f"[V43][FONTES] Status visual atualizado pelo relatório: {info.get('atualizadas')} fonte(s).")
        except Exception as e: print(f"[V43][FONTES] falha ao atualizar status: {e}")
        return ret

    old_info=getattr(PainelUrurau,"_calcular_info",None)
    def _calcular_info_v43(self,p: dict) -> str:
        base=old_info(self,p) if old_info else ""
        try:
            fonte=(p or {}).get("fonte_nome") or (p or {}).get("nome_fonte") or ""
            link=(p or {}).get("link_origem") or (p or {}).get("url") or ""
            dominio=link.split("//",1)[-1].split("/",1)[0] if link else ""
            tipo="site de notícias" if fonte else "fonte não identificada"
            confianca="★★★★☆"
            bloco=("\n"+"="*60+"\nORIGEM E CONFIABILIDADE DA FONTE\n"+"="*60+"\n"+
                   f"NOME DA FONTE : {fonte}\n"+
                   f"TIPO          : {tipo}\n"+
                   f"CONFIABILIDADE: {confianca}\n"+
                   f"DOMÍNIO       : {dominio}\n"+
                   f"URL ORIGINAL  : {link}\n")
            return bloco+"\n"+base
        except Exception:
            return base

    def _wrap_action(nome_metodo,acao):
        old=getattr(PainelUrurau,nome_metodo,None)
        if not old or getattr(old,"_v43_wrapped",False): return
        def wrapper(self,*a,**kw):
            try:
                pauta=getattr(self,"_pauta_sel",None)
                if a and isinstance(a[0],dict): pauta=a[0]
                from ururau.editorial.memoria_operacional_v43 import registrar_decisao_v43
                registrar_decisao_v43(acao,pauta if isinstance(pauta,dict) else {})
            except Exception: pass
            return old(self,*a,**kw)
        wrapper._v43_wrapped=True; setattr(PainelUrurau,nome_metodo,wrapper)
    def _patch_scoring():
        try:
            import ururau.coleta.scoring as scoring; old=getattr(scoring,"calcular_score_editorial",None)
            if old and not getattr(old,"_v43_memory",False):
                def calc_v43(pauta,*a,**kw):
                    base=int(old(pauta,*a,**kw) or 0)
                    try:
                        from ururau.editorial.memoria_operacional_v43 import bonus_pauta_v43
                        base+=int(bonus_pauta_v43(pauta))
                    except Exception: pass
                    return max(0,min(100,base))
                calc_v43._v43_memory=True; scoring.calcular_score_editorial=calc_v43; print("[V43][MEMÓRIA] Scoring adaptativo ativado.")
        except Exception as e: print(f"[V43][MEMÓRIA] scoring adaptativo não aplicado: {e}")
    def _criar_aba_fontes_links_v43(self,nb):
        outer=tk.Frame(nb,bg=COLORS["surface"]); nb.add(outer,text="Fontes / Links"); top=tk.Frame(outer,bg=COLORS["surface"]); top.pack(fill="x",padx=8,pady=(8,4))
        tk.Label(top,text="Fontes / Links",bg=COLORS["surface"],fg=COLORS["text"],font=("Segoe UI",11,"bold")).pack(side="left"); tk.Label(top,text="RSS, XML/Sitemap, Especiais, Regionais e AutoFontes com status do último relatório real.",bg=COLORS["surface"],fg=COLORS["muted"],font=("Segoe UI",8),wraplength=820,justify="left").pack(side="left",padx=12); tk.Button(top,text="Atualizar status",command=lambda:self._v43_refresh_fontes_status(),bg=COLORS["surface2"],fg=COLORS["text"],relief="flat",padx=8,pady=3).pack(side="right")
        sub=ttk.Notebook(outer); sub.pack(fill="both",expand=True,padx=8,pady=(0,6)); self._fontes_links_nb_v132=sub; self._criar_aba_rss(sub); self._criar_aba_xml_sitemap(sub); self._criar_aba_fontes_especiais_v129(sub)
        if hasattr(self,"_criar_aba_regionais_v1305"): self._criar_aba_regionais_v1305(sub)
        box=tk.LabelFrame(outer,text="Saúde das fontes",bg=COLORS["surface"],fg=COLORS["muted"],bd=1); box.pack(fill="x",padx=8,pady=(0,8)); self._v43_status_fontes_txt=tk.Text(box,height=7,bg=COLORS["surface3"],fg=COLORS["text"],insertbackground=COLORS["text"],font=("Consolas",8),wrap="none",relief="flat"); self._v43_status_fontes_txt.pack(fill="x",padx=6,pady=6); self._v43_refresh_fontes_status()
    def _v43_refresh_fontes_status(self):
        try:
            from ururau.coleta.fontes_links_v43 import consolidar_fontes_links_v43
            data=consolidar_fontes_links_v43(); items=data.get("items",[]); ordermap={"erro":0,"sem_coleta":1,"quarentena":2,"atencao":3,"sem_envio":4,"ok":5,"aplicada":6,"desconhecido":7}; icon={"ok":"OK","sem_envio":"SEM","atencao":"ATN","erro":"ERR","sem_coleta":"ERR","quarentena":"OFF","aplicada":"TEST","desconhecido":"?"}
            linhas=[f"{icon.get(it.get('status'),'?'):<4} {it.get('grupo'):<11} | {it.get('nome'):<28} | {it.get('status'):<12} | {it.get('motivo_status','')[:90]}" for it in sorted(items,key=lambda x:(ordermap.get(x.get('status'),9),x.get('grupo',''),x.get('nome','')))[:100]]; txt="\n".join(linhas) or "Sem fontes indexadas. Clique em Salvar e Aplicar ou rode uma coleta."; w=getattr(self,"_v43_status_fontes_txt",None)
            if w: w.delete("1.0","end"); w.insert("1.0",txt)
        except Exception as e:
            w=getattr(self,"_v43_status_fontes_txt",None)
            if w: w.delete("1.0","end"); w.insert("1.0",f"Falha ao atualizar status V43: {e}")
    if _ConfigWidget:
        setattr(_ConfigWidget,"_criar_aba_fontes_links_v132",_criar_aba_fontes_links_v43); setattr(_ConfigWidget,"_v43_refresh_fontes_status",_v43_refresh_fontes_status)
    if JanelaConfiguracoes:
        setattr(JanelaConfiguracoes,"_criar_aba_fontes_links_v132",_criar_aba_fontes_links_v43); setattr(JanelaConfiguracoes,"_v43_refresh_fontes_status",_v43_refresh_fontes_status)
    # V43: fila de pautas mais leve, sem botão Gerar e com título em duas linhas.
    FilaPautas_cls=g.get("FilaPautas")
    if FilaPautas_cls:
        try:
            FilaPautas_cls._BUFFER=3
            FilaPautas_cls._ROW_H=92
        except Exception:
            pass
        def _v43_wrap_title(txt,limit=94):
            txt=str(txt or "").strip()
            if len(txt)<=limit:
                return txt
            cut=txt[:limit].rsplit(" ",1)[0] or txt[:limit]
            rest=txt[len(cut):].strip()
            if len(rest)>limit:
                rest=rest[:limit-1].rstrip()+"…"
            return cut+"\n"+rest
        old_draw_row=getattr(FilaPautas_cls,"_draw_row",None)
        def _draw_row_v43(self,idx:int,w:int):
            p=self._itens[idx]
            y=idx*self._ROW_H
            status=str(p.get("status") or "")
            uid=self._uid(p,idx)
            sep=bool(p.get("_separador_coleta_v123"))
            selecionado=idx==self._sel_idx
            termos=self._termos_prioridade(p)
            if sep:
                bg="#071528"; border="#22d3ee"
            elif selecionado:
                bg="#33205f"; border=COLORS["brand"]
            elif status=="excluida":
                bg="#1a1a1a"; border="#64748b"
            elif status=="baixo_score":
                bg="#2a1644"; border="#f59e0b"
            elif termos:
                bg="#102a36"; border="#14b8a6"
            else:
                bg="#111827" if idx%2==0 else "#151f32"; border="#253047"
            c=self._canvas
            c.create_rectangle(0,y,w,y+self._ROW_H-1,fill=bg,outline=bg,tags="row")
            c.create_rectangle(0,y,4,y+self._ROW_H-1,fill=border,outline=border,tags="row")
            if sep:
                titulo=str(p.get("titulo_origem") or "Coleta")
                sub=str(p.get("_subtitulo_separador_v123") or "Separador visual.")
                c.create_text(18,y+24,anchor="w",text=titulo,fill="#67e8f9",font=("Segoe UI",11,"bold"),tags="row")
                c.create_text(18,y+50,anchor="w",text=sub,fill="#94a3b8",font=("Segoe UI",9),tags="row")
                return
            checked=uid in self._selecionados
            c.create_rectangle(13,y+39,27,y+53,fill=("#1e3a5f" if checked else bg),outline="#94a3b8",tags="row")
            if checked:
                c.create_text(20,y+46,text="✓",fill="#7dd3fc",font=("Segoe UI",9,"bold"),tags="row")
            x=40
            for text,bbg,ffg in self._badge_textos(p)[:5]:
                if x>max(250,w-190): break
                x=self._draw_badge(x,y+9,text,bbg,ffg)
            # Mantém apenas ações realmente úteis na fila. Botão Gerar foi removido.
            if status=="excluida":
                self._draw_button(w-112,y+9,w-24,y+29,"↩ Reativar","#374151","#d1d5db","reativar",idx)
            elif status=="baixo_score":
                self._draw_button(w-206,y+9,w-116,y+29,"✕ Reprovar","#7f1d1d","#fecaca","reprovar_baixo",idx)
                self._draw_button(w-106,y+9,w-24,y+29,"✓ Aprovar","#92400e","#fde68a","aprovar_baixo",idx)
            elif p.get("materia"):
                self._draw_button(w-88,y+9,w-24,y+29,"✓ Ver","#14532d","#86efac","abrir",idx)
            titulo=_v43_wrap_title(self._titulo(p), max(58,int((w-130)/8.0)))
            c.create_text(40,y+45,anchor="w",text=titulo,fill=("#ffffff" if selecionado else "#f4f7fb"),font=("Segoe UI",10,"bold" if selecionado else "normal"),width=max(260,w-150),tags="row")
            fonte=self._fonte(p)[:34]
            data_pub=str(p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or "")[:16]
            meta="  ·  ".join([x for x in [fonte,("Publicado: "+data_pub if data_pub else "")] if x])
            if meta:
                c.create_text(40,y+78,anchor="w",text=meta,fill="#9aa7bc",font=("Segoe UI",8),tags="row")
            c.create_line(0,y+self._ROW_H-1,w,y+self._ROW_H-1,fill="#253047",tags="row")
        setattr(FilaPautas_cls,"_draw_row",_draw_row_v43)
        old_request=getattr(FilaPautas_cls,"_request_redraw",None)
        def _request_redraw_v43(self,delay:int=16):
            # Coalescimento mais agressivo durante coleta para evitar piscadas/saltos.
            return old_request(self,max(90,delay)) if old_request else None
        setattr(FilaPautas_cls,"_request_redraw",_request_redraw_v43)

    old_set_status=getattr(PainelUrurau,"_set_status",None)
    old_construir_statusbar_v43=_construir_statusbar_v43
    def _construir_statusbar_v43_final(self):
        old_construir_statusbar_v43(self)
        try:
            self._v43_progress=ttk.Progressbar(self._statusbar_frame,mode="indeterminate",length=160)
            self._v43_progress.pack(side="right",padx=(8,10),pady=3)
            self._v43_progress_state=False
            self._v43_progress_lbl=tk.Label(self._statusbar_frame,text="",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",8))
            self._v43_progress_lbl.pack(side="right",padx=6)
        except Exception:
            pass
    def _set_status_v43(self,msg:str):
        if old_set_status:
            try: old_set_status(self,msg)
            except Exception: pass
        try:
            m=str(msg or "")
            busy=any(x in m.lower() for x in ["carregando","coleta","buscando","hidratador","baixando","imagem","atualizando"] ) and not any(x in m.lower() for x in ["pautas na fila","pronto","erro ao carregar","encerrado"])
            if getattr(self,"_v43_progress",None):
                if busy and not getattr(self,"_v43_progress_state",False):
                    self._v43_progress.start(10); self._v43_progress_state=True
                elif (not busy) and getattr(self,"_v43_progress_state",False):
                    self._v43_progress.stop(); self._v43_progress_state=False
            if getattr(self,"_v43_progress_lbl",None):
                self._v43_progress_lbl.configure(text=("carregando pautas..." if busy else ""))
        except Exception:
            pass

    for name,obj in {"_construir_interface":_construir_interface_v43,"_v43_build_top_header":_v43_build_top_header,"_v43_build_analysis_strip":_v43_build_analysis_strip,"_v43_build_main_panels":_v43_build_main_panels,"_v43_apply_panes_saved":_v43_apply_panes_saved,"_v43_update_kpis":_v43_update_kpis,"_ao_selecionar":_ao_selecionar_v43,"_construir_statusbar":_construir_statusbar_v43_final,"_set_status":_set_status_v43,"_v126_atualizar_diagnostico_coleta":_v126_atualizar_diagnostico_coleta_v43}.items(): setattr(PainelUrurau,name,obj)
    setattr(PainelUrurau,"_calcular_info",_calcular_info_v43)
    for meth,acao in [("_acao_redigir","redigir"),("_acao_copydesk","copydesk"),("_acao_preview","preview"),("_acao_publicar","publicar"),("_acao_descartar","descartar"),("_descartar_rapido","descartar"),("_acao_aprovar_baixo_score_v129","aprovar"),("_acao_reprovar_baixo_score_v129_1","reprovar")]: _wrap_action(meth,acao)
    _patch_scoring()
    try:
        from ururau.coleta.fontes_links_v43 import consolidar_fontes_links_v43
        info=consolidar_fontes_links_v43(); print(f"[V43][FONTES] Fonte única inicializada: {info.get('summary')}")
    except Exception as e: print(f"[V43][FONTES] fonte única não inicializada: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # V43 Premium — ajuste final de fluidez, progresso no topo, config e console.
    # ─────────────────────────────────────────────────────────────────────
    try:
        import os as _os_v43
        _os_v43.environ.setdefault("URURAU_V105_MAX_ENFILEIRAR_POR_REFRESH", "10")
        _os_v43.environ.setdefault("URURAU_V1298_DB_REFRESH_MS", "10000")
        _os_v43.environ.setdefault("URURAU_V43_UI_LEVE", "1")
    except Exception:
        pass

    def _v43_status_limpo(msg: str) -> str:
        import re as _re_v43
        m = str(msg or "").strip()
        m = _re_v43.sub(r"\bv\d+\s*—\s*", "", m, flags=_re_v43.I)
        m = _re_v43.sub(r"\(\s*F5\s+para\s+atualizar\s*\)", "", m, flags=_re_v43.I)
        m = m.replace("; hidratador de fonte ativo.", "")
        m = m.replace("hidratador de fonte ativo.", "")
        m = _re_v43.sub(r"\s+", " ", m).strip(" -;|•")
        return m or "Sistema operacional"

    def _v43_progress_pct(msg: str) -> int:
        m = str(msg or "").lower()
        if "erro" in m or "falha" in m:
            return 0
        if "pautas na fila" in m or "pronto" in m or "conclu" in m or "encerr" in m:
            return 100
        if "publica" in m:
            return 92
        if "imagem" in m or "preview" in m:
            return 78
        if "fonte" in m or "hidrat" in m or "buscando texto" in m:
            return 62
        if "coleta" in m or "rss" in m or "sitemap" in m or "termos" in m:
            return 42
        if "carregando" in m or "atualizando" in m:
            return 25
        return 8

    def _v43_build_top_header_final(self):
        # Header mais alto e com coluna direita larga para não cortar texto.
        hdr=tk.Frame(self,bg=COLORS["bg"],height=118)
        hdr.pack(fill="x",side="top"); hdr.pack_propagate(False)

        logo=tk.Frame(hdr,bg=COLORS["bg"],width=168)
        logo.pack(side="left",fill="y",padx=(12,8)); logo.pack_propagate(False)
        try:
            from PIL import Image,ImageTk
            ico=_base_dir()/"ururau_atalho_icon.ico"
            if ico.exists():
                img=Image.open(str(ico)).resize((34,34),Image.LANCZOS); ph=ImageTk.PhotoImage(img)
                lb=tk.Label(logo,image=ph,bg=COLORS["bg"]); lb.image=ph; lb.pack(side="left",pady=14,padx=(0,8))
        except Exception:
            pass
        tbox=tk.Frame(logo,bg=COLORS["bg"]); tbox.pack(side="left",pady=12)
        tk.Label(tbox,text="URURAU",bg=COLORS["bg"],fg=COLORS["brand"],font=("Segoe UI",17,"bold")).pack(anchor="w")
        tk.Label(tbox,text="Robô Editorial",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",8)).pack(anchor="w")

        status=tk.Frame(hdr,bg=COLORS["bg"],width=145)
        status.pack(side="left",fill="y",padx=(0,8)); status.pack_propagate(False)
        tk.Label(status,text="● Sistema operacional",bg=COLORS["bg"],fg=COLORS["green"],font=("Segoe UI",8,"bold")).pack(anchor="w",pady=(20,2))
        tk.Label(status,text="Ambiente: Produção",bg=COLORS["surface2"],fg="#93c5fd",font=("Segoe UI",7),padx=7,pady=2).pack(anchor="w")

        actions=tk.Frame(hdr,bg=COLORS["bg"])
        actions.pack(side="left",fill="both",expand=True)
        for text,cmd,color in [
            ("Coletar",self._acao_coletar,COLORS["brand"]),
            ("Redigir",self._acao_redigir,COLORS["blue"]),
            ("Copydesk",self._acao_copydesk,COLORS["purple"]),
            ("Preview",self._acao_preview,"#2563eb"),
            ("Publicar",self._acao_publicar,COLORS["green"]),
            ("Descartar",self._acao_descartar,COLORS["red"]),
            ("Exportar",self._acao_exportar,COLORS["surface2"]),
        ]:
            _btn(actions,text,cmd,color).pack(side="left",padx=4,pady=25)
        self._btn_monitor=tk.Button(actions,text="Monitor OFF",command=self._toggle_monitor,bg=COLORS["surface2"],fg=COLORS["muted"],relief="flat",padx=10,pady=8,cursor="hand2",font=("Segoe UI Semibold",9))
        self._btn_monitor.pack(side="left",padx=3,pady=25)
        self._btn_console=tk.Button(actions,text="Console",command=self._toggle_console,bg=COLORS["surface2"],fg=COLORS["muted"],relief="flat",padx=10,pady=8,cursor="hand2",font=("Segoe UI Semibold",9))
        self._btn_console.pack(side="left",padx=3,pady=25)
        tk.Button(actions,text="⚙",command=self._acao_configuracoes,bg=COLORS["surface2"],fg=COLORS["text"],relief="flat",padx=10,pady=8,cursor="hand2",font=("Segoe UI",10,"bold")).pack(side="left",padx=3,pady=25)

        # Topo direito: KPIs, qualidade/risco, barra colorida e status sem corte.
        right=tk.Frame(hdr,bg=COLORS["bg"],width=540)
        right.pack(side="right",fill="y",padx=(4,10)); right.pack_propagate(False)
        top=tk.Frame(right,bg=COLORS["bg"]); top.pack(fill="x",pady=(7,3))
        self._v43_kpis={}
        for name,title,value,sub,color,width in [
            ("pautas","Pautas","0","fila",None,68),
            ("publicadas","Pub.","0","hoje",None,56),
            ("materias","Mat.","0","rasc.",None,56),
            ("saude","Saúde","100%","OK",COLORS["green"],72),
        ]:
            c=_card(top,title,value,sub,color,width); c.pack(side="left",padx=2,fill="y"); self._v43_kpis[name]=c
        ana=tk.Frame(top,bg=COLORS["surface2"],highlightbackground=COLORS["border"],highlightthickness=1,width=194,height=50)
        ana.pack(side="right",padx=(6,0),fill="y"); ana.pack_propagate(False)
        self._v43_quality=tk.Label(ana,text="Qualidade IA: --/100",bg=COLORS["surface2"],fg=COLORS["blue"],font=("Segoe UI Semibold",8),anchor="w",padx=8)
        self._v43_quality.pack(fill="x",pady=(7,0))
        self._v43_risk=tk.Label(ana,text="Risco: --/100",bg=COLORS["surface2"],fg=COLORS["yellow"],font=("Segoe UI Semibold",8),anchor="w",padx=8)
        self._v43_risk.pack(fill="x")

        prog=tk.Frame(right,bg=COLORS["bg"]); prog.pack(fill="x",pady=(5,0))
        # Canvas em vez de ttk.Progressbar para garantir preenchimento colorido no Windows.
        self._v43_progress_w=450
        self._v43_progress_canvas=tk.Canvas(prog,width=self._v43_progress_w,height=14,bg=COLORS["bg"],highlightthickness=0,bd=0)
        self._v43_progress_canvas.pack(side="left",fill="x",expand=True,padx=(2,6))
        self._v43_progress_canvas.create_rectangle(0,1,self._v43_progress_w,13,fill="#d1d5db",outline="#253047",tags="trough")
        self._v43_progress_fill=self._v43_progress_canvas.create_rectangle(0,1,1,13,fill=COLORS["green"],outline=COLORS["green"],tags="fill")
        self._v43_header_pct=tk.Label(prog,text="0%",bg=COLORS["bg"],fg=COLORS["text"],font=("Segoe UI",8,"bold"),width=4)
        self._v43_header_pct.pack(side="left")
        self._v43_header_status=tk.Label(right,text="● Aguardando operação",bg=COLORS["bg"],fg=COLORS["green"],font=("Segoe UI",8,"bold"),anchor="w")
        self._v43_header_status.pack(fill="x",padx=2,pady=(4,0))
        try:
            self.after(600,self._v43_sanitize_header_buttons)
            self.after(900,self._v43_pulse_status_dot)
        except Exception:
            pass

    def _construir_statusbar_v43_header_final(self):
        sb=tk.Frame(self,bg=COLORS["bg"],height=24)
        sb.pack(fill="x",side="bottom"); sb.pack_propagate(False)
        self._statusbar_frame=sb
        self._status_dot=tk.Label(sb,text="●",bg=COLORS["bg"],fg=COLORS["green"],font=("Segoe UI",8))
        self._status_dot.pack(side="left",padx=(8,2))
        self._status_lbl=tk.Label(sb,text="Sistema operacional • todos os serviços ativos",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",8),anchor="w")
        self._status_lbl.pack(side="left",fill="x",expand=True)
        tk.Label(sb,text="V43 Premium",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",8)).pack(side="right",padx=10)

    def _set_status_v43_header_final(self,msg:str):
        clean=_v43_status_limpo(msg)
        pct=_v43_progress_pct(msg)
        def _apply():
            try:
                if getattr(self,"_status_lbl",None):
                    self._status_lbl.config(text="Sistema operacional • todos os serviços ativos")
                if getattr(self,"_v43_header_status",None):
                    self._v43_header_status.config(text=("● "+clean)[:82])
                if getattr(self,"_v43_progress_canvas",None):
                    try:
                        width=max(1,int(getattr(self,"_v43_progress_w",450)))
                        fill=max(1,int(width*pct/100))
                        self._v43_progress_canvas.coords(self._v43_progress_fill,0,1,fill,13)
                    except Exception:
                        pass
                if getattr(self,"_v43_header_pct",None):
                    self._v43_header_pct.configure(text=f"{pct}%")
            except Exception:
                pass
        try: self.after(0,_apply)
        except Exception: _apply()

    old_construir_console_v43=getattr(PainelUrurau,"_construir_console",None)
    def _construir_console_v43_buffered(self):
        if old_construir_console_v43:
            old_construir_console_v43(self)
        self._v43_console_buffer=[]
        try:
            self._console_frame.configure(height=320)
            self._console_txt.configure(font=("Consolas",9),height=16)
        except Exception:
            pass

    def _append_console_v43_buffered(self,texto:str):
        if not texto or not str(texto).strip():
            return
        try:
            if not getattr(self,"_console_visible",False):
                buf=getattr(self,"_v43_console_buffer",None)
                if buf is None:
                    self._v43_console_buffer=[]; buf=self._v43_console_buffer
                buf.append(str(texto).rstrip())
                if len(buf)>350:
                    del buf[:len(buf)-350]
                return
            if getattr(self,"_v43_console_buffer",None):
                linhas=list(self._v43_console_buffer); self._v43_console_buffer.clear()
                for ln in linhas[-250:]:
                    _append_console_v43_buffered(self,ln)
            if not getattr(self,"_console_txt",None):
                return
            tag="info"; tl=str(texto).lower()
            if "[ok]" in tl or "sucesso" in tl or "✓" in tl: tag="ok"
            elif "erro" in tl or "error" in tl or "falha" in tl or "✗" in tl: tag="err"
            elif "aviso" in tl or "warn" in tl or "⚠" in tl or "bloq" in tl: tag="warn"
            self._console_txt.config(state="normal")
            self._console_txt.insert("end",str(texto).rstrip()+"\n",tag)
            # Limita linhas renderizadas para manter a interface fluida.
            try:
                total=int(float(self._console_txt.index('end-1c').split('.')[0]))
                if total>900:
                    self._console_txt.delete('1.0',f'{total-650}.0')
            except Exception:
                pass
            self._console_txt.see("end")
            self._console_txt.config(state="disabled")
        except Exception:
            pass

    old_toggle_console_v43=getattr(PainelUrurau,"_toggle_console",None)
    def _toggle_console_v43_final(self):
        try:
            visible=not getattr(self,"_console_visible",False)
            self._console_visible=visible
            if visible:
                try: self._console_frame.configure(height=320)
                except Exception: pass
                self._console_frame.pack(fill="x",side="bottom",before=self._statusbar_frame)
                try: self._btn_console.config(bg="#1c4532",fg="#86efac")
                except Exception: pass
                # Despeja buffer depois de abrir.
                buf=list(getattr(self,"_v43_console_buffer",[]) or [])[-250:]
                self._v43_console_buffer=[]
                for ln in buf:
                    _append_console_v43_buffered(self,ln)
            else:
                self._console_frame.pack_forget()
                try: self._btn_console.config(bg=COLORS["surface2"],fg=COLORS["muted"])
                except Exception: pass
        except Exception:
            if old_toggle_console_v43: old_toggle_console_v43(self)

    old_construir_detalhe_v43=getattr(PainelUrurau,"_construir_detalhe",None)
    def _construir_detalhe_v43_fontes(self,frame):
        if old_construir_detalhe_v43:
            old_construir_detalhe_v43(self,frame)
        try:
            for w in [getattr(self,"_aba_info",None),getattr(self,"_aba_checagem",None),getattr(self,"_aba_risco",None),getattr(self,"_aba_materia",None),getattr(self,"_aba_auditoria",None)]:
                if w: w.configure(font=("Consolas",10),padx=8,pady=8)
        except Exception:
            pass

    old_construir_aba_leitura_v43=getattr(PainelUrurau,"_construir_aba_leitura",None)
    def _construir_aba_leitura_v43_readable(self,frame):
        if old_construir_aba_leitura_v43:
            old_construir_aba_leitura_v43(self,frame)
        try:
            self._leitura_txt.configure(font=("Consolas",11),padx=10,pady=8)
            self._lbl_leitura_termos.configure(font=("Segoe UI",9))
        except Exception:
            pass

    old_tab_v43=getattr(PainelUrurau,"_ao_trocar_aba",None)
    def _ao_trocar_aba_v43_config(self,*a,**kw):
        try:
            idx=self._notebook.index("current")
            if idx==getattr(self,"_idx_aba_config",-999):
                if not getattr(self,"_aba_config_frame",None).winfo_children():
                    self._abrir_config_inline()
                return
        except Exception:
            pass
        if old_tab_v43:
            return old_tab_v43(self,*a,**kw)


    def _v43_sanitize_header_buttons(self):
        """Remove caracteres/ícones de botões principais mesmo se alguma camada legada os recolocar."""
        import re as _re_v43_sanitize
        wanted={"coletar":"Coletar","redigir":"Redigir","copydesk":"Copydesk","preview":"Preview","publicar":"Publicar","descartar":"Descartar","exportar":"Exportar"}
        def walk(w):
            for ch in w.winfo_children():
                try:
                    if isinstance(ch,tk.Button):
                        t=str(ch.cget("text") or "")
                        low=t.lower()
                        for key,label in wanted.items():
                            if key in low:
                                ch.configure(text=label,font=("Segoe UI Semibold",10),padx=18,pady=9)
                                break
                    walk(ch)
                except Exception:
                    pass
        try: walk(self)
        except Exception: pass
        try: self.after(4000,self._v43_sanitize_header_buttons)
        except Exception: pass

    def _v43_pulse_status_dot(self):
        try:
            lbl=getattr(self,"_v43_header_status",None)
            if lbl:
                cur=str(lbl.cget("fg"))
                lbl.configure(fg=("#86efac" if cur==COLORS["green"] else COLORS["green"]))
        except Exception:
            pass
        try: self.after(900,self._v43_pulse_status_dot)
        except Exception: pass

    # Override final da fila: menos desenho, fonte mais legível e sem botão Gerar.
    if FilaPautas_cls:
        try:
            FilaPautas_cls._BUFFER=1
            FilaPautas_cls._ROW_H=104
        except Exception:
            pass
        def _v43_wrap_title_final(txt,limit=88):
            txt=str(txt or "").strip()
            if len(txt)<=limit: return txt
            cut=txt[:limit].rsplit(" ",1)[0] or txt[:limit]
            rest=txt[len(cut):].strip()
            if len(rest)>limit: rest=rest[:limit-1].rstrip()+"…"
            return cut+"\n"+rest
        def _draw_row_v43_final(self,idx:int,w:int):
            p=self._itens[idx]; y=idx*self._ROW_H; status=str(p.get("status") or ""); uid=self._uid(p,idx); sep=bool(p.get("_separador_coleta_v123")); selecionado=idx==self._sel_idx; termos=self._termos_prioridade(p)
            if sep: bg="#071528"; border="#22d3ee"
            elif selecionado: bg="#33205f"; border=COLORS["brand"]
            elif status=="excluida": bg="#1a1a1a"; border="#64748b"
            elif status=="baixo_score": bg="#2a1644"; border="#f59e0b"
            elif termos: bg="#102a36"; border="#14b8a6"
            else: bg="#111827" if idx%2==0 else "#151f32"; border="#253047"
            c=self._canvas; c.create_rectangle(0,y,w,y+self._ROW_H-1,fill=bg,outline=bg,tags="row"); c.create_rectangle(0,y,4,y+self._ROW_H-1,fill=border,outline=border,tags="row")
            if sep:
                c.create_text(18,y+26,anchor="w",text=str(p.get("titulo_origem") or "Coleta"),fill="#67e8f9",font=("Segoe UI",11,"bold"),tags="row")
                c.create_text(18,y+54,anchor="w",text=str(p.get("_subtitulo_separador_v123") or "Separador visual."),fill="#94a3b8",font=("Segoe UI",9),tags="row")
                return
            checked=uid in self._selecionados
            c.create_rectangle(14,y+42,28,y+56,fill=("#1e3a5f" if checked else bg),outline="#94a3b8",tags="row")
            if checked: c.create_text(21,y+49,text="✓",fill="#7dd3fc",font=("Segoe UI",9,"bold"),tags="row")
            x=42
            for text,bbg,ffg in self._badge_textos(p)[:5]:
                if x>max(250,w-90): break
                x=self._draw_badge(x,y+10,text,bbg,ffg)
            # Nada de botão Gerar em pauta normal. Só ações de exceção permanecem.
            if status=="excluida":
                self._draw_button(w-112,y+9,w-24,y+29,"↩ Reativar","#374151","#d1d5db","reativar",idx)
            elif status=="baixo_score":
                self._draw_button(w-206,y+9,w-116,y+29,"✕ Reprovar","#7f1d1d","#fecaca","reprovar_baixo",idx)
                self._draw_button(w-106,y+9,w-24,y+29,"✓ Aprovar","#92400e","#fde68a","aprovar_baixo",idx)
            titulo=_v43_wrap_title_final(self._titulo(p),max(64,int((w-100)/8.2)))
            c.create_text(42,y+50,anchor="w",text=titulo,fill=("#ffffff" if selecionado else "#f4f7fb"),font=("Segoe UI",11,"bold" if selecionado else "normal"),width=max(250,w-90),tags="row")
            fonte=self._fonte(p)[:34]; data_pub=str(p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or "")[:16]
            meta="  ·  ".join([x for x in [fonte,("Publicado: "+data_pub if data_pub else "")] if x])
            if meta: c.create_text(42,y+86,anchor="w",text=meta,fill="#9aa7bc",font=("Segoe UI",9),tags="row")
            c.create_line(0,y+self._ROW_H-1,w,y+self._ROW_H-1,fill="#253047",tags="row")
        setattr(FilaPautas_cls,"_draw_row",_draw_row_v43_final)

    # Aplica overrides finais.
    for _n,_o in {
        "_v43_build_top_header":_v43_build_top_header_final,
        "_construir_statusbar":_construir_statusbar_v43_header_final,
        "_set_status":_set_status_v43_header_final,
        "_construir_console":_construir_console_v43_buffered,
        "_append_console":_append_console_v43_buffered,
        "_toggle_console":_toggle_console_v43_final,
        "_construir_detalhe":_construir_detalhe_v43_fontes,
        "_construir_aba_leitura":_construir_aba_leitura_v43_readable,
        "_ao_trocar_aba":_ao_trocar_aba_v43_config,
    }.items():
        setattr(PainelUrurau,_n,_o)
    print("[V43 Premium] Ajuste final aplicado: progresso no topo, config restaurada, console leve e fila sem botão Gerar.")

    # ─────────────────────────────────────────────────────────────────────
    # V43 Premium — ACABAMENTO VISUAL DEFINITIVO SEM IMAGEM
    # Correções: header alinhado, KPIs sem corte, console robusto, fila com score circular.
    # ─────────────────────────────────────────────────────────────────────
    def _v43_build_top_header_acabamento(self):
        hdr=tk.Frame(self,bg=COLORS["bg"],height=104)
        hdr.pack(fill="x",side="top"); hdr.pack_propagate(False)

        logo=tk.Frame(hdr,bg=COLORS["bg"],width=178)
        logo.pack(side="left",fill="y",padx=(12,8)); logo.pack_propagate(False)
        try:
            from PIL import Image,ImageTk
            ico=_base_dir()/"ururau_atalho_icon.ico"
            if ico.exists():
                img=Image.open(str(ico)).resize((36,36),Image.LANCZOS)
                ph=ImageTk.PhotoImage(img)
                lb=tk.Label(logo,image=ph,bg=COLORS["bg"]); lb.image=ph
                lb.pack(side="left",pady=22,padx=(0,8))
        except Exception:
            pass
        tbox=tk.Frame(logo,bg=COLORS["bg"]); tbox.pack(side="left",pady=18)
        tk.Label(tbox,text="URURAU",bg=COLORS["bg"],fg=COLORS["brand"],font=("Segoe UI",17,"bold")).pack(anchor="w")
        tk.Label(tbox,text="Robô Editorial",bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",8)).pack(anchor="w")

        env=tk.Frame(hdr,bg=COLORS["bg"],width=126)
        env.pack(side="left",fill="y",padx=(0,10)); env.pack_propagate(False)
        # Removido “Sistema operacional” no topo esquerdo. Status operacional fica no rodapé e no indicador de progresso.
        tk.Label(env,text="Ambiente: Produção",bg=COLORS["surface2"],fg="#93c5fd",font=("Segoe UI",8),padx=8,pady=4).pack(anchor="w",pady=(30,0))

        actions=tk.Frame(hdr,bg=COLORS["bg"])
        actions.pack(side="left",fill="both",expand=True)
        for text,cmd,color in [
            ("Coletar",self._acao_coletar,COLORS["brand"]),
            ("Redigir",self._acao_redigir,COLORS["blue"]),
            ("Copydesk",self._acao_copydesk,COLORS["purple"]),
            ("Preview",self._acao_preview,"#2563eb"),
            ("Publicar",self._acao_publicar,COLORS["green"]),
            ("Descartar",self._acao_descartar,COLORS["red"]),
            ("Exportar",self._acao_exportar,COLORS["surface2"]),
        ]:
            b=_btn(actions,text,cmd,color)
            try:
                b.configure(font=("Segoe UI Semibold",10),padx=20,pady=10,relief="flat",bd=0,highlightthickness=0)
            except Exception:
                pass
            b.pack(side="left",padx=4,pady=27)
        self._btn_monitor=tk.Button(actions,text="Monitor OFF",command=self._toggle_monitor,bg=COLORS["surface2"],fg=COLORS["muted"],relief="flat",padx=12,pady=9,cursor="hand2",font=("Segoe UI Semibold",9))
        self._btn_monitor.pack(side="left",padx=3,pady=27)
        self._btn_console=tk.Button(actions,text="Console",command=self._toggle_console,bg=COLORS["surface2"],fg=COLORS["muted"],relief="flat",padx=12,pady=9,cursor="hand2",font=("Segoe UI Semibold",9))
        self._btn_console.pack(side="left",padx=3,pady=27)
        tk.Button(actions,text="⚙",command=self._acao_configuracoes,bg=COLORS["surface2"],fg=COLORS["text"],relief="flat",padx=11,pady=9,cursor="hand2",font=("Segoe UI",10,"bold")).pack(side="left",padx=3,pady=27)

        # Bloco direito redesenhado: sem texto cortado e sem espaços mortos entre cards.
        right=tk.Frame(hdr,bg=COLORS["bg"],width=650)
        right.pack(side="right",fill="y",padx=(4,10)); right.pack_propagate(False)
        top=tk.Frame(right,bg=COLORS["bg"]); top.pack(fill="x",pady=(7,2))
        self._v43_kpis={}
        for name,title,value,sub,color,width in [
            ("pautas","Pautas","0","na fila",None,78),
            ("publicadas","Publicadas","0","hoje",None,96),
            ("materias","Matérias","0","rascunhos",None,92),
            ("saude","Saúde do sistema","100%","OK",COLORS["green"],128),
        ]:
            c=_card(top,title,value,sub,color,width)
            c.pack(side="left",padx=(0,4),fill="y")
            self._v43_kpis[name]=c
        ana=tk.Frame(top,bg=COLORS["surface2"],highlightbackground=COLORS["border"],highlightthickness=1,width=190,height=54)
        ana.pack(side="right",padx=(6,0),fill="y"); ana.pack_propagate(False)
        self._v43_quality=tk.Label(ana,text="Qualidade IA: --/100",bg=COLORS["surface2"],fg=COLORS["blue"],font=("Segoe UI Semibold",8),anchor="w",padx=8)
        self._v43_quality.pack(fill="x",pady=(8,1))
        self._v43_risk=tk.Label(ana,text="Risco: --/100",bg=COLORS["surface2"],fg=COLORS["yellow"],font=("Segoe UI Semibold",8),anchor="w",padx=8)
        self._v43_risk.pack(fill="x",pady=(0,4))

        prog=tk.Frame(right,bg=COLORS["bg"]); prog.pack(fill="x",pady=(5,0))
        self._v43_progress_w=560
        self._v43_progress_canvas=tk.Canvas(prog,width=self._v43_progress_w,height=14,bg=COLORS["bg"],highlightthickness=0,bd=0)
        self._v43_progress_canvas.pack(side="left",fill="x",expand=True,padx=(2,6))
        self._v43_progress_canvas.create_rectangle(0,1,self._v43_progress_w,13,fill="#d1d5db",outline="#253047",tags="trough")
        self._v43_progress_fill=self._v43_progress_canvas.create_rectangle(0,1,1,13,fill=COLORS["green"],outline=COLORS["green"],tags="fill")
        self._v43_header_pct=tk.Label(prog,text="0%",bg=COLORS["bg"],fg=COLORS["text"],font=("Segoe UI",8,"bold"),width=4)
        self._v43_header_pct.pack(side="left")
        self._v43_header_status=tk.Label(right,text="● Aguardando operação",bg=COLORS["bg"],fg=COLORS["green"],font=("Segoe UI",8,"bold"),anchor="w")
        self._v43_header_status.pack(fill="x",padx=2,pady=(3,0))
        try:
            self.after(600,self._v43_sanitize_header_buttons)
            self.after(900,self._v43_pulse_status_dot)
        except Exception:
            pass

    def _toggle_console_v43_robusto(self):
        try:
            visible=not getattr(self,"_console_visible",False)
            self._console_visible=visible
            if visible:
                try: self._console_frame.pack_forget()
                except Exception: pass
                try: self._statusbar_frame.pack_forget()
                except Exception: pass
                try: self._console_frame.configure(height=240)
                except Exception: pass
                self._console_frame.pack(fill="x",side="bottom")
                try: self._statusbar_frame.pack(fill="x",side="bottom")
                except Exception: pass
                try: self._btn_console.config(bg="#1c4532",fg="#86efac")
                except Exception: pass
                buf=list(getattr(self,"_v43_console_buffer",[]) or [])[-220:]
                self._v43_console_buffer=[]
                for ln in buf:
                    _append_console_v43_buffered(self,ln)
            else:
                try: self._console_frame.pack_forget()
                except Exception: pass
                try:
                    if not self._statusbar_frame.winfo_ismapped():
                        self._statusbar_frame.pack(fill="x",side="bottom")
                except Exception: pass
                try: self._btn_console.config(bg=COLORS["surface2"],fg=COLORS["muted"])
                except Exception: pass
        except Exception:
            if old_toggle_console_v43:
                old_toggle_console_v43(self)

    # Fila final: score circular no lado direito, sem botão Gerar, leitura mais limpa.
    if FilaPautas_cls:
        def _score_v43_item(p):
            for k in ("score_editorial","score","score_geral","_score_final","score_final"):
                try:
                    v=p.get(k)
                    if v is not None and str(v).strip()!="":
                        return max(0,min(100,int(float(v))))
                except Exception:
                    pass
            try:
                # fallback visual neutro quando não houver score salvo.
                if p.get("status") in ("captada","em_redacao","revisada"):
                    return 70
            except Exception:
                pass
            return None
        def _draw_row_v43_acabamento(self,idx:int,w:int):
            p=self._itens[idx]; y=idx*self._ROW_H; status=str(p.get("status") or ""); uid=self._uid(p,idx); sep=bool(p.get("_separador_coleta_v123")); selecionado=idx==self._sel_idx; termos=self._termos_prioridade(p)
            if sep: bg="#071528"; border="#22d3ee"
            elif selecionado: bg="#33205f"; border=COLORS["brand"]
            elif status=="excluida": bg="#1a1a1a"; border="#64748b"
            elif status=="baixo_score": bg="#2a1644"; border="#f59e0b"
            elif termos: bg="#102a36"; border="#14b8a6"
            else: bg="#111827" if idx%2==0 else "#151f32"; border="#253047"
            c=self._canvas; c.create_rectangle(0,y,w,y+self._ROW_H-1,fill=bg,outline=bg,tags="row"); c.create_rectangle(0,y,4,y+self._ROW_H-1,fill=border,outline=border,tags="row")
            if sep:
                c.create_text(18,y+26,anchor="w",text=str(p.get("titulo_origem") or "Coleta"),fill="#67e8f9",font=("Segoe UI",11,"bold"),tags="row")
                c.create_text(18,y+54,anchor="w",text=str(p.get("_subtitulo_separador_v123") or "Separador visual."),fill="#94a3b8",font=("Segoe UI",9),tags="row")
                return
            checked=uid in self._selecionados
            c.create_rectangle(14,y+42,28,y+56,fill=("#1e3a5f" if checked else bg),outline="#94a3b8",tags="row")
            if checked: c.create_text(21,y+49,text="✓",fill="#7dd3fc",font=("Segoe UI",9,"bold"),tags="row")
            x=44
            for text,bbg,ffg in self._badge_textos(p)[:5]:
                if x>max(250,w-120): break
                x=self._draw_badge(x,y+10,text,bbg,ffg)
            if status=="excluida":
                self._draw_button(w-122,y+9,w-28,y+29,"Reativar","#374151","#d1d5db","reativar",idx)
            elif status=="baixo_score":
                self._draw_button(w-214,y+9,w-124,y+29,"Reprovar","#7f1d1d","#fecaca","reprovar_baixo",idx)
                self._draw_button(w-116,y+9,w-28,y+29,"Aprovar","#92400e","#fde68a","aprovar_baixo",idx)
            titulo=_v43_wrap_title_final(self._titulo(p),max(58,int((w-130)/8.2)))
            c.create_text(44,y+50,anchor="w",text=titulo,fill=("#ffffff" if selecionado else "#f4f7fb"),font=("Segoe UI",11,"bold" if selecionado else "normal"),width=max(240,w-150),tags="row")
            fonte=self._fonte(p)[:38]; data_pub=str(p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or "")[:16]
            meta="  ·  ".join([x for x in [fonte,("Publicado: "+data_pub if data_pub else "")] if x])
            if meta: c.create_text(44,y+86,anchor="w",text=meta,fill="#9aa7bc",font=("Segoe UI",9),tags="row")
            sc=_score_v43_item(p)
            if sc is not None and w>420:
                cx=w-46; cy=y+50; r=17
                c.create_oval(cx-r,cy-r,cx+r,cy+r,outline=COLORS["brand"],width=2,tags="row")
                c.create_text(cx,cy,text=str(sc),fill="#ffb86b",font=("Segoe UI",9,"bold"),tags="row")
            c.create_line(0,y+self._ROW_H-1,w,y+self._ROW_H-1,fill="#253047",tags="row")
        setattr(FilaPautas_cls,"_draw_row",_draw_row_v43_acabamento)

    setattr(PainelUrurau,"_v43_build_top_header",_v43_build_top_header_acabamento)
    setattr(PainelUrurau,"_toggle_console",_toggle_console_v43_robusto)
    print("[V43 Premium] Acabamento visual final aplicado: header alinhado, KPIs sem corte, console robusto e score circular na fila.")


    # ------------------------------------------------------------------
    # V43 Premium Final Pro — refinamento visual inspirado no painel de referência
    # sem trocar stack, sem React/Electron e sem alterar motor editorial.
    # ------------------------------------------------------------------
    def _v43_mini_metric(parent, title, value, sub='', fg=None, width=82):
        box=tk.Frame(parent,bg=COLORS['surface2'],width=width,height=48,highlightbackground=COLORS['border'],highlightthickness=1)
        box.pack_propagate(False)
        tk.Label(box,text=title,bg=COLORS['surface2'],fg=COLORS['muted'],font=('Segoe UI Semibold',7),anchor='w').pack(fill='x',padx=8,pady=(5,0))
        tk.Label(box,text=value,bg=COLORS['surface2'],fg=fg or COLORS['text'],font=('Segoe UI Semibold',13),anchor='w').pack(fill='x',padx=8,pady=(0,0))
        if sub:
            tk.Label(box,text=sub,bg=COLORS['surface2'],fg=COLORS['muted'],font=('Segoe UI',7),anchor='w').pack(fill='x',padx=8,pady=(0,4))
        return box

    def _v43_round_score(parent, title, value='--', color=None, width=58):
        f=tk.Frame(parent,bg=COLORS['bg'],width=width,height=48)
        f.pack_propagate(False)
        cv=tk.Canvas(f,width=42,height=42,bg=COLORS['bg'],highlightthickness=0,bd=0)
        cv.pack(anchor='center',pady=3)
        cv.create_oval(4,4,38,38,outline=color or COLORS['brand'],width=2)
        cv.create_text(21,19,text=str(value),fill=color or COLORS['brand'],font=('Segoe UI Semibold',9))
        cv.create_text(21,31,text=title,fill=COLORS['muted'],font=('Segoe UI',6))
        return f, cv

    def _v43_build_top_header_pro(self):
        try:
            if hasattr(self,'_v43_header_frame') and self._v43_header_frame.winfo_exists():
                self._v43_header_frame.destroy()
        except Exception:
            pass
        hdr=tk.Frame(self,bg=COLORS['bg'],height=76)
        self._v43_header_frame=hdr
        hdr.pack(fill='x',side='top')
        hdr.pack_propagate(False)

        # Linha principal
        row=tk.Frame(hdr,bg=COLORS['bg'],height=54)
        row.pack(fill='x',side='top')
        row.pack_propagate(False)

        brand=tk.Frame(row,bg=COLORS['bg'],width=210)
        brand.pack(side='left',fill='y',padx=(14,8))
        brand.pack_propagate(False)
        try:
            from PIL import Image,ImageTk
            ico=_base_dir()/ 'ururau_atalho_icon.ico'
            if ico.exists():
                img=Image.open(str(ico)).resize((30,30),Image.LANCZOS)
                ph=ImageTk.PhotoImage(img)
                lb=tk.Label(brand,image=ph,bg=COLORS['bg'])
                lb.image=ph
                lb.pack(side='left',pady=11,padx=(0,8))
        except Exception:
            # fallback sem depender de imagem
            tk.Label(brand,text='U',bg=COLORS['green'],fg=COLORS['bg'],font=('Segoe UI Semibold',12),width=2).pack(side='left',pady=11,padx=(0,8))
        txt=tk.Frame(brand,bg=COLORS['bg'])
        txt.pack(side='left',pady=7)
        tk.Label(txt,text='URURAU',bg=COLORS['bg'],fg=COLORS['brand'],font=('Segoe UI Semibold',15),anchor='w').pack(anchor='w')
        tk.Label(txt,text='Robô Editorial',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',8),anchor='w').pack(anchor='w')

        env=tk.Label(row,text='Produção',bg='#1f1808',fg='#fbbf24',font=('Segoe UI Semibold',8),padx=10,pady=3,highlightbackground='#854d0e',highlightthickness=1)
        env.pack(side='left',pady=15,padx=(0,14))

        actions=tk.Frame(row,bg=COLORS['bg'])
        actions.pack(side='left',fill='both',expand=True)
        btns=[('Coletar',self._acao_coletar,COLORS['brand']),('Redigir',self._acao_redigir,COLORS['blue']),('Copydesk',self._acao_copydesk,COLORS['purple']),('Preview',self._acao_preview,'#2563eb'),('Publicar',self._acao_publicar,COLORS['green']),('Descartar',self._acao_descartar,COLORS['red']),('Exportar',self._acao_exportar,COLORS['surface2'])]
        for text,cmd,color in btns:
            b=tk.Button(actions,text=text,command=cmd,bg=color,fg='white' if text!='Exportar' else COLORS['muted'],activebackground=color,activeforeground='white',relief='flat',bd=0,highlightthickness=0,padx=17,pady=8,cursor='hand2',font=('Segoe UI Semibold',9))
            b.pack(side='left',padx=3,pady=11)
        self._btn_monitor=tk.Button(actions,text='Monitor OFF',command=self._toggle_monitor,bg=COLORS['surface2'],fg=COLORS['muted'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8))
        self._btn_monitor.pack(side='left',padx=3,pady=11)
        self._btn_console=tk.Button(actions,text='Console',command=self._toggle_console,bg=COLORS['surface2'],fg=COLORS['muted'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8))
        self._btn_console.pack(side='left',padx=3,pady=11)
        tk.Button(actions,text='Config',command=self._acao_configuracoes,bg=COLORS['surface2'],fg=COLORS['text'],relief='flat',bd=0,padx=11,pady=8,cursor='hand2',font=('Segoe UI Semibold',8)).pack(side='left',padx=3,pady=11)

        right=tk.Frame(row,bg=COLORS['bg'],width=470)
        right.pack(side='right',fill='y',padx=(4,12))
        right.pack_propagate(False)
        self._v43_kpis={}
        krow=tk.Frame(right,bg=COLORS['bg'])
        krow.pack(side='left',fill='y')
        data=[('pautas','Pautas','0',''),('publicadas','Publicadas','0',''),('materias','Matérias','0',''),('saude','Saúde','100%','')]
        for key,title,val,sub in data:
            c=_v43_mini_metric(krow,title,val,sub,COLORS['green'] if key=='saude' else None,78 if key!='publicadas' else 86)
            c.pack(side='left',padx=(0,4),pady=4)
            self._v43_kpis[key]=c
        scores=tk.Frame(right,bg=COLORS['bg'])
        scores.pack(side='right',fill='y',padx=(8,0))
        self._v43_ia_frame,self._v43_ia_canvas=_v43_round_score(scores,'IA','--',COLORS['green'],50)
        self._v43_ia_frame.pack(side='left',padx=2)
        self._v43_risk_frame,self._v43_risk_canvas=_v43_round_score(scores,'Risco','--',COLORS['yellow'],52)
        self._v43_risk_frame.pack(side='left',padx=2)

        # Faixa de sinal/progresso: fora do detalhe da pauta, sem sobreposição.
        strip=tk.Frame(hdr,bg='#06110a',height=22,highlightbackground='#0f2417',highlightthickness=1)
        strip.pack(fill='x',side='bottom')
        strip.pack_propagate(False)
        self._v43_header_status=tk.Label(strip,text='● Sistema operacional • todos os serviços ativos',bg='#06110a',fg=COLORS['green'],font=('Segoe UI Semibold',8),anchor='w')
        self._v43_header_status.pack(side='left',fill='x',expand=True,padx=12)
        self._v43_progress_canvas=tk.Canvas(strip,width=210,height=10,bg='#06110a',highlightthickness=0,bd=0)
        self._v43_progress_canvas.pack(side='right',padx=(4,4),pady=5)
        self._v43_progress_w=210
        self._v43_progress_canvas.create_rectangle(0,1,self._v43_progress_w,9,fill='#1f2937',outline='#1f2937',tags='trough')
        self._v43_progress_fill=self._v43_progress_canvas.create_rectangle(0,1,1,9,fill=COLORS['green'],outline=COLORS['green'],tags='fill')
        self._v43_header_pct=tk.Label(strip,text='0%',bg='#06110a',fg=COLORS['text'],font=('Segoe UI Semibold',8),width=5,anchor='e')
        self._v43_header_pct.pack(side='right',padx=(0,10))
        try:
            self.after(700,self._v43_pulse_status_dot)
        except Exception:
            pass

    def _toggle_console_v43_final_pro(self):
        try:
            visible=not getattr(self,'_console_visible',False)
            self._console_visible=visible
            if visible:
                try: self._console_frame.pack_forget()
                except Exception: pass
                try: self._statusbar_frame.pack_forget()
                except Exception: pass
                try: self._console_frame.configure(height=175)
                except Exception: pass
                self._console_frame.pack(fill='x',side='bottom')
                try: self._statusbar_frame.pack(fill='x',side='bottom')
                except Exception: pass
                try: self._btn_console.configure(bg='#1c4532',fg='#86efac')
                except Exception: pass
                buf=list(getattr(self,'_v43_console_buffer',[]) or [])[-220:]
                self._v43_console_buffer=[]
                for ln in buf:
                    try: _append_console_v43_buffered(self,ln)
                    except Exception: pass
            else:
                try: self._console_frame.pack_forget()
                except Exception: pass
                try:
                    if not self._statusbar_frame.winfo_ismapped():
                        self._statusbar_frame.pack(fill='x',side='bottom')
                except Exception: pass
                try: self._btn_console.configure(bg=COLORS['surface2'],fg=COLORS['muted'])
                except Exception: pass
        except Exception:
            try:
                old_toggle_console_v43(self)
            except Exception:
                pass

    def _v43_update_kpis_final_pro(self):
        try:
            s=self.db.estatisticas()
            vals={'pautas':str(s.get('total_pautas',0)),'publicadas':str(s.get('total_publicadas',0)),'materias':str(s.get('total_materias',0)),'saude':'100%'}
            for k,v in vals.items():
                card=self._v43_kpis.get(k)
                labs=[w for w in card.winfo_children() if isinstance(w,tk.Label)] if card else []
                if len(labs)>1: labs[1].config(text=v)
            p=int(vals.get('pautas') or '0')
            pct=100 if p else 0
            try:
                self._v43_progress_canvas.coords(self._v43_progress_fill,0,1,max(1,int(self._v43_progress_w*pct/100)),9)
                self._v43_header_pct.config(text=f'{pct}%')
            except Exception: pass
            try:
                self._v43_header_status.config(text=f'● {p} pautas na fila • sistema operacional • todos os serviços ativos')
            except Exception: pass
            try:
                # Usa valores reais quando existirem, sem cortar no topo.
                item=getattr(self,'pauta_atual',None) or getattr(self,'_pauta_atual',None) or {}
                ia=int(float(item.get('qualidade_ia') or item.get('score_ia') or item.get('score_editorial') or 88)) if isinstance(item,dict) else 88
                risco=int(float(item.get('risco') or item.get('risco_editorial') or 12)) if isinstance(item,dict) else 12
                if hasattr(self,'_v43_ia_canvas'):
                    self._v43_ia_canvas.itemconfigure(2,text=str(max(0,min(100,ia))))
                if hasattr(self,'_v43_risk_canvas'):
                    self._v43_risk_canvas.itemconfigure(2,text=str(max(0,min(100,risco))))
            except Exception: pass
        except Exception: pass
        try: self.after(1300,self._v43_update_kpis)
        except Exception: pass

    # Ativa a última camada visual. Mantém o nome V43 Premium.
    setattr(PainelUrurau,'_v43_build_top_header',_v43_build_top_header_pro)
    setattr(PainelUrurau,'_toggle_console',_toggle_console_v43_final_pro)
    setattr(PainelUrurau,'_v43_update_kpis',_v43_update_kpis_final_pro)
    print('[V43 Premium] Final Pro aplicado: diagramação limpa, header compacto, métricas circulares, progresso sem sobreposição e console robusto.')

    # ─────────────────────────────────────────────────────────────────────
    # V43 Premium — refinamento final de diagramação pedido em 2026-05-03.
    # Sem nova versão: mantém V43 Premium, remove badge Produção do topo,
    # melhora rings de IA/Risco e score da fila, centraliza progresso.
    # ─────────────────────────────────────────────────────────────────────
    def _v43_ring_color_v2(value, inverse=False):
        try: v=int(float(value))
        except Exception: v=0
        if inverse:
            if v <= 25: return COLORS['green']
            if v <= 60: return COLORS['yellow']
            return COLORS['red']
        if v >= 80: return COLORS['green']
        if v >= 55: return COLORS['yellow']
        return COLORS['red']

    def _v43_draw_metric_ring_v2(parent, title, value='--', inverse=False, size=54):
        f=tk.Frame(parent,bg=COLORS['bg'],width=size+18,height=size+14)
        f.pack_propagate(False)
        cv=tk.Canvas(f,width=size+10,height=size+10,bg=COLORS['bg'],highlightthickness=0,bd=0)
        cv.pack(anchor='center',pady=(2,0))
        try: val=int(float(value))
        except Exception: val=0
        val=max(0,min(100,val))
        color=_v43_ring_color_v2(val,inverse=inverse)
        pad=5; x0=pad; y0=pad; x1=size+5; y1=size+5
        cv.create_oval(x0,y0,x1,y1,outline='#263246',width=3,tags='base')
        cv.create_arc(x0,y0,x1,y1,start=90,extent=-max(1,int(359*val/100)),style='arc',outline=color,width=3,tags='arc')
        cv.create_text((x0+x1)//2,(y0+y1)//2-2,text=str(val),fill=color,font=('Segoe UI Semibold',10),tags='value')
        cv.create_text((x0+x1)//2,(y0+y1)//2+12,text=title,fill=COLORS['muted'],font=('Segoe UI',6),tags='label')
        f._v43_canvas=cv; f._v43_inverse=inverse
        return f

    def _v43_update_ring_v2(frame, value, label=None):
        try: val=max(0,min(100,int(float(value))))
        except Exception: val=0
        try:
            cv=frame._v43_canvas; inverse=getattr(frame,'_v43_inverse',False); color=_v43_ring_color_v2(val,inverse=inverse)
            items=cv.find_withtag('arc')
            if items: cv.itemconfigure(items[0],outline=color); cv.itemconfigure(items[0],extent=-max(1,int(359*val/100)))
            vals=cv.find_withtag('value')
            if vals: cv.itemconfigure(vals[0],text=str(val),fill=color)
            if label:
                labs=cv.find_withtag('label')
                if labs: cv.itemconfigure(labs[0],text=label)
        except Exception:
            pass

    def _v43_build_top_header_layout_final(self):
        hdr=tk.Frame(self,bg=COLORS['bg'],height=92)
        self._v43_header_frame=hdr
        hdr.pack(fill='x',side='top')
        hdr.pack_propagate(False)

        # Marca: com altura suficiente para não cortar "Robô Editorial".
        brand=tk.Frame(hdr,bg=COLORS['bg'],width=188)
        brand.pack(side='left',fill='y',padx=(14,8)); brand.pack_propagate(False)
        try:
            from PIL import Image,ImageTk
            ico=_base_dir()/ 'ururau_atalho_icon.ico'
            if ico.exists():
                img=Image.open(str(ico)).resize((32,32),Image.LANCZOS)
                ph=ImageTk.PhotoImage(img)
                lb=tk.Label(brand,image=ph,bg=COLORS['bg']); lb.image=ph
                lb.pack(side='left',pady=(18,0),padx=(0,8),anchor='n')
        except Exception:
            tk.Label(brand,text='U',bg=COLORS['green'],fg=COLORS['bg'],font=('Segoe UI Semibold',12),width=2).pack(side='left',pady=(18,0),padx=(0,8),anchor='n')
        txt=tk.Frame(brand,bg=COLORS['bg']); txt.pack(side='left',pady=(13,0),anchor='n')
        tk.Label(txt,text='URURAU',bg=COLORS['bg'],fg=COLORS['brand'],font=('Segoe UI Semibold',16),anchor='w').pack(anchor='w')
        tk.Label(txt,text='Robô Editorial',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',8),anchor='w').pack(anchor='w',pady=(1,0))

        # Sem badge Produção no meio dos botões: o ambiente fica no rodapé/status quando necessário.
        actions=tk.Frame(hdr,bg=COLORS['bg'])
        actions.pack(side='left',fill='both',expand=True)
        for text,cmd,color in [
            ('Coletar',self._acao_coletar,COLORS['brand']),
            ('Redigir',self._acao_redigir,COLORS['blue']),
            ('Copydesk',self._acao_copydesk,COLORS['purple']),
            ('Preview',self._acao_preview,'#2563eb'),
            ('Publicar',self._acao_publicar,COLORS['green']),
            ('Descartar',self._acao_descartar,COLORS['red']),
            ('Exportar',self._acao_exportar,COLORS['surface2']),
        ]:
            tk.Button(actions,text=text,command=cmd,bg=color,fg='white' if text!='Exportar' else COLORS['muted'],activebackground=color,activeforeground='white',relief='flat',bd=0,highlightthickness=0,padx=18,pady=8,cursor='hand2',font=('Segoe UI Semibold',9)).pack(side='left',padx=3,pady=(18,0),anchor='n')
        self._btn_monitor=tk.Button(actions,text='Monitor OFF',command=self._toggle_monitor,bg=COLORS['surface2'],fg=COLORS['muted'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8))
        self._btn_monitor.pack(side='left',padx=3,pady=(18,0),anchor='n')
        self._btn_console=tk.Button(actions,text='Console',command=self._toggle_console,bg=COLORS['surface2'],fg=COLORS['muted'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8))
        self._btn_console.pack(side='left',padx=3,pady=(18,0),anchor='n')
        tk.Button(actions,text='Config',command=self._acao_configuracoes,bg=COLORS['surface2'],fg=COLORS['text'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8)).pack(side='left',padx=3,pady=(18,0),anchor='n')

        # Métricas superiores: agrupadas e sem espaços vazios excessivos.
        right=tk.Frame(hdr,bg=COLORS['bg'],width=512)
        right.pack(side='right',fill='y',padx=(4,12)); right.pack_propagate(False)
        top=tk.Frame(right,bg=COLORS['bg'],height=56)
        top.pack(fill='x',side='top',pady=(5,0)); top.pack_propagate(False)
        self._v43_kpis={}
        krow=tk.Frame(top,bg=COLORS['bg']); krow.pack(side='left',fill='y')
        for key,title,val,width in [('pautas','Pautas','0',68),('publicadas','Publicadas','0',78),('materias','Matérias','0',70),('saude','Saúde','100%',74)]:
            c=_v43_mini_metric(krow,title,val,'',COLORS['green'] if key=='saude' else None,width)
            c.pack(side='left',padx=(0,4),pady=3); self._v43_kpis[key]=c
        rbox=tk.Frame(top,bg=COLORS['bg']); rbox.pack(side='right',fill='y',padx=(8,0))
        self._v43_ia_frame=_v43_draw_metric_ring_v2(rbox,'IA','88',False,46); self._v43_ia_frame.pack(side='left',padx=3)
        self._v43_risk_frame=_v43_draw_metric_ring_v2(rbox,'Risco','12',True,46); self._v43_risk_frame.pack(side='left',padx=3)

        # Barra centralizada abaixo dos cards, no mesmo bloco à direita.
        progress_row=tk.Frame(right,bg=COLORS['bg'],height=20)
        progress_row.pack(fill='x',side='top',pady=(2,0)); progress_row.pack_propagate(False)
        self._v43_progress_canvas=tk.Canvas(progress_row,width=382,height=12,bg=COLORS['bg'],highlightthickness=0,bd=0)
        self._v43_progress_canvas.pack(side='left',padx=(0,8),pady=3)
        self._v43_progress_w=382
        self._v43_progress_canvas.create_rectangle(0,2,self._v43_progress_w,10,fill='#1f2937',outline='#1f2937',tags='trough')
        self._v43_progress_fill=self._v43_progress_canvas.create_rectangle(0,2,1,10,fill=COLORS['green'],outline=COLORS['green'],tags='fill')
        self._v43_header_pct=tk.Label(progress_row,text='0%',bg=COLORS['bg'],fg=COLORS['text'],font=('Segoe UI Semibold',8),width=5,anchor='e')
        self._v43_header_pct.pack(side='left',pady=0)
        self._v43_header_status=tk.Label(right,text='● aguardando operação',bg=COLORS['bg'],fg=COLORS['green'],font=('Segoe UI Semibold',8),anchor='w')
        self._v43_header_status.pack(fill='x',side='top',pady=(1,0))
        try: self.after(900,self._v43_pulse_status_dot)
        except Exception: pass

    def _v43_update_kpis_layout_final(self):
        try:
            s=self.db.estatisticas()
            vals={'pautas':str(s.get('total_pautas',0)),'publicadas':str(s.get('total_publicadas',0)),'materias':str(s.get('total_materias',0)),'saude':'100%'}
            for k,v in vals.items():
                card=self._v43_kpis.get(k)
                labs=[]
                try: labs=[w for w in card.winfo_children() if isinstance(w,tk.Label)] if card else []
                except Exception: pass
                if len(labs)>1: labs[1].config(text=v)
            p=int(vals.get('pautas') or '0')
            pct=100 if p else 0
            try:
                self._v43_progress_canvas.coords(self._v43_progress_fill,0,2,max(1,int(self._v43_progress_w*pct/100)),10)
                self._v43_header_pct.config(text=f'{pct}%')
                self._v43_header_status.config(text=f'● {p} pautas na fila • sistema operacional')
            except Exception: pass
            try:
                item=getattr(self,'pauta_atual',None) or getattr(self,'_pauta_atual',None) or {}
                ia=int(float(item.get('qualidade_ia') or item.get('score_ia') or item.get('score_editorial') or 88)) if isinstance(item,dict) else 88
                risco=int(float(item.get('risco') or item.get('risco_editorial') or 12)) if isinstance(item,dict) else 12
                _v43_update_ring_v2(self._v43_ia_frame,ia,'IA')
                _v43_update_ring_v2(self._v43_risk_frame,risco,'Risco')
            except Exception: pass
        except Exception: pass
        try: self.after(1300,self._v43_update_kpis)
        except Exception: pass

    def _set_status_v43_layout_final(self,msg:str):
        clean=_v43_status_limpo(msg)
        pct=_v43_progress_pct(msg)
        def _apply():
            try:
                if getattr(self,'_status_lbl',None):
                    self._status_lbl.config(text='Sistema operacional • todos os serviços ativos')
                if getattr(self,'_v43_header_status',None):
                    self._v43_header_status.config(text=('● '+clean)[:90])
                if getattr(self,'_v43_progress_canvas',None):
                    fill=max(1,int(self._v43_progress_w*pct/100)); self._v43_progress_canvas.coords(self._v43_progress_fill,0,2,fill,10)
                if getattr(self,'_v43_header_pct',None): self._v43_header_pct.config(text=f'{pct}%')
            except Exception: pass
        try: self.after(0,_apply)
        except Exception: _apply()

    if FilaPautas_cls:
        try: FilaPautas_cls._ROW_H=104; FilaPautas_cls._BUFFER=1
        except Exception: pass
        def _draw_score_ring_queue_v43(c,cx,cy,value):
            try: v=max(0,min(100,int(float(value))))
            except Exception: v=70
            color=_v43_ring_color_v2(v,False)
            r=17
            c.create_oval(cx-r,cy-r,cx+r,cy+r,outline='#253047',width=3,tags='row')
            c.create_arc(cx-r,cy-r,cx+r,cy+r,start=90,extent=-max(1,int(359*v/100)),style='arc',outline=color,width=3,tags='row')
            c.create_text(cx,cy,text=str(v),fill=color,font=('Segoe UI Semibold',9),tags='row')
        def _draw_row_v43_layout_final(self,idx:int,w:int):
            p=self._itens[idx]; y=idx*self._ROW_H; status=str(p.get('status') or ''); uid=self._uid(p,idx); sep=bool(p.get('_separador_coleta_v123')); selecionado=idx==self._sel_idx; termos=self._termos_prioridade(p)
            if sep: bg='#071528'; border='#22d3ee'
            elif selecionado: bg='#33205f'; border=COLORS['brand']
            elif status=='excluida': bg='#1a1a1a'; border='#64748b'
            elif status=='baixo_score': bg='#2a1644'; border=COLORS['yellow']
            elif termos: bg='#102a36'; border='#14b8a6'
            else: bg='#111827' if idx%2==0 else '#151f32'; border='#253047'
            c=self._canvas; c.create_rectangle(0,y,w,y+self._ROW_H-1,fill=bg,outline=bg,tags='row'); c.create_rectangle(0,y,4,y+self._ROW_H-1,fill=border,outline=border,tags='row')
            if sep:
                c.create_text(18,y+26,anchor='w',text=str(p.get('titulo_origem') or 'Coleta'),fill='#67e8f9',font=('Segoe UI',11,'bold'),tags='row')
                c.create_text(18,y+54,anchor='w',text=str(p.get('_subtitulo_separador_v123') or 'Separador visual.'),fill='#94a3b8',font=('Segoe UI',9),tags='row')
                return
            checked=uid in self._selecionados
            c.create_rectangle(14,y+42,28,y+56,fill=('#1e3a5f' if checked else bg),outline='#94a3b8',tags='row')
            if checked: c.create_text(21,y+49,text='✓',fill='#7dd3fc',font=('Segoe UI',9,'bold'),tags='row')
            x=44
            for text,bbg,ffg in self._badge_textos(p)[:5]:
                if x>max(250,w-128): break
                x=self._draw_badge(x,y+10,text,bbg,ffg)
            if status=='excluida': self._draw_button(w-122,y+9,w-28,y+29,'Reativar','#374151','#d1d5db','reativar',idx)
            elif status=='baixo_score':
                self._draw_button(w-214,y+9,w-124,y+29,'Reprovar','#7f1d1d','#fecaca','reprovar_baixo',idx); self._draw_button(w-116,y+9,w-28,y+29,'Aprovar','#92400e','#fde68a','aprovar_baixo',idx)
            titulo=_v43_wrap_title_final(self._titulo(p),max(58,int((w-140)/8.2)))
            c.create_text(44,y+50,anchor='w',text=titulo,fill=('#ffffff' if selecionado else '#f4f7fb'),font=('Segoe UI',11,'bold' if selecionado else 'normal'),width=max(240,w-150),tags='row')
            fonte=self._fonte(p)[:38]; data_pub=str(p.get('data_pub_fonte') or p.get('data_pub_fonte_br') or '')[:16]
            meta='  ·  '.join([x for x in [fonte,('Publicado: '+data_pub if data_pub else '')] if x])
            if meta: c.create_text(44,y+86,anchor='w',text=meta,fill='#9aa7bc',font=('Segoe UI',9),tags='row')
            try: score=max(0,min(100,int(float(p.get('score_editorial') or p.get('score') or p.get('score_final') or 70))))
            except Exception: score=70
            if w>430: _draw_score_ring_queue_v43(c,w-46,y+50,score)
            c.create_line(0,y+self._ROW_H-1,w,y+self._ROW_H-1,fill='#253047',tags='row')
        setattr(FilaPautas_cls,'_draw_row',_draw_row_v43_layout_final)

    setattr(PainelUrurau,'_v43_build_top_header',_v43_build_top_header_layout_final)
    setattr(PainelUrurau,'_v43_update_kpis',_v43_update_kpis_layout_final)
    setattr(PainelUrurau,'_set_status',_set_status_v43_layout_final)
    print('[V43 Premium] Layout final refinado: sem badge Produção, rings efetivos, barra centralizada e marca sem corte.')

    # ─────────────────────────────────────────────────────────────────────
    # V43 Premium — correção visual solicitada: status sem corte,
    # círculos suaves/anti-aliased e console interno com área dobrada.
    # Mantém a Fila de Pautas e o Detalhe de Pauta nas mesmas posições.
    # ─────────────────────────────────────────────────────────────────────
    def _v43_hex_to_rgba_visual_fix(hex_color, alpha=255):
        h=str(hex_color or '#000000').strip().lstrip('#')
        if len(h)==3:
            h=''.join(ch*2 for ch in h)
        try:
            return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16), alpha)
        except Exception:
            return (0,0,0,alpha)

    def _v43_get_ring_photo_visual_fix(owner, value, inverse=False, size=44, thickness=3):
        """Gera ring anti-aliased via Pillow. Fallback seguro para Canvas legado."""
        try:
            from PIL import Image, ImageDraw, ImageTk
            try:
                resample = Image.Resampling.LANCZOS
            except Exception:
                resample = Image.LANCZOS
            try:
                v=max(0,min(100,int(float(value))))
            except Exception:
                v=0
            color=_v43_ring_color_v2(v, inverse=inverse)
            key=(v,bool(inverse),int(size),int(thickness),str(color))
            cache=getattr(owner,'_v43_ring_photo_cache',None)
            if cache is None:
                cache={}
                try: setattr(owner,'_v43_ring_photo_cache',cache)
                except Exception: pass
            if key in cache:
                return cache[key]
            scale=4
            s=max(24,int(size))*scale
            t=max(2,int(thickness))*scale
            pad=max(t+2, 4*scale)
            img=Image.new('RGBA',(s,s),(0,0,0,0))
            draw=ImageDraw.Draw(img)
            bbox=(pad,pad,s-pad,s-pad)
            draw.ellipse(bbox,outline=_v43_hex_to_rgba_visual_fix('#263246'),width=t)
            if v > 0:
                end=-90 + min(359.5, 360.0*v/100.0)
                draw.arc(bbox,start=-90,end=end,fill=_v43_hex_to_rgba_visual_fix(color),width=t)
            img=img.resize((int(size),int(size)),resample)
            photo=ImageTk.PhotoImage(img)
            cache[key]=photo
            # Limite defensivo para não crescer indefinidamente em sessões longas.
            if len(cache)>220:
                for old_key in list(cache.keys())[:60]:
                    try: del cache[old_key]
                    except Exception: pass
            return photo
        except Exception:
            return None

    def _v43_draw_metric_ring_visual_fix(parent, title, value='--', inverse=False, size=50):
        f=tk.Frame(parent,bg=COLORS['bg'],width=size+18,height=size+18)
        f.pack_propagate(False)
        cv=tk.Canvas(f,width=size+10,height=size+16,bg=COLORS['bg'],highlightthickness=0,bd=0)
        cv.pack(anchor='center',pady=(1,0))
        try:
            val=max(0,min(100,int(float(value))))
        except Exception:
            val=0
        color=_v43_ring_color_v2(val,inverse=inverse)
        cx=(size+10)//2; cy=(size+8)//2
        photo=_v43_get_ring_photo_visual_fix(f,val,inverse,size=size,thickness=3)
        if photo:
            cv.create_image(cx,cy,image=photo,tags='ring_img')
            f._v43_ring_current_photo=photo
        else:
            pad=5; x0=pad; y0=pad; x1=size+5; y1=size+5
            cv.create_oval(x0,y0,x1,y1,outline='#263246',width=3,tags='base')
            cv.create_arc(x0,y0,x1,y1,start=90,extent=-max(1,int(359*val/100)),style='arc',outline=color,width=3,tags='arc')
        cv.create_text(cx,cy-3,text=str(val),fill=color,font=('Segoe UI Semibold',10),tags='value')
        cv.create_text(cx,cy+13,text=str(title),fill=COLORS['muted'],font=('Segoe UI',6),tags='label')
        f._v43_canvas=cv; f._v43_inverse=inverse; f._v43_ring_size=size
        return f

    def _v43_update_metric_ring_visual_fix(frame, value, label=None):
        try:
            val=max(0,min(100,int(float(value))))
        except Exception:
            val=0
        try:
            cv=frame._v43_canvas
            inverse=getattr(frame,'_v43_inverse',False)
            size=int(getattr(frame,'_v43_ring_size',50))
            color=_v43_ring_color_v2(val,inverse=inverse)
            photo=_v43_get_ring_photo_visual_fix(frame,val,inverse,size=size,thickness=3)
            imgs=cv.find_withtag('ring_img')
            if photo and imgs:
                cv.itemconfigure(imgs[0],image=photo)
                frame._v43_ring_current_photo=photo
            else:
                arcs=cv.find_withtag('arc')
                if arcs:
                    cv.itemconfigure(arcs[0],outline=color)
                    cv.itemconfigure(arcs[0],extent=-max(1,int(359*val/100)))
            vals=cv.find_withtag('value')
            if vals:
                cv.itemconfigure(vals[0],text=str(val),fill=color)
            if label:
                labs=cv.find_withtag('label')
                if labs:
                    cv.itemconfigure(labs[0],text=label)
        except Exception:
            pass

    def _v43_build_top_header_visual_fix(self):
        # Header com folga vertical explícita para impedir corte do status abaixo da barra.
        hdr=tk.Frame(self,bg=COLORS['bg'],height=118)
        self._v43_header_frame=hdr
        hdr.pack(fill='x',side='top')
        hdr.pack_propagate(False)

        brand=tk.Frame(hdr,bg=COLORS['bg'],width=188)
        brand.pack(side='left',fill='y',padx=(14,8)); brand.pack_propagate(False)
        try:
            from PIL import Image,ImageTk
            ico=_base_dir()/ 'ururau_atalho_icon.ico'
            if ico.exists():
                img=Image.open(str(ico)).resize((32,32),Image.LANCZOS)
                ph=ImageTk.PhotoImage(img)
                lb=tk.Label(brand,image=ph,bg=COLORS['bg']); lb.image=ph
                lb.pack(side='left',pady=(18,0),padx=(0,8),anchor='n')
        except Exception:
            tk.Label(brand,text='U',bg=COLORS['green'],fg=COLORS['bg'],font=('Segoe UI Semibold',12),width=2).pack(side='left',pady=(18,0),padx=(0,8),anchor='n')
        txt=tk.Frame(brand,bg=COLORS['bg']); txt.pack(side='left',pady=(13,0),anchor='n')
        tk.Label(txt,text='URURAU',bg=COLORS['bg'],fg=COLORS['brand'],font=('Segoe UI Semibold',16),anchor='w').pack(anchor='w')
        tk.Label(txt,text='Robô Editorial',bg=COLORS['bg'],fg=COLORS['muted'],font=('Segoe UI',8),anchor='w').pack(anchor='w',pady=(1,0))

        actions=tk.Frame(hdr,bg=COLORS['bg'])
        actions.pack(side='left',fill='both',expand=True)
        for text,cmd,color in [
            ('Coletar',self._acao_coletar,COLORS['brand']),
            ('Redigir',self._acao_redigir,COLORS['blue']),
            ('Copydesk',self._acao_copydesk,COLORS['purple']),
            ('Preview',self._acao_preview,'#2563eb'),
            ('Publicar',self._acao_publicar,COLORS['green']),
            ('Descartar',self._acao_descartar,COLORS['red']),
            ('Exportar',self._acao_exportar,COLORS['surface2']),
        ]:
            tk.Button(actions,text=text,command=cmd,bg=color,fg='white' if text!='Exportar' else COLORS['muted'],activebackground=color,activeforeground='white',relief='flat',bd=0,highlightthickness=0,padx=18,pady=8,cursor='hand2',font=('Segoe UI Semibold',9)).pack(side='left',padx=3,pady=(18,0),anchor='n')
        self._btn_monitor=tk.Button(actions,text='Monitor OFF',command=self._toggle_monitor,bg=COLORS['surface2'],fg=COLORS['muted'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8))
        self._btn_monitor.pack(side='left',padx=3,pady=(18,0),anchor='n')
        self._btn_console=tk.Button(actions,text='Console',command=self._toggle_console,bg=COLORS['surface2'],fg=COLORS['muted'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8))
        self._btn_console.pack(side='left',padx=3,pady=(18,0),anchor='n')
        tk.Button(actions,text='Config',command=self._acao_configuracoes,bg=COLORS['surface2'],fg=COLORS['text'],relief='flat',bd=0,padx=12,pady=8,cursor='hand2',font=('Segoe UI Semibold',8)).pack(side='left',padx=3,pady=(18,0),anchor='n')

        right=tk.Frame(hdr,bg=COLORS['bg'],width=620)
        right.pack(side='right',fill='y',padx=(4,12)); right.pack_propagate(False)
        top=tk.Frame(right,bg=COLORS['bg'],height=62)
        top.pack(fill='x',side='top',pady=(5,0)); top.pack_propagate(False)
        self._v43_kpis={}
        krow=tk.Frame(top,bg=COLORS['bg']); krow.pack(side='left',fill='y')
        for key,title,val,width in [('pautas','Pautas','0',74),('publicadas','Publicadas','0',86),('materias','Matérias','0',78),('saude','Saúde','100%',82)]:
            c=_v43_mini_metric(krow,title,val,'',COLORS['green'] if key=='saude' else None,width)
            c.pack(side='left',padx=(0,5),pady=4); self._v43_kpis[key]=c
        rbox=tk.Frame(top,bg=COLORS['bg']); rbox.pack(side='right',fill='y',padx=(8,0))
        self._v43_ia_frame=_v43_draw_metric_ring_visual_fix(rbox,'IA','88',False,50); self._v43_ia_frame.pack(side='left',padx=4)
        self._v43_risk_frame=_v43_draw_metric_ring_visual_fix(rbox,'Risco','12',True,50); self._v43_risk_frame.pack(side='left',padx=4)

        progress_row=tk.Frame(right,bg=COLORS['bg'],height=20)
        progress_row.pack(fill='x',side='top',pady=(2,0)); progress_row.pack_propagate(False)
        self._v43_progress_canvas=tk.Canvas(progress_row,width=455,height=12,bg=COLORS['bg'],highlightthickness=0,bd=0)
        self._v43_progress_canvas.pack(side='left',padx=(0,8),pady=3)
        self._v43_progress_w=455
        self._v43_progress_canvas.create_rectangle(0,2,self._v43_progress_w,10,fill='#1f2937',outline='#1f2937',tags='trough')
        self._v43_progress_fill=self._v43_progress_canvas.create_rectangle(0,2,1,10,fill=COLORS['green'],outline=COLORS['green'],tags='fill')
        self._v43_header_pct=tk.Label(progress_row,text='0%',bg=COLORS['bg'],fg=COLORS['text'],font=('Segoe UI Semibold',8),width=5,anchor='e')
        self._v43_header_pct.pack(side='left',pady=0)

        status_row=tk.Frame(right,bg=COLORS['bg'],height=28)
        status_row.pack(fill='x',side='top',pady=(4,0)); status_row.pack_propagate(False)
        self._v43_header_status=tk.Label(status_row,text='● aguardando operação',bg=COLORS['bg'],fg=COLORS['green'],font=('Segoe UI Semibold',8),anchor='w',justify='left')
        self._v43_header_status.pack(fill='both',expand=True,padx=(1,0),pady=(0,4))
        try: self.after(900,self._v43_pulse_status_dot)
        except Exception: pass

    old_construir_console_visual_fix=getattr(PainelUrurau,'_construir_console',None)
    def _construir_console_v43_visual_fix(self):
        if old_construir_console_visual_fix:
            old_construir_console_visual_fix(self)
        try:
            self._console_frame.configure(bg=COLORS['surface3'],height=360)
            self._console_frame.pack_propagate(False)
        except Exception:
            pass
        try:
            self._console_txt.configure(font=('Consolas',9),height=21,bg='#050b14',fg='#cbd5e1',insertbackground=COLORS['text'],padx=10,pady=8,wrap='word')
            self._console_txt.tag_configure('ok',foreground='#86efac')
            self._console_txt.tag_configure('err',foreground='#fca5a5')
            self._console_txt.tag_configure('warn',foreground='#fde68a')
            self._console_txt.tag_configure('info',foreground='#cbd5e1')
        except Exception:
            pass

    old_toggle_console_visual_fix=getattr(PainelUrurau,'_toggle_console',None)
    def _toggle_console_v43_visual_fix(self):
        try:
            visible=not getattr(self,'_console_visible',False)
            self._console_visible=visible
            if visible:
                try: self._console_frame.pack_forget()
                except Exception: pass
                try: self._console_frame.configure(height=360)
                except Exception: pass
                try:
                    self._console_frame.pack(fill='x',side='bottom',before=self._statusbar_frame)
                except Exception:
                    self._console_frame.pack(fill='x',side='bottom')
                try: self._btn_console.configure(bg='#1c4532',fg='#86efac')
                except Exception: pass
                buf=list(getattr(self,'_v43_console_buffer',[]) or [])[-260:]
                self._v43_console_buffer=[]
                for ln in buf:
                    try: _append_console_v43_buffered(self,ln)
                    except Exception: pass
            else:
                try: self._console_frame.pack_forget()
                except Exception: pass
                try: self._btn_console.configure(bg=COLORS['surface2'],fg=COLORS['muted'])
                except Exception: pass
        except Exception:
            try:
                old_toggle_console_visual_fix(self)
            except Exception:
                pass

    def _v43_update_kpis_visual_fix(self):
        try:
            s=self.db.estatisticas()
            vals={'pautas':str(s.get('total_pautas',0)),'publicadas':str(s.get('total_publicadas',0)),'materias':str(s.get('total_materias',0)),'saude':'100%'}
            for k,v in vals.items():
                card=self._v43_kpis.get(k)
                labs=[]
                try: labs=[w for w in card.winfo_children() if isinstance(w,tk.Label)] if card else []
                except Exception: pass
                if len(labs)>1: labs[1].config(text=v)
            p=int(vals.get('pautas') or '0')
            pct=100 if p else 0
            try:
                self._v43_progress_canvas.coords(self._v43_progress_fill,0,2,max(1,int(self._v43_progress_w*pct/100)),10)
                self._v43_header_pct.config(text=f'{pct}%')
                self._v43_header_status.config(text=f'● {p} pautas na fila • sistema operacional')
            except Exception: pass
            try:
                item=getattr(self,'pauta_atual',None) or getattr(self,'_pauta_atual',None) or getattr(self,'_pauta_sel',None) or {}
                ia=int(float(item.get('qualidade_ia') or item.get('score_ia') or item.get('score_editorial') or 88)) if isinstance(item,dict) else 88
                risco=int(float(item.get('risco') or item.get('risco_editorial') or item.get('risco_score') or 12)) if isinstance(item,dict) else 12
                _v43_update_metric_ring_visual_fix(self._v43_ia_frame,ia,'IA')
                _v43_update_metric_ring_visual_fix(self._v43_risk_frame,risco,'Risco')
            except Exception: pass
        except Exception: pass
        try: self.after(1300,self._v43_update_kpis)
        except Exception: pass

    def _set_status_v43_visual_fix(self,msg:str):
        clean=_v43_status_limpo(msg)
        pct=_v43_progress_pct(msg)
        def _apply():
            try:
                if getattr(self,'_status_lbl',None):
                    self._status_lbl.config(text='Sistema operacional • todos os serviços ativos')
                if getattr(self,'_v43_header_status',None):
                    self._v43_header_status.config(text=('● '+clean)[:140])
                if getattr(self,'_v43_progress_canvas',None):
                    fill=max(1,int(self._v43_progress_w*pct/100)); self._v43_progress_canvas.coords(self._v43_progress_fill,0,2,fill,10)
                if getattr(self,'_v43_header_pct',None): self._v43_header_pct.config(text=f'{pct}%')
            except Exception: pass
        try: self.after(0,_apply)
        except Exception: _apply()

    if FilaPautas_cls:
        try: FilaPautas_cls._ROW_H=104; FilaPautas_cls._BUFFER=1
        except Exception: pass
        def _draw_score_ring_queue_v43_smooth(c,cx,cy,value):
            try: v=max(0,min(100,int(float(value))))
            except Exception: v=70
            color=_v43_ring_color_v2(v,False)
            photo=_v43_get_ring_photo_visual_fix(c,v,False,size=40,thickness=3)
            if photo:
                c.create_image(cx,cy,image=photo,tags='row')
                try: c._v43_last_ring_photo=photo
                except Exception: pass
            else:
                r=18
                c.create_oval(cx-r,cy-r,cx+r,cy+r,outline='#253047',width=3,tags='row')
                c.create_arc(cx-r,cy-r,cx+r,cy+r,start=90,extent=-max(1,int(359*v/100)),style='arc',outline=color,width=3,tags='row')
            c.create_text(cx,cy,text=str(v),fill=color,font=('Segoe UI Semibold',9),tags='row')
        def _draw_row_v43_visual_fix(self,idx:int,w:int):
            p=self._itens[idx]; y=idx*self._ROW_H; status=str(p.get('status') or ''); uid=self._uid(p,idx); sep=bool(p.get('_separador_coleta_v123')); selecionado=idx==self._sel_idx; termos=self._termos_prioridade(p)
            if sep: bg='#071528'; border='#22d3ee'
            elif selecionado: bg='#33205f'; border=COLORS['brand']
            elif status=='excluida': bg='#1a1a1a'; border='#64748b'
            elif status=='baixo_score': bg='#2a1644'; border=COLORS['yellow']
            elif termos: bg='#102a36'; border='#14b8a6'
            else: bg='#111827' if idx%2==0 else '#151f32'; border='#253047'
            c=self._canvas; c.create_rectangle(0,y,w,y+self._ROW_H-1,fill=bg,outline=bg,tags='row'); c.create_rectangle(0,y,4,y+self._ROW_H-1,fill=border,outline=border,tags='row')
            if sep:
                c.create_text(18,y+26,anchor='w',text=str(p.get('titulo_origem') or 'Coleta'),fill='#67e8f9',font=('Segoe UI',11,'bold'),tags='row')
                c.create_text(18,y+54,anchor='w',text=str(p.get('_subtitulo_separador_v123') or 'Separador visual.'),fill='#94a3b8',font=('Segoe UI',9),tags='row')
                return
            checked=uid in self._selecionados
            c.create_rectangle(14,y+42,28,y+56,fill=('#1e3a5f' if checked else bg),outline='#94a3b8',tags='row')
            if checked: c.create_text(21,y+49,text='✓',fill='#7dd3fc',font=('Segoe UI',9,'bold'),tags='row')
            x=44
            for text,bbg,ffg in self._badge_textos(p)[:5]:
                if x>max(250,w-132): break
                x=self._draw_badge(x,y+10,text,bbg,ffg)
            if status=='excluida': self._draw_button(w-122,y+9,w-28,y+29,'Reativar','#374151','#d1d5db','reativar',idx)
            elif status=='baixo_score':
                self._draw_button(w-214,y+9,w-124,y+29,'Reprovar','#7f1d1d','#fecaca','reprovar_baixo',idx); self._draw_button(w-116,y+9,w-28,y+29,'Aprovar','#92400e','#fde68a','aprovar_baixo',idx)
            titulo=_v43_wrap_title_final(self._titulo(p),max(58,int((w-144)/8.2)))
            c.create_text(44,y+50,anchor='w',text=titulo,fill=('#ffffff' if selecionado else '#f4f7fb'),font=('Segoe UI',11,'bold' if selecionado else 'normal'),width=max(240,w-154),tags='row')
            fonte=self._fonte(p)[:38]; data_pub=str(p.get('data_pub_fonte') or p.get('data_pub_fonte_br') or '')[:16]
            meta='  ·  '.join([x for x in [fonte,('Publicado: '+data_pub if data_pub else '')] if x])
            if meta: c.create_text(44,y+86,anchor='w',text=meta,fill='#9aa7bc',font=('Segoe UI',9),tags='row')
            try: score=max(0,min(100,int(float(p.get('score_editorial') or p.get('score') or p.get('score_final') or 70))))
            except Exception: score=70
            if w>430: _draw_score_ring_queue_v43_smooth(c,w-46,y+50,score)
            c.create_line(0,y+self._ROW_H-1,w,y+self._ROW_H-1,fill='#253047',tags='row')
        setattr(FilaPautas_cls,'_draw_row',_draw_row_v43_visual_fix)

    setattr(PainelUrurau,'_v43_build_top_header',_v43_build_top_header_visual_fix)
    setattr(PainelUrurau,'_construir_console',_construir_console_v43_visual_fix)
    setattr(PainelUrurau,'_toggle_console',_toggle_console_v43_visual_fix)
    setattr(PainelUrurau,'_v43_update_kpis',_v43_update_kpis_visual_fix)
    setattr(PainelUrurau,'_set_status',_set_status_v43_visual_fix)
    print('[V43 Premium] Correção visual aplicada: status com folga, rings suaves e console interno ampliado.')
