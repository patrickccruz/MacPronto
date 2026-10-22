import { FolderOpen } from "lucide-react"
import { cn } from "cn"
import { useEffect, useRef, useState } from "react"

import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { api } from "@/lib/api"
import type { LogLine } from "@/lib/types"

const LEVEL_STYLE: Record<string, string> = {
  debug: "text-muted-foreground",
  info: "",
  warning: "text-tweak",
  error: "text-incompatible",
}

export function LogsPage() {
  const [lines, setLines] = useState<LogLine[]>([])
  const lastId = useRef(0)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const fresh = await api.logsRecent(lastId.current)
        if (!active || fresh.length === 0) return
        lastId.current = fresh[fresh.length - 1].id
        setLines((current) => [...current, ...fresh].slice(-1500))
      } catch {
        // Registros indisponíveis: tenta de novo no próximo ciclo
      }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1500)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Registros"
        title="O que o MacPronto está fazendo"
        description="Úteis para entender um erro. Os arquivos completos ficam na pasta de registros; apague números de série antes de compartilhar."
        actions={
          <Button variant="outline" onClick={() => void api.openLogsFolder()}>
            <FolderOpen data-icon="inline-start" />
            Abrir pasta
          </Button>
        }
      />
      <Card>
        <CardContent>
          <div className="scroll-thin h-[60vh] overflow-y-auto font-mono text-xs leading-relaxed">
            {lines.length === 0 && <p className="text-muted-foreground">Nenhum registro ainda.</p>}
            {lines.map((line) => (
              <p key={line.id} className={cn("break-words whitespace-pre-wrap", LEVEL_STYLE[line.level])}>
                <span className="text-muted-foreground tabular-nums">{line.time}</span> {line.message}
              </p>
            ))}
            <div ref={bottom} />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
