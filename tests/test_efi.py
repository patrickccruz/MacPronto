from __future__ import annotations

import plistlib

from macpronto.efi import service as efi


def make_efi(tmp_path):
    efi_dir = tmp_path / "EFI"
    kexts = efi_dir / "OC" / "Kexts"
    for name in ("Lilu.kext", "USBToolBox.kext", "UTBDefault.kext", "WhateverGreen.kext"):
        (kexts / name / "Contents").mkdir(parents=True)
    config = {
        "Kernel": {
            "Add": [
                {
                    "Arch": "x86_64",
                    "BundlePath": name,
                    "Enabled": True,
                    "ExecutablePath": "",
                    "PlistPath": "Contents/Info.plist",
                }
                for name in ("Lilu.kext", "USBToolBox.kext", "UTBDefault.kext", "WhateverGreen.kext")
            ]
        },
        "NVRAM": {"Add": {efi.NVRAM_GUID: {"boot-args": "-v", "prev-lang:kbd": b""}}},
        "PlatformInfo": {"Generic": {"SystemProductName": "iMac19,1"}},
    }
    with (efi_dir / "OC" / "config.plist").open("wb") as handle:
        plistlib.dump(config, handle)
    return efi_dir


def read_config(efi_dir):
    with (efi_dir / "OC" / "config.plist").open("rb") as handle:
        return plistlib.load(handle)


def test_teclado_abnt2(tmp_path):
    efi_dir = make_efi(tmp_path)
    efi.apply_keyboard(efi_dir / "OC" / "config.plist", "abnt2")
    assert read_config(efi_dir)["NVRAM"]["Add"][efi.NVRAM_GUID]["prev-lang:kbd"] == b"pt-BR:128"


def test_mapa_usb_substitui_utbdefault(tmp_path):
    efi_dir = make_efi(tmp_path)
    usb_map = tmp_path / "UTBMap.kext"
    (usb_map / "Contents").mkdir(parents=True)
    (usb_map / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"CFBundleName": "UTBMap"}))

    efi.apply_usb_map(efi_dir, usb_map)

    kexts_dir = efi_dir / "OC" / "Kexts"
    assert (kexts_dir / "UTBMap.kext" / "Contents" / "Info.plist").exists()
    assert not (kexts_dir / "UTBDefault.kext").exists()
    order = [entry["BundlePath"] for entry in read_config(efi_dir)["Kernel"]["Add"]]
    assert order == ["Lilu.kext", "USBToolBox.kext", "UTBMap.kext", "WhateverGreen.kext"]

    # Aplicar de novo não duplica a entrada
    efi.apply_usb_map(efi_dir, usb_map)
    assert [e["BundlePath"] for e in read_config(efi_dir)["Kernel"]["Add"]].count("UTBMap.kext") == 1


def test_resumo_detecta_vesa(tmp_path):
    efi_dir = make_efi(tmp_path)
    config_path = efi_dir / "OC" / "config.plist"
    config = read_config(efi_dir)
    config["NVRAM"]["Add"][efi.NVRAM_GUID]["boot-args"] = "-v igfxonln=1 -igfxvesa"
    with config_path.open("wb") as handle:
        plistlib.dump(config, handle)
    summary = efi.summarize(config_path)
    assert summary["vesa"] is True
    assert summary["smbios"]["model"] == "iMac19,1"


def make_build(root, name, scan_id, darwin, complete=True, selection=None):
    folder = root / "EFI" / name
    efi_dir = folder / "EFI"
    for part in ("OC/OpenCore.efi", "OC/config.plist", "BOOT/BOOTx64.efi"):
        if part == "OC/OpenCore.efi" and not complete:
            continue
        (efi_dir / part).parent.mkdir(parents=True, exist_ok=True)
        (efi_dir / part).write_bytes(b"x")
    info = {"created_at": name, "scan_id": scan_id, "folder": str(folder), "efi_dir": str(efi_dir), "macos": darwin}
    if selection is not None:
        info["selection"] = selection
    (folder / efi.INFO_FILE).write_text(__import__("json").dumps(info), encoding="utf-8")
    return info


def test_efi_anterior_volta_ao_abrir_o_diagnostico(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from macpronto.api import Api

    monkeypatch.setenv("MACPRONTO_OUTPUT_DIR", str(tmp_path))
    make_build(tmp_path, "20261023-100000-PC", "pc", 24)
    make_build(tmp_path, "20261023-110000-PC", "pc", 24, complete=False)  # pasta mexida: ignorada
    make_build(tmp_path, "20261023-090000-OUTRO", "outro", 24)
    api = Api()
    scan = SimpleNamespace(id="pc")

    api._restore_efi(scan, 24)  # noqa: SLF001
    assert api._session.efi["created_at"] == "20261023-100000-PC"  # noqa: SLF001

    api._session.efi = None  # noqa: SLF001
    api._restore_efi(scan, 25)  # recomendado mudou: não reaproveita  # noqa: SLF001
    assert api._session.efi is None  # noqa: SLF001

    custom = efi.default_selection(24) | {"smbios_model": "iMac20,1"}
    make_build(tmp_path, "20261023-120000-PC", "pc", 24, selection=custom)
    api._restore_efi(scan, 24)  # a mais nova tem escolhas próprias: fica só na lista  # noqa: SLF001
    assert api._session.efi is None  # noqa: SLF001
    assert efi.build_selection(efi.list_builds("pc")[0])["smbios_model"] == "iMac20,1"
    assert efi.build_selection({"macos": 24}) == efi.default_selection(24)  # montagens antigas
