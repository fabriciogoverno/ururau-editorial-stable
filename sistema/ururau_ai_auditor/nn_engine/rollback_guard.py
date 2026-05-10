# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Dict, Union
from .impact_tracker import ImpactTracker

class RollbackGuard:
    THRESHOLD_PIORA = -15.0

    def __init__(self, root="."):
        self.root = Path(root)
        self.backup_dir = self.root / "sandbox_ml" / "backups_pre_patch"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = ImpactTracker(root)
        self._log_path = self.root / "dados_ml" / "rollback_log.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def backup_arquivo(self, filepath, patch_id):
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo nao existe: {path}")
        bak = self.backup_dir / f"{patch_id}_{path.name}.bak"
        shutil.copy2(path, bak)
        return bak

    def aplicar_patch(self, filepath, patch, patch_id):
        path = Path(filepath)
        bak = self.backup_arquivo(path, patch_id)
        self.tracker.registrar_baseline(patch_id, patch.get("explicacao", ""))
        path.write_text(patch["patched"], encoding="utf-8")
        return {"patch_id": patch_id, "arquivo": str(path), "backup": str(bak), "status": "aplicado", "aguardar_fechamento": "Rode rollback_guard.fechar(patch_id) apos 24h"}

    def fechar(self, patch_id):
        resultado = self.tracker.registrar_fechamento(patch_id)
        if "erro" in resultado:
            return resultado
        delta = resultado.get("delta_percent", {})
        chaves_criticas = ["taxa_sucesso_pub_24h", "pautas_24h", "publicacoes_24h"]
        piorou = any(delta.get(k, 0) < self.THRESHOLD_PIORA for k in chaves_criticas)
        if piorou:
            bak = self._find_backup(patch_id)
            if bak:
                arquivo = self._find_arquivo_from_backup(bak)
                if arquivo:
                    shutil.copy2(bak, arquivo)
                    self._log(patch_id, "ROLLBACK_EXECUTADO", f"Piora detectada: {delta}")
                    return {"patch_id": patch_id, "acao": "ROLLBACK", "motivo": f"Piora > {self.THRESHOLD_PIORA}%", "delta": delta}
        self._log(patch_id, "PATCH_MANTIDO", f"Delta: {delta}")
        return {"patch_id": patch_id, "acao": "MANTIDO", "delta": delta}

    def _find_backup(self, patch_id):
        for f in self.backup_dir.glob(f"{patch_id}_*.bak"):
            return f
        return None

    def _find_arquivo_from_backup(self, bak):
        nome = bak.stem.replace(bak.stem.split("_")[0] + "_", "")
        for py in self.root.rglob(nome + ".py"):
            return py
        return None

    def _log(self, patch_id, acao, detalhe):
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"patch_id": patch_id, "acao": acao, "detalhe": detalhe}, ensure_ascii=False) + "\n")
