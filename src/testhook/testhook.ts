import type { App, CameraView, IssuedCommand, QualityView, UnitView } from '../app';
import { ControlInventory } from '../ui/controls';
import type { HudSnapshot, ScreenId } from '../ui/router';
import type { WorldState } from '../sim/types';
import type { WatchdogReport } from '../platform/watchdog';
import type { RenderStats, ScreenBounds } from '../render/renderer';

export interface TestHook {
  snapshot(): WorldState;
  sendCommand(command: unknown): boolean;
  screen(): string;
  renderStats(): RenderStats;
  freezeSim(ms: number): void;
  pauseSim(paused: boolean): void;
  controls(): string[];
  go(screenId: string): void;
  units(): UnitView[];
  worldToScreen(x: number, z: number): { x: number; y: number };
  lastGroundPick(): { x: number; z: number } | null;
  lastIssuedCommand(): IssuedCommand | null;
  lastFreezeReport(): WatchdogReport | null;
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
  alerts(): Array<{ x: number; z: number }>;
  setSimSpeed(multiplier: number): void;
  setCamera(info: Partial<CameraView>): void;
}

export function installTestHook(app: App): void {
  const hook: TestHook = {
    snapshot: () => app.snapshot(),
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
    worldToScreen: (x, z) => app.worldToScreen(x, z),
    lastGroundPick: () => app.lastGroundPick(),
    lastIssuedCommand: () => app.lastIssuedCommand(),
    lastFreezeReport: () => app.lastFreezeReport(),
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
    alerts: () => app.alerts(),
    setSimSpeed: (multiplier) => {
      app.setSimSpeed(multiplier);
    },
    setCamera: (info) => {
      app.setCamera(info);
    },
  };

  (window as unknown as { __TC_TEST__?: TestHook }).__TC_TEST__ = hook;
}
