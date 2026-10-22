"""Extração das tabelas ACPI com o acpidump oficial do ACPICA."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from macpronto import paths
from macpronto.net import download, file_sha256

log = logging.getLogger(__name__)

# Mesma versão usada pelo Hardware Sniffer, com o hash conferido.
ACPIDUMP_URL = "https://github.com/acpica/acpica/releases/download/R2024_12_12/acpidump.exe"
ACPIDUMP_SHA256 = "9f54227f9f7dccbf1fbc652f05d342e7525d5de0861905bfef05254064a07fd4"
CREATE_NO_WINDOW = 0x08000000


class AcpiDumpError(Exception):
    pass


def acpidump_path() -> Path:
    return paths.cache_dir() / "tools" / "acpidump.exe"


def ensure_acpidump() -> Path:
    target = acpidump_path()
    if target.exists() and file_sha256(target) == ACPIDUMP_SHA256:
        return target
    log.info("Baixando acpidump.exe do ACPICA")
    download(ACPIDUMP_URL, target, sha256=ACPIDUMP_SHA256)
    return target


def dump_tables(destination: Path) -> list[str]:
    """Extrai as tabelas para ``destination`` como arquivos .aml e devolve os nomes."""
    if sys.platform != "win32":
        raise AcpiDumpError("A extração de tabelas ACPI só funciona no Windows.")

    executable = ensure_acpidump()
    destination.mkdir(parents=True, exist_ok=True)
    for old in destination.glob("*.aml"):
        old.unlink()

    completed = subprocess.run(
        [str(executable), "-b"],
        cwd=destination,
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    if completed.returncode != 0:
        raise AcpiDumpError((completed.stderr or completed.stdout or "acpidump falhou").strip())

    tables = []
    for item in sorted(destination.glob("*.dat")):
        target = item.with_suffix(".aml")
        item.replace(target)
        tables.append(target.name)

    if not any(name.lower().startswith("dsdt") for name in tables):
        raise AcpiDumpError("A tabela DSDT não foi encontrada na extração.")
    log.info("%d tabelas ACPI extraídas para %s", len(tables), destination)
    return tables
