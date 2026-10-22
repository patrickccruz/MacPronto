// Backend de demonstração: permite abrir a interface num navegador comum, sem o Python.
// Os dados vêm de frontend/src/mocks, gerados por scripts/make_ui_mocks.py.

import desktop from "@/mocks/desktop-coffee-lake-rx580.json"
import laptop from "@/mocks/laptop-tiger-lake.json"

import type { Backend } from "./bridge"
import type { ScanPayload, Selection, Settings, TaskEvent } from "./types"

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function ok<T>(data: T) {
  return { ok: true as const, data }
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
      return ok({ plan, selection: session.selection })
    },
  }
}
