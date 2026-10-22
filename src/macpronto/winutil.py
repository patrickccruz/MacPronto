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


def relaunch_as_admin() -> bool:
    """Abre uma nova cópia do MacPronto como administrador (aviso do UAC). True se o Windows aceitou."""
    if sys.platform != "win32":
        return False
    from macpronto import paths

    if paths.is_frozen():
        executable, parameters = sys.executable, ""
    else:
        executable, parameters = sys.executable, "-m macpronto"
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, os.getcwd(), 1)
    return int(result) > 32


def eject(letter: str) -> bool:
    """Ejeta a unidade com segurança pelo Shell do Windows."""
    if sys.platform != "win32" or not letter:
        return False
    script = f"(New-Object -ComObject Shell.Application).Namespace(17).ParseName('{letter[0]}:').InvokeVerb('Eject')"
    completed = run_hidden(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    return completed.returncode == 0


def run_hidden(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    if sys.platform == "win32":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
    return subprocess.run(args, **kwargs)
