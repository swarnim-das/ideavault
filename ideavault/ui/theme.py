"""Shared colours (light, dark) and fonts so every pane looks consistent."""
import customtkinter as ctk

from ..config import MONO_FONT, UI_FONT

SIDEBAR_BG = ("#eceef1", "#16181c")
LIST_BG = ("#f5f6f8", "#1c1f24")
EDITOR_BG = ("#ffffff", "#212429")

ROW_BG = ("#ffffff", "#262a30")
ROW_HOVER = ("#eef2f7", "#2e333a")
ROW_SELECTED = ("#d7e6f8", "#1f3b5c")

TEXT = ("#1b1d21", "#e6e8eb")
MUTED = ("#6b7280", "#8b929c")
ACCENT = ("#2563eb", "#3b82f6")
ACCENT_HOVER = ("#1d4ed8", "#2563eb")
DANGER = ("#dc2626", "#b91c1c")
DANGER_HOVER = ("#b91c1c", "#991b1b")
NAV_HOVER = ("#dde1e6", "#24282e")
NAV_ACTIVE = ("#d0d7e2", "#2a3442")


def font(size: int = 13, weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FONT if mono else UI_FONT, size=size, weight=weight)
