"""Configuração dos registros (logs) do MacPronto."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from collections import deque
from datetime import datetime

from macpronto import paths

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_memory_handler: MemoryHandler | None = None


class MemoryHandler(logging.Handler):
    """Mantém as últimas linhas em memória para a tela de registros."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        self.records: deque[dict] = deque(maxlen=capacity)
        self.counter = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.counter += 1
        self.records.append(
            {
                "id": self.counter,
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname.lower(),
                "source": record.name,
                "message": record.getMessage(),
            }
        )

    def since(self, last_id: int) -> list[dict]:
        return [item for item in self.records if item["id"] > last_id]


def setup(debug: bool = False) -> logging.Logger:
    global _memory_handler

    root = logging.getLogger()
    if _memory_handler is not None:
        return logging.getLogger("macpronto")

    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(LOG_FORMAT)

    log_file = paths.logs_dir() / f"macpronto-{datetime.now():%Y%m%d}.log"
    file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # No executável sem console, sys.stderr pode não existir
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        console.setFormatter(formatter)
        root.addHandler(console)

    _memory_handler = MemoryHandler()
    _memory_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    root.addHandler(_memory_handler)

    # Bibliotecas barulhentas
    for name in ("urllib3", "pywebview", "comtypes"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logger = logging.getLogger("macpronto")
    logger.info("Registros em %s", log_file)
    return logger


def recent(last_id: int = 0) -> list[dict]:
    if _memory_handler is None:
        return []
    return _memory_handler.since(last_id)


def current_log_file() -> str:
    return str(paths.logs_dir() / f"macpronto-{datetime.now():%Y%m%d}.log")
