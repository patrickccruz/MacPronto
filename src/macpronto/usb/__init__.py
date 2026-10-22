"""Mapeamento das portas USB no Windows e geração do UTBMap.kext.

A lógica de classificação de portas, mescla de leituras e geração do kext é
portada do USBToolBox (https://github.com/USBToolBox/tool), de Dhinak G, sob a
licença MIT (third_party/USBToolBox/LICENSE). A leitura das portas foi
reescrita com as IOCTLs de hub do Windows, sem o usbdump.exe.
"""
