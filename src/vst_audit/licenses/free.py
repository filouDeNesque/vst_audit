"""Plugins connus pour être gratuits (aucune clé nécessaire). Liste à enrichir."""

from __future__ import annotations

from ..config import Config, patterns, matches
from ..models import License, LicenseResult, Plugin

KNOWN_FREE = patterns([
    "Valhalla Supermassive",
    "Valhalla Freq Echo",
    "Valhalla Space Modulator",
    "TDR Nova",
    "Spitfire LABS",
    "Vital",
])


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    if matches(plugin.name, KNOWN_FREE):
        return LicenseResult(License.FREE, "liste gratuits")
    return None
