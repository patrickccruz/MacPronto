"""Regras de segurança do pendrive e geração do guia (sem formatar nada)."""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from macpronto.guide import render
from macpronto.guide.share import GuideShare
from macpronto.media import disks, recovery
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


def test_scripts_do_diskpart():
    assert formatter.STYLES[0] == "mbr"  # MBR primeiro: funcionou de primeira no pendrive real
    prepare = formatter.prepare_script(3, 64 * GB, "mbr", ["E"]).splitlines()
    assert prepare[:2] == ["select volume E", "remove all dismount noerr"]
    assert "select disk 3" in prepare and "clean" in prepare and "convert mbr noerr" in prepare
    assert "create partition primary size=16384" in prepare  # FAT32 limitado a 16 GB
    assert not any(line.startswith(("format", "gpt")) for line in prepare)  # formatar só depois do volume aparecer

    fmt = formatter.format_script(3, 2).splitlines()
    assert fmt[:4] == ["select disk 3", "select partition 2", 'format fs=fat32 quick label="MACPRONTO"', "assign noerr"]

    gpt = formatter.prepare_script(3, 8 * GB, "gpt")
    assert "convert gpt noerr" in gpt and "size=7565" in gpt
    with pytest.raises(ValueError):
        formatter.prepare_script(-1, 8 * GB)
    with pytest.raises(ValueError):
        formatter.prepare_script(1, 8 * GB, "apm")


def test_particao_de_dados_ignora_a_reservada():
    msr = {"number": 1, "size": 16 * 1024**2, "gpt_type": "{e3c9e316-0b5c-4db8-817d-f92df00215ae}"}
    data = {"number": 2, "size": 16 * GB, "gpt_type": formatter.GPT_BASIC_DATA}
    assert formatter.pick_data_partition([msr, data])["number"] == 2
    assert formatter.pick_data_partition([{"number": 1, "size": GB, "gpt_type": ""}])["number"] == 1  # MBR
    assert formatter.pick_data_partition([]) is None


class FakeApple:
    """Simula os servidores da Apple e o download, sem rede."""

    def __init__(self, monkeypatch, product="111-11111", online=True):
        self.product = product
        self.online = online
        self.downloads = 0
        monkeypatch.setattr(recovery, "image_info", self.image_info)
        monkeypatch.setattr(recovery, "download", self.download)
        monkeypatch.setattr(recovery, "verify", lambda *args, **kwargs: None)

    def image_info(self, darwin):
        if not self.online:
            raise recovery.RecoveryError("sem internet")
        return {
            "product": self.product,
            "image_url": "https://oscdn.apple.com/x/BaseSystem.dmg",
            "image_token": "t",
            "chunklist_url": "https://oscdn.apple.com/x/BaseSystem.chunklist",
            "chunklist_token": "t",
        }

    def download(self, url, target, **kwargs):
        self.downloads += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{self.product} {url}", encoding="utf-8")
        return target


def test_macos_recovery_reaproveitado_ou_atualizado(monkeypatch, tmp_path):
    monkeypatch.setenv("MACPRONTO_DATA_DIR", str(tmp_path))
    apple = FakeApple(monkeypatch)

    first = recovery.ensure(24)
    assert first["cached"] is False and apple.downloads == 2

    again = recovery.ensure(24)  # a Apple tem o mesmo: usa o do computador
    assert again["cached"] is True and apple.downloads == 2

    apple.online = False  # sem internet: usa o do computador
    assert recovery.ensure(24)["cached"] is True and apple.downloads == 2

    apple.online, apple.product = True, "222-22222"  # a Apple publicou outro: baixa o novo
    newer = recovery.ensure(24)
    assert newer["cached"] is False and newer["product"] == "222-22222" and newer["replaced"] == "111-11111"
    assert "222-22222" in Path(newer["dmg"]).read_text(encoding="utf-8")
    assert not list(Path(newer["dmg"]).parent.glob("novo-*"))  # pasta temporária removida

    listed = recovery.cached_images()
    assert [item["product"] for item in listed] == ["222-22222"]
    assert recovery.clear_cache() > 0 and recovery.cached_images() == []


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
