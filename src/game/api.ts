import type { AudioStatusView, SoundEvent } from '../audio/audio';
import type { SettingsState } from '../platform/settings';
import type { WatchdogReport } from '../platform/watchdog';
import type { AlertKind, AlertSnapshot } from '../ui/alerts';

export interface SaveSlotSummary {
  slot: string;
  savedAtIso: string | null;
  status: 'ok' | 'missing' | 'corrupt' | 'incompatible';
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
  status: 'ok' | 'error';
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
  saveBugReport(input: BugReportInput): Promise<BugReportResult>;
  lastFreezeReport(): WatchdogReport | null;
  logs(): string[];
  version(): string;
}
