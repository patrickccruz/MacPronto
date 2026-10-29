"""Adaptador do OpCore Simplify. Roda dentro do worker, com a área de trabalho no sys.path.

O OpCore Simplify conversa com o usuário por ``Utils.request_input``. Aqui essas
perguntas são respondidas por regras: cada pergunta conhecida tem uma chave
estável, uma resposta padrão e, quando é uma escolha real, vira uma "decisão"
devolvida à interface, que pode trocá-la e pedir um novo plano.
"""

from __future__ import annotations

import importlib.util
import json
import plistlib
import re
import shutil
import subprocess
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from macpronto.engine.errors import EngineError
from macpronto.engine.worker import TaskContext

OPTION_LINE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
LAYOUT_LINE = re.compile(r"^\s*(\d+)\s{2,}(.+?)\s*$")
DEFAULT_IN_PROMPT = re.compile(r"\(default:\s*([^)]+)\)")
RECOMMENDED_LAYOUT_AUTHORS = ("Mirone", "InsanelyDeepak", "Toleda", "DalianSky")

STAGE_TITLES = {
    "Compatibility Checker": "Verificando compatibilidade",
    "Hardware Customization": "Personalizando o hardware",
    "Select Required Kernel Extensions": "Selecionando kexts",
    "Kext Compatibility Check": "Verificando kexts",
    "Select macOS Version": "Escolhendo a versão do macOS",
    "Gathering Files": "Baixando arquivos",
    "Building OpenCore EFI": "Montando a EFI",
    "Loading ACPI Table(s)": "Carregando tabelas ACPI",
    "Choosing Codec Layout ID": "Escolhendo o layout de áudio",
    "Dumping ACPI Tables": "Extraindo tabelas ACPI",
}
SILENT_STAGES = {"Device Selection Summary", "OpCore Simplify"}

# Mensagens de encerramento do OpCore Simplify -> código estável.
FATAL_MESSAGES = (
    ("Missing required SSE4.x instruction set", "cpu-sse4"),
    ("No GPU found", "no-gpu"),
    ("without a supported GPU", "gpu-unsupported"),
    ("Intel VMD controllers are not supported", "intel-vmd"),
    ("No storage controller found", "no-storage"),
    ("No compatible storage controller", "storage-unsupported"),
)


class OCSExit(Exception):
    """O OpCore Simplify chamou exit_program(): a máquina tem um impedimento."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = [line for line in lines if line.strip()]
        text = " ".join(self.lines)
        self.code = next((code for needle, code in FATAL_MESSAGES if needle in text), "ocs-exit")
        super().__init__(text or "O OpCore Simplify encerrou a análise.")


@dataclass(frozen=True)
class PromptRule:
    pattern: re.Pattern
    key: Callable[[re.Match], str]
    label: str
    decision: bool
    default: Callable[[PromptBroker, re.Match, list[dict]], str]


def _keep_default(_broker, _match, _options) -> str:
    return ""


def _last_option(_broker, _match, options) -> str:
    return options[-1]["value"] if options else "1"


def _first_option(_broker, _match, options) -> str:
    return options[0]["value"] if options else "1"


def _recommended_layout(_broker, _match, options) -> str:
    for option in options:
        if any(author in option["label"] for author in RECOMMENDED_LAYOUT_AUTHORS):
            return option["value"]
    return options[0]["value"] if options else ""


PROMPT_RULES = (
    PromptRule(
        re.compile(r"Build EFI for UEFI\?"), lambda m: "firmware-uefi", "Montar a EFI para UEFI", True, lambda *_: "yes"
    ),
    PromptRule(
        re.compile(r"Select a (\w+) combination"),
        lambda m: f"combination-{m.group(1).lower()}",
        "Combinação de dispositivos",
        True,
        _last_option,
    ),
    PromptRule(
        re.compile(r"Select a (\w+) device \(1-\d+\)"),
        lambda m: f"device-{m.group(1).lower()}",
        "Dispositivo a manter ativo",
        True,
        _first_option,
    ),
    PromptRule(
        re.compile(r"Select audio kext for your system"),
        lambda m: "tahoe-audio",
        "Áudio no macOS Tahoe",
        True,
        lambda *_: "2",
    ),
    PromptRule(
        re.compile(r"Select kext for your AMD (.+) GPU"),
        lambda m: "amd-gpu-kext",
        "Kext da GPU AMD",
        True,
        _keep_default,
    ),
    PromptRule(
        re.compile(r"Select Intel Wi-Fi kext"), lambda m: "intel-wifi-kext", "Kext do Wi-Fi Intel", True, _keep_default
    ),
    # Importar as senhas de Wi-Fi do Windows para o itlwm: o MacPronto não importa (ficariam em
    # texto puro na EFI). Sem esta regra, o Enter era inválido e a pergunta se repetia.
    PromptRule(
        re.compile(r"scan for WiFi profiles"),
        lambda m: "wifi-profiles",
        "Importar as redes Wi-Fi do Windows",
        False,
        lambda *_: "no",
    ),
    PromptRule(
        re.compile(r"force load"),
        lambda m: "force-load-kexts",
        "Forçar kexts sem suporte oficial",
        True,
        lambda *_: "no",
    ),
    PromptRule(
        re.compile(r"Enter the ID of the codec layout"),
        lambda m: "audio-layout-id",
        "Layout de áudio (layout-id)",
        True,
        _recommended_layout,
    ),
    PromptRule(
        re.compile(r"Please enter the macOS version"),
        lambda m: "macos-version",
        "Versão do macOS",
        False,
        _keep_default,
    ),
    PromptRule(re.compile(r"Press Enter|^\s*$"), lambda m: "continue", "Continuar", False, _keep_default),
)


class PromptBroker:
    """Responde aos request_input do OpCore Simplify e registra as decisões."""

    def __init__(self, ctx: TaskContext, answers: dict[str, str] | None = None) -> None:
        self.ctx = ctx
        self.answers = {str(k): str(v) for k, v in (answers or {}).items()}
        self.lines: deque[str] = deque(maxlen=400)
        self.previous_block: list[str] = []
        self.decisions: dict[str, dict] = {}
        self.counts: Counter[str] = Counter()
        self.acpi_dir: str | None = None
        ctx.line_hooks.append(self.lines.append)

    def recent_lines(self) -> list[str]:
        return self.previous_block + list(self.lines)

    def on_head(self, title: str | None) -> None:
        self.lines.clear()
        if title and title not in SILENT_STAGES:
            self.ctx.stage(STAGE_TITLES.get(title, title))

    def ask(self, prompt: str) -> str:
        prompt = prompt or ""
        block = list(self.lines)
        self.previous_block = block
        self.lines.clear()

        if "ACPI Tables folder" in prompt:
            self.counts["acpi-folder"] += 1
            if self.acpi_dir and self.counts["acpi-folder"] == 1:
                return self.acpi_dir
            raise EngineError("acpi-missing", "As tabelas ACPI desta máquina não foram encontradas.")

        for rule in PROMPT_RULES:
            match = rule.pattern.search(prompt)
            if not match:
                continue
            key = rule.key(match)
            self.counts[key] += 1
            if self.counts[key] > 6:
                raise EngineError("prompt-loop", f"O OpCore Simplify repetiu a pergunta: {prompt.strip()}")
            options = self._options_for(key, block)
            default = rule.default(self, match, options)
            answer = self.answers.get(key, default)
            if rule.decision:
                self._record(key, rule.label, prompt, options, default, answer)
            self.ctx.log("debug", f"Pergunta '{prompt.strip()}' respondida com '{answer or '(padrão)'}'")
            return answer

        self.counts[prompt] += 1
        if self.counts[prompt] > 3:
            raise EngineError("prompt-unknown", f"Pergunta inesperada do OpCore Simplify: {prompt.strip()}")
        self.ctx.log("warning", f"Pergunta não mapeada respondida com Enter: {prompt.strip()}")
        return ""

    @staticmethod
    def _options_for(key: str, block: list[str]) -> list[dict]:
        options = []
        if key == "audio-layout-id":
            in_table = False
            for line in block:
                if line.strip().startswith("ID") and "Comment" in line:
                    in_table = True
                    continue
                if in_table:
                    match = LAYOUT_LINE.match(line)
                    if match:
                        options.append({"value": match.group(1), "label": match.group(2)})
                    elif line.strip() and not line.strip().startswith("-"):
                        in_table = False
            return options

        for line in block:
            match = OPTION_LINE.match(line)
            if match:
                options.append({"value": match.group(1), "label": match.group(2), "details": []})
            elif options and line.startswith("   ") and line.strip():
                options[-1]["details"].append(line.strip())
        return options

    def _record(self, key: str, label: str, prompt: str, options: list[dict], default: str, answer: str) -> None:
        recommended = default
        prompt_default = DEFAULT_IN_PROMPT.search(prompt)
        if not recommended and prompt_default:
            wanted = prompt_default.group(1).strip()
            wanted_tokens = set(re.findall(r"[a-z0-9]+", wanted.lower()))
            match = next(
                (
                    o
                    for o in options
                    if o["value"] == wanted
                    or set(re.findall(r"[a-z0-9]+", o["label"].split(" - ")[0].lower())) == wanted_tokens
                ),
                None,
            )
            recommended = match["value"] if match else wanted
        self.decisions[key] = {
            "key": key,
            "label": label,
            "prompt": prompt.strip(),
            "options": options,
            "recommended": recommended,
            "chosen": answer or recommended,
        }


# --------------------------------------------------------------------------- carregamento


class OCS(SimpleNamespace):
    """Módulos do OpCore Simplify já importados e com a interface substituída."""


def load(ctx: TaskContext, answers: dict | None = None, allow_iasl_download: bool = True) -> tuple[OCS, PromptBroker]:
    if ctx.workspace is None:
        raise EngineError("workspace", "Área de trabalho do OpCore Simplify não definida.")

    broker = PromptBroker(ctx, answers)

    from Scripts.datasets import (  # type: ignore[import-not-found]
        acpi_patch_data,
        codec_layouts,
        kext_data,
        mac_model_data,
        os_data,
        pci_data,
    )

    from Scripts import (  # type: ignore[import-not-found]
        acpi_guru,
        compatibility_checker,
        dsdt,
        gathering_files,
        hardware_customizer,
        kext_maestro,
        smbios,
        utils,
    )

    def request_input(self, prompt="Press Enter to continue..."):
        return broker.ask(prompt)

    def head(self, text=None, width=68, resize=True):
        broker.on_head(text)

    def progress_bar(self, title, steps, current_step_index, done=False):
        if done:
            ctx.progress(len(steps), len(steps), title, force=True)
        else:
            ctx.progress(current_step_index, len(steps), steps[current_step_index], force=True)

    def exit_program(self):
        raise OCSExit(broker.recent_lines())

    utils.Utils.request_input = request_input
    utils.Utils.head = head
    utils.Utils.progress_bar = progress_bar
    utils.Utils.exit_program = exit_program
    utils.Utils.adjust_window_size = lambda self, content="": None
    utils.Utils.open_folder = lambda self, folder_path: None

    if not allow_iasl_download:
        original_check = dsdt.DSDT.check_iasl

        def offline_check(self, legacy=False, try_downloading=True):
            return original_check(self, legacy=legacy, try_downloading=False) or "iasl-pendente"

        dsdt.DSDT.check_iasl = offline_check

    _keep_ocvalidate(ctx, gathering_files)

    main_module = _load_main_module(ctx.workspace)

    return (
        OCS(
            acpi_guru=acpi_guru,
            compatibility_checker=compatibility_checker,
            gathering_files=gathering_files,
            hardware_customizer=hardware_customizer,
            kext_maestro=kext_maestro,
            smbios=smbios,
            utils=utils,
            acpi_patch_data=acpi_patch_data,
            codec_layouts=codec_layouts,
            kext_data=kext_data,
            mac_model_data=mac_model_data,
            os_data=os_data,
            pci_data=pci_data,
            main=main_module,
        ),
        broker,
    )


def _load_main_module(workspace: Path):
    spec = importlib.util.spec_from_file_location("opcore_simplify_main", workspace / "OpCore-Simplify.py")
    if spec is None or spec.loader is None:
        raise EngineError("ocs-load", "Não foi possível carregar o OpCore-Simplify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _keep_ocvalidate(ctx: TaskContext, gathering_files) -> None:
    """Guarda o ocvalidate.exe do pacote OpenCorePkg, que o OpCore Simplify descarta."""
    original = gathering_files.gatheringFiles.move_bootloader_kexts_to_product_directory
    bin_dir = Path(ctx.workspace) / "bin"

    def wrapper(self, product_name):
        if "OpenCore" in product_name:
            source = Path(self.temporary_dir) / product_name
            found = next(iter(source.rglob("ocvalidate.exe")), None) if source.exists() else None
            if found:
                bin_dir.mkdir(exist_ok=True)
                shutil.copy2(found, bin_dir / "ocvalidate.exe")
        return original(self, product_name)

    gathering_files.gatheringFiles.move_bootloader_kexts_to_product_directory = wrapper


# --------------------------------------------------------------------------- utilidades


def _darwin_major(version: str | None) -> int | None:
    if not version:
        return None
    return int(str(version).split(".")[0])


def _normalize_version(value) -> str:
    """Aceita 24, "24" ou "24.1.0" e devolve no formato do OpCore Simplify."""
    text = str(value).strip()
    parts = text.split(".")
    while len(parts) < 3:
        parts.append("99")
    return ".".join(parts[:3])


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, bytes):
        return value.hex().upper()
    return value


def _macos_catalog(ocs: OCS) -> list[dict]:
    return [
        {
            "darwin": item.darwin_version,
            "name": item.name,
            "version": item.macos_version,
            "beta": item.release_status != "final",
        }
        for item in ocs.os_data.macos_versions
    ]


def _device_tags(ocs: OCS, report: dict) -> dict[str, dict[str, list[str]]]:
    """Informações auxiliares por dispositivo para o laudo (família de Wi-Fi, codec etc.)."""
    pci = ocs.pci_data
    tags: dict[str, dict[str, list[str]]] = {}

    for name, props in report.get("Network", {}).items():
        device_id = props.get("Device ID")
        found = []
        if device_id in pci.WirelessCardIDs:
            found.append("wifi")
            if device_id in pci.BroadcomWiFiIDs:
                found.append("broadcom")
            elif device_id in pci.IntelWiFiIDs:
                found.append("intel")
            elif device_id in pci.AtherosWiFiIDs:
                found.append("atheros")
            elif device_id in getattr(pci, "rtw88WiFiIDs", []):
                found.append("realtek-rtw88")
        elif device_id in getattr(pci, "WirelessUSBIDs", []):
            found.extend(["wifi", "usb"])
        elif device_id in pci.EthernetIDs:
            found.append("ethernet")
        tags.setdefault("Network", {})[name] = found

    for name, props in report.get("Sound", {}).items():
        device_id = props.get("Device ID", "")
        found = []
        if "USB" in props.get("Bus Type", ""):
            found.append("usb-audio")
        elif device_id in ocs.codec_layouts.data:
            found.append("codec-supported")
        elif device_id.startswith(("8086", "1002", "10DE")):
            found.append("hdmi-audio")
        tags.setdefault("Sound", {})[name] = found

    for name, props in report.get("Bluetooth", {}).items():
        device_id = props.get("Device ID")
        found = []
        if device_id in getattr(pci, "IntelBluetoothIDs", []):
            found.append("intel")
        elif device_id in getattr(pci, "BroadcomBluetoothIDs", []):
            found.append("broadcom")
        elif device_id in getattr(pci, "RealtekBluetoothIDs", []):
            found.append("realtek")
        tags.setdefault("Bluetooth", {})[name] = found

    return tags


# --------------------------------------------------------------------------- análise


def _check_compatibility(ocs: OCS, report: dict) -> tuple[dict, dict | None, dict | None, list[dict]]:
    """Roda o verificador do OpCore Simplify sem parar no primeiro impedimento."""
    checker = ocs.compatibility_checker.CompatibilityChecker()
    fatal: list[dict] = []
    latest = ocs.os_data.get_latest_darwin_version()
    lowest = ocs.os_data.get_lowest_darwin_version()

    for attribute in dir(checker):
        if (
            not (attribute.startswith("check_") and attribute.endswith("_compatibility"))
            or attribute == "check_compatibility"
        ):
            continue
        original = getattr(checker, attribute)
        area_name = attribute.removeprefix("check_").removesuffix("_compatibility")

        def guarded(original=original, area=area_name):
            try:
                original()
            except OCSExit as exc:
                fatal.append({"area": area, "code": exc.code, "message": " ".join(exc.lines)})
                if not hasattr(checker, "max_native_macos_version"):
                    checker.max_native_macos_version = latest
                    checker.min_native_macos_version = lowest

        setattr(checker, attribute, guarded)

    hardware_report, native, oclp = checker.check_compatibility(report)
    native_range = None if fatal else {"min": native[0], "max": native[1]}
    oclp_range = {"max": oclp[0], "min": oclp[1]} if oclp else None
    return hardware_report, native_range, oclp_range, fatal


def _suggest_version(ocs: OCS, hardware_report: dict, native: dict, oclp: dict | None) -> str | None:
    fake_self = SimpleNamespace(u=ocs.utils.Utils())
    oclp_tuple = (oclp["max"], oclp["min"]) if oclp else None
    try:
        return ocs.main.OCPE.select_macos_version(
            fake_self, hardware_report, (native["min"], native["max"]), oclp_tuple
        )
    except EngineError:
        return native["max"]


def analyze(ctx: TaskContext) -> dict:
    report = ctx.params["report"]
    ocs, _broker = load(ctx, allow_iasl_download=False)
    ctx.stage("Verificando compatibilidade")

    hardware_report, native, oclp, fatal = _check_compatibility(ocs, report)
    suggested = _suggest_version(ocs, hardware_report, native, oclp) if native else None

    return {
        "report": _json_safe(hardware_report),
        "native": native,
        "oclp": oclp,
        "fatal": fatal,
        "suggested": suggested,
        "catalog": _macos_catalog(ocs),
        "tags": _device_tags(ocs, hardware_report),
        "cpu": _cpu_flags(hardware_report),
    }


def _cpu_flags(report: dict) -> dict:
    from Scripts.datasets import cpu_data  # type: ignore[import-not-found]

    from Scripts import kext_maestro  # type: ignore[import-not-found]

    cpu = report.get("CPU", {})
    name = cpu.get("Processor Name", "")
    codename = cpu.get("Codename", "")
    manufacturer = cpu.get("Manufacturer", "")
    generations = cpu_data.IntelCPUGenerations
    index = generations.index(codename) if codename in generations else None
    return {
        "manufacturer": manufacturer,
        "codename": codename,
        "intel_generation_index": index,
        # Índices 0 a 19: Arrow, Lunar, Meteor, Raptor e Alder Lake (núcleos P e E)
        "hybrid": index is not None and index <= 19 and codename != "Lakefield",
        # Índice 62 em diante: Ivy Bridge e anteriores
        "legacy": index is not None and index >= 62,
        "hedt": kext_maestro.KextMaestro.is_intel_hedt_cpu(None, name, codename),
        "low_end": any(brand in name for brand in ("Celeron", "Pentium", "Atom")),
        "avx2": "AVX2" in cpu.get("SIMD Features", ""),
        "amd_generation": codename if manufacturer == "AMD" and codename in cpu_data.AMDCPUGenerations else None,
    }


# --------------------------------------------------------------------------- plano e montagem


def _apply_overrides(ocs: OCS, ocpe, macos_version: str, params: dict) -> None:
    for name, enabled in (params.get("acpi_overrides") or {}).items():
        for patch in ocpe.ac.patches:
            if patch.name == name:
                patch.checked = bool(enabled)

    for name, enabled in (params.get("kext_overrides") or {}).items():
        index = ocs.kext_data.kext_index_by_name.get(name)
        if index is None:
            continue
        if enabled:
            ocpe.k.check_kext(index, macos_version, force_load=True)
        else:
            ocpe.k.uncheck_kext(index)


def _prepare(ctx: TaskContext, ocs: OCS, ocpe) -> dict:
    """Etapas comuns ao plano e à montagem. Devolve o estado necessário para montar."""
    params = ctx.params
    report = params["report"]
    macos_version = _normalize_version(params["macos_version"])

    ctx.stage("Verificando compatibilidade")
    try:
        hardware_report, native, oclp = ocpe.c.check_compatibility(json.loads(json.dumps(report)))
    except OCSExit as exc:
        raise EngineError(exc.code, "Esta máquina tem um impedimento para o macOS.", " ".join(exc.lines)) from exc

    ctx.stage("Personalizando o hardware")
    customized, disabled, needs_oclp = ocpe.h.hardware_customization(hardware_report, macos_version)

    default_smbios = ocpe.s.select_smbios_model(customized, macos_version)
    smbios_model = params.get("smbios_model") or default_smbios

    ctx.stage("Selecionando patches ACPI e kexts")
    ocpe.ac.select_acpi_patches(customized, disabled)
    needs_oclp = ocpe.k.select_required_kexts(customized, macos_version, needs_oclp, ocpe.ac.patches)
    ocpe.s.smbios_specific_options(customized, smbios_model, macos_version, ocpe.ac.patches, ocpe.k)
    _apply_overrides(ocs, ocpe, macos_version, params)

    # Antecipa a escolha do layout de áudio para que ela apareça no plano. Na montagem,
    # o config_prodigy pergunta de novo e recebe a mesma resposta.
    if any(kext.checked and kext.name == "AppleALC" for kext in ocs.kext_data.kexts):
        ocpe.co.select_audio_codec_layout(customized)

    bios_requirements = ocs.main.OCPE.check_bios_requirements(SimpleNamespace(u=ocpe.u), hardware_report, customized)

    return {
        "macos_version": macos_version,
        "hardware_report": hardware_report,
        "customized": customized,
        "disabled": disabled,
        "needs_oclp": needs_oclp,
        "smbios_model": smbios_model,
        "default_smbios": default_smbios,
        "bios_requirements": bios_requirements,
        "native": {"min": native[0], "max": native[1]},
        "oclp": {"max": oclp[0], "min": oclp[1]} if oclp else None,
    }


def _plan_summary(ocs: OCS, broker: PromptBroker, ocpe, state: dict) -> dict:
    macos_version = state["macos_version"]
    parse = ocs.utils.Utils().parse_darwin_version
    smbios_candidates = [
        {
            "name": device.name,
            "cpu": device.cpu,
            "generation": device.cpu_generation,
            "gpu": device.discrete_gpu,
        }
        for device in ocs.mac_model_data.mac_devices
        if parse(device.initial_support) <= parse(macos_version) <= parse(device.last_supported_version)
    ]

    disabled = []
    for label, props in state["disabled"].items():
        kind, _, name = label.partition(": ")
        disabled.append({"label": label, "type": kind, "name": name, "device_id": props.get("Device ID")})

    return {
        "macos_version": macos_version,
        "needs_oclp": state["needs_oclp"],
        "smbios_model": state["smbios_model"],
        "default_smbios": state["default_smbios"],
        "smbios_candidates": smbios_candidates,
        "disabled_devices": disabled,
        "customized": _json_safe(state["customized"]),
        "kexts": [
            {
                "name": kext.name,
                "description": kext.description,
                "category": kext.category,
                "checked": bool(kext.checked),
                "required": bool(kext.required),
            }
            for kext in ocs.kext_data.kexts
        ],
        "acpi_patches": [
            {"name": patch.name, "description": patch.description, "checked": bool(patch.checked)}
            for patch in ocpe.ac.patches
        ],
        "decisions": list(broker.decisions.values()),
        "bios_requirements": state["bios_requirements"],
        "native": state["native"],
        "oclp": state["oclp"],
    }


def plan(ctx: TaskContext) -> dict:
    ocs, broker = load(ctx, ctx.params.get("answers"), allow_iasl_download=False)
    ocpe = ocs.main.OCPE()
    state = _prepare(ctx, ocs, ocpe)
    return _plan_summary(ocs, broker, ocpe, state)


def build(ctx: TaskContext) -> dict:
    params = ctx.params
    output_dir = Path(params["output_dir"])
    acpi_dir = params.get("acpi_dir")
    if not acpi_dir or not Path(acpi_dir).is_dir():
        raise EngineError("acpi-missing", "As tabelas ACPI são necessárias para montar a EFI. Refaça o diagnóstico.")

    ocs, broker = load(ctx, params.get("answers"), allow_iasl_download=True)
    broker.acpi_dir = acpi_dir

    ctx.stage("Preparando o iasl")
    ocpe = ocs.main.OCPE()
    ocpe.result_dir = str(output_dir)

    ctx.stage("Carregando tabelas ACPI")
    ocpe.ac.read_acpi_tables(acpi_dir)
    if not ocpe.ac._ensure_dsdt():
        raise EngineError("acpi-invalid", "Não foi possível ler a DSDT desta máquina.")

    state = _prepare(ctx, ocs, ocpe)
    summary = _plan_summary(ocs, broker, ocpe, state)

    _ensure_ocvalidate_download(ctx, ocpe)

    ctx.stage("Baixando OpenCore e kexts")
    try:
        ok = ocpe.o.gather_bootloader_kexts(ocpe.k.kexts, state["macos_version"])
    except Exception as exc:  # noqa: BLE001 - erros de rede chegam como Exception genérica
        raise EngineError("download", f"Falha ao baixar o OpenCore ou os kexts: {exc}") from exc
    if ok is False:
        raise EngineError("download", "Falha ao baixar o OpenCore ou os kexts.", "\n".join(broker.recent_lines()))

    ctx.stage("Montando a EFI")
    ocpe.build_opencore_efi(
        state["customized"], state["disabled"], state["smbios_model"], state["macos_version"], state["needs_oclp"]
    )

    config_path = output_dir / "EFI" / "OC" / "config.plist"
    if not config_path.exists():
        raise EngineError("build", "A EFI não foi gerada (config.plist ausente).")

    validation = _run_ocvalidate(ctx, config_path)
    return {
        "plan": summary,
        "efi_dir": str(output_dir / "EFI"),
        "config": _config_summary(config_path),
        "validation": validation,
        "opencore": _opencore_version(ocpe),
    }


def _ensure_ocvalidate_download(ctx: TaskContext, ocpe) -> None:
    """Sem ocvalidate guardado, força o novo download do OpenCorePkg para obtê-lo."""
    if (Path(ctx.workspace) / "bin" / "ocvalidate.exe").exists():
        return
    history_file = Path(ocpe.o.download_history_file)
    if not history_file.exists():
        return
    try:
        history = json.loads(history_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(history, list):
        history = [item for item in history if item.get("product_name") != "OpenCorePkg"]
        history_file.write_text(json.dumps(history, indent=4), encoding="utf-8")


def _opencore_version(ocpe) -> str | None:
    try:
        history = json.loads(Path(ocpe.o.download_history_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for item in history:
        if item.get("product_name") == "OpenCorePkg":
            match = re.search(r"OpenCore-(\d+\.\d+\.\d+)", item.get("url", ""))
            return match.group(1) if match else item.get("id")
    return None


def _run_ocvalidate(ctx: TaskContext, config_path: Path) -> dict:
    executable = Path(ctx.workspace) / "bin" / "ocvalidate.exe"
    if not executable.exists():
        return {"ran": False, "ok": None, "output": "ocvalidate não disponível."}
    ctx.stage("Validando o config.plist com o ocvalidate")
    completed = subprocess.run(
        [str(executable), str(config_path)], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    output = (completed.stdout + completed.stderr).strip()
    return {"ran": True, "ok": completed.returncode == 0, "output": output}


def _config_summary(config_path: Path) -> dict:
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    generic = config.get("PlatformInfo", {}).get("Generic", {})
    nvram = config.get("NVRAM", {}).get("Add", {}).get("7C436110-AB2A-4BBB-A880-FE41995C9F82", {})
    return {
        "smbios": {
            "model": generic.get("SystemProductName"),
            "serial": generic.get("SystemSerialNumber"),
            "mlb": generic.get("MLB"),
            "uuid": generic.get("SystemUUID"),
            "rom": generic.get("ROM").hex().upper() if isinstance(generic.get("ROM"), bytes) else generic.get("ROM"),
        },
        "boot_args": nvram.get("boot-args", ""),
        "kexts": [
            {"bundle": item.get("BundlePath"), "enabled": bool(item.get("Enabled"))}
            for item in config.get("Kernel", {}).get("Add", [])
        ],
        "ssdts": [item.get("Path") for item in config.get("ACPI", {}).get("Add", []) if item.get("Enabled")],
        "drivers": [item.get("Path") for item in config.get("UEFI", {}).get("Drivers", []) if item.get("Enabled")],
        "secure_boot_model": config.get("Misc", {}).get("Security", {}).get("SecureBootModel"),
    }


def selftest(ctx: TaskContext) -> dict:
    ocs, _ = load(ctx, allow_iasl_download=False)
    return {
        "macos_versions": _macos_catalog(ocs),
        "kexts": len(ocs.kext_data.kexts),
        "acpi_patches": len(ocs.acpi_patch_data.patches),
    }
