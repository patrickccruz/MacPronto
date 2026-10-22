import {
  BookOpenText,
  ClipboardCheck,
  Cpu,
  HardDriveDownload,
  House,
  type LucideIcon,
  ScanSearch,
  Sparkles,
  Usb,
} from "lucide-react"

import type { ScanPayload } from "./types"

export type StepId = "welcome" | "diagnosis" | "report" | "version" | "efi" | "usb" | "pendrive" | "guide"
export type ViewId = StepId | "logs" | "about"

export interface StepInfo {
  id: StepId
  title: string
  description: string
  icon: LucideIcon
}

export const STEPS: StepInfo[] = [
  { id: "welcome", title: "Início", description: "Como funciona", icon: House },
  { id: "diagnosis", title: "Diagnóstico", description: "Raio-X do computador", icon: ScanSearch },
  { id: "report", title: "Laudo", description: "O que funciona no macOS", icon: ClipboardCheck },
  { id: "version", title: "Versão do macOS", description: "Escolhas da instalação", icon: Sparkles },
  { id: "efi", title: "EFI", description: "Pasta de boot do OpenCore", icon: Cpu },
  { id: "usb", title: "Portas USB", description: "Mapeamento no Windows", icon: Usb },
  { id: "pendrive", title: "Pendrive", description: "Instalador do macOS", icon: HardDriveDownload },
  { id: "guide", title: "Guia", description: "Passo a passo da instalação", icon: BookOpenText },
]

export interface Progress {
  payload: ScanPayload | null
  efiReady: boolean
}

/** Motivo pelo qual a etapa ainda não está disponível, ou null se estiver. */
export function lockReason(step: StepId, progress: Progress, policyAccepted: boolean): string | null {
  if (step === "welcome") return null
  if (!policyAccepted) return "Aceite a política de uso na tela inicial."
  if (step === "diagnosis") return null
  if (!progress.payload) return "Faça ou abra um diagnóstico primeiro."
  if (step === "report") return null
  const verdict = progress.payload.laudo.verdict.status
  if (verdict === "incompatible") return "Este computador não é compatível com o macOS."
  if (step === "version" || step === "guide") return null
  if (step === "efi") {
    if (verdict === "needs-bios" || verdict === "needs-hardware") return "Resolva os impedimentos do laudo primeiro."
    return null
  }
  if (step === "usb") {
    if (progress.payload.scan.source !== "local") return "O mapeamento USB só funciona no próprio computador."
    return null
  }
  if (step === "pendrive") {
    if (!progress.efiReady) return "Monte a EFI primeiro."
    return null
  }
  return null
}
