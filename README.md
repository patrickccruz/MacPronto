# MacPronto

> Analisa o seu PC ainda no Windows, diz se ele pode virar um Hackintosh e até qual macOS ele aguenta, e prepara o pendrive de instalação com um passo a passo feito para a sua máquina.

![status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![plataforma](https://img.shields.io/badge/plataforma-Windows%2010%20%7C%2011-blue)
![licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

> [!WARNING]
> Projeto pessoal, para uso próprio e de amigos. Instalar o macOS em hardware que não é da Apple viola a licença do macOS, e a instalação **apaga o disco do computador**. Leia a [Política de Uso](POLITICA-DE-USO.md) antes de usar.

## Como funciona

O MacPronto roda **no próprio computador que vai virar Hackintosh**, enquanto ele ainda tem Windows:

1. **Diagnóstico**: lê processador, placa-mãe, vídeo, áudio, rede, Wi-Fi, USB e tabelas ACPI.
2. **Laudo**: mostra componente por componente o que funciona nativamente, o que precisa de ajuste, o que precisa ser trocado e o que é incompatível.
3. **Versão do macOS**: recomenda a versão mais estável para a máquina e indica até qual ela chega (do High Sierra ao Tahoe).
4. **EFI**: gera a pasta EFI do OpenCore, com kexts, patches ACPI, `config.plist` e SMBIOS.
5. **Mapeamento USB**: mapeia as portas USB ainda no Windows, onde isso é mais fácil.
6. **Pendrive**: formata o pendrive escolhido e baixa o macOS Recovery direto dos servidores da Apple.
7. **Guia personalizado**: passo a passo de BIOS, instalação e pós-instalação. Fica salvo no próprio pendrive e abre no celular por QR code, porque depois da formatação o Windows deixa de existir.

Com o pendrive pronto, você desliga o PC, ajusta a BIOS, dá boot pelo pendrive e instala o macOS seguindo o guia.

## Requisitos previstos

- Windows 10 ou 11, 64 bits, com permissão de administrador
- Pendrive de 16 GB ou mais (todo o conteúdo dele será apagado)
- Internet, de preferência por cabo de rede
- Backup completo do computador

## Tecnologia

| Camada | Tecnologia |
|---|---|
| Lógica | Python 3.12 |
| Interface | React + TypeScript + Tailwind + shadcn/ui |
| Janela | pywebview (Edge WebView2) |
| Empacotamento | Nuitka + Inno Setup |

## Roadmap

| Marco | Conteúdo |
|---|---|
| **Marco 1: Diagnóstico** | Laudo de compatibilidade e versão do macOS indicada |
| **Marco 2: MVP desktop** | EFI, pendrive e guia completos para desktops |
| **v1.0** | Notebooks, versões antigas do macOS e acabamento |

O plano detalhado, sprint por sprint, está em [docs/ROADMAP.md](docs/ROADMAP.md).

## Créditos

O MacPronto não reinventa a roda: ele organiza ferramentas da comunidade Hackintosh. Cada uma mantém a própria licença.

- [OpCore Simplify](https://github.com/lzhoang2801/OpCore-Simplify) e [Hardware Sniffer](https://github.com/lzhoang2801/Hardware-Sniffer), de lzhoang2801
- [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) e kexts como [Lilu](https://github.com/acidanthera/Lilu), da Acidanthera
- [gibMacOS](https://github.com/corpnewt/gibMacOS) e [SSDTTime](https://github.com/corpnewt/SSDTTime), da CorpNewt
- [USBToolBox](https://github.com/USBToolBox/tool)
- [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher), da Dortania, e o [fork de lzhoang2801](https://github.com/lzhoang2801/OpenCore-Legacy-Patcher) com suporte ao Tahoe
- [Guia de instalação do OpenCore](https://dortania.github.io/OpenCore-Install-Guide/), da Dortania

## Licença

O código do MacPronto é distribuído sob a [licença MIT](LICENSE).

Apple, Mac e macOS são marcas registradas da Apple Inc. O MacPronto não é afiliado, patrocinado nem endossado pela Apple.
