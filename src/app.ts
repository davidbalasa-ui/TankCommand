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
  type ItemResearchView,
  type KitView,
  type PlacementView,
  type ResearchQueueView,
  type RendererHandle,
  type ScreenContext,
  type ScreenId,
  type WorkerActions,
} from './ui/router';
import { InputController, type IssuedCommand } from './ui/input';
import { hashWorld, snapshot } from './sim/world';
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
import { pushLog } from './platform/logBuffer';
import {
  DEFAULT_SETTINGS,
  type SettingsState,
} from './platform/settings';
import type { RenderStats, RenderView, ScreenBounds } from './render/renderer';
import type { AlertKind, AlertSnapshot } from './ui/alerts';
import type { AudioStatusView } from './audio/audio';
import type {
  ImportSaveResult,
  LoadSlotResult,
  SaveActionResult,
  SaveSlotSummary,
} from './game/api';
import { GameServices } from './game/services';
import { FpsMeter } from './ui/fpsMeter';
import { addStructure, addUnit, placementValidity, structureAtPoint } from './sim/spawn';
import { isItemUnlocked, researchDone, researchPlan, researchRejection, researchStatus, unlockingNode } from './sim/research';
import { missionAllows } from './sim/triggers';
import { upgradeRejection } from './sim/upgrades';
import { UPGRADE_COST_METAL, UPGRADE_COST_ORE } from './sim/tuning';
import { perceivedUnits } from './sim/vision';
import { stepWithAi } from './ai/driver';
import { missionMarkers } from './sim/triggers';
import type { StructureState } from './sim/types';
import type { BaseAction, BaseView, ResearchNodeView } from './ui/basePanel';
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
  jobTargetId: number | null;
  jobSource: string | null;
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

/**
 * A command the player actually issues. Everything except the test/debug
 * commands counts, so new order kinds from later packages are blocked while
 * paused without touching this list.
 */
function isPlayerOrder(command: Command): boolean {
  return command.kind !== 'noop' && !command.kind.startsWith('debug.');
}

const TITLE_SIDE_OFFSET = 11;

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
  private readonly fpsMeter = new FpsMeter();
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
  private lifecyclePauseScreen: ScreenId | null = null;
  private freezeSimUntil = 0;
  private selectedIds: number[] = [];
  private simSpeedMultiplier = 1;
  private nextSeed = 1;
  private queueModeValue = false;
  private selectModeValue = false;
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
  private matchActive = false;
  private dropPadId: number | null = null;
  private placementState: PlacementState | null = null;
  private readonly controlGroups = new Map<number, number[]>();
  private hud: HudHandle | null = null;
  private services: GameServices | null = null;

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
      api: this.services?.api,
      go: (id) => {
        this.go(id);
      },
      pauseSim: (paused) => {
        this.pauseSim(paused);
      },
      attachRenderer: (canvas) => this.attachRenderer(canvas),
      attachTitleBackdrop: (canvas) => this.attachTitleBackdrop(canvas),
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
      thumbnail: (kind, typeId) => this.renderView?.thumbnail(kind, typeId) ?? null,
      itemName: (typeId) => this.itemName(typeId),
      itemRole: (typeId) => this.itemRole(typeId),
      isSelectMode: () => this.selectModeValue,
      setSelectMode: (value) => {
        this.selectModeValue = value;
      },
      getOwnPads: () => this.ownPads(),
      getSelectedPadId: () => this.currentDropPadId(),
      setSelectedPad: (id) => {
        this.setSelectedPad(id);
      },
      buyItem: (itemId) => this.buyItem(itemId),
      getDropQueue: () => this.dropQueue(),
      getResearchQueue: () => this.researchQueue(),
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
      getSkirmishMaps: () =>
        this.mapRows.filter((row) => !row.campaignOnly).map((row) => ({
          id: row.id,
          name: row.name,
          preview: {
            size: row.size,
            cellSize: row.cellSize,
            seed: 1,
            starts: row.starts,
            deposits: row.deposits,
            features: row.features ?? null,
          },
        })),
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

    this.services = new GameServices({
      getWorld: () => this.world,
      loadWorld: (world, startMatch) => {
        this.loadWorld(world, startMatch);
      },
      currentScreen: () => this.router.current(),
      inMatch: () => this.matchActive,
      setCameraTarget: (x, z) => {
        this.setCamera({ targetX: x, targetZ: z });
      },
      worldToScreen: (x, z) => this.renderView?.worldToScreen(x, z) ?? null,
      setSimSpeed: (multiplier) => {
        this.simSpeedMultiplier = Math.min(8, Math.max(0.5, multiplier));
      },
      getSimSpeed: () => this.simSpeedMultiplier,
      freezeReport: () => this.lastFreeze,
      applySettings: (settings) => {
        this.applySettings(settings);
      },
    });
    this.leftHandedValue = this.services.settings().leftHanded;
  }

  start(): void {
    this.router.start('title');
    this.lifecycle = bindLifecycleToBrowserAndCapacitor();
    this.lifecycle.on('pause', () => {
      this.pauseLifecycle();
      void this.services?.onBackground();
    });
    this.lifecycle.on('resume', () => {
      this.resumeLifecycle();
    });
    this.lifecycle.on('back', () => {
      this.handleAndroidBack();
    });
    this.installAudioUnlock();
    window.addEventListener('keydown', this.onKeyDown);
    installGlobalErrorCapture(window, (error) => {
      console.error(error.message);
      pushLog('error', `${error.kind}: ${error.message}`);
    });
  }

  go(id: ScreenId): void {
    if (id === 'loading') {
      this.startSkirmish();
    }
    if (id === 'title' || id === 'results') {
      this.matchActive = false;
    }
    this.router.go(id);
    this.services?.setMatchActive(this.matchActive && id !== 'results');
  }

  snapshot(): WorldState {
    return { ...snapshot(this.world) };
  }

  worldHash(): string {
    return hashWorld(this.world);
  }

  sendCommand(command: unknown): boolean {
    const validated = validateCommand(command);
    if (!validated) {
      return false;
    }
    const order = isPlayerOrder(validated);
    // GAME-01 refuses *orders* while paused. Debug-only commands (`noop`,
    // `debug.addCounter`) are not orders, so they stay accepted — HOOK-02
    // uses them specifically to steer the sim while the pause gate is up.
    if (this.paused && order) {
      return false;
    }
    const stamped = this.stampCommand(validated);
    this.pendingCommands.push(stamped);
    if (stamped.kind === 'move' || stamped.kind === 'attackMove') {
      this.renderView?.pulseMarker(stamped.x, stamped.z);
    }
    if (order) {
      this.services?.playSound({ type: 'orderAck' });
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
        jobTargetId: unit.job?.targetId ?? null,
        jobSource: unit.job?.kind === 'tug' ? (unit.job.source ?? 'station') : null,
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
    const next = [...new Set(ids)].filter((id) => valid.has(id));
    const previous = this.selectedIds;
    const changed =
      previous.length !== next.length ||
      next.some((id, index) => id !== previous[index]);
    this.selectedIds = next;
    if (changed && next.length > 0) {
      this.services?.playSound({ type: 'selection' });
    }
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

  alerts(): AlertSnapshot[] {
    return this.services?.alerts() ?? [];
  }

  simSpeed(): number {
    return this.simSpeedMultiplier;
  }

  isSimPaused(): boolean {
    return this.paused;
  }

  settings(): SettingsState {
    return this.services?.settings() ?? DEFAULT_SETTINGS;
  }

  audioStatus(): AudioStatusView {
    return this.services?.audioStatus() ?? {
      unlocked: false,
      contextAvailable: false,
      masterVolume: 0,
      musicVolume: 0,
      effectsVolume: 0,
      played: [],
    };
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
        return 'Research first';
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
      if (row.faction !== faction || this.world.unitTypes.get(row.id)?.deploysTo || !missionAllows(this.world, 1, row.id)) {
        continue;
      }
      items.push({
        id: row.id,
        name: row.name,
        roleLabel: row.roleLabel,
        kind: 'unit',
        ore: row.cost.ore,
        metal: row.cost.metal,
        deliverySec: row.deliverySec,
        disabledReason: disabled('unit', row.cost.ore, row.cost.metal, row.id),
        research: this.itemResearch(row.id),
      });
    }
    for (const row of this.structureRows) {
      // Missions can hold items back so each one adds a single new idea; those are not listed.
      if (row.faction !== faction || row.buyable === false || !missionAllows(this.world, 1, row.id)) {
        continue;
      }
      items.push({
        id: row.id,
        name: row.name,
        roleLabel: row.roleLabel,
        kind: 'structure',
        ore: row.cost.ore,
        metal: row.cost.metal,
        deliverySec: row.deliverySec,
        disabledReason: disabled('structure', row.cost.ore, row.cost.metal, row.id),
        research: this.itemResearch(row.id),
      });
    }
    return items;
  }

  /** The research a locked card starts (undefined when the item is unlocked). */
  private itemResearch(itemId: string): ItemResearchView | undefined {
    const node = unlockingNode(this.world, 1, itemId);
    return node ? this.researchView(node.id) : undefined;
  }

  private researchView(nodeId: string): ItemResearchView | undefined {
    const plan = researchPlan(this.world, 1, nodeId);
    const first = plan?.[0];
    if (!plan || !first) {
      return undefined;
    }
    const status = researchStatus(this.world, 1);
    const chain = [status.active?.node.id, ...status.queue.map((item) => item.id)];
    const running = plan.some((step) => chain.includes(step.id));
    const busy = status.active !== null || status.queue.length > 0;
    const stats = this.sideStats(1);
    const short = !stats || stats.ore < first.cost.ore || stats.metal < first.cost.metal;
    const names = plan.map((step) => step.name);
    const active = status.active;
    return {
      nodeId,
      label: `Research ${names.join(', then ')}`,
      ore: first.cost.ore,
      metal: first.cost.metal,
      timeSec: first.timeSec,
      state: running ? 'running' : busy ? 'busy' : short ? 'short' : 'ready',
      progress: running && active && active.node.timeSec > 0 ? 1 - active.left / active.node.timeSec : 0,
    };
  }

  /** The side's research for the top queue strip: the running step, then those waiting. */
  researchQueue(): ResearchQueueView[] {
    const status = researchStatus(this.world, 1);
    const picture = (unlocks: readonly string[]): string | null =>
      unlocks.find((id) => !id.includes('_packed')) ?? null;
    const views: ResearchQueueView[] = [];
    if (status.active) {
      const node = status.active.node;
      views.push({
        nodeId: node.id,
        name: node.name,
        pictureId: picture(node.unlocks),
        progress: node.timeSec > 0 ? 1 - status.active.left / node.timeSec : 1,
        remainingSec: status.active.left,
        waiting: false,
      });
    }
    for (const node of status.queue) {
      views.push({
        nodeId: node.id,
        name: node.name,
        pictureId: picture(node.unlocks),
        progress: 0,
        remainingSec: node.timeSec,
        waiting: true,
      });
    }
    return views;
  }

  baseView(): BaseView {
    const world = this.world;
    const stats = this.sideStats(1);
    const faction = this.factionFor(1);
    const own = world.structures.filter((item) => item.owner === 1 && item.hp > 0);
    const done = researchDone(world, 1);
    const status = researchStatus(world, 1);
    const queued = status.queue.map((node) => node.id);
    const itemNames = (ids: readonly string[]): string =>
      ids.filter((id) => missionAllows(world, 1, id)).map((id) => this.itemName(id)).join(', ');
    // The research building shows the same unlocks as the locked cards: only research that
    // unlocks something this match offers.
    const nodes = [...world.researchTree.values()]
      .filter((node) => node.faction === faction && (done.has(node.id) || itemNames(node.unlocks) !== ''))
      .map((node) => {
        const view = this.researchView(node.id);
        let state: ResearchNodeView['state'] = 'available';
        let reason: string | null = null;
        if (done.has(node.id)) {
          state = 'done';
        } else if (status.active?.node.id === node.id) {
          state = 'researching';
        } else if (queued.includes(node.id)) {
          state = 'queued';
        } else if (view?.state === 'busy' || view?.state === 'running') {
          reason = 'After the current research';
        } else if (view?.state === 'short') {
          reason = 'Cannot afford';
        } else {
          const code = researchRejection(world, 1, node.id);
          reason = code === null ? null : code;
        }
        return {
          id: node.id,
          name: node.name,
          unlocks: itemNames(node.unlocks),
          label: view?.label ?? `Research ${node.name}`,
          ore: view?.ore ?? node.cost.ore,
          metal: view?.metal ?? node.cost.metal,
          timeSec: view?.timeSec ?? node.timeSec,
          state,
          reason,
          progress:
            state === 'researching' && status.active && node.timeSec > 0
              ? 1 - status.active.left / node.timeSec
              : state === 'done'
                ? 1
                : 0,
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
      researchBusy: status.active !== null || status.queue.length > 0,
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
      case 'research':
        return this.sendCommand({ ...base, kind: 'research', nodeId: action.nodeId });
      case 'cancelResearch':
        return this.sendCommand({ ...base, kind: 'cancelResearch' });
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

  haulAt(depositId: number): boolean {
    const ids = this.selectedIds.filter((id) => {
      const unit = this.world.units.find((item) => item.id === id);
      const type = unit ? this.world.unitTypes.get(unit.typeId) : undefined;
      return type?.workerKind === 'tug';
    });
    if (ids.length === 0) {
      return false;
    }
    return this.sendCommand({
      kind: 'haul',
      unitIds: ids,
      depositId,
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
    const structure = structureAtPoint(this.viewWorld(), x, z);
    if (!structure) {
      return null;
    }
    const type = this.world.structureTypes.get(structure.typeId);
    return { id: structure.id, owner: structure.owner, kind: type?.kind ?? 'pad' };
  }

  setSimSpeed(multiplier: number): void {
    this.simSpeedMultiplier = Math.min(8, Math.max(0.5, multiplier));
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
    this.services?.setSetting('leftHanded', value);
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
      return { loadedModels: [], meshCount: 0, drawCalls: 0,
        triangles: 0, frame: 0, units: 0 };
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

  pressAndroidBack(): void {
    this.pauseLifecycle();
    this.handleAndroidBack();
  }

  requestAutosave(): Promise<void> {
    return this.services?.requestAutosave() ?? Promise.resolve();
  }

  listSaveSlots(): Promise<SaveSlotSummary[]> {
    return this.services?.listSaveSlots() ?? Promise.resolve([]);
  }

  lastSaveOutcome(): SaveActionResult | null {
    return this.services?.lastSaveOutcome() ?? null;
  }

  lastLoadOutcome(): LoadSlotResult | null {
    return this.services?.lastLoadOutcome() ?? null;
  }

  lastImportOutcome(): ImportSaveResult | null {
    return this.services?.lastImportOutcome() ?? null;
  }

  lastBugReport(): { fileName: string; content: string } | null {
    return this.services?.lastBugReport() ?? null;
  }

  async writeRawSave(slot: string, text: string): Promise<void> {
    await this.services?.writeRawSave(slot, text);
  }

  setStorageFullForTest(value: boolean): void {
    this.services?.setStorageFullForTest(value);
  }

  /**
   * Test-only stress scene: fills the map with `perSide` ground units for the player and twice
   * that for the enemy (standing in for two NPC teams), lined up to fight across the middle.
   * Returns how many units were added.
   */
  stressSpawnForTest(perSide: number, withEnemies = true): number {
    const world = this.world;
    const ground = (faction: string) =>
      [...world.unitTypes.values()].filter((type) => type.faction === faction && !type.air && type.weapon && !type.workerKind);
    const human = ground('human');
    const alien = ground('alien');
    const half = world.map.size / 2;
    let added = 0;
    const place = (owner: number, types: typeof human, count: number, z0: number, dir: number) => {
      const columns = 16;
      for (let i = 0; i < count; i += 1) {
        const type = types[i % types.length];
        if (!type) {
          return;
        }
        const x = (-columns / 2 + (i % columns) + 0.5) * (half / 10);
        const z = z0 + dir * Math.floor(i / columns) * 5;
        if (addUnit(world, { owner, typeId: type.id, x, z, heading: dir > 0 ? Math.PI / 2 : -Math.PI / 2 })) {
          added += 1;
        }
      }
    };
    place(1, human, perSide, half * 0.12, 1);
    if (withEnemies) {
      place(2, alien, perSide, -half * 0.12, -1);
      place(2, human, perSide, -half * 0.12 - Math.ceil(perSide / 16) * 5, -1);
    }
    return added;
  }

  spawnUnitForTest(typeId: string, owner: number, x: number, z: number, heading = 0): number | null {
    return addUnit(this.world, { owner, typeId, x, z, heading })?.id ?? null;
  }

  spawnStructureForTest(typeId: string, owner: number, x: number, z: number): number | null {
    return addStructure(this.world, { owner, typeId, x, z })?.id ?? null;
  }

  raiseAlertForTest(kind: AlertKind, x: number, z: number): void {
    this.services?.raiseAlert(kind, x, z);
  }

  unlockAudio(): void {
    this.services?.unlockAudio();
  }

  private itemRole(itemId: string): string | undefined {
    const unit = this.unitRows.find((row) => row.id === itemId) as { roleLabel?: string } | undefined;
    const structure = this.world.structureTypes.get(itemId) as { roleLabel?: string } | undefined;
    return unit?.roleLabel ?? structure?.roleLabel;
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
    this.matchActive = true;
    this.services?.resetAlerts(this.world);
    this.services?.setMatchActive(true);
  }

  private loadWorld(world: WorldState, startMatch: boolean): void {
    this.world = world;
    // A save remembers whether it was a mission, so Retry, Next and progress work after loading.
    this.mode = world.mission ? { kind: 'mission', id: world.mission.def.id } : { kind: 'skirmish' };
    if (world.mission) {
      this.selectedMissionId = world.mission.def.id;
      this.campaignValue = MISSIONS.find((item) => item.id === world.mission?.def.id)?.campaign ?? this.campaignValue;
    }
    this.resultRecorded = world.result !== null;
    this.pendingCommands = [];
    this.selectedIds = [];
    this.fixed.reset();
    this.lastFreeze = null;
    this.dropPadId = null;
    this.placementState = null;
    this.renderView?.clearPlacement();
    this.services?.resetAlerts(world);
    if (startMatch) {
      this.matchActive = true;
      this.router.start('inGame');
      this.services?.setMatchActive(true);
    } else {
      this.hud?.refresh();
    }
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

  /**
   * Title screen background: a separate demo skirmish (own pad and starting force, no fog) drawn
   * by its own renderer with the camera slowly orbiting the pad. Nothing is simulated. It only
   * draws while the title is the top screen and is skipped on the low quality level.
   */
  private attachTitleBackdrop(canvas: HTMLCanvasElement): Promise<() => void> {
    const settings = this.services?.settings();
    if (settings?.graphicsQuality === 'low') {
      return Promise.resolve(() => undefined);
    }
    return import('./render/renderer').then(
      (mod) => {
        const world = createSkirmishWorld(
          this.simData,
          7,
          [
            { player: 1, faction: 'human', controller: 'human' },
            { player: 2, faction: 'alien', controller: 'ai', difficulty: 'normal' },
          ],
          { fog: false, mapId: this.mapIdValue, resources: 'normal', force: 'padForce' },
        );
        world.aiStates = [];
        const view = new mod.RenderView(canvas, this.registry, world);
        // The canvas stays invisible (CSS) until the models are in, then fades up; the gradient
        // behind it shows meanwhile, never the grey placeholder tanks.
        void view.whenReady().then(() => {
          canvas.classList.add('ready');
        });
        const pad = world.structures.find((item) => item.owner === 1);
        const centreX = pad?.x ?? 0;
        const centreZ = pad?.z ?? 0;
        const started = performance.now();
        let raf = 0;
        let disposed = false;
        const frame = (now: number): void => {
          raf = 0;
          if (disposed) {
            return;
          }
          if (this.router.current() === 'title' && document.visibilityState === 'visible') {
            const t = (now - started) / 1000;
            const yaw = 0.6 + t * 0.035;
            // Drift round the pad. The target sits to the pad's screen-left so the pad stays in the
            // right-hand part of the picture, clear of the menu column.
            view.setCamera({
              targetX: centreX + Math.cos(yaw) * TITLE_SIDE_OFFSET,
              targetZ: centreZ - Math.sin(yaw) * TITLE_SIDE_OFFSET,
              distance: 34,
              yaw,
            });
            view.render(0, world);
          }
          raf = window.requestAnimationFrame(frame);
        };
        raf = window.requestAnimationFrame(frame);
        return () => {
          disposed = true;
          if (raf !== 0) {
            window.cancelAnimationFrame(raf);
          }
          view.dispose();
          view.releaseContext();
        };
      },
      () => () => undefined,
    );
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
          isSelectMode: () => this.selectModeValue,
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
          onHaulOrder: (depositId) => this.haulAt(depositId),
          onAttackStructure: (structureId) => this.attackStructure(structureId),
          onOwnStructureTap: (structure) => this.hud?.openForStructure?.(structure) ?? false,
          isPlacementActive: () => this.placementState !== null,
          previewPlacement: (x, z) => {
            this.previewPlacement(x, z);
          },
        });
        if (this.services) {
          this.applySettings(this.services.settings());
          this.services.setMusic('human', false);
        }
        // Hold the match (sim and drawing) until the models are in, so no placeholder boxes show.
        const ready = view.whenReady().then(() => {
          if (this.renderView === view) {
            this.startLoop();
          }
        });
        return {
          error: null,
          ready,
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

  private installAudioUnlock(): void {
    const unlock = (): void => {
      this.services?.unlockAudio();
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('touchstart', unlock);
      window.removeEventListener('keydown', unlock);
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('touchstart', unlock);
    window.addEventListener('keydown', unlock);
  }

  private pauseLifecycle(): void {
    this.lifecyclePauseScreen = this.router.current();
    this.lifecyclePaused = true;
    this.applyPauseState();
  }

  private resumeLifecycle(): void {
    this.lifecyclePaused = false;
    this.lifecyclePauseScreen = null;
    this.applyPauseState();
  }

  private handleAndroidBack(): void {
    const before = this.lifecyclePauseScreen;
    this.lifecyclePauseScreen = null;
    if (before === 'inGame') {
      this.go('pause');
      return;
    }
    if (before === 'pause') {
      this.lifecyclePaused = false;
      this.applyPauseState();
      this.router.back();
      return;
    }
    this.router.back();
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

  private applySettings(settings: SettingsState): void {
    document.documentElement.dataset.textSize = settings.textSize;
    document.documentElement.classList.toggle('text-large', settings.textSize === 'large');
    document.documentElement.classList.toggle('quality-low', settings.graphicsQuality === 'low');
    this.leftHandedValue = settings.leftHanded;
    this.input?.setEdgeScroll(settings.edgeScroll);
    this.renderView?.setQualityPreference(settings.graphicsQuality);
    this.renderView?.setHealthBarsMode(settings.healthBars);
    this.renderView?.setColorBlindMode(settings.colourBlind);
    this.fpsMeter.setEnabled(settings.showFps);
    this.renderView?.getCamera().setSensitivity(settings.cameraSensitivity);
    this.hud?.refresh();
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
      const result = this.fixed.advance(elapsed * this.simSpeedMultiplier);
      alpha = result.alpha;
      if (result.steps > 0) {
        this.watchdog.beat('sim');
      }
    }

    this.input?.update(elapsed);
    this.pruneSelection();
    this.watchdog.check();
    this.services?.observe(this.world);
    this.renderView.setSelection(this.selectedIds);
    const vision = this.world.vision.find((item) => item.player === 1);
    this.renderView.setPerception(
      this.world.fogEnabled && vision
        ? { cells: vision.cells, cols: this.world.map.cols, rows: this.world.map.rows }
        : null,
      vision?.contacts ?? [],
    );
    this.renderView.setObjectiveMarkers(missionMarkers(this.world.mission));
    this.renderView.render(alpha, this.viewWorld());
    this.fpsMeter.frame(now, () => {
      const stats = this.renderView?.stats();
      return stats ? `${this.world.units.length} units · ${stats.drawCalls} draws · ${Math.round(stats.triangles / 1000)}k tris` : '';
    });
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
