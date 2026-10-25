"""Base de plugins d'Ableton Live (Live-plugins-*.db, SQLite)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from ..models import Format, HostState, Plugin

log = logging.getLogger(__name__)

NAME = "Ableton"
DB_DIR = Path.home() / "Library/Application Support/Ableton/Live Database"


def _latest_db() -> Path | None:
    dbs = sorted(DB_DIR.glob("Live-plugins-*.db"), key=lambda p: p.stat().st_mtime)
    return dbs[-1] if dbs else None


def read_states() -> dict[str, tuple[HostState, int]]:
    """chemin du bundle -> (état, code scanstate).

    scanstate 1 = scan réussi ; les autres codes (2, 3 observés) = plugin rejeté par Live
    (signification exacte non documentée, le code est conservé). enabled 0 = désactivé.
    """
    db = _latest_db()
    if not db:
        return {}
    log.debug("Base Ableton : %s", db)
    # immutable=1 : lecture seule, sans verrou (Live peut être ouvert)
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    try:
        rows = con.execute(
            """SELECT m.path, m.scanstate, p.scanstate, p.enabled
               FROM plugin_modules m LEFT JOIN plugins p ON p.module_id = m.module_id"""
        ).fetchall()
    finally:
        con.close()

    rank = {HostState.FAILED: 0, HostState.DISABLED: 1, HostState.OK: 2}
    states: dict[str, tuple[HostState, int]] = {}
    for path, module_scan, plugin_scan, enabled in rows:
        code = module_scan if module_scan != 1 else (plugin_scan or 1)
        if code != 1:
            state = HostState.FAILED
        elif enabled == 0:
            state = HostState.DISABLED
        else:
            state = HostState.OK
        # un module peut contenir plusieurs plugins : on garde le pire état
        if path not in states or rank[state] < rank[states[path][0]]:
            states[path] = (state, code)
    return states


def annotate(plugins: list[Plugin]) -> bool:
    states = read_states()
    if not states:
        return False
    for p in plugins:
        if p.format in (Format.VST2, Format.VST3, Format.AU):
            state, code = states.get(p.path, (HostState.UNSEEN, 0))
            p.hosts[NAME] = state
            if state == HostState.FAILED:
                p.extra["ableton_scanstate"] = str(code)
    return True
