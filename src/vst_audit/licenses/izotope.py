"""iZotope : fichiers ~/Library/Preferences/com.izotope.*.<CODE>.Authorizations.plist.

Un fichier contenant des données d'autorisation (d1/d2) indique un produit
autorisé localement. Les versions récentes (11+) passent par Native Access /
iZotope Product Portal et n'écrivent souvent que "AuthWizard Trial Check" :
dans ce cas on ne conclut pas.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

from ..config import Config
from ..models import License, LicenseResult, Plugin

PREFS = Path.home() / "Library/Preferences"


def _auth_files(code: str) -> list[Path]:
    code = code.upper()
    return [p for p in PREFS.glob("com.izotope.*Authorizations.plist")
            if p.name.upper().endswith(f".{code}.AUTHORIZATIONS.PLIST")]


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    if not plugin.bundle_id.lower().startswith("com.izotope."):
        return None
    code = plugin.bundle_id.rsplit(".", 1)[-1]
    files = _auth_files(code)
    for path in files:
        try:
            data = plistlib.loads(path.read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError):
            continue
        if data.get("d1") or data.get("d2"):
            return LicenseResult(License.LICENSED, "izotope", "autorisation locale trouvée")
    detail = "aucune autorisation locale lisible" if files else "aucun fichier d'autorisation"
    return LicenseResult(License.UNKNOWN, "izotope", f"{detail} : vérifier dans Native Access")
