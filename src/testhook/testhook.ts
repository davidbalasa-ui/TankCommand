import type { App, CameraView, UnitView } from '../app';
import { ControlInventory } from '../ui/controls';
import type { ScreenId } from '../ui/router';
import type { WorldState } from '../sim/types';
import type { RenderStats } from '../render/renderer';

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
  unitScreenCentre(id: number): { x: number; y: number } | null;
  selection(): number[];
  camera(): CameraView;
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
    unitScreenCentre: (id) => app.unitScreenCentre(id),
    selection: () => app.selection(),
    camera: () => app.camera(),
    setSimSpeed: (multiplier) => {
      app.setSimSpeed(multiplier);
    },
    setCamera: (info) => {
      app.setCamera(info);
    },
  };

  (window as unknown as { __TC_TEST__?: TestHook }).__TC_TEST__ = hook;
}
