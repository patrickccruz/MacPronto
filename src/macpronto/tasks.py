"""Tarefas longas disparadas pela interface, com eventos de progresso e cancelamento."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any

from macpronto.engine import EngineError, EngineEvent, TaskCancelled
from macpronto.net import DownloadCancelled

log = logging.getLogger(__name__)

Emitter = Callable[[dict], None]


class UserFacingError(Exception):
    """Erro com mensagem pronta para o usuário."""

    def __init__(self, code: str, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class TaskReporter:
    """Envia o andamento de uma tarefa para a interface."""

    def __init__(self, task_id: str, emit: Emitter, cancel: threading.Event) -> None:
        self.task_id = task_id
        self._emit = emit
        self.cancel = cancel
        self._last_progress = 0.0

    def _send(self, kind: str, data: dict) -> None:
        try:
            self._emit({"taskId": self.task_id, "kind": kind, "data": data})
        except Exception:  # noqa: BLE001 - a janela pode ter sido fechada
            log.debug("Falha ao enviar evento %s", kind, exc_info=True)

    def stage(self, title: str) -> None:
        log.info("[%s] %s", self.task_id, title)
        self._send("stage", {"title": title})

    def progress(self, current: float, total: float, label: str = "", force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_progress < 0.15 and (not total or current < total):
            return
        self._last_progress = now
        self._send("progress", {"current": current, "total": total, "label": label})

    def log(self, level: str, message: str) -> None:
        self._send("log", {"level": level, "message": message})

    def engine_event(self, event: EngineEvent) -> None:
        if event.kind == "stage":
            self.stage(event.data.get("title", ""))
        elif event.kind == "progress":
            self.progress(event.data.get("current", 0), event.data.get("total", 0), event.data.get("label", ""))
        elif event.kind == "log" and event.data.get("level") in ("info", "warning", "error"):
            self.log(event.data["level"], event.data.get("message", ""))

    def check_cancelled(self) -> None:
        if self.cancel.is_set():
            raise TaskCancelled(self.task_id)


class TaskManager:
    def __init__(self, emit: Emitter) -> None:
        self._emit = emit
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        # Tarefas do motor que usam a mesma área de trabalho não podem rodar ao mesmo tempo.
        self.engine_lock = threading.Lock()

    def run(self, task_id: str, function: Callable[[TaskReporter], Any]) -> dict:
        cancel = threading.Event()
        with self._lock:
            self._cancels[task_id] = cancel
        reporter = TaskReporter(task_id, self._emit, cancel)
        try:
            return ok(function(reporter))
        except (TaskCancelled, DownloadCancelled):
            return failure("cancelled", "Operação cancelada.")
        except EngineError as exc:
            log.error("Tarefa %s falhou: %s %s", task_id, exc.code, exc.message)
            if exc.details:
                log.debug(exc.details)
            return failure(exc.code, exc.message, exc.details)
        except UserFacingError as exc:
            log.error("Tarefa %s: %s", task_id, exc.message)
            return failure(exc.code, exc.message, exc.details)
        except ValueError as exc:
            log.error("Tarefa %s: %s", task_id, exc)
            return failure("invalid", str(exc))
        except Exception as exc:  # noqa: BLE001 - nenhum erro pode travar a interface
            log.exception("Erro inesperado na tarefa %s", task_id)
            return failure("unexpected", f"Erro inesperado: {exc}", traceback.format_exc())
        finally:
            with self._lock:
                self._cancels.pop(task_id, None)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            event = self._cancels.get(task_id)
        if event is None:
            return False
        event.set()
        return True

    def active(self, prefix: str = "") -> list[str]:
        """Tarefas em andamento (opcionalmente só as que começam com ``prefix``)."""
        with self._lock:
            return [task_id for task_id in self._cancels if task_id.startswith(prefix)]

    def cancel_all(self) -> None:
        with self._lock:
            events = list(self._cancels.values())
        for event in events:
            event.set()


def ok(data: Any = None) -> dict:
    return {"ok": True, "data": data}


def failure(code: str, message: str, details: str | None = None) -> dict:
    return {"ok": False, "error": {"code": code, "message": message, "details": details}}


def guarded(function: Callable[..., Any]) -> Callable[..., dict]:
    """Envolve chamadas rápidas da API no mesmo formato {ok, data | error}."""

    def wrapper(*args, **kwargs):
        try:
            return ok(function(*args, **kwargs))
        except UserFacingError as exc:
            return failure(exc.code, exc.message, exc.details)
        except EngineError as exc:
            return failure(exc.code, exc.message, exc.details)
        except FileNotFoundError as exc:
            return failure("not-found", f"Não encontrado: {exc}")
        except ValueError as exc:
            return failure("invalid", str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro em %s", function.__name__)
            return failure("unexpected", f"Erro inesperado: {exc}", traceback.format_exc())

    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper
