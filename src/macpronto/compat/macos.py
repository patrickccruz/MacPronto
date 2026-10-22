"""Versões do macOS cobertas pelo MacPronto e a política de recomendação."""

from __future__ import annotations

from dataclasses import dataclass

# Sequoia é a versão padrão: a mais estável entre as que ainda recebem atualizações.
DEFAULT_DARWIN = 24
# Tahoe (26) é a última versão com suporte a processadores Intel.
LAST_INTEL_DARWIN = 25


@dataclass(frozen=True)
class MacOSVersion:
    darwin: int
    name: str
    version: str
    year: int
    note: str = ""

    @property
    def label(self) -> str:
        return f"macOS {self.name} {self.version}"

    def to_dict(self) -> dict:
        return {
            "darwin": self.darwin,
            "name": self.name,
            "version": self.version,
            "year": self.year,
            "label": self.label,
            "note": self.note,
        }


VERSIONS = (
    MacOSVersion(17, "High Sierra", "10.13", 2017, "Última com drivers NVIDIA Web para placas Maxwell e Pascal."),
    MacOSVersion(18, "Mojave", "10.14", 2018, "Última com suporte a aplicativos de 32 bits."),
    MacOSVersion(19, "Catalina", "10.15", 2019),
    MacOSVersion(20, "Big Sur", "11", 2020),
    MacOSVersion(21, "Monterey", "12", 2021, "Última com suporte nativo a placas NVIDIA Kepler."),
    MacOSVersion(22, "Ventura", "13", 2022, "Exige AVX2 no processador, ou o kext CryptexFixup."),
    MacOSVersion(23, "Sonoma", "14", 2023, "Removeu o suporte nativo a Wi-Fi Broadcom antigo."),
    MacOSVersion(24, "Sequoia", "15", 2024, "Versão padrão do MacPronto: a mais estável para Hackintosh."),
    MacOSVersion(25, "Tahoe", "26", 2025, "Última versão com suporte a Intel. Removeu o AppleHDA (áudio)."),
)

BY_DARWIN = {item.darwin: item for item in VERSIONS}


def major(version: str | int | None) -> int | None:
    """'24.99.99' -> 24."""
    if version is None or version == "":
        return None
    return int(str(version).split(".")[0])


def get(darwin: int | None) -> MacOSVersion | None:
    return BY_DARWIN.get(darwin) if darwin is not None else None


def label(darwin: int | None) -> str:
    item = get(darwin)
    return item.label if item else "versão desconhecida"


def in_range(darwin: int, version_range: dict | None) -> bool:
    if not version_range:
        return False
    low, high = major(version_range.get("min")), major(version_range.get("max"))
    return low is not None and high is not None and low <= darwin <= high


def recommend(native: dict | None, suggested: str | None) -> tuple[int | None, str]:
    """Escolhe a versão recomendada e explica o motivo.

    A sugestão do OpCore Simplify já considera limites de estabilidade do vídeo
    (por exemplo, Skylake até o Monterey). Por cima dela, o MacPronto prefere o
    Sequoia quando o hardware alcança versões mais novas.
    """
    if not native:
        return None, "Nenhuma versão é compatível com este computador."

    low, high = major(native["min"]), major(native["max"])
    ocs_choice = major(suggested) if suggested else high
    ocs_choice = min(max(ocs_choice, low), high)

    if ocs_choice > DEFAULT_DARWIN and low <= DEFAULT_DARWIN:
        return DEFAULT_DARWIN, (
            f"O hardware aceita até o {label(high)}, mas o Sequoia é a versão mais estável para Hackintosh."
        )
    if ocs_choice < high:
        return ocs_choice, (
            f"O {label(ocs_choice)} é a versão mais estável para este vídeo, embora a máquina alcance o {label(high)}."
        )
    if ocs_choice < DEFAULT_DARWIN:
        return ocs_choice, "É a versão mais nova que este hardware suporta sem patches."
    return ocs_choice, "É a versão indicada para este hardware."
