"""Vérification active : observer le plugin en fonctionnement plutôt que lire des fichiers.

Le plugin est chargé dans un processus séparé (sonde/worker.py). On en déduit son état :
  · interface : écran d'activation (« not activated », « 4 activations left », « TRY UNLICENSED »…) ;
  · son : traité, muet, ou passé tel quel (un UADx non licencié laisse passer le signal intact) ;
  · effet de bord utile : les UADx écrivent leur état PACE à jour dans leur journal UA.
Résultats : data/sondes.json (+ capture de l'interface dans data/sondes/<id>.png).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path

from ..config import DATA_DIR
from ..models import License

log = logging.getLogger(__name__)

SONDES_FILE = DATA_DIR / "sondes.json"
# À incrémenter quand la logique change : les résultats non concluants plus anciens seront retentés.
# 2 : repli VST3, délais par étape, vigie au chargement (PACE), UAD-2 sans Apollo, interface lisible.
VERSION = 2
CAPTURES_DIR = DATA_DIR / "sondes"
SAMPLE_FORMATS = ("AU", "VST3")  # VST2 : formats en fin de vie, souvent Intel

# Plugins qui sont eux-mêmes des hôtes (multi-sorties, sessions entières) : ils plantent dans
# l'hôte minimal de la sonde (constaté : MPC Beats, SIGSEGV dans AUBufferList au rendu).
HOST_PLUGINS = re.compile(
    r"^com\.(akaipro\.mpc|nektartech\.nektarine|native-instruments\.(komplete|maschine)|bluecataudio\.patchwork|gigperformer)",
    re.I)
SIGNALS = {-11: "SIGSEGV", -10: "SIGBUS", -6: "SIGABRT", -4: "SIGILL", -9: "SIGKILL"}


@dataclass
class Finding:
    status: License | None  # None : la sonde n'a pas permis de conclure
    label: str
    evidence: list[str] = field(default_factory=list)


# --- Choix du bundle ---------------------------------------------------------------

def unprobeable(items: list[dict]) -> str | None:
    """Raison pour laquelle ce plugin ne doit pas être sondé, ou None."""
    if any(HOST_PLUGINS.match(i["bundle_id"] or "") for i in items):
        return "plugin-hôte (MPC, Nektarine…) : non sondable, il planterait la sonde"
    if is_uad2(items) and not apollo_present():
        return "UAD-2 : aucun DSP disponible (Apollo non branché), branchez-le pour sonder"
    if pick_item(items) is None:
        return "aucun format sondable (AU/VST3 natif requis)"
    return None


def candidates(items: list[dict], prefer: str | None = None) -> list[dict]:
    """Bundles sondables, dans l'ordre d'essai : AU puis VST3, natifs Apple Silicon uniquement
    (un binaire Intel ne se charge pas ici). Un seul bundle par format."""
    native = [i for i in items if i["format"] in SAMPLE_FORMATS and "arm64" in i["archs"] and i["health"] != "invalide"]
    order = [prefer] + [f for f in SAMPLE_FORMATS if f != prefer] if prefer else list(SAMPLE_FORMATS)
    by_format = {}
    for i in sorted(native, key=lambda i: order.index(i["format"])):
        by_format.setdefault(i["format"], i)
    return list(by_format.values())


def pick_item(items: list[dict]) -> dict | None:
    found = candidates(items)
    return found[0] if found else None


def is_uad2(items: list[dict]) -> bool:
    """UAD-2 (DSP) : bundles « UAD xxx » d'Universal Audio, par opposition aux UADx « uaudio_xxx »."""
    return any((i["bundle_id"] or "").startswith("com.uaudio.") for i in items) and not any(
        Path(i["path"]).name.startswith("uaudio_") for i in items)


@cache
def apollo_present() -> bool:
    """Un Apollo / UAD-2 est-il branché ? Sans lui, un plugin UAD-2 affiche une alerte bloquante
    (« CreateUAD2Topology failed » dans son journal)."""
    try:
        out = subprocess.run(["system_profiler", "SPThunderboltDataType", "SPUSBDataType"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return True  # dans le doute, on laisse sonder
    return bool(re.search(r"apollo|universal audio|uad-2", out, re.I))


# --- Classement --------------------------------------------------------------------

_NOT_ACTIVATED = re.compile(r"not activated|activate your licen|activations? left", re.I)
_ACTIVATIONS = re.compile(r"(\d+)\s+activations?\s+left", re.I)
_UNLICENSED = re.compile(r"activate your product|try unlicensed|serial key|unlicensed|unregistered|register now", re.I)
_TRIAL = re.compile(r"\btrial\b|\bdemo\b|days? left|days? remaining", re.I)
_EXPIRED = re.compile(r"expired|has ended|trial is over", re.I)


def classify(result: dict, vendor: str = "", native_ua: bool = False) -> Finding:
    """native_ua : UADx natif (bundle « uaudio_… »). Un UAD-2 laisse aussi passer le son intact
    quand aucun DSP n'est disponible : ce n'est pas un indice de licence pour lui."""
    evidence: list[str] = []
    if result.get("timeout"):
        where = result.get("stage")
        return Finding(None, f"bloqué pendant : {where}" if where else "délai dépassé",
                       ["la sonde n'a pas répondu à temps (fenêtre modale ? chargement très long ?)"])
    if result.get("activation_helper"):
        return Finding(License.KEY_REQUIRED, "protection iLok / PACE : activation demandée",
                       [f"bloqué pendant : {result.get('stage')}, assistant « {result['activation_helper']} » lancé par le plugin"])
    if result.get("modal"):
        modal = result["modal"]
        found = classify({"loaded": True, "gui": {"window": True, "text": modal["text"]}}, vendor)
        lines = [line for line in modal["text"] if line != "Pedalboard"][:6]
        evidence = [f"bloqué pendant : {modal['stage']}, fenêtre ouverte : « " + " · ".join(lines) + " »"]
        if found.status in (License.KEY_REQUIRED, License.DEMO, License.NOT_OWNED):
            return Finding(found.status, found.label + " (fenêtre au chargement)", evidence)
        return Finding(None, f"bloqué par une fenêtre pendant : {modal['stage']}", evidence)
    if result.get("crash"):
        crash = result["crash"]
        return Finding(None, f"le plugin a planté pendant : {crash['stage']} ({crash['signal']})",
                       ["incompatibilité avec l'hôte de test, pas un indice de licence"])
    if not result.get("loaded"):
        return Finding(None, "chargement impossible", [result.get("error", "erreur inconnue")])

    audio = result.get("audio", {})
    gui = result.get("gui") or {}
    text = " · ".join(gui.get("text", []))
    licence_lines = [line for line in gui.get("text", [])
                     if _NOT_ACTIVATED.search(line) or _UNLICENSED.search(line) or _TRIAL.search(line) or _EXPIRED.search(line)]
    if licence_lines:
        evidence.append("interface : « " + " · ".join(licence_lines[:6]) + " »")
    if audio:
        if audio.get("passthrough"):
            evidence.append("son : passe intact, sans traitement")
        elif audio.get("silent"):
            evidence.append("son : aucun")
        else:
            evidence.append("son : traité normalement")

    # 1. ce que dit l'interface, le plus explicite
    if _NOT_ACTIVATED.search(text):
        m = _ACTIVATIONS.search(text)
        left = f" ({m[1]} activations restantes)" if m else ""
        return Finding(License.KEY_REQUIRED, f"licence possédée, non activée sur ce Mac{left}", evidence)
    if _EXPIRED.search(text):
        return Finding(License.NOT_OWNED, "essai expiré", evidence)
    if _UNLICENSED.search(text):
        return Finding(License.KEY_REQUIRED, "non activé : activation ou essai proposés", evidence)
    if _TRIAL.search(text):
        return Finding(License.DEMO, "en mode démo / essai", evidence)

    # 2. le son
    if audio.get("passthrough") and native_ua:
        return Finding(License.NOT_OWNED, "non licencié (le son passe sans traitement)", evidence)
    # 3. interface lisible sans aucun écran de licence : le plugin est utilisable, même s'il est muet
    #    ou neutre par défaut (instrument sans son chargé : Kontakt, Reaktor… ; EQ à plat : Ozone EQ…)
    if gui.get("window") and len(gui.get("text", [])) >= 5:
        if audio.get("silent"):
            return Finding(License.LICENSED, "fonctionne, aucun écran d'activation (muet par défaut)", evidence)
        if audio.get("passthrough"):
            return Finding(License.LICENSED, "fonctionne, aucun écran d'activation (neutre par défaut)", evidence)
        return Finding(License.LICENSED, "fonctionne, aucun écran d'activation", evidence)
    if audio.get("passthrough"):
        return Finding(None, "son non traité : réglages neutres ou plugin bloqué", evidence)
    if audio.get("silent"):
        return Finding(None, "aucun son : plugin bloqué ou en attente", evidence)
    if not gui:
        return Finding(None, "son traité ; interface non vérifiée", evidence)
    if gui.get("blocked"):
        return Finding(None, "son traité ; l'interface ne s'ouvre pas dans l'hôte de test", evidence)
    return Finding(None, "son traité ; interface illisible", evidence)


# --- Exécution ---------------------------------------------------------------------

BLOCKING_STAGES = ("chargement", "vérification de licence")
# au-delà, l'hôte de test est bloqué (constaté : rendu de l'AU de Kontakt 7, interface de SynthMaster 2)
STAGE_LIMITS = {"rendu audio": 30, "ouverture de l'interface": 45}
PACE_HELPER = re.compile(r"PACEEdenExperience|Software Activation|iLok License", re.I)


def _activation_helper(pid: int) -> tuple[int, str] | None:
    """Assistant d'activation PACE / iLok lancé par la sonde (processus enfant)."""
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] == str(pid) and PACE_HELPER.search(parts[2]):
            return int(parts[0]), Path(parts[2]).name
    return None


def _kill(proc: subprocess.Popen, *extra_pids: int) -> None:
    for pid in extra_pids:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    proc.kill()
    proc.wait()


def run_worker(path: str, name: str, gui_png: Path | None, wait: float = 4.0, timeout: int = 90,
               watchdog: float = 20.0) -> dict:
    cmd = [sys.executable, "-m", "vst_audit.sonde.worker", path, "--name", name, "--wait", str(wait)]
    if gui_png:
        gui_png.parent.mkdir(parents=True, exist_ok=True)
        gui_png.unlink(missing_ok=True)
        cmd += ["--gui", str(gui_png)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr_lines: list[str] = []
    reader = threading.Thread(target=lambda: stderr_lines.extend(proc.stderr), daemon=True)
    reader.start()
    started = stage_since = time.monotonic()
    last_stage = None
    while proc.poll() is None:
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            proc.kill()
            proc.wait()
            return {"timeout": True, "stage": _last_stage("".join(stderr_lines))}
        # vigie : toujours au chargement après `watchdog` s ET une fenêtre est ouverte -> c'est presque
        # toujours une fenêtre de licence modale : on la lit et on arrête là. Sans fenêtre, le plugin est
        # simplement lent à charger (Kontakt : ~30 s) et on continue d'attendre.
        stage = _last_stage("".join(stderr_lines))
        if stage != last_stage:
            last_stage, stage_since = stage, time.monotonic()
        if elapsed > watchdog and stage in BLOCKING_STAGES:
            helper = _activation_helper(proc.pid)
            if helper:  # protection PACE / iLok : le plugin attend son assistant d'activation
                _kill(proc, helper[0])
                return {"loaded": False, "activation_helper": helper[1], "stage": stage}
            text = _read_window(proc.pid)
            if text is not None:
                _kill(proc)
                return {"loaded": False, "modal": {"stage": stage, "text": text}}
        limit = STAGE_LIMITS.get(stage, wait + 15 if stage == "vérification de licence" else None)
        if limit and time.monotonic() - stage_since > limit:
            _kill(proc)
            partial = _partial("".join(stderr_lines))
            if partial and stage == "ouverture de l'interface":  # le son a été mesuré : on le garde
                return {**partial, "gui": {"window": False, "text": [], "blocked": True}}
            return {"timeout": True, "stage": stage}
        time.sleep(0.5)
    stdout = proc.stdout.read()
    reader.join(2)
    stderr = "".join(stderr_lines)
    line = next((l for l in stdout.splitlines() if l.startswith("SONDE_RESULT ")), None)
    if line is None:  # le plugin a fait planter le processus avant la fin
        stage = _last_stage(stderr)
        return {"loaded": stage not in (None, "chargement"), "crash": {
            "stage": stage or "démarrage", "signal": SIGNALS.get(proc.returncode, f"code {proc.returncode}")}}
    return json.loads(line[len("SONDE_RESULT "):])


def _read_window(pid: int) -> list[str] | None:
    """Capture et lit la fenêtre visible du processus de sonde. None : aucune fenêtre ouverte."""
    import tempfile

    from .worker import front_window, ocr

    wid = front_window(pid)
    if wid is None:
        return None
    png = Path(tempfile.mkdtemp(prefix="vst-audit-")) / "modal.png"
    subprocess.run(["screencapture", "-x", "-o", f"-l{wid}", str(png)], capture_output=True)
    return ocr(str(png)) if png.exists() else []


def _partial(stderr: str) -> dict | None:
    line = next((l for l in stderr.splitlines() if l.startswith("SONDE_PARTIAL ")), None)
    return json.loads(line[len("SONDE_PARTIAL "):]) if line else None


def _last_stage(stderr: str) -> str | None:
    stages = [l[len("SONDE_STAGE "):] for l in stderr.splitlines() if l.startswith("SONDE_STAGE ")]
    return stages[-1] if stages else None


def capture_id(group_key: str) -> str:
    return hashlib.sha1(group_key.encode()).hexdigest()[:16]


def probe_group(group_key: str, name: str, vendor: str, items: list[dict], gui: bool = True,
                prefer: str | None = None) -> dict:
    """Sonde un plugin (un de ses formats) et enregistre le résultat."""
    reason = unprobeable(items)
    keys = sorted({k for i in items for k in i["group_keys"]})
    item, raw, png, failed = None, {}, None, []
    if reason:
        finding = Finding(None, reason)
    else:
        png = CAPTURES_DIR / f"{capture_id(group_key)}.png" if gui else None
        started = time.monotonic()
        # un AU avec sidechain ou plusieurs bus peut planter l'hôte de test : on essaie alors le VST3
        for item in candidates(items, prefer):
            raw = run_worker(item["path"], item["name"], png)
            if not (raw.get("crash") or raw.get("timeout")):
                break  # assistant PACE ou fenêtre lue : inutile d'essayer un autre format
            failed.append(f"{item['format']} : {classify(raw).label}")
        finding = classify(raw, vendor, native_ua=Path(item["path"]).name.startswith("uaudio_"))
        if failed:
            finding.evidence.append("essais ratés : " + " ; ".join(failed))
        raw["duration_s"] = round(time.monotonic() - started, 1)
    entry = {
        "name": name, "vendor": vendor, "keys": keys,
        "path": item["path"] if item else None, "format": item["format"] if item else None,
        "date": datetime.now().isoformat(timespec="seconds"), "version": VERSION,
        "status": finding.status.value if finding.status else None,
        "label": finding.label, "evidence": finding.evidence,
        "capture": png.name if png and png.exists() else None,
        "raw": {k: v for k, v in raw.items() if k != "gui"} | (
            {"gui_text": raw["gui"].get("text", [])[:40]} if raw.get("gui") else {}),
    }
    entries = load()
    entries[group_key] = entry
    save(entries)
    index.cache_clear()
    log.info("Sonde %s : %s", name, finding.label)
    return entry


# --- Stockage ------------------------------------------------------------------------

def load(path: Path | None = None) -> dict[str, dict]:
    path = path or SONDES_FILE
    try:
        return json.loads(path.read_text()).get("plugins", {})
    except (OSError, ValueError):
        return {}


def save(entries: dict[str, dict], path: Path | None = None) -> None:
    path = path or SONDES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "plugins": entries}, ensure_ascii=False, indent=2))
    tmp.replace(path)


@cache
def index() -> dict[str, dict]:
    """clé de regroupement -> dernier résultat (pour le détecteur)."""
    return {key: entry for entry in load().values() for key in entry["keys"]}


def reclassify_stored() -> int:
    """Reclasse, avec la logique actuelle, les anciens résultats non concluants dont les mesures
    suffisent (son et texte d'interface enregistrés). Évite de relancer la sonde. Retourne le nombre résolu."""
    entries, solved = load(), 0
    for entry in entries.values():
        raw = dict(entry.get("raw") or {})
        if entry["status"] is not None or entry.get("version", 1) >= VERSION or not raw.get("loaded"):
            continue
        if raw.get("crash") or raw.get("timeout"):
            continue  # il faut resonder (repli VST3, vigie)
        if "gui_text" in raw:
            raw["gui"] = {"window": bool(raw["gui_text"]), "text": raw.pop("gui_text")}
        native = bool(entry.get("path")) and Path(entry["path"]).name.startswith("uaudio_")
        finding = classify(raw, entry.get("vendor", ""), native_ua=native)
        if finding.status is not None:
            entry.update(status=finding.status.value, label=finding.label + " (reclassé)",
                         evidence=finding.evidence, version=VERSION)
            solved += 1
    if solved:
        save(entries)
        index.cache_clear()
    return solved


def needs_probe(entry: dict | None) -> bool:
    """Faut-il (re)sonder ? Jamais sondé, ou non concluant avec une logique plus ancienne."""
    return entry is None or (entry["status"] is None and entry.get("version", 1) < VERSION)


def lookup(group_keys: list[str]) -> dict | None:
    idx = index()
    return next((idx[k] for k in group_keys if k in idx), None)


def finding_dict(entry: dict) -> dict:
    return {k: entry[k] for k in ("status", "label", "evidence", "date", "format", "capture")}


__all__ = ["Finding", "classify", "probe_group", "pick_item", "unprobeable", "load", "lookup", "finding_dict", "asdict"]
