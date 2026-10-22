from __future__ import annotations

import json
import zipfile

import pytest

from macpronto.scanner import service as scans


def test_exportar_e_importar(report_loader, tmp_path):
    report = report_loader("desktop-coffee-lake-rx580")
    scan = scans._import_report_json(report, None)
    acpi = scan.folder / scans.ACPI_DIR
    acpi.mkdir(parents=True)
    (acpi / "dsdt.aml").write_bytes(b"DSDT")
    scan.acpi_tables = ["dsdt.aml"]
    scan.save()

    exported = scans.export_scan(scan, tmp_path / "amigo")
    assert exported.suffix == ".macpronto"
    with zipfile.ZipFile(exported) as archive:
        assert set(archive.namelist()) == {"scan.json", "ACPI/dsdt.aml"}

    imported = scans.import_scan(exported)
    assert imported.source == "imported"
    assert imported.id != scan.id
    assert imported.acpi_tables == ["dsdt.aml"]
    assert imported.report == report
    assert any(item["id"] == imported.id for item in scans.list_scans())


def test_importar_zip_do_hardware_sniffer(report_loader, tmp_path):
    bundle = tmp_path / "SysReport.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("SysReport/Report.json", json.dumps(report_loader("desktop-intel-vmd")))
        archive.writestr("SysReport/ACPI/DSDT.aml", b"DSDT")
        archive.writestr("SysReport/ACPI/SSDT1.aml", b"SSDT")
    scan = scans.import_scan(bundle)
    assert sorted(scan.acpi_tables) == ["DSDT.aml", "SSDT1.aml"]
    assert scan.label == "MSI MAG B460M MORTAR"


def test_relatorio_incompleto_e_recusado(tmp_path):
    broken = tmp_path / "Report.json"
    broken.write_text(json.dumps({"CPU": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Relatório incompleto"):
        scans.import_scan(broken)
