import {
  ArrowRight,
  CircleCheckBig,
  FolderOpen,
  HardDriveDownload,
  LogOut,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  Usb,
} from "lucide-react"
import { cn } from "cn"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/PageHeader"
import { TaskPanel } from "@/components/TaskPanel"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { BridgeError } from "@/lib/bridge"
import { useApp } from "@/lib/store"
import type { DiskInfo, MediaResult } from "@/lib/types"
import { useTask } from "@/lib/useTask"

function diskTitle(disk: DiskInfo) {
  return `${disk.model} · ${disk.size_gb} GB`
}

function DiskOption({ disk, selected, onSelect }: { disk: DiskInfo; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      disabled={!disk.eligible}
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-4 rounded-xl border bg-card p-4 text-left transition-colors",
        selected ? "border-primary ring-2 ring-primary/35" : disk.eligible ? "hover:border-primary/40" : "cursor-not-allowed opacity-50",
      )}
    >
      <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", disk.eligible ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
        <Usb className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{diskTitle(disk)}</p>
        <p className="text-sm text-muted-foreground">
          Disco {disk.number} · {disk.bus}
          {disk.letters.length > 0 && ` · unidade ${disk.letters.map((letter) => `${letter}:`).join(", ")}`}
          {disk.labels.filter(Boolean).length > 0 && ` (${disk.labels.filter(Boolean).join(", ")})`}
        </p>
        {!disk.eligible && <p className="text-xs text-muted-foreground">{disk.reason}</p>}
      </div>
      {selected && <Badge>Escolhido</Badge>}
    </button>
  )
}

function Done({ result }: { result: MediaResult }) {
  const { go } = useApp()
  const [ejected, setEjected] = useState(false)

  async function eject() {
    const ok = await api.mediaEject(result.letter)
    setEjected(ok)
    if (ok) toast.success("Pode remover o pendrive.")
    else toast.error("Não foi possível ejetar. Feche as janelas que estejam usando o pendrive.")
  }

  return (
    <div className="space-y-4">
      <Card className="ring-1 ring-native/40">
        <CardContent className="flex flex-wrap items-center gap-4">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-native/12 text-native">
            <CircleCheckBig className="size-6" />
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <p className="text-lg font-semibold">Pendrive pronto na unidade {result.letter}:</p>
            <p className="text-sm text-muted-foreground">
              macOS Recovery {result.product}, verificado com a assinatura da Apple. EFI e guia copiados.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void api.openPath(`${result.letter}:\\`)}>
              <FolderOpen data-icon="inline-start" />
              Abrir
            </Button>
            <Button variant="outline" disabled={ejected} onClick={() => void eject()}>
              <LogOut data-icon="inline-start" />
              {ejected ? "Ejetado" : "Ejetar com segurança"}
            </Button>
          </div>
        </CardContent>
      </Card>
      <Alert>
        <ShieldAlert className="text-tweak" />
        <AlertTitle>Antes de desligar o computador</AlertTitle>
        <AlertDescription>
          Abra o guia no celular (próxima etapa) e confira o backup. Depois de instalar o macOS, o Windows deixa de existir.
        </AlertDescription>
      </Alert>
      <div className="flex justify-end">
        <Button onClick={() => go("guide")}>
          Abrir o guia
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>
    </div>
  )
}

export function PendriveStep() {
  const { payload, info } = useApp()
  const task = useTask()
  const [disks, setDisks] = useState<DiskInfo[] | null>(null)
  const [selected, setSelected] = useState<DiskInfo | null>(null)
  const [aware, setAware] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [typed, setTyped] = useState("")
  const [result, setResult] = useState<MediaResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const list = await api.mediaDisks()
      setDisks(list)
      setSelected((current) => list.find((disk) => disk.eligible && disk.unique_id === current?.unique_id) ?? null)
      setError(null)
    } catch (caught) {
      setError(caught instanceof BridgeError ? caught.message : String(caught))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  if (!payload) return null
  const version = payload.laudo.macos.versions.find((item) => item.darwin === payload.selection.darwin)
  const eligible = disks?.filter((disk) => disk.eligible) ?? []
  const isAdmin = info?.is_admin ?? false

  async function create() {
    if (!selected) return
    setDialogOpen(false)
    const disk = selected
    const outcome = await task.run("pendrive", (taskId) =>
      api.mediaCreate(taskId, { number: disk.number, unique_id: disk.unique_id, size_bytes: disk.size_bytes, confirm: typed }),
    )
    setTyped("")
    setAware(false)
    if (outcome) {
      setResult(outcome)
      toast.success("Pendrive pronto.")
    } else {
      void refresh()
    }
  }

  if (task.running) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Pendrive" title="Preparando o pendrive" description="Não desconecte o pendrive nem desligue o computador." />
        <TaskPanel
          task={task}
          title={selected ? `Gravando em ${diskTitle(selected)}` : "Gravando o pendrive"}
          onCancel={task.cancel}
          hint="O download do macOS Recovery (cerca de 900 MB) acontece antes de apagar o pendrive. Se cancelar durante o download, nada é apagado."
        />
      </div>
    )
  }

  if (result) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Pendrive" title="Pendrive de instalação pronto" />
        <Done result={result} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Pendrive"
        title="Preparar o pendrive de instalação"
        description="O MacPronto baixa o macOS Recovery direto da Apple, formata o pendrive escolhido e copia a EFI e o guia."
        actions={
          <Button variant="outline" onClick={() => void refresh()}>
            <RefreshCw data-icon="inline-start" />
            Atualizar lista
          </Button>
        }
      />

      {!isAdmin && (
        <Alert className="border-tweak/40">
          <ShieldAlert className="text-tweak" />
          <AlertTitle>Formatar exige administrador</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>O MacPronto está aberto sem permissão de administrador. Reabra para poder formatar o pendrive.</p>
            <Button size="sm" onClick={() => void api.relaunchAsAdmin()}>
              <ShieldCheck data-icon="inline-start" />
              Reabrir como administrador
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>O que vai para o pendrive</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-muted-foreground">macOS Recovery</p>
            <p className="font-medium">{version?.label ?? "?"}</p>
            <p className="text-xs text-muted-foreground">Baixado da Apple (cerca de 900 MB)</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">EFI do OpenCore</p>
            <p className="font-medium">{payload.efi ? `OpenCore ${payload.efi.opencore ?? ""}` : "Ainda não montada"}</p>
            <p className="text-xs text-muted-foreground">{payload.efi?.usb_map ? "Com mapa USB" : "Todas as portas USB"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Guia personalizado</p>
            <p className="font-medium">HTML e PDF</p>
            <p className="text-xs text-muted-foreground">Na pasta MacPronto do pendrive</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Escolha o pendrive</CardTitle>
          <CardDescription>Só aparecem como opção discos USB entre 4 GB e 256 GB que não sejam do Windows. 16 GB ou mais é o recomendado.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {error && (
            <Alert variant="destructive">
              <TriangleAlert />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {disks === null && <p className="text-sm text-muted-foreground">Procurando discos...</p>}
          {disks !== null && eligible.length === 0 && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Usb className="size-4" />
              Nenhum pendrive encontrado. Conecte um e clique em Atualizar lista.
            </p>
          )}
          {disks?.map((disk) => (
            <DiskOption
              key={`${disk.number}-${disk.unique_id}`}
              disk={disk}
              selected={selected?.unique_id === disk.unique_id && selected.number === disk.number}
              onSelect={() => {
                setSelected(disk)
                setAware(false)
              }}
            />
          ))}
        </CardContent>
      </Card>

      {selected && (
        <Card className="ring-1 ring-incompatible/35">
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3">
              <Checkbox id="aware" checked={aware} onCheckedChange={(value) => setAware(value === true)} className="mt-0.5" />
              <Label htmlFor="aware" className="leading-snug font-normal">
                Entendo que <strong>tudo</strong> o que está em <strong>{diskTitle(selected)}</strong>
                {selected.letters.length > 0 && ` (unidade ${selected.letters.join(", ")}:)`} será apagado e não poderá ser recuperado.
              </Label>
            </div>
            <div className="flex justify-end">
              <Button
                size="lg"
                variant="destructive"
                disabled={!aware || !payload.efi || !isAdmin}
                onClick={() => setDialogOpen(true)}
              >
                <HardDriveDownload data-icon="inline-start" />
                Apagar e criar o pendrive
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <AlertDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open)
          if (!open) setTyped("")
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apagar {selected ? diskTitle(selected) : "o pendrive"}?</AlertDialogTitle>
            <AlertDialogDescription>
              Todo o conteúdo do disco {selected?.number} será apagado. Para confirmar, digite <strong>APAGAR</strong> abaixo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Input autoFocus value={typed} onChange={(event) => setTyped(event.target.value)} placeholder="APAGAR" aria-label="Confirmação" />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={typed.trim().toUpperCase() !== "APAGAR"}
              onClick={(event) => {
                event.preventDefault()
                void create()
              }}
              className="bg-incompatible text-white hover:bg-incompatible/90"
            >
              Apagar e criar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
