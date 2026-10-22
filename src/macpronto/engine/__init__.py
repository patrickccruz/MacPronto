"""Motor: executa as ferramentas da comunidade em um processo separado.

O OpCore Simplify, o Hardware Sniffer e o USBToolBox foram escritos como
programas de terminal interativos, gravam arquivos na própria pasta e usam o
mesmo nome de pacote (``Scripts``). Por isso cada tarefa roda num subprocesso
(o "worker"), a partir de uma cópia gravável do código em
``%LOCALAPPDATA%\\MacPronto\\engine``, e conversa com o MacPronto por linhas JSON.
"""

from macpronto.engine.errors import EngineError, TaskCancelled
from macpronto.engine.runner import EngineEvent, run_task

__all__ = ["EngineError", "EngineEvent", "TaskCancelled", "run_task"]
