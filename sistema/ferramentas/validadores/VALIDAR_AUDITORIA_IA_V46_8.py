"""
Validador local v46.8 — Auditoria IA / fallback.

Uso:
    python VALIDAR_AUDITORIA_IA_V46_8.py
    python VALIDAR_AUDITORIA_IA_V46_8.py --openai

Sem --openai, não chama a API. Ele apenas valida sintaxe e prova que o
fallback local fica marcado como fallback_sem_ia.
Com --openai, faz uma chamada curta ao modelo configurado no .env e registra
openai_ok ou o erro real em logs/ia_diagnostico.*.
"""
from __future__ import annotations

import argparse
import compileall
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except Exception:
    pass


def validar_sintaxe() -> bool:
    print("[1/3] Validando sintaxe do pacote ururau...")
    ok = compileall.compile_dir(str(BASE_DIR / "ururau"), quiet=1)
    print("      OK" if ok else "      FALHOU")
    return bool(ok)


def validar_fallback() -> bool:
    print("[2/3] Testando fallback local com diagnóstico explícito...")
    from ururau.editorial.engine import generate_ururau_article

    fonte = (
        "O Grupo de Atuação Especial de Combate ao Crime Organizado do Ministério Público do Estado do Rio de Janeiro "
        "denunciou seis policiais penais e outras seis pessoas por tráfico de drogas e por suposta facilitação "
        "da entrada de celulares em dois presídios de Campos dos Goytacazes. A Polícia Civil cumpre mandados "
        "nesta quinta-feira nas unidades Dalton Crespo de Castro e Carlos Tinoco da Fonseca, além de endereços "
        "ligados aos investigados em cidades do estado. A investigação teve início após a morte de Marcelo Aparecido "
        "de Lima, em abril de 2025, no Parque Santa Clara. Segundo o MPRJ, dados de celulares indicaram a existência "
        "de um grupo com divisão de tarefas. A Justiça também determinou o afastamento dos policiais penais das funções "
        "e a suspensão do porte de armas. "
    ) * 3
    pauta = {
        "uid": "teste-v46-8",
        "titulo_origem": "GAECO denuncia policiais penais por drogas e celulares em presídios de Campos",
        "resumo_origem": "MPRJ aponta esquema em unidades prisionais de Campos.",
        "cleaned_source_text": fonte,
        "fonte_nome": "MPRJ",
        "link_origem": "https://exemplo.local/teste",
        "canal": "Polícia",
    }
    materia = generate_ururau_article(pauta, None, os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), "Polícia")
    gj = getattr(materia, "generated_article_json", {}) or {}
    modo = getattr(materia, "modo_geracao", "") or gj.get("modo_geracao")
    status = getattr(materia, "ia_status", "") or gj.get("ia_status")
    origem = getattr(materia, "ia_texto_final_origem", "") or gj.get("ia_texto_final_origem")
    print(f"      modo_geracao={modo}")
    print(f"      ia_status={status}")
    print(f"      ia_texto_final_origem={origem}")
    print(f"      titulo={getattr(materia, 'titulo', '')}")
    print(f"      retranca={getattr(materia, 'retranca', '')}")
    ok = modo == "fallback_sem_ia" and origem == "fallback_local" and bool(getattr(materia, "conteudo", "").strip())
    print("      OK" if ok else "      FALHOU")
    return ok


def testar_openai_real() -> bool:
    print("[3/3] Testando chamada real OpenAI...")
    from ururau.config.settings import MODELO_OPENAI, OPENAI_API_KEY, validate_openai_config
    from ururau.ia.diagnostico import trace_openai_ok, trace_openai_erro

    valid = validate_openai_config(OPENAI_API_KEY, MODELO_OPENAI)
    if not valid.ok:
        print(f"      NÃO CHAMOU API: {valid.codigo or valid.reason}")
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=MODELO_OPENAI,
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": "Retorne {\"ok\": true, \"teste\": \"ururau\"}."},
            ],
            temperature=0,
            max_tokens=80,
        )
        raw = (resp.choices[0].message.content or "").strip()
        trace_openai_ok("teste_manual_v46_8", MODELO_OPENAI, detalhe={"chars_resposta": len(raw)})
        print("      OPENAI OK")
        print(f"      modelo={MODELO_OPENAI}")
        print(f"      resposta={raw[:120]}")
        return True
    except Exception as exc:
        tr = trace_openai_erro("teste_manual_v46_8", MODELO_OPENAI, exc)
        print(f"      OPENAI FALHOU: {tr.get('status')} - {tr.get('erro_mensagem')}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--openai", action="store_true", help="faz uma chamada real à OpenAI")
    args = ap.parse_args()

    ok1 = validar_sintaxe()
    ok2 = validar_fallback() if ok1 else False
    ok3 = True
    if args.openai:
        ok3 = testar_openai_real()
    else:
        print("[3/3] Chamada real OpenAI ignorada. Use --openai para testar a chave.")
    print("\nResultado:", "OK" if (ok1 and ok2 and ok3) else "VERIFICAR")
    print("Logs de IA: logs/ia_diagnostico.log e logs/ia_diagnostico.jsonl")
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    raise SystemExit(main())
