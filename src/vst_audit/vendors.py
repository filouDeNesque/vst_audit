"""Où récupérer ses licences / clés par éditeur (utile après un changement d'ordinateur)."""

from __future__ import annotations

from .models import normalize

# fragment du nom d'éditeur normalisé -> outil ou compte où retrouver les licences
PORTALS = {
    "universal audio": "UA Connect · compte my.uaudio.com (My Products)",
    "uadx": "UA Connect · compte my.uaudio.com (My Products)",
    "native instruments": "Native Access",
    "izotope": "Native Access / iZotope Product Portal",
    "arturia": "Arturia Software Center",
    "valhalla": "compte Valhalla DSP (clés renvoyées par e-mail)",
    "softube": "Softube Central",
    "slate": "Slate Digital Connect / iLok",
    "akai": "inMusic Software Center",
    "inmusic": "inMusic Software Center",
    "splice": "application Splice",
    "klevgrand": "compte Klevgrand",
    "tokyo dawn": "compte Tokyo Dawn Labs",
    "output": "Output Hub",
    "gforce": "compte GForce",
    "baby audio": "compte BABY Audio",
    "steinberg": "Steinberg Activation Manager",
    "kv331": "compte KV331 Audio",
    "auburn": "compte Auburn Sounds (licence par e-mail)",
}


def portal_for(vendor: str) -> str | None:
    n = normalize(vendor)
    return next((tool for key, tool in PORTALS.items() if key in n), None)
