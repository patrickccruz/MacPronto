// Ponte com o backend Python exposto pelo pywebview (window.pywebview.api).
// Fora do MacPronto (navegador comum ou ?mock na URL), usa um backend de demonstração.

import type { TaskEvent } from "./types"

type Envelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string; details?: string | null } }

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Backend = Record<string, (...args: any[]) => Promise<Envelope<any>>>

declare global {
  interface Window {
    pywebview?: { api: Backend }
    __macpronto?: (event: TaskEvent) => void
  }
}

export class BridgeError extends Error {
  code: string
  details?: string | null

  constructor(code: string, message: string, details?: string | null) {
    super(message)
    this.code = code
    this.details = details
  }
}

const listeners = new Set<(event: TaskEvent) => void>()

export function emit(event: TaskEvent) {
  listeners.forEach((listener) => listener(event))
}

window.__macpronto = emit

export function onTaskEvent(listener: (event: TaskEvent) => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function newTaskId(prefix = "tarefa") {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

let backendPromise: Promise<Backend> | null = null
let mockMode = false

export function isMockMode() {
  return mockMode
}

function waitForPywebview(timeout: number): Promise<Backend | null> {
  return new Promise((resolve) => {
    if (window.pywebview?.api) {
      resolve(window.pywebview.api)
      return
    }
    const timer = window.setTimeout(() => resolve(window.pywebview?.api ?? null), timeout)
    window.addEventListener(
      "pywebviewready",
      () => {
        window.clearTimeout(timer)
        resolve(window.pywebview?.api ?? null)
      },
      { once: true },
    )
  })
}

function backend(): Promise<Backend> {
  if (!backendPromise) {
    backendPromise = (async () => {
      const forceMock = new URLSearchParams(window.location.search).has("mock")
      const real = forceMock ? null : await waitForPywebview(3000)
      if (real) return real
      mockMode = true
      const { createMockBackend } = await import("./mock")
      return createMockBackend(emit)
    })()
  }
  return backendPromise
}

export async function call<T>(method: string, ...args: unknown[]): Promise<T> {
  const api = await backend()
  const fn = api[method]
  if (typeof fn !== "function") {
    throw new BridgeError("missing-method", `Função ${method} indisponível nesta versão.`)
  }
  const response = (await fn(...args)) as Envelope<T>
  if (!response || typeof response !== "object") {
    throw new BridgeError("bad-response", `Resposta inválida de ${method}.`)
  }
  if (!response.ok) {
    throw new BridgeError(response.error.code, response.error.message, response.error.details)
  }
  return response.data
}
