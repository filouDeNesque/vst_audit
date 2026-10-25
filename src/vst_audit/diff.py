"""Comparaison de deux analyses, plugin par plugin (formats regroupés)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .grouping import PluginGroup, group_plugins


@dataclass
class Change:
    group: PluginGroup
    what: str
    before: str
    after: str


@dataclass
class ScanDiff:
    added: list[PluginGroup] = field(default_factory=list)
    removed: list[PluginGroup] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def transitions(self) -> Counter[tuple[str, str]]:
        """(statut avant, statut après) -> nombre de plugins."""
        return Counter((c.before, c.after) for c in self.changed if c.what == "statut")


def _formats(g: PluginGroup) -> str:
    return " ".join(sorted({i["format"] for i in g.items}))


def _versions(g: PluginGroup) -> str:
    return ", ".join(sorted({i["version"] for i in g.items if i["version"]}))


def compare(old: list[dict], new: list[dict]) -> ScanDiff:
    before = {g.key: g for g in group_plugins(old)}
    after = {g.key: g for g in group_plugins(new)}
    diff = ScanDiff(
        added=[after[k] for k in after.keys() - before.keys()],
        removed=[before[k] for k in before.keys() - after.keys()],
    )
    for key in after.keys() & before.keys():
        a, b = before[key], after[key]
        for what, getter in (("statut", lambda g: str(g.verdict)), ("version", _versions), ("formats", _formats)):
            if getter(a) != getter(b):
                diff.changed.append(Change(b, what, getter(a), getter(b)))

    def order(g: PluginGroup) -> tuple[str, str]:
        return g.vendor.lower(), g.name.lower()

    diff.added.sort(key=order)
    diff.removed.sort(key=order)
    diff.changed.sort(key=lambda c: order(c.group))
    return diff
