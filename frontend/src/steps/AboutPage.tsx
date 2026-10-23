import { ExternalLink } from "lucide-react"

import { Logo } from "@/components/Logo"
import { PageHeader } from "@/components/PageHeader"
import { RulesCard } from "@/components/RulesCard"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { useApp } from "@/lib/store"

const CREDITS = [
  { name: "OpCore Simplify", author: "lzhoang2801", url: "https://github.com/lzhoang2801/OpCore-Simplify", role: "Regras de compatibilidade e geração da EFI" },
  { name: "Hardware Sniffer", author: "lzhoang2801", url: "https://github.com/lzhoang2801/Hardware-Sniffer", role: "Coleta do hardware no Windows" },
  { name: "OpenCorePkg", author: "Acidanthera", url: "https://github.com/acidanthera/OpenCorePkg", role: "Bootloader, macrecovery, ocvalidate e macserial" },
  { name: "Lilu, VirtualSMC, WhateverGreen, AppleALC", author: "Acidanthera", url: "https://github.com/acidanthera", role: "Kexts essenciais" },
  { name: "USBToolBox", author: "Dhinak G", url: "https://github.com/USBToolBox/tool", role: "Mapeamento de portas USB" },
  { name: "SSDTTime e gibMacOS", author: "CorpNewt", url: "https://github.com/corpnewt", role: "Patches ACPI (via OpCore Simplify)" },
  { name: "OpenCore Legacy Patcher", author: "Dortania", url: "https://github.com/dortania/OpenCore-Legacy-Patcher", role: "Pós-instalação em hardware antigo" },
  { name: "Guia de instalação do OpenCore", author: "Dortania", url: "https://dortania.github.io/OpenCore-Install-Guide/", role: "Base do guia passo a passo" },
  { name: "ACPICA", author: "Intel", url: "https://github.com/acpica/acpica", role: "acpidump e iasl" },
]

export function AboutPage() {
  const { info } = useApp()

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Sobre" title="MacPronto" description="Projeto pessoal, para uso próprio e de amigos. Código sob licença MIT." />

      <Card>
        <CardContent className="flex flex-wrap items-center gap-5">
          <Logo className="size-16" />
          <div className="flex-1 space-y-1">
            <p className="text-lg font-semibold">MacPronto {info?.version}</p>
            <p className="text-sm text-muted-foreground">
              Apple, Mac e macOS são marcas registradas da Apple Inc. O MacPronto não é afiliado, patrocinado nem endossado pela Apple.
            </p>
          </div>
          <Button variant="outline" onClick={() => void api.openUrl("https://github.com/patrickccruz/MacPronto")}>
            Repositório
            <ExternalLink data-icon="inline-end" />
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Créditos</CardTitle>
          <CardDescription>O MacPronto organiza ferramentas da comunidade Hackintosh. Cada uma mantém a própria licença.</CardDescription>
        </CardHeader>
        <CardContent className="divide-y">
          {CREDITS.map((credit) => (
            <div key={credit.name} className="flex items-center justify-between gap-4 py-2.5 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="font-medium">
                  {credit.name} <span className="font-normal text-muted-foreground">· {credit.author}</span>
                </p>
                <p className="text-sm text-muted-foreground">{credit.role}</p>
              </div>
              <Button variant="ghost" size="icon-sm" onClick={() => void api.openUrl(credit.url)} aria-label={`Abrir ${credit.name}`}>
                <ExternalLink />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <RulesCard />

      {info && Object.keys(info.components).length > 0 && (
        <Card size="sm">
          <CardHeader>
            <CardTitle>Versões que vêm com o MacPronto</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2">
            {Object.entries(info.components).map(([name, component]) => (
              <div key={name} className="text-sm">
                <p className="font-medium">{name}</p>
                <p className="font-mono text-xs text-muted-foreground">
                  {component.commit} · {component.license}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
