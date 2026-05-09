from __future__ import annotations
import json, os, threading, time

def _is_text_widget(w):
    try:
        cls=str(w.winfo_class()).lower(); return cls in {'entry','text','spinbox','combobox'} or 'entry' in cls or 'text' in cls
    except Exception: return False

def _parse_row(row):
    d=dict(row or {})
    try:
        extra=json.loads(d.get('dados_json') or '{}')
        if isinstance(extra,dict): d.update(extra)
    except Exception: pass
    if d.get('uid') and not d.get('_uid'): d['_uid']=d.get('uid')
    return d

def _texto_util(self,p):
    try:
        ok,util,_=self._v105_texto_fonte_util(p); return bool(ok),int(util),int(self._v105_min_chars_fonte())
    except Exception:
        txt=str(p.get('cleaned_source_text') or p.get('fonte_aba_texto') or p.get('texto_fonte') or p.get('dossie') or '')
        return len(txt)>=900,len(txt),900

def _materia_dict(p):
    m={}; raw=p.get('materia') or p.get('materia_json') or {}
    if isinstance(raw,dict): m.update(raw)
    elif isinstance(raw,str) and raw.strip().startswith('{'):
        try: m.update(json.loads(raw))
        except Exception: pass
    for k in ('titulo','titulo_seo','titulo_capa','subtitulo','meta_description','tags','conteudo','texto_final','corpo_materia','canal','retranca'):
        if p.get(k) not in (None,''): m[k]=p.get(k)
    return m

def aplicar_patch_v47_12(g):
    PainelUrurau=g.get('PainelUrurau'); FilaPautas=g.get('FilaPautas')
    if PainelUrurau is None: return
    old_build=getattr(PainelUrurau,'_construir_interface',None)
    def _build(self,*a,**kw):
        r=old_build(self,*a,**kw) if callable(old_build) else None
        try:
            def qkey(evt,dir):
                if _is_text_widget(self.focus_get()): return None
                fila=getattr(self,'_fila',None)
                if not fila: return None
                try:
                    fila.focar()
                    return {'up':fila._nav_cima,'down':fila._nav_baixo,'pgup':fila._nav_pgup,'pgdn':fila._nav_pgdn}.get(dir,lambda e:None)(evt)
                except Exception: return None
            self.bind_all('<Up>',lambda e:qkey(e,'up'),add='+'); self.bind_all('<Down>',lambda e:qkey(e,'down'),add='+')
            self.bind_all('<Prior>',lambda e:qkey(e,'pgup'),add='+'); self.bind_all('<Next>',lambda e:qkey(e,'pgdn'),add='+')
        except Exception: pass
        try: self.after(2500,self._v47_12_iniciar_varredura_fila)
        except Exception: pass
        return r
    PainelUrurau._construir_interface=_build
    old_select=getattr(PainelUrurau,'_ao_selecionar',None)
    def _select(self,pauta):
        p=dict(pauta or {}); uid=str(p.get('uid') or p.get('_uid') or '')
        if uid:
            try:
                fresh=self._v105_carregar_pauta_uid(uid)
                if fresh: p.update(fresh)
            except Exception: pass
        ret=old_select(self,p) if callable(old_select) else None
        try: self._pauta_sel=p; self._v47_12_update_seo_sidebar(p)
        except Exception: pass
        return ret
    PainelUrurau._ao_selecionar=_select
    def _update_seo(self,pauta=None):
        p=pauta or getattr(self,'_pauta_sel',None) or {}
        if not isinstance(p,dict): p={}
        try:
            ok,util,minc=_texto_util(self,p); mat=_materia_dict(p); seo=None
            if mat and (mat.get('conteudo') or mat.get('texto_final') or mat.get('corpo_materia')):
                try:
                    from ururau.editorial.seo_premium_v47_12 import pontuar_seo_materia
                    seo=int(pontuar_seo_materia(mat,p).score)
                except Exception: seo=None
            lbl=getattr(self,'_v46_quality_score',None)
            if lbl is not None: lbl.configure(text='--' if seo is None else str(seo), fg=('#94a3b8' if seo is None else '#22c55e' if seo>=90 else '#f59e0b' if seo>=75 else '#ef4444'))
            b=getattr(self,'_v46_bar_seo',None)
            if callable(b): b(int(seo or 0))
            bl=getattr(self,'_v46_bar_legibilidade',None)
            if callable(bl):
                corpo=str(mat.get('conteudo') or mat.get('texto_final') or mat.get('corpo_materia') or '')
                bl(92 if len(corpo)>=1800 else 80 if len(corpo)>=1100 else min(85,int((util/max(1,minc))*85)) if util else 0)
            titulo=str(p.get('titulo_origem') or p.get('titulo') or 'sem pauta selecionada')[:82]
            msg=f"Selecionado: {titulo} — texto {util}/{minc}; SEO {'--' if seo is None else str(seo)+'/100'}; F5 força varredura de extração."
            try: self._v46_update_sidebar_status(msg)
            except Exception: pass
        except Exception: pass
    PainelUrurau._v47_12_update_seo_sidebar=_update_seo
    def _varrer(self,limite=160,motivo='varredura_persistente'):
        try:
            conn=self.db._conectar()
            try:
                rows=conn.execute("SELECT uid,titulo_origem,link_origem,status,score_editorial,dados_json,fonte_nome,captada_em,atualizada_em FROM pautas WHERE status NOT IN ('publicada','excluida','rejeitada') ORDER BY atualizada_em DESC LIMIT ?",(int(limite),)).fetchall()
            finally: conn.close()
            n=0
            for row in rows:
                p=_parse_row(dict(row)); ok,util,minc=_texto_util(self,p)
                if ok:
                    try:
                        if not self._v106_imagem_ok(p): self._v106_agendar_imagem(p,motivo='v47_12_texto_ok_varredura',delay=2.0)
                    except Exception: pass
                    continue
                try: self._v105_agendar_hidratacao(p,prioridade=False,motivo=motivo); n+=1
                except Exception: pass
            return n
        except Exception as e:
            try: self._set_status(f'Varredura de extração falhou: {e}')
            except Exception: pass
            return 0
    def _loop(self):
        while not getattr(self,'_v47_12_sweep_stop',False):
            n=self._v47_12_varrer_fila(int(os.getenv('URURAU_V47_12_SWEEP_LIMITE','160') or '160'))
            if n:
                try: self.after(0,lambda n=n:self._set_status(f'Extração persistente: {n} pauta(s) enfileiradas; imagem vem depois do texto.'))
                except Exception: pass
            time.sleep(float(os.getenv('URURAU_V47_12_SWEEP_INTERVALO_SEG','25') or '25'))
    def _start(self):
        if getattr(self,'_v47_12_sweep_started',False): return
        self._v47_12_sweep_started=True; self._v47_12_sweep_stop=False
        threading.Thread(target=self._v47_12_sweep_loop,daemon=True,name='FilaSweepV47_12').start()
        try: self._set_status('Varredura persistente da fila ativada: texto completo primeiro; imagem depois.')
        except Exception: pass
    PainelUrurau._v47_12_varrer_fila=_varrer; PainelUrurau._v47_12_sweep_loop=_loop; PainelUrurau._v47_12_iniciar_varredura_fila=_start
    old_f5=getattr(PainelUrurau,'_acao_atualizar_geral_v132',None)
    def _f5(self):
        if callable(old_f5): old_f5(self)
        else:
            try: self._carregar_pautas(forcar=True)
            except Exception: pass
        try:
            n=self._v47_12_varrer_fila(220,'F5_varredura_integral'); self._set_status(f'F5 aplicado: fila recarregada e {n} pauta(s) reencaminhadas para extração persistente.')
        except Exception: pass
    PainelUrurau._acao_atualizar_geral_v132=_f5; PainelUrurau._acao_atualizar_geral_v47_12=_f5
    if FilaPautas is not None:
        old_sel=getattr(FilaPautas,'_selecionar',None)
        def _fs(self,idx,chamar_callback=True):
            try: self._canvas.focus_set()
            except Exception: pass
            r=old_sel(self,idx,chamar_callback) if callable(old_sel) else None
            try: self._scroll_para_visivel(idx)
            except Exception: pass
            return r
        FilaPautas._selecionar=_fs
