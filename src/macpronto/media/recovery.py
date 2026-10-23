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
import shutil
import threading
import time
from collections.abc import Callable
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from macpronto import paths
from macpronto.net import DownloadCancelled, download
from macpronto.tasks import UserFacingError

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


class RecoveryError(UserFacingError):
    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("recovery", message, details)


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


def _read_cache(folder: Path) -> dict | None:
    meta_file = folder / "meta.json"
    if not meta_file.exists():
        return None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        dmg, chunklist = folder / meta["image"], folder / meta["chunklist"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        log.warning("Registro do cache do macOS Recovery ilegível (%s): %s", meta_file, exc)
        return None
    if not (dmg.exists() and chunklist.exists()):
        log.warning("Cache do macOS Recovery incompleto em %s", folder)
        return None
    return {**meta, "dmg": str(dmg), "chunklist_path": str(chunklist)}


def _safe_name(product: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in product) or "imagem"


def _download_into_cache(folder: Path, info: dict, darwin: int, previous: dict | None, progress, cancel) -> dict:
    """Baixa numa pasta à parte e só troca o cache depois de verificado."""
    staging = folder / f"novo-{_safe_name(info['product'])}"
    for leftover in folder.glob("novo-*"):  # downloads interrompidos de outras versões
        if leftover != staging and leftover.is_dir():
            shutil.rmtree(leftover, ignore_errors=True)
    image_name = Path(urlparse(info["image_url"]).path).name or "BaseSystem.dmg"
    chunklist_name = Path(urlparse(info["chunklist_url"]).path).name or "BaseSystem.chunklist"

    def report(done: int, total: int) -> None:
        if progress:
            progress(done, total, "Baixando")

    started = time.monotonic()
    download(
        info["chunklist_url"],
        staging / chunklist_name,
        headers=_headers(info["chunklist_url"], info["chunklist_token"]),
        cancel=cancel,
    )
    download(
        info["image_url"],
        staging / image_name,
        headers=_headers(info["image_url"], info["image_token"]),
        progress=report,
        cancel=cancel,
    )
    verify(staging / image_name, staging / chunklist_name, progress, cancel)
    size = (staging / image_name).stat().st_size
    log.info(
        "macOS Recovery %s baixado e verificado: %s, %.0f MB em %.0f s",
        darwin,
        info["product"],
        size / 1024**2,
        time.monotonic() - started,
    )

    if previous is not None:
        for name in (previous.get("image"), previous.get("chunklist")):
            if name:
                (folder / name).unlink(missing_ok=True)
    for name in (image_name, chunklist_name):
        (staging / name).replace(folder / name)
    shutil.rmtree(staging, ignore_errors=True)

    meta = {
        "darwin": darwin,
        "product": info["product"],
        "image": image_name,
        "chunklist": chunklist_name,
        "size": size,
        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {**meta, "dmg": str(folder / image_name), "chunklist_path": str(folder / chunklist_name)}


def ensure(
    darwin: int,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
    force: bool = False,
    status: Callable[[str], None] | None = None,
) -> dict:
    """Garante o macOS Recovery da versão no cache, baixado e verificado.

    Se já houver um no computador, pergunta à Apple qual é o atual: se for o mesmo,
    usa o do computador; se a Apple tiver um mais novo, baixa o novo. Sem internet
    (ou se a Apple não responder), usa o do computador.
    """
    folder = cache_folder(darwin)
    cached = None if force else _read_cache(folder)
    info = None

    if cached is not None:
        try:
            info = image_info(darwin)
        except RecoveryError as exc:
            log.warning("Sem resposta da Apple (%s); usando o macOS Recovery do computador.", exc.message)
        if info is None or info["product"] == cached["product"]:
            if status:
                status("Conferindo o macOS Recovery salvo no computador")
            try:
                verify(Path(cached["dmg"]), Path(cached["chunklist_path"]), progress, cancel)
            except RecoveryError as exc:
                log.warning("O macOS Recovery do computador está corrompido (%s); baixando de novo.", exc.message)
            else:
                log.info(
                    "macOS Recovery %s do computador (produto %s, baixado em %s)%s",
                    darwin,
                    cached["product"],
                    cached.get("downloaded_at", "?"),
                    "" if info else "; não deu para conferir na Apple se há outro mais novo",
                )
                return {**cached, "cached": True, "replaced": None}
        else:
            log.info(
                "A Apple tem um macOS Recovery mais novo para a versão %s: %s (no computador: %s).",
                darwin,
                info["product"],
                cached["product"],
            )

    if info is None:
        info = image_info(darwin)
    if status:
        status("Baixando a versão mais nova do macOS Recovery" if cached else "Baixando o macOS Recovery da Apple")
    result = _download_into_cache(folder, info, darwin, cached, progress, cancel)
    return {**result, "cached": False, "replaced": cached["product"] if cached else None}


def cached_images() -> list[dict]:
    """macOS Recovery guardados no computador, para mostrar e limpar."""
    root = paths.cache_dir() / "recovery"
    found = []
    for folder in sorted(root.glob("*")) if root.exists() else []:
        meta = _read_cache(folder) if folder.is_dir() else None
        if meta is not None:
            size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
            found.append(
                {
                    "darwin": meta.get("darwin"),
                    "product": meta.get("product"),
                    "size": size,
                    "downloaded_at": meta.get("downloaded_at"),
                }
            )
    return found


def clear_cache() -> int:
    """Apaga todos os macOS Recovery guardados. Devolve quantos bytes foram liberados."""
    root = paths.cache_dir() / "recovery"
    if not root.exists():
        return 0
    freed = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    shutil.rmtree(root, ignore_errors=True)
    log.info("Cache do macOS Recovery apagado (%.0f MB)", freed / 1024**2)
    return freed
