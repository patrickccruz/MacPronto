"""Cria o pendrive de instalação.

Ordem pensada para não apagar o pendrive à toa:
1. confere o disco escolhido;
2. baixa e verifica o macOS Recovery (antes de formatar);
3. confere o disco de novo e formata (GPT + FAT32);
4. copia o Recovery, a EFI, a EFI definitiva (para o disco interno), o guia e, com o
   Wi-Fi Intel pelo itlwm, o HeliPort (o macOS instalado ainda não tem internet para baixá-lo);
5. confere a cópia do Recovery com o chunklist da Apple.
"""

from __future__ import annotations

import logging
import os
import plistlib
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from macpronto import __version__, net, paths
from macpronto.efi import service as efi_service
from macpronto.media import disks, recovery
from macpronto.media import format as formatter
from macpronto.net import DownloadCancelled

log = logging.getLogger(__name__)

RECOVERY_DIR = "com.apple.recovery.boot"
FINAL_EFI_DIR = "EFI-definitiva"
COPY_CHUNK = 4 * 1024 * 1024
HELIPORT_URL = "https://github.com/OpenIntelWireless/HeliPort/releases/latest/download/HeliPort.dmg"
HELIPORT_MAX_AGE = 30 * 24 * 3600  # segundos; depois disso tenta baixar uma versão mais nova

FINAL_EFI_NOTE = (
    "EFI definitiva, para o disco interno.\n\n"
    "Quando o macOS estiver instalado e funcionando, copie a pasta EFI daqui para a partição EFI do disco\n"
    "interno. O passo a passo está no guia (Pós-instalação) e no arquivo AJUDA-IA.md.\n\n"
    "Diferenças para a EFI da raiz do pendrive: sem o modo detalhado (-v), então o boot mostra o logo da\n"
    "Apple, e com o menu do OpenCore escondido (aperte Esc logo depois de ligar para ver o menu).\n"
    "Se você mudar alguma coisa na EFI do pendrive (kexts, config.plist), faça a mesma mudança aqui antes\n"
    "de copiar. Guarde o pendrive: ele é o pendrive de emergência.\n"
)


class Reporter(Protocol):
    cancel: threading.Event

    def stage(self, title: str) -> None: ...

    def progress(self, current: float, total: float, label: str = "", force: bool = False) -> None: ...


def _check(reporter: Reporter) -> None:
    if reporter.cancel.is_set():
        raise DownloadCancelled("pendrive")


def _copy_file(source: Path, target: Path, on_bytes: Callable[[int], None], cancel: threading.Event) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, target.open("wb") as writer:
        while True:
            if cancel.is_set():
                raise DownloadCancelled(str(source))
            block = reader.read(COPY_CHUNK)
            if not block:
                break
            writer.write(block)
            on_bytes(len(block))
        # Garante que os dados chegaram ao pendrive (e não só ao cache do Windows)
        writer.flush()
        os.fsync(writer.fileno())


def _copy_tree(source: Path, target: Path, reporter: Reporter, label: str) -> None:
    files = [f for f in source.rglob("*") if f.is_file()]
    total = sum(f.stat().st_size for f in files)
    done = 0

    def advance(count: int) -> None:
        nonlocal done
        done += count
        reporter.progress(done, total, label)

    for file in files:
        _copy_file(file, target / file.relative_to(source), advance, reporter.cancel)


def _enabled_kexts(config_path: Path) -> set[str]:
    with config_path.open("rb") as handle:
        config = plistlib.load(handle)
    return {e.get("BundlePath") for e in config.get("Kernel", {}).get("Add", []) if e.get("Enabled")}


def heliport(reporter: Reporter) -> Path | None:
    """HeliPort.dmg salvo no computador; baixa de novo quando passa de 30 dias. Sem internet, usa o salvo."""
    cached = paths.cache_dir() / "heliport" / "HeliPort.dmg"
    if not (cached.exists() and time.time() - cached.stat().st_mtime < HELIPORT_MAX_AGE):
        try:
            net.download(
                HELIPORT_URL,
                cached,
                progress=lambda done, total: reporter.progress(done, total or done, "Baixando o HeliPort"),
                cancel=reporter.cancel,
            )
        except net.DownloadError as exc:
            log.warning("HeliPort não baixado (o pendrive segue sem ele): %s", exc)
    return cached if cached.exists() else None


def create(
    reporter: Reporter,
    disk_number: int,
    unique_id: str,
    size_bytes: int,
    darwin: int,
    efi_dir: Path,
    extra_folder: Path | None = None,
    keyboard: str = "abnt2",
) -> dict:
    """Formata o pendrive e grava tudo. ``extra_folder`` vai para X:\\MacPronto (guia, laudo)."""
    if not (efi_dir / "OC" / "OpenCore.efi").exists():
        raise ValueError("A pasta EFI está incompleta. Monte a EFI de novo.")

    reporter.stage("Conferindo o pendrive")
    disk = disks.find_disk(disk_number, unique_id, size_bytes)
    _check(reporter)

    reporter.stage("Conferindo o macOS Recovery na Apple")
    image = recovery.ensure(darwin, progress=reporter.progress, cancel=reporter.cancel, status=reporter.stage)
    _check(reporter)

    reporter.stage("Apagando e formatando o pendrive")
    letter = formatter.format_disk(disk_number, unique_id, size_bytes)
    root = Path(f"{letter}:\\")
    _check(reporter)

    reporter.stage("Copiando o macOS Recovery")
    dmg, chunklist = Path(image["dmg"]), Path(image["chunklist_path"])
    target_dir = root / RECOVERY_DIR
    total = dmg.stat().st_size + chunklist.stat().st_size
    copied = 0

    def advance(count: int) -> None:
        nonlocal copied
        copied += count
        reporter.progress(copied, total, "Copiando")

    _copy_file(chunklist, target_dir / chunklist.name, advance, reporter.cancel)
    _copy_file(dmg, target_dir / dmg.name, advance, reporter.cancel)

    reporter.stage("Copiando a EFI")
    _copy_tree(efi_dir, root / "EFI", reporter, "Copiando a EFI")
    # Vale também para EFIs montadas antes dos ajustes (por exemplo, reaproveitadas de outra sessão)
    efi_service.apply_installer_options(root / "EFI" / "OC" / "config.plist")
    efi_service.apply_hardware_fixes(root / "EFI", keyboard)

    reporter.stage("Copiando a EFI definitiva (para o disco interno)")
    final_dir = root / "MacPronto" / FINAL_EFI_DIR
    _copy_tree(root / "EFI", final_dir / "EFI", reporter, "Copiando a EFI definitiva")
    efi_service.apply_final_options(final_dir / "EFI" / "OC" / "config.plist")
    (final_dir / "LEIA-ME.txt").write_text(FINAL_EFI_NOTE, encoding="utf-8")

    has_heliport = False
    if "itlwm.kext" in _enabled_kexts(root / "EFI" / "OC" / "config.plist"):
        reporter.stage("Baixando o HeliPort (Wi-Fi Intel)")
        dmg_heliport = heliport(reporter)
        if dmg_heliport is not None:
            _copy_file(dmg_heliport, root / "MacPronto" / "HeliPort.dmg", lambda _count: None, reporter.cancel)
            has_heliport = True

    if extra_folder is not None and extra_folder.is_dir():
        reporter.stage("Copiando o guia")
        _copy_tree(extra_folder, root / "MacPronto", reporter, "Copiando o guia")

    reporter.stage("Conferindo o pendrive")
    recovery.verify(target_dir / dmg.name, target_dir / chunklist.name, reporter.progress, reporter.cancel)
    for required in (
        "EFI/BOOT/BOOTx64.efi",
        "EFI/OC/OpenCore.efi",
        "EFI/OC/config.plist",
        f"MacPronto/{FINAL_EFI_DIR}/EFI/OC/config.plist",
    ):
        if not (root / required).exists():
            raise formatter.FormatError(f"Arquivo ausente no pendrive: {required}")

    summary = (
        f"Pendrive criado pelo MacPronto {__version__} em {datetime.now():%d/%m/%Y %H:%M}.\n"
        f"macOS Recovery: produto {image['product']} (Darwin {darwin}).\n"
        "Para instalar, siga o guia em MacPronto\\Guia.pdf ou Guia.html (o QR code do MacPronto baixa os PDFs no celular).\n"
        "Com dúvida ou problema, abra uma IA (Claude, ChatGPT, Gemini), envie o arquivo MacPronto\\AJUDA-IA.md\n"
        "(ou AJUDA-IA.pdf) e descreva o que aconteceu.\n"
        f"Depois de instalar: a pasta MacPronto\\{FINAL_EFI_DIR} vai para o disco interno (veja o guia).\n"
        "Primeira vez no Mac? Abra MacPronto\\Bem-vindo-ao-Mac.pdf (atalhos e diferenças para o Windows).\n"
    )
    if has_heliport:
        summary += "Wi-Fi: instale o MacPronto\\HeliPort.dmg no macOS (copie o HeliPort para Aplicativos).\n"
    (root / "MacPronto").mkdir(exist_ok=True)
    (root / "MacPronto" / "LEIA-ME.txt").write_text(summary, encoding="utf-8")

    log.info("Pendrive pronto na unidade %s:", letter)
    return {
        "letter": letter,
        "disk": disk,
        "product": image["product"],
        "darwin": darwin,
        "recovery_cached": image["cached"],
        "recovery_replaced": image.get("replaced"),
        "verified": True,
        "final_efi": True,
        "heliport": has_heliport,
    }
