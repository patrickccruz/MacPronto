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


@dataclass(frozen=True)
class Step:
    title: str
    text: str
    items: tuple[str, ...] = ()
    # Nomes das ilustrações de figures.py que acompanham o passo
    figures: tuple[str, ...] = ()
    tip: str = ""
    warning: str = ""


# Os textos aceitam {bios_key}, {boot_key} e {macos_name}, trocados pelos desta máquina.
INSTALL_STEPS = (
    Step(
        "Dê boot pelo pendrive",
        "Com o pendrive conectado (de preferência numa porta USB 2 ou na traseira), ligue o computador apertando a tecla do "
        "menu de boot ({boot_key}). Escolha o pendrive com o nome UEFI.",
        figures=("boot_menu",),
        tip="O pendrive não aparece na lista? Use outra porta USB e confira na BIOS se o Secure Boot e o CSM ficaram desligados.",
    ),
    Step(
        "Escolha o instalador no OpenCore",
        'Aparece a tela do OpenCore, com fundo preto e uma lista numerada. Com as setas, escolha "macOS Base System" (ou '
        '"Install macOS") e aperte Enter. Se só aparecer o Windows, aperte a barra de espaço para mostrar as opções escondidas.',
        figures=("opencore", "verbose"),
        tip="O OpenCore espera alguns segundos e liga a opção padrão sozinho: aperte uma seta logo que a lista aparecer. "
        "Depois, vão passar muitas linhas de texto: é normal, a EFI do pendrive liga o modo detalhado para ajudar a achar "
        "problemas.",
    ),
    Step(
        "Apague o disco de destino",
        "Na tela de Recuperação, escolha Utilitário de Disco e Continuar. Clique em Visualizar > Mostrar Todos os "
        "Dispositivos, selecione o disco inteiro (não a partição) onde o macOS vai ficar e clique em Apagar: nome "
        "Macintosh HD, formato APFS e esquema Mapa de Partição GUID.",
        figures=("recovery", "disk_utility"),
        warning="Isto apaga o Windows e todos os arquivos desse disco. Confira o tamanho do disco antes de apagar.",
    ),
    Step(
        "Reinstale o macOS",
        "Feche o Utilitário de Disco (Command + Q), escolha Reinstalar o {macos_name}, aceite os termos e escolha o disco "
        "Macintosh HD. O instalador baixa o sistema da Apple: a internet precisa estar funcionando (cabo de rede é o mais "
        "garantido).",
        figures=("installer",),
        tip="Leva de 30 a 90 minutos. A tela pode ficar preta ou parada na barra de progresso por vários minutos: espere.",
    ),
    Step(
        "Escolha a entrada certa nas reinicializações",
        'O computador reinicia algumas vezes. Em todas, dê boot pelo pendrive ({boot_key}) e escolha "macOS Installer" no '
        "OpenCore. Quando essa opção sumir, escolha o nome do disco (Macintosh HD), até aparecer a configuração inicial do "
        "macOS.",
        figures=("opencore_reboot",),
        tip="Caiu na tela de Recuperação de novo? Foi a opção errada: reinicie e escolha macOS Installer.",
    ),
    Step(
        "Configure o macOS",
        "Siga a configuração inicial: país, idioma, rede e conta de usuário. Crie a conta já com o seu nome: trocar depois dá "
        "trabalho. Na tela do Apple ID, escolha Configurar Depois: o login no iCloud fica para depois de conferir o número de "
        "série (veja a pós-instalação).",
    ),
)


# Pós-instalação, na ordem em que aparece no guia. render.py escolhe os passos que valem para a
# máquina. Os textos vêm da primeira instalação completa num notebook (VAIO VJFE, outubro de 2026).
POST_STEPS = {
    "pendrive": Step(
        "Por enquanto, ligue sempre com o pendrive",
        "O pendrive dá a partida (o OpenCore) e o macOS roda do disco interno. Deixe-o conectado ao ligar até o passo "
        "\"Ligue sem o pendrive\". Antes de tirá-lo com o macOS ligado, ejete o MACPRONTO no Finder (⏏). Num teclado de PC, "
        "a tecla Windows faz o papel da Command (⌘) e a Alt, o da Option.",
        figures=("finder_pendrive",),
    ),
    "oclp": Step(
        "Rode o OpenCore Legacy Patcher",
        "Esta instalação precisa de patches de sistema. No macOS instalado, baixe o OpenCore Legacy Patcher "
        "(github.com/dortania/OpenCore-Legacy-Patcher; para o Tahoe, o fork github.com/lzhoang2801/OpenCore-Legacy-Patcher), "
        "abra-o, escolha Post-Install Root Patch > Start Root Patching e reinicie. Repita depois de cada atualização do "
        "macOS. Não use a opção Build and Install OpenCore: a EFI do MacPronto já é a certa.",
    ),
    "heliport": Step(
        "Conecte o Wi-Fi pelo HeliPort",
        "O Wi-Fi Intel usa o driver itlwm. Com ele, o Wi-Fi do próprio macOS (o ícone e Ajustes > Wi-Fi) fica sempre "
        "desligado, e é normal: a conexão é feita pelo aplicativo HeliPort. AirDrop não funciona com Wi-Fi Intel.",
        (
            "No Finder, abra o pendrive MACPRONTO > MacPronto > HeliPort.dmg. Se não estiver lá, baixe em "
            "github.com/OpenIntelWireless/HeliPort por outro aparelho ou com cabo de rede.",
            "Copie o HeliPort para Aplicativos: selecione, Command + C; em Aplicativos, Command + V. Não abra direto do "
            ".dmg: ele avisa \"caminho inesperado\".",
            "Abra o HeliPort em Aplicativos. Se o macOS bloquear, vá em Ajustes do Sistema > Privacidade e Segurança > Abrir "
            "Mesmo Assim. Na pergunta sobre atualizações automáticas, escolha Não Buscar.",
            "Clique no ícone de Wi-Fi do HeliPort, perto do relógio, escolha a rede e digite a senha.",
            "Para ele abrir sozinho: Ajustes do Sistema > Geral > Itens de Início > + > HeliPort.",
        ),
        figures=("heliport",),
    ),
    "keyboard": Step(
        "Ajuste o teclado ABNT2",
        "Sem este ajuste, a tecla abaixo do Esc e a tecla ao lado do Z podem sair trocadas.",
        (
            "Ajustes do Sistema > Teclado > Fontes de Entrada > Editar… > + > Português (Brasil) > Brasileiro – ABNT2. "
            "Apague as outras fontes com o botão –.",
            "Ajustes do Sistema > Teclado > Alterar Tipo de Teclado…: aperte as teclas pedidas e escolha ISO (Europeu e outros).",
            "Reinicie: a troca de tipo de teclado só vale depois de reiniciar.",
            "Teste: a tecla abaixo do Esc deve dar ' e \" e a tecla ao lado do Z, \\ e |. Se continuarem trocadas, escolha "
            "ANSI e reinicie de novo.",
        ),
        figures=("pc_keyboard", "keyboard_settings"),
    ),
    "trackpad": Step(
        "Ajuste o trackpad",
        "Em Ajustes do Sistema > Trackpad, na aba Apontar e Clicar:",
        (
            "Pesquisar e detectores de dados: Desativado (senão, arrastar com o botão abre uma prévia do arquivo).",
            "Clique firme e retorno tátil: desligado. Tocar para clicar: ligado, se preferir.",
            "Para arrastar sem apertar nada: Ajustes do Sistema > Acessibilidade > Controle do Ponteiro > Opções do "
            "Trackpad… > Usar o trackpad para arrastar > Arrastar com três dedos.",
        ),
        figures=("trackpad_settings",),
    ),
    "usb": Step(
        "Teste todas as portas USB",
        "Conecte um mouse ou pendrive em cada porta. Porta que não funciona no macOS, mas dá boot pela BIOS, ficou fora do "
        "mapa USB: veja Problemas e soluções.",
    ),
    "usb_map": Step(
        "Mapeie as portas USB",
        "A EFI está com todas as portas ativas (UTBDefault). Se alguma porta não funcionar ou o USB 3 ficar lento, volte ao "
        "MacPronto no Windows antes de formatar, ou faça o mapa no macOS com o USBToolBox.",
    ),
    "vesa": Step(
        "Ative a aceleração do vídeo integrado",
        "A EFI usa o modo VESA porque há monitor no HDMI/DVI do vídeo integrado. Ligue o monitor na DisplayPort e remova "
        "-igfxvesa dos boot-args, ou peça ajuda nos fóruns para mapear as portas do vídeo (framebuffer patching).",
    ),
    "final_efi": Step(
        "Ligue sem o pendrive (EFI definitiva)",
        "A pasta MacPronto > EFI-definitiva do pendrive tem a mesma EFI, sem as linhas de texto no boot e com o menu do "
        "OpenCore escondido. Copie-a para a partição EFI do disco interno:",
        (
            "No Terminal, rode diskutil list e ache o disco interno (internal) onde está o macOS. A partição EFI dele "
            "costuma ser a disk0s1 (tipo EFI, de 100 a 300 MB). Não mexa em outros discos internos.",
            "Rode sudo diskutil mount disk0s1 (troque pelo identificador certo) e digite a senha do Mac. Aparece \"EFI\" ou "
            "\"NO NAME\" no Finder.",
            "Se já existir uma pasta EFI lá (do Windows antigo), copie-a para MACPRONTO > MacPronto > backup, por segurança.",
            "Copie a pasta EFI de MacPronto > EFI-definitiva e cole na partição. Quando o Mac perguntar, escolha "
            "Substituir. Confira que ficaram as pastas BOOT e OC.",
            "Ejete a partição. Em Ajustes do Sistema > Geral > Disco de Inicialização, escolha o disco do macOS.",
            "Desligue, tire o pendrive e, na BIOS ({bios_key}), coloque o disco interno em primeiro na ordem de boot.",
            "Para ver o menu do OpenCore depois, aperte Esc logo depois de ligar. Guarde o pendrive: ele continua dando "
            "boot e serve de emergência.",
        ),
        figures=("terminal_diskutil", "finder_efi"),
        tip="No Terminal, a senha não aparece enquanto você digita: é normal. Digite e aperte Enter.",
    ),
    "apple_id": Step(
        "Antes de entrar com o seu Apple ID (iCloud e App Store)",
        "iCloud e App Store costumam funcionar. O risco não é perder dados: no pior caso, a Apple bloqueia iMessage e "
        "FaceTime neste computador e pede contato com o suporte. Antes de entrar:",
        (
            "Veja o número de série em menu Apple > Sobre Este Mac e consulte em checkcoverage.apple.com: o certo é a "
            "mensagem de número inválido. Se ele pertencer a um Mac de verdade, não entre: monte a EFI de novo, que gera "
            "outro. Nunca publique esse número.",
            "No Terminal, rode ioreg -r -c IOEthernetInterface -d 1 e confira que o bloco com \"BSD Name\" = \"en0\" tem "
            "\"IOBuiltin\" = Yes. Sem isso, a App Store pode recusar o login.",
            "Entre em Ajustes do Sistema > Iniciar sessão. Se aparecer um erro com \"código de cliente\", pare e não "
            "insista: tentativas repetidas pioram o bloqueio.",
            "AirDrop, Sidecar, Apple Pay e Touch ID dependem de peças dos Macs e não funcionam (o AirDrop só funciona com "
            "placa Wi-Fi Broadcom).",
            "Se o computador for da empresa ou tiver dados de trabalho, fale com a TI antes de usar uma conta pessoal.",
        ),
        figures=("about_mac",),
    ),
    "updates": Step(
        "Atualizações do macOS",
        "Antes de uma atualização grande, atualize o OpenCore e os kexts (monte a EFI de novo no MacPronto). Atualizações "
        "pequenas costumam funcionar direto. Se o macOS não ligar depois de uma atualização, dê boot pelo pendrive.",
    ),
}

TROUBLESHOOTING = (
    (
        "No menu do OpenCore só aparece o Windows",
        [
            'Aperte a barra de espaço: o instalador ("macOS Base System") pode estar entre as opções escondidas.',
            "Se mesmo assim não aparecer, confira no Windows se o pendrive tem a pasta com.apple.recovery.boot com o "
            "BaseSystem.dmg e, se não tiver, grave o pendrive de novo no MacPronto.",
        ],
    ),
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
        "O Wi-Fi aparece desligado e não liga",
        [
            "Com Wi-Fi Intel e o driver itlwm, o Wi-Fi do próprio macOS fica sempre desligado: use o HeliPort (veja a "
            "pós-instalação).",
            "Se o próprio HeliPort mostrar o Wi-Fi desligado e travado, rode no Terminal ioreg -r -c itlwm -d 1. Se não "
            "aparecer nada, o driver não se ligou à placa: peça ajuda com o AJUDA-IA.md.",
            "Placas sem suporte não funcionam: troque por uma placa Broadcom compatível.",
        ],
    ),
    (
        "O HeliPort diz que está \"rodando em um caminho inesperado\"",
        ["Ele foi aberto direto do .dmg. Copie o HeliPort para Aplicativos e abra de lá."],
    ),
    (
        "AirDrop não funciona",
        [
            "O AirDrop só funciona com placa Wi-Fi Broadcom, como as dos Macs. Com Intel, Realtek ou outras, não há como.",
            "Antes de comprar uma placa Broadcom, confira se o encaixe aceita: placas Intel do tipo CNVi (como a 9462, a 9560 "
            "e a AX201) costumam ficar num encaixe que só aceita placas CNVi.",
        ],
    ),
    (
        "O touchpad do notebook não responde",
        [
            "Use um mouse USB enquanto isso.",
            "Touchpad I2C: a EFI usa o VoodooI2CHID. Em touchpads Synaptics, a outra opção é o VoodooRMI: no config.plist, em "
            "Kernel > Add, desative VoodooI2CHID.kext e ative VoodooRMI.kext e VoodooRMI.kext/Contents/PlugIns/RMII2C.kext. "
            "Faça a mesma mudança na EFI definitiva.",
            "Para editar o config.plist, use o ProperTree (no Windows de outro computador ou no próprio Mac). Peça o passo a "
            "passo a uma IA com o AJUDA-IA.md.",
        ],
    ),
    (
        "Arrastar com o botão do touchpad abre uma prévia do arquivo",
        [
            "É a Visualização Rápida. Em Ajustes do Sistema > Trackpad, deixe \"Pesquisar e detectores de dados\" como "
            "Desativado e desligue o \"Clique firme\".",
            "Para arrastar sem botão: Acessibilidade > Controle do Ponteiro > Opções do Trackpad > Arrastar com três dedos. "
            "Para copiar arquivos, Command + C e Command + V também resolvem.",
        ],
    ),
    (
        "A tecla abaixo do Esc e a tecla ao lado do Z estão trocadas",
        [
            "Use o layout Brasileiro – ABNT2 e o tipo de teclado ISO (Ajustes do Sistema > Teclado > Alterar Tipo de "
            "Teclado…) e reinicie: a troca de tipo só vale depois de reiniciar.",
            "Se continuarem trocadas depois de reiniciar, escolha ANSI e reinicie de novo.",
        ],
    ),
    (
        "Uma porta USB não funciona no macOS, mas a BIOS dá boot por ela",
        [
            "A BIOS enxerga todas as portas; o macOS, só as do mapa USB. Essa porta não recebeu nenhum dispositivo no "
            "mapeamento.",
            "Use outra porta. Para corrigir, o mapa (EFI/OC/Kexts/UTBMap.kext) precisa ganhar a porta que falta, até o "
            "limite de 15. O AJUDA-IA.md tem a lista das portas do mapa: peça ajuda a uma IA com ele.",
        ],
    ),
    (
        "O pendrive não aparece no Finder",
        [
            "Ele pode estar numa porta fora do mapa USB: troque de porta.",
            "Se ele foi ejetado, tire e conecte de novo, ou monte pelo Utilitário de Disco (selecione e clique em Montar).",
        ],
    ),
    (
        "Depois de copiar a EFI para o disco interno, não liga sem o pendrive",
        [
            "Ligue pelo pendrive, que continua funcionando, e confira na BIOS se o disco interno está em primeiro na ordem "
            "de boot.",
            "Algumas BIOS só aceitam a entrada antiga \"Windows Boot Manager\". Nesse caso, peça ajuda com o AJUDA-IA.md: "
            "dá para fazer essa entrada abrir o OpenCore.",
        ],
    ),
)
