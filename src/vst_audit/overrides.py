"""Statuts définis depuis l'interface web pour un plugin précis (data/overrides.json).

Une entrée couvre tous les formats d'un plugin : elle est enregistrée avec toutes les clés
de regroupement de ses bundles (voir Plugin.group_keys). Prioritaire sur toute détection.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import cache
from pathlib import Path

from .config import DATA_DIR
from .models import License

OVERRIDES_FILE = DATA_DIR / "overrides.json"


def load(path: Path | None = None) -> dict[str, dict]:
    path = path or OVERRIDES_FILE
    try:
        return json.loads(path.read_text()).get("plugins", {})
    except (OSError, ValueError):
        return {}


def _save(entries: dict[str, dict], path: Path | None = None) -> None:
    path = path or OVERRIDES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "plugins": entries}, ensure_ascii=False, indent=2))
    tmp.replace(path)


@cache
def index() -> dict[str, dict]:
    """clé de regroupement -> entrée (pour le détecteur)."""
    return {key: entry for entry in load().values() for key in entry["keys"]}


def lookup(group_keys: list[str]) -> dict | None:
    idx = index()
    return next((idx[k] for k in group_keys if k in idx), None)


def set_status(group_key: str, keys: list[str], name: str, status: License, note: str = "") -> dict:
    entries = load()
    entries[group_key] = {
        "name": name, "status": status.value, "note": note, "keys": sorted(set(keys)),
        "date": datetime.now().isoformat(timespec="seconds"),
    }
    _save(entries)
    index.cache_clear()
    return entries[group_key]


def remove(group_key: str) -> bool:
    entries = load()
    if entries.pop(group_key, None) is None:
        return False
    _save(entries)
    index.cache_clear()
    return True
