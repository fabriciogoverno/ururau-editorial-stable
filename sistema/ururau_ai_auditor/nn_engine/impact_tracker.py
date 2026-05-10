# -*- coding: utf-8 -*-
"""
Mede o impacto de patches aplicados comparando métricas antes/depois.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Union


class ImpactTracker:
    """Rastreia métricas de desempenho 24h apos aplicar patch."""

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self._path = self.root / "dados_ml" / "impact_tracker.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._registros: List[Dict] = []
        self._load()

    def _load(self):
        if self._path.exists():
            self._registros = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self):
        self._path.write_text(json.dumps(self._registros[-100:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _extrair_metricas(self, db_path: Path) -> Dict[str, float]:
        """Extrai métricas atuais do banco."""
        if not db_path.exists():
            return {}
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # Pautas nas últimas 24h
            cur.execute("SELECT COUNT(*), AVG(score_editorial), SUM(urgente) FROM pautas WHERE captada_em > datetime('now', '-1 day')")
            row = cur.fetchone()
            metricas = {
                "pautas_24h": row[0] or 0,
                "avg_score_24h": row[1] or 0,
                "urgentes_24h": row[2] or 0,
            }

            # Publicações nas últimas 24h
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN status='publicada' THEN 1 ELSE 0 END), AVG(tentativa) FROM publicacoes WHERE publicada_em > datetime('now', '-1 day')")
            row = cur.fetchone()
            metricas["publicacoes_24h"] = row[0] or 0
            metricas["taxa_sucesso_pub_24h"] = (row[1] or 0) / max(row[0] or 1, 1)
            metricas["avg_tentativas_24h"] = row[2] or 0

            # Erros nas últimas 24h
            cur.execute("SELECT COUNT(*) FROM auditoria WHERE timestamp > datetime('now', '-1 day') AND sucesso=0")
            metricas["erros_24h"] = cur.fetchone()[0] or 0

            conn.close()
            return metricas
        except Exception:
            return {}

    def registrar_baseline(self, patch_id: str, descricao: str):
        """Registrar métricas ANTES de aplicar patch."""
        db = self.root / "sistema" / "data" / "ururau.db"
        metricas = self._extrair_metricas(db)
        self._registros.append({
            "patch_id": patch_id,
            "descricao": descricao,
            "fase": "baseline",
            "timestamp": None,  # preenchido no fechamento
            "metricas": metricas
        })
        self._save()

    def registrar_fechamento(self, patch_id: str) -> Dict:
        """Registrar métricas DEPOIS de 24h e calcular delta."""
        db = self.root / "sistema" / "data" / "ururau.db"
        metricas_pos = self._extrair_metricas(db)

        # Encontra baseline
        baseline = None
        for r in reversed(self._registros):
            if r["patch_id"] == patch_id and r["fase"] == "baseline":
                baseline = r
                break

        if baseline is None:
            return {"erro": "Baseline nao encontrado"}

        metricas_pre = baseline["metricas"]
        delta = {}
        for k in metricas_pos:
            pre = metricas_pre.get(k, 0)
            pos = metricas_pos[k]
            if pre != 0:
                delta[k] = round((pos - pre) / pre * 100, 2)
            else:
                delta[k] = round(pos * 100, 2)

        resultado = {
            "patch_id": patch_id,
            "fase": "fechamento",
            "metricas_pre": metricas_pre,
            "metricas_pos": metricas_pos,
            "delta_percent": delta,
            "melhorou": sum(1 for d in delta.values() if d > 0) > sum(1 for d in delta.values() if d < 0)
        }
        self._registros.append(resultado)
        self._save()
        return resultado

    def get_historico(self, patch_id: str = None) -> List[Dict]:
        if patch_id:
            return [r for r in self._registros if r.get("patch_id") == patch_id]
        return self._registros
