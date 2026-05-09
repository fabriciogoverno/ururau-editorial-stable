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
}

def read_env():
    data = {}
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")
    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data

def write_env(data):
    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")

def main():
    data = read_env()
    added = []
    for k, v in DEFAULTS.items():
        if k not in data or (k.endswith("URL") and not data.get(k)):
            data[k] = v
            added.append(k)
    write_env(data)
    if added:
        print("[v46.2][ENV] Variáveis adicionadas/corrigidas:", ", ".join(added))
    print("[v46.2][ENV] .env validado sem bloqueio")
    print("[v46.2][ENV] OPENAI_MODEL:", data.get("OPENAI_MODEL", ""))
    print("[v46.2][ENV] SITE_LOGIN_URL:", data.get("SITE_LOGIN_URL", ""))
    print("[v46.2][ENV] SITE_NOVA_URL:", data.get("SITE_NOVA_URL", ""))
    if not data.get("OPENAI_API_KEY"):
        print("[v46.2][AVISO] OPENAI_API_KEY vazia: painel abre em fallback sem IA até preencher.")
    if not data.get("URURAU_LOGIN") or not data.get("URURAU_SENHA"):
        print("[v46.2][AVISO] URURAU_LOGIN/URURAU_SENHA vazios: publicação real exige preencher as credenciais.")
    print("[v46.2][OK] Validação concluída. Não trava por variáveis antigas ausentes.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
