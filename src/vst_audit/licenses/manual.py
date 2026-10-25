"""Statuts définis par l'utilisateur : interface web (overrides.json), puis config/licences.toml."""

from __future__ import annotations

from .. import overrides
from ..config import Config
from ..models import License, LicenseResult, Plugin


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    if entry := overrides.lookup(plugin.group_keys):
        detail = f"défini le {entry['date'][:10]}" + (f" · {entry['note']}" if entry["note"] else "")
        return LicenseResult(License(entry["status"]), "défini (web)", detail)
    if status := cfg.plugin_status(plugin.name):
        return LicenseResult(status, "déclaré", "config [plugins]")
    if status := cfg.vendor_status(plugin.vendor):
        return LicenseResult(status, "déclaré", "config [editeurs]")
    return None
