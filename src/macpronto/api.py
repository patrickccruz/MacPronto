"""API exposta à interface (window.pywebview.api).

Todo método público devolve {"ok": true, "data": ...} ou {"ok": false, "error": {...}}.
Métodos longos recebem um ``task_id`` gerado pela interface; o andamento chega
por eventos (window.__macpronto) com esse mesmo identificador.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from macpronto import __version__, logs, paths, settings, updater, winutil
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
    guide: dict | None = None
    media: dict | None = None


class Api:
    def __init__(self) -> None:
        self._window: Any = None
        self._session = Session()
        self._tasks = TaskManager(self._emit)
        self._usb_session = None
        self._share = None
        self._updater = updater.Updater(self._notify_update)

    # ------------------------------------------------------------------ infraestrutura

    def _attach(self, window: Any) -> None:
        self._window = window
        self._updater.start()

    def _shutdown(self) -> None:
        """Chamado ao fechar a janela: cancela tarefas e desliga o compartilhamento do guia."""
        self._updater.stop()
        self._tasks.cancel_all()
        if self._share is not None:
            self._share.stop()

    def _notify_update(self, status: dict) -> None:
        self._emit({"taskId": "atualizacao", "kind": "update", "data": status})

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
        updated = settings.update(changes or {})
        if (changes or {}).get("auto_update"):
            self._updater.wake()
        return updated

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
        # O mapa USB feito numa sessão anterior fica salvo em Documentos\MacPronto\USB\<diagnóstico>
        saved_map = paths.documents_dir() / "USB" / scan.id / "UTBMap.kext"
        self._session.usb_map = saved_map if saved_map.is_dir() else None
        recommended = result["laudo"]["macos"]["recommended"]
        self._session.selection = efi_service.default_selection(recommended)
        self._restore_efi(scan, recommended)
        settings.update({"last_scan_id": scan.id})
        return self._scan_payload()

    def _restore_efi(self, scan: scans.Scan, recommended: int) -> None:
        """Reaproveita a EFI mais recente deste diagnóstico, se ela bate com o plano recomendado."""
        builds = [info for info in efi_service.list_builds(scan.id) if efi_service.is_complete(info)]
        if not builds:
            return
        latest = builds[0]
        selection = efi_service.build_selection(latest)
        if int(selection["darwin"]) != int(recommended) or not efi_service.is_default_selection(selection):
            log.info("EFI anterior (%s) foi montada com outras escolhas; fica na lista para usar", latest["folder"])
            return
        self._session.efi = latest
        log.info("EFI anterior reaproveitada: %s (montada em %s)", latest["folder"], latest.get("created_at"))

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
            "guide": self._session.guide,
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
    def efi_builds(self) -> list[dict]:
        """EFIs já montadas para o diagnóstico aberto, da mais nova para a mais antiga."""
        scan = self._require_scan()
        current = (self._session.efi or {}).get("folder")
        return [
            {
                **info,
                "complete": efi_service.is_complete(info),
                "current": info.get("folder") == current,
                "selection": efi_service.build_selection(info),
            }
            for info in efi_service.list_builds(scan.id)
        ]

    def efi_use(self, task_id: str, folder: str) -> dict:
        """Volta a usar uma EFI montada antes. Recalcula o plano se ela foi feita com outras escolhas."""

        def job(reporter: TaskReporter) -> dict:
            scan = self._require_scan()
            info = next((b for b in efi_service.list_builds(scan.id) if b.get("folder") == folder), None)
            if info is None:
                raise UserFacingError("not-found", "Essa EFI não foi encontrada. Ela pode ter sido apagada.")
            if not efi_service.is_complete(info):
                raise UserFacingError(
                    "incomplete", "A pasta dessa EFI está incompleta (arquivos apagados). Monte de novo."
                )
            selection = efi_service.build_selection(info)
            if selection != self._session.selection:
                reporter.stage("Recalculando o plano para as escolhas dessa EFI")
                with self._tasks.engine_lock:
                    self._session.plan = compat.plan(
                        scan,
                        int(selection["darwin"]),
                        answers=selection.get("answers"),
                        smbios_model=selection.get("smbios_model"),
                        acpi_overrides=selection.get("acpi_overrides"),
                        kext_overrides=selection.get("kext_overrides"),
                        on_event=reporter.engine_event,
                        cancel=reporter.cancel,
                    )
                self._session.selection = selection
            self._session.efi = info
            log.info("Usando a EFI montada em %s (%s)", info.get("created_at"), info["folder"])
            return self._scan_payload()

        return self._tasks.run(task_id, job)

    @guarded
    def efi_keyboards(self) -> list[dict]:
        return [{"value": key, "label": label} for key, (_, label) in efi_service.KEYBOARDS.items()]

    # ------------------------------------------------------------------ mapeamento USB

    def _usb(self):
        from macpronto.usb.mapper import UsbMapSession

        scan = self._require_scan()
        if scan.source != "local":
            raise UserFacingError("usb-remote", "O mapeamento USB só funciona no próprio computador diagnosticado.")
        if self._usb_session is None or self._usb_session.scan_id != scan.id:
            self._usb_session = UsbMapSession(scan.id)
        return self._usb_session

    @guarded
    def usb_refresh(self) -> dict:
        return self._usb().refresh()

    @guarded
    def usb_update_port(self, controller_id: str, index: int, changes: dict) -> dict:
        return self._usb().update_port(controller_id, int(index), changes or {})

    @guarded
    def usb_select(self, mode: str) -> dict:
        return self._usb().select(mode)

    @guarded
    def usb_reset(self) -> dict:
        self._session.usb_map = None
        return self._usb().reset()

    @guarded
    def usb_build(self) -> dict:
        session = self._usb()
        scan = self._require_scan()
        destination = paths.documents_dir() / "USB" / scan.id
        destination.mkdir(parents=True, exist_ok=True)
        kext = session.build_kext(destination)
        self._session.usb_map = kext
        efi_updated = False
        if self._session.efi is not None:
            self._session.efi = efi_service.apply_usb_to_build(self._session.efi, kext)
            efi_updated = True
        return {"kext": str(kext), "efi_updated": efi_updated, "efi": self._session.efi}

    # ------------------------------------------------------------------ guia

    def _build_guide(self, with_pdf: bool = True) -> dict:
        from macpronto.guide import render

        scan = self._require_scan()
        if self._session.laudo is None:
            raise UserFacingError("no-laudo", "Faça ou abra um diagnóstico primeiro.")
        selection = dict(self._session.selection)
        if self._session.efi and self._session.efi.get("macos"):
            selection["darwin"] = self._session.efi["macos"]  # o guia segue a EFI montada
        info = render.build(
            scan.to_dict(),
            self._session.laudo,
            selection,
            self._session.efi,
            usb_mapped=bool(self._session.efi and self._session.efi.get("usb_map")),
            with_pdf=with_pdf,
        )
        self._session.guide = info
        return info

    def guide_build(self, task_id: str) -> dict:
        def job(reporter: TaskReporter) -> dict:
            reporter.stage("Gerando o guia personalizado")
            return self._build_guide()

        return self._tasks.run(task_id, job)

    @guarded
    def guide_share_start(self) -> dict:
        from macpronto.guide.share import GuideShare

        guide = self._session.guide or self._build_guide(with_pdf=False)
        if self._share is None:
            self._share = GuideShare()
        return self._share.start(Path(guide["folder"]))

    @guarded
    def guide_share_stop(self) -> None:
        if self._share is not None:
            self._share.stop()

    # ------------------------------------------------------------------ pendrive

    @guarded
    def media_disks(self) -> list[dict]:
        from macpronto.media import disks

        return disks.list_disks()

    def media_create(self, task_id: str, options: dict) -> dict:
        from macpronto.media import writer

        def job(reporter: TaskReporter) -> dict:
            options_ = options or {}
            if str(options_.get("confirm", "")).strip().upper() != "APAGAR":
                raise UserFacingError("confirm", "Digite APAGAR para confirmar que o pendrive pode ser apagado.")
            if self._session.efi is None:
                raise UserFacingError("no-efi", "Monte a EFI antes de preparar o pendrive.")
            if not winutil.is_admin():
                raise UserFacingError(
                    "admin",
                    "Formatar o pendrive exige administrador. Use o botão para reabrir o MacPronto como administrador.",
                )
            reporter.stage("Atualizando o guia")
            guide = self._build_guide()
            result = writer.create(
                reporter,
                disk_number=int(options_["number"]),
                unique_id=str(options_["unique_id"]),
                size_bytes=int(options_["size_bytes"]),
                # A versão para a qual a EFI foi montada (a seleção pode ter mudado depois)
                darwin=int(self._session.efi.get("macos") or self._session.selection["darwin"]),
                efi_dir=Path(self._session.efi["efi_dir"]),
                extra_folder=Path(guide["folder"]),
            )
            self._session.media = result
            return {**result, "guide": guide}

        return self._tasks.run(task_id, job)

    @guarded
    def media_eject(self, letter: str) -> bool:
        return winutil.eject(letter)

    @guarded
    def media_recovery_cache(self) -> list[dict]:
        from macpronto.media import recovery

        return recovery.cached_images()

    @guarded
    def media_recovery_clear(self) -> int:
        from macpronto.media import recovery

        if self._tasks.active("pendrive"):
            raise UserFacingError("busy", "Espere o pendrive terminar de ser gravado.")
        return recovery.clear_cache()

    @guarded
    def relaunch_as_admin(self) -> bool:
        if not winutil.relaunch_as_admin():
            return False
        if self._window is not None:
            self._window.destroy()
        return True

    # ------------------------------------------------------------------ atualizações

    @guarded
    def update_status(self) -> dict:
        return self._updater.status()

    @guarded
    def update_check(self) -> dict:
        return self._updater.check()

    def update_install(self, task_id: str) -> dict:
        def busy() -> bool:
            return any(other != task_id for other in self._tasks.active())

        def job(reporter: TaskReporter) -> dict:
            info = self._updater.available
            if info is None:
                raise UserFacingError("no-update", "Não há atualização disponível.")
            if not updater.is_installed():
                raise UserFacingError(
                    "portable",
                    "Esta cópia do MacPronto não veio do instalador (é a portátil). Baixe a versão nova na página do GitHub.",
                )
            message = "Espere terminar o que está em andamento (pendrive, EFI ou diagnóstico) antes de atualizar."
            if busy():
                raise UserFacingError("busy", message)
            reporter.stage(f"Baixando o MacPronto {info['version']}")
            installer = self._updater.download(
                info,
                progress=lambda done, total: reporter.progress(done, total, "Baixando"),
                cancel=reporter.cancel,
            )
            reporter.check_cancelled()
            if busy():
                raise UserFacingError("busy", message)
            reporter.stage("Instalando: o MacPronto vai fechar e abrir de novo sozinho")
            updater.launch_installer(installer, info["version"])
            threading.Timer(1.5, self._close_for_update).start()
            return {"version": info["version"], "restarting": True}

        return self._tasks.run(task_id, job)

    def _close_for_update(self) -> None:
        log.info("Fechando o MacPronto para o instalador da atualização")
        self._shutdown()
        if self._window is not None:
            self._window.destroy()

    # ------------------------------------------------------------------ laudo

    def laudo_export(self, task_id: str) -> dict:
        def job(reporter: TaskReporter) -> dict:
            from macpronto.guide import render

            scan = self._require_scan()
            if self._session.laudo is None:
                raise UserFacingError("no-laudo", "Faça ou abra um diagnóstico primeiro.")
            reporter.stage("Salvando o laudo")
            return render.export_laudo(scan.to_dict(), self._session.laudo)

        return self._tasks.run(task_id, job)

    # ------------------------------------------------------------------ base de regras

    @guarded
    def engine_status(self) -> list[dict]:
        from macpronto.engine import updates

        return updates.status()

    @guarded
    def engine_check(self, name: str) -> dict:
        from macpronto.engine import updates

        try:
            return updates.check(name)
        except OSError as exc:
            raise UserFacingError("offline", f"Não foi possível consultar o GitHub: {exc}") from exc

    def engine_update(self, task_id: str, name: str) -> dict:
        from macpronto.engine import updates

        def job(reporter: TaskReporter) -> dict:
            with self._tasks.engine_lock:
                return updates.install(name, on_event=reporter.engine_event, cancel=reporter.cancel)

        return self._tasks.run(task_id, job)

    @guarded
    def engine_revert(self, name: str) -> list[dict]:
        from macpronto.engine import updates

        with self._tasks.engine_lock:
            updates.revert(name)
        return updates.status()
