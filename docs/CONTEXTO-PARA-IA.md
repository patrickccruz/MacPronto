# MacPronto: contexto para assistentes de IA

Este documento dá a um assistente de IA o contexto do projeto MacPronto, da máquina em que ele está sendo testado e dos erros já encontrados, para ajudar a diagnosticar problemas na instalação do macOS ou no próprio programa.

Atualizado em 29/10/2026, versão 0.1.0-beta.3. Repositório: https://github.com/patrickccruz/MacPronto (público, licença MIT).

## Como o assistente deve ajudar

- Responda em português do Brasil, em linguagem simples. O usuário não é especialista em Hackintosh.
- Antes de propor uma solução para um travamento no boot, peça uma **foto da tela com as últimas linhas do modo detalhado (verbose)**. A EFI já sai com `-v`, e a última linha antes de travar é o que identifica a causa.
- Use como referência principal o [guia de instalação do OpenCore da Dortania](https://dortania.github.io/OpenCore-Install-Guide/), seção Comet Lake (desktop), que é a geração da máquina de teste.
- O usuário só tem Windows até a instalação terminar. Mudanças no `config.plist` são feitas no Windows com o [ProperTree](https://github.com/corpnewt/ProperTree), ou gerando a EFI de novo no MacPronto.
- **Nunca peça nem repita números de série.** Em `PlatformInfo > Generic`, os campos `SystemSerialNumber`, `MLB`, `SystemUUID` e `ROM` são uma identidade de Mac gerada para esta máquina e não devem ser publicados. Se o usuário colar o `config.plist`, oriente a apagar esses quatro campos antes.
- Diga quando uma resposta for palpite. Não invente opções de BIOS nem valores de `config.plist`: se não tiver certeza, aponte a seção da Dortania correspondente.

## O que é o MacPronto

O MacPronto é um programa para Windows, em português, que prepara a instalação do macOS num PC (Hackintosh). Ele roda **no próprio computador de destino, antes de formatar**:

1. **Diagnóstico:** lê o hardware e as tabelas ACPI pelo Windows, sem alterar nada. Usa o Hardware Sniffer e consultas WMI.
2. **Laudo:** diz o que funciona no macOS, componente por componente, dá uma nota de dificuldade de 1 a 5 e recomenda a versão do macOS. O padrão é o Sequoia 15 (Darwin 24); o Tahoe 26 é o último com suporte a Intel.
3. **EFI:** monta a pasta do OpenCore com o [OpCore Simplify](https://github.com/lzhoang2801/OpCore-Simplify), usado como biblioteca, e valida com o `ocvalidate`.
4. **Mapa USB:** mapeia as portas USB ainda no Windows (por IOCTL, com a lógica do USBToolBox) e gera o `UTBMap.kext`.
5. **Pendrive:** baixa o macOS Recovery direto da Apple (`macrecovery.py` do OpenCorePkg), confere com o chunklist assinado pela Apple, formata o pendrive e copia o Recovery, a EFI e o guia.
6. **Guia:** gera um passo a passo em HTML e PDF, com a BIOS por marca e linha de produto, a instalação, a pós-instalação e os problemas comuns. Ele abre no celular por QR code.

O MacPronto **não** instala o macOS, não mexe no disco interno e não aplica os patches do OpenCore Legacy Patcher.

### O que o MacPronto muda na EFI gerada pelo OpCore Simplify

- `NVRAM > Add > 7C436110-AB2A-4BBB-A880-FE41995C9F82 > prev-lang:kbd` = `pt-BR:128`, para o teclado ABNT2 no instalador.
- `Misc > Boot > HideAuxiliary` = `false` (desde a 0.1.0-beta.3), para o instalador aparecer no menu do OpenCore. Veja o erro 6 do histórico.
- Com o mapa USB feito, o `UTBMap.kext` substitui o `UTBDefault.kext` (que ativa todas as portas).

### Como o pendrive fica

- **Formato:** MBR com uma partição FAT32 de 16 GB, rótulo `MACPRONTO`. Se o MBR falhar, o programa tenta GPT. A UEFI dá boot por FAT32 em MBR.
- **Conteúdo:**
  - `EFI\BOOT\BOOTx64.efi` e `EFI\OC\` (OpenCore, `config.plist`, drivers, kexts, ACPI);
  - `com.apple.recovery.boot\BaseSystem.dmg` e `BaseSystem.chunklist` (macOS Recovery, cerca de 880 MB);
  - `MacPronto\Guia.html`, `Guia.pdf` e `LEIA-ME.txt`.

### Onde ficam os arquivos no Windows

| O quê | Onde |
|---|---|
| Registros do programa | `%LOCALAPPDATA%\MacPronto\logs\macpronto-AAAAMMDD.log` |
| Registro da atualização automática | `%LOCALAPPDATA%\MacPronto\logs\atualizacao-<versão>.log` |
| macOS Recovery baixado (reaproveitado) | `%LOCALAPPDATA%\MacPronto\cache\recovery\<darwin>\` |
| EFIs montadas | `Documentos\MacPronto\EFI\<data>-<máquina>\EFI` e `macpronto-efi.json` |
| Mapa USB | `Documentos\MacPronto\USB\<diagnóstico>\UTBMap.kext` |
| Guias | `Documentos\MacPronto\Guias\<diagnóstico>\` |
| Diagnósticos | `Documentos\MacPronto\Diagnosticos\` |

## Arquitetura (para mudanças no código)

- **Núcleo em Python 3.12** (`src/macpronto`). A interface é React, TypeScript, Tailwind e shadcn (`frontend/`), aberta numa janela do Edge WebView2 pelo pywebview. As respostas da API têm o formato `{ok, data | error}`, e o progresso chega por eventos.
- **Módulos principais:**
  - `scanner/`: diagnóstico;
  - `compat/`: laudo;
  - `efi/`: montagem e ajustes da EFI;
  - `usb/`: mapa USB;
  - `media/`: discos, formatação com diskpart e Recovery;
  - `guide/`: guia, com os perfis de BIOS em `guide/bios_profiles.json`;
  - `updater.py`: atualização automática;
  - `api.py`: ponte com a interface.
- **Motor:** o OpCore Simplify e o Hardware Sniffer ficam numa cópia travada em `third_party/` e rodam num processo separado (`MacPronto.exe --engine`), porque os dois têm um pacote Python chamado `Scripts`.
- **Distribuição:**
  - o executável é compilado com o Nuitka e pede administrador ao abrir (formatar exige);
  - o instalador é gerado com o Inno Setup;
  - o GitHub Actions roda os testes a cada envio e, numa tag `v*`, compila, roda o autoteste do executável e publica a versão.
- **Atualização automática:**
  - o programa lê `github.com/patrickccruz/MacPronto/releases.atom` a cada minuto e o `macpronto-update.json` de cada versão, que traz o tamanho e o SHA-256 do instalador;
  - com a autorização do usuário, roda o instalador com `/SILENT /ATUALIZACAO`.
- **Testes e checagens:**
  - `python -m pytest` (122 testes);
  - `python -m ruff check src tests`;
  - na pasta `frontend`: `npx tsc -b` e `npx oxlint src`;
  - build com `python scripts/build.py`.

## Máquina de teste atual

| Item | Valor |
|---|---|
| Computador | Lenovo ThinkCentre M80q (Tiny), tipo 11DQ |
| BIOS | Lenovo M2WKT65A, de 28/05/2026. Entra com F1; menu de boot com F12 |
| Chipset | Intel Q470 |
| Processador | Intel Core i5-10500T (Comet Lake-S, 10ª geração) |
| Vídeo | Intel UHD Graphics 630, ID 8086:9BC8 (integrado, sem placa de vídeo) |
| Monitores | Dois Lenovo S22e-18: um no HDMI e outro na DisplayPort do vídeo integrado |
| Áudio | Realtek (HDA) e o áudio do vídeo integrado |
| Rede | Ethernet Intel I219-LM; Wi-Fi Intel AX201 (Wi-Fi 6) com Bluetooth Intel |
| Armazenamento | NVMe WD PC SN740 256 GB (sem DRAM, da família do SN770); controladora SATA em AHCI |
| Pendrive | SanDisk Cruzer Blade 64 GB (USB 2) |

### EFI gerada para essa máquina

- **Versões:** OpenCore 1.0.9 para o macOS Sequoia 15 (Darwin 24); SMBIOS `iMac20,1`.
- **boot-args:** `-v debug=0x100 keepsyms=1 igfxonln=1 -igfxvesa`. O `-igfxvesa` (modo VESA, sem aceleração de vídeo) foi ligado porque há monitor no HDMI do vídeo integrado.
- **SSDTs:** SSDT-SBUS, SSDT-EC, SSDT-MCHC, SSDT-PLUG, SSDT-RTCAWAC, SSDT-USB-Reset e SSDT-USBX.
- **Kexts:** Lilu, VirtualSMC, SMCProcessor, SMCSuperIO, WhateverGreen, AppleALC, IntelMausiEthernet, AirportItlwm, IntelBluetoothFirmware, IntelBTPatcher, BlueToolFixup, NVMeFix, RestrictEvents, USBToolBox, UTBMap e XHCI-unsupported.
- **DeviceProperties:**
  - vídeo integrado (`PciRoot(0x0)/Pci(0x2,0x0)`): `AAPL,ig-platform-id` = `00009B3E` (0x3E9B0000), com `framebuffer-patch-enable` e `framebuffer-stolenmem`;
  - áudio (`PciRoot(0x0)/Pci(0x1f,0x3)`): `layout-id` = 3.
- **Quirks:**
  - Kernel: AppleXcpmCfgLock, DisableIoMapper, DisableLinkeditJettison, PanicNoKextDump, PowerTimeoutKernelPanic e CustomSMBIOSGuid;
  - Booter: AvoidRuntimeDefrag, DevirtualiseMmio, EnableSafeModeSlide, FixupAppleEfiImages, ProtectUefiServices, ProvideCustomSlide, RebuildAppleMemoryMap, SetupVirtualMap e SyncRuntimePermissions;
  - UEFI: ReleaseUsbOwnership, RequestBootVarRouting e EnableVectorAcceleration.
- **Segurança:** `ScanPolicy` = 0, `DmgLoading` = Signed, `SecureBootModel` = Disabled e `Vault` = Optional.
- **Drivers:** HfsPlus.efi, OpenRuntime.efi e ResetNvramEntry.efi.
- **Pedidos do laudo para a BIOS:** ativar o Above 4G Decoding e desativar o Resizable BAR. Na BIOS do ThinkCentre, essas opções provavelmente não existem.

## Situação dos testes em 23/10/2026

**Já funcionou nessa máquina:**
- diagnóstico, laudo e EFI sem erros no `ocvalidate`;
- mapa USB com 26 portas na controladora XHC;
- download e verificação do Recovery do Sequoia (produto 696-28424);
- pendrive criado do começo ao fim (MBR, FAT32);
- guia;
- instalador do programa e atualização automática pelo GitHub (da 0.1.0-beta.1 para a 0.1.0-beta.2).

**Primeiro boot pelo pendrive:** o OpenCore abriu, mas o menu só mostrava o Windows. A causa foi o `HideAuxiliary` (erro 6 do histórico). Contorno: apertar a barra de espaço no menu do OpenCore.

**Ainda não testado:** escolher o instalador, a instalação do macOS e a pós-instalação.

## Teste em notebook: Positivo VAIO VJFE (28 e 29/10/2026)

Primeiro notebook real. O MacPronto 0.1.0-beta.3 rodou no próprio notebook, que depois foi formatado com o pendrive.

| Item | Valor |
|---|---|
| Computador | Positivo VAIO VJFE (o diagnóstico mostra "Positivo Bahia - VAIO VJFE") |
| Processador | Intel Core i5-10210U (Comet Lake-U, 10ª geração) |
| Vídeo | Intel UHD Graphics (integrado) |
| Rede | Ethernet Realtek (RealtekRTL8111); Wi-Fi Intel Wireless-AC 9462 (CNVi) com Bluetooth Intel |
| Entrada | Touchpad Synaptics I2C (ID `SYNA…`, da lista `InputIDs` do OpCore Simplify) e teclado PS/2 |
| Armazenamento | NVMe CA5-8D256 |
| macOS | Sonoma 14 (Recovery 696-08090, Darwin 23); SMBIOS `MacBookPro16,3`; OpenCore 1.0.9 |

**EFI gerada:**
- boot-args: `-v debug=0x100 keepsyms=1 -igfxblt -vi2c-force-polling`;
- SSDTs: ALSD, SBUS, EC, GPI0, MCHC, PLUG, PNLF, RTCAWAC, USB-Reset, USBX e XOSI;
- Wi-Fi: `itlwm` 2.3.0. O `WiFiConfig` do `Info.plist` ficou com as 4 redes de exemplo do próprio itlwm, e não com as redes do Windows (veja "Redes do Windows no itlwm" abaixo);
- touchpad: VoodooI2C 2.9.1 com VoodooRMI 1.4.3 (RMII2C); o VoodooI2CHID ia na pasta `Kexts`, mas fora do `config.plist`.

**Resultados:**
- A instalação terminou. O macOS ainda inicia pelo pendrive: a EFI não foi copiada para o disco interno.
- **Touchpad:** não funcionou com VoodooRMI + RMII2C. Funcionou depois de desativar os dois e ativar o VoodooI2CHID (erro 12).
- **Wi-Fi (resolvido em 29/10/2026, erro 13):** conectou depois que o HeliPort foi copiado para Aplicativos e usado pelo ícone dele. Como se chegou lá:
  - o driver funciona: `kextstat -b com.zxystd.itlwm` mostra o itlwm 2.3.0 carregado, e `ioreg -r -c itlwm -d 1` mostra o serviço `itlwm` ativo ("registered, matched, active"), com endereço MAC e `IOLinkStatus = 1` (sem conexão);
  - o usuário relatou "Wi-Fi desativado". O menu fotografado termina em "Ajustes de Wi-Fi…", que é o menu de Wi-Fi do próprio macOS (o HeliPort 1.5.0 mostra "Wi-Fi Settings..." sem tradução). Com o itlwm, o Wi-Fi do macOS fica sempre desligado, e a conexão é feita pelo HeliPort;
  - aberto direto do `.dmg`, o HeliPort avisa "HeliPort rodando em um caminho inesperado" e só oferece sair; ele precisa estar em Aplicativos;
  - arrastar o ícone com o botão físico do touchpad abria a Visualização Rápida (provável leitura como clique firme). Contornos: copiar e colar (Command + C / Command + V), o mouse USB ou "Arrastar com três dedos" em Acessibilidade.
- **Teclado ABNT2 (em investigação):** a tecla à esquerda do Z e a tecla abaixo do Esc digitam `§`/`±` e `` ` ``/`¨`, como num teclado Apple ISO. No layout Brasileiro do macOS, a barra vertical (`|`) não fica em nenhuma das duas. Enquanto isso, os comandos passados ao usuário evitam o `|`; o Visualizador de Teclado é o contorno. A EFI usa `prev-lang:kbd` = `pt-BR:128`, que na lista do OpenCore (`AppleKeyboardLayouts.txt`) é "Brazilian-ABNT2" (71 é "Brazilian" e 72 é "Brazilian - Pro"). Isso vale para o instalador; o macOS instalado provavelmente ficou com outro layout. Próximo teste: ativar a fonte de entrada "Brasileiro – ABNT2" nos Ajustes.
  - Com o "Brasileiro – ABNT2" ativo, as duas teclas ficaram trocadas entre si: abaixo do Esc sai `\`, e ao lado do Z sai `'`. Trocar o tipo de teclado no macOS ("Alterar Tipo de Teclado…", ISO e depois ANSI) não mudou nada.
  - Em 29/10/2026 foi ligada a opção `Use ISO layout keyboard` do VoodooPS2Keyboard (`Platform Profile > Default`), que troca o mapeamento das scancodes PS/2 0x29 e 0x56. O original está em `MacPronto\backup\VoodooPS2Keyboard-Info-original.plist`. Falta testar depois de reiniciar.
  - Se funcionar, o MacPronto pode ligar essa opção sozinho em notebooks com teclado ABNT2 PS/2.
- **USB (em investigação):** uma porta não funciona no macOS, nem com mouse com fio nem com o pendrive; a outra funciona. A BIOS dá boot por ela, mas o macOS só ativa as portas do `UTBMap.kext`, e o mapeamento no Windows só marca as portas que receberam algum dispositivo (ou cuja companheira USB 2/USB 3 recebeu). Provavelmente essa porta, ou o lado USB 2 dela, não foi testada no mapeamento.
  - O notebook tem três portas: uma USB-A de cada lado (só a da direita funciona) e uma USB-C do lado esquerdo, ainda sem teste.
  - O `UTBMap.kext` tinha só HS02, HS04, HS05, HS07 (tipo 0) e HS10 (tipo 255). Nenhuma porta USB 3.
  - Em 29/10/2026 o mapa foi ampliado para o limite de 15 portas: HS01–HS10 e SS01–SS05 (tipo 3, índices 13–17). A numeração supõe o padrão do PCH Comet Lake-U, com USR1/USR2 em 11–12 e SS01–SS06 em 13–18; a SS06 ficou de fora. O original está em `MacPronto\backup\UTBMap-Info-original.plist` no pendrive.
  - Falta testar a porta esquerda e a USB-C e, se der, enxugar o mapa com os IDs de localização das portas reais (Informações do Sistema > USB).
- **Redes do Windows no itlwm (pendente no código):** o OpCore Simplify pergunta "Would you like to scan for WiFi profiles? (Yes/no)", e o adaptador não tem regra para essa pergunta. Ele responde com Enter, que é inválido; na 4ª repetição sai o `prompt-unknown`, que o `except` sem tipo de `modify_kexts` engole. O itlwm fica com as redes de exemplo. Falta decidir se o MacPronto oferece a importação (ela grava senhas de Wi-Fi em texto puro na EFI e no `ioreg`) ou responde "no" e limpa as redes de exemplo.

## Histórico de erros já resolvidos

| # | Sintoma | Causa | Solução |
|---|---|---|---|
| 1 | diskpart: "O disco especificado não está formatado em MBR" | `convert gpt` num pendrive que continuava GPT depois do `clean` | `convert ... noerr` |
| 2 | diskpart: "Nenhum volume foi selecionado" no `format` | O Windows ainda não tinha montado o volume da partição recém-criada | Formatar em etapas: criar, esperar o volume (com `rescan`) e formatar; PowerShell `Format-Volume` como reserva |
| 3 | Janelas do Windows: "Você precisa formatar o disco na unidade X:" e "X: não está acessível" durante a gravação | O volume vazio (RAW) aparece por alguns segundos, e o Explorer reage a ele | Inofensivo: clicar em Cancelar. O programa avisa na tela |
| 4 | diskpart em GPT: "O sistema não pode encontrar o arquivo especificado" | Comando na partição logo depois de criá-la, num pendrive removível | MBR passou a ser a primeira tentativa |
| 5 | diskpart: "O dispositivo não está pronto" (0x80070015); Log de Eventos do Sistema: "Não é possível zerar os setores do disco PhysicalDriveN" | O pendrive não respondia à gravação. Ele foi ejetado e continuou conectado, ou travou | Desconectar e conectar de novo, de preferência na porta traseira; se repetir, trocar o pendrive. Desde a beta.3 há mensagem clara, e o programa não repete a tentativa em GPT |
| 6 | No menu do OpenCore só aparece o Windows | `Misc > Boot > HideAuxiliary = true` (padrão do OpCore Simplify) esconde o Recovery do pendrive, que conta como entrada auxiliar | Apertar a barra de espaço no menu. Desde a beta.3 a EFI sai com `HideAuxiliary = false` |
| 7 | A atualização automática acusava 404 no `macpronto-update.json` | A tag aparece no feed do GitHub uns 15 minutos antes de o GitHub Actions publicar os arquivos | O programa tenta de novo sozinho |
| 8 | Downloads sem verificação TLS no motor | O OpCore Simplify e o Hardware Sniffer desligam a verificação quando falta o `certifi` | O MacPronto troca pelo contexto TLS padrão do Windows |
| 9 | O executável não achava o código de terceiros | Colisão entre a pasta `scripts/` e o pacote `Scripts`; `sys.executable` errado no Nuitka | Exclusões no Nuitka; o caminho do executável vem de `sys.argv[0]` |
| 10 | O mapa USB não enxergava a controladora real | O `usbdump.exe` se confunde com o adaptador virtual do Parsec | Leitura própria das portas por IOCTL |
| 11 | Arquivos do OpenCore com caminho acima de 260 caracteres | Pasta de usuário muito longa | Dados em `%LOCALAPPDATA%\MacPronto`, com caminhos curtos. Ainda é um risco |
| 12 | Touchpad Synaptics I2C parado depois de instalar (VAIO VJFE) | Para touchpads `SYNA…` em I2C, o OpCore Simplify usa VoodooRMI + RMII2C e tira o VoodooI2CHID do `config.plist` (o arquivo continua na pasta `Kexts`) | Em `Kernel > Add`: desativar VoodooRMI e RMII2C e adicionar o VoodooI2CHID logo depois do VoodooInput do VoodooI2C. Confirmado em 29/10/2026 |
| 13 | Wi-Fi Intel aparece desligado depois de instalar (VAIO VJFE, itlwm) | Com o itlwm, o Wi-Fi do próprio macOS (ícone e Ajustes > Wi-Fi) fica sempre desligado; a placa aparece como rede cabeada e a conexão é feita pelo HeliPort | Copiar o HeliPort para Aplicativos e usar o ícone dele na barra de menus. Sem internet no macOS, levar o `HeliPort.dmg` no pendrive. Confirmado em 29/10/2026 |

## Próximos erros prováveis nessa máquina, etapa por etapa

São pontos de atenção para a instalação, com base no hardware e na EFI acima. Antes de agir, confirme com a foto da tela.

1. **O pendrive não aparece no menu de boot (F12).**
   - Confira na BIOS: Secure Boot desligado, CSM desligado e boot por USB permitido.
   - Use uma porta traseira.
   - A entrada costuma aparecer como "USB HDD: SanDisk" ou "UEFI: SanDisk".
2. **No menu do OpenCore só aparece o Windows.** Aperte a barra de espaço e escolha "macOS Base System" (erro 6).
3. **Trava em `[EB|#LOG:EXITBS:START]`.** É o problema mais comum de BIOS ou quirks de memória.
   - Confira de novo o Secure Boot e o CSM.
   - Sem a opção CFG Lock na BIOS, o `AppleXcpmCfgLock` já está ligado.
   - Consulte "Kernel Space Issues" na seção de solução de problemas da Dortania.
4. **Trava em `PCI configuration begin` ou `end`.** A BIOS não tem Above 4G Decoding. Acrescente `npci=0x2000` aos boot-args.
5. **Símbolo de proibido 🚫 ou "Waiting for Root Device".** Costuma ser USB.
   - Tente outra porta, de preferência USB 2.
   - Se o mapa USB estiver errado, teste com o `UTBDefault.kext` ativado e o `UTBMap.kext` desativado.
   - O `XHCI-unsupported` já está na EFI.
6. **Tela preta ou travada depois das linhas de texto.** É o vídeo integrado.
   - A EFI está em modo VESA (`-igfxvesa`), que deveria dar imagem sem aceleração.
   - Deixe um monitor só, de preferência na DisplayPort.
   - Para a aceleração depois de instalar, os valores de `AAPL,ig-platform-id` e `device-id` do UHD 630 Comet Lake de desktop estão na seção Comet Lake da Dortania. O `0x3E9B0000` foi o que o OpCore Simplify escolheu; confira antes de trocar.
7. **O Utilitário de Disco não mostra o NVMe.**
   - Confira o SATA em AHCI e se não há Intel RST ou VMD ligados.
   - O NVMeFix está na EFI.
   - Há relatos de problemas no macOS com alguns SSDs WD sem DRAM da família SN770. Se o instalador travar ou ficar muito lento ao copiar, considere testar com outro SSD. É uma suspeita, não uma confirmação.
8. **"O servidor de recuperação não pôde ser contatado".**
   - Acerte a data pelo Terminal da recuperação (comando `date`).
   - Use o cabo de rede: o I219-LM funciona com o IntelMausiEthernet.
   - O Wi-Fi AX201 com o AirportItlwm pode não funcionar no instalador do Sequoia.
9. **Reinicializações durante a instalação.** Em cada uma, dê boot pelo pendrive e escolha a entrada "macOS Installer" (ou o nome do disco) no OpenCore.
10. **Pós-instalação:**
    - copiar a EFI para a partição EFI do NVMe;
    - sem som: testar outros `layout-id` do codec Realtek;
    - Wi-Fi Intel: usar o AirportItlwm ou o itlwm com o HeliPort;
    - aceleração de vídeo: tirar o `-igfxvesa`, com o monitor na DisplayPort ou com o ajuste de portas do framebuffer.

## O que pedir ao usuário para diagnosticar

- Foto da tela no ponto em que parou, com as últimas linhas do verbose legíveis.
- A versão do MacPronto (canto superior esquerdo do programa) e a etapa em que estava.
- O registro do MacPronto: no programa, **Registros > Abrir pasta**, arquivo `macpronto-AAAAMMDD.log`. Ele não traz números de série.
- O diagnóstico exportado (**Laudo > Exportar diagnóstico**, arquivo `.macpronto`), que não traz números de série.
- Se for preciso, o `config.plist` da EFI, **sem os quatro campos de série** de `PlatformInfo > Generic`.
- Para erros do pendrive: o texto completo da mensagem, com os detalhes técnicos, e os eventos do Log de Eventos do Windows (Sistema) com origem "VDS Basic Provider" ou "disk".
