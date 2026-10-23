import {
  ArrowRight,
  CircleCheckBig,
  FolderOpen,
  HardDriveDownload,
  LogOut,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Trash2,
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
import { useBackgroundTask } from "@/lib/backgroundTasks"
import { BridgeError } from "@/lib/bridge"
import { useApp } from "@/lib/store"
import type { DiskInfo, MediaResult, RecoveryCacheItem } from "@/lib/types"

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

function formatBytes(bytes: number) {
  return bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1).replace(".", ",")} GB` : `${Math.round(bytes / 1024 ** 2)} MB`
}

function Done({ result, onAgain }: { result: MediaResult; onAgain: () => void }) {
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
              macOS Recovery {result.product}
              {result.recovery_replaced
                ? ` (versão mais nova da Apple, no lugar da ${result.recovery_replaced})`
                : result.recovery_cached
                  ? " (reaproveitado do computador)"
                  : ""}
              , verificado com a assinatura da Apple. EFI e guia copiados.
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
      {ejected && (
        <p className="text-sm text-muted-foreground">
          Pendrive ejetado. Para gravar nele de novo, desconecte e conecte antes de clicar em Criar outro pendrive.
        </p>
      )}
      <Alert>
        <ShieldAlert className="text-tweak" />
        <AlertTitle>Antes de desligar o computador</AlertTitle>
        <AlertDescription>
          Abra o guia no celular (próxima etapa) e confira o backup. Depois de instalar o macOS, o Windows deixa de existir.
        </AlertDescription>
      </Alert>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onAgain}>
          <HardDriveDownload data-icon="inline-start" />
          Criar outro pendrive
        </Button>
        <Button onClick={() => go("guide")}>
          Abrir o guia
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>
    </div>
  )
}

const FORMAT_HINT =
  "Se o Windows abrir uma janela perguntando se deseja formatar a unidade, ou dizendo que ela não está acessível, clique em Cancelar: quem formata é o MacPronto."
const DOWNLOAD_HINT =
  "O macOS Recovery (cerca de 900 MB) é baixado ou conferido antes de apagar o pendrive. Se cancelar nessa fase, nada é apagado. Pode usar as outras telas enquanto isso."


export function PendriveStep() {
  const { payload, info, go } = useApp()
  const media = useBackgroundTask("pendrive")
  const [disks, setDisks] = useState<DiskInfo[] | null>(null)
  const [selected, setSelected] = useState<DiskInfo | null>(null)
  const [aware, setAware] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [typed, setTyped] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [cache, setCache] = useState<RecoveryCacheItem[]>([])

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
    // Primeira leitura: o estado só muda quando a resposta chega
    let active = true
    api.mediaRecoveryCache().then(
      (list) => {
        if (active) setCache(list)
      },
      () => undefined,
    )
    api.mediaDisks().then(
      (list) => {
        if (active) setDisks(list)
      },
      (caught) => {
        if (active) setError(caught instanceof BridgeError ? caught.message : String(caught))
      },
    )
    return () => {
      active = false
    }
  }, [])

  if (!payload) return null
  // A versão é a da EFI montada (a escolha pode ter mudado depois de montar)
  const darwin = payload.efi?.macos ?? payload.selection.darwin
  const version = payload.laudo.macos.versions.find((item) => item.darwin === darwin)
  const cached = cache.find((item) => item.darwin === darwin)
  const cacheSize = cache.reduce((total, item) => total + item.size, 0)
  const eligible = disks?.filter((disk) => disk.eligible) ?? []
  const isAdmin = info?.is_admin ?? false
  const task = media.task
  const result = task?.finished && !task.error ? (task.result as MediaResult) : null
  const failure = task?.finished && task.error && task.error.code !== "cancelled" ? task.error : null

  async function create() {
    if (!selected) return
    setDialogOpen(false)
    const disk = selected
    const confirm = typed
    setTyped("")
    setAware(false)
    const outcome = await media.run({ title: `Gravando em ${diskTitle(disk)}`, view: "pendrive" }, async (taskId) => {
      const created = await api.mediaCreate(taskId, {
        number: disk.number,
        unique_id: disk.unique_id,
        size_bytes: disk.size_bytes,
        confirm,
      })
      toast.success(`Pendrive pronto na unidade ${created.letter}:`)
      return created
    })
    if (!outcome) void refresh()
    void api.mediaRecoveryCache().then(setCache, () => undefined)
  }

  async function clearCache() {
    try {
      const freed = await api.mediaRecoveryClear()
      setCache([])
      toast.success(`${formatBytes(freed)} liberados. O macOS Recovery será baixado de novo na próxima gravação.`)
    } catch (caught) {
      toast.error(caught instanceof BridgeError ? caught.message : String(caught))
    }
  }

  if (task?.running) {
    const formatting = /formatando/i.test(task.stage ?? "")
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Pendrive" title="Preparando o pendrive" description="Não desconecte o pendrive nem desligue o computador." />
        <TaskPanel task={task} title={task.title} onCancel={media.cancel} hint={formatting ? FORMAT_HINT : DOWNLOAD_HINT} />
      </div>
    )
  }

  if (result) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Pendrive" title="Pendrive de instalação pronto" />
        <Done
          result={result}
          onAgain={() => {
            media.dismiss()
            void refresh()
          }}
        />
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

      {failure && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Não foi possível criar o pendrive</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{failure.message}</p>
            {failure.details && (
              <details>
                <summary className="cursor-pointer text-xs">Detalhes técnicos</summary>
                <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-muted p-2 font-mono text-xs whitespace-pre-wrap text-foreground">
                  {failure.details}
                </pre>
              </details>
            )}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => go("logs")}>
                <ScrollText data-icon="inline-start" />
                Ver os registros
              </Button>
              <Button size="sm" variant="ghost" onClick={media.dismiss}>
                Fechar
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

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
            <p className="text-xs text-muted-foreground">
              {cached
                ? `Já está no computador (${formatBytes(cached.size)}). Antes de gravar, o MacPronto confere se a Apple tem uma mais nova.`
                : "Baixado da Apple (cerca de 900 MB) e guardado para as próximas vezes"}
            </p>
            {cacheSize > 0 && (
              <Button size="xs" variant="ghost" className="mt-1 -ml-2 text-muted-foreground" onClick={() => void clearCache()}>
                <Trash2 data-icon="inline-start" />
                Apagar as cópias salvas ({formatBytes(cacheSize)})
              </Button>
            )}
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
                disabled={!aware || !payload.efi || !isAdmin || media.running}
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
