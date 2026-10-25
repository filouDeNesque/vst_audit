"""Résultats de la vérification active (vst-audit sonder / bouton « Sonder » de l'interface)."""

from __future__ import annotations

from .. import sonde
from ..config import Config
from ..models import License, LicenseResult, Plugin


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    entry = sonde.lookup(plugin.group_keys)
    if not entry or not entry["status"]:
        return None
    return LicenseResult(License(entry["status"]), "sonde", f"{entry['label']} · sondé le {entry['date'][:10]}")
