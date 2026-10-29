"""Monta a EFI com o OpCore Simplify e aplica os ajustes do MacPronto.

Ajustes feitos depois da montagem:
- idioma e teclado do instalador (prev-lang:kbd), em português com ABNT2 por padrão;
- teclado ABNT2 PS/2 com a opção ISO do VoodooPS2, touchpad Synaptics I2C pelo VoodooI2CHID e
  itlwm sem as redes de exemplo (vistos num VAIO VJFE, veja docs/CONTEXTO-PARA-IA.md);
- mapa USB gerado no Windows (UTBMap.kext no lugar do UTBDefault.kext);
- nova validação com o ocvalidate e um .zip da pasta EFI.

A "EFI definitiva" (para o disco interno) é a mesma EFI sem o modo detalhado e com o menu
do OpenCore escondido; o writer grava as duas no pendrive.
"""

from __future__ import annotations

import json
import logging
import plistlib
import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from macpronto import paths
from macpronto.engine import EngineEvent, run_task, workspace
from macpronto.scanner.service import Scan

log = logging.getLogger(__name__)

NVRAM_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
INFO_FILE = "macpronto-efi.json"
CREATE_NO_WINDOW = 0x08000000

# Identificadores da lista AppleKeyboardLayouts do OpenCorePkg.
KEYBOARDS = {
    "abnt2": ("pt-BR:128", "Português (Brasil), teclado ABNT2"),
    "br-pro": ("pt-BR:72", "Português (Brasil), teclado Brasileiro Pro"),
    "us": ("en-US:0", "Inglês (EUA), teclado americano"),
}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:40] or "EFI"


def build(
    scan: Scan,
    selection: dict,
    keyboard: str = "abnt2",
    usb_map: Path | None = None,
    on_event: Callable[[EngineEvent], None] | None = None,
    cancel: threading.Event | None = None,
) -> dict:
    if scan.acpi_dir is None:
        raise ValueError("Este diagnóstico não tem as tabelas ACPI. Refaça o diagnóstico no próprio computador.")

    output = paths.efi_output_dir() / f"{datetime.now():%Y%m%d-%H%M%S}-{_slug(scan.label)}"
    params = {
        "report": scan.report,
        "acpi_dir": str(scan.acpi_dir),
        "macos_version": str(selection["darwin"]),
        "answers": selection.get("answers") or {},
        "smbios_model": selection.get("smbios_model"),
        "acpi_overrides": selection.get("acpi_overrides") or {},
        "kext_overrides": selection.get("kext_overrides") or {},
        "output_dir": str(output),
    }
    result = run_task("build", params, on_event=on_event, cancel=cancel)

    efi_dir = output / "EFI"
    config_path = efi_dir / "OC" / "config.plist"
    if on_event:
        on_event(EngineEvent("stage", {"title": "Aplicando os ajustes do MacPronto"}))
    apply_keyboard(config_path, keyboard)
    apply_installer_options(config_path)
    apply_hardware_fixes(efi_dir, keyboard)
    usb_applied = False
    if usb_map is not None and usb_map.is_dir():
        apply_usb_map(efi_dir, usb_map)
        usb_applied = True

    validation = validate(config_path) or result.get("validation")
    archive = shutil.make_archive(str(output / f"EFI-{_slug(scan.label)}"), "zip", root_dir=output, base_dir="EFI")

    info = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scan_id": scan.id,
        "machine": scan.label,
        "folder": str(output),
        "efi_dir": str(efi_dir),
        "zip": archive,
        "size_mb": round(sum(f.stat().st_size for f in efi_dir.rglob("*") if f.is_file()) / 1024**2, 1),
        "opencore": result.get("opencore"),
        "macos": selection["darwin"],
        # Escolhas completas usadas na montagem, para reabrir esta EFI numa próxima sessão
        "selection": {key: selection.get(key) for key in SELECTION_KEYS},
        "keyboard": keyboard,
        "keyboard_label": KEYBOARDS.get(keyboard, KEYBOARDS["abnt2"])[1],
        "usb_map": usb_applied,
        "validation": validation,
        "config": summarize(config_path),
        "plan": {
            "needs_oclp": result["plan"]["needs_oclp"],
            "smbios_model": result["plan"]["smbios_model"],
            "decisions": result["plan"]["decisions"],
            "bios_requirements": result["plan"]["bios_requirements"],
            "disabled_devices": result["plan"]["disabled_devices"],
        },
    }
    (output / INFO_FILE).write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("EFI pronta em %s", efi_dir)
    return info


def apply_keyboard(config_path: Path, keyboard: str) -> None:
    value = KEYBOARDS.get(keyboard, KEYBOARDS["abnt2"])[0]
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    config.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(NVRAM_GUID, {})["prev-lang:kbd"] = value.encode()
    with config_path.open("wb") as handle:
        plistlib.dump(config, handle)


def apply_installer_options(config_path: Path) -> None:
    """Deixa o instalador visível no menu do OpenCore.

    O OpCore Simplify liga o HideAuxiliary, que esconde as entradas "auxiliares". O macOS
    Recovery do pendrive (com.apple.recovery.boot) conta como auxiliar, então o menu só
    mostrava o Windows até apertar a barra de espaço (visto num ThinkCentre M80q).
    """
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    config.setdefault("Misc", {}).setdefault("Boot", {})["HideAuxiliary"] = False
    with config_path.open("wb") as handle:
        plistlib.dump(config, handle)


def apply_final_options(config_path: Path) -> None:
    """EFI definitiva: sem o modo detalhado (-v) e com o menu do OpenCore escondido (Esc mostra)."""
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    nvram = config.setdefault("NVRAM", {}).setdefault("Add", {}).setdefault(NVRAM_GUID, {})
    nvram["boot-args"] = " ".join(arg for arg in str(nvram.get("boot-args", "")).split() if arg != "-v")
    config.setdefault("Misc", {}).setdefault("Boot", {})["ShowPicker"] = False
    with config_path.open("wb") as handle:
        plistlib.dump(config, handle)


def apply_hardware_fixes(efi_dir: Path, keyboard: str) -> list[str]:
    """Correções vindas do teste num notebook real (VAIO VJFE). Podem rodar mais de uma vez.

    Devolve o que foi aplicado, para o registro.
    """
    applied = []
    if keyboard == "abnt2" and apply_ps2_iso_layout(efi_dir):
        applied.append("teclado ABNT2 PS/2 com a opção ISO do VoodooPS2")
    if apply_touchpad_hid(efi_dir):
        applied.append("touchpad I2C pelo VoodooI2CHID no lugar do VoodooRMI")
    if clear_itlwm_samples(efi_dir):
        applied.append("itlwm sem as redes Wi-Fi de exemplo")
    if applied:
        log.info("Correções de hardware na EFI: %s", "; ".join(applied))
    return applied


def apply_ps2_iso_layout(efi_dir: Path) -> bool:
    """Liga 'Use ISO layout keyboard' no VoodooPS2Keyboard.

    No teclado ABNT2 PS/2, a tecla abaixo do Esc e a tecla ao lado do Z saem trocadas. Com
    essa opção e o tipo de teclado ISO no macOS (que é o que o macOS escolhe para o ABNT2),
    as duas ficam certas depois de reiniciar.
    """
    plist = efi_dir / "OC" / "Kexts" / "VoodooPS2Controller.kext" / "Contents" / "PlugIns" / "VoodooPS2Keyboard.kext"
    plist = plist / "Contents" / "Info.plist"
    if not plist.is_file():
        return False
    with plist.open("rb") as handle:
        info = plistlib.load(handle)
    changed = False
    for personality in (info.get("IOKitPersonalities") or {}).values():
        default = (personality.get("Platform Profile") or {}).get("Default")
        if isinstance(default, dict) and default.get("Use ISO layout keyboard") is not True:
            default["Use ISO layout keyboard"] = True
            changed = True
    if changed:
        with plist.open("wb") as handle:
            plistlib.dump(info, handle)
    return changed


def apply_touchpad_hid(efi_dir: Path) -> bool:
    """Troca o VoodooRMI (RMII2C) pelo VoodooI2CHID nos touchpads Synaptics I2C.

    O OpCore Simplify escolhe o RMII2C para touchpads SYNA em I2C e tira o VoodooI2CHID do
    config.plist. No VAIO VJFE o RMII2C não funcionou e o VoodooI2CHID, genérico para
    touchpads I2C HID, funcionou. O VoodooRMI fica na pasta, desativado, para quem quiser voltar.
    """
    kexts_dir = efi_dir / "OC" / "Kexts"
    if not (kexts_dir / "VoodooI2CHID.kext" / "Contents" / "Info.plist").is_file():
        return False
    config_path = efi_dir / "OC" / "config.plist"
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    entries = config.get("Kernel", {}).get("Add", [])
    by_path = {e.get("BundlePath"): e for e in entries}
    rmi_i2c = by_path.get("VoodooRMI.kext/Contents/PlugIns/RMII2C.kext")
    if not (rmi_i2c and rmi_i2c.get("Enabled") and (by_path.get("VoodooI2C.kext") or {}).get("Enabled")):
        return False
    if (by_path.get("VoodooI2CHID.kext") or {}).get("Enabled"):
        return False
    for path, entry in by_path.items():
        if path and path.startswith("VoodooRMI.kext"):
            entry["Enabled"] = False
    hid = by_path.get("VoodooI2CHID.kext")
    if hid is None:
        position = max(i for i, e in enumerate(entries) if str(e.get("BundlePath", "")).startswith("VoodooI2C.kext")) + 1
        hid = {**by_path["VoodooI2C.kext"], "BundlePath": "VoodooI2CHID.kext", "ExecutablePath": "Contents/MacOS/VoodooI2CHID"}
        entries.insert(position, hid)
    hid.update(Enabled=True, Comment="MacPronto: touchpad I2C pelo HID (VoodooRMI desativado)")
    with config_path.open("wb") as handle:
        plistlib.dump(config, handle)
    return True


def clear_itlwm_samples(efi_dir: Path) -> bool:
    """Tira do itlwm as redes de exemplo que vêm no Info.plist dele (nomes e senhas de teste).

    O OpCore Simplify só troca essas redes pelas do Windows quando o usuário aceita importar
    as senhas; o MacPronto não importa (elas ficariam em texto puro na EFI e no ioreg).
    """
    plist = efi_dir / "OC" / "Kexts" / "itlwm.kext" / "Contents" / "Info.plist"
    if not plist.is_file():
        return False
    with plist.open("rb") as handle:
        info = plistlib.load(handle)
    personality = (info.get("IOKitPersonalities") or {}).get("itlwm") or {}
    if not personality.get("WiFiConfig"):
        return False
    personality["WiFiConfig"] = {}
    with plist.open("wb") as handle:
        plistlib.dump(info, handle)
    return True


def apply_usb_map(efi_dir: Path, usb_map: Path) -> None:
    """Troca o UTBDefault.kext (todas as portas) pelo mapa gerado no Windows."""
    kexts_dir = efi_dir / "OC" / "Kexts"
    target = kexts_dir / "UTBMap.kext"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(usb_map, target)
    default = kexts_dir / "UTBDefault.kext"
    if default.exists():
        shutil.rmtree(default)

    config_path = efi_dir / "OC" / "config.plist"
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    entries = [e for e in config["Kernel"]["Add"] if e.get("BundlePath") not in ("UTBDefault.kext", "UTBMap.kext")]
    position = next((i + 1 for i, e in enumerate(entries) if e.get("BundlePath") == "USBToolBox.kext"), len(entries))
    template = entries[position - 1] if position else {}
    entries.insert(
        position,
        {
            "Arch": template.get("Arch", "x86_64"),
            "BundlePath": "UTBMap.kext",
            "Comment": "Mapa USB gerado pelo MacPronto",
            "Enabled": True,
            "ExecutablePath": "",
            "MaxKernel": "",
            "MinKernel": "",
            "PlistPath": "Contents/Info.plist",
        },
    )
    config["Kernel"]["Add"] = entries
    with config_path.open("wb") as handle:
        plistlib.dump(config, handle)


def ocvalidate_path() -> Path:
    return workspace.ensure("OpCore-Simplify") / "bin" / "ocvalidate.exe"


def validate(config_path: Path) -> dict | None:
    executable = ocvalidate_path()
    if not executable.exists():
        return None
    completed = subprocess.run(
        [str(executable), str(config_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    output = (completed.stdout + completed.stderr).strip()
    return {"ran": True, "ok": completed.returncode == 0, "output": output}


def summarize(config_path: Path) -> dict:
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    generic = config.get("PlatformInfo", {}).get("Generic", {})
    nvram = config.get("NVRAM", {}).get("Add", {}).get(NVRAM_GUID, {})
    rom = generic.get("ROM")
    return {
        "smbios": {
            "model": generic.get("SystemProductName"),
            "serial": generic.get("SystemSerialNumber"),
            "mlb": generic.get("MLB"),
            "uuid": generic.get("SystemUUID"),
            "rom": rom.hex().upper() if isinstance(rom, bytes) else rom,
        },
        "boot_args": nvram.get("boot-args", ""),
        "keyboard": (nvram.get("prev-lang:kbd") or b"").decode(errors="replace"),
        "kexts": [e.get("BundlePath") for e in config.get("Kernel", {}).get("Add", []) if e.get("Enabled")],
        "ssdts": [e.get("Path") for e in config.get("ACPI", {}).get("Add", []) if e.get("Enabled")],
        "drivers": [e.get("Path") for e in config.get("UEFI", {}).get("Drivers", []) if e.get("Enabled")],
        "secure_boot_model": config.get("Misc", {}).get("Security", {}).get("SecureBootModel"),
        "vesa": "-igfxvesa" in nvram.get("boot-args", ""),
    }


SELECTION_KEYS = ("darwin", "answers", "smbios_model", "acpi_overrides", "kext_overrides")


def default_selection(darwin: int) -> dict:
    return {"darwin": darwin, "answers": {}, "smbios_model": None, "acpi_overrides": {}, "kext_overrides": {}}


def build_selection(info: dict) -> dict:
    """Escolhas de uma EFI já montada (as montagens antigas só guardavam a versão do macOS)."""
    stored = info.get("selection") or {}
    selection = default_selection(int(stored.get("darwin") or info["macos"]))
    selection.update({key: stored[key] for key in SELECTION_KEYS if stored.get(key) is not None})
    return selection


def is_default_selection(selection: dict) -> bool:
    return not (
        selection.get("answers")
        or selection.get("smbios_model")
        or selection.get("acpi_overrides")
        or selection.get("kext_overrides")
    )


def is_complete(info: dict) -> bool:
    """A pasta da EFI ainda existe e tem o essencial (o usuário pode ter apagado ou mexido)."""
    efi_dir = Path(info.get("efi_dir") or "")
    return all((efi_dir / part).is_file() for part in ("OC/OpenCore.efi", "OC/config.plist", "BOOT/BOOTx64.efi"))


def list_builds(scan_id: str | None = None) -> list[dict]:
    builds = []
    root = paths.efi_output_dir()
    for folder in sorted(root.iterdir(), reverse=True) if root.exists() else []:
        info_file = folder / INFO_FILE
        if not info_file.exists():
            continue
        try:
            info = json.loads(info_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if scan_id is None or info.get("scan_id") == scan_id:
            builds.append(info)
    return builds


def apply_usb_to_build(info: dict, usb_map: Path) -> dict:
    """Aplica o mapa USB a uma EFI já montada, valida de novo e refaz o .zip."""
    folder = Path(info["folder"])
    efi_dir = folder / "EFI"
    config_path = efi_dir / "OC" / "config.plist"
    apply_usb_map(efi_dir, usb_map)
    validation = validate(config_path) or info.get("validation")
    archive = Path(info["zip"])
    archive.unlink(missing_ok=True)
    zip_path = shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=folder, base_dir="EFI")
    updated = {
        **info,
        "zip": zip_path,
        "usb_map": True,
        "validation": validation,
        "config": summarize(config_path),
        "size_mb": round(sum(f.stat().st_size for f in efi_dir.rglob("*") if f.is_file()) / 1024**2, 1),
    }
    (folder / INFO_FILE).write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    return updated
