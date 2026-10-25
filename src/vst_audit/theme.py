"""Apparence Ableton Live pour l'interface web : couleurs du thème Live actif et police Ableton Sans.

Rien n'est copié dans le projet : les thèmes (.ask) et la police sont lus dans l'application
Live installée, et servis uniquement au navigateur local. Sans Live, style.css garde ses valeurs
par défaut (reprises de « Default Dark Neutral Medium »).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

APPS = Path("/Applications")
PREFS = Path.home() / "Library/Preferences/Ableton"
DEFAULT_THEME = "Default Dark Neutral Medium"

FONT_FILES = {  # nom servi -> fichier dans App-Resources/Fonts
    "AbletonSansSmall-Regular.ttf", "AbletonSansSmall-Bold.ttf",
    "AbletonSansSmall-RegularItalic.ttf", "AbletonSans-Light.ttf",
}

# variable CSS -> clés du thème Live (la première présente gagne)
MAPPING = {
    "--bg": ["Desktop"],
    "--well": ["SurfaceArea"],
    "--surface": ["SurfaceBackground"],
    "--surface-2": ["ControlBackground"],
    "--header": ["TreeColumnHeadBackground", "SurfaceHighlight"],
    "--highlight": ["SurfaceHighlight"],
    "--border": ["ControlContrastFrame"],
    "--text": ["ControlForeground"],
    "--muted": ["TextDisabled"],
    "--on-text": ["ControlOnForeground"],
    "--accent": ["ChosenDefault"],
    "--selection": ["SelectionBackground"],
    "--selection-text": ["SelectionForeground"],
    "--display": ["DisplayBackground"],
    # statuts : couleurs sémantiques de Live
    "--v-invalide": ["ChosenRecord"],
    "--v-cle": ["ChosenAlert", "Alert"],
    "--v-nonacquis": ["TextDisabled"],
    "--v-demo": ["Clip14"],
    "--v-desactive": ["ChosenPreListen"],
    "--v-verifier": ["RangeDefault", "ChosenAlternative"],
    "--v-ok": ["ChosenPlay"],
}


@cache
def live_app() -> Path | None:
    """Application Live la plus récente (« Ableton Live 12 Suite.app »…)."""
    apps = sorted(APPS.glob("Ableton Live*.app"), key=lambda p: p.stat().st_mtime, reverse=True)
    return apps[0] if apps else None


def _resources() -> Path | None:
    app = live_app()
    return app / "Contents/App-Resources" if app else None


def themes_dir() -> Path | None:
    res = _resources()
    return res / "Themes" if res and (res / "Themes").is_dir() else None


def font_path(name: str) -> Path | None:
    res = _resources()
    if name not in FONT_FILES or not res:
        return None
    path = res / "Fonts" / name
    return path if path.is_file() else None


def available_themes() -> list[str]:
    folder = themes_dir()
    return sorted(p.stem for p in folder.glob("*.ask")) if folder else []


def active_theme() -> str | None:
    """Thème choisi dans Live : son nom figure (en UTF-16) dans Preferences.cfg."""
    names = available_themes()
    prefs = sorted(PREFS.glob("Live */Preferences.cfg"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not names or not prefs:
        return None
    try:
        text = prefs[0].read_bytes().decode("utf-16-le", errors="ignore")
    except OSError:
        return None
    found = [(text.find(n), n) for n in names if n in text]
    return min(found)[1] if found else (DEFAULT_THEME if DEFAULT_THEME in names else None)


def theme_colors(name: str) -> dict[str, str]:
    folder = themes_dir()
    if not folder or name not in available_themes():
        return {}
    xml = (folder / f"{name}.ask").read_text(errors="replace")
    return dict(re.findall(r'<(\w+) Value="(#[0-9a-fA-F]{6,8})"', xml))


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def css(name: str | None = None) -> str:
    """Feuille de style : @font-face Ableton Sans + variables du thème demandé (ou actif)."""
    parts = []
    if font_path("AbletonSansSmall-Regular.ttf"):
        parts.append("""
@font-face { font-family: "Ableton Sans Small"; src: url("/fonts/AbletonSansSmall-Regular.ttf"); font-weight: 400; }
@font-face { font-family: "Ableton Sans Small"; src: url("/fonts/AbletonSansSmall-Bold.ttf"); font-weight: 700; }
@font-face { font-family: "Ableton Sans Small"; src: url("/fonts/AbletonSansSmall-RegularItalic.ttf"); font-style: italic; }
@font-face { font-family: "Ableton Sans Light"; src: url("/fonts/AbletonSans-Light.ttf"); font-weight: 300; }""")
    theme = name or active_theme()
    colors = theme_colors(theme) if theme else {}
    if colors:
        lines = []
        for var, keys in MAPPING.items():
            value = next((colors[k] for k in keys if k in colors and len(colors[k]) == 7), None)
            if value:
                lines.append(f"  {var}: {value};")
        scheme = "light" if _luminance(colors.get("SurfaceBackground", "#000000")) > 0.5 else "dark"
        lines.append(f"  color-scheme: {scheme};")
        parts.append(f"/* Thème Live : {theme} */\n:root {{\n" + "\n".join(lines) + "\n}")
    return "\n".join(parts) + "\n"
