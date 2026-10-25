"""Chargement de config/licences.toml (déclarations manuelles de l'utilisateur)."""

from __future__ import annotations

import fnmatch
import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .models import License, normalize

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config/licences.toml"
DATA_DIR = PROJECT_ROOT / "data"

_STATUS = {s.value: s for s in License}


def patterns(items: list[str]) -> list[str]:
    """Motifs normalisés ; sans joker, on cherche le motif n'importe où dans le nom."""
    out = []
    for item in items:
        pat = "*".join(normalize(part) for part in item.split("*"))
        out.append(pat if "*" in item else f"*{pat}*")
    return out


def matches(name: str, patterns: list[str]) -> bool:
    n = normalize(name)
    return any(fnmatch.fnmatchcase(n, p) for p in patterns)


@dataclass
class Config:
    vendors: dict[str, License] = field(default_factory=dict)
    plugins: list[tuple[list[str], License]] = field(default_factory=list)
    uad_owned: list[str] = field(default_factory=list)
    uad_strict: bool = False
    path: Path | None = None

    def vendor_status(self, vendor: str) -> License | None:
        return self.vendors.get(normalize(vendor))

    def plugin_status(self, name: str) -> License | None:
        for patterns, status in self.plugins:
            if matches(name, patterns):
                return status
        return None


def _status(value: str, where: str) -> License | None:
    status = _STATUS.get(value)
    if status is None:
        log.warning("%s : statut « %s » inconnu (valeurs : %s)", where, value, ", ".join(_STATUS))
    return status


def load(path: Path = CONFIG_FILE) -> Config:
    if not path.exists():
        log.info("Pas de %s : détection automatique seule", path.name)
        return Config()
    raw = tomllib.loads(path.read_text())
    cfg = Config(path=path)

    for vendor, value in raw.get("editeurs", {}).items():
        if status := _status(value, f"[editeurs] {vendor}"):
            cfg.vendors[normalize(vendor)] = status

    for value, names in raw.get("plugins", {}).items():
        if status := _status(value, "[plugins]"):
            cfg.plugins.append((patterns(names), status))

    uad = raw.get("uad", {})
    cfg.uad_owned = patterns(uad.get("possedes", []))
    cfg.uad_strict = bool(uad.get("strict", False))
    return cfg
