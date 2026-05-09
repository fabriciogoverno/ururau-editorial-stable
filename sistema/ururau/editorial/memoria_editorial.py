"""
ururau.editorial.memoria_editorial — v74
Memória editorial local do Ururau.

Armazena padrões de títulos, tags, decisões de canal e assinaturas semânticas
para melhorar consistência e detectar repetição sem depender de API externa.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEMORY_PATH = Path("data/memoria_editorial_ururau.json")


def _norm(text: str) -> str:
    text = (text or "").lower()
    repl = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    text = text.translate(repl)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    stop = {"de","da","do","das","dos","em","no","na","nos","nas","para","por","com","sem","que","e","o","a","os","as","um","uma","ao","aos","sobre","nesta","neste","novo","nova"}
    return {t for t in _norm(text).split() if len(t) > 2 and t not in stop}


def assinatura(text: str, limit: int = 18) -> list[str]:
    toks = sorted(tokens(text))
    return toks[:limit]


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


@dataclass
class MemoryItem:
    titulo: str
    canal: str
    article_type: str
    link: str = ""
    fonte: str = ""
    slug: str = ""
    tags: list[str] | None = None
    signature: list[str] | None = None
    created_at: str = ""


class EditorialMemory:
    def __init__(self, path: Path | str = MEMORY_PATH):
        self.path = Path(path)
        self.items: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.items = list(data.get("items", []))[-1000:]
            else:
                self.items = []
        except Exception:
            self.items = []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "v74", "updated_at": datetime.now(timezone.utc).isoformat(), "items": self.items[-1000:]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, titulo: str, canal: str, article_type: str, link: str = "", fonte: str = "", slug: str = "", tags: list[str] | None = None, texto: str = "") -> None:
        if not titulo:
            return
        sig_text = " ".join([titulo or "", texto or "", link or ""])
        item = MemoryItem(
            titulo=titulo, canal=canal, article_type=article_type, link=link, fonte=fonte, slug=slug,
            tags=tags or [], signature=assinatura(sig_text), created_at=datetime.now(timezone.utc).isoformat()
        )
        # evita gravar exatamente o mesmo link/título várias vezes
        nt = _norm(titulo)
        for old in self.items[-120:]:
            if link and old.get("link") == link:
                return
            if _norm(old.get("titulo", "")) == nt:
                return
        self.items.append(asdict(item))
        self.save()

    def similaridade_recente(self, titulo: str, texto: str = "", janela: int = 250) -> tuple[float, dict[str, Any] | None]:
        sig = tokens(" ".join([titulo or "", texto or ""]))
        best = 0.0
        best_item = None
        for item in self.items[-janela:]:
            old = set(item.get("signature") or []) | tokens(item.get("titulo", ""))
            score = jaccard(sig, old)
            if score > best:
                best = score
                best_item = item
        return best, best_item


def carregar_memoria() -> EditorialMemory:
    return EditorialMemory()


def registrar_materia_na_memoria(materia: Any, article_type: str = "") -> None:
    try:
        tags = getattr(materia, "tags", "") or ""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if isinstance(tags, str) else list(tags or [])
        carregar_memoria().add(
            titulo=getattr(materia, "titulo", "") or "",
            canal=getattr(materia, "canal", "") or getattr(materia, "retranca", "") or "",
            article_type=article_type,
            link=getattr(materia, "link_origem", "") or "",
            fonte=getattr(materia, "fonte_nome", "") or "",
            slug=getattr(materia, "slug", "") or "",
            tags=tag_list,
            texto=getattr(materia, "conteudo", "") or "",
        )
    except Exception as exc:
        print(f"[MEMORIA v74] Falha ao registrar: {exc}")
