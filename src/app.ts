import rawManifest from '../public/assets/manifest.json';
import units from './data/units.placeholder.json';
import { parseAssetManifest } from './assets/manifestSchema';
import { AssetRegistry } from './assets/registry';
import { loadUnitTable } from './data/dataRegistry';
import type { UnitRow } from './data/unitSchema';
import { createScreens } from './ui/screens';
import {
  ScreenRouter,
  type HudHandle,
  type HudSnapshot,
  type RendererHandle,
  type ScreenContext,
  type ScreenId,
} from './ui/router';
import { InputController, type IssuedCommand } from './ui/input';
import { createWorld, snapshot, step, type CreateWorldOptions } from './sim/world';
import type { PlayerId, SimUnitType, Stance, WorldState } from './sim/types';
import { validateCommand, type Command } from './sim/commands';
import { FixedStepLoop } from './sim/loop';
import { SIM_TICK_HZ } from './sim/constants';
import {
  Watchdog,
  installGlobalErrorCapture,
  type WatchdogReport,
} from './platform/watchdog';
import { bindLifecycleToBrowserAndCapacitor, type Lifecycle } from './platform/lifecycle';
import type { RenderStats, RenderView, ScreenBounds } from './render/renderer';

export type { IssuedCommand } from './ui/input';

export interface UnitView {
  id: number;
  owner: PlayerId;
  typeId: string;
  x: number;
  z: number;
  hp: number;
  selected: boolean;
  stance: Stance;
  orderKind: string;
  pathPoints: number;
  queued: boolean;
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

export interface QualityView {
  level: number;
  pixelRatio: number;
  shadows: boolean;
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
  private lastFreeze: WatchdogReport | null = null;
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
  private queueModeValue = false;
  private attackMoveArmedValue = false;
  private leftHandedValue = false;
  private readonly controlGroups = new Map<number, number[]>();
  private hud: HudHandle | null = null;

  constructor(root: HTMLElement) {
    this.registry = new AssetRegistry(parseAssetManifest(rawManifest));
    const table = loadUnitTable(units, this.registry);
    this.unitTypes = buildUnitTypes(table);
    this.world = this.newSkirmish();
    try {
      this.leftHandedValue = window.localStorage.getItem('setting.leftHanded') === 'true';
    } catch {
      this.leftHandedValue = false;
    }
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
      onFreeze: (report) => {
        this.lastFreeze = report;
      },
      onRecover: () => {
        this.router.go('recovery');
      },
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
      sendCommand: (command) => this.sendCommand(command),
      getCamera: () => this.camera(),
      cameraFootprint: () => this.cameraFootprint(),
      setCameraTarget: (x, z) => {
        this.setCamera({ targetX: x, targetZ: z });
      },
      isLeftHanded: () => this.leftHandedValue,
      setLeftHanded: (value) => {
        this.setLeftHanded(value);
      },
      isQueueMode: () => this.queueModeValue,
      setQueueMode: (value) => {
        this.queueModeValue = value;
      },
      isAttackMoveArmed: () => this.attackMoveArmedValue,
      setAttackMoveArmed: (value) => {
        this.attackMoveArmedValue = value;
      },
      assignGroup: (group) => {
        this.assignGroup(group);
      },
      selectGroup: (group) => {
        this.selectGroup(group);
      },
      centerGroup: (group) => {
        this.centerGroup(group);
      },
      groupMembers: (group) => this.groupMembers(group),
      registerHud: (hud) => {
        this.hud = hud;
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
    if ((stamped.kind === 'move' || stamped.kind === 'attackMove') && this.renderView) {
      this.renderView.pulseMarker(stamped.x, stamped.z);
    }
    return true;
  }

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
      case 'attackMove':
        return { ...command, tick: earliest };
      case 'attack':
        return { ...command, tick: earliest };
      case 'hold':
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
      if (order.kind === 'move' || order.kind === 'attackMove') {
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
        typeId: unit.typeId,
        x: unit.x,
        z: unit.z,
        hp: unit.hp,
        selected: this.selectedIds.includes(unit.id),
        stance: unit.stance,
        orderKind: order.kind,
        pathPoints: unit.path.length,
        queued:
          (order.kind === 'move' || order.kind === 'attackMove') && order.queue,
        orderX,
        orderZ,
      };
    });
  }

  selection(): number[] {
    return [...this.selectedIds];
  }

  lastGroundPick(): { x: number; z: number } | null {
    return this.input?.getLastGroundPick() ?? null;
  }

  lastIssuedCommand(): IssuedCommand | null {
    return this.input?.getLastIssuedCommand() ?? null;
  }

  lastFreezeReport(): WatchdogReport | null {
    return this.lastFreeze;
  }

  quality(): QualityView {
    return this.renderView?.quality() ?? { level: 0, pixelRatio: 1, shadows: false };
  }

  unitScreenCentre(id: number): { x: number; y: number } | null {
    return this.renderView?.unitScreenCentre(id) ?? null;
  }

  unitScreenBounds(id: number): ScreenBounds | null {
    return this.renderView?.unitScreenBounds(id) ?? null;
  }

  unitIsOnScreen(id: number): boolean {
    return this.renderView?.unitIsOnScreen(id) ?? false;
  }

  groundPickAt(x: number, y: number): { x: number; z: number } | null {
    return this.renderView?.pickGround(x, y) ?? null;
  }

  setSelection(ids: number[]): void {
    const valid = new Set(
      this.world.units.filter((unit) => unit.owner === 1).map((unit) => unit.id),
    );
    this.selectedIds = [...new Set(ids)].filter((id) => valid.has(id));
    // The command bar's disabled state must follow the selection immediately
    // rather than on the 200 ms minimap tick, otherwise the HUD tests would
    // observe stale disabled flags right after the selection changed.
    this.hud?.refresh();
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

  cameraFootprint(): Array<{ x: number; z: number }> {
    return this.renderView?.cameraFootprint() ?? [];
  }

  orderPaths(): Array<{ unitId: number; points: number; queued: boolean }> {
    return this.renderView?.orderPaths() ?? [];
  }

  inputState(): { longPressReady: boolean } {
    return { longPressReady: this.input?.isLongPressReady() ?? false };
  }

  hudSnapshot(): HudSnapshot | null {
    return this.hud?.snapshot() ?? null;
  }

  alerts(): Array<{ x: number; z: number }> {
    return [];
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

  setQueueMode(value: boolean): void {
    this.queueModeValue = value;
    this.hud?.refresh();
  }

  queueMode(): boolean {
    return this.queueModeValue;
  }

  setAttackMoveArmed(value: boolean): void {
    this.attackMoveArmedValue = value;
    this.hud?.refresh();
  }

  attackMoveArmed(): boolean {
    return this.attackMoveArmedValue;
  }

  setLeftHanded(value: boolean): void {
    this.leftHandedValue = value;
    try {
      window.localStorage.setItem('setting.leftHanded', value ? 'true' : 'false');
    } catch {
      // Storage can be unavailable; the setting still applies for this session.
    }
    this.hud?.refresh();
  }

  leftHanded(): boolean {
    return this.leftHandedValue;
  }

  assignGroup(group: number): void {
    if (group < 1 || group > 9) {
      return;
    }
    this.controlGroups.set(group, [...this.selectedIds]);
  }

  selectGroup(group: number): void {
    const ids = this.controlGroups.get(group);
    if (ids) {
      this.setSelection(ids);
    }
  }

  centerGroup(group: number): void {
    this.selectGroup(group);
    this.centerSelection();
  }

  groupMembers(group: number): number[] {
    return [...(this.controlGroups.get(group) ?? [])];
  }

  centerSelection(): void {
    const selected = this.world.units.filter((unit) => this.selectedIds.includes(unit.id));
    if (selected.length === 0) {
      return;
    }
    const x = selected.reduce((sum, unit) => sum + unit.x, 0) / selected.length;
    const z = selected.reduce((sum, unit) => sum + unit.z, 0) / selected.length;
    this.setCamera({ targetX: x, targetZ: z });
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
    this.lastFreeze = null;
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
          getQueueMode: () => this.queueModeValue,
          getAttackMoveArmed: () => this.attackMoveArmedValue,
          clearAttackMove: () => {
            this.attackMoveArmedValue = false;
          },
          setAttackMoveArmed: (value) => {
            this.attackMoveArmedValue = value;
          },
          assignGroup: (group) => {
            this.assignGroup(group);
          },
          selectGroup: (group) => {
            this.selectGroup(group);
          },
          centerGroup: (group) => {
            this.centerGroup(group);
          },
          jumpToLatestAlert: () => {
            const latest = this.alerts().at(-1);
            if (latest) {
              this.setCamera({ targetX: latest.x, targetZ: latest.z });
            }
          },
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

    this.watchdog.beat('render');

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
