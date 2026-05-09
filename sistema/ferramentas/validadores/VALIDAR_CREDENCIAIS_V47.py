from pathlib import Path
import tempfile, shutil, os, sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from ururau.ui.painel import _ler_env_atual, _atualizar_env

# teste seguro: não usa chave real, apenas valores fake temporários no ambiente do projeto atual
valores = {
    "OPENAI_API_KEY": "sk-test-v47-nao-usar",
    "URURAU_LOGIN": "login_teste_v47",
    "URURAU_SENHA": "senha_teste_v47",
    "URURAU_ASSINATURA": "Ururau",
    "SITE_LOGIN_URL": "https://www.ururau.com.br/acessocpainel/",
    "SITE_NOVA_URL": "https://www.ururau.com.br/acessocpainel/noticias/nova/",
}
_atualizar_env(valores)
carregado = _ler_env_atual()
falhas = [k for k, v in valores.items() if carregado.get(k) != v]
if falhas:
    print("FALHA: campos não persistiram:", ", ".join(falhas))
    raise SystemExit(1)
print("OK: credenciais persistem e são relidas com prioridade correta.")
