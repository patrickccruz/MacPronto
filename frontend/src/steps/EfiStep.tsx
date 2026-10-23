import {
  ArrowRight,
  CircleCheckBig,
  Copy,
  Eye,
  EyeOff,
  FileArchive,
  FolderOpen,
  Hammer,
  History,
  KeyRound,
  MonitorOff,
  TriangleAlert,
  Usb,
} from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/PageHeader"
import { TaskPanel } from "@/components/TaskPanel"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { api } from "@/lib/api"
import { useBackgroundTask } from "@/lib/backgroundTasks"
import { formatDate } from "@/lib/labels"
import { useApp } from "@/lib/store"
import type { EfiBuildItem, EfiInfo } from "@/lib/types"

const DEFAULT_KEYBOARDS = [
  { value: "abnt2", label: "Português (Brasil), teclado ABNT2" },
  { value: "br-pro", label: "Português (Brasil), teclado Brasileiro Pro" },
  { value: "us", label: "Inglês (EUA), teclado americano" },
]

function copy(text: string, label: string) {
  void navigator.clipboard.writeText(text).then(() => toast.success(`${label} copiado.`))
}

function SmbiosCard({ efi }: { efi: EfiInfo }) {
  const [visible, setVisible] = useState(false)
  const smbios = efi.config.smbios
  const rows = [
    ["Modelo", smbios.model],
    ["Número de série", smbios.serial],
    ["MLB", smbios.mlb],
    ["UUID do sistema", smbios.uuid],
    ["ROM", smbios.rom],
  ]
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-primary" />
          Identidade de Mac (SMBIOS)
        </CardTitle>
        <CardDescription>Gerada só para esta EFI. Não compartilhe estes números em fóruns ou grupos.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.map(([label, value], index) => (
          <div key={label} className="flex items-center justify-between gap-3 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className="flex items-center gap-1 font-mono text-xs">
              {index === 0 || visible ? value : "•".repeat(Math.min(12, value?.length ?? 8))}
              {(index === 0 || visible) && value && (
                <Button size="icon-xs" variant="ghost" onClick={() => copy(value, label)} aria-label={`Copiar ${label}`}>
                  <Copy />
                </Button>
              )}
            </span>
          </div>
        ))}
        <Button size="sm" variant="outline" onClick={() => setVisible((current) => !current)}>
          {visible ? <EyeOff data-icon="inline-start" /> : <Eye data-icon="inline-start" />}
          {visible ? "Ocultar números" : "Mostrar números"}
        </Button>
      </CardContent>
    </Card>
  )
}

function Result({ efi, onRebuild }: { efi: EfiInfo; onRebuild: () => void }) {
  const { go, payload } = useApp()
  const valid = efi.validation?.ok
  return (
    <div className="space-y-4">
      <Card className="ring-1 ring-native/40">
        <CardContent className="flex flex-wrap items-center gap-4">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-native/12 text-native">
            <CircleCheckBig className="size-6" />
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <p className="text-lg font-semibold">EFI pronta</p>
            <p className="truncate text-sm text-muted-foreground" title={efi.efi_dir}>
              {efi.efi_dir}
            </p>
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="secondary">OpenCore {efi.opencore ?? "?"}</Badge>
              <Badge variant="secondary">{efi.size_mb} MB</Badge>
              <Badge variant={valid ? "secondary" : "destructive"}>{valid ? "ocvalidate sem problemas" : "ocvalidate com avisos"}</Badge>
              <Badge variant={efi.usb_map ? "secondary" : "outline"}>{efi.usb_map ? "Mapa USB incluído" : "Sem mapa USB"}</Badge>
              <Badge variant="outline">{formatDate(efi.created_at)}</Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void api.openPath(efi.folder)}>
              <FolderOpen data-icon="inline-start" />
              Abrir pasta
            </Button>
            <Button variant="outline" onClick={() => void api.revealPath(efi.zip)}>
              <FileArchive data-icon="inline-start" />
              Ver o .zip
            </Button>
          </div>
        </CardContent>
      </Card>

      {efi.config.vesa && (
        <Alert className="border-tweak/40">
          <MonitorOff className="text-tweak" />
          <AlertTitle>Vídeo integrado em modo VESA</AlertTitle>
          <AlertDescription>
            Há monitor no HDMI/DVI do vídeo integrado, então a EFI liga o modo VESA (sem aceleração) para garantir imagem na
            instalação. Depois de instalar, ligue o monitor na DisplayPort ou siga o guia para ajustar as portas.
          </AlertDescription>
        </Alert>
      )}

      {efi.plan.needs_oclp && (
        <Alert className="border-tweak/40">
          <TriangleAlert className="text-tweak" />
          <AlertTitle>Exige o OpenCore Legacy Patcher depois de instalar</AlertTitle>
          <AlertDescription>O guia traz o passo a passo da pós-instalação com o OCLP.</AlertDescription>
        </Alert>
      )}

      {efi.validation && !efi.validation.ok && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>O ocvalidate encontrou problemas</AlertTitle>
          <AlertDescription>
            <pre className="mt-2 max-h-48 overflow-auto font-mono text-xs whitespace-pre-wrap">{efi.validation.output}</pre>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <SmbiosCard efi={efi} />
        <Card size="sm">
          <CardHeader>
            <CardTitle>Configuração de boot</CardTitle>
            <CardDescription>{efi.keyboard_label}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <p className="text-muted-foreground">boot-args</p>
              <p className="font-mono text-xs">{efi.config.boot_args || "(vazio)"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">SSDTs ({efi.config.ssdts.length})</p>
              <p className="font-mono text-xs">{efi.config.ssdts.join(", ")}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Drivers UEFI</p>
              <p className="font-mono text-xs">{efi.config.drivers.join(", ")}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Kexts ({efi.config.kexts.length})</p>
              <p className="font-mono text-xs">{efi.config.kexts.map((kext) => kext.replace(".kext", "")).join(", ")}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" onClick={onRebuild}>
          <Hammer data-icon="inline-start" />
          Montar de novo
        </Button>
        {payload?.scan.source === "local" && !efi.usb_map && (
          <Button variant="outline" onClick={() => go("usb")}>
            <Usb data-icon="inline-start" />
            Mapear portas USB
          </Button>
        )}
        <Button onClick={() => go("pendrive")}>
          Preparar o pendrive
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>
    </div>
  )
}

function PreviousBuilds({ builds, onUse }: { builds: EfiBuildItem[]; onUse: (build: EfiBuildItem) => void }) {
  const { payload } = useApp()
  const label = (darwin: number) => payload?.laudo.macos.versions.find((item) => item.darwin === darwin)?.label ?? `Darwin ${darwin}`
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4 text-primary" />
          EFIs já montadas para este computador
        </CardTitle>
        <CardDescription>Dá para voltar a usar uma delas sem montar de novo.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {builds.map((build) => (
          <div key={build.folder} className="flex flex-wrap items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-medium">
                {formatDate(build.created_at)} · {label(build.selection.darwin ?? build.macos)}
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">OpenCore {build.opencore ?? "?"}</Badge>
                <Badge variant={build.usb_map ? "secondary" : "outline"}>{build.usb_map ? "Com mapa USB" : "Sem mapa USB"}</Badge>
                {build.validation && !build.validation.ok && <Badge variant="destructive">ocvalidate com avisos</Badge>}
                {build.selection.smbios_model && <Badge variant="outline">{build.selection.smbios_model}</Badge>}
                {!build.complete && <Badge variant="destructive">Pasta incompleta</Badge>}
              </div>
            </div>
            {build.current ? (
              <Badge>Em uso</Badge>
            ) : (
              <Button size="sm" variant="outline" disabled={!build.complete} onClick={() => onUse(build)}>
                Usar esta
              </Button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function EfiStep() {
  const { payload, setEfi, setPayload } = useApp()
  const efiTask = useBackgroundTask("efi")
  const [keyboards, setKeyboards] = useState(DEFAULT_KEYBOARDS)
  const [keyboard, setKeyboard] = useState("abnt2")
  const [useUsbMap, setUseUsbMap] = useState(true)
  const [rebuilding, setRebuilding] = useState(false)
  const [builds, setBuilds] = useState<EfiBuildItem[]>([])
  const efiFolder = payload?.efi?.folder

  useEffect(() => {
    void api.efiKeyboards().then(setKeyboards).catch(() => undefined)
  }, [])

  useEffect(() => {
    // Recarrega a lista quando a EFI em uso muda (montagem nova ou troca)
    let active = true
    api.efiBuilds().then(
      (list) => {
        if (active) setBuilds(list)
      },
      () => undefined,
    )
    return () => {
      active = false
    }
  }, [efiFolder])

  if (!payload) return null
  const { plan, laudo, selection } = payload
  const version = laudo.macos.versions.find((item) => item.darwin === selection.darwin)

  async function build() {
    const result = await efiTask.run({ title: "Montando a EFI do OpenCore", view: "efi" }, async (taskId) => {
      const built = await api.efiBuild(taskId, { keyboard, use_usb_map: useUsbMap })
      setEfi(built)
      toast.success("EFI montada e validada.")
      return built
    })
    if (result) setRebuilding(false)
  }

  async function reuseBuild(build: EfiBuildItem) {
    const result = await efiTask.run({ title: "Abrindo a EFI anterior", view: "efi" }, async (taskId) => {
      const opened = await api.efiUse(taskId, build.folder)
      setPayload(opened)
      toast.success(`Usando a EFI montada em ${formatDate(build.created_at)}.`)
      return opened
    })
    if (result) setRebuilding(false)
  }

  if (efiTask.task?.running) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="EFI" title="Montando a EFI" description="Na primeira vez baixa o OpenCore e os kexts (cerca de 50 MB). Depois fica em cache." />
        <TaskPanel task={efiTask.task} title={efiTask.task.title} onCancel={efiTask.cancel} />
      </div>
    )
  }

  if (payload.efi && !rebuilding) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="EFI" title="Pasta EFI do OpenCore" description="Ela vai para o pendrive na próxima etapa. Guarde uma cópia: é ela que dá boot no macOS depois." />
        <Result efi={payload.efi} onRebuild={() => setRebuilding(true)} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="EFI"
        title="Montar a EFI do OpenCore"
        description="O MacPronto baixa o OpenCore e os kexts dos projetos oficiais, compila os patches ACPI desta máquina, gera o config.plist e valida tudo com o ocvalidate."
      />

      <Card>
        <CardHeader>
          <CardTitle>Resumo do que será montado</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-xs text-muted-foreground">Versão do macOS</p>
            <p className="font-medium">{version?.label ?? "?"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Mac simulado</p>
            <p className="font-medium">{plan?.smbios ?? "?"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Kexts</p>
            <p className="font-medium">{plan?.kexts.length ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Patches ACPI</p>
            <p className="font-medium">{plan?.acpi_patches.length ?? 0}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Opções</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label>Idioma e teclado do instalador</Label>
            <Select value={keyboard} onValueChange={setKeyboard}>
              <SelectTrigger className="w-full max-w-md">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {keyboards.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="usbmap">Usar o mapa de portas USB</Label>
              <p className="text-xs text-muted-foreground">
                {payload.usb_mapped
                  ? "O mapa feito nesta sessão substitui o UTBDefault (todas as portas)."
                  : "Ainda não há mapa: a EFI ativa todas as portas, o que basta para instalar. Dá para mapear depois."}
              </p>
            </div>
            <Switch id="usbmap" checked={useUsbMap && payload.usb_mapped} disabled={!payload.usb_mapped} onCheckedChange={setUseUsbMap} />
          </div>
        </CardContent>
      </Card>

      {builds.length > 0 && <PreviousBuilds builds={builds} onUse={(build) => void reuseBuild(build)} />}

      {!payload.acpi_tables.length && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Sem tabelas ACPI</AlertTitle>
          <AlertDescription>Este diagnóstico não tem as tabelas ACPI. Refaça o diagnóstico no próprio computador para montar a EFI.</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end gap-2">
        {rebuilding && (
          <Button variant="ghost" onClick={() => setRebuilding(false)}>
            Voltar
          </Button>
        )}
        <Button size="lg" disabled={!plan || !payload.acpi_tables.length} onClick={() => void build()}>
          <Hammer data-icon="inline-start" />
          Montar a EFI
        </Button>
      </div>
    </div>
  )
}
