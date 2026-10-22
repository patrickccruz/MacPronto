import {
  ArrowRight,
  ChevronDown,
  FileText,
  CircleAlert,
  CircleCheckBig,
  CircleX,
  Download,
  Info,
  ListChecks,
  TriangleAlert,
  Wrench,
} from "lucide-react"
import { cn } from "cn"
import { useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/PageHeader"
import { StatusBadge, StatusDot } from "@/components/StatusBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { api } from "@/lib/api"
import { CATEGORY, CATEGORY_ORDER, STATUS_STYLE, VERDICT_TONE, VERSION_STATUS_LABEL } from "@/lib/labels"
import { useApp } from "@/lib/store"
import type { Laudo, LaudoComponent, VerdictStatus } from "@/lib/types"
import { useTask } from "@/lib/useTask"

const VERDICT_ICON: Record<VerdictStatus, typeof CircleCheckBig> = {
  compatible: CircleCheckBig,
  caveats: CircleAlert,
  "needs-bios": Wrench,
  "needs-hardware": Wrench,
  incompatible: CircleX,
}

function DifficultyMeter({ score }: { score: number }) {
  return (
    <div className="flex gap-1" aria-label={`Dificuldade ${score} de 5`}>
      {[1, 2, 3, 4, 5].map((level) => (
        <span
          key={level}
          className={cn(
            "h-2 w-6 rounded-full",
            level <= score ? (score <= 2 ? "bg-native" : score === 3 ? "bg-tweak" : "bg-incompatible") : "bg-muted",
          )}
        />
      ))}
    </div>
  )
}

function VerdictHero({ laudo }: { laudo: Laudo }) {
  const tone = VERDICT_TONE[laudo.verdict.status]
  const style = STATUS_STYLE[tone]
  const Icon = VERDICT_ICON[laudo.verdict.status]

  return (
    <Card className={cn("ring-1", style.ring)}>
      <CardContent className="grid gap-6 md:grid-cols-[1fr_auto] md:items-center">
        <div className="flex items-start gap-4">
          <span className={cn("flex size-12 shrink-0 items-center justify-center rounded-2xl", style.bg, style.text)}>
            <Icon className="size-6" />
          </span>
          <div className="space-y-1.5">
            <h2 className="text-xl font-semibold tracking-tight text-balance">{laudo.verdict.headline}</h2>
            <p className="text-sm text-muted-foreground">{laudo.verdict.summary}</p>
            {laudo.macos.recommended_label && (
              <p className="text-sm text-muted-foreground">{laudo.macos.reason}</p>
            )}
          </div>
        </div>
        <div className="flex gap-6 md:border-l md:pl-6">
          {laudo.macos.recommended_label && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Versão recomendada</p>
              <p className="font-semibold">{laudo.macos.recommended_label}</p>
            </div>
          )}
          {laudo.difficulty && (
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Dificuldade</p>
              <DifficultyMeter score={laudo.difficulty.score} />
              <p className="text-sm font-medium">{laudo.difficulty.label}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function VersionStrip({ laudo }: { laudo: Laudo }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Versões do macOS</CardTitle>
        <CardDescription>Do High Sierra (2017) ao Tahoe, a última com suporte a processadores Intel.</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-9">
          {laudo.macos.versions.map((version) => {
            const status =
              version.status === "recommended" || version.status === "supported"
                ? "native"
                : version.status === "oclp"
                  ? "tweak"
                  : "incompatible"
            return (
              <li
                key={version.darwin}
                className={cn(
                  "rounded-lg border p-2.5",
                  version.status === "recommended" ? "border-primary bg-primary/8 ring-1 ring-primary/40" : "bg-background",
                  version.status === "unsupported" && "opacity-55",
                )}
              >
                <p className="truncate text-sm font-medium">{version.name}</p>
                <p className="text-xs text-muted-foreground">
                  {version.version} · {version.year}
                </p>
                <p className="mt-1.5 flex items-center gap-1.5 text-xs">
                  <StatusDot status={status} />
                  {VERSION_STATUS_LABEL[version.status]}
                </p>
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}

function ComponentRow({ component }: { component: LaudoComponent }) {
  const [open, setOpen] = useState(false)
  const hasDetails = component.details.length > 0
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="py-3 first:pt-0 last:pb-0">
      <CollapsibleTrigger asChild disabled={!hasDetails}>
        <button type="button" className="flex w-full items-start gap-3 text-left disabled:cursor-default">
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="truncate font-medium" title={component.name}>
              {component.name}
              {component.disabled && <span className="ml-2 text-xs font-normal text-muted-foreground">(desativado na EFI)</span>}
            </p>
            <p className="text-sm text-muted-foreground">{component.summary}</p>
          </div>
          <StatusBadge status={component.status} label={component.blocking ? "Impede a instalação" : undefined} />
          {hasDetails && (
            <ChevronDown className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="mt-2 ml-0.5 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
          {component.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}

function ComponentGroups({ components }: { components: LaudoComponent[] }) {
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: components.filter((component) => component.category === category),
  })).filter((group) => group.items.length > 0)

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {groups.map(({ category, items }) => {
        const info = CATEGORY[category] ?? { label: category, icon: Info }
        return (
          <Card key={category} size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <info.icon className="size-4 text-primary" />
                {info.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              {items.map((component, index) => (
                <ComponentRow key={`${component.name}-${index}`} component={component} />
              ))}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export function ReportStep() {
  const { payload, go } = useApp()
  const exporting = useTask()
  if (!payload) return null
  const { laudo } = payload
  const counts = laudo.components.reduce<Record<string, number>>((acc, component) => {
    acc[component.status] = (acc[component.status] ?? 0) + 1
    return acc
  }, {})
  const canContinue = laudo.verdict.status !== "incompatible"

  async function exportLaudo() {
    const result = await exporting.run("laudo", api.laudoExport)
    if (result) {
      toast.success("Laudo salvo na pasta do diagnóstico.")
      void api.openPath(result.pdf ?? result.html)
    }
  }

  async function exportScan() {
    try {
      const path = await api.scanExport()
      if (path) toast.success(`Diagnóstico salvo em ${path}`)
    } catch (error) {
      toast.error((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Laudo"
        title={laudo.machine.name}
        description={`${laudo.machine.form_label} · ${laudo.machine.cpu}${laudo.machine.ram_gb ? ` · ${laudo.machine.ram_gb} GB de RAM` : ""}`}
        actions={
          <>
            <Button variant="outline" disabled={exporting.running} onClick={() => void exportLaudo()}>
              <FileText data-icon="inline-start" />
              {exporting.running ? "Salvando..." : "Salvar laudo (PDF)"}
            </Button>
            <Button variant="outline" onClick={() => void exportScan()}>
              <Download data-icon="inline-start" />
              Exportar diagnóstico
            </Button>
            {canContinue && (
              <Button onClick={() => go("version")}>
                Escolher a versão
                <ArrowRight data-icon="inline-end" />
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-4">
        <VerdictHero laudo={laudo} />

        {laudo.fatal.map((item) => (
          <Alert key={item.code} variant={item.kind === "incompatible" ? "destructive" : "default"} className={item.kind === "bios" ? "border-tweak/40" : undefined}>
            {item.kind === "incompatible" ? <CircleX /> : <Wrench className="text-tweak" />}
            <AlertTitle>{item.title}</AlertTitle>
            <AlertDescription>{item.message}</AlertDescription>
          </Alert>
        ))}

        {laudo.warnings.map((warning) => (
          <Alert key={warning}>
            <TriangleAlert className="text-tweak" />
            <AlertDescription>{warning}</AlertDescription>
          </Alert>
        ))}

        <div className="flex flex-wrap gap-2 text-sm">
          {(["native", "tweak", "replace", "incompatible"] as const).map((status) =>
            counts[status] ? (
              <StatusBadge key={status} status={status} label={`${counts[status]} · ${{ native: "funcionam", tweak: "com ajuste", replace: "trocar", incompatible: "incompatíveis" }[status]}`} />
            ) : null,
          )}
        </div>

        <VersionStrip laudo={laudo} />

        {laudo.bios_requirements.length > 0 && (
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListChecks className="size-4 text-primary" />
                Ajustes obrigatórios na BIOS
              </CardTitle>
              <CardDescription>O guia final traz o passo a passo completo para a sua placa.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1.5 text-sm">
                {laudo.bios_requirements.map((requirement) => (
                  <li key={requirement} className="flex items-center gap-2">
                    <StatusDot status="tweak" />
                    {requirement}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <ComponentGroups components={laudo.components} />

        {laudo.difficulty && (
          <Card size="sm">
            <CardHeader>
              <CardTitle>Por que a dificuldade é “{laudo.difficulty.label.toLowerCase()}”</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                {laudo.difficulty.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <p className="text-xs text-muted-foreground">
          O laudo é uma estimativa feita com as regras da comunidade Hackintosh (OpCore Simplify) e não garante que tudo vá funcionar.
        </p>
      </div>
    </div>
  )
}
