from __future__ import annotations

import plistlib
from pathlib import Path

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


def test_instalador_aparece_no_menu_do_opencore(tmp_path):
    efi_dir = make_efi(tmp_path)
    efi.apply_installer_options(efi_dir / "OC" / "config.plist")
    assert read_config(efi_dir)["Misc"]["Boot"]["HideAuxiliary"] is False


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



def write_plist(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(data))


def make_laptop_efi(tmp_path):
    """EFI como a do VAIO VJFE: VoodooI2C + VoodooRMI (RMII2C), VoodooPS2 e itlwm com as redes de exemplo."""
    efi_dir = tmp_path / "EFI"
    kexts = efi_dir / "OC" / "Kexts"
    paths = [
        "VoodooI2C.kext",
        "VoodooI2C.kext/Contents/PlugIns/VoodooInput.kext",
        "VoodooPS2Controller.kext",
        "VoodooRMI.kext",
        "VoodooRMI.kext/Contents/PlugIns/RMII2C.kext",
        "VoodooRMI.kext/Contents/PlugIns/VoodooInput.kext",
        "itlwm.kext",
    ]
    entry = {"Arch": "Any", "Comment": "", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"}
    add = [
        {**entry, "BundlePath": path, "Enabled": not path.endswith("RMI.kext/Contents/PlugIns/VoodooInput.kext"),
         "ExecutablePath": f"Contents/MacOS/{Path(path).stem}"}
        for path in paths
    ]
    config = {
        "Kernel": {"Add": add},
        "Misc": {"Boot": {"ShowPicker": True}},
        "NVRAM": {"Add": {efi.NVRAM_GUID: {"boot-args": "-v debug=0x100 keepsyms=1 -vi2c-force-polling"}}},
        "PlatformInfo": {"Generic": {"SystemProductName": "MacBookPro16,3", "SystemSerialNumber": "SEGREDO123"}},
    }
    write_plist(efi_dir / "OC" / "config.plist", config)
    write_plist(kexts / "VoodooI2CHID.kext" / "Contents" / "Info.plist", {"CFBundleIdentifier": "com.alexandred.VoodooI2CHID"})
    keyboard = kexts / "VoodooPS2Controller.kext/Contents/PlugIns/VoodooPS2Keyboard.kext/Contents/Info.plist"
    profile = {"Default": {"Use ISO layout keyboard": False, "Swap command and option": False}, "HPQOEM": {}}
    write_plist(keyboard, {"IOKitPersonalities": {"ApplePS2Keyboard": {"Platform Profile": profile}}})
    wifi = {"ssdt": {"ssid": "ssdt", "password": "zxyssdt112233"}, "Redmi": {"ssid": "Redmi", "password": "1234"}}
    write_plist(kexts / "itlwm.kext" / "Contents" / "Info.plist", {"IOKitPersonalities": {"itlwm": {"WiFiConfig": wifi}}})
    return efi_dir


def test_correcoes_do_notebook(tmp_path):
    efi_dir = make_laptop_efi(tmp_path)
    kexts = efi_dir / "OC" / "Kexts"
    applied = efi.apply_hardware_fixes(efi_dir, "abnt2")
    assert len(applied) == 3

    keyboard = kexts / "VoodooPS2Controller.kext/Contents/PlugIns/VoodooPS2Keyboard.kext/Contents/Info.plist"
    profile = plistlib.loads(keyboard.read_bytes())["IOKitPersonalities"]["ApplePS2Keyboard"]["Platform Profile"]
    assert profile["Default"]["Use ISO layout keyboard"] is True

    itlwm = plistlib.loads((kexts / "itlwm.kext" / "Contents" / "Info.plist").read_bytes())
    assert itlwm["IOKitPersonalities"]["itlwm"]["WiFiConfig"] == {}

    add = read_config(efi_dir)["Kernel"]["Add"]
    state = {e["BundlePath"]: e["Enabled"] for e in add}
    assert state["VoodooI2CHID.kext"] is True
    assert not any(enabled for path, enabled in state.items() if path.startswith("VoodooRMI.kext"))
    order = [e["BundlePath"] for e in add]
    assert order.index("VoodooI2CHID.kext") == order.index("VoodooI2C.kext/Contents/PlugIns/VoodooInput.kext") + 1
    assert next(e for e in add if e["BundlePath"] == "VoodooI2CHID.kext")["ExecutablePath"] == "Contents/MacOS/VoodooI2CHID"

    # Rodar de novo não muda nada nem duplica a entrada
    assert efi.apply_hardware_fixes(efi_dir, "abnt2") == []
    assert [e["BundlePath"] for e in read_config(efi_dir)["Kernel"]["Add"]].count("VoodooI2CHID.kext") == 1


def test_teclado_americano_nao_liga_a_opcao_iso(tmp_path):
    efi_dir = make_laptop_efi(tmp_path)
    applied = efi.apply_hardware_fixes(efi_dir, "us")
    assert not any("ISO" in item for item in applied)


def test_efi_definitiva_sem_modo_detalhado(tmp_path):
    efi_dir = make_laptop_efi(tmp_path)
    efi.apply_final_options(efi_dir / "OC" / "config.plist")
    config = read_config(efi_dir)
    assert config["NVRAM"]["Add"][efi.NVRAM_GUID]["boot-args"] == "debug=0x100 keepsyms=1 -vi2c-force-polling"
    assert config["Misc"]["Boot"]["ShowPicker"] is False
    assert config["PlatformInfo"]["Generic"]["SystemSerialNumber"] == "SEGREDO123"  # o resto fica igual

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
