"""API exposta à interface (window.pywebview.api).

Todo método público devolve {"ok": true, "data": ...} ou {"ok": false, "error": {...}}.
Métodos longos recebem um ``task_id`` gerado pela interface; o andamento chega
por eventos (window.__macpronto) com esse mesmo identificador.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from macpronto import __version__, logs, paths, settings, winutil
from macpronto.compat import laudo as laudo_builder
from macpronto.compat import service as compat
from macpronto.efi import service as efi_service
from macpronto.engine import workspace
from macpronto.scanner import service as scans
from macpronto.tasks import TaskManager, TaskReporter, UserFacingError, guarded

log = logging.getLogger(__name__)


@dataclass
class Session:
    scan: scans.Scan | None = None
    analysis: dict | None = None
    plan: dict | None = None
    laudo: dict | None = None
    selection: dict = field(default_factory=dict)
    efi: dict | None = None
    usb_map: Path | None = None


class Api:
    def __init__(self) -> None:
        self._window: Any = None
        self._session = Session()
        self._tasks = TaskManager(self._emit)

    # ------------------------------------------------------------------ infraestrutura

    def _attach(self, window: Any) -> None:
        self._window = window

    def _emit(self, payload: dict) -> None:
        if self._window is None:
            return
        script = f"window.__macpronto && window.__macpronto({json.dumps(payload, ensure_ascii=False)})"
        self._window.evaluate_js(script)

    def _require_scan(self) -> scans.Scan:
        if self._session.scan is None:
            raise UserFacingError("no-scan", "Faça ou abra um diagnóstico primeiro.")
        return self._session.scan

    def _file_dialog(self, kind: str, file_types: tuple[str, ...], save_filename: str = "") -> str | None:
        import webview

        if self._window is None:
            raise UserFacingError("no-window", "Janela indisponível.")
        dialog = webview.FileDialog.OPEN if kind == "open" else webview.FileDialog.SAVE
        result = self._window.create_file_dialog(
            dialog,
            directory=str(paths.documents_dir()),
            allow_multiple=False,
            save_filename=save_filename,
            file_types=file_types,
        )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    # ------------------------------------------------------------------ aplicativo

    @guarded
    def app_info(self) -> dict:
        try:
            components = workspace.pinned_versions()
        except OSError:
            components = {}
        return {
            "version": __version__,
            "is_admin": winutil.is_admin(),
            "documents_dir": str(paths.documents_dir()),
            "logs_dir": str(paths.logs_dir()),
            "settings": settings.load(),
            "components": {
                name: {
                    "commit": info.get("commit", "")[:12],
                    "repository": info.get("repository"),
                    "license": info.get("license"),
                }
                for name, info in components.items()
            },
        }

    @guarded
    def settings_update(self, changes: dict) -> dict:
        return settings.update(changes or {})

    @guarded
    def logs_recent(self, last_id: int = 0) -> list[dict]:
        return logs.recent(int(last_id or 0))

    @guarded
    def open_logs_folder(self) -> None:
        winutil.open_path(paths.logs_dir())

    @guarded
    def open_path(self, path: str) -> None:
        winutil.open_path(path)

    @guarded
    def reveal_path(self, path: str) -> None:
        winutil.reveal(path)

    @guarded
    def open_url(self, url: str) -> None:
        winutil.open_url(url)

    @guarded
    def cancel(self, task_id: str) -> bool:
        return self._tasks.cancel(task_id)

    # ------------------------------------------------------------------ diagnóstico e laudo

    def _evaluate(self, reporter: TaskReporter, scan: scans.Scan) -> dict:
        with self._tasks.engine_lock:
            result = compat.evaluate(scan, on_event=reporter.engine_event, cancel=reporter.cancel)
        self._session.scan = scan
        self._session.analysis = result["analysis"]
        self._session.plan = result["plan"]
        self._session.laudo = result["laudo"]
        self._session.efi = None
        recommended = result["laudo"]["macos"]["recommended"]
        self._session.selection = {
            "darwin": recommended,
            "answers": {},
            "smbios_model": None,
            "acpi_overrides": {},
            "kext_overrides": {},
        }
        settings.update({"last_scan_id": scan.id})
        return self._scan_payload()

    def _scan_payload(self) -> dict:
        scan = self._session.scan
        assert scan is not None
        return {
            "scan": scan.summary(),
            "report": scan.report,
            "extras": scan.extras,
            "acpi_tables": scan.acpi_tables,
            "laudo": self._session.laudo,
            "plan": self._plan_payload(),
            "selection": self._session.selection,
            "efi": self._session.efi,
            "usb_mapped": self._session.usb_map is not None,
        }

    def _plan_payload(self) -> dict | None:
        plan = self._session.plan
        if plan is None:
            return None
        section = laudo_builder.plan_section(plan)
        return {
            **section,
            "smbios_candidates": plan.get("smbios_candidates", []),
            "default_smbios": plan.get("default_smbios"),
            "all_kexts": plan.get("kexts", []),
            "all_acpi_patches": plan.get("acpi_patches", []),
            "bios_requirements": plan.get("bios_requirements", []),
        }

    def scan_run(self, task_id: str) -> dict:
        def job(reporter: TaskReporter) -> dict:
            with self._tasks.engine_lock:
                scan = scans.run_scan(on_event=reporter.engine_event, cancel=reporter.cancel)
            reporter.stage("Analisando a compatibilidade")
            return self._evaluate(reporter, scan)

        return self._tasks.run(task_id, job)

    def scan_open(self, task_id: str, scan_id: str) -> dict:
        def job(reporter: TaskReporter) -> dict:
            reporter.stage("Abrindo o diagnóstico")
            return self._evaluate(reporter, scans.load_scan(scan_id))

        return self._tasks.run(task_id, job)

    def scan_import(self, task_id: str) -> dict:
        def job(reporter: TaskReporter) -> dict | None:
            chosen = self._file_dialog(
                "open",
                ("Diagnósticos (*.macpronto;*.json;*.zip)", "Todos os arquivos (*.*)"),
            )
            if not chosen:
                return None
            reporter.stage("Importando o diagnóstico")
            try:
                scan = scans.import_scan(Path(chosen))
            except ValueError as exc:
                raise UserFacingError("import", str(exc)) from exc
            return self._evaluate(reporter, scan)

        return self._tasks.run(task_id, job)

    @guarded
    def scan_list(self) -> list[dict]:
        return scans.list_scans()

    @guarded
    def scan_delete(self, scan_id: str) -> None:
        scans.delete_scan(scan_id)
        if self._session.scan and self._session.scan.id == scan_id:
            self._session = Session()

    @guarded
    def scan_export(self) -> str | None:
        scan = self._require_scan()
        default_name = f"{scan.id}{scans.EXPORT_SUFFIX}"
        chosen = self._file_dialog("save", ("Diagnóstico do MacPronto (*.macpronto)",), default_name)
        if not chosen:
            return None
        return str(scans.export_scan(scan, Path(chosen)))

    @guarded
    def session_state(self) -> dict | None:
        if self._session.scan is None:
            return None
        return self._scan_payload()

    # ------------------------------------------------------------------ versão do macOS e plano

    def plan_update(self, task_id: str, selection: dict) -> dict:
        def job(reporter: TaskReporter) -> dict:
            scan = self._require_scan()
            current = {**self._session.selection, **(selection or {})}
            if current.get("darwin") is None:
                raise UserFacingError("no-version", "Escolha uma versão do macOS.")
            reporter.stage("Recalculando o plano da EFI")
            with self._tasks.engine_lock:
                plan = compat.plan(
                    scan,
                    int(current["darwin"]),
                    answers=current.get("answers"),
                    smbios_model=current.get("smbios_model"),
                    acpi_overrides=current.get("acpi_overrides"),
                    kext_overrides=current.get("kext_overrides"),
                    on_event=reporter.engine_event,
                    cancel=reporter.cancel,
                )
            self._session.plan = plan
            self._session.selection = current
            self._session.efi = None
            return {"plan": self._plan_payload(), "selection": current}

        return self._tasks.run(task_id, job)

    # ------------------------------------------------------------------ EFI

    def efi_build(self, task_id: str, options: dict) -> dict:
        def job(reporter: TaskReporter) -> dict:
            scan = self._require_scan()
            if self._session.selection.get("darwin") is None:
                raise UserFacingError("no-version", "Escolha uma versão do macOS.")
            options_ = options or {}
            usb_map = self._session.usb_map if options_.get("use_usb_map", True) else None
            reporter.stage("Preparando a montagem")
            with self._tasks.engine_lock:
                info = efi_service.build(
                    scan,
                    self._session.selection,
                    keyboard=options_.get("keyboard", "abnt2"),
                    usb_map=usb_map,
                    on_event=reporter.engine_event,
                    cancel=reporter.cancel,
                )
            self._session.efi = info
            return info

        return self._tasks.run(task_id, job)

    @guarded
    def efi_keyboards(self) -> list[dict]:
        return [{"value": key, "label": label} for key, (_, label) in efi_service.KEYBOARDS.items()]
