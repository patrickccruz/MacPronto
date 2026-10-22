"""Preferências do usuário, guardadas em %LOCALAPPDATA%\\MacPronto\\settings.json."""

from __future__ import annotations

import json
import logging
import threading

from macpronto import paths

log = logging.getLogger(__name__)

DEFAULTS = {
    "theme": "system",  # system | light | dark
    "policy_accepted": False,
    "advanced": False,
    "last_scan_id": None,
}

_lock = threading.Lock()


def _file():
    return paths.data_dir() / "settings.json"


def load() -> dict:
    with _lock:
        try:
            stored = json.loads(_file().read_text(encoding="utf-8"))
        except FileNotFoundError:
            stored = {}
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Preferências ilegíveis, usando o padrão: %s", exc)
            stored = {}
    return {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}


def update(changes: dict) -> dict:
    current = load()
    current.update({k: v for k, v in changes.items() if k in DEFAULTS})
    with _lock:
        _file().write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current
