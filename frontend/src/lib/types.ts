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
  guide: GuideInfo | null
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
  auto_update: boolean
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
  kind: "stage" | "progress" | "log" | "update"
  data: { title?: string; current?: number; total?: number; label?: string; level?: string; message?: string }
}

export interface UsbDevice {
  name: string
  vid_pid?: string | null
  speed: string
}

export interface UsbPort {
  index: number
  name: string
  speed: string
  class: number
  selected: boolean
  auto_selected: boolean
  type: number
  type_label: string
  type_guessed: boolean
  comment: string | null
  current: UsbDevice[]
  errors: string[]
  seen: UsbDevice[]
  companion: string | null
  user_connectable: boolean
}

export interface UsbController {
  id: string
  name: string
  class_label: string
  acpi_path: string | null
  selected: number
  total: number
  limit: number | null
  ports: UsbPort[]
}

export interface UsbState {
  controllers: UsbController[]
  errors: string[]
  /** Avisos que não impedem o mapa (portas sem teste, nenhuma USB 3 marcada). */
  warnings: string[]
  connector_types: { value: number; label: string }[]
  updated_at: string
}

export interface UsbBuildResult {
  kext: string
  efi_updated: boolean
  efi: EfiInfo | null
}

export interface GuideInfo {
  folder: string
  html: string
  pdf: string | null
  vendor: string
  profile?: { id: string; name: string; confidence: string; detected: boolean }
  generated: string
}

export interface GuideProfiles {
  choices: { id: string; name: string; group: string }[]
  detected: { id: string; name: string }
  /** Perfil escolhido à mão (null = o detectado). */
  selected: string | null
}

export interface ShareInfo {
  url: string
  qr_svg: string
  minutes: number
}

export interface DiskInfo {
  number: number
  model: string
  size_bytes: number
  size_gb: number
  bus: string
  unique_id: string
  system: boolean
  boot: boolean
  read_only: boolean
  letters: string[]
  labels: string[]
  eligible: boolean
  reason: string
}

export interface MediaResult {
  letter: string
  disk: DiskInfo
  product: string
  darwin: number
  recovery_cached: boolean
  /** Produto antigo substituído por um mais novo da Apple (null se não houve troca). */
  recovery_replaced?: string | null
  verified: boolean
  guide: GuideInfo
}

export interface EfiBuildItem extends EfiInfo {
  /** A pasta ainda tem o OpenCore e o config.plist. */
  complete: boolean
  /** É a EFI em uso nesta sessão. */
  current: boolean
  selection: Selection
}

export interface UpdateInfo {
  version: string
  tag: string
  name: string
  size: number
  sha256: string
  url: string
  page: string
  notes: string
  published_at: string | null
}

export interface UpdateStatus {
  current: string
  enabled: boolean
  /** Instalado pelo instalador (a cópia portátil é atualizada baixando de novo). */
  installed: boolean
  checking: boolean
  last_check: string | null
  error: string | null
  available: UpdateInfo | null
}

export interface RecoveryCacheItem {
  darwin: number
  product: string
  size: number
  downloaded_at: string | null
}

export interface EngineComponent {
  name: string
  repository: string
  pinned: string
  active: string
  origin: "travada" | "atualizada"
  installed_at: string | null
  commit_date: string | null
}

export interface EngineCheck {
  name: string
  sha: string
  date: string | null
  message: string
  active: string
  origin: string
  newer: boolean
}
