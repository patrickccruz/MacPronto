"""Downloads com progresso, retomada simples e verificação de hash."""

from __future__ import annotations

import hashlib
import logging
import ssl
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from macpronto import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"MacPronto/{__version__}"
ProgressCallback = Callable[[int, int], None]


class DownloadError(Exception):
    pass


class DownloadCancelled(Exception):
    pass


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def download(
    url: str,
    target: Path,
    sha256: str | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> Path:
    """Baixa ``url`` para ``target`` de forma atômica (arquivo .part renomeado no fim)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            _download_once(url, partial, progress, cancel, headers)
            if sha256:
                actual = file_sha256(partial)
                if actual.lower() != sha256.lower():
                    partial.unlink(missing_ok=True)
                    raise DownloadError(f"Hash diferente do esperado para {url}")
            partial.replace(target)
            return target
        except DownloadCancelled:
            partial.unlink(missing_ok=True)
            raise
        except Exception as exc:  # noqa: BLE001 - tenta de novo em qualquer falha de rede
            last_error = exc
            log.warning("Falha ao baixar %s (tentativa %d/%d): %s", url, attempt, attempts, exc)
            time.sleep(min(2 * attempt, 6))

    raise DownloadError(f"Não foi possível baixar {url}: {last_error}")


def _download_once(
    url: str,
    partial: Path,
    progress: ProgressCallback | None,
    cancel: threading.Event | None,
    headers: dict[str, str] | None,
) -> None:
    existing = partial.stat().st_size if partial.exists() else 0
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    if existing:
        request_headers["Range"] = f"bytes={existing}-"

    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
        resumed = existing and response.status == 206
        if not resumed:
            existing = 0
        length = int(response.headers.get("Content-Length") or 0)
        total = existing + length if length else 0
        done = existing
        with partial.open("ab" if resumed else "wb") as handle:
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled(url)
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
    if total and done < total:
        raise DownloadError(f"Download incompleto ({done} de {total} bytes)")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
