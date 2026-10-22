import {
  Bluetooth,
  CircuitBoard,
  Cpu,
  CreditCard,
  Fingerprint,
  HardDrive,
  type LucideIcon,
  MemoryStick,
  Monitor,
  MousePointer2,
  Network,
  Speaker,
  Usb,
  Wifi,
} from "lucide-react"

import type { ComponentStatus, VerdictStatus, VersionStatus } from "./types"

export const STATUS_LABEL: Record<ComponentStatus, string> = {
  native: "Funciona",
  tweak: "Com ajuste",
  replace: "Trocar peça",
  incompatible: "Incompatível",
  info: "Informação",
}

// Classes completas (o Tailwind só gera classes que aparecem escritas no código).
export const STATUS_STYLE: Record<ComponentStatus, { text: string; bg: string; border: string; ring: string; dot: string }> = {
  native: { text: "text-native", bg: "bg-native/10", border: "border-native/30", ring: "ring-native/40", dot: "bg-native" },
  tweak: { text: "text-tweak", bg: "bg-tweak/12", border: "border-tweak/35", ring: "ring-tweak/45", dot: "bg-tweak" },
  replace: { text: "text-replace", bg: "bg-replace/12", border: "border-replace/35", ring: "ring-replace/45", dot: "bg-replace" },
  incompatible: {
    text: "text-incompatible",
    bg: "bg-incompatible/10",
    border: "border-incompatible/30",
    ring: "ring-incompatible/40",
    dot: "bg-incompatible",
  },
  info: { text: "text-info", bg: "bg-info/10", border: "border-info/25", ring: "ring-info/30", dot: "bg-info" },
}

export const VERDICT_TONE: Record<VerdictStatus, ComponentStatus> = {
  compatible: "native",
  caveats: "tweak",
  "needs-bios": "tweak",
  "needs-hardware": "replace",
  incompatible: "incompatible",
}

export const VERSION_STATUS_LABEL: Record<VersionStatus, string> = {
  recommended: "Recomendada",
  supported: "Compatível",
  oclp: "Requer OCLP",
  unsupported: "Sem suporte",
}

export const CATEGORY: Record<string, { label: string; icon: LucideIcon }> = {
  cpu: { label: "Processador", icon: Cpu },
  gpu: { label: "Vídeo", icon: Monitor },
  audio: { label: "Áudio", icon: Speaker },
  ethernet: { label: "Rede cabeada", icon: Network },
  wifi: { label: "Wi-Fi", icon: Wifi },
  bluetooth: { label: "Bluetooth", icon: Bluetooth },
  storage: { label: "Armazenamento", icon: HardDrive },
  disk: { label: "Discos", icon: HardDrive },
  usb: { label: "USB", icon: Usb },
  input: { label: "Teclado e touchpad", icon: MousePointer2 },
  biometric: { label: "Biometria", icon: Fingerprint },
  sdcard: { label: "Leitor de cartão", icon: CreditCard },
  firmware: { label: "BIOS", icon: CircuitBoard },
  memory: { label: "Memória", icon: MemoryStick },
}

export const CATEGORY_ORDER = [
  "cpu",
  "gpu",
  "audio",
  "ethernet",
  "wifi",
  "bluetooth",
  "storage",
  "disk",
  "usb",
  "input",
  "biometric",
  "sdcard",
  "firmware",
]

export function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
  } catch {
    return iso
  }
}
