import { ArrowRight, LoaderCircle, Puzzle, Settings2, ShieldAlert, Sparkles } from "lucide-react"
import { cn } from "cn"

import { PageHeader } from "@/components/PageHeader"
import { StatusDot } from "@/components/StatusBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api } from "@/lib/api"
import { VERSION_STATUS_LABEL } from "@/lib/labels"
import { useApp } from "@/lib/store"
import type { Decision, MacVersion, Selection } from "@/lib/types"
import { useTask } from "@/lib/useTask"

function VersionCard({
  version,
  selected,
  disabled,
  onSelect,
}: {
  version: MacVersion
  selected: boolean
  disabled: boolean
  onSelect: () => void
}) {
  const unsupported = version.status === "unsupported"
  return (
    <button
      type="button"
      disabled={unsupported || disabled}
      onClick={onSelect}
      className={cn(
        "flex flex-col gap-1 rounded-xl border bg-card p-3.5 text-left transition-all",
        selected ? "border-primary ring-2 ring-primary/40" : "hover:border-primary/40",
        unsupported && "cursor-not-allowed opacity-45 hover:border-border",
      )}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="font-medium">{version.name}</span>
        {version.status === "recommended" && <Sparkles className="size-4 text-primary" />}
      </span>
      <span className="text-xs text-muted-foreground">
        macOS {version.version} · {version.year}
      </span>
      <span className="mt-1 flex items-center gap-1.5 text-xs">
        <StatusDot status={unsupported ? "incompatible" : version.status === "oclp" ? "tweak" : "native"} />
        {VERSION_STATUS_LABEL[version.status]}
      </span>
    </button>
  )
}

function DecisionControl({
  decision,
  disabled,
  onChange,
}: {
  decision: Decision
  disabled: boolean
  onChange: (value: string) => void
}) {
  if (decision.options.length === 0) {
    const checked = (decision.chosen || decision.recommended) === "yes"
    return (
      <div className="flex items-center gap-3">
        <Switch id={decision.key} checked={checked} disabled={disabled} onCheckedChange={(value) => onChange(value ? "yes" : "no")} />
        <Label htmlFor={decision.key}>{checked ? "Sim" : "Não"}</Label>
      </div>
    )
  }

  if (decision.options.length > 6) {
    return (
      <Select value={decision.chosen} disabled={disabled} onValueChange={onChange}>
        <SelectTrigger className="w-full max-w-md">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {decision.options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {decision.key === "audio-layout-id" ? `Layout ${option.value} · ${option.label}` : option.label_pt ?? option.label}
              {option.value === decision.recommended && " (recomendado)"}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  return (
    <RadioGroup value={decision.chosen} disabled={disabled} onValueChange={onChange} className="gap-2">
      {decision.options.map((option) => (
        <Label
          key={option.value}
          htmlFor={`${decision.key}-${option.value}`}
          className={cn(
            "flex items-start gap-3 rounded-lg border p-3 font-normal",
            decision.chosen === option.value && "border-primary/50 bg-primary/5",
          )}
        >
          <RadioGroupItem id={`${decision.key}-${option.value}`} value={option.value} className="mt-0.5" />
          <span className="space-y-0.5">
            <span className="flex flex-wrap items-center gap-2 font-medium">
              {option.label_pt ?? option.label}
              {option.value === decision.recommended && <Badge variant="secondary">Recomendado</Badge>}
            </span>
            {option.details?.map((detail) => (
              <span key={detail} className="block text-xs text-muted-foreground">
                {detail}
              </span>
            ))}
          </span>
        </Label>
      ))}
    </RadioGroup>
  )
}

export function VersionStep() {
  const { payload, setPlan, go, settings, updateSettings } = useApp()
  const task = useTask()
  if (!payload) return null
  const { laudo, plan, selection } = payload
  const busy = task.running

  async function update(changes: Partial<Selection>) {
    const result = await task.run("plano", (taskId) => api.planUpdate(taskId, changes))
    if (result) setPlan(result.plan, result.selection)
  }

  function answer(key: string, value: string) {
    void update({ answers: { ...selection.answers, [key]: value } })
  }

  const chosenVersion = laudo.macos.versions.find((version) => version.darwin === selection.darwin)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Versão do macOS"
        title="Escolha a versão e confira o plano"
        description="O MacPronto já marcou a versão recomendada. Trocar a versão recalcula kexts, patches e o modelo de Mac simulado."
        actions={
          <Button disabled={busy || !plan} onClick={() => go("efi")}>
            Montar a EFI
            <ArrowRight data-icon="inline-end" />
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {laudo.macos.versions.map((version) => (
          <VersionCard
            key={version.darwin}
            version={version}
            selected={selection.darwin === version.darwin}
            disabled={busy}
            onSelect={() => void update({ darwin: version.darwin, answers: {} })}
          />
        ))}
      </div>

      {chosenVersion?.note && <p className="text-sm text-muted-foreground">{chosenVersion.note}</p>}

      {busy && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin" />
          {task.stage ?? "Recalculando o plano..."}
        </div>
      )}

      {plan?.needs_oclp && (
        <Alert className="border-tweak/40">
          <ShieldAlert className="text-tweak" />
          <AlertTitle>Esta escolha exige o OpenCore Legacy Patcher</AlertTitle>
          <AlertDescription>
            Depois de instalar, você vai rodar o OCLP para repor drivers. Ele desliga proteções do macOS (SIP e AMFI), e as atualizações
            passam a exigir o instalador completo. O guia explica o passo a passo.
          </AlertDescription>
        </Alert>
      )}

      {plan && plan.decisions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Escolhas para esta máquina</CardTitle>
            <CardDescription>Já vêm com a opção recomendada. Mude só se souber o que está fazendo.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {plan.decisions.map((decision) => (
              <div key={decision.key} className="space-y-2.5">
                <div>
                  <p className="font-medium">{decision.label}</p>
                  {decision.help && <p className="text-sm text-muted-foreground">{decision.help}</p>}
                </div>
                <DecisionControl decision={decision} disabled={busy} onChange={(value) => answer(decision.key, value)} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {plan && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="size-4 text-primary" />
                Identidade de Mac (SMBIOS)
              </CardTitle>
              <CardDescription>O modelo de Mac que o macOS vai enxergar. Os números de série são gerados na montagem.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {settings.advanced ? (
                <Select
                  value={plan.smbios}
                  disabled={busy}
                  onValueChange={(value) => void update({ smbios_model: value === plan.default_smbios ? null : value })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {plan.smbios_candidates.map((candidate) => (
                      <SelectItem key={candidate.name} value={candidate.name}>
                        {candidate.name} · {candidate.generation}
                        {candidate.name === plan.default_smbios && " (recomendado)"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <p className="text-lg font-semibold">{plan.smbios}</p>
              )}
              {plan.disabled_devices.length > 0 && (
                <div className="space-y-1 text-sm">
                  <p className="font-medium">Dispositivos desativados na EFI</p>
                  {plan.disabled_devices.map((device) => (
                    <p key={device.label} className="text-muted-foreground">
                      {device.name}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Puzzle className="size-4 text-primary" />
                Patches ACPI ({plan.acpi_patches.length})
              </CardTitle>
              <CardDescription>Correções que fazem a BIOS deste PC conversar com o macOS.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {(settings.advanced ? plan.all_acpi_patches : plan.acpi_patches).map((patch) => {
                const checked = "checked" in patch ? Boolean(patch.checked) : true
                return (
                  <Tooltip key={patch.name}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        disabled={!settings.advanced || busy}
                        onClick={() => void update({ acpi_overrides: { ...selection.acpi_overrides, [patch.name]: !checked } })}
                        className={cn(
                          "rounded-md border px-2 py-1 font-mono text-xs",
                          checked ? "border-primary/40 bg-primary/8" : "text-muted-foreground opacity-60",
                          settings.advanced && "hover:border-primary",
                        )}
                      >
                        {patch.name}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">{patch.description}</TooltipContent>
                  </Tooltip>
                )
              })}
            </CardContent>
          </Card>

          <Card size="sm" className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Kexts ({plan.kexts.length})</CardTitle>
              <CardDescription>Drivers que a EFI vai carregar. Todos são baixados dos projetos oficiais no GitHub.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-x-6 gap-y-2.5 sm:grid-cols-2 xl:grid-cols-3">
              {plan.kexts.map((kext) => (
                <div key={kext.name} className="min-w-0">
                  <p className="truncate font-mono text-xs font-medium">{kext.name}</p>
                  <p className="text-xs text-muted-foreground">{kext.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex items-center justify-between gap-4 rounded-xl border bg-card p-4">
        <div className="space-y-0.5">
          <Label htmlFor="advanced">Modo avançado</Label>
          <p className="text-xs text-muted-foreground">Permite trocar o SMBIOS e ligar ou desligar patches ACPI.</p>
        </div>
        <Switch id="advanced" checked={settings.advanced} onCheckedChange={(value) => void updateSettings({ advanced: value })} />
      </div>
    </div>
  )
}
