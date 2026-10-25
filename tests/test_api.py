"""Tests de l'API sur des données factices (aucune lecture du vrai système)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from vst_audit import api, overrides, pipeline, store, suivi
from vst_audit.models import Format, Health, License, LicenseResult, Plugin


def fake_plugins() -> list[Plugin]:
    au = Plugin(name="Comp", vendor="Acme", format=Format.AU, path="/x/Comp.component",
                bundle_id="com.acme.comp", extra={"au_id": "aufx Comp Acme"})
    vst3 = Plugin(name="Comp", vendor="Acme", format=Format.VST3, path="/x/Comp.vst3", bundle_id="com.acme.comp")
    broken = Plugin(name="Old", vendor="Acme", format=Format.VST2, path="/x/Old.vst", bundle_id="com.acme.old")
    broken.add_issue("Binaire introuvable", Health.BROKEN)
    for p in (au, vst3):
        p.apply_license(LicenseResult(License.UNKNOWN, "test"))
    return [au, vst3, broken]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "h.sqlite")
    monkeypatch.setattr(store, "SNAPSHOT_DIR", tmp_path / "scans")
    monkeypatch.setattr(overrides, "OVERRIDES_FILE", tmp_path / "o.json")
    monkeypatch.setattr(suivi, "SUIVI_FILE", tmp_path / "s.json")
    overrides.index.cache_clear()

    def fake_scan(signatures=False, on_step=None):
        plugins = fake_plugins()
        # rejoue la détection manuelle pour que les overrides soient pris en compte
        for p in plugins:
            if entry := overrides.lookup(p.group_keys):
                p.apply_license(LicenseResult(License(entry["status"]), "défini (web)"))
        return pipeline.ScanResult(plugins, ["Ableton"], datetime(2026, 1, 1), 0.1)

    monkeypatch.setattr(pipeline, "run_scan", fake_scan)
    api.live.result = None
    return TestClient(api.app)


def test_analysis_groups_formats(client):
    data = client.get("/api/analysis").json()
    assert data["summary"]["unique"] == 2 and data["summary"]["bundles"] == 3
    comp = next(p for p in data["plugins"] if p["name"] == "Comp")
    assert [f["format"] for f in comp["formats"]] == ["AU", "VST3"]
    assert comp["verdict"] == "à vérifier"


def test_override_changes_verdict_then_reset(client):
    key = next(p["key"] for p in client.get("/api/analysis").json()["plugins"] if p["name"] == "Comp")
    r = client.put("/api/plugin/override", json={"key": key, "status": "licencié", "note": "facture 2024"})
    assert r.status_code == 200 and r.json()["verdict"] == "fonctionnel"
    assert r.json()["override"]["note"] == "facture 2024"
    r = client.delete("/api/plugin/override", params={"key": key})
    assert r.json()["verdict"] == "à vérifier" and r.json()["override"] is None


def test_actions_refuse_unknown_paths(client):
    client.get("/api/analysis")
    assert client.post("/api/plugin/reveal", json={"path": "/etc/passwd"}).status_code == 403
    assert client.post("/api/plugin/auval", json={"path": "/x/Comp.vst3"}).status_code == 400


def test_scans_saved_and_compared(client):
    first = client.post("/api/scans").json()
    assert first["diff"] is None
    second = client.post("/api/scans").json()
    assert second["diff"]["changed"] == []
    assert len(client.get("/api/scans").json()) == 2
    assert client.get(f"/api/scans/{first['scan']['id']}").json()["summary"]["unique"] == 2


def test_tests_never_touch_real_data(client):
    client.post("/api/scans")
    assert store.DB_PATH.parent != api.config.DATA_DIR


def test_web_page_served(client):
    assert "vst-audit" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
