"""Historique des analyses : data/history.sqlite + un instantané JSON par analyse."""

from __future__ import annotations

import json
import platform
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR
from .models import Plugin

DB_PATH = DATA_DIR / "history.sqlite"
SNAPSHOT_DIR = DATA_DIR / "scans"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    machine     TEXT NOT NULL,
    duration_s  REAL NOT NULL,
    total       INTEGER NOT NULL,
    hosts       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    scan_id  INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    uid      TEXT NOT NULL,
    name     TEXT NOT NULL,
    vendor   TEXT NOT NULL,
    format   TEXT NOT NULL,
    version  TEXT,
    verdict  TEXT NOT NULL,
    license  TEXT NOT NULL,
    health   TEXT NOT NULL,
    data     TEXT NOT NULL,
    PRIMARY KEY (scan_id, uid)
);
"""


@dataclass
class ScanInfo:
    id: int
    started_at: str
    machine: str
    duration_s: float
    total: int
    hosts: list[str]


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH  # résolu à l'appel (les tests redirigent DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save(plugins: list[Plugin], started: datetime, duration: float, hosts: list[str]) -> ScanInfo:
    machine = platform.node()
    with connect() as con:
        cur = con.execute(
            "INSERT INTO scans (started_at, machine, duration_s, total, hosts) VALUES (?,?,?,?,?)",
            (started.isoformat(timespec="seconds"), machine, duration, len(plugins), json.dumps(hosts)),
        )
        scan_id = cur.lastrowid
        con.executemany(
            "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(scan_id, p.uid, p.name, p.vendor, str(p.format), p.version, str(p.verdict),
              str(p.license), str(p.health), json.dumps(p.to_dict(), ensure_ascii=False))
             for p in plugins],
        )
    info = ScanInfo(scan_id, started.isoformat(timespec="seconds"), machine, duration, len(plugins), hosts)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = SNAPSHOT_DIR / f"{started:%Y-%m-%d_%H%M%S}_scan{scan_id}.json"
    snapshot.write_text(json.dumps(
        {"scan": info.__dict__, "plugins": [p.to_dict() for p in plugins]},
        ensure_ascii=False, indent=2,
    ))
    return info


def _info(row: sqlite3.Row) -> ScanInfo:
    return ScanInfo(row["id"], row["started_at"], row["machine"], row["duration_s"],
                    row["total"], json.loads(row["hosts"]))


def list_scans(limit: int = 20) -> list[ScanInfo]:
    if not DB_PATH.exists():
        return []
    with connect() as con:
        rows = con.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_info(r) for r in rows]


def load_scan(scan_id: int | None = None) -> tuple[ScanInfo, list[dict]] | None:
    """Charge une analyse (la dernière si scan_id est None)."""
    if not DB_PATH.exists():
        return None
    with connect() as con:
        if scan_id is None:
            row = con.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        else:
            row = con.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if not row:
            return None
        results = con.execute("SELECT data FROM results WHERE scan_id = ?", (row["id"],)).fetchall()
    return _info(row), [json.loads(r["data"]) for r in results]


def previous_id(scan_id: int) -> int | None:
    with connect() as con:
        row = con.execute("SELECT MAX(id) FROM scans WHERE id < ?", (scan_id,)).fetchone()
    return row[0]
