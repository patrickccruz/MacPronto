"""Monta o laudo de compatibilidade a partir da análise do OpCore Simplify.

Cada componente recebe um dos estados:
    native        funciona com a EFI padrão
    tweak         funciona com ajuste ou ressalva
    replace       não funciona, mas a peça pode ser trocada
    incompatible  não funciona e não há troca possível
    info          informativo
e a marcação ``blocking`` quando impede a instalação.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from macpronto import __version__
from macpronto.compat import knowledge, macos

STATUS_RANK = {"info": -1, "native": 0, "tweak": 1, "replace": 2, "incompatible": 3}

LATEST = macos.VERSIONS[-1].darwin
LOWEST = macos.VERSIONS[0].darwin


@dataclass
class Component:
    category: str
    name: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)
    device_id: str | None = None
    blocking: bool = False
    disabled: bool = False
    range: dict | None = None
    oclp_range: dict | None = None


def _range(compatibility) -> dict | None:
    """[max, min] do OpCore Simplify -> {"min": 17, "max": 25}."""
    if not compatibility or compatibility[0] is None:
        return None
    return {"max": macos.major(compatibility[0]), "min": macos.major(compatibility[1])}


def _range_text(version_range: dict | None) -> str:
    if not version_range:
        return "sem suporte"
    low, high = version_range["min"], version_range["max"]
    low_name = macos.get(low).name if macos.get(low) else str(low)
    high_name = macos.get(high).name if macos.get(high) else str(high)
    if low <= LOWEST and high >= LATEST:
        return "todas as versões, do High Sierra ao Tahoe"
    if low <= LOWEST:
        return f"até o macOS {high_name}"
    if high >= LATEST:
        return f"a partir do macOS {low_name}"
    return f"do macOS {low_name} ao {high_name}"


# --------------------------------------------------------------------------- componentes


def _cpu(report: dict, flags: dict) -> Component:
    cpu = report.get("CPU", {})
    name = cpu.get("Processor Name", "Processador")
    version_range = _range(cpu.get("Compatibility"))
    cores = int(cpu.get("Core Count", "0") or 0)
    details = [f"Arquitetura {cpu.get('Codename', 'desconhecida')}, {cores} núcleos."]

    if version_range is None:
        return Component(
            "cpu", name, "incompatible", "Não tem as instruções SSE4 exigidas pelo macOS.", details, blocking=True
        )

    if not flags.get("avx2"):
        details.append("Sem AVX2: do Ventura em diante o MacPronto inclui o CryptexFixup, e alguns apps exigem AVX2.")
    if flags.get("low_end"):
        details.append("Pentium e Celeron não têm aceleração de vídeo integrado no macOS.")

    if flags.get("manufacturer") == "AMD":
        details += [
            "Usa os patches de kernel AMD Vanilla, aplicados automaticamente na EFI.",
            "Não há virtualização por hypervisor (Parallels, VMware Fusion, Docker Desktop).",
            "Alguns apps, como os da Adobe, podem precisar de ajustes.",
        ]
        return Component(
            "cpu", name, "tweak", "Processador AMD: funciona com patches no kernel.", details, range=version_range
        )

    if flags.get("hybrid"):
        index = flags.get("intel_generation_index")
        details.append("Os núcleos de desempenho e de eficiência são organizados pelo CpuTopologyRebuild.")
        if index is not None and index <= 6:
            details.append("Plataforma muito recente: o suporte da comunidade ainda está amadurecendo.")
        return Component(
            "cpu", name, "tweak", "Intel híbrido (núcleos P e E): funciona com ajustes.", details, range=version_range
        )

    if flags.get("legacy"):
        details.append("Versões recentes do macOS exigem o OpenCore Legacy Patcher depois da instalação.")
        return Component(
            "cpu",
            name,
            "tweak",
            "Processador Intel antigo: funciona, com limites de versão.",
            details,
            range=version_range,
        )

    if flags.get("hedt"):
        details.append("Plataforma HEDT/Xeon: a EFI inclui correções específicas (APIC, TSC).")
        return Component(
            "cpu", name, "tweak", "Processador Intel HEDT: funciona com correções extras.", details, range=version_range
        )

    return Component("cpu", name, "native", "Processador Intel compatível.", details, range=version_range)


def _gpus(report: dict, is_laptop: bool) -> list[Component]:
    gpus = report.get("GPU", {})
    monitors = report.get("Monitor", {})
    compatible = [name for name, props in gpus.items() if _range(props.get("Compatibility"))]
    components = []

    for name, props in gpus.items():
        integrated = props.get("Device Type") == "Integrated GPU"
        manufacturer = props.get("Manufacturer", "")
        codename = props.get("Codename", "")
        version_range = _range(props.get("Compatibility"))
        oclp_range = _range(props.get("OCLP Compatibility"))
        kind = "integrado" if integrated else "dedicado"
        details = [f"Vídeo {kind} {manufacturer} ({codename or 'arquitetura desconhecida'})."]

        connected = [
            f"{monitor} ({info.get('Connector Type', '?')}, {info.get('Resolution', '?')})"
            for monitor, info in monitors.items()
            if info.get("Connected GPU") == name
        ]
        if connected:
            details.append("Monitores: " + "; ".join(connected) + ".")

        if version_range is None:
            others = [other for other in compatible if other != name]
            if others:
                component = Component(
                    "gpu",
                    name,
                    "incompatible",
                    f"Será desativado. O vídeo fica com {others[0]}.",
                    details,
                    props.get("Device ID"),
                    disabled=True,
                )
                if is_laptop and not integrated:
                    details.append(
                        "No macOS, notebooks com vídeo dedicado sem suporte (NVIDIA Optimus) usam só o integrado."
                    )
            elif is_laptop:
                component = Component(
                    "gpu",
                    name,
                    "incompatible",
                    "Vídeo sem suporte no macOS, e em notebook não há como trocar.",
                    details,
                    props.get("Device ID"),
                    blocking=True,
                )
            else:
                summary = (
                    "Vídeo integrado sem suporte. Instale uma placa de vídeo compatível."
                    if integrated
                    else "Placa de vídeo sem suporte no macOS. Troque por uma compatível."
                )
                details.append("Sugestão: " + knowledge.REPLACEMENTS["gpu-desktop"])
                component = Component("gpu", name, "replace", summary, details, props.get("Device ID"), blocking=True)
            components.append(component)
            continue

        status = "native"
        summary = f"Compatível com {_range_text(version_range)}."
        if manufacturer == "AMD" and integrated:
            status = "tweak"
            summary = "Vídeo integrado AMD: funciona com o NootedRed, com desempenho limitado."
        if codename.startswith("Navi 2"):
            details.append("Placas RDNA 2 podem usar o NootRX ou o WhateverGreen; o MacPronto escolhe o mais seguro.")
        if oclp_range and version_range["max"] < oclp_range["max"]:
            details.append(
                f"Sem patches vai até o {macos.label(version_range['max'])}; com o OpenCore Legacy Patcher, "
                f"até o {macos.label(oclp_range['max'])}."
            )
        if props.get("Resizable BAR") == "Enabled":
            details.append("Resizable BAR ativo: a EFI ajusta isso automaticamente.")
        components.append(
            Component(
                "gpu",
                name,
                status,
                summary,
                details,
                props.get("Device ID"),
                range=version_range,
                oclp_range=oclp_range,
            )
        )
    return components


def _audio(report: dict, tags: dict) -> list[Component]:
    components = []
    for name, props in report.get("Sound", {}).items():
        found = tags.get("Sound", {}).get(name, [])
        version_range = _range(props.get("Compatibility"))
        endpoints = props.get("Audio Endpoints") or []
        details = [f"Saídas: {', '.join(endpoints)}."] if endpoints else []

        if version_range is None and "Compatibility" in props:
            details.append("Sugestão: " + knowledge.REPLACEMENTS["audio"])
            components.append(
                Component(
                    "audio",
                    name,
                    "replace",
                    "Codec de áudio sem suporte no macOS.",
                    details,
                    props.get("Device ID"),
                    disabled=True,
                )
            )
            continue
        if "usb-audio" in found:
            summary = "Áudio USB: funciona sem configuração."
        elif "hdmi-audio" in found:
            summary = "Áudio pelo HDMI ou DisplayPort."
        elif "codec-supported" in found:
            summary = "Funciona com o AppleALC."
            details.append("Se não sair som depois da instalação, teste outro layout-id (o guia explica como).")
            details.append("No macOS Tahoe a Apple removeu o driver de áudio; a EFI usa o SimpleHDA para repô-lo.")
        else:
            summary = "Compatível."
        components.append(
            Component("audio", name, "native", summary, details, props.get("Device ID"), range=version_range)
        )
    return components


def _network(report: dict, tags: dict, is_laptop: bool) -> list[Component]:
    components = []
    for name, props in report.get("Network", {}).items():
        found = tags.get("Network", {}).get(name, [])
        version_range = _range(props.get("Compatibility"))
        oclp_range = _range(props.get("OCLP Compatibility"))
        device_id = props.get("Device ID")

        if "wifi" in found:
            if version_range is None:
                suggestion = knowledge.REPLACEMENTS["wifi-laptop" if is_laptop else "wifi-desktop"]
                components.append(
                    Component(
                        "wifi",
                        name,
                        "replace",
                        "Placa Wi-Fi sem suporte. Dá para trocar por uma compatível.",
                        ["Sugestão: " + suggestion],
                        device_id,
                        disabled=True,
                    )
                )
                continue
            details = []
            if "broadcom" in found:
                status, summary = "native", "Wi-Fi Broadcom: funciona com AirDrop, Handoff e demais recursos da Apple."
                if oclp_range:
                    status = "tweak"
                    details.append(
                        f"Sem patches funciona até o {macos.label(version_range['max'])}; "
                        "nas versões mais novas exige o OpenCore Legacy Patcher."
                    )
            elif "intel" in found:
                status, summary = "tweak", "Wi-Fi Intel: funciona com driver da comunidade, sem AirDrop."
                details += [
                    "Handoff e Área de Transferência Universal funcionam com o AirportItlwm.",
                    "Para ter todos os recursos da Apple, a troca por uma placa Broadcom resolve: "
                    + knowledge.REPLACEMENTS["wifi-laptop" if is_laptop else "wifi-desktop"],
                ]
            elif "atheros" in found:
                status, summary = "tweak", f"Wi-Fi Atheros: suporte limitado, {_range_text(version_range)}."
                details.append("Sem recursos de continuidade (AirDrop, Handoff).")
            elif "realtek-rtw88" in found:
                status, summary = "tweak", "Wi-Fi Realtek: driver experimental (Feixiao)."
            elif "usb" in found:
                status, summary = (
                    "tweak",
                    "Adaptador Wi-Fi USB: funciona com driver de terceiros, em versões limitadas.",
                )
            else:
                status, summary = "native", f"Wi-Fi compatível com {_range_text(version_range)}."
            components.append(
                Component("wifi", name, status, summary, details, device_id, range=version_range, oclp_range=oclp_range)
            )
            continue

        bus = props.get("Bus Type", "")
        if version_range is None:
            if not bus.startswith("PCI"):
                continue
            components.append(
                Component(
                    "ethernet",
                    name,
                    "replace",
                    "Rede cabeada sem suporte.",
                    ["Sugestão: " + knowledge.REPLACEMENTS["ethernet"]],
                    device_id,
                    disabled=True,
                )
            )
            continue
        details = []
        if version_range["min"] > LOWEST:
            details.append(f"Exige no mínimo o {macos.label(version_range['min'])}.")
        if version_range["max"] < LATEST:
            details.append(f"Funciona até o {macos.label(version_range['max'])}.")
        components.append(
            Component("ethernet", name, "native", "Rede cabeada compatível.", details, device_id, range=version_range)
        )
    return components


def _bluetooth(report: dict, tags: dict) -> list[Component]:
    components = []
    for name, props in report.get("Bluetooth", {}).items():
        found = tags.get("Bluetooth", {}).get(name, [])
        version_range = _range(props.get("Compatibility"))
        device_id = props.get("Device ID")
        if version_range is None:
            components.append(
                Component(
                    "bluetooth",
                    name,
                    "replace",
                    "Bluetooth sem suporte.",
                    ["Ao trocar a placa Wi-Fi por uma Broadcom, o Bluetooth vem junto."],
                    device_id,
                )
            )
        elif "broadcom" in found:
            components.append(
                Component(
                    "bluetooth",
                    name,
                    "native",
                    "Bluetooth Broadcom: funciona com AirDrop e Handoff.",
                    [],
                    device_id,
                    range=version_range,
                )
            )
        elif "intel" in found:
            components.append(
                Component(
                    "bluetooth",
                    name,
                    "tweak",
                    "Bluetooth Intel: funciona com fones, teclados e mouses.",
                    ["Sem AirDrop e sem Handoff."],
                    device_id,
                    range=version_range,
                )
            )
        elif "realtek" in found:
            components.append(
                Component(
                    "bluetooth",
                    name,
                    "tweak",
                    "Bluetooth Realtek: funciona com firmware da comunidade.",
                    [],
                    device_id,
                    range=version_range,
                )
            )
        else:
            components.append(
                Component("bluetooth", name, "native", "Bluetooth compatível.", [], device_id, range=version_range)
            )
    return components


def _storage(report: dict, extras: dict) -> list[Component]:
    components = []
    for name, props in report.get("Storage Controllers", {}).items():
        if "Compatibility" not in props:
            continue
        version_range = _range(props.get("Compatibility"))
        disks = props.get("Disk Drives") or []
        details = [f"Disco: {disk}." for disk in disks]
        nvme = "NVMe" in name or "NVM Express" in name or "SSD" in name
        if version_range is None:
            details.append("Sugestão: " + knowledge.REPLACEMENTS["ssd"])
            components.append(
                Component("storage", name, "replace", "SSD sem suporte no macOS.", details, props.get("Device ID"))
            )
            continue
        summary = "SSD NVMe compatível." if nvme else "Controladora de disco compatível."
        if version_range["min"] > LOWEST:
            details.append(f"Exige no mínimo o {macos.label(version_range['min'])}.")
        components.append(
            Component("storage", name, "native", summary, details, props.get("Device ID"), range=version_range)
        )

    if components and all(c.status == "replace" for c in components):
        for component in components:
            component.blocking = True

    for disk in extras.get("disks", []):
        if disk.get("bus") == "USB":
            continue
        role = " Contém o Windows atual." if disk.get("system") else ""
        status = "info"
        summary = f"{disk.get('size_gb', '?')} GB, {disk.get('bus')}, {disk.get('media')}.{role}"
        details = []
        if disk.get("bus") == "RAID":
            status = "tweak"
            details.append("O disco está em modo RAID/RST. Mude o SATA para AHCI na BIOS antes de instalar.")
        if disk.get("media") == "HDD":
            details.append("HD mecânico: o macOS funciona, mas fica bem mais lento que num SSD.")
        components.append(Component("disk", disk.get("model") or "Disco", status, summary, details))
    return components


def _usb(report: dict, plan: dict | None) -> list[Component]:
    checked = {k["name"] for k in (plan or {}).get("kexts", []) if k.get("checked")}
    components = []
    for name, props in report.get("USB Controllers", {}).items():
        details = ["O macOS aceita no máximo 15 portas por controladora; o mapeamento USB do MacPronto resolve isso."]
        status, summary = "native", "Controladora USB compatível."
        if checked & {"XHCI-unsupported", "GenericUSBXHCI"}:
            status, summary = "tweak", "Controladora USB que precisa de kext extra (incluído na EFI)."
        components.append(Component("usb", name, status, summary, details, props.get("Device ID")))
    return components


def _input(report: dict) -> list[Component]:
    components = []
    for name, props in report.get("Input", {}).items():
        device_type = props.get("Device Type", "")
        if "PS/2" in device_type:
            components.append(
                Component(
                    "input",
                    name,
                    "native",
                    "Teclado ou touchpad PS/2: funciona com o VoodooPS2.",
                    [],
                    props.get("Device"),
                )
            )
        elif "I2C" in device_type:
            components.append(
                Component(
                    "input",
                    name,
                    "tweak",
                    "Touchpad I2C: funciona com o VoodooI2C.",
                    ["Alguns modelos precisam de ajuste fino depois da instalação."],
                    props.get("Device"),
                )
            )
    return components


def _others(report: dict) -> list[Component]:
    components = []
    for name, props in report.get("Biometric", {}).items():
        components.append(
            Component(
                "biometric",
                name,
                "incompatible",
                "Leitor de digital: nunca funciona em Hackintosh.",
                ["O Touch ID exige o chip de segurança dos Macs (T2 ou Apple Silicon)."],
                props.get("Device ID"),
            )
        )
    for name, props in report.get("SD Controller", {}).items():
        if _range(props.get("Compatibility")):
            components.append(
                Component(
                    "sdcard",
                    name,
                    "tweak",
                    "Leitor de cartão Realtek: funciona com kext da comunidade.",
                    [],
                    props.get("Device ID"),
                )
            )
        else:
            components.append(
                Component(
                    "sdcard",
                    name,
                    "incompatible",
                    "Leitor de cartão sem suporte. Será desativado.",
                    [],
                    props.get("Device ID"),
                    disabled=True,
                )
            )
    return components


def _firmware(report: dict) -> Component:
    bios = report.get("BIOS", {})
    details = [f"Versão {bios.get('Version', '?')} ({bios.get('Release Date', '?')})."]
    if bios.get("Secure Boot") == "Enabled":
        details.append("O Secure Boot está ligado: desative-o antes de instalar.")
    if bios.get("Firmware Type") != "UEFI":
        details.append("Se a placa tiver modo UEFI, ative-o: o OpenCore funciona melhor assim.")
        return Component("firmware", "BIOS", "tweak", "BIOS em modo Legacy.", details)
    return Component("firmware", "BIOS", "native", "Firmware UEFI.", details)


# --------------------------------------------------------------------------- veredito


def _verdict(components: list[Component], fatal: list[dict], recommended: int | None) -> dict:
    kinds = {knowledge.FATAL.get(item["code"], {}).get("kind", "incompatible") for item in fatal}
    blocking = [c for c in components if c.blocking]

    if (
        "incompatible" in kinds
        or any(c.status == "incompatible" for c in blocking)
        or (recommended is None and not kinds)
    ):
        status = "incompatible"
        headline = "Este computador não pode rodar o macOS."
    elif "replace" in kinds or any(c.status == "replace" for c in blocking):
        status = "needs-hardware"
        headline = "Só é possível trocando peças."
    elif "bios" in kinds:
        status = "needs-bios"
        headline = "Possível, depois de um ajuste na BIOS."
    elif any(c.status in ("tweak", "replace", "incompatible") for c in components):
        status = "caveats"
        headline = "Pode virar um Hackintosh, com ressalvas."
    else:
        status = "compatible"
        headline = "Pode virar um Hackintosh."

    caveats = [c for c in components if c.status in ("tweak", "replace", "incompatible") and not c.blocking]
    if status in ("compatible", "caveats") and recommended:
        summary = f"Versão recomendada: {macos.label(recommended)}."
        if len(caveats) == 1:
            summary += " 1 item com ressalva abaixo."
        elif caveats:
            summary += f" {len(caveats)} itens com ressalvas abaixo."
    elif status == "needs-bios":
        summary = "Corrija o item da BIOS indicado e refaça o diagnóstico."
    elif status == "needs-hardware":
        summary = "Veja abaixo quais peças trocar e as sugestões de modelos compatíveis."
    else:
        summary = "Veja abaixo o motivo."
    return {"status": status, "headline": headline, "summary": summary}


def _difficulty(
    components: list[Component], is_laptop: bool, flags: dict, plan: dict | None, report: dict, has_network: bool
) -> dict:
    score = 1
    reasons = []

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append(reason)

    if is_laptop:
        add(1, "Notebooks exigem mais ajustes: bateria, brilho, touchpad e teclas.")
    if flags.get("manufacturer") == "AMD":
        add(1, "Processador AMD depende de patches no kernel.")
    if flags.get("hybrid"):
        add(1, "Intel de 12ª geração em diante exige ajustes nos núcleos.")
    if flags.get("legacy"):
        add(1, "Processador antigo: versões recentes exigem patches pós-instalação.")
    if plan and plan.get("needs_oclp"):
        add(1, "A versão escolhida exige o OpenCore Legacy Patcher depois de instalar.")
    if any(c.category == "input" and c.status == "tweak" for c in components):
        add(1, "Touchpad I2C costuma exigir ajustes.")
    if report.get("BIOS", {}).get("Firmware Type") != "UEFI":
        add(1, "BIOS em modo Legacy.")
    if not has_network:
        add(1, "Sem rede cabeada compatível, a instalação (que baixa o macOS) fica mais difícil.")

    score = max(1, min(5, score))
    if not reasons:
        reasons.append("Hardware muito parecido com o de Macs reais.")
    return {"score": score, "label": knowledge.DIFFICULTY_LABELS[score], "reasons": reasons}


def _versions(native: dict | None, oclp: dict | None, recommended: int | None) -> list[dict]:
    items = []
    for version in macos.VERSIONS:
        if version.darwin == recommended:
            status = "recommended"
        elif macos.in_range(version.darwin, native):
            status = "supported"
        elif macos.in_range(version.darwin, oclp):
            status = "oclp"
        else:
            status = "unsupported"
        items.append({**version.to_dict(), "status": status})
    return items


def _installed_ram(extras: dict) -> float | None:
    """Soma dos módulos instalados; o total do Windows desconta a memória reservada ao vídeo."""
    memory = extras.get("memory", {})
    modules = sum(m.get("capacity_gb", 0) for m in memory.get("modules", []))
    return round(modules, 1) if modules else memory.get("total_gb")


def _machine(report: dict, extras: dict, is_laptop: bool) -> dict:
    system = extras.get("system", {})
    form = system.get("form_factor") or ("laptop" if is_laptop else "desktop")
    cpu = report.get("CPU", {})
    return {
        "name": report.get("Motherboard", {}).get("Name", "Computador"),
        "form_factor": form,
        "form_label": {"laptop": "Notebook", "mini": "Mini PC", "desktop": "Desktop"}.get(form, "Desktop"),
        "manufacturer": system.get("manufacturer", ""),
        "model": system.get("model", ""),
        "board": " ".join(
            filter(None, [extras.get("baseboard", {}).get("manufacturer"), extras.get("baseboard", {}).get("product")])
        ),
        "chipset": report.get("Motherboard", {}).get("Chipset", ""),
        "cpu": cpu.get("Processor Name", ""),
        "cpu_codename": cpu.get("Codename", ""),
        "gpus": list(report.get("GPU", {}).keys()),
        "ram_gb": _installed_ram(extras),
        "firmware": report.get("BIOS", {}).get("Firmware Type", ""),
        "secure_boot": report.get("BIOS", {}).get("Secure Boot", ""),
        "bios_vendor": extras.get("bios", {}).get("vendor", ""),
        "os": extras.get("os", {}).get("caption", ""),
        "virtual_machine": bool(system.get("is_virtual_machine")),
    }


def _plan_section(plan: dict | None) -> dict | None:
    if not plan:
        return None
    return {
        "macos": macos.major(plan["macos_version"]),
        "smbios": plan["smbios_model"],
        "needs_oclp": plan["needs_oclp"],
        "kexts": [
            {"name": k["name"], "description": knowledge.kext_description(k["name"], k["description"])}
            for k in plan["kexts"]
            if k["checked"]
        ],
        "acpi_patches": [
            {"name": p["name"], "description": knowledge.acpi_description(p["name"], p["description"])}
            for p in plan["acpi_patches"]
            if p["checked"]
        ],
        "disabled_devices": plan["disabled_devices"],
        "decisions": plan["decisions"],
    }


def build(scan: dict, analysis: dict, plan: dict | None = None) -> dict:
    """Gera o laudo. ``scan`` é Scan.to_dict(); ``plan`` é o plano para a versão recomendada."""
    report = analysis["report"]
    extras = scan.get("extras") or {}
    tags = analysis.get("tags") or {}
    flags = analysis.get("cpu") or {}
    is_laptop = (
        report.get("Motherboard", {}).get("Platform") == "Laptop"
        or extras.get("system", {}).get("form_factor") == "laptop"
    )

    recommended, reason = macos.recommend(analysis.get("native"), analysis.get("suggested"))

    components: list[Component] = [_cpu(report, flags)]
    components += _gpus(report, is_laptop)
    components += _audio(report, tags)
    components += _network(report, tags, is_laptop)
    components += _bluetooth(report, tags)
    components += _storage(report, extras)
    components += _usb(report, plan)
    if is_laptop:
        components += _input(report)
    components += _others(report)
    components.append(_firmware(report))

    disabled_names = {d["name"] for d in (plan or {}).get("disabled_devices", [])}
    for component in components:
        if component.name in disabled_names:
            component.disabled = True

    fatal = []
    for item in analysis.get("fatal", []):
        info = knowledge.FATAL.get(
            item["code"], {"kind": "incompatible", "title": "Impedimento", "message": item.get("message", "")}
        )
        fatal.append({"code": item["code"], **info, "original": item.get("message", "")})

    has_network = any(c.category == "ethernet" and c.status == "native" for c in components)
    warnings = []
    if extras.get("system", {}).get("is_virtual_machine"):
        warnings.append("O diagnóstico foi feito numa máquina virtual: o laudo não representa um computador real.")
    ram = _installed_ram(extras)
    if ram and ram < 8:
        warnings.append(
            f"O computador tem {ram} GB de RAM. O macOS funciona com 4 GB, mas o recomendado é 8 GB ou mais."
        )
    if not has_network:
        warnings.append(
            "Não há rede cabeada compatível. O instalador baixa o macOS pela internet: use um adaptador USB-Ethernet "
            "RTL8153 ou a ancoragem USB de um celular Android durante a instalação."
        )
    if not scan.get("acpi_tables"):
        warnings.append(
            "Este diagnóstico não tem as tabelas ACPI: o laudo está completo, mas a EFI só pode ser montada "
            "com um diagnóstico feito no próprio computador."
        )

    plan_section = _plan_section(plan)
    bios_requirements = [knowledge.bios_requirement(req) for req in (plan or {}).get("bios_requirements", [])]
    verdict = _verdict(components, fatal, recommended)
    difficulty = (
        None
        if verdict["status"] == "incompatible"
        else _difficulty(components, is_laptop, flags, plan, report, has_network)
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "app_version": __version__,
        "scan_id": scan.get("id"),
        "source": scan.get("source", "local"),
        "machine": _machine(report, extras, is_laptop),
        "verdict": verdict,
        "difficulty": difficulty,
        "macos": {
            "recommended": recommended,
            "recommended_label": macos.label(recommended) if recommended else None,
            "reason": reason,
            "native": analysis.get("native"),
            "oclp": analysis.get("oclp"),
            "maximum": max(
                (
                    v["darwin"]
                    for v in _versions(analysis.get("native"), analysis.get("oclp"), recommended)
                    if v["status"] != "unsupported"
                ),
                default=None,
            ),
            "versions": _versions(analysis.get("native"), analysis.get("oclp"), recommended),
        },
        "components": [asdict(c) for c in components],
        "fatal": fatal,
        "bios_requirements": bios_requirements,
        "warnings": warnings,
        "efi_plan": plan_section,
    }
