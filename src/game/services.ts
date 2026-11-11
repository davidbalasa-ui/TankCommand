import { Capacitor } from '@capacitor/core';
import { Directory, Encoding, Filesystem } from '@capacitor/filesystem';
import rawGameplay from '../data/gameplay.json';
import { parseGameplayConfig } from '../data/gameplaySchema';
import { AudioEngine, type AudioStatusView, type SoundEvent } from '../audio/audio';
import { APP_VERSION } from '../platform/appInfo';
import { HapticsService } from '../platform/haptics';
import { createKvStore, StorageFullError, type KvStore } from '../platform/kv';
import { pushLog, recentLogs } from '../platform/logBuffer';
import {
  decodeSave,
  encodeSave,
  SaveManager,
  type LoadSaveResult,
} from '../platform/saves';
import { SettingsStore, type SettingsState } from '../platform/settings';
import type { WatchdogReport } from '../platform/watchdog';
import type { WorldState } from '../sim/types';
import { AUTOSAVE_CHECK_INTERVAL_MS } from '../sim/tuning';
import { SIM_TICK_HZ } from '../sim/constants';
import { AlertCenter, type AlertKind, type AlertSnapshot } from '../ui/alerts';
import type {
  AutosaveSummary,
  BugReportInput,
  BugReportResult,
  GameApi,
  ImportSaveResult,
  LoadSlotResult,
  SaveActionResult,
  SaveSlotSummary,
} from './api';
import { GameSpeed } from './speed';

export interface GameServicesHost {
  getWorld(): WorldState;
  loadWorld(world: WorldState, startMatch: boolean): void;
  currentScreen(): string;
  inMatch(): boolean;
  setCameraTarget(x: number, z: number): void;
  setSimSpeed(multiplier: number): void;
  getSimSpeed(): number;
  freezeReport(): WatchdogReport | null;
  applySettings(settings: SettingsState): void;
}

export interface GameServicesOptions {
  kv?: KvStore;
  settings?: SettingsStore;
  audio?: AudioEngine;
  mount?: HTMLElement;
  now?: () => number;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error';
}

function deviceInfo(): Record<string, string> {
  if (typeof navigator === 'undefined') {
    return { userAgent: 'unknown', platform: 'unknown', language: 'unknown', screen: 'unknown' };
  }
  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    language: navigator.language,
    screen:
      typeof window === 'undefined'
        ? 'unknown'
        : `${window.screen.width}x${window.screen.height}`,
  };
}

function downloadText(fileName: string, text: string): void {
  if (typeof document === 'undefined') {
    return;
  }
  const blob = new Blob([text], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}

export class GameServices implements GameApi {
  public readonly api: GameApi = this;
  private readonly host: GameServicesHost;
  private readonly kv: KvStore;
  private readonly manager: SaveManager;
  private readonly settingsStore: SettingsStore;
  private readonly audioEngine: AudioEngine;
  private readonly haptics: HapticsService;
  private readonly alertsCenter: AlertCenter;
  private readonly speed = new GameSpeed();
  private readonly autosaveMs: number;
  private readonly autosaveTimer: number;
  private lastAutoAt = 0;
  private lastSaveResult: SaveActionResult | null = null;
  private lastLoadResult: LoadSlotResult | null = null;
  private lastImportResult: ImportSaveResult | null = null;
  private lastReport: { fileName: string; content: string } | null = null;
  private forceStorageFull = false;

  constructor(host: GameServicesHost, options: GameServicesOptions = {}) {
    this.host = host;
    this.kv = options.kv ?? createKvStore();
    this.manager = new SaveManager(this.kv, { gameVersion: APP_VERSION });
    this.settingsStore = options.settings ?? new SettingsStore();
    this.audioEngine = options.audio ?? new AudioEngine();
    this.haptics = new HapticsService(this.settingsStore.getValue('haptics'));
    this.alertsCenter = new AlertCenter({
      host: options.mount ?? document.body,
      onJump: (x, z) => {
        this.host.setCameraTarget(x, z);
      },
      onAlert: (alert) => {
        this.audioEngine.play({ type: 'alert', kind: alert.kind });
        void this.haptics.alert();
      },
      now: options.now,
    });
    const gameplay = parseGameplayConfig(rawGameplay);
    this.autosaveMs = gameplay.autosaveMinutes * 60_000;
    this.host.setSimSpeed(this.speed.multiplier);
    this.applySettings(this.settingsStore.get());
    this.settingsStore.subscribe((state) => {
      this.applySettings(state);
    });
    this.lastAutoAt = Date.now();
    this.autosaveTimer = window.setInterval(() => {
      void this.maybeAutosave();
    }, AUTOSAVE_CHECK_INTERVAL_MS);
    this.alertsCenter.setEnabled(false);
  }

  settings(): Readonly<SettingsState> {
    return this.settingsStore.get();
  }

  setSetting<K extends keyof SettingsState>(key: K, value: SettingsState[K]): void {
    this.settingsStore.set(key, value);
  }

  simSpeed(): number {
    return this.host.getSimSpeed();
  }

  speedLabel(): string {
    return this.speed.label;
  }

  cycleSpeed(): void {
    this.speed.cycle();
    this.host.setSimSpeed(this.speed.multiplier);
  }

  setSpeedMultiplier(multiplier: number): void {
    this.speed.setMultiplier(multiplier);
    this.host.setSimSpeed(this.speed.multiplier);
  }

  async saveToSlot(slot: string): Promise<SaveActionResult> {
    if (this.forceStorageFull) {
      const result: SaveActionResult = {
        status: 'full',
        message: 'Storage is full; delete a save or free space.',
      };
      this.lastSaveResult = result;
      return result;
    }
    try {
      await this.manager.save(slot, this.host.getWorld());
      const result: SaveActionResult = { status: 'ok', message: `Saved ${slot}.` };
      this.lastSaveResult = result;
      return result;
    } catch (error) {
      const result: SaveActionResult =
        error instanceof StorageFullError
          ? { status: 'full', message: 'Storage is full; delete a save or free space.' }
          : { status: 'error', message: `Save failed: ${errorMessage(error)}` };
      this.lastSaveResult = result;
      return result;
    }
  }

  async loadFromSlot(slot: string): Promise<LoadSlotResult> {
    const loaded = await this.manager.load(slot);
    const result = this.fromLoadResult(loaded);
    if (result.status === 'ok' && loaded.status === 'ok') {
      this.host.loadWorld(loaded.save.world, !this.host.inMatch());
      result.savedAtIso = loaded.save.meta.savedAtIso;
    }
    this.lastLoadResult = result;
    return result;
  }

  async listSaveSlots(): Promise<SaveSlotSummary[]> {
    const summaries: SaveSlotSummary[] = [];
    for (let index = 1; index <= 5; index += 1) {
      const slot = `manual-${index}`;
      const loaded = await this.manager.load(slot);
      summaries.push({
        slot,
        savedAtIso: loaded.status === 'ok' ? loaded.save.meta.savedAtIso : null,
        status: loaded.status,
      });
    }
    return summaries;
  }

  async latestAutosave(): Promise<AutosaveSummary | null> {
    const slot = await this.manager.latestAutosaveSlot();
    if (!slot) {
      return null;
    }
    const loaded = await this.manager.load(slot);
    if (loaded.status !== 'ok') {
      return null;
    }
    const world = loaded.save.world;
    return {
      slot,
      savedAtIso: loaded.save.meta.savedAtIso,
      mode: world.mission ? 'mission' : 'skirmish',
      playSeconds: Math.floor(world.tick / SIM_TICK_HZ),
    };
  }

  async resumeLastGame(): Promise<LoadSlotResult> {
    const latest = await this.latestAutosave();
    if (!latest) {
      const result: LoadSlotResult = { status: 'missing', message: 'No autosave found.' };
      this.lastLoadResult = result;
      return result;
    }
    return this.loadFromSlot(latest.slot);
  }

  exportSave(): Promise<string> {
    return Promise.resolve(
      encodeSave(this.host.getWorld(), {
        gameVersion: APP_VERSION,
        savedAtIso: new Date().toISOString(),
      }),
    );
  }

  async importSave(text: string): Promise<ImportSaveResult> {
    const decoded = decodeSave(text);
    if (!decoded.ok) {
      const result: ImportSaveResult =
        decoded.reason === 'incompatible'
          ? { status: 'incompatible', message: 'That save is incompatible with this version.' }
          : { status: 'invalid', message: 'That file is not a valid TankCommand save.' };
      this.lastImportResult = result;
      return result;
    }
    if (this.forceStorageFull) {
      const result: ImportSaveResult = {
        status: 'full',
        message: 'Storage is full; delete a save or free space.',
      };
      this.lastImportResult = result;
      return result;
    }
    try {
      await this.manager.save('manual-1', decoded.world);
    } catch (error) {
      const result: ImportSaveResult =
        error instanceof StorageFullError
          ? { status: 'full', message: 'Storage is full; delete a save or free space.' }
          : { status: 'error', message: `Import failed: ${errorMessage(error)}` };
      this.lastImportResult = result;
      return result;
    }
    this.host.loadWorld(decoded.world, !this.host.inMatch());
    const result: ImportSaveResult = { status: 'ok', message: 'Save imported.' };
    this.lastImportResult = result;
    return result;
  }

  playSound(event: SoundEvent): void {
    this.audioEngine.play(event);
    if (event.type === 'selection') {
      void this.haptics.selection();
    } else if (event.type === 'orderAck') {
      void this.haptics.order();
    }
  }

  unlockAudio(): void {
    this.audioEngine.unlock();
  }

  audioStatus(): AudioStatusView {
    return this.audioEngine.status();
  }

  setMusic(faction: 'human' | 'alien', combat: boolean): void {
    this.audioEngine.setMusic(faction, combat);
  }

  raiseAlert(kind: AlertKind, x: number, z: number, message?: string): void {
    this.alertsCenter.raiseAlert(kind, x, z, message);
  }

  alerts(): AlertSnapshot[] {
    return this.alertsCenter.list();
  }

  jumpToAlert(id: number): void {
    const alert = this.alertsCenter.get(id);
    if (alert) {
      this.host.setCameraTarget(alert.x, alert.z);
    }
  }

  async saveBugReport(input: BugReportInput): Promise<BugReportResult> {
    const save = input.includeSave
      ? encodeSave(this.host.getWorld(), {
          gameVersion: APP_VERSION,
          savedAtIso: new Date().toISOString(),
        })
      : null;
    const content = JSON.stringify(
      {
        version: APP_VERSION,
        createdAt: new Date().toISOString(),
        message: input.message,
        includeSave: input.includeSave,
        device: deviceInfo(),
        lastFreezeReport: this.host.freezeReport(),
        logs: recentLogs(200),
        save,
      },
      null,
      2,
    );
    const fileName = `bug-report-${Date.now()}.json`;
    try {
      if (Capacitor.isNativePlatform()) {
        await Filesystem.writeFile({
          path: `bug-reports/${fileName}`,
          directory: Directory.Data,
          data: content,
          encoding: Encoding.UTF8,
        });
      } else {
        downloadText(fileName, content);
      }
      this.lastReport = { fileName, content };
      pushLog('info', `Bug report saved as ${fileName}`);
      return { status: 'ok', message: 'Saved', fileName, content };
    } catch (error) {
      return { status: 'error', message: `Could not save report: ${errorMessage(error)}` };
    }
  }

  lastFreezeReport(): WatchdogReport | null {
    return this.host.freezeReport();
  }

  logs(): string[] {
    return recentLogs(200);
  }

  version(): string {
    return APP_VERSION;
  }

  setMatchActive(active: boolean): void {
    this.alertsCenter.setEnabled(active);
  }

  observe(world: WorldState): void {
    if (!this.host.inMatch()) {
      this.alertsCenter.setEnabled(false);
      return;
    }
    this.alertsCenter.setEnabled(true);
    this.alertsCenter.update(world);
    const combat = world.projectiles.length > 0;
    this.audioEngine.setMusic('human', combat);
  }

  resetAlerts(world?: WorldState): void {
    this.alertsCenter.reset(world);
  }

  async maybeAutosave(): Promise<void> {
    if (!this.host.inMatch()) {
      return;
    }
    if (Date.now() - this.lastAutoAt < this.autosaveMs) {
      return;
    }
    await this.autosaveNow();
  }

  async onBackground(): Promise<void> {
    if (!this.host.inMatch()) {
      return;
    }
    await this.autosaveNow();
  }

  async requestAutosave(): Promise<void> {
    await this.autosaveNow();
  }

  lastSaveOutcome(): SaveActionResult | null {
    return this.lastSaveResult;
  }

  lastLoadOutcome(): LoadSlotResult | null {
    return this.lastLoadResult;
  }

  lastImportOutcome(): ImportSaveResult | null {
    return this.lastImportResult;
  }

  lastBugReport(): { fileName: string; content: string } | null {
    return this.lastReport;
  }

  async writeRawSave(slot: string, text: string): Promise<void> {
    await this.kv.set(`save:${slot}`, text);
  }

  setStorageFullForTest(value: boolean): void {
    this.forceStorageFull = value;
  }

  dispose(): void {
    window.clearInterval(this.autosaveTimer);
    this.alertsCenter.dispose();
  }

  private async autosaveNow(): Promise<void> {
    try {
      await this.manager.autosave(this.host.getWorld());
      this.lastAutoAt = Date.now();
    } catch (error) {
      if (error instanceof StorageFullError) {
        this.lastSaveResult = {
          status: 'full',
          message: 'Storage is full; delete a save or free space.',
        };
      }
    }
  }

  private applySettings(state: SettingsState): void {
    this.audioEngine.setMasterVolume(state.masterVolume);
    this.audioEngine.setMusicVolume(state.musicVolume);
    this.audioEngine.setEffectsVolume(state.effectsVolume);
    this.haptics.setEnabled(state.haptics);
    this.host.applySettings(state);
  }

  private fromLoadResult(loaded: LoadSaveResult): LoadSlotResult {
    switch (loaded.status) {
      case 'ok':
        return { status: 'ok', message: 'Save loaded.' };
      case 'missing':
        return { status: 'missing', message: 'That save slot is empty.' };
      case 'corrupt':
        return { status: 'corrupt', message: 'That save is corrupt and could not be loaded.' };
      case 'incompatible':
        return {
          status: 'incompatible',
          message: 'That save is incompatible with this version.',
        };
    }
  }
}
