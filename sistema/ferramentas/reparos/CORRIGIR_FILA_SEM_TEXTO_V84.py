"""Marca como bloqueadas pautas antigas que entraram na fila sem texto de fonte."""
from __future__ import annotations
import json
from datetime import datetime
from ururau.core.database import Database
from ururau.config.settings import ARQUIVO_DB
from ururau.coleta.fail_closed_v84 import tem_texto_util_prevalidado_v84

STATUS_ALVO = {"captada", "triada", "aprovada", "em_redacao", "revisada", "pronta"}

def main():
    db = Database(ARQUIVO_DB)
    conn = db._conectar()
    total = 0
    bloqueadas = 0
    try:
        rows = conn.execute("SELECT uid, status, dados_json, titulo_origem FROM pautas").fetchall()
        for row in rows:
            status = row["status"] or ""
            if status not in STATUS_ALVO:
                continue
            total += 1
            try:
                dados = json.loads(row["dados_json"] or "{}")
            except Exception:
                dados = {}
            if tem_texto_util_prevalidado_v84(dados):
                continue
            dados["status"] = "bloqueada"
            dados["bloqueio_coleta_v84"] = True
            dados["motivo_bloqueio_coleta_v84"] = "fila antiga sem texto útil da fonte"
            dados["status_validacao"] = "erro_extracao"
            dados["status_publicacao_sugerido"] = "bloquear_total"
            conn.execute(
                "UPDATE pautas SET status='bloqueada', atualizada_em=?, dados_json=? WHERE uid=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(dados, ensure_ascii=False, default=str), row["uid"]),
            )
            bloqueadas += 1
        conn.commit()
    finally:
        conn.close()
    print(f"V84_LIMPEZA_FILA_OK: analisadas={total} bloqueadas_sem_texto={bloqueadas}")

if __name__ == "__main__":
    main()
