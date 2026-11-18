import type { AudioStatusView, SoundEvent } from '../audio/audio';
import type { SettingsState } from '../platform/settings';
import type { WatchdogReport } from '../platform/watchdog';
import type { AlertKind, AlertSnapshot } from '../ui/alerts';

export interface SaveSlotSummary {
  slot: string;
  savedAtIso: string | null;
  status: 'ok' | 'missing' | 'corrupt' | 'incompatible';
  /** What was being played: the mission's name, or "Skirmish". */
  title?: string;
  /** In-game time played, in seconds. */
  playSeconds?: number;
}

export interface SaveActionResult {
  status: 'ok' | 'full' | 'error';
  message: string;
}

export interface LoadSlotResult {
  status: 'ok' | 'missing' | 'corrupt' | 'incompatible' | 'full' | 'error';
  message: string;
  savedAtIso?: string;
}

export interface AutosaveSummary {
  slot: string;
  savedAtIso: string;
  /** 'mission' when the save is a campaign mission, else 'skirmish'. */
  mode?: 'mission' | 'skirmish';
  /** In-game time played, in seconds. */
  playSeconds?: number;
  /** What was being played: the mission's name, or "Skirmish". */
  title?: string;
}

export interface ImportSaveResult {
  status: 'ok' | 'invalid' | 'incompatible' | 'full' | 'error';
  message: string;
}

export interface BugReportInput {
  message: string;
  includeSave: boolean;
}

export interface BugReportResult {
  /**
   * ok: saved on the device (Save). sent: the report server took it (Send). notSent: Send failed,
   * so it was saved on the device instead. error: nothing was saved or sent.
   */
  status: 'ok' | 'sent' | 'notSent' | 'error';
  message: string;
  fileName?: string;
  content?: string;
}

export interface GameApi {
  settings(): Readonly<SettingsState>;
  setSetting<K extends keyof SettingsState>(key: K, value: SettingsState[K]): void;
  simSpeed(): number;
  speedLabel(): string;
  cycleSpeed(): void;
  setSpeedMultiplier(multiplier: number): void;
  saveToSlot(slot: string): Promise<SaveActionResult>;
  loadFromSlot(slot: string): Promise<LoadSlotResult>;
  listSaveSlots(): Promise<SaveSlotSummary[]>;
  deleteSlot(slot: string): Promise<SaveActionResult>;
  /** Saves the running match for Continue on the title screen (never into a manual slot). */
  quitSave(): Promise<SaveActionResult>;
  /** Drops the running match's autosaves (restart, quit without saving), so Continue skips it. */
  discardMatch(): Promise<void>;
  /** The newest autosave of a match that has not ended, or null. */
  latestAutosave(): Promise<AutosaveSummary | null>;
  resumeLastGame(): Promise<LoadSlotResult>;
  exportSave(): Promise<string>;
  importSave(text: string): Promise<ImportSaveResult>;
  playSound(event: SoundEvent): void;
  unlockAudio(): void;
  audioStatus(): AudioStatusView;
  setMusic(faction: 'human' | 'alien', combat: boolean): void;
  raiseAlert(kind: AlertKind, x: number, z: number, message?: string): void;
  alerts(): AlertSnapshot[];
  jumpToAlert(id: number): void;
  /** Saves the report as a file on the device, with no network request (BUG-01). */
  saveBugReport(input: BugReportInput): Promise<BugReportResult>;
  /** Sends the report to the report server; if that fails it is saved on the device instead. */
  sendBugReport(input: BugReportInput): Promise<BugReportResult>;
  lastFreezeReport(): WatchdogReport | null;
  logs(): string[];
  version(): string;
}
