"""Coleta de hardware com o Hardware Sniffer. Roda dentro do worker."""

from __future__ import annotations

import tempfile

from macpronto.engine.errors import EngineError
from macpronto.engine.worker import TaskContext

STEP_LABELS = {
    "Gathering PnP devices": "Listando dispositivos",
    "Gathering motherboard information": "Placa-mãe",
    "Gathering BIOS information": "BIOS",
    "Gathering CPU information": "Processador",
    "Gathering GPU information": "Vídeo",
    "Gathering monitor information": "Monitores",
    "Gathering network information": "Rede e Wi-Fi",
    "Gathering sound information": "Áudio",
    "Gathering USB controllers": "Controladoras USB",
    "Gathering input devices": "Teclado, mouse e touchpad",
    "Gathering storage controllers": "Armazenamento",
    "Gathering biometric information": "Biometria",
    "Gathering bluetooth information": "Bluetooth",
    "Gathering sd controller information": "Leitor de cartão",
    "Gathering system devices": "Dispositivos do sistema",
}


def run(ctx: TaskContext) -> dict:
    from Scripts import utils  # type: ignore[import-not-found]

    def progress_bar(self, title, steps, current_step_index, done=False):
        if done:
            ctx.progress(len(steps), len(steps), "Coleta concluída", force=True)
            return
        step = steps[current_step_index]
        ctx.progress(current_step_index, len(steps), STEP_LABELS.get(step, step), force=True)

    def exit_program(self):
        raise EngineError("sniffer-exit", "O Hardware Sniffer encerrou a coleta inesperadamente.")

    utils.Utils.request_input = lambda self, prompt="": ""
    utils.Utils.head = lambda self, text=None, width=68, resize=True: None
    utils.Utils.adjust_window_size = lambda self, content="": None
    utils.Utils.progress_bar = progress_bar
    utils.Utils.exit_program = exit_program

    import HardwareSniffer  # type: ignore[import-not-found]

    ctx.stage("Coletando informações do hardware")
    sniffer = HardwareSniffer.HardwareSniffer(tempfile.mkdtemp(prefix="macpronto_hs_"), rich_format=False)
    try:
        sniffer.hardware_info.hardware_collector()
    except EngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EngineError("sniffer", f"Falha ao coletar o hardware: {exc}") from exc

    ctx.stage("Lendo informações complementares")
    from macpronto.scanner import extras

    try:
        extra_info = extras.collect()
    except Exception as exc:  # noqa: BLE001 - os dados extras são opcionais
        ctx.log("warning", f"Informações complementares indisponíveis: {exc}")
        extra_info = {}

    return {"report": sniffer.hardware_info.result, "extras": extra_info}
