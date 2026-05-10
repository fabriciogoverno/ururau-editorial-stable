# -*- coding: utf-8 -*-
"""
Guarda de reversão inteligente.
Se métricas pioram > threshold após patch, reverte automaticamente.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Union

from .impact_tracker import ImpactTracker


class RollbackGuard:
    """Monitora patches e reverte se impacto for negativo."""

    THRESHOLD_PIORA = -15.0  # piora > 15% em qualquer métrica chave dispara rollback

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self.backup_dir = self.root / "sandbox_ml" / "backups_pre_patch"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = ImpactTracker(root)
        self._log_path = self.root / "dados_ml" / "rollback_log.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def backup_arquivo(self, filepath: Union[str, Path], patch_id: str) -> Path:
        """Cria backup .bak antes de aplicar patch."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo nao existe: {path}")
        bak = self.backup_dir / f"{patch_id}_{path.name}.bak"
        shutil.copy2(path, bak)
        return bak

    def aplicar_patch(self, filepath: Union[str, Path], patch: Dict[str, str], patch_id: str) -> Dict:
        """Aplica patch no arquivo real, registra baseline, retorna laudo."""
        path = Path(filepath)

        # 1. Backup
        bak = self.backup_arquivo(path, patch_id)

        # 2. Baseline
        self.tracker.registrar_baseline(patch_id, patch.get("explicacao", ""))

        # 3. Aplica
        path.write_text(patch["patched"], encoding="utf-8")

        return {
            "patch_id": patch_id,
            "arquivo": str(path),
            "backup": str(bak),
            "status": "aplicado",
            "aguardar_fechamento": "Rode rollback_guard.fechar(patch_id) apos 24h"
        }

    def fechar(self, patch_id: str) -> Dict:
        """Fecha ciclo de 24h. Se piorou, reverte."""
        resultado = self.tracker.registrar_fechamento(patch_id)

        if "erro" in resultado:
            return resultado

        delta = resultado.get("delta_percent", {})
        chaves_criticas = ["taxa_sucesso_pub_24h", "pautas_24h", "publicacoes_24h"]
        piorou = any(delta.get(k, 0) < self.THRESHOLD_PIORA for k in chaves_criticas)

        if piorou:
            # Reverte
            bak = self._find_backup(patch_id)
            if bak:
                arquivo = self._find_arquivo_from_backup(bak)
                if arquivo:
                    shutil.copy2(bak, arquivo)
                    self._log(patch_id, "ROLLBACK_EXECUTADO", f"Piora detectada: {delta}")
                    return {"patch_id": patch_id, "acao": "ROLLBACK", "motivo": f"Piora > {self.THRESHOLD_PIORA}%", "delta": delta}

        self._log(patch_id, "PATCH_MANTIDO", f"Delta: {delta}")
        return {"patch_id": patch_id, "acao": "MANTIDO", "delta": delta}

    def _find_backup(self, patch_id: str) -> Path | None:
        for f in self.backup_dir.glob(f"{patch_id}_*.bak"):
            return f
        return None

    def _find_arquivo_from_backup(self, bak: Path) -> Path | None:
        # Extrai nome original: {patch_id}_{nome}.bak
        nome = bak.stem.replace(bak.stem.split("_")[0] + "_", "")
        # Procura no projeto
        for py in self.root.rglob(nome + ".py"):
            return py
        return None

    def _log(self, patch_id: str, acao: str, detalhe: str):
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"patch_id": patch_id, "acao": acao, "detalhe": detalhe}, ensure_ascii=False) + "
")
