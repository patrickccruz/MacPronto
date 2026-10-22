"""Conteúdo do guia: BIOS por fabricante, instalação, pós-instalação e problemas.

Baseado no guia de instalação do OpenCore da Dortania
(https://dortania.github.io/OpenCore-Install-Guide/), adaptado ao que a EFI do
MacPronto já resolve sozinha.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Vendor:
    key: str
    name: str
    bios_key: str
    boot_key: str
    notes: tuple[str, ...] = ()
    # Onde fica cada ajuste no menu deste fabricante (chave -> caminho)
    paths: dict[str, str] = field(default_factory=dict)


VENDORS = {
    "asus": Vendor(
        "asus",
        "ASUS",
        "Del ou F2",
        "F8 (desktop) ou Esc (notebook)",
        ("Aperte F7 para alternar entre o modo simples (EZ Mode) e o avançado (Advanced Mode).",),
        {
            "secure_boot": "Boot > Secure Boot > OS Type: Other OS",
            "fast_boot": "Boot > Fast Boot",
            "csm": "Boot > CSM (Compatibility Support Module) > Launch CSM",
            "above4g": "Advanced > PCI Subsystem Settings > Above 4G Decoding",
            "rebar": "Advanced > PCI Subsystem Settings > Re-Size BAR Support",
            "vtd": "Advanced > System Agent (SA) Configuration > VT-d",
            "sata": "Advanced > PCH Storage Configuration > SATA Mode",
            "dvmt": "Advanced > System Agent (SA) Configuration > Graphics Configuration > DVMT Pre-Allocated",
            "xhci": "Advanced > USB Configuration > XHCI Hand-off",
            "vmd": "Advanced > System Agent (SA) Configuration > VMD setup menu",
        },
    ),
    "gigabyte": Vendor(
        "gigabyte",
        "Gigabyte",
        "Del",
        "F12",
        ("Aperte F2 para alternar entre o modo simples e o avançado.",),
        {
            "secure_boot": "Boot > Secure Boot",
            "fast_boot": "Boot > Fast Boot",
            "csm": "Boot > CSM Support",
            "above4g": "Settings > IO Ports > Above 4G Decoding",
            "rebar": "Settings > IO Ports > Re-Size BAR Support",
            "vtd": "Settings > Miscellaneous > Intel VT-d Technology",
            "sata": "Settings > IO Ports > SATA And RST Configuration > SATA Mode Selection",
            "dvmt": "Chipset > Internal Graphics > DVMT Pre-Allocated",
            "xhci": "Settings > IO Ports > USB Configuration > XHCI Hand-off",
            "vmd": "Settings > IO Ports > VMD setup menu",
        },
    ),
    "msi": Vendor(
        "msi",
        "MSI",
        "Del",
        "F11",
        ("Aperte F7 para entrar no modo avançado.",),
        {
            "secure_boot": "Settings > Advanced > Windows OS Configuration > Secure Boot",
            "fast_boot": "Settings > Advanced > Windows OS Configuration > MSI Fast Boot e Fast Boot",
            "csm": "Settings > Advanced > Windows OS Configuration > BIOS UEFI/CSM Mode: UEFI",
            "above4g": "Settings > Advanced > PCI Subsystem Settings > Above 4G memory/Crypto Currency mining",
            "rebar": "Settings > Advanced > PCI Subsystem Settings > Re-Size BAR Support",
            "vtd": "OC > CPU Features > Intel VT-D Tech",
            "sata": "Settings > Advanced > Integrated Peripherals > SATA Mode",
            "dvmt": "Settings > Advanced > Integrated Graphics Configuration > DVMT Pre-Allocated",
            "xhci": "Settings > Advanced > USB Configuration > XHCI Hand-off",
            "vmd": "Settings > Advanced > Integrated Peripherals > VMD",
        },
    ),
    "asrock": Vendor(
        "asrock",
        "ASRock",
        "F2 ou Del",
        "F11",
        (),
        {
            "secure_boot": "Security > Secure Boot",
            "fast_boot": "Boot > Fast Boot",
            "csm": "Boot > CSM (Compatibility Support Module)",
            "above4g": "Advanced > Chipset Configuration > Above 4G Decoding",
            "rebar": "Advanced > Chipset Configuration > Re-Size BAR Support",
            "vtd": "Advanced > Chipset Configuration > VT-d",
            "sata": "Advanced > Storage Configuration > SATA Mode Selection",
            "dvmt": "Advanced > Chipset Configuration > Share Memory",
            "xhci": "Advanced > USB Configuration > XHCI Hand-off",
            "vmd": "Advanced > Storage Configuration > VMD Global Mapping",
        },
    ),
    "dell": Vendor(
        "dell",
        "Dell",
        "F2",
        "F12",
        ("Muitos ajustes ficam em General, System Configuration, Secure Boot e Virtualization Support.",),
        {
            "secure_boot": "Secure Boot > Secure Boot Enable",
            "fast_boot": "POST Behavior > Fastboot: Thorough",
            "csm": "General > Advanced Boot Options > Enable Legacy Option ROMs (desligado)",
            "vtd": "Virtualization Support > VT for Direct I/O",
            "sata": "System Configuration > SATA Operation: AHCI",
            "vmd": "System Configuration > SATA Operation: AHCI",
        },
    ),
    "lenovo": Vendor(
        "lenovo",
        "Lenovo",
        "F1 (ThinkPad e ThinkCentre) ou F2 (IdeaPad e Legion)",
        "F12",
        (
            "Nos IdeaPad também dá para usar o botão Novo (furinho na lateral) para abrir o menu de boot.",
            "Nos ThinkPad e ThinkCentre, aperte Enter na tela da Lenovo e depois F1.",
        ),
        {
            "secure_boot": "Security > Secure Boot",
            "fast_boot": "Startup > Boot Mode: Diagnostics (no lugar de Quick)",
            "csm": "Startup > CSM: Disabled e UEFI/Legacy Boot: UEFI Only",
            "vtd": "Security > Virtualization > Intel VT-d Feature",
            "sata": "Devices > ATA Drive Setup > SATA Controller Mode: AHCI",
            "vmd": "Devices > Storage > Intel VMD Controller (ou Configure SATA as: AHCI)",
        },
    ),
    "hp": Vendor(
        "hp",
        "HP",
        "F10 (ou Esc e depois F10)",
        "F9",
        ("Depois de mudar o Secure Boot, a HP pede para digitar um código de 4 dígitos na próxima inicialização.",),
        {
            "secure_boot": "Advanced > Secure Boot Configuration > Secure Boot",
            "fast_boot": "Advanced > Boot Options > Fast Boot",
            "csm": "Advanced > Secure Boot Configuration > Legacy Support: Disable",
            "vtd": "Advanced > System Options > Virtualization Technology for Directed I/O (VT-d)",
            "sata": "Advanced > System Options > Configure Storage Controller for RAID/AHCI",
            "vmd": "Advanced > System Options > Configure Storage Controller for Intel VMD (desligado)",
        },
    ),
    "acer": Vendor(
        "acer",
        "Acer",
        "F2",
        'F12 (ative "F12 Boot Menu" em Main antes)',
        ("Na Acer, o Secure Boot só pode ser desligado depois de definir uma senha de supervisor em Security.",),
        {
            "secure_boot": "Boot > Secure Boot (exige senha de supervisor em Security)",
            "fast_boot": "Main > Fast Boot",
            "csm": "Boot > Boot Mode: UEFI",
            "sata": "Main > SATA Mode: AHCI",
            "vmd": "Main > VMD Controller (desligado)",
        },
    ),
    "generic": Vendor(
        "generic",
        "sua placa-mãe",
        "Del ou F2 (às vezes F1, F10 ou Esc)",
        "F12, F11 ou F8",
        ("Os nomes mudam um pouco entre fabricantes. Procure pelas palavras-chave de cada ajuste.",),
        {},
    ),
}

VENDOR_MARKERS = (
    ("asustek", "asus"),
    ("asus", "asus"),
    ("gigabyte", "gigabyte"),
    ("micro-star", "msi"),
    ("msi", "msi"),
    ("asrock", "asrock"),
    ("dell", "dell"),
    ("lenovo", "lenovo"),
    ("hewlett", "hp"),
    ("hp", "hp"),
    ("acer", "acer"),
)

OEM_BRANDS = {"dell", "lenovo", "hp", "acer"}


def detect_vendor(system_manufacturer: str, board_manufacturer: str, is_laptop: bool) -> Vendor:
    """Para notebooks e desktops de marca vale o fabricante do sistema; para PCs montados, o da placa."""
    system = (system_manufacturer or "").lower()
    board = (board_manufacturer or "").lower()

    def match(text: str) -> str | None:
        return next((key for marker, key in VENDOR_MARKERS if marker in text), None)

    system_key, board_key = match(system), match(board)
    if system_key in OEM_BRANDS or (is_laptop and system_key):
        return VENDORS[system_key]
    return VENDORS[board_key or system_key or "generic"]


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
