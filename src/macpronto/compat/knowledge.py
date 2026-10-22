"""Textos em português para o laudo: kexts, patches ACPI, impedimentos e requisitos de BIOS."""

from __future__ import annotations

KEXTS = {
    "Lilu": "Base para os demais kexts: permite aplicar patches no sistema.",
    "VirtualSMC": "Emula o chip SMC dos Macs. Sem ele o macOS não inicia.",
    "SMCBatteryManager": "Mostra o nível e o estado da bateria.",
    "SMCDellSensors": "Leitura e controle das ventoinhas em computadores Dell.",
    "SMCLightSensor": "Usa o sensor de luz ambiente para o brilho automático.",
    "SMCProcessor": "Lê a temperatura do processador Intel.",
    "SMCRadeonSensors": "Lê a temperatura das placas de vídeo AMD.",
    "SMCSuperIO": "Lê sensores da placa-mãe e a velocidade das ventoinhas.",
    "NootRX": "Suporte às placas AMD RDNA 2 (Navi 22) com o firmware mais recente.",
    "NootedRed": "Suporte ao vídeo integrado AMD Vega dos processadores Ryzen.",
    "WhateverGreen": "Correções de vídeo: aceleração, saídas de vídeo e tela.",
    "AppleALC": "Ativa o áudio onboard (codec Realtek, Conexant etc.) com o driver da Apple.",
    "SimpleHDA": "Repõe o driver de áudio da Apple no Tahoe sem patches de sistema.",
    "AirPortAtheros40-Tahoe": "Wi-Fi Atheros no macOS Tahoe.",
    "AirportBrcmFixup": "Correções para placas Wi-Fi Broadcom que não são da Apple.",
    "AirPortBrcmNIC-Tahoe": "Wi-Fi Broadcom no macOS Tahoe.",
    "AirportItlwm": "Wi-Fi Intel com o menu nativo do macOS.",
    "AirportItlwm-laobamac": "Wi-Fi Intel com o menu nativo, sem patches de sistema no Sequoia 15.2+ e no Tahoe.",
    "corecaptureElCap": "Suporte a placas Wi-Fi Atheros antigas.",
    "Feixiao": "Wi-Fi Realtek (rtw88), ainda experimental.",
    "IO80211ElCap": "Suporte a placas Wi-Fi Atheros antigas.",
    "IO80211FamilyLegacy": "Repõe o suporte a placas Wi-Fi antigas da Apple.",
    "IOSkywalkFamily": "Repõe o suporte a placas Wi-Fi antigas no Sonoma e mais novos.",
    "itlwm": "Wi-Fi Intel pelo aplicativo HeliPort. Mais estável, sem recursos de continuidade.",
    "Ath3kBT": "Bluetooth Atheros.",
    "Ath3kBTInjector": "Bluetooth Atheros.",
    "BlueToolFixup": "Ajusta o Bluetooth para placas que não são da Apple.",
    "BrcmBluetoothInjector": "Liga e desliga o Bluetooth Broadcom em versões antigas.",
    "BrcmFirmwareData": "Firmware do Bluetooth Broadcom.",
    "BrcmPatchRAM2": "Carrega o firmware do Bluetooth Broadcom.",
    "BrcmPatchRAM3": "Carrega o firmware do Bluetooth Broadcom.",
    "IntelBluetoothFirmware": "Carrega o firmware do Bluetooth Intel.",
    "IntelBTPatcher": "Corrige falhas de conexão do Bluetooth Intel.",
    "IntelBluetoothInjector": "Liga e desliga o Bluetooth Intel em versões antigas.",
    "RealtekBluetoothFirmware": "Carrega o firmware do Bluetooth Realtek.",
    "AppleIGB": "Rede cabeada Intel IGB.",
    "AppleIGC": "Rede cabeada Intel 2,5 Gb (I225/I226).",
    "AtherosE2200Ethernet": "Rede cabeada Atheros/Killer E2200.",
    "CatalinaBCM5701Ethernet": "Rede cabeada Broadcom BCM57xx.",
    "HoRNDIS": "Internet pelo celular Android via cabo USB (ancoragem).",
    "IntelLucy": "Rede cabeada Intel X500 (10 Gb).",
    "IntelMausiEthernet": "Rede cabeada Intel (I217, I218, I219 e similares).",
    "LucyRTL8125Ethernet": "Rede cabeada Realtek 2,5 Gb (RTL8125).",
    "NullEthernet": "Cria uma rede falsa para a App Store e o iCloud funcionarem sem rede compatível.",
    "RealtekRTL8100": "Rede cabeada Realtek RTL8100.",
    "RealtekRTL8111": "Rede cabeada Realtek RTL8111/8168.",
    "RTL812xLucy": "Rede cabeada Realtek RTL812x.",
    "GenericUSBXHCI": "Corrige USB 3.0 em alguns notebooks Ryzen.",
    "USBToolBox": "Base do mapeamento de portas USB.",
    "UTBDefault": "Ativa todas as portas USB até o mapeamento ser feito.",
    "UTBMap": "Mapa das portas USB desta máquina, gerado pelo MacPronto.",
    "XHCI-unsupported": "Ativa o USB 3.0 em controladoras que o macOS não reconhece.",
    "AlpsHID": "Gestos multitoque no touchpad Alps I2C.",
    "VoodooInput": "Emula o Magic Trackpad para os gestos do touchpad.",
    "VoodooPS2Controller": "Teclado e touchpad PS/2 de notebooks.",
    "VoodooRMI": "Touchpad Synaptics via SMBus/I2C.",
    "VoodooSMBus": "Touchpad ELAN via SMBus.",
    "VoodooI2C": "Base para touchpads e telas sensíveis ao toque I2C.",
    "VoodooI2CAtmelMXT": "Telas sensíveis ao toque Atmel.",
    "VoodooI2CELAN": "Touchpads ELAN I2C.",
    "VoodooI2CFTE": "Touchpads FTE I2C.",
    "VoodooI2CHID": "Touchpads e telas I2C no padrão HID.",
    "VoodooI2CSynaptics": "Touchpads Synaptics I2C.",
    "AsusSMC": "Sensor de luz, luz do teclado e teclas Fn em notebooks ASUS.",
    "BigSurface": "Suporte ao hardware dos Microsoft Surface.",
    "YogaSMC": "Recursos específicos de notebooks Lenovo (sensores, teclas, ventoinha).",
    "CtlnaAHCIPort": "Melhora o suporte a algumas controladoras SATA.",
    "SATA-unsupported": "Melhora o suporte a algumas controladoras SATA.",
    "NVMeFix": "Melhora a economia de energia e a compatibilidade de SSDs NVMe.",
    "PC711Probe": "Suporte ao SSD SK Hynix PC711.",
    "PC711ProbeForce": "Modo de compatibilidade MSI-X para controladoras NVMe.",
    "RealtekCardReader": "Leitor de cartão SD Realtek.",
    "RealtekCardReaderFriend": "Mostra o leitor de cartão Realtek nas Informações do Sistema.",
    "Sinetek-rtsx": "Leitor de cartão SD Realtek PCIe.",
    "AmdTscSync": "Sincroniza o relógio dos núcleos em processadores AMD.",
    "VoodooTSCSync": "Sincroniza o relógio dos núcleos em processadores Intel.",
    "CpuTscSync": "Sincroniza o relógio dos núcleos em processadores Intel HEDT.",
    "ForgedInvariant": "Sincroniza o relógio dos núcleos em processadores AMD e Intel.",
    "AMFIPass": "Permite os patches do OpenCore Legacy Patcher sem desligar toda a segurança.",
    "ASPP-Override": "Gerenciamento de energia em processadores Sandy Bridge.",
    "AppleIntelCPUPowerManagement": "Gerenciamento de energia em processadores Intel antigos.",
    "AppleIntelCPUPowerManagementClient": "Gerenciamento de energia em processadores Intel antigos.",
    "AppleMCEReporterDisabler": "Evita travamentos em processadores AMD e com mais de um soquete.",
    "BrightnessKeys": "Faz as teclas de brilho do notebook funcionarem.",
    "CPUFriend": "Ajuste fino do gerenciamento de energia do processador.",
    "CpuTopologyRebuild": "Organiza os núcleos de desempenho e eficiência dos Intel de 12ª geração em diante.",
    "CryptexFixup": "Permite o Ventura e mais novos em processadores sem AVX2.",
    "ECEnabler": "Permite ler o nível da bateria em notebooks.",
    "FeatureUnlock": "Libera recursos como Sidecar e AirPlay para o Mac em hardware não oficial.",
    "HibernationFixup": "Corrige a hibernação.",
    "NoTouchID": "Evita lentidão em pedidos de senha nos modelos com Touch ID.",
    "RestrictEvents": "Bloqueia processos problemáticos e libera recursos do sistema.",
    "RTCMemoryFixup": "Emula partes da memória CMOS (RTC) para evitar erros na BIOS.",
}

ACPI_PATCHES = {
    "ALS": "Sensor de luz ambiente (falso ou real) para guardar o brilho da tela.",
    "APIC": "Evita travamento em processadores HEDT apontando a primeira CPU ativa.",
    "BATP": "Mostra a porcentagem da bateria no notebook.",
    "BUS0": "Cria o dispositivo SMBus que o macOS espera.",
    "Disable Devices": "Desliga dispositivos PCI incompatíveis (vídeo dedicado, Wi-Fi, leitor de cartão).",
    "FakeEC": "Cria o controlador embarcado (EC) que o macOS exige.",
    "RCSP": "Remove declarações condicionais que confundem o macOS.",
    "CMOS": "Evita o erro 005 de perda de energia do relógio em computadores HP.",
    "FixHPET": "Resolve conflitos de interrupção (IRQ).",
    "GPI0": "Ativa o controlador GPIO para o touchpad I2C funcionar.",
    "IMEI": "Cria o dispositivo IMEI para a aceleração do vídeo Intel.",
    "MCHC": "Cria o controlador de memória que o macOS espera.",
    "PMC": "Ativa a NVRAM em placas-mãe Intel série 300.",
    "PM (Legacy)": "Desativa tabelas de energia antigas em processadores Ivy Bridge e anteriores.",
    "PLUG": "Ativa o gerenciamento de energia nativo do processador.",
    "PNLF": "Ativa o controle de brilho da tela do notebook.",
    "RMNE": "Cria uma rede falsa para o iCloud e a App Store.",
    "RTC0": "Cria um relógio (RTC) compatível em sistemas HEDT.",
    "RTCAWAC": "Ativa o relógio RTC no lugar do AWAC, que o macOS não reconhece.",
    "PRW": "Evita que o computador acorde logo após dormir.",
    "Surface Patch": "Patch específico para os Microsoft Surface.",
    "UNC": "Desliga pontes de memória não usadas em sistemas HEDT.",
    "USB Reset": "Desliga hubs USB da ACPI para reconstruir as portas.",
    "USBX": "Informa ao macOS a energia disponível nas portas USB.",
    "WMIS": "Corrige zonas térmicas que não respondem em alguns modelos.",
    "XOSI": "Faz a ACPI acreditar que o sistema é Windows, liberando dispositivos como o touchpad.",
}

# Impedimentos detectados pelo OpCore Simplify.
FATAL = {
    "cpu-sse4": {
        "kind": "incompatible",
        "title": "Processador sem SSE4",
        "message": "O processador não tem as instruções SSE4.x exigidas pelo macOS a partir do High Sierra.",
    },
    "no-gpu": {
        "kind": "incompatible",
        "title": "Vídeo não detectado",
        "message": "Nenhuma placa de vídeo apareceu no diagnóstico. Confira se os drivers de vídeo do Windows estão instalados e refaça o diagnóstico.",
    },
    "gpu-unsupported": {
        "kind": "replace",
        "title": "Nenhum vídeo compatível",
        "message": "O macOS precisa de aceleração gráfica, e nenhuma das placas de vídeo deste computador é compatível.",
    },
    "intel-vmd": {
        "kind": "bios",
        "title": "Intel VMD ligado",
        "message": "A controladora Intel VMD está ativa e o macOS não a reconhece. Desative o VMD na BIOS (ou mude o SATA para AHCI) e refaça o diagnóstico.",
    },
    "no-storage": {
        "kind": "incompatible",
        "title": "Armazenamento não detectado",
        "message": "Nenhuma controladora de disco apareceu no diagnóstico.",
    },
    "storage-unsupported": {
        "kind": "replace",
        "title": "SSD incompatível",
        "message": "Nenhum SSD deste computador é compatível com o macOS. É preciso instalar outro SSD NVMe.",
    },
}

BIOS_REQUIREMENTS = {
    "Enable UEFI mode (disable Legacy/CSM (Compatibility Support Module))": "Ativar o modo UEFI e desativar o CSM (Legacy).",
    "Disable Secure Boot": "Desativar o Secure Boot.",
    "Enable Above 4G Decoding": "Ativar o Above 4G Decoding.",
    "Disable Resizable BAR/Smart Access Memory": "Desativar o Resizable BAR (Smart Access Memory).",
}

REPLACEMENTS = {
    "wifi-desktop": "Placa PCIe Fenvi T919 ou FV-HB1200 (chip Broadcom BCM94360), que também traz Bluetooth, AirDrop e Handoff.",
    "wifi-laptop": "Placa M.2 Broadcom BCM94360NG (ou DW1560/DW1820A), que traz Wi-Fi e Bluetooth nativos.",
    "gpu-desktop": "Placa AMD Radeon RX 6600/6600 XT, RX 6800, RX 5700 ou RX 580/570. Placas NVIDIA atuais não funcionam no macOS.",
    "ssd": "SSD NVMe Western Digital (SN570, SN770, SN850X) ou Crucial P3. Evite Samsung PM981/PM991 e Micron 2200S.",
    "ethernet": "Adaptador USB para rede cabeada com chip Realtek RTL8153, reconhecido nativamente pelo macOS.",
    "audio": "Adaptador de áudio USB, que funciona sem configuração.",
}

# Tradução das opções das decisões, pelo início do rótulo original do OpCore Simplify.
DECISION_OPTIONS = {
    "intel-wifi-kext": {
        "laobamac AirportItlwm": "AirportItlwm (versão laobamac): menu de Wi-Fi nativo, sem patches de sistema no Sequoia 15.2+ e no Tahoe.",
        "AirportItlwm": "AirportItlwm: menu de Wi-Fi nativo, com Handoff. No Sequoia e no Tahoe exige patches do OCLP.",
        "itlwm": "itlwm: o mais estável. Usa o aplicativo HeliPort no lugar do menu de Wi-Fi.",
    },
    "tahoe-audio": {
        "AppleALC + OCLP": "AppleALC + OCLP: repõe o driver de áudio com um patch de sistema.",
        "AppleALC + SimpleHDA": "AppleALC + SimpleHDA: áudio pelo OpenCore, sem patches de sistema.",
    },
    "amd-gpu-kext": {
        "NootRX": "NootRX: usa o firmware mais recente da placa.",
        "WhateverGreen": "WhateverGreen: usa o firmware original da Apple.",
    },
}

DECISION_HELP = {
    "intel-wifi-kext": "O Wi-Fi Intel não tem driver da Apple. Escolha qual driver da comunidade usar.",
    "tahoe-audio": "O macOS Tahoe removeu o driver de áudio (AppleHDA). Escolha como repô-lo.",
    "amd-gpu-kext": "Placas AMD RDNA 2 funcionam com dois kexts diferentes. Dá para trocar depois de instalar.",
    "audio-layout-id": "Cada placa-mãe liga o codec de um jeito. Se não sair som, teste outro layout.",
    "firmware-uefi": "A BIOS está em modo Legacy. Montar a EFI para UEFI exige ativar o modo UEFI na BIOS.",
    "force-load-kexts": "Alguns kexts não declaram suporte a esta versão do macOS. Forçar pode causar instabilidade.",
    "combination-gpu": "Mais de uma placa de vídeo compatível. Escolha quais ficam ativas no macOS.",
    "device-wifi": "Há mais de uma placa Wi-Fi. O macOS funciona melhor com só uma ativa.",
    "device-bluetooth": "Há mais de um Bluetooth. O macOS funciona melhor com só um ativo.",
}


_DETAIL_REPLACEMENTS = (
    ("OCLP Compatibility", "Com OCLP"),
    ("Compatibility", "Compatibilidade"),
    ("Maximum support up to", "no máximo até o"),
    ("Up to", "até o"),
    (" to ", " ao "),
    ("Device ID", "ID do dispositivo"),
    ("Unsupported", "sem suporte"),
)


def _translate_detail(text: str) -> str:
    for source, target in _DETAIL_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def translate_decision(decision: dict) -> dict:
    translations = DECISION_OPTIONS.get(decision.get("key"), {})
    options = []
    for option in decision.get("options", []):
        label = option.get("label", "")
        name = label.split(" - ")[0].strip()
        options.append(
            {
                **option,
                "label_pt": translations.get(name),
                "details": [_translate_detail(d) for d in option.get("details", [])],
            }
        )
    return {**decision, "options": options, "help": DECISION_HELP.get(decision.get("key"), "")}


DIFFICULTY_LABELS = {
    1: "Muito fácil",
    2: "Fácil",
    3: "Moderado",
    4: "Difícil",
    5: "Muito difícil",
}


def kext_description(name: str, fallback: str = "") -> str:
    return KEXTS.get(name, fallback)


def acpi_description(name: str, fallback: str = "") -> str:
    return ACPI_PATCHES.get(name, fallback)


def bios_requirement(text: str) -> str:
    return BIOS_REQUIREMENTS.get(text, text)
