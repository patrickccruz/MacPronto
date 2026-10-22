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
