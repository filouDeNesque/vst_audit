"""Liste de plugins d'Akai MPC 3 (~/Library/Application Support/Akai/MPC 3/MPC 3.settings).

Le fichier contient la liste JUCE des plugins scannés (<KNOWNPLUGINS>) :
  <PLUGIN ... file="/Library/Audio/Plug-Ins/VST3/X.vst3"/>       VST2 / VST3 : chemin du bundle
  <PLUGIN ... file="AudioUnit:Effects/aufx,58AU,!UAD"/>          AU : type, sous-type, fabricant
  <BLACKLISTED id="…"/>                                          rejeté au scan (plantage, incompatible)
et la liste des plugins désactivés par l'utilisateur (DisabledPlugins.List).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ..models import Format, HostState, Plugin

log = logging.getLogger(__name__)

NAME = "MPC"
SETTINGS = Path.home() / "Library/Application Support/Akai/MPC 3/MPC 3.settings"

_PLUGIN_FILE = re.compile(r'<PLUGIN\b[^>]*?\bfile="([^"]+)"', re.S)
_BLACKLISTED = re.compile(r'<BLACKLISTED\s+id="([^"]+)"')
_DISABLED = re.compile(r'<VALUE name="DisabledPlugins\.List">(.*?)</VALUE>', re.S)
_QUOTED = re.compile(r'"([^"]+)"')


def plugin_ref(plugin: Plugin) -> str | None:
    """Identifiant du plugin tel que MPC l'écrit."""
    if plugin.format == Format.AU:
        au = plugin.extra.get("au_id", "").split()
        return ",".join(au) if len(au) == 3 else None  # « aufx,58AU,!UAD » (la catégorie est ignorée)
    return plugin.path


def _normalize(ref: str) -> str:
    # « AudioUnit:Effects/aufx,58AU,!UAD » -> « aufx,58AU,!UAD »
    return ref.split("/", 1)[1] if ref.startswith("AudioUnit:") and "/" in ref else ref


def parse(text: str) -> dict[str, HostState]:
    states = {_normalize(ref): HostState.OK for ref in _PLUGIN_FILE.findall(text)}
    if m := _DISABLED.search(text):
        for ref in _QUOTED.findall(m.group(1)) + re.findall(r'\bid="([^"]+)"', m.group(1)):
            states[_normalize(ref)] = HostState.DISABLED
    for ref in _BLACKLISTED.findall(text):
        states[_normalize(ref)] = HostState.FAILED
    return states


def annotate(plugins: list[Plugin]) -> bool:
    try:
        text = SETTINGS.read_text(errors="replace")
    except OSError:
        return False
    states = parse(text)
    if not states:
        return False
    log.debug("MPC 3 : %d plugins connus", len(states))
    for p in plugins:
        if p.format == Format.CLAP:
            continue
        ref = plugin_ref(p)
        p.hosts[NAME] = states.get(ref, HostState.UNSEEN) if ref else HostState.UNSEEN
    return True
