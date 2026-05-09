from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime
import json
import os
import re
import socket
import urllib.request
from urllib.parse import urlparse


def _env_bool(nome: str, padrao: str = "1") -> bool:
    return str(os.getenv(nome, padrao)).strip().lower() in {"1", "true", "sim", "yes", "s", "on"}


def _diag_http_basico_v128(url: str, timeout: int = 8) -> dict:
    """Diagnóstico leve de link/fonte. Não interfere na coleta; só tenta explicar falha."""
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return {}
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
                "Range": "bytes=0-4095",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            ctype = resp.headers.get("Content-Type", "")
            clen = resp.headers.get("Content-Length", "")
            sample = resp.read(4096) or b""
            txt = sample[:600].decode("utf-8", errors="ignore").lower()
            kind = "DESCONHECIDO"
            if "<rss" in txt or "<feed" in txt or "</channel>" in txt:
                kind = "FEED_RSS_ATOM"
            elif "<urlset" in txt or "<sitemapindex" in txt:
                kind = "SITEMAP_XML"
            elif "<html" in txt or "<!doctype html" in txt:
                kind = "HTML"
            elif "json" in ctype.lower():
                kind = "JSON"
            return {
                "status_http": int(status) if status is not None else "",
                "content_type": ctype,
                "content_length": clen,
                "tipo_conteudo_detectado": kind,
                "amostra_bytes": len(sample),
                "erro_http": "",
            }
    except Exception as exc:
        return {
            "status_http": "",
            "content_type": "",
            "content_length": "",
            "tipo_conteudo_detectado": "ERRO",
            "amostra_bytes": 0,
            "erro_http": f"{type(exc).__name__}: {exc}",
        }


@dataclass
class RegistroFonteV126:
    ordem: int
    nome: str
    url: str
    tipo: str
    encontradas: int = 0
    enviadas_fila: int = 0
    erro: str = ""
    observacao: str = ""
    status: str = "pendente"
    diagnostico: dict = field(default_factory=dict)


class AuditoriaColetaV126:
    def __init__(self, lote_label: str = ""):
        self.lote_label = lote_label or datetime.now().strftime("Coleta - %H:%M")
        self.inicio_iso = datetime.now().isoformat(timespec="seconds")
        self.registros: list[RegistroFonteV126] = []
        self.versao_diagnostico = "v129-linha-editorial-especial"

    def registrar(self, *, ordem: int = 0, nome: str, url: str = "", tipo: str = "rss",
                  encontradas: int = 0, enviadas_fila: int = 0, erro: str = "",
                  observacao: str = "", diagnostico: dict | None = None, **metricas) -> None:
        encontradas = int(encontradas or 0)
        enviadas_fila = int(enviadas_fila or 0)
        erro = (erro or "").strip()
        observacao = (observacao or "").strip()
        diagnostico = dict(diagnostico or {})
        diagnostico.update({k: v for k, v in metricas.items() if v is not None})

        if erro:
            status = "falha_fluxo"
        elif encontradas <= 0:
            status = "sem_coleta"
        elif enviadas_fila <= 0:
            status = "sem_envio_fila"
        else:
            status = "ok"

        # v128: diagnóstico HTTP/content-type para link de fonte, sem alterar a coleta.
        if _env_bool("URURAU_V128_DIAG_HTTP", "1") and str(url or "").lower().startswith(("http://", "https://")):
            try:
                diagnostico.setdefault("http_basico_v128", _diag_http_basico_v128(url, timeout=int(os.getenv("URURAU_V128_DIAG_HTTP_TIMEOUT", "8") or 8)))
            except Exception as exc:
                diagnostico.setdefault("http_basico_v128", {"erro_http": f"{type(exc).__name__}: {exc}"})

        diagnostico.setdefault("motivo_principal_v128", self._motivo_principal_v128(
            status=status,
            encontradas=encontradas,
            enviadas_fila=enviadas_fila,
            erro=erro,
            observacao=observacao,
            diagnostico=diagnostico,
        ))

        self.registros.append(RegistroFonteV126(
            ordem=int(ordem or len(self.registros) + 1),
            nome=(nome or url or "Fonte").strip(),
            url=(url or "").strip(),
            tipo=(tipo or "rss").strip(),
            encontradas=encontradas,
            enviadas_fila=enviadas_fila,
            erro=erro,
            observacao=observacao,
            status=status,
            diagnostico=diagnostico,
        ))

    def _emoji(self, status: str) -> str:
        return {
            "ok": "OK",
            "sem_envio_fila": "SEM ENVIO",
            "sem_coleta": "SEM COLETA",
            "falha_fluxo": "FALHA",
            "pendente": "PENDENTE",
        }.get(status, status.upper())

    def _motivo_principal_v128(self, *, status: str, encontradas: int, enviadas_fila: int,
                               erro: str, observacao: str, diagnostico: dict) -> str:
        if erro:
            return f"falha_fluxo: {erro}"
        http = diagnostico.get("http_basico_v128") or {}
        if http.get("erro_http") and encontradas <= 0:
            return f"erro_http: {http.get('erro_http')}"
        if http.get("status_http") and str(http.get("status_http")) not in {"200", "206"} and encontradas <= 0:
            return f"HTTP {http.get('status_http')}"
        if encontradas <= 0:
            kind = http.get("tipo_conteudo_detectado") or diagnostico.get("tipo_conteudo_detectado") or ""
            if kind == "HTML":
                return "feed retornou HTML ou página sem entradas RSS úteis"
            return "feed/coletor retornou 0 itens úteis"

        # Ordem de decisão para explicar SEM ENVIO.
        keys = [
            ("ja_na_fila", "todos ou maioria já estava na fila"),
            ("publicadas", "itens já publicados no banco local"),
            ("similares_site", "itens já publicados/similares no Ururau"),
            ("fora_janela", "itens fora da janela de publicação"),
            ("descartadas_ruido", "itens descartados por ruído editorial"),
            ("score_baixo", "itens abaixo do score mínimo"),
            ("baixo_score_review", "amostra enviada para Baixo score para avaliação"),
            ("limite_por_fonte", "limite por fonte atingido"),
            ("url_imagem_ou_asset", "links eram imagens/assets, não notícias"),
            ("falhas_salvar", "falha ao salvar na fila"),
        ]
        if enviadas_fila <= 0:
            maior = None
            for k, msg in keys:
                try:
                    v = int(diagnostico.get(k) or 0)
                except Exception:
                    v = 0
                if v > 0 and (maior is None or v > maior[0]):
                    maior = (v, msg)
            if maior:
                return maior[1]
            return observacao or "encontrou itens, mas nenhum passou pelos filtros finais"
        return "enviou matéria(s) para a fila"

    def registros_problematicos(self) -> list[RegistroFonteV126]:
        return [r for r in self.registros if r.status in {"sem_coleta", "falha_fluxo", "sem_envio_fila"}]

    def _compactar(self, valor, limite: int = 150) -> str:
        txt = re.sub(r"\s+", " ", str(valor or "")).strip()
        return txt[:limite]

    def _linha_metricas_v128(self, r: RegistroFonteV126) -> list[str]:
        d = r.diagnostico or {}
        http = d.get("http_basico_v128") or {}
        linhas = []
        linhas.append(f"    URL: {r.url or '-'}")
        linhas.append(f"    Tipo detectado/configurado: {r.tipo}")
        if http:
            linhas.append(
                "    HTTP: "
                f"status={http.get('status_http','-')} | content-type={self._compactar(http.get('content_type','-'), 90)} | "
                f"kind={http.get('tipo_conteudo_detectado','-')} | erro={self._compactar(http.get('erro_http',''), 120) or '-'}"
            )
        linhas.append(
            "    Funil: "
            f"brutas={d.get('brutas', r.encontradas)} | "
            f"dedup_local={d.get('apos_deduplicacao_local', '-')} | "
            f"duplicadas_lote={d.get('duplicadas_no_lote', '-')} | "
            f"ja_na_fila={d.get('ja_na_fila', '-')} | "
            f"publicadas={d.get('publicadas', '-')} | "
            f"similares_site={d.get('similares_site', '-')} | "
            f"fora_janela={d.get('fora_janela', '-')} | "
            f"ruido={d.get('descartadas_ruido', '-')} | "
            f"score_baixo={d.get('score_baixo', '-')} | "
            f"bypass_score={d.get('bypass_score', '-')} | "
            f"baixo_score_review={d.get('baixo_score_review', '-')} | "
            f"limite_fonte={d.get('limite_por_fonte', '-')} | "
            f"enviadas={r.enviadas_fila}"
        )
        if d.get("primeira_materia_encontrada"):
            linhas.append(f"    Primeira encontrada: {self._compactar(d.get('primeira_materia_encontrada'), 160)}")
        if d.get("primeira_materia_enviada"):
            linhas.append(f"    Primeira enviada: {self._compactar(d.get('primeira_materia_enviada'), 160)}")
        linhas.append(f"    Motivo principal: {self._compactar(d.get('motivo_principal_v128') or r.erro or r.observacao, 220)}")

        campos = d.get("campos24_detalhe") or {}
        if campos:
            linhas.append("    Campos 24 Horas detalhado:")
            for item in (campos.get("feeds") or [])[:20]:
                linhas.append(f"      RSS: {item.get('url')} | status={item.get('status_http','-')} | itens={item.get('itens', 0)} | erro={self._compactar(item.get('erro',''), 90) or '-'}")
            for item in (campos.get("html") or [])[:20]:
                linhas.append(f"      HTML: {item.get('url')} | status={item.get('status_http','-')} | links={item.get('links', 0)} | erro={self._compactar(item.get('erro',''), 90) or '-'}")
            linhas.append(f"      Total final coletor especial: {campos.get('total_final', '-')}")

        manchete = d.get("mancheterj_detalhe_v12913") or {}
        if manchete:
            linhas.append("    Manchete RJ detalhado v129.13:")
            linhas.append(f"      estratégia usada={manchete.get('estrategia_usada','-')} | total_final={manchete.get('total_final','-')}")
            for item in (manchete.get("feeds") or [])[:10]:
                linhas.append(
                    f"      RSS: {item.get('url')} | status={item.get('status','-')} | entradas={item.get('entradas', 0)} | "
                    f"aceitas_janela={item.get('aceitas_janela', 0)} | fallback_fora_janela={item.get('fallback_fora_janela', 0)} | "
                    f"erro={self._compactar(item.get('erro',''), 90) or '-'}"
                )
            wp = manchete.get("wp_api") or {}
            if wp:
                linhas.append(
                    f"      WP API: {wp.get('url')} | status={wp.get('status','-')} | http={wp.get('status_http','-')} | "
                    f"itens={wp.get('itens', 0)} | aceitas_janela={wp.get('aceitas_janela', 0)} | "
                    f"fallback_fora_janela={wp.get('fallback_fora_janela', 0)} | erro={self._compactar(wp.get('erro',''), 90) or '-'}"
                )
            for item in (manchete.get("sitemaps") or [])[:10]:
                linhas.append(
                    f"      Sitemap: {item.get('url')} | status={item.get('status','-')} | http={item.get('status_http','-')} | "
                    f"urls={item.get('urls', 0)} | artigos={item.get('artigos_candidatos', 0)} | erro={self._compactar(item.get('erro',''), 90) or '-'}"
                )
            for item in (manchete.get("html") or [])[:10]:
                linhas.append(
                    f"      HTML: {item.get('url')} | status={item.get('status','-')} | http={item.get('status_http','-')} | "
                    f"links={item.get('links', 0)} | artigos={item.get('artigos_candidatos', 0)} | erro={self._compactar(item.get('erro',''), 90) or '-'}"
                )

        sitemap = d.get("sitemap_detalhe") or {}
        if sitemap:
            linhas.append("    XML/Sitemap detalhado:")
            for item in (sitemap.get("sitemaps") or [])[:20]:
                linhas.append(f"      {item.get('url')} | itens={item.get('itens', 0)} | erro={self._compactar(item.get('erro',''), 90) or '-'}")

        termos = d.get("termos_detalhe") or {}
        if termos:
            linhas.append("    Busca por Termos detalhada:")
            linhas.append(f"      janela={termos.get('janela_horas','-')}h | termos={termos.get('total_termos','-')} | candidatos={termos.get('total_candidatos','-')}")
            for item in (termos.get("termos") or [])[:60]:
                desc = item.get("descartes") or {}
                linhas.append(
                    f"      termo='{item.get('termo')}' | resultados={item.get('resultados_brutos', 0)} | "
                    f"candidatos={item.get('candidatos_gerados', 0)} | descartes={desc} | url={item.get('url_google_news_rss')}"
                )
        return linhas

    def resumo_texto(self, limite: int = 120) -> str:
        total = len(self.registros)
        ok = len([r for r in self.registros if r.status == "ok"])
        sem_coleta = len([r for r in self.registros if r.status == "sem_coleta"])
        sem_envio = len([r for r in self.registros if r.status == "sem_envio_fila"])
        falha = len([r for r in self.registros if r.status == "falha_fluxo"])

        linhas = []
        linhas.append(f"{self.lote_label} | Diagnóstico técnico v129 | Fontes auditadas: {total} | OK: {ok} | Sem coleta: {sem_coleta} | Sem envio: {sem_envio} | Falha: {falha}")
        linhas.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Início da coleta: {self.inicio_iso}")
        linhas.append("")

        problemas = self.registros_problematicos()
        if problemas:
            linhas.append("PORTAIS/ETAPAS QUE NÃO ENVIARAM MATÉRIA NOVA PARA A FILA")
            linhas.append("-" * 92)
            for r in problemas[:limite]:
                motivo = (r.diagnostico or {}).get("motivo_principal_v128") or r.erro or r.observacao or ("sem entradas" if r.encontradas <= 0 else "encontrou, mas não entrou na fila")
                motivo = re.sub(r"\s+", " ", str(motivo)).strip()
                linhas.append(f"{r.ordem:03d}. {self._emoji(r.status)} | {r.nome} | encontradas={r.encontradas} | enviadas={r.enviadas_fila} | {motivo[:220]}")
                linhas.extend(self._linha_metricas_v128(r))
                linhas.append("")
        else:
            linhas.append("Todos os portais auditados enviaram ao menos 1 matéria para a fila nesta coleta.")
            linhas.append("")

        linhas.append("OK COM ENVIO PARA FILA")
        linhas.append("-" * 92)
        for r in [x for x in self.registros if x.status == "ok"][:limite]:
            linhas.append(f"{r.ordem:03d}. OK | {r.nome} | encontradas={r.encontradas} | enviadas={r.enviadas_fila}")
            # v128: também mostra detalhes dos OK, mas compacto.
            linhas.extend(self._linha_metricas_v128(r))
            linhas.append("")

        return "\n".join(linhas).strip()

    def to_dict(self) -> dict:
        return {
            "versao_diagnostico": self.versao_diagnostico,
            "lote_label": self.lote_label,
            "inicio_iso": self.inicio_iso,
            "registros": [asdict(r) for r in self.registros],
        }

    def salvar(self, pasta: str | Path = "logs") -> tuple[Path, Path]:
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = pasta / f"diagnostico_coleta_v129_{stamp}.json"
        txt_path = pasta / f"diagnostico_coleta_v129_{stamp}.txt"
        json_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(self.resumo_texto(), encoding="utf-8")
        (pasta / "diagnostico_coleta_v129_ultimo.txt").write_text(self.resumo_texto(), encoding="utf-8")
        # Mantém nomes legados para o painel e ferramentas antigas.
        (pasta / "diagnostico_coleta_v128_ultimo.txt").write_text(self.resumo_texto(), encoding="utf-8")
        (pasta / "diagnostico_coleta_v126_ultimo.txt").write_text(self.resumo_texto(), encoding="utf-8")
        return json_path, txt_path
