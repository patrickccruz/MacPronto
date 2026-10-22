"""Laudo de compatibilidade com o OpCore Simplify vendorizado (testes de integração)."""

from __future__ import annotations

from datetime import datetime

import pytest

from macpronto.compat import laudo, macos
from macpronto.compat import service as compat
from macpronto.scanner.service import Scan


def make_scan(report: dict, name: str) -> Scan:
    return Scan(
        id=f"teste-{name}",
        created_at=datetime.now().isoformat(timespec="seconds"),
        source="imported",
        label=name,
        report=report,
    )


@pytest.fixture(scope="module")
def evaluations():
    from tests.conftest import load_report

    results = {}
    for name in (
        "desktop-coffee-lake-rx580",
        "laptop-tiger-lake",
        "desktop-ryzen-rtx3060",
        "desktop-intel-vmd",
        "legacy-no-sse4",
    ):
        results[name] = compat.evaluate(make_scan(load_report(name), name))
    return results


def statuses(result: dict, category: str) -> list[str]:
    return [c["status"] for c in result["laudo"]["components"] if c["category"] == category]


def test_desktop_compativel(evaluations):
    result = evaluations["desktop-coffee-lake-rx580"]
    report = result["laudo"]
    assert report["verdict"]["status"] == "compatible"
    assert report["macos"]["recommended"] == macos.DEFAULT_DARWIN
    assert report["difficulty"]["score"] == 1
    assert statuses(result, "gpu") == ["native", "native"]
    plan = result["plan"]
    checked = {k["name"] for k in plan["kexts"] if k["checked"]}
    assert {"Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausiEthernet"} <= checked
    assert plan["smbios_model"]


def test_notebook_iris_xe_incompativel(evaluations):
    report = evaluations["laptop-tiger-lake"]["laudo"]
    assert report["verdict"]["status"] == "incompatible"
    assert report["difficulty"] is None
    assert any(f["code"] == "gpu-unsupported" for f in report["fatal"])
    gpu = [c for c in report["components"] if c["category"] == "gpu"]
    assert all(c["status"] == "incompatible" for c in gpu)
    assert any(c["category"] == "biometric" for c in report["components"])


def test_ryzen_com_nvidia_precisa_trocar_video(evaluations):
    report = evaluations["desktop-ryzen-rtx3060"]["laudo"]
    assert report["verdict"]["status"] == "needs-hardware"
    gpu = next(c for c in report["components"] if c["category"] == "gpu")
    assert gpu["status"] == "replace" and gpu["blocking"]
    cpu = next(c for c in report["components"] if c["category"] == "cpu")
    assert cpu["status"] == "tweak"


def test_vmd_pede_ajuste_na_bios(evaluations):
    report = evaluations["desktop-intel-vmd"]["laudo"]
    assert report["verdict"]["status"] == "needs-bios"
    assert report["fatal"][0]["code"] == "intel-vmd"


def test_processador_sem_sse4_incompativel(evaluations):
    report = evaluations["legacy-no-sse4"]["laudo"]
    assert report["verdict"]["status"] == "incompatible"
    assert any(f["code"] == "cpu-sse4" for f in report["fatal"])


def test_plano_responde_decisoes(report_loader):
    scan = make_scan(report_loader("laptop-tiger-lake"), "plano")
    # A análise falha (sem vídeo compatível), mas o Wi-Fi Intel sozinho gera uma decisão.
    scan.report["GPU"]["Intel(R) Iris(R) Xe Graphics"]["Device ID"] = "8086-9B41"  # UHD 620 (Comet Lake-U)
    scan.report["CPU"]["Codename"] = "Comet Lake-U"
    plan = compat.plan(scan, 24)
    wifi = next(d for d in plan["decisions"] if d["key"] == "intel-wifi-kext")
    assert wifi["options"] and wifi["recommended"] == "1"

    changed = compat.plan(scan, 24, answers={"intel-wifi-kext": "3"})
    checked = {k["name"] for k in changed["kexts"] if k["checked"]}
    assert "itlwm" in checked


@pytest.mark.parametrize(
    ("native", "suggested", "expected"),
    [
        ({"min": "17.0.0", "max": "25.99.99"}, "25.99.99", 24),
        ({"min": "17.0.0", "max": "21.99.99"}, "21.99.99", 21),
        ({"min": "17.0.0", "max": "25.99.99"}, "22.99.99", 22),
        ({"min": "20.0.0", "max": "25.99.99"}, "25.99.99", 24),
        (None, None, None),
    ],
)
def test_recomendacao(native, suggested, expected):
    assert macos.recommend(native, suggested)[0] == expected


def test_texto_de_faixa():
    assert laudo._range_text({"min": 17, "max": 25}) == "todas as versões, do High Sierra ao Tahoe"
    assert laudo._range_text({"min": 17, "max": 21}) == "até o macOS Monterey"
    assert laudo._range_text({"min": 20, "max": 25}) == "a partir do macOS Big Sur"
