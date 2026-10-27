import type { App } from '../app';
import { ControlInventory } from '../ui/controls';
import type { ScreenId } from '../ui/router';
import type { WorldState } from '../sim/world';
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
      app.router.go(screenId as ScreenId);
    },
  };

  (window as unknown as { __TC_TEST__?: TestHook }).__TC_TEST__ = hook;
}
