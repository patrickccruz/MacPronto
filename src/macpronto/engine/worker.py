"""Lado do subprocesso: recebe uma tarefa por stdin e responde com linhas JSON.

Mensagens enviadas ao MacPronto (uma por linha):
    {"event": "log", "level": "...", "message": "..."}
    {"event": "stage", "title": "..."}
    {"event": "progress", "current": n, "total": n, "label": "..."}
    {"event": "result", "data": {...}}
    {"event": "error", "code": "...", "message": "...", "details": "..."}
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path

from macpronto.engine.errors import EngineError

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
DOWNLOAD_PROGRESS = re.compile(r"(\d{1,3})%\s+([\d.]+)/([\d.]+)MB")
CREATE_NO_WINDOW = 0x08000000


class Channel:
    """Canal exclusivo do protocolo, separado da saída padrão que as ferramentas usam."""

    def __init__(self, stream: io.TextIOBase) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def send(self, event: str, **data) -> None:
        payload = json.dumps({"event": event, **data}, ensure_ascii=False, default=_json_default)
        with self._lock:
            self._stream.write(payload + "\n")
            self._stream.flush()


def _json_default(value):
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return repr(value)


class TaskContext:
    def __init__(self, channel: Channel, params: dict, workspace: Path | None) -> None:
        self.channel = channel
        self.params = params
        self.workspace = workspace
        self._last_progress = 0.0
        self.line_hooks: list[Callable[[str], None]] = []

    def log(self, level: str, message: str) -> None:
        self.channel.send("log", level=level, message=message)

    def stage(self, title: str) -> None:
        self.channel.send("stage", title=title)

    def progress(self, current: float, total: float, label: str = "", force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_progress < 0.2 and current < total:
            return
        self._last_progress = now
        self.channel.send("progress", current=current, total=total, label=label)


class CapturedOutput(io.TextIOBase):
    """Substitui sys.stdout: cada linha impressa pelas ferramentas vira um evento de log."""

    def __init__(self, ctx: TaskContext) -> None:
        super().__init__()
        self.ctx = ctx
        self._buffer = ""

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return "utf-8"

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._buffer += text
        while True:
            match = re.search(r"[\r\n]", self._buffer)
            if not match:
                break
            line, self._buffer = self._buffer[: match.start()], self._buffer[match.end() :]
            self._emit(line)
        return len(text)

    def flush(self) -> None:
        pass

    def finish(self) -> None:
        if self._buffer:
            self._emit(self._buffer)
            self._buffer = ""

    def _emit(self, raw: str) -> None:
        line = ANSI_ESCAPE.sub("", raw).rstrip()
        for hook in self.ctx.line_hooks:
            hook(line)
        if not line.strip():
            return
        progress = DOWNLOAD_PROGRESS.search(line)
        if progress:
            done, total = float(progress.group(2)), float(progress.group(3))
            self.ctx.progress(done, total, "download")
            return
        if set(line.strip()) <= set("═║╔╗╚╝─│┌┐└┘ "):
            return
        self.ctx.log("debug", line)


def _hide_child_consoles() -> None:
    """Impede que iasl, macserial etc. abram janelas de console piscando."""
    if sys.platform != "win32":
        return
    original_init = subprocess.Popen.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
        original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = patched_init  # type: ignore[method-assign]

    original_system = os.system

    def patched_system(command: str) -> int:
        if command.strip() in ("cls", "clear"):
            return 0
        return original_system(command)

    os.system = patched_system


def _load_tasks() -> dict[str, Callable[[TaskContext], dict]]:
    from macpronto.engine.tasks import ocs, sniff

    return {
        "sniff": sniff.run,
        "analyze": ocs.analyze,
        "plan": ocs.plan,
        "build": ocs.build,
        "selftest": ocs.selftest,
    }


def main() -> int:
    raw_request = sys.stdin.buffer.read().decode("utf-8")

    # O protocolo usa uma cópia do stdout original; o descritor 1 passa a apontar
    # para o nulo, para que programas filhos não corrompam as mensagens.
    protocol_fd = os.dup(1)
    protocol_stream = os.fdopen(protocol_fd, "w", encoding="utf-8", buffering=1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)

    channel = Channel(protocol_stream)
    try:
        request = json.loads(raw_request)
    except json.JSONDecodeError as exc:
        channel.send("error", code="bad-request", message=f"Pedido inválido: {exc}", details=None)
        return 2

    workspace = Path(request["workspace"]) if request.get("workspace") else None
    ctx = TaskContext(channel, request.get("params") or {}, workspace)
    captured = CapturedOutput(ctx)
    sys.stdout = captured

    _hide_child_consoles()

    if workspace is not None:
        os.chdir(workspace)
        sys.path.insert(0, str(workspace))

    try:
        tasks = _load_tasks()
        handler = tasks.get(request.get("task", ""))
        if handler is None:
            raise EngineError("unknown-task", f"Tarefa desconhecida: {request.get('task')}")
        result = handler(ctx)
        captured.finish()
        channel.send("result", data=result)
        return 0
    except EngineError as exc:
        captured.finish()
        channel.send("error", **exc.to_dict())
        return 1
    except BaseException as exc:  # noqa: BLE001 - qualquer falha precisa chegar à interface
        captured.finish()
        channel.send(
            "error",
            code="unexpected",
            message=f"Erro inesperado no motor: {exc}",
            details=traceback.format_exc(),
        )
        return 1
