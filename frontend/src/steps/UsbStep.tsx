import { CircleCheckBig, FolderOpen, Pause, Play, RotateCcw, Sparkles, TriangleAlert, Usb } from "lucide-react"
import { cn } from "cn"
import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/PageHeader"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { BridgeError } from "@/lib/bridge"
import { useApp } from "@/lib/store"
import type { UsbBuildResult, UsbController, UsbPort, UsbState } from "@/lib/types"

const STEPS_TEXT = [
  "Conecte um pendrive USB 3 em cada porta, uma de cada vez. Espere uns 3 segundos em cada uma.",
  "Repita com um dispositivo USB 2 (mouse, teclado ou pendrive antigo), porque cada conector USB 3 tem uma porta USB 2 escondida.",
  "Nas portas USB-C, conecte nos dois sentidos do cabo.",
]

function PortRow({
  port,
  types,
  onChange,
}: {
  port: UsbPort
  types: UsbState["connector_types"]
  onChange: (index: number, changes: { selected?: boolean; type?: number | null; comment?: string }) => void
}) {
  const [comment, setComment] = useState(port.comment ?? "")
  const active = port.current.length > 0
  useEffect(() => setComment(port.comment ?? ""), [port.comment])

  return (
    <div
      className={cn(
        "grid grid-cols-[auto_6.5rem_1fr_13rem_10rem] items-center gap-3 rounded-lg px-2 py-2 text-sm",
        active ? "bg-native/8" : port.selected ? "" : "opacity-60",
      )}
    >
      <Checkbox
        checked={port.selected}
        onCheckedChange={(value) => onChange(port.index, { selected: value === true })}
        aria-label={`Usar a porta ${port.name}`}
      />
      <div className="leading-tight">
        <p className="font-mono text-xs font-medium">{port.name}</p>
        <p className="text-xs text-muted-foreground">{port.speed}</p>
      </div>
      <div className="min-w-0 space-y-0.5">
        {port.current.map((device) => (
          <p key={`${device.name}-${device.vid_pid}`} className="flex items-center gap-1.5 truncate font-medium">
            <span className="size-2 shrink-0 animate-pulse rounded-full bg-native" />
            {device.name}
          </p>
        ))}
        {port.errors.map((error) => (
          <p key={error} className="text-xs text-incompatible">
            Erro na porta: {error}
          </p>
        ))}
        {port.current.length === 0 && port.seen.length > 0 && (
          <p className="truncate text-xs text-muted-foreground">Usada por: {port.seen.map((device) => device.name).join(", ")}</p>
        )}
        {port.current.length === 0 && port.seen.length === 0 && (
          <p className="text-xs text-muted-foreground">{port.companion ? `Par de ${port.companion}` : "Nada conectado ainda"}</p>
        )}
      </div>
      <Select
        value={String(port.type)}
        onValueChange={(value) => onChange(port.index, { type: Number(value) })}
      >
        <SelectTrigger size="sm" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {types.map((type) => (
            <SelectItem key={type.value} value={String(type.value)}>
              {type.label}
              {port.type_guessed && port.type === type.value ? " (palpite)" : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        value={comment}
        placeholder="Apelido (ex.: frente)"
        className="h-8"
        onChange={(event) => setComment(event.target.value)}
        onBlur={() => comment !== (port.comment ?? "") && onChange(port.index, { comment })}
      />
    </div>
  )
}

function ControllerCard({
  controller,
  types,
  onChange,
  onlyUsed,
}: {
  controller: UsbController
  types: UsbState["connector_types"]
  onChange: (controllerId: string, index: number, changes: { selected?: boolean; type?: number | null; comment?: string }) => void
  onlyUsed: boolean
}) {
  const over = controller.limit !== null && controller.selected > controller.limit
  const ports = onlyUsed ? controller.ports.filter((port) => port.selected || port.seen.length || port.current.length) : controller.ports
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <Usb className="size-4 text-primary" />
          {controller.name}
          <Badge variant="outline">{controller.class_label}</Badge>
          {controller.acpi_path && <Badge variant="outline" className="font-mono">{controller.acpi_path}</Badge>}
        </CardTitle>
        <CardDescription className="space-y-2">
          <span className={cn("block", over && "font-medium text-incompatible")}>
            {controller.selected} de {controller.limit ?? controller.total} portas selecionadas
            {controller.limit !== null && ` (a controladora tem ${controller.total})`}
          </span>
          {controller.limit !== null && (
            <Progress value={Math.min(100, (controller.selected / controller.limit) * 100)} className={cn("h-1.5", over && "[&>*]:bg-incompatible")} />
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-0.5">
        <div className="grid grid-cols-[auto_6.5rem_1fr_13rem_10rem] gap-3 px-2 pb-1 text-xs text-muted-foreground">
          <span className="w-4" />
          <span>Porta</span>
          <span>Dispositivos</span>
          <span>Tipo de conector</span>
          <span>Apelido</span>
        </div>
        {ports.length === 0 && <p className="px-2 py-3 text-sm text-muted-foreground">Nenhuma porta usada ainda.</p>}
        {ports.map((port) => (
          <PortRow key={port.index} port={port} types={types} onChange={(index, changes) => onChange(controller.id, index, changes)} />
        ))}
      </CardContent>
    </Card>
  )
}

export function UsbStep() {
  const { payload, setEfi, setUsbMapped, go } = useApp()
  const [state, setState] = useState<UsbState | null>(null)
  const [discovering, setDiscovering] = useState(true)
  const [onlyUsed, setOnlyUsed] = useState(false)
  const [result, setResult] = useState<UsbBuildResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const busy = useRef(false)

  const refresh = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    try {
      setState(await api.usbRefresh())
      setError(null)
    } catch (caught) {
      setError(caught instanceof BridgeError ? caught.message : String(caught))
    } finally {
      busy.current = false
    }
  }, [])

  useEffect(() => {
    void refresh()
    if (!discovering) return
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(timer)
  }, [discovering, refresh])

  async function apply<T extends UsbState>(promise: Promise<T>) {
    try {
      setState(await promise)
      setResult(null)
    } catch (caught) {
      toast.error(caught instanceof BridgeError ? caught.message : String(caught))
    }
  }

  async function build() {
    try {
      const built = await api.usbBuild()
      setResult(built)
      setUsbMapped(true)
      if (built.efi) setEfi(built.efi)
      toast.success(built.efi_updated ? "Mapa USB gerado e aplicado à EFI." : "Mapa USB gerado.")
    } catch (caught) {
      toast.error(caught instanceof BridgeError ? caught.message : String(caught))
    }
  }

  if (!payload) return null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Portas USB"
        title="Mapeamento das portas USB"
        description="O macOS aceita no máximo 15 portas por controladora. O mapa diz quais portas existem de verdade e de que tipo são; sem ele, portas somem ou o USB 3 fica lento."
        actions={
          <>
            <Button variant="outline" onClick={() => setDiscovering((current) => !current)}>
              {discovering ? <Pause data-icon="inline-start" /> : <Play data-icon="inline-start" />}
              {discovering ? "Pausar a detecção" : "Retomar a detecção"}
            </Button>
            <Button disabled={!state || state.errors.length > 0} onClick={() => void build()}>
              <Sparkles data-icon="inline-start" />
              Gerar mapa USB
            </Button>
          </>
        }
      />

      <Card>
        <CardContent className="grid gap-4 md:grid-cols-3">
          {STEPS_TEXT.map((text, index) => (
            <div key={text} className="flex gap-3">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary tabular-nums">
                {index + 1}
              </span>
              <p className="text-sm text-muted-foreground">{text}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Não foi possível ler as portas</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <Alert className="border-native/40">
          <CircleCheckBig className="text-native" />
          <AlertTitle>Mapa USB pronto</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>
              {result.efi_updated
                ? "O UTBMap.kext já foi colocado na EFI, no lugar do UTBDefault, e o config.plist foi validado de novo."
                : "Ele vai entrar na EFI quando você montá-la."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => void api.revealPath(result.kext)}>
                <FolderOpen data-icon="inline-start" />
                Ver o UTBMap.kext
              </Button>
              <Button size="sm" onClick={() => go(result.efi_updated ? "pendrive" : "efi")}>
                {result.efi_updated ? "Preparar o pendrive" : "Montar a EFI"}
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {state?.errors.map((message) => (
        <Alert key={message} variant="destructive">
          <TriangleAlert />
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => void apply(api.usbSelect("used"))}>
            Selecionar só as usadas
          </Button>
          <Button size="sm" variant="outline" onClick={() => void apply(api.usbSelect("none"))}>
            Desmarcar todas
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void apply(api.usbReset())}>
            <RotateCcw data-icon="inline-start" />
            Recomeçar
          </Button>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Switch id="only-used" checked={onlyUsed} onCheckedChange={setOnlyUsed} />
            <Label htmlFor="only-used" className="text-xs font-normal">
              Mostrar só portas usadas
            </Label>
          </div>
          {state && <span className="tabular-nums">Atualizado às {state.updated_at}</span>}
        </div>
      </div>

      {state?.controllers.map((controller) => (
        <ControllerCard
          key={controller.id}
          controller={controller}
          types={state.connector_types}
          onlyUsed={onlyUsed}
          onChange={(controllerId, index, changes) => void apply(api.usbUpdatePort(controllerId, index, changes))}
        />
      ))}

      {state && state.controllers.length === 0 && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">Nenhuma controladora USB física encontrada.</CardContent>
        </Card>
      )}
    </div>
  )
}
