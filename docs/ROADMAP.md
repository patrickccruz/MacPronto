# Roadmap

O plano original previa sprints de 2 semanas. A partir de 22/10/2026 a implementação passou a ser feita de forma contínua, sem cadência de sprints; a lista abaixo continua organizada pelos blocos originais só para acompanhar o andamento.

## Status em 22/10/2026

**Funciona de ponta a ponta no modo de desenvolvimento** (`python -m macpronto`), testado com o hardware real de um Lenovo ThinkCentre M80q (i5-10500T, UHD 630):

- Diagnóstico, laudo, escolha da versão do macOS, montagem da EFI (validada pelo `ocvalidate`, sem problemas), mapeamento USB, download do macOS Recovery (884 MB do Sequoia, verificado com a assinatura da Apple) e geração do guia em HTML e PDF.
- 39 testes automáticos passando (laudo com 5 máquinas sintéticas, EFI, USB, regras de segurança do pendrive e guia).

**Implementado, mas ainda sem validação real:**

- Formatação e gravação do pendrive: a lógica e as regras de segurança têm testes automáticos, mas nenhum pendrive foi formatado ainda.
- Empacotamento: `scripts/build.py` (Nuitka), `installer/MacPronto.iss` (Inno Setup) e o workflow do GitHub Actions (`docs/ci/build.yml`) estão escritos. A primeira compilação com o Nuitka foi interrompida no início, a pedido.
- Regras de notebooks, AMD e hardware antigo: vêm do OpCore Simplify e foram conferidas no laudo com relatórios sintéticos, mas nenhuma EFI foi testada nessas máquinas.

### Próximos passos

1. Concluir a compilação com o Nuitka e testar o `.exe` (abrir como administrador, worker do motor, WebView2).
2. Testar a criação do pendrive com um pendrive de verdade e dar boot nesta máquina.
3. Gerar o instalador e a versão portátil. Ativar o GitHub Actions: rodar `gh auth refresh -h github.com -s workflow` (o token atual não tem o escopo `workflow`) e mover `docs/ci/build.yml` para `.github/workflows/build.yml`. A build do executável roda só manualmente ou em tags `v*`.
4. Testar o `.exe` contra o Windows Defender e outros antivírus.
5. Atualização da base de regras sob demanda (baixar o OpCore Simplify mais novo, validar com os testes e permitir voltar à versão travada).
6. Testes com amigos (desktops AMD, notebooks e máquinas antigas) usando o modo simulação e máquinas reais.

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
- [ ] Protótipo com pywebview + Nuitka executando como administrador (pywebview validado; compilação com o Nuitka pendente)
- [ ] Testar o .exe contra o Windows Defender e outros antivírus
- [x] Confirmar as licenças das ferramentas de terceiros (BSD-3-Clause e MIT)

### Fundação
- [x] Estrutura do projeto (backend Python + frontend React)
- [x] Ponte Python ↔ JavaScript
- [x] Kit visual: cores, tipografia, componentes, modo claro e escuro
- [x] Navegação do assistente (passo a passo)
- [x] Registros (logs)
- [ ] Build automática do .exe no GitHub Actions (workflow escrito em `docs/ci/build.yml`, ainda não ativado)

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
- [ ] Formatação do pendrive (GPT + FAT32) (implementada; falta teste com pendrive real)
- [x] Download do macOS Recovery com barra de progresso
- [ ] Cópia da EFI e verificação final (implementada; falta teste com pendrive real)

### Guia passo a passo (desktop)
- [x] Configurações de BIOS por fabricante (ASUS, Gigabyte, MSI, ASRock)
- [x] Instalação e pós-instalação
- [x] Solução de problemas por sintoma
- [x] Exportação em HTML/PDF, cópia no pendrive e QR code

**🏁 Marco 2: MVP desktop** (falta validar o pendrive e o boot em máquina real)

### Notebooks
- [ ] Trackpad, bateria, brilho e desligamento da GPU dedicada (regras do OpCore Simplify no laudo e na EFI; falta testar em notebook real)
- [x] Regras específicas no laudo (ex.: vídeo Iris Xe é incompatível)
- [x] BIOS de Dell, Lenovo, HP e Acer no guia

### Versões antigas e casos especiais
- [x] Fluxo de pós-instalação com OCLP (no guia, quando a EFI exige)
- [ ] CPUs sem AVX2, GPUs legadas, AMD Ryzen (laudo pronto; falta validar a EFI em máquinas reais)
- [x] Atualização automática de kexts (sempre as versões mais novas na montagem da EFI)
- [ ] Atualização da base de regras sob demanda

### Beta e acabamento
- [ ] Testes com amigos e correções
- [ ] Instalador (Inno Setup) e versão portátil (scripts escritos, ainda não gerados)
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
| Formatar o disco errado | Só discos USB entre 4 e 256 GB que não sejam do Windows, confirmação dupla e nova conferência da identidade do disco logo antes do diskpart |
| Variedade de hardware | Modo simulação com laudos de amigos e testes em máquinas reais |
| Ferramentas que ignoram hardware real (ex.: usbdump com o Parsec) | Leitura própria das portas pelas APIs do Windows |
