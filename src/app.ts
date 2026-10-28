import rawManifest from '../public/assets/manifest.json';
import units from './data/units.placeholder.json';
import { parseAssetManifest } from './assets/manifestSchema';
import { AssetRegistry } from './assets/registry';
import { loadUnitTable } from './data/dataRegistry';
import type { UnitRow } from './data/unitSchema';
import { createScreens } from './ui/screens';
import { ScreenRouter, type RendererHandle, type ScreenContext, type ScreenId } from './ui/router';
import { InputController, type IssuedCommand } from './ui/input';
import { createWorld, snapshot, step, type CreateWorldOptions } from './sim/world';
import type { PlayerId, SimUnitType, WorldState } from './sim/types';
import { validateCommand, type Command } from './sim/commands';
import { FixedStepLoop } from './sim/loop';
import { SIM_TICK_HZ } from './sim/constants';
import { Watchdog, installGlobalErrorCapture } from './platform/watchdog';
import { bindLifecycleToBrowserAndCapacitor, type Lifecycle } from './platform/lifecycle';
import type { RenderStats, RenderView, ScreenBounds } from './render/renderer';

export type { IssuedCommand } from './ui/input';

export interface UnitView {
  id: number;
  owner: PlayerId;
  x: number;
  z: number;
  hp: number;
  selected: boolean;
  orderX: number | null;
  orderZ: number | null;
}

export interface CameraView {
  targetX: number;
  targetZ: number;
  distance: number;
  yaw: number;
  pitch: number;
}

function buildUnitTypes(table: ReadonlyMap<string, UnitRow>): ReadonlyMap<string, SimUnitType> {
  const result = new Map<string, SimUnitType>();
  for (const row of table.values()) {
    const weapon = row.weapons[0];
    result.set(row.id, {
      id: row.id,
      hp: row.hp,
      armor: row.armor,
      topSpeed: row.speed.top,
      accel: row.speed.accel,
      turnDegPerSec: row.speed.turnDegPerSec,
      turretTurnDegPerSec: row.turretTurnDegPerSec,
      fireOnMove: row.fireOnMove,
      sightRange: row.sightRange,
      weapon: weapon
        ? {
            damage: weapon.damage,
            range: weapon.range,
            reloadSec: weapon.reloadSec,
            projectileSpeed: weapon.projectileSpeed,
            accuracy: weapon.accuracy,
            splashRadius: weapon.splashRadius,
          }
        : null,
    });
  }
  return result;
}

export class App {
  public readonly router: ScreenRouter;
  private readonly registry: AssetRegistry;
  private readonly unitTypes: ReadonlyMap<string, SimUnitType>;
  private world: WorldState;
  private pendingCommands: Command[] = [];
  private readonly fixed: FixedStepLoop;
  private readonly watchdog: Watchdog;
  private lifecycle: Lifecycle | null = null;
  private renderView: RenderView | null = null;
  private input: InputController | null = null;
  private raf = 0;
  private checkTimer = 0;
  private lastFrame = 0;
  private paused = false;
  private uiPaused = false;
  private lifecyclePaused = false;
  private freezeSimUntil = 0;
  private selectedIds: number[] = [];
  private simSpeed = 1;
  private nextSeed = 1;

  constructor(root: HTMLElement) {
    this.registry = new AssetRegistry(parseAssetManifest(rawManifest));
    const table = loadUnitTable(units, this.registry);
    this.unitTypes = buildUnitTypes(table);
    this.world = this.newSkirmish();
    this.fixed = new FixedStepLoop({
      tickHz: SIM_TICK_HZ,
      maxStepsPerFrame: 20,
      step: () => {
        this.stepSimulation();
      },
    });
    this.watchdog = new Watchdog({
      now: () => performance.now(),
      freezeMs: 2000,
      recoverMs: 5000,
      onFreeze: () => {
        this.router.go('recovery');
      },
      onRecover: () => undefined,
    });

    this.router = new ScreenRouter(root, createScreens(), (router): ScreenContext => ({
      router,
      go: (id) => {
        this.go(id);
      },
      pauseSim: (paused) => {
        this.pauseSim(paused);
      },
      attachRenderer: (canvas) => this.attachRenderer(canvas),
      getWorld: () => this.snapshot(),
      selection: () => this.selection(),
      setSelection: (ids) => {
        this.setSelection(ids);
      },
      issueStop: () => {
        this.stopSelected();
      },
      deselect: () => {
        this.setSelection([]);
      },
    }));
  }

  start(): void {
    this.router.start('title');
    this.lifecycle = bindLifecycleToBrowserAndCapacitor();
    this.lifecycle.on('pause', () => {
      this.pauseLifecycle();
    });
    this.lifecycle.on('resume', () => {
      this.resumeLifecycle();
    });
    this.lifecycle.on('back', () => {
      this.router.back();
    });
    window.addEventListener('keydown', this.onKeyDown);
    installGlobalErrorCapture(window, (error) => {
      console.error(error.message);
    });
  }

  go(id: ScreenId): void {
    if (id === 'loading') {
      this.startSkirmish();
    }
    this.router.go(id);
  }

  snapshot(): WorldState {
    return { ...snapshot(this.world) };
  }

  sendCommand(command: unknown): boolean {
    const validated = validateCommand(command);
    if (!validated) {
      return false;
    }
    const stamped = this.stampCommand(validated);
    this.pendingCommands.push(stamped);
    if (stamped.kind === 'move' && this.renderView) {
      this.renderView.pulseMarker(stamped.x, stamped.z);
    }
    return true;
  }

  /**
   * Commands are addressed to a tick, and the input layer computes that tick
   * from the world it can see. Between the pointer event and the next fixed step
   * the simulation may already have advanced — a slow frame runs several steps
   * at once — so the command used to address a tick in the past, where
   * `stepSimulation` discards it without a trace. That is why a right-click
   * could appear to do nothing at all. Re-anchor anything stale to the next tick
   * that will actually be stepped, so a player's click always takes effect.
   */
  private stampCommand(command: Command): Command {
    const earliest = this.world.tick + 1;
    if (command.tick >= earliest) {
      return command;
    }
    switch (command.kind) {
      case 'noop':
        return { ...command, tick: earliest };
      case 'debug.addCounter':
        return { ...command, tick: earliest };
      case 'move':
        return { ...command, tick: earliest };
      case 'attack':
        return { ...command, tick: earliest };
      case 'stop':
        return { ...command, tick: earliest };
    }
  }

  units(): UnitView[] {
    return this.world.units.map((unit) => {
      let orderX: number | null = null;
      let orderZ: number | null = null;
      const order = unit.order;
      if (order.kind === 'move') {
        orderX = order.x;
        orderZ = order.z;
      } else if (order.kind === 'attack') {
        const targetId = order.targetId;
        const target = this.world.units.find((item) => item.id === targetId);
        if (target) {
          orderX = target.x;
          orderZ = target.z;
        }
      }
      return {
        id: unit.id,
        owner: unit.owner,
        x: unit.x,
        z: unit.z,
        hp: unit.hp,
        selected: this.selectedIds.includes(unit.id),
        orderX,
        orderZ,
      };
    });
  }

  selection(): number[] {
    return [...this.selectedIds];
  }

  /**
   * Ground point the input layer resolved for the most recent click or tap, or
   * null before the first one. Read-only view of what picking produced.
   */
  lastGroundPick(): { x: number; z: number } | null {
    return this.input?.getLastGroundPick() ?? null;
  }

  /** The most recent command the input layer issued, or null before any. */
  lastIssuedCommand(): IssuedCommand | null {
    return this.input?.getLastIssuedCommand() ?? null;
  }

  /** Canvas-space projection of a unit's picking centre (matches `pickUnit`). */
  unitScreenCentre(id: number): { x: number; y: number } | null {
    return this.renderView?.unitScreenCentre(id) ?? null;
  }

  /** Canvas-space bounding box of a unit's rendered model. */
  unitScreenBounds(id: number): ScreenBounds | null {
    return this.renderView?.unitScreenBounds(id) ?? null;
  }

  setSelection(ids: number[]): void {
    const valid = new Set(
      this.world.units.filter((unit) => unit.owner === 1).map((unit) => unit.id),
    );
    this.selectedIds = [...new Set(ids)].filter((id) => valid.has(id));
  }

  worldToScreen(x: number, z: number): { x: number; y: number } {
    return this.renderView?.worldToScreen(x, z) ?? { x: 0, y: 0 };
  }

  camera(): CameraView {
    const info = this.renderView?.cameraInfo();
    if (info) {
      return {
        targetX: info.targetX,
        targetZ: info.targetZ,
        distance: info.distance,
        yaw: info.yaw,
        pitch: info.pitch,
      };
    }
    return { targetX: 0, targetZ: 0, distance: 60, yaw: 0, pitch: 0 };
  }

  setSimSpeed(multiplier: number): void {
    this.simSpeed = Math.min(8, Math.max(1, multiplier));
  }

  setCamera(info: Partial<CameraView>): void {
    this.renderView?.setCamera(info);
  }

  setEdgeScroll(enabled: boolean): void {
    this.input?.setEdgeScroll(enabled);
  }

  renderStats(): RenderStats {
    if (!this.renderView) {
      return { loadedModels: [], meshCount: 0, drawCalls: 0, frame: 0, units: 0 };
    }
    return this.renderView.stats();
  }

  freezeSim(ms: number): void {
    this.freezeSimUntil = performance.now() + Math.max(0, ms);
  }

  pauseSim(paused: boolean): void {
    this.uiPaused = paused;
    this.applyPauseState();
  }

  private newSkirmish(): WorldState {
    const options: CreateWorldOptions = { unitTypes: this.unitTypes };
    const world = createWorld(this.nextSeed, options);
    this.nextSeed += 1;
    return world;
  }

  private startSkirmish(): void {
    this.world = this.newSkirmish();
    this.pendingCommands = [];
    this.selectedIds = [];
    this.fixed.reset();
  }

  private stopSelected(): void {
    if (this.selectedIds.length === 0) {
      return;
    }
    this.sendCommand({
      kind: 'stop',
      unitIds: [...this.selectedIds],
      tick: this.world.tick + 1,
      issuer: 1,
    });
  }

  private attachRenderer(canvas: HTMLCanvasElement): Promise<RendererHandle> {
    return import('./render/renderer').then(
      (mod) => {
        const view = new mod.RenderView(canvas, this.registry, this.world);
        this.renderView = view;
        this.input = new InputController({
          canvas,
          renderView: view,
          getWorld: () => this.world,
          getSelection: () => this.selectedIds,
          setSelection: (ids) => {
            this.setSelection(ids);
          },
          sendCommand: (command) => this.sendCommand(command),
        });
        this.startLoop();
        return {
          error: null,
          dispose: (): void => {
            if (this.renderView === view) {
              this.stopLoop();
              this.input?.dispose();
              this.input = null;
              view.dispose();
              this.renderView = null;
            }
          },
        };
      },
      () => ({
        error: '3D rendering is unavailable on this device.',
        dispose: (): void => undefined,
      }),
    );
  }

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (event.key === 'Escape') {
      this.router.back();
    }
  };

  private pauseLifecycle(): void {
    this.lifecyclePaused = true;
    this.applyPauseState();
  }

  private resumeLifecycle(): void {
    this.lifecyclePaused = false;
    this.applyPauseState();
  }

  private applyPauseState(): void {
    const next = this.uiPaused || this.lifecyclePaused;
    if (next === this.paused) {
      return;
    }
    this.paused = next;
    if (next) {
      this.watchdog.setSuspended(true);
      this.stopLoop();
    } else {
      this.watchdog.setSuspended(false);
      this.startLoop();
    }
  }

  private startLoop(): void {
    if (this.raf !== 0 || !this.renderView || this.paused) {
      return;
    }
    this.lastFrame = performance.now();
    this.watchdog.beat('sim');
    this.watchdog.beat('render');
    this.checkTimer = window.setInterval(() => {
      this.watchdog.check();
    }, 250);
    this.raf = window.requestAnimationFrame(this.frame);
  }

  private stopLoop(): void {
    if (this.raf !== 0) {
      window.cancelAnimationFrame(this.raf);
      this.raf = 0;
    }
    if (this.checkTimer !== 0) {
      window.clearInterval(this.checkTimer);
      this.checkTimer = 0;
    }
  }

  private readonly frame = (now: number): void => {
    this.raf = 0;
    if (this.paused || !this.renderView) {
      return;
    }

    const elapsed = now - this.lastFrame;
    this.lastFrame = now;
    const frozen = now < this.freezeSimUntil;
    let alpha = 0;

    if (!frozen) {
      const result = this.fixed.advance(elapsed * this.simSpeed);
      alpha = result.alpha;
      if (result.steps > 0) {
        this.watchdog.beat('sim');
      }
    }

    this.input?.update(elapsed);
    this.pruneSelection();
    this.watchdog.beat('render');
    this.watchdog.check();
    this.renderView.setSelection(this.selectedIds);
    this.renderView.render(alpha, this.world);
    this.raf = window.requestAnimationFrame(this.frame);
  };

  private pruneSelection(): void {
    this.selectedIds = this.selectedIds.filter((id) =>
      this.world.units.some((unit) => unit.id === id && unit.owner === 1),
    );
  }

  private stepSimulation(): void {
    const nextTick = this.world.tick + 1;
    const due = this.pendingCommands.filter((command) => command.tick === nextTick);
    this.world = step(this.world, due);
    this.pendingCommands = this.pendingCommands.filter((command) => command.tick > nextTick);
    this.pruneSelection();
  }
}

export function createApp(root: HTMLElement): App {
  return new App(root);
}
