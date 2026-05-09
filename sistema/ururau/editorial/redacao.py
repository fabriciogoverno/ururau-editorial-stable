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

import re
from typing import TYPE_CHECKING

from ururau.config.house_style import instrucao_canal, template_para_canal
from ururau.core.models import MapaEvidencias, Materia
from ururau.editorial.extracao import (
    extrair_mapa_evidencias,
    mapa_para_contexto_redacao,
    separar_fonte_de_metadados,
)
from ururau.editorial.risco import analisar_risco
from ururau.editorial.safe_title import (
    safe_title,
    safe_truncate,
    validar_limites_titulos,
    LIMITE_TITULO_SEO,
    LIMITE_TITULO_CAPA,
)
from ururau.ia.pipeline import executar_pipeline
from ururau.ia.logger import obter_logger


# Alias mantido por compatibilidade com chamadas legadas em outros módulos.
# Internamente delega para safe_title (módulo editorial.safe_title).
def _truncar_titulo_seguro(texto: str, limite: int) -> str:
    """Wrapper legado — usar safe_title diretamente em código novo."""
    return safe_title(texto, limite)

if TYPE_CHECKING:
    from openai import OpenAI


def _extrair_texto_corpo(dados: dict, fallback: str = "") -> str:
    """
    Extrai o corpo da matéria dos dados, tentando todos os aliases possíveis.
    Ordem de prioridade: corpo_materia > texto_final > conteudo > fallback.
    """
    return (
        dados.get("corpo_materia")
        or dados.get("texto_final")
        or dados.get("conteudo")
        or fallback
    )


def _extrair_subtitulo(dados: dict, fallback: str = "") -> str:
    """
    Extrai o subtítulo tentando todos os aliases.
    Ordem: subtitulo_curto > subtitulo > fallback.
    """
    return (
        dados.get("subtitulo_curto")
        or dados.get("subtitulo")
        or fallback
    )


def _extrair_legenda(dados: dict, fallback: str = "Reprodução") -> str:
    """
    Extrai a legenda tentando todos os aliases.
    Ordem: legenda_curta > legenda > fallback.
    """
    return (
        dados.get("legenda_curta")
        or dados.get("legenda")
        or fallback
    )


def gerar_materia(
    pauta: "dict | object",
    client: "OpenAI",
    modelo: str,
    canal: str,
    modo_operacional: str = "painel",
    caminho_db: str = "ururau.db",
) -> Materia:
    """
    Pipeline principal de redação — v49.

    1. Extrai mapa de evidências (ancora toda geração em fatos confirmados).
    2. Executa pipeline IA: geração + auditoria + aprendizado.
    3. Bloqueia se auditoria reprovar.
    4. Aplica score de risco editorial.
    5. Retorna Materia populada com metadados completos de auditoria.
    """

    # ── Compatibilidade dict / dataclass ──────────────────────────────────────
    def _get(key: str, default=""):
        if isinstance(pauta, dict):
            return pauta.get(key, default)
        return getattr(pauta, key, default)

    titulo_origem = _get("titulo_origem")
    resumo_origem = _get("resumo_origem")
    texto_fonte   = _get("texto_fonte")
    link_origem   = _get("link_origem")
    fonte_nome    = _get("fonte_nome")
    dossie        = _get("dossie", "")
    score_edit    = int(_get("score_editorial", 0))
    uid           = _get("uid") or _get("_uid", "")

    pauta_dict: dict = {
        "uid":           uid,
        "titulo_origem": titulo_origem,
        "resumo_origem": resumo_origem,
        "texto_fonte":   texto_fonte,
        "link_origem":   link_origem,
        "fonte_nome":    fonte_nome,
        "dossie":        dossie,
        "canal_forcado": canal,
        # Metadados separados (disponíveis para o pipeline mas não devem virar fatos)
        "_legendas_fonte":        [],   # preenchido após separação (ver abaixo)
        "_creditos_fonte":        [],
        "_metadados_descartados": [],
    }

    # ── Etapa 0: Separação de metadados da fonte ─────────────────────────────
    # Separa legenda de imagem, créditos, links relacionados, timestamps e publicidade
    # do corpo real da matéria ANTES de qualquer extração ou geração.
    # REGRA: legendas e créditos NÃO devem virar fatos no artigo gerado.
    _texto_para_separar = (texto_fonte or "") + "\n" + (dossie or "")
    _separacao = separar_fonte_de_metadados(_texto_para_separar)
    _metadados_descartados = _separacao.get("metadados_descartados", [])
    _legendas_fonte = _separacao.get("legendas_identificadas", [])
    _creditos_fonte = _separacao.get("creditos_foto", [])
    _texto_limpo = _separacao.get("corpo_limpo", _texto_para_separar)

    print(f"[REDACAO] Separação de metadados: "
          f"{len(_metadados_descartados)} itens removidos "
          f"(legendas={len(_legendas_fonte)}, créditos={len(_creditos_fonte)})")
    if _metadados_descartados:
        for item in _metadados_descartados[:5]:
            print(f"[REDACAO]   Removido: {item}")

    # Usa o texto limpo (sem metadados) para extração e geração
    # dossie limpo = parte do texto_limpo que é "extra" além do texto_fonte
    _texto_fonte_limpo = _texto_limpo[:len(texto_fonte or "")] if texto_fonte else _texto_limpo
    _dossie_limpo = _texto_limpo[len(_texto_fonte_limpo):].strip()

    # Propaga metadados para o pauta_dict
    pauta_dict["_legendas_fonte"]        = _legendas_fonte
    pauta_dict["_creditos_fonte"]        = _creditos_fonte
    pauta_dict["_metadados_descartados"] = _metadados_descartados
    # Usa texto limpo no pipeline (evita que metadados virem fatos)
    pauta_dict["texto_fonte"] = _texto_fonte_limpo or texto_fonte or ""
    pauta_dict["dossie"]      = _dossie_limpo or dossie

    # ── Etapa 1: Mapa de evidências ───────────────────────────────────────────
    print(f"[REDACAO] Extraindo mapa de evidências: {titulo_origem[:60]}")
    try:
        mapa_dict = extrair_mapa_evidencias(
            titulo=titulo_origem,
            resumo=resumo_origem,
            texto_fonte=_texto_fonte_limpo or texto_fonte or "",
            dossie=_dossie_limpo or dossie,
            client=client,
            modelo=modelo,
        )
    except Exception as _e_mapa:
        print(f"[REDACAO v78b] mapa de evidências falhou; usando fallback local seguro: {_e_mapa}")
        try:
            from ururau.editorial.fallback_local import gerar_materia_fallback, classificar_canal_v78
            pauta_fb = dict(pauta_dict)
            pauta_fb["texto_fonte"] = (_texto_limpo or texto_fonte or dossie or resumo_origem or "")
            canal_fb = classificar_canal_v78(titulo_origem, resumo_origem + " " + pauta_fb.get("texto_fonte", ""), canal)
            m_fb = gerar_materia_fallback(pauta_fb, canal=canal_fb, motivo=f"Fallback v78b por falha na extração IA: {_e_mapa}")
            # Se a fonte é curta, bloqueia publicação direta.
            if len((pauta_fb.get("texto_fonte") or "").strip()) < 900:
                m_fb.status_validacao = "erro_extracao"
                m_fb.status_publicacao_sugerido = "salvar_rascunho"
                m_fb.revisao_humana_necessaria = True
                m_fb.auditoria_bloqueada = True
            return m_fb
        except Exception as _e_fb:
            raise RuntimeError(f"Falha de IA e fallback local indisponível: {_e_mapa} / {_e_fb}")
    contexto_redacao = mapa_para_contexto_redacao(mapa_dict)

    # Carrega estilo personalizado do .env
    import os as _os
    _ep = (_os.getenv("URURAU_ESTILO_POSITIVO") or "").strip()
    _en = (_os.getenv("URURAU_ESTILO_NEGATIVO") or "").strip()
    _ex = (_os.getenv("URURAU_ESTILO_EXEMPLOS") or "").strip()
    if _ep or _en or _ex:
        partes = ["== ESTILO EDITORIAL PERSONALIZADO =="]
        if _ep:
            partes.append(f"DIRETRIZES:\n{_ep}")
        if _en:
            partes.append(f"EXCLUSÕES:\n{_en}")
        if _ex:
            partes.append(f"EXEMPLOS DE REFERÊNCIA:\n{_ex}")
        contexto_redacao = "\n\n".join(partes) + "\n\n" + contexto_redacao

    instrucao_do_canal = instrucao_canal(canal)
    template = template_para_canal(canal)

    # ── v70: ENGINE CANONICO eh o caminho real de producao ──────────────────
    import os as _os70
    if _os70.getenv("URURAU_DISABLE_V70_ENGINE", "0").strip() not in ("1", "true", "yes"):
        try:
            from ururau.editorial.engine import generate_ururau_article
            _m70 = generate_ururau_article(pauta_dict, client, modelo, canal, modo=modo_operacional)
            print(f"[v81][REDACAO_BASE] engine canonico OK | status={_m70.status_validacao}")
            return _m70
        except Exception as _e70:
            print(f"[v81][REDACAO_BASE] engine canonico FALHOU: {_e70}")
            try:
                from ururau.editorial.fallback_local import gerar_materia_fallback, classificar_canal_v78
                pauta_fb = dict(pauta_dict)
                pauta_fb["texto_fonte"] = (_texto_limpo or texto_fonte or dossie or resumo_origem or "")
                canal_fb = classificar_canal_v78(titulo_origem, resumo_origem + " " + pauta_fb.get("texto_fonte", ""), canal)
                m_fb = gerar_materia_fallback(pauta_fb, canal=canal_fb, motivo=f"Engine v70 falhou: {_e70}")
                if len((pauta_fb.get("texto_fonte") or "").strip()) < 900:
                    m_fb.status_validacao = "erro_extracao"
                    m_fb.status_publicacao_sugerido = "salvar_rascunho"
                    m_fb.revisao_humana_necessaria = True
                    m_fb.auditoria_bloqueada = True
                return m_fb
            except Exception as _fallback_e:
                print(f"[REDACAO v78b] fallback_local falhou: {_fallback_e}")
            # Compatibilidade legada abaixo, apenas se fallback v78b indisponível.
            try:
                from ururau.editorial.engine import (
                    build_source_context, classify_article_type, build_editorial_angle,
                    build_paragraph_plan, build_editorial_brief, _build_local_draft_from_brief
                )
                from ururau.core.models import Materia as _M70
                _src70 = build_source_context(pauta_dict)
                _tipo70 = classify_article_type(_src70, canal)
                _plan70 = build_paragraph_plan(_tipo70, [])
                _angle70 = build_editorial_angle(_src70, _tipo70, [], [])
                _brief70 = build_editorial_brief(_src70, _tipo70, canal, [], [], _angle70, _plan70)
                _dados70 = _build_local_draft_from_brief(
                    _brief70,
                    reason=f"Engine v70 falhou ({_e70}); rascunho local v71 gerado para revisão."
                )
                _m70 = _M70()
                _m70.titulo = _dados70.get("titulo_seo") or titulo_origem
                _m70.titulo_capa = _dados70.get("titulo_capa", "")
                _m70.subtitulo = _dados70.get("subtitulo_curto", "")
                _m70.legenda = _dados70.get("legenda_curta", "")
                _m70.retranca = _dados70.get("retranca", canal)
                _m70.tags = ", ".join(_dados70.get("tags", []) or [])
                _m70.conteudo = _dados70.get("corpo_materia", "")
                _m70.meta_description = _dados70.get("meta_description", "")
                _m70.resumo_curto = _dados70.get("resumo_curto", "")
                _m70.chamada_social = _dados70.get("chamada_social", "")
                _m70.slug = _dados70.get("slug", "")
                _m70.fonte_nome = pauta_dict.get("fonte_nome", "")
                _m70.link_origem = pauta_dict.get("link_origem", "")
                _m70.canal = canal
                _m70.nome_da_fonte = _dados70.get("nome_da_fonte") or pauta_dict.get("fonte_nome") or "Fonte original"
                _m70.creditos_da_foto = _dados70.get("creditos_da_foto") or "Reprodução"
                _m70.status_validacao = "pendente"
                _m70.status_publicacao_sugerido = "salvar_rascunho"
                _m70.revisao_humana_necessaria = True
                _m70.auditoria_bloqueada = False
                _m70.auditoria_aprovada = False
                _m70.erros_validacao = _dados70.get("erros_validacao", [])
                _m70.cleaned_source_text = _src70.cleaned_source_text
                _m70.raw_source_text = _src70.raw_source_text
                _m70.generated_article_json = _dados70
                try:
                    from ururau.ia.diagnostico import aplicar_trace_em_materia
                    aplicar_trace_em_materia(_m70, _dados70.get("_ia_trace") or _dados70.get("ia_trace"), fallback_motivo=_dados70.get("ia_fallback_motivo") or f"Engine v70 falhou: {_e70}")
                except Exception:
                    pass
                return _m70
            except Exception as _fallback_e:
                from ururau.core.models import Materia as _M70
                _merr = _M70()
                _merr.titulo = titulo_origem
                _merr.subtitulo = resumo_origem
                _merr.legenda = resumo_origem[:100]
                _merr.retranca = canal
                _merr.canal = canal
                _merr.conteudo = (texto_fonte or resumo_origem or titulo_origem).strip()
                _merr.status_validacao = "pendente"
                _merr.status_publicacao_sugerido = "salvar_rascunho"
                _merr.revisao_humana_necessaria = True
                _merr.auditoria_bloqueada = False
                _merr.erros_validacao = [{
                    "categoria": "WARNING", "codigo": "engine_v71_emergency_fallback",
                    "mensagem": f"Fallback local emergencial usado. Erro original: {_e70}. Erro fallback: {_fallback_e}",
                    "bloqueia_publicacao": False, "corrigivel_automaticamente": True,
                }]
                try:
                    from ururau.ia.diagnostico import trace_fallback, aplicar_trace_em_materia
                    _tr = trace_fallback("redacao_emergency_fallback", modelo, f"Engine v70 e fallback estruturado falharam: {_e70} / {_fallback_e}", uid=uid, origem="redacao_v71_emergency")
                    aplicar_trace_em_materia(_merr, _tr, fallback_motivo=_tr.get("erro_mensagem", ""))
                except Exception:
                    pass
                return _merr

    # ── v69c: Pre-IA — required_facts + entity_relationships ANTES da geracao
    # Os fatos obrigatorios e relacoes entram como contexto no prompt para que
    # o GPT-4.1-mini gere artigo cobrindo todos os fatos essenciais.
    _required_facts_pre = []
    _relacoes_pre = []
    try:
        from ururau.editorial.coverage_por_tipo import extract_required_facts_from_source
        from ururau.editorial.relationships import extract_entity_relationships
        _src_pre = (_texto_limpo or texto_fonte or "")
        _tipo_pre = canal or ""
        _required_facts_pre = extract_required_facts_from_source(_src_pre, _tipo_pre)
        _relacoes_pre = extract_entity_relationships(_src_pre, _tipo_pre, client, modelo)
        # Anexa ao pauta_dict para o pipeline/agente usar no prompt
        pauta_dict["required_facts_pre"] = _required_facts_pre
        pauta_dict["entity_relationships_pre"] = _relacoes_pre
        # Anexa tambem ao contexto_redacao
        if _required_facts_pre:
            _bloco_req = "\n\n== FATOS OBRIGATORIOS DA FONTE (incluir todos no corpo) ==\n"
            _bloco_req += "\n".join(f"- [{f.get('type','')}] {f.get('text','')[:120]}"
                                    for f in _required_facts_pre[:15])
            contexto_redacao += _bloco_req
        if _relacoes_pre:
            _bloco_rel = "\n\n== RELACOES FACTUAIS (preservar subject->relationship->object) ==\n"
            _bloco_rel += "\n".join(
                f"- {r.get('subject','')} {r.get('relationship','')} {r.get('object','')}"
                for r in _relacoes_pre[:8]
            )
            contexto_redacao += _bloco_rel
        print(f"[REDACAO v69c] pre-IA: {len(_required_facts_pre)} fatos + "
               f"{len(_relacoes_pre)} relacoes adicionadas ao prompt")
    except Exception as _e:
        print(f"[REDACAO v69c] aviso: pre-IA falhou: {_e}")

    # ── Etapa 2: Geração IA — v69c usa AGENTE CANONICO por default ───────────
    # URURAU_USE_CANONICAL_AGENT=1 (default) usa agente_editorial_ururau.gerar_via_agente
    # Para fallback ao pipeline antigo, defina URURAU_USE_CANONICAL_AGENT=0.
    import os as _os69c
    _USE_CANON = _os69c.getenv("URURAU_USE_CANONICAL_AGENT", "1").strip() not in ("0", "false", "no")
    print(f"[REDACAO] Geracao IA (canal={canal}, modo={modo_operacional}, modelo={modelo}, "
          f"motor={'CANONICAL' if _USE_CANON else 'pipeline_legacy'})")

    resultado = None
    if _USE_CANON and client is not None:
        try:
            from ururau.agents.agente_editorial_ururau import gerar_via_agente
            # Repassa contexto_redacao via dossie para o agente
            pauta_dict_canon = dict(pauta_dict)
            pauta_dict_canon["dossie"] = (pauta_dict.get("dossie", "") + "\n\n" + contexto_redacao).strip()
            dados_canon = gerar_via_agente(
                pauta_dict_canon, client, modelo, canal, modo_operacional
            )
            # Adapta para a interface ResultadoPipeline esperada abaixo
            from types import SimpleNamespace
            resultado = SimpleNamespace(
                sucesso=True,
                dados_finais=dados_canon or {},
                aprovado_auditoria=bool(dados_canon and not dados_canon.get("_auditoria_bloqueada", False)),
                bloqueado=bool(dados_canon and dados_canon.get("_auditoria_bloqueada", False)),
                status_publicacao=dados_canon.get("status_publicacao_sugerido", "salvar_rascunho") if dados_canon else "bloquear",
                violacoes_factuais=dados_canon.get("_violacoes_factuais", []) if dados_canon else [],
                todos_erros=dados_canon.get("auditoria_erros", []) if dados_canon else [],
                erros_validacao_geracao=[],
                erros_validacao_auditoria=[],
                violacoes_editoriais=[],
                log=[],
                timestamp="",
                modelo_usado=modelo,
                tentativas_geracao=1,
                tentativas_auditoria=0,
                _modo_operacional=modo_operacional,
            )
            print(f"[REDACAO v69c] motor canonical OK")
        except Exception as _e:
            print(f"[REDACAO v69c] motor canonical FALHOU: {_e} - fallback ao pipeline legacy")
            resultado = None

    if resultado is None:
        resultado = executar_pipeline(
            pauta=pauta_dict,
            mapa_evidencias=mapa_dict,
            contexto_redacao=contexto_redacao,
            canal=canal,
            client=client,
            modelo=modelo,
            instrucao_canal=instrucao_do_canal,
            template=template,
            modo_operacional=modo_operacional,
            caminho_db=caminho_db,
        )

    # ── Etapa 3: Log completo ─────────────────────────────────────────────────
    logger = obter_logger(caminho_db)
    resultado._modo_operacional = modo_operacional  # type: ignore
    logger.registrar_de_resultado(resultado, pauta_dict, acao="geracao_materia")

    # ── Etapa 4: Extrai dados finais ──────────────────────────────────────────
    dados = resultado.dados_finais
    try:
        from ururau.ia.diagnostico import aplicar_trace_em_dados, trace_fallback
        if not isinstance(dados, dict):
            dados = {}
        if not dados.get("modo_geracao") and not dados.get("ia_status"):
            if client is None:
                _tr_sem_client = trace_fallback("redacao_pipeline", modelo, "Pipeline executado sem client OpenAI disponível", uid=uid, origem="pipeline_sem_client")
                dados = aplicar_trace_em_dados(dados, _tr_sem_client, fallback_motivo=_tr_sem_client.get("erro_mensagem", ""))
            else:
                # Caminhos legados podem gerar texto sem registrar telemetria. Não rotular como IA confirmada.
                dados.setdefault("modo_geracao", "sem_telemetria_ia")
                dados.setdefault("ia_provider", "indefinido")
                dados.setdefault("ia_modelo", modelo or "")
                dados.setdefault("ia_status", "sem_telemetria_ia")
                dados.setdefault("ia_etapa", "redacao_pipeline")
                dados.setdefault("ia_chamada_ok", False)
                dados.setdefault("ia_fallback_motivo", "Caminho legado retornou dados sem prova de chamada OpenAI.")
                dados.setdefault("ia_erros", [])
    except Exception:
        if not isinstance(dados, dict):
            dados = {}

    # Se pipeline falhou completamente — NÃO usar fragmento de fonte como corpo
    # Falha pode ser CONFIG_ERROR (API key inválida) ou EXTRACTION_ERROR (fonte vazia)
    if not dados:
        # Tenta aproveitar dados_finais que pipeline.py já preencheu com erro estruturado
        _df = resultado.dados_finais or {}
        _is_config_err = _df.get("_is_config_error", False)
        _status_val = _df.get("status_validacao", "")

        if _is_config_err or _status_val == "erro_configuracao":
            # CONFIG_ERROR: pipeline detectou falha de API — preserva o resultado já estruturado
            dados = _df
        else:
            # Outro tipo de falha de pipeline: cria rascunho técnico SEM corpo gerado por IA
            # corpo_materia fica VAZIO — nunca usar resumo_origem ou fonte como corpo
            dados = {
                "titulo_seo":         safe_title(titulo_origem, LIMITE_TITULO_SEO),
                "titulo_capa":        safe_title(titulo_origem, LIMITE_TITULO_CAPA),
                "subtitulo_curto":    safe_truncate(resumo_origem, 200),
                "legenda_curta":      safe_truncate(resumo_origem, 100) or "Reprodução",
                "retranca":           canal,
                "tags":               [canal],
                "nome_da_fonte":      "Redação",
                "creditos_da_foto":   "Reprodução",
                "corpo_materia":      "",          # NUNCA fragmento de fonte
                "editoria":           canal,
                "canal":              canal,
                "status_publicacao_sugerido": "bloquear",
                "justificativa_status": "Falha no pipeline de geração",
                "status_validacao":   "erro_extracao",
                "slug": re.sub(r"[^a-z0-9]+", "-", titulo_origem.lower())[:80].strip("-"),
                "meta_description":   resumo_origem[:155],
                "resumo_curto":       resumo_origem[:280],
                "chamada_social":     titulo_origem[:240],
                "estrutura_decisao":  "",
                "erros_validacao": [{
                    "categoria": "EXTRACTION_ERROR",
                    "codigo":    "pipeline_failure",
                    "mensagem":  "Pipeline falhou sem produzir dados — artigo não gerado.",
                    "campo":     "corpo_materia",
                    "bloqueante": True,
                }],
            }

    # ── Normalização de campos: resolve todos os aliases ─────────────────────
    # Título SEO — truncagem segura via safe_title (sem slicing bruto)
    titulo_seo = safe_title(
        str(dados.get("titulo_seo") or dados.get("titulo") or titulo_origem),
        LIMITE_TITULO_SEO,
    )

    # Título capa — truncagem segura via safe_title (sem slicing bruto)
    titulo_capa = safe_title(
        str(dados.get("titulo_capa") or titulo_origem),
        LIMITE_TITULO_CAPA,
    )

    # Subtítulo — aceita subtitulo_curto (v45) ou subtitulo (legado)
    subtitulo = str(_extrair_subtitulo(dados, ""))[:200].rstrip()

    # Legenda — aceita legenda_curta (v45) ou legenda (legado)
    legenda_raw = _extrair_legenda(dados, "Reprodução")
    legenda = str(legenda_raw)[:100].rstrip()
    if not legenda.strip():
        legenda = (subtitulo or titulo_capa or "Reprodução")[:100]

    # Canal/retranca: guard determinístico final para impedir editoria contaminada.
    try:
        from ururau.editorial.fallback_local import classificar_canal_v78
        _canal_corrigido = classificar_canal_v78(
            titulo_origem,
            " ".join([resumo_origem or "", _texto_limpo or "", str(dados.get("corpo_materia") or dados.get("conteudo") or "")]),
            str(dados.get("canal") or dados.get("editoria") or canal),
        )
        if _canal_corrigido:
            canal = _canal_corrigido
            dados["canal"] = canal
            dados["editoria"] = canal
    except Exception:
        pass

    # Retranca
    retranca = " ".join(str(dados.get("retranca") or canal).split()[:1])[:30].rstrip()
    if retranca in {"Esportes", "Economia"} and canal == "Política":
        retranca = "Política"

    # Meta description
    meta_description = str(dados.get("meta_description") or "")[:160]

    # Resumo curto
    resumo_curto = str(dados.get("resumo_curto") or "")[:280]

    # Chamada social
    chamada_social = str(dados.get("chamada_social") or "")[:240]

    # Slug
    slug = dados.get("slug") or re.sub(r"[^a-z0-9]+", "-", titulo_seo.lower())[:80].strip("-")

    # v68 fix: corpo_materia NUNCA usa resumo/titulo como fallback.
    texto_conteudo = _extrair_texto_corpo(dados, "")
    if not texto_conteudo or not texto_conteudo.strip():
        texto_conteudo = ""
        _err = {
            "categoria":  "EDITORIAL_BLOCKER",
            "codigo":     "corpo_materia_ausente",
            "severidade": "alta",
            "campo":      "corpo_materia",
            "mensagem":   "Corpo da materia vazio apos geracao - sem fallback (v68).",
            "trecho":     "",
            "sugestao":   "Reprocessar com fonte completa ou aprovar manualmente.",
            "bloqueia_publicacao":     True,
            "corrigivel_automaticamente": False,
        }
        erros_existentes = dados.get("erros_validacao") or []
        if not any(isinstance(e, dict) and e.get("codigo") == "corpo_materia_ausente"
                    for e in erros_existentes):
            erros_existentes.append(_err)
        dados["erros_validacao"] = erros_existentes
        dados["status_validacao"] = "erro_extracao"
        dados["status_publicacao_sugerido"] = "salvar_rascunho"
        dados["revisao_humana_necessaria"] = True

    # Normaliza parágrafos no corpo (garante \n\n entre parágrafos)
    # Importa a função de limpeza do pipeline para reusar a lógica
    try:
        from ururau.ia.pipeline import _corrigir_paragrafos
        texto_conteudo = _corrigir_paragrafos(texto_conteudo)
    except Exception:
        pass

    # Grava aliases canônicos no dict para compatibilidade total downstream
    dados["titulo_seo"]      = titulo_seo
    dados["titulo"]          = titulo_seo        # alias legado para painel
    dados["titulo_capa"]     = titulo_capa
    dados["subtitulo_curto"] = subtitulo
    dados["subtitulo"]       = subtitulo         # alias legado para copydesk / painel
    dados["legenda_curta"]   = legenda
    dados["legenda"]         = legenda           # alias legado para copydesk / painel
    dados["retranca"]        = retranca
    dados["meta_description"] = meta_description
    dados["resumo_curto"]    = resumo_curto
    dados["chamada_social"]  = chamada_social
    dados["slug"]            = slug
    dados["corpo_materia"]   = texto_conteudo
    dados["conteudo"]        = texto_conteudo    # alias legado para copydesk / painel
    dados["texto_final"]     = texto_conteudo    # alias legado para compatibilidade

    # ── Tags: sempre string separada por vírgulas ─────────────────────────────
    tags_raw = dados.get("tags", [canal])
    if isinstance(tags_raw, list):
        tags_str = ", ".join(str(t).strip() for t in tags_raw if str(t).strip())
    else:
        tags_str = str(tags_raw)
    dados["tags"] = tags_str

    # ── Etapa 4.5: Validação de limites de títulos (FIXABLE_FIELD) ───────────
    # Se algum título escapou do safe_title (raro), aplica correção e registra
    # em erros_validacao como FIXABLE_FIELD. Reaplica safe_title para garantir.
    _erros_titulo = validar_limites_titulos(dados)
    if _erros_titulo:
        # Re-corrige automaticamente
        dados["titulo_seo"]  = safe_title(dados["titulo_seo"], LIMITE_TITULO_SEO)
        dados["titulo_capa"] = safe_title(dados["titulo_capa"], LIMITE_TITULO_CAPA)
        dados["titulo"]      = dados["titulo_seo"]
        # Mescla erros (não duplicados)
        _existentes = dados.get("erros_validacao", []) or []
        dados["erros_validacao"] = list(_existentes) + _erros_titulo
        print(f"[REDACAO] ⚠ {len(_erros_titulo)} título(s) corrigido(s) por safe_title")

    # ── Etapa 4.7 (v67): Coverage Score + Quality Score reais ───────────────
    # Coverage: compara mapa de evidencias com corpo gerado.
    # Quality: penaliza erros, limites, expressoes proibidas, etc.
    try:
        from ururau.editorial.quality_gates import (
            calculate_fact_coverage,
            calculate_quality_score,
        )
        _cov = calculate_fact_coverage(dados, mapa_dict)
        _qual = calculate_quality_score(
            dados,
            essential_facts=mapa_dict,
            erros_validacao=dados.get("erros_validacao") or [],
            coverage=_cov,
        )
        dados["coverage_score"]   = _cov["coverage_score"]
        dados["facts_required"]   = _cov["facts_required"]
        dados["facts_used"]       = _cov["facts_used"]
        dados["facts_missing"]    = _cov["facts_missing"]
        dados["score_qualidade"]  = _qual["score_qualidade"]
        dados["score_qualidade_detalhes"] = _qual["detalhes"]
        print(f"[REDACAO] coverage_score={_cov['coverage_score']:.2f} | "
              f"facts_used={len(_cov['facts_used'])}/{len(_cov['facts_required'])} | "
              f"score_qualidade={_qual['score_qualidade']}/100")
        # Se cobertura baixa, adiciona EDITORIAL_BLOCKER
        if _cov["coverage_score"] < 0.85:
            erros_existentes = dados.get("erros_validacao") or []
            erros_existentes.append({
                "categoria": "EDITORIAL_BLOCKER",
                "codigo":    "low_source_coverage",
                "severidade":"alta",
                "campo":     "corpo_materia",
                "mensagem":  (f"Coverage baixa: {_cov['coverage_score']:.2f}. "
                              f"{len(_cov['facts_missing'])} fato(s) ausente(s)."),
                "trecho":    "",
                "sugestao":  "Reescreva o corpo incluindo os fatos essenciais ausentes.",
                "bloqueia_publicacao":     True,
                "corrigivel_automaticamente": False,
            })
            dados["erros_validacao"] = erros_existentes
    except Exception as _e:
        print(f"[REDACAO] Aviso: nao foi possivel calcular coverage/quality: {_e}")
        dados["coverage_score"]  = 0.0
        dados["score_qualidade"] = 0

    # ── Etapa 5: Score de risco ───────────────────────────────────────────────
    resultado_risco = analisar_risco(dados["conteudo"], canal=canal)
    score_risco = resultado_risco.score
    print(f"[REDACAO] Score de risco: {score_risco}/100 ({resultado_risco.nivel})")

    # ── Etapa 6: Informações de auditoria nos dados ───────────────────────────
    dados["_auditoria_aprovada"]  = resultado.aprovado_auditoria
    dados["_auditoria_bloqueada"] = resultado.bloqueado
    dados["_auditoria_erros"]     = resultado.todos_erros[:5]
    dados["_status_pipeline"]     = resultado.status_publicacao
    dados["_violacoes_factuais"]  = resultado.violacoes_factuais

    bloq_txt = "BLOQUEADA" if resultado.bloqueado else "APROVADA"
    print(f"[REDACAO] Auditoria: {bloq_txt} | Título: '{titulo_seo[:60]}'")
    print(f"[REDACAO] Corpo: {len(dados['conteudo'])} chars | "
          f"Parágrafos: {len([p for p in dados['conteudo'].split(chr(10)*2) if p.strip()])}")

    # ── Determina status da matéria com base na auditoria ────────────────────
    # Se a auditoria bloqueou → salva como rascunho para revisão humana.
    # Nunca expõe artigo bloqueado para publicação direta.
    _status_materia = "rascunho"
    if resultado.aprovado_auditoria and not resultado.bloqueado:
        _pub = resultado.status_publicacao
        if _pub == "publicar_direto":
            _status_materia = "pronta"
        elif _pub == "salvar_rascunho":
            _status_materia = "rascunho"
        else:
            _status_materia = "rascunho"

    if resultado.bloqueado:
        print(f"[REDACAO] ⛔ MATÉRIA BLOQUEADA — será salva como rascunho para revisão humana")
        print(f"[REDACAO] Motivos: {resultado.todos_erros[:3]}")

    # ── Etapa 7: Monta dataclass Materia ─────────────────────────────────────
    mapa_obj = MapaEvidencias(
        fato_principal    = mapa_dict.get("fato_principal", ""),
        fatos_secundarios = mapa_dict.get("fatos_secundarios", []),
        quem              = mapa_dict.get("quem", []),
        onde              = mapa_dict.get("onde", ""),
        quando            = mapa_dict.get("quando", ""),
        por_que_importa   = mapa_dict.get("por_que_importa", ""),
        consequencia      = mapa_dict.get("consequencia", ""),
        contexto_anterior = mapa_dict.get("contexto_anterior", ""),
        numero_principal  = mapa_dict.get("numero_principal", ""),
        orgao_central     = mapa_dict.get("orgao_central", ""),
        status_atual      = mapa_dict.get("status_atual", ""),
        proximos_passos   = mapa_dict.get("proximos_passos", ""),
        fonte_primaria    = mapa_dict.get("fonte_primaria", ""),
        fontes_secundarias = mapa_dict.get("fontes_secundarias", []),
        grau_confianca    = mapa_dict.get("grau_confianca", "medio"),
        risco_editorial   = mapa_dict.get("risco_editorial", "baixo"),
    )

    materia = Materia(
        retranca          = dados["retranca"],
        titulo            = dados["titulo"],
        titulo_capa       = dados["titulo_capa"],
        titulos_alternativos     = [],
        titulos_capa_alternativos = [],
        frase_chave       = dados.get("frase_chave", ""),
        slug              = dados["slug"],
        meta_description  = dados["meta_description"],
        subtitulo         = dados["subtitulo"],
        legenda           = dados["legenda"],
        tags              = dados["tags"],
        intertitulos      = [],
        estrutura_decisao = dados.get("estrutura_decisao", ""),
        conteudo          = dados["conteudo"],
        resumo_curto      = dados["resumo_curto"],
        chamada_social    = dados["chamada_social"],
        fonte_nome        = fonte_nome,
        link_origem       = link_origem,
        canal             = canal,
        score_editorial   = score_edit,
        score_risco       = score_risco,
        status            = _status_materia,
        mapa_evidencias   = mapa_obj,
        termos_ia_detectados = [],
        nome_da_fonte     = dados.get("nome_da_fonte", "Redação"),
        creditos_da_foto  = dados.get("creditos_da_foto", ""),
        auditoria_aprovada  = resultado.aprovado_auditoria,
        auditoria_bloqueada = resultado.bloqueado,
        auditoria_erros   = resultado.todos_erros[:5],
        status_pipeline   = resultado.status_publicacao,
        violacoes_factuais = resultado.violacoes_factuais,
        metadados_apurados = dados.get("metadados_apurados", {}),
    )

    # ── v69b: PROPAGAÇÃO COMPLETA dos campos para Materia ───────────────────
    # Bug do v69: este bloco estava truncado e gerar_materia() podia retornar None.
    # Agora todos os campos sao propagados, coverage tipado calculado, relacoes
    # validadas e finalmente retornamos a Materia com tudo populado.
    try:
        materia.coverage_score          = float(dados.get("coverage_score", 0.0) or 0.0)
        materia.score_qualidade         = int(dados.get("score_qualidade", 0) or 0)
        materia.score_risco_validacao   = int(dados.get("score_risco_validacao", 0) or 0)
        materia.facts_required          = list(dados.get("facts_required", []) or [])
        materia.facts_used              = list(dados.get("facts_used", []) or [])
        materia.facts_missing           = list(dados.get("facts_missing", []) or [])
        materia.entity_relationships    = list(dados.get("entity_relationships", []) or [])
        materia.relationship_errors     = list(dados.get("relationship_errors", []) or [])
        materia.source_sufficiency_score = int(_get("source_sufficiency_score", 0) or 0)
        materia.extraction_method       = str(_get("extraction_method", ""))
        materia.extraction_status       = str(_get("extraction_status", ""))
        materia.raw_source_text         = str(_get("raw_source_text", ""))[:8000]
        materia.cleaned_source_text     = str(_get("cleaned_source_text", _texto_limpo or ""))[:8000]
        materia.rss_context_text        = str(_get("rss_context_text", ""))[:4000]
        materia.article_type            = str(dados.get("article_type", "") or canal or "")
        materia.editorial_angle         = str(dados.get("editorial_angle", ""))
        materia.paragraph_plan          = list(dados.get("paragraph_plan", []) or [])
        materia.modo_geracao            = str(dados.get("modo_geracao", ""))
        materia.ia_provider             = str(dados.get("ia_provider", ""))
        materia.ia_modelo               = str(dados.get("ia_modelo", modelo or ""))
        materia.ia_status               = str(dados.get("ia_status", ""))
        materia.ia_etapa                = str(dados.get("ia_etapa", ""))
        materia.ia_chamada_ok           = bool(dados.get("ia_chamada_ok", False))
        materia.ia_fallback_motivo      = str(dados.get("ia_fallback_motivo", ""))
        materia.ia_erros                = list(dados.get("ia_erros", []) or [])
        materia.ia_texto_final_origem   = str(dados.get("ia_texto_final_origem", ""))
        materia.ia_openai_status        = str(dados.get("ia_openai_status", ""))
        materia.ia_openai_chamada_ok    = bool(dados.get("ia_openai_chamada_ok", False))
        materia.ia_erro_original_openai = dict(dados.get("ia_erro_original_openai", {}) or {})
        materia.generated_article_json  = {k: v for k, v in dados.items()
                                            if not k.startswith("_") and k != "metadados_apurados"
                                            and not callable(v)}
        # Status / revisao
        if dados.get("status_validacao"):
            materia.status_validacao = str(dados["status_validacao"])
            materia.status_publicacao_sugerido = str(dados["status_publicacao_sugerido"])
        if dados.get("revisao_humana_necessaria") is not None:
            materia.revisao_humana_necessaria = bool(dados["revisao_humana_necessaria"])
        if dados.get("erros_validacao"):
            materia.erros_validacao = list(dados["erros_validacao"])
    except Exception as _e:
        print(f"[REDACAO v69c] aviso: propagacao parcial falhou: {_e}")

    # ── v69c: Coverage tipado (validacao pos-IA) ─────────────────────────────
    try:
        from ururau.editorial.coverage_por_tipo import (
            extract_required_facts_from_source, calculate_fact_coverage_typed,
        )
        _src_cov = materia.cleaned_source_text or _texto_limpo or ""
        _tipo = materia.article_type or canal or ""
        if _src_cov:
            req_facts = extract_required_facts_from_source(_src_cov, _tipo)
            cov = calculate_fact_coverage_typed(dados, req_facts, _src_cov)
            materia.coverage_score = cov["coverage_score"]
            materia.facts_required = cov["facts_required"]
            materia.facts_used     = cov["facts_used"]
            materia.facts_missing  = cov["facts_missing"]
            print(f"[REDACAO v69c] coverage_tipado={cov['coverage_score']:.2f}")
            if cov["coverage_score"] < 0.85 and len(req_facts) > 0:
                erros = list(materia.erros_validacao or [])
                if not any(isinstance(e, dict) and e.get("codigo") == "low_source_coverage"
                           for e in erros):
                    erros.append({
                        "categoria": "EDITORIAL_BLOCKER",
                        "codigo": "low_source_coverage",
                        "severidade": "alta",
                        "campo": "corpo_materia",
                        "mensagem": f"Coverage tipado baixo: {cov['coverage_score']:.2f}",
                        "bloqueia_publicacao": True,
                        "corrigivel_automaticamente": False,
                    })
                    materia.erros_validacao = erros
                materia.auditoria_bloqueada = True
                materia.status_validacao = "reprovado"
    except Exception as _e:
        print(f"[REDACAO v69c] aviso: coverage falhou: {_e}")

    # ── v69c: Validacao de relacoes (pos-IA) ────────────────────────────────
    try:
        from ururau.editorial.relationships import (
            extract_entity_relationships, validate_entity_relationships,
        )
        _src_rel = materia.cleaned_source_text or _texto_limpo or ""
        if _src_rel:
            relacoes = extract_entity_relationships(_src_rel, materia.article_type, client, modelo)
            materia.entity_relationships = relacoes
            erros_rel = validate_entity_relationships(dados, relacoes)
            if erros_rel:
                materia.relationship_errors = erros_rel
                materia.erros_validacao = list(materia.erros_validacao or []) + erros_rel
                if any(e.get("categoria") == "EDITORIAL_BLOCKER" for e in erros_rel):
                    materia.auditoria_bloqueada = True
                    materia.status_validacao = "reprovado"
    except Exception as _e:
        print(f"[REDACAO v69c] aviso: relacoes falhou: {_e}")

    return materia

# ─────────────────────────────────────────────────────────────────────────────
# v78 PRODUÇÃO ESTÁVEL — fallback local global
# ─────────────────────────────────────────────────────────────────────────────
# O monitor 24h não pode morrer quando a OpenAI retorna 401, cota, timeout ou
# qualquer falha do engine. O wrapper abaixo mantém o engine profissional como
# caminho principal, mas gera uma matéria local conservadora se houver exceção.
try:
    _gerar_materia_pre_v78 = gerar_materia

    def gerar_materia(pauta, client, modelo, canal, modo_operacional="painel", caminho_db="ururau.db"):  # type: ignore[override]
        try:
            materia = _gerar_materia_pre_v78(pauta, client, modelo, canal, modo_operacional, caminho_db)
            if materia and (getattr(materia, "conteudo", "") or "").strip():
                return materia
            from ururau.editorial.fallback_local import gerar_materia_fallback
            return gerar_materia_fallback(pauta, canal, motivo="engine retornou matéria vazia", auditar=False)
        except Exception as exc:
            print(f"[REDACAO v78] fallback local acionado: {exc}")
            from ururau.editorial.fallback_local import gerar_materia_fallback
            return gerar_materia_fallback(pauta, canal, motivo=exc, auditar=False)
except Exception as _wrap_exc:
    print(f"[REDACAO v78] aviso: wrapper não instalado: {_wrap_exc}")

# ─────────────────────────────────────────────────────────────────────────────
# v78c — auditoria final + fallback forte sem IA
# ─────────────────────────────────────────────────────────────────────────────
# Esta camada é propositalmente instalada no final do arquivo para vencer os
# wrappers anteriores sem apagar histórico. Ela garante que toda matéria passe
# pela auditoria v78c e que falhas de IA/API caiam para fallback local seguro.
try:
    _gerar_materia_pre_v78c = gerar_materia

    def gerar_materia(pauta, client, modelo, canal, modo_operacional="painel", caminho_db="ururau.db"):  # type: ignore[override]
        from ururau.editorial.auditoria_v78c import aplicar_auditoria_v78c
        from ururau.editorial.fallback_local import gerar_materia_fallback

        def _texto_fonte_local(p):
            if isinstance(p, dict):
                return (
                    p.get("cleaned_source_text") or p.get("dossie") or
                    p.get("texto_fonte") or p.get("texto") or p.get("conteudo") or
                    p.get("resumo_origem") or ""
                )
            return (
                getattr(p, "cleaned_source_text", "") or getattr(p, "dossie", "") or
                getattr(p, "texto_fonte", "") or getattr(p, "texto", "") or
                getattr(p, "conteudo", "") or getattr(p, "resumo_origem", "") or ""
            )

        modo_norm = "monitor" if str(modo_operacional).lower() in {"monitor", "publicar", "direct"} else "panel"

        # v78d: se não há cliente de IA, não deixe o engine antigo v70 assumir o fluxo.
        # O v70 consegue montar um rascunho local curto e depois marca como ia_ou_engine,
        # o que mascara a ausência de IA e derruba a qualidade. Sem client/modelo local,
        # o caminho correto é o fallback forte determinístico v78c/v78d.
        import os as _os_v78d
        modelo_norm = str(modelo or "").strip().lower()
        sem_cliente_ia = client is None
        modelo_local = modelo_norm in {"fallback-local", "fallback_local", "local", "sem-ia", "sem_ia"}
        chave_ausente = not (_os_v78d.getenv("OPENAI_API_KEY") or "").strip()
        if sem_cliente_ia or modelo_local:
            motivo = "client=None" if sem_cliente_ia else f"modelo local: {modelo}"
            print(f"[v81][REDACAO] fallback forte sem IA acionado antes do engine: {motivo}")
            materia = gerar_materia_fallback(pauta, canal, motivo=motivo, auditar=False)
            return aplicar_auditoria_v78c(materia, _texto_fonte_local(pauta), modo=modo_norm, modo_geracao="fallback_sem_ia")

        if chave_ausente and _os_v78d.getenv("URURAU_FORCE_ENGINE_WITHOUT_OPENAI_KEY", "0").strip().lower() not in {"1", "true", "yes"}:
            print("[v81][REDACAO] OPENAI_API_KEY ausente: fallback forte sem IA acionado antes do engine")
            materia = gerar_materia_fallback(pauta, canal, motivo="OPENAI_API_KEY ausente", auditar=False)
            return aplicar_auditoria_v78c(materia, _texto_fonte_local(pauta), modo=modo_norm, modo_geracao="fallback_sem_ia")

        try:
            materia = _gerar_materia_pre_v78c(pauta, client, modelo, canal, modo_operacional, caminho_db)
            try:
                gj_tmp = getattr(materia, "generated_article_json", {}) or {}
                if materia and (gj_tmp.get("ia_trace") or gj_tmp.get("_ia_trace")):
                    from ururau.ia.diagnostico import aplicar_trace_em_materia
                    aplicar_trace_em_materia(materia, gj_tmp.get("_ia_trace") or gj_tmp.get("ia_trace"), fallback_motivo=gj_tmp.get("ia_fallback_motivo", ""))
            except Exception:
                pass
            if not materia or not (getattr(materia, "conteudo", "") or "").strip():
                materia = gerar_materia_fallback(pauta, canal, motivo="engine retornou matéria vazia", auditar=False)
                return aplicar_auditoria_v78c(materia, _texto_fonte_local(pauta), modo=modo_norm, modo_geracao="fallback_sem_ia")

            # Se o engine antigo devolveu reprovação técnica, tenta o fallback forte antes de entregar bloqueado.
            status_validacao = str(getattr(materia, "status_validacao", "") or "").lower()
            status_publicacao = str(getattr(materia, "status_publicacao_sugerido", "") or getattr(materia, "status_pipeline", "") or "").lower()
            score_atual = int(getattr(materia, "score_qualidade", 0) or 0)
            if status_validacao in {"erro_configuracao", "erro_extracao"} or (status_validacao == "reprovado" and score_atual < 75) or status_publicacao == "bloquear":
                print(f"[v81][REDACAO] engine devolveu status fraco ({status_validacao}/{status_publicacao}, score={score_atual}); tentando fallback forte")
                materia_fb = gerar_materia_fallback(pauta, canal, motivo=f"engine devolveu {status_validacao}/{status_publicacao} score={score_atual}", auditar=False)
                materia_fb = aplicar_auditoria_v78c(materia_fb, _texto_fonte_local(pauta), modo=modo_norm, modo_geracao="fallback_sem_ia")
                if int(getattr(materia_fb, "score_qualidade", 0) or 0) >= score_atual:
                    return materia_fb

            # Detecta se a matéria veio de fallback ou de IA e audita tudo.
            gj = getattr(materia, "generated_article_json", {}) or {}
            modo_geracao = (
                getattr(materia, "modo_geracao", "")
                or gj.get("modo_geracao")
                or ("fallback_sem_ia" if getattr(materia, "extraction_status", "") == "fallback_local_v78c" else "sem_telemetria_ia")
            )
            if modo_geracao in {"ia_ou_engine", "", None}:
                modo_geracao = "sem_telemetria_ia"
            materia = aplicar_auditoria_v78c(materia, _texto_fonte_local(pauta), modo=modo_norm, modo_geracao=modo_geracao)
            try:
                gj2 = dict(getattr(materia, "generated_article_json", {}) or {})
                gj2.setdefault("modo_geracao", modo_geracao)
                gj2.setdefault("ia_status", getattr(materia, "ia_status", "") or "sem_telemetria_ia")
                gj2.setdefault("ia_chamada_ok", bool(getattr(materia, "ia_chamada_ok", False)))
                setattr(materia, "generated_article_json", gj2)
                setattr(materia, "modo_geracao", modo_geracao)
            except Exception:
                pass
            return materia
        except Exception as exc:
            print(f"[v81][REDACAO] fallback forte acionado: {exc}")
            materia = gerar_materia_fallback(pauta, canal, motivo=exc, auditar=False)
            return aplicar_auditoria_v78c(materia, _texto_fonte_local(pauta), modo=modo_norm, modo_geracao="fallback_sem_ia")
except Exception as _wrap_exc_v78c:
    print(f"[v81][REDACAO] aviso: wrapper final não instalado: {_wrap_exc_v78c}")
