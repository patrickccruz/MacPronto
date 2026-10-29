import { call } from "./bridge"
import type {
  AppInfo,
  EfiBuildItem,
  EfiInfo,
  LogLine,
  PlanPayload,
  ScanPayload,
  ScanSummary,
  Selection,
  Settings,
  DiskInfo,
  EngineCheck,
  EngineComponent,
  GuideInfo,
  GuideProfiles,
  MediaResult,
  RecoveryCacheItem,
  ShareInfo,
  UpdateStatus,
  UsbBuildResult,
  UsbState,
} from "./types"

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

  efiBuild: (taskId: string, options: { keyboard: string; use_usb_map: boolean }) =>
    call<EfiInfo>("efi_build", taskId, options),
  efiKeyboards: () => call<{ value: string; label: string }[]>("efi_keyboards"),
  efiBuilds: () => call<EfiBuildItem[]>("efi_builds"),
  efiUse: (taskId: string, folder: string) => call<ScanPayload>("efi_use", taskId, folder),

  usbRefresh: () => call<UsbState>("usb_refresh"),
  usbUpdatePort: (controllerId: string, index: number, changes: { selected?: boolean; type?: number | null; comment?: string }) =>
    call<UsbState>("usb_update_port", controllerId, index, changes),
  usbSelect: (mode: "used" | "all" | "none" | "fill") => call<UsbState>("usb_select", mode),
  usbReset: () => call<UsbState>("usb_reset"),
  usbBuild: () => call<UsbBuildResult>("usb_build"),

  laudoExport: (taskId: string) => call<{ html: string; pdf: string | null }>("laudo_export", taskId),
  guideBuild: (taskId: string, options?: { profile: string }) => call<GuideInfo>("guide_build", taskId, options ?? null),
  guideProfiles: () => call<GuideProfiles>("guide_profiles"),
  guideShareStart: () => call<ShareInfo>("guide_share_start"),
  guideShareStop: () => call<void>("guide_share_stop"),

  mediaDisks: () => call<DiskInfo[]>("media_disks"),
  mediaCreate: (taskId: string, options: { number: number; unique_id: string; size_bytes: number; confirm: string }) =>
    call<MediaResult>("media_create", taskId, options),
  mediaEject: (letter: string) => call<boolean>("media_eject", letter),
  mediaRecoveryCache: () => call<RecoveryCacheItem[]>("media_recovery_cache"),
  mediaRecoveryClear: () => call<number>("media_recovery_clear"),

  updateStatus: () => call<UpdateStatus>("update_status"),
  updateCheck: () => call<UpdateStatus>("update_check"),
  updateInstall: (taskId: string) => call<{ version: string; restarting: boolean }>("update_install", taskId),
  relaunchAsAdmin: () => call<boolean>("relaunch_as_admin"),

  engineStatus: () => call<EngineComponent[]>("engine_status"),
  engineCheck: (name: string) => call<EngineCheck>("engine_check", name),
  engineUpdate: (taskId: string, name: string) =>
    call<{ name: string; commit: string; date: string | null; selftest: string }>("engine_update", taskId, name),
  engineRevert: (name: string) => call<EngineComponent[]>("engine_revert", name),
}
