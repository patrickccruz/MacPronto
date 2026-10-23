"""Atualização automática pelas versões publicadas no GitHub.

Cada versão publicada leva, além do instalador, o arquivo ``macpronto-update.json``
(gerado por scripts/build.py) com a versão, o nome, o tamanho e o SHA-256 do instalador.

Para descobrir as versões, o MacPronto lê o feed público de versões
(github.com/<repositório>/releases.atom), que não tem o limite de 60 consultas por hora
da API do GitHub. Com ETag, a consulta repetida a cada minuto quase não trafega dados.

Quem está numa versão de teste (ex.: 0.1.0-beta.1) recebe as de teste e as estáveis;
quem está numa estável recebe só as estáveis.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

from macpronto import __version__, net, paths, settings

log = logging.getLogger(__name__)

REPOSITORY = "patrickccruz/MacPronto"
MANIFEST = "macpronto-update.json"
CHECK_INTERVAL = 60  # segundos
MAX_INTERVAL = 15 * 60  # espera máxima depois de falhas seguidas
MISSING_MANIFEST_RETRY = 5 * 60  # versão recém-criada pode ainda estar recebendo os arquivos
MAX_FEED_BYTES = 2 * 1024 * 1024

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")
_TAG_LINK = re.compile(r'href="[^"]*/releases/tag/([^"?#]+)"')


def base_url() -> str:
    # MACPRONTO_UPDATE_URL só existe para testar a atualização com um servidor local
    return (os.environ.get("MACPRONTO_UPDATE_URL") or f"https://github.com/{REPOSITORY}").rstrip("/")


def version_key(text: str) -> tuple | None:
    """Chave de comparação no padrão SemVer: 1.0.0-beta.2 < 1.0.0-rc.1 < 1.0.0."""
    match = _VERSION.match(text.strip())
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    core = (int(major), int(minor), int(patch))
    if not pre:
        return (core, 1, ())
    parts = tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in pre.split("."))
    return (core, 0, parts)


def is_prerelease(text: str) -> bool:
    key = version_key(text)
    return key is not None and key[1] == 0


def is_newer(candidate: str, current: str) -> bool:
    new, old = version_key(candidate), version_key(current)
    return new is not None and old is not None and new > old


def parse_feed(content: str) -> list[str]:
    """Tags das versões no feed Atom do GitHub, na ordem do feed."""
    tags: list[str] = []
    for raw in _TAG_LINK.findall(content):
        tag = unquote(raw)
        if tag not in tags:
            tags.append(tag)
    return tags


def parse_manifest(data: dict, tag: str, base: str) -> dict:
    """Confere o manifesto de uma versão. Levanta ValueError se algo não bater."""
    version = str(data.get("version", ""))
    if version_key(version) is None or version_key(version) != version_key(tag):
        raise ValueError(f"versão {version!r} não confere com a tag {tag!r}")
    installer = data.get("installer") or {}
    name = str(installer.get("name", ""))
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.exe", name):
        raise ValueError(f"nome de instalador inválido: {name!r}")
    sha256 = str(installer.get("sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("SHA-256 inválido")
    size = int(installer.get("size", 0))
    if not 1024**2 <= size <= 1024**3:
        raise ValueError(f"tamanho improvável: {size}")
    return {
        "version": version,
        "tag": tag,
        "name": name,
        "size": size,
        "sha256": sha256,
        "url": f"{base}/releases/download/{quote(tag)}/{quote(name)}",
        "page": f"{base}/releases/tag/{quote(tag)}",
        "notes": str(data.get("notes") or "")[:12000],
        "published_at": data.get("published_at"),
    }


def _get(url: str, etag: str | None = None, timeout: float = 20) -> tuple[int, bytes, str | None]:
    headers = {"User-Agent": net.USER_AGENT, "Cache-Control": "no-cache"}
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            return response.status, response.read(MAX_FEED_BYTES), response.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return 304, b"", etag
        raise


def is_installed() -> bool:
    """True quando roda a partir de uma instalação (Inno Setup), e não da cópia portátil ou do código."""
    return paths.is_frozen() and (paths.executable().parent / "unins000.exe").exists()


def cleanup(current: str = __version__) -> None:
    """Apaga instaladores baixados de versões que já estão instaladas."""
    folder = paths.data_dir() / "updates"
    if not folder.exists():
        return
    for item in folder.iterdir():
        if item.is_dir() and not is_newer(item.name, current):
            shutil.rmtree(item, ignore_errors=True)
            log.info("Instalador antigo apagado: %s", item.name)


def launch_installer(installer: Path, version: str) -> None:
    """Roda o instalador em modo silencioso. Ele fecha o MacPronto, instala e abre a versão nova."""
    if sys.platform != "win32":
        raise RuntimeError("A atualização automática só funciona no Windows.")
    import ctypes

    install_log = paths.logs_dir() / f"atualizacao-{version}.log"
    parameters = subprocess.list2cmdline(
        [
            "/SILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/FORCECLOSEAPPLICATIONS",
            "/ATUALIZACAO",  # o instalador abre o MacPronto de novo no fim
            f"/LOG={install_log}",
        ]
    )
    log.warning("Iniciando o instalador do MacPronto %s: %s %s", version, installer, parameters)
    # ShellExecute (e não CreateProcess): se o MacPronto estiver sem administrador, o Windows pede a elevação
    result = ctypes.windll.shell32.ShellExecuteW(None, "open", str(installer), parameters, str(installer.parent), 1)
    if int(result) <= 32:
        raise RuntimeError(f"O Windows não abriu o instalador (código {int(result)}).")


class Updater:
    """Verifica novas versões a cada minuto, numa thread à parte."""

    def __init__(self, notify: Callable[[dict], None], current: str = __version__) -> None:
        self._notify = notify
        self.current = current
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._etag: str | None = None
        self._tags: list[str] = []
        self._manifests: dict[str, dict] = {}
        self._missing: dict[str, float] = {}  # tag -> quando faltou o manifesto
        self._failures = 0
        self._announced: str | None = None
        self.available: dict | None = None
        self.last_check: str | None = None
        self.error: str | None = None
        self.checking = False

    # ------------------------------------------------------------------ ciclo

    def start(self) -> None:
        if self._thread is not None:
            return
        cleanup(self.current)
        self._thread = threading.Thread(target=self._loop, name="atualizacoes", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        """Antecipa a próxima verificação (ex.: o usuário religou a verificação automática)."""
        self._wake.set()

    def _loop(self) -> None:
        self._stop.wait(5)  # deixa a janela abrir primeiro
        while not self._stop.is_set():
            if settings.load().get("auto_update", True):
                self.check()
            interval = min(MAX_INTERVAL, CHECK_INTERVAL * 2 ** min(self._failures, 4))
            self._wake.wait(interval)
            self._wake.clear()

    # ------------------------------------------------------------------ consulta

    def status(self) -> dict:
        return {
            "current": self.current,
            "enabled": bool(settings.load().get("auto_update", True)),
            "installed": is_installed(),
            "checking": self.checking,
            "last_check": self.last_check,
            "error": self.error,
            "available": self.available,
        }

    def check(self) -> dict:
        """Consulta o GitHub agora. Nunca levanta exceção: o erro fica em ``error``."""
        if not self._lock.acquire(blocking=False):
            return self.status()  # já há uma consulta em andamento
        previous_error = self.error
        self.checking = True
        try:
            status, body, etag = _get(f"{base_url()}/releases.atom", self._etag)
            if status != 304:
                self._tags = parse_feed(body.decode("utf-8", errors="replace"))
                self._etag = etag
            self.available = self._newest()
            self.error = None
            self._failures = 0
        except urllib.error.HTTPError as exc:
            self._failures += 1
            if exc.code == 404:
                self.error = (
                    "O endereço das atualizações não está acessível (repositório privado ou sem versões publicadas)."
                )
            elif exc.code in (403, 429):
                self.error = "O GitHub pediu um intervalo entre as consultas; o MacPronto tenta de novo mais tarde."
            else:
                self.error = f"O GitHub respondeu com erro {exc.code}."
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self._failures += 1
            self.error = "Sem conexão com o GitHub para verificar atualizações."
            log.debug("Falha ao verificar atualizações: %s", exc)
        finally:
            self.checking = False
            self.last_check = datetime.now().isoformat(timespec="seconds")
            self._lock.release()

        if self.error and self.error != previous_error:
            log.warning("Verificação de atualizações: %s", self.error)
        elif previous_error and not self.error:
            log.info("Verificação de atualizações voltou a funcionar")
        if self.available and self.available["version"] != self._announced:
            self._announced = self.available["version"]
            log.info("Nova versão do MacPronto disponível: %s (instalada: %s)", self._announced, self.current)
            self._notify(self.status())
        return self.status()

    def _newest(self) -> dict | None:
        allow_pre = is_prerelease(self.current)
        candidates = [
            tag for tag in self._tags if is_newer(tag, self.current) and (allow_pre or not is_prerelease(tag))
        ]
        candidates.sort(key=version_key, reverse=True)
        for tag in candidates:
            manifest = self._manifest(tag)
            if manifest is not None:
                return manifest
        return None

    def _manifest(self, tag: str) -> dict | None:
        if tag in self._manifests:
            return self._manifests[tag]
        missing_since = self._missing.get(tag)
        if missing_since is not None and time.monotonic() - missing_since < MISSING_MANIFEST_RETRY:
            return None
        base = base_url()
        try:
            _, body, _ = _get(f"{base}/releases/download/{quote(tag)}/{MANIFEST}")
            manifest = parse_manifest(json.loads(body), tag, base)
        except urllib.error.HTTPError as exc:
            log.info("A versão %s ainda não tem o %s (HTTP %s)", tag, MANIFEST, exc.code)
            self._missing[tag] = time.monotonic()
            return None
        except (ValueError, json.JSONDecodeError) as exc:
            log.warning("Manifesto da versão %s inválido: %s", tag, exc)
            self._missing[tag] = time.monotonic()
            return None
        self._manifests[tag] = manifest
        return manifest

    # ------------------------------------------------------------------ instalação

    def download(self, info: dict, progress=None, cancel: threading.Event | None = None) -> Path:
        """Baixa o instalador e confere o tamanho e o SHA-256 do manifesto."""
        target = paths.data_dir() / "updates" / info["version"] / info["name"]
        if target.exists() and target.stat().st_size == info["size"] and net.file_sha256(target) == info["sha256"]:
            log.info("Instalador do MacPronto %s já baixado", info["version"])
            return target
        started = time.monotonic()
        net.download(info["url"], target, sha256=info["sha256"], progress=progress, cancel=cancel)
        if target.stat().st_size != info["size"]:
            target.unlink(missing_ok=True)
            raise ValueError("O instalador baixado não tem o tamanho esperado.")
        log.info(
            "Instalador do MacPronto %s baixado e conferido (%.1f MB em %.0f s)",
            info["version"],
            info["size"] / 1024**2,
            time.monotonic() - started,
        )
        return target
