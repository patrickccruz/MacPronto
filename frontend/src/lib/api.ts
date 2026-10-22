import { call } from "./bridge"
import type { AppInfo, LogLine, PlanPayload, ScanPayload, ScanSummary, Selection, Settings } from "./types"

export const api = {
  appInfo: () => call<AppInfo>("app_info"),
  settingsUpdate: (changes: Partial<Settings>) => call<Settings>("settings_update", changes),
  logsRecent: (lastId: number) => call<LogLine[]>("logs_recent", lastId),
  openLogsFolder: () => call<void>("open_logs_folder"),
  openPath: (path: string) => call<void>("open_path", path),
  revealPath: (path: string) => call<void>("reveal_path", path),
  openUrl: (url: string) => call<void>("open_url", url),
  cancel: (taskId: string) => call<boolean>("cancel", taskId),

  scanRun: (taskId: string) => call<ScanPayload>("scan_run", taskId),
  scanOpen: (taskId: string, scanId: string) => call<ScanPayload>("scan_open", taskId, scanId),
  scanImport: (taskId: string) => call<ScanPayload | null>("scan_import", taskId),
  scanList: () => call<ScanSummary[]>("scan_list"),
  scanDelete: (scanId: string) => call<void>("scan_delete", scanId),
  scanExport: () => call<string | null>("scan_export"),
  sessionState: () => call<ScanPayload | null>("session_state"),

  planUpdate: (taskId: string, selection: Partial<Selection>) =>
    call<{ plan: PlanPayload; selection: Selection }>("plan_update", taskId, selection),
}
