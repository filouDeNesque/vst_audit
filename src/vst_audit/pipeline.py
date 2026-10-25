"""Chaîne d'analyse commune à la CLI et à l'API web."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config, discovery, hosts, licenses, overrides, sonde, suivi
from .licenses import ua_sources
from .models import Health, Plugin

log = logging.getLogger(__name__)

Step = Callable[[str, int, int], None]  # (étape, fait, total)


@dataclass
class ScanResult:
    plugins: list[Plugin]
    hosts: list[str]
    started: datetime
    duration: float
    roots: list[Path] = field(default_factory=list)


def clear_caches() -> None:
    """Les sources sont mises en cache pendant une analyse ; un serveur web doit les relire à chaque fois."""
    ua_sources.uadx_states.cache_clear()
    ua_sources.system_profile.cache_clear()
    suivi.notes.cache_clear()
    overrides.index.cache_clear()
    licenses.inmusic.unlocked_products.cache_clear()
    sonde.index.cache_clear()
    sonde.apollo_present.cache_clear()


def check_signature(p: Plugin) -> None:
    try:
        ok, message = discovery.verify_signature(Path(p.path))
        if not ok:
            p.add_issue(f"Signature invalide : {message}", Health.BROKEN)
    except Exception as exc:
        log.debug("codesign %s : %s", p.path, exc)


def run_scan(signatures: bool = False, on_step: Step | None = None) -> ScanResult:
    step = on_step or (lambda *_: None)
    clear_caches()
    started = datetime.now()
    t0 = time.perf_counter()

    roots = discovery.default_roots()
    log.info("Dossiers analysés : %s", ", ".join(map(str, roots)))
    cfg = config.load()
    if cfg.path:
        log.info("Configuration : %s", cfg.path)

    bundles = list(discovery.iter_bundles(roots))
    plugins: list[Plugin] = []
    for n, (path, fmt) in enumerate(bundles, 1):
        plugin = discovery.inspect_bundle(path, fmt)
        for issue in plugin.issues:
            log.debug("%s [%s] : %s", plugin.name, plugin.format, issue)
        plugins.append(plugin)
        step("Lecture des bundles", n, len(bundles))
    discovery.canonicalize_vendors(plugins)

    if signatures:
        done = 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            for _ in pool.map(check_signature, plugins):
                done += 1
                step("Signatures de code", done, len(plugins))

    step("État dans les DAW", 0, 0)
    found_hosts = hosts.annotate(plugins)
    licenses.detect_all(plugins, cfg)
    return ScanResult(plugins, found_hosts, started, time.perf_counter() - t0, roots)
