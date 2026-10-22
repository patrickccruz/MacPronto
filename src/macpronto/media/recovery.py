"""Download e verificação do macOS Recovery direto dos servidores da Apple.

Usa as funções do macrecovery.py do OpenCorePkg (third_party/macrecovery) para
abrir a sessão, consultar a imagem e validar o chunklist assinado pela Apple.
O download em si é do MacPronto, com progresso, retomada e cache.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import threading
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from macpronto import paths
from macpronto.net import DownloadCancelled, download

log = logging.getLogger(__name__)

MLB_ZERO = "00000000000000000"

# Board-ID, MLB e tipo de consulta por versão (third_party/macrecovery/recovery_urls.txt)
BOARDS = {
    17: ("Mac-7BA5B2D9E42DDD94", "00000000000J80300", "default"),
    18: ("Mac-7BA5B2DFE22DDD8C", "00000000000KXPG00", "default"),
    19: ("Mac-00BE6ED71E35EB86", MLB_ZERO, "default"),
    20: ("Mac-2BD1B31983FE1663", MLB_ZERO, "default"),
    21: ("Mac-E43C1C25D4880AD6", MLB_ZERO, "default"),
    22: ("Mac-B4831CEBD52A0C4C", MLB_ZERO, "default"),
    23: ("Mac-827FAC58A8FDFA22", MLB_ZERO, "default"),
    24: ("Mac-7BA5B2D9E42DDD94", MLB_ZERO, "default"),
    25: ("Mac-CFF7D910A743CAAF", MLB_ZERO, "latest"),
}

Progress = Callable[[float, float, str], None]


class RecoveryError(Exception):
    pass


@lru_cache(maxsize=1)
def macrecovery():
    source = paths.third_party_dir() / "macrecovery" / "macrecovery.py"
    spec = importlib.util.spec_from_file_location("macpronto_macrecovery", source)
    if spec is None or spec.loader is None:
        raise RecoveryError("macrecovery.py não encontrado.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cache_folder(darwin: int) -> Path:
    folder = paths.cache_dir() / "recovery" / str(darwin)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def image_info(darwin: int) -> dict:
    """Consulta a Apple: devolve o produto e os endereços da imagem e do chunklist."""
    if darwin not in BOARDS:
        raise RecoveryError(f"Versão {darwin} sem macOS Recovery conhecido.")
    board, mlb, os_type = BOARDS[darwin]
    module = macrecovery()
    try:
        session = module.get_session(SimpleNamespace(verbose=False))
        info = module.get_image_info(session, bid=board, mlb=mlb, diag=False, os_type=os_type)
    except SystemExit as exc:  # o macrecovery chama sys.exit em erro HTTP
        raise RecoveryError("Os servidores da Apple recusaram a consulta. Tente de novo em alguns minutos.") from exc
    except Exception as exc:  # noqa: BLE001
        raise RecoveryError(f"Não foi possível consultar os servidores da Apple: {exc}") from exc
    return {
        "product": info[module.INFO_PRODUCT],
        "image_url": info[module.INFO_IMAGE_LINK],
        "image_token": info[module.INFO_IMAGE_SESS],
        "chunklist_url": info[module.INFO_SIGN_LINK],
        "chunklist_token": info[module.INFO_SIGN_SESS],
    }


def _headers(url: str, token: str) -> dict[str, str]:
    return {
        "Host": urlparse(url).hostname or "",
        "User-Agent": "InternetRecovery/1.0",
        "Cookie": f"AssetToken={token}",
    }


def verify(dmg: Path, chunklist: Path, progress: Progress | None = None, cancel: threading.Event | None = None) -> None:
    """Confere a imagem com o chunklist assinado pela Apple. Levanta RecoveryError se não bater."""
    module = macrecovery()
    total = dmg.stat().st_size
    done = 0
    try:
        with dmg.open("rb") as handle:
            for index, (size, digest) in enumerate(module.verify_chunklist(str(chunklist)), 1):
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled(str(dmg))
                chunk = handle.read(size)
                if len(chunk) != size or hashlib.sha256(chunk).digest() != digest:
                    raise RecoveryError(f"O pedaço {index} do macOS Recovery está corrompido.")
                done += size
                if progress:
                    progress(done, total, "Verificando")
            if handle.read(1):
                raise RecoveryError("O macOS Recovery é maior do que o chunklist indica.")
    except AssertionError as exc:
        raise RecoveryError("O chunklist do macOS Recovery é inválido ou não tem a assinatura da Apple.") from exc


def ensure(
    darwin: int,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
    force: bool = False,
) -> dict:
    """Garante o macOS Recovery da versão no cache, baixado e verificado."""
    folder = cache_folder(darwin)
    meta_file = folder / "meta.json"
    if not force and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            dmg, chunklist = folder / meta["image"], folder / meta["chunklist"]
            if dmg.exists() and chunklist.exists():
                verify(dmg, chunklist, progress, cancel)
                log.info("macOS Recovery %s do cache (%s)", darwin, meta.get("product"))
                return {**meta, "dmg": str(dmg), "chunklist_path": str(chunklist), "cached": True}
        except (OSError, json.JSONDecodeError, KeyError, RecoveryError) as exc:
            log.warning("Cache do macOS Recovery inválido, baixando de novo: %s", exc)

    info = image_info(darwin)
    image_name = Path(urlparse(info["image_url"]).path).name or "BaseSystem.dmg"
    chunklist_name = Path(urlparse(info["chunklist_url"]).path).name or "BaseSystem.chunklist"
    chunklist = folder / chunklist_name
    dmg = folder / image_name

    def report(done: int, total: int) -> None:
        if progress:
            progress(done, total, "Baixando")

    download(
        info["chunklist_url"],
        chunklist,
        headers=_headers(info["chunklist_url"], info["chunklist_token"]),
        cancel=cancel,
    )
    download(
        info["image_url"], dmg, headers=_headers(info["image_url"], info["image_token"]), progress=report, cancel=cancel
    )
    verify(dmg, chunklist, progress, cancel)

    meta = {"darwin": darwin, "product": info["product"], "image": image_name, "chunklist": chunklist_name}
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("macOS Recovery %s baixado: %s", darwin, info["product"])
    return {**meta, "dmg": str(dmg), "chunklist_path": str(chunklist), "cached": False}
