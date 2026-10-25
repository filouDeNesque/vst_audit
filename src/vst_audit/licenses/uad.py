"""Universal Audio : UAD-2 (DSP Apollo/Satellite) et UADx (natifs, achetés ou via Spark).

L'installeur dépose tout le catalogue, d'où les centaines de plugins « démo » dans les DAW.
Ordre des sources, de la plus fiable à la moins fiable :
  1. journaux PACE des UADx (achat, Spark, démo, démo expirée) : voir ua_sources ;
  2. notes du suivi interactif (vst-audit uad --suivi, data/uad_suivi.json) ;
  3. profil système UAD-2 (autorisations DSP), s'il a été généré avec l'Apollo branché ;
  4. liste [uad].possedes de config/licences.toml ;
  5. strict = true : tout le reste est « non acquis ».
Les autorisations brutes (~/Library/Preferences/Universal Audio/.uadauth) sont chiffrées.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import Config, matches
from ..models import License, LicenseResult, Plugin
from . import ua_sources

_PREFIX = re.compile(r"^(uadx|uad)\s+", re.I)


def is_uad(plugin: Plugin) -> bool:
    return plugin.bundle_id.startswith("com.uaudio.") or plugin.vendor.startswith("Universal Audio")


def plugin_id(plugin: Plugin) -> str:
    """« uaudio_minimoog » pour les bundles UADx, comme dans les journaux UAPW."""
    return re.sub(r"\(m\)$", "", Path(plugin.path).stem)


def family(plugin: Plugin) -> str:
    # les UADx sont livrés en bundles « uaudio_xxx » ; les UAD-2 en « UAD Xxx »
    if Path(plugin.path).name.startswith("uaudio_") or "UADx" in plugin.vendor:
        return "UADx natif"
    return "UAD-2 DSP"


def detect(plugin: Plugin, cfg: Config) -> LicenseResult | None:
    if not is_uad(plugin):
        return None
    kind = family(plugin)
    plugin.extra["uad_famille"] = kind

    if kind == "UADx natif" and (state := ua_sources.uadx_states().get(plugin_id(plugin))):
        plugin.extra["uad_vu_le"] = state.seen.date().isoformat()
        return LicenseResult(state.status, "UA journaux", state.detail)

    from .. import suivi  # import différé : suivi dépend de l'affichage, lui-même chargé après les détecteurs

    if note := suivi.notes().get(plugin_id(plugin)):
        detail = f"{note['label']} · suivi du {note['date'][:10]}" + (f" · {note['note']}" if note["note"] else "")
        return LicenseResult(License(note["status"]), "UA suivi", detail)

    if kind == "UAD-2 DSP" and (profile := ua_sources.system_profile()):
        if found := ua_sources.match_product(plugin.name, profile.products):
            status, label = found
            return LicenseResult(status, "UA profil", f"{label} · profil du {profile.date}")

    bare = _PREFIX.sub("", plugin.name)
    if cfg.uad_owned and (matches(bare, cfg.uad_owned) or matches(plugin.name, cfg.uad_owned)):
        return LicenseResult(License.LICENSED, "uad", f"{kind}, déclaré possédé")
    if cfg.uad_strict:
        return LicenseResult(License.NOT_OWNED, "uad", f"{kind}, aucune licence trouvée")
    hint = ("jamais ouvert en natif : ouvrez-le une fois dans une DAW" if kind == "UADx natif"
            else "générez le profil UAD (vst-audit uad)")
    return LicenseResult(License.UNKNOWN, "uad", f"{kind} : {hint}")
