"""Cópia gravável do código de terceiros.

As ferramentas da comunidade gravam downloads (iasl, macserial, kexts) na
própria pasta. A cópia em %LOCALAPPDATA% mantém a pasta do programa intacta e
preserva esses caches entre execuções.

A origem da cópia é a versão travada em third_party/ ou, se o usuário atualizou
a base de regras e o autoteste passou, a versão baixada em engine-updates/.
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


def updates_dir() -> Path:
    folder = paths.data_dir() / "engine-updates"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _active_file() -> Path:
    return updates_dir() / "active.json"


def active_updates() -> dict:
    try:
        return json.loads(_active_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Registro de atualizações ilegível, usando as versões travadas: %s", exc)
        return {}


def set_active_update(component: str, info: dict | None) -> None:
    with _lock:
        data = active_updates()
        if info is None:
            data.pop(component, None)
        else:
            data[component] = info
        _active_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def active_source(component: str) -> tuple[Path, str, str]:
    """(pasta de origem, commit, "travada" ou "atualizada")."""
    update = active_updates().get(component)
    if update and Path(update.get("path", "")).is_dir():
        return Path(update["path"]), update["commit"], "atualizada"
    source = paths.third_party_dir() / component
    if not source.is_dir():
        raise FileNotFoundError(f"Componente {component} não encontrado em {source}")
    commit = pinned_versions().get(component, {}).get("commit", "desconhecido")
    return source, commit, "travada"


def source_dir(component: str) -> Path:
    return active_source(component)[0]


def ensure(component: str) -> Path:
    """Garante que a cópia do componente ativo está atualizada e devolve o caminho."""
    source, commit, _origin = active_source(component)
    return ensure_from(source, component, commit)


def ensure_from(source: Path, name: str, commit: str) -> Path:
    """Sincroniza ``source`` para engine/<name>, se a versão mudou."""
    with _lock:
        target = paths.engine_dir() / name
        expected = f"{commit}:{__version__}"
        stamp = target / STAMP_FILE

        if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == expected:
            return target

        log.info("Preparando %s (%s) em %s", name, commit[:12], target)
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
