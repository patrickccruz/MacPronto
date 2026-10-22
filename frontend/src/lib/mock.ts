// Backend de demonstração: permite abrir a interface num navegador comum, sem o Python.
// Os dados vêm de frontend/src/mocks, gerados por scripts/make_ui_mocks.py.

import desktop from "@/mocks/desktop-coffee-lake-rx580.json"
import laptop from "@/mocks/laptop-tiger-lake.json"

import type { Backend } from "./bridge"
import type { EfiInfo, ScanPayload, Selection, Settings, TaskEvent } from "./types"

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function ok<T>(data: T) {
  return { ok: true as const, data }
}

const SAMPLE_FOLDER = "C:\\Users\\voce\\Documents\\MacPronto\\EFI\\exemplo"

function sampleEfi(current: ScanPayload, keyboard: string): EfiInfo {
  return {
    created_at: new Date().toISOString(),
    scan_id: current.scan.id,
    machine: current.scan.label,
    folder: SAMPLE_FOLDER,
    efi_dir: `${SAMPLE_FOLDER}\\EFI`,
    zip: `${SAMPLE_FOLDER}\\EFI.zip`,
    size_mb: 23.5,
    opencore: "1.0.9",
    macos: current.selection.darwin ?? 24,
    keyboard,
    keyboard_label: "Português (Brasil), teclado ABNT2",
    usb_map: false,
    validation: { ran: true, ok: true, output: "No issues found." },
    config: {
      smbios: {
        model: current.plan?.smbios ?? "iMac19,1",
        serial: "C02XXXXXXXXX",
        mlb: "C02000000000000XX",
        uuid: "00000000-0000-0000-0000-000000000000",
        rom: "001122334455",
      },
      boot_args: "-v debug=0x100 keepsyms=1 alcid=1",
      keyboard: "pt-BR:128",
      kexts: (current.plan?.kexts ?? []).map((kext) => `${kext.name}.kext`),
      ssdts: ["SSDT-EC.aml", "SSDT-PLUG.aml", "SSDT-USBX.aml"],
      drivers: ["HfsPlus.efi", "OpenRuntime.efi", "ResetNvramEntry.efi"],
      secure_boot_model: "Disabled",
      vesa: false,
    },
    plan: { needs_oclp: false, smbios_model: current.plan?.smbios ?? "", decisions: [], bios_requirements: [], disabled_devices: [] },
  }
}

export function createMockBackend(emit: (event: TaskEvent) => void): Backend {
  const params = new URLSearchParams(window.location.search)
  const sample = (params.get("mock") === "laptop" ? laptop : desktop) as unknown as ScanPayload
  let settings: Settings = {
    theme: (params.get("theme") as Settings["theme"] | null) ?? "system",
    policy_accepted: params.has("accepted"),
    advanced: false,
    last_scan_id: null,
  }
  let session: ScanPayload | null = params.has("loaded") ? structuredClone(sample) : null
  if (session && params.has("efi")) session.efi = sampleEfi(session, "abnt2")
  const cancelled = new Set<string>()
  let logId = 0

  async function simulate(taskId: string, stages: string[]) {
    for (const [index, title] of stages.entries()) {
      if (cancelled.has(taskId)) throw new Error("cancelled")
      emit({ taskId, kind: "stage", data: { title } })
      for (let step = 0; step <= 4; step++) {
        emit({ taskId, kind: "progress", data: { current: index * 4 + step, total: stages.length * 4, label: title } })
        await wait(120)
      }
    }
  }

  return {
    app_info: async () =>
      ok({
        version: "0.1.0",
        is_admin: false,
        documents_dir: "C:\\Users\\voce\\Documents\\MacPronto",
        logs_dir: "C:\\Users\\voce\\AppData\\Local\\MacPronto\\logs",
        settings,
        components: {
          "OpCore-Simplify": { commit: "f0e1e441bb45", repository: "https://github.com/lzhoang2801/OpCore-Simplify", license: "BSD-3-Clause" },
          "Hardware-Sniffer": { commit: "2e0fa1602027", repository: "https://github.com/lzhoang2801/Hardware-Sniffer", license: "BSD-3-Clause" },
          USBToolBox: { commit: "0c6823a2c643", repository: "https://github.com/USBToolBox/tool", license: "MIT" },
          macrecovery: { commit: "963025f1382e", repository: "https://github.com/acidanthera/OpenCorePkg", license: "BSD-3-Clause" },
        },
      }),
    settings_update: async (changes: Partial<Settings>) => {
      settings = { ...settings, ...changes }
      return ok(settings)
    },
    logs_recent: async () => {
      logId += 1
      return ok([{ id: logId, time: new Date().toLocaleTimeString("pt-BR"), level: "info", source: "demo", message: "Modo de demonstração: nenhum dado real." }])
    },
    open_logs_folder: async () => ok(null),
    open_path: async () => ok(null),
    reveal_path: async () => ok(null),
    open_url: async (url: string) => {
      window.open(url, "_blank")
      return ok(null)
    },
    cancel: async (taskId: string) => {
      cancelled.add(taskId)
      return ok(true)
    },
    scan_run: async (taskId: string) => {
      try {
        await simulate(taskId, ["Coletando informações do hardware", "Lendo informações complementares", "Extraindo tabelas ACPI", "Verificando compatibilidade", "Selecionando kexts"])
      } catch {
        return { ok: false as const, error: { code: "cancelled", message: "Operação cancelada." } }
      }
      session = structuredClone(sample)
      return ok(session)
    },
    scan_open: async (taskId: string) => {
      await simulate(taskId, ["Abrindo o diagnóstico", "Verificando compatibilidade"])
      session = structuredClone(sample)
      return ok(session)
    },
    scan_import: async (taskId: string) => {
      await simulate(taskId, ["Importando o diagnóstico"])
      session = structuredClone(laptop as unknown as ScanPayload)
      return ok(session)
    },
    scan_list: async () =>
      ok([
        { ...desktop.scan, label: desktop.scan.label },
        { ...laptop.scan, source: "imported", label: laptop.scan.label },
      ]),
    scan_delete: async () => ok(null),
    scan_export: async () => ok("C:\\Users\\voce\\Documents\\MacPronto\\exemplo.macpronto"),
    session_state: async () => ok(session),
    efi_keyboards: async () =>
      ok([
        { value: "abnt2", label: "Português (Brasil), teclado ABNT2" },
        { value: "br-pro", label: "Português (Brasil), teclado Brasileiro Pro" },
        { value: "us", label: "Inglês (EUA), teclado americano" },
      ]),
    efi_build: async (taskId: string, options: { keyboard: string }) => {
      await simulate(taskId, ["Preparando o iasl", "Carregando tabelas ACPI", "Baixando OpenCore e kexts", "Montando a EFI", "Validando o config.plist com o ocvalidate"])
      if (!session) return { ok: false as const, error: { code: "no-scan", message: "Sem diagnóstico." } }
      const efi = sampleEfi(session, options.keyboard)
      session.efi = efi
      return ok(efi)
    },
    plan_update: async (taskId: string, selection: Partial<Selection>) => {
      await simulate(taskId, ["Recalculando o plano da EFI"])
      if (!session || !session.plan) return { ok: false as const, error: { code: "no-scan", message: "Sem diagnóstico." } }
      session.selection = { ...session.selection, ...selection }
      const plan = { ...session.plan, macos: session.selection.darwin ?? session.plan.macos }
      plan.decisions = plan.decisions.map((decision) => ({
        ...decision,
        chosen: session!.selection.answers[decision.key] ?? decision.recommended,
      }))
      if (session.selection.smbios_model) plan.smbios = session.selection.smbios_model
      session.plan = plan
      session.efi = null
      return ok({ plan, selection: session.selection })
    },
  }
}
