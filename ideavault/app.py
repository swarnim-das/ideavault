"""Main window: wires the sidebar, list and editor to the repository."""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import exporter
from .config import (ALL_CATEGORY, APP_NAME, APP_VERSION, AUTOSAVE_DELAY_MS, DEFAULT_CATEGORY,
                     SEARCH_DELAY_MS, Settings, db_path, get_data_dir, log_path, resource_path)
from .database import IdeaRepository
from .ui.editor import Editor
from .ui.idea_list import IdeaList
from .ui.sidebar import Sidebar
from .utils import open_in_explorer

log = logging.getLogger(APP_NAME)


class IdeaVaultApp(ctk.CTk):
    def __init__(self, repo: IdeaRepository | None = None, settings: Settings | None = None):
        self.settings = settings or Settings()
        ctk.set_appearance_mode(self.settings.get("appearance"))
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title(f"{APP_NAME}")
        self.geometry(self.settings.get("geometry"))
        self.minsize(980, 600)
        icon = resource_path("assets/ideavault.ico")
        if sys.platform == "win32" and icon.exists():
            try:
                self.iconbitmap(default=str(icon))  # also applies to dialogs
            except Exception:
                log.warning("Could not set window icon", exc_info=True)
        if self.settings.get("zoomed") and sys.platform == "win32":
            self.after(0, lambda: self.state("zoomed"))

        self.repo = repo or IdeaRepository(db_path())
        self.category = ALL_CATEGORY
        self.query = ""
        self.current_id: int | None = None
        self._save_job: str | None = None
        self._search_job: str | None = None
        self._list_width = 330

        # ---------------- layout: sidebar | list | editor
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(
            self, on_new=self.new_idea, on_category=self.set_category,
            on_export_json=lambda: self.export("json"), on_export_md=lambda: self.export("md"),
            on_import=self.import_json, on_backup=self.backup_db, on_open_data=self.open_data_folder,
            on_theme=self.toggle_theme, dark=ctk.get_appearance_mode().lower() == "dark",
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.idea_list = IdeaList(self, on_select=self.select_idea, on_search=self.on_search_typed)
        self.idea_list.grid(row=0, column=1, sticky="nsew")
        self.editor = Editor(self, on_change=self.on_editor_change, on_delete=self.delete_current)
        self.editor.grid(row=0, column=2, sticky="nsew")

        self._bind_shortcuts()
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.refresh(scroll_top=True)
        ids = self.idea_list.visible_ids
        if ids:
            self.select_idea(ids[0])

    # ================================================================== shortcuts
    def _bind_shortcuts(self) -> None:
        def key(seq: str, fn):
            # Bind both cases so shortcuts still work with Caps Lock on.
            for s in {seq, seq[:-2] + seq[-2].upper() + ">"}:
                self.bind_all(s, lambda _e: (fn(), "break")[1])

        key("<Control-n>", self.new_idea)
        key("<Control-f>", self.idea_list.focus_search)
        key("<Control-s>", lambda: self.flush_save(force_status=True))
        key("<Control-e>", lambda: self.export("json"))
        self.bind_all("<Control-Shift-E>", lambda _e: (self.export("md"), "break")[1])
        self.bind_all("<Control-Shift-D>", lambda _e: (self.delete_current(), "break")[1])
        self.bind_all("<Alt-Down>", lambda _e: (self.step_selection(1), "break")[1])
        self.bind_all("<Alt-Up>", lambda _e: (self.step_selection(-1), "break")[1])

    def _on_resize(self, event) -> None:
        if event.widget is not self:
            return
        # List pane scales with the window: ~27% of width, clamped to a comfortable range.
        width = max(280, min(420, int(event.width * 0.27)))
        if abs(width - self._list_width) > 8:
            self._list_width = width
            self.idea_list.configure(width=width)

    # ================================================================== list / filters
    def refresh(self, scroll_top: bool = False) -> None:
        cat = None if self.category == ALL_CATEGORY else self.category
        ideas = self.repo.list_ideas(cat, self.query)
        self.idea_list.set_heading(self.category)
        self.idea_list.set_ideas(ideas, self.current_id, len(ideas), self.query, scroll_top=scroll_top)
        self.sidebar.update_counts(self.repo.category_counts())

    def set_category(self, name: str) -> None:
        self.flush_save()
        self._discard_if_empty()
        self.category = name
        self.sidebar.set_active(name)
        self._refresh_and_keep_selection()

    def on_search_typed(self, text: str) -> None:
        if text == self.query:
            return
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(SEARCH_DELAY_MS, lambda: self._apply_search(text))

    def _apply_search(self, text: str) -> None:
        self._search_job = None
        self.flush_save()
        self.query = text
        self._refresh_and_keep_selection(select_first=False)

    def _refresh_and_keep_selection(self, select_first: bool = True) -> None:
        self.refresh(scroll_top=True)
        ids = self.idea_list.visible_ids
        if self.current_id in ids:
            return
        if select_first and ids:
            self.select_idea(ids[0])
        elif self.current_id is not None and self.repo.get(self.current_id) is None:
            self.current_id = None
            self.editor.load(None)

    def step_selection(self, delta: int) -> None:
        ids = self.idea_list.visible_ids
        if not ids:
            return
        idx = ids.index(self.current_id) + delta if self.current_id in ids else 0
        self.select_idea(ids[max(0, min(len(ids) - 1, idx))])

    # ================================================================== selection / CRUD
    def select_idea(self, idea_id: int) -> None:
        if idea_id == self.current_id:
            return
        self.flush_save()
        removed = self._discard_if_empty(exclude=idea_id)
        idea = self.repo.get(idea_id)
        self.current_id = idea.id if idea else None
        self.editor.load(idea)
        if removed:
            self.refresh()
        else:
            self.idea_list.highlight(self.current_id)

    def new_idea(self) -> None:
        self.flush_save()
        self._discard_if_empty()
        category = self.category if self.category != ALL_CATEGORY else DEFAULT_CATEGORY
        idea = self.repo.create(category)
        if self.query:
            self.query = ""
            self.idea_list.clear_search()
        self.current_id = idea.id
        self.editor.load(idea)
        self.editor.set_status("New idea — start typing, it saves automatically")
        self.refresh(scroll_top=True)
        self.editor.focus_title()

    def delete_current(self) -> None:
        if self.current_id is None:
            return
        idea = self.repo.get(self.current_id)
        if idea is None:
            return
        if not idea.is_empty() or self.editor.has_changes():
            if not messagebox.askyesno("Delete idea", f"Delete “{idea.display_title}”?\n\nThis can't be undone.",
                                       icon="warning", parent=self):
                return
        self._cancel_save()
        ids = self.idea_list.visible_ids
        nxt = None
        if idea.id in ids:
            i = ids.index(idea.id)
            rest = ids[:i] + ids[i + 1:]
            nxt = rest[min(i, len(rest) - 1)] if rest else None
        self.repo.delete(idea.id)
        self.current_id = None
        self.editor.load(None)
        self.refresh()
        if nxt is not None:
            self.select_idea(nxt)

    def _discard_if_empty(self, exclude: int | None = None) -> bool:
        """Silently drop a brand-new idea the user never typed into."""
        if self.current_id is None or self.current_id == exclude:
            return False
        idea = self.repo.get(self.current_id)
        if idea and idea.is_empty():
            self.repo.delete(idea.id)
            self.current_id = None
            return True
        return False

    # ================================================================== auto-save
    def on_editor_change(self, immediate: bool) -> None:
        self._cancel_save()
        if immediate:
            self.flush_save()
        else:
            self._save_job = self.after(AUTOSAVE_DELAY_MS, self.flush_save)

    def _cancel_save(self) -> None:
        if self._save_job:
            self.after_cancel(self._save_job)
            self._save_job = None

    def flush_save(self, force_status: bool = False) -> None:
        self._cancel_save()
        if self.current_id is None:
            return
        if not self.editor.has_changes():
            if force_status:
                self.editor.set_status(f"✓ Saved {datetime.now():%H:%M:%S}")
            return
        try:
            idea = self.repo.update(self.current_id, **self.editor.values())
        except Exception:
            log.exception("Auto-save failed")
            self.editor.set_status("⚠ Save failed — see log in data folder")
            return
        if idea:
            self.editor.mark_saved(idea, f"{datetime.now():%H:%M:%S}")
            self.refresh()

    # ================================================================== export / backup
    def _ask_folder(self, title: str) -> str:
        initial = self.settings.get("last_export_dir") or str(Path.home() / "Documents")
        folder = filedialog.askdirectory(title=title, initialdir=initial, mustexist=True, parent=self)
        if folder:
            self.settings.set("last_export_dir", folder)
            self.settings.save()
        return folder

    def export(self, fmt: str) -> None:
        self.flush_save()
        ideas = self.repo.all_ideas()
        if not ideas:
            messagebox.showinfo("Export", "There are no ideas to export yet.", parent=self)
            return
        folder = self._ask_folder("Choose a folder for the export")
        if not folder:
            return
        try:
            path = exporter.export_json(ideas, folder) if fmt == "json" else exporter.export_markdown(ideas, folder)
        except OSError as exc:
            log.exception("Export failed")
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        if messagebox.askyesno("Export complete", f"Exported {len(ideas)} ideas to:\n{path}\n\nOpen the folder?",
                               parent=self):
            open_in_explorer(folder)

    def import_json(self) -> None:
        self.flush_save()
        file = filedialog.askopenfilename(title="Import IdeaVault JSON export", parent=self,
                                          filetypes=[("JSON export", "*.json"), ("All files", "*.*")])
        if not file:
            return
        try:
            added, skipped = exporter.import_json(self.repo, file)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        self.refresh(scroll_top=True)
        messagebox.showinfo("Import complete", f"Imported {added} ideas."
                            + (f"\nSkipped {skipped} already in your vault." if skipped else ""), parent=self)

    def backup_db(self) -> None:
        self.flush_save()
        initial = self.settings.get("last_export_dir") or str(Path.home() / "Documents")
        dest = filedialog.asksaveasfilename(
            title="Save database backup", parent=self, initialdir=initial, defaultextension=".db",
            initialfile=f"ideas_backup_{datetime.now():%Y%m%d_%H%M}.db",
            filetypes=[("SQLite database", "*.db")])
        if not dest:
            return
        try:
            self.repo.backup_to(dest)
        except Exception as exc:
            log.exception("Backup failed")
            messagebox.showerror("Backup failed", str(exc), parent=self)
            return
        messagebox.showinfo("Backup complete", f"Database backed up to:\n{dest}", parent=self)

    def open_data_folder(self) -> None:
        open_in_explorer(get_data_dir())

    # ================================================================== theme / lifecycle
    def toggle_theme(self, dark: bool) -> None:
        mode = "dark" if dark else "light"
        ctk.set_appearance_mode(mode)
        self.settings.set("appearance", mode)
        self.settings.save()

    def report_callback_exception(self, exc, val, tb) -> None:  # Tk hook for errors in callbacks
        log.error("Unhandled UI error:\n%s", "".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror(APP_NAME, f"Something went wrong:\n{val}\n\nDetails were written to:\n{log_path()}",
                             parent=self)

    def on_close(self) -> None:
        try:
            self.flush_save()
            self._discard_if_empty()
            zoomed = sys.platform == "win32" and self.state() == "zoomed"
            self.settings.set("zoomed", zoomed)
            if not zoomed:
                self.settings.set("geometry", self.geometry())
            self.settings.save()
        finally:
            self.repo.close()
            self.destroy()


def _setup_logging() -> None:
    handler = RotatingFileHandler(log_path(), maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _set_windows_app_id() -> None:
    """Gives the app its own taskbar identity instead of grouping under python.exe."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"IdeaVault.App.{APP_VERSION}")
        except Exception:
            pass


def run() -> int:
    _setup_logging()
    _set_windows_app_id()
    log.info("Starting %s %s — data at %s", APP_NAME, APP_VERSION, get_data_dir())
    app = IdeaVaultApp()
    app.mainloop()
    return 0
