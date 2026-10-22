"""Localização dos recursos do programa e das pastas de dados do usuário."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from macpronto import APP_NAME


def is_frozen() -> bool:
    """True quando roda como executável gerado pelo Nuitka."""
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Pasta que contém third_party/ e a interface compilada."""
    override = os.environ.get("MACPRONTO_RESOURCE_DIR")
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys.argv[0]).resolve().parent
    # src/macpronto/paths.py -> raiz do repositório
    return Path(__file__).resolve().parents[2]


def third_party_dir() -> Path:
    return resource_root() / "third_party"


def frontend_dir() -> Path:
    root = resource_root()
    bundled = root / "ui"
    if bundled.is_dir():
        return bundled
    return root / "frontend" / "dist"


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Dados internos: motor, cache de downloads e registros."""
    override = os.environ.get("MACPRONTO_DATA_DIR")
    if override:
        return _ensure(Path(override))
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return _ensure(Path(base) / APP_NAME)


def engine_dir() -> Path:
    return _ensure(data_dir() / "engine")


def cache_dir() -> Path:
    return _ensure(data_dir() / "cache")


def logs_dir() -> Path:
    return _ensure(data_dir() / "logs")


def documents_dir() -> Path:
    """Pasta visível ao usuário com laudos, EFI e guias."""
    override = os.environ.get("MACPRONTO_OUTPUT_DIR")
    if override:
        return _ensure(Path(override))
    documents = None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buffer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 (Documentos), respeita pastas redirecionadas para o OneDrive
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
                documents = Path(buffer.value)
        except Exception:  # noqa: BLE001 - qualquer falha cai no padrão abaixo
            documents = None
    if documents is None:
        documents = Path.home() / "Documents"
    return _ensure(documents / APP_NAME)


def scans_dir() -> Path:
    return _ensure(documents_dir() / "Diagnosticos")


def efi_output_dir() -> Path:
    return _ensure(documents_dir() / "EFI")


def guides_dir() -> Path:
    return _ensure(documents_dir() / "Guias")
