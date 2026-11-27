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
  | 'recovery'
  | 'unlock';

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
  /** Set while the item is locked: its card is the research order (overhaul step 4). */
  research?: ItemResearchView;
}

/** The research a locked card starts: its parents first, then the step that unlocks the item. */
export interface ItemResearchView {
  /** The node that unlocks the item (tapping queues any missing parent first). */
  nodeId: string;
  /** "Research Sensors, then Aviation". */
  label: string;
  /** Price and time of the first step (each step is paid when it starts). */
  ore: number;
  metal: number;
  timeSec: number;
  /** ready: tap to start. short: can't afford the first step. running: this chain is underway. busy: other research is. */
  state: 'ready' | 'short' | 'running' | 'busy';
  /** 0..1 progress of the running step when state is running. */
  progress: number;
}

/** One research tile in the top queue strip: the running step, or one waiting after it. */
export interface ResearchQueueView {
  nodeId: string;
  name: string;
  /** An item the step unlocks, for the tile's picture. */
  pictureId: string | null;
  progress: number;
  remainingSec: number;
  /** A queued step that hasn't started (it starts, and is paid, when the one before it ends). */
  waiting: boolean;
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

export type CampaignDifficulty = 'easy' | 'normal' | 'hard';

export interface MissionListItem {
  id: string;
  title: string;
  order: number;
  status: 'locked' | 'open' | 'done';
  /** The hardest difficulty the mission has been won on. */
  bestDifficulty?: CampaignDifficulty;
  /** Part of the full game and not yet unlocked: tapping opens the unlock screen. */
  fullGame?: boolean;
}

export interface BriefingView {
  title: string;
  text: string;
  objectives: Array<{ text: string; kind: 'primary' | 'optional' }>;
  /** The campaign difficulty the mission will be played on. */
  difficulty?: CampaignDifficulty;
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
  /** The next mission is part of the full game, which is not unlocked: Next opens the unlock screen. */
  nextNeedsFullGame?: boolean;
  /** The last mission of a story campaign was won: the results screen closes the campaign. */
  campaignComplete: boolean;
  /** The campaign's closing text, when campaignComplete. */
  epilogue: string | null;
  /** The difficulty a mission was played on. */
  difficulty?: CampaignDifficulty;
}

export interface HudSnapshot {
  leftHanded: boolean;
  groupsOpen: boolean;
  /** Select mode is on (a drag draws a box, a tap adds or removes a unit). */
  selectMode: boolean;
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
  research: ResearchQueueView[];
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
  isPatrolArmed?: () => boolean;
  setPatrolArmed?: (value: boolean) => void;
  assignGroup?: (group: number) => void;
  selectGroup?: (group: number) => void;
  centerGroup?: (group: number) => void;
  groupMembers?: (group: number) => number[];
  clearGroup?: (group: number) => void;
  registerHud?: (hud: HudHandle | null) => void;
  getBuildItems?: () => BuildItemView[];
  /** Draws the live 3D title background into the canvas; resolves to its dispose function. */
  attachTitleBackdrop?: (canvas: HTMLCanvasElement) => Promise<() => void>;
  /** Portrait of a unit or structure type rendered from its model; null until loaded. */
  thumbnail?: (kind: 'unit' | 'structure', typeId: string) => string | null;
  /** Friendly name of a unit or structure type. */
  itemName?: (typeId: string) => string;
  /** Plain-terms role of a unit or structure type ("Light tank"), if it has one. */
  itemRole?: (typeId: string) => string | undefined;
  /** Select mode: one-finger drag draws a box and a tap adds or removes a unit. */
  isSelectMode?: () => boolean;
  setSelectMode?: (value: boolean) => void;
  getOwnPads?: () => Array<{ id: number; x: number; z: number }>;
  getSelectedPadId?: () => number | null;
  setSelectedPad?: (id: number) => void;
  buyItem?: (itemId: string) => boolean;
  getDropQueue?: () => DropQueueView[];
  /** The side's research: the running step first, then any waiting after it. */
  getResearchQueue?: () => ResearchQueueView[];
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
  /** Campaign difficulty, saved with the campaign progress. */
  getDifficulty?: () => CampaignDifficulty;
  setDifficulty?: (difficulty: CampaignDifficulty) => void;
  /** A match is running (Save and Delete are offered on the save slots only then). */
  inMatch?: () => boolean;
  getMissionList?: () => MissionListItem[];
  chooseMission?: (id: string) => boolean;
  getBriefing?: () => BriefingView | null;
  getObjectives?: () => ObjectiveView[];
  getMissionMessages?: () => MissionMessageView[];
  getResultView?: () => ResultView;
  chooseNextMission?: () => boolean;
  /** Restart / Retry / Play again can rebuild the match (false for an old skirmish save). */
  canRestart?: () => boolean;
  getSkirmishConfig?: () => SkirmishConfig;
  setSkirmishConfig?: (config: SkirmishConfig) => void;
  /** `fullGame` marks a map that needs the full game unlock (not yet bought). */
  getSkirmishMaps?: () => Array<{ id: string; name: string; preview?: BriefingView['map']; fullGame?: boolean }>;
  beginSkirmish?: () => void;
  /** The "full game unlock" purchase. */
  purchases?: PurchasesView;
  /** Google Play Games cloud saves (the Play build only). */
  cloudSave?: CloudSaveView;
  getBaseView?: () => import('./basePanel').BaseView;
  baseAction?: (action: import('./basePanel').BaseAction) => boolean;
}

export interface PurchasesView {
  isUnlocked(): boolean;
  /** False on the web: the full game is bought in the Android app. */
  canPurchase(): boolean;
  price(): Promise<string | null>;
  buy(): Promise<{ status: string; message: string }>;
  restore(): Promise<{ status: string; message: string }>;
  subscribe(listener: () => void): () => void;
}

export interface CloudSaveView {
  /** False on the web and in a build without Play Games set up: the button is left out. */
  available(): boolean;
  state(): 'unavailable' | 'signedOut' | 'signingIn' | 'syncing' | 'synced' | 'offline';
  playerName(): string | undefined;
  signIn(): Promise<void>;
  syncNow(): Promise<void>;
  subscribe(listener: () => void): () => void;
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
  title: ['campaignSelect', 'skirmishSetup', 'settings', 'credits', 'help', 'saveSlots'],
  campaignSelect: ['title', 'missionSelect'],
  missionSelect: ['campaignSelect', 'briefing', 'unlock'],
  briefing: ['missionSelect', 'loading'],
  skirmishSetup: ['title', 'loading', 'unlock'],
  loading: ['inGame', 'title'],
  inGame: ['pause', 'objectives', 'help', 'bugReport', 'saveSlots', 'recovery', 'results', 'title'],
  pause: ['settings', 'bugReport', 'saveSlots', 'help', 'objectives', 'loading', 'title', 'inGame'],
  settings: ['title', 'pause', 'inGame'],
  help: ['title', 'inGame'],
  objectives: ['inGame'],
  results: ['title', 'missionSelect', 'briefing', 'loading', 'unlock'],
  credits: ['title'],
  bugReport: ['title', 'inGame', 'pause'],
  saveSlots: ['pause', 'inGame', 'title'],
  recovery: ['inGame', 'title'],
  unlock: ['missionSelect', 'skirmishSetup', 'results', 'title'],
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
  // Over a match Save / Load is an overlay and Back pops it; from the title it is a screen of its own.
  saveSlots: 'title',
  recovery: 'inGame',
  pause: 'inGame',
  unlock: 'title',
};

/** Screens whose Back returns to the screen that opened them rather than to a fixed parent. */
const RETURN_TO_OPENER: ReadonlySet<ScreenId> = new Set<ScreenId>(['unlock']);

/** Overlays drawn over the screen below rather than replacing it (the battlefield behind the pause card). */
const SEE_THROUGH_OVERLAYS: ReadonlySet<ScreenId> = new Set<ScreenId>(['pause']);

export class ScreenRouter {
  private readonly root: HTMLElement;
  private readonly screens: Record<ScreenId, ScreenModule>;
  private readonly contextFactory: (router: ScreenRouter) => ScreenContext;
  private context: ScreenContext | null = null;
  private base: MountedScreen | null = null;
  private overlays: MountedScreen[] = [];
  /** The base screen a RETURN_TO_OPENER screen was opened from. */
  private opener: ScreenId | null = null;

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
      if (RETURN_TO_OPENER.has(id)) {
        this.opener = this.base?.id ?? null;
      }
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
    const opener = RETURN_TO_OPENER.has(this.base.id) ? this.opener : null;
    const parent = opener && this.canGo(this.base.id, opener) ? opener : PARENT[this.base.id];
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
      if (SEE_THROUGH_OVERLAYS.has(id)) {
        // The screen below stays in view (dimmed by the overlay) but takes no input or focus.
        top.el.inert = true;
      } else {
        top.el.style.visibility = 'hidden';
      }
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
      top.el.inert = false;
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
