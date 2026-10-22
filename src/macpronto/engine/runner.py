"""Lado do MacPronto: inicia o worker e repassa os eventos."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from macpronto import paths
from macpronto.engine import workspace
from macpronto.engine.errors import EngineError, TaskCancelled

log = logging.getLogger(__name__)

# Componente de terceiros que cada tarefa precisa na área de trabalho.
TASK_COMPONENTS = {
    "sniff": "Hardware-Sniffer",
    "analyze": "OpCore-Simplify",
    "plan": "OpCore-Simplify",
    "build": "OpCore-Simplify",
    "selftest": "OpCore-Simplify",
}

CREATE_NO_WINDOW = 0x08000000


@dataclass
class EngineEvent:
    kind: str
    data: dict = field(default_factory=dict)


def worker_command() -> list[str]:
    if paths.is_frozen():
        return [sys.executable, "--engine"]
    return [sys.executable, "-m", "macpronto", "--engine"]


def _worker_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if not paths.is_frozen():
        src = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    return env


def run_task(
    task: str,
    params: dict | None = None,
    on_event: Callable[[EngineEvent], None] | None = None,
    cancel: threading.Event | None = None,
    timeout: float | None = None,
) -> dict:
    """Executa uma tarefa no worker e devolve o resultado.

    Levanta EngineError se a tarefa falhar e TaskCancelled se ``cancel`` for acionado.
    """
    component = TASK_COMPONENTS.get(task)
    workspace_dir = str(workspace.ensure(component)) if component else None
    request = {"task": task, "params": params or {}, "workspace": workspace_dir}

    log.debug("Iniciando worker para a tarefa %s", task)
    process = subprocess.Popen(
        worker_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_worker_env(),
        creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    stderr_lines: list[str] = []

    def read_stderr() -> None:
        assert process.stderr is not None
        for raw in process.stderr:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                stderr_lines.append(line)
                log.debug("[worker %s stderr] %s", task, line)

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()

    watcher_done = threading.Event()

    def watch_cancel() -> None:
        while not watcher_done.wait(0.25):
            if cancel is not None and cancel.is_set() and process.poll() is None:
                log.info("Cancelando tarefa %s", task)
                _kill_tree(process.pid)
                return

    watcher = threading.Thread(target=watch_cancel, daemon=True)
    watcher.start()

    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps(request).encode("utf-8"))
    process.stdin.close()

    result: dict | None = None
    error: dict | None = None
    try:
        for raw in process.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                log.debug("[worker %s] %s", task, line)
                continue
            kind = message.pop("event", "log")
            if kind == "result":
                result = message.get("data", {})
            elif kind == "error":
                error = message
            else:
                if kind == "log":
                    _log_worker_line(task, message)
                if on_event is not None:
                    on_event(EngineEvent(kind, message))
        process.wait(timeout=timeout)
    finally:
        watcher_done.set()
        stderr_thread.join(timeout=2)

    if cancel is not None and cancel.is_set():
        raise TaskCancelled(task)
    if error is not None:
        raise EngineError(error.get("code", "engine"), error.get("message", "Erro no motor"), error.get("details"))
    if result is None:
        details = "\n".join(stderr_lines[-30:])
        raise EngineError("worker-crash", f"O motor terminou sem resposta (código {process.returncode}).", details)
    return result


def _log_worker_line(task: str, message: dict) -> None:
    level = getattr(logging, str(message.get("level", "debug")).upper(), logging.DEBUG)
    log.log(level, "[%s] %s", task, message.get("message", ""))


def _kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        os.kill(pid, 9)
