"""Gera o guia personalizado (HTML) e o PDF (pelo Edge do Windows, em modo headless)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from macpronto import __version__, paths
from macpronto.compat import macos
from macpronto.guide import content

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent / "templates"
CREATE_NO_WINDOW = 0x08000000

EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_context(scan: dict, laudo: dict, selection: dict, efi: dict | None, usb_mapped: bool) -> dict:
    machine = laudo["machine"]
    extras = scan.get("extras") or {}
    is_laptop = machine.get("form_factor") == "laptop"
    vendor = content.detect_vendor(
        extras.get("system", {}).get("manufacturer", machine.get("manufacturer", "")),
        extras.get("baseboard", {}).get("manufacturer", ""),
        is_laptop,
    )

    darwin = selection.get("darwin") or laudo["macos"].get("recommended")
    version = macos.get(darwin)
    report = scan.get("report", {})
    has_igpu = any(g.get("Device Type") == "Integrated GPU" for g in report.get("GPU", {}).values())
    vmd = any(f.get("code") == "intel-vmd" for f in laudo.get("fatal", []))

    plan = (efi or {}).get("plan") or {}
    requirements = plan.get("bios_requirements") or []
    settings = [
        {"setting": setting, "path": vendor.paths.get(setting.key)}
        for setting in content.bios_settings(
            report.get("CPU", {}).get("Manufacturer", "Intel"), has_igpu, requirements, vmd
        )
    ]

    macos_name = version.name if version else "macOS"
    install_steps = [
        {"title": title, "text": text.format(boot_key=vendor.boot_key, macos_name=macos_name)}
        for title, text in content.INSTALL_STEPS
    ]

    post_install = [{"title": title, "text": text} for title, text in content.POST_INSTALL]
    if plan.get("needs_oclp"):
        post_install.insert(
            1,
            {
                "title": "Rode o OpenCore Legacy Patcher",
                "text": (
                    "Esta instalação precisa de patches de sistema. No macOS instalado, baixe o OpenCore Legacy Patcher "
                    "(github.com/dortania/OpenCore-Legacy-Patcher; para o Tahoe, o fork github.com/lzhoang2801/OpenCore-Legacy-Patcher), "
                    "abra-o, escolha Post-Install Root Patch > Start Root Patching e reinicie. Repita depois de cada atualização "
                    "do macOS. Não use a opção Build and Install OpenCore: a EFI do MacPronto já é a certa."
                ),
            },
        )
    config = (efi or {}).get("config") or {}
    if config.get("vesa"):
        post_install.append(
            {
                "title": "Ative a aceleração do vídeo integrado",
                "text": (
                    "A EFI usa o modo VESA porque há monitor no HDMI/DVI do vídeo integrado. Ligue o monitor na DisplayPort e "
                    "remova -igfxvesa dos boot-args, ou peça ajuda nos fóruns para mapear as portas do vídeo (framebuffer patching)."
                ),
            }
        )
    decisions = {d["key"]: d for d in plan.get("decisions", [])}
    wifi = decisions.get("intel-wifi-kext")
    if wifi and any(
        o["value"] == wifi.get("chosen") and o["label"].startswith("itlwm") for o in wifi.get("options", [])
    ):
        post_install.append(
            {
                "title": "Instale o HeliPort",
                "text": "Você escolheu o itlwm para o Wi-Fi Intel. Baixe o aplicativo HeliPort (github.com/OpenIntelWireless/HeliPort) "
                "para conectar às redes Wi-Fi.",
            }
        )
    if not usb_mapped:
        post_install.append(
            {
                "title": "Mapeie as portas USB",
                "text": "A EFI está com todas as portas ativas (UTBDefault). Se alguma porta não funcionar ou o USB 3 ficar lento, "
                "volte ao MacPronto no Windows antes de formatar, ou faça o mapa no macOS com o USBToolBox.",
            }
        )

    components = [c for c in laudo.get("components", []) if c["status"] != "info"]
    return {
        "app_version": __version__,
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "machine": machine,
        "verdict": laudo["verdict"],
        "difficulty": laudo.get("difficulty"),
        "macos_label": version.label if version else "macOS",
        "macos_note": version.note if version else "",
        "vendor": vendor,
        "bios_settings": settings,
        "bios_requirements": laudo.get("bios_requirements", []),
        "install_steps": install_steps,
        "post_install": post_install,
        "troubleshooting": content.TROUBLESHOOTING,
        "components": components,
        "warnings": laudo.get("warnings", []),
        "efi": efi,
        "config": config,
        "plan": plan,
        "usb_mapped": usb_mapped,
    }


def render_html(context: dict) -> str:
    return _environment().get_template("guia.html.j2").render(**context)


def find_edge() -> str | None:
    for candidate in EDGE_PATHS:
        if os.path.exists(candidate):
            return candidate
    return shutil.which("msedge")


def html_to_pdf(html_file: Path, pdf_file: Path) -> bool:
    edge = find_edge()
    if edge is None:
        log.warning("Microsoft Edge não encontrado: o guia fica só em HTML.")
        return False
    profile = paths.cache_dir() / "edge-pdf"
    command = [
        edge,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--user-data-dir={profile}",
        f"--print-to-pdf={pdf_file}",
        html_file.resolve().as_uri(),
    ]
    try:
        subprocess.run(command, capture_output=True, timeout=120, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("Falha ao gerar o PDF do guia: %s", exc)
        return False
    return pdf_file.exists() and pdf_file.stat().st_size > 0


def build(scan: dict, laudo: dict, selection: dict, efi: dict | None, usb_mapped: bool, with_pdf: bool = True) -> dict:
    folder = paths.guides_dir() / scan["id"]
    folder.mkdir(parents=True, exist_ok=True)
    context = build_context(scan, laudo, selection, efi, usb_mapped)
    html_file = folder / "Guia.html"
    html_file.write_text(render_html(context), encoding="utf-8")
    pdf_file = folder / "Guia.pdf"
    pdf_ok = html_to_pdf(html_file, pdf_file) if with_pdf else False
    log.info("Guia gerado em %s", folder)
    return {
        "folder": str(folder),
        "html": str(html_file),
        "pdf": str(pdf_file) if pdf_ok else None,
        "vendor": context["vendor"].name,
        "generated": context["generated"],
    }
