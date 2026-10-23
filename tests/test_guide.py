"""Perfis de BIOS do guia: detecção por marca e linha, placa-mãe e tipo de BIOS."""

from __future__ import annotations

import pytest

from macpronto.guide import content, render

# (fabricante do sistema, família, modelo, fabricante da placa, fabricante da BIOS, notebook) -> perfil
CASES = [
    ("LENOVO", "ThinkCentre M80q", "11DQS1JR00", "LENOVO", "LENOVO", False, "lenovo-thinkcentre"),
    ("LENOVO", "ThinkStation P340", "30DH", "LENOVO", "LENOVO", False, "lenovo-thinkcentre"),
    ("LENOVO", "ThinkPad T480", "20L5CTO1WW", "LENOVO", "LENOVO", True, "lenovo-thinkpad"),
    ("LENOVO", "IdeaPad 3 15ITL6", "82H8", "LENOVO", "LENOVO", True, "lenovo-consumer"),
    ("LENOVO", "Legion 5 15ACH6H", "82JU", "LENOVO", "LENOVO", True, "lenovo-consumer"),
    ("LENOVO", "ThinkBook 14 G2 ITL", "20VD", "LENOVO", "LENOVO", True, "lenovo-consumer"),
    ("LENOVO", "IdeaCentre 3 07ADA05", "90MV", "LENOVO", "LENOVO", False, "lenovo-consumer"),
    ("Dell Inc.", "OptiPlex", "OptiPlex 7070", "Dell Inc.", "Dell Inc.", False, "dell-business"),
    ("Dell Inc.", "Latitude", "Latitude 5420", "Dell Inc.", "Dell Inc.", True, "dell-business"),
    ("Dell Inc.", "", "Precision 3561", "Dell Inc.", "Dell Inc.", True, "dell-business"),
    ("Dell Inc.", "Inspiron", "Inspiron 15 3511", "Dell Inc.", "Dell Inc.", True, "dell-consumer"),
    ("Dell Inc.", "XPS", "XPS 13 9310", "Dell Inc.", "Dell Inc.", True, "dell-consumer"),
    ("Alienware", "Alienware", "Alienware m15 R4", "Alienware", "Alienware", True, "dell-consumer"),
    ("HP", "103C_53307F HP EliteDesk", "HP EliteDesk 800 G4 DM 65W", "HP", "HP", False, "hp-business"),
    ("HP", "103C_5336AN HP ProBook", "HP ProBook 440 G8 Notebook PC", "HP", "HP", True, "hp-business"),
    ("HP", "103C_5336AN HP ZBook", "HP ZBook Firefly 14 G8", "HP", "HP", True, "hp-business"),
    (
        "Hewlett-Packard",
        "103C_53307F",
        "HP Compaq 8200 Elite SFF PC",
        "Hewlett-Packard",
        "Hewlett-Packard",
        False,
        "hp-business",
    ),
    ("HP", "103C_5335KV HP Pavilion", "HP Pavilion Laptop 15-eg0xxx", "HP", "Insyde", True, "hp-consumer"),
    ("HP", "103C_5335KV HP Victus", "Victus by HP Laptop 16-d0xxx", "HP", "AMI", True, "hp-consumer"),
    ("HP", "", "HP Laptop 15-dy2xxx", "HP", "Insyde", True, "hp-consumer"),
    ("Acer", "Aspire 5", "Aspire A515-54G", "CFL", "Insyde Corp.", True, "acer"),
    (
        "ASUSTeK COMPUTER INC.",
        "VivoBook",
        "VivoBook_ASUSLaptop X512FA",
        "ASUSTeK COMPUTER INC.",
        "American Megatrends Inc.",
        True,
        "asus-notebook",
    ),
    (
        "ASUSTeK COMPUTER INC.",
        "",
        "System Product Name",
        "ASUSTeK COMPUTER INC.",
        "American Megatrends Inc.",
        False,
        "asus",
    ),
    (
        "Micro-Star International Co., Ltd.",
        "GF",
        "GF63 Thin 9SC",
        "Micro-Star International Co., Ltd.",
        "American Megatrends Inc.",
        True,
        "msi-notebook",
    ),
    (
        "Micro-Star International Co., Ltd.",
        "",
        "MS-7C02",
        "Micro-Star International Co., Ltd.",
        "American Megatrends Inc.",
        False,
        "msi",
    ),
    (
        "To Be Filled By O.E.M.",
        "To Be Filled By O.E.M.",
        "To Be Filled By O.E.M.",
        "ASRock",
        "American Megatrends Inc.",
        False,
        "asrock",
    ),
    (
        "Gigabyte Technology Co., Ltd.",
        "Z390 MB",
        "Z390 AORUS PRO",
        "Gigabyte Technology Co., Ltd.",
        "American Megatrends Inc.",
        False,
        "gigabyte",
    ),
    ("Positivo Tecnologia SA", "Positivo Motion", "C4128F", "Positivo Tecnologia SA", "Insyde Corp.", True, "positivo"),
    ("VAIO", "VAIO FE15", "VJFE52F11X", "VAIO", "American Megatrends Inc.", True, "positivo"),
    ("Avell High Performance", "", "A62 LIV", "Avell", "INSYDE Corp.", True, "avell"),
    ("Multilaser", "Ultra", "UB230", "Multilaser", "American Megatrends Inc.", True, "multilaser"),
    (
        "SAMSUNG ELECTRONICS CO., LTD.",
        "Galaxy Book2",
        "750XED",
        "SAMSUNG ELECTRONICS CO., LTD.",
        "American Megatrends International, LLC.",
        True,
        "samsung",
    ),
    ("BIOSTAR Group", "", "B450MH", "BIOSTAR Group", "American Megatrends Inc.", False, "biostar"),
    ("System manufacturer", "", "System Product Name", "Desconhecida", "American Megatrends Inc.", False, "engine-ami"),
    ("OEM", "", "Notebook", "Unknown", "INSYDE Corp.", True, "engine-insyde"),
    ("", "", "", "", "Phoenix Technologies Ltd.", True, "engine-phoenix"),
    (
        "Shpacker Industrial",
        "Dynamic",
        "Chipset X",
        "Unknown",
        "",
        False,
        "generic",
    ),  # "hp" e "ami" no meio de palavras
]


@pytest.mark.parametrize(("system", "family", "model", "board", "bios", "laptop", "expected"), CASES)
def test_deteccao_do_perfil(system, family, model, board, bios, laptop, expected):
    profile = content.detect_profile(system, family, model, board, bios, laptop)
    assert profile.id == expected


def test_arquivo_de_perfis_e_valido():
    settings = set(content.keywords())
    profiles = content.profiles()
    assert "generic" in profiles
    for profile in profiles.values():
        assert profile.kind in ("oem", "board", "engine", "generic"), profile.id
        assert profile.confidence in content.CONFIDENCE, profile.id
        assert profile.bios_key and profile.boot_key and profile.name, profile.id
        assert set(profile.paths) <= settings, f"{profile.id}: ajuste desconhecido em paths"
        assert set(profile.absent) <= settings, f"{profile.id}: ajuste desconhecido em absent"
        if profile.confidence == "conferido":
            assert profile.checked_on, f"{profile.id}: conferido sem o modelo em checked_on"
        if profile.kind in ("oem", "board") and not profile.engine_paths:
            assert "secure_boot" in profile.paths and "csm" in profile.paths, profile.id


def test_marcas_que_seguem_o_tipo_de_bios():
    insyde = content.profile_by_id("positivo", "Insyde Corp.")
    ami = content.profile_by_id("positivo", "American Megatrends Inc.")
    assert insyde.paths["secure_boot"] == content.profiles()["engine-insyde"].paths["secure_boot"]
    assert ami.paths["sata"] == content.profiles()["engine-ami"].paths["sata"]
    with pytest.raises(ValueError):
        content.profile_by_id("nao-existe")


def make_inputs(system="LENOVO", family="ThinkCentre M80q", bios="LENOVO"):
    laudo = {
        "machine": {
            "name": "LENOVO 11DQS1JR00",
            "form_factor": "desktop",
            "form_label": "Desktop",
            "manufacturer": system,
        },
        "verdict": {"status": "compatible", "headline": "Pode virar um Hackintosh.", "summary": "Tudo funciona."},
        "difficulty": {"score": 1, "label": "Muito fácil", "reasons": []},
        "macos": {"recommended": 24},
        "components": [],
        "warnings": [],
        "fatal": [],
        "bios_requirements": [],
    }
    scan = {
        "id": "teste-perfil",
        "extras": {
            "system": {"manufacturer": system, "family": family, "model": "11DQS1JR00"},
            "baseboard": {"manufacturer": system},
            "bios": {"vendor": bios},
        },
        "report": {"CPU": {"Manufacturer": "Intel"}, "GPU": {"UHD 630": {"Device Type": "Integrated GPU"}}},
    }
    return scan, laudo


@pytest.mark.parametrize("profile_id", list(content.profiles()))
def test_guia_gerado_para_cada_perfil(profile_id):
    scan, laudo = make_inputs()
    context = render.build_context(scan, laudo, {"darwin": 24}, None, usb_mapped=False, profile_id=profile_id)
    html = render.render_html(context)
    profile = content.profiles()[profile_id]
    assert profile.name in html
    assert "Procure por:" in html  # palavras-chave sempre presentes
    assert "Teclas da BIOS por marca" in html and "Lenovo ThinkPad" in html
    assert "(escolhido à mão)" in html
    for item in context["bios_settings"]:
        assert item["path"] or item["keywords"], f"{profile_id}: {item['setting'].key} sem caminho nem palavras-chave"


def test_guia_detectado_mostra_a_maquina_e_o_perfil():
    scan, laudo = make_inputs()
    context = render.build_context(scan, laudo, {"darwin": 24}, None, usb_mapped=False)
    html = render.render_html(context)
    assert context["vendor"].id == "lenovo-thinkcentre" and context["profile_detected"]
    assert "feitos para: LENOVO ThinkCentre M80q" in html
    assert "Devices &gt; ATA Drive Setup" in html  # caminho do perfil ThinkCentre
    assert "(escolhido à mão)" not in html
