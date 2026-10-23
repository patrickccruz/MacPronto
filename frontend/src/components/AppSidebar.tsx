import { Check, Download, Info, Laptop, Lock, Moon, ScrollText, Sun } from "lucide-react"
import { cn } from "cn"

import { Logo } from "@/components/Logo"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { lockReason, STEPS, type ViewId } from "@/lib/steps"
import { useApp } from "@/lib/store"
import { useUpdates } from "@/lib/updates"

const THEMES = [
  { value: "system", label: "Igual ao Windows", icon: Laptop },
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
] as const

export function AppSidebar({ completed }: { completed: Set<ViewId> }) {
  const { view, go, payload, efiReady, settings, updateSettings, info, resolvedTheme } = useApp()
  const { status: update, openDialog } = useUpdates()
  const currentIndex = STEPS.findIndex((step) => step.id === view)

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-3 px-5 pt-5 pb-6">
        <Logo />
        <div className="leading-tight">
          <p className="font-semibold tracking-tight">MacPronto</p>
          <p className="text-xs text-muted-foreground">versão {info?.version ?? "..."}</p>
        </div>
      </div>

      <nav className="scroll-thin flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Etapas">
        {STEPS.map((step, index) => {
          const reason = lockReason(step.id, { payload, efiReady }, settings.policy_accepted)
          const active = view === step.id
          const done = completed.has(step.id) && !active
          const Icon = step.icon
          const item = (
            <button
              key={step.id}
              type="button"
              disabled={reason !== null}
              onClick={() => go(step.id)}
              aria-current={active ? "step" : undefined}
              className={cn(
                "group flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors",
                active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "hover:bg-sidebar-accent/60",
                reason !== null && "cursor-not-allowed opacity-45 hover:bg-transparent",
              )}
            >
              <span
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium tabular-nums",
                  active && "border-primary bg-primary text-primary-foreground",
                  done && "border-native/40 bg-native/15 text-native",
                  !active && !done && "border-sidebar-border bg-background text-muted-foreground",
                )}
              >
                {done ? <Check className="size-3.5" /> : reason !== null && index > currentIndex ? <Lock className="size-3" /> : <Icon className="size-3.5" />}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{step.title}</span>
                <span className="block truncate text-xs text-muted-foreground">{step.description}</span>
              </span>
            </button>
          )
          if (reason === null) return item
          return (
            <Tooltip key={step.id}>
              <TooltipTrigger asChild>
                <div>{item}</div>
              </TooltipTrigger>
              <TooltipContent side="right">{reason}</TooltipContent>
            </Tooltip>
          )
        })}
      </nav>

      <div className="space-y-1 border-t border-sidebar-border p-3">
        {update?.available && (
          <Button variant="ghost" className="w-full justify-start text-primary hover:text-primary" onClick={openDialog}>
            <Download data-icon="inline-start" />
            <span className="truncate">Atualizar para {update.available.version}</span>
          </Button>
        )}
        <Button
          variant="ghost"
          className={cn("w-full justify-start", view === "logs" && "bg-sidebar-accent")}
          onClick={() => go("logs")}
        >
          <ScrollText data-icon="inline-start" />
          Registros
        </Button>
        <Button
          variant="ghost"
          className={cn("w-full justify-start", view === "about" && "bg-sidebar-accent")}
          onClick={() => go("about")}
        >
          <Info data-icon="inline-start" />
          Sobre e créditos
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="w-full justify-start">
              {resolvedTheme === "dark" ? <Moon data-icon="inline-start" /> : <Sun data-icon="inline-start" />}
              Aparência
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="end">
            {THEMES.map((theme) => (
              <DropdownMenuItem key={theme.value} onSelect={() => void updateSettings({ theme: theme.value })}>
                <theme.icon />
                {theme.label}
                {settings.theme === theme.value && <Check className="ml-auto" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}
