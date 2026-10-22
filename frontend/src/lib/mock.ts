// Backend de demonstração: permite abrir a interface num navegador comum, sem o Python.
// Os dados vêm de frontend/src/mocks, gerados por scripts/make_ui_mocks.py.

import desktop from "@/mocks/desktop-coffee-lake-rx580.json"
import laptop from "@/mocks/laptop-tiger-lake.json"

import type { Backend } from "./bridge"
import type { EfiInfo, ScanPayload, Selection, Settings, TaskEvent, UsbPort, UsbState } from "./types"

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

const CONNECTORS = [
  { value: 0, label: "USB 2 Tipo A" },
  { value: 3, label: "USB 3 Tipo A" },
  { value: 8, label: "Tipo C (só USB 2)" },
  { value: 9, label: "Tipo C (com chave)" },
  { value: 10, label: "Tipo C (sem chave)" },
  { value: 255, label: "Interna" },
]

function sampleUsb(): UsbState {
  const seen: Record<string, string> = { HS01: "Logitech Unifying Receiver", HS03: "SanDisk Cruzer", HS14: "Intel(R) Wireless Bluetooth(R)", SS01: "Samsung BAR Plus", SS03: "Samsung BAR Plus" }
  const ports: UsbPort[] = []
  for (let index = 1; index <= 20; index++) {
    const usb3 = index > 14
    const name = usb3 ? `SS${String(index - 14).padStart(2, "0")}` : `HS${String(index).padStart(2, "0")}`
    const device = seen[name]
    const type = name === "HS14" ? 255 : usb3 || index <= 6 ? 3 : 0
    ports.push({
      index,
      name,
      speed: usb3 ? "USB 3.0" : "USB 2.0",
      class: usb3 ? 3 : 2,
      selected: Boolean(device) || (!usb3 && index <= 6 && Boolean(seen[`SS${String(index).padStart(2, "0")}`])),
      auto_selected: true,
      type,
      type_label: CONNECTORS.find((item) => item.value === type)?.label ?? "",
      type_guessed: true,
      comment: name === "SS01" ? "Traseira, em cima" : null,
      current: name === "SS03" ? [{ name: "Samsung BAR Plus", speed: "USB 3.0" }] : [],
      errors: [],
      seen: device ? [{ name: device, speed: usb3 ? "USB 3.0" : "USB 2.0" }] : [],
      companion: usb3 ? `HS${String(index - 14).padStart(2, "0")}` : index <= 6 ? `SS${String(index).padStart(2, "0")}` : null,
      user_connectable: name !== "HS14",
    })
  }
  return {
    controllers: [
      {
        id: "PCI\\VEN_8086&DEV_A36D",
        name: "Intel(R) USB 3.1 eXtensible Host Controller - 1.10 (Microsoft)",
        class_label: "USB 3 (XHCI)",
        acpi_path: "\\_SB.PCI0.XHC",
        selected: ports.filter((port) => port.selected).length,
        total: ports.length,
        limit: 15,
        ports,
      },
    ],
    errors: [],
    connector_types: CONNECTORS,
    updated_at: new Date().toLocaleTimeString("pt-BR"),
  }
}

function recount(state: UsbState) {
  for (const controller of state.controllers) controller.selected = controller.ports.filter((port) => port.selected).length
  state.updated_at = new Date().toLocaleTimeString("pt-BR")
  return state
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
  let usb = sampleUsb()
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
    usb_refresh: async () => ok(recount(usb)),
    usb_update_port: async (_controller: string, index: number, changes: { selected?: boolean; type?: number; comment?: string }) => {
      const port = usb.controllers[0].ports.find((item) => item.index === index)
      if (port) {
        if (changes.selected !== undefined) port.selected = changes.selected
        if (changes.type !== undefined) {
          port.type = changes.type
          port.type_guessed = false
          port.type_label = CONNECTORS.find((item) => item.value === changes.type)?.label ?? ""
        }
        if (changes.comment !== undefined) port.comment = changes.comment || null
      }
      return ok(recount(usb))
    },
    usb_select: async (mode: string) => {
      for (const port of usb.controllers[0].ports) port.selected = mode === "all" ? true : mode === "none" ? false : port.seen.length > 0
      return ok(recount(usb))
    },
    usb_reset: async () => {
      usb = sampleUsb()
      return ok(usb)
    },
    usb_build: async () => {
      if (session) session.usb_mapped = true
      if (session?.efi) session.efi = { ...session.efi, usb_map: true }
      return ok({ kext: `${SAMPLE_FOLDER}\\UTBMap.kext`, efi_updated: Boolean(session?.efi), efi: session?.efi ?? null })
    },
    laudo_export: async (taskId: string) => {
      await simulate(taskId, ["Salvando o laudo"])
      return ok({ html: `${SAMPLE_FOLDER}\\Laudo.html`, pdf: `${SAMPLE_FOLDER}\\Laudo.pdf` })
    },
    guide_build: async (taskId: string) => {
      await simulate(taskId, ["Gerando o guia personalizado"])
      const guide = {
        folder: SAMPLE_FOLDER,
        html: `${SAMPLE_FOLDER}\\Guia.html`,
        pdf: `${SAMPLE_FOLDER}\\Guia.pdf`,
        vendor: "Gigabyte",
        generated: new Date().toLocaleString("pt-BR"),
      }
      if (session) session.guide = guide
      return ok(guide)
    },
    guide_share_start: async () =>
      ok({
        url: "http://192.168.0.10:51234/Guia.html",
        qr_svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21"><rect width="21" height="21" fill="#fff"/><path d="M1 1h7v7H1zM13 1h7v7h-7zM1 13h7v7H1z" fill="#111827"/><path d="M10 10h2v2h-2zM14 14h2v2h-2zM17 11h2v2h-2z" fill="#111827"/></svg>',
        minutes: 30,
      }),
    guide_share_stop: async () => ok(null),
    media_disks: async () =>
      ok([
        { number: 2, model: "SanDisk Ultra USB 3.0", size_bytes: 32010928128, size_gb: 32, bus: "USB", unique_id: "USBSTOR\\SANDISK", system: false, boot: false, read_only: false, letters: ["E"], labels: ["SANDISK"], eligible: true, reason: "" },
        { number: 0, model: "Samsung SSD 970 EVO Plus 500GB", size_bytes: 500107862016, size_gb: 500.1, bus: "NVMe", unique_id: "eui.0025", system: true, boot: true, read_only: false, letters: ["C"], labels: ["Windows"], eligible: false, reason: "É o disco do Windows." },
        { number: 1, model: "Seagate Expansion", size_bytes: 2000398934016, size_gb: 2000.4, bus: "USB", unique_id: "USBSTOR\\SEAGATE", system: false, boot: false, read_only: false, letters: ["D"], labels: ["Backup"], eligible: false, reason: "Grande demais para ser um pendrive. Se for um HD externo, use outro dispositivo." },
      ]),
    media_create: async (taskId: string) => {
      await simulate(taskId, ["Atualizando o guia", "Conferindo o pendrive", "Baixando o macOS Recovery da Apple", "Apagando e formatando o pendrive", "Copiando o macOS Recovery", "Copiando a EFI", "Conferindo o pendrive"])
      return ok({ letter: "E", disk: null, product: "696-28424", darwin: 24, recovery_cached: false, verified: true, guide: session?.guide })
    },
    media_eject: async () => ok(true),
    relaunch_as_admin: async () => ok(false),
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
