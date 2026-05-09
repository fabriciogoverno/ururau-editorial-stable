from pathlib import Path

ENV_PATH = Path(".env")
DEFAULTS = {
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "gpt-4.1-mini",
    "URURAU_LOGIN": "",
    "URURAU_SENHA": "",
    "URURAU_ASSINATURA": "Ururau",
    "SITE_LOGIN_URL": "https://www.ururau.com.br/acessocpainel/",
    "SITE_NOVA_URL": "https://www.ururau.com.br/acessocpainel/noticias/nova/",
    "URURAU_PANEL_URL": "https://www.ururau.com.br/acessocpainel/",
    "URURAU_NEW_POST_URL": "https://www.ururau.com.br/acessocpainel/noticias/nova/",
    "URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR": "1",
    "URURAU_SCORE_MINIMO_RASCUNHO": "65",
    "URURAU_AUDITORIA_FACTUAL_V81": "1",
    "URURAU_BLOQUEAR_TITULO_SOZINHO": "1",
    "URURAU_FALLBACK_SEM_IA": "1",
    "URURAU_FORCE_FALLBACK_WITHOUT_OPENAI_KEY": "1",
    "URURAU_V46_LAYOUT_DEFINITIVO": "1",
    "URURAU_V46_FALLBACK_SE_LAYOUT_FALHAR": "1",
    "URURAU_V46_2_ENV_REPARADO": "1",
    "ARQUIVO_DB": "data/ururau.db",
    "PASTA_IMAGENS": "data/imagens",
    "PASTA_PRINTS": "data/prints",
    "PASTA_LOGS": "logs",
    "TZ": "America/Sao_Paulo",
}

def ler():
    data = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data

def main():
    data = ler()
    for k, v in DEFAULTS.items():
        if k not in data or (k.endswith("URL") and not data.get(k)):
            data[k] = v
    if not data.get("SITE_LOGIN_URL"):
        data["SITE_LOGIN_URL"] = data["URURAU_PANEL_URL"]
    if not data.get("SITE_NOVA_URL"):
        data["SITE_NOVA_URL"] = data["URURAU_NEW_POST_URL"]
    if not data.get("URURAU_PANEL_URL"):
        data["URURAU_PANEL_URL"] = data["SITE_LOGIN_URL"]
    if not data.get("URURAU_NEW_POST_URL"):
        data["URURAU_NEW_POST_URL"] = data["SITE_NOVA_URL"]
    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")
    print("[v46.2][OK] .env preservado, reparado e normalizado.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
