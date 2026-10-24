"""Middle pane: search box + scrollable list of idea cards.

Row widgets are pooled and re-used so live search stays fast even with hundreds of ideas.
"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..config import MAX_LIST_ROWS
from ..database import Idea
from ..utils import one_line, relative_time
from . import theme


class _Row:
    def __init__(self, parent, on_click: Callable[[int], None]):
        self.idea_id: int | None = None
        self.selected = False
        self.frame = ctk.CTkFrame(parent, corner_radius=10, fg_color=theme.ROW_BG)
        self.frame.grid_columnconfigure(0, weight=1)
        self.title = ctk.CTkLabel(self.frame, anchor="w", height=20, font=theme.font(14, "bold"),
                                  text_color=theme.TEXT)
        self.snippet = ctk.CTkLabel(self.frame, anchor="w", height=18, font=theme.font(12),
                                    text_color=theme.MUTED)
        self.meta = ctk.CTkLabel(self.frame, anchor="w", height=16, font=theme.font(11),
                                 text_color=theme.MUTED)
        self.title.grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 0))
        self.snippet.grid(row=1, column=0, sticky="ew", padx=12)
        self.meta.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 9))

        for w in (self.frame, self.title, self.snippet, self.meta):
            w.bind("<Button-1>", lambda _e: self.idea_id is not None and on_click(self.idea_id))
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)

    def fill(self, idea: Idea, selected: bool) -> None:
        self.idea_id = idea.id
        self.title.configure(text=one_line(idea.display_title, 38))
        self.snippet.configure(text=one_line(idea.content, 52) or "No content yet")
        meta = f"{idea.category}  ·  {relative_time(idea.updated_at)}"
        if idea.tag_list:
            meta += "  ·  " + " ".join(f"#{t}" for t in idea.tag_list[:3])
        self.meta.configure(text=one_line(meta, 58))
        self.set_selected(selected)

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.frame.configure(fg_color=theme.ROW_SELECTED if selected else theme.ROW_BG)

    def _enter(self, _e=None) -> None:
        if not self.selected:
            self.frame.configure(fg_color=theme.ROW_HOVER)

    def _leave(self, _e=None) -> None:
        # Leaving the card for one of its own labels shouldn't clear the hover.
        x, y = self.frame.winfo_pointerxy()
        under = self.frame.winfo_containing(x, y)
        if under is not None and str(under).startswith(str(self.frame)):
            return
        if not self.selected:
            self.frame.configure(fg_color=theme.ROW_BG)


class IdeaList(ctk.CTkFrame):
    def __init__(self, master, *, on_select: Callable[[int], None], on_search: Callable[[str], None]):
        super().__init__(master, width=330, corner_radius=0, fg_color=theme.LIST_BG)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._on_select = on_select
        self._rows: list[_Row] = []
        self._ids: list[int] = []
        self._selected_id: int | None = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 8))
        header.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(header, text="All Ideas", anchor="w", font=theme.font(18, "bold"),
                                    text_color=theme.TEXT)
        self.heading.grid(row=0, column=0, sticky="w")
        self.count_label = ctk.CTkLabel(header, text="", anchor="e", font=theme.font(12), text_color=theme.MUTED)
        self.count_label.grid(row=0, column=1, sticky="e")

        self.search = ctk.CTkEntry(self, height=36, corner_radius=10, font=theme.font(13),
                                   placeholder_text="Search title, content or #tag   (Ctrl+F)")
        self.search.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.search.bind("<KeyRelease>", lambda _e: on_search(self.search.get()))
        self.search.bind("<Escape>", lambda _e: self.clear_search(notify=True, on_search=on_search))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=(8, 2), pady=(0, 8))
        self.scroll.grid_columnconfigure(0, weight=1)

        self.empty_label = ctk.CTkLabel(self.scroll, text="", font=theme.font(13), text_color=theme.MUTED,
                                        justify="center", wraplength=260)
        self.more_label = ctk.CTkLabel(self.scroll, text="", font=theme.font(11), text_color=theme.MUTED)

    # ------------------------------------------------------------------ public API
    def set_heading(self, text: str) -> None:
        self.heading.configure(text=text)

    def clear_search(self, notify: bool = False, on_search: Callable[[str], None] | None = None) -> None:
        self.search.delete(0, "end")
        if notify and on_search:
            on_search("")

    def focus_search(self) -> None:
        self.search.focus_set()
        self.search.select_range(0, "end")

    def set_ideas(self, ideas: list[Idea], selected_id: int | None, total: int, query: str,
                  scroll_top: bool = False) -> None:
        self._selected_id = selected_id
        shown = ideas[:MAX_LIST_ROWS]
        self._ids = [i.id for i in shown]
        while len(self._rows) < len(shown):
            self._rows.append(_Row(self.scroll, self._on_select))

        for idx, row in enumerate(self._rows):
            if idx < len(shown):
                row.fill(shown[idx], shown[idx].id == selected_id)
                row.frame.grid(row=idx, column=0, sticky="ew", padx=4, pady=3)
            else:
                row.idea_id = None
                row.frame.grid_remove()

        self.count_label.configure(text=f"{total} idea{'s' if total != 1 else ''}")
        if not shown:
            self.empty_label.configure(
                text=f"No ideas match “{query.strip()}”." if query.strip()
                else "Nothing here yet.\nPress Ctrl+N to capture your first idea.")
            self.empty_label.grid(row=0, column=0, pady=40)
        else:
            self.empty_label.grid_remove()
        if total > len(shown):
            self.more_label.configure(text=f"Showing {len(shown)} of {total} — refine your search to see more.")
            self.more_label.grid(row=len(shown), column=0, pady=8)
        else:
            self.more_label.grid_remove()
        if scroll_top:
            self.scroll._parent_canvas.yview_moveto(0)

    def highlight(self, selected_id: int | None) -> None:
        self._selected_id = selected_id
        for row in self._rows:
            if row.idea_id is not None:
                row.set_selected(row.idea_id == selected_id)

    @property
    def visible_ids(self) -> list[int]:
        return list(self._ids)
