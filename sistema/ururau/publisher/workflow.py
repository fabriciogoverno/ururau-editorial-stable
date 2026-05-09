
# PATCH_V47_20_DICT_ATTR_COMPAT
from __future__ import annotations
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

import re

import asyncio
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from ururau.config.settings import (
    LIMIAR_RISCO_MAXIMO,
    LOGIN,
    SENHA,
    StatusPauta,
    CategoriaErro,
)
from ururau.core.models import Pauta, Materia, ImagemDados
from ururau.editorial.redacao import gerar_materia
from ururau.editorial.pacote import completar_pacote_editorial
from ururau.editorial.risco import analisar_risco, resumo_risco
from ururau.imaging.processamento import pipeline_imagem
from ururau.coleta.scraping import extrair_dossie


def _uid_para_pauta(link: str = "", titulo: str = "") -> str:
    """
    Gera o identificador estável de uma pauta.

    Esta função voltou a ser exportada pelo módulo porque painel.py e
    monitor.py importam `WorkflowPublicacao, _uid_para_pauta` diretamente.
    Sem ela, a ação "Redigir matéria selecionada" quebrava antes de iniciar
    o workflow. Mantém a mesma regra usada em Database._uid_para_pauta.
    """
    import hashlib
    base = f"{link or ''}{titulo or ''}"
    if not base.strip():
        base = datetime.now().isoformat()
    return hashlib.md5(base.encode("utf-8", errors="ignore")).hexdigest()[:16]

if TYPE_CHECKING:
    from openai import OpenAI
    from ururau.core.database import Database


# ── Gate de publicação — função central obrigatória ──────────────────────────

def can_publish(artigo: dict, modo: str = "panel") -> tuple[bool, str]:
    """
    Gate de publicação v69c — aceita modo='panel' ou modo='monitor'.

    PANEL:  coverage_score >= 0.85, score_qualidade >= 90
    MONITOR: coverage_score >= 0.90, score_qualidade >= 92, score_risco <= 10

    Comum: status_validacao='aprovado', auditoria_bloqueada=False, sem
    CONFIG_ERROR/EXTRACTION_ERROR/EDITORIAL_BLOCKER, sem relationship_errors,
    limites validos, corpo nao vazio.

    Aprovação manual libera mesmo com erros (mas exige corpo).
    """
    modo = (modo or "panel").lower()
    if not artigo:
        return False, "Artigo nulo ou vazio."

    # ── Caminho 0 (SEMPRE BLOQUEANTE): CONFIG_ERROR e EXTRACTION_ERROR ────────
    # Estes erros indicam que o artigo NUNCA FOI GERADO corretamente.
    # Nem aprovação manual pode autorizar a publicação de um artigo sem corpo.
    erros_val = artigo.get("erros_validacao", []) or []

    if artigo.get("_is_config_error"):
        return False, (
            "CONFIG_ERROR: O pipeline abortou por falha de configuração da API OpenAI. "
            "O artigo não foi gerado. Corrija a API key e reprocesse."
        )

    status_val_raw = artigo.get("status_validacao") or ""
    _sv_str = status_val_raw if isinstance(status_val_raw, str) else ""
    if _sv_str == "erro_configuracao":
        return False, (
            "CONFIG_ERROR: status_validacao='erro_configuracao'. "
            "O artigo não foi gerado — chave de API inválida ou ausente. "
            "Corrija a configuração e use 'Reprocessar' na aba de Revisão."
        )
    if _sv_str == "erro_extracao":
        return False, (
            "EXTRACTION_ERROR: status_validacao='erro_extracao'. "
            "A fonte estava vazia ou inválida — o artigo não foi gerado. "
            "Verifique a fonte e use 'Reprocessar' na aba de Revisão."
        )

    _config_erros = [
        e for e in erros_val
        if isinstance(e, dict) and e.get("categoria") == CategoriaErro.CONFIG_ERROR
    ]
    if _config_erros:
        primeiro = _config_erros[0]
        return False, (
            f"CONFIG_ERROR: {primeiro.get('mensagem', 'Falha de configuração da API')} "
            f"[{primeiro.get('codigo','')}]. O artigo não foi gerado."
        )

    _extr_erros = [
        e for e in erros_val
        if isinstance(e, dict) and e.get("categoria") == CategoriaErro.EXTRACTION_ERROR
    ]
    if _extr_erros:
        primeiro = _extr_erros[0]
        return False, (
            f"EXTRACTION_ERROR: {primeiro.get('mensagem', 'Fonte inválida ou vazia')} "
            f"[{primeiro.get('codigo','')}]. O artigo não foi gerado."
        )

    # Bloqueia se corpo_materia estiver vazio (artigo sem conteúdo gerado)
    corpo = (artigo.get("corpo_materia") or artigo.get("conteudo") or "").strip()
    if not corpo:
        return False, (
            "Artigo sem corpo (corpo_materia vazio). "
            "O pipeline não gerou conteúdo — verifique erros e reprocesse."
        )

    # v47.3: termos de IA são bloqueio determinístico antes de qualquer publicação direta,
    # inclusive antes de aprovação manual. Rascunho pode seguir para revisão; ao vivo não.
    try:
        from ururau.editorial.regras_editoriais import validar_termos_ia_em_artigo
        check_ia = validar_termos_ia_em_artigo(artigo, modo=modo)
        if not check_ia.get("passou", True):
            achados = check_ia.get("achados", []) or []
            resumo = "; ".join(f"{a.get('campo')}={a.get('termo')}" for a in achados[:4])
            return False, "Termo(s) de IA proibido(s) detectado(s): " + (resumo or str(check_ia.get("total", 0)))
    except Exception as e:
        if modo == "monitor":
            return False, f"Falha ao validar blocklist de IA no monitor: {e}"

    # ── Caminho 1: aprovação manual explícita ─────────────────────────────────
    approved_by     = artigo.get("approved_by", "") or ""
    approved_at     = artigo.get("approved_at", "") or ""
    approval_reason = artigo.get("manual_approval_reason", "") or ""
    if approved_by.strip() and approved_at.strip() and approval_reason.strip():
        return True, ""

    # ── Caminho 2: aprovação automática (auditoria passou) ───────────────────
    status_val = _sv_str.lower().strip() if _sv_str else (
        str(status_val_raw) if isinstance(status_val_raw, str) else ""
    )
    aud_bloqueada = artigo.get("auditoria_bloqueada", True)

    # Aceita "aprovado" ou mapa de auditoria com aprovado=True
    _aprovado_status = status_val == "aprovado"
    if not _aprovado_status:
        # Fallback: dict status_validacao do pipeline (pode ser dict ou str)
        sv = artigo.get("status_validacao")
        if isinstance(sv, dict):
            _aprovado_status = bool(sv.get("aprovado", False))

    if not _aprovado_status:
        return False, (
            f"status_validacao='{status_val}' (esperado: 'aprovado'). "
            "Corrija os erros de validação ou obtenha aprovação manual."
        )

    if aud_bloqueada:
        erros_aud = artigo.get("auditoria_erros", []) or []
        resumo = "; ".join(str(e) for e in erros_aud[:2])
        return False, (
            f"Auditoria bloqueou o artigo. "
            f"{('Erros: ' + resumo) if resumo else 'Verifique a aba Auditoria.'}"
        )

    # Verifica erros classificados como EDITORIAL_BLOCKER
    blockers = [
        e for e in erros_val
        if isinstance(e, dict) and e.get("categoria") == CategoriaErro.EDITORIAL_BLOCKER
    ]
    if blockers:
        return False, (
            f"{len(blockers)} erro(s) EDITORIAL_BLOCKER não resolvido(s). "
            f"Primeiro: {blockers[0].get('mensagem', '')[:80]}"
        )

    # ── v69c: gates por MODO (panel: 0.85/90, monitor: 0.90/92/risco<=10) ──
    cov_min = 0.90 if modo == "monitor" else 0.85
    sq_min  = 92 if modo == "monitor" else 90

    cov = artigo.get("coverage_score")
    if modo == "monitor":
        # Monitor: coverage AUSENTE/0 bloqueia
        if cov is None or cov == 0:
            return False, (
                f"coverage_score ausente/0 (modo monitor exige >= {cov_min}). "
                "Reescreva incluindo os fatos essenciais ausentes."
            )
    if cov is not None:
        try:
            cov_f = float(cov)
            if cov_f > 0 and cov_f < cov_min:
                return False, (
                    f"coverage_score={cov_f:.2f} abaixo de {cov_min} (modo={modo}). "
                    "Reescreva incluindo os fatos essenciais ausentes."
                )
        except Exception:
            return False, f"coverage_score invalido: {cov!r}"

    sq = artigo.get("score_qualidade")
    if sq is not None:
        try:
            sq_i = int(sq)
            if sq_i > 0 and sq_i < sq_min:
                return False, (
                    f"score_qualidade={sq_i} abaixo de {sq_min} (modo={modo}). "
                    "Use o Copydesk para corrigir os campos com problema."
                )
        except Exception:
            pass

    # Monitor: gate adicional de risco
    if modo == "monitor":
        risco = artigo.get("score_risco_validacao") or artigo.get("score_risco") or 0
        try:
            if int(risco) > 10:
                return False, f"score_risco={risco} > 10 (modo monitor exige <=10)."
        except Exception:
            pass

    aud81 = artigo.get("auditoria_factual_v81") or {}
    if isinstance(aud81, dict):
        if aud81.get("contradicoes"):
            return False, "Auditoria factual v81 bloqueou por contradição: " + str(aud81.get("contradicoes")[:2])
        if aud81.get("claims_sem_evidencia"):
            return False, "Auditoria factual v81 bloqueou claims sem evidência: " + str(aud81.get("claims_sem_evidencia")[:2])
        if aud81.get("status") not in (None, "", "aprovado"):
            return False, f"Auditoria factual v81 status={aud81.get('status')}."

    rel_errs = artigo.get("relationship_errors") or []
    if rel_errs:
        primeiro = rel_errs[0] if isinstance(rel_errs[0], dict) else {}
        return False, (
            f"{len(rel_errs)} erro(s) de relacao factual. "
            f"Primeiro: {primeiro.get('mensagem', str(rel_errs[0]))[:80]}"
        )

    titulo_seo = artigo.get("titulo_seo") or artigo.get("titulo") or ""
    titulo_capa = artigo.get("titulo_capa") or ""
    if titulo_seo and len(titulo_seo) > 89:
        return False, f"titulo_seo tem {len(titulo_seo)} chars (limite 89)."
    if titulo_capa and len(titulo_capa) > 60:
        return False, f"titulo_capa tem {len(titulo_capa)} chars (limite 60)."

    return True, ""


def revisao_humana_necessaria(artigo: dict) -> bool:
    """
    Retorna True se o artigo precisa de revisão humana antes de publicar.

    Critérios:
    - auditoria_bloqueada = True
    - status_validacao != "aprovado"
    - status_publicacao_sugerido in ("salvar_rascunho", "bloquear")
    - revisao_humana_necessaria = True (campo explícito)
    """
    if artigo.get("revisao_humana_necessaria"):
        return True
    if artigo.get("auditoria_bloqueada", False):
        return True
    sv = artigo.get("status_validacao", "") or ""
    if isinstance(sv, dict):
        sv = "aprovado" if sv.get("aprovado") else "reprovado"
    if sv not in ("aprovado",):
        return True
    pub = (artigo.get("status_publicacao_sugerido") or "").lower()
    if pub in ("salvar_rascunho", "bloquear"):
        return True
    return False


class WorkflowPublicacao:
    """
    Máquina de estados para o ciclo de vida completo de uma pauta.

    Estados formais (StatusPauta):
        captada → triada → aprovada → em_redacao → revisada → pronta → publicada
        Em caso de falha: → rejeitada | bloqueada
    """

    def __init__(
        self,
        db: "Database",
        client: "OpenAI",
        modelo: str,
    ):
        self.db = db
        self.client = client
        self.modelo = modelo
        # v85: último resultado detalhado do envio ao CMS para o painel não exibir erro genérico.
        self.ultimo_resultado_cms = None

    # ── Helpers de log ────────────────────────────────────────────────────────

    def _log(self, uid: str, acao: str, detalhe: str = "", sucesso: bool = True):
        """Registra evento no log de auditoria e imprime no console."""
        print(f"[WORKFLOW] [{uid[:8]}] {acao}: {detalhe}")
        try:
            self.db.log_auditoria(uid, acao, detalhe, sucesso=sucesso)
        except Exception as e:
            print(f"[WORKFLOW] Falha ao registrar auditoria: {e}")

    def _set_status(self, uid: str, pauta_dict: dict, status: str, motivo: str = ""):
        """Atualiza status da pauta no banco e no dict."""
        pauta_dict["status"] = status
        try:
            self.db.atualizar_status_pauta(uid, status)
        except Exception:
            pass
        if motivo:
            self._log(uid, f"status:{status}", motivo)
        else:
            self._log(uid, f"status:{status}")

    # ── Etapas individuais ────────────────────────────────────────────────────

    def etapa_gate_antiduplicacao(self, uid: str, pauta: dict,
                                     modo: str = "redigir") -> bool:
        """
        Gate de entrada anti-duplicação.

        modo='redigir' (padrão): bloqueia se já publicada, descartada ou título similar.
            Permite pautas em qualquer status de rascunho (pronta, revisada, etc.).

        modo='publicar': verifica APENAS se já foi publicada de fato no CMS.
            Permite publicar rascunhos em qualquer estágio.

        Verifica (em ordem, para modo='redigir'):
          1. Já publicada no Ururau  → rejeita definitivamente
          2. Descartada/bloqueada   → rejeita (não reprocessa)
          3. Título similar publicado nas últimas 72h → rejeita

        Para modo='publicar':
          1. Apenas verifica se já publicada no CMS
        """
        link   = pauta.get("link_origem", "")
        titulo = pauta.get("titulo_origem", "")

        # 1. Já publicada no CMS (bloqueia sempre, qualquer modo)
        if self.db.pauta_ja_publicada(link, uid):
            self._log(uid, "gate:duplicada", "Pauta ja publicada no Ururau", sucesso=False)
            return False

        # Para modo publicar: só verifica se já foi publicada de fato
        if modo == "publicar":
            return True

        # 2. Descartada ou bloqueada anteriormente (apenas no modo redigir)
        if self.db.pauta_foi_descartada(link, uid):
            status_anterior = self.db.classificar_pauta(link, uid)
            self._log(uid, "gate:descartada",
                      f"Status anterior: {status_anterior}", sucesso=False)
            return False

        # 3. Título similar publicado recentemente (apenas no modo redigir)
        similar = self.db.titulo_similar_ja_publicado(titulo)
        if similar:
            self._log(uid, "gate:similar",
                      f"Titulo similar: '{similar[:60]}'", sucesso=False)
            self._set_status(uid, pauta, 'rejeitada',
                             f"Similar a: {similar[:60]}")
            return False

        return True

    def etapa_triagem(self, uid: str, pauta: dict) -> bool:
        """Valida dados mínimos da pauta."""
        titulo = pauta.get("titulo_origem", "")
        link   = pauta.get("link_origem", "")

        if not titulo or not link:
            self._log(uid, "triagem", "Pauta sem título ou link", sucesso=False)
            self._set_status(uid, pauta, 'rejeitada', "Dados incompletos")
            return False

        self._set_status(uid, pauta, 'triada')
        return True

    def etapa_coleta_texto(self, uid: str, pauta: dict, modo: str = "panel") -> bool:
        """
        v68: Extrai texto completo via extrair_dossie_completo() e respeita
        extraction_status. Se 'failed', NAO continua com resumo_origem.

        modo='panel'   -> em failed, salva como rascunho (status='erro_extracao')
                          e retorna False para encerrar pipeline.
        modo='monitor' -> em failed, retorna False (publicacao direta nunca
                          parte de fonte falhada).
        """
        try:
            from ururau.coleta.scraping import extrair_dossie_completo
            res = extrair_dossie_completo(
                url=pauta.get("link_origem", ""),
                texto_existente=pauta.get("texto_fonte", ""),
            )
            dossie    = res.get("dossie", "") or ""
            status    = res.get("extraction_status", "failed")
            metodo    = res.get("extraction_method", "failed")
            score     = res.get("source_sufficiency_score", 0)
            raw_src   = res.get("raw_source_text", "")
            clean_src = res.get("cleaned_source_text", "")
            metadata  = res.get("metadata", {}) or {}
            resolved_url = str(metadata.get("resolved_url") or "").strip()
            if resolved_url and resolved_url.startswith("http") and "news.google.com" not in resolved_url.lower():
                pauta["link_origem"] = resolved_url
                pauta["link_fonte_resolvido"] = resolved_url

            # V47.7: a extração textual costuma descobrir og:image/crédito antes do pipeline de imagem.
            # Mantém essa imagem como candidata preferencial, sem dispensar as buscas posteriores.
            img_meta = str(metadata.get("imagem") or metadata.get("image") or metadata.get("og_image") or "").strip()
            cred_meta = str(metadata.get("credito_foto") or metadata.get("image_credit") or "").strip()
            if img_meta and img_meta.startswith(("http://", "https://")):
                pauta.setdefault("imagem_url_extracao", img_meta)
                if not pauta.get("imagem_url"):
                    pauta["imagem_url"] = img_meta
                pauta["imagem_origem_v47_7"] = "extracao_textual"
            if cred_meta and not pauta.get("imagem_credito"):
                pauta["imagem_credito"] = cred_meta

            pauta["dossie"]                   = dossie
            pauta["raw_source_text"]          = raw_src
            pauta["cleaned_source_text"]      = clean_src
            pauta["extraction_method"]        = metodo
            pauta["source_sufficiency_score"] = score
            pauta["extraction_status"]        = status

            # v78b: corrige canal com base no texto real extraído. Não deixa
            # canal_forcado/RSS sobrescrever editoria claramente errada.
            try:
                from ururau.editorial.fallback_local import classificar_canal_v78
                canal_corrigido = classificar_canal_v78(
                    pauta.get("titulo_origem", ""),
                    (pauta.get("resumo_origem", "") + " " + clean_src + " " + dossie),
                    pauta.get("canal_forcado", ""),
                )
                pauta["canal"] = canal_corrigido
                pauta["canal_forcado"] = canal_corrigido
            except Exception:
                pass

            # v104: se o scraper principal retornar pouco texto, usa a mesma
            # cascata definitiva da aba Fonte. Porém NÃO promove snippet curto
            # a extração ok. Isso era a causa de matérias com 1 parágrafo.
            try:
                from ururau.coleta.limpeza_texto_v81 import texto_util_chars
                fonte_atual_v96 = clean_src or dossie or pauta.get("texto_fonte", "") or ""
                min_fonte_v104 = int(__import__("os").getenv("URURAU_V104_MIN_CHARS_ARTIGO", __import__("os").getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "350")) or "350")
                if texto_util_chars(str(fonte_atual_v96)) < min_fonte_v104:
                    from ururau.coleta.leitura_fonte import ler_fonte_pauta
                    res_v96 = ler_fonte_pauta(pauta, forcar_refresh=True)
                    if getattr(res_v96, "sucesso", False):
                        txt_v96 = (getattr(res_v96, "texto_limpo", "") or "").strip()
                        util_v96 = texto_util_chars(txt_v96)
                        if util_v96 >= min_fonte_v104 and util_v96 > texto_util_chars(str(fonte_atual_v96)):
                            dossie = txt_v96[:12000]
                            raw_src = txt_v96[:12000]
                            clean_src = txt_v96[:12000]
                            status = "ok" if util_v96 >= 1200 else "short_usable"
                            metodo = "leitura_fonte_v104"
                            score = max(int(score or 0), 88 if util_v96 >= 1200 else 78)
                            pauta["_fonte_aba_texto"] = txt_v96
                            pauta["fonte_aba_texto"] = txt_v96
                            pauta["leitura_fonte_texto"] = txt_v96
                            pauta["dossie"] = dossie
                            pauta["raw_source_text"] = raw_src
                            pauta["cleaned_source_text"] = clean_src
                            pauta["extraction_method"] = metodo
                            pauta["source_sufficiency_score"] = score
                            pauta["extraction_status"] = status
                            # Atualiza o dict avaliado pelos guards v83/v84.
                            res = dict(res or {})
                            res["dossie"] = dossie
                            res["raw_source_text"] = raw_src
                            res["cleaned_source_text"] = clean_src
                            res["extraction_method"] = metodo
                            res["source_sufficiency_score"] = score
                            res["extraction_status"] = status
                            meta = dict(res.get("metadata") or {})
                            meta["scraped_chars"] = len(clean_src)
                            meta["total_chars"] = len(clean_src)
                            meta["util_chars"] = util_v96
                            res["metadata"] = meta
                            self._log(uid, "coleta_texto", f"v104 recuperou fonte completa pela aba Fonte: {util_v96} chars", sucesso=True)
                        else:
                            self._log(uid, "coleta_texto", f"v104 recusou fonte curta ({util_v96} chars); não gera matéria por snippet", sucesso=False)
            except Exception as _e_v96:
                self._log(uid, "coleta_texto", f"Aviso v104 leitura_fonte: {_e_v96}", sucesso=False)

            # Mantem texto_fonte tambem para retrocompatibilidade, mas agora
            # sobrescreve quando a fonte hidratada é maior que o resumo/RSS curto.
            if dossie and len(dossie) > len(str(pauta.get("texto_fonte") or "")):
                pauta["texto_fonte"] = dossie[:12000]

            self._log(uid, "coleta_texto",
                       f"{len(dossie)} chars | metodo={metodo} | status={status} | score={score}")

            # v83: FAIL-CLOSED real no monitor 24h.
            # Se a URL não entregar texto real da matéria, a pauta não segue para imagem,
            # redação, rascunho CMS ou publicação direta.
            if modo == "monitor":
                try:
                    from ururau.coleta.fail_closed_v83 import (
                        avaliar_extracao_para_monitor_v83,
                        aplicar_bloqueio_coleta_v83,
                    )
                    decisao_coleta = avaliar_extracao_para_monitor_v83(res, pauta)
                    pauta["decisao_coleta_v83"] = {
                        "ok": decisao_coleta.ok,
                        "motivo": decisao_coleta.motivo,
                        "codigo": decisao_coleta.codigo,
                        "util_chars": decisao_coleta.util_chars,
                        "scraped_chars": decisao_coleta.scraped_chars,
                        "metodo": decisao_coleta.metodo,
                        "status": decisao_coleta.status,
                    }
                    if not decisao_coleta.ok:
                        aplicar_bloqueio_coleta_v83(pauta, decisao_coleta)
                        self._log(uid, "coleta_texto",
                                   f"FAIL-CLOSED v83: {decisao_coleta.motivo}. "
                                   "Pauta barrada antes da redação; sem rascunho CMS.",
                                   sucesso=False)
                        self._set_status(uid, pauta, 'bloqueada',
                                          "Coleta de texto falhou: " + decisao_coleta.motivo)
                        return False
                    self._log(uid, "coleta_texto",
                              f"v83 OK: {decisao_coleta.motivo}", sucesso=True)
                except Exception as e_guard:
                    pauta["status_validacao"] = "erro_extracao"
                    pauta["status_publicacao_sugerido"] = "bloquear_total"
                    pauta["_bloqueio_coleta_v83"] = True
                    self._log(uid, "coleta_texto",
                              f"FAIL-CLOSED v83: erro no guard de extração: {e_guard}",
                              sucesso=False)
                    self._set_status(uid, pauta, 'bloqueada',
                                      f"Erro no guard de coleta: {e_guard}")
                    return False

            # v105: bloqueia também quando o método marcou algo diferente de failed,
            # mas o texto útil segue abaixo do mínimo. Isso evita matéria em 1 parágrafo.
            try:
                from ururau.coleta.limpeza_texto_v81 import texto_util_chars as _texto_util_v105
                _util_final_v105 = int(_texto_util_v105(clean_src or dossie or ""))
            except Exception:
                _util_final_v105 = len(str(clean_src or dossie or "").strip())
            _min_final_v105 = int(__import__("os").getenv("URURAU_V105_MIN_CHARS_FONTE_OK", __import__("os").getenv("URURAU_V104_MIN_CHARS_ARTIGO", "350")) or "350")
            if status == "failed" or _util_final_v105 < _min_final_v105:
                # v83/v105: NAO mascara falha com resumo_origem e NAO envia rascunho CMS.
                self._log(uid, "coleta_texto",
                           f"FAIL-CLOSED: fonte insuficiente ({_util_final_v105}/{_min_final_v105}); abortando pipeline.",
                           sucesso=False)
                pauta["status_validacao"]            = "erro_extracao"
                pauta["status_publicacao_sugerido"]  = "bloquear_total"
                pauta["revisao_humana_necessaria"]   = False
                pauta["_bloqueio_coleta_v83"]         = True
                pauta["status_fonte_v105"]            = "falhou" if _util_final_v105 == 0 else "curta"
                pauta["fonte_chars_v105"]             = _util_final_v105
                self._set_status(uid, pauta, 'bloqueada',
                                  "Fonte textual insuficiente para redação")
                return False

            return True
        except Exception as e:
            self._log(uid, "coleta_texto", f"Erro: {e}", sucesso=False)
            # v83: NUNCA continuar com resumo_origem como fonte e NUNCA enviar rascunho CMS.
            pauta["dossie"]                     = ""
            pauta["status_validacao"]           = "erro_extracao"
            pauta["status_publicacao_sugerido"] = "bloquear_total"
            pauta["revisao_humana_necessaria"]  = False
            pauta["_bloqueio_coleta_v83"]       = True
            pauta["motivo_bloqueio_coleta_v83"] = str(e)
            self._set_status(uid, pauta, 'bloqueada',
                              f"Erro de extracao: {e}")
            return False

    def etapa_imagem(self, uid: str, pauta: dict) -> Optional[ImagemDados]:
        """Executa pipeline de imagem."""
        try:
            imagem = pipeline_imagem(
                url_pagina=pauta.get("link_origem", ""),
                titulo=pauta.get("titulo_origem", ""),
                pauta_uid=uid,
                imagem_preferencial=(pauta.get("imagem_url") or pauta.get("imagem_url_extracao") or pauta.get("imagem") or ""),
                credito_preferencial=(pauta.get("imagem_credito") or pauta.get("credito_foto") or ""),
                dossie_texto=(pauta.get("texto_fonte") or pauta.get("cleaned_source_text") or pauta.get("resumo_origem") or ""),
            )
            if imagem and imagem.caminho_imagem:
                pauta["imagem_status"]   = "aprovada"
                pauta["imagem_caminho"]  = imagem.caminho_imagem
                pauta["imagem_url"]      = imagem.url_imagem
                pauta["imagem_credito"]  = imagem.credito_foto
                pauta["imagem_estrategia"] = imagem.estrategia_imagem
                self.db.salvar_imagem(uid, imagem.to_dict())
                self._log(uid, "imagem", f"Estratégia: {imagem.estrategia_imagem}")
                return imagem
            else:
                pauta["imagem_status"] = "sem_imagem"
                self._log(uid, "imagem", "Nenhuma imagem encontrada", sucesso=False)
                return None
        except Exception as e:
            pauta["imagem_status"] = "erro"
            self._log(uid, "imagem", f"Erro: {e}", sucesso=False)
            return None

    def etapa_redacao(self, uid: str, pauta: dict) -> Optional[Materia]:
        """Gera a matéria completa."""
        canal = pauta.get("canal") or pauta.get("canal_forcado") or "Brasil e Mundo"

        self._set_status(uid, pauta, getattr(StatusPauta, 'EM_REDACAO', 'em_redacao'))
        try:
            materia = gerar_materia(pauta, self.client, self.modelo, canal)
            # PATCH_V47_23_CANAL_FINAL
            try:
                from ururau.editorial.canal_final_v47_23 import corrigir_canal_materia
                canal_v4723 = corrigir_canal_materia(materia, pauta)
                self._log(uid, 'canal_final_v47_23', f'Canal final: {canal_v4723}', sucesso=True)
            except Exception as _e_canal_v4723:
                self._log(uid, 'canal_final_v47_23', f'Falha ao corrigir canal: {_e_canal_v4723}', sucesso=False)
            # v96: se a redação gerou corpo curto/um parágrafo apesar de fonte
            # longa, reescreve imediatamente com o mesmo regenerador do Copydesk.
            try:
                fonte_v96 = pauta.get("cleaned_source_text") or pauta.get("dossie") or pauta.get("texto_fonte") or ""
                corpo_v96 = getattr(materia, "conteudo", "") or ""
                paras_v96 = [p for p in re.split(r"\n\s*\n", corpo_v96.strip()) if p.strip()]
                if len(str(fonte_v96).strip()) >= 1000 and (len(paras_v96) < 3 or len(corpo_v96.strip()) < 850):
                    from ururau.editorial.copydesk_regenerador_v87 import regenerar_materia_com_fonte_v87
                    md_v96 = materia.to_dict() if hasattr(materia, "to_dict") else dict(materia)
                    md_v96["cleaned_source_text"] = fonte_v96
                    md_v96["raw_source_text"] = pauta.get("raw_source_text") or fonte_v96
                    novo_v96 = regenerar_materia_com_fonte_v87(md_v96, pauta, client=self.client, modelo=self.modelo, min_fonte_chars=300)
                    for k, v in novo_v96.items():
                        if hasattr(materia, k):
                            setattr(materia, k, v)
                    if novo_v96.get("corpo_materia") or novo_v96.get("conteudo"):
                        materia.conteudo = novo_v96.get("corpo_materia") or novo_v96.get("conteudo")
                    materia.cleaned_source_text = str(fonte_v96)
                    materia.raw_source_text = pauta.get("raw_source_text") or str(fonte_v96)
                    self._log(uid, "redacao_v96", f"corpo curto regenerado pela fonte: {len(materia.conteudo)} chars")
            except Exception as _e_v96:
                self._log(uid, "redacao_v96", f"Aviso: não regenerou corpo curto ({_e_v96})", sucesso=False)
            # v46.7: diagnóstico explícito da IA/fallback.
            # Antes o workflow só registrava “redacao OK”; agora mostra se o GPT Mini
            # respondeu de fato ou se o texto veio de fallback local/camada legada.
            try:
                gj_ia = dict(getattr(materia, "generated_article_json", {}) or {})
                modo_ia = str(getattr(materia, "modo_geracao", "") or gj_ia.get("modo_geracao") or "sem_telemetria_ia")
                status_ia = str(getattr(materia, "ia_status", "") or gj_ia.get("ia_status") or "sem_telemetria_ia")
                modelo_ia = str(getattr(materia, "ia_modelo", "") or gj_ia.get("ia_modelo") or self.modelo or "")
                motivo_ia = str(getattr(materia, "ia_fallback_motivo", "") or gj_ia.get("ia_fallback_motivo") or "")
                ok_ia = bool(getattr(materia, "ia_chamada_ok", False) or gj_ia.get("ia_chamada_ok"))
                origem_ia = str(getattr(materia, "ia_texto_final_origem", "") or gj_ia.get("ia_texto_final_origem") or ("openai" if ok_ia else "fallback_local"))
                openai_status = str(getattr(materia, "ia_openai_status", "") or gj_ia.get("ia_openai_status") or "")
                self._log(
                    uid,
                    "ia_diagnostico",
                    f"modo={modo_ia} | status={status_ia} | origem={origem_ia} | openai_status={openai_status or '-'} | modelo={modelo_ia} | motivo={motivo_ia[:180]}",
                    sucesso=ok_ia,
                )
            except Exception as _e_ia_diag:
                self._log(uid, "ia_diagnostico", f"Aviso: sem telemetria de IA ({_e_ia_diag})", sucesso=False)

            # v80: preserva a editoria definida pela triagem do monitor e corrige
            # falsos positivos como PMs/homicidio virando Política.
            try:
                from ururau.editorial.fallback_local import classificar_canal_v78
                canal_corrigido = classificar_canal_v78(
                    pauta.get("titulo_origem", "") or materia.titulo,
                    " ".join([
                        pauta.get("resumo_origem", "") or "",
                        pauta.get("cleaned_source_text", "") or "",
                        pauta.get("dossie", "") or "",
                        materia.conteudo or "",
                    ]),
                    canal,
                )
                if canal_corrigido:
                    materia.canal = canal_corrigido
            except Exception:
                materia.canal = canal
            self._log(uid, "redacao", f"Título: {materia.titulo[:60]} | Canal: {materia.canal}")
            return materia
        except Exception as e:
            self._log(uid, "redacao", f"Erro: {e}", sucesso=False)
            self._set_status(uid, pauta, 'rejeitada', f"Falha na redação: {e}")
            return None

    def etapa_pacote_editorial(self, uid: str, materia: Materia, pauta: dict | None = None) -> Materia:
        """Complementa pacote editorial e aplica auditoria factual v81."""
        try:
            materia = completar_pacote_editorial(materia, self.client, self.modelo)
            self._log(uid, "pacote_editorial", "Pacote completo")
        except Exception as e:
            self._log(uid, "pacote_editorial", f"Aviso: {e}", sucesso=False)

        try:
            from ururau.editorial.auditoria_factual_v81 import aplicar_auditoria_materia_v81
            materia = aplicar_auditoria_materia_v81(materia, pauta or {})
            aud = getattr(materia, "auditoria_factual_v81", {}) if not isinstance(materia, dict) else materia.get("auditoria_factual_v81", {})
            self._log(uid, "auditoria_factual_v81",
                      f"score={aud.get('score')} status={aud.get('status')} publicar={aud.get('pode_publicar')}",
                      sucesso=(aud.get("status") == "aprovado"))
        except Exception as e:
            self._log(uid, "auditoria_factual_v81", f"FAIL-CLOSED: {e}", sucesso=False)
            try:
                materia.status_validacao = "reprovado"
                materia.status_publicacao_sugerido = "bloquear"
                materia.auditoria_bloqueada = True
                materia.auditoria_aprovada = False
                materia.auditoria_erros = [f"auditoria_factual_v81 falhou: {e}"]
            except Exception:
                pass
        return materia

    def etapa_copydesk_automatico_v102(self, uid: str, pauta: dict, materia: Materia, modo: str = "monitor") -> Materia:
        """
        v102: envia a matéria recém-redigida ao Copydesk IA antes da publicação.

        Fluxo novo do monitor 24h:
          redação automática -> pacote editorial -> copydesk IA -> auditoria factual -> risco -> CMS.

        Se o Copydesk falhar, a matéria não segue para publicação direta: fica marcada
        para rascunho/revisão, preservando o texto já gerado como backup local.
        """
        try:
            from ururau.editorial.copydesk import pipeline_copydesk

            md = materia.to_dict() if hasattr(materia, "to_dict") else dict(materia)
            fonte = (
                pauta.get("cleaned_source_text") or pauta.get("_fonte_aba_texto") or
                pauta.get("fonte_aba_texto") or pauta.get("leitura_fonte_texto") or
                pauta.get("dossie") or pauta.get("texto_fonte") or md.get("cleaned_source_text") or ""
            )
            md["cleaned_source_text"] = str(fonte or "")
            md["raw_source_text"] = pauta.get("raw_source_text") or str(fonte or "")

            mapa = md.get("mapa_evidencias") or {}
            canal = md.get("canal") or pauta.get("canal_forcado") or pauta.get("canal") or "Brasil e Mundo"

            self._log(uid, "copydesk_v103", "Enviando matéria ao Copydesk IA com TEXTO-FONTE integral antes da publicação.", sucesso=True)

            # v103: o copydesk não pode revisar apenas o resumo curto. Se houver fonte
            # útil, primeiro reconstrói a matéria pela fonte integral; depois roda o
            # copydesk de revisão. Isso corrige textos de 1 parágrafo e resumos rasos.
            if len(str(fonte or "").strip()) >= 800:
                try:
                    from ururau.editorial.copydesk_regenerador_v87 import regenerar_materia_com_fonte_v87
                    base_reg = dict(md)
                    base_reg["cleaned_source_text"] = str(fonte or "")
                    base_reg["raw_source_text"] = pauta.get("raw_source_text") or str(fonte or "")
                    reg = regenerar_materia_com_fonte_v87(
                        base_reg, pauta, client=self.client, modelo=self.modelo, min_fonte_chars=300
                    )
                    if reg:
                        md.update(reg)
                        self._log(uid, "copydesk_v103", f"matéria reconstruída pela fonte antes da revisão ({len(str(reg.get('corpo_materia') or reg.get('conteudo') or ''))} chars).", sucesso=True)
                except Exception as e_reg_pre:
                    self._log(uid, "copydesk_v103", f"Aviso: reconstrução pré-copydesk falhou: {e_reg_pre}", sucesso=False)

            revisado, problemas = pipeline_copydesk(md, canal, mapa, self.client, self.modelo)
            try:
                self._log(
                    uid,
                    "copydesk_ia_diagnostico",
                    f"status={revisado.get('copydesk_ia_status') or revisado.get('ia_status') or 'sem_telemetria'} | modelo={revisado.get('copydesk_ia_modelo') or revisado.get('ia_modelo') or self.modelo} | chamada_ok={bool(revisado.get('copydesk_ia_chamada_ok') or revisado.get('ia_chamada_ok'))}",
                    sucesso=bool(revisado.get('copydesk_ia_chamada_ok') or revisado.get('ia_chamada_ok')),
                )
            except Exception:
                pass

            aliases = {
                "titulo_seo": "titulo",
                "subtitulo_curto": "subtitulo",
                "legenda_curta": "legenda",
                "corpo_materia": "conteudo",
            }
            for k, v in list(revisado.items()):
                destino = aliases.get(k, k)
                if hasattr(materia, destino):
                    try:
                        setattr(materia, destino, v)
                    except Exception:
                        pass

            # Garante aliases principais mesmo quando o copydesk devolve campos legados.
            if revisado.get("titulo") and hasattr(materia, "titulo"):
                materia.titulo = revisado.get("titulo")
            if revisado.get("conteudo") and hasattr(materia, "conteudo"):
                materia.conteudo = revisado.get("conteudo")
            if revisado.get("texto_final") and hasattr(materia, "conteudo"):
                materia.conteudo = revisado.get("texto_final")
            if revisado.get("subtitulo") and hasattr(materia, "subtitulo"):
                materia.subtitulo = revisado.get("subtitulo")
            if revisado.get("legenda") and hasattr(materia, "legenda"):
                materia.legenda = revisado.get("legenda")

            try:
                materia.cleaned_source_text = str(fonte or "")
                materia.raw_source_text = pauta.get("raw_source_text") or str(fonte or "")
                materia.historico_correcoes.append({
                    "etapa": "copydesk_v102",
                    "modo": modo,
                    "problemas_residuais": problemas,
                    "chars_corpo": len(getattr(materia, "conteudo", "") or ""),
                    "chars_fonte": len(str(fonte or "")),
                })
            except Exception:
                pass

            # Trava contra copydesk que devolve corpo curto demais quando há fonte longa.
            corpo = (getattr(materia, "conteudo", "") or "").strip()
            paras = [x for x in re.split(r"\n\s*\n", corpo) if x.strip()]
            if len(str(fonte or "")) >= 1200 and (len(corpo) < 900 or len(paras) < 4):
                try:
                    from ururau.editorial.copydesk_regenerador_v87 import regenerar_materia_com_fonte_v87
                    novo = regenerar_materia_com_fonte_v87(
                        revisado,
                        pauta,
                        client=self.client,
                        modelo=self.modelo,
                        min_fonte_chars=300,
                    )
                    novo_corpo = (novo.get("corpo_materia") or novo.get("conteudo") or "").strip()
                    if len(novo_corpo) > len(corpo):
                        materia.conteudo = novo_corpo
                        for campo, attr in {
                            "titulo_seo": "titulo",
                            "titulo_capa": "titulo_capa",
                            "subtitulo_curto": "subtitulo",
                            "legenda_curta": "legenda",
                            "retranca": "retranca",
                            "meta_description": "meta_description",
                            "tags": "tags",
                            "resumo_curto": "resumo_curto",
                            "chamada_social": "chamada_social",
                        }.items():
                            if novo.get(campo) and hasattr(materia, attr):
                                setattr(materia, attr, novo.get(campo))
                        self._log(uid, "copydesk_v102", "Copydesk devolveu corpo curto; matéria regenerada pela fonte antes do CMS.", sucesso=True)
                except Exception as e_reg:
                    self._log(uid, "copydesk_v102", f"Aviso: não conseguiu regenerar corpo curto: {e_reg}", sucesso=False)

            # v103: gate final determinístico de qualidade e metadados do robô.
            try:
                from ururau.editorial.quality_gate_v103 import (
                    aplicar_padrao_publicacao_robo_v103, validar_qualidade_materia,
                )
                materia = aplicar_padrao_publicacao_robo_v103(materia, pauta, None)
                ok_q, motivos_q = validar_qualidade_materia(materia, pauta)
                if not ok_q:
                    self._log(uid, "quality_gate_v103", f"REVISÃO obrigatória: {'; '.join(motivos_q[:4])}", sucesso=False)
                    pauta["_forcar_rascunho_v82"] = True
                    pauta.setdefault("_motivos_rascunho_v82", []).append("quality_gate_v103: " + "; ".join(motivos_q[:3]))
                    materia.status_publicacao_sugerido = "salvar_rascunho"
                    materia.revisao_humana_necessaria = True
                    materia.auditoria_bloqueada = True
                    materia.auditoria_erros = list(getattr(materia, "auditoria_erros", []) or []) + ["quality_gate_v103: " + "; ".join(motivos_q[:3])]
                else:
                    self._log(uid, "quality_gate_v103", "OK: corpo, parágrafos, metadados e fonte normalizados.", sucesso=True)
            except Exception as e_q:
                self._log(uid, "quality_gate_v103", f"FAIL-CLOSED: {e_q}", sucesso=False)
                pauta["_forcar_rascunho_v82"] = True

            # Reaplica auditoria factual depois do Copydesk, pois o texto mudou.
            try:
                from ururau.editorial.auditoria_factual_v81 import aplicar_auditoria_materia_v81
                materia = aplicar_auditoria_materia_v81(materia, pauta or {})
            except Exception as e_aud:
                materia.status_validacao = "reprovado"
                materia.status_publicacao_sugerido = "salvar_rascunho"
                materia.auditoria_bloqueada = True
                materia.auditoria_aprovada = False
                materia.auditoria_erros = list(getattr(materia, "auditoria_erros", []) or []) + [f"auditoria pós-copydesk v102 falhou: {e_aud}"]

            if problemas:
                self._log(uid, "copydesk_v102", f"Copydesk concluído com avisos: {'; '.join(map(str, problemas[:3]))}", sucesso=False)
                if modo == "monitor":
                    pauta["_forcar_rascunho_v82"] = True
                    pauta.setdefault("_motivos_rascunho_v82", []).append("copydesk_v102 deixou avisos residuais")
            else:
                self._log(uid, "copydesk_v102", "Copydesk IA concluído sem problemas residuais.", sucesso=True)
            return materia
        except Exception as e:
            self._log(uid, "copydesk_v102", f"Falha no Copydesk automático: {e}. Direta bloqueada; rascunho permitido.", sucesso=False)
            try:
                pauta["_forcar_rascunho_v82"] = True
                pauta.setdefault("_motivos_rascunho_v82", []).append(f"copydesk_v102 falhou: {e}")
                materia.status_publicacao_sugerido = "salvar_rascunho"
                materia.auditoria_bloqueada = True
                materia.auditoria_aprovada = False
                materia.auditoria_erros = list(getattr(materia, "auditoria_erros", []) or []) + [f"copydesk_v102 falhou: {e}"]
            except Exception:
                pass
            return materia

    def etapa_gate_qualidade_final_v103(self, uid: str, pauta: dict, materia: Materia, imagem: Optional[ImagemDados] = None) -> bool:
        """Gate final comum ao monitor 24h e ao fluxo principal do painel."""
        try:
            from ururau.editorial.quality_gate_v103 import (
                aplicar_padrao_publicacao_robo_v103, validar_qualidade_materia, detectar_duplicidade_materia,
            )
            materia = aplicar_padrao_publicacao_robo_v103(materia, pauta, imagem)
            ok, motivos = validar_qualidade_materia(materia, pauta)
            if not ok:
                self._log(uid, "quality_gate_v103", "BLOQUEADO para publicação direta: " + "; ".join(motivos[:5]), sucesso=False)
                pauta["_forcar_rascunho_v82"] = True
                pauta.setdefault("_motivos_rascunho_v82", []).append("quality_gate_v103: " + "; ".join(motivos[:3]))
                materia.status_publicacao_sugerido = "salvar_rascunho"
                materia.revisao_humana_necessaria = True
                materia.auditoria_bloqueada = True
                materia.auditoria_erros = list(getattr(materia, "auditoria_erros", []) or []) + ["quality_gate_v103: " + "; ".join(motivos[:3])]
                return True

            publicados = []
            try:
                publicados.extend(self.db.listar_publicadas_recentes(horas=72) or [])
            except Exception:
                pass
            try:
                from ururau.coleta.ururau_check import buscar_titulos_publicados_ururau
                publicados.extend(buscar_titulos_publicados_ururau(horas=72) or [])
            except Exception:
                pass
            dup, motivo_dup = detectar_duplicidade_materia(materia, publicados)
            if dup:
                self._log(uid, "duplicate_gate_v103", "BLOQUEADO: " + motivo_dup, sucesso=False)
                self._set_status(uid, pauta, 'revisada', motivo_dup)
                pauta["_forcar_rascunho_v82"] = True
                pauta.setdefault("_motivos_rascunho_v82", []).append("duplicidade: " + motivo_dup)
                materia.status_publicacao_sugerido = "salvar_rascunho"
                materia.revisao_humana_necessaria = True
                materia.auditoria_bloqueada = True
                materia.auditoria_erros = list(getattr(materia, "auditoria_erros", []) or []) + ["duplicate_gate_v103: " + motivo_dup]
            else:
                self._log(uid, "quality_gate_v103", "OK sem duplicidade detectada nas publicações recentes.", sucesso=True)
            return True
        except Exception as e:
            self._log(uid, "quality_gate_v103", f"FAIL-CLOSED: {e}", sucesso=False)
            pauta["_forcar_rascunho_v82"] = True
            pauta.setdefault("_motivos_rascunho_v82", []).append(f"quality_gate_v103 falhou: {e}")
            return True

    def etapa_verificacao_risco(self, uid: str, pauta: dict, materia: Materia) -> bool:
        """
        Verifica score de risco editorial.
        Retorna False (e bloqueia) se score >= LIMIAR_RISCO_MAXIMO.
        """
        resultado = analisar_risco(materia.conteudo, canal=materia.canal)
        materia.score_risco = _v4718_get_score(resultado, 0)
        pauta["score_risco"] = _v4718_get_score(resultado, 0)

        resumo = resumo_risco(resultado)
        self._log(uid, "risco", resumo, sucesso=not _v4720_get_bool(resultado, 'bloqueante', False))

        if _v4720_get_bool(resultado, 'bloqueante', False):
            self._set_status(
                uid, pauta, 'bloqueada',
                f"Score de risco: {_v4718_get_score(resultado, 0)}/100 — {', '.join(resultado.alertas[:3])}"
            )
            return False

        self._set_status(uid, pauta, 'revisada')
        return True

    def etapa_persistir_materia(self, uid: str, pauta: dict, materia: Materia) -> bool:
        """
        Persiste matéria no banco de dados.

        IMPORTANTE: NÃO define status=PRONTA se a auditoria bloqueou a matéria.
        Matérias bloqueadas ficam em 'revisada' (aguardando revisão humana).
        Apenas matérias aprovadas chegam a 'pronta'.
        """
        try:
            materia_dict = materia.to_dict()
            pauta["materia"] = materia_dict
            self.db.salvar_materia(uid, materia_dict)
            self.db.salvar_pauta({**pauta, "_uid": uid})

            # Nunca marca PRONTA se há CONFIG_ERROR ou EXTRACTION_ERROR
            _erros_mat = materia_dict.get("erros_validacao", []) or []
            _has_sys_error = (
                materia_dict.get("_is_config_error") or
                materia_dict.get("status_validacao") in ("erro_configuracao", "erro_extracao") or
                any(
                    isinstance(e, dict) and e.get("categoria") in (
                        CategoriaErro.CONFIG_ERROR, CategoriaErro.EXTRACTION_ERROR
                    )
                    for e in _erros_mat
                )
            )
            if _has_sys_error:
                self._set_status(uid, pauta, 'revisada')
                self._log(uid, "persistencia",
                          "Matéria salva para REVISÃO HUMANA — CONFIG/EXTRACTION ERROR detectado",
                          sucesso=False)
            # Gate: só marca PRONTA se a auditoria aprovada E não bloqueada
            elif materia.auditoria_aprovada and not materia.auditoria_bloqueada:
                self._set_status(uid, pauta, 'pronta')
                self._log(uid, "persistencia", "Matéria aprovada e salva como PRONTA")
            else:
                # Bloqueada ou pendente: salva como REVISADA (aguarda revisão humana)
                self._set_status(uid, pauta, 'revisada')
                self._log(uid, "persistencia",
                          f"Matéria salva para REVISÃO HUMANA "
                          f"(auditoria_bloqueada={materia.auditoria_bloqueada}, "
                          f"status_pipeline={materia.status_pipeline})")
            return True
        except Exception as e:
            self._log(uid, "persistencia", f"Erro: {e}", sucesso=False)
            return False

    def etapa_publicacao(
        self,
        uid: str,
        pauta: dict,
        materia: Materia,
        imagem: Optional[ImagemDados],
        rascunho: bool = True,
    ) -> bool:
        """
        Executa publicação via Playwright.

        rascunho=True (padrão) → salva como rascunho no CMS (não publica ao vivo).
        rascunho=False → publica diretamente (use com cautela).

        Gate v62: chama can_publish() antes de qualquer ação no CMS.
        Em modo rascunho, ainda permite envio (CMS recebe e salva como draft),
        mas registra o motivo do bloqueio para auditoria.
        """
        # Gate v67: FAIL-CLOSED em modo monitor (rascunho=False).
        artigo_dict = {}
        try:
            artigo_dict = materia.to_dict() if hasattr(materia, "to_dict") else {}
        except Exception:
            artigo_dict = {}
        # v85: publicação manual pelo Preview. Quando o editor escolhe "Publicar!",
        # o workflow deve chamar o CMS e respeitar a aprovação humana, salvo falha fatal.
        try:
            manual_override = bool(
                pauta.get("forcar_publicacao_manual") or
                pauta.get("aprovacao_manual_editor") or
                artigo_dict.get("forcar_publicacao_manual") or
                artigo_dict.get("aprovacao_manual_editor") or
                (artigo_dict.get("approved_by") and artigo_dict.get("approved_at") and artigo_dict.get("manual_approval_reason"))
            )
        except Exception:
            manual_override = False

        def _bloqueio_fatal_manual(_art: dict) -> str:
            corpo = (_art.get("corpo_materia") or _art.get("conteudo") or "").strip()
            if len(corpo) < 100:
                return "bloqueio fatal: matéria sem corpo suficiente para cadastrar no CMS"
            sv = str(_art.get("status_validacao") or "").lower().strip()
            if sv in {"erro_configuracao", "erro_extracao"}:
                return f"bloqueio fatal: status_validacao={sv}"
            for e in (_art.get("erros_validacao") or []):
                if isinstance(e, dict) and str(e.get("categoria", "")).upper() in {"CONFIG_ERROR", "EXTRACTION_ERROR"}:
                    return f"bloqueio fatal: {e.get('categoria')} {e.get('codigo','')}"
            return ""

        if manual_override and not rascunho:
            fatal = _bloqueio_fatal_manual(artigo_dict)
            if fatal:
                self.ultimo_resultado_cms = {"ok": False, "status": "bloqueado", "mensagem": fatal}
                self._log(uid, "gate_manual_preview_v85", fatal, sucesso=False)
                return False
            self._log(uid, "gate_manual_preview_v85",
                      "Publicação direta autorizada manualmente no Preview; gates editoriais automáticos foram convertidos em aviso.",
                      sucesso=True)
            pode, motivo = True, "aprovação manual no Preview"
        else:
            try:
                # v69c: modo apropriado - rascunho=False (publicacao real) eh "monitor"
                _modo_cp = "monitor" if not rascunho else "panel"
                pode, motivo = can_publish(artigo_dict, modo=_modo_cp)
            except Exception as _e:
                if not rascunho:
                    self.ultimo_resultado_cms = {"ok": False, "status": "bloqueado", "mensagem": f"can_publish lançou erro: {_e}"}
                    self._log(uid, "gate_can_publish",
                              f"FAIL-CLOSED (monitor): can_publish lancou: {_e}",
                              sucesso=False)
                    return False
                else:
                    self._log(uid, "gate_can_publish",
                              f"Aviso (rascunho): can_publish falhou - prosseguindo. {_e}",
                              sucesso=True)
                    pode, motivo = True, ""
            if not pode and not rascunho:
                self.ultimo_resultado_cms = {"ok": False, "status": "bloqueado", "mensagem": f"Publicação direta bloqueada por can_publish: {motivo}"}
                self._log(uid, "gate_can_publish",
                          f"Publicação direta bloqueada por can_publish: {motivo}", sucesso=False)
                return False
            if not pode and rascunho:
                self._log(uid, "gate_can_publish",
                          f"[v82] Enviando RASCUNHO ao painel do Ururau mesmo com restrições: {motivo}",
                          sucesso=True)

        # v77: gate final de produção antes de publicação real no painel.
        if not rascunho and not manual_override:
            try:
                from ururau.publisher.producao_v77 import (
                    validar_ambiente_publicacao_real,
                    gate_editorial_publicacao_real,
                    limpar_chamada_social,
                )
                gate_env = validar_ambiente_publicacao_real()
                if not gate_env.aprovado:
                    self._log(uid, "v77_env_gate",
                              f"BLOQUEADO: {gate_env.motivo_texto()}",
                              sucesso=False)
                    return False
                try:
                    materia.chamada_social = limpar_chamada_social(getattr(materia, "chamada_social", ""))
                except Exception:
                    pass
                gate_ed = gate_editorial_publicacao_real(materia)
                if not gate_ed.aprovado:
                    self._log(uid, "v77_editorial_gate",
                              f"BLOQUEADO: {gate_ed.motivo_texto()}",
                              sucesso=False)
                    return False
                self._log(uid, "v77_editorial_gate", "OK", sucesso=True)
            except Exception as _e:
                self._log(uid, "v77_editorial_gate",
                          f"FAIL-CLOSED: {_e}", sucesso=False)
                return False

        # v67: gate adicional para monitor (publicacao direta)
        if not rascunho and not manual_override:
            try:
                from ururau.editorial.quality_gates import monitor_autopub_check
                pode_dir, motivos = monitor_autopub_check(artigo_dict)
                if not pode_dir:
                    self._log(uid, "monitor_autopub_gate",
                              f"BLOQUEADO: {'; '.join(motivos[:3])}",
                              sucesso=False)
                    return False
                self._log(uid, "monitor_autopub_gate", "OK", sucesso=True)
            except Exception as _e:
                self._log(uid, "monitor_autopub_gate",
                          f"FAIL-CLOSED: {_e}", sucesso=False)
                return False

        # v103: última barreira imediatamente antes do CMS. Nunca envia matéria em
        # bloco único/curta ao vivo. Rascunho ainda pode seguir para revisão humana.
        try:
            from ururau.editorial.quality_gate_v103 import aplicar_padrao_publicacao_robo_v103, validar_qualidade_materia
            materia = aplicar_padrao_publicacao_robo_v103(materia, pauta, imagem)
            ok_q, motivos_q = validar_qualidade_materia(materia, pauta)
            if not ok_q and not rascunho and not manual_override:
                self._log(uid, "quality_gate_v103_presubmit", "BLOQUEADO AO VIVO: " + "; ".join(motivos_q[:4]), sucesso=False)
                return False
            if not ok_q and rascunho:
                self._log(uid, "quality_gate_v103_presubmit", "RASCUNHO com avisos: " + "; ".join(motivos_q[:4]), sucesso=False)
        except Exception as e_q:
            self._log(uid, "quality_gate_v103_presubmit", f"FAIL-CLOSED: {e_q}", sucesso=False)
            if not rascunho and not manual_override:
                return False

        try:
            from ururau.publisher.preflight_publicacao_v47_23 import preflight_publicacao
            ok_pre_v4723, msg_pre_v4723 = preflight_publicacao(pauta, materia, imagem, rascunho=rascunho)
            # PATCH_V47_23_PREFLIGHT_IMAGEM
            if not ok_pre_v4723:
                self._log(uid, 'preflight_publicacao_v47_23', msg_pre_v4723, sucesso=False)
                try:
                    pauta['status_pipeline'] = 'aguardando_imagem'
                    materia.status_pipeline = 'aguardando_imagem'
                except Exception:
                    pass
                return False
            from ururau.publisher.cms_playwright_v81 import publicar_no_cms_v81
            print(f"[v103][PUBLICACAO] Chamando CMS Playwright v81: canal={materia.canal} rascunho={rascunho}")
            resultado_cms = publicar_no_cms_v81(materia, imagem, publicar=(not rascunho), rascunho=rascunho)
            self.ultimo_resultado_cms = resultado_cms
            sucesso = bool(resultado_cms.get("ok"))
            if not sucesso:
                self._log(uid, "publicacao_cms_v81",
                          f"Falha: {resultado_cms.get('mensagem')} screenshot={resultado_cms.get('screenshot')} html={resultado_cms.get('html_debug')}",
                          sucesso=False)
            if sucesso:
                if rascunho:
                    try:
                        materia.status_pipeline = "rascunho_cms"
                        materia.status_publicacao_sugerido = "salvar_rascunho"
                        pauta["status_pipeline"] = "rascunho_cms"
                    except Exception:
                        pass
                    self._set_status(uid, pauta, 'revisada')
                    self._log(uid, "publicacao",
                              "[v82][CMS] Matéria salva como RASCUNHO no painel do Ururau para revisão humana.",
                              sucesso=True)
                else:
                    try:
                        materia.status_pipeline = "publicado"
                    except Exception:
                        pass
                    self._set_status(uid, pauta, 'publicada')
                    self.db.registrar_publicacao(
                        uid, materia.canal, materia.titulo,
                        sucesso=True,
                        link_origem=pauta.get("link_origem", ""),
                    )
                    self._log(uid, "publicacao", f"[v82][CMS] Publicado ao vivo | Canal: {materia.canal}")
                return True
            else:
                self._log(uid, "publicacao", "Falha na publicação", sucesso=False)
                pauta["tentativas_publicacao"] = pauta.get("tentativas_publicacao", 0) + 1
                return False
        except Exception as e:
            self.ultimo_resultado_cms = {"ok": False, "status": "erro", "mensagem": f"{type(e).__name__}: {e}"}
            self._log(uid, "publicacao", f"Erro: {e}", sucesso=False)
            return False

    # ── Pipeline principal ────────────────────────────────────────────────────

    def executar_publicacao(
        self,
        pauta: dict,
        publicar: bool = True,
    ) -> dict:
        """
        Executa o workflow completo para uma pauta.

        Parâmetros:
            pauta: dict com dados da pauta (deve ter título, link, canal_forcado)
            publicar: se True, tenta publicar no CMS após aprovação

        Retorna dict com resultado do workflow:
            - sucesso: bool
            - uid: str
            - status: str
            - materia: dict | None
            - imagem: dict | None
            - erro: str
        """
        uid = pauta.get("_uid") or _uid_para_pauta(
            pauta.get("link_origem", ""),
            pauta.get("titulo_origem", ""),
        )
        pauta["_uid"] = uid

        resultado = {
            "sucesso": False,
            "uid": uid,
            "status": pauta.get("status", 'captada'),
            "materia": None,
            "imagem": None,
            "erro": "",
        }

        self._log(uid, "inicio_workflow", pauta.get("titulo_origem", "")[:80])

        # ── Etapa 0: Gate anti-duplicação (modo redigir — não bloqueia rascunhos) ─
        if not self.etapa_gate_antiduplicacao(uid, pauta, modo="redigir"):
            resultado["status"] = pauta.get("status", 'rejeitada')
            resultado["erro"] = "Pauta bloqueada pelo gate anti-duplicacao"
            return resultado

        # ── Etapa 1: Triagem ───────────────────────────────────────────────────
        if not self.etapa_triagem(uid, pauta):
            resultado["status"] = pauta["status"]
            resultado["erro"] = "Falhou triagem"
            return resultado

        # ── Etapa 2: Coleta de texto ───────────────────────────────────────────
        # v68: respeita resultado da extracao - se failed, NAO segue para geracao.
        # modo do workflow: panel quando publicar=False (rascunho), monitor quando publicar=True.
        _modo_extracao = "monitor" if publicar else "panel"
        if not self.etapa_coleta_texto(uid, pauta, modo=_modo_extracao):
            resultado["status"] = pauta.get("status", 'bloqueada')
            resultado["status_pipeline"] = "bloqueado_coleta"
            resultado["erro"] = pauta.get("motivo_bloqueio_coleta_v83") or "Falhou na extracao da fonte (FAIL-CLOSED v83)"
            resultado["sucesso"] = False
            return resultado

        # ── Etapa 3: Imagem ────────────────────────────────────────────────────
        imagem = self.etapa_imagem(uid, pauta)
        if imagem:
            resultado["imagem"] = imagem.to_dict()

        # ── Etapa 4: Redação ───────────────────────────────────────────────────
        materia = self.etapa_redacao(uid, pauta)
        if not materia:
            resultado["status"] = pauta["status"]
            resultado["erro"] = "Falhou na redação"
            return resultado

        # ── Etapa 5: Pacote editorial ──────────────────────────────────────────
        materia = self.etapa_pacote_editorial(uid, materia, pauta)

        # ── Etapa 5.1 v102: Copydesk IA automático antes de publicar/salvar ────
        materia = self.etapa_copydesk_automatico_v102(
            uid, pauta, materia, modo=("monitor" if publicar else "panel")
        )

        # ── Etapa 5.2 v103: qualidade final comum ao monitor e painel ────────
        self.etapa_gate_qualidade_final_v103(uid, pauta, materia, imagem)

        # ── Etapa 6: Verificação de risco ──────────────────────────────────────
        if not self.etapa_verificacao_risco(uid, pauta, materia):
            resultado["status"] = pauta.get("status", 'rejeitada')
            resultado["erro"] = "Bloqueada por risco editorial"
            return resultado

        # ── Etapa 7: Persistência ──────────────────────────────────────────────
        if not self.etapa_persistir_materia(uid, pauta, materia):
            resultado["status"] = pauta["status"]
            resultado["erro"] = "Falha na persistência"
            return resultado

        resultado["materia"] = materia.to_dict()

        # v82: decisão única de destino. Auditoria bloqueia publicação direta,
        # mas não bloqueia automaticamente o envio como rascunho real no CMS.
        try:
            from ururau.editorial.decision_v82 import (
                decidir_destino_publicacao_v82,
                aplicar_aviso_rascunho_v82,
            )
            auditoria = getattr(materia, "auditoria_factual_v81", {}) or {}
            contexto_decisao = {
                "chars_fonte": len(pauta.get("cleaned_source_text") or pauta.get("dossie") or pauta.get("texto_fonte") or ""),
                "extraction_status": pauta.get("extraction_status", ""),
                "link_origem": pauta.get("link_origem", ""),
                "fonte_nome": pauta.get("fonte_nome", ""),
                "publicar_solicitado": publicar,
                "permitir_publicacao_direta": bool(publicar),
                "modo_cms": "direto" if publicar else "rascunho",
            }
            decisao = decidir_destino_publicacao_v82(materia, auditoria, contexto_decisao)
            resultado["decisao_v82"] = decisao
            self._log(uid, "decisao_v82",
                      f"destino={decisao.get('destino')} rascunho={decisao.get('rascunho')} motivos={'; '.join(decisao.get('motivos', [])[:3])}",
                      sucesso=(decisao.get("destino") != "bloquear_total"))
        except Exception as e:
            decisao = {
                "destino": "bloquear_total",
                "pode_enviar_cms": False,
                "rascunho": True,
                "motivos": [f"falha na decisão v82: {e}"],
                "aviso": None,
            }
            resultado["decisao_v82"] = decisao
            self._log(uid, "decisao_v82", f"FAIL-CLOSED: {e}", sucesso=False)

        if publicar:
            destino = decisao.get("destino")
            if destino == "publicar_direto":
                ok_pub = self.etapa_publicacao(uid, pauta, materia, imagem, rascunho=False)
                resultado["sucesso"] = bool(ok_pub)
                resultado["status_pipeline"] = "publicado" if ok_pub else "erro_cms"
                resultado["status"] = pauta.get("status", 'publicada' if ok_pub else 'revisada')
                if not ok_pub:
                    resultado["erro"] = "Falha na publicação direta CMS"
                return resultado

            if destino == "salvar_rascunho":
                try:
                    materia = aplicar_aviso_rascunho_v82(materia, decisao.get("aviso"))
                    self._log(uid, "aviso_rascunho",
                              decisao.get("aviso") or "Matéria será enviada como rascunho no CMS.",
                              sucesso=True)
                except Exception:
                    pass
                ok_rasc = self.etapa_publicacao(uid, pauta, materia, imagem, rascunho=True)
                resultado["sucesso"] = bool(ok_rasc)
                resultado["status_pipeline"] = "rascunho_cms" if ok_rasc else "erro_cms"
                resultado["status"] = pauta.get("status", 'revisada')
                if ok_rasc:
                    resultado["erro"] = ""
                    self._log(uid, "resultado_v82",
                              "Pipeline concluído como rascunho no painel do Ururau.",
                              sucesso=True)
                else:
                    resultado["erro"] = "Falha ao salvar rascunho no CMS"
                return resultado

            resultado["sucesso"] = False
            resultado["status_pipeline"] = "bloqueado_local"
            resultado["status"] = pauta.get("status", 'revisada')
            resultado["erro"] = "Bloqueada até para rascunho: " + "; ".join(decisao.get("motivos", [])[:4])
            self._log(uid, "bloqueio_total_v82", resultado["erro"], sucesso=False)
            return resultado

        resultado["sucesso"] = True
        resultado["status"] = pauta.get("status", 'pronta')
        resultado["status_pipeline"] = "local_sem_cms"
        return resultado
