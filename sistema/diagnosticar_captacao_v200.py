#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""diagnosticar_captacao_v200 — verifica os 6 fixes da captacao 100%.

Uso:
    python sistema/diagnosticar_captacao_v200.py
    python sistema/diagnosticar_captacao_v200.py --fonte alerj
    python sistema/diagnosticar_captacao_v200.py --sitemap https://www.metropoles.com/sitemap_index.xml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def diag_fallback_urls() -> dict:
    from ururau.coleta.fontes_oficiais_fallback_v200 import substituir_url_se_quebrado
    amostras = [
        "https://www.camara.leg.br/rss/noticias.xml",
        "https://www.alerj.rj.gov.br/Noticias/rss",
        "https://www.mprj.mp.br/rss",
        "https://www.tre-rj.jus.br/comunicacao/noticias/RSS",
        "https://www.tjrj.jus.br/web/guest/home/-/noticias/rss",
        "https://defensoria.rj.def.br/rss/noticias",
        "https://www.rj.gov.br/noticias/rss",
        "https://www.tce.rj.gov.br/",
        "https://www.portodoacu.com.br/",
        "https://noticias.stf.jus.br/feed/",  # NAO deve mudar
    ]
    res = []
    for u in amostras:
        nova, motivo = substituir_url_se_quebrado(u)
        res.append({
            "original": u,
            "efetiva": nova,
            "alterada": nova != u,
            "motivo": motivo,
        })
    return {"endpoints_quebrados_redirecionados": res}


def diag_janelas() -> dict:
    from ururau.coleta.datas_v99 import janela_para_fonte_v200, janela_publicacao_horas
    casos = [
        {"nome": "Default (Prensa Babel)", "fonte": {}, "url": "https://prensadebabel.com.br/feed/"},
        {"nome": "Regional Nfnoticias", "fonte": {}, "url": "https://www.nfnoticias.com.br/rss/"},
        {"nome": "Regional Tribuna NF", "fonte": {}, "url": "https://www.tribunanf.com.br/feed/"},
        {"nome": "Oficial Gov.br", "fonte": {"bypass_score": True}, "url": "https://www.gov.br/rss.xml"},
        {"nome": "Oficial STF", "fonte": {}, "url": "https://noticias.stf.jus.br/feed/"},
        {"nome": "Tipo regional_v1305", "fonte": {"tipo": "regional_v1305"}, "url": "https://qualquer.com/feed/"},
    ]
    res = []
    for c in casos:
        j = janela_para_fonte_v200(c["fonte"], c["url"], c["nome"])
        res.append({"fonte": c["nome"], "url": c["url"], "janela_horas": j})
    return {
        "janela_padrao_horas": janela_publicacao_horas(),
        "janelas_por_fonte": res,
    }


def diag_dominios_timeout() -> dict:
    from ururau.coleta.fontes_oficiais_fallback_v200 import (
        dominio_e_timeout_cronico, url_wayback_recente,
    )
    casos = [
        "https://girorj.com.br/feed/",
        "https://www.girorj.com.br/feed/",
        "https://g1.globo.com/rss/g1/politica/",
        "https://prensadebabel.com.br/feed/",
    ]
    res = []
    for u in casos:
        tc = dominio_e_timeout_cronico(u)
        res.append({
            "url": u,
            "timeout_cronico": tc,
            "wayback_fallback": url_wayback_recente(u) if tc else None,
        })
    return {"dominios_timeout_cronico": res}


def diag_sitemap(url: str | None) -> dict:
    if not url:
        return {"skipped": "sem --sitemap"}
    from ururau.coleta.sitemap_xml_coletor_v200 import (
        coletar_sitemap_xml, obter_diagnostico_sitemap_v200,
    )
    try:
        itens = coletar_sitemap_xml(url, janela_horas=72, limite=20)
        return {
            "url": url,
            "itens_coletados": len(itens),
            "primeiros_5": [
                {"titulo": p.get("titulo_origem", "")[:80], "url": p.get("link_origem")}
                for p in itens[:5]
            ],
        }
    except Exception as e:
        return {"url": url, "erro": f"{type(e).__name__}: {e}"}


def diag_sanitizador() -> dict:
    from ururau.coleta.sitemap_xml_coletor_v200 import sanitizar_xml
    bruto = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://exemplo.com/noticia/foo&bar</loc>
    <lastmod>2026-05-13T22:00:00-03:00</lastmod>
  </url>
  <url>
    <loc>https://exemplo.com/noticia/s&atilde;o-jo&aacute;o</loc>
  </url>
</urlset>"""
    saneado = sanitizar_xml(bruto)
    return {
        "bytes_original": len(bruto),
        "bytes_saneado": len(saneado),
        "trecho_saneado": saneado[:300].decode("utf-8", errors="ignore"),
    }


def main():
    ap = argparse.ArgumentParser(description="Diagnostico da captacao v200")
    ap.add_argument("--sitemap", default=None, help="URL de sitemap para testar")
    ap.add_argument("--json", action="store_true", help="Saida em JSON")
    args = ap.parse_args()

    relatorio = {
        "fix_1_5_fallback_urls": diag_fallback_urls(),
        "fix_2_sitemap": diag_sitemap(args.sitemap),
        "fix_3_sanitizador": diag_sanitizador(),
        "fix_4_dominios_timeout": diag_dominios_timeout(),
        "fix_6_janelas": diag_janelas(),
    }

    if args.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
        return 0

    # Modo legivel
    print("=" * 78)
    print("DIAGNOSTICO CAPTACAO v200 — relatorio resumido")
    print("=" * 78)

    print("\n[Fix 1+5] Endpoints oficiais quebrados -> fallback Google News:")
    for it in relatorio["fix_1_5_fallback_urls"]["endpoints_quebrados_redirecionados"]:
        marca = "REDIRECIONOU" if it["alterada"] else "OK (sem mudar)"
        print(f"  {marca}: {it['original']}")
        if it["alterada"]:
            print(f"      -> {it['efetiva']}")

    print("\n[Fix 2] Sitemap testado:")
    sm = relatorio["fix_2_sitemap"]
    if "skipped" in sm:
        print(f"  {sm['skipped']} (passe --sitemap <url> para testar)")
    elif "erro" in sm:
        print(f"  ERRO: {sm['erro']}")
    else:
        print(f"  URL: {sm['url']}")
        print(f"  Itens coletados: {sm['itens_coletados']}")
        for p in sm.get("primeiros_5", []):
            print(f"    - {p['titulo']}")
            print(f"      {p['url']}")

    print("\n[Fix 3] Sanitizador XML:")
    sn = relatorio["fix_3_sanitizador"]
    print(f"  {sn['bytes_original']} bytes -> {sn['bytes_saneado']} bytes")
    print(f"  Trecho saneado: {sn['trecho_saneado'][:200]}")

    print("\n[Fix 4] Dominios com timeout cronico:")
    for it in relatorio["fix_4_dominios_timeout"]["dominios_timeout_cronico"]:
        marca = "TIMEOUT_CRONICO" if it["timeout_cronico"] else "ok"
        print(f"  {marca}: {it['url']}")
        if it["wayback_fallback"]:
            print(f"      fallback Wayback: {it['wayback_fallback']}")

    print("\n[Fix 6] Janelas por tipo de fonte (em horas):")
    print(f"  Padrao global: {relatorio['fix_6_janelas']['janela_padrao_horas']}h")
    for it in relatorio["fix_6_janelas"]["janelas_por_fonte"]:
        print(f"  {it['janela_horas']:>3}h  {it['fonte']:<30} {it['url']}")

    print("\n" + "=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
