"""Détection du statut de licence.

Chaque détecteur expose `detect(plugin, cfg) -> LicenseResult | None`.
Ils sont essayés dans l'ordre : le premier résultat concluant l'emporte. Un résultat « inconnu »
n'arrête pas la recherche ; le premier rencontré sert de repli (pour son conseil).
Pour ajouter un éditeur : créer un module ici et l'insérer dans DETECTORS.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..models import License, LicenseResult, Plugin
from . import free, inmusic, izotope, manual, sonde, uad

log = logging.getLogger(__name__)

# manual : choix de l'utilisateur · uad : journaux UA (plus précis que la sonde : Spark ou achat)
# free : plugins connus pour être gratuits (une sonde les verrait « licenciés »)
# sonde : comportement observé · puis indices propres à chaque éditeur
DETECTORS = [manual, uad, free, sonde, izotope, inmusic]


def detect_all(plugins: list[Plugin], cfg: Config) -> None:
    for p in plugins:
        fallback: LicenseResult | None = None
        for detector in DETECTORS:
            try:
                result = detector.detect(p, cfg)
            except Exception as exc:
                log.warning("Détecteur %s en erreur sur %s : %s", detector.__name__, p.name, exc)
                continue
            if result is None:
                continue
            if result.status != License.UNKNOWN:
                p.apply_license(result)
                break
            fallback = fallback or result
        else:
            if fallback:
                p.apply_license(fallback)
