"""Small formatting and OS helpers."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _parse(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def format_timestamp(iso: str) -> str:
    try:
        return _parse(iso).astimezone().strftime("%d %b %Y, %H:%M")
    except (ValueError, TypeError):
        return iso or ""


def relative_time(iso: str, now: datetime | None = None) -> str:
    try:
        dt = _parse(iso)
    except (ValueError, TypeError):
        return ""
    now = now or datetime.now(timezone.utc)
    secs = int((now - dt).total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    if secs < 7 * 86400:
        return f"{secs // 86400}d ago"
    return dt.astimezone().strftime("%d %b %Y")


def one_line(text: str, max_chars: int) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= max_chars else flat[: max_chars - 1].rstrip() + "…"


def open_in_explorer(path: str | Path) -> None:
    path = str(path)
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
