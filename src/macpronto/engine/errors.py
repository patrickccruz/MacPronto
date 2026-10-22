from __future__ import annotations


class EngineError(Exception):
    """Falha de uma tarefa do motor, com um código estável para a interface."""

    def __init__(self, code: str, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class TaskCancelled(Exception):
    """A tarefa foi cancelada pelo usuário."""
