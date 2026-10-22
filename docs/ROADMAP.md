# Roadmap

Sprints de 2 semanas. O Sprint 0 dura 1 semana. Estimativa total: cerca de 4,5 meses em tempo integral, ou de 8 a 10 meses em meio período.

## Premissas

- O programa roda **no computador de destino**, com Windows, antes da formatação.
- Cobre **desktops e notebooks**.
- Prioriza as versões recentes do macOS (Sequoia e Tahoe), mas recomenda versões mais antigas quando o hardware exigir.
- Público: uso próprio e de amigos.
- O macOS Tahoe (26) é a última versão com suporte a Intel. O Sequoia é a versão padrão recomendada, por ser a mais estável.

## Arquitetura

```
┌──────────────── MacPronto.exe (Nuitka) ─────────────┐
│  Interface: React + Tailwind (WebView2)             │
│                ↕  ponte pywebview                   │
│  Backend Python                                     │
│   ├─ scanner/   WMI, IDs PCI, ACPI, bateria, tela   │
│   ├─ compat/    regras, laudo e versão do macOS     │
│   ├─ efi/       fork do OpCore Simplify (biblioteca)│
│   ├─ usb/       mapeamento via USBToolBox           │
│   ├─ media/     pendrive (diskpart) + macrecovery   │
│   └─ guide/     guia personalizado em HTML/PDF      │
└─────────────────────────────────────────────────────┘
```

## Sprints

### Sprint 0: Validação (1 semana)
- [ ] Rodar o OpCore Simplify e o macrecovery manualmente em 2 ou 3 PCs reais (desktop Intel, notebook e, se possível, AMD)
- [ ] Protótipo "olá mundo" com pywebview + Nuitka, executando como administrador
- [ ] Testar o .exe protótipo contra o Windows Defender e outros antivírus
- [ ] Confirmar as licenças das ferramentas de terceiros

### Sprint 1: Fundação
- [ ] Estrutura do projeto (backend Python + frontend React)
- [ ] Ponte Python ↔ JavaScript
- [ ] Kit visual: cores, tipografia, componentes, modo claro e escuro
- [ ] Navegação do assistente (passo a passo)
- [ ] Registros (logs)
- [ ] Build automática do .exe no GitHub Actions

### Sprint 2: Diagnóstico
- [ ] Coleta via WMI e IDs PCI
- [ ] Extração das tabelas ACPI
- [ ] Detecção de notebook, bateria e tela
- [ ] Tela de raio-X do computador

### Sprint 3: Motor de compatibilidade e laudo
- [ ] Integração com as regras do OpCore Simplify
- [ ] Faixa de versões do macOS por componente e interseção entre elas
- [ ] Nota de dificuldade de 1 a 5
- [ ] Exportação do laudo
- [ ] Modo simulação: carregar laudos exportados de outros computadores

**🏁 Marco 1: Diagnóstico**

### Sprint 4: Geração da EFI (desktop)
- [ ] Fork do OpCore Simplify em modo biblioteca
- [ ] Cache de kexts
- [ ] Geração do SMBIOS com macserial
- [ ] Validação com ocvalidate

### Sprint 5: Pendrive e mapeamento USB
- [ ] Mapeamento interativo das portas USB
- [ ] Listagem somente de discos removíveis, com confirmação dupla
- [ ] Formatação do pendrive (GPT + FAT32)
- [ ] Download do macOS Recovery com barra de progresso
- [ ] Cópia da EFI e verificação final

### Sprint 6: Guia passo a passo (desktop)
- [ ] Configurações de BIOS por fabricante (ASUS, Gigabyte, MSI, ASRock)
- [ ] Instalação e pós-instalação
- [ ] Solução de problemas por sintoma
- [ ] Exportação em HTML/PDF, cópia no pendrive e QR code

**🏁 Marco 2: MVP desktop**

### Sprint 7: Notebooks
- [ ] Trackpad, bateria, brilho e desligamento da GPU dedicada
- [ ] Regras específicas no laudo (ex.: vídeo Iris Xe é incompatível)
- [ ] BIOS de Dell, Lenovo, HP e Acer no guia

### Sprint 8: Versões antigas e casos especiais
- [ ] Fluxo de pós-instalação com OCLP
- [ ] CPUs sem AVX2, GPUs legadas, AMD Ryzen
- [ ] Atualização automática de kexts e da base de regras

### Sprint 9: Beta e acabamento
- [ ] Testes com amigos e correções
- [ ] Instalador (Inno Setup) e versão portátil
- [ ] Ícone, tela "Sobre" e créditos
- [ ] Assinatura digital (opcional)

**🏁 v1.0**

## Riscos

| Risco | Mitigação |
|---|---|
| O OpCore Simplify muda a estrutura interna | Fork com versões travadas e sincronização controlada |
| O Tahoe depende do fork do OCLP | Sequoia como versão padrão |
| O macOS 27 não roda em Intel | Escopo assumido: o projeto vale para as versões atuais |
| Falso positivo de antivírus | Testar desde o Sprint 0; usar Nuitka; assinatura digital opcional |
| Formatar o disco errado | Listar só discos removíveis e pedir confirmação dupla |
| Variedade de hardware | Modo simulação com laudos de amigos e testes em máquinas reais |
