"""Plugins connus pour être gratuits (aucune clé nécessaire). Liste à enrichir."""

from __future__ import annotations

from ..config import Config
from ..models import License, LicenseResult, Plugin, normalize

KNOWN_FREE = [
    "Valhalla Supermassive",
    "Valhalla Freq Echo",
    "Valhalla Space Modulator",
    "TDR Nova",
    "Spitfire LABS",
    "Vital",
]


def _compact(text: str) -> str:
    # sans espaces : « ValhallaSupermassive » (nom réel du bundle) = « Valhalla Supermassive »
    return normalize(text).replace(" ", "")


_FREE = [_compact(n) for n in KNOWN_FREE]


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    name = _compact(plugin.name)
    if any(f in name for f in _FREE):
        return LicenseResult(License.FREE, "liste gratuits")
    return None
