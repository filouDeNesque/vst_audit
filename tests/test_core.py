import struct

from vst_audit.config import matches, patterns
from vst_audit.diff import compare
from vst_audit.discovery import canonicalize_vendors, macho_archs
from vst_audit.grouping import group_plugins
from vst_audit.hosts.logic import _LINE
from vst_audit.models import Format, Health, HostState, License, LicenseResult, Plugin, Verdict


def make(name="Comp", vendor="Acme", fmt=Format.VST3, path=None, bundle_id="com.acme.comp", **kw):
    ext = {Format.VST3: "vst3", Format.AU: "component", Format.VST2: "vst", Format.CLAP: "clap"}[fmt]
    return Plugin(name=name, vendor=vendor, format=fmt, path=path or f"/x/{name}.{ext}",
                  bundle_id=bundle_id, **kw)


def test_patterns_match_without_case_or_punctuation():
    pats = patterns(["1176", "Pultec EQP-1A Legacy", "LA-2A*Gray"])
    assert matches("UAD UA 1176LN Legacy", pats)
    assert matches("uad pultec eqp 1a legacy", pats)
    assert matches("LA-2A Gray", pats)
    assert not matches("UAD Fairchild 670", pats)


def test_macho_fat_and_thin(tmp_path):
    fat = tmp_path / "fat"
    fat.write_bytes(struct.pack(">II", 0xCAFEBABE, 2)
                    + struct.pack(">5I", 0x01000007, 3, 0, 0, 0)
                    + struct.pack(">5I", 0x0100000C, 0, 0, 0, 0))
    thin = tmp_path / "thin"
    thin.write_bytes(struct.pack("<II", 0xFEEDFACF, 0x01000007))
    junk = tmp_path / "junk"
    junk.write_bytes(b"not a binary")
    assert macho_archs(fat) == ["x86_64", "arm64"]
    assert macho_archs(thin) == ["x86_64"]
    assert macho_archs(junk) == []


def test_verdict_priority():
    p = make()
    p.apply_license(LicenseResult(License.LICENSED, "test"))
    assert p.verdict == Verdict.OK
    p.hosts["Ableton"] = HostState.DISABLED
    assert p.verdict == Verdict.DISABLED
    p.apply_license(LicenseResult(License.DEMO, "test"))
    assert p.verdict == Verdict.DEMO
    p.add_issue("Binaire introuvable", Health.BROKEN)
    assert p.verdict == Verdict.BROKEN


def test_vendor_canonicalized_from_bundle_id():
    au = make(fmt=Format.AU, vendor="Auburn Sounds", bundle_id="com.auburnsounds.audiounit.Couture",
              vendor_from_metadata=True)
    vst2 = make(fmt=Format.VST2, vendor="auburnsounds", bundle_id="com.auburnsounds.vst.Couture")
    canonicalize_vendors([au, vst2])
    assert vst2.vendor == "Auburn Sounds"


def test_grouping_by_bundle_name_or_display_name():
    # même nom de bundle, noms affichés différents (cas UADx)
    au = make("UADx 1176 FET Compressor", fmt=Format.AU, path="/c/uaudio_ua_1176.component",
              bundle_id="com.uaudio.effects.U3CM")
    vst3 = make("uaudio_ua_1176", path="/v/uaudio_ua_1176.vst3", bundle_id="com.uaudio.effects.U3CM")
    # même nom affiché, bundles différents (cas iZotope)
    iz_au = make("Ozone 11 Equalizer", fmt=Format.AU, path="/c/iZOzone11EqualizerAUHook.component",
                 bundle_id="com.izotope.AU.OZONE11EQ")
    iz_vst3 = make("Ozone 11 Equalizer", path="/v/Ozone 11 Equalizer.vst3", bundle_id="com.izotope.VST3.OZONE11EQ")
    groups = group_plugins([p.to_dict() for p in (au, vst3, iz_au, iz_vst3)])
    assert sorted(len(g.items) for g in groups) == [2, 2]
    assert {g.name for g in groups} == {"UADx 1176 FET Compressor", "Ozone 11 Equalizer"}


def test_group_verdict_uses_best_format():
    vst3 = make()
    vst3.apply_license(LicenseResult(License.LICENSED, "test"))
    vst2 = make(fmt=Format.VST2)
    vst2.apply_license(LicenseResult(License.LICENSED, "test"))
    vst2.add_issue("Intel uniquement (Rosetta)")
    vst2.hosts["Ableton"] = HostState.FAILED
    [group] = group_plugins([vst3.to_dict(), vst2.to_dict()])
    assert group.verdict == Verdict.OK
    assert group.broken_formats == ["VST2"]


def test_diff_detects_status_change_added_removed():
    a, b = make("A"), make("B")
    old = [a.to_dict(), b.to_dict()]
    a.apply_license(LicenseResult(License.NOT_OWNED, "test"))
    new = [a.to_dict(), make("C").to_dict()]
    diff = compare(old, new)
    assert [g.name for g in diff.added] == ["C"]
    assert [g.name for g in diff.removed] == ["B"]
    assert diff.transitions == {("à vérifier", "non acquis"): 1}


def test_logic_log_line():
    m = _LINE.match("[20-10-2026_18-32-47] UAD Ampeg B15N no need to start validator because of status success")
    assert m and m["name"] == "UAD Ampeg B15N" and m["result"] == "success"
    m = _LINE.match("[20-10-2026_18-32-47] Kikrame finished validator with result failed")
    assert m and m["result"] == "failed"
    assert not _LINE.match("[20-10-2026_18-32-47] Kikrame start validator with result not completed")


def test_ua_pace_log_and_demo_expiry():
    from datetime import datetime

    from vst_audit.licenses.ua_sources import demo_status, parse_pace_log
    from vst_audit.models import License

    text = ("x Update PACE State after []: [eLicenseState_FullActive]\n"
            "y Update PACE State after [DEMO ACTIVE - 2 Days]: [eLicenseState_DemoActive]\n")
    assert parse_pace_log(text) == ("DemoActive", "DEMO ACTIVE - 2 Days")
    seen = datetime(2025, 8, 22)
    assert demo_status("DEMO ACTIVE - 77 Days", seen, now=datetime(2025, 9, 1))[0] == License.DEMO
    status, label = demo_status("DEMO ACTIVE - 77 Days", seen, now=datetime(2026, 1, 1))
    assert status == License.NOT_OWNED and "07/11/2025" in label


def test_ua_system_profile_matching():
    from vst_audit.licenses.ua_sources import match_product, parse_system_profile
    from vst_audit.models import License

    empty = "Number of Devices:\t\t\t 0\nUAD-2 Plug-in Authorizations\nUAD Fairchild 670: No UAD-2 devices found\n"
    assert parse_system_profile(empty) == {}
    text = ("Number of Devices:\t\t\t 1\n UAD-2 Plug-in Authorizations \n"
            "UAD UA 1176LN Legacy Limiter: Authorized for all devices\n"
            "UAD Fairchild 670: Demo not started\n")
    products = parse_system_profile(text)
    assert match_product("UAD UA 1176LN Legacy", products)[0] == License.LICENSED
    assert match_product("UAD Fairchild 670", products)[0] == License.NOT_OWNED
    assert match_product("UAD Neve 1073", products) is None
