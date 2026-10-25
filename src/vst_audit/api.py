"""API HTTP locale entre l'outil d'analyse et l'interface web.

Lancement : `vst-audit web` (écoute sur 127.0.0.1 uniquement). Documentation interactive : /api/docs.
Toutes les réponses sont en JSON ; les données viennent des mêmes modules que la CLI.
"""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, actions, config, insights, overrides, pipeline, store, suivi
from .diff import ScanDiff, compare
from .grouping import PluginGroup, group_plugins
from .licenses import ua_sources
from .models import License, Verdict
from .vendors import portal_for

WEB_DIR = Path(__file__).parent / "web"

app = FastAPI(
    title="vst-audit API",
    version=__version__,
    description="Analyse des plugins audio installés : validité, licences, démos, historique.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


# --- Analyse en direct (mémoire) ------------------------------------------------

class _Live:
    """Dernière analyse en direct, non enregistrée. Relancée à la demande (moins d'une seconde)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.result: pipeline.ScanResult | None = None
        self.items: list[dict] = []

    def get(self, refresh: bool = False) -> tuple[pipeline.ScanResult, list[dict]]:
        with self.lock:
            if refresh or self.result is None:
                self.result = pipeline.run_scan()
                self.items = [p.to_dict() for p in self.result.plugins]
            return self.result, self.items

    def known_paths(self) -> set[str]:
        return {i["path"] for i in self.get()[1]}


live = _Live()


# --- Sérialisation ----------------------------------------------------------------

def group_json(g: PluginGroup, full: bool = False) -> dict:
    main = g.main
    formats: dict[str, str] = {}
    for item in g.items:  # pire statut par format (VST2 mono/stéréo UAD)
        v = Verdict(item["verdict"])
        if item["format"] not in formats or v.rank < Verdict(formats[item["format"]]).rank:
            formats[item["format"]] = v.value
    data = {
        "key": g.key,
        "name": g.name,
        "vendor": g.vendor,
        "verdict": g.verdict.value,
        "formats": [{"format": f, "verdict": v} for f, v in sorted(formats.items())],
        "versions": sorted({i["version"] for i in g.items if i["version"]}),
        "license": main["license"],
        "license_source": main["license_source"],
        "license_detail": main["license_detail"],
        "issues": g.issues,
        "broken_formats": g.broken_formats,
        "uad_family": main["extra"].get("uad_famille"),
    }
    if full:
        data["items"] = g.items
        data["portal"] = portal_for(g.vendor)
        data["override"] = overrides.lookup(sorted({k for i in g.items for k in i["group_keys"]}))
        if data["uad_family"] == "UADx natif":
            data["ua_plugin_id"] = Path(main["path"]).stem.removesuffix("(m)")
            data["ua_suivi"] = suivi.load().get(data["ua_plugin_id"])
    return data


def summary_json(groups: list[PluginGroup], items: list[dict]) -> dict:
    counts = Counter(g.verdict.value for g in groups)
    by_vendor: dict[str, Counter] = defaultdict(Counter)
    for g in groups:
        by_vendor[g.vendor][g.verdict.value] += 1
    vendors = [{"vendor": v, "total": sum(c.values()), "counts": dict(c)} for v, c in by_vendor.items()]
    vendors.sort(key=lambda r: tuple(-r["counts"].get(v.value, 0) for v in Verdict))
    return {
        "unique": len(groups),
        "bundles": len(items),
        "verdicts": [{"verdict": v.value, "count": counts.get(v.value, 0)} for v in Verdict],
        "formats": dict(Counter(i["format"] for i in items)),
        "vendors": vendors,
        "todo": [asdict(t) for t in insights.todo(groups)],
    }


def analysis_json(info: store.ScanInfo, items: list[dict]) -> dict:
    groups = group_plugins(items)
    return {
        "scan": asdict(info),
        "summary": summary_json(groups, items),
        "plugins": [group_json(g) for g in groups],
    }


def diff_json(diff: ScanDiff, old_id: int, new_id: int) -> dict:
    def short(g: PluginGroup) -> dict:
        return {"key": g.key, "name": g.name, "vendor": g.vendor, "verdict": g.verdict.value}

    return {
        "old": old_id, "new": new_id,
        "added": [short(g) for g in diff.added],
        "removed": [short(g) for g in diff.removed],
        "changed": [{**short(c.group), "what": c.what, "before": c.before, "after": c.after} for c in diff.changed],
        "transitions": [{"before": b, "after": a, "count": n} for (b, a), n in diff.transitions.most_common()],
    }


def _live_info(result: pipeline.ScanResult) -> store.ScanInfo:
    return store.ScanInfo(0, result.started.isoformat(timespec="seconds"), "analyse en direct",
                          result.duration, len(result.plugins), result.hosts)


def _group(key: str) -> PluginGroup:
    for g in group_plugins(live.get()[1]):
        if g.key == key:
            return g
    raise HTTPException(404, f"plugin introuvable : {key}")


def _checked_path(path: str) -> Path:
    """Les actions ne portent que sur des bundles trouvés par l'analyse (pas de chemin arbitraire)."""
    if path not in live.known_paths():
        raise HTTPException(403, "chemin inconnu de l'analyse")
    return Path(path)


# --- Modèles de requête -------------------------------------------------------------

LicenseValue = Literal["licencié", "gratuit", "démo", "non acquis", "clé requise"]


class OverrideIn(BaseModel):
    key: str
    status: LicenseValue
    note: str = ""


class PathIn(BaseModel):
    path: str


class SuiviIn(BaseModel):
    status: Literal["acheté", "spark", "démo", "non acquis"] = Field(description="ce que vous constatez")
    note: str = ""


SUIVI_CHOICES = {"acheté": "a", "spark": "s", "démo": "d", "non acquis": "n"}


# --- Routes : analyse ------------------------------------------------------------------

@app.get("/api/status", tags=["général"])
def status() -> dict:
    scans = store.list_scans(1)
    return {"version": __version__, "data_dir": str(config.DATA_DIR),
            "config_file": str(config.CONFIG_FILE) if config.CONFIG_FILE.exists() else None,
            "last_scan": asdict(scans[0]) if scans else None}


@app.get("/api/analysis", tags=["analyse"], summary="Analyse en direct (non enregistrée)")
def analysis(refresh: bool = Query(False, description="relancer l'analyse")) -> dict:
    result, items = live.get(refresh)
    return analysis_json(_live_info(result), items)


@app.post("/api/scans", tags=["historique"], summary="Lancer et enregistrer une analyse")
def create_scan(signatures: bool = False) -> dict:
    with live.lock:
        result = pipeline.run_scan(signatures=signatures)
        live.result, live.items = result, [p.to_dict() for p in result.plugins]
    info = store.save(result.plugins, result.started, result.duration, result.hosts)
    prev = store.previous_id(info.id)
    diff = None
    if prev and (old := store.load_scan(prev)):
        diff = diff_json(compare(old[1], live.items), prev, info.id)
    return {"scan": asdict(info), "diff": diff}


@app.get("/api/scans", tags=["historique"])
def list_scans(limit: int = 50) -> list[dict]:
    return [asdict(s) for s in store.list_scans(limit)]


@app.get("/api/scans/{scan_id}", tags=["historique"], summary="Analyse enregistrée")
def get_scan(scan_id: int) -> dict:
    loaded = store.load_scan(scan_id)
    if not loaded:
        raise HTTPException(404, "analyse introuvable")
    return analysis_json(*loaded)


@app.get("/api/diff", tags=["historique"], summary="Comparer deux analyses enregistrées")
def get_diff(old: int | None = None, new: int | None = None) -> dict:
    new_scan = store.load_scan(new)
    if not new_scan:
        raise HTTPException(404, "analyse introuvable")
    old = old or store.previous_id(new_scan[0].id)
    old_scan = store.load_scan(old) if old else None
    if not old_scan:
        raise HTTPException(400, "il faut au moins deux analyses")
    return diff_json(compare(old_scan[1], new_scan[1]), old_scan[0].id, new_scan[0].id)


# --- Routes : un plugin --------------------------------------------------------------

@app.get("/api/plugin", tags=["plugin"], summary="Détail d'un plugin (tous ses formats)")
def plugin_detail(key: str) -> dict:
    return group_json(_group(key), full=True)


@app.put("/api/plugin/override", tags=["plugin"], summary="Définir le statut de licence d'un plugin")
def set_override(body: OverrideIn) -> dict:
    g = _group(body.key)
    keys = [k for i in g.items for k in i["group_keys"]]
    overrides.set_status(g.key, keys, g.name, License(body.status), body.note)
    live.get(refresh=True)
    return group_json(_group(body.key), full=True)


@app.delete("/api/plugin/override", tags=["plugin"], summary="Revenir à la détection automatique")
def delete_override(key: str) -> dict:
    overrides.remove(key)
    live.get(refresh=True)
    return group_json(_group(key), full=True)


@app.post("/api/plugin/reveal", tags=["actions"], summary="Montrer le bundle dans le Finder")
def reveal(body: PathIn) -> dict:
    actions.reveal(_checked_path(body.path))
    return {"ok": True}


@app.post("/api/plugin/signature", tags=["actions"], summary="Vérifier la signature de code")
def signature(body: PathIn) -> dict:
    return actions.signature(_checked_path(body.path))


@app.post("/api/plugin/auval", tags=["actions"], summary="Valider l'Audio Unit avec auval")
def auval(body: PathIn) -> dict:
    path = _checked_path(body.path)
    item = next(i for i in live.get()[1] if i["path"] == str(path))
    if not item["extra"].get("au_id"):
        raise HTTPException(400, "ce bundle n'est pas une Audio Unit")
    return actions.auval(item["extra"]["au_id"])


# --- Routes : Universal Audio ------------------------------------------------------------

@app.get("/api/uad", tags=["uad"], summary="Sources de licence UA et liste de suivi des UADx")
def uad_overview() -> dict:
    result, items = live.get()
    profile = ua_sources.system_profile()
    groups = [g for g in group_plugins(items) if g.main["extra"].get("uad_famille")]
    entries = suivi.load()
    return {
        "sources": {
            "uadx_logs": len(ua_sources.uadx_states()),
            "profile": {"products": len(profile.products), "date": profile.date} if profile else None,
        },
        "plugins": [group_json(g) for g in groups],
        "suivi": [{**asdict(i), "entry": entries.get(i.plugin_id)}
                  for i in suivi.build_items(result.plugins, include_known=False)],
    }


@app.post("/api/uad/check/{plugin_id}", tags=["uad"], summary="Relire le journal d'un UADx")
def uad_check(plugin_id: str) -> dict:
    return {"state": actions.ua_log_state(plugin_id)}


@app.put("/api/uad/suivi/{plugin_id}", tags=["uad"], summary="Noter l'état constaté d'un UADx")
def uad_note(plugin_id: str, body: SuiviIn) -> dict:
    result, _ = live.get()
    item = next((i for i in suivi.build_items(result.plugins, include_known=True) if i.plugin_id == plugin_id), None)
    if not item:
        raise HTTPException(404, "UADx introuvable")
    entries = suivi.load()
    status, label = suivi.MANUAL[SUIVI_CHOICES[body.status]]
    suivi.record(entries, item, status, label, "manuel", body.note)
    live.get(refresh=True)
    return entries[plugin_id]


@app.post("/api/uad/suivi/{plugin_id}/journal", tags=["uad"], summary="Valider l'état lu dans le journal")
def uad_accept_log(plugin_id: str, note: str = "") -> dict:
    result, _ = live.get()
    item = next((i for i in suivi.build_items(result.plugins, include_known=True) if i.plugin_id == plugin_id), None)
    state = ua_sources.read_uadx_states(only=plugin_id).get(plugin_id)
    if not item or not state:
        raise HTTPException(404, "aucun état de licence dans le journal")
    entries = suivi.load()
    suivi.record(entries, item, state.status, state.label, "journal", note)
    live.get(refresh=True)
    return entries[plugin_id]


@app.delete("/api/uad/suivi/{plugin_id}", tags=["uad"], summary="Effacer la note d'un UADx")
def uad_forget(plugin_id: str) -> dict:
    entries = suivi.load()
    if entries.pop(plugin_id, None) is not None:
        suivi.save(entries)
        live.get(refresh=True)
    return {"ok": True}


# --- Interface web --------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
