"""Gera o guia personalizado (HTML) e os PDFs (pelo Edge do Windows, em modo headless).

Além do Guia, vão para o pendrive o AJUDA-IA.md e o Bem-vindo-ao-Mac.html, cada um com o
seu PDF. Os PDFs são o que o celular baixa pelo QR code (veja share.py).
"""

from __future__ import annotations

import logging
import os
import plistlib
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup

from macpronto import __version__, paths
from macpronto.compat import macos
from macpronto.guide import content, figures

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent / "templates"
AI_HELP_FILE = "AJUDA-IA.md"
WELCOME_FILE = "Bem-vindo-ao-Mac.html"
CREATE_NO_WINDOW = 0x08000000

# O que o celular baixa: (PDF, versão sem PDF, título, descrição)
DOWNLOADS = (
    ("Guia.pdf", "Guia.html", "Passo a passo da instalação", "BIOS, instalação e pós-instalação, com as telas ilustradas."),
    ("Bem-vindo-ao-Mac.pdf", WELCOME_FILE, "Bem-vindo ao Mac", "Atalhos e diferenças para quem vem do Windows."),
    (
        "AJUDA-IA.pdf",
        AI_HELP_FILE,
        "Ajuda para IA",
        "Com dúvida, envie este arquivo para uma IA (Claude, ChatGPT, Gemini) e conte o que aconteceu.",
    ),
)

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


def machine_profile(scan: dict, laudo: dict, profile_id: str | None = None) -> tuple[content.Profile, bool]:
    """Perfil de BIOS da máquina: o escolhido à mão ou o detectado. Devolve (perfil, foi_detectado)."""
    extras = scan.get("extras") or {}
    system = extras.get("system") or {}
    bios_vendor = (extras.get("bios") or {}).get("vendor", "")
    if profile_id:
        return content.profile_by_id(profile_id, bios_vendor), False
    machine = laudo["machine"]
    profile = content.detect_profile(
        system_manufacturer=system.get("manufacturer", machine.get("manufacturer", "")),
        family=system.get("family", ""),
        model=system.get("model", ""),
        board_manufacturer=(extras.get("baseboard") or {}).get("manufacturer", ""),
        bios_vendor=bios_vendor,
        is_laptop=machine.get("form_factor") == "laptop",
    )
    return profile, True


def build_context(
    scan: dict, laudo: dict, selection: dict, efi: dict | None, usb_mapped: bool, profile_id: str | None = None
) -> dict:
    machine = laudo["machine"]
    extras = scan.get("extras") or {}
    vendor, detected = machine_profile(scan, laudo, profile_id)
    system = extras.get("system") or {}

    darwin = selection.get("darwin") or laudo["macos"].get("recommended")
    version = macos.get(darwin)
    report = scan.get("report", {})
    has_igpu = any(g.get("Device Type") == "Integrated GPU" for g in report.get("GPU", {}).values())
    vmd = any(f.get("code") == "intel-vmd" for f in laudo.get("fatal", []))

    plan = (efi or {}).get("plan") or {}
    requirements = plan.get("bios_requirements") or []
    terms = content.keywords()
    settings = [
        {
            "setting": setting,
            "path": vendor.paths.get(setting.key),
            "keywords": terms.get(setting.key, [])[:3],
            "absent": setting.key in vendor.absent and not vendor.paths.get(setting.key),
            "absent_hint": content.ABSENT_HINTS.get(setting.key, content.DEFAULT_ABSENT_HINT),
        }
        for setting in content.bios_settings(
            report.get("CPU", {}).get("Manufacturer", "Intel"), has_igpu, requirements, vmd
        )
    ]

    macos_name = f"macOS {version.name}" if version else "macOS"
    config = (efi or {}).get("config") or {}
    decisions = {d["key"]: d for d in plan.get("decisions", [])}
    wifi = decisions.get("intel-wifi-kext")
    itlwm = "itlwm.kext" in config.get("kexts", []) or bool(
        wifi
        and any(o["value"] == wifi.get("chosen") and o["label"].startswith("itlwm") for o in wifi.get("options", []))
    )
    abnt2 = (efi or {}).get("keyboard", "abnt2") == "abnt2"
    is_laptop = machine.get("form_factor") == "laptop"
    drawings = figures.build(
        bios_key=vendor.bios_key,
        boot_key=vendor.boot_key,
        macos_name=macos_name,
        macos_label=version.label if version else "macOS",
        opencore=(efi or {}).get("opencore") or "1.0.9",
        smbios_model=(config.get("smbios") or {}).get("model") or plan.get("smbios_model") or "",
        laptop=is_laptop,
        abnt2=abnt2,
        heliport_app=itlwm,
    )
    keys = {"bios_key": vendor.bios_key, "boot_key": vendor.boot_key, "macos_name": macos_name}

    def present(item: content.Step, anchor: str = "") -> dict:
        return {
            "id": anchor,
            "title": item.title,
            "text": item.text.format(**keys),
            "items": [text.format(**keys) for text in item.items],
            "figures": [drawings[name] for name in item.figures],
            "tip": item.tip.format(**keys),
            "warning": item.warning.format(**keys),
        }

    install_steps = [present(item) for item in content.INSTALL_STEPS]
    chosen = ["pendrive"]
    if plan.get("needs_oclp"):
        chosen.append("oclp")
    if itlwm:
        chosen.append("heliport")
    if abnt2:
        chosen.append("keyboard")
    if is_laptop:
        chosen.append("trackpad")
    chosen.append("usb")
    if not usb_mapped:
        chosen.append("usb_map")
    if config.get("vesa"):
        chosen.append("vesa")
    chosen += ["final_efi", "apple_id", "updates"]
    post_install = [present(content.POST_STEPS[key], key) for key in chosen]

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
        "profile_detected": detected,
        "key_table": content.key_table(),
        # Para qual máquina o pendrive e o guia foram feitos (sem números de série)
        "target": " ".join(
            part for part in (system.get("manufacturer"), system.get("family") or system.get("model")) if part
        )
        or machine["name"],
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
        "usb_ports": usb_map_ports(efi),
        "itlwm": itlwm,
        "is_laptop": is_laptop,
        "bios_figures": [drawings["keys"], drawings["bios"]],
        "keyboard_figure": drawings["pc_keyboard"],
        "printing": False,
    }


def usb_map_ports(efi: dict | None) -> list[str]:
    """Portas do UTBMap.kext da EFI, para o AJUDA-IA.md (vazio sem mapa)."""
    plist = Path((efi or {}).get("efi_dir") or "") / "OC" / "Kexts" / "UTBMap.kext" / "Contents" / "Info.plist"
    if not (efi and plist.is_file()):
        return []
    try:
        with plist.open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return []
    names = []
    for personality in (info.get("IOKitPersonalities") or {}).values():
        names += list((personality.get("IOProviderMergeProperties") or {}).get("ports") or {})
    return sorted(names)


def render_html(context: dict) -> str:
    return _environment().get_template("guia.html.j2").render(**context)


def render_welcome(context: dict) -> str:
    return _environment().get_template("boas-vindas.html.j2").render(**context)


def render_markdown(context: dict) -> str:
    """AJUDA-IA.md: o contexto da máquina e da instalação para colar numa IA (sem números de série)."""
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES)), autoescape=False, trim_blocks=True, lstrip_blocks=True
    )
    return environment.get_template("ajuda-ia.md.j2").render(**context)


def markdown_html(text: str) -> Markup:
    """Markdown em HTML para o PDF. HTML cru no texto sai escapado (o texto traz nomes vindos do hardware)."""
    return Markup(MarkdownIt("commonmark", {"html": False}).enable("table").render(text))


def render_document(title: str, body: Markup) -> str:
    return _environment().get_template("documento.html.j2").render(title=title, body=body)


def _size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB".replace(".", ",")
    return f"{max(1, size // 1024)} KB"


def render_downloads(folder: Path) -> str:
    """Página que o celular abre pelo QR code: só os botões para baixar os PDFs."""
    items = []
    for pdf, fallback, title, text in DOWNLOADS:
        for name, kind in ((pdf, "PDF"), (fallback, "página")):
            file = folder / name
            if file.is_file():
                items.append({"href": name, "title": title, "text": text, "kind": kind, "size": _size(file.stat().st_size)})
                break
    return _environment().get_template("baixar.html.j2").render(items=items, app_version=__version__)


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


def export_pdfs(folder: Path, context: dict) -> dict[str, str | None]:
    """Guia, Bem-vindo e Ajuda para IA em PDF, a partir das versões para impressão (tudo aberto, sem botões)."""
    printing = {**context, "printing": True}
    sources = {
        "pdf": ("Guia.pdf", render_html(printing)),
        "welcome_pdf": ("Bem-vindo-ao-Mac.pdf", render_welcome(printing)),
        "ai_help_pdf": (
            "AJUDA-IA.pdf",
            render_document(f"Ajuda para IA · {context['target']}", markdown_html(render_markdown(context))),
        ),
    }
    result: dict[str, str | None] = {}
    paths.cache_dir().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as temp:
        for key, (name, html) in sources.items():
            source = Path(temp) / name.replace(".pdf", ".html")
            source.write_text(html, encoding="utf-8")
            target = folder / name
            target.unlink(missing_ok=True)
            result[key] = str(target) if html_to_pdf(source, target) else None
    return result


def build(
    scan: dict,
    laudo: dict,
    selection: dict,
    efi: dict | None,
    usb_mapped: bool,
    with_pdf: bool = True,
    profile_id: str | None = None,
) -> dict:
    folder = paths.guides_dir() / scan["id"]
    folder.mkdir(parents=True, exist_ok=True)
    context = build_context(scan, laudo, selection, efi, usb_mapped, profile_id)
    html_file = folder / "Guia.html"
    html_file.write_text(render_html(context), encoding="utf-8")
    ai_file = folder / AI_HELP_FILE
    ai_file.write_text(render_markdown(context), encoding="utf-8")
    welcome_file = folder / WELCOME_FILE
    welcome_file.write_text(render_welcome(context), encoding="utf-8")
    pdfs = export_pdfs(folder, context) if with_pdf else {"pdf": None, "welcome_pdf": None, "ai_help_pdf": None}
    log.info("Guia gerado em %s", folder)
    return {
        "folder": str(folder),
        "html": str(html_file),
        "ai_help": str(ai_file),
        "welcome": str(welcome_file),
        **pdfs,
        "vendor": context["vendor"].name,
        "profile": {
            "id": context["vendor"].id,
            "name": context["vendor"].name,
            "confidence": context["vendor"].confidence,
            "detected": context["profile_detected"],
        },
        "generated": context["generated"],
    }


def export_laudo(scan: dict, laudo: dict, with_pdf: bool = True) -> dict:
    """Salva o laudo em HTML (e PDF) na pasta do diagnóstico."""
    folder = paths.scans_dir() / scan["id"]
    folder.mkdir(parents=True, exist_ok=True)
    html = (
        _environment()
        .get_template("laudo.html.j2")
        .render(
            app_version=__version__,
            generated=datetime.now().strftime("%d/%m/%Y %H:%M"),
            machine=laudo["machine"],
            verdict=laudo["verdict"],
            difficulty=laudo.get("difficulty"),
            macos=laudo["macos"],
            fatal=laudo.get("fatal", []),
            warnings=laudo.get("warnings", []),
            bios_requirements=laudo.get("bios_requirements", []),
            components=laudo.get("components", []),
        )
    )
    html_file = folder / "Laudo.html"
    html_file.write_text(html, encoding="utf-8")
    pdf_file = folder / "Laudo.pdf"
    pdf_ok = html_to_pdf(html_file, pdf_file) if with_pdf else False
    return {"html": str(html_file), "pdf": str(pdf_file) if pdf_ok else None}
