# -*- coding: utf-8 -*-
"""
Neural Service — Cerebro autonomo do ecossistema Ururau.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ururau_ai_auditor.nn_engine.feature_store import FeatureStore
from ururau_ai_auditor.nn_engine.anomaly_ciclo import AnomalyCicloDetector
from ururau_ai_auditor.nn_engine.fonte_bandit import FonteBandit
from ururau_ai_auditor.nn_engine.intervalo_optimizer import IntervaloOptimizer
from ururau_ai_auditor.nn_engine.score_adaptive import ScoreAdaptive
from ururau_ai_auditor.nn_engine.patch_generator import PatchGenerator
from ururau_ai_auditor.nn_engine.sandbox_ml import SandboxML
from ururau_ai_auditor.nn_engine.rollback_guard import RollbackGuard
from ururau_ai_auditor.nn_engine.long_term_memory import LongTermMemory
from ururau_ai_auditor.nn_engine.vector_db import LogVectorDB
from ururau_ai_auditor.nn_engine.vectorizer import LogVectorizer
from ururau_ai_auditor.scanner_codigo import escanear


class NeuralService:
    _instance = None
    _lock = threading.Lock()

    INTERVALO_TREINO = 3600
    INTERVALO_REPARO = 1800
    INTERVALO_OTIMIZACAO = 600
    INTERVALO_FECHAMENTO = 86400

    def __new__(cls, root=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, root=None):
        if self._initialized:
            return
        if root is None:
            root = Path(__file__).resolve().parents[1]
        self.root = Path(root)
        self.db_path = self.root / "sistema" / "data" / "ururau.db"
        self.modelos_dir = self.root / "modelos_ml"
        self.modelos_dir.mkdir(parents=True, exist_ok=True)

        self.feature_store = FeatureStore(self.db_path)
        self.bandit = FonteBandit(self.root)
        self.intervalo_opt = IntervaloOptimizer(self.root)
        self.score_adaptive = ScoreAdaptive(self.root)
        self.patch_gen = PatchGenerator()
        self.sandbox = SandboxML(self.root)
        self.guard = RollbackGuard(self.root)
        self.memory = LongTermMemory(self.root)
        self.vector_db = LogVectorDB(self.root)
        self.vectorizer = LogVectorizer()

        self._running = False
        self._thread = None
        self._last_treino = 0
        self._last_reparo = 0
        self._last_otimizacao = 0
        self._last_fechamento = 0
        self._stats = {"ciclos": 0, "erros": 0, "patches": 0, "anomalias": 0}
        self._initialized = True

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="NeuralService")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def is_running(self):
        return self._running and self._thread is not None and self._thread.is_alive()

    def status(self):
        return {
            "running": self.is_running(),
            "stats": self._stats.copy(),
            "score_threshold": self.score_adaptive.get_threshold(),
            "intervalo_segundos": self.intervalo_opt.get_intervalo(),
            "fontes_rank": self.bandit.rank(self._get_fontes_ativas())[:5] if self._get_fontes_ativas() else [],
        }

    def _loop(self):
        while self._running:
            agora = time.time()
            if agora - self._last_treino > self.INTERVALO_TREINO:
                self._executar_treino()
                self._last_treino = agora
            if agora - self._last_reparo > self.INTERVALO_REPARO:
                self._executar_reparo()
                self._last_reparo = agora
            if agora - self._last_otimizacao > self.INTERVALO_OTIMIZACAO:
                self._executar_otimizacao()
                self._last_otimizacao = agora
            if agora - self._last_fechamento > self.INTERVALO_FECHAMENTO:
                self._executar_fechamento()
                self._last_fechamento = agora
            time.sleep(30)

    def _executar_treino(self):
        try:
            df_c = self.feature_store.extrair_ciclos(1000)
            if len(df_c) >= 10:
                det = AnomalyCicloDetector()
                det.fit(df_c)
                det.save(self.modelos_dir / "anomaly_ciclo_v1.pkl")
                self._stats["ciclos"] += 1
        except Exception as e:
            self._log("treino", str(e))

    def _executar_reparo(self):
        try:
            resultados = escanear(str(self.root / "sistema"))
            sintaxe = []
            for r in resultados:
                for erro in r.get("erros", []):
                    if "SyntaxError" in erro:
                        sintaxe.append({"arquivo": str(self.root / "sistema" / r["caminho"]), "caminho_rel": r["caminho"], "mensagem": erro})
            if sintaxe:
                erro = sintaxe[0]
                patch = self.patch_gen.generate_for_syntax_error(erro["arquivo"], erro["mensagem"], "")
                if patch:
                    laudo = self.sandbox.validar_patch(erro["arquivo"], patch)
                    if laudo["aprovado"]:
                        safe = erro["caminho_rel"].replace("/", "_").replace("\\", "_").replace(":", "_")
                        pid = "patch_" + safe + "_" + str(int(time.time()))
                        self.guard.aplicar_patch(erro["arquivo"], patch, pid)
                        self.memory.adicionar(erro["mensagem"], patch["patched"], "aplicado", erro["arquivo"], pid)
                        self._stats["patches"] += 1
        except Exception as e:
            self._log("reparo", str(e))

    def _executar_otimizacao(self):
        pass

    def _executar_fechamento(self):
        try:
            from ururau_ai_auditor.nn_engine.impact_tracker import ImpactTracker
            t = ImpactTracker(self.root)
            historico = t.get_historico()
            for r in historico:
                if r.get("fase") == "baseline":
                    ja = any(x.get("fase") == "fechamento" and x.get("patch_id") == r["patch_id"] for x in historico)
                    if not ja:
                        self.guard.fechar(r["patch_id"])
        except Exception as e:
            self._log("fechamento", str(e))

    def _log(self, acao, detalhe):
        log_path = self.root / "dados_ml" / "neural_service.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "acao": acao, "detalhe": detalhe}, ensure_ascii=False) + "\n")

    def _get_fontes_ativas(self):
        try:
            df = self.feature_store.extrair_fontes(50)
            return df["dominio"].tolist() if not df.empty else []
        except Exception:
            return []

    def registrar_ciclo(self, fontes_coletadas, materias_geradas, erros, duracao):
        self.intervalo_opt.registrar(materias_geradas > 0, materias_geradas)
        self._stats["ciclos"] += 1

    def registrar_pauta(self, fonte, score, aprovada):
        self.bandit.update(fonte, aprovada)
        self.score_adaptive.registrar(score, aprovada)

    def registrar_publicacao(self, sucesso, tentativas=1):
        pass

    def registrar_erro(self, texto_erro, severidade="MEDIO"):
        self.vector_db.add([texto_erro], [{"severidade": severidade}])
        self._stats["erros"] += 1

    def avaliar_fonte(self, fonte):
        rank = self.bandit.rank([fonte])
        if rank:
            return rank[0]
        return {"fonte": fonte, "expected_reward": 0.5, "alpha": 1.0, "beta": 1.0}

    def get_intervalo_recomendado(self):
        return self.intervalo_opt.get_intervalo()

    def get_score_threshold(self):
        return self.score_adaptive.get_threshold()

    def get_anomaly_detector(self):
        pkl = self.modelos_dir / "anomaly_ciclo_v1.pkl"
        if pkl.exists():
            det = AnomalyCicloDetector()
            det.load(pkl)
            return det
        return None


_neural = None

def get_neural(root=None):
    global _neural
    if _neural is None:
        _neural = NeuralService(root)
    return _neural
