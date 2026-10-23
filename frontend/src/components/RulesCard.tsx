import { CircleCheckBig, CloudDownload, LoaderCircle, RotateCcw, Search } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { BridgeError } from "@/lib/bridge"
import { formatDate } from "@/lib/labels"
import type { EngineCheck, EngineComponent } from "@/lib/types"
import { useTask } from "@/lib/useTask"

function short(sha: string) {
  return sha.slice(0, 7)
}

function ComponentRow({ item, onChanged }: { item: EngineComponent; onChanged: (list: EngineComponent[]) => void }) {
  const [checking, setChecking] = useState(false)
  const [latest, setLatest] = useState<EngineCheck | null>(null)
  const task = useTask()

  async function check() {
    setChecking(true)
    try {
      setLatest(await api.engineCheck(item.name))
    } catch (caught) {
      toast.error(caught instanceof BridgeError ? caught.message : String(caught))
    } finally {
      setChecking(false)
    }
  }

  async function update() {
    const result = await task.run("regras", (taskId) => api.engineUpdate(taskId, item.name))
    if (result) {
      toast.success(`${item.name} atualizado. ${result.selftest}`)
      setLatest(null)
      onChanged(await api.engineStatus())
    }
  }

  async function revert() {
    try {
      onChanged(await api.engineRevert(item.name))
      setLatest(null)
      toast.success(`${item.name} voltou para a versão original.`)
    } catch (caught) {
      toast.error(caught instanceof BridgeError ? caught.message : String(caught))
    }
  }

  return (
    <div className="space-y-2 py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 font-medium">
            {item.name}
            <Badge variant={item.origin === "atualizada" ? "default" : "secondary"}>
              {item.origin === "atualizada" ? "Atualizada" : "Versão original"}
            </Badge>
          </p>
          <p className="font-mono text-xs text-muted-foreground">
            em uso: {short(item.active)}
            {item.origin === "atualizada" && ` · original: ${short(item.pinned)}`}
            {item.installed_at && ` · atualizada em ${formatDate(item.installed_at)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.origin === "atualizada" && (
            <Button size="sm" variant="ghost" disabled={task.running} onClick={() => void revert()}>
              <RotateCcw data-icon="inline-start" />
              Voltar à original
            </Button>
          )}
          <Button size="sm" variant="outline" disabled={checking || task.running} onClick={() => void check()}>
            {checking ? <LoaderCircle data-icon="inline-start" className="animate-spin" /> : <Search data-icon="inline-start" />}
            Procurar atualização
          </Button>
        </div>
      </div>

      {latest && !latest.newer && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <CircleCheckBig className="size-4 text-native" />
          Já está na versão mais nova ({short(latest.sha)}).
        </p>
      )}

      {latest?.newer && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/40 p-3 text-sm">
          <div className="min-w-0">
            <p className="font-medium">
              Versão nova: {short(latest.sha)}
              {latest.date && <span className="font-normal text-muted-foreground"> · {formatDate(latest.date)}</span>}
            </p>
            {latest.message && <p className="truncate text-muted-foreground">{latest.message}</p>}
          </div>
          <Button size="sm" disabled={task.running} onClick={() => void update()}>
            {task.running ? <LoaderCircle data-icon="inline-start" className="animate-spin" /> : <CloudDownload data-icon="inline-start" />}
            {task.running ? (task.stage ?? "Atualizando...") : "Baixar e testar"}
          </Button>
        </div>
      )}
    </div>
  )
}

export function RulesCard() {
  const [items, setItems] = useState<EngineComponent[] | null>(null)

  useEffect(() => {
    void api.engineStatus().then(setItems).catch(() => setItems([]))
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Base de regras</CardTitle>
        <CardDescription>
          As regras de compatibilidade e a coleta de hardware vêm do OpCore Simplify e do Hardware Sniffer, numa versão travada e
          testada. Dá para trazer a versão mais nova do GitHub: ela só é ativada se passar no autoteste, e você pode voltar à original.
        </CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {items === null && <p className="text-sm text-muted-foreground">Carregando...</p>}
        {items?.map((item) => (
          <ComponentRow key={item.name} item={item} onChanged={setItems} />
        ))}
      </CardContent>
    </Card>
  )
}
