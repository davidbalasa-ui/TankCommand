import type { App, CameraView, IssuedCommand, QualityView, UnitView } from '../app';
import { ControlInventory } from '../ui/controls';
import type {
  BuildItemView,
  DropQueueView,
  HudSnapshot,
  KitView,
  PlacementView,
  ScreenId,
} from '../ui/router';
import type {
  CommandOutcome,
  DepositState,
  SideStats,
  WorldState,
} from '../sim/types';
import type { WatchdogReport } from '../platform/watchdog';
import type { RenderStats, ScreenBounds } from '../render/renderer';
import type {
  ImportSaveResult,
  LoadSlotResult,
  SaveActionResult,
  SaveSlotSummary,
} from '../game/api';
import type { AlertKind, AlertSnapshot } from '../ui/alerts';
import type { AudioStatusView } from '../audio/audio';
import type { SettingsState } from '../platform/settings';

export interface StructureView {
  id: number;
  owner: number;
  typeId: string;
  kind: string;
  x: number;
  z: number;
  hp: number;
  maxHp: number;
}

export interface DropStateView {
  queue: DropQueueView[];
  kits: KitView[];
  selectedPadId: number | null;
  unitCount: number;
  unitCap: number;
}

export interface TestHook {
  snapshot(): WorldState;
  worldHash(): string;
  sendCommand(command: unknown): boolean;
  screen(): string;
  renderStats(): RenderStats;
  freezeSim(ms: number): void;
  pauseSim(paused: boolean): void;
  controls(): string[];
  go(screenId: string): void;
  units(): UnitView[];
  structures(): StructureView[];
  deposits(): DepositState[];
  resources(): SideStats[];
  worldToScreen(x: number, z: number): { x: number; y: number };
  lastGroundPick(): { x: number; z: number } | null;
  lastIssuedCommand(): IssuedCommand | null;
  lastFreezeReport(): WatchdogReport | null;
  lastCommandOutcome(): CommandOutcome | null;
  quality(): QualityView;
  unitScreenCentre(id: number): { x: number; y: number } | null;
  unitScreenBounds(id: number): ScreenBounds | null;
  unitIsOnScreen(id: number): boolean;
  groundPickAt(x: number, y: number): { x: number; z: number } | null;
  selection(): number[];
  setSelection(ids: number[]): void;
  camera(): CameraView;
  cameraFootprint(): Array<{ x: number; z: number }>;
  orderPaths(): Array<{ unitId: number; points: number; queued: boolean }>;
  inputState(): { longPressReady: boolean };
  hud(): HudSnapshot | null;
  buildItems(): BuildItemView[];
  dropState(): DropStateView;
  placement(): PlacementView | null;
  startPlacement(kitId: number): boolean;
  previewPlacement(x: number, z: number): void;
  confirmPlacement(): boolean;
  cancelPlacement(): void;
  alerts(): Array<{ x: number; z: number }>;
  setSimSpeed(multiplier: number): void;
  setCamera(info: Partial<CameraView>): void;
  simSpeed(): number;
  isSimPaused(): boolean;
  settings(): SettingsState;
  audioStatus(): AudioStatusView;
  listSaveSlots(): Promise<SaveSlotSummary[]>;
  requestAutosave(): Promise<void>;
  lastSaveOutcome(): SaveActionResult | null;
  lastLoadOutcome(): LoadSlotResult | null;
  lastImportOutcome(): ImportSaveResult | null;
  writeRawSave(slot: string, text: string): Promise<void>;
  lastBugReport(): { fileName: string; content: string } | null;
  raiseAlert(kind: AlertKind, x: number, z: number): void;
  alertList(): AlertSnapshot[];
  setStorageFullForTest(value: boolean): void;
  pressAndroidBack(): void;
}

export function installTestHook(app: App): void {
  const hook: TestHook = {
    snapshot: () => app.snapshot(),
    worldHash: () => app.worldHash(),
    sendCommand: (command) => app.sendCommand(command),
    screen: () => app.router.current(),
    renderStats: () => app.renderStats(),
    freezeSim: (ms) => {
      app.freezeSim(ms);
    },
    pauseSim: (paused) => {
      app.pauseSim(paused);
    },
    controls: () => ControlInventory.all(),
    go: (screenId) => {
      app.go(screenId as ScreenId);
    },
    units: () => app.units(),
    structures: () => app.structures(),
    deposits: () => app.deposits(),
    resources: () => app.resources(),
    worldToScreen: (x, z) => app.worldToScreen(x, z),
    lastGroundPick: () => app.lastGroundPick(),
    lastIssuedCommand: () => app.lastIssuedCommand(),
    lastFreezeReport: () => app.lastFreezeReport(),
    lastCommandOutcome: () => app.lastCommandOutcome(),
    quality: () => app.quality(),
    unitScreenCentre: (id) => app.unitScreenCentre(id),
    unitScreenBounds: (id) => app.unitScreenBounds(id),
    unitIsOnScreen: (id) => app.unitIsOnScreen(id),
    groundPickAt: (x, y) => app.groundPickAt(x, y),
    selection: () => app.selection(),
    setSelection: (ids) => {
      app.setSelection(ids);
    },
    camera: () => app.camera(),
    cameraFootprint: () => app.cameraFootprint(),
    orderPaths: () => app.orderPaths(),
    inputState: () => app.inputState(),
    hud: () => app.hudSnapshot(),
    buildItems: () => app.buildItems(),
    dropState: () => app.dropState(),
    placement: () => app.placement(),
    startPlacement: (kitId) => app.startPlacement(kitId),
    previewPlacement: (x, z) => {
      app.previewPlacement(x, z);
    },
    confirmPlacement: () => app.confirmPlacement(),
    cancelPlacement: () => {
      app.cancelPlacement();
    },
    alerts: () => app.alerts(),
    setSimSpeed: (multiplier) => {
      app.setSimSpeed(multiplier);
    },
    setCamera: (info) => {
      app.setCamera(info);
    },
    simSpeed: () => app.simSpeed(),
    isSimPaused: () => app.isSimPaused(),
    settings: () => app.settings(),
    audioStatus: () => app.audioStatus(),
    listSaveSlots: () => app.listSaveSlots(),
    requestAutosave: () => app.requestAutosave(),
    lastSaveOutcome: () => app.lastSaveOutcome(),
    lastLoadOutcome: () => app.lastLoadOutcome(),
    lastImportOutcome: () => app.lastImportOutcome(),
    writeRawSave: (slot, text) => app.writeRawSave(slot, text),
    lastBugReport: () => app.lastBugReport(),
    raiseAlert: (kind, x, z) => {
      app.raiseAlertForTest(kind, x, z);
    },
    alertList: () => app.alerts(),
    setStorageFullForTest: (value) => {
      app.setStorageFullForTest(value);
    },
    pressAndroidBack: () => {
      app.pressAndroidBack();
    },
  };

  (window as unknown as { __TC_TEST__?: TestHook }).__TC_TEST__ = hook;
}
