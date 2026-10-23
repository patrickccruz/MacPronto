import {
  ArrowRight,
  Bluetooth,
  CircuitBoard,
  Cpu,
  Download,
  FolderOpen,
  HardDrive,
  Import,
  Keyboard,
  MemoryStick,
  Monitor,
  Network,
  RefreshCw,
  ScanSearch,
  Speaker,
  Trash2,
  Usb,
} from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/PageHeader"
import { TaskPanel } from "@/components/TaskPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { formatDate } from "@/lib/labels"
import { useApp } from "@/lib/store"
import type { ScanPayload, ScanSummary } from "@/lib/types"
import { useBackgroundTask, useMountedRef } from "@/lib/backgroundTasks"

type Props = Record<string, unknown>

function entries(section: unknown): [string, Props][] {
  if (!section || typeof section !== "object") return []
  return Object.entries(section as Record<string, Props>)
}

function text(value: unknown) {
  return typeof value === "string" ? value : value == null ? "" : String(value)
}

function DeviceId({ value }: { value: unknown }) {
  if (!value) return null
  return <span className="font-mono text-[11px] text-muted-foreground">{text(value)}</span>
}

function Section({ icon: Icon, title, children }: { icon: typeof Cpu; title: string; children: ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-4 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  )
}

function Row({ title, subtitle, id }: { title: string; subtitle?: string; id?: unknown }) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 truncate font-medium" title={title}>
          {title}
        </p>
        <DeviceId value={id} />
      </div>
      {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
    </div>
  )
}

function Empty() {
  return <p className="text-sm text-muted-foreground">Nada encontrado.</p>
}

function XRay({ payload }: { payload: ScanPayload }) {
  const { report, extras } = payload
  const cpu = (report.CPU ?? {}) as Props
  const board = (report.Motherboard ?? {}) as Props
  const bios = (report.BIOS ?? {}) as Props
  const monitors = entries(report.Monitor)
  const memory = extras.memory
  const disks = extras.disks ?? []

  return (
    <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
      <Section icon={Cpu} title="Processador">
        <Row title={text(cpu["Processor Name"])} subtitle={`${text(cpu.Codename)} · ${Number(cpu["Core Count"] ?? 0)} núcleos`} />
        <p className="text-xs text-muted-foreground">{text(cpu["SIMD Features"])}</p>
      </Section>

      <Section icon={CircuitBoard} title="Placa-mãe e BIOS">
        <Row title={text(board.Name)} subtitle={`Chipset ${text(board.Chipset)} · ${board.Platform === "Laptop" ? "notebook" : "desktop"}`} />
        <Row
          title={`BIOS ${text(bios.Version)}`}
          subtitle={`${text(bios["Release Date"])} · ${text(bios["Firmware Type"])} · Secure Boot ${bios["Secure Boot"] === "Enabled" ? "ligado" : "desligado"}`}
        />
      </Section>

      <Section icon={MemoryStick} title="Memória">
        {memory?.modules?.length ? (
          <>
            <Row title={`${memory.modules.reduce((sum, m) => sum + m.capacity_gb, 0)} GB instalados`} subtitle={`${memory.modules.length} módulo(s)`} />
            {memory.modules.map((module, index) => (
              <p key={index} className="text-xs text-muted-foreground">
                {module.capacity_gb} GB · {module.speed_mhz} MHz · {module.manufacturer || "fabricante desconhecido"}
              </p>
            ))}
          </>
        ) : memory?.total_gb ? (
          <Row title={`${memory.total_gb} GB`} />
        ) : (
          <Empty />
        )}
      </Section>

      <Section icon={Monitor} title="Vídeo e monitores">
        {entries(report.GPU).map(([name, props]) => (
          <Row
            key={name}
            title={name}
            subtitle={`${props["Device Type"] === "Integrated GPU" ? "Integrado" : "Dedicado"} · ${text(props.Codename) || "arquitetura desconhecida"}`}
            id={props["Device ID"]}
          />
        ))}
        {monitors.map(([name, props]) => (
          <p key={name} className="text-xs text-muted-foreground">
            {name}: {text(props["Connector Type"])}, {text(props.Resolution)}
          </p>
        ))}
      </Section>

      <Section icon={Speaker} title="Áudio">
        {entries(report.Sound).length === 0 && <Empty />}
        {entries(report.Sound).map(([name, props]) => (
          <Row key={name} title={name} subtitle={text(props["Bus Type"])} id={props["Device ID"]} />
        ))}
      </Section>

      <Section icon={Network} title="Rede">
        {entries(report.Network).length === 0 && <Empty />}
        {entries(report.Network).map(([name, props]) => (
          <Row key={name} title={name} subtitle={text(props["Bus Type"])} id={props["Device ID"]} />
        ))}
      </Section>

      <Section icon={HardDrive} title="Armazenamento">
        {disks.length > 0
          ? disks
              .filter((disk) => disk.bus !== "USB")
              .map((disk) => (
                <Row
                  key={disk.number}
                  title={disk.model}
                  subtitle={`${disk.size_gb} GB · ${disk.bus} · ${disk.media}${disk.system ? " · Windows" : ""}`}
                />
              ))
          : entries(report["Storage Controllers"]).map(([name, props]) => (
              <Row key={name} title={name} subtitle={((props["Disk Drives"] as string[]) ?? []).join(", ")} id={props["Device ID"]} />
            ))}
      </Section>

      <Section icon={Usb} title="Controladoras USB">
        {entries(report["USB Controllers"]).map(([name, props]) => (
          <Row key={name} title={name} id={props["Device ID"]} />
        ))}
      </Section>

      {(entries(report.Bluetooth).length > 0 || entries(report.Input).length > 0) && (
        <Section icon={entries(report.Bluetooth).length ? Bluetooth : Keyboard} title="Bluetooth e entrada">
          {entries(report.Bluetooth).map(([name, props]) => (
            <Row key={name} title={name} subtitle="Bluetooth" id={props["Device ID"]} />
          ))}
          {entries(report.Input).map(([name, props]) => (
            <Row key={name} title={name} subtitle={text(props["Device Type"]) || text(props["Bus Type"])} id={props["Device ID"] ?? props.Device} />
          ))}
        </Section>
      )}
    </div>
  )
}

function SavedScans({ onOpen, disabled }: { onOpen: (scan: ScanSummary) => void; disabled: boolean }) {
  const [scans, setScans] = useState<ScanSummary[] | null>(null)

  useEffect(() => {
    void api.scanList().then(setScans)
  }, [])

  async function remove(scan: ScanSummary) {
    await api.scanDelete(scan.id)
    setScans((current) => current?.filter((item) => item.id !== scan.id) ?? null)
    toast.success("Diagnóstico apagado.")
  }

  if (!scans || scans.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Diagnósticos salvos</CardTitle>
        <CardDescription>Ficam em Documentos\MacPronto\Diagnosticos.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {scans.map((scan) => (
          <div key={scan.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
            <div className="min-w-0">
              <p className="truncate font-medium">{scan.label}</p>
              <p className="text-xs text-muted-foreground">
                {formatDate(scan.created_at)} · {scan.source === "local" ? "este computador" : "importado"}
                {!scan.has_acpi && " · sem tabelas ACPI"}
              </p>
            </div>
            <div className="flex shrink-0 gap-1">
              <Button size="sm" variant="outline" disabled={disabled} onClick={() => onOpen(scan)}>
                <FolderOpen data-icon="inline-start" />
                Abrir
              </Button>
              <Button size="icon-sm" variant="ghost" disabled={disabled} onClick={() => void remove(scan)} aria-label="Apagar diagnóstico">
                <Trash2 />
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function DiagnosisStep() {
  const { payload, setPayload, go } = useApp()
  const scanTask = useBackgroundTask("diagnostico")
  const mounted = useMountedRef()

  async function scanThisPc() {
    await scanTask.run({ title: "Diagnosticando este computador", view: "diagnosis" }, async (taskId) => {
      const result = await api.scanRun(taskId)
      setPayload(result)
      toast.success("Diagnóstico concluído.")
      return result
    })
  }

  async function openScan(scan: ScanSummary) {
    const result = await scanTask.run({ title: `Abrindo ${scan.label}`, view: "diagnosis" }, async (taskId) => {
      const opened = await api.scanOpen(taskId, scan.id)
      setPayload(opened)
      return opened
    })
    if (result && mounted.current) go("report")
  }

  async function importScan() {
    const result = await scanTask.run({ title: "Importando diagnóstico", view: "diagnosis" }, async (taskId) => {
      const imported = await api.scanImport(taskId)
      if (imported) {
        setPayload(imported)
        toast.success("Diagnóstico importado. Você está no modo simulação.")
      }
      return imported
    })
    if (result && mounted.current) go("report")
  }

  async function exportScan() {
    try {
      const path = await api.scanExport()
      if (path) toast.success(`Diagnóstico salvo em ${path}`)
    } catch (error) {
      toast.error(String((error as Error).message))
    }
  }

  if (scanTask.task?.running) {
    const { title } = scanTask.task
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Diagnóstico" title={title} description="Leva de 15 a 30 segundos. Nada é alterado no computador." />
        <TaskPanel task={scanTask.task} title={title} onCancel={scanTask.cancel} />
      </div>
    )
  }

  if (!payload) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Diagnóstico"
          title="Raio-X do computador"
          description="O MacPronto lê o hardware e as tabelas ACPI pelo Windows. Nada é alterado e nenhum dado sai deste computador."
        />
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="ring-primary/30">
            <CardContent className="flex h-full flex-col gap-4">
              <span className="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                <ScanSearch className="size-5" />
              </span>
              <div className="flex-1 space-y-1">
                <p className="text-base font-medium">Diagnosticar este computador</p>
                <p className="text-sm text-muted-foreground">O caminho normal: rode aqui, no PC que vai virar Hackintosh.</p>
              </div>
              <Button size="lg" onClick={() => void scanThisPc()}>
                Iniciar diagnóstico
                <ArrowRight data-icon="inline-end" />
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex h-full flex-col gap-4">
              <span className="flex size-11 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
                <Import className="size-5" />
              </span>
              <div className="flex-1 space-y-1">
                <p className="text-base font-medium">Analisar o computador de um amigo</p>
                <p className="text-sm text-muted-foreground">
                  Modo simulação: importe um arquivo .macpronto exportado em outra máquina, ou o Report.json do Hardware Sniffer.
                </p>
              </div>
              <Button size="lg" variant="outline" onClick={() => void importScan()}>
                Importar diagnóstico
              </Button>
            </CardContent>
          </Card>
        </div>
        <SavedScans onOpen={(scan) => void openScan(scan)} disabled={scanTask.running} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Diagnóstico"
        title={payload.laudo.machine.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {payload.laudo.machine.form_label}
            {payload.extras.os?.caption && <span>· {payload.extras.os.caption}</span>}
            <Badge variant={payload.scan.source === "local" ? "secondary" : "outline"}>
              {payload.scan.source === "local" ? "Este computador" : "Modo simulação"}
            </Badge>
            <Badge variant="outline">{payload.acpi_tables.length} tabelas ACPI</Badge>
          </span>
        }
        actions={
          <>
            <Button variant="outline" onClick={() => void exportScan()}>
              <Download data-icon="inline-start" />
              Exportar
            </Button>
            <Button variant="outline" onClick={() => void scanThisPc()}>
              <RefreshCw data-icon="inline-start" />
              Refazer
            </Button>
            <Button onClick={() => go("report")}>
              Ver o laudo
              <ArrowRight data-icon="inline-end" />
            </Button>
          </>
        }
      />
      <XRay payload={payload} />
    </div>
  )
}
