# Política de Uso

Última atualização: 22/10/2026

O MacPronto é um projeto pessoal, sem fins comerciais, compartilhado entre amigos. Ao usar o programa, você concorda com os termos abaixo.

## 1. Licença do macOS

- A licença do macOS (EULA) só permite instalar o sistema em computadores da Apple. Montar um Hackintosh viola essa licença.
- O MacPronto **não inclui, não hospeda e não redistribui** nenhum arquivo da Apple. O macOS é baixado diretamente dos servidores da Apple, por iniciativa de quem usa o programa.
- A decisão de instalar o macOS, e a responsabilidade por ela, são de quem usa.

## 2. Sem garantia

- O MacPronto é fornecido "como está", sem garantia de nenhum tipo (veja a [licença](LICENSE)).
- O laudo de compatibilidade é uma estimativa feita a partir de regras da comunidade Hackintosh. Ele não garante que tudo vá funcionar.
- A instalação do macOS **apaga o disco do computador**. Faça backup completo antes de começar.
- Alterar configurações da BIOS e instalar sistemas não suportados envolve risco. Os autores não se responsabilizam por perda de dados, defeitos no equipamento ou qualquer custo decorrente do uso.

## 3. O que o MacPronto faz no seu computador

- **Lê** informações do hardware e as tabelas ACPI, sem alterar nada.
- **Apaga e formata somente o pendrive que você escolher**, depois de uma confirmação dupla. Discos internos nunca aparecem como opção de formatação.
- Pede permissão de administrador, necessária para ler as tabelas ACPI e formatar o pendrive.
- Não altera o Windows, a BIOS nem os discos internos. A formatação do computador acontece depois, pelo instalador do macOS, seguindo o guia.

## 4. Privacidade

- Nenhum dado do seu computador é enviado aos autores ou a terceiros. Não há telemetria, conta nem cadastro.
- O programa só se conecta à internet para:
  - baixar o macOS Recovery dos servidores da Apple;
  - baixar kexts e ferramentas de código aberto do GitHub.
- O laudo, os registros (logs) e a pasta EFI ficam apenas no seu computador e no pendrive.
- Esses arquivos contêm números de série, inclusive os do SMBIOS gerado. **Apague os números de série antes de compartilhar** laudos ou a EFI em fóruns e grupos.

## 5. Segurança

- Baixe o MacPronto somente do repositório oficial ou de alguém em quem você confia.
- Antivírus podem acusar falso positivo, porque o programa formata discos e lê tabelas do firmware. Nunca desative o antivírus para rodar uma cópia de origem desconhecida.
- Encontrou uma falha de segurança? Avise o mantenedor ([@patrickccruz](https://github.com/patrickccruz)) em particular, sem abrir issue pública.

## 6. Software de terceiros

O MacPronto usa ferramentas de código aberto da comunidade. Cada uma mantém a própria licença e os próprios termos. A lista está na seção [Créditos do README](README.md#créditos).

## 7. Marcas

Apple, Mac e macOS são marcas registradas da Apple Inc. O MacPronto não é afiliado, patrocinado nem endossado pela Apple.
