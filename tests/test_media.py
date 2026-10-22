"""Regras de segurança do pendrive e geração do guia (sem formatar nada)."""

from __future__ import annotations

import urllib.request

import pytest

from macpronto.guide import content, render
from macpronto.guide.share import GuideShare
from macpronto.media import disks
from macpronto.media import format as formatter

GB = 1000**3


def make_disk(**changes) -> disks.Disk:
    base = dict(
        number=2,
        model="SanDisk Ultra",
        size_bytes=32 * GB,
        bus="USB",
        unique_id="USBSTOR\\DISK",
        system=False,
        boot=False,
        read_only=False,
    )
    base.update(changes)
    return disks.Disk(**base)


@pytest.mark.parametrize(
    ("changes", "bus", "eligible", "reason"),
    [
        ({}, disks.BUS_USB, True, ""),
        ({"system": True}, disks.BUS_USB, False, "Windows"),
        ({"boot": True}, disks.BUS_USB, False, "Windows"),
        ({"bus": "NVMe"}, 17, False, "USB"),
        ({"read_only": True}, disks.BUS_USB, False, "protegido"),
        ({"size_bytes": 2 * GB}, disks.BUS_USB, False, "Pequeno"),
        ({"size_bytes": 1000 * GB}, disks.BUS_USB, False, "Grande"),
    ],
)
def test_regras_do_pendrive(changes, bus, eligible, reason):
    disk = disks.evaluate(make_disk(**changes), bus)
    assert disk.eligible is eligible
    assert reason in disk.reason


def test_disco_trocado_e_recusado(monkeypatch):
    listed = [make_disk().to_dict() | {"eligible": True}]
    monkeypatch.setattr(disks, "list_disks", lambda: listed)
    assert disks.find_disk(2, "USBSTOR\\DISK", 32 * GB)["number"] == 2
    with pytest.raises(ValueError, match="mudou"):
        disks.find_disk(2, "OUTRO", 32 * GB)
    with pytest.raises(ValueError, match="não está mais"):
        disks.find_disk(5, "USBSTOR\\DISK", 32 * GB)


def test_script_do_diskpart():
    script = formatter.build_script(3, 64 * GB)
    lines = script.splitlines()
    assert lines[0] == "select disk 3"
    assert "clean" in lines and "convert gpt" in lines
    assert "create partition primary size=16384" in lines  # FAT32 limitado a 16 GB
    assert 'format fs=fat32 quick label="MACPRONTO"' in lines
    small = formatter.build_script(3, 8 * GB)
    assert "size=7565" in small
    with pytest.raises(ValueError):
        formatter.build_script(-1, 8 * GB)


@pytest.mark.parametrize(
    ("system", "board", "laptop", "expected"),
    [
        ("LENOVO", "LENOVO", False, "lenovo"),
        ("Gigabyte Technology Co., Ltd.", "Gigabyte Technology Co., Ltd.", False, "gigabyte"),
        ("To Be Filled By O.E.M.", "ASRock", False, "asrock"),
        ("ASUS", "ASUSTeK COMPUTER INC.", True, "asus"),
        ("Micro-Star International Co., Ltd.", "Micro-Star International Co., Ltd.", False, "msi"),
        ("System manufacturer", "Desconhecida", False, "generic"),
    ],
)
def test_fabricante_da_bios(system, board, laptop, expected):
    assert content.detect_vendor(system, board, laptop).key == expected


def test_guia_e_compartilhamento(tmp_path):
    laudo = {
        "machine": {
            "name": "GIGABYTE Z390 AORUS PRO",
            "form_factor": "desktop",
            "form_label": "Desktop",
            "manufacturer": "Gigabyte",
        },
        "verdict": {"status": "compatible", "headline": "Pode virar um Hackintosh.", "summary": "Tudo funciona."},
        "difficulty": {"score": 1, "label": "Muito fácil", "reasons": []},
        "macos": {"recommended": 24},
        "components": [{"name": "i7-9700K", "status": "native", "summary": "Compatível."}],
        "warnings": [],
        "fatal": [],
        "bios_requirements": ["Desativar o Secure Boot."],
    }
    scan = {
        "id": "teste-guia",
        "extras": {
            "system": {"manufacturer": "Gigabyte Technology Co., Ltd."},
            "baseboard": {"manufacturer": "Gigabyte"},
        },
        "report": {"CPU": {"Manufacturer": "Intel"}, "GPU": {"UHD 630": {"Device Type": "Integrated GPU"}}},
    }
    efi = {
        "opencore": "1.0.9",
        "keyboard_label": "Português (Brasil), teclado ABNT2",
        "config": {
            "smbios": {"model": "iMac19,1", "serial": "SEGREDO123"},
            "boot_args": "-v alcid=1",
            "ssdts": ["SSDT-EC.aml"],
            "kexts": ["Lilu.kext"],
            "vesa": True,
        },
        "plan": {"needs_oclp": True, "bios_requirements": [], "decisions": []},
    }
    context = render.build_context(scan, laudo, {"darwin": 24}, efi, usb_mapped=False)
    html = render.render_html(context)
    assert "Gigabyte" in html and "F12" in html
    assert "OpenCore Legacy Patcher" in html  # passo do OCLP
    assert "-igfxvesa" in html  # aviso do modo VESA
    assert "SEGREDO123" not in html  # números de série nunca entram no guia
    assert "macOS Sequoia 15" in html

    (tmp_path / "Guia.html").write_text(html, encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("não pode sair", encoding="utf-8")
    share = GuideShare()
    info = share.start(tmp_path)
    try:
        port = info["url"].rsplit(":", 1)[1].split("/")[0]
        local = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{local}/Guia.html", timeout=5) as response:
            assert "Gigabyte" in response.read().decode("utf-8")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"{local}/segredo.txt", timeout=5)
        assert info["qr_svg"].startswith("<svg")
    finally:
        share.stop()
