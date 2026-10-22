"""Gera os dados de exemplo da interface (frontend/src/mocks) a partir dos relatórios de teste.

Uso: python scripts/make_ui_mocks.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("MACPRONTO_DATA_DIR", tempfile.mkdtemp(prefix="macpronto-mocks-"))
os.environ.setdefault("MACPRONTO_OUTPUT_DIR", tempfile.mkdtemp(prefix="macpronto-mocks-docs-"))

from macpronto.api import Api  # noqa: E402
from macpronto.compat import service as compat  # noqa: E402
from macpronto.scanner.service import Scan  # noqa: E402

EXTRAS = {
    "desktop-coffee-lake-rx580": {
        "system": {
            "manufacturer": "Gigabyte Technology Co., Ltd.",
            "model": "Z390 AORUS PRO",
            "family": "",
            "form_factor": "desktop",
            "chassis_types": [3],
            "pc_system_type": 1,
            "is_virtual_machine": False,
        },
        "baseboard": {"manufacturer": "Gigabyte Technology Co., Ltd.", "product": "Z390 AORUS PRO-CF"},
        "bios": {"vendor": "American Megatrends Inc.", "version": "F12", "date": "2021-10-12"},
        "os": {
            "caption": "Microsoft Windows 11 Pro",
            "version": "10.0.26100",
            "build": "26100",
            "architecture": "64 bits",
        },
        "memory": {
            "total_gb": 31.9,
            "modules": [
                {"capacity_gb": 16.0, "speed_mhz": 3200, "manufacturer": "Corsair"},
                {"capacity_gb": 16.0, "speed_mhz": 3200, "manufacturer": "Corsair"},
            ],
        },
        "battery": {"present": False, "count": 0},
        "disks": [
            {
                "number": 0,
                "model": "Samsung SSD 970 EVO Plus 500GB",
                "size_gb": 500,
                "bus": "NVMe",
                "media": "SSD",
                "system": True,
            },
            {
                "number": 1,
                "model": "ST2000DM008-2FR102",
                "size_gb": 2000,
                "bus": "SATA",
                "media": "HDD",
                "system": False,
            },
        ],
    },
    "laptop-tiger-lake": {
        "system": {
            "manufacturer": "Dell Inc.",
            "model": "Inspiron 15 5502",
            "family": "Inspiron",
            "form_factor": "laptop",
            "chassis_types": [10],
            "pc_system_type": 2,
            "is_virtual_machine": False,
        },
        "baseboard": {"manufacturer": "Dell Inc.", "product": "0X4F9T"},
        "bios": {"vendor": "Dell Inc.", "version": "1.19.0", "date": "2023-03-01"},
        "os": {
            "caption": "Microsoft Windows 11 Home",
            "version": "10.0.22631",
            "build": "22631",
            "architecture": "64 bits",
        },
        "memory": {"total_gb": 7.7, "modules": [{"capacity_gb": 8.0, "speed_mhz": 3200, "manufacturer": "SK Hynix"}]},
        "battery": {"present": True, "count": 1},
        "disks": [
            {
                "number": 0,
                "model": "WDC PC SN530 SDBPNPZ-512G-1002",
                "size_gb": 512,
                "bus": "NVMe",
                "media": "SSD",
                "system": True,
            }
        ],
    },
}


def main() -> int:
    target = ROOT / "frontend" / "src" / "mocks"
    target.mkdir(parents=True, exist_ok=True)
    for name, extras in EXTRAS.items():
        report = json.loads((ROOT / "tests" / "fixtures" / "reports" / f"{name}.json").read_text(encoding="utf-8"))
        scan = Scan(
            id=f"20261022-090000-{name}",
            created_at=datetime(2026, 10, 22, 9, 0).isoformat(timespec="seconds"),
            source="local",
            label=report["Motherboard"]["Name"],
            report=report,
            extras=extras,
            acpi_tables=["dsdt.aml", "ssdt1.aml", "ssdt2.aml"],
        )
        result = compat.evaluate(scan)
        api = Api()
        api._session.scan = scan  # noqa: SLF001
        api._session.analysis = result["analysis"]  # noqa: SLF001
        api._session.plan = result["plan"]  # noqa: SLF001
        api._session.laudo = result["laudo"]  # noqa: SLF001
        api._session.selection = {  # noqa: SLF001
            "darwin": result["laudo"]["macos"]["recommended"],
            "answers": {},
            "smbios_model": None,
            "acpi_overrides": {},
            "kext_overrides": {},
        }
        payload = api._scan_payload()  # noqa: SLF001
        out = target / f"{name}.json"
        out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{out.relative_to(ROOT)}: {result['laudo']['verdict']['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
