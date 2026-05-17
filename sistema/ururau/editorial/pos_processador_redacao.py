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
from urllib.parse import urlparse


# ─────────────────────── Helpers basicos ──────────────────────────────────

def _norm_para_comparacao(s: str) -> str:
    """Normaliza para comparar frases (lower, sem acento, sem pontuacao)."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _termo_para_regex_flexivel(termo: str) -> str:
    """Regex literal tolerante a acentos, cedilha e espaços variáveis."""
    mapa = {
        "a": "aáàãâä",
        "e": "eéèêë",
        "i": "iíìîï",
        "o": "oóòõôö",
        "u": "uúùûü",
        "c": "cç",
    }
    partes: list[str] = []
    for ch in str(termo or ""):
        if ch.isspace():
            partes.append(r"\s+")
            continue
        base = unicodedata.normalize("NFD", ch)[0].lower() if ch else ch
        if base in mapa:
            chars = mapa[base]
            partes.append("[" + re.escape(chars + chars.upper()) + "]")
        elif ch in "-–—":
            partes.append(r"[\-–—]")
        else:
            partes.append(re.escape(ch))
    return "".join(partes)


def _termos_proibidos_unificados() -> list[str]:
    termos: list[str] = []
    try:
        from ururau.editorial.regras_editoriais_ururau import TERMOS_PROIBIDOS_UNIFICADOS
        termos.extend(str(t) for t in TERMOS_PROIBIDOS_UNIFICADOS)
    except Exception:
        pass
    try:
        from ururau.editorial.regras_editoriais import (
            obter_expressoes_proibidas,
            obter_frases_genericas_proibidas,
            obter_termos_ia_proibidos,
        )
        termos.extend(str(t) for t in obter_termos_ia_proibidos())
        termos.extend(str(t) for t in obter_expressoes_proibidas().keys())
        termos.extend(str(t) for t in obter_frases_genericas_proibidas())
    except Exception:
        pass
    vistos: set[str] = set()
    out: list[str] = []
    for termo in termos:
        chave = _norm_para_comparacao(termo)
        if chave and chave not in vistos:
            out.append(termo)
            vistos.add(chave)
    return out


def _detectar_termos_proibidos_unificados(texto: str) -> list[str]:
    try:
        from ururau.editorial.regras_editoriais_ururau import detectar_termos_proibidos
        ach = detectar_termos_proibidos(texto or "")
    except Exception:
        alvo = _norm_para_comparacao(texto or "")
        ach = [t for t in _termos_proibidos_unificados() if _norm_para_comparacao(t) in alvo]
    return list(dict.fromkeys(str(t) for t in ach if str(t).strip()))


def metas_seo_por_fonte(fonte_texto: str = "", corpo: str = "") -> dict[str, int]:
    """V200_23: metas baseadas em PALAVRAS (SEO) em vez de paragrafos.

    O minimo de paragrafos vira HINT (nao bloqueia), apenas garante que a IA
    quebre o texto em paragrafos curtos. O que conta agora e o tamanho em
    palavras, alinhado com metricas SEO do Google (sweet spot 600-1200).
    """
    n = max(len(str(fonte_texto or "")), len(str(corpo or "")))
    if n >= 4200:
        return {"paragrafos_min": 4, "paragrafos_alvo": 6,
                "palavras_min": 800, "palavras_alvo": 1200,
                "max_chars_paragrafo": 480}
    if n >= 2600:
        return {"paragrafos_min": 3, "paragrafos_alvo": 5,
                "palavras_min": 600, "palavras_alvo": 1000,
                "max_chars_paragrafo": 480}
    if n >= 1400:
        return {"paragrafos_min": 3, "paragrafos_alvo": 4,
                "palavras_min": 500, "palavras_alvo": 800,
                "max_chars_paragrafo": 480}
    if n >= 800:
        return {"paragrafos_min": 2, "paragrafos_alvo": 3,
                "palavras_min": 400, "palavras_alvo": 700,
                "max_chars_paragrafo": 480}
    return {"paragrafos_min": 2, "paragrafos_alvo": 3,
            "palavras_min": 250, "palavras_alvo": 400,
            "max_chars_paragrafo": 480}


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
        metas = metas_seo_por_fonte(fonte_texto, corpo)
        fonte_nome = (
            corrigido.get("_veiculo_origem_para_remover")
            or corrigido.get("fonte_nome")
            or corrigido.get("nome_da_fonte")
            or corrigido.get("fonte")
            or ""
        )
        link_fonte = (
            corrigido.get("link_da_fonte")
            or corrigido.get("link_origem")
            or corrigido.get("url")
            or ""
        )
        corpo2, n_dup = deduplicar_frases_repetidas(corpo)
        if n_dup:
            correcoes.append(f"deduplicou_{n_dup}_frase_(s)_repetida(s)")
            corpo = corpo2
        corpo_pre = corpo
        corpo, rem_termos = remover_termos_proibidos(corpo)
        if rem_termos:
            correcoes.append(f"removeu_{len(rem_termos)}_termo(s)_ia_proibido(s)")
        corpo, rem_veiculos = remover_citacoes_veiculo_origem(corpo, fonte_nome=fonte_nome, link=link_fonte)
        if rem_veiculos:
            correcoes.append("removeu_citacao_veiculo_origem")
        corpo, corr_genericas = remover_fechos_e_aberturas_genericas(corpo)
        correcoes.extend(corr_genericas)
        corpo_dividido = dividir_paragrafo_unico(
            corpo,
            alvo_paragrafos=metas["paragrafos_alvo"],
            max_chars_paragrafo=metas["max_chars_paragrafo"],
        )
        if corpo_dividido != corpo:
            correcoes.append("ajustou_paragrafos_seo")
            corpo = corpo_dividido
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
        if "texto_final" in corrigido:
            corrigido["texto_final"] = corpo

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

    corpo_final = str(corrigido.get("corpo_materia") or corrigido.get("conteudo") or "")
    metas_finais = metas_seo_por_fonte(fonte_texto, corpo_final)
    termos_residuais = _detectar_termos_proibidos_unificados(corpo_final)
    fonte_nome_diag = (
        corrigido.get("_veiculo_origem_para_remover")
        or corrigido.get("fonte_nome")
        or corrigido.get("nome_da_fonte")
        or corrigido.get("fonte")
        or ""
    )
    veiculos_residuais = []
    link_diag = str(corrigido.get("link_da_fonte") or corrigido.get("link_origem") or corrigido.get("url") or "")
    for nome in _possiveis_nomes_veiculo(str(fonte_nome_diag), link_diag):
        if _norm_para_comparacao(nome) in _norm_para_comparacao(corpo_final):
            veiculos_residuais.append(nome)

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
        "metas_seo": metas_finais,
        "termos_ia_residuais": termos_residuais,
        "veiculo_origem_residual": sorted(set(veiculos_residuais)),
        "padrao_editorial_ok": not termos_residuais and not veiculos_residuais,
    }

    return {
        "pacote": corrigido,
        "correcoes": correcoes,
        "diagnostico": diag,
    }


# ─────────────────── 8) Auto-split de paragrafo unico (V200_2) ────────────

_SUBSTITUICOES_TERMOS_PROIBIDOS_V200_2 = (
    (r"\bo caso evidencia\b[^\.\!\?]*[\.\!\?]\s*", ""),
    (r"\bo caso mostra\b[^\.\!\?]*[\.\!\?]\s*", ""),
    (r"\bo caso reforca\b[^\.\!\?]*[\.\!\?]\s*", ""),
    (r"\bo caso reforça\b[^\.\!\?]*[\.\!\?]\s*", ""),
    (r"\btraz\s+à\s+tona\b", "expoe"),
    (r"\breacende o debate\b", "retoma a discussao"),
    (r"\bjoga luz sobre\b", "evidencia"),
    (r"\bcoloca em xeque\b", "questiona"),
    (r"\bvale destacar\b", ""),
    (r"\bvale ressaltar\b", ""),
    (r"\bé importante destacar\b", ""),
    (r"\bcabe destacar\b", ""),
    (r"\bnesse sentido,?\s*", ""),
    (r"\bdesta forma,?\s*", ""),
    (r"\bdessa forma,?\s*", ""),
    (r"\bdiante desse cenario,?\s*", ""),
    (r"\bdiante desse cenário,?\s*", ""),
    (r"\bem meio a\b", "durante"),
    (r"\bacende[u]?\s+(?:o|um)\s+alerta\b", "preocupa"),
    (r"\bsinal de alerta\b", "preocupacao"),
    (r"\bchama[ru]?\s+atenção\b", "destaca-se"),
    (r"\bganha[u]?\s+destaque\b", "ganhou notoriedade"),
    (r"\bé destaque\b", "tem repercussao"),
    (r"\breforça a importância\b", "confirma a relevancia"),
    (r"\breforça o compromisso\b", "confirma o compromisso"),
    (r"\breforça a necessidade\b", "confirma a necessidade"),
    (r"\bdestaca a importância\b", "indica a relevancia"),
    (r"\bevidencia a importância\b", "indica a relevancia"),
    (r"\bmostra a importância\b", "indica a relevancia"),
    (r"\bno centro das atenções\b", "em evidencia"),
    (r"\bsegue dando o que falar\b", "continua repercutindo"),
    (r"\bmovimenta os bastidores\b", "repercute"),
    (r"\bpromete movimentar\b", "deve repercutir"),
    (r"\bpopulação fica em alerta\b", "populacao esta atenta"),
    (r"\bautoridades seguem acompanhando\b", "autoridades acompanham"),
    (r"\bmedidas cabíveis\b", "providencias"),
    (r"\bprovidências cabíveis\b", "providencias"),
    (r"\baté o fechamento desta matéria\b", "ate a publicacao"),
    (r"\baté a publicação desta reportagem\b", "ate a publicacao"),
)

_SUBSTITUICOES_TERMOS_DINAMICOS = {
    "reforça": "afirma",
    "reforca": "afirma",
    "reafirma": "afirma",
    "reforçou": "afirmou",
    "reforçando": "afirmando",
    "ressalta": "informa",
    "ressaltou": "afirmou",
    "destaca": "informa",
    "destacou": "afirmou",
    "evidencia": "aponta",
    "evidenciando": "apontando",
    "sinaliza": "indica",
    "sinaliza que": "indica que",
    "mostra que": "indica que",
    "demonstra": "indica",
    "ilustra": "mostra",
    "escancara": "mostra",
    "robusto": "amplo",
    "robusta": "ampla",
    "emblemático": "relevante",
    "emblematica": "relevante",
    "emblemática": "relevante",
}


def _substituicoes_termos_proibidos_unificadas() -> dict[str, str]:
    """Substituicoes vindas da matriz editorial, com fallback local seguro."""
    subs = dict(_SUBSTITUICOES_TERMOS_DINAMICOS)
    try:
        from ururau.editorial.regras_editoriais import (
            obter_expressoes_proibidas,
            obter_matriz_editorial,
        )
        for termo, repl in obter_expressoes_proibidas().items():
            chave = _norm_para_comparacao(termo)
            if not chave:
                continue
            if isinstance(repl, str) and repl.strip():
                subs[chave] = repl.strip()
            else:
                subs.setdefault(chave, "")
        for termo, repl in (obter_matriz_editorial().get("verbos_crutch") or {}).items():
            if isinstance(repl, str) and repl.strip():
                subs[_norm_para_comparacao(termo)] = repl.strip()
    except Exception:
        pass
    return subs


def remover_termos_proibidos(texto):
    """Substitui termos proibidos e devolve (texto_limpo, lista_removidos)."""
    if not texto:
        return texto, []
    removidos = []
    out = texto
    substituicoes = _substituicoes_termos_proibidos_unificadas()
    for rx_src, sub in _SUBSTITUICOES_TERMOS_PROIBIDOS_V200_2:
        rx = re.compile(rx_src, re.IGNORECASE)
        if rx.search(out):
            removidos.append(rx_src)
            out = rx.sub(sub, out)
    for termo in _detectar_termos_proibidos_unificados(out):
        termo_norm = _norm_para_comparacao(termo)
        sub = substituicoes.get(termo_norm, "")
        rx = re.compile(r"(?<!\w)" + _termo_para_regex_flexivel(termo) + r"(?!\w)", re.IGNORECASE)
        if rx.search(out):
            removidos.append(termo)
            out = rx.sub(sub, out)
        elif termo_norm in _norm_para_comparacao(out):
            removidos.append(termo)
    out = re.sub(r"\s+([,\.;:])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r",\s*,+", ",", out)
    out = out.replace(" — ", ", ").replace(" – ", ", ")
    out = out.replace("—", "").replace("–", "")
    return out.strip(), removidos


def _possiveis_nomes_veiculo(fonte_nome: str = "", link: str = "") -> list[str]:
    nomes: list[str] = []
    for bruto in (fonte_nome or "",):
        bruto = re.sub(r"\s+", " ", str(bruto)).strip(" -|")
        if bruto:
            nomes.append(bruto)
            nomes.append(re.sub(r"\b(?:noticias|notícias|jornal|portal|site|online)\b", "", bruto, flags=re.I).strip())
    try:
        host = urlparse(str(link or "")).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        base = host.split(".")[0]
        base_curta_valida = len(base) >= 2 and any(c.isdigit() for c in base)
        if base and (len(base) >= 3 or base_curta_valida):
            nomes.append(base)
    except Exception:
        pass
    bloqueados = {"redacao", "redação", "reproducao", "reprodução", "assessoria", "internet", "fonte"}
    out: list[str] = []
    vistos: set[str] = set()
    for nome in nomes:
        nome = re.sub(r"\s+", " ", str(nome or "")).strip()
        chave = _norm_para_comparacao(nome)
        nome_curto_valido = len(chave) >= 2 and any(c.isdigit() for c in chave)
        if (len(chave) < 3 and not nome_curto_valido) or chave in bloqueados or chave in vistos:
            continue
        out.append(nome)
        vistos.add(chave)
    return out


def _nome_para_regex(nome: str) -> str:
    partes = [re.escape(p) for p in re.split(r"\s+", nome.strip()) if p]
    return r"\s+".join(partes)


def remover_citacoes_veiculo_origem(texto: str, fonte_nome: str = "", link: str = "") -> tuple[str, list[str]]:
    """Remove atribuições ao veículo de origem no corpo, preservando o crédito em campo próprio."""
    if not texto:
        return texto, []
    out = texto
    removidos: list[str] = []
    artigo = r"(?:o|a|os|as|ao|à|aos|às|pelo|pela|pelos|pelas|do|da|dos|das)?"
    qualificador = r"(?:(?:portal|site|jornal|revista|agência|agencia)\s+)?"
    for nome in _possiveis_nomes_veiculo(fonte_nome, link):
        nrx = _nome_para_regex(nome)
        padroes = [
            (
                re.compile(rf"\b(segundo|conforme|de acordo com)\s+{artigo}\s*{qualificador}{nrx}\b", re.I),
                r"\1 a fonte",
            ),
            (
                re.compile(rf"\b{artigo}\s*{qualificador}{nrx}\s+(?:apurou|informou|noticiou|publicou|divulgou|relatou)\s+que\b", re.I),
                "A fonte informa que",
            ),
            (
                re.compile(rf"\b(?:em entrevista|ao|à)\s+{artigo}\s*{qualificador}{nrx}\b", re.I),
                "à fonte",
            ),
            (
                re.compile(rf"\bFonte\s*:\s*{artigo}\s*{qualificador}{nrx}\b[.;]?", re.I),
                "",
            ),
        ]
        for rx, sub in padroes:
            if rx.search(out):
                removidos.append(nome)
                out = rx.sub(sub, out)
    out = re.sub(r"\s+([,\.;:])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip(), sorted(set(removidos))


def remover_fechos_e_aberturas_genericas(texto: str) -> tuple[str, list[str]]:
    if not texto:
        return texto, []
    correcoes: list[str] = []
    pars = [p.strip() for p in re.split(r"\n\s*\n+", texto) if p.strip()]
    novos: list[str] = []
    for p in pars:
        antes = p
        p = re.sub(r"^(?:além disso|alem disso|por outro lado|dessa forma|desta forma|nesse contexto|neste contexto|com isso),?\s+", "", p, flags=re.I)
        p = re.sub(r"^(?:o caso|a situação|a medida|a iniciativa)\s+(?:mostra|reforça|evidencia|demonstra)\s+[^.!?]*[.!?]\s*", "", p, flags=re.I)
        if p != antes:
            correcoes.append("removeu_abertura_generica")
        if p.strip():
            novos.append(p.strip())
    return "\n\n".join(novos), correcoes


def _split_em_sentencas_v200_2(texto):
    if not texto:
        return []
    partes = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÁ-Ú0-9])", texto.strip())
    return [p.strip() for p in partes if p.strip()]


def dividir_paragrafo_unico(texto, alvo_paragrafos=4, max_chars_paragrafo=600):
    """Se o corpo for paragrafo unico (ou poucos), divide em N paragrafos."""
    if not texto:
        return texto
    pars_atuais = [p.strip() for p in re.split(r"\n\s*\n+", texto) if p.strip()]
    if (len(pars_atuais) >= alvo_paragrafos
            and all(len(p) <= max_chars_paragrafo for p in pars_atuais)):
        return texto
    sentencas = []
    for p in pars_atuais or [texto]:
        sentencas.extend(_split_em_sentencas_v200_2(p))
    if not sentencas or len(sentencas) <= 1:
        return texto
    alvo_sent_por_par = max(1, round(len(sentencas) / alvo_paragrafos))
    paragrafos = []
    buffer = []
    for s in sentencas:
        candidato = (" ".join(buffer + [s])).strip()
        if (len(buffer) >= alvo_sent_por_par
                or len(candidato) > max_chars_paragrafo):
            if buffer:
                paragrafos.append(" ".join(buffer).strip())
                buffer = [s]
            else:
                paragrafos.append(s)
                buffer = []
        else:
            buffer.append(s)
    if buffer:
        paragrafos.append(" ".join(buffer).strip())
    paragrafos = [p for p in paragrafos if p.strip()]
    return "\n\n".join(paragrafos) if paragrafos else texto


def corrigir_corpo_motor_v2(corpo, alvo_paragrafos=4, max_chars_paragrafo=600,
                            *, fonte_texto: str = "", fonte_nome: str = "",
                            link: str = ""):
    """Aplica remover_termos_proibidos + dividir_paragrafo_unico."""
    correcoes = []
    if not corpo:
        return corpo, correcoes
    corpo_novo, removidos = remover_termos_proibidos(corpo)
    if removidos:
        correcoes.append("removeu_" + str(len(removidos)) + "_termos_proibidos")
    corpo_novo, veiculos = remover_citacoes_veiculo_origem(corpo_novo, fonte_nome=fonte_nome, link=link)
    if veiculos:
        correcoes.append("removeu_citacao_veiculo_origem")
    corpo_novo, corr_genericas = remover_fechos_e_aberturas_genericas(corpo_novo)
    correcoes.extend(corr_genericas)
    if fonte_texto and alvo_paragrafos == 4:
        alvo_paragrafos = metas_seo_por_fonte(fonte_texto, corpo_novo)["paragrafos_alvo"]
    corpo_dividido = dividir_paragrafo_unico(
        corpo_novo, alvo_paragrafos=alvo_paragrafos,
        max_chars_paragrafo=480,
    )
    if corpo_dividido != corpo_novo:
        corpo_novo = corpo_dividido
        correcoes.append("auto_split_paragrafo_unico")

    return corpo_novo, correcoes
