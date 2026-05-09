from __future__ import annotations

import os
import re
import tkinter as tk
from pathlib import Path
from typing import Any

URL_RE = re.compile(r"https?://[^\s|]+", re.I)


def _is_xml(url: str) -> bool:
    low = (url or "").lower().strip()
    return "sitemap" in low


def _strip_ordem(line: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.\-\|\)]?\s*", "", (line or "").strip()).strip()


def _extract_url(line: str) -> str:
    line = _strip_ordem(line)
    if "|" in line:
        line = line.split("|", 1)[0].strip()
    m = URL_RE.search(line)
    return m.group(0).strip() if m else ""


def _extract_urls(text: str, *, include_xml: bool = False) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        url = _extract_url(line)
        if not url:
            continue
        if _is_xml(url) and not include_xml:
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        urls.append(url)
    return urls


def _extract_xmls(text: str) -> list[str]:
    return [u for u in _extract_urls(text, include_xml=True) if _is_xml(u)]


def _register_xmls(text: str) -> None:
    xmls = _extract_xmls(text)
    if not xmls:
        return
    try:
        path = Path(os.getenv("URURAU_XML_SITEMAP_CONFIG", "fontes_xml_sitemap_vfinal.txt"))
        atuais = []
        if path.exists():
            atuais = [x.strip() for x in path.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
        vistos = {x.rstrip("/") for x in atuais}
        mudou = False
        for url in xmls:
            key = url.rstrip("/")
            if key not in vistos:
                atuais.append(url)
                vistos.add(key)
                mudou = True
        if mudou:
            path.write_text("\n".join(atuais) + "\n", encoding="utf-8")
            print(f"[CONFIG_V119] XML/Sitemap registrado em {path}: {len(xmls)} link(s)")
    except Exception as exc:
        print(f"[CONFIG_V119][AVISO] falha ao salvar XML/Sitemap: {exc}")


class RSSUrlGrid(tk.Frame):
    """
    Campo visual para Fontes RSS.

    A numeração fica em Canvas próprio, à esquerda, e não faz parte do texto.
    A área editável contém apenas URLs. O objeto expõe get/insert/delete para
    continuar compatível com o código antigo que usava tk.Text.
    """

    def __init__(self, master: Any, *, bg: str = "#16213e", fg: str = "white",
                 insertbackground: str = "white", font=("Courier New", 9),
                 wrap: str = "none", relief: str = "flat", padx: int = 6,
                 pady: int = 6, **kwargs: Any) -> None:
        super().__init__(master, bg=bg)
        self._bg = bg
        self._fg = fg
        self._line_fg = "#8fb7ff"
        self._font = font
        self._normalizing = False

        self.gutter = tk.Canvas(self, width=54, bg="#10203f", highlightthickness=0, bd=0)
        self.gutter.pack(side="left", fill="y")

        self.text = tk.Text(
            self,
            bg=bg,
            fg=fg,
            insertbackground=insertbackground,
            font=font,
            wrap=wrap,
            relief=relief,
            padx=padx,
            pady=pady,
            undo=True,
        )
        self.text.pack(side="left", fill="both", expand=True)

        self._wire_events()
        self.after(100, self._refresh_all)

    def _wire_events(self) -> None:
        self.text.bind("<KeyRelease>", lambda _e: self._redraw_later(), add="+")
        self.text.bind("<<Paste>>", lambda _e: self.after(80, self.normalize_visible), add="+")
        self.text.bind("<FocusOut>", lambda _e: self.normalize_visible(), add="+")
        self.text.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.text.bind("<ButtonRelease-1>", lambda _e: self._redraw_later(), add="+")
        self.text.bind("<Configure>", lambda _e: self._redraw_later(), add="+")
        self.gutter.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event: Any) -> str:
        try:
            self.text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            self._redraw_later()
            return "break"
        except Exception:
            return ""

    def _redraw_later(self) -> None:
        self.after_idle(self._redraw_numbers)

    def _line_count(self) -> int:
        raw = self.text.get("1.0", "end-1c")
        return max(80, raw.count("\n") + 1)

    def _ensure_blank_lines(self, min_lines: int = 80) -> None:
        raw = self.text.get("1.0", "end-1c")
        qtd = raw.count("\n") + 1 if raw else 1
        if qtd < min_lines:
            self.text.insert("end", "\n" * (min_lines - qtd))

    def _redraw_numbers(self) -> None:
        self.gutter.delete("all")
        total = self._line_count()
        for i in range(1, total + 1):
            info = self.text.dlineinfo(f"{i}.0")
            if info is None:
                continue
            y = info[1]
            self.gutter.create_text(44, y + 8, text=str(i), fill=self._line_fg,
                                    anchor="e", font=self._font)

    def _refresh_all(self) -> None:
        self._ensure_blank_lines()
        self._redraw_numbers()

    def normalize_visible(self) -> None:
        if self._normalizing:
            return
        self._normalizing = True
        try:
            raw = self.text.get("1.0", "end-1c")
            _register_xmls(raw)
            urls = _extract_urls(raw)
            visual = "\n".join(urls)
            precisa_limpar = "|" in raw or bool(re.search(r"^\s*\d+\s*[\.\-\|\)]", raw, flags=re.M)) or any(_is_xml(u) for u in _extract_urls(raw, include_xml=True))
            if precisa_limpar:
                self.text.delete("1.0", "end")
                if visual:
                    self.text.insert("1.0", visual)
            self._ensure_blank_lines()
            self._redraw_later()
        finally:
            self._normalizing = False

    def get(self, index1: str = "1.0", index2: str = "end", *args: Any) -> str:
        raw = self.text.get(index1, index2, *args)
        _register_xmls(raw)
        return "\n".join(_extract_urls(raw))

    def insert(self, index: str, chars: str, *args: Any) -> None:
        # Se veio de carregamento do sistema com formato antigo/visual numerado, mostra só URL.
        if "|" in (chars or "") or re.search(r"^\s*\d+\s*[\.\-\|\)]?\s*https?://", chars or "", flags=re.M):
            urls = _extract_urls(chars)
            chars = "\n".join(urls)
        self.text.insert(index, chars, *args)
        self.after(50, self._refresh_all)

    def delete(self, index1: str, index2: str | None = None) -> None:
        self.text.delete(index1, index2)
        self.after(50, self._refresh_all)

    def add_blank_url_line(self) -> None:
        raw = self.text.get("1.0", "end-1c")
        if raw and not raw.endswith("\n"):
            self.text.insert("end", "\n")
        self.text.insert("end", "https://")
        self.text.focus_set()
        self.after(50, self._refresh_all)

    def focus_set(self) -> None:  # type: ignore[override]
        self.text.focus_set()
