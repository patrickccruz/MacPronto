"""Lista os discos e decide quais podem virar pendrive de instalação.

Regras de segurança (todas obrigatórias):
- barramento USB;
- não é o disco do sistema nem de boot, não é somente leitura;
- entre 4 GB e 256 GB (HDs externos maiores ficam de fora).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

log = logging.getLogger(__name__)

BUS_USB = 7
MIN_BYTES = 4 * 1000**3
MAX_BYTES = 256 * 1000**3
BUS_NAMES = {7: "USB", 11: "SATA", 17: "NVMe", 8: "RAID", 12: "SD", 13: "MMC", 10: "SAS"}


@dataclass
class Disk:
    number: int
    model: str
    size_bytes: int
    bus: str
    unique_id: str
    system: bool
    boot: bool
    read_only: bool
    letters: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    eligible: bool = False
    reason: str = ""

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / 1000**3, 1)

    def to_dict(self) -> dict:
        return {**asdict(self), "size_gb": self.size_gb}


def evaluate(disk: Disk, bus_type: int) -> Disk:
    """Preenche eligible e reason. Separado da leitura para poder ser testado."""
    if disk.system or disk.boot:
        disk.reason = "É o disco do Windows."
    elif bus_type != BUS_USB:
        disk.reason = f"Não é um disco USB ({disk.bus})."
    elif disk.read_only:
        disk.reason = "Está protegido contra gravação."
    elif disk.size_bytes < MIN_BYTES:
        disk.reason = "Pequeno demais: use um pendrive de 4 GB ou mais (16 GB recomendado)."
    elif disk.size_bytes > MAX_BYTES:
        disk.reason = "Grande demais para ser um pendrive. Se for um HD externo, use outro dispositivo."
    else:
        disk.eligible = True
    return disk


def _letter(value) -> str | None:
    if value in (None, 0, "", "\x00"):
        return None
    if isinstance(value, int):
        return chr(value)
    return str(value)[0]


def list_disks() -> list[dict]:
    import pythoncom  # type: ignore[import-not-found]
    import wmi  # type: ignore[import-not-found]

    pythoncom.CoInitialize()
    storage = wmi.WMI(namespace="root/Microsoft/Windows/Storage")
    letters: dict[int, list[str]] = {}
    for partition in storage.MSFT_Partition():
        letter = _letter(partition.DriveLetter)
        if letter:
            letters.setdefault(int(partition.DiskNumber), []).append(letter)
    labels = {}
    for volume in storage.MSFT_Volume():
        letter = _letter(volume.DriveLetter)
        if letter:
            labels[letter] = volume.FileSystemLabel or ""

    disks = []
    for raw in storage.MSFT_Disk():
        number = int(raw.Number)
        bus_type = int(raw.BusType or 0)
        disk_letters = sorted(letters.get(number, []))
        disk = Disk(
            number=number,
            model=(raw.FriendlyName or raw.Model or "Disco").strip(),
            size_bytes=int(raw.Size or 0),
            bus=BUS_NAMES.get(bus_type, f"tipo {bus_type}"),
            unique_id=str(raw.UniqueId or ""),
            system=bool(raw.IsSystem),
            boot=bool(raw.IsBoot),
            read_only=bool(raw.IsReadOnly),
            letters=disk_letters,
            labels=[labels.get(letter, "") for letter in disk_letters],
        )
        disks.append(evaluate(disk, bus_type).to_dict())
    return sorted(disks, key=lambda d: (not d["eligible"], d["number"]))


def find_disk(number: int, unique_id: str, size_bytes: int) -> dict:
    """Relê os discos e confirma que o escolhido ainda é o mesmo e ainda é elegível."""
    for disk in list_disks():
        if disk["number"] != number:
            continue
        if disk["unique_id"] != unique_id or disk["size_bytes"] != size_bytes:
            raise ValueError("O pendrive mudou desde a escolha (foi trocado de porta?). Escolha de novo.")
        if not disk["eligible"]:
            raise ValueError(f"Este disco não pode ser usado: {disk['reason']}")
        return disk
    raise ValueError("O pendrive escolhido não está mais conectado.")
