"""AIR Music Technology / inMusic (Akai) : système « software unlock ».

Les plugins AIR récents embarquent la bibliothèque inmusic::software_unlock (connexion au
compte inMusic). Chaque produit déverrouillé laisse un fichier nommé d'après son code produit
dans ~/Library/Application Support/com.inmusicbrands.softwareunlock/[<version>/]<CODE>
(ex. AKMP3 pour MPC 3). Le contenu est chiffré, et la correspondance code ↔ plugin n'est
pas publique : on liste les produits déverrouillés sans conclure plugin par plugin.
Le cache de l'inMusic Software Center (PISCache.json) est chiffré via le trousseau macOS.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from ..config import Config
from ..models import License, LicenseResult, Plugin

UNLOCK_DIR = Path.home() / "Library/Application Support/com.inmusicbrands.softwareunlock"

# codes produits identifiés (à compléter au fil des déverrouillages)
KNOWN_CODES = {"AKMP3": "MPC 3"}


def is_inmusic(plugin: Plugin) -> bool:
    bid = plugin.bundle_id.lower()
    return (bid.startswith(("com.inmusicbrands.", "com.airmusictech.", "com.akaipro."))
            or plugin.vendor.lower().startswith(("air music", "inmusic")))


@cache
def unlocked_products(unlock_dir: Path = UNLOCK_DIR) -> list[str]:
    """Codes produits déverrouillés sur ce Mac (fichiers du dossier software unlock)."""
    if not unlock_dir.is_dir():
        return []
    codes = {f.name for f in unlock_dir.rglob("*") if f.is_file() and f.name.isupper() and not f.name.startswith(".")}
    codes.discard("SESSION")
    return sorted(codes)


def describe(codes: list[str]) -> str:
    return ", ".join(f"{c} ({KNOWN_CODES[c]})" if c in KNOWN_CODES else c for c in codes) or "aucun"


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    if not is_inmusic(plugin):
        return None
    if plugin.bundle_id.lower().startswith("com.akaipro.mpc"):  # MPC en plugin : licence de l'application
        if "AKMP3" in unlocked_products() and "mpc3" in plugin.bundle_id.lower():
            return LicenseResult(License.LICENSED, "inMusic", "MPC 3 déverrouillé (fichier AKMP3)")
        return None
    codes = unlocked_products()
    unknown = [c for c in codes if c not in KNOWN_CODES]
    if unknown:
        detail = (f"produits déverrouillés non identifiés : {describe(unknown)}. "
                  "Ouvrez le plugin : s'il ne demande pas de connexion, définissez-le « licencié »")
    else:
        detail = (f"aucun déverrouillage inMusic propre à ce plugin sur ce Mac (déverrouillés : {describe(codes)}). "
                  "Ouvrez-le : s'il demande de se connecter ou d'activer, il est en démo ou non acquis")
    return LicenseResult(License.UNKNOWN, "inMusic", detail)
