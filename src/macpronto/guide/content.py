"""Conteúdo do guia: BIOS por fabricante, instalação, pós-instalação e problemas.

Baseado no guia de instalação do OpenCore da Dortania
(https://dortania.github.io/OpenCore-Install-Guide/), adaptado ao que a EFI do
MacPronto já resolve sozinha.

Os perfis de BIOS ficam em bios_profiles.json. A detecção vai do mais específico
ao mais genérico: linha de produto (ex.: Lenovo ThinkPad), placa-mãe de PC montado,
tipo de BIOS (AMI, Insyde, Phoenix) e, por fim, um perfil genérico com palavras-chave.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

PROFILES_FILE = Path(__file__).resolve().parent / "bios_profiles.json"
CONFIDENCE = {
    "conferido": "Caminhos conferidos numa máquina real ({checked_on}).",
    "documentacao": "Caminhos tirados da documentação do fabricante e de guias da comunidade. Os nomes podem mudar um pouco "
    "conforme o modelo e a versão da BIOS: se não achar, procure pelas palavras-chave.",
    "tipo": "O MacPronto não reconheceu a linha deste computador; os caminhos seguem o tipo de BIOS ({name}). Os nomes "
    "podem mudar bastante: use as palavras-chave.",
    "generico": "O MacPronto não reconheceu a BIOS deste computador. Procure cada ajuste pelas palavras-chave.",
}


@dataclass(frozen=True)
class Profile:
    id: str
    kind: str  # oem (linha de produto), board (placa-mãe), engine (tipo de BIOS) ou generic
    brand: str
    name: str
    bios_key: str
    boot_key: str
    notes: tuple[str, ...] = ()
    # Onde fica cada ajuste no menu (chave do ajuste -> caminho)
    paths: dict[str, str] = field(default_factory=dict)
    # Ajustes que normalmente não aparecem nesta BIOS
    absent: frozenset[str] = frozenset()
    confidence: str = "documentacao"
    checked_on: tuple[str, ...] = ()
    match: dict = field(default_factory=dict)
    # Usa os caminhos do tipo de BIOS da máquina (marcas que trocam de fornecedor de BIOS)
    engine_paths: bool = False

    @property
    def confidence_text(self) -> str:
        return CONFIDENCE[self.confidence].format(name=self.name, checked_on=", ".join(self.checked_on))


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def profiles() -> dict[str, Profile]:
    result = {}
    for raw in _data()["profiles"]:
        result[raw["id"]] = Profile(
            id=raw["id"],
            kind=raw["kind"],
            brand=raw["brand"],
            name=raw["name"],
            bios_key=raw["bios_key"],
            boot_key=raw["boot_key"],
            notes=tuple(raw.get("notes") or ()),
            paths=dict(raw.get("paths") or {}),
            absent=frozenset(raw.get("absent") or ()),
            confidence=raw.get("confidence", "documentacao"),
            checked_on=tuple(raw.get("checked_on") or ()),
            match=dict(raw.get("match") or {}),
            engine_paths=bool(raw.get("engine_paths")),
        )
    return result


def keywords() -> dict[str, list[str]]:
    return _data()["keywords"]


def _has_marker(text: str, markers: list[str]) -> bool:
    # Palavra inteira: "hp" não pode casar com "chipset", nem "ami" com "family"
    return any(re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", text) for marker in markers)


def engine_for(bios_vendor: str) -> Profile:
    """Perfil do tipo de BIOS (AMI, Insyde, Phoenix) ou o genérico."""
    bios = (bios_vendor or "").lower()
    for profile in profiles().values():
        if profile.kind == "engine" and _has_marker(bios, profile.match.get("bios", [])):
            return profile
    return profiles()["generic"]


def detect_profile(
    system_manufacturer: str = "",
    family: str = "",
    model: str = "",
    board_manufacturer: str = "",
    bios_vendor: str = "",
    is_laptop: bool = False,
) -> Profile:
    """Escolhe o perfil de BIOS mais específico para a máquina."""
    system = (system_manufacturer or "").lower()
    line = f" {family or ''} {model or ''} ".lower()
    board = (board_manufacturer or "").lower()

    for profile in profiles().values():
        if profile.kind != "oem" or not _has_marker(system, profile.match.get("manufacturer", [])):
            continue
        form = profile.match.get("form")
        if form == "laptop" and not is_laptop:
            continue
        families = profile.match.get("family")
        if families and not any(item in line for item in families):
            continue
        return resolve(profile, bios_vendor)

    # PC montado: vale a placa-mãe (o fabricante do sistema costuma vir genérico, como "To Be Filled By O.E.M.")
    for candidate in (board, system):
        for profile in profiles().values():
            if profile.kind == "board" and _has_marker(candidate, profile.match.get("board", [])):
                return resolve(profile, bios_vendor)
    return engine_for(bios_vendor)


def resolve(profile: Profile, bios_vendor: str = "") -> Profile:
    """Completa os caminhos com os do tipo de BIOS quando o perfil depende dele."""
    if not profile.engine_paths:
        return profile
    engine = engine_for(bios_vendor)
    return replace(profile, paths={**engine.paths, **profile.paths}, absent=profile.absent | engine.absent)


def profile_by_id(profile_id: str, bios_vendor: str = "") -> Profile:
    profile = profiles().get(profile_id)
    if profile is None:
        raise ValueError(f"Perfil de BIOS desconhecido: {profile_id}")
    return resolve(profile, bios_vendor)


def profile_choices() -> list[dict]:
    """Perfis que o usuário pode escolher à mão na tela do guia."""
    groups = {
        "oem": "Marca e linha",
        "board": "Placa-mãe (PC montado)",
        "engine": "Tipo de BIOS",
        "generic": "Genérico",
    }
    return [{"id": profile.id, "name": profile.name, "group": groups[profile.kind]} for profile in profiles().values()]


def key_table() -> list[dict]:
    """Teclas da BIOS e do menu de boot de todas as marcas, para o fim do guia."""
    return [
        {"name": profile.name, "bios_key": profile.bios_key, "boot_key": profile.boot_key}
        for profile in profiles().values()
        if profile.kind in ("oem", "board")
    ]


# O que fazer quando um ajuste costuma não aparecer na BIOS deste perfil
ABSENT_HINTS = {
    "above4g": "Costuma não aparecer nesta BIOS: siga em frente. Se o boot travar em PCI Configuration, veja Problemas e soluções.",
    "sata": "Costuma não aparecer nesta BIOS. Se o disco interno não aparecer no instalador, veja as observações acima.",
    "vmd": "Costuma não aparecer nesta BIOS. Se o disco interno não aparecer no instalador, veja as observações acima.",
}
DEFAULT_ABSENT_HINT = "Costuma não aparecer nesta BIOS: se não achar, siga em frente."


@dataclass(frozen=True)
class BiosSetting:
    key: str
    title: str
    action: str  # "Desativar", "Ativar", "Ajustar"
    why: str
    optional: bool = False


def bios_settings(cpu_manufacturer: str, has_igpu: bool, requirements: list[str], vmd: bool) -> list[BiosSetting]:
    intel = cpu_manufacturer == "Intel"
    above4g_required = any("Above 4G" in r for r in requirements)
    rebar_required = any("Resizable BAR" in r for r in requirements)
    settings = [
        BiosSetting("secure_boot", "Secure Boot", "Desativar", "O OpenCore não é assinado pela Microsoft."),
        BiosSetting("fast_boot", "Fast Boot", "Desativar", "Com ele, a BIOS pula o pendrive e vai direto ao Windows."),
        BiosSetting("csm", "CSM (modo Legacy)", "Desativar", "A EFI foi feita para o modo UEFI puro."),
        BiosSetting("sata", "Modo SATA", "Ajustar para AHCI", "O macOS não reconhece discos em modo RAID ou RST."),
        BiosSetting(
            "above4g",
            "Above 4G Decoding",
            "Ativar",
            "Necessário para placas de vídeo modernas e para a EFI desta máquina."
            if above4g_required
            else "Ajuda placas de vídeo modernas. Se a opção não existir, siga em frente.",
            optional=not above4g_required,
        ),
        BiosSetting(
            "rebar",
            "Resizable BAR / Smart Access Memory",
            "Desativar",
            "Deixa o macOS instável.",
            optional=not rebar_required,
        ),
        BiosSetting("xhci", "XHCI Hand-off", "Ativar", "Entrega o controle das portas USB ao macOS.", optional=True),
    ]
    if vmd:
        settings.insert(0, BiosSetting("vmd", "Intel VMD", "Desativar", "O macOS não enxerga discos atrás do VMD."))
    if intel:
        settings += [
            BiosSetting(
                "vtd",
                "VT-d",
                "Pode ficar ligado",
                "A EFI já desliga o IOMMU no macOS. Se der problema, desligue.",
                optional=True,
            ),
            BiosSetting(
                "sgx", "Intel SGX", "Desativar", "Não é usado pelo macOS e pode atrapalhar o boot.", optional=True
            ),
            BiosSetting(
                "cfg", "CFG Lock", "Desativar se existir", "Se a opção não aparecer, a EFI já contorna.", optional=True
            ),
        ]
        if has_igpu:
            settings.append(
                BiosSetting(
                    "dvmt",
                    "DVMT Pre-Allocated (memória do vídeo integrado)",
                    "Ajustar para 64 MB ou mais",
                    "O vídeo Intel precisa de pelo menos 64 MB.",
                    optional=True,
                )
            )
    else:
        settings += [
            BiosSetting(
                "iommu", "IOMMU", "Desativar", "Evita travamentos no boot de processadores AMD.", optional=True
            ),
            BiosSetting(
                "svm", "SVM (virtualização)", "Pode ficar ligado", "Só é usado por máquinas virtuais.", optional=True
            ),
        ]
    return settings


INSTALL_STEPS = (
    (
        "Dê boot pelo pendrive",
        "Com o pendrive conectado (de preferência numa porta USB 2 ou na traseira), ligue o computador apertando a tecla do menu de boot "
        "({boot_key}). Escolha o pendrive com o nome UEFI.",
    ),
    (
        "Escolha o instalador no OpenCore",
        'Aparece a tela do OpenCore. Escolha a opção com "macOS Base System" ou "Install macOS" e aperte Enter. Vão passar muitas '
        "linhas de texto: é normal, a EFI liga o modo detalhado (verbose) para ajudar a diagnosticar problemas.",
    ),
    (
        "Apague o disco de destino",
        "No menu de Recuperação, abra o Utilitário de Disco. Clique em Visualizar > Mostrar Todos os Dispositivos, selecione o disco "
        "inteiro (não a partição) onde o macOS vai ficar e clique em Apagar: formato APFS e esquema Mapa de Partição GUID. "
        "Isto apaga o Windows e todos os arquivos desse disco.",
    ),
    (
        "Reinstale o macOS",
        "Feche o Utilitário de Disco, escolha Reinstalar o macOS {macos_name} e siga as telas. O instalador baixa o sistema da Apple: "
        "a internet precisa estar funcionando (cabo de rede é o mais garantido).",
    ),
    (
        "Escolha a entrada certa nas reinicializações",
        'O computador reinicia algumas vezes. Em todas, dê boot pelo pendrive e escolha a entrada "macOS Installer" (ou o nome do '
        "disco) no OpenCore, até aparecer a tela de configuração inicial do macOS.",
    ),
    (
        "Configure o macOS",
        "Siga a configuração inicial normalmente. Se preferir, deixe o login no iCloud para depois de conferir os números de série "
        "(veja a pós-instalação).",
    ),
)

POST_INSTALL = (
    (
        "Copie a EFI para o disco interno",
        "Hoje o macOS só inicia com o pendrive conectado. Para iniciar sem ele, copie a pasta EFI do pendrive para a partição EFI do "
        'disco interno. No Terminal: "sudo diskutil list" para achar a partição EFI do disco interno (por exemplo disk0s1), '
        '"sudo diskutil mount disk0s1" para montá-la, e copie a pasta EFI do pendrive para ela. Depois, escolha esse disco como '
        "primeiro na ordem de boot da BIOS.",
    ),
    (
        "Tire o modo detalhado (opcional)",
        'Para trocar as linhas de texto pela maçã no boot, remova "-v" dos boot-args no config.plist (com o ProperTree, em '
        "NVRAM > Add > 7C436110-AB2A-4BBB-A880-FE41995C9F82 > boot-args).",
    ),
    (
        "Confira os números de série",
        "O número de série gerado deve ser inválido para a Apple, para não colidir com um Mac real. Consulte-o em "
        "checkcoverage.apple.com: o esperado é a mensagem de número inválido. Se ele pertencer a um Mac, gere outro montando a EFI de novo.",
    ),
    (
        "Atualizações do macOS",
        "Antes de uma atualização grande, atualize o OpenCore e os kexts (monte a EFI de novo no MacPronto). Atualizações pequenas "
        "costumam funcionar direto.",
    ),
)

TROUBLESHOOTING = (
    (
        "Trava logo no início, numa linha com [EB|#LOG:EXITBS:START]",
        [
            "Confira os ajustes da BIOS, principalmente CSM desligado, Secure Boot desligado e Above 4G Decoding.",
            "Se a BIOS tiver a opção CFG Lock, desligue-a.",
        ],
    ),
    (
        'Trava numa linha com "PCI configuration begin" ou "PCI configuration end"',
        [
            "Ative o Above 4G Decoding na BIOS.",
            "Se a BIOS não tem essa opção, acrescente npci=0x2000 aos boot-args do config.plist (com o ProperTree, em "
            "NVRAM > Add > 7C436110-AB2A-4BBB-A880-FE41995C9F82 > boot-args) e tente de novo.",
        ],
    ),
    (
        'Aparece um símbolo de proibido (🚫) ou a mensagem "Waiting for Root Device"',
        [
            "Use outra porta USB, de preferência USB 2 ou na traseira.",
            "Se você fez o mapa USB, confira se a porta do pendrive estava marcada.",
            "Desligue o Intel VMD e deixe o SATA em AHCI na BIOS.",
        ],
    ),
    (
        "O computador reinicia sozinho no meio do boot",
        [
            "Confira o Above 4G Decoding e desligue o Resizable BAR.",
            "Em notebooks, desconecte acessórios USB e tente de novo.",
            "Anote a última linha que aparece antes de reiniciar: ela ajuda a achar a causa nos fóruns.",
        ],
    ),
    (
        "Tela preta depois das linhas de texto",
        [
            "Se o monitor está no HDMI do vídeo integrado, tente a DisplayPort.",
            "Com placa de vídeo dedicada, ligue o monitor nela, não na placa-mãe.",
            "Espere 2 minutos: a primeira inicialização às vezes demora.",
        ],
    ),
    (
        '"O servidor de recuperação não pôde ser contatado"',
        [
            'A data do computador está errada. Abra o Terminal no menu Utilitários e acerte com o comando "date" '
            "(formato MMDDhhmmAA, por exemplo date 1022153026 para 22/10/2026 15:30).",
            "Confira se a internet está funcionando no instalador.",
        ],
    ),
    (
        "Sem internet no instalador",
        [
            "Use cabo de rede. O Wi-Fi Intel nem sempre funciona dentro do instalador.",
            "Sem rede compatível, use um adaptador USB-Ethernet com chip Realtek RTL8153 ou a ancoragem USB de um celular Android.",
        ],
    ),
    (
        "Sem som depois de instalar",
        [
            "O AppleALC precisa do layout-id certo. No config.plist, mude o alcid=N dos boot-args para outro valor da lista "
            "do seu codec (o MacPronto mostra a lista na etapa Versão do macOS) e reinicie.",
            "No macOS Tahoe, confira se o kext SimpleHDA está na EFI.",
        ],
    ),
    (
        "Wi-Fi ou Bluetooth não funcionam",
        [
            "Wi-Fi Intel com itlwm: instale o aplicativo HeliPort para conectar às redes.",
            "Placas sem suporte não funcionam: troque por uma placa Broadcom compatível.",
        ],
    ),
    (
        "Teclado ou touchpad do notebook não respondem",
        [
            "Use um teclado e um mouse USB durante a instalação.",
            "Touchpads I2C às vezes precisam de ajuste fino depois; procure o modelo do notebook nos fóruns da comunidade.",
        ],
    ),
)
