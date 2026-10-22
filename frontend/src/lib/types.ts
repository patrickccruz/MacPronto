// Tipos que espelham os dados devolvidos pelo backend Python (src/macpronto).

export type ComponentStatus = "native" | "tweak" | "replace" | "incompatible" | "info"
export type VerdictStatus = "compatible" | "caveats" | "needs-bios" | "needs-hardware" | "incompatible"
export type VersionStatus = "recommended" | "supported" | "oclp" | "unsupported"

export interface VersionRange {
  min: number
  max: number
}

export interface LaudoComponent {
  category: string
  name: string
  status: ComponentStatus
  summary: string
  details: string[]
  device_id?: string | null
  blocking: boolean
  disabled: boolean
  range?: VersionRange | null
  oclp_range?: VersionRange | null
}

export interface MacVersion {
  darwin: number
  name: string
  version: string
  year: number
  label: string
  note: string
  status: VersionStatus
}

export interface Machine {
  name: string
  form_factor: "laptop" | "desktop" | "mini"
  form_label: string
  manufacturer: string
  model: string
  board: string
  chipset: string
  cpu: string
  cpu_codename: string
  gpus: string[]
  ram_gb: number | null
  firmware: string
  secure_boot: string
  bios_vendor: string
  os: string
  virtual_machine: boolean
}

export interface Fatal {
  code: string
  kind: "incompatible" | "replace" | "bios"
  title: string
  message: string
  original: string
}

export interface DecisionOption {
  value: string
  label: string
  label_pt?: string | null
  details?: string[]
}

export interface Decision {
  key: string
  label: string
  prompt: string
  help?: string
  options: DecisionOption[]
  recommended: string
  chosen: string
}

export interface KextInfo {
  name: string
  description: string
}

export interface PlanPayload {
  macos: number
  smbios: string
  needs_oclp: boolean
  kexts: KextInfo[]
  acpi_patches: KextInfo[]
  disabled_devices: { label: string; type: string; name: string; device_id?: string | null }[]
  decisions: Decision[]
  smbios_candidates: { name: string; cpu: string; generation: string; gpu: string | null }[]
  default_smbios: string
  all_kexts: { name: string; description: string; category: string; checked: boolean; required: boolean }[]
  all_acpi_patches: { name: string; description: string; checked: boolean }[]
  bios_requirements: string[]
}

export interface Laudo {
  generated_at: string
  app_version: string
  scan_id: string
  source: "local" | "imported"
  machine: Machine
  verdict: { status: VerdictStatus; headline: string; summary: string }
  difficulty: { score: number; label: string; reasons: string[] } | null
  macos: {
    recommended: number | null
    recommended_label: string | null
    reason: string
    native: { min: string; max: string } | null
    oclp: { min: string; max: string } | null
    maximum: number | null
    versions: MacVersion[]
  }
  components: LaudoComponent[]
  fatal: Fatal[]
  bios_requirements: string[]
  warnings: string[]
  efi_plan: PlanPayload | null
}

export interface ScanSummary {
  id: string
  created_at: string
  source: "local" | "imported"
  label: string
  has_acpi: boolean
}

export interface Selection {
  darwin: number | null
  answers: Record<string, string>
  smbios_model: string | null
  acpi_overrides: Record<string, boolean>
  kext_overrides: Record<string, boolean>
}

export type HardwareReport = Record<string, Record<string, unknown>>

export interface Extras {
  system?: { manufacturer?: string; model?: string; family?: string; form_factor?: string; is_virtual_machine?: boolean }
  baseboard?: { manufacturer?: string; product?: string }
  bios?: { vendor?: string; version?: string; date?: string }
  os?: { caption?: string; version?: string; build?: string }
  memory?: { total_gb?: number; modules?: { capacity_gb: number; speed_mhz: number; manufacturer: string }[] }
  battery?: { present: boolean; count: number }
  disks?: { number: number; model: string; size_gb: number; bus: string; media: string; system: boolean }[]
}

export interface EfiInfo {
  created_at: string
  scan_id: string
  machine: string
  folder: string
  efi_dir: string
  zip: string
  size_mb: number
  opencore: string | null
  macos: number
  keyboard: string
  keyboard_label: string
  usb_map: boolean
  validation: { ran: boolean; ok: boolean | null; output: string } | null
  config: {
    smbios: { model: string; serial: string; mlb: string; uuid: string; rom: string }
    boot_args: string
    keyboard: string
    kexts: string[]
    ssdts: string[]
    drivers: string[]
    secure_boot_model: string
    vesa: boolean
  }
  plan: {
    needs_oclp: boolean
    smbios_model: string
    decisions: Decision[]
    bios_requirements: string[]
    disabled_devices: { label: string; type: string; name: string }[]
  }
}

export interface ScanPayload {
  scan: ScanSummary
  report: HardwareReport
  extras: Extras
  acpi_tables: string[]
  laudo: Laudo
  plan: PlanPayload | null
  selection: Selection
  efi: EfiInfo | null
  usb_mapped: boolean
}

export interface AppInfo {
  version: string
  is_admin: boolean
  documents_dir: string
  logs_dir: string
  settings: Settings
  components: Record<string, { commit: string; repository: string; license: string }>
}

export interface Settings {
  theme: "system" | "light" | "dark"
  policy_accepted: boolean
  advanced: boolean
  last_scan_id: string | null
}

export interface LogLine {
  id: number
  time: string
  level: "debug" | "info" | "warning" | "error"
  source: string
  message: string
}

export interface TaskEvent {
  taskId: string
  kind: "stage" | "progress" | "log"
  data: { title?: string; current?: number; total?: number; label?: string; level?: string; message?: string }
}
