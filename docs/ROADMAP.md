# Roadmap

O plano original previa sprints de 2 semanas. A partir de 22/10/2026 a implementação passou a ser feita de forma contínua, sem cadência de sprints; a lista abaixo continua organizada pelos blocos originais só para acompanhar o andamento.

## Status em 23/10/2026

**O executável funciona.** O `MacPronto.exe` gerado pelo Nuitka foi testado neste Lenovo ThinkCentre M80q (i5-10500T, UHD 630):

- A janela abre com a interface completa e a ponte com o Python.
- O autoteste (`MacPronto.exe --selftest --full`) passa nos 7 itens: recursos empacotados, motor em subprocesso, laudo e guia, QR code, portas USB, discos e coleta do hardware.
- Uma EFI completa foi montada pelo próprio executável, do zero (download do OpenCore 1.0.9 e de 16 kexts, 7 SSDTs compiladas), em 83 segundos, e o `ocvalidate` não encontrou problemas.
- O Windows Defender (assinaturas de 23/10/2026) não encontrou ameaças no executável, no instalador nem no portátil.
- Saídas da build: instalador de 15,2 MB e versão portátil de 19,9 MB.
- O instalador foi testado: instalação silenciosa em `C:\Program Files\MacPronto` (54 MB), atalhos no menu Iniciar, registro em Programas e Recursos e desinstalação completa. O programa instalado pede administrador pelo UAC ao abrir e passou no autoteste completo já elevado.
- 122 testes automáticos passando.

No modo de desenvolvimento também foram validados com o hardware real: diagnóstico, laudo, mapeamento USB, download do macOS Recovery (884 MB do Sequoia, conferido com a assinatura da Apple) e guia em HTML e PDF.

**Pendrive criado do começo ao fim** num SanDisk Cruzer Blade de 64 GB: FAT32 de 16 GB, macOS Recovery reaproveitado do computador e conferido, EFI e guia. O caminho até aqui:

- Os dois primeiros testes falharam no diskpart. O primeiro erro foi o `convert gpt` num pendrive que já era GPT; o segundo, o `format` rodando antes de o Windows montar a partição nova ("Nenhum volume foi selecionado").
- A formatação foi refeita em etapas: apaga e particiona, espera o volume (com `rescan`) e formata, com o PowerShell como alternativa.
- No terceiro teste, o GPT ainda falhou (a partição removível demora a aparecer) e a reserva em MBR funcionou de primeira. Agora o MBR é a primeira tentativa, com GPT de reserva; os dois caminhos passaram num disco virtual.

Primeiro boot pelo pendrive: o OpenCore abriu, mas só mostrava o Windows (o `HideAuxiliary` do OpCore Simplify esconde o macOS Recovery). Contorno: barra de espaço no menu; desde a `v0.1.0-beta.3` a EFI sai com `HideAuxiliary = false`. Falta escolher o instalador e instalar.

**Também nesta etapa:**

- O macOS Recovery salvo no computador é reaproveitado: o MacPronto confere na Apple e só baixa de novo se houver uma imagem mais nova (sem internet, usa a salva).
- Pendrive, EFI e diagnóstico continuam visíveis ao trocar de tela (cartão flutuante com a porcentagem).
- Atualização automática: a cada minuto o programa lê o feed de versões do GitHub e, com autorização do usuário, baixa o instalador (conferido pelo SHA-256 do `macpronto-update.json`), instala em modo silencioso e reabre. Testada de ponta a ponta com o programa instalado e um servidor local no lugar do GitHub. O repositório passou a ser público em 23/10/2026.
- A EFI e o mapa USB de uma sessão anterior voltam ao abrir o diagnóstico.
- Primeira versão pública: `v0.1.0-beta.1`, publicada pelo GitHub Actions como pré-lançamento.
- Guia por marca e linha de produto (`v0.1.0-beta.2`), em três níveis: linha de produto, tipo de BIOS e genérico.
  - Os perfis ficam em `src/macpronto/guide/bios_profiles.json`: Lenovo, Dell e HP por linha; Acer, notebooks ASUS e MSI, Samsung, Positivo, Vaio, Compaq, Multilaser e Avell; placas-mãe de PC montado; e AMI, Insyde e Phoenix.
  - Cada perfil traz o nível de confiança. Todos estão como "documentação" até alguém conferir numa máquina real e anotar o modelo em `checked_on`.
  - Na tela do Guia dá para trocar o perfil à mão.

**Implementado, mas ainda sem validação real:**

- A desinstalação passou a apagar `%LOCALAPPDATA%\MacPronto` (motor, caches e registros), preservando `Documentos\MacPronto`; essa limpeza ainda não foi retestada.
- Regras de notebooks, AMD e hardware antigo: vêm do OpCore Simplify e foram conferidas no laudo com relatórios sintéticos, mas nenhuma EFI foi testada nessas máquinas.

**Corrigido nesta etapa:**

- Os downloads do OpCore Simplify e do Hardware Sniffer desligavam a verificação TLS quando não achavam o `cert.pem` nem o `certifi`. Agora usam o repositório de certificados do Windows.
- No executável, o código de terceiros não carregava (colisão da pasta `scripts/` com o pacote `Scripts` e caminho errado do worker).

### Primeira instalação completa: notebook VAIO VJFE (28 e 29/10/2026)

Um Positivo VAIO VJFE (i5-10210U, Wi-Fi Intel AC 9462, touchpad Synaptics I2C) foi do diagnóstico ao macOS Sonoma ligando pelo disco interno, sem o pendrive. Os detalhes estão em `docs/CONTEXTO-PARA-IA.md`, erros 12 a 15. O que precisou de ajuste à mão virou melhoria no programa, na `main`:

- mapa USB com avisos de portas sem teste e o botão "Completar até 15";
- EFI com o teclado ABNT2 PS/2 (opção ISO do VoodooPS2), o touchpad I2C pelo VoodooI2CHID e o itlwm sem as redes de exemplo;
- pendrive com a EFI definitiva (sem `-v`, menu escondido), o HeliPort, o `AJUDA-IA.md` (para colar numa IA) e o `Bem-vindo-ao-Mac.html`;
- guia com a pós-instalação completa: Wi-Fi, teclado, trackpad, USB, cópia da EFI para o disco interno e Apple ID.

### Próximos passos

1. Publicar uma versão com as melhorias do teste no VAIO e gerar um pendrive novo para conferir os arquivos novos.
2. Dar boot pelo pendrive no ThinkCentre M80q e instalar o macOS.
3. Conferir os caminhos da BIOS do ThinkCentre M80q durante o boot e marcar o perfil como conferido; repetir com as máquinas dos amigos.
4. Testar contra outros antivírus além do Windows Defender.
5. Testes com amigos (desktops AMD, notebooks e máquinas antigas), usando o modo simulação e máquinas reais.
6. Avaliar o suporte a caminhos longos: com uma pasta de usuário muito longa, alguns arquivos do OpenCore passam de 260 caracteres (ver Riscos).

## Premissas

- O programa roda **no computador de destino**, com Windows, antes da formatação.
- Cobre **desktops e notebooks**.
- Prioriza as versões recentes do macOS (Sequoia e Tahoe), mas recomenda versões mais antigas quando o hardware exigir.
- Público: uso próprio e de amigos.
- O macOS Tahoe (26) é a última versão com suporte a Intel. O Sequoia é a versão padrão recomendada, por ser a mais estável.

## Arquitetura

```
┌──────────────── MacPronto.exe (Nuitka, pede administrador) ─────────────┐
│  Interface: React + Tailwind + shadcn/ui (WebView2)                      │
│                ↕  ponte pywebview (respostas {ok, data|error} + eventos) │
│  Backend Python (src/macpronto)                                          │
│   ├─ engine/   worker em subprocesso para as ferramentas da comunidade   │
│   │            (cópia gravável em %LOCALAPPDATA%\MacPronto\engine)       │
│   ├─ scanner/  Hardware Sniffer + WMI + acpidump (hash conferido)        │
│   ├─ compat/   laudo em português, dificuldade e versão do macOS         │
│   ├─ efi/      OpCore Simplify como biblioteca + ajustes + ocvalidate    │
│   ├─ usb/      leitura das portas por IOCTL + lógica do USBToolBox       │
│   ├─ media/    discos, diskpart (GPT + FAT32) e macOS Recovery           │
│   └─ guide/    guia e laudo em HTML/PDF, QR code pela rede local         │
│  third_party/  OpCore Simplify, Hardware Sniffer, USBToolBox (Info.plist)│
│                e macrecovery, em commits travados (VERSIONS.json)        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Decisões tomadas durante a implementação

- **Cópia travada em vez de fork**: o código de terceiros fica sem modificações em `third_party/`, e um adaptador responde às perguntas do terminal do OpCore Simplify. As escolhas reais (Wi-Fi Intel, áudio no Tahoe, GPU AMD, layout de áudio, combinação de GPUs) viram decisões na interface.
- **Motor em subprocesso**: o OpCore Simplify e o Hardware Sniffer usam o mesmo nome de pacote (`Scripts`) e gravam na própria pasta, por isso rodam isolados.
- **Sem o usbdump.exe**: ele ignorava a controladora USB real quando havia um adaptador virtual (Parsec). As portas são lidas direto pelas IOCTLs de hub do Windows.
- **Administrador ao abrir**: o `.exe` pede elevação uma vez, porque formatar o pendrive exige.
- **Instalador em português**: a EFI define `prev-lang:kbd` como `pt-BR:128` (ABNT2), com opção de teclado americano.

## Andamento por bloco

### Validação
- [ ] Rodar o OpCore Simplify e o macrecovery em 2 ou 3 PCs reais (feito em 1 desktop Intel; faltam notebook e AMD)
- [x] Protótipo com pywebview + Nuitka, executando como administrador
- [x] Testar o .exe contra o Windows Defender
- [ ] Testar o .exe contra outros antivírus
- [x] Confirmar as licenças das ferramentas de terceiros (BSD-3-Clause e MIT)

### Fundação
- [x] Estrutura do projeto (backend Python + frontend React)
- [x] Ponte Python ↔ JavaScript
- [x] Kit visual: cores, tipografia, componentes, modo claro e escuro
- [x] Navegação do assistente (passo a passo)
- [x] Registros (logs)
- [ ] Build automática do .exe no GitHub Actions (workflow ativado em 23/10/2026; primeira execução em andamento)

### Diagnóstico
- [x] Coleta via WMI e IDs PCI
- [x] Extração das tabelas ACPI
- [x] Detecção de notebook, bateria e tela
- [x] Tela de raio-X do computador

### Motor de compatibilidade e laudo
- [x] Integração com as regras do OpCore Simplify
- [x] Faixa de versões do macOS por componente e interseção entre elas
- [x] Nota de dificuldade de 1 a 5
- [x] Exportação do laudo (.macpronto, HTML e PDF)
- [x] Modo simulação: carregar laudos exportados de outros computadores

**🏁 Marco 1: Diagnóstico** (atingido no modo de desenvolvimento)

### Geração da EFI (desktop)
- [x] OpCore Simplify em modo biblioteca (cópia travada + adaptador)
- [x] Cache de kexts
- [x] Geração do SMBIOS com macserial
- [x] Validação com ocvalidate

### Pendrive e mapeamento USB
- [x] Mapeamento interativo das portas USB
- [x] Listagem somente de discos removíveis, com confirmação dupla
- [x] Formatação do pendrive (MBR + FAT32, com GPT de reserva), testada com pendrive real
- [x] Download do macOS Recovery com barra de progresso e reaproveitamento da imagem salva
- [x] Cópia da EFI e verificação final, testada com pendrive real

### Guia passo a passo (desktop)
- [x] Configurações de BIOS por marca, linha de produto e tipo de BIOS (perfis em `bios_profiles.json`)
- [x] Instalação e pós-instalação
- [x] Solução de problemas por sintoma
- [x] Exportação em HTML/PDF, cópia no pendrive e QR code

**🏁 Marco 2: MVP desktop** (instalação completa feita num notebook em 29/10/2026; falta repetir num desktop)

### Notebooks
- [ ] Trackpad, bateria, brilho e desligamento da GPU dedicada (trackpad I2C, Wi-Fi Intel, teclado ABNT2 e USB validados no VAIO VJFE em 29/10/2026; faltam bateria, brilho e GPU dedicada)
- [x] Regras específicas no laudo (ex.: vídeo Iris Xe é incompatível)
- [x] BIOS de notebooks Dell, Lenovo, HP, Acer, ASUS, MSI, Samsung, Positivo, Multilaser e Avell no guia

### Versões antigas e casos especiais
- [x] Fluxo de pós-instalação com OCLP (no guia, quando a EFI exige)
- [ ] CPUs sem AVX2, GPUs legadas, AMD Ryzen (laudo pronto; falta validar a EFI em máquinas reais)
- [x] Atualização automática de kexts (sempre as versões mais novas na montagem da EFI)
- [x] Atualização da base de regras sob demanda (só ativa versões que passam no autoteste)

### Beta e acabamento
- [ ] Testes com amigos e correções
- [x] Instalador (Inno Setup) e versão portátil
- [x] Atualização automática pelas versões do GitHub
- [x] Ícone, tela "Sobre" e créditos
- [ ] Assinatura digital (opcional)

**🏁 v1.0**

## Riscos

| Risco | Mitigação |
|---|---|
| O OpCore Simplify muda a estrutura interna | Cópia travada em `third_party/`; os testes de integração rodam o motor de verdade e acusam quebras ao atualizar |
| O Tahoe depende do fork do OCLP | Sequoia como versão padrão |
| O macOS 27 não roda em Intel | Escopo assumido: o projeto vale para as versões atuais |
| Falso positivo de antivírus | Sem binários de terceiros no pacote além do necessário; Nuitka; assinatura digital opcional |
| Atualização com defeito deixa todos sem conserto | Instalador conferido por tamanho e SHA-256; nunca atualiza com tarefa em andamento; o instalador mantém a versão anterior se falhar; registro em `logs\atualizacao-<versão>.log` |
| Formatar o disco errado | Só discos USB entre 4 e 256 GB que não sejam do Windows, confirmação dupla e nova conferência da identidade do disco logo antes do diskpart |
| Variedade de hardware | Modo simulação com laudos de amigos e testes em máquinas reais |
| Ferramentas que ignoram hardware real (ex.: usbdump com o Parsec) | Leitura própria das portas pelas APIs do Windows |
| Caminhos com mais de 260 caracteres (pasta de usuário muito longa) | Dados em %LOCALAPPDATA%\MacPronto, com caminhos curtos; avaliar manifesto com suporte a caminhos longos |
