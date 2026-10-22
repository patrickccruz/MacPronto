"""Cópia gravável do código de terceiros.

As ferramentas da comunidade gravam downloads (iasl, macserial, kexts) na
própria pasta. A cópia em %LOCALAPPDATA% mantém a pasta do programa intacta e
preserva esses caches entre execuções.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path

from macpronto import __version__, paths

log = logging.getLogger(__name__)

STAMP_FILE = ".macpronto-stamp"
_lock = threading.Lock()


def pinned_versions() -> dict:
    versions_file = paths.third_party_dir() / "VERSIONS.json"
    return json.loads(versions_file.read_text(encoding="utf-8"))


def source_dir(component: str) -> Path:
    path = paths.third_party_dir() / component
    if not path.is_dir():
        raise FileNotFoundError(f"Componente {component} não encontrado em {path}")
    return path


def ensure(component: str) -> Path:
    """Garante que a cópia do componente está atualizada e devolve o caminho."""
    with _lock:
        source = source_dir(component)
        target = paths.engine_dir() / component
        commit = pinned_versions().get(component, {}).get("commit", "desconhecido")
        expected = f"{commit}:{__version__}"
        stamp = target / STAMP_FILE

        if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == expected:
            return target

        log.info("Preparando %s (%s) em %s", component, commit[:12], target)
        _sync(source, target)
        stamp.write_text(expected, encoding="utf-8")
        return target


def _sync(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    source_files = set()
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        source_files.add(relative)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)

    # Remove módulos Python que deixaram de existir na versão nova, sem tocar nos caches baixados.
    for item in target.rglob("*.py"):
        relative = item.relative_to(target)
        if relative not in source_files:
            item.unlink()
    for item in target.rglob("__pycache__"):
        shutil.rmtree(item, ignore_errors=True)
