import rawManifest from '../public/assets/manifest.json';
import { parseAssetManifest } from './assets/manifestSchema';
import { AssetRegistry } from './assets/registry';
import { createSkirmishWorld, loadSimData, type SimData } from './data/simData';
import { MISSIONS, buildMissionWorld, missionsOf, nextMission } from './data/missions';
import { createKvStore, type KvStore } from './platform/kv';
import {
  emptyProgress,
  loadProgress,
  missionStatus,
  recordWin,
  saveProgress,
  type CampaignProgress,
} from './platform/progress';
import type { MapRow } from './data/mapSchema';
import type { StructureRow } from './data/structureSchema';
import type { UnitRow } from './data/unitSchema';
import { createScreens } from './ui/screens';
import {
  ScreenRouter,
  type BuildItemView,
  type BriefingView,
  type CampaignId,
  type MissionListItem,
  type ObjectiveView,
  type ResultView,
  type SkirmishConfig,
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
import { snapshot } from './sim/world';
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
import { placementValidity, structureAtPoint } from './sim/spawn';
import { isItemUnlocked, researchDone, researchRejection, unlockingNode } from './sim/research';
import { upgradeRejection } from './sim/upgrades';
import { UPGRADE_COST_METAL, UPGRADE_COST_ORE } from './sim/tuning';
import { perceivedUnits } from './sim/vision';
import { stepWithAi } from './ai/driver';
import type { StructureState } from './sim/types';
import type { BaseAction, BaseView } from './ui/basePanel';
import type { UpgradeKind } from './sim/types';

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

export class App {
  public readonly router: ScreenRouter;
  private readonly registry: AssetRegistry;
  private readonly unitTypes: ReadonlyMap<string, SimUnitType>;
  private readonly structureTypes: ReadonlyMap<string, SimStructureType>;
  private readonly unitRows: UnitRow[];
  private readonly structureRows: StructureRow[];
  private readonly researchTree: ReadonlyMap<string, ResearchNode>;
  private readonly mapData: MapRow;
  private readonly mapRows: MapRow[];
  private world: WorldState;
  private viewCache: { source: WorldState; view: WorldState } | null = null;
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
  private fogValue = true;
  private aiValue = true;
  private mapIdValue: string | undefined;
  private readonly simData: SimData;
  private mode: { kind: 'skirmish' } | { kind: 'mission'; id: string } = { kind: 'skirmish' };
  private skirmishConfig: SkirmishConfig = {
    mapId: '',
    faction: 'human',
    opponents: [{ faction: 'alien', difficulty: 'normal' }],
    resources: 'normal',
    force: 'padForce',
    fog: true,
  };
  private campaignValue: CampaignId | null = null;
  private selectedMissionId: string | null = null;
  private progress: CampaignProgress = emptyProgress();
  private readonly kv: KvStore;
  private resultRecorded = false;
  private dropPadId: number | null = null;
  private placementState: PlacementState | null = null;
  private readonly controlGroups = new Map<number, number[]>();
  private hud: HudHandle | null = null;

  constructor(root: HTMLElement) {
    this.registry = new AssetRegistry(parseAssetManifest(rawManifest));
    const data = loadSimData(this.registry);
    this.simData = data;
    this.kv = createKvStore();
    void loadProgress(this.kv).then((loaded) => {
      this.progress = loaded;
    });
    this.mapData = data.mapData;
    this.mapRows = data.mapRows;
    this.unitTypes = data.unitTypes;
    this.structureTypes = data.structureTypes;
    this.unitRows = data.unitRows;
    this.structureRows = data.structureRows;
    this.researchTree = data.researchTree;
    this.world = this.newSkirmish();
    try {
      this.leftHandedValue = window.localStorage.getItem('setting.leftHanded') === 'true';
      this.fogValue = window.localStorage.getItem('setting.fog') !== 'revealed';
      this.aiValue = window.localStorage.getItem('setting.ai') !== 'off';
      this.mapIdValue = window.localStorage.getItem('setting.map') ?? undefined;
      this.skirmishConfig = { ...this.skirmishConfig, mapId: this.mapIdValue ?? '', fog: this.fogValue };
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
      getWorld: () => this.viewWorld(),
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
      isFogOn: () => this.fogValue,
      setFogOn: (value) => {
        this.setFogOn(value);
      },
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
      chooseCampaign: (campaign) => {
        this.campaignValue = campaign;
      },
      getCampaign: () => this.campaignValue,
      getMissionList: () => this.missionList(),
      chooseMission: (id) => this.chooseMission(id),
      getBriefing: () => this.briefing(),
      getObjectives: () => this.objectives(),
      getResultView: () => this.resultView(),
      chooseNextMission: () => this.chooseNextMission(),
      getSkirmishConfig: () => this.skirmishConfig,
      setSkirmishConfig: (config) => {
        this.skirmishConfig = config;
      },
      getSkirmishMaps: () => this.mapRows.map((row) => ({ id: row.id, name: row.name })),
      beginSkirmish: () => {
        this.mode = { kind: 'skirmish' };
        this.fogValue = this.skirmishConfig.fog;
        this.mapIdValue = this.skirmishConfig.mapId || this.mapIdValue;
      },
      getBaseView: () => this.baseView(),
      baseAction: (action) => this.baseAction(action),
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

  // The world as the player may see it: hidden enemy units and structures are removed, remembered
  // structures come back as ghosts. Renderer, HUD, minimap and the test hook use this only.
  viewWorld(): WorldState {
    const world = this.world;
    if (!world.fogEnabled) {
      return world;
    }
    if (this.viewCache && this.viewCache.source === world) {
      return this.viewCache.view;
    }
    const perceived = perceivedUnits(world, 1);
    const ghosts: StructureState[] = perceived.ghosts.flatMap((ghost) => {
      const type = world.structureTypes.get(ghost.typeId);
      if (!type) {
        return [];
      }
      return [
        {
          id: ghost.id,
          owner: ghost.owner,
          typeId: ghost.typeId,
          x: ghost.x,
          z: ghost.z,
          hp: type.hp,
          containers: 0,
          fill: 0,
          depositId: null,
          upgrades: [],
          reloadLeft: 0,
          turretHeading: 0,
          work: null,
          research: null,
        },
      ];
    });
    const view: WorldState = {
      ...world,
      units: perceived.units,
      structures: [...perceived.structures, ...ghosts],
    };
    this.viewCache = { source: world, view };
    return view;
  }

  units(): UnitView[] {
    return this.viewWorld().units.map((unit) => {
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
    return this.viewWorld().structures.map((structure) => {
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
    const disabled = (
      kind: 'unit' | 'structure',
      ore: number,
      metal: number,
      itemId: string,
    ): string | null => {
      if (!isItemUnlocked(this.world, 1, itemId)) {
        const node = unlockingNode(this.world, 1, itemId);
        return `Needs: ${node?.name ?? 'research'}`;
      }
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
      if (row.faction !== faction || this.world.unitTypes.get(row.id)?.deploysTo) {
        continue;
      }
      items.push({
        id: row.id,
        name: row.name,
        kind: 'unit',
        ore: row.cost.ore,
        metal: row.cost.metal,
        deliverySec: row.deliverySec,
        disabledReason: disabled('unit', row.cost.ore, row.cost.metal, row.id),
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
        disabledReason: disabled('structure', row.cost.ore, row.cost.metal, row.id),
      });
    }
    return items;
  }

  baseView(): BaseView {
    const world = this.world;
    const stats = this.sideStats(1);
    const faction = this.factionFor(1);
    const own = world.structures.filter((item) => item.owner === 1 && item.hp > 0);
    const labs = own.filter((item) => world.structureTypes.get(item.typeId)?.kind === 'lab');
    const idleLab = labs.find((item) => item.research === null && item.work === null) ?? null;
    const done = researchDone(world, 1);
    const nodes = [...world.researchTree.values()]
      .filter((node) => node.faction === faction)
      .map((node) => {
        const running = own.find((item) => item.research?.nodeId === node.id);
        let state: 'done' | 'researching' | 'available' | 'locked' = 'available';
        let reason: string | null = null;
        if (done.has(node.id)) {
          state = 'done';
        } else if (running) {
          state = 'researching';
        } else if (node.requires.some((req) => !done.has(req))) {
          state = 'locked';
          const need = node.requires.find((req) => !done.has(req));
          reason = `Needs: ${world.researchTree.get(need ?? '')?.name ?? 'research'}`;
        } else if (!stats || stats.ore < node.cost.ore || stats.metal < node.cost.metal) {
          reason = 'Cannot afford';
        } else if (idleLab) {
          const code = researchRejection(world, 1, idleLab.id, node.id);
          reason = code === null ? null : code;
        }
        return {
          id: node.id,
          name: node.name,
          ore: node.cost.ore,
          metal: node.cost.metal,
          timeSec: node.timeSec,
          state,
          reason,
          progress:
            running?.research && node.timeSec > 0 ? 1 - running.research.left / node.timeSec : state === 'done' ? 1 : 0,
        };
      });
    const structures = own
      .filter((item) => world.structureTypes.get(item.typeId)?.kind !== 'pad')
      .map((item) => {
        const type = world.structureTypes.get(item.typeId);
        return {
          id: item.id,
          name: type?.name ?? item.typeId,
          kind: type?.kind ?? 'pad',
          hpPercent: type ? Math.round((item.hp / type.hp) * 100) : 100,
          busy: item.work?.kind ?? null,
          canPack: Boolean(type?.packedUnitId),
          canDismantle: true,
        };
      });
    const units = this.selectedIds
      .map((id) => world.units.find((unit) => unit.id === id && unit.owner === 1 && unit.hp > 0))
      .filter((unit): unit is NonNullable<typeof unit> => unit !== undefined)
      .map((unit) => {
        const type = world.unitTypes.get(unit.typeId);
        const labels: Record<UpgradeKind, string> = { fireRate: 'Fire rate', armor: 'Armor', stealth: 'Stealth' };
        const kinds = (type?.upgrades ?? []).filter(
          (kind): kind is UpgradeKind => kind === 'fireRate' || kind === 'armor' || kind === 'stealth',
        );
        const upgrades = kinds.map((kind) => {
          const have = unit.upgrades.includes(kind);
          const code = have ? null : upgradeRejection(world, 1, unit.id, kind);
          return {
            kind,
            label: `${labels[kind]} ${UPGRADE_COST_ORE}O ${UPGRADE_COST_METAL}M`,
            have,
            reason: code,
          };
        });
        return {
          id: unit.id,
          name: this.itemName(unit.typeId),
          hpPercent: type ? Math.round((unit.hp / type.hp) * 100) : 100,
          canDeploy: Boolean(type?.deploysTo),
          deployReason: null,
          upgrades,
        };
      });
    return {
      labId: idleLab?.id ?? labs[0]?.id ?? null,
      labBusy: labs.length > 0 && idleLab === null,
      nodes,
      structures,
      units,
      ore: stats?.ore ?? 0,
      metal: stats?.metal ?? 0,
    };
  }

  baseAction(action: BaseAction): boolean {
    const base = { tick: this.world.tick + 1, issuer: 1 };
    switch (action.kind) {
      case 'research': {
        const view = this.baseView();
        const lab = this.world.structures.find(
          (item) =>
            item.owner === 1 &&
            item.hp > 0 &&
            this.world.structureTypes.get(item.typeId)?.kind === 'lab' &&
            item.research === null &&
            item.work === null,
        );
        if (!lab || view.labId === null) {
          return false;
        }
        return this.sendCommand({ ...base, kind: 'research', labId: lab.id, nodeId: action.nodeId });
      }
      case 'cancelResearch': {
        const lab = this.world.structures.find(
          (item) =>
            item.owner === 1 &&
            item.research !== null &&
            (action.nodeId === undefined || item.research.nodeId === action.nodeId),
        );
        return lab ? this.sendCommand({ ...base, kind: 'cancelResearch', labId: lab.id }) : false;
      }
      case 'pack':
        return this.sendCommand({ ...base, kind: 'pack', structureId: action.structureId });
      case 'dismantle':
        return this.sendCommand({ ...base, kind: 'dismantle', structureId: action.structureId });
      case 'deploy':
        return this.sendCommand({ ...base, kind: 'deploy', unitId: action.unitId });
      case 'upgrade':
        return this.sendCommand({
          ...base,
          kind: 'upgrade',
          targetId: action.targetId,
          upgrade: action.upgrade,
        });
    }
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

  setFogOn(value: boolean): void {
    this.fogValue = value;
    try {
      window.localStorage.setItem('setting.fog', value ? 'on' : 'revealed');
    } catch {
      // Storage can be unavailable; the setting still applies for this session.
    }
  }

  fogOn(): boolean {
    return this.fogValue;
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
    const config = this.skirmishConfig;
    const specs = [
      { player: 1, faction: config.faction, controller: 'human' as const },
      ...config.opponents.map((opponent, index) => ({
        player: index + 2,
        faction: opponent.faction,
        controller: 'ai' as const,
        difficulty: opponent.difficulty,
      })),
    ];
    const world = createSkirmishWorld(this.simData, this.nextSeed, specs, {
      fog: this.fogValue,
      mapId: this.mapIdValue,
      resources: config.resources,
      force: config.force,
    });
    if (!this.aiValue) {
      world.aiStates = [];
    }
    this.nextSeed += 1;
    this.dropPadId = null;
    this.placementState = null;
    return world;
  }

  private newMission(id: string): WorldState {
    const row = MISSIONS.find((mission) => mission.id === id);
    if (!row) {
      return this.newSkirmish();
    }
    const world = buildMissionWorld(this.simData, row, 1, { fog: this.fogValue });
    if (!this.aiValue) {
      world.aiStates = [];
    }
    this.dropPadId = null;
    this.placementState = null;
    return world;
  }

  private missionList(): MissionListItem[] {
    if (!this.campaignValue) {
      return [];
    }
    const missions = missionsOf(this.campaignValue);
    return missions.map((mission) => ({
      id: mission.id,
      title: mission.title,
      order: mission.order,
      status: missionStatus(this.progress, missions, mission.id),
    }));
  }

  private chooseMission(id: string): boolean {
    const mission = MISSIONS.find((item) => item.id === id);
    if (!mission) {
      return false;
    }
    const status = missionStatus(this.progress, missionsOf(mission.campaign), id);
    if (status === 'locked') {
      return false;
    }
    this.selectedMissionId = id;
    this.mode = { kind: 'mission', id };
    return true;
  }

  private chooseNextMission(): boolean {
    const current = MISSIONS.find((item) => item.id === this.selectedMissionId);
    const next = current ? nextMission(current) : null;
    return next ? this.chooseMission(next.id) : false;
  }

  private briefing(): BriefingView | null {
    const mission = MISSIONS.find((item) => item.id === this.selectedMissionId);
    const map = mission ? this.mapRows.find((row) => row.id === mission.mapId) : undefined;
    if (!mission || !map) {
      return null;
    }
    return {
      title: mission.title,
      text: mission.briefing,
      objectives: mission.objectives.map((o) => ({ text: o.text, kind: o.kind })),
      map: {
        size: map.size,
        cellSize: map.cellSize,
        seed: 1,
        starts: map.starts,
        deposits: map.deposits,
        features: map.features ?? null,
      },
    };
  }

  private objectives(): ObjectiveView[] {
    return (this.world.mission?.objectives ?? []).map((o) => ({ ...o }));
  }

  private resultView(): ResultView {
    const mission = this.world.mission;
    if (!mission) {
      return { mission: false, won: false, title: null, reason: null, hasNext: false };
    }
    const row = MISSIONS.find((item) => item.id === mission.def.id);
    const won = this.world.result?.winner === mission.humanSide;
    const reasons: Record<string, string> = {
      timeout: 'Time ran out.',
      defeated: 'Your base was lost.',
    };
    return {
      mission: true,
      won,
      title: row?.title ?? null,
      reason: mission.failReason ? (reasons[mission.failReason] ?? mission.failReason) : null,
      hasNext: row ? nextMission(row) !== null : false,
    };
  }

  private recordMissionResult(): void {
    const mission = this.world.mission;
    if (!mission || !this.world.result || this.resultRecorded) {
      return;
    }
    this.resultRecorded = true;
    if (this.world.result.winner === mission.humanSide) {
      this.progress = recordWin(this.progress, mission.def.id, this.world.tick / SIM_TICK_HZ);
      void saveProgress(this.kv, this.progress).catch(() => undefined);
    }
  }

  private startSkirmish(): void {
    this.resultRecorded = false;
    this.world = this.mode.kind === 'mission' ? this.newMission(this.mode.id) : this.newSkirmish();
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
    const vision = this.world.vision.find((item) => item.player === 1);
    this.renderView.setPerception(
      this.world.fogEnabled && vision
        ? { cells: vision.cells, cols: this.world.map.cols, rows: this.world.map.rows }
        : null,
      vision?.contacts ?? [],
    );
    this.renderView.render(alpha, this.viewWorld());
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
    this.world = stepWithAi(this.world, due);
    this.pendingCommands = this.pendingCommands.filter((command) => command.tick > nextTick);
    this.pruneSelection();
    this.recordMissionResult();
    if (this.placementState && !this.world.pendingKits.some((kit) => kit.id === this.placementState?.kitId)) {
      this.placementState = null;
      this.renderView?.clearPlacement();
    }
  }
}

export function createApp(root: HTMLElement): App {
  return new App(root);
}
