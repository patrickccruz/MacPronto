"""Informações complementares ao relatório do Hardware Sniffer, lidas via WMI.

Nada aqui coleta números de série: o diagnóstico pode ser compartilhado.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Win32_SystemEnclosure.ChassisTypes
LAPTOP_CHASSIS = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
DESKTOP_CHASSIS = {3, 4, 5, 6, 7, 13, 15, 16, 24, 35, 36}
MINI_CHASSIS = {35, 36}

# MSFT_PhysicalDisk
DISK_BUS = {
    1: "SCSI",
    2: "ATAPI",
    3: "ATA",
    6: "Fibre Channel",
    7: "USB",
    8: "RAID",
    9: "iSCSI",
    10: "SAS",
    11: "SATA",
    12: "SD",
    13: "MMC",
    15: "File Backed Virtual",
    16: "Storage Spaces",
    17: "NVMe",
}
DISK_MEDIA = {3: "HDD", 4: "SSD", 5: "SCM"}

VM_MARKERS = ("virtual machine", "vmware", "virtualbox", "kvm", "qemu", "parallels", "hyper-v", "xen")


def _first(query) -> object | None:
    try:
        items = list(query)
    except Exception:  # noqa: BLE001 - classes WMI podem não existir em todas as edições
        return None
    return items[0] if items else None


def _text(value) -> str:
    return str(value).strip() if value not in (None, "") else ""


def collect() -> dict:
    import wmi  # type: ignore[import-not-found]

    cimv2 = wmi.WMI()
    result: dict = {}

    system = _first(cimv2.Win32_ComputerSystem())
    enclosure = _first(cimv2.Win32_SystemEnclosure())
    chassis_types = [int(t) for t in (getattr(enclosure, "ChassisTypes", None) or [])]
    pc_system_type = int(getattr(system, "PCSystemType", 0) or 0)
    model = _text(getattr(system, "Model", ""))
    manufacturer = _text(getattr(system, "Manufacturer", ""))

    if any(t in LAPTOP_CHASSIS for t in chassis_types) or pc_system_type in (2, 8):
        form = "laptop"
    elif any(t in MINI_CHASSIS for t in chassis_types):
        form = "mini"
    else:
        form = "desktop"

    result["system"] = {
        "manufacturer": manufacturer,
        "model": model,
        "family": _text(getattr(system, "SystemFamily", "")),
        "form_factor": form,
        "chassis_types": chassis_types,
        "pc_system_type": pc_system_type,
        "is_virtual_machine": any(marker in f"{manufacturer} {model}".lower() for marker in VM_MARKERS),
    }

    board = _first(cimv2.Win32_BaseBoard())
    result["baseboard"] = {
        "manufacturer": _text(getattr(board, "Manufacturer", "")),
        "product": _text(getattr(board, "Product", "")),
    }

    bios = _first(cimv2.Win32_BIOS())
    release = _text(getattr(bios, "ReleaseDate", ""))
    result["bios"] = {
        "vendor": _text(getattr(bios, "Manufacturer", "")),
        "version": _text(getattr(bios, "SMBIOSBIOSVersion", "")),
        "date": f"{release[:4]}-{release[4:6]}-{release[6:8]}" if len(release) >= 8 else "",
    }

    os_info = _first(cimv2.Win32_OperatingSystem())
    result["os"] = {
        "caption": _text(getattr(os_info, "Caption", "")),
        "version": _text(getattr(os_info, "Version", "")),
        "build": _text(getattr(os_info, "BuildNumber", "")),
        "architecture": _text(getattr(os_info, "OSArchitecture", "")),
    }

    modules = []
    try:
        for module in cimv2.Win32_PhysicalMemory():
            capacity = int(getattr(module, "Capacity", 0) or 0)
            modules.append(
                {
                    "capacity_gb": round(capacity / 1024**3, 1),
                    "speed_mhz": int(getattr(module, "ConfiguredClockSpeed", 0) or getattr(module, "Speed", 0) or 0),
                    "manufacturer": _text(getattr(module, "Manufacturer", "")),
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("Falha ao ler módulos de memória: %s", exc)
    total = int(getattr(system, "TotalPhysicalMemory", 0) or 0)
    result["memory"] = {"total_gb": round(total / 1024**3, 1), "modules": modules}

    batteries = []
    try:
        batteries = list(cimv2.Win32_Battery())
    except Exception:  # noqa: BLE001
        pass
    result["battery"] = {"present": bool(batteries), "count": len(batteries)}

    result["disks"] = _disks(wmi)
    return result


def _disks(wmi_module) -> list[dict]:
    disks: list[dict] = []
    try:
        storage = wmi_module.WMI(namespace="root/Microsoft/Windows/Storage")
    except Exception as exc:  # noqa: BLE001
        log.debug("Namespace de armazenamento indisponível: %s", exc)
        return disks

    system_numbers = set()
    try:
        for disk in storage.MSFT_Disk():
            if getattr(disk, "IsSystem", False) or getattr(disk, "IsBoot", False):
                system_numbers.add(int(disk.Number))
    except Exception:  # noqa: BLE001
        pass

    try:
        for physical in storage.MSFT_PhysicalDisk():
            number = int(getattr(physical, "DeviceId", -1) or -1)
            size = int(getattr(physical, "Size", 0) or 0)
            disks.append(
                {
                    "number": number,
                    "model": _text(getattr(physical, "FriendlyName", "")) or _text(getattr(physical, "Model", "")),
                    "size_gb": round(size / 1000**3),
                    "bus": DISK_BUS.get(int(getattr(physical, "BusType", 0) or 0), "Desconhecido"),
                    "media": DISK_MEDIA.get(int(getattr(physical, "MediaType", 0) or 0), "Desconhecido"),
                    "system": number in system_numbers,
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("Falha ao listar discos físicos: %s", exc)
    return sorted(disks, key=lambda d: d["number"])
