from __future__ import annotations

import re
import tkinter as tk
from typing import Any

URL_RE = re.compile(r"https?://[^\s|]+", re.I)


def _is_sitemap(url: str) -> bool:
    return "sitemap" in (url or "").lower()


def _strip_ordem(line: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.\-\|\)]?\s*", "", (line or "").strip()).strip()


def _extract_url(line: str) -> str:
    line = _strip_ordem(line)
    if "|" in line:
        line = line.split("|", 1)[0].strip()
    m = URL_RE.search(line)
    return m.group(0).strip() if m else ""


def _extract_urls(text: str, *, mode: str = "rss") -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    mode = (mode or "rss").lower()
    for line in (text or "").splitlines():
        url = _extract_url(line)
        if not url:
            continue

        is_sitemap = _is_sitemap(url)
        if mode == "rss" and is_sitemap:
            continue
        if mode in {"xml", "sitemap", "xml_sitemap"} and not is_sitemap:
            continue

        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        urls.append(url)
    return urls


class URLPriorityGridV120(tk.Frame):
    """
    Grade de URL com numeração fixa lateral.

    A numeração é desenhada em um Canvas separado e não faz parte do conteúdo.
    O Text da direita contém somente URLs, uma por linha.

    mode='rss': aceita feeds RSS, inclusive feed.xml/rss.xml. Exclui sitemap.
    mode='sitemap': aceita apenas URLs com 'sitemap'.
    """

    def __init__(
        self,
        master: Any,
        *,
        mode: str = "rss",
        bg: str = "#16213e",
        fg: str = "white",
        insertbackground: str = "white",
        font=("Courier New", 9),
        wrap: str = "none",
        relief: str = "flat",
        padx: int = 6,
        pady: int = 6,
        min_lines: int = 80,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, bg=bg)
        self.mode = mode
        self._bg = bg
        self._fg = fg
        self._line_fg = "#8fb7ff"
        self._font = font
        self._min_lines = min_lines
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
        self.gutter.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.text.bind("<ButtonRelease-1>", lambda _e: self._redraw_later(), add="+")
        self.text.bind("<Configure>", lambda _e: self._redraw_later(), add="+")

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
        return max(self._min_lines, raw.count("\n") + 1)

    def _ensure_blank_lines(self) -> None:
        raw = self.text.get("1.0", "end-1c")
        qtd = raw.count("\n") + 1 if raw else 1
        if qtd < self._min_lines:
            self.text.insert("end", "\n" * (self._min_lines - qtd))

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
            urls = _extract_urls(raw, mode=self.mode)
            visual = "\n".join(urls)
            needs_clean = (
                "|" in raw
                or bool(re.search(r"^\s*\d+\s*[\.\-\|\)]", raw, flags=re.M))
                or visual != "\n".join(_extract_urls(raw, mode=self.mode))
            )
            # Também limpa quando o usuário colou conteúdo de outro tipo.
            if needs_clean:
                self.text.delete("1.0", "end")
                if visual:
                    self.text.insert("1.0", visual)
            self._ensure_blank_lines()
            self._redraw_later()
        finally:
            self._normalizing = False

    def get(self, index1: str = "1.0", index2: str = "end", *args: Any) -> str:
        raw = self.text.get(index1, index2, *args)
        return "\n".join(_extract_urls(raw, mode=self.mode))

    def insert(self, index: str, chars: str, *args: Any) -> None:
        chars = chars or ""
        if "|" in chars or re.search(r"^\s*\d+\s*[\.\-\|\)]?\s*https?://", chars, flags=re.M):
            chars = "\n".join(_extract_urls(chars, mode=self.mode))
        else:
            # Em modo sitemap, se vier texto misto, só mostra sitemap.
            if self.mode in {"sitemap", "xml", "xml_sitemap"}:
                extracted = _extract_urls(chars, mode=self.mode)
                chars = "\n".join(extracted)
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
