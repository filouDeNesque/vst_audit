"""Sonde exécutée dans un processus séparé : `python -m vst_audit.sonde.worker <bundle> [options]`.

1. charge le plugin (pedalboard) et fait tourner la boucle d'événements macOS quelques secondes :
   les vérifications de licence asynchrones (PACE, comptes éditeurs) ont le temps d'aboutir ;
2. lui envoie un signal test (1 s de son / 1 s de silence) ou des notes MIDI s'il s'agit d'un
   instrument, et mesure ce qui sort ;
3. en option, ouvre son interface, en fait une capture et lit le texte affiché (OCR Vision).

Le résultat est écrit en JSON sur la sortie standard, préfixé par « SONDE_RESULT ».
Un plugin qui plante ou bloque n'emporte que ce processus.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import sys
import time

import numpy as np

SR = 44100
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def stage(name: str) -> None:
    """Étape en cours, sur stderr : le lanceur sait où le plugin plante ou bloque."""
    print(f"SONDE_STAGE {name}", file=sys.stderr, flush=True)


def front_window(pid: int) -> int | None:
    """Plus grande fenêtre visible du processus `pid` (utilisé aussi par le lanceur)."""
    import Quartz

    wins = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
    mine = [w for w in wins if w.get("kCGWindowOwnerPID") == pid
            and w.get("kCGWindowIsOnscreen") and w.get("kCGWindowBounds", {}).get("Height", 0) > 60]
    if not mine:
        return None
    return max(mine, key=lambda w: w["kCGWindowBounds"]["Height"] * w["kCGWindowBounds"]["Width"])["kCGWindowNumber"]


def pump(seconds: float) -> None:
    from Foundation import NSDate, NSRunLoop

    end = time.time() + seconds
    while time.time() < end:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))


def load(path: str, name: str | None):
    import pedalboard

    try:
        return pedalboard.load_plugin(path)
    except ValueError as exc:  # bundle « shell » contenant plusieurs plugins
        loader = pedalboard.AudioUnitPlugin if path.endswith(".component") else pedalboard.VST3Plugin
        names = loader.get_plugin_names_for_file(path)
        if not names:
            raise exc
        choice = next((n for n in names if name and name.lower() in n.lower()), names[0])
        return pedalboard.load_plugin(path, plugin_name=choice)


def db(x) -> float:
    x = np.asarray(x, dtype=np.float64)
    return round(float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)), 1) if x.size else -240.0


def analyse_audio(plugin) -> dict:
    n = SR * 8
    t = np.arange(n) / SR
    gate = (t % 2.0) < 1.0
    tail = (~gate) & ((t % 2.0) > 1.8)  # fin des silences, après les queues de réverb
    if plugin.is_instrument:
        import mido

        msgs = [m for k in range(4) for m in (mido.Message("note_on", note=60, velocity=100, time=2.0 * k),
                                              mido.Message("note_off", note=60, time=2.0 * k + 1.0))]
        out = np.asarray(plugin(msgs, duration=8, sample_rate=SR, num_channels=2)).mean(axis=0)[:n]
        return {"notes_db": db(out[gate[: len(out)]]), "gaps_db": db(out[tail[: len(out)]]),
                "silent": db(out) < -100}
    rng = np.random.default_rng(1)
    sig = ((0.2 * np.sin(2 * np.pi * 440 * t) + 0.05 * rng.standard_normal(n)) * gate).astype(np.float32)
    out = np.asarray(plugin(np.stack([sig, sig]), SR)).mean(axis=0)[:n]
    diff = db(out - sig[: len(out)]) - db(sig)
    return {"out_db": db(out), "diff_db": round(diff, 1), "gaps_db": db(out[tail[: len(out)]]),
            "silent": db(out) < -100, "passthrough": diff < -100}


def read_editor(plugin, png: str, wait: float) -> dict:
    """Ouvre l'éditeur, capture sa fenêtre après `wait` secondes, puis la referme."""
    close = threading.Event()
    info: dict = {"window": False}

    def window_id() -> int | None:
        return front_window(os.getpid())

    def capture() -> list[str]:
        wid = window_id()
        if wid is None:
            return []
        subprocess.run(["screencapture", "-x", "-o", f"-l{wid}", png], capture_output=True)
        info["window"] = os.path.exists(png)
        return ocr(png) if info["window"] else []

    def grab() -> None:
        time.sleep(wait)
        # première ouverture parfois lente : on attend la fenêtre, puis qu'elle soit dessinée
        for _ in range(8):
            if window_id() is not None:
                break
            time.sleep(1)
        text = capture()
        if len(text) < 3:
            time.sleep(3)
            text = capture() or text
        info["text"] = text
        close.set()

    threading.Thread(target=grab, daemon=True).start()
    plugin.show_editor(close)
    info.setdefault("text", [])
    return info


def ocr(png: str) -> list[str]:
    import Vision
    from Foundation import NSURL

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(png), None)
    handler.performRequests_error_([request], None)
    lines = [o.topCandidates_(1)[0].string() for o in (request.results() or [])]
    return [EMAIL.sub("<e-mail>", line) for line in lines]  # rien de personnel dans les résultats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--name")
    parser.add_argument("--wait", type=float, default=4.0, help="attente de la vérification de licence")
    parser.add_argument("--gui", metavar="PNG", help="ouvrir l'éditeur et enregistrer sa capture ici")
    parser.add_argument("--gui-wait", type=float, default=10.0)
    args = parser.parse_args()

    result: dict = {}
    try:
        t0 = time.time()
        stage("chargement")
        plugin = load(args.path, args.name)
        result.update(loaded=True, load_s=round(time.time() - t0, 1),
                      instrument=bool(plugin.is_instrument), params=len(plugin.parameters))
        stage("vérification de licence")
        pump(args.wait)
        stage("rendu audio")
        result["audio"] = analyse_audio(plugin)
        if args.gui:
            # résultat partiel d'abord : si l'interface bloque, le lanceur garde au moins le son
            print("SONDE_PARTIAL " + json.dumps(result, ensure_ascii=False), file=sys.stderr, flush=True)
            stage("ouverture de l'interface")
            result["gui"] = read_editor(plugin, args.gui, args.gui_wait)
    except Exception as exc:  # le résultat partiel reste utile
        result.update(error=f"{type(exc).__name__}: {EMAIL.sub('<e-mail>', str(exc))[:300]}")
    print("SONDE_RESULT " + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
