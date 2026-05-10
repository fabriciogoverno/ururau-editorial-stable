# -*- coding: utf-8 -*-
"""
Orquestrador de treinamento Fase 1 — CORRIGIDO para data/ururau.db
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ururau_ai_auditor.nn_engine.feature_store import FeatureStore
from ururau_ai_auditor.nn_engine.anomaly_ciclo import AnomalyCicloDetector
from ururau_ai_auditor.nn_engine.vector_db import LogVectorDB
from ururau_ai_auditor.nn_engine.vectorizer import LogVectorizer


def main() -> int:
    root = BASE_DIR
    db = root / "sistema" / "data" / "ururau.db"  # BANCO REAL AQUI
    mdir = root / "modelos_ml"
    mdir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("URURAU NEURAL ENGINE — TREINAMENTO FASE 1 (v1.1)")
    print("=" * 60)

    if not db.exists():
        print(f"[ERRO] Banco nao encontrado: {db}")
        return 1

    fs = FeatureStore(db)

    # Ciclos sintéticos
    df_c = fs.extrair_ciclos(1000)
    if not df_c.empty:
        fs.salvar(df_c, "ciclos_features", root)
        print(f"[OK] Ciclos sinteticos: {len(df_c)} janelas")
    else:
        print("[AVISO] Sem dados de pauta para ciclos.")

    # Fontes
    df_f = fs.extrair_fontes(2000)
    if not df_f.empty:
        fs.salvar(df_f, "fontes_features", root)
        print(f"[OK] Fontes: {len(df_f)} fontes distintas")
    else:
        print("[AVISO] Sem dados de fonte.")

    # Publicações
    df_p = fs.extrair_publicacoes(1000)
    if not df_p.empty:
        fs.salvar(df_p, "publicacoes_features", root)
        print(f"[OK] Publicacoes: {len(df_p)} registros")

    # Auditoria
    df_a = fs.extrair_auditoria(1000)
    if not df_a.empty:
        fs.salvar(df_a, "auditoria_features", root)
        print(f"[OK] Auditoria: {len(df_a)} registros")

    # Anomaly Detector
    if len(df_c) >= 10:
        det = AnomalyCicloDetector()
        try:
            det.fit(df_c)
            det.save(mdir / "anomaly_ciclo_v1.pkl")
            print("[OK] Anomaly detector treinado.")
        except Exception as e:
            print(f"[ERRO] Anomaly: {e}")
    else:
        print(f"[PULAR] Anomaly precisa de >=10 ciclos (tem {len(df_c)}).")

    # VectorDB + Vectorizer
    LogVectorDB(root, "ururau_logs")
    print("[OK] VectorDB OK.")
    vec = LogVectorizer()
    vec.save(mdir / "vectorizer_v1")
    print("[OK] Vectorizer OK.")

    print("=" * 60)
    print("CONCLUIDO. Artefatos em modelos_ml/ e dados_ml/")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
