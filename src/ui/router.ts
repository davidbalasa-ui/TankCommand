import type { WorldState } from '../sim/types';
import type { GameApi } from '../game/api';

export type ScreenId =
  | 'title'
  | 'campaignSelect'
  | 'missionSelect'
  | 'briefing'
  | 'skirmishSetup'
  | 'loading'
  | 'inGame'
  | 'pause'
  | 'settings'
  | 'help'
  | 'objectives'
  | 'results'
  | 'credits'
  | 'bugReport'
  | 'saveSlots'
  | 'recovery';

export interface RendererHandle {
  error: string | null;
  /** Resolves when the match's models have loaded (the screen hides the scene until then). */
  ready?: Promise<void>;
  dispose: () => void;
}

export interface CameraSnapshot {
  targetX: number;
  targetZ: number;
  distance: number;
  yaw: number;
  pitch: number;
}

export interface DropQueueView {
  id: number;
  itemId: string;
  name: string;
  remainingSec: number;
  totalSec: number;
  progress: number;
}

export interface KitView {
  id: number;
  structureTypeId: string;
  name: string;
}

export interface BuildItemView {
  id: string;
  name: string;
  /** Plain-terms role shown small and grey under the name ("Light tank"). */
  roleLabel?: string;
  kind: 'unit' | 'structure';
  ore: number;
  metal: number;
  deliverySec: number;
  disabledReason: string | null;
}

export interface PlacementView {
  kitId: number;
  structureTypeId: string;
  name: string;
  x: number;
  z: number;
  valid: boolean;
}

export interface WorkerActions {
  canMine: boolean;
  canAssign: boolean;
  canSalvage: boolean;
}

export type CampaignId = 'training' | 'human' | 'alien';

export interface MissionListItem {
  id: string;
  title: string;
  order: number;
  status: 'locked' | 'open' | 'done';
}

export interface BriefingView {
  title: string;
  text: string;
  objectives: Array<{ text: string; kind: 'primary' | 'optional' }>;
  map: {
    size: number;
    cellSize: number;
    seed: number;
    starts: Array<{ player: number; x: number; z: number }>;
    deposits: Array<{ kind: string; x: number; z: number }>;
    features: import('../sim/map').MapFeatures | null;
  };
}

export interface ObjectiveView {
  id: string;
  text: string;
  kind: 'primary' | 'optional';
  status: 'active' | 'done' | 'failed';
}

export interface MissionMessageView {
  seq: number;
  speaker: string | null;
  text: string;
}

export interface SkirmishOpponent {
  faction: 'human' | 'alien';
  difficulty: 'easy' | 'normal' | 'hard';
}

export interface SkirmishConfig {
  mapId: string;
  faction: 'human' | 'alien';
  opponents: SkirmishOpponent[];
  resources: 'low' | 'normal' | 'high';
  force: 'padOnly' | 'padForce';
  fog: boolean;
}

export interface ResultView {
  mission: boolean;
  won: boolean;
  title: string | null;
  reason: string | null;
  hasNext: boolean;
}

export interface HudSnapshot {
  leftHanded: boolean;
  groupsOpen: boolean;
  queueMode: boolean;
  attackMoveArmed: boolean;
  selectedCount: number;
  ownUnits: number;
  enemyUnits: number;
  minimapFootprint: Array<{ x: number; z: number }>;
  minimapRedraws: number;
  commandButtonsDisabled: boolean;
  buildMenuOpen: boolean;
  baseOpen: boolean;
  ore: number;
  metal: number;
  workers: number;
  unitCount: number;
  unitCap: number;
  queue: DropQueueView[];
  kits: KitView[];
  selectedPadId: number | null;
  placementActive: boolean;
}

export interface HudHandle {
  snapshot(): HudSnapshot;
  /** Re-read the current selection and update the disabled state of the command bar. */
  refresh(): void;
  /** The player tapped one of their structures: pad opens Build, others open Base. */
  openForStructure?(structure: { id: number; owner: number; kind: string }): boolean;
  dispose(): void;
}

export interface ScreenContext {
  router: ScreenRouter;
  api?: GameApi;
  go: (id: ScreenId) => void;
  pauseSim: (paused: boolean) => void;
  attachRenderer: (canvas: HTMLCanvasElement) => Promise<RendererHandle>;
  getWorld?: () => WorldState;
  selection?: () => number[];
  setSelection?: (ids: number[]) => void;
  issueStop?: () => void;
  deselect?: () => void;
  sendCommand?: (command: unknown) => boolean;
  getCamera?: () => CameraSnapshot;
  cameraFootprint?: () => Array<{ x: number; z: number }>;
  setCameraTarget?: (x: number, z: number) => void;
  isFogOn?: () => boolean;
  setFogOn?: (value: boolean) => void;
  isLeftHanded?: () => boolean;
  setLeftHanded?: (value: boolean) => void;
  isQueueMode?: () => boolean;
  setQueueMode?: (value: boolean) => void;
  isAttackMoveArmed?: () => boolean;
  setAttackMoveArmed?: (value: boolean) => void;
  assignGroup?: (group: number) => void;
  selectGroup?: (group: number) => void;
  centerGroup?: (group: number) => void;
  groupMembers?: (group: number) => number[];
  registerHud?: (hud: HudHandle | null) => void;
  getBuildItems?: () => BuildItemView[];
  /** Draws the live 3D title background into the canvas; resolves to its dispose function. */
  attachTitleBackdrop?: (canvas: HTMLCanvasElement) => Promise<() => void>;
  /** Portrait of a unit or structure type rendered from its model; null until loaded. */
  thumbnail?: (kind: 'unit' | 'structure', typeId: string) => string | null;
  /** Friendly name of a unit or structure type. */
  itemName?: (typeId: string) => string;
  getOwnPads?: () => Array<{ id: number; x: number; z: number }>;
  getSelectedPadId?: () => number | null;
  setSelectedPad?: (id: number) => void;
  buyItem?: (itemId: string) => boolean;
  getDropQueue?: () => DropQueueView[];
  cancelOrder?: (orderId: number) => void;
  getKits?: () => KitView[];
  startPlacement?: (kitId: number) => boolean;
  getPlacement?: () => PlacementView | null;
  confirmPlacement?: () => boolean;
  cancelPlacement?: () => void;
  getWorkerActions?: () => WorkerActions;
  salvageSelected?: () => void;
  chooseCampaign?: (campaign: CampaignId) => void;
  getCampaign?: () => CampaignId | null;
  getMissionList?: () => MissionListItem[];
  chooseMission?: (id: string) => boolean;
  getBriefing?: () => BriefingView | null;
  getObjectives?: () => ObjectiveView[];
  getMissionMessages?: () => MissionMessageView[];
  getResultView?: () => ResultView;
  chooseNextMission?: () => boolean;
  getSkirmishConfig?: () => SkirmishConfig;
  setSkirmishConfig?: (config: SkirmishConfig) => void;
  getSkirmishMaps?: () => Array<{ id: string; name: string; preview?: BriefingView['map'] }>;
  beginSkirmish?: () => void;
  getBaseView?: () => import('./basePanel').BaseView;
  baseAction?: (action: import('./basePanel').BaseAction) => boolean;
}

export interface ScreenModule {
  id: ScreenId;
  mount(root: HTMLElement, ctx: ScreenContext): () => void;
}

interface MountedScreen {
  id: ScreenId;
  el: HTMLDivElement;
  unmount: () => void;
}

const OVERLAY_IDS = new Set<ScreenId>([
  'pause',
  'objectives',
  'help',
  'recovery',
  'bugReport',
  'saveSlots',
]);

const ALLOWED: Record<ScreenId, readonly ScreenId[]> = {
  title: ['campaignSelect', 'skirmishSetup', 'settings', 'credits', 'help'],
  campaignSelect: ['title', 'missionSelect'],
  missionSelect: ['campaignSelect', 'briefing'],
  briefing: ['missionSelect', 'loading'],
  skirmishSetup: ['title', 'loading'],
  loading: ['inGame', 'title'],
  inGame: ['pause', 'objectives', 'help', 'bugReport', 'saveSlots', 'recovery', 'results', 'title'],
  pause: ['settings', 'bugReport', 'saveSlots', 'title', 'inGame'],
  settings: ['title', 'pause', 'inGame'],
  help: ['title', 'inGame'],
  objectives: ['inGame'],
  results: ['title', 'missionSelect', 'loading'],
  credits: ['title'],
  bugReport: ['title', 'inGame', 'pause'],
  saveSlots: ['pause', 'inGame'],
  recovery: ['inGame', 'title'],
};

const PARENT: Partial<Record<ScreenId, ScreenId>> = {
  campaignSelect: 'title',
  missionSelect: 'campaignSelect',
  briefing: 'missionSelect',
  skirmishSetup: 'title',
  loading: 'title',
  settings: 'title',
  help: 'title',
  objectives: 'inGame',
  results: 'title',
  credits: 'title',
  bugReport: 'inGame',
  saveSlots: 'pause',
  recovery: 'inGame',
  pause: 'inGame',
};

export class ScreenRouter {
  private readonly root: HTMLElement;
  private readonly screens: Record<ScreenId, ScreenModule>;
  private readonly contextFactory: (router: ScreenRouter) => ScreenContext;
  private context: ScreenContext | null = null;
  private base: MountedScreen | null = null;
  private overlays: MountedScreen[] = [];

  constructor(
    root: HTMLElement,
    screens: Record<ScreenId, ScreenModule>,
    contextFactory: (router: ScreenRouter) => ScreenContext,
  ) {
    this.root = root;
    this.screens = screens;
    this.contextFactory = contextFactory;
  }

  start(id: ScreenId = 'title'): void {
    this.mountBase(id);
  }

  current(): ScreenId {
    return this.overlays.at(-1)?.id ?? this.base?.id ?? 'title';
  }

  go(id: ScreenId): void {
    const current = this.current();
    if (id === current) {
      return;
    }

    const overlay = this.isOverlayTarget(id, current);
    if (!this.canGo(current, id)) {
      this.reject(id);
      return;
    }

    if (overlay) {
      this.mountOverlay(id);
    } else {
      this.mountBase(id);
    }
  }

  back(): void {
    if (this.overlays.length > 0) {
      this.popOverlay();
      return;
    }
    if (!this.base) {
      return;
    }
    if (this.base.id === 'inGame') {
      this.go('pause');
      return;
    }
    const parent = PARENT[this.base.id];
    if (parent) {
      this.go(parent);
    }
  }

  private isOverlayTarget(id: ScreenId, current: ScreenId): boolean {
    if (id === 'settings') {
      return current === 'pause' && this.base?.id === 'inGame';
    }
    return OVERLAY_IDS.has(id) && this.base?.id === 'inGame';
  }

  private canGo(from: ScreenId, to: ScreenId): boolean {
    return ALLOWED[from].includes(to);
  }

  private reject(id: ScreenId): void {
    const message = `Screen transition not allowed: ${id}`;
    if (import.meta.env.DEV) {
      throw new Error(message);
    }
    console.warn(message);
  }

  private mountBase(id: ScreenId): void {
    for (const overlay of [...this.overlays].reverse()) {
      this.unmountScreen(overlay);
    }
    this.overlays = [];
    if (this.base) {
      this.unmountScreen(this.base);
    }
    const mounted = this.createScreen(id, false);
    mounted.el.style.visibility = 'visible';
    this.base = mounted;
  }

  private mountOverlay(id: ScreenId): void {
    const top = this.currentMounted();
    if (top) {
      top.el.style.visibility = 'hidden';
    }
    const mounted = this.createScreen(id, true);
    mounted.el.style.visibility = 'visible';
    this.overlays.push(mounted);
  }

  private popOverlay(): void {
    const mounted = this.overlays.pop();
    if (!mounted) {
      return;
    }
    this.unmountScreen(mounted);
    const top = this.currentMounted();
    if (top) {
      top.el.style.visibility = 'visible';
    }
  }

  private currentMounted(): MountedScreen | null {
    return this.overlays.at(-1) ?? this.base;
  }

  private createScreen(id: ScreenId, overlay: boolean): MountedScreen {
    const el = document.createElement('div');
    el.className = `screen screen-${id}${overlay ? ' overlay' : ''}`;
    el.dataset.screenId = id;
    this.root.append(el);
    const screen = this.screens[id];
    const unmount = screen.mount(el, this.ensureContext());
    return { id, el, unmount };
  }

  private unmountScreen(mounted: MountedScreen): void {
    mounted.unmount();
    mounted.el.remove();
  }

  private ensureContext(): ScreenContext {
    if (!this.context) {
      this.context = this.contextFactory(this);
    }
    return this.context;
  }
}
