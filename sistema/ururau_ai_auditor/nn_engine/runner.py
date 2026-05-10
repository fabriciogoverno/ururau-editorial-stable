# -*- coding: utf-8 -*-
"""
Orquestrador da Fase 1 Neural.
Treina modelos, gera relatório e salva artefatos.
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
    db_path = root / "sistema" / "ururau.db"
    modelos_dir = root / "modelos_ml"
    modelos_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("URURAU NEURAL ENGINE — FASE 1: TREINAMENTO")
    print("=" * 60)

    # 1. Feature Store
    fs = FeatureStore(db_path)
    df_ciclos = fs.extrair_ciclos(limit=1000)
    df_fontes = fs.extrair_fontes(limit=2000)

    if not df_ciclos.empty:
        fs.salvar(df_ciclos, "ciclos_features", root)
        print(f"[OK] Features de ciclos: {len(df_ciclos)} registros")
    else:
        print("[AVISO] Nenhum dado de ciclo encontrado. Modelo de anomalia não será treinado.")

    if not df_fontes.empty:
        fs.salvar(df_fontes, "fontes_features", root)
        print(f"[OK] Features de fontes: {len(df_fontes)} registros")
    else:
        print("[AVISO] Nenhum dado de fonte encontrado.")

    # 2. Anomaly Detector
    if len(df_ciclos) >= 10:
        detector = AnomalyCicloDetector()
        try:
            detector.fit(df_ciclos)
            detector.save(modelos_dir / "anomaly_ciclo_v1.pkl")
            print("[OK] AnomalyCicloDetector treinado e salvo.")
        except Exception as e:
            print(f"[ERRO] Falha no treino do anomaly detector: {e}")
    else:
        print("[PULAR] AnomalyCicloDetector precisa de >= 10 ciclos.")

    # 3. VectorDB (inicializa vazia, pronta para receber logs)
    vdb = LogVectorDB(root, collection_name="ururau_logs")
    print("[OK] VectorDB inicializado.")

    # 4. Vectorizer
    vec = LogVectorizer()
    vec.save(modelos_dir / "vectorizer_v1")
    print("[OK] Vectorizer inicializado e salvo.")

    print("=" * 60)
    print("TREINAMENTO CONCLUÍDO. Artefatos em: modelos_ml/")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
