"""Actions ponctuelles sur un plugin, déclenchées depuis l'interface web."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import discovery
from .licenses import ua_sources


def reveal(path: Path) -> None:
    """Sélectionne le bundle dans le Finder."""
    subprocess.run(["open", "-R", str(path)], check=True, timeout=10)


def signature(path: Path) -> dict:
    ok, message = discovery.verify_signature(path)
    proc = subprocess.run(["codesign", "-dvv", str(path)], capture_output=True, text=True, timeout=60)
    details: dict[str, str] = {}
    for line in proc.stderr.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in ("Identifier", "Authority", "TeamIdentifier", "Timestamp", "Format"):
            details.setdefault(key, value.strip())  # la première « Authority » est le développeur
    return {"ok": ok, "message": message or ("Signature valide" if ok else ""), "details": details}


def auval(au_id: str) -> dict:
    """Validation Apple de l'Audio Unit (« auval -v type sous-type fabricant »)."""
    parts = au_id.split()
    if len(parts) != 3:
        raise ValueError(f"identifiant AU invalide : {au_id!r}")
    proc = subprocess.run(["auval", "-v", *parts], capture_output=True, text=True, timeout=180)
    out = proc.stdout + proc.stderr
    passed = "AU VALIDATION SUCCEEDED" in out
    lines = out.strip().splitlines()
    return {"ok": passed, "summary": "AU VALIDATION SUCCEEDED" if passed else
            next((l for l in reversed(lines) if "FAIL" in l or "ERROR" in l), lines[-1] if lines else ""),
            "output": "\n".join(lines[-60:])}


def ua_log_state(plugin_id: str) -> dict | None:
    """Relit le journal UADx d'un plugin (sans cache)."""
    state = ua_sources.read_uadx_states(only=plugin_id).get(plugin_id)
    if not state:
        return None
    return {"status": state.status.value, "label": state.label, "seen": state.seen.isoformat(timespec="seconds")}
