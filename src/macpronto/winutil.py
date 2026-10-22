"""Funções específicas do Windows."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

log = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000


def is_admin() -> bool:
    if sys.platform != "win32":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def open_path(path: str | Path) -> None:
    """Abre uma pasta no Explorer ou um arquivo no programa padrão."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(str(target))
    if sys.platform == "win32":
        os.startfile(str(target))  # noqa: S606 - caminho controlado pelo programa
    else:
        subprocess.run(["xdg-open", str(target)], check=False)


def reveal(path: str | Path) -> None:
    """Abre o Explorer com o arquivo selecionado."""
    target = Path(path)
    if sys.platform == "win32" and target.exists():
        subprocess.run(["explorer", "/select,", str(target)], check=False)
    else:
        open_path(target.parent)


def open_url(url: str) -> None:
    if not url.startswith(("https://", "http://")):
        raise ValueError("Somente endereços http(s) podem ser abertos.")
    webbrowser.open(url)


def run_hidden(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    if sys.platform == "win32":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
    return subprocess.run(args, **kwargs)
