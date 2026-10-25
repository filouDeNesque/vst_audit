"""Modèle de données d'un plugin analysé."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import PurePath


class Format(StrEnum):
    VST2 = "VST2"
    VST3 = "VST3"
    AU = "AU"
    CLAP = "CLAP"


class Health(StrEnum):
    """État technique du bundle (indépendant de la licence)."""

    OK = "ok"
    WARNING = "attention"
    BROKEN = "invalide"


class License(StrEnum):
    LICENSED = "licencié"
    FREE = "gratuit"
    DEMO = "démo"
    NOT_OWNED = "non acquis"
    KEY_REQUIRED = "clé requise"
    UNKNOWN = "inconnu"


class HostState(StrEnum):
    OK = "ok"
    DISABLED = "désactivé"
    FAILED = "échec"
    UNSEEN = "non scanné"


class Verdict(StrEnum):
    """Synthèse affichée à l'utilisateur, par ordre de gravité décroissante."""

    BROKEN = "invalide"
    KEY_REQUIRED = "clé requise"
    NOT_OWNED = "non acquis"
    DEMO = "démo"
    DISABLED = "désactivé"
    TO_CHECK = "à vérifier"
    OK = "fonctionnel"

    @property
    def rank(self) -> int:
        return list(Verdict).index(self)


@dataclass
class LicenseResult:
    status: License
    source: str  # quel détecteur a conclu
    detail: str = ""


@dataclass
class Plugin:
    name: str
    vendor: str
    format: Format
    path: str
    bundle_id: str = ""
    vendor_from_metadata: bool = False
    version: str = ""
    archs: list[str] = field(default_factory=list)
    health: Health = Health.OK
    issues: list[str] = field(default_factory=list)
    license: License = License.UNKNOWN
    license_source: str = ""
    license_detail: str = ""
    # hôte -> HostState (ex. {"Ableton": "ok", "Logic": "échec"})
    hosts: dict[str, str] = field(default_factory=dict)
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.format}:{self.path}"

    @property
    def group_keys(self) -> list[str]:
        """Clés partagées par les différents formats d'un même plugin : même nom de
        bundle (« UAD Pultec EQP-1A.vst3 » / « .component ») ou même nom affiché."""
        company = self.bundle_id.split(".")[1].lower() if self.bundle_id.count(".") >= 2 else ""
        owner = company or normalize(self.vendor)
        stem = re.sub(r"\(m\)$", "", PurePath(self.path).stem)  # variantes mono VST2 de UAD
        return [f"{owner}|f:{normalize(stem)}", f"{owner}|n:{normalize(self.name)}"]

    def add_issue(self, message: str, severity: Health = Health.WARNING) -> None:
        self.issues.append(message)
        order = list(Health)
        if order.index(severity) > order.index(self.health):
            self.health = severity

    def apply_license(self, result: LicenseResult) -> None:
        self.license = result.status
        self.license_source = result.source
        self.license_detail = result.detail

    @property
    def verdict(self) -> Verdict:
        if self.health == Health.BROKEN or HostState.FAILED in self.hosts.values():
            return Verdict.BROKEN
        mapping = {
            License.KEY_REQUIRED: Verdict.KEY_REQUIRED,
            License.NOT_OWNED: Verdict.NOT_OWNED,
            License.DEMO: Verdict.DEMO,
        }
        if self.license in mapping:
            return mapping[self.license]
        if HostState.DISABLED in self.hosts.values():
            return Verdict.DISABLED
        if self.license == License.UNKNOWN or self.health == Health.WARNING:
            return Verdict.TO_CHECK
        return Verdict.OK

    def to_dict(self) -> dict:
        data = asdict(self)
        data["uid"] = self.uid
        data["group_keys"] = self.group_keys
        data["verdict"] = str(self.verdict)
        return data


_STRIP = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Forme comparable d'un nom : minuscules, sans ponctuation."""
    return _STRIP.sub(" ", text.lower()).strip()
