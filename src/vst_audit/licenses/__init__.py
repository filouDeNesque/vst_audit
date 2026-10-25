"""Détection du statut de licence.

Chaque détecteur expose `detect(plugin, cfg) -> LicenseResult | None`.
Ils sont essayés dans l'ordre : le premier qui conclut l'emporte.
Pour ajouter un éditeur : créer un module ici et l'insérer dans DETECTORS.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..models import Plugin
from . import free, inmusic, izotope, manual, uad

log = logging.getLogger(__name__)

DETECTORS = [manual, uad, izotope, inmusic, free]


def detect_all(plugins: list[Plugin], cfg: Config) -> None:
    for p in plugins:
        for detector in DETECTORS:
            try:
                result = detector.detect(p, cfg)
            except Exception as exc:
                log.warning("Détecteur %s en erreur sur %s : %s", detector.__name__, p.name, exc)
                continue
            if result:
                p.apply_license(result)
                break
