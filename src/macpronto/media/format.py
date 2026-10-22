"""Formatação do pendrive com o diskpart (GPT + FAT32). Exige administrador."""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from pathlib import Path

from macpronto import winutil
from macpronto.media import disks

log = logging.getLogger(__name__)

LABEL = "MACPRONTO"
# O diskpart só formata FAT32 até 32 GB; 16 GB sobram para o macOS Recovery, a EFI e o guia.
MAX_PARTITION_MB = 16 * 1024
CREATE_NO_WINDOW = 0x08000000


class FormatError(Exception):
    pass


def partition_size_mb(size_bytes: int) -> int:
    available = size_bytes // 1024**2 - 64  # margem para as estruturas GPT
    return max(1024, min(MAX_PARTITION_MB, available))


def build_script(number: int, size_bytes: int, label: str = LABEL) -> str:
    if not isinstance(number, int) or number < 0:
        raise ValueError("Número de disco inválido.")
    return "\n".join(
        [
            f"select disk {number}",
            "clean",
            "convert gpt",
            f"create partition primary size={partition_size_mb(size_bytes)}",
            f'format fs=fat32 quick label="{label}"',
            "assign",
            "exit",
            "",
        ]
    )


def format_disk(number: int, unique_id: str, size_bytes: int) -> str:
    """Apaga o disco e devolve a letra da unidade criada.

    Confere de novo a identidade do disco imediatamente antes de chamar o diskpart.
    """
    if not winutil.is_admin():
        raise FormatError("Formatar o pendrive exige administrador. Reabra o MacPronto como administrador.")
    disks.find_disk(number, unique_id, size_bytes)

    script = build_script(number, size_bytes)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="ascii") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    log.warning("Formatando o disco %s (%s bytes) com o diskpart", number, size_bytes)
    try:
        completed = subprocess.run(
            ["diskpart", "/s", str(script_path)],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=600,
        )
    finally:
        script_path.unlink(missing_ok=True)

    # O diskpart escreve na página de código OEM do console (cp850 no Windows em português)
    try:
        output = completed.stdout.decode("oem", errors="replace")
    except LookupError:
        output = completed.stdout.decode("cp850", errors="replace")
    log.debug("Saída do diskpart:\n%s", output)
    if completed.returncode != 0:
        raise FormatError(f"O diskpart falhou (código {completed.returncode}).\n{output.strip()[-800:]}")

    for _ in range(30):
        for disk in disks.list_disks():
            if disk["number"] == number and disk["letters"]:
                return disk["letters"][0]
        time.sleep(1)
    raise FormatError("O pendrive foi formatado, mas o Windows não atribuiu uma letra de unidade.")
