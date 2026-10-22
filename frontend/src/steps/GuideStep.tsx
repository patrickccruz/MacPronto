import { BookOpenText, FileText, FolderOpen, RefreshCw, Smartphone, Wifi, WifiOff } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/PageHeader"
import { TaskPanel } from "@/components/TaskPanel"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { BridgeError } from "@/lib/bridge"
import { useApp } from "@/lib/store"
import type { GuideInfo, ShareInfo } from "@/lib/types"
import { useTask } from "@/lib/useTask"

const SECTIONS = [
  "Antes de começar: backup e o que ter em mãos",
  "Ajustes da BIOS do fabricante desta máquina, com as teclas e os caminhos dos menus",
  "Instalação passo a passo, do boot pelo pendrive à configuração inicial",
  "Pós-instalação: iniciar sem o pendrive, OCLP e ajustes finos",
  "Problemas e soluções por sintoma",
  "O que funciona e os detalhes técnicos da EFI",
]

export function GuideStep() {
  const { payload } = useApp()
  const task = useTask()
  const [guide, setGuide] = useState<GuideInfo | null>(payload?.guide ?? null)
  const [share, setShare] = useState<ShareInfo | null>(null)

  async function build() {
    const result = await task.run("guia", api.guideBuild)
    if (result) setGuide(result)
  }

  useEffect(() => {
    if (!guide) void build()
    // Gera o guia uma vez ao abrir a etapa
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(
    () => () => {
      void api.guideShareStop()
    },
    [],
  )

  async function startShare() {
    try {
      setShare(await api.guideShareStart())
    } catch (caught) {
      toast.error(caught instanceof BridgeError ? caught.message : String(caught))
    }
  }

  async function stopShare() {
    await api.guideShareStop()
    setShare(null)
  }

  if (!payload) return null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Guia"
        title="Guia de instalação desta máquina"
        description="Feito com o laudo, a EFI e a BIOS deste computador. Ele também vai para o pendrive, na pasta MacPronto."
        actions={
          <Button variant="outline" disabled={task.running} onClick={() => void build()}>
            <RefreshCw data-icon="inline-start" />
            Gerar de novo
          </Button>
        }
      />

      {task.running && <TaskPanel task={task} title="Gerando o guia" />}

      {!payload.efi && (
        <Alert>
          <BookOpenText />
          <AlertDescription>A EFI ainda não foi montada: o guia sai sem os detalhes técnicos dela. Monte a EFI e gere de novo.</AlertDescription>
        </Alert>
      )}

      {guide && !task.running && (
        <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <Card>
            <CardHeader>
              <CardTitle>O que tem no guia</CardTitle>
              <CardDescription>
                BIOS: {guide.vendor} · gerado em {guide.generated}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ol className="list-decimal space-y-1.5 pl-5 text-sm">
                {SECTIONS.map((section) => (
                  <li key={section}>{section}</li>
                ))}
              </ol>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void api.openPath(guide.html)}>
                  <BookOpenText data-icon="inline-start" />
                  Abrir o guia
                </Button>
                {guide.pdf && (
                  <Button variant="outline" onClick={() => void api.openPath(guide.pdf!)}>
                    <FileText data-icon="inline-start" />
                    Abrir o PDF
                  </Button>
                )}
                <Button variant="outline" onClick={() => void api.openPath(guide.folder)}>
                  <FolderOpen data-icon="inline-start" />
                  Abrir a pasta
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Smartphone className="size-4 text-primary" />
                Abrir no celular
              </CardTitle>
              <CardDescription>Depois de formatar, o Windows deixa de existir. Leve o guia no celular.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {share ? (
                <>
                  <div
                    className="mx-auto w-fit overflow-hidden rounded-xl border bg-white p-2 [&_svg]:size-48"
                    dangerouslySetInnerHTML={{ __html: share.qr_svg }}
                  />
                  <p className="text-center font-mono text-xs break-all text-muted-foreground">{share.url}</p>
                  <p className="text-xs text-muted-foreground">
                    Aponte a câmera do celular para o código. O celular precisa estar na mesma rede Wi-Fi. Se o Windows perguntar,
                    permita o acesso em redes privadas. O compartilhamento desliga sozinho em {share.minutes} minutos.
                  </p>
                  <Button variant="outline" className="w-full" onClick={() => void stopShare()}>
                    <WifiOff data-icon="inline-start" />
                    Parar de compartilhar
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    O MacPronto mostra um QR code e entrega só o guia, pela rede local. Nada passa pela internet.
                  </p>
                  <Button className="w-full" onClick={() => void startShare()}>
                    <Wifi data-icon="inline-start" />
                    Mostrar QR code
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
