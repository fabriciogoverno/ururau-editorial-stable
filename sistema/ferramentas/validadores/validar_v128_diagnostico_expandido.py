from pathlib import Path

base = Path(__file__).resolve().parent
painel = (base / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")
aud = (base / "ururau" / "coleta" / "coleta_auditoria_v126.py").read_text(encoding="utf-8", errors="ignore")
termos = (base / "ururau" / "coleta" / "termos_busca_v127.py").read_text(encoding="utf-8", errors="ignore")
campos = (base / "ururau" / "coleta" / "adapters" / "campos24horas_v126.py").read_text(encoding="utf-8", errors="ignore")
sitemap = (base / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py").read_text(encoding="utf-8", errors="ignore")

assert "Diagnóstico técnico v128" in aud
assert "motivo_principal_v128" in aud
assert "_v128_diag_lote" in painel
assert "stats_v128" in painel
assert "obter_diagnostico_termos_v128" in termos
assert "url_google_news_rss" in termos
assert "obter_diagnostico_campos24_v128" in campos
assert "obter_diagnostico_sitemap_v128" in sitemap
assert "coletar_campos24horas_v126" in campos
assert "coletar_busca_termos_v127" in termos
print("[OK] v128 validado: diagnóstico técnico expandido aplicado sem remover coletores existentes")
