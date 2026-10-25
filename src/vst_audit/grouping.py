"""Regroupement des formats d'un même plugin (VST3 + AU + VST2…)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .models import Verdict

FORMAT_PRIORITY = ["AU", "VST3", "CLAP", "VST2"]  # l'AU porte le nom et l'éditeur les plus lisibles


@dataclass
class PluginGroup:
    """Un même plugin dans ses différents formats (VST3 + AU + VST2…)."""

    items: list[dict] = field(default_factory=list)

    @property
    def main(self) -> dict:
        return min(self.items, key=lambda i: FORMAT_PRIORITY.index(i["format"]))

    @property
    def key(self) -> str:
        """Identifiant stable d'une analyse à l'autre."""
        return self.main["group_keys"][0]

    @property
    def name(self) -> str:
        return self.main["name"]

    @property
    def vendor(self) -> str:
        return self.main["vendor"]

    @property
    def verdict(self) -> Verdict:
        """Le meilleur format décide : un VST3 fonctionnel suffit à rendre le plugin utilisable.
        Les formats cassés restent visibles (pastilles rouges, « formats à nettoyer »)."""
        return max((Verdict(i["verdict"]) for i in self.items), key=lambda v: v.rank)

    @property
    def broken_formats(self) -> list[str]:
        return sorted({i["format"] for i in self.items if i["verdict"] == Verdict.BROKEN})

    @property
    def issues(self) -> list[str]:
        """Remarques fusionnées : « Intel uniquement (VST2, VST3) » plutôt qu'une ligne par format."""
        formats: dict[str, list[str]] = defaultdict(list)
        for i in self.items:
            messages = list(i["issues"])
            for host, state in i["hosts"].items():
                if state not in ("ok", "non scanné"):
                    code = i["extra"].get(f"{host.lower()}_scanstate")
                    messages.append(f"{host} : {state}" + (f" (code {code})" if code else ""))
            for msg in messages:
                formats[msg].append(i["format"])
        if len(self.items) == 1:
            return list(formats)
        return [f"{msg} ({', '.join(sorted(set(fmts)))})" for msg, fmts in formats.items()]


def group_plugins(plugins: list[dict]) -> list[PluginGroup]:
    """Regroupe les formats d'un même plugin (union-find sur les clés de regroupement)."""
    parent = list(range(len(plugins)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first_with_key: dict[str, int] = {}
    for i, p in enumerate(plugins):
        for key in p["group_keys"]:
            if key in first_with_key:
                parent[find(i)] = find(first_with_key[key])
            else:
                first_with_key[key] = i

    groups: dict[int, PluginGroup] = defaultdict(PluginGroup)
    for i, p in enumerate(plugins):
        groups[find(i)].items.append(p)
    return sorted(groups.values(), key=lambda g: (g.verdict.rank, g.vendor.lower(), g.name.lower()))
