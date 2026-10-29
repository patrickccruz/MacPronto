"""Ilustrações do guia: telas montadas em SVG, com o caminho marcado em vermelho.

Não são capturas de tela: são desenhos das telas que a pessoa vai encontrar (BIOS, menu
de boot, OpenCore, Recuperação, Utilitário de Disco, Finder, Terminal, Ajustes do
Sistema), personalizados com as teclas, o macOS e os arquivos desta máquina. Saem iguais
no HTML, no PDF e no celular. Os círculos vermelhos numerados correspondem às notas da
figura, na mesma ordem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from markupsafe import Markup, escape

WIDTH = 640
SANS = "'Segoe UI', -apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "Consolas, Menlo, 'Courier New', monospace"
MARK = "#e5484d"
INK = "#1d1d1f"
SOFT = "#6e6e73"
LINE = "#d2d2d7"
BLUE = "#0a64d8"
PANEL = "#f2f2f7"
DESKTOP = "#8197b8"
BIOS_BG, BIOS_BAR, BIOS_TEXT = "#0f2350", "#1a3d8f", "#dfe6f3"
CHAR = 0.55  # largura de um caractere da fonte monoespaçada, em fração do tamanho

KEY_NAME = re.compile(r"^(F\d{1,2}|Del|Esc|Enter)$")


@dataclass(frozen=True)
class Figure:
    svg: Markup
    caption: str
    notes: tuple[str, ...] = ()


# ------------------------------------------------------------------ peças


def _svg(height: int, label: str, parts: list[str]) -> Markup:
    return Markup(
        f'<svg class="shot" viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{escape(label)}" font-family="{SANS}">{"".join(parts)}</svg>'
    )


def _rect(x, y, w, h, fill="none", r=0, stroke=None, width=1.0, opacity=None) -> str:
    extra = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
    if opacity is not None:
        extra += f' opacity="{opacity}"'
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{extra}/>'


def _text(x, y, value, size=13.0, fill=INK, weight=400, anchor="start", mono=False, opacity=None) -> str:
    extra = f' font-family="{MONO}"' if mono else ""
    if opacity is not None:
        extra += f' opacity="{opacity}"'
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"'
        f'{extra} style="white-space:pre">{escape(value)}</text>'
    )


def _line(x1, y1, x2, y2, stroke=LINE, width=1.0) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{width}"/>'


def _mark(x, y, w, h) -> str:
    """Contorno vermelho em volta do que a pessoa deve escolher."""
    return _rect(x, y, w, h, r=7, stroke=MARK, width=2.5)


def _badge(number: int, x, y) -> str:
    return f'<circle cx="{x}" cy="{y}" r="11" fill="{MARK}" stroke="#fff" stroke-width="2"/>' + _text(
        x, y + 4.5, str(number), size=12.5, fill="#fff", weight=700, anchor="middle"
    )


def _mono_width(text: str, size: float) -> float:
    return len(text) * size * CHAR


def _window(x, y, w, h, title="", sidebar=0, bar=28) -> list[str]:
    """Janela do macOS: barra de título com os três botões e, se pedir, a barra lateral."""
    parts = [_rect(x, y, w, h, "#ffffff", 10)]
    if sidebar:
        parts.append(
            f'<path d="M{x} {y + bar} h{sidebar} v{h - bar} h{-(sidebar - 10)} a10 10 0 0 1 -10 -10 z" fill="{PANEL}"/>'
        )
        parts.append(_line(x + sidebar, y + bar, x + sidebar, y + h))
    parts.append(
        f'<path d="M{x} {y + bar} v{-(bar - 10)} a10 10 0 0 1 10 -10 h{w - 20} a10 10 0 0 1 10 10 v{bar - 10} z" '
        'fill="#ececef"/>'
    )
    parts.append(_line(x, y + bar, x + w, y + bar))
    for index, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        parts.append(f'<circle cx="{x + 16 + index * 18}" cy="{y + bar / 2}" r="6" fill="{color}"/>')
    if title:
        parts.append(_text(x + w / 2, y + bar / 2 + 4.5, title, size=12.5, fill=SOFT, weight=600, anchor="middle"))
    parts.append(_rect(x, y, w, h, r=10, stroke="#c7c7cc"))
    return parts


def _menu_bar(items: tuple[str, ...], height=300) -> list[str]:
    """Fundo da tela com a barra de menus do macOS no alto."""
    parts = [_rect(0, 0, WIDTH, height, DESKTOP, 8), _rect(0, 0, WIDTH, 24, "#f5f5f7", 8), _rect(0, 16, WIDTH, 8, "#f5f5f7")]
    x = 18
    for index, item in enumerate(items):
        parts.append(_text(x, 17, item, size=12.5, weight=700 if index == 0 else 400))
        x += len(item) * 6.8 + 20
    return parts


def _key(x, y, label, w=46, h=40, size=15.0, opacity=None) -> list[str]:
    return [
        _rect(x, y + 3, w, h, "#c9ccd3", 7, opacity=opacity),
        _rect(x, y, w, h, "#ffffff", 7, "#b9bcc4", 1.2, opacity),
        _text(x + w / 2, y + h / 2 + size * 0.35, label, size=size, weight=600, anchor="middle", opacity=opacity),
    ]


def _arrow(x1, y, x2, color=SOFT) -> str:
    return _line(x1, y, x2 - 7, y, color, 2) + f'<path d="M{x2} {y} l-9 -5 v10 z" fill="{color}"/>'


def _button(x, y, w, label, primary=False, h=22) -> list[str]:
    fill, color = (BLUE, "#ffffff") if primary else ("#ffffff", INK)
    return [
        _rect(x, y, w, h, fill, 6, None if primary else "#c7c7cc"),
        _text(x + w / 2, y + h / 2 + 4.5, label, size=12, fill=color, weight=500, anchor="middle"),
    ]


def _toggle(x, y, on: bool) -> list[str]:
    knob = x + 26 if on else x + 10
    return [_rect(x, y, 36, 20, "#34c759" if on else "#d1d1d6", 10), f'<circle cx="{knob}" cy="{y + 10}" r="8" fill="#fff"/>']


def _slider(x, y, w, value=0.6) -> list[str]:
    return [_rect(x, y - 2, w, 4, "#d1d1d6", 2), _rect(x, y - 2, w * value, 4, BLUE, 2),
            f'<circle cx="{x + w * value}" cy="{y}" r="8" fill="#fff" stroke="#c7c7cc"/>']


def _popup(x, y, w, label) -> list[str]:
    return [_rect(x, y - 15, w, 22, "#ffffff", 5, "#c7c7cc"), _text(x + 10, y, label, size=12),
            _text(x + w - 10, y, "▾", size=12, fill=SOFT, anchor="end")]


def _folder(x, y) -> str:
    return (
        f'<path d="M{x} {y + 3} a2 2 0 0 1 2 -2 h5 l2 2 h7 a2 2 0 0 1 2 2 v9 a2 2 0 0 1 -2 2 h-14 '
        f'a2 2 0 0 1 -2 -2 z" fill="#5ea8f0"/>'
    )


def _file(x, y, kind="doc") -> str:
    if kind == "folder":
        return _folder(x, y)
    fill = {"dmg": "#d8dbe2", "pdf": "#f3d3d1"}.get(kind, "#ffffff")
    return _rect(x + 3, y, 13, 16, fill, 2, "#a1a1a6")


def _eject(x, y) -> str:
    return f'<path d="M{x} {y + 6} l5 -6 l5 6 z M{x} {y + 8} h10 v2 h-10 z" fill="{SOFT}"/>'


def _wifi(cx, cy, color=INK) -> str:
    arcs = "".join(
        f'<path d="M{cx - r * 0.72} {cy - r * 0.7} A{r} {r} 0 0 1 {cx + r * 0.72} {cy - r * 0.7}" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>'
        for r in (4.5, 8.5, 12.5)
    )
    return arcs + f'<circle cx="{cx}" cy="{cy - 1}" r="1.7" fill="{color}"/>'


def _power(cx, cy) -> list[str]:
    return [
        f'<circle cx="{cx}" cy="{cy}" r="20" fill="#ffffff" stroke="#b9bcc4"/>',
        f'<path d="M{cx - 6.4} {cy - 6.4} A9 9 0 1 0 {cx + 6.4} {cy - 6.4}" fill="none" stroke="{INK}" '
        'stroke-width="2.2" stroke-linecap="round"/>',
        f'<path d="M{cx} {cy - 11} V{cy - 1}" stroke="{INK}" stroke-width="2.2" stroke-linecap="round"/>',
    ]


def _settings_window(selected: str, title: str) -> list[str]:
    """Ajustes do Sistema, com a barra lateral e o painel escolhido."""
    parts = _window(10, 10, 620, 282, sidebar=180)
    parts += [_rect(22, 44, 156, 22, "#e3e3e8", 6), _text(34, 59, "Buscar", size=11.5, fill=SOFT)]
    colors = ("#0a84ff", "#0a84ff", "#0a84ff", "#ff3b30", "#ff2d55", "#8e8e93", "#0a84ff", "#8e8e93", "#8e8e93")
    items = ("Wi-Fi", "Bluetooth", "Rede", "Notificações", "Som", "Geral", "Tela", "Teclado", "Trackpad")
    for index, (item, color) in enumerate(zip(items, colors, strict=True)):
        y = 92 + index * 22
        if item == selected:
            parts.append(_rect(16, y - 15, 168, 21, BLUE, 6))
        parts.append(_rect(24, y - 11, 13, 13, color, 3))
        parts.append(_text(44, y, item, size=12.5, fill="#ffffff" if item == selected else INK))
    parts.append(_text(206, 29, title, size=14, weight=700))
    return parts


def key_names(text: str) -> list[str]:
    """Teclas citadas no texto do perfil de BIOS: "Del ou F2 (às vezes F1)" vira ["Del", "F2"]."""
    plain = re.sub(r"\([^)]*\)", " ", text)
    names = [part.strip() for part in re.split(r",| ou ", plain)]
    return [name for name in names if KEY_NAME.match(name)][:2]


def mac_name(smbios_model: str) -> str:
    """Nome comercial do Mac simulado: MacBookPro16,3 vira MacBook Pro."""
    for prefix, name in (
        ("MacBookPro", "MacBook Pro"),
        ("MacBookAir", "MacBook Air"),
        ("MacBook", "MacBook"),
        ("iMacPro", "iMac Pro"),
        ("iMac", "iMac"),
        ("Macmini", "Mac mini"),
        ("MacPro", "Mac Pro"),
    ):
        if smbios_model.startswith(prefix):
            return name
    return "Mac"


# ------------------------------------------------------------------ BIOS e boot


def power_keys(bios_key: str, boot_key: str) -> Figure:
    parts = [_rect(0, 0, WIDTH, 168, "#f6f7fa", 8)]
    for label, keys, top in (("Entrar na BIOS", bios_key, 18), ("Menu de boot (escolher o pendrive)", boot_key, 96)):
        names = key_names(keys) or [keys.split()[0]]
        parts += _power(40, top + 20)
        parts.append(_text(40, top + 56, "ligar", size=11, fill=SOFT, anchor="middle"))
        parts.append(_arrow(68, top + 20, 104))
        width = max(46, 10 * len(names[0]) + 24)
        x = 116
        for opacity in (1, 0.7, 0.45):
            parts += _key(x, top, names[0], w=width, opacity=opacity)
            x += width + 10
        parts.append(_text(x + 10, top + 17, label, size=14, weight=600))
        hint = "aperte várias vezes, logo depois de ligar"
        if len(names) > 1:
            hint += f" (ou {names[1]})"
        parts.append(_text(x + 10, top + 37, hint, size=12, fill=SOFT))
    return Figure(
        _svg(168, "Ligar o computador e apertar a tecla várias vezes", parts),
        f"Entrar na BIOS: {bios_key}. Menu de boot: {boot_key}.",
    )


def bios_screen() -> Figure:
    parts = [_rect(0, 0, WIDTH, 306, BIOS_BG, 8), _rect(0, 0, WIDTH, 26, BIOS_BAR, 8), _rect(0, 18, WIDTH, 8, BIOS_BAR)]
    parts.append(_text(WIDTH / 2, 18, "Setup Utility", size=12, fill="#ffffff", anchor="middle", mono=True))
    for name, x in (("Main", 22), ("Advanced", 82), ("Boot", 170), ("Security", 228), ("Save & Exit", 318)):
        selected = name == "Security"
        if selected:
            parts.append(_rect(x - 6, 32, _mono_width(name, 13) + 12, 20, BIOS_TEXT, 3))
        parts.append(_text(x, 47, name, fill=BIOS_BG if selected else BIOS_TEXT, mono=True))
    parts += [_line(0, 58, WIDTH, 58, "#3b5aa8"), _line(424, 58, 424, 264, "#3b5aa8")]
    rows = (
        ("Secure Boot", "[Enabled]"),
        ("Fast Boot", "[Enabled]"),
        ("CSM Support", "[Disabled]"),
        ("SATA Mode", "[AHCI]"),
        ("Above 4G Decoding", "[Enabled]"),
    )
    for index, (name, value) in enumerate(rows):
        y = 86 + index * 30
        if index == 0:
            parts.append(_rect(14, y - 17, 400, 24, "#2f6fe4", 3))
        parts.append(_text(24, y, name, fill="#ffffff" if index == 0 else BIOS_TEXT, mono=True))
        parts.append(_text(270, y, value, fill="#ffffff" if index == 0 else "#ffd866", mono=True))
    # Opções abertas com Enter
    parts += [_rect(236, 102, 170, 92, BIOS_TEXT, 4, "#ffffff", 2)]
    parts.append(_text(321, 122, "Secure Boot", size=12, fill=BIOS_BG, weight=700, anchor="middle", mono=True))
    parts.append(_text(321, 148, "Enabled", fill=BIOS_BG, anchor="middle", mono=True))
    parts += [_rect(248, 158, 146, 22, "#2f6fe4", 3), _text(321, 174, "Disabled", fill="#ffffff", anchor="middle", mono=True)]
    for index, line in enumerate(("Item Specific Help", "", "Enable or disable", "Secure Boot.")):
        parts.append(_text(438, 82 + index * 18, line, size=12, fill="#9fb3d9", mono=True))
    parts += [_rect(0, 264, WIDTH, 42, BIOS_BAR, 8), _rect(0, 264, WIDTH, 8, BIOS_BAR)]
    parts.append(_text(16, 281, "↑↓ Select Item    Enter Select    F9 Setup Defaults", size=12, fill="#ffffff", mono=True))
    parts.append(_text(16, 298, "Esc Exit    F10 Save and Exit", size=12, fill="#ffffff", mono=True))
    f10 = 16 + _mono_width("Esc Exit    ", 12)
    f10_end = f10 + _mono_width("F10 Save and Exit", 12) + 5
    parts += [
        _mark(10, 65, 408, 32),
        _badge(1, 418, 65),
        _mark(244, 154, 154, 30),
        _badge(2, 398, 154),
        _mark(f10 - 5, 285, f10_end - f10 + 5, 19),
        _badge(3, f10_end + 18, 294),
    ]
    return Figure(
        _svg(306, "Ilustração de uma BIOS com o Secure Boot sendo desligado", parts),
        "Ilustração de uma BIOS desligando o Secure Boot. A sua tem outro visual, mas funciona do mesmo jeito: setas, "
        "Enter e F10.",
        (
            "Com as setas do teclado, vá até o ajuste. O nome e a aba mudam de marca para marca: veja a tabela abaixo.",
            "Enter abre as opções. Escolha a certa (aqui, Disabled) e confirme com Enter.",
            "Depois de todos os ajustes, F10 salva e reinicia. Confirme com Yes ou Enter.",
        ),
    )


def boot_menu(boot_key: str) -> Figure:
    box_x, box_w = 100, 440
    parts = [_rect(0, 0, WIDTH, 226, "#0b0b0f", 8), _rect(box_x, 20, box_w, 186, "#e9ecf2", 4, "#9aa3b5")]
    parts += [_rect(box_x, 20, box_w, 26, BIOS_BAR, 4), _rect(box_x, 38, box_w, 8, BIOS_BAR)]
    parts.append(_text(WIDTH / 2, 38, "Boot Menu", fill="#ffffff", anchor="middle", mono=True))
    parts.append(_text(box_x + 18, 72, "Please select boot device:", size=12, mono=True))
    items = ("Windows Boot Manager (NVMe SSD)", "UEFI: SanDisk Cruzer Blade, Partition 1", "Enter Setup")
    for index, item in enumerate(items):
        y = 102 + index * 28
        if index == 1:
            parts.append(_rect(box_x + 10, y - 17, box_w - 20, 24, BIOS_BAR, 3))
        parts.append(_text(box_x + 18, y, item, fill="#ffffff" if index == 1 else INK, mono=True))
    parts.append(_text(box_x + 18, 194, "↑↓ move    Enter select", size=11, fill=SOFT, mono=True))
    parts += [_mark(box_x + 5, 109, box_w - 10, 32), _badge(1, box_x + box_w - 5, 109)]
    names = key_names(boot_key) or [boot_key]
    return Figure(
        _svg(226, "Menu de boot com o pendrive selecionado", parts),
        f"Menu de boot ({names[0]} logo depois de ligar). Os nomes mudam conforme o computador e o pendrive.",
        ("Escolha a opção que começa com UEFI e tem a marca do pendrive (SanDisk, Kingston…). Aperte Enter.",),
    )


def _picker(entries: tuple[str, ...], selected: int, version: str) -> list[str]:
    parts = [_rect(0, 0, WIDTH, 178, "#000000", 8), _text(24, 34, f"OpenCore {version}", fill="#c8c8c8", mono=True)]
    for index, entry in enumerate(entries):
        y = 80 + index * 28
        label = f"{index + 1}. {entry}"
        if index == selected:
            parts.append(_rect(18, y - 18, _mono_width(label, 13) + 14, 25, "#c8c8c8"))
        parts.append(_text(24, y, label, fill="#000000" if index == selected else "#c8c8c8", mono=True))
    top = 80 + selected * 28 - 22
    width = _mono_width(f"{selected + 1}. {entries[selected]}", 13) + 22
    parts += [_mark(14, top, width, 33), _badge(1, 14 + width, top)]
    return parts


def opencore_install(version: str) -> Figure:
    entries = ("Windows", "macOS Base System (dmg)", "Reset NVRAM")
    return Figure(
        _svg(178, "Menu do OpenCore com o instalador do macOS selecionado", _picker(entries, 1, version)),
        "O menu do OpenCore (ilustração; as opções mudam um pouco de máquina para máquina).",
        ('Com as setas, escolha "macOS Base System" (ou "Install macOS") e aperte Enter.',),
    )


def opencore_reboot(version: str) -> Figure:
    entries = ("macOS Installer", "macOS Base System (dmg)", "Reset NVRAM")
    return Figure(
        _svg(178, "Menu do OpenCore com o macOS Installer selecionado", _picker(entries, 0, version)),
        "O menu do OpenCore nas reinicializações da instalação.",
        ('Escolha "macOS Installer". Quando ele sumir, escolha o nome do disco (Macintosh HD).',),
    )


def verbose() -> Figure:
    lines = (
        "[EB|#LOG:EXITBS:START]",
        "IOAPIC: Version 0x20 Vectors 64:87",
        "ACPI: sleep states S3 S4 S5",
        "pci (build 14:22:05 Sep 18 2026), flags 0x63008, pfm64 (39 cpu) 0x7f80000000, 0x80000000",
        "AppleACPICPU: ProcessorId=1 LocalApicId=0 Enabled",
        "Lilu: kern_start @ patching kernel...",
        "apfs_module_start:2581: load: com.apple.filesystems.apfs",
        "AppleIntelCPUPowerManagement: Turbo Ratios 2234",
        "IOThunderboltSwitch: Waiting for link... █",
    )
    parts = [_rect(0, 0, WIDTH, 168, "#000000", 8)]
    for index, line in enumerate(lines):
        last = index == len(lines) - 1
        parts.append(_text(16, 24 + index * 16, line, size=10.5, fill="#ffffff" if last else "#a8a8a8", mono=True))
    return Figure(
        _svg(168, "Linhas de texto do modo detalhado durante o boot", parts),
        "Depois do OpenCore, passam muitas linhas de texto por alguns minutos: é normal (modo detalhado). Se a tela "
        "parar na mesma linha por mais de 5 minutos, tire uma foto das últimas linhas.",
    )


# ------------------------------------------------------------------ instalação


def recovery(macos_name: str) -> Figure:
    parts = _menu_bar(("Recuperação", "Arquivo", "Editar", "Utilitários", "Janela"))
    parts += _window(150, 40, 340, 248)
    options = (
        ("Restaurar do Time Machine", "#6b6b70"),
        (f"Reinstalar o {macos_name}", "#2f6fe4"),
        ("Safari", "#1e8ef0"),
        ("Utilitário de Disco", "#8e8e93"),
    )
    for index, (label, color) in enumerate(options):
        y = 96 + index * 42
        selected = index == 3
        if selected:
            parts.append(_rect(162, y - 18, 316, 38, BLUE, 7))
        parts.append(_rect(174, y - 13, 28, 28, color, 7))
        parts.append(f'<circle cx="188" cy="{y + 1}" r="7" fill="none" stroke="#fff" stroke-width="2"/>')
        parts.append(_text(214, y + 5, label, size=13.5, fill="#ffffff" if selected else INK, weight=500))
    parts += _button(396, 256, 82, "Continuar", primary=True)
    parts += [_mark(158, 200, 324, 46), _badge(1, 482, 200), _mark(158, 116, 324, 46), _badge(2, 482, 116)]
    return Figure(
        _svg(300, "Tela de Recuperação do macOS", parts),
        "A tela de Recuperação do macOS. Se precisar do Terminal, ele fica no menu Utilitários.",
        (
            "Primeiro: Utilitário de Disco e Continuar, para apagar o disco.",
            f"Depois de apagar, feche o Utilitário de Disco (Command + Q) e escolha Reinstalar o {macos_name}.",
        ),
    )


def disk_utility() -> Figure:
    parts = _window(10, 10, 620, 314, sidebar=190, bar=46)
    parts += [_rect(84, 22, 96, 24, "#e1e1e6", 6), _text(132, 38, "Visualizar ▾", size=12, weight=500, anchor="middle")]
    parts.append(_text(214, 39, "Utilitário de Disco", size=13, weight=700))
    for label, center in (("Partição", 440), ("Apagar", 510), ("Montar", 576)):
        parts += [_rect(center - 30, 22, 60, 24, "#e1e1e6", 6), _text(center, 38, label, size=12, anchor="middle")]
    # Barra lateral, já mostrando todos os dispositivos
    parts.append(_text(26, 136, "Interno", size=11, fill=SOFT, weight=700))
    parts += [_rect(18, 144, 176, 24, BLUE, 6), _rect(26, 150, 16, 12, "#dfe7f5", 2)]
    parts.append(_text(50, 161, "NVMe SSD 256 GB", size=12.5, fill="#ffffff", weight=500))
    parts += [_rect(50, 176, 12, 10, "#b0b4bd", 2), _text(68, 186, "Windows", size=12, fill=SOFT)]
    parts.append(_text(26, 218, "Externo", size=11, fill=SOFT, weight=700))
    parts += [_rect(26, 230, 16, 12, "#8e8e93", 2), _text(50, 241, "SanDisk Cruzer Blade", size=12.5)]
    parts += [_rect(50, 256, 12, 10, "#b0b4bd", 2), _text(68, 266, "MACPRONTO", size=12, fill=SOFT)]
    # Menu Visualizar aberto
    parts += [_rect(86, 52, 244, 60, "#00000014", 8), _rect(84, 50, 244, 58, "#ffffff", 8, "#c7c7cc")]
    parts.append(_text(108, 72, "Mostrar Apenas Volumes", size=12.5))
    parts += [_rect(90, 80, 232, 22, BLUE, 5), _text(96, 96, "✓", size=12, fill="#ffffff")]
    parts.append(_text(108, 96, "Mostrar Todos os Dispositivos", size=12.5, fill="#ffffff"))
    # Disco escolhido e a janela de apagar
    parts.append(_text(356, 82, "NVMe SSD 256 GB", size=15, weight=700))
    parts.append(_text(356, 100, "Disco interno PCI-Express", size=11.5, fill=SOFT))
    parts += [_rect(356, 112, 254, 12, "#e5e5ea", 6), _rect(356, 112, 160, 12, "#4f8ef7", 6)]
    parts += [_rect(225, 141, 396, 178, "#00000018", 10), _rect(222, 136, 396, 178, "#f6f6f8", 10, "#c7c7cc")]
    parts.append(_text(242, 160, 'Apagar "NVMe SSD 256 GB"?', size=13, weight=700))
    parts.append(_text(242, 178, "Todos os dados deste disco serão apagados.", size=11, fill=SOFT))
    for label, value, y in (("Nome:", "Macintosh HD", 206), ("Formato:", "APFS", 234), ("Esquema:", "Mapa de Partição GUID", 262)):
        parts.append(_text(330, y, label, size=12, anchor="end"))
        if label == "Nome:":
            parts += [_rect(338, y - 15, 260, 22, "#ffffff", 5, "#c7c7cc"), _text(346, y, value, size=12)]
        else:
            parts += _popup(338, y, 260, value)
    parts += _button(452, 284, 72, "Cancelar") + _button(532, 284, 72, "Apagar", primary=True)
    parts += [
        _mark(80, 76, 252, 30),
        _badge(1, 336, 91),
        _mark(14, 140, 184, 32),
        _badge(2, 198, 140),
        _mark(476, 18, 68, 32),
        _badge(3, 544, 18),
        _mark(334, 186, 274, 84),
        _badge(4, 608, 186),
    ]
    return Figure(
        _svg(332, "Utilitário de Disco apagando o disco interno", parts),
        "Utilitário de Disco. O nome do disco muda de computador para computador: confira pelo tamanho.",
        (
            "Visualizar > Mostrar Todos os Dispositivos.",
            "Selecione o disco inteiro (a linha de cima, com o nome do fabricante), não a partição Windows embaixo dele.",
            "Clique em Apagar.",
            "Nome: Macintosh HD. Formato: APFS. Esquema: Mapa de Partição GUID. Clique em Apagar e, no fim, em OK.",
        ),
    )


def installer_disk(macos_name: str) -> Figure:
    parts = [_rect(0, 0, WIDTH, 252, DESKTOP, 8)]
    parts += _window(110, 12, 420, 228, f"Instalar o {macos_name}")
    parts.append(_text(320, 60, f"Selecione o disco onde deseja instalar o {macos_name}.", size=12.5, anchor="middle"))
    for label, detail, center, chosen in (
        ("Macintosh HD", "o disco que você apagou", 230, True),
        ("MACPRONTO", "o pendrive", 410, False),
    ):
        opacity = None if chosen else 0.45
        if chosen:
            parts.append(_rect(center - 74, 80, 148, 114, "#dbe8fb", 10))
        parts += [_rect(center - 34, 92, 68, 50, "#c7c9d1", 8, "#a1a3ab", 1, opacity)]
        parts.append(_rect(center + 18, 128, 6, 6, "#7d8089", 3, opacity=opacity))
        parts.append(_text(center, 164, label, weight=600, anchor="middle", opacity=opacity))
        parts.append(_text(center, 182, detail, size=11, fill=SOFT, anchor="middle", opacity=opacity))
    parts += _button(130, 206, 70, "Voltar") + _button(440, 206, 80, "Continuar", primary=True)
    parts += [_mark(152, 76, 156, 122), _badge(1, 308, 76), _mark(436, 202, 88, 30), _badge(2, 524, 202)]
    return Figure(
        _svg(252, "Escolha do disco no instalador do macOS", parts),
        "O instalador do macOS.",
        (
            "Escolha Macintosh HD, o disco que você apagou. Nunca o MACPRONTO.",
            "Continuar. Daí em diante, o computador reinicia sozinho algumas vezes.",
        ),
    )


# ------------------------------------------------------------------ pós-instalação


def finder_pendrive(heliport: bool, feedback: bool) -> Figure:
    parts = _window(10, 10, 620, 290, "MacPronto", sidebar=170)
    parts.append(_text(24, 58, "Favoritos", size=11, fill=SOFT, weight=700))
    for index, item in enumerate(("Aplicativos", "Mesa", "Downloads")):
        parts.append(_text(30, 80 + index * 22, item, size=12.5))
    parts.append(_text(24, 156, "Locais", size=11, fill=SOFT, weight=700))
    parts.append(_text(30, 178, "Macintosh HD", size=12.5))
    parts += [_rect(16, 185, 158, 22, "#dcdce1", 6), _text(30, 200, "MACPRONTO", size=12.5, weight=600), _eject(156, 190)]
    files = [("AJUDA-IA.md", "doc"), ("AJUDA-IA.pdf", "pdf"), ("backup", "folder"), ("Bem-vindo-ao-Mac.pdf", "pdf")]
    if feedback:
        files.append(("Conte-como-foi.html", "doc"))
    files += [("EFI-definitiva", "folder"), ("Guia.pdf", "pdf")]
    if heliport:
        files.append(("HeliPort.dmg", "dmg"))
    files.append(("LEIA-ME.txt", "doc"))
    parts += [_text(204, 54, "Nome", size=11, fill=SOFT, weight=600), _line(190, 62, 630, 62)]
    for index, (name, kind) in enumerate(files):
        y = 82 + index * 20
        if index % 2:
            parts.append(_rect(181, y - 14, 448, 20, "#f5f5f7"))
        parts += [_file(204, y - 12, kind), _text(230, y, name, size=12.5)]
    parts += [_line(180, 278, 630, 278), _text(204, 293, "MACPRONTO  ›  MacPronto", size=11, fill=SOFT)]
    bottom = 82 + (len(files) - 1) * 20 + 10
    parts += [_mark(13, 182, 164, 28), _badge(1, 177, 182), _mark(196, 66, 300, bottom - 62), _badge(2, 496, 66)]
    return Figure(
        _svg(310, "Finder com a pasta MacPronto do pendrive", parts),
        "Finder: os arquivos do pendrive.",
        (
            "O pendrive aparece na barra lateral do Finder como MACPRONTO. Antes de tirá-lo, clique no ⏏ (ejetar).",
            "A pasta MacPronto tem o guia, a ajuda para IA, a EFI definitiva e os outros arquivos.",
        ),
    )


def heliport() -> Figure:
    parts = _menu_bar(("Finder", "Arquivo", "Editar", "Visualizar", "Ir"), height=236)
    parts.append(_wifi(452, 18))
    parts += [_rect(478, 7, 22, 11, "none", 3, INK, 1.2), _rect(480, 9, 15, 7, INK, 1), _rect(501, 10, 2, 5, INK, 1)]
    parts += [_rect(514, 6, 16, 6, "none", 3, INK, 1.2), _rect(514, 13, 16, 6, "none", 3, INK, 1.2)]
    parts.append(_text(WIDTH - 14, 17, "qui. 14:32", size=12.5, anchor="end"))
    parts += [_rect(303, 33, 260, 196, "#00000018", 10), _rect(300, 30, 260, 196, "#fafafc", 10, "#c7c7cc")]
    parts.append(_text(316, 56, "Wi-Fi", size=13, weight=700))
    parts += _toggle(510, 42, True)
    parts += [_line(310, 70, 550, 70), _text(316, 90, "Redes", size=11, fill=SOFT, weight=700)]
    for index, name in enumerate(("Minha Casa", "Minha Casa 5G", "Vizinho_2G")):
        y = 114 + index * 26
        selected = index == 0
        if selected:
            parts.append(_rect(306, y - 17, 248, 24, BLUE, 6))
        color = "#ffffff" if selected else INK
        parts.append(_text(316, y, name, size=12.5, fill=color))
        parts.append(_wifi(534, y + 2, color))
    parts += [_line(310, 190, 550, 190), _text(316, 212, "Entrar em Outra Rede…", size=12.5)]
    parts += [_mark(436, 1, 32, 23), _badge(1, 422, 12), _mark(302, 93, 256, 30), _badge(2, 558, 93)]
    return Figure(
        _svg(236, "Menu do HeliPort na barra de menus", parts),
        "O HeliPort na barra de menus.",
        (
            "O ícone do HeliPort, perto do relógio. Se não aparecer, abra o HeliPort em Aplicativos.",
            "Escolha a sua rede e digite a senha. O Wi-Fi dos Ajustes do Sistema continua desligado: é normal.",
        ),
    )


def _cap(x, y, w=34, label="", top="", bottom="") -> list[str]:
    parts = [_rect(x, y + 3, w, 34, "#9a9ca3", 5), _rect(x, y, w, 34, "#f2f3f5", 5)]
    if label:
        parts.append(_text(x + w / 2, y + 22, label, size=12, weight=600, anchor="middle"))
    if top:
        parts.append(_text(x + 7, y + 14, top, size=11))
    if bottom:
        parts.append(_text(x + 7, y + 29, bottom, size=11))
    return parts


def _windows_logo(cx, cy) -> str:
    return "".join(_rect(cx + dx, cy + dy, 5, 5, INK, 0.5) for dx in (-6, 0) for dy in (-6, 0))


def _mini_cap(x, y, label, w=34) -> list[str]:
    return [_rect(x, y + 2, w, 26, "#c9ccd3", 5), _rect(x, y, w, 26, "#ffffff", 5, "#b9bcc4"),
            _text(x + w / 2, y + 17, label, size=11.5, weight=600, anchor="middle")]


def pc_keyboard(abnt2: bool) -> Figure:
    parts = [_rect(0, 0, WIDTH, 290, "#f6f7fa", 8), _rect(8, 8, 342, 256, "#2b2d33", 12)]
    parts += _cap(20, 18, label="Esc")
    for index in range(4):
        parts += _cap(78 + index * 40, 18, label=f"F{index + 1}")
    parts += _cap(20, 60, top='"', bottom="'")
    for index, (top, bottom) in enumerate((("!", "1"), ("@", "2"), ("#", "3"), ("$", "4"), ("%", "5"), ("¨", "6"), ("&", "7"))):
        parts += _cap(60 + index * 40, 60, top=top, bottom=bottom)
    parts += _cap(20, 100, w=50, label="Tab")
    for index, letter in enumerate("QWERTY"):
        parts += _cap(76 + index * 40, 100, label=letter)
    parts += _cap(20, 140, w=58, label="Caps")
    for index, letter in enumerate("ASDFGH"):
        parts += _cap(84 + index * 40, 140, label=letter)
    parts += _cap(20, 180, w=36, label="⇧")
    parts += _cap(62, 180, top="|", bottom="\\")
    for index, letter in enumerate("ZXCVBN"):
        parts += _cap(102 + index * 40, 180, label=letter)
    parts += _cap(20, 220, w=44, label="Ctrl") + _cap(70, 220, w=44) + _cap(120, 220, w=44, label="Alt")
    parts += _cap(170, 220, w=170)
    parts.append(_windows_logo(92, 240))
    parts += [_text(110, 232, "⌘", size=11, fill=BLUE, weight=700, anchor="end"),
              _text(160, 232, "⌥", size=11, fill=BLUE, weight=700, anchor="end")]
    parts += [_mark(66, 216, 52, 44), _badge(1, 92, 276), _mark(116, 216, 52, 44), _badge(2, 142, 276)]
    notes = ["A tecla Windows é a Command (⌘), a mais usada nos atalhos do Mac.", "A Alt é a Option (⌥)."]
    if abnt2:
        parts += [_mark(16, 56, 42, 44), _badge(3, 16, 56), _mark(58, 176, 42, 44), _badge(4, 58, 176)]
        notes += [
            "Abaixo do Esc: ' e, com Shift, \".",
            "Ao lado do Z: \\ e, com Shift, |. Se estas duas teclas saírem trocadas, siga o ajuste do teclado ABNT2.",
        ]
    # Atalhos à direita
    parts.append(_text(372, 34, "Atalhos do Windows no Mac", size=13.5, weight=700))
    parts.append(_text(372, 53, "troque o Ctrl pela tecla Windows (⌘)", size=11.5, fill=SOFT))
    for index, (old, new, letter, action) in enumerate(
        (("Ctrl", "⌘", "C", "copiar"), ("Ctrl", "⌘", "V", "colar"), ("Ctrl", "⌘", "Z", "desfazer"), ("Alt", "⌘", "Tab", "outro app"))
    ):
        y = 72 + index * 44
        letter_w = 38 if letter == "Tab" else 28
        parts += _mini_cap(372, y, old, 36) + _mini_cap(412, y, letter, letter_w)
        parts.append(_arrow(458, y + 13, 480))
        parts += _mini_cap(486, y, new, 30) + _mini_cap(520, y, letter, letter_w)
        parts.append(_text(572 if letter == "Tab" else 562, y + 17, action, size=11.5, fill=SOFT))
    return Figure(
        _svg(290, "Teclado de PC com as teclas equivalentes do Mac", parts),
        "O teclado do PC no Mac.",
        tuple(notes),
    )


def keyboard_settings() -> Figure:
    parts = _settings_window("Teclado", "Teclado")
    parts.append(_rect(206, 50, 410, 64, "#f6f6f8", 8, "#e5e5ea"))
    parts += [_text(220, 74, "Repetição de teclas", size=12.5)] + _slider(440, 70, 160)
    parts += [_line(214, 84, 608, 84, "#e5e5ea"), _text(220, 104, "Atraso até repetir", size=12.5)] + _slider(440, 100, 160, 0.4)
    parts.append(_text(210, 140, "Entrada de Texto", size=12, weight=700))
    parts += [_rect(206, 148, 410, 46, "#f6f6f8", 8, "#e5e5ea"), _text(220, 175, "Fontes de entrada", size=12.5)]
    parts.append(_text(470, 175, "Brasileiro – ABNT2", size=12, fill=SOFT, anchor="end"))
    parts += _button(482, 160, 72, "Editar…")
    parts += _button(290, 252, 150, "Atalhos de Teclado…") + _button(452, 252, 160, "Alterar Tipo de Teclado…")
    parts += [_mark(477, 155, 82, 32), _badge(1, 559, 155), _mark(447, 247, 170, 32), _badge(2, 617, 247)]
    return Figure(
        _svg(302, "Ajustes do Sistema, painel Teclado", parts),
        "Ajustes do Sistema > Teclado.",
        (
            "Fontes de entrada > Editar… > + > Português (Brasil) > Brasileiro – ABNT2. Apague as outras com o –.",
            "Alterar Tipo de Teclado…: aperte as teclas pedidas e escolha ISO (Europeu e outros). Depois, reinicie.",
        ),
    )


def trackpad_settings() -> Figure:
    parts = _settings_window("Trackpad", "Trackpad")
    parts += [_rect(250, 44, 330, 24, "#e3e3e8", 7), _rect(252, 46, 108, 20, "#ffffff", 6)]
    for label, center in (("Apontar e Clicar", 306), ("Rolar e Zoom", 416), ("Mais Gestos", 526)):
        parts.append(_text(center, 60, label, size=11.5, weight=600 if center == 306 else 400, anchor="middle"))
    parts.append(_rect(206, 80, 410, 196, "#f6f6f8", 8, "#e5e5ea"))
    rows = ("Velocidade de rastreamento", "Clique firme e retorno tátil", "Pesquisar e detectores de dados",
            "Clique secundário", "Tocar para clicar")
    for index, label in enumerate(rows):
        y = 106 + index * 38
        if index:
            parts.append(_line(214, y - 23, 608, y - 23, "#e5e5ea"))
        parts.append(_text(220, y, label, size=12.5))
    parts += _slider(450, 102, 150)
    parts += _toggle(564, 134, False)
    parts += _popup(436, 182, 172, "Desativado")
    parts += _popup(436, 220, 172, "Clique com dois dedos")
    parts += _toggle(564, 248, True)
    parts += [
        _mark(431, 163, 182, 28),
        _badge(1, 613, 163),
        _mark(559, 129, 46, 30),
        _badge(2, 605, 129),
        _mark(559, 243, 46, 30),
        _badge(3, 605, 243),
    ]
    return Figure(
        _svg(302, "Ajustes do Sistema, painel Trackpad", parts),
        "Ajustes do Sistema > Trackpad > Apontar e Clicar.",
        (
            "Pesquisar e detectores de dados: Desativado. Assim, arrastar com o botão não abre a prévia do arquivo.",
            "Clique firme e retorno tátil: desligado.",
            "Tocar para clicar: ligue, se preferir tocar em vez de apertar.",
        ),
    )


def terminal_diskutil() -> Figure:
    lines = (
        "usuario@Mac ~ % diskutil list",
        "/dev/disk0 (internal, physical):",
        "   #:                       TYPE NAME                    SIZE       IDENTIFIER",
        "   0:      GUID_partition_scheme                        *256.1 GB   disk0",
        "   1:                        EFI EFI                     209.7 MB   disk0s1",
        "   2:                 Apple_APFS Container disk1         255.9 GB   disk0s2",
        "",
        "/dev/disk2 (external, physical):",
        "   0:     FDisk_partition_scheme                        *30.8 GB    disk2",
        "   1:             Windows_FAT_32 MACPRONTO               30.8 GB    disk2s1",
        "",
        "usuario@Mac ~ % sudo diskutil mount disk0s1",
        "Password:",
        "Volume EFI on disk0s1 mounted",
    )
    parts = _window(10, 10, 620, 292, "Terminal — zsh")
    for index, line in enumerate(lines):
        parts.append(_text(24, 58 + index * 16.5, line, size=11.5, mono=True))
    command = _mono_width(lines[0], 11.5)
    mount = _mono_width(lines[11], 11.5)
    parts += [
        _mark(18, 44, command + 14, 19),
        _badge(1, 32 + command, 44),
        _mark(18, 110, 524, 19),
        _badge(2, 542, 110),
        _mark(18, 225, mount + 14, 19),
        _badge(3, 32 + mount, 225),
    ]
    return Figure(
        _svg(312, "Terminal com o diskutil list e o comando para montar a partição EFI", parts),
        "Terminal (Aplicativos > Utilitários > Terminal). Os números dos discos mudam de computador para computador.",
        (
            "diskutil list mostra os discos. O interno tem (internal); o pendrive, (external).",
            "A partição EFI do disco interno, do tipo EFI. Aqui é a disk0s1; confira a sua (pode se chamar EFI ou NO NAME).",
            "sudo diskutil mount disk0s1 e a senha do Mac. A senha não aparece enquanto você digita: é normal. Aperte Enter.",
        ),
    )


def finder_efi() -> Figure:
    parts = _window(10, 10, 620, 272, "EFI", sidebar=170)
    parts.append(_text(24, 58, "Locais", size=11, fill=SOFT, weight=700))
    parts.append(_text(30, 80, "Macintosh HD", size=12.5))
    parts += [_rect(16, 87, 158, 22, "#dcdce1", 6), _text(30, 102, "EFI", size=12.5, weight=600), _eject(156, 92)]
    parts += [_text(30, 124, "MACPRONTO", size=12.5), _eject(156, 114)]
    parts += [_text(204, 54, "Nome", size=11, fill=SOFT, weight=600), _line(190, 62, 630, 62)]
    for name, indent, y in (("EFI", 0, 84), ("BOOT", 22, 106), ("OC", 22, 128)):
        if not indent:
            parts.append(_text(194, y, "▾", size=11, fill=SOFT))
        parts += [_folder(208 + indent, y - 13), _text(234 + indent, y, name, size=12.5)]
    # De onde vem a pasta
    parts += [_rect(303, 157, 312, 112, "#00000014", 10), _rect(300, 154, 312, 112, "#ffffff", 10, "#c7c7cc")]
    parts.append(_text(314, 176, "MACPRONTO › MacPronto › EFI-definitiva", size=11, fill=SOFT))
    parts += [_folder(316, 188), _text(342, 201, "EFI", size=12.5, weight=600)]
    parts += _mini_cap(452, 186, "⌘", 30) + _mini_cap(486, 186, "C", 28)
    parts.append(_text(524, 203, "copiar", size=11.5, fill=SOFT))
    parts.append(_text(314, 246, "Na partição EFI:", size=12))
    parts += _mini_cap(452, 230, "⌘", 30) + _mini_cap(486, 230, "V", 28)
    parts.append(_text(524, 247, "colar", size=11.5, fill=SOFT))
    parts += [
        _mark(306, 182, 270, 36),
        _badge(1, 576, 182),
        _mark(13, 84, 164, 28),
        _badge(2, 177, 84),
        _mark(222, 90, 120, 46),
        _badge(3, 342, 90),
    ]
    return Figure(
        _svg(292, "Finder copiando a pasta EFI para a partição EFI do disco interno", parts),
        "Finder: a EFI definitiva na partição EFI do disco interno.",
        (
            "No pendrive, em MACPRONTO > MacPronto > EFI-definitiva, selecione a pasta EFI e copie (Command + C).",
            "Clique na partição EFI do disco interno (EFI ou NO NAME) e cole (Command + V). Se perguntar, escolha Substituir.",
            "Confira: dentro de EFI ficam as pastas BOOT e OC. Depois, ejete a partição (⏏).",
        ),
    )


def about_mac(smbios_model: str, macos_label: str, laptop: bool) -> Figure:
    parts = [_rect(0, 0, WIDTH, 266, DESKTOP, 8)]
    parts += _window(170, 12, 300, 244)
    if laptop:
        parts += [_rect(280, 50, 80, 52, "#2b2d33", 6), _rect(284, 54, 72, 44, "#6d8fd6", 2)]
        parts.append('<path d="M268 104 h104 l-6 7 h-92 z" fill="#c7c9d1"/>')
    else:
        parts += [_rect(276, 46, 88, 60, "#2b2d33", 6), _rect(280, 50, 80, 48, "#6d8fd6", 2)]
        parts.append('<path d="M310 106 h20 l4 10 h-28 z" fill="#c7c9d1"/>')
    parts.append(_text(320, 142, mac_name(smbios_model), size=17, weight=700, anchor="middle"))
    for label, value, y in (("macOS", macos_label, 172), ("Número de série", "●●●●●●●●●●●●", 196)):
        parts += [_text(312, y, label, size=12, fill=SOFT, anchor="end"), _text(320, y, value, size=12)]
    parts += _button(256, 216, 128, "Mais Informações…")
    parts += [_mark(186, 181, 268, 22), _badge(1, 454, 181)]
    return Figure(
        _svg(266, "Janela Sobre Este Mac com o número de série escondido", parts),
        "Menu Apple > Sobre Este Mac.",
        (
            "Clique duas vezes no número de série para selecionar e copie. Confira em checkcoverage.apple.com: o certo "
            "é dar número inválido. Nunca publique esse número.",
        ),
    )


# ------------------------------------------------------------------ conjunto


def build(
    *,
    bios_key: str,
    boot_key: str,
    macos_name: str,
    macos_label: str,
    opencore: str,
    smbios_model: str,
    laptop: bool,
    abnt2: bool,
    heliport_app: bool,
    feedback: bool = False,
) -> dict[str, Figure]:
    """Todas as figuras do guia, pelo nome que os passos de content.py usam."""
    return {
        "keys": power_keys(bios_key, boot_key),
        "bios": bios_screen(),
        "boot_menu": boot_menu(boot_key),
        "opencore": opencore_install(opencore),
        "verbose": verbose(),
        "recovery": recovery(macos_name),
        "disk_utility": disk_utility(),
        "installer": installer_disk(macos_name),
        "opencore_reboot": opencore_reboot(opencore),
        "finder_pendrive": finder_pendrive(heliport_app, feedback),
        "heliport": heliport(),
        "pc_keyboard": pc_keyboard(abnt2),
        "keyboard_settings": keyboard_settings(),
        "trackpad_settings": trackpad_settings(),
        "terminal_diskutil": terminal_diskutil(),
        "finder_efi": finder_efi(),
        "about_mac": about_mac(smbios_model, macos_label, laptop),
    }
