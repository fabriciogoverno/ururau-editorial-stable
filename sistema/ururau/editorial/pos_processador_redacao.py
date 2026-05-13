# -*- coding: utf-8 -*-
"""pos_processador_redacao — conserta defeitos tipicos do GPT antes de salvar.

Spec do usuario (13/05/2026), em cima do output real do GPT-4 mini:

    1) Frases repetidas literais no corpo (parafrase emendada).
    2) Titulo SEO truncado (cortado no limite sem encerrar a ideia).
    3) Aspas tipograficas mal aplicadas (',') em vez de aspas retas (\").
    4) Pontuacao solta (', ,' / ' .' / '.,').
    5) Falta de lead 5W no primeiro paragrafo.
    6) Tags sem virgula / com hashtag.
    7) Sem palavra-chave principal no inicio do titulo SEO.

Politica: NUNCA descarta materia. So conserta o pacote. Devolve diagnostico
com o que foi corrigido para auditoria.

API:

    aplicar_metricas_seo_google(pacote, fonte_texto='', palavra_chave='')
        -> {'pacote': pacote_corrigido, 'correcoes': list[str],
            'diagnostico': dict}

    deduplicar_frases_repetidas(texto) -> (str, int_removidas)
    corrigir_aspas_tipograficas(texto)  -> str
    corrigir_pontuacao_solta(texto)     -> str
    garantir_titulo_seo_completo(titulo, max_chars=89) -> str
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


# ─────────────────────── Helpers basicos ──────────────────────────────────

def _norm_para_comparacao(s: str) -> str:
    """Normaliza para comparar frases (lower, sem acento, sem pontuacao)."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ─────────────────── 1) Dedup de frases literais ──────────────────────────

def deduplicar_frases_repetidas(texto: str,
                                *, janela_chars: int = 300,
                                similaridade_min: int = 60) -> tuple[str, int]:
    """Remove repeticoes literais e quase-literais.

    Caso real do GPT-4 mini que vimos:
      "O ministro X informou que ... O ministro X informou que ..."

    Estrategia: percorre o texto e, para cada substring de >=60 chars que
    aparece >1 vez dentro de uma janela_chars, mantem so a primeira
    ocorrencia. Tambem corta duplicacoes 'inline' (mesma sentenca
    aparecendo de novo dentro do paragrafo).
    """
    if not texto:
        return texto, 0
    n_removidas = 0

    # 1.a) Detecta sentencas duplicadas adjacentes (mesma sentenca aparece
    #      logo depois da primeira no mesmo paragrafo).
    paragrafos = re.split(r"(\n\s*\n+)", texto)
    out_pars = []
    for chunk in paragrafos:
        if not chunk.strip() or chunk.startswith("\n"):
            out_pars.append(chunk)
            continue
        sents = re.split(r"(?<=[\.\!\?])\s+", chunk)
        sents_unicas: list[str] = []
        vistas_norm: list[str] = []
        for s in sents:
            s_strip = s.strip()
            if not s_strip:
                continue
            sn = _norm_para_comparacao(s_strip)
            # se identica a uma anterior (>40 chars normalizados), pula
            if len(sn) >= 25 and sn in vistas_norm:
                n_removidas += 1
                continue
            sents_unicas.append(s_strip)
            vistas_norm.append(sn)
        out_pars.append(" ".join(sents_unicas))
    texto = "".join(out_pars)

    # 1.b) Detecta substrings literais repetidas (>=similaridade_min chars)
    #      dentro de uma janela. Caso classico: "X informou que ... X informou que".
    out = []
    i = 0
    while i < len(texto):
        # busca repeticao a partir de i
        max_len = min(janela_chars, len(texto) - i)
        achou = False
        for L in range(min(max_len, 240), similaridade_min - 1, -10):
            trecho = texto[i:i + L]
            # so dedup se for "frase" — comeca em letra/numero
            if not trecho or not trecho[0].isalnum():
                continue
            tn = _norm_para_comparacao(trecho)
            if len(tn) < similaridade_min:
                continue
            # procura proxima ocorrencia normalizada
            resto = texto[i + L: i + L + janela_chars * 2]
            if tn in _norm_para_comparacao(resto)[:500]:
                # encontrou repeticao logo a seguir — pula a segunda
                idx_real = resto.lower().find(trecho.lower())
                if idx_real != -1 and idx_real < janela_chars:
                    out.append(trecho)
                    i += L + idx_real + L  # pula L da repeticao tambem
                    n_removidas += 1
                    achou = True
                    break
        if not achou:
            out.append(texto[i])
            i += 1
    return "".join(out), n_removidas


# ─────────────────── 2) Aspas tipograficas ────────────────────────────────

# Caso real: o GPT escreve `, frase , afirmou.` em vez de `"frase", afirmou.`.
# Detectamos isolada virgula entre espaços e proximidade de fala atribuida.
_RX_ASPAS_TIPO = (
    (re.compile(r"[“”«»]"), '"'),
    (re.compile(r"[‘’]"), "'"),
)

# Padroes "fala atribuida" onde uma virgula isolada na verdade era aspa.
_RX_VIRGULA_VOLANTE_ABRE = re.compile(
    r"(\.\s*)(,\s+)([A-ZÁ-Ú][^,\n]{20,300}?)(\s*,\s*)([a-zà-ú])"
)


def corrigir_aspas_tipograficas(texto: str) -> str:
    if not texto:
        return texto
    for rx, sub in _RX_ASPAS_TIPO:
        texto = rx.sub(sub, texto)
    # caso especial: " . , frase , palavra" -> " . \"frase\", palavra"
    texto = _RX_VIRGULA_VOLANTE_ABRE.sub(r'\1"\3", \5', texto)
    return texto


# ─────────────────── 3) Pontuacao solta ───────────────────────────────────

def corrigir_pontuacao_solta(texto: str) -> str:
    if not texto:
        return texto
    # vírgula seguida de vírgula
    texto = re.sub(r",\s*,+", ",", texto)
    # ponto + virgula isolada virou ponto
    texto = re.sub(r"\.\s*,\s+(?=[A-ZÁ-Ú])", ". ", texto)
    # espaco antes de pontuacao
    texto = re.sub(r"\s+([\.,;:\!\?])", r"\1", texto)
    # duplo espaco
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    # ' , ' isolado entre letras
    texto = re.sub(r"(\w)\s+,\s+(\w)", r"\1, \2", texto)
    # parenteses orfaos
    texto = re.sub(r"\(\s+", "(", texto)
    texto = re.sub(r"\s+\)", ")", texto)
    return texto.strip()


# ─────────────────── 4) Titulo SEO completo ───────────────────────────────

_PALAVRAS_TRUNCAVEIS = {
    "bilhao", "bilhões", "bilhoes", "bilhão",
    "milhao", "milhão", "milhões", "milhoes",
    "trilhao", "trilhão", "trilhões", "trilhoes",
    "mil", "mi", "bi",
    "litro", "litros",
    "horas", "hora",
    "anos", "ano",
    "reais", "real",
    "dia", "dias",
    "semana", "semanas",
}


def garantir_titulo_seo_completo(titulo: str,
                                  *, max_chars: int = 89,
                                  contexto_corpo: str = "") -> str:
    """Encerra unidade truncada (R$ 13 -> R$ 13 bilhões) usando heuristica.

    Funciona em DOIS cenarios:
      (a) titulo passa de max_chars  -> trunca e tenta completar unidade
      (b) titulo cabe (<=max_chars) MAS termina em numero/R$ sem unidade
          (caso do GPT-4 mini que vimos: 'R$ 13' sem 'bilhoes') -> tenta
          inferir unidade do contexto_corpo (se R$ 13 bilhoes aparece la,
          completa). Se nao houver contexto, mantem como esta.
    """
    if not titulo:
        return titulo
    t = titulo.strip()

    def _termina_em_numero_sem_unidade(s: str) -> bool:
        if re.search(r"\bR\$\s*[\d,.]+\s*$", s):
            return True
        # numero solto sem unidade depois
        m = re.search(r"(\d[\d,.]*)\s*$", s)
        return bool(m and not re.search(r"\b(bilh|milh|trilh|mil|reais|real|por\s+cento|%|porcento|por\s+litro|por\s+kg|km|m\b|cm|kg|g\b|ml|l\b|dia|dias|semana|semanas|ano|anos|mes|meses|hora|horas)\b", s[-40:].lower()))

    def _inferir_unidade(t_atual: str, ctx: str) -> str | None:
        """Procura no contexto_corpo a unidade que casa com R$/numero do titulo."""
        if not ctx:
            return None
        # extrai numero do final do titulo
        m = re.search(r"R\$\s*([\d,.]+)\s*$", t_atual) or re.search(r"(\d[\d,.]*)\s*$", t_atual)
        if not m:
            return None
        num = m.group(1)
        # busca esse numero no corpo com uma unidade
        rx = re.compile(
            re.escape(num) + r"\s+(bilh[oõ]es?|milh[oõ]es?|trilh[oõ]es?|mil)\b",
            re.I,
        )
        m2 = rx.search(ctx or "")
        if m2:
            return m2.group(1).lower()
        return None

    # (a) titulo cabe MAS termina em numero/R$ sem unidade
    if len(t) <= max_chars and _termina_em_numero_sem_unidade(t):
        unidade = _inferir_unidade(t, contexto_corpo)
        if unidade:
            candidato = f"{t} {unidade}"
            if len(candidato) <= max_chars:
                return candidato
            # Nao cabe? Encurta o INICIO removendo palavras-conector
            # ate sobrar espaco para a unidade. Estrategia: tirar trecho
            # entre 'detalha' e o R$, p.ex., ou tirar adjetivos opcionais.
            for trecho_opcional in (
                "de até ", "ate ", "até ",
                "do total ", "no total ", "do programa ",
                "anunciado ", "anunciada ",
                "para gasolina ", "para diesel ",
                "por litro ",
            ):
                if trecho_opcional in t.lower():
                    pos = t.lower().find(trecho_opcional)
                    encurtado = t[:pos] + t[pos + len(trecho_opcional):]
                    candidato2 = f"{encurtado.strip()} {unidade}".strip()
                    if len(candidato2) <= max_chars:
                        return candidato2
            # ultimo recurso: trunca palavras do meio, mantendo lead + numero + unidade
            return candidato[:max_chars].rstrip(",;:.- ")

    if len(t) <= max_chars:
        return _remover_preposicoes_orfas(t)

    # (b) titulo passa de max_chars
    palavras = t.split()
    if not palavras:
        return t[:max_chars]
    while palavras and len(" ".join(palavras)) > max_chars:
        palavras.pop()
    base = " ".join(palavras).rstrip(",;:.- ")
    if _termina_em_numero_sem_unidade(base):
        unidade = _inferir_unidade(base, contexto_corpo or t)
        if not unidade:
            # heuristica: tenta achar unidade no titulo original
            m_u = re.search(r"\b(bilh[oõ]es?|milh[oõ]es?|trilh[oõ]es?|mil)\b",
                            t, re.I)
            unidade = m_u.group(1).lower() if m_u else "bilhoes"
        candidato = f"{base} {unidade}"
        if len(candidato) <= max_chars:
            return _remover_preposicoes_orfas(candidato)
    return _remover_preposicoes_orfas(base)


_PREPS_ORFAS = (
    "de", "do", "da", "dos", "das", "para", "com", "em", "no", "na",
    "nos", "nas", "ao", "aos", "à", "às", "a", "o", "e", "ou",
)


def _remover_preposicoes_orfas(t: str) -> str:
    palavras = t.rstrip(",;:.- ").split()
    while palavras and palavras[-1].lower() in _PREPS_ORFAS:
        palavras.pop()
    return " ".join(palavras)


# ─────────────────── 5) Lead 5W obrigatorio ───────────────────────────────

def primeiro_paragrafo_tem_lead_5w(texto: str) -> dict:
    """Heuristica leve: confere se o primeiro paragrafo cobre quem/o que/
    quando/onde no minimo. Devolve {'ok', 'cobertura', 'sugestoes'}."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n+", texto or "") if p.strip()]
    if not paragrafos:
        return {"ok": False, "cobertura": {}, "sugestoes": ["sem_paragrafos"]}
    lead = paragrafos[0]
    cobertura: dict[str, bool] = {}
    # QUEM (pessoa/orgao com letra maiuscula seguida de minuscula, >=2 palavras)
    cobertura["quem"] = bool(re.search(r"\b[A-ZÁ-Ú][a-zà-ú]+(?:\s+(?:de\s+|do\s+|da\s+)?[A-ZÁ-Ú][a-zà-ú]+){0,3}\b", lead))
    # QUANDO (data, hora, dia da semana, mes)
    cobertura["quando"] = bool(re.search(
        r"\b\d{1,2}[/\-.]\d{1,2}(?:[/\-.]\d{2,4})?\b|\b(?:hoje|ontem|amanha|segunda|terca|quarta|quinta|sexta|sabado|domingo|janeiro|fevereiro|marco|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
        lead, re.I,
    ))
    # ONDE (preposicao local em+ProperNoun, ou cidade conhecida)
    cobertura["onde"] = bool(re.search(
        r"\b(?:em|no|na|nos|nas)\s+[A-ZÁ-Ú]", lead,
    ))
    # O QUE (verbo de acao no presente/passado, simplificado)
    cobertura["o_que"] = bool(re.search(
        r"\b(?:anunciou|disse|afirmou|informou|aprovou|rejeitou|"
        r"determinou|decidiu|abriu|fechou|criou|investiu|pagou|"
        r"recebeu|inaugurou|publicou|lancou|comecou|terminou)\b",
        lead, re.I,
    ))
    sugestoes = [k for k, v in cobertura.items() if not v]
    return {"ok": not sugestoes, "cobertura": cobertura, "sugestoes": sugestoes}


# ─────────────────── 6) Tags com virgula sem hashtag ──────────────────────

def normalizar_tags(tags: str) -> str:
    if not tags:
        return tags
    s = re.sub(r"#", "", tags)
    # se separadas por espacos sem virgula, adiciona virgulas
    if "," not in s and len(s.split()) > 1:
        # so se nao for uma frase (cada token deve ser curto)
        toks = s.split()
        if all(len(t) <= 25 for t in toks):
            s = ", ".join(toks)
    s = re.sub(r"\s*,\s*,+", ",", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*", ", ", s)
    return s.strip().strip(",").strip()


# ─────────────────── 7) Pipeline principal ────────────────────────────────

def aplicar_metricas_seo_google(pacote: dict | None,
                                fonte_texto: str = "",
                                *, palavra_chave: str = "") -> dict:
    """Aplica TODAS as correcoes SEO/redacionais. Politica: nunca descarta.

    Retorna:
        {
          "pacote": pacote_corrigido (dict),
          "correcoes": list[str],  # auditoria do que mudou
          "diagnostico": dict      # estado final, indicadores SEO
        }
    """
    if not isinstance(pacote, dict):
        return {"pacote": pacote, "correcoes": [], "diagnostico": {}}

    corrigido = dict(pacote)
    correcoes: list[str] = []

    # 1) corpo: dedup + aspas + pontuacao
    corpo = str(corrigido.get("corpo_materia") or corrigido.get("conteudo") or "")
    if corpo:
        corpo2, n_dup = deduplicar_frases_repetidas(corpo)
        if n_dup:
            correcoes.append(f"deduplicou_{n_dup}_frase_(s)_repetida(s)")
            corpo = corpo2
        corpo_pre = corpo
        corpo = corrigir_aspas_tipograficas(corpo)
        if corpo != corpo_pre:
            correcoes.append("corrigiu_aspas_tipograficas_no_corpo")
        corpo_pre = corpo
        corpo = corrigir_pontuacao_solta(corpo)
        if corpo != corpo_pre:
            correcoes.append("corrigiu_pontuacao_solta_no_corpo")
        corrigido["corpo_materia"] = corpo
        if "conteudo" in corrigido:
            corrigido["conteudo"] = corpo

    # 2) titulo SEO
    t_seo = str(corrigido.get("titulo_seo") or "").strip()
    if t_seo:
        t_seo_pre = t_seo
        t_seo = corrigir_aspas_tipograficas(t_seo)
        t_seo = corrigir_pontuacao_solta(t_seo)
        t_seo = garantir_titulo_seo_completo(
            t_seo, max_chars=89,
            contexto_corpo=str(corrigido.get("corpo_materia") or "") + " " + fonte_texto,
        )
        if t_seo != t_seo_pre:
            correcoes.append(f"ajustou_titulo_seo:'{t_seo_pre[-30:]}'->'{t_seo[-30:]}'")
        corrigido["titulo_seo"] = t_seo

    # 3) titulo capa
    t_capa = str(corrigido.get("titulo_capa") or "").strip()
    if t_capa:
        t_capa_pre = t_capa
        t_capa = corrigir_aspas_tipograficas(t_capa)
        t_capa = corrigir_pontuacao_solta(t_capa)
        t_capa = garantir_titulo_seo_completo(
            t_capa, max_chars=60,
            contexto_corpo=str(corrigido.get("corpo_materia") or "") + " " + fonte_texto,
        )
        if t_capa != t_capa_pre:
            correcoes.append("ajustou_titulo_capa")
        corrigido["titulo_capa"] = t_capa

    # 4) subtitulo / legenda
    for k in ("subtitulo_curto", "legenda_curta"):
        v = str(corrigido.get(k) or "").strip()
        if v:
            v_pre = v
            v = corrigir_aspas_tipograficas(v)
            v = corrigir_pontuacao_solta(v)
            if v != v_pre:
                correcoes.append(f"ajustou_{k}")
            corrigido[k] = v

    # 5) tags
    tags = str(corrigido.get("tags") or "").strip()
    if tags:
        tags_pre = tags
        tags = normalizar_tags(tags)
        if tags != tags_pre:
            correcoes.append("normalizou_tags")
        corrigido["tags"] = tags

    # 6) credito_foto - removr 'foto:' redundante e cortar
    cf = str(corrigido.get("credito_foto") or "").strip()
    if cf:
        cf_pre = cf
        cf = re.sub(r"^(?:foto|imagem|arte|reproducao|reprodução)\s*[:\-]\s*",
                     "", cf, flags=re.I)
        cf = cf.strip()
        if cf != cf_pre:
            correcoes.append("normalizou_credito_foto")
        corrigido["credito_foto"] = cf

    # Diagnostico final
    lead = primeiro_paragrafo_tem_lead_5w(corrigido.get("corpo_materia", ""))
    diag = {
        "titulo_seo_chars": len(corrigido.get("titulo_seo", "")),
        "titulo_capa_chars": len(corrigido.get("titulo_capa", "")),
        "tags_count": len([t for t in (corrigido.get("tags") or "").split(",") if t.strip()]),
        "paragrafos_corpo": len([p for p in re.split(
            r"\n\s*\n+", corrigido.get("corpo_materia", "")) if p.strip()]),
        "lead_5w": lead,
        "palavra_chave_no_titulo": (
            bool(palavra_chave) and palavra_chave.lower() in
            corrigido.get("titulo_seo", "").lower()
        ) if palavra_chave else None,
    }

    return {
        "pacote": corrigido,
        "correcoes": correcoes,
        "diagnostico": diag,
    }


__all__ = [
    "aplicar_metricas_seo_google",
    "deduplicar_frases_repetidas",
    "corrigir_aspas_tipograficas",
    "corrigir_pontuacao_solta",
    "garantir_titulo_seo_completo",
    "primeiro_paragrafo_tem_lead_5w",
    "normalizar_tags",
]
