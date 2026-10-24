"""Left navigation: new idea, category filters, export/backup actions, theme switch."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..config import ALL_CATEGORY, APP_NAME, CATEGORIES
from . import theme

CATEGORY_ICONS = {ALL_CATEGORY: "◎", "General": "•", "Projects": "▣", "Writing": "✎", "Code": "</>", "To-Do": "☑"}


class Sidebar(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        on_new: Callable[[], None],
        on_category: Callable[[str], None],
        on_export_json: Callable[[], None],
        on_export_md: Callable[[], None],
        on_import: Callable[[], None],
        on_backup: Callable[[], None],
        on_open_data: Callable[[], None],
        on_theme: Callable[[bool], None],
        dark: bool,
    ):
        super().__init__(master, width=220, corner_radius=0, fg_color=theme.SIDEBAR_BG)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self._on_category = on_category
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active = ALL_CATEGORY

        ctk.CTkLabel(self, text=APP_NAME, font=theme.font(20, "bold"), text_color=theme.TEXT,
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 14))

        ctk.CTkButton(self, text="＋  New idea", height=38, font=theme.font(14, "bold"),
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=on_new).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 16))

        self._section("LIBRARY", 2)
        row = 3
        for name in [ALL_CATEGORY, *CATEGORIES]:
            btn = ctk.CTkButton(
                self, text=name, anchor="w", height=34, corner_radius=8, font=theme.font(13),
                fg_color="transparent", hover_color=theme.NAV_HOVER, text_color=theme.TEXT,
                command=lambda n=name: self._on_category(n),
            )
            btn.grid(row=row, column=0, sticky="ew", padx=10, pady=1)
            self._buttons[name] = btn
            row += 1

        self.grid_rowconfigure(row, weight=1)  # spacer pushes actions to the bottom
        row += 1

        self._section("EXPORT & BACKUP", row)
        row += 1
        for text, cmd in [("⇩  Export JSON", on_export_json), ("⇩  Export Markdown", on_export_md),
                          ("⇧  Import JSON", on_import), ("⛁  Backup database", on_backup),
                          ("↗  Open data folder", on_open_data)]:
            ctk.CTkButton(self, text=text, anchor="w", height=30, corner_radius=8, font=theme.font(12),
                          fg_color="transparent", hover_color=theme.NAV_HOVER, text_color=theme.TEXT,
                          command=cmd).grid(row=row, column=0, sticky="ew", padx=10, pady=1)
            row += 1

        self.theme_switch = ctk.CTkSwitch(self, text="Dark mode", font=theme.font(12), text_color=theme.TEXT,
                                          command=lambda: on_theme(bool(self.theme_switch.get())))
        if dark:
            self.theme_switch.select()
        self.theme_switch.grid(row=row, column=0, sticky="w", padx=18, pady=(14, 6))
        row += 1

        ctk.CTkLabel(self, text="Ctrl+N new · Ctrl+F search\nCtrl+S save · Ctrl+E export",
                     font=theme.font(11), text_color=theme.MUTED, justify="left",
                     anchor="w").grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 16))

        self.set_active(ALL_CATEGORY)

    def _section(self, text: str, row: int) -> None:
        ctk.CTkLabel(self, text=text, font=theme.font(11, "bold"), text_color=theme.MUTED,
                     anchor="w").grid(row=row, column=0, sticky="ew", padx=18, pady=(8, 4))

    def set_active(self, name: str) -> None:
        self._active = name
        for n, btn in self._buttons.items():
            btn.configure(fg_color=theme.NAV_ACTIVE if n == name else "transparent",
                          font=theme.font(13, "bold" if n == name else "normal"))

    def update_counts(self, counts: dict[str, int]) -> None:
        for name, btn in self._buttons.items():
            n = counts.get("__total__" if name == ALL_CATEGORY else name, 0)
            btn.configure(text=f"{CATEGORY_ICONS.get(name, '•'):<3} {name}   ·  {n}")
