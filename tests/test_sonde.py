from vst_audit import sonde
from vst_audit.config import Config
from vst_audit.licenses import detect_all
from vst_audit.models import Format, License, Plugin

ARTURIA = ["REV PLATE-140 DEMO", "Authorization", "<e-mail>", "Welcome to Rev PLATE-140!",
           "This software is not activated on this computer", "Activate your license to proceed:",
           "Rev PLATE-140", "4 activations left", "Activate", "Demo", "The demo is limited to 20 minutes."]
AIR = ["Welcome Paul!", "Activate your product to get started.", "Product:", "AIR Vocal Doubler",
       "Don't have a serial key? Click to purchase a license at www.airmusictech.com", "10-DAY TRIAL", "TRY UNLICENSED"]
PROCESSED = {"out_db": -19.7, "diff_db": -1.4, "silent": False, "passthrough": False}


def probe(audio=None, text=None, **kw):
    r = {"loaded": True, "audio": audio or PROCESSED, **kw}
    if text is not None:
        r["gui"] = {"window": True, "text": text}
    return r


def test_activation_screens():
    f = sonde.classify(probe({"silent": True, "passthrough": False}, ARTURIA), "Arturia")
    assert f.status == License.KEY_REQUIRED and "4 activations restantes" in f.label
    f = sonde.classify(probe({"silent": True, "passthrough": False}, AIR), "AIR Music Technology")
    assert f.status == License.KEY_REQUIRED and "non activé" in f.label


def test_sound_rules():
    passthrough = {"silent": False, "passthrough": True}
    assert sonde.classify(probe(passthrough), "Universal Audio (UADx)", native_ua=True).status == License.NOT_OWNED
    # UAD-2 (DSP) : sans Apollo disponible, le son passe aussi intact -> pas de conclusion
    assert sonde.classify(probe(passthrough), "Universal Audio").status is None
    assert sonde.classify(probe(passthrough), "Acme").status is None  # réglages neutres possibles
    assert sonde.classify(probe({"silent": True, "passthrough": False}), "Acme").status is None
    working = sonde.classify(probe(PROCESSED, ["CUTOFF", "RESONANCE", "DRIVE", "MIX", "OUTPUT", "PRESET"]), "Acme")
    assert working.status == License.LICENSED
    assert sonde.classify(probe(PROCESSED), "Acme").status is None  # interface non vérifiée


def test_failures_are_not_conclusive():
    assert sonde.classify({"timeout": True}).status is None
    assert sonde.classify({"loaded": False, "error": "boom"}).status is None


def test_pick_item_prefers_native_au():
    items = [
        {"format": "VST2", "archs": ["arm64"], "health": "ok", "bundle_id": ""},
        {"format": "VST3", "archs": ["x86_64", "arm64"], "health": "ok", "bundle_id": ""},
        {"format": "AU", "archs": ["x86_64"], "health": "attention"},  # Intel : non chargeable
    ]
    assert sonde.pick_item(items)["format"] == "VST3"
    assert sonde.pick_item([{"format": "VST2", "archs": ["arm64"], "health": "ok"}]) is None


def test_unknown_result_does_not_hide_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(sonde, "SONDES_FILE", tmp_path / "s.json")
    p = Plugin(name="UADx Thing", vendor="Universal Audio (UADx)", format=Format.AU,
               path="/x/uaudio_thing.component", bundle_id="com.uaudio.effects.XXXX")
    sonde.save({"k": {"keys": p.group_keys, "status": "non acquis", "label": "non licencié", "date": "2026-10-25T10:00:00"}})
    sonde.index.cache_clear()
    detect_all([p], Config())  # le détecteur UAD ne sait rien (inconnu) : la sonde doit l'emporter
    assert p.license == License.NOT_OWNED and p.license_source == "sonde"
    sonde.index.cache_clear()


def test_host_plugins_and_crashes():
    mpc = [{"format": "AU", "archs": ["arm64"], "health": "ok", "bundle_id": "com.akaipro.mpc"}]
    assert "plugin-hôte" in sonde.unprobeable(mpc)
    ok = [{"format": "AU", "archs": ["arm64"], "health": "ok", "bundle_id": "com.acme.comp"}]
    assert sonde.unprobeable(ok) is None
    f = sonde.classify({"loaded": True, "crash": {"stage": "rendu audio", "signal": "SIGSEGV"}})
    assert f.status is None and "rendu audio" in f.label and "SIGSEGV" in f.label


class FakePopen:
    """Remplace subprocess.Popen : sortie et code de retour choisis, ou blocage."""

    def __init__(self, returncode=-11, stderr="", hang=False):
        import io

        self.returncode_final, self.stderr_text, self.hang, self.killed = returncode, stderr, hang, False
        self.stderr, self.stdout, self.pid = io.StringIO(stderr), io.StringIO(""), 99999

    def __call__(self, *args, **kwargs):
        return self

    def poll(self):
        return None if self.hang and not self.killed else self.returncode_final

    @property
    def returncode(self):
        return self.poll()

    def wait(self, timeout=None):
        return self.returncode_final

    def kill(self):
        self.killed = True


STAGES = "SONDE_STAGE chargement\nSONDE_STAGE vérification de licence\nSONDE_STAGE rendu audio\n"


def test_run_worker_reports_crash_stage(monkeypatch):
    monkeypatch.setattr(sonde.subprocess, "Popen", FakePopen(-11, STAGES))
    raw = sonde.run_worker("/x/Comp.component", "Comp", None)
    assert raw["crash"] == {"stage": "rendu audio", "signal": "SIGSEGV"} and raw["loaded"]
    assert "rendu audio (SIGSEGV)" in sonde.classify(raw).label


def test_run_worker_reports_hang_stage(monkeypatch):
    monkeypatch.setattr(sonde.subprocess, "Popen", FakePopen(stderr="SONDE_STAGE chargement\nSONDE_STAGE vérification de licence\n", hang=True))
    monkeypatch.setattr(sonde, "_activation_helper", lambda pid: None)
    monkeypatch.setattr(sonde, "_read_window", lambda pid: None)  # aucune fenêtre : simple lenteur
    raw = sonde.run_worker("/x/UAD.component", "UAD", None, timeout=1, watchdog=0.2)
    assert raw == {"timeout": True, "stage": "vérification de licence"}


def test_watchdog_reads_modal_window(monkeypatch):
    monkeypatch.setattr(sonde.subprocess, "Popen", FakePopen(stderr="SONDE_STAGE chargement\n", hang=True))
    monkeypatch.setattr(sonde, "_activation_helper", lambda pid: None)
    monkeypatch.setattr(sonde, "_read_window", lambda pid: ["This product is not activated"])
    raw = sonde.run_worker("/x/Slate.component", "Slate", None, timeout=10, watchdog=0.2)
    assert raw == {"loaded": False, "modal": {"stage": "chargement", "text": ["This product is not activated"]}}


def test_readable_gui_without_licence_screen():
    kontakt = ["KONTAKT PLAYER", "Libraries", "Files", "Database", "View", "Search"]
    f = sonde.classify(probe({"silent": True, "passthrough": False}, kontakt), "Native Instruments")
    assert f.status == License.LICENSED and "muet par défaut" in f.label
    ozone = ["Ozone", "ADVANCED", "Presets", "Analog", "dB", "Help us improve your experience."]
    f = sonde.classify(probe({"silent": False, "passthrough": True}, ozone), "iZotope")
    assert f.status == License.LICENSED and "neutre par défaut" in f.label


def test_fallback_to_vst3_after_au_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(sonde, "SONDES_FILE", tmp_path / "s.json")
    calls = []

    def fake_worker(path, name, png, **kw):
        calls.append(path)
        if path.endswith(".component"):
            return {"loaded": False, "crash": {"stage": "chargement", "signal": "SIGSEGV"}}
        return {"loaded": True, "audio": PROCESSED, "gui": {"window": True, "text": ["A", "B", "C", "D", "E"]}}

    monkeypatch.setattr(sonde, "run_worker", fake_worker)
    items = [{"format": f, "archs": ["arm64"], "health": "ok", "bundle_id": "com.acme.x", "name": "X",
              "path": f"/x/X.{ext}", "group_keys": ["acme|f:x"]} for f, ext in (("AU", "component"), ("VST3", "vst3"))]
    entry = sonde.probe_group("acme|f:x", "X", "Acme", items, gui=False)
    assert calls == ["/x/X.component", "/x/X.vst3"]
    assert entry["status"] == "licencié" and entry["format"] == "VST3"
    assert any("AU : le plugin a planté" in e for e in entry["evidence"])
    sonde.index.cache_clear()


def test_uad2_needs_apollo(monkeypatch):
    uad2 = [{"format": "AU", "archs": ["arm64"], "health": "ok", "bundle_id": "com.uaudio.effects.58AU",
             "path": "/c/UAD 4K Buss Compressor.component"}]
    uadx = [{"format": "AU", "archs": ["arm64"], "health": "ok", "bundle_id": "com.uaudio.effects.U3CM",
             "path": "/c/uaudio_176.component"}]
    monkeypatch.setattr(sonde, "apollo_present", lambda: False)
    assert "Apollo" in sonde.unprobeable(uad2)
    assert sonde.unprobeable(uadx) is None  # les UADx natifs n'ont pas besoin de DSP
    monkeypatch.setattr(sonde, "apollo_present", lambda: True)
    assert sonde.unprobeable(uad2) is None


def test_timeout_keeps_stage():
    f = sonde.classify({"timeout": True, "stage": "vérification de licence"})
    assert f.status is None and f.label == "bloqué pendant : vérification de licence"


def test_modal_window_at_load():
    raw = {"loaded": False, "modal": {"stage": "chargement", "text": ["Pedalboard", "Slate Digital Connect",
           "This product is not activated", "Sign in to activate"]}}
    f = sonde.classify(raw, "Slate Digital")
    assert f.status == License.KEY_REQUIRED and "fenêtre au chargement" in f.label
    raw = {"loaded": False, "modal": {"stage": "chargement", "text": ["Loading presets", "Please wait"]}}
    assert sonde.classify(raw, "Acme").status is None


def test_pace_activation_helper_and_preferred_format():
    f = sonde.classify({"loaded": False, "activation_helper": "Software Activation", "stage": "chargement"})
    assert f.status == License.KEY_REQUIRED and "PACE" in f.label
    items = [{"format": f, "archs": ["arm64"], "health": "ok", "path": f"/x/X.{f}"} for f in ("AU", "VST3")]
    assert [i["format"] for i in sonde.candidates(items)] == ["AU", "VST3"]
    assert [i["format"] for i in sonde.candidates(items, prefer="VST3")] == ["VST3", "AU"]


def test_needs_probe_and_free_beats_probe(tmp_path, monkeypatch):
    assert sonde.needs_probe(None)
    assert sonde.needs_probe({"status": None, "version": 1})               # non concluant, ancienne logique
    assert not sonde.needs_probe({"status": None, "version": sonde.VERSION})
    assert not sonde.needs_probe({"status": "licencié", "version": 1})    # concluant : on garde
    monkeypatch.setattr(sonde, "SONDES_FILE", tmp_path / "s.json")
    p = Plugin(name="ValhallaSupermassive", vendor="Valhalla DSP, LLC", format=Format.AU,
               path="/c/ValhallaSupermassive.component", bundle_id="com.ValhallaDSP.ValhallaSupermassive")
    sonde.save({"k": {"keys": p.group_keys, "status": "licencié", "label": "fonctionne", "date": "2026-10-25T15:00:00"}})
    sonde.index.cache_clear()
    detect_all([p], Config())
    assert p.license == License.FREE
    sonde.index.cache_clear()


def test_reclassify_stored(tmp_path, monkeypatch):
    monkeypatch.setattr(sonde, "SONDES_FILE", tmp_path / "s.json")
    sonde.save({
        "ozone": {"keys": ["a"], "status": None, "label": "son non traité", "vendor": "iZotope", "path": "/c/Ozone.component",
                  "raw": {"loaded": True, "audio": {"silent": False, "passthrough": True},
                          "gui_text": ["Ozone", "ADVANCED", "Presets", "Analog", "dB"]}},
        "crash": {"keys": ["b"], "status": None, "label": "planté", "vendor": "Acme", "path": "/c/X.component",
                  "raw": {"loaded": False, "crash": {"stage": "chargement", "signal": "SIGSEGV"}}},
    })
    assert sonde.reclassify_stored() == 1
    entries = sonde.load()
    assert entries["ozone"]["status"] == "licencié" and entries["ozone"]["version"] == sonde.VERSION
    assert entries["crash"]["status"] is None and sonde.needs_probe(entries["crash"])
    sonde.index.cache_clear()
