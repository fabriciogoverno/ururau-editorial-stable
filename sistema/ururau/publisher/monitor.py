"""
publisher/monitor.py — Robô de monitoramento 24h do Ururau v43.

FLUXO 1: MONITORAMENTO 24H
  - Modo explícito: local, rascunho CMS ou publicação ao vivo
  - Score mínimo mais alto (SCORE_MIN_AUTOPUBLICACAO)
  - Confiança mínima obrigatória (CONFIANCA_MIN_AUTOPUB)
  - Máx 4 publicações/hora (MAX_PUB_HORA_MONITOR)
  - Máx 4 pautas da mesma fonte por ciclo
  - Log de decisão transparente (motivo de aprovação/rejeição)

Uso:
    from ururau.publisher.monitor import MonitorRobo
    robo = MonitorRobo(db, client, modelo)
    robo.iniciar()   # bloqueia em loop — use em thread separada
    robo.parar()     # sinaliza parada limpa
"""

from __future__ import annotations
import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ururau.config.settings import (
    INTERVALO_ENTRE_CICLOS_SEGUNDOS,
    MAX_PUBLICACOES_MONITORAMENTO_POR_HORA,
    MAX_CANDIDATAS_AVALIADAS,
    LIMIAR_RELEVANCIA_PUBLICAR,
    LIMIAR_RELEVANCIA_URGENTE,
    LIMIAR_RISCO_MAXIMO,
    StatusPauta,
    SCORE_MONITOR_DIRETO_IMEDIATO,
    SCORE_MONITOR_DIRETO_CONFIANCA,
    SCORE_MONITOR_PAINEL_PRIORIDADE,
)

if TYPE_CHECKING:
    from openai import OpenAI
    from ururau.core.database import Database


# v84: evita dois monitores 24h rodando ao mesmo tempo no mesmo processo.
_MONITOR_GLOBAL_LOCK = threading.Lock()
_MONITOR_GLOBAL_ATIVO = False


def monitor_global_ativo() -> bool:
    """Retorna True quando já existe um monitor 24h rodando neste processo."""
    with _MONITOR_GLOBAL_LOCK:
        return bool(_MONITOR_GLOBAL_ATIVO)


def _monitor_cfg_v47_12() -> dict:
    try:
        p = Path(__file__).resolve().parents[2] / "config" / "monitor_24h.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _cfg_int_v47_12(name: str, default: int) -> int:
    try:
        cfg = _monitor_cfg_v47_12(); val = cfg.get(name, None)
        if val is None:
            for section in ("gates_monitor_24h", "coleta", "extracao_texto", "seo"):
                sub = cfg.get(section) or {}
                if isinstance(sub, dict) and name in sub:
                    val = sub.get(name); break
        return int(val) if int(val) > 0 else int(default)
    except Exception:
        return int(default)


# ── Logger ─────────────────────────────────────────────────────────────────────

def _setup_logger() -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("ururau.monitor")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_dir / "monitor.log", encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ── Classe principal ───────────────────────────────────────────────────────────

class MonitorRobo:
    """
    Robô de monitoramento editorial 24h.

    CRITÉRIOS RIGOROSOS (modo monitor):
      - rascunho=False  →  publica diretamente no CMS
      - score editorial mínimo: SCORE_MIN_AUTOPUBLICACAO (padrão 65, mais alto que o painel)
      - confiança mínima obrigatória: CONFIANCA_MIN_AUTOPUB (padrão 70)
      - exige pelo menos 1 critério de relevância real: regionalidade, impacto político,
        impacto policial, prioridade esportes/saúde/rural — NÃO publica só por score_base
      - máx 4 publicações/hora, mas NÃO corre para preenchê-las
      - se ciclo não encontrar nada relevante: aguarda INTERVALO_SEM_PAUTA (padrão 15 min)
        antes de tentar novamente, em vez do intervalo normal
      - máx 4 da mesma fonte por ciclo
      - log de decisão por pauta (motivo de aprovação/rejeição)
    """

    # Intervalo reduzido quando não há nada relevante (15 min)
    INTERVALO_SEM_PAUTA = int(os.getenv("INTERVALO_SEM_PAUTA_SEGUNDOS", str(_cfg_int_v47_12("intervalo_sem_pauta_segundos", 180))))
    # Score mínimo extra para monitor (mais alto que o painel)
    SCORE_MIN_MONITOR   = int(os.getenv("SCORE_MIN_MONITOR", str(_cfg_int_v47_12("score_minimo_monitor", _cfg_int_v47_12("score_minimo_rascunho", 35)))))
    # Exige sub-score de relevância acima de zero para publicação direta
    RELEVANCIA_MIN_MONITOR = int(os.getenv("RELEVANCIA_MIN_MONITOR", str(_cfg_int_v47_12("relevancia_minima_monitor", 3))))

    # v82: se não passar nos gates de publicação direta, tenta salvar no CMS como rascunho.
    RASCUNHO_SE_NAO_APROVAR = os.getenv("URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR", "1").lower() in ("1", "true", "sim", "yes", "s")
    SCORE_MIN_RASCUNHO = int(os.getenv("URURAU_SCORE_MINIMO_RASCUNHO", "30"))

    def __init__(
        self,
        db: "Database",
        client: "OpenAI",
        modelo: str,
        intervalo_segundos: int = INTERVALO_ENTRE_CICLOS_SEGUNDOS,
        max_por_hora: int = MAX_PUBLICACOES_MONITORAMENTO_POR_HORA,
        publicar_no_cms: bool = True,
        permitir_publicacao_direta: bool = False,
        modo_cms: str = "rascunho",
        intervalo_sem_pauta_segundos: Optional[int] = None,
    ):
        self.db               = db
        self.client           = client
        self.modelo           = modelo
        self.intervalo        = intervalo_segundos
        self.max_por_hora     = max_por_hora
        self.modo_cms         = (modo_cms or ("direto" if permitir_publicacao_direta else ("rascunho" if publicar_no_cms else "local"))).lower()
        if self.modo_cms not in ("local", "rascunho", "direto"):
            self.modo_cms = "rascunho"

        # v47.6: normaliza o destino real. Antes o painel podia exibir modo rascunho,
        # mas passar publicar_no_cms=False, fazendo o robô operar como LOCAL/BANCO.
        if self.modo_cms == "local":
            self.publicar_no_cms = False
            self.permitir_publicacao_direta = False
        elif self.modo_cms == "rascunho":
            self.publicar_no_cms = True
            self.permitir_publicacao_direta = False
        else:
            self.publicar_no_cms = True
            self.permitir_publicacao_direta = bool(permitir_publicacao_direta)

        self.intervalo_sem_pauta = int(intervalo_sem_pauta_segundos or self.intervalo or self.INTERVALO_SEM_PAUTA)
        self._parar           = threading.Event()
        self._log             = _setup_logger()
        self._publicados_hora: list[datetime] = []   # timestamps das publicações na janela 1h

    # ── Controle ───────────────────────────────────────────────────────────────

    def iniciar(self):
        """Entra em loop de monitoramento (bloqueante). Use em thread separada."""
        try:
            from ururau.publisher.monitor_capacidade_v47_9 import aplicar_defaults_coleta_monitor
            aplicar_defaults_coleta_monitor(forcar=True, logger=self._log)
        except Exception as _e_cap_v47_9:
            try: self._log.info(f"[V47.9][CAPACIDADE] Aviso: {_e_cap_v47_9}")
            except Exception: pass
        global _MONITOR_GLOBAL_ATIVO
        with _MONITOR_GLOBAL_LOCK:
            if _MONITOR_GLOBAL_ATIVO:
                self._log.warning("[v84] Monitor 24h já está ativo neste processo. Nova tentativa ignorada.")
                self._parar.set()
                return
            _MONITOR_GLOBAL_ATIVO = True
        self._log.info("=" * 60)
        _modo_desc = {
            "local": "LOCAL/BANCO",
            "rascunho": "RASCUNHO CMS",
            "direto": "PUBLICAÇÃO AO VIVO",
        }.get(self.modo_cms, "RASCUNHO CMS")
        self._log.info(f"=== MONITORAMENTO 24H iniciado — modo {_modo_desc} ===")
        self._log.info(
            f"Intervalo normal: {self.intervalo}s | "
            f"Intervalo sem pauta: {self.intervalo_sem_pauta}s | "
            f"Max/hora: {self.max_por_hora} | "
            f"Score mínimo monitor: {self.SCORE_MIN_MONITOR} | "
            f"modo_cms={self.modo_cms} | direta={self.permitir_publicacao_direta}"
        )
        self._log.info("=" * 60)
        ciclo = 0
        while not self._parar.is_set():
            ciclo += 1
            self._log.info(f"--- Ciclo {ciclo} [{datetime.now().strftime('%H:%M:%S')}] ---")
            publicadas_ciclo = 0
            try:
                publicadas_ciclo = self._executar_ciclo(ciclo)
            except Exception as e:
                self._log.error(f"Erro no ciclo {ciclo}: {e}", exc_info=True)

            if self._parar.is_set():
                break

            # Intervalo adaptativo: se publicou algo, aguarda o intervalo completo
            # Se não publicou nada relevante, aguarda apenas 15 min antes de tentar novamente
            if publicadas_ciclo > 0:
                espera = self.intervalo
                self._log.info(
                    f"Processadas/cadastradas: {publicadas_ciclo}. "
                    f"Aguardando {espera}s ({espera//60} min) para próximo ciclo..."
                )
            else:
                espera = self.intervalo_sem_pauta
                self._log.info(
                    f"Nenhuma pauta relevante encontrada neste ciclo. "
                    f"Monitor CONTINUA ATIVO; próxima busca em {espera}s ({espera//60} min)."
                )
            self._parar.wait(timeout=espera)

        with _MONITOR_GLOBAL_LOCK:
            _MONITOR_GLOBAL_ATIVO = False
        self._log.info("=== Monitoramento encerrado ===")

    def parar(self):
        """Sinaliza parada limpa. O ciclo corrente é concluído antes de sair."""
        self._log.info("Sinal de parada recebido.")
        self._parar.set()

    # ── Ciclo ──────────────────────────────────────────────────────────────────

    def _executar_ciclo(self, ciclo: int) -> int:
        """
        Ciclo completo de coleta → seleção → processamento.

        CRITÉRIOS MONITOR (mais rígidos que o painel):
          - score mínimo = SCORE_MIN_MONITOR (padrão 65, configurável)
          - confiança mínima = CONFIANCA_MIN_AUTOPUB (padrão 70)
          - exige pelo menos um sub-score de relevância > RELEVANCIA_MIN_MONITOR:
            regionalidade, impacto político, policial, esportes, saúde ou rural
          - NÃO publica apenas por score_base + frescor (não é pauta de relevância real)
          - máx 4 da mesma fonte no ciclo
          - retorna número de pautas publicadas no ciclo
        """
        from ururau.coleta.rss import (coletar_rss, coletar_google_news,
                                       deduplicar, filtrar_contra_banco,
                                       obter_termos_google_news,
                                       coletar_source_hunter_premium_v88,
                                       obter_termos_radar_audiencia_v88)
        from ururau.coleta.scoring import (
            calcular_score_completo,
            classificar_canal,
            filtrar_e_ordenar,
            PESOS,
        )
        from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta

        # ── 1. Coleta ──────────────────────────────────────────────────────────
        self._log.info("Coletando RSS + Google News...")
        fontes = _carregar_fontes_rss()
        raw: list[dict] = []
        if fontes:
            self._log.info(f"Fontes RSS carregadas: {len(fontes)}")
            raw += coletar_rss(fontes)

        # V47.7: AutoFontes/Diagnóstico de Fonte também entram no monitor 24h.
        # Não substitui RSS, Google News nem Source Hunter; apenas soma capacidade.
        try:
            from ururau.coleta.auto_perfil_fontes_v131 import coletar_todos_perfis_v131
            lotes_auto = coletar_todos_perfis_v131()
            qtd_auto = 0
            for perfil_auto, lote_auto, stats_auto in lotes_auto:
                if lote_auto:
                    qtd_auto += len(lote_auto)
                    raw += lote_auto
                try:
                    self._log.info(
                        f"[V47.7][AUTOFONTES] {perfil_auto.get('nome') or perfil_auto.get('dominio')} | "
                        f"{len(lote_auto or [])} pauta(s) | status={stats_auto.get('status_operacional') or stats_auto.get('parser_usado') or '-'}"
                    )
                except Exception:
                    pass
            if lotes_auto:
                self._log.info(f"[V47.7][AUTOFONTES] perfis={len(lotes_auto)} pautas={qtd_auto}")
        except Exception as e_auto:
            self._log.info(f"[V47.7][AUTOFONTES] indisponível/falhou: {e_auto}")

        # Termos do Google News: usa consultas_google_news.json se disponível
        _termos_fallback = [
            "Rio de Janeiro", "RJ policia", "RJ politica", "RJ economia",
            "governo RJ", "Rio noticias", "estado RJ", "saude RJ",
            "rural norte fluminense", "Porto do Açu", "Campos dos Goytacazes",
            "Norte Fluminense", "ALERJ", "TCE-RJ",
        ]
        termos_gnews = obter_termos_google_news(_termos_fallback)
        try:
            termos_radar = obter_termos_radar_audiencia_v88()
            if termos_radar:
                self._log.info(f"[v88][RADAR] {len(termos_radar)} termos auxiliares adicionados")
                termos_gnews = list(dict.fromkeys(list(termos_gnews) + list(termos_radar)))
        except Exception as e:
            self._log.info(f"[v88][RADAR] falha: {e}")
        self._log.info(f"Termos Google News: {len(termos_gnews)}")

        # v110 teste/v111: usa coletor integrado Google News quando a flag estiver ativa.
        # Fallback v110 permanece disponível por URURAU_V110_MONITOR_GNEWS_LEGADO=1.
        try:
            from ururau.publisher.monitor_v111_patch import injetar_gnews_v111_no_raw
            adicionadas_v111 = injetar_gnews_v111_no_raw(
                raw,
                logger=self._log,
                termos_legado=termos_gnews,
            )
            self._log.info(f"[V111][GNEWS] Injeção concluída: {adicionadas_v111} pauta(s)")
        except Exception as e:
            self._log.info(f"[V111][GNEWS] falha ignorada no monitor: {e}")

        # RSS legado do Google News só entra se solicitado de forma explícita.
        if str(os.getenv("URURAU_V111_GNEWS_INTEGRADO", "1")).lower() not in ("1", "true", "sim", "yes", "s") and str(os.getenv("URURAU_V108_GNEWS_TERMOS", "0")).lower() in ("1", "true", "sim", "yes", "s"):
            raw += coletar_google_news(termos_gnews, max_por_termo=8)
        try:
            premium = coletar_source_hunter_premium_v88()
            self._log.info(f"[v88][SOURCE_HUNTER] {len(premium)} pautas premium coletadas")
            raw += premium
        except Exception as e:
            self._log.info(f"[v88][SOURCE_HUNTER] falha: {e}")
        self._log.info(f"Brutas coletadas: {len(raw)}")

        # ── 2. Deduplicação e filtro contra banco ──────────────────────────────
        raw = deduplicar(raw)
        candidatas, resumo = filtrar_contra_banco(raw, self.db)
        self._log.info(
            f"Filtro banco: {resumo['total']} → {resumo['aprovadas']} novas | "
            f"{resumo['publicadas']} já pub | {resumo['descartadas']} descartadas | "
            f"{resumo['similares']} similares"
        )

        # V47.9: também processa conteúdo já existente na fila do painel.
        try:
            from ururau.publisher.monitor_capacidade_v47_9 import carregar_pautas_fila_para_monitor, mesclar_fila_com_candidatas
            fila_monitor = carregar_pautas_fila_para_monitor(self.db)
            if fila_monitor:
                antes_fila = len(candidatas)
                candidatas = mesclar_fila_com_candidatas(candidatas, fila_monitor)
                self._log.info(f"[V47.9][FILA] {len(fila_monitor)} pauta(s) da fila avaliadas; candidatas {antes_fila} → {len(candidatas)}")
        except Exception as e_fila_v47_9:
            self._log.info(f"[V47.9][FILA] indisponível/falhou: {e_fila_v47_9}")

        # ── 2b. Filtro anti-duplicata: verifica o que está no ar no Portal Ururau
        # Passa db= para que links encontrados no site sejam bloqueados permanentemente
        if candidatas:
            try:
                from ururau.coleta.ururau_check import filtrar_contra_site_ururau
                candidatas, rem_site = filtrar_contra_site_ururau(candidatas, db=self.db)
                if rem_site:
                    self._log.info(
                        f"Filtro Portal Ururau: {rem_site} pautas removidas "
                        f"(assunto já publicado no site — bloqueados permanentemente)"
                    )
            except Exception as e_site:
                self._log.warning(f"Filtro Portal Ururau falhou (continuando): {e_site}")

        if not candidatas:
            self._log.info("Nenhuma candidata nova neste ciclo.")
            return 0

        # ── 3. Scoring completo ────────────────────────────────────────────────
        # Monta contexto de fontes para penalidade de repetição
        contexto_fontes: dict[str, int] = {}
        for p in candidatas:
            nome = p.get("fonte_nome") or p.get("nome_fonte") or "desconhecida"
            contexto_fontes[nome] = contexto_fontes.get(nome, 0) + 1

        for pauta in candidatas:
            try:
                sd = calcular_score_completo(pauta, contexto_fontes)
                pauta["_score_detalhado"]  = sd
                pauta["score_editorial"]   = sd.score_editorial
                pauta["score_autopub"]     = sd.score_confianca_autopub
                pauta["modo_destino"]      = sd.modo_destino
                pauta["justificativa"]     = "; ".join(sd.motivos_rejeicao[:2]) if sd.motivos_rejeicao else ""
                # Guarda sub-scores para gate de relevância
                pauta["_sub_regional"]   = sd.score_regionalidade
                pauta["_sub_politico"]   = sd.score_impacto_politico
                pauta["_sub_policial"]   = sd.score_impacto_policial
                pauta["_sub_esportes"]   = sd.score_prioridade_esportes
                pauta["_sub_saude"]      = sd.score_prioridade_saude
                pauta["_sub_rural"]      = sd.score_prioridade_rural
                pauta["_sub_audiencia"]  = sd.score_potencial_audiencia
                # Canal v78: aplica classificador determinístico final para evitar
                # falsos positivos do feed/scoring (ex.: Congresso em Esportes, Irã em Saúde).
                try:
                    from ururau.editorial.fallback_local import classificar_canal_v78
                    _canal_v78 = classificar_canal_v78(
                        pauta.get("titulo_origem", ""),
                        (pauta.get("resumo_origem", "") or "") + " " + (pauta.get("texto_fonte", "") or ""),
                        sd.canal_sugerido,
                    )
                    if _canal_v78 and _canal_v78 != sd.canal_sugerido:
                        sd.motivos_aprovacao.append(f"Canal corrigido v78: {sd.canal_sugerido} → {_canal_v78}")
                        sd.canal_sugerido = _canal_v78
                        sd.canal_confianca = "alta"
                except Exception:
                    pass
                pauta["canal_forcado"]       = sd.canal_sugerido
                pauta["_confianca_canal"]    = sd.canal_confianca
            except Exception as ex:
                self._log.debug(f"Scoring falhou para pauta: {ex}")
                pauta["score_editorial"] = 0
                pauta["score_autopub"]   = 0
                pauta["modo_destino"]    = "rascunho"

        # ── 4. Filtragem e ordenação modo=monitor (score mínimo mais alto) ──────
        score_min_monitor = self.SCORE_MIN_MONITOR
        selecionadas = filtrar_e_ordenar(
            candidatas,
            score_minimo=score_min_monitor,
            max_por_canal=PESOS["max_por_canal"],
            modo="monitor",
            contexto_fontes=contexto_fontes,
        )
        self._log.info(
            f"Após filtro monitor (score≥{score_min_monitor}): "
            f"{len(selecionadas)} candidatas | total candidatas: {len(candidatas)}"
        )

        if not selecionadas:
            self._log.info(
                "Nenhuma pauta atingiu o critério mínimo do monitor. "
                "Aguardando próxima janela de busca."
            )
            return 0

        # ── 5. Processamento (respeitando limite/hora) ─────────────────────────
        wf = WorkflowPublicacao(self.db, self.client, self.modelo)
        processadas = 0

        for pauta in selecionadas:
            if self._parar.is_set():
                self._log.info("Parada solicitada durante processamento.")
                break

            vagas = self._vagas_na_hora()
            if vagas <= 0:
                self._log.info(
                    f"Limite {self.max_por_hora}/hora atingido. "
                    f"Aguardando próximo ciclo."
                )
                break

            titulo = (pauta.get("titulo_origem") or "")[:70]
            uid    = pauta.get("_uid") or _uid_para_pauta(
                pauta.get("link_origem", ""), pauta.get("titulo_origem", ""))
            pauta["_uid"] = uid

            score_ed    = pauta.get("score_editorial", 0)
            score_ap    = pauta.get("score_autopub", 0)
            canal       = pauta.get("canal_forcado", "?")
            confianca   = pauta.get("_confianca_canal", "?")
            justificativa = pauta.get("justificativa", "")

            # Sub-scores de relevância real
            sub_regional  = pauta.get("_sub_regional", 0)
            sub_politico  = pauta.get("_sub_politico", 0)
            sub_policial  = pauta.get("_sub_policial", 0)
            sub_esportes  = pauta.get("_sub_esportes", 0)
            sub_saude     = pauta.get("_sub_saude", 0)
            sub_rural     = pauta.get("_sub_rural", 0)
            sub_audiencia = pauta.get("_sub_audiencia", 0)

            # Intel editorial — sub-scores adicionais
            score_intel   = pauta.get("_score_intel_adicional", 0)
            intel_log     = pauta.get("_intel_log", "")
            intel_urgencia = bool(pauta.get("_intel_urgencia", False))
            intel_triang   = bool(pauta.get("_intel_triangulacao", False))
            intel_proto_ok = bool(pauta.get("_intel_protocolo_ok", True))

            # Relevância máxima entre todos os sub-scores específicos
            relevancia_max = max(
                sub_regional, sub_politico, sub_policial,
                sub_esportes, sub_saude, sub_rural, sub_audiencia,
                score_intel,  # intel conta como relevância também
            )

            self._log.info(
                f"\n  ▶ [{canal}] {titulo}\n"
                f"    Score: {score_ed} | Confiança: {score_ap} | "
                f"Canal conf: {confianca} | Relevância máx: {relevancia_max}\n"
                f"    Sub: regional={sub_regional} pol={sub_politico} "
                f"policial={sub_policial} esp={sub_esportes} "
                f"saude={sub_saude} rural={sub_rural} aud={sub_audiencia}\n"
                f"    Intel: +{score_intel} | urgencia={intel_urgencia} "
                f"triang={intel_triang} proto_ok={intel_proto_ok}"
                + (f"\n    Intel detalhe: {intel_log}" if intel_log else "")
            )

            # ── Gate 0: Protocolo de verdade — bloqueia autopub se falhou ─────
            pauta["_forcar_rascunho_v82"] = False
            pauta["_motivos_rascunho_v82"] = []

            if not intel_proto_ok:
                pauta["_forcar_rascunho_v82"] = True
                pauta["_motivos_rascunho_v82"].append("protocolo de verdade exige revisão")
                self._log.info(
                    f"    ⚠ DIRETA BLOQUEADA — Protocolo de verdade falhou: revisar cargo/fato.\n"
                    f"      → v82: será enviada ao painel do Ururau como RASCUNHO."
                )

            # ── Gate 1 v78: relevância flexível ──────────────────────────
            # Antes o monitor travava pautas boas quando relevancia_max < 5,
            # mesmo com score editorial alto. Agora publica se houver score muito
            # forte OU relevância específica suficiente. Isso evita score_autopub=0
            # por excesso de rigidez.
            if relevancia_max < self.RELEVANCIA_MIN_MONITOR and score_ed < SCORE_MONITOR_DIRETO_CONFIANCA:
                pauta["_forcar_rascunho_v82"] = True
                pauta["_motivos_rascunho_v82"].append(
                    f"relevância real {relevancia_max} abaixo do mínimo {self.RELEVANCIA_MIN_MONITOR}"
                )
                self._log.info(
                    f"    ⚠ DIRETA BLOQUEADA — relevância real {relevancia_max} < "
                    f"{self.RELEVANCIA_MIN_MONITOR} e score {score_ed} < "
                    f"{SCORE_MONITOR_DIRETO_CONFIANCA}.\n"
                    f"      → v82: será enviada ao painel do Ururau como RASCUNHO."
                )
            elif relevancia_max < self.RELEVANCIA_MIN_MONITOR:
                self._log.info(
                    f"    ✓ PRÉ-LIBERADA v78 — score editorial alto ({score_ed}) "
                    f"compensou relevância específica baixa ({relevancia_max})."
                )

            # ── Gate 2: confiança na classificação do canal ────────────────────
            confianca_min = PESOS["confianca_min_autopub"]
            if score_ap < confianca_min:
                pauta["_forcar_rascunho_v82"] = True
                pauta["_motivos_rascunho_v82"].append(
                    f"confiança autopub {score_ap} abaixo de {confianca_min}"
                )
                self._log.info(
                    f"    ⚠ DIRETA BLOQUEADA — confiança autopub {score_ap} < {confianca_min}.\n"
                    f"      Motivo: {justificativa or 'score insuficiente'}\n"
                    f"      → v82: será enviada ao painel do Ururau como RASCUNHO."
                )

            # ── Gate 3: canal com confiança mínima ────────────────────────────
            if confianca == "baixa":
                pauta["_forcar_rascunho_v82"] = True
                pauta["_motivos_rascunho_v82"].append(f"canal com baixa confiança: {canal}")
                self._log.info(
                    f"    ⚠ DIRETA BLOQUEADA — canal classificado com baixa confiança: {canal}.\n"
                    f"      Monitor exige confiança média ou alta para publicação direta.\n"
                    f"      → v82: será enviada ao painel do Ururau como RASCUNHO."
                )

            # ── Tier de publicação expandido (v43) ────────────────────────────
            # 90+: publicação direta e imediata (tier 1)
            # 80-89: direta se confiança canal=alta (tier 2)
            # 65-79: vai para painel como prioridade (tier 3)
            # <65: fila normal de painel (já filtrado pelo score_min_monitor acima)
            tier_pub = "direto"
            if score_ed >= SCORE_MONITOR_DIRETO_IMEDIATO:
                tier_pub = "direto_imediato"
            elif score_ed >= SCORE_MONITOR_DIRETO_CONFIANCA:
                tier_pub = "direto" if confianca == "alta" else "painel_prioridade"
            elif score_ed >= SCORE_MONITOR_PAINEL_PRIORIDADE:
                tier_pub = "painel_prioridade"
            else:
                tier_pub = "fila_normal"

            pauta["_tier_publicacao"] = tier_pub
            pauta["_intel_urgencia"]  = intel_urgencia
            pauta["_intel_triang"]    = intel_triang

            if pauta.get("_forcar_rascunho_v82"):
                self._log.info(
                    f"    → v82 RASCUNHO APROVADO PARA REVISÃO — score={score_ed} confiança={score_ap} "
                    f"relevância={relevancia_max} canal={canal} ({confianca}) "
                    f"motivos={'; '.join(pauta.get('_motivos_rascunho_v82', [])[:3])}"
                )
            else:
                self._log.info(
                    f"    ✓ PRÉ-APROVADA PARA DIRETA — score={score_ed} confiança={score_ap} "
                    f"relevância={relevancia_max} canal={canal} ({confianca}) "
                    f"tier={tier_pub}; falta texto completo, imagem, copydesk, risco e CMS"
                    + (" ⚡URGENTE" if intel_urgencia else "")
                    + (" ★TRIANGULAÇÃO" if intel_triang else "")
                )

            try:
                resultado = self._processar_pauta(wf, uid, pauta)
                if isinstance(resultado, dict):
                    status_pipeline = resultado.get("status_pipeline") or resultado.get("status") or ""
                    if status_pipeline == "publicado":
                        self._registrar_publicacao()
                        processadas += 1
                        self._log.info(
                            f"    [CMS OK] Publicado ao vivo: {titulo}\n"
                            f"             Canal: {canal} | Score: {score_ed} | "
                            f"Relevância: {relevancia_max}"
                        )
                    elif status_pipeline in {"rascunho_cms", "rascunho_local"}:
                        processadas += 1
                        self._log.info(
                            f"    [RASCUNHO] Matéria cadastrada/persistida para revisão: {titulo}\n"
                            f"             AVISO: não foi aprovada para publicação direta; aguarda revisão humana."
                        )
                    elif status_pipeline == "bloqueado_coleta":
                        self._log.info(
                            f"    [COLETA BLOQUEADA v83] Matéria não capturou texto útil e não será cadastrada: {titulo}\n"
                            f"             Motivo: {resultado.get('erro', '')}\n"
                            f"             Regra: sem texto da matéria, não há geração, rascunho nem publicação."
                        )
                    elif status_pipeline == "bloqueado_local":
                        self._log.info(
                            f"    [BLOQUEADA] Não enviada nem como rascunho: {titulo}\n"
                            f"             Motivo: {resultado.get('erro', '')}"
                        )
                    else:
                        self._log.info(f"    [--] Pipeline falhou: {titulo}")
                        self._log.info("        Verifique logs/monitor.log, logs/painel_inicializacao.log e prints/debug_*.png para o motivo detalhado.")
                elif resultado:
                    self._registrar_publicacao()
                    processadas += 1
                    self._log.info(
                        f"    [CMS OK] Publicado ao vivo: {titulo}\n"
                        f"             Canal: {canal} | Score: {score_ed} | "
                        f"Relevância: {relevancia_max}"
                    )
                else:
                    self._log.info(f"    [--] Pipeline falhou: {titulo}")
                    self._log.info("        Verifique logs/monitor.log, logs/painel_inicializacao.log e prints/debug_*.png para o motivo detalhado.")
            except Exception as e:
                self._log.warning(
                    f"    [ERR] Erro ao processar '{titulo}': {e}",
                    exc_info=False,
                )

        self._log.info(
            f"Ciclo {ciclo} concluído. "
            f"Processadas/cadastradas: {processadas} | "
            f"Publicadas ao vivo na última hora: {self.publicacoes_na_hora}/{self.max_por_hora}"
        )
        return processadas

    # ── Processamento individual ───────────────────────────────────────────────

    def _processar_pauta(self, wf, uid: str, pauta: dict) -> bool:
        """
        Pipeline completo para uma pauta do monitor 24h.

        A decisão final respeita self.modo_cms:
          local    → não envia ao CMS;
          rascunho → envia ao CMS como rascunho;
          direto   → permite publicação ao vivo apenas após gates completos.
        """
        # Gate anti-duplicação
        if not wf.etapa_gate_antiduplicacao(uid, pauta, modo="redigir"):
            self._log.debug(f"  Gate antiduplicação bloqueou: {uid}")
            return False

        # Triagem de risco/qualidade
        if not wf.etapa_triagem(uid, pauta):
            self._log.debug(f"  Triagem bloqueou: {uid}")
            return False

        # v83: NÃO salvar como CAPTADA antes de confirmar que o texto da matéria foi capturado.
        # Pauta sem texto útil não entra na fila do robô, não vira rascunho CMS e não gera matéria.
        modo_coleta_v47_16 = "monitor" if self.permitir_publicacao_direta else "panel"
        self._log.info(f"  [V47.16] Coleta textual em modo={modo_coleta_v47_16} para destino={self.modo_cms}")
        if not wf.etapa_coleta_texto(uid, pauta, modo=modo_coleta_v47_16):
            motivo = pauta.get("motivo_bloqueio_coleta_v83") or "extração falhou"
            print(f"[MONITOR] [{uid[:8]}] Coleta falhou - pauta barrada antes de captação (FAIL-CLOSED v83): {motivo}")
            try:
                wf.db.log_auditoria(uid, "monitor_fail_closed_v83",
                                    "Coleta de texto falhou; pauta não captada: " + str(motivo),
                                    sucesso=False)
            except Exception:
                pass
            try:
                from ururau.coleta.auto_reparo_fontes_v47_9 import agendar_diagnostico_fonte
                if agendar_diagnostico_fonte(pauta, motivo=str(motivo), logger=self._log):
                    self._log.info("    [V47.9][AUTO-DIAG] Diagnóstico de fonte agendado; próxima coleta tentará a estratégia corrigida.")
            except Exception as _e_diag_v47_9:
                self._log.info(f"    [V47.9][AUTO-DIAG] não agendado: {_e_diag_v47_9}")
            try:
                if os.getenv("URURAU_BLOQUEAR_LINK_SEM_TEXTO", "0").lower() in ("1", "true", "sim", "yes", "s"):
                    wf.db.bloquear_link(
                        pauta.get("link_origem", ""), uid, pauta.get("titulo_origem", ""),
                        motivo="coleta_texto_fail_closed_v83",
                    )
            except Exception:
                pass
            return {
                "ok": False,
                "status_pipeline": "bloqueado_coleta",
                "erro": motivo,
                "publicado": False,
                "rascunho": False,
            }

        # Só agora a pauta é considerada captada pelo robô.
        pauta["status"] = 'captada'
        try:
            self.db.salvar_pauta(pauta)
        except Exception:
            pass

        # Imagem
        imagem = wf.etapa_imagem(uid, pauta)

        # Redação pela IA
        materia = wf.etapa_redacao(uid, pauta)
        if not materia:
            self._log.debug(f"  Redação falhou: {uid}")
            return False

        # Pacote editorial (título, subtítulo, tags…)
        materia = wf.etapa_pacote_editorial(uid, materia, pauta)

        # v102/v103: antes de qualquer publicação direta, passa obrigatoriamente
        # no Copydesk IA com fonte integral e no gate final de qualidade.
        materia = wf.etapa_copydesk_automatico_v102(uid, pauta, materia, modo="monitor")
        wf.etapa_gate_qualidade_final_v103(uid, pauta, materia, imagem)

        # Verificação de risco editorial
        if not wf.etapa_verificacao_risco(uid, pauta, materia):
            self._log.debug(f"  Risco bloqueante detectado: {uid}")
            return False

        # Persistência local
        if not wf.etapa_persistir_materia(uid, pauta, materia):
            self._log.debug(f"  Persistência falhou: {uid}")
            return False

        self._log.info(
            f"  Matéria: {materia.titulo[:60]}\n"
            f"  Canal: {materia.canal} | Risco: {materia.score_risco}/100"
        )

        # v82: decide entre publicação direta, rascunho real no painel ou bloqueio total.
        try:
            from ururau.editorial.decision_v82 import (
                decidir_destino_publicacao_v82,
                aplicar_aviso_rascunho_v82,
            )
            auditoria = getattr(materia, "auditoria_factual_v81", {}) or {}
            contexto = {
                "chars_fonte": len(pauta.get("cleaned_source_text") or pauta.get("dossie") or pauta.get("texto_fonte") or ""),
                "extraction_status": pauta.get("extraction_status", ""),
                "link_origem": pauta.get("link_origem", ""),
                "fonte_nome": pauta.get("fonte_nome", ""),
                "score_risco": getattr(materia, "score_risco", 0),
                "modo_cms": self.modo_cms,
                "permitir_publicacao_direta": self.permitir_publicacao_direta,
            }
            decisao = decidir_destino_publicacao_v82(materia, auditoria, contexto)

            # Segurança v47.3: modo rascunho/local nunca deixa uma decisão virar publicação ao vivo,
            # mesmo se alguma variável de ambiente antiga estiver habilitada por engano.
            if not self.permitir_publicacao_direta and decisao.get("destino") == "publicar_direto":
                decisao = {
                    "destino": "salvar_rascunho",
                    "pode_enviar_cms": bool(self.publicar_no_cms),
                    "rascunho": True,
                    "motivos": [f"modo do monitor é {self.modo_cms}; publicação ao vivo bloqueada"],
                    "aviso": "AVISO: O monitor 24h está configurado para rascunho/local. A publicação ao vivo foi bloqueada.",
                }

            # Gates de triagem do monitor podem forçar rascunho mesmo quando a redação saiu aprovada.
            if pauta.get("_forcar_rascunho_v82") and decisao.get("destino") == "publicar_direto":
                decisao = {
                    "destino": "salvar_rascunho",
                    "pode_enviar_cms": True,
                    "rascunho": True,
                    "motivos": pauta.get("_motivos_rascunho_v82") or ["triagem do monitor exige revisão"],
                    "aviso": "AVISO: Esta matéria não foi aprovada para publicação direta. Foi enviada ao CMS do Ururau como rascunho para revisão humana.",
                }

            self._log.info(
                f"  [v82] Decisão: destino={decisao.get('destino')} "
                f"rascunho={decisao.get('rascunho')} motivos={'; '.join(decisao.get('motivos', [])[:3])}"
            )
        except Exception as e:
            self._log.warning(f"  [v82] Falha na decisão de publicação: {e}")
            return {"ok": False, "status_pipeline": "bloqueado_local", "erro": f"falha na decisão v82: {e}"}

        if decisao.get("destino") == "bloquear_total":
            erro = "Bloqueada até para rascunho: " + "; ".join(decisao.get("motivos", [])[:4])
            self._log.warning(f"  [v82] {erro}")
            return {"ok": False, "status_pipeline": "bloqueado_local", "erro": erro}

        if decisao.get("destino") == "salvar_rascunho":
            materia = aplicar_aviso_rascunho_v82(materia, decisao.get("aviso"))
            self._log.info("  [v82][CMS] Enviando como RASCUNHO no painel do Ururau.")
            self._log.info("  [v82][CMS] Checkbox de rascunho deve ficar marcada: Não publicar a notícia agora.")
            if self.publicar_no_cms:
                sucesso_cms = wf.etapa_publicacao(uid, pauta, materia, imagem, rascunho=True)
                if sucesso_cms:
                    self._log.info("  [v82][CMS] Rascunho salvo no site Ururau para revisão humana [OK]")
                    return {"ok": True, "status_pipeline": "rascunho_cms", "publicado": False, "rascunho": True}
                self._log.warning("  [v82][CMS] Falha ao salvar rascunho no painel; salvando spool local operacional.")
                try:
                    from ururau.publisher.rascunho_spool_v47_16 import salvar_rascunho_spool
                    arq_spool = salvar_rascunho_spool(uid, pauta, materia, imagem, motivo="falha ao salvar rascunho no CMS")
                    self._log.info(f"  [V47.16][SPOOL] Rascunho salvo localmente para revisão: {arq_spool}")
                    return {"ok": True, "status_pipeline": "rascunho_spool_local", "erro": "CMS falhou; rascunho salvo em spool local", "spool": arq_spool, "publicado": False, "rascunho": True}
                except Exception as _e_spool:
                    self._log.warning(f"  [V47.16][SPOOL] Falhou também: {_e_spool}")
                try:
                    from ururau.publisher.rascunho_spool_v47_16 import salvar_rascunho_spool
                    arq_spool = salvar_rascunho_spool(uid, pauta, materia, imagem, motivo="falha ao salvar rascunho no CMS")
                    self._log.info(f"  [V47.16][SPOOL] Rascunho salvo localmente para revisão: {arq_spool}")
                    return {"ok": True, "status_pipeline": "rascunho_spool_local", "erro": "CMS falhou; rascunho salvo em spool local", "spool": arq_spool, "publicado": False, "rascunho": True}
                except Exception:
                    pass
                return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha ao salvar rascunho no CMS"}
            return {"ok": True, "status_pipeline": "rascunho_local", "publicado": False, "rascunho": True}

        # Publicação direta no CMS. Só chega aqui se o modo direto foi explicitamente permitido.
        if not self.permitir_publicacao_direta:
            self._log.info("  [v47.3] Publicação ao vivo bloqueada pelo modo do monitor; convertendo para rascunho/local.")
            if self.publicar_no_cms:
                materia = aplicar_aviso_rascunho_v82(materia, "AVISO: publicação ao vivo bloqueada pelo modo do monitor; salvo como rascunho para revisão humana.")
                sucesso_cms = wf.etapa_publicacao(uid, pauta, materia, imagem, rascunho=True)
                if sucesso_cms:
                    return {"ok": True, "status_pipeline": "rascunho_cms", "publicado": False, "rascunho": True}
                try:
                    from ururau.publisher.rascunho_spool_v47_16 import salvar_rascunho_spool
                    arq_spool = salvar_rascunho_spool(uid, pauta, materia, imagem, motivo="falha ao salvar rascunho no CMS")
                    self._log.info(f"  [V47.16][SPOOL] Rascunho salvo localmente para revisão: {arq_spool}")
                    return {"ok": True, "status_pipeline": "rascunho_spool_local", "erro": "CMS falhou; rascunho salvo em spool local", "spool": arq_spool, "publicado": False, "rascunho": True}
                except Exception:
                    pass
                return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha ao salvar rascunho no CMS"}
            return {"ok": True, "status_pipeline": "rascunho_local", "publicado": False, "rascunho": True}

        # Publicação direta no CMS.
        if self.publicar_no_cms:
            sucesso_cms = wf.etapa_publicacao(uid, pauta, materia, imagem, rascunho=False)
            if sucesso_cms:
                self._log.info("  [v82][CMS] Publicado ao vivo [OK]")
                return {"ok": True, "status_pipeline": "publicado", "publicado": True, "rascunho": False}
            self._log.warning(
                "  [v82][CMS] Falha na publicação direta. Tentando salvar como rascunho no painel."
            )
            if self.RASCUNHO_SE_NAO_APROVAR:
                materia = aplicar_aviso_rascunho_v82(materia)
                sucesso_rasc = wf.etapa_publicacao(uid, pauta, materia, imagem, rascunho=True)
                if sucesso_rasc:
                    self._log.info("  [v82][CMS] Direta falhou, mas rascunho foi salvo no painel [OK]")
                    return {"ok": True, "status_pipeline": "rascunho_cms", "publicado": False, "rascunho": True}
            return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha na publicação direta e no rascunho"}

        return {"ok": True, "status_pipeline": "local_sem_cms", "publicado": False}

    # ── Rate limiting ──────────────────────────────────────────────────────────

    def _vagas_na_hora(self) -> int:
        """Retorna quantas publicações ainda cabem na janela de 1 hora."""
        agora  = datetime.now()
        janela = agora - timedelta(hours=1)
        self._publicados_hora = [t for t in self._publicados_hora if t > janela]
        return self.max_por_hora - len(self._publicados_hora)

    def _registrar_publicacao(self):
        """Registra timestamp da publicação para controle de rate limit."""
        self._publicados_hora.append(datetime.now())

    # ── Estado público ─────────────────────────────────────────────────────────

    @property
    def publicacoes_na_hora(self) -> int:
        """Número de publicações feitas na última hora."""
        agora  = datetime.now()
        janela = agora - timedelta(hours=1)
        return sum(1 for t in self._publicados_hora if t > janela)

    @property
    def ativo(self) -> bool:
        return not self._parar.is_set()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _carregar_fontes_rss() -> list[dict]:
    # V47.7: carrega todas as configurações conhecidas, não apenas o primeiro arquivo encontrado.
    try:
        from ururau.coleta.config_unificada import carregar_fontes_rss_unificadas
        fontes = carregar_fontes_rss_unificadas()
        if fontes:
            return fontes
    except Exception as e:
        try:
            print(f"[V47.7][RSS] config unificada indisponível: {e}")
        except Exception:
            pass
    return [
        {"url": "https://g1.globo.com/rss/g1/rio-de-janeiro/",
         "nome": "G1 RJ", "canal_forcado": "Estado RJ", "tipo_coleta": "rss"},
        {"url": "https://www.cnnbrasil.com.br/rss/",
         "nome": "CNN Brasil", "canal_forcado": "", "tipo_coleta": "rss"},
        {"url": "https://feeds.folha.uol.com.br/poder/rss091.xml",
         "nome": "Folha Poder", "canal_forcado": "Política", "tipo_coleta": "rss"},
        {"url": "https://www.uol.com.br/esporte/rss.xml",
         "nome": "UOL Esportes", "canal_forcado": "Esportes", "tipo_coleta": "rss"},
    ]


def coletar_google_news(termos: list[str], max_por_termo: int = 8) -> list[dict]:
    """Wrapper local para evitar importação circular."""
    from ururau.coleta.rss import coletar_google_news as _cgn
    return _cgn(termos, max_por_termo)


# PATCH_V47_14_MONITOR_ENV
try:
    from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers as _v4714_defaults
    _v4714_defaults(globals().get('logger'), forcar=True)
except Exception:
    pass


# PATCH_V47_16_MONITOR_RASCUNHO
try:
    import os as _os_v4716
    _os_v4716.environ.setdefault('URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL', '1')
    _os_v4716.environ.setdefault('URURAU_V104_MIN_CHARS_ARTIGO', '350')
    _os_v4716.environ.setdefault('URURAU_V105_MIN_CHARS_FONTE_OK', '350')
    _os_v4716.environ.setdefault('URURAU_MIN_CHARS_FONTE_MONITOR', '350')
except Exception:
    pass


# PATCH_V47_17_REAL_ENV
try:
    import os as _os_v4717
    _os_v4717.environ.setdefault('URURAU_V110_KIMI_TIMEOUT_SEG','25')
    _os_v4717.environ.setdefault('URURAU_V111_TIMEOUT_SEG','35')
    _os_v4717.environ.setdefault('URURAU_SOURCE_HUNTER_TIMEOUT_SEG','20')
    _os_v4717.environ.setdefault('URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL','1')
except Exception:
    pass


# PATCH_V47_22_STOP_GUARD
try:
    from ururau.publisher.monitor_stop_v47_22 import instalar_stop_guard as _v4722_install_stop
    _v4722_install_stop(MonitorRobo)
except Exception as _e_v4722_stop:
    try:
        logger.info(f'[V47.22][STOP] guard não aplicado: {_e_v4722_stop}')
    except Exception:
        pass


# PATCH_V47_23_STOP_GUARD
try:
    from ururau.publisher.monitor_stop_v47_23 import instalar_stop_guard as _v4723_stop
    _v4723_stop(MonitorRobo)
except Exception as _e:
    try: logger.info(f'[V47.23][STOP] guard nao aplicado: {_e}')
    except Exception: pass
