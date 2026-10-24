"""Application constants, data-folder resolution and persisted UI settings."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "IdeaVault"
APP_VERSION = "1.0.0"

ALL_CATEGORY = "All Ideas"
DEFAULT_CATEGORY = "General"
CATEGORIES = ["General", "Projects", "Writing", "Code", "To-Do"]

AUTOSAVE_DELAY_MS = 600     # pause after typing before the note is written to disk
SEARCH_DELAY_MS = 150       # debounce for live search
MAX_LIST_ROWS = 500         # cap on rendered rows; refine search to see more

UI_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
MONO_FONT = "Cascadia Mono" if sys.platform == "win32" else "Courier"

log = logging.getLogger(__name__)


def get_data_dir() -> Path:
    """Folder that holds ideas.db, settings and logs.

    Windows: %LOCALAPPDATA%\\IdeaVault  (e.g. C:\\Users\\you\\AppData\\Local\\IdeaVault)
    Override with the IDEAVAULT_DATA_DIR environment variable (handy for a portable USB copy).
    """
    override = os.environ.get("IDEAVAULT_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_path(relative: str) -> Path:
    """Locate bundled files both from source and inside a PyInstaller .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def db_path() -> Path:
    return get_data_dir() / "ideas.db"


def log_path() -> Path:
    return get_data_dir() / "ideavault.log"


class Settings:
    """Tiny JSON-backed settings store (theme, window size, last folders)."""

    DEFAULTS: dict[str, Any] = {
        "appearance": "dark",
        "geometry": "1240x760",
        "zoomed": False,
        "last_export_dir": "",
    }

    def __init__(self, path: Path | None = None):
        self.path = path or get_data_dir() / "settings.json"
        self._data = dict(self.DEFAULTS)
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
        except (OSError, ValueError) as exc:
            log.warning("Could not read settings, using defaults: %s", exc)

    def get(self, key: str) -> Any:
        return self._data.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.warning("Could not save settings: %s", exc)
