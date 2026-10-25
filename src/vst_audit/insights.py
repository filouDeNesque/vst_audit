"""Conseils « À faire » calculés sur une analyse (partagés par la console et l'interface web)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .grouping import PluginGroup
from .models import Verdict
from .vendors import portal_for


@dataclass
class Tip:
    kind: str     # clé, uad, non_acquis, invalide, nettoyage
    icon: str
    title: str    # partie mise en avant
    text: str     # suite de la phrase
    filter: str = ""  # statut à filtrer dans l'interface pour voir les plugins concernés


def todo(groups: list[PluginGroup]) -> list[Tip]:
    tips: list[Tip] = []
    keys: dict[str, list[str]] = defaultdict(list)
    for g in groups:
        if g.verdict in (Verdict.KEY_REQUIRED, Verdict.DEMO):
            keys[g.vendor].append(g.name)
    for vendor, names in sorted(keys.items()):
        tool = portal_for(vendor) or "site / compte de l'éditeur"
        tips.append(Tip("clé", "⚿", f"{vendor} ({len(names)})", f"→ {tool}", Verdict.KEY_REQUIRED.value))

    uad_unknown = sum(1 for g in groups if g.verdict == Verdict.TO_CHECK
                      and any(i["license_source"] == "uad" for i in g.items))
    if uad_unknown:
        tips.append(Tip("uad", "ℹ", f"{uad_unknown} plugins UAD",
                        "sans statut : voir l'onglet / la commande UAD pour les compléter.", Verdict.TO_CHECK.value))
    not_owned = sum(1 for g in groups if g.verdict == Verdict.NOT_OWNED)
    if not_owned:
        tips.append(Tip("non_acquis", "∅", f"{not_owned} plugins non acquis",
                        "encombrent vos DAW (candidats au masquage, prochaine étape du projet).",
                        Verdict.NOT_OWNED.value))
    broken = sum(1 for g in groups if g.verdict == Verdict.BROKEN)
    if broken:
        tips.append(Tip("invalide", "✖", f"{broken} plugins inutilisables",
                        "(aucun format ne fonctionne) : réinstaller une version récente ou supprimer.",
                        Verdict.BROKEN.value))
    stale = sum(1 for g in groups if g.verdict != Verdict.BROKEN and g.broken_formats)
    if stale:
        tips.append(Tip("nettoyage", "✂", f"{stale} plugins ont des formats à nettoyer",
                        "(souvent d'anciens VST2 Intel) : un autre format fonctionne."))
    return tips
