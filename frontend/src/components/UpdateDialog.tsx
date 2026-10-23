import { Download, ExternalLink, LoaderCircle, TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"
import { toast } from "sonner"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { api } from "@/lib/api"
import { useBackgroundTask, useBackgroundTasks } from "@/lib/backgroundTasks"
import { useUpdates } from "@/lib/updates"
import { taskPercent } from "@/lib/useTask"

/** Markdown simples das notas da versão (títulos, listas e parágrafos), sem HTML. */
function Notes({ text }: { text: string }) {
  const clean = (line: string) =>
    line
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/[*`_]{1,2}([^*`_]+)[*`_]{1,2}/g, "$1")
      .trim()
  const blocks: ReactNode[] = []
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trimEnd()
    if (!line.trim() || line.startsWith(">")) return
    if (/^#{1,6}\s/.test(line)) {
      blocks.push(
        <p key={index} className="pt-2 font-semibold first:pt-0">
          {clean(line.replace(/^#+\s*/, ""))}
        </p>,
      )
    } else if (/^\s*[-*]\s/.test(line)) {
      blocks.push(
        <p key={index} className="flex gap-2 pl-1">
          <span className="text-muted-foreground">•</span>
          <span>{clean(line.replace(/^\s*[-*]\s+/, ""))}</span>
        </p>,
      )
    } else {
      blocks.push(<p key={index}>{clean(line)}</p>)
    }
  })
  return <div className="space-y-1 text-sm">{blocks}</div>
}

export function UpdateDialog() {
  const { status, dialogOpen, postpone } = useUpdates()
  const update = useBackgroundTask("atualizar")
  const { tasks } = useBackgroundTasks()
  const available = status?.available
  if (!status || !available) return null

  const busy = Object.values(tasks).filter((task) => task.running && task.key !== "atualizar")
  const task = update.task
  const installing = Boolean(task?.running)
  const percent = taskPercent(task?.progress ?? null)

  async function install() {
    const result = await update.run({ title: `Atualizando para a versão ${available!.version}`, view: "about" }, (taskId) =>
      api.updateInstall(taskId),
    )
    if (result?.restarting) toast.success("Instalando a versão nova. O MacPronto vai fechar e abrir de novo sozinho.")
  }

  return (
    <Dialog open={dialogOpen || installing} onOpenChange={(open) => !open && !installing && postpone()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nova versão do MacPronto</DialogTitle>
          <DialogDescription>
            A versão {available.version} está disponível. Você está na {status.current}.
          </DialogDescription>
        </DialogHeader>

        {available.notes.trim() && (
          <div className="scroll-thin max-h-64 overflow-y-auto rounded-lg border bg-muted/40 p-3">
            <Notes text={available.notes} />
          </div>
        )}

        {installing && task && (
          <div className="space-y-2">
            <p className="flex items-center gap-2 text-sm">
              <LoaderCircle className="size-4 animate-spin text-primary" />
              {task.stage ?? "Preparando..."}
            </p>
            <Progress value={percent ?? undefined} className={percent === null ? "animate-pulse" : undefined} />
          </div>
        )}

        {busy.length > 0 && !installing && (
          <Alert className="border-tweak/40">
            <TriangleAlert className="text-tweak" />
            <AlertDescription>
              Termine o que está em andamento antes de atualizar: {busy.map((item) => item.title).join(", ")}.
            </AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button variant="ghost" disabled={installing} onClick={postpone}>
            Depois
          </Button>
          {status.installed ? (
            <Button disabled={installing || busy.length > 0} onClick={() => void install()}>
              <Download data-icon="inline-start" />
              Instalar e reiniciar ({Math.round(available.size / 1024 ** 2)} MB)
            </Button>
          ) : (
            <Button onClick={() => void api.openUrl(available.page)}>
              <ExternalLink data-icon="inline-start" />
              Baixar na página da versão
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
