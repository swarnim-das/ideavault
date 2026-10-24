"""Right pane: title, category, tags and a Markdown-friendly body editor."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..config import CATEGORIES
from ..database import Idea
from ..utils import format_timestamp
from . import theme


class Editor(ctk.CTkFrame):
    def __init__(self, master, *, on_change: Callable[[bool], None], on_delete: Callable[[], None]):
        """on_change(immediate) is called whenever the user edits a field;
        immediate=True for discrete changes (category) that should save right away."""
        super().__init__(master, corner_radius=0, fg_color=theme.EDITOR_BG)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._on_change = on_change
        self._loading = False
        self._snapshot: dict[str, str] = {}

        # ---------------- empty state
        self.empty = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.empty, text="✦", font=theme.font(44), text_color=theme.ACCENT).pack(pady=(0, 6))
        ctk.CTkLabel(self.empty, text="Select an idea, or press Ctrl+N to start a new one.",
                     font=theme.font(14), text_color=theme.MUTED).pack()

        # ---------------- edit form
        self.form = ctk.CTkFrame(self, fg_color="transparent")
        self.form.grid_columnconfigure(0, weight=1)
        self.form.grid_rowconfigure(2, weight=1)

        self.title_entry = ctk.CTkEntry(self.form, height=48, border_width=0, fg_color="transparent",
                                        font=theme.font(24, "bold"), placeholder_text="Untitled idea")
        self.title_entry.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 4))

        bar = ctk.CTkFrame(self.form, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))
        bar.grid_columnconfigure(1, weight=1)
        self.category = ctk.CTkOptionMenu(bar, values=CATEGORIES, width=140, height=32, font=theme.font(13),
                                          dynamic_resizing=False, command=lambda _v: self._changed(True))
        self.category.grid(row=0, column=0, sticky="w")
        self.tags_entry = ctk.CTkEntry(bar, height=32, font=theme.font(13),
                                       placeholder_text="Tags, comma separated — e.g. python, ui, someday")
        self.tags_entry.grid(row=0, column=1, sticky="ew", padx=10)
        self.delete_btn = ctk.CTkButton(bar, text="✕  Delete", width=96, height=32, font=theme.font(13),
                                        fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER, command=on_delete)
        self.delete_btn.grid(row=0, column=2, sticky="e")

        self.body = ctk.CTkTextbox(self.form, wrap="word", undo=True, autoseparators=True, maxundo=-1,
                                   font=theme.font(14, mono=True), corner_radius=10, border_spacing=12,
                                   activate_scrollbars=True)
        self.body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))

        footer = ctk.CTkFrame(self.form, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=26, pady=(0, 14))
        footer.grid_columnconfigure(1, weight=1)
        self.status = ctk.CTkLabel(footer, text="", font=theme.font(12), text_color=theme.MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="w")
        self.stamps = ctk.CTkLabel(footer, text="", font=theme.font(12), text_color=theme.MUTED, anchor="e")
        self.stamps.grid(row=0, column=1, sticky="e")

        # change detection
        for entry in (self.title_entry, self.tags_entry):
            entry.bind("<KeyRelease>", lambda _e: self._changed(False))
        self.body.bind("<<Modified>>", self._body_modified)
        self.body.bind("<KeyRelease>", lambda _e: self._changed(False))
        self.title_entry.bind("<Return>", lambda _e: self.body.focus_set())

        self.load(None)

    # ------------------------------------------------------------------ public API
    def load(self, idea: Idea | None) -> None:
        self._loading = True
        try:
            if idea is None:
                self.form.grid_remove()
                self.empty.grid(row=0, column=0)
                self._snapshot = {}
                return
            self.empty.grid_remove()
            self.form.grid(row=0, column=0, sticky="nsew")
            self._set_entry(self.title_entry, idea.title)
            self._set_entry(self.tags_entry, idea.tags)
            self.category.set(idea.category if idea.category in CATEGORIES else CATEGORIES[0])
            self.body.delete("1.0", "end")
            self.body.insert("1.0", idea.content)
            self.body.edit_reset()          # undo history doesn't leak between ideas
            self.body.edit_modified(False)
            self.body.mark_set("insert", "1.0")
            self._snapshot = self.values()
            self.show_timestamps(idea)
            self.set_status("All changes saved")
        finally:
            self._loading = False

    def values(self) -> dict[str, str]:
        return {
            "title": self.title_entry.get().strip(),
            "content": self.body.get("1.0", "end-1c"),
            "category": self.category.get(),
            "tags": self.tags_entry.get(),
        }

    def has_changes(self) -> bool:
        return bool(self._snapshot) and self.values() != self._snapshot

    def mark_saved(self, idea: Idea, when: str) -> None:
        self._snapshot = self.values()
        self.show_timestamps(idea)
        self.set_status(f"✓ Saved {when}")

    def show_timestamps(self, idea: Idea) -> None:
        self.stamps.configure(text=f"Created {format_timestamp(idea.created_at)}   ·   "
                                   f"Updated {format_timestamp(idea.updated_at)}")

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def focus_title(self) -> None:
        self.title_entry.focus_set()

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, text: str) -> None:
        entry.delete(0, "end")
        if text:
            entry.insert(0, text)

    def _body_modified(self, _e=None) -> None:
        if self.body.edit_modified():
            self.body.edit_modified(False)
            self._changed(False)

    def _changed(self, immediate: bool) -> None:
        if self._loading or not self._snapshot:
            return
        if self.has_changes():
            self.set_status("● Editing…")
            self._on_change(immediate)
