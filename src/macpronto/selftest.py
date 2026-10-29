"""Autoteste do MacPronto empacotado: MacPronto.exe --selftest [arquivo.json]

Roda sem janela e grava o resultado em JSON (padrão: %TEMP%\\macpronto-selftest.json).
Confere os recursos empacotados, o motor (worker em subprocesso), o laudo, o guia
e as leituras do Windows. Não altera nada no computador.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from macpronto import __version__, logs, paths

SAMPLE = Path(__file__).resolve().parent / "engine" / "selftest" / "desktop.json"


def _check(results: list[dict], name: str, function: Callable[[], str]) -> None:
    start = time.monotonic()
    try:
        detail = function()
        results.append({"check": name, "ok": True, "detail": detail, "seconds": round(time.monotonic() - start, 2)})
    except Exception as exc:  # noqa: BLE001 - o autoteste registra qualquer falha
        results.append(
            {
                "check": name,
                "ok": False,
                "detail": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "seconds": round(time.monotonic() - start, 2),
            }
        )


def run(output: Path | None = None) -> int:
    logs.setup()
    output = output or Path(tempfile.gettempdir()) / "macpronto-selftest.json"
    results: list[dict] = []
    state: dict = {}

    def resources() -> str:
        required = [
            paths.third_party_dir() / "VERSIONS.json",
            paths.third_party_dir() / "OpCore-Simplify" / "Scripts" / "compatibility_checker.py",
            paths.third_party_dir() / "Hardware-Sniffer" / "HardwareSniffer.py",
            paths.third_party_dir() / "USBToolBox" / "resources" / "Info.plist",
            paths.third_party_dir() / "macrecovery" / "macrecovery.py",
            paths.frontend_dir() / "index.html",
            Path(__file__).resolve().parent / "guide" / "templates" / "guia.html.j2",
            Path(__file__).resolve().parent / "guide" / "templates" / "ajuda-ia.md.j2",
            Path(__file__).resolve().parent / "guide" / "templates" / "boas-vindas.html.j2",
            Path(__file__).resolve().parent / "guide" / "bios_profiles.json",
            SAMPLE,
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError(", ".join(missing))
        return f"{len(required)} recursos em {paths.resource_root()}"

    def engine() -> str:
        from macpronto.engine import run_task

        report = json.loads(SAMPLE.read_text(encoding="utf-8"))
        analysis = run_task("analyze", {"report": report})
        plan = run_task("plan", {"report": report, "macos_version": "24"})
        state.update(report=report, analysis=analysis, plan=plan)
        kexts = [k["name"] for k in plan["kexts"] if k["checked"]]
        return f"worker {paths.executable()}; {len(kexts)} kexts, SMBIOS {plan['smbios_model']}"

    def laudo_and_guide() -> str:
        from macpronto.compat import laudo
        from macpronto.guide import render

        scan = {"id": "selftest", "report": state["report"], "extras": {}, "acpi_tables": []}
        built = laudo.build(scan, state["analysis"], state["plan"])
        html = render.render_html(render.build_context(scan, built, {"darwin": 24}, None, usb_mapped=False))
        return f"veredito {built['verdict']['status']}; guia com {len(html)} caracteres"

    def qr() -> str:
        from macpronto.guide.share import qr_svg

        return f"QR code com {len(qr_svg('http://127.0.0.1/Guia.html'))} caracteres"

    def usb() -> str:
        from macpronto.usb import windows

        controllers = windows.read_controllers()
        ports = sum(len(c["ports"]) for c in controllers)
        return f"{len(controllers)} controladora(s), {ports} portas"

    def disks() -> str:
        from macpronto.media import disks as media_disks

        found = media_disks.list_disks()
        return f"{len(found)} disco(s), {sum(1 for d in found if d['eligible'])} elegível(is)"

    def sniffer() -> str:
        from macpronto.engine import run_task

        result = run_task("sniff", {})
        return f"{len(result['report'])} seções do Hardware Sniffer"

    _check(results, "recursos empacotados", resources)
    _check(results, "motor (análise e plano)", engine)
    if "plan" in state:
        _check(results, "laudo e guia", laudo_and_guide)
    _check(results, "QR code", qr)
    _check(results, "portas USB", usb)
    _check(results, "discos", disks)
    if "--full" in sys.argv:
        _check(results, "coleta do hardware", sniffer)

    summary = {
        "version": __version__,
        "frozen": paths.is_frozen(),
        "executable": str(paths.executable()),
        "sys_executable": sys.executable,
        "argv0": sys.argv[0],
        "admin": _is_admin(),
        "compat_layer": os.environ.get("__COMPAT_LAYER"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ok": all(item["ok"] for item in results),
        "results": results,
    }
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if summary["ok"] else 1


def _is_admin() -> bool:
    from macpronto import winutil

    return winutil.is_admin()
