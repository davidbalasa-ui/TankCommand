import rawManifest from '../public/assets/manifest.json';
import units from './data/units.placeholder.json';
import structures from './data/structures.placeholder.json';
import maps from './data/maps.placeholder.json';
import research from './data/research.placeholder.json';
import { parseAssetManifest } from './assets/manifestSchema';
import { AssetRegistry } from './assets/registry';
import {
  loadMapTable,
  loadResearchTable,
  loadStructureTable,
  loadUnitTable,
} from './data/dataRegistry';
import type { MapRow } from './data/mapSchema';
import type { StructureRow } from './data/structureSchema';
import type { UnitRow } from './data/unitSchema';
import { createScreens } from './ui/screens';
import {
  ScreenRouter,
  type BuildItemView,
  type DropQueueView,
  type HudHandle,
  type HudSnapshot,
  type KitView,
  type PlacementView,
  type RendererHandle,
  type ScreenContext,
  type ScreenId,
  type WorkerActions,
} from './ui/router';
import { InputController, type IssuedCommand } from './ui/input';
import { createWorld, snapshot, step, type CreateWorldOptions } from './sim/world';
import type {
  CommandOutcome,
  DepositState,
  PlayerId,
  ResearchNode,
  SimStructureType,
  SimUnitType,
  Stance,
  WorldState,
} from './sim/types';
import { validateCommand, type Command } from './sim/commands';
import { FixedStepLoop } from './sim/loop';
import { SIM_TICK_HZ } from './sim/constants';
import {
  DEFAULT_DISMANTLE_REFUND_PERCENT,
  DEFAULT_DISMANTLE_SEC,
  DEPOSIT_PICK_RADIUS,
  UNIT_CAP,
} from './sim/tuning';
import {
  Watchdog,
  installGlobalErrorCapture,
  type WatchdogReport,
} from './platform/watchdog';
import { bindLifecycleToBrowserAndCapacitor, type Lifecycle } from './platform/lifecycle';
import type { RenderStats, RenderView, ScreenBounds } from './render/renderer';
import { buildSkirmishSetup } from './sim/skirmishSetup';
import { placementValidity, structureAtPoint } from './sim/spawn';

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
  jobKind: string | null;
  jobStage: string | null;
  load: number;
  workerKind: string | null;
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

export interface StructureView {
  id: number;
  owner: PlayerId;
  typeId: string;
  kind: string;
  x: number;
  z: number;
  hp: number;
  maxHp: number;
}

interface PlacementState {
  kitId: number;
  structureTypeId: string;
  name: string;
  x: number;
  z: number;
  valid: boolean;
}

function buildUnitTypes(table: ReadonlyMap<string, UnitRow>): ReadonlyMap<string, SimUnitType> {
  const result = new Map<string, SimUnitType>();
  for (const row of table.values()) {
    const weapon = row.weapons[0];
    result.set(row.id, {
      id: row.id,
      faction: row.faction,
      role: row.role,
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
      oreCost: row.cost.ore,
      metalCost: row.cost.metal,
      deliverySec: row.deliverySec,
      workerKind: row.workerKind ?? null,
      miningRatePerSec: row.miningRatePerSec ?? 0,
      carryCapacity: row.carryCapacity ?? 0,
      salvageRefundPercent: row.salvageRefundPercent ?? 0,
      repair: row.repair ? { radius: row.repair.radius, ratePerSec: row.repair.ratePerSec } : null,
      deploysTo: row.deploysTo ?? null,
      deploySec: row.deploySec ?? 0,
      upgrades: [...row.upgrades],
    });
  }
  return result;
}

function buildStructureTypes(
  table: ReadonlyMap<string, StructureRow>,
): ReadonlyMap<string, SimStructureType> {
  const result = new Map<string, SimStructureType>();
  for (const row of table.values()) {
    result.set(row.id, {
      id: row.id,
      name: row.name,
      faction: row.faction,
      kind: row.kind,
      cost: { ore: row.cost.ore, metal: row.cost.metal },
      deliverySec: row.deliverySec,
      hp: row.hp,
      armor: row.armor,
      footprint: { cellsX: row.footprint.cellsX, cellsZ: row.footprint.cellsZ },
      sightRange: row.sightRange,
      modelId: row.modelId,
      buildOnMetalDeposit: row.buildOnMetalDeposit,
      metalRatePerSec: row.metalRatePerSec ?? 0,
      containerSize: row.containerSize ?? 0,
      maxContainers: row.maxContainers ?? 0,
      weapon: row.weapon ? { ...row.weapon } : null,
      turretTurnDegPerSec: row.turretTurnDegPerSec ?? 0,
      packSec: row.packSec ?? 0,
      packedUnitId: row.packedUnitId ?? null,
      dismantleSec: row.dismantleSec ?? DEFAULT_DISMANTLE_SEC,
      dismantleRefundPercent: row.dismantleRefundPercent ?? DEFAULT_DISMANTLE_REFUND_PERCENT,
      sensorRange: row.sensorRange ?? row.sightRange,
      upgrades: [...(row.upgrades ?? [])],
    });
  }
  return result;
}

export class App {
  public readonly router: ScreenRouter;
  private readonly registry: AssetRegistry;
  private readonly unitTypes: ReadonlyMap<string, SimUnitType>;
  private readonly structureTypes: ReadonlyMap<string, SimStructureType>;
  private readonly unitRows: UnitRow[];
  private readonly structureRows: StructureRow[];
  private readonly researchTree: ReadonlyMap<string, ResearchNode>;
  private readonly mapData: MapRow;
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
  private dropPadId: number | null = null;
  private placementState: PlacementState | null = null;
  private readonly controlGroups = new Map<number, number[]>();
  private hud: HudHandle | null = null;

  constructor(root: HTMLElement) {
    this.registry = new AssetRegistry(parseAssetManifest(rawManifest));
    const table = loadUnitTable(units, this.registry);
    const structureTable = loadStructureTable(structures);
    const mapTable = loadMapTable(maps);
    const map = mapTable[0];
    if (!map) {
      throw new Error('No map data available');
    }
    this.mapData = map;
    this.unitTypes = buildUnitTypes(table);
    this.structureTypes = buildStructureTypes(structureTable);
    this.unitRows = [...table.values()];
    this.structureRows = [...structureTable.values()];
    const researchTable = loadResearchTable(
      research,
      new Set([...table.keys(), ...structureTable.keys()]),
    );
    this.researchTree = new Map(
      [...researchTable.values()].map((row) => [
        row.id,
        {
          id: row.id,
          name: row.name,
          faction: row.faction,
          cost: { ore: row.cost.ore, metal: row.cost.metal },
          timeSec: row.timeSec,
          requires: [...row.requires],
          unlocks: [...row.unlocks],
          upgrades: [...row.upgrades],
        },
      ]),
    );
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
      getBuildItems: () => this.buildItems(),
      getOwnPads: () => this.ownPads(),
      getSelectedPadId: () => this.currentDropPadId(),
      setSelectedPad: (id) => {
        this.setSelectedPad(id);
      },
      buyItem: (itemId) => this.buyItem(itemId),
      getDropQueue: () => this.dropQueue(),
      cancelOrder: (orderId) => {
        this.cancelOrder(orderId);
      },
      getKits: () => this.kits(),
      startPlacement: (kitId) => this.startPlacement(kitId),
      getPlacement: () => this.placement(),
      confirmPlacement: () => this.confirmPlacement(),
      cancelPlacement: () => {
        this.cancelPlacement();
      },
      getWorkerActions: () => this.workerActions(),
      salvageSelected: () => {
        this.salvageSelected();
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
    return { ...command, tick: earliest };
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
        const targetUnit = this.world.units.find((item) => item.id === order.targetId);
        const targetStructure = this.world.structures.find((item) => item.id === order.targetId);
        if (targetUnit) {
          orderX = targetUnit.x;
          orderZ = targetUnit.z;
        } else if (targetStructure) {
          orderX = targetStructure.x;
          orderZ = targetStructure.z;
        }
      }
      const type = this.world.unitTypes.get(unit.typeId);
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
        jobKind: unit.job?.kind ?? null,
        jobStage: unit.job?.stage ?? null,
        load: unit.job?.load ?? 0,
        workerKind: type?.workerKind ?? null,
      };
    });
  }

  structures(): StructureView[] {
    return this.world.structures.map((structure) => {
      const type = this.world.structureTypes.get(structure.typeId);
      return {
        id: structure.id,
        owner: structure.owner,
        typeId: structure.typeId,
        kind: type?.kind ?? 'pad',
        x: structure.x,
        z: structure.z,
        hp: structure.hp,
        maxHp: type?.hp ?? Math.max(1, structure.hp),
      };
    });
  }

  deposits(): DepositState[] {
    return this.world.deposits.map((deposit) => ({ ...deposit }));
  }

  resources(): Array<{
    player: PlayerId;
    ore: number;
    metal: number;
    oreGathered: number;
    metalGathered: number;
    unitsBuilt: number;
    unitsLost: number;
  }> {
    return this.world.resources.map((stats) => ({ ...stats }));
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

  lastCommandOutcome(): CommandOutcome | null {
    return this.world.lastCommandOutcome;
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
    return this.world.alerts.map((alert) => ({ x: alert.x, z: alert.z }));
  }

  buildItems(): BuildItemView[] {
    const faction = this.factionFor(1);
    const pads = this.ownPads();
    const stats = this.sideStats(1);
    const ownUnits = this.world.units.filter((unit) => unit.owner === 1 && unit.hp > 0).length;
    const queuedUnits = this.world.dropQueue.filter(
      (order) => order.owner === 1 && order.itemKind === 'unit',
    ).length;
    const disabled = (kind: 'unit' | 'structure', ore: number, metal: number): string | null => {
      if (pads.length === 0) {
        return 'No landing pad';
      }
      if (kind === 'unit' && ownUnits + queuedUnits >= UNIT_CAP) {
        return 'Unit cap reached';
      }
      if (!stats || stats.ore < ore || stats.metal < metal) {
        return 'Cannot afford';
      }
      return null;
    };
    const items: BuildItemView[] = [];
    for (const row of this.unitRows) {
      if (row.faction !== faction) {
        continue;
      }
      items.push({
        id: row.id,
        name: row.name,
        kind: 'unit',
        ore: row.cost.ore,
        metal: row.cost.metal,
        deliverySec: row.deliverySec,
        disabledReason: disabled('unit', row.cost.ore, row.cost.metal),
      });
    }
    for (const row of this.structureRows) {
      if (row.faction !== faction) {
        continue;
      }
      items.push({
        id: row.id,
        name: row.name,
        kind: 'structure',
        ore: row.cost.ore,
        metal: row.cost.metal,
        deliverySec: row.deliverySec,
        disabledReason: disabled('structure', row.cost.ore, row.cost.metal),
      });
    }
    return items;
  }

  dropQueue(): DropQueueView[] {
    return this.world.dropQueue
      .filter((order) => order.owner === 1)
      .sort((a, b) => a.id - b.id)
      .map((order) => ({
        id: order.id,
        itemId: order.itemId,
        name: this.itemName(order.itemId),
        remainingSec: order.remainingSec,
        totalSec: order.totalSec,
        progress: order.totalSec > 0 ? 1 - order.remainingSec / order.totalSec : 1,
      }));
  }

  dropState(): {
    queue: DropQueueView[];
    kits: KitView[];
    selectedPadId: number | null;
    unitCount: number;
    unitCap: number;
  } {
    return {
      queue: this.dropQueue(),
      kits: this.kits(),
      selectedPadId: this.currentDropPadId(),
      unitCount: this.world.units.filter((unit) => unit.owner === 1 && unit.hp > 0).length,
      unitCap: UNIT_CAP,
    };
  }

  kits(): KitView[] {
    return this.world.pendingKits
      .filter((kit) => kit.owner === 1)
      .map((kit) => ({
        id: kit.id,
        structureTypeId: kit.structureTypeId,
        name: this.world.structureTypes.get(kit.structureTypeId)?.name ?? kit.structureTypeId,
      }));
  }

  ownPads(): Array<{ id: number; x: number; z: number }> {
    return this.world.structures
      .filter((structure) => {
        if (structure.owner !== 1 || structure.hp <= 0) {
          return false;
        }
        return this.world.structureTypes.get(structure.typeId)?.kind === 'pad';
      })
      .map((structure) => ({ id: structure.id, x: structure.x, z: structure.z }));
  }

  setSelectedPad(id: number): void {
    if (this.ownPads().some((pad) => pad.id === id)) {
      this.dropPadId = id;
      this.hud?.refresh();
    }
  }

  currentDropPadId(): number | null {
    const pads = this.ownPads();
    if (this.dropPadId !== null && pads.some((pad) => pad.id === this.dropPadId)) {
      return this.dropPadId;
    }
    return pads[0]?.id ?? null;
  }

  buyItem(itemId: string): boolean {
    const padId = this.currentDropPadId();
    if (padId === null) {
      return false;
    }
    const ok = this.sendCommand({
      kind: 'buy',
      itemId,
      padId,
      tick: this.world.tick + 1,
      issuer: 1,
    });
    if (ok) {
      this.dropPadId = padId;
    }
    return ok;
  }

  cancelOrder(orderId: number): void {
    this.sendCommand({
      kind: 'cancel',
      orderId,
      tick: this.world.tick + 1,
      issuer: 1,
    });
  }

  startPlacement(kitId: number): boolean {
    const kit = this.world.pendingKits.find((item) => item.id === kitId && item.owner === 1);
    if (!kit) {
      return false;
    }
    const type = this.world.structureTypes.get(kit.structureTypeId);
    if (!type) {
      return false;
    }
    const pad = this.ownPads()[0];
    const x = pad ? pad.x + 8 : 0;
    const z = pad ? pad.z - 8 : 0;
    this.placementState = {
      kitId,
      structureTypeId: type.id,
      name: type.name,
      x,
      z,
      valid: false,
    };
    this.previewPlacement(x, z);
    this.hud?.refresh();
    return true;
  }

  previewPlacement(x: number, z: number): void {
    const placement = this.placementState;
    if (!placement) {
      return;
    }
    const type = this.world.structureTypes.get(placement.structureTypeId);
    if (!type) {
      return;
    }
    const validity = placementValidity(this.world, 1, type, x, z);
    let px = x;
    let pz = z;
    if (validity.valid && type.buildOnMetalDeposit && validity.depositId !== null) {
      const deposit = this.world.deposits.find((item) => item.id === validity.depositId);
      if (deposit) {
        px = deposit.x;
        pz = deposit.z;
      }
    }
    this.placementState = { ...placement, x: px, z: pz, valid: validity.valid };
    this.renderView?.showPlacement(type.id, px, pz, validity.valid);
  }

  confirmPlacement(): boolean {
    const placement = this.placementState;
    if (!placement || !placement.valid) {
      return false;
    }
    const ok = this.sendCommand({
      kind: 'placeKit',
      kitId: placement.kitId,
      x: placement.x,
      z: placement.z,
      tick: this.world.tick + 1,
      issuer: 1,
    });
    if (ok) {
      this.cancelPlacement();
    }
    return ok;
  }

  cancelPlacement(): void {
    this.placementState = null;
    this.renderView?.clearPlacement();
    this.hud?.refresh();
  }

  placement(): PlacementView | null {
    if (!this.placementState) {
      return null;
    }
    return { ...this.placementState };
  }

  workerActions(): WorkerActions {
    let canMine = false;
    let canAssign = false;
    let canSalvage = false;
    for (const id of this.selectedIds) {
      const unit = this.world.units.find((item) => item.id === id);
      if (!unit) {
        continue;
      }
      const type = this.world.unitTypes.get(unit.typeId);
      if (type?.workerKind === 'oreMiner') {
        canMine = true;
      }
      if (type?.workerKind === 'tug') {
        canAssign = true;
      }
      if (type && type.workerKind && type.salvageRefundPercent > 0) {
        canSalvage = true;
      }
    }
    return { canMine, canAssign, canSalvage };
  }

  mineAt(depositId: number): boolean {
    const ids = this.selectedIds.filter((id) => {
      const unit = this.world.units.find((item) => item.id === id);
      const type = unit ? this.world.unitTypes.get(unit.typeId) : undefined;
      return type?.workerKind === 'oreMiner';
    });
    if (ids.length === 0) {
      return false;
    }
    return this.sendCommand({
      kind: 'mine',
      unitIds: ids,
      depositId,
      tick: this.world.tick + 1,
      issuer: 1,
    });
  }

  assignAt(stationId: number): boolean {
    const ids = this.selectedIds.filter((id) => {
      const unit = this.world.units.find((item) => item.id === id);
      const type = unit ? this.world.unitTypes.get(unit.typeId) : undefined;
      return type?.workerKind === 'tug';
    });
    if (ids.length === 0) {
      return false;
    }
    return this.sendCommand({
      kind: 'assign',
      unitIds: ids,
      stationId,
      tick: this.world.tick + 1,
      issuer: 1,
    });
  }

  attackStructure(structureId: number): boolean {
    if (this.selectedIds.length === 0) {
      return false;
    }
    return this.sendCommand({
      kind: 'attack',
      unitIds: this.selectedIds,
      targetId: structureId,
      tick: this.world.tick + 1,
      issuer: 1,
    });
  }

  salvageSelected(): void {
    const ids = this.selectedIds.filter((id) => {
      const unit = this.world.units.find((item) => item.id === id);
      const type = unit ? this.world.unitTypes.get(unit.typeId) : undefined;
      return type !== undefined && type.workerKind !== null && type.salvageRefundPercent > 0;
    });
    if (ids.length === 0) {
      return;
    }
    this.sendCommand({
      kind: 'salvage',
      unitIds: ids,
      tick: this.world.tick + 1,
      issuer: 1,
    });
  }

  depositAt(x: number, z: number): { id: number; kind: 'ore' | 'metal' } | null {
    for (const deposit of this.world.deposits) {
      if (Math.hypot(deposit.x - x, deposit.z - z) <= DEPOSIT_PICK_RADIUS) {
        return { id: deposit.id, kind: deposit.kind };
      }
    }
    return null;
  }

  structureAt(x: number, z: number): { id: number; owner: PlayerId; kind: string } | null {
    const structure = structureAtPoint(this.world, x, z);
    if (!structure) {
      return null;
    }
    const type = this.world.structureTypes.get(structure.typeId);
    return { id: structure.id, owner: structure.owner, kind: type?.kind ?? 'pad' };
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

  private itemName(itemId: string): string {
    // Units only carry their id on `SimUnitType`, so the display name comes from
    // the raw data sheet. Structure types carry their own name. The previous
    // implementation used `unitTypes.get(id)?.id`, which returned the raw id
    // (e.g. `unit.human.scout`) for any unit entry, so the queue row showed the
    // internal id instead of the friendly "Scout".
    return (
      this.unitRows.find((row) => row.id === itemId)?.name ??
      this.world.structureTypes.get(itemId)?.name ??
      itemId
    );
  }

  private factionFor(player: PlayerId): 'human' | 'alien' {
    return (
      this.world.factions.find((entry) => entry.player === player)?.faction ??
      (player === 1 ? 'human' : 'alien')
    );
  }

  private sideStats(player: PlayerId) {
    return this.world.resources.find((stats) => stats.player === player);
  }

  private newSkirmish(): WorldState {
    const setup = buildSkirmishSetup(
      this.unitTypes,
      this.structureTypes,
      {
        size: this.mapData.size,
        cellSize: this.mapData.cellSize,
        starts: this.mapData.starts,
        deposits: this.mapData.deposits,
      },
      [
        { player: 1, faction: 'human' },
        { player: 2, faction: 'alien' },
      ],
    );
    const options: CreateWorldOptions = {
      unitTypes: this.unitTypes,
      structureTypes: this.structureTypes,
      researchTree: this.researchTree,
      startUnits: setup.startUnits,
      startStructures: setup.startStructures,
      deposits: setup.deposits,
      factions: setup.factions,
      startResources: setup.resources,
      size: setup.size,
      cellSize: setup.cellSize,
    };
    const world = createWorld(this.nextSeed, options);
    this.nextSeed += 1;
    this.dropPadId = null;
    this.placementState = null;
    return world;
  }

  private startSkirmish(): void {
    this.world = this.newSkirmish();
    this.pendingCommands = [];
    this.selectedIds = [];
    this.fixed.reset();
    this.lastFreeze = null;
    this.renderView?.clearPlacement();
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
          getDepositAt: (x, z) => this.depositAt(x, z),
          getStructureAt: (x, z) => this.structureAt(x, z),
          onMineOrder: (depositId) => this.mineAt(depositId),
          onAssignOrder: (stationId) => this.assignAt(stationId),
          onAttackStructure: (structureId) => this.attackStructure(structureId),
          isPlacementActive: () => this.placementState !== null,
          previewPlacement: (x, z) => {
            this.previewPlacement(x, z);
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
    if (this.placementState && !this.world.pendingKits.some((kit) => kit.id === this.placementState?.kitId)) {
      this.placementState = null;
      this.renderView?.clearPlacement();
    }
  }
}

export function createApp(root: HTMLElement): App {
  return new App(root);
}
