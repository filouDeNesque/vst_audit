"""Sources locales d'état de licence Universal Audio (lecture seule).

1. Journaux UADx  ~/Library/Logs/Universal Audio/UAPW_<id>_MM_DD_YY_hh_mm_ss.txt
   Écrits à chaque ouverture d'un plugin UADx en mode natif. Ils contiennent l'état PACE :
       Update PACE State after [DEMO ACTIVE - 2 Days]: [eLicenseState_DemoActive]
   On garde l'état le plus récent par plugin. Un plugin jamais ouvert en natif n'a pas
   d'état (en mode DSP « TrySetMode->[UAD2] », aucune licence PACE n'est vérifiée).

2. Profil système UAD-2  ~/Library/Logs/Universal Audio/UADSystemProfile_cur.txt
   Écrit par « UAD Meter & Control Panel » → System Info. La section
   « UAD-2 Plug-in Authorizations » liste chaque produit avec son statut,
   à condition que l'Apollo ait été branché au moment de la génération.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path

from ..models import License, normalize

log = logging.getLogger(__name__)

LOG_DIR = Path.home() / "Library/Logs/Universal Audio"

_LOG_NAME = re.compile(r"^UAPW_(?P<id>.+?)_(?P<ts>\d\d_\d\d_\d\d_\d\d_\d\d_\d\d)(?:_\d+)?\.txt$")
_PACE = re.compile(r"Update PACE State after \[(?P<label>[^\]]*)\]: \[eLicenseState_(?P<state>\w+)\]")

# état PACE -> (statut, libellé lisible)
PACE_STATES = {
    "FullActive": (License.LICENSED, "acheté"),
    "SubscriptionActive": (License.LICENSED, "Spark (abonnement)"),
    "DemoActive": (License.DEMO, "démo en cours"),
    "DemoExpired": (License.NOT_OWNED, "démo expirée"),
    "NotLicensed": (License.NOT_OWNED, "non licencié"),
}


@dataclass(frozen=True)
class UAState:
    status: License
    label: str
    seen: datetime
    source: str

    @property
    def detail(self) -> str:
        return f"{self.label} · {self.source} du {self.seen:%d/%m/%Y}"


def parse_pace_log(text: str) -> tuple[str, str] | None:
    """Dernier (état, libellé) PACE d'un journal, ou None."""
    last = None
    for m in _PACE.finditer(text):
        last = (m["state"], m["label"].strip())
    return last


_DAYS = re.compile(r"(\d+)\s*Day", re.I)


def demo_status(label: str, seen: datetime, now: datetime | None = None) -> tuple[License, str]:
    """« DEMO ACTIVE - 77 Days » vu le 22/08/2025 → démo jusqu'au 07/11/2025, ou expirée si c'est passé."""
    m = _DAYS.search(label)
    if not m:
        return License.DEMO, "démo en cours"
    end = seen + timedelta(days=int(m[1]))
    if end < (now or datetime.now()):
        return License.NOT_OWNED, f"démo expirée le {end:%d/%m/%Y}"
    return License.DEMO, f"démo jusqu'au {end:%d/%m/%Y}"


@cache
def uadx_states(log_dir: Path = LOG_DIR) -> dict[str, UAState]:
    """identifiant de plugin (« uaudio_minimoog ») -> état le plus récent (lu une fois par analyse)."""
    states = read_uadx_states(log_dir)
    log.info("Journaux UADx : %d plugins avec un état de licence", len(states))
    return states


def read_uadx_states(log_dir: Path = LOG_DIR, only: str | None = None) -> dict[str, UAState]:
    """Lecture sans cache ; `only` limite à un plugin (utilisé par le suivi interactif)."""
    files: list[tuple[datetime, str, Path]] = []
    for path in log_dir.glob(f"UAPW_{only}_*.txt" if only else "UAPW_*.txt"):
        m = _LOG_NAME.match(path.name)
        if not m or (only and m["id"] != only):
            continue
        try:
            ts = datetime.strptime(m["ts"], "%m_%d_%y_%H_%M_%S")
        except ValueError:
            continue
        files.append((ts, m["id"], path))

    states: dict[str, UAState] = {}
    for ts, plugin_id, path in sorted(files, reverse=True):  # du plus récent au plus ancien
        if plugin_id in states:
            continue
        try:
            found = parse_pace_log(path.read_text(errors="replace"))
        except OSError:
            continue
        if found and found[0] in PACE_STATES:
            status, label = PACE_STATES[found[0]]
            if found[0] == "DemoActive":
                status, label = demo_status(found[1], ts)
            states[plugin_id] = UAState(status, label, ts, "journal UADx")
    return states


# --- Profil système UAD-2 -------------------------------------------------------

_DATE = re.compile(r"Date:\s*(.+)$", re.M)
_DEVICES = re.compile(r"Number of Devices:\s*(\d+)")
_AUTH_LINE = re.compile(r"^(?P<name>UAD [^:]+):\s*(?P<status>.+?)\s*$", re.M)


def classify_auth(status: str) -> tuple[License, str] | None:
    s = status.lower()
    if "no uad-2 devices" in s:
        return None
    if "authorized" in s and "not" not in s:
        return License.LICENSED, "autorisé (DSP)"
    if "demo" in s and ("remaining" in s or "active" in s or "days" in s):
        return License.DEMO, f"démo (DSP) : {status}"
    if "demo" in s or "purchase" in s or "not" in s or "expired" in s:
        return License.NOT_OWNED, f"non autorisé (DSP) : {status}"
    return None


def parse_system_profile(text: str) -> dict[str, tuple[License, str]]:
    """nom de produit normalisé -> (statut, libellé). Vide si aucun Apollo n'était branché."""
    devices = _DEVICES.search(text)
    if devices and devices[1] == "0":
        return {}
    section = text.split("Plug-in Authorizations", 1)[-1]
    out = {}
    for m in _AUTH_LINE.finditer(section):
        if result := classify_auth(m["status"]):
            out[normalize(re.sub(r"^UAD\s+", "", m["name"]))] = result
    return out


@dataclass
class Profile:
    products: dict[str, tuple[License, str]]
    date: str
    path: Path


@cache
def system_profile(log_dir: Path = LOG_DIR) -> Profile | None:
    path = log_dir / "UADSystemProfile_cur.txt"
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    products = parse_system_profile(text)
    date = (_DATE.search(text) or [None, "?"])[1].strip()
    if not products:
        log.info("Profil UAD-2 du %s inexploitable (aucun Apollo branché lors de sa génération)", date)
        return None
    return Profile(products, date, path)


def match_product(plugin_name: str, products: dict[str, tuple[License, str]]) -> tuple[License, str] | None:
    """Associe un plugin à un produit du profil.

    Les noms diffèrent un peu : « UAD UA 1176LN Legacy » ↔ « UA 1176LN Legacy Limiter »,
    « UAD Pultec EQP-1A » ↔ « Pultec Passive EQ Collection ». On accepte un produit dont
    le nom commence par celui du plugin, ou l'inverse. En cas de doute, on ne conclut pas.
    """
    name = normalize(re.sub(r"^UADx?\s+", "", plugin_name, flags=re.I))
    if name in products:
        return products[name]
    candidates = [p for p in products if p.startswith(name + " ") or name.startswith(p + " ")]
    if len(candidates) == 1:
        return products[candidates[0]]
    return None
