"""Lecture de l'état des plugins vu par les DAW (sans les lancer)."""

from __future__ import annotations

import logging

from ..models import Plugin
from . import ableton, logic, mpc

log = logging.getLogger(__name__)

HOSTS = [ableton, logic, mpc]


def annotate(plugins: list[Plugin]) -> list[str]:
    """Ajoute à chaque plugin son état par DAW. Retourne les DAW effectivement lus."""
    found = []
    for host in HOSTS:
        try:
            if host.annotate(plugins):
                found.append(host.NAME)
        except Exception as exc:  # une DAW illisible ne doit pas bloquer l'analyse
            log.warning("Lecture %s impossible : %s", host.NAME, exc)
    return found
