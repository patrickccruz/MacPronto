import { ArrowRight, ExternalLink, HardDriveDownload, ScanSearch, ShieldAlert, Sparkles, Usb, Wrench } from "lucide-react"
import { useState } from "react"

import { Logo } from "@/components/Logo"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { useApp } from "@/lib/store"

const POLICY_URL = "https://github.com/patrickccruz/MacPronto/blob/main/POLITICA-DE-USO.md"

const FLOW = [
  { icon: ScanSearch, title: "Diagnóstico", text: "Lê processador, vídeo, áudio, rede, USB e tabelas ACPI, sem alterar nada." },
  { icon: Sparkles, title: "Laudo e versão", text: "Mostra o que funciona e indica a versão do macOS mais estável para a máquina." },
  { icon: Wrench, title: "EFI e portas USB", text: "Monta a pasta do OpenCore e mapeia as portas USB ainda no Windows." },
  { icon: HardDriveDownload, title: "Pendrive e guia", text: "Prepara o pendrive com o macOS e um passo a passo feito para este computador." },
]

export function WelcomeStep() {
  const { settings, updateSettings, go } = useApp()
  const [accepted, setAccepted] = useState(settings.policy_accepted)

  async function start() {
    if (!settings.policy_accepted) await updateSettings({ policy_accepted: true })
    go("diagnosis")
  }

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-6 rounded-2xl border bg-card p-8 md:flex-row md:items-center">
        <Logo className="size-20 shrink-0" />
        <div className="space-y-3">
          <h1 className="text-3xl font-semibold tracking-tight text-balance">Transforme este PC num Hackintosh, sem adivinhação.</h1>
          <p className="max-w-2xl text-pretty text-muted-foreground">
            O MacPronto roda aqui no Windows, antes de qualquer formatação. Ele diz se o computador aguenta o macOS, até qual
            versão, e entrega um pendrive pronto com um guia feito para esta máquina.
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {FLOW.map((item, index) => (
          <Card key={item.title} size="sm">
            <CardContent className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <item.icon className="size-4.5" />
                </span>
                <span className="text-xs font-medium text-muted-foreground tabular-nums">Passo {index + 1}</span>
              </div>
              <p className="font-medium">{item.title}</p>
              <p className="text-sm text-muted-foreground">{item.text}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Alert className="border-tweak/40 bg-tweak/8">
        <ShieldAlert className="text-tweak" />
        <AlertTitle>Antes de começar</AlertTitle>
        <AlertDescription>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            <li>A licença do macOS só permite instalá-lo em computadores da Apple. A decisão de instalar é sua.</li>
            <li>
              A instalação <strong>apaga o disco do computador</strong>. Faça backup completo antes de formatar.
            </li>
            <li>O MacPronto só lê o hardware. O único disco que ele apaga é o pendrive que você escolher, com confirmação dupla.</li>
            <li>Nenhum dado é enviado aos autores. A internet é usada só para baixar o macOS da Apple e kexts do GitHub.</li>
          </ul>
        </AlertDescription>
      </Alert>

      <Card>
        <CardContent className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <Checkbox
              id="policy"
              checked={accepted}
              onCheckedChange={(value) => setAccepted(value === true)}
              className="mt-0.5"
            />
            <div className="space-y-1">
              <Label htmlFor="policy" className="leading-snug">
                Li e aceito a Política de Uso do MacPronto
              </Label>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                onClick={() => void api.openUrl(POLICY_URL)}
              >
                Ler a política completa
                <ExternalLink className="size-3" />
              </button>
            </div>
          </div>
          <Button size="lg" disabled={!accepted} onClick={() => void start()}>
            Começar o diagnóstico
            <ArrowRight data-icon="inline-end" />
          </Button>
        </CardContent>
      </Card>

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Usb className="size-3.5" />
        Você vai precisar de um pendrive de 16 GB ou mais e, de preferência, internet por cabo.
      </p>
    </div>
  )
}
