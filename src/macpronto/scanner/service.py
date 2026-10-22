"""Diagnóstico: coleta, salva, exporta e importa.

Cada diagnóstico fica em Documentos\\MacPronto\\Diagnosticos\\<id>\\ com:
    scan.json   relatório do Hardware Sniffer + dados complementares
    ACPI\\       tabelas ACPI (.aml)

O arquivo exportado (.macpronto) é um zip com esse mesmo conteúdo. Ele serve
para o modo simulação: analisar o computador de um amigo em outra máquina.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from macpronto import __version__, paths
from macpronto.engine import EngineEvent, run_task
from macpronto.scanner import acpi

log = logging.getLogger(__name__)

SCAN_FILE = "scan.json"
ACPI_DIR = "ACPI"
EXPORT_SUFFIX = ".macpronto"


@dataclass
class Scan:
    id: str
    created_at: str
    source: str  # "local" ou "imported"
    label: str
    report: dict
    extras: dict = field(default_factory=dict)
    acpi_tables: list[str] = field(default_factory=list)
    app_version: str = __version__

    @property
    def folder(self) -> Path:
        return paths.scans_dir() / self.id

    @property
    def acpi_dir(self) -> Path | None:
        folder = self.folder / ACPI_DIR
        return folder if self.acpi_tables and folder.is_dir() else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "source": self.source,
            "label": self.label,
            "report": self.report,
            "extras": self.extras,
            "acpi_tables": self.acpi_tables,
            "app_version": self.app_version,
        }

    def summary(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "source": self.source,
            "label": self.label,
            "has_acpi": bool(self.acpi_tables),
        }

    def save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / SCAN_FILE).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> Scan:
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            source=data.get("source", "local"),
            label=data.get("label") or machine_label(data.get("report", {})),
            report=data["report"],
            extras=data.get("extras") or {},
            acpi_tables=data.get("acpi_tables") or [],
            app_version=data.get("app_version", "?"),
        )


def machine_label(report: dict) -> str:
    name = report.get("Motherboard", {}).get("Name") or "Computador"
    return re.sub(r"\s+", " ", name).strip()


def _new_id(label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-")[:40] or "computador"
    return f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"


def run_scan(on_event: Callable[[EngineEvent], None] | None = None, cancel: threading.Event | None = None) -> Scan:
    """Diagnóstico completo da máquina atual."""
    result = run_task("sniff", {}, on_event=on_event, cancel=cancel)
    report = result["report"]
    label = machine_label(report)
    scan = Scan(
        id=_new_id(label),
        created_at=datetime.now().isoformat(timespec="seconds"),
        source="local",
        label=label,
        report=report,
        extras=result.get("extras") or {},
    )

    if on_event:
        on_event(EngineEvent("stage", {"title": "Extraindo tabelas ACPI"}))
    try:
        scan.acpi_tables = acpi.dump_tables(scan.folder / ACPI_DIR)
    except Exception as exc:  # noqa: BLE001 - o laudo sai mesmo sem ACPI; a EFI é que exige
        log.warning("Tabelas ACPI não extraídas: %s", exc)
        if on_event:
            on_event(EngineEvent("log", {"level": "warning", "message": f"Tabelas ACPI não extraídas: {exc}"}))

    scan.save()
    log.info("Diagnóstico salvo em %s", scan.folder)
    return scan


def load_scan(scan_id: str) -> Scan:
    path = paths.scans_dir() / scan_id / SCAN_FILE
    if not path.exists():
        raise FileNotFoundError(f"Diagnóstico {scan_id} não encontrado")
    return Scan.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_scans() -> list[dict]:
    items = []
    for folder in sorted(paths.scans_dir().iterdir(), reverse=True):
        scan_file = folder / SCAN_FILE
        if not scan_file.exists():
            continue
        try:
            items.append(Scan.from_dict(json.loads(scan_file.read_text(encoding="utf-8"))).summary())
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            log.debug("Ignorando diagnóstico inválido em %s: %s", folder, exc)
    return items


def delete_scan(scan_id: str) -> None:
    folder = paths.scans_dir() / scan_id
    if folder.is_dir() and folder.parent == paths.scans_dir():
        shutil.rmtree(folder)


def export_scan(scan: Scan, destination: Path) -> Path:
    if destination.suffix != EXPORT_SUFFIX:
        destination = destination.with_suffix(EXPORT_SUFFIX)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(SCAN_FILE, json.dumps(scan.to_dict(), indent=2, ensure_ascii=False))
        if scan.acpi_dir:
            for table in sorted(scan.acpi_dir.glob("*.aml")):
                archive.write(table, f"{ACPI_DIR}/{table.name}")
    return destination


def import_scan(source: Path) -> Scan:
    """Importa um .macpronto, um Report.json do Hardware Sniffer ou um zip com Report.json e ACPI/."""
    if source.suffix.lower() == ".json":
        return _import_report_json(json.loads(source.read_text(encoding="utf-8")), None)

    if not zipfile.is_zipfile(source):
        raise ValueError("Arquivo não reconhecido. Use um .macpronto, um Report.json ou um .zip do Hardware Sniffer.")

    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        scan_name = next((n for n in names if n.rsplit("/", 1)[-1] == SCAN_FILE), None)
        report_name = next((n for n in names if n.rsplit("/", 1)[-1].lower() == "report.json"), None)

        if scan_name:
            data = json.loads(archive.read(scan_name).decode("utf-8"))
            label = data.get("label") or machine_label(data.get("report", {}))
            data.update({"id": _new_id(label), "source": "imported", "acpi_tables": []})
            scan = Scan.from_dict(data)
        elif report_name:
            scan = _import_report_json(json.loads(archive.read(report_name).decode("utf-8")), None)
        else:
            raise ValueError("O arquivo não contém um diagnóstico do MacPronto nem um Report.json.")

        tables = [n for n in names if n.lower().endswith(".aml") and "/acpi/" in f"/{n.lower()}"]
        if tables:
            target = scan.folder / ACPI_DIR
            target.mkdir(parents=True, exist_ok=True)
            for name in tables:
                file_name = Path(name).name
                (target / file_name).write_bytes(archive.read(name))
                scan.acpi_tables.append(file_name)

    _validate_report(scan.report)
    scan.save()
    return scan


def _import_report_json(report: dict, _acpi: Path | None) -> Scan:
    _validate_report(report)
    label = machine_label(report)
    scan = Scan(
        id=_new_id(label),
        created_at=datetime.now().isoformat(timespec="seconds"),
        source="imported",
        label=label,
        report=report,
    )
    scan.save()
    return scan


def _validate_report(report: dict) -> None:
    required = ("Motherboard", "CPU", "GPU")
    missing = [key for key in required if key not in report]
    if missing:
        raise ValueError(f"Relatório incompleto: faltam as seções {', '.join(missing)}.")
