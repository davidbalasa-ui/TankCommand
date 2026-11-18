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
  type LoadedSave,
  type LoadSaveResult,
  type SaveExtras,
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
  /** Screen point of a map point, or null with no 3D view (used for the alert edge flash). */
  worldToScreen?(x: number, z: number): { x: number; y: number } | null;
  setSimSpeed(multiplier: number): void;
  getSimSpeed(): number;
  freezeReport(): WatchdogReport | null;
  applySettings(settings: SettingsState): void;
  /** A short name for what a saved world is playing (a mission's title, or "Skirmish"). */
  describeWorld?(world: WorldState): string;
}

export interface GameServicesOptions {
  kv?: KvStore;
  settings?: SettingsStore;
  audio?: AudioEngine;
  mount?: HTMLElement;
  now?: () => number;
}

const MANUAL_SLOTS = 5;
const STORAGE_FULL = 'Storage is full; delete a save or free space.';

function newMatchId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
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
  /** The running match: every save of it carries this id, so its autosaves go when it ends. */
  private matchId: string | null = null;

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
      locate: (x, z) => this.host.worldToScreen?.(x, z) ?? null,
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
    const label = /^manual-\d+$/.test(slot) ? `slot ${slot.slice('manual-'.length)}` : slot;
    return this.writeSave(() => this.manager.save(slot, this.host.getWorld(), this.extras()), `Saved to ${label}.`);
  }

  async quitSave(): Promise<SaveActionResult> {
    const result = await this.writeSave(
      () => this.manager.autosave(this.host.getWorld(), this.extras()),
      'Saved. Continue on the title screen picks it up.',
    );
    if (result.status === 'ok') {
      this.lastAutoAt = Date.now();
    }
    return result;
  }

  async deleteSlot(slot: string): Promise<SaveActionResult> {
    try {
      await this.manager.remove(slot);
      return { status: 'ok', message: 'Save deleted.' };
    } catch (error) {
      return { status: 'error', message: `Delete failed: ${errorMessage(error)}` };
    }
  }

  async loadFromSlot(slot: string): Promise<LoadSlotResult> {
    const loaded = await this.manager.load(slot);
    const result = this.fromLoadResult(loaded);
    if (result.status === 'ok' && loaded.status === 'ok') {
      this.matchId = loaded.save.meta.matchId ?? newMatchId();
      this.host.loadWorld(loaded.save.world, !this.host.inMatch());
      result.savedAtIso = loaded.save.meta.savedAtIso;
    }
    this.lastLoadResult = result;
    return result;
  }

  async listSaveSlots(): Promise<SaveSlotSummary[]> {
    const summaries: SaveSlotSummary[] = [];
    for (let index = 1; index <= MANUAL_SLOTS; index += 1) {
      const slot = `manual-${index}`;
      const loaded = await this.manager.load(slot);
      if (loaded.status === 'ok') {
        const world = loaded.save.world;
        summaries.push({
          slot,
          savedAtIso: loaded.save.meta.savedAtIso,
          status: 'ok',
          title: this.describe(world),
          playSeconds: Math.floor(world.tick / SIM_TICK_HZ),
        });
      } else {
        summaries.push({ slot, savedAtIso: null, status: loaded.status });
      }
    }
    return summaries;
  }

  async latestAutosave(): Promise<AutosaveSummary | null> {
    // The newest autosave wins, but only of a match that can still be played on.
    const preferred = await this.manager.latestAutosaveSlot();
    const slots = (await this.manager.listSlots()).filter((slot) => slot.startsWith('auto-'));
    let best: { slot: string; save: LoadedSave } | null = null;
    for (const slot of slots) {
      const loaded = await this.manager.load(slot);
      if (loaded.status !== 'ok' || loaded.save.world.result !== null) {
        continue;
      }
      if (slot === preferred) {
        best = { slot, save: loaded.save };
        break;
      }
      if (!best || loaded.save.meta.savedAtIso > best.save.meta.savedAtIso) {
        best = { slot, save: loaded.save };
      }
    }
    if (!best) {
      return null;
    }
    const world = best.save.world;
    return {
      slot: best.slot,
      savedAtIso: best.save.meta.savedAtIso,
      mode: world.mission ? 'mission' : 'skirmish',
      playSeconds: Math.floor(world.tick / SIM_TICK_HZ),
      title: this.describe(world),
    };
  }

  /** A new match is starting: its saves get a fresh match id. */
  beginMatch(): void {
    this.matchId = newMatchId();
  }

  /** The running match ended: its autosaves can't be played on, so Continue stops offering them. */
  async finishMatch(): Promise<void> {
    const finished = this.matchId;
    this.matchId = null;
    const slots = (await this.manager.listSlots()).filter((slot) => slot.startsWith('auto-'));
    for (const slot of slots) {
      const loaded = await this.manager.load(slot);
      const ended =
        loaded.status === 'ok' &&
        (loaded.save.world.result !== null || (finished !== null && loaded.save.meta.matchId === finished));
      if (ended) {
        await this.manager.remove(slot);
      }
    }
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
      const result: ImportSaveResult = { status: 'full', message: STORAGE_FULL };
      this.lastImportResult = result;
      return result;
    }
    const matchId = decoded.meta.matchId ?? newMatchId();
    // An import goes into the first empty manual slot. With none free it becomes the latest
    // autosave rather than overwriting one of the player's own saves.
    let slot: string | null = null;
    for (let index = 1; index <= MANUAL_SLOTS && slot === null; index += 1) {
      if ((await this.manager.load(`manual-${index}`)).status === 'missing') {
        slot = `manual-${index}`;
      }
    }
    try {
      if (slot) {
        await this.manager.save(slot, decoded.world, { matchId });
      } else {
        await this.manager.autosave(decoded.world, { matchId });
      }
    } catch (error) {
      const result: ImportSaveResult =
        error instanceof StorageFullError
          ? { status: 'full', message: STORAGE_FULL }
          : { status: 'error', message: `Import failed: ${errorMessage(error)}` };
      this.lastImportResult = result;
      return result;
    }
    this.matchId = matchId;
    this.host.loadWorld(decoded.world, !this.host.inMatch());
    const where = slot ? ` into slot ${slot.slice('manual-'.length)}` : '';
    const result: ImportSaveResult = { status: 'ok', message: `Save imported${where}.` };
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
      await this.manager.autosave(this.host.getWorld(), this.extras());
      this.lastAutoAt = Date.now();
    } catch (error) {
      if (error instanceof StorageFullError) {
        this.lastSaveResult = { status: 'full', message: STORAGE_FULL };
      }
    }
  }

  private extras(): SaveExtras {
    return this.matchId ? { matchId: this.matchId } : {};
  }

  private describe(world: WorldState): string {
    return this.host.describeWorld?.(world) ?? (world.mission ? 'Campaign' : 'Skirmish');
  }

  private async writeSave(write: () => Promise<void>, okMessage: string): Promise<SaveActionResult> {
    let result: SaveActionResult;
    if (this.forceStorageFull) {
      result = { status: 'full', message: STORAGE_FULL };
    } else {
      try {
        await write();
        result = { status: 'ok', message: okMessage };
      } catch (error) {
        result =
          error instanceof StorageFullError
            ? { status: 'full', message: STORAGE_FULL }
            : { status: 'error', message: `Save failed: ${errorMessage(error)}` };
      }
    }
    this.lastSaveResult = result;
    return result;
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
