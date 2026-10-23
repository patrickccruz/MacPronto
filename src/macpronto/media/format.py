"""Formatação do pendrive (GPT + FAT32). Exige administrador.

Em etapas separadas, porque o Windows demora alguns segundos para montar o volume
de uma partição recém-criada (sobretudo em pendrives GPT). Se o "format" vier logo
depois do "create partition" no mesmo script, o diskpart falha com
"Nenhum volume foi selecionado":

1. diskpart: desmonta, tira a proteção de gravação, apaga, converte e cria a partição;
2. espera o volume da partição aparecer (com "rescan" se demorar);
3. diskpart: seleciona a partição, formata em FAT32 e atribui uma letra;
   se falhar, tenta pelo PowerShell (Format-Volume).

Em GPT a partição nasce com o atributo "sem letra de unidade": assim o Windows não
monta uma unidade vazia (RAW) no meio do processo e o Explorer não abre a pergunta
"Você precisa formatar o disco na unidade X:". O atributo sai depois de formatar.

Se nada disso der certo em GPT, repete tudo em MBR, que todo firmware UEFI também lê.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

from macpronto import winutil
from macpronto.media import disks
from macpronto.tasks import UserFacingError

log = logging.getLogger(__name__)

LABEL = "MACPRONTO"
# O diskpart só formata FAT32 até 32 GB; 16 GB sobram para o macOS Recovery, a EFI e o guia.
MAX_PARTITION_MB = 16 * 1024
CREATE_NO_WINDOW = 0x08000000
VOLUME_WAIT_SECONDS = 40
RESCAN_AFTER_SECONDS = 10
LETTER_WAIT_SECONDS = 15
GPT_BASIC_DATA = "{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}"
GPT_NO_DRIVE_LETTER = "0x8000000000000000"
STYLES = ("gpt", "mbr")


class FormatError(UserFacingError):
    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("format", message, details)


def partition_size_mb(size_bytes: int) -> int:
    available = size_bytes // 1024**2 - 64  # margem para as estruturas GPT
    return max(1024, min(MAX_PARTITION_MB, available))


def _check_number(number: int) -> None:
    if not isinstance(number, int) or isinstance(number, bool) or number < 0:
        raise ValueError("Número de disco inválido.")


def prepare_script(number: int, size_bytes: int, style: str = "gpt", letters: list[str] | None = None) -> str:
    """Etapa 1: libera o disco, apaga, converte e cria a partição."""
    _check_number(number)
    if style not in STYLES:
        raise ValueError(f"Esquema de partição inválido: {style}")
    lines = []
    # Desmonta os volumes atuais do pendrive para nada ficar preso (Explorer, antivírus)
    for letter in letters or []:
        if len(letter) == 1 and letter.isalpha():
            lines += [f"select volume {letter.upper()}", "remove all dismount noerr"]
    lines += [
        f"select disk {number}",
        "attributes disk clear readonly noerr",
        "online disk noerr",
        "clean",
        # Pendrives que já eram GPT continuam GPT depois do clean, e o convert gpt
        # falha neles ("não está formatado em MBR"); com noerr o script segue.
        f"convert {style} noerr",
        f"create partition primary size={partition_size_mb(size_bytes)}",
    ]
    if style == "gpt":
        lines.append(f"gpt attributes={GPT_NO_DRIVE_LETTER}")
    return "\n".join([*lines, "exit", ""])


def format_script(number: int, partition: int, style: str = "gpt", label: str = LABEL) -> str:
    """Etapa 2: com o volume já montado, formata em FAT32 e atribui uma letra."""
    _check_number(number)
    _check_number(partition)
    lines = [f"select disk {number}", f"select partition {partition}", f'format fs=fat32 quick label="{label}"']
    if style == "gpt":
        lines.append("gpt attributes=0x0000000000000000")
    return "\n".join([*lines, "assign noerr", "exit", ""])


def _decode(raw: bytes) -> str:
    # O diskpart escreve na página de código OEM do console (cp850 no Windows em português)
    try:
        return raw.decode("oem", errors="replace")
    except LookupError:
        return raw.decode("cp850", errors="replace")


def _run_diskpart(script: str, step: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="ascii") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    log.info("diskpart (%s), script:\n%s", step, script.strip())
    started = time.monotonic()
    try:
        completed = subprocess.run(
            ["diskpart", "/s", str(script_path)], capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=600
        )
    finally:
        script_path.unlink(missing_ok=True)
    output = _decode(completed.stdout).strip()
    elapsed = time.monotonic() - started
    if completed.returncode == 0:
        log.info("diskpart (%s) concluído em %.1f s. Saída:\n%s", step, elapsed, output)
    else:
        log.error(
            "diskpart (%s) falhou com o código %s em %.1f s. Saída:\n%s", step, completed.returncode, elapsed, output
        )
    return completed.returncode, output


def _partitions(number: int) -> list[dict]:
    """Partições do disco, com o estado do volume de cada uma."""
    import pythoncom  # type: ignore[import-not-found]
    import wmi  # type: ignore[import-not-found]

    pythoncom.CoInitialize()
    storage = wmi.WMI(namespace="root/Microsoft/Windows/Storage")
    found = []
    for partition in storage.query(f"SELECT * FROM MSFT_Partition WHERE DiskNumber = {int(number)}"):
        paths = [str(p) for p in (partition.AccessPaths or [])]
        found.append(
            {
                "number": int(partition.PartitionNumber),
                "size": int(partition.Size or 0),
                "gpt_type": str(partition.GptType or "").lower(),
                "has_volume": any(p.startswith("\\\\?\\Volume{") for p in paths),
                "letter": disks._letter(partition.DriveLetter),  # noqa: SLF001
            }
        )
    return found


def describe_partitions(number: int) -> str:
    """Resumo das partições do disco, para o registro."""
    try:
        return json.dumps(_partitions(number), ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 - só para o registro
        return f"indisponível ({exc})"


def pick_data_partition(partitions: list[dict]) -> dict | None:
    """A partição de dados: em GPT o Windows pode criar também uma reservada (MSR), que é ignorada."""
    candidates = [p for p in partitions if not p["gpt_type"] or p["gpt_type"] == GPT_BASIC_DATA] or partitions
    return max(candidates, key=lambda p: p["size"]) if candidates else None


def _wait_for_volume(number: int) -> dict | None:
    started = time.monotonic()
    rescanned = False
    partition = None
    while time.monotonic() - started < VOLUME_WAIT_SECONDS:
        partition = pick_data_partition(_partitions(number))
        if partition and partition["has_volume"]:
            log.info("Volume da partição %s montado em %.1f s", partition["number"], time.monotonic() - started)
            return partition
        if not rescanned and time.monotonic() - started > RESCAN_AFTER_SECONDS:
            log.warning("O volume ainda não apareceu; pedindo ao Windows para reler os discos (rescan).")
            _run_diskpart("rescan\nexit\n", "reler os discos")
            rescanned = True
        time.sleep(1)
    log.warning("O volume não apareceu em %s s. Partições: %s", VOLUME_WAIT_SECONDS, describe_partitions(number))
    return partition


def _powershell(script: str, step: str) -> tuple[int, str]:
    log.info("PowerShell (%s):\n%s", step, script)
    completed = winutil.run_hidden(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "$ErrorActionPreference = 'Stop'; " + script],
        capture_output=True,
        timeout=600,
    )
    output = _decode(completed.stdout + completed.stderr).strip()
    if completed.returncode == 0:
        log.info("PowerShell (%s) concluído. Saída: %s", step, output or "(vazia)")
    else:
        log.error("PowerShell (%s) falhou com o código %s. Saída:\n%s", step, completed.returncode, output)
    return completed.returncode, output


def _assign_script(number: int, partition: int) -> str:
    """Tira o atributo "sem letra" e atribui uma letra, se ainda não houver."""
    target = f"-DiskNumber {int(number)} -PartitionNumber {int(partition)}"
    return (
        f"try {{ Set-Partition {target} -NoDefaultDriveLetter $false }} catch {{ }}; "
        f"$p = Get-Partition {target}; "
        "if (-not $p.DriveLetter -or $p.DriveLetter -eq [char]0) { $p | Add-PartitionAccessPath -AssignDriveLetter }"
    )


def _format_with_powershell(number: int, partition: int) -> tuple[int, str]:
    target = f"-DiskNumber {int(number)} -PartitionNumber {int(partition)}"
    script = (
        f"Get-Partition {target} | Format-Volume -FileSystem FAT32 -NewFileSystemLabel '{LABEL}' -Force -Confirm:$false"
        f" | Out-Null; {_assign_script(number, partition)}"
    )
    return _powershell(script, "formatar com Format-Volume")


def _wait_for_letter(number: int) -> str | None:
    deadline = time.monotonic() + LETTER_WAIT_SECONDS
    while time.monotonic() < deadline:
        for disk in disks.list_disks():
            if disk["number"] == number and disk["letters"]:
                return disk["letters"][0]
        time.sleep(1)
    return None


def _attempt(number: int, size_bytes: int, style: str, letters: list[str]) -> str:
    """Uma tentativa completa (apagar, particionar, formatar) num esquema de partição."""
    code, output = _run_diskpart(
        prepare_script(number, size_bytes, style, letters), f"apagar e criar a partição {style.upper()}"
    )
    if code != 0:
        raise FormatError(
            f"O diskpart não conseguiu apagar e particionar o pendrive (código {code}).",
            output[-2000:],
        )
    log.info("Partições depois de criar: %s", describe_partitions(number))

    partition = _wait_for_volume(number)
    if partition is None:
        raise FormatError("A partição do pendrive não apareceu depois de criada.", describe_partitions(number))

    code, output = _run_diskpart(format_script(number, partition["number"], style), "formatar em FAT32")
    if code != 0:
        log.warning("O diskpart não formatou; tentando pelo PowerShell.")
        time.sleep(2)
        ps_code, ps_output = _format_with_powershell(number, partition["number"])
        if ps_code != 0:
            raise FormatError(
                "O pendrive foi apagado, mas não foi possível formatá-lo em FAT32.",
                f"diskpart:\n{output[-1500:]}\n\nPowerShell:\n{ps_output[-1500:]}\n\n"
                f"Partições: {describe_partitions(number)}",
            )

    letter = _wait_for_letter(number)
    if letter is None:
        log.warning("O pendrive foi formatado, mas ficou sem letra; atribuindo pelo PowerShell.")
        _powershell(_assign_script(number, partition["number"]), "atribuir a letra")
        letter = _wait_for_letter(number)
    if letter is None:
        raise FormatError(
            "O pendrive foi formatado, mas o Windows não atribuiu uma letra de unidade.", describe_partitions(number)
        )
    return letter


def format_disk(number: int, unique_id: str, size_bytes: int) -> str:
    """Apaga o disco e devolve a letra da unidade criada.

    Confere de novo a identidade do disco imediatamente antes de cada tentativa.
    """
    if not winutil.is_admin():
        raise FormatError("Formatar o pendrive exige administrador. Reabra o MacPronto como administrador.")

    errors: list[tuple[str, FormatError]] = []
    for style in STYLES:
        disk = disks.find_disk(number, unique_id, size_bytes)
        log.warning(
            "Formatando o pendrive em %s: disco %s, %s, %s GB, %s, partições %s, unidades %s. Antes: %s",
            style.upper(),
            number,
            disk["model"],
            disk["size_gb"],
            disk["bus"],
            disk.get("partition_style") or "?",
            ", ".join(f"{letter}:" for letter in disk["letters"]) or "nenhuma",
            describe_partitions(number),
        )
        try:
            letter = _attempt(number, size_bytes, style, disk["letters"])
        except FormatError as exc:
            errors.append((style, exc))
            if style != STYLES[-1]:
                log.warning("Não deu certo em %s (%s). Tentando de novo em MBR.", style.upper(), exc.message)
            continue
        log.info(
            "Pendrive formatado em %s: unidade %s:. Partições: %s", style.upper(), letter, describe_partitions(number)
        )
        return letter

    raise FormatError(
        f"{errors[-1][1].message} Desconecte o pendrive, conecte em outra porta e tente de novo, ou use outro pendrive.",
        "\n\n".join(f"[{style.upper()}] {exc.message}\n{exc.details or ''}" for style, exc in errors),
    )
