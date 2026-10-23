"""Atualização da base de regras sob demanda.

O usuário pode trocar a versão travada do OpCore Simplify ou do Hardware Sniffer
pelo último commit do GitHub. A versão nova só é ativada se passar no autoteste:
- OpCore Simplify: análise e plano de uma máquina de exemplo, com os mesmos
  resultados essenciais da versão travada;
- Hardware Sniffer: coleta do hardware desta máquina.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from macpronto.engine import components, workspace
from macpronto.engine.errors import EngineError
from macpronto.engine.runner import EngineEvent, run_task

log = logging.getLogger(__name__)

SELFTEST_REPORT = Path(__file__).resolve().parent / "selftest" / "desktop.json"
EXPECTED_KEXTS = {"Lilu", "VirtualSMC", "WhateverGreen", "AppleALC"}


def status() -> list[dict]:
    pinned = workspace.pinned_versions()
    result = []
    for component in components.COMPONENTS:
        if not component.updatable:
            continue
        _, commit, origin = workspace.active_source(component.name)
        update = workspace.active_updates().get(component.name, {})
        result.append(
            {
                "name": component.name,
                "repository": component.repository,
                "pinned": pinned.get(component.name, {}).get("commit", ""),
                "active": commit,
                "origin": origin,
                "installed_at": update.get("installed_at"),
                "commit_date": update.get("date"),
            }
        )
    return result


def check(name: str) -> dict:
    component = _component(name)
    latest = components.latest_commit(component)
    _, active, origin = workspace.active_source(name)
    return {**latest, "name": name, "active": active, "origin": origin, "newer": latest["sha"] != active}


def _component(name: str) -> components.Component:
    component = components.BY_NAME.get(name)
    if component is None or not component.updatable:
        raise ValueError(f"Componente {name} não pode ser atualizado.")
    return component


def _selftest(name: str, workspace_dir: Path, on_event, cancel) -> str:
    if name == "OpCore-Simplify":
        report = json.loads(SELFTEST_REPORT.read_text(encoding="utf-8"))
        analysis = run_task(
            "analyze", {"report": report}, on_event=on_event, cancel=cancel, workspace_dir=workspace_dir
        )
        if analysis.get("fatal") or not analysis.get("native"):
            raise EngineError("selftest", "A versão nova não reconheceu a máquina de exemplo como compatível.")
        plan = run_task(
            "plan",
            {"report": report, "macos_version": "24"},
            on_event=on_event,
            cancel=cancel,
            workspace_dir=workspace_dir,
        )
        checked = {kext["name"] for kext in plan.get("kexts", []) if kext.get("checked")}
        missing = EXPECTED_KEXTS - checked
        if missing or not plan.get("smbios_model"):
            raise EngineError(
                "selftest", f"O plano da versão nova ficou incompleto (faltam {', '.join(sorted(missing))})."
            )
        return f"Análise e plano da máquina de exemplo: {len(checked)} kexts, SMBIOS {plan['smbios_model']}."

    sniff = run_task("sniff", {}, on_event=on_event, cancel=cancel, workspace_dir=workspace_dir)
    report = sniff.get("report", {})
    missing = [key for key in ("Motherboard", "CPU", "GPU") if key not in report]
    if missing:
        raise EngineError("selftest", f"A coleta da versão nova veio sem {', '.join(missing)}.")
    return f"Coleta do hardware desta máquina: {len(report)} seções."


def install(
    name: str,
    on_event: Callable[[EngineEvent], None] | None = None,
    cancel: threading.Event | None = None,
) -> dict:
    """Baixa o último commit, roda o autoteste e ativa a versão se ele passar."""
    component = _component(name)

    def stage(title: str) -> None:
        if on_event:
            on_event(EngineEvent("stage", {"title": title}))

    stage("Consultando o GitHub")
    latest = components.latest_commit(component)
    target = workspace.updates_dir() / f"{name}-{latest['sha'][:12]}"

    stage(f"Baixando {name} ({latest['sha'][:7]})")
    try:
        components.extract(component, components.download_zip(component, latest["sha"]), target)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de rede ou de estrutura cancela a atualização
        shutil.rmtree(target, ignore_errors=True)
        raise EngineError("update-download", f"Não foi possível baixar a versão nova: {exc}") from exc

    stage("Testando a versão nova")
    test_dir = workspace.ensure_from(target, f"{name}-teste", latest["sha"])
    try:
        summary = _selftest(name, test_dir, on_event, cancel)
    except EngineError as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise EngineError(
            "update-selftest",
            f"A versão nova do {name} não passou no autoteste e não foi ativada. A versão anterior continua em uso.",
            exc.details or exc.message,
        ) from exc
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    workspace.set_active_update(
        name,
        {
            "commit": latest["sha"],
            "date": latest.get("date"),
            "path": str(target),
            "installed_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    _cleanup(name, keep=target)
    log.info("%s atualizado para %s: %s", name, latest["sha"][:12], summary)
    return {"name": name, "commit": latest["sha"], "date": latest.get("date"), "selftest": summary}


def revert(name: str) -> None:
    """Volta para a versão travada que veio com o MacPronto."""
    _component(name)
    workspace.set_active_update(name, None)
    _cleanup(name, keep=None)


def _cleanup(name: str, keep: Path | None) -> None:
    for folder in workspace.updates_dir().glob(f"{name}-*"):
        if folder.is_dir() and folder != keep:
            shutil.rmtree(folder, ignore_errors=True)
