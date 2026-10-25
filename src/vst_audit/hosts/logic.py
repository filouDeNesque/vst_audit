"""Résultats de validation Audio Unit de Logic (journaux AUScan*.plist)."""

from __future__ import annotations

import logging
import plistlib
import re
from pathlib import Path

from ..models import Format, HostState, Plugin, normalize

log = logging.getLogger(__name__)

NAME = "Logic"
LOG_DIR = Path.home() / "Library/Caches/AudioUnitCache/Logs"

# "[20-10-2026_18-32-47] UAD Ampeg B15N no need to start validator because of status success"
# "[...] Kikrame finished validator with result success"
_LINE = re.compile(
    r"^\[[^\]]+\] (?P<name>.+?) (?:no need to start validator because of status"
    r"|finished validator with result|validation result) (?P<result>[\w ]+?)\"?$"
)


def read_states() -> dict[str, HostState]:
    """nom AU normalisé -> dernier état connu (journaux lus du plus ancien au plus récent)."""
    states: dict[str, HostState] = {}
    for path in sorted(LOG_DIR.glob("AUScan*.plist"), key=lambda p: p.stat().st_mtime):
        try:
            data = plistlib.loads(path.read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError) as exc:
            log.debug("Journal Logic illisible %s : %s", path, exc)
            continue
        for lines in data.values():
            for line in lines if isinstance(lines, list) else []:
                m = _LINE.match(line)
                if m:
                    ok = m["result"].strip() == "success"
                    states[normalize(m["name"])] = HostState.OK if ok else HostState.FAILED
    return states


def annotate(plugins: list[Plugin]) -> bool:
    states = read_states()
    if not states:
        return False
    for p in plugins:
        if p.format == Format.AU:
            p.hosts[NAME] = states.get(normalize(p.name), HostState.UNSEEN)
    return True
