"""Encadeia análise, plano e laudo para um diagnóstico."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from macpronto.compat import laudo, macos
from macpronto.engine import EngineError, EngineEvent, run_task
from macpronto.scanner.service import Scan

log = logging.getLogger(__name__)


def analyze(
    scan: Scan, on_event: Callable[[EngineEvent], None] | None = None, cancel: threading.Event | None = None
) -> dict:
    return run_task("analyze", {"report": scan.report}, on_event=on_event, cancel=cancel)


def plan(
    scan: Scan,
    darwin: int,
    answers: dict | None = None,
    smbios_model: str | None = None,
    acpi_overrides: dict | None = None,
    kext_overrides: dict | None = None,
    on_event: Callable[[EngineEvent], None] | None = None,
    cancel: threading.Event | None = None,
) -> dict:
    params = {
        "report": scan.report,
        "macos_version": str(darwin),
        "answers": answers or {},
        "smbios_model": smbios_model,
        "acpi_overrides": acpi_overrides or {},
        "kext_overrides": kext_overrides or {},
    }
    return run_task("plan", params, on_event=on_event, cancel=cancel)


def evaluate(
    scan: Scan, on_event: Callable[[EngineEvent], None] | None = None, cancel: threading.Event | None = None
) -> dict:
    """Análise completa: devolve {"analysis", "plan", "laudo"}."""
    analysis = analyze(scan, on_event, cancel)
    recommended, _ = macos.recommend(analysis.get("native"), analysis.get("suggested"))

    plan_result = None
    if recommended is not None:
        try:
            plan_result = plan(scan, recommended, on_event=on_event, cancel=cancel)
        except EngineError as exc:
            log.warning("Plano para a versão recomendada falhou: %s", exc.message)

    report = laudo.build(scan.to_dict(), analysis, plan_result)
    return {"analysis": analysis, "plan": plan_result, "laudo": report}
