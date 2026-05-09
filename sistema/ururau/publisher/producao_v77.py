"""
ururau.publisher.producao_v77
Camada v77: validacao de producao para monitoramento 24h com publicacao real no painel.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ResultadoGateV77:
    aprovado: bool
    motivos: list[str] = field(default_factory=list)
    def motivo_texto(self) -> str:
        return "; ".join(self.motivos) if self.motivos else "OK"

# URURAU v47.2: termos de IA unificados
try:
    from ururau.editorial.regras_editoriais import obter_termos_ia_proibidos as _v472_termos_ia
    EXPRESSOES_PROIBIDAS = tuple(_v472_termos_ia())
except Exception:
    EXPRESSOES_PROIBIDAS = ("fique atento", "confira todos os detalhes", "saiba mais", "veja abaixo", "acende o alerta", "vale lembrar", "cabe ressaltar", "nesse contexto", "reforça")

def _texto(obj: Any, nome: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(nome, default) or "")
    return str(getattr(obj, nome, default) or "")

def _parece_placeholder(valor: str, nomes: tuple[str, ...]) -> bool:
    v = (valor or "").strip().lower()
    if not v:
        return True
    if v in nomes:
        return True
    if v.startswith(("cole_", "coloque_", "sua_", "seu_")):
        return True
    return False

def validar_ambiente_publicacao_real() -> ResultadoGateV77:
    """v78: OpenAI não é mais bloqueante; fallback local mantém o robô operando."""
    motivos: list[str] = []
    login = os.getenv("URURAU_LOGIN", "").strip()
    senha = os.getenv("URURAU_SENHA", "").strip()
    confirmar = os.getenv("URURAU_PUBLICACAO_REAL_CONFIRMADA", "").strip().upper()
    publicar_direto = os.getenv("URURAU_PUBLICAR_DIRETO", "").strip().lower()
    cms_direto = os.getenv("URURAU_CMS_PUBLICACAO_DIRETA", "").strip().lower()
    if _parece_placeholder(login, ("seu_login_do_painel", "login", "usuario")):
        motivos.append("URURAU_LOGIN ausente ou placeholder")
    if _parece_placeholder(senha, ("sua_senha_do_painel", "senha", "password")):
        motivos.append("URURAU_SENHA ausente ou placeholder")
    liberado = confirmar == "SIM" or publicar_direto in ("1", "true", "sim", "yes") or cms_direto in ("1", "true", "sim", "yes")
    if not liberado:
        motivos.append("publicação direta não confirmada: use URURAU_PUBLICACAO_REAL_CONFIRMADA=SIM ou URURAU_PUBLICAR_DIRETO=1")
    return ResultadoGateV77(aprovado=not motivos, motivos=motivos)

def gate_editorial_publicacao_real(materia: Any) -> ResultadoGateV77:
    motivos: list[str] = []
    # v78c: auditoria determinística final, padrão UOL/G1, antes de liberar publicação real.
    try:
        from ururau.editorial.auditoria_v78c import auditar_materia_10
        texto_fonte = _texto(materia, "cleaned_source_text") or _texto(materia, "raw_source_text")
        audit = auditar_materia_10(materia, texto_fonte=texto_fonte, modo="monitor")
        if audit.get("score_qualidade", 0) < 90:
            motivos.append(f"auditoria v78c abaixo de 90: {audit.get('score_qualidade')}/100")
        for blocker in (audit.get("bloqueadores") or [])[:3]:
            motivos.append("auditoria v78c: " + str(blocker.get("mensagem", blocker.get("codigo", "bloqueador"))))
    except Exception as exc:
        motivos.append(f"auditoria v78c falhou: {exc}")

    titulo = _texto(materia, "titulo") or _texto(materia, "titulo_seo")
    titulo_capa = _texto(materia, "titulo_capa")
    subtitulo = _texto(materia, "subtitulo") or _texto(materia, "subtitulo_curto")
    meta = _texto(materia, "meta_description")
    slug = _texto(materia, "slug")
    canal = _texto(materia, "canal")
    conteudo = _texto(materia, "conteudo") or _texto(materia, "corpo_materia")
    tags = _texto(materia, "tags")
    chamada = _texto(materia, "chamada_social")
    if len(titulo.strip()) < 20:
        motivos.append("titulo curto ou ausente")
    if len(titulo) > 89:
        motivos.append("titulo SEO acima de 89 caracteres")
    if titulo_capa and len(titulo_capa) > 60:
        motivos.append("titulo de capa acima de 60 caracteres")
    if not subtitulo or len(subtitulo) < 40:
        motivos.append("subtitulo fraco ou ausente")
    if not meta or len(meta) < 80 or len(meta) > 160:
        motivos.append("meta description fora do padrao 80-160 caracteres")
    if not slug or len(slug) < 20 or slug.endswith("-"):
        motivos.append("slug ausente, curto ou quebrado")
    if not canal:
        motivos.append("canal/editoria ausente")
    if len(conteudo.strip()) < 500:
        motivos.append("corpo abaixo de 500 caracteres")
    if "foto:" in conteudo.lower() or "publicidade" in conteudo.lower() or "🔎" in conteudo:
        motivos.append("conteudo ainda contem lixo de scraping")
    if "—" in conteudo or "–" in conteudo:
        motivos.append("corpo contem travessao")
    if any(expr in (conteudo + " " + chamada).lower() for expr in EXPRESSOES_PROIBIDAS):
        motivos.append("texto contem expressao generica/proibida")
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    if len(tag_list) < 5:
        motivos.append("menos de 5 tags")
    if len(tag_list) != len(set(tag_list)):
        motivos.append("tags duplicadas")
    if "r$" in titulo.lower() and re.search(r"saldo medio|media disponivel|valor medio", conteudo, re.I):
        motivos.append("titulo transforma valor medio em promessa de pagamento")
    return ResultadoGateV77(aprovado=not motivos, motivos=motivos)

def limpar_chamada_social(chamada: str) -> str:
    if not chamada:
        return ""
    out = chamada
    for frase in (
        "Fique atento aos prazos e condições.",
        "Fique atento ao prazo para não perder esse benefício.",
        "Confira todos os detalhes.",
        "Saiba mais.",
    ):
        out = out.replace(frase, "")
    out = re.sub(r"\s+", " ", out).strip()
    return out
