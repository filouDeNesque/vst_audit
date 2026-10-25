"""Découverte des bundles de plugins et contrôles techniques (sans les charger)."""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import plistlib
import re
import struct
import subprocess
from collections.abc import Iterator
from pathlib import Path

from .models import Format, Health, Plugin, company_from_bundle_id, normalize

log = logging.getLogger(__name__)

EXTENSIONS = {
    ".vst": Format.VST2,
    ".vst3": Format.VST3,
    ".component": Format.AU,
    ".clap": Format.CLAP,
}

FOLDERS = {
    Format.VST2: "VST",
    Format.VST3: "VST3",
    Format.AU: "Components",
    Format.CLAP: "CLAP",
}


def default_roots() -> list[Path]:
    bases = [Path("/Library/Audio/Plug-Ins"), Path.home() / "Library/Audio/Plug-Ins"]
    return [b / sub for b in bases for sub in FOLDERS.values() if (b / sub).is_dir()]


def iter_bundles(roots: list[Path]) -> Iterator[tuple[Path, Format]]:
    """Parcourt récursivement les dossiers (les éditeurs rangent parfois en sous-dossiers)."""
    for root in roots:
        for dirpath, dirnames, _ in os.walk(root):
            keep = []
            for d in dirnames:
                fmt = EXTENSIONS.get(Path(d).suffix.lower())
                if fmt:
                    yield Path(dirpath) / d, fmt
                else:
                    keep.append(d)
            dirnames[:] = keep  # ne pas descendre dans les bundles


# --- Mach-O -----------------------------------------------------------------

_CPU = {0x01000007: "x86_64", 0x0100000C: "arm64", 7: "i386"}


def macho_archs(binary: Path) -> list[str]:
    """Lit l'en-tête Mach-O (fat ou thin) pour lister les architectures."""
    try:
        with binary.open("rb") as f:
            head = f.read(8)
            if len(head) < 8:
                return []
            magic = struct.unpack(">I", head[:4])[0]
            if magic in (0xCAFEBABE, 0xCAFEBABF):  # fat (32 / 64 bits)
                count = struct.unpack(">I", head[4:8])[0]
                size = 20 if magic == 0xCAFEBABE else 32
                archs = []
                for _ in range(min(count, 16)):
                    cpu = struct.unpack(">I", f.read(size)[:4])[0]
                    archs.append(_CPU.get(cpu, hex(cpu)))
                return archs
            magic_le, cpu = struct.unpack("<II", head)
            if magic_le in (0xFEEDFACF, 0xFEEDFACE):
                return [_CPU.get(cpu, hex(cpu))]
    except OSError as exc:
        log.debug("Lecture Mach-O impossible %s : %s", binary, exc)
    return []


# --- Attributs étendus --------------------------------------------------------

_libc = ctypes.CDLL(None, use_errno=True)
_libc.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                           ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
_libc.getxattr.restype = ctypes.c_ssize_t


def has_xattr(path: Path, name: str) -> bool:
    return _libc.getxattr(os.fsencode(path), name.encode(), None, 0, 0, 0) >= 0


def verify_signature(bundle: Path) -> tuple[bool, str]:
    """codesign --verify (lent : à activer avec --signatures).

    Sans --strict : cette option rejette aussi les attributs Finder (« detritus »), sans rapport
    avec la validité de la signature.
    """
    proc = subprocess.run(
        ["codesign", "--verify", str(bundle)],
        capture_output=True, text=True, timeout=120,
    )
    message = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""
    return proc.returncode == 0, message


# --- Lecture d'un bundle ------------------------------------------------------

def _read_plist(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            return plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError) as exc:
        log.debug("Info.plist illisible %s : %s", path, exc)
        return {}


def _read_moduleinfo(bundle: Path) -> dict:
    path = bundle / "Contents/Resources/moduleinfo.json"
    try:
        return json.loads(path.read_text(errors="replace"))
    except (OSError, ValueError):
        return {}


def _vendor_from_bundle_id(bundle_id: str) -> str:
    company = company_from_bundle_id(bundle_id)
    return bundle_id.split(".")[1] if company else ""  # casse d'origine


def _find_binary(bundle: Path, executable: str | None) -> Path | None:
    macos = bundle / "Contents/MacOS"
    if executable and (macos / executable).is_file():
        return macos / executable
    # CFBundleExecutable vide ou faux : certains éditeurs l'oublient, l'hôte prend alors le seul binaire présent
    candidates = [f for f in macos.iterdir() if f.is_file()] if macos.is_dir() else []
    if len(candidates) == 1:
        return candidates[0]
    return next((f for f in candidates if f.name == bundle.stem), None)


def inspect_bundle(bundle: Path, fmt: Format) -> Plugin:
    info = _read_plist(bundle / "Contents/Info.plist")
    bundle_id = info.get("CFBundleIdentifier", "")
    name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or bundle.stem
    vendor = ""

    au_id = ""
    if fmt == Format.AU and info.get("AudioComponents"):
        component = info["AudioComponents"][0]
        au_id = " ".join(str(component.get(k, "")) for k in ("type", "subtype", "manufacturer"))
        # "Universal Audio (UADx): UADx 176 Compressor"
        full = component.get("name", "")
        if ": " in full:
            vendor, name = full.split(": ", 1)
    elif fmt == Format.VST3:
        module = _read_moduleinfo(bundle)
        vendor = module.get("Factory Info", {}).get("Vendor", "")
        audio = [c for c in module.get("Classes", []) if c.get("Category") == "Audio Module Class"]
        if audio:
            name = audio[0].get("Name", name)

    plugin = Plugin(
        name=name,
        vendor=vendor or _vendor_from_bundle_id(bundle_id) or "Inconnu",
        vendor_from_metadata=bool(vendor),
        format=fmt,
        path=str(bundle),
        bundle_id=bundle_id,
        version=str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""),
    )
    if au_id:
        plugin.extra["au_id"] = au_id  # « aufx 58AU !UAD », pour auval

    if not info:
        plugin.add_issue("Info.plist illisible", Health.BROKEN)
        return plugin

    binary = _find_binary(bundle, info.get("CFBundleExecutable"))
    if not binary:
        plugin.add_issue("Binaire introuvable", Health.BROKEN)
    else:
        plugin.archs = macho_archs(binary)
        if not plugin.archs:
            plugin.add_issue("Binaire Mach-O invalide", Health.BROKEN)
        elif platform.machine() == "arm64" and "arm64" not in plugin.archs:
            plugin.add_issue("Intel uniquement (Rosetta)")

    if not (bundle / "Contents/_CodeSignature").exists():
        plugin.add_issue("Non signé")
    if has_xattr(bundle, "com.apple.quarantine"):
        plugin.add_issue("Quarantaine Gatekeeper")

    return plugin


def canonicalize_vendors(plugins: list[Plugin]) -> None:
    """Unifie les noms d'éditeurs : un VST2 n'expose que son bundle id (« auburnsounds »),
    on reprend le nom lisible (« Auburn Sounds ») trouvé dans l'AU ou le VST3 du même éditeur."""
    by_company: dict[str, str] = {}
    by_compact: dict[str, str] = {}
    for p in plugins:
        if p.vendor_from_metadata:
            company = _vendor_from_bundle_id(p.bundle_id).lower()
            if company:
                by_company.setdefault(company, p.vendor)
            by_compact.setdefault(_compact(p.vendor), p.vendor)
    for p in plugins:
        if not p.vendor_from_metadata:
            p.vendor = (by_company.get(_vendor_from_bundle_id(p.bundle_id).lower())
                        or by_compact.get(_compact(p.vendor)) or p.vendor)
    # éditeur toujours inconnu : on reprend celui d'un bundle du même nom (« Kontakt.vst3 » / « Kontakt.component »)
    by_stem = {normalize(Path(p.path).stem): p.vendor for p in plugins if p.vendor_from_metadata}
    for p in plugins:
        if p.vendor == "Inconnu":
            p.vendor = by_stem.get(normalize(Path(p.path).stem), p.vendor)
    # variantes d'un même nom (« Valhalla DSP, LLC » / « ValhallaDSP ») : la plus fréquente gagne
    counts: dict[str, dict[str, int]] = {}
    for p in plugins:
        variants = counts.setdefault(_compact(p.vendor), {})
        variants[p.vendor] = variants.get(p.vendor, 0) + 1
    for p in plugins:
        variants = counts[_compact(p.vendor)]
        p.vendor = max(variants, key=variants.get)


def _compact(vendor: str) -> str:
    v = re.sub(r"[^a-z0-9]", "", vendor.lower())
    return re.sub(r"(llc|inc|ltd|gmbh|sas)$", "", v)
