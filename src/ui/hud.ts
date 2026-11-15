import { missionMarkers } from '../sim/triggers';
import { isHostile } from '../sim/diplomacy';
import { cellState } from '../sim/vision';
import { heightAt } from '../sim/map';
import { UNIT_CAP } from '../sim/tuning';
import { isUpgradeAvailable } from '../sim/research';
import type { WorldState } from '../sim/types';
import { button } from './controls';
import { BasePanel, type BaseAction, type BaseView } from './basePanel';
import { BuildDrawer } from './buildDrawer';
import { QueueStrip } from './queueStrip';
import { ensureIconSprite, icon, resourceIcon, type IconName } from './icons';
import type { AlertSnapshot } from './alerts';
import type {
  BuildItemView,
  DropQueueView,
  HudHandle,
  HudSnapshot,
  KitView,
  ResearchQueueView,
  PlacementView,
  WorkerActions,
} from './router';
import { SELECT_HINT_TEXT } from './textLimits';

export interface HudCamera {
  targetX: number;
  targetZ: number;
  distance: number;
  yaw: number;
  pitch: number;
}

export interface HudContext {
  openObjectives?: () => void;
  getWorld: () => WorldState;
  getSelection: () => number[];
  setSelection: (ids: number[]) => void;
  sendCommand: (command: unknown) => boolean;
  getCamera: () => HudCamera;
  cameraFootprint: () => Array<{ x: number; z: number }>;
  setCameraTarget: (x: number, z: number) => void;
  isLeftHanded: () => boolean;
  setLeftHanded: (value: boolean) => void;
  isQueueMode: () => boolean;
  setQueueMode: (value: boolean) => void;
  isAttackMoveArmed: () => boolean;
  setAttackMoveArmed: (value: boolean) => void;
  assignGroup: (group: number) => void;
  selectGroup: (group: number) => void;
  centerGroup: (group: number) => void;
  groupMembers: (group: number) => number[];
  pause: () => void;
  getBuildItems?: () => BuildItemView[];
  getOwnPads?: () => Array<{ id: number; x: number; z: number }>;
  getSelectedPadId?: () => number | null;
  setSelectedPad?: (id: number) => void;
  buyItem?: (itemId: string) => boolean;
  getDropQueue?: () => DropQueueView[];
  getResearchQueue?: () => ResearchQueueView[];
  cancelOrder?: (orderId: number) => void;
  getKits?: () => KitView[];
  startPlacement?: (kitId: number) => boolean;
  getPlacement?: () => PlacementView | null;
  confirmPlacement?: () => boolean;
  cancelPlacement?: () => void;
  getWorkerActions?: () => WorkerActions;
  salvageSelected?: () => void;
  getBaseView?: () => BaseView;
  baseAction?: (action: BaseAction) => boolean;
  /** Recent alerts (newest last) for the bell and its unread badge. */
  getAlerts?: () => AlertSnapshot[];
  simSpeed?: () => number;
  cycleSpeed?: () => void;
  thumbnail?: (kind: 'unit' | 'structure', typeId: string) => string | null;
  itemName?: (typeId: string) => string;
  itemRole?: (typeId: string) => string | undefined;
  isSelectMode?: () => boolean;
  setSelectMode?: (value: boolean) => void;
}

const MINIMAP_SIZE = 240;
const MINIMAP_MARGIN = 4;
const MINIMAP_INTERVAL_MS = 200;
/** Group tiles: "All army", then groups 1 to 4. */
const GROUP_COUNT = 4;
/** How long a fresh alert pings on the minimap. */
const PING_MS = 3000;

interface WorldPoint {
  x: number;
  z: number;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function heightColour(t: number): string {
  if (t < 0.25) {
    return `rgb(${52 + t * 80}, ${82 + t * 90}, ${46 + t * 30})`;
  }
  if (t < 0.6) {
    return `rgb(${95 + t * 60}, ${118 + t * 45}, ${63 + t * 28})`;
  }
  if (t < 0.82) {
    return `rgb(${156 + t * 30}, ${142 + t * 24}, ${101 + t * 18})`;
  }
  return `rgb(${132 + t * 40}, ${132 + t * 34}, ${132 + t * 30})`;
}

function clipAlongX(polygon: readonly WorldPoint[], limit: number, keepGreater: boolean): WorldPoint[] {
  const result: WorldPoint[] = [];
  const inside = (point: WorldPoint): boolean =>
    keepGreater ? point.x >= limit : point.x <= limit;
  for (let index = 0; index < polygon.length; index += 1) {
    const current = polygon[index];
    const next = polygon[(index + 1) % polygon.length];
    if (!current || !next) {
      continue;
    }
    const currentInside = inside(current);
    const nextInside = inside(next);
    if (currentInside) {
      result.push(current);
    }
    if (currentInside !== nextInside && next.x !== current.x) {
      const t = (limit - current.x) / (next.x - current.x);
      result.push({ x: limit, z: current.z + (next.z - current.z) * t });
    }
  }
  return result;
}

function clipAlongZ(polygon: readonly WorldPoint[], limit: number, keepGreater: boolean): WorldPoint[] {
  const result: WorldPoint[] = [];
  const inside = (point: WorldPoint): boolean =>
    keepGreater ? point.z >= limit : point.z <= limit;
  for (let index = 0; index < polygon.length; index += 1) {
    const current = polygon[index];
    const next = polygon[(index + 1) % polygon.length];
    if (!current || !next) {
      continue;
    }
    const currentInside = inside(current);
    const nextInside = inside(next);
    if (currentInside) {
      result.push(current);
    }
    if (currentInside !== nextInside && next.z !== current.z) {
      const t = (limit - current.z) / (next.z - current.z);
      result.push({ x: current.x + (next.x - current.x) * t, z: limit });
    }
  }
  return result;
}

function clipToMapSquare(points: readonly WorldPoint[], half: number): WorldPoint[] {
  let polygon: WorldPoint[] = points.map((point) => ({ x: point.x, z: point.z }));
  polygon = clipAlongX(polygon, -half, true);
  polygon = clipAlongX(polygon, half, false);
  polygon = clipAlongZ(polygon, -half, true);
  polygon = clipAlongZ(polygon, half, false);
  return polygon;
}

const WORKER_STAGE_TEXT: Record<string, string> = {
  toDeposit: 'Driving to the field',
  digging: 'Mining',
  toPad: 'Delivering to pad',
  toStation: 'Driving to station',
  loading: 'Loading',
  unloading: 'Unloading',
  waiting: 'Waiting in line',
};

const ORDER_TEXT: Record<string, string> = {
  idle: 'Idle',
  move: 'Moving',
  attackMove: 'Attack-moving',
  attack: 'Attacking',
};

const ROLE_TEXT: Record<string, string> = {
  scout: 'Scout',
  tank: 'Tank',
  artillery: 'Artillery',
  support: 'Support',
  air: 'Aircraft',
  structure: 'Packed structure',
};

const ROLE_PLURAL: Record<string, [string, string]> = {
  tank: ['tank', 'tanks'],
  scout: ['scout', 'scouts'],
  air: ['aircraft', 'aircraft'],
  artillery: ['gun', 'guns'],
  worker: ['worker', 'workers'],
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function hpColour(fraction: number): string {
  return fraction > 0.6 ? 'var(--green)' : fraction > 0.3 ? 'var(--amber)' : 'var(--red)';
}

/** Command button: line icon over a caption, accessible name = caption. */
function commandButton(name: string, label: string, iconName: IconName, onClick: () => void): HTMLButtonElement {
  const node = button('inGame', name, label, onClick);
  node.classList.add('hud-cmd');
  node.setAttribute('aria-label', label);
  node.replaceChildren(icon(iconName), el('span', 'hud-cmd-label', label));
  return node;
}

interface SelectionKinds {
  any: boolean;
  combat: boolean;
  air: boolean;
}

export class Hud implements HudHandle {
  private readonly root: HTMLDivElement;
  private readonly ctx: HudContext;
  private readonly oreValue: HTMLSpanElement;
  private readonly metalValue: HTMLSpanElement;
  private readonly workersValue: HTMLSpanElement;
  private readonly unitsValue: HTMLSpanElement;
  private readonly queueStrip: QueueStrip;
  private readonly objectiveLine: HTMLButtonElement;
  private readonly objectiveText: HTMLSpanElement;
  private readonly selectModeButton: HTMLButtonElement;
  private readonly allArmyButton: HTMLButtonElement;
  private readonly minimap: HTMLCanvasElement;
  private readonly selectionPanel: HTMLDivElement;
  private readonly selectionBody: HTMLDivElement;
  private selectionSignature = '';
  private readonly selectionRefs = new Map<number, { fill: HTMLElement; img: HTMLElement }>();
  private singleRefs: {
    hp: HTMLElement;
    status: HTMLElement;
    cargo: HTMLElement;
    cargoFill: HTMLElement;
    cargoText: HTMLElement;
    img: HTMLElement;
  } | null = null;
  private readonly groupsStrip: HTMLDivElement;
  private readonly commandBar: HTMLDivElement;
  private readonly attackButton: HTMLButtonElement;
  private readonly holdButton: HTMLButtonElement;
  private readonly airButton: HTMLButtonElement;
  private readonly airInfo: HTMLSpanElement;
  private messageSeq = 0;
  private messageUntil = 0;
  private readonly stopButton: HTMLButtonElement;
  private readonly queueButton: HTMLButtonElement;
  private readonly mineButton: HTMLButtonElement;
  private readonly assignButton: HTMLButtonElement;
  private readonly salvageButton: HTMLButtonElement;
  private readonly deployButton: HTMLButtonElement;
  private readonly upgradeButton: HTMLButtonElement;
  private readonly buildDrawer: BuildDrawer;
  private readonly basePanel: BasePanel;
  private baseOpen = false;
  private readonly placementBar: HTMLDivElement;
  private readonly confirmPlacement: HTMLButtonElement;
  private readonly cancelPlacement: HTMLButtonElement;
  private readonly groupButtons: HTMLButtonElement[] = [];
  private readonly timer: number;
  private buildMenuOpen = false;
  private minimapRedraws = 0;
  private lastFootprint: Array<{ x: number; z: number }> = [];
  private minimapPointer: number | null = null;
  private lastGroupTap: { group: number; time: number } | null = null;
  private lastAllTap = 0;

  constructor(host: HTMLElement, ctx: HudContext) {
    this.ctx = ctx;
    ensureIconSprite();
    this.root = document.createElement('div');
    this.root.className = 'hud-shell';
    this.root.dataset.hudShell = 'true';

    // Top-left: resources, workers and unit count.
    const resources = el('div', 'hud-resbar panel');
    resources.dataset.hudItem = 'resources';
    const stat = (glyph: SVGSVGElement, title: string): HTMLSpanElement => {
      const wrap = el('span', 'hud-res');
      wrap.title = title;
      const value = el('span', 'hud-res-value', '0');
      wrap.append(glyph, value);
      resources.append(wrap);
      return value;
    };
    this.oreValue = stat(resourceIcon('ore', 16), 'Ore');
    this.metalValue = stat(resourceIcon('metal', 16), 'Metal');
    this.workersValue = stat(icon('worker', 'hud-res-ico'), 'Workers');
    this.unitsValue = stat(icon('unit', 'hud-res-ico'), 'Units');

    // Top-right: pause. The clock and game speed live in the pause menu.
    const corner = el('div', 'hud-corner');
    corner.dataset.hudItem = 'corner';
    const pause = button('inGame', 'pause', 'Pause', () => {
      ctx.pause();
    });
    pause.classList.add('hud-icon-button');
    pause.setAttribute('aria-label', 'Pause');
    pause.replaceChildren(icon('pause'));
    corner.append(pause);

    // Top-centre: the build queue, and under it one line for mission messages and the current
    // objective (tap it for the full list).
    this.queueStrip = new QueueStrip({
      getDropQueue: () => this.ctx.getDropQueue?.() ?? [],
      getKits: () => this.ctx.getKits?.() ?? [],
      getResearch: () => this.ctx.getResearchQueue?.() ?? [],
      cancelOrder: (orderId) => {
        this.ctx.cancelOrder?.(orderId);
      },
      cancelResearch: () => {
        this.ctx.baseAction?.({ kind: 'cancelResearch' });
      },
      research: (nodeId) => this.ctx.baseAction?.({ kind: 'research', nodeId }) ?? false,
      buyItem: (itemId) => this.ctx.buyItem?.(itemId) ?? false,
      startPlacement: (kitId) => {
        const started = this.ctx.startPlacement?.(kitId) ?? false;
        if (started) {
          this.setBuildMenu(false);
        }
        return started;
      },
      itemCost: (itemId) => {
        const item = (this.ctx.getBuildItems?.() ?? []).find((entry) => entry.id === itemId);
        return item ? { ore: item.ore, metal: item.metal } : null;
      },
      thumbnail: (kind, typeId) => this.ctx.thumbnail?.(kind, typeId) ?? null,
      changed: () => {
        this.refresh();
      },
    });
    this.objectiveLine = button('inGame', 'objectives', 'Objectives', () => {
      ctx.openObjectives?.();
    });
    this.objectiveLine.classList.add('hud-objective');
    // The line shows the objective or a message; its name stays "Objectives" (it opens them).
    this.objectiveLine.setAttribute('aria-label', 'Objectives');
    this.objectiveLine.dataset.hudItem = 'objective';
    this.objectiveText = el('span', 'hud-objective-text');
    this.objectiveLine.replaceChildren(icon('list'), this.objectiveText);
    this.objectiveLine.hidden = true;

    // Left edge: select mode.
    this.selectModeButton = button('inGame', 'selectMode', 'Select', () => {
      this.ctx.setSelectMode?.(!(this.ctx.isSelectMode?.() ?? false));
      this.refresh();
    });
    this.selectModeButton.classList.add('hud-select-mode');
    this.selectModeButton.dataset.hudItem = 'selectMode';
    this.selectModeButton.setAttribute('aria-label', 'Select mode');
    this.selectModeButton.replaceChildren(icon('group'), el('span', 'hud-cmd-label', 'Select'));

    // Bottom: group tiles. "All army" first, then groups 1 to 4. Tap selects, a second tap
    // centres the camera, holding saves the current selection into the tile.
    this.groupsStrip = el('div', 'hud-groups');
    this.groupsStrip.dataset.hudItem = 'groups';
    this.allArmyButton = button('inGame', 'groupAll', 'All army', () => {
      this.selectAllArmy();
    });
    this.allArmyButton.classList.add('hud-group-button', 'all');
    this.allArmyButton.setAttribute('aria-label', 'All army');
    this.allArmyButton.replaceChildren(el('b', 'group-number', 'All'), el('span', 'group-caption', 'army'));
    this.groupsStrip.append(this.allArmyButton);
    for (let group = 1; group <= GROUP_COUNT; group += 1) {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'hud-group-button';
      element.dataset.controlId = `inGame.group${group}`;
      element.dataset.group = String(group);
      element.setAttribute('aria-label', `Group ${group}`);
      element.append(el('b', 'group-number', String(group)), el('span', 'group-caption', 'hold to save'));
      this.attachGroupHandlers(element, group);
      this.groupButtons.push(element);
      this.groupsStrip.append(element);
    }

    // Bottom-left: minimap.
    const minimapWrap = el('div', 'hud-minimap panel');
    minimapWrap.dataset.hudItem = 'minimap';
    this.minimap = el('canvas', 'minimap-canvas');
    this.minimap.width = MINIMAP_SIZE;
    this.minimap.height = MINIMAP_SIZE;
    this.minimap.setAttribute('aria-label', 'Minimap');
    minimapWrap.append(this.minimap);
    this.minimap.addEventListener('pointerdown', this.onMinimapDown);
    this.minimap.addEventListener('pointermove', this.onMinimapMove);
    this.minimap.addEventListener('pointerup', this.onMinimapUp);
    this.minimap.addEventListener('pointercancel', this.onMinimapUp);
    this.minimap.addEventListener('contextmenu', this.onMinimapContext);

    // Right: command grid with only the commands the selection can use.
    this.commandBar = el('div', 'hud-commandbar');
    this.commandBar.dataset.hudItem = 'commandbar';
    this.attackButton = commandButton('attackMove', 'Attack', 'attack', () => {
      ctx.setAttackMoveArmed(!ctx.isAttackMoveArmed());
      this.refresh();
    });
    this.mineButton = commandButton('mine', 'Mine', 'mine', () => {
      this.refresh();
    });
    this.assignButton = commandButton('assign', 'Haul', 'haul', () => {
      this.refresh();
    });
    this.stopButton = commandButton('stop', 'Stop', 'stop', () => {
      this.issueStop();
    });
    this.holdButton = commandButton('hold', 'Hold', 'hold', () => {
      this.issueHold();
    });
    this.queueButton = commandButton('queue', 'Waypoints', 'way', () => {
      ctx.setQueueMode(!ctx.isQueueMode());
      this.refresh();
    });
    this.salvageButton = commandButton('salvage', 'Salvage', 'salvage', () => {
      ctx.salvageSelected?.();
      this.refresh();
    });
    this.deployButton = commandButton('deploy', 'Deploy', 'deploy', () => {
      this.issueDeploy();
    });
    // Researched upgrades (armour, fire rate, stealth) for the selected vehicles: opens Base with
    // the vehicles listed, each upgrade bought per vehicle.
    this.upgradeButton = commandButton('upgrade', 'Upgrade', 'star', () => {
      this.setBase(true);
    });
    this.airButton = commandButton('air', 'Launch', 'air', () => {
      this.issueAir();
    });
    this.airButton.hidden = true;
    this.airInfo = el('span', 'hud-airinfo');
    this.airInfo.hidden = true;
    this.commandBar.append(
      this.airInfo,
      this.attackButton,
      this.mineButton,
      this.assignButton,
      this.stopButton,
      this.holdButton,
      this.queueButton,
      this.salvageButton,
      this.deployButton,
      this.upgradeButton,
      this.airButton,
    );

    // Bottom-left, beside the minimap: selection panel (portraits, or one unit's details).
    this.selectionPanel = el('div', 'hud-selection panel');
    this.selectionPanel.dataset.hudItem = 'selection';
    this.selectionBody = el('div', 'hud-selection-body');
    const deselect = button('inGame', 'deselect', 'Deselect', () => {
      ctx.setSelection([]);
    });
    deselect.classList.add('hud-deselect');
    deselect.setAttribute('aria-label', 'Deselect');
    deselect.replaceChildren(icon('x'));
    this.selectionPanel.append(this.selectionBody, deselect);

    this.buildDrawer = new BuildDrawer({
      getBuildItems: () => this.ctx.getBuildItems?.() ?? [],
      getOwnPads: () => this.ctx.getOwnPads?.() ?? [],
      getSelectedPadId: () => this.ctx.getSelectedPadId?.() ?? null,
      setSelectedPad: (id) => {
        this.ctx.setSelectedPad?.(id);
      },
      buyItem: (itemId) => this.ctx.buyItem?.(itemId) ?? false,
      getDropQueue: () => this.ctx.getDropQueue?.() ?? [],
      cancelOrder: (orderId) => {
        this.ctx.cancelOrder?.(orderId);
      },
      getKits: () => this.ctx.getKits?.() ?? [],
      startPlacement: (kitId) => this.ctx.startPlacement?.(kitId) ?? false,
      baseAction: (action) => this.ctx.baseAction?.(action) ?? false,
      getResources: () => {
        const stats = this.ctx.getWorld().resources.find((item) => item.player === 1);
        return { ore: stats?.ore ?? 0, metal: stats?.metal ?? 0 };
      },
      thumbnail: (kind, typeId) => this.ctx.thumbnail?.(kind, typeId) ?? null,
      close: () => {
        this.setBuildMenu(false);
      },
    });

    this.basePanel = new BasePanel(
      {
        getView: () => this.baseView(),
        act: (action) => this.ctx.baseAction?.(action) ?? false,
      },
      () => {
        this.setBase(false);
      },
    );
    this.basePanel.element.classList.add('hud-drawer');

    this.placementBar = el('div', 'hud-placement panel');
    this.placementBar.dataset.hudItem = 'placementBar';
    this.confirmPlacement = button('inGame', 'placeConfirm', 'Confirm', () => {
      this.ctx.confirmPlacement?.();
      this.refresh();
    });
    this.confirmPlacement.classList.add('primary');
    this.cancelPlacement = button('inGame', 'placeCancel', 'Cancel', () => {
      this.ctx.cancelPlacement?.();
      this.refresh();
    });
    this.placementBar.append(this.confirmPlacement, this.cancelPlacement);

    this.root.append(
      resources,
      this.queueStrip.element,
      this.objectiveLine,
      corner,
      this.selectModeButton,
      this.groupsStrip,
      minimapWrap,
      this.selectionPanel,
      this.commandBar,
      this.buildDrawer.element,
      this.basePanel.element,
      this.placementBar,
    );
    host.append(this.root);

    this.showSelectHintOnce();
    this.update();
    this.timer = window.setInterval(() => {
      this.update();
    }, MINIMAP_INTERVAL_MS);
  }

  /** A one-time hint for the selection gestures, beside the select mode button. */
  private showSelectHintOnce(): void {
    const key = 'tc.hint.select';
    // Automated browsers (tests) skip it, so it never lands under a scripted tap.
    if (typeof navigator !== 'undefined' && navigator.webdriver) {
      return;
    }
    try {
      if (window.localStorage.getItem(key)) {
        return;
      }
      window.localStorage.setItem(key, '1');
    } catch {
      return;
    }
    const hint = el('button', 'hud-hint', SELECT_HINT_TEXT);
    hint.type = 'button';
    hint.dataset.hudItem = 'selectHint';
    const close = (): void => {
      hint.remove();
    };
    hint.addEventListener('click', close);
    window.setTimeout(close, 9000);
    this.root.append(hint);
  }

  snapshot(): HudSnapshot {
    const world = this.ctx.getWorld();
    const selection = this.ctx.getSelection();
    const stats = world.resources.find((item) => item.player === 1);
    const ownUnits = world.units.filter((unit) => unit.owner === 1 && unit.hp > 0);
    const workerCount = ownUnits.filter((unit) => {
      const type = world.unitTypes.get(unit.typeId);
      return type?.workerKind !== null && type?.workerKind !== undefined;
    }).length;
    return {
      leftHanded: this.ctx.isLeftHanded(),
      groupsOpen: false,
      selectMode: this.ctx.isSelectMode?.() ?? false,
      queueMode: this.ctx.isQueueMode(),
      attackMoveArmed: this.ctx.isAttackMoveArmed(),
      selectedCount: selection.length,
      ownUnits: ownUnits.length,
      enemyUnits: world.units.filter((unit) => isHostile(world, 1, unit.owner) && unit.hp > 0).length,
      minimapFootprint: this.lastFootprint.map((point) => ({ x: point.x, z: point.z })),
      minimapRedraws: this.minimapRedraws,
      commandButtonsDisabled: this.attackButton.disabled,
      buildMenuOpen: this.buildMenuOpen,
      baseOpen: this.baseOpen,
      ore: stats?.ore ?? 0,
      metal: stats?.metal ?? 0,
      workers: workerCount,
      unitCount: ownUnits.length,
      unitCap: UNIT_CAP,
      queue: this.ctx.getDropQueue?.() ?? [],
      research: this.ctx.getResearchQueue?.() ?? [],
      kits: this.ctx.getKits?.() ?? [],
      selectedPadId: this.ctx.getSelectedPadId?.() ?? null,
      placementActive: this.ctx.getPlacement?.() !== null,
    };
  }

  dispose(): void {
    window.clearInterval(this.timer);
    this.root.remove();
  }

  private baseView(): BaseView {
    return (
      this.ctx.getBaseView?.() ?? {
        researchBusy: false,
        nodes: [],
        structures: [],
        units: [],
        ore: 0,
        metal: 0,
      }
    );
  }

  private selectionKinds(selection: readonly number[]): SelectionKinds {
    const world = this.ctx.getWorld();
    const kinds: SelectionKinds = { any: false, combat: false, air: false };
    for (const id of selection) {
      const unit = world.units.find((item) => item.id === id);
      if (!unit || unit.hp <= 0) {
        continue;
      }
      kinds.any = true;
      const type = world.unitTypes.get(unit.typeId);
      // Packed buildings carry no weapon: they only move, stop and unpack.
      if (!type?.workerKind && !type?.deploysTo) {
        kinds.combat = true;
      }
      if (unit.air) {
        kinds.air = true;
      }
    }
    return kinds;
  }

  refresh(): void {
    const selection = this.ctx.getSelection();
    const hasSelection = selection.length > 0;
    const kinds = this.selectionKinds(selection);
    const actions: WorkerActions = this.ctx.getWorkerActions?.() ?? {
      canMine: false,
      canAssign: false,
      canSalvage: false,
    };
    // Only the commands this selection can use are shown; hidden ones are also disabled.
    const show = (node: HTMLButtonElement, visible: boolean): void => {
      node.hidden = !visible;
      node.disabled = !visible;
    };
    const combat = hasSelection && (kinds.combat || !kinds.any);
    show(this.attackButton, combat);
    show(this.holdButton, combat);
    show(this.queueButton, combat);
    show(this.stopButton, hasSelection);
    show(this.mineButton, actions.canMine);
    show(this.assignButton, actions.canAssign);
    show(this.salvageButton, actions.canSalvage);
    show(this.deployButton, hasSelection && this.deployableSelected(selection).length > 0);
    show(this.upgradeButton, hasSelection && this.canUpgrade(selection));
    this.refreshAir(selection);
    this.refreshMission();
    this.queueStrip.refresh();
    this.queueButton.classList.toggle('active', this.ctx.isQueueMode());
    this.attackButton.classList.toggle('active', this.ctx.isAttackMoveArmed());
    const selectMode = this.ctx.isSelectMode?.() ?? false;
    this.selectModeButton.classList.toggle('active', selectMode);
    this.selectModeButton.setAttribute('aria-pressed', selectMode ? 'true' : 'false');
    this.root.classList.toggle('select-mode', selectMode);
    this.commandBar.hidden = !hasSelection;
    this.root.classList.toggle('left-handed', this.ctx.isLeftHanded());
    // The alert line lives outside the HUD shell; it mirrors through the root element.
    document.documentElement.dataset.hand = this.ctx.isLeftHanded() ? 'left' : 'right';
    this.root.classList.toggle('build-open', this.buildMenuOpen);
    this.root.classList.toggle('base-open', this.baseOpen);
    const placing = this.ctx.getPlacement?.() !== null;
    this.root.classList.toggle('placing', placing);
    this.placementBar.classList.toggle('open', placing);
    this.refreshGroups(selection);
    this.buildDrawer.refresh();
    this.basePanel.refresh();
  }

  private update(): void {
    const world = this.ctx.getWorld();
    this.refreshMission();
    const selection = this.ctx.getSelection();
    const stats = world.resources.find((item) => item.player === 1);
    const ownUnits = world.units.filter((unit) => unit.owner === 1 && unit.hp > 0);
    const workers = ownUnits.filter((unit) => {
      const type = world.unitTypes.get(unit.typeId);
      return type?.workerKind !== null && type?.workerKind !== undefined;
    }).length;
    this.oreValue.textContent = String(stats?.ore ?? 0);
    this.metalValue.textContent = String(stats?.metal ?? 0);
    this.workersValue.textContent = String(workers);
    // Packed buildings on their way don't count toward the unit cap, so they aren't shown here.
    const army = ownUnits.filter((unit) => !world.unitTypes.get(unit.typeId)?.deploysTo).length;
    this.unitsValue.replaceChildren(String(army), el('small', 'hud-res-cap', `/${UNIT_CAP}`));
    this.refresh();
    this.renderSelection(world, selection);
    this.drawMinimap(world);
  }

  private refreshGroups(selection: readonly number[]): void {
    const world = this.ctx.getWorld();
    const selected = selection.slice().sort((a, b) => a - b);
    for (const element of this.groupButtons) {
      const group = Number(element.dataset.group ?? '0');
      const members = this.ctx
        .groupMembers(group)
        .filter((id) => world.units.some((unit) => unit.id === id && unit.hp > 0))
        .sort((a, b) => a - b);
      const same =
        members.length > 0 &&
        members.length === selected.length &&
        members.every((id, index) => id === selected[index]);
      element.classList.toggle('selected', same);
      // An empty tile is a faint outline that says how to fill it.
      element.classList.toggle('empty', members.length === 0);
      const caption = element.querySelector('.group-caption');
      if (caption) {
        const text = members.length === 0 ? 'hold to save' : this.groupCaption(world, members);
        if (caption.textContent !== text) {
          caption.textContent = text;
        }
      }
    }
  }

  /** Every own combat unit (miners and haulers stay out of it). */
  private armyIds(): number[] {
    const world = this.ctx.getWorld();
    return world.units
      .filter((unit) => unit.owner === 1 && unit.hp > 0 && !world.unitTypes.get(unit.typeId)?.workerKind)
      .map((unit) => unit.id);
  }

  private selectAllArmy(): void {
    const ids = this.armyIds();
    const now = performance.now();
    this.ctx.setSelection(ids);
    // A second tap soon after centres the camera on the army.
    if (now - this.lastAllTap < 600 && ids.length > 0) {
      const world = this.ctx.getWorld();
      const units = world.units.filter((unit) => ids.includes(unit.id));
      this.ctx.setCameraTarget(
        units.reduce((sum, unit) => sum + unit.x, 0) / units.length,
        units.reduce((sum, unit) => sum + unit.z, 0) / units.length,
      );
      this.lastAllTap = 0;
    } else {
      this.lastAllTap = now;
    }
    this.refresh();
  }

  private groupCaption(world: WorldState, members: readonly number[]): string {
    const roles = new Set<string>();
    for (const id of members) {
      const unit = world.units.find((item) => item.id === id);
      const role = unit ? world.unitTypes.get(unit.typeId)?.role : undefined;
      roles.add(role ?? 'unit');
    }
    const n = members.length;
    const only = roles.size === 1 ? [...roles][0] : undefined;
    const words = (only ? ROLE_PLURAL[only] : undefined) ?? ['unit', 'units'];
    return `${n} ${n === 1 ? words[0] : words[1]}`;
  }

  /** Selected units that can unfold into a structure right now. */
  /** True when a selected vehicle has an upgrade it doesn't own yet and its research is done. */
  private canUpgrade(selection: readonly number[]): boolean {
    const world = this.ctx.getWorld();
    return selection.some((id) => {
      const unit = world.units.find((item) => item.id === id && item.owner === 1 && item.hp > 0);
      const kinds = unit ? (world.unitTypes.get(unit.typeId)?.upgrades ?? []) : [];
      return kinds.some(
        (kind) =>
          (kind === 'fireRate' || kind === 'armor' || kind === 'stealth') &&
          !unit?.upgrades.includes(kind) &&
          isUpgradeAvailable(world, 1, kind),
      );
    });
  }

  private deployableSelected(selection: readonly number[]): number[] {
    // Cheap check first: the full base view is only built when a selected unit
    // is of a type that unfolds into a structure.
    const world = this.ctx.getWorld();
    const candidate = selection.some((id) => {
      const unit = world.units.find((item) => item.id === id);
      return unit ? Boolean(world.unitTypes.get(unit.typeId)?.deploysTo) : false;
    });
    if (!candidate) {
      return [];
    }
    const units = this.baseView().units;
    return selection.filter((id) => units.some((unit) => unit.id === id && unit.canDeploy));
  }

  private issueDeploy(): void {
    for (const unitId of this.deployableSelected(this.ctx.getSelection())) {
      this.ctx.baseAction?.({ kind: 'deploy', unitId });
    }
    this.refresh();
  }

  /** Tap on one of your structures: the landing pad opens Build, anything else opens Base. */
  openForStructure(structure: { id: number; owner: number; kind: string }): boolean {
    if (structure.owner !== 1) {
      return false;
    }
    this.ctx.setSelection([]);
    if (structure.kind === 'pad') {
      this.ctx.setSelectedPad?.(structure.id);
      this.setBuildMenu(true);
    } else {
      this.setBase(true);
    }
    return true;
  }

  private setBase(open: boolean): void {
    this.baseOpen = open;
    if (open) {
      this.buildMenuOpen = false;
      this.buildDrawer.setOpen(false);
    }
    this.basePanel.setOpen(open);
    this.refresh();
  }

  private setBuildMenu(open: boolean): void {
    if (open) {
      this.baseOpen = false;
      this.basePanel.setOpen(false);
    }
    this.buildMenuOpen = open;
    this.buildDrawer.setOpen(open);
    this.root.classList.toggle('build-open', open);
    this.refresh();
  }

  private unitLabel(typeId: string): string {
    return this.ctx.itemName?.(typeId) ?? typeId.split('.').pop() ?? typeId;
  }

  private portrait(className: string, typeId: string): HTMLSpanElement {
    const slot = el('span', className);
    const url = this.ctx.thumbnail?.('unit', typeId) ?? null;
    if (url) {
      slot.style.backgroundImage = `url(${url})`;
      slot.dataset.loaded = 'true';
    } else {
      slot.append(icon('unit', 'thumb-fallback'));
    }
    slot.dataset.typeId = typeId;
    return slot;
  }

  private fillPortrait(slot: HTMLElement): void {
    if (slot.dataset.loaded === 'true') {
      return;
    }
    const typeId = slot.dataset.typeId ?? '';
    const url = this.ctx.thumbnail?.('unit', typeId) ?? null;
    if (url) {
      slot.replaceChildren();
      slot.style.backgroundImage = `url(${url})`;
      slot.dataset.loaded = 'true';
    }
  }

  /** How many portraits fit between the minimap and the right-hand dock. */
  private portraitCapacity(): number {
    const width = this.root.clientWidth || window.innerWidth;
    // Between the minimap and the group tiles, less the count and the deselect button.
    const available = width - 156 - 142 - 316 - 8 - 70 - 52;
    return Math.max(1, Math.floor(available / 52));
  }

  private renderSelection(world: WorldState, selection: number[]): void {
    const alive = selection
      .map((id) => world.units.find((item) => item.id === id))
      .filter((unit): unit is NonNullable<typeof unit> => unit !== undefined);
    this.selectionPanel.hidden = selection.length === 0;
    if (selection.length === 0) {
      if (this.selectionSignature !== '') {
        this.selectionBody.replaceChildren();
        this.selectionRefs.clear();
        this.singleRefs = null;
        this.selectionSignature = '';
      }
      return;
    }
    const capacity = this.portraitCapacity();
    const signature = `${alive.length === 1 ? 'one' : 'many'}:${capacity}:${alive.map((unit) => `${unit.id}/${unit.typeId}`).join(',')}`;
    if (signature !== this.selectionSignature) {
      this.selectionSignature = signature;
      this.selectionRefs.clear();
      this.singleRefs = null;
      this.selectionBody.replaceChildren();
      this.selectionPanel.classList.toggle('single', alive.length === 1);
      const only = alive[0];
      if (alive.length === 1 && only) {
        this.buildSingle(world, only);
      } else {
        this.buildMany(alive, capacity);
      }
    }
    // Live values: HP, status line, cargo, late-loading portraits.
    for (const unit of alive) {
      const refs = this.selectionRefs.get(unit.id);
      if (refs) {
        const max = world.unitTypes.get(unit.typeId)?.hp ?? Math.max(1, unit.hp);
        const fraction = clamp01(unit.hp / Math.max(1, max));
        refs.fill.style.width = `${fraction * 100}%`;
        refs.fill.style.background = hpColour(fraction);
        this.fillPortrait(refs.img);
      }
    }
    const only = alive[0];
    if (this.singleRefs && only) {
      this.updateSingle(world, only);
    }
  }

  private buildMany(units: ReadonlyArray<WorldState['units'][number]>, capacity: number): void {
    const count = el('div', 'hud-selection-count');
    count.append(el('b', '', String(units.length)), el('span', '', 'selected'));
    const list = el('div', 'hud-selection-list');
    const shown = units.length > capacity ? capacity - 1 : units.length;
    for (const unit of units) {
      const tile = el('button', 'selection-icon');
      tile.type = 'button';
      tile.dataset.unitId = String(unit.id);
      tile.setAttribute('aria-label', `Select ${this.unitLabel(unit.typeId)} ${unit.id}`);
      const img = this.portrait('selection-thumb', unit.typeId);
      const bar = el('span', 'selection-hp');
      const fill = el('span', 'selection-hp-fill');
      bar.append(fill);
      tile.append(img, bar);
      tile.addEventListener('click', () => {
        this.ctx.setSelection([unit.id]);
      });
      this.selectionRefs.set(unit.id, { fill, img });
      // Tiles past the visible count stay in the DOM (tests and keyboard can reach them) but hidden.
      if (list.childElementCount >= shown) {
        tile.hidden = true;
      }
      list.append(tile);
    }
    if (units.length > shown) {
      list.append(el('span', 'selection-more', `+${units.length - shown}`));
    }
    this.selectionBody.append(count, list);
  }

  private buildSingle(world: WorldState, unit: WorldState['units'][number]): void {
    const type = world.unitTypes.get(unit.typeId);
    const tile = el('button', 'selection-icon selection-single-portrait');
    tile.type = 'button';
    tile.dataset.unitId = String(unit.id);
    tile.setAttribute('aria-label', `Centre on ${this.unitLabel(unit.typeId)}`);
    tile.addEventListener('click', () => {
      this.ctx.setCameraTarget(unit.x, unit.z);
    });
    const img = this.portrait('selection-thumb', unit.typeId);
    const hpBar = el('span', 'selection-hp');
    const hpFill = el('span', 'selection-hp-fill');
    hpBar.append(hpFill);
    tile.append(img, hpBar);
    this.selectionRefs.set(unit.id, { fill: hpFill, img });

    const info = el('div', 'selection-info');
    const role =
      this.ctx.itemRole?.(unit.typeId) ??
      (type?.workerKind === 'oreMiner'
        ? 'Ore miner'
        : type?.workerKind === 'tug'
          ? 'Hauler'
          : (ROLE_TEXT[type?.role ?? ''] ?? 'Unit'));
    const head = el('div', 'selection-head');
    head.append(el('span', 'selection-name', this.unitLabel(unit.typeId)), el('span', 'selection-role', role));
    const hp = el('div', 'bar');
    const hpInner = el('i', '');
    hp.append(hpInner);
    const statusRow = el('div', 'selection-status');
    const status = el('span', '');
    const cargoText = el('span', 'selection-cargo-text');
    statusRow.append(status, cargoText);
    const cargo = el('div', 'bar thin');
    const cargoFill = el('i', '');
    cargo.append(cargoFill);
    info.append(head, hp, statusRow, cargo);
    this.selectionBody.append(tile, info);
    this.singleRefs = { hp: hpInner, status, cargo, cargoFill, cargoText, img };
  }

  private updateSingle(world: WorldState, unit: WorldState['units'][number]): void {
    const refs = this.singleRefs;
    if (!refs) {
      return;
    }
    const type = world.unitTypes.get(unit.typeId);
    const fraction = clamp01(unit.hp / Math.max(1, type?.hp ?? unit.hp));
    refs.hp.style.width = `${fraction * 100}%`;
    refs.hp.style.background = hpColour(fraction);
    let status = unit.stance === 'hold' ? 'Holding position' : (ORDER_TEXT[unit.order.kind] ?? 'Idle');
    let cargo: { have: number; max: number; colour: string; noun: string } | null = null;
    if (unit.job) {
      status = WORKER_STAGE_TEXT[unit.job.stage] ?? status;
      const max = type?.carryCapacity ?? 0;
      if (max > 0) {
        const noun = unit.job.kind === 'oreMiner' ? 'ore' : (unit.job.cargo ?? 'metal');
        cargo = { have: Math.floor(unit.job.load), max, colour: noun === 'ore' ? 'var(--ore)' : '#b8c7d9', noun };
      }
    } else if (type?.workerKind) {
      status = type.workerKind === 'oreMiner' ? 'Idle · tap Mine, then an ore field' : 'Idle · tap Haul, then a station';
    }
    if (unit.air) {
      status = `${unit.air.mode === 'flying' ? 'Flying' : unit.air.mode === 'returning' ? 'Returning' : unit.air.mode === 'rearming' ? 'Rearming' : 'Landed'}`;
      cargo = null;
    }
    if (refs.status.textContent !== status) {
      refs.status.textContent = status;
    }
    refs.cargo.hidden = cargo === null;
    refs.cargoText.textContent = cargo ? `${cargo.have}/${cargo.max} ${cargo.noun}` : '';
    if (cargo) {
      refs.cargoFill.style.width = `${clamp01(cargo.have / cargo.max) * 100}%`;
      refs.cargoFill.style.background = cargo.colour;
    }
  }

  private drawMinimap(world: WorldState): void {
    const context = this.minimap.getContext('2d');
    if (!context) {
      return;
    }
    const width = this.minimap.width;
    const height = this.minimap.height;
    context.clearRect(0, 0, width, height);
    context.fillStyle = '#0b1220';
    context.fillRect(0, 0, width, height);

    const map = world.map;
    const size = Math.min(width, height) - MINIMAP_MARGIN * 2;
    const offX = (width - size) / 2;
    const offY = (height - size) / 2;
    const half = map.size / 2;

    let minHeight = Number.POSITIVE_INFINITY;
    let maxHeight = Number.NEGATIVE_INFINITY;
    for (let index = 0; index < map.heights.length; index += 1) {
      const value = map.heights[index] ?? 0;
      if (value < minHeight) {
        minHeight = value;
      }
      if (value > maxHeight) {
        maxHeight = value;
      }
    }
    const span = Math.max(0.001, maxHeight - minHeight);

    const cells = 32;
    for (let iz = 0; iz < cells; iz += 1) {
      for (let ix = 0; ix < cells; ix += 1) {
        const x = -half + ((ix + 0.5) / cells) * map.size;
        const z = -half + ((iz + 0.5) / cells) * map.size;
        const h = heightAt(map, x, z);
        context.fillStyle = heightColour(clamp01((h - minHeight) / span));
        context.fillRect(
          offX + (ix / cells) * size,
          offY + (iz / cells) * size,
          Math.ceil(size / cells) + 1,
          Math.ceil(size / cells) + 1,
        );
      }
    }

    const toMap = (x: number, z: number): { x: number; y: number } => ({
      x: offX + ((x + half) / map.size) * size,
      y: offY + ((z + half) / map.size) * size,
    });

    for (const deposit of world.deposits) {
      const point = toMap(deposit.x, deposit.z);
      context.fillStyle = deposit.kind === 'ore' ? '#f2c94c' : '#cfd8e3';
      context.fillRect(point.x - 2, point.y - 2, 4, 4);
    }

    if (world.fogEnabled) {
      for (let iz = 0; iz < cells; iz += 1) {
        for (let ix = 0; ix < cells; ix += 1) {
          const state = cellState(
            world,
            1,
            -half + ((ix + 0.5) / cells) * map.size,
            -half + ((iz + 0.5) / cells) * map.size,
          );
          if (state === 2) {
            continue;
          }
          context.fillStyle = state === 0 ? 'rgba(0,0,0,1)' : 'rgba(0,0,0,0.5)';
          context.fillRect(
            offX + (ix / cells) * size,
            offY + (iz / cells) * size,
            Math.ceil(size / cells) + 1,
            Math.ceil(size / cells) + 1,
          );
        }
      }
    }

    for (const structure of world.structures) {
      const point = toMap(structure.x, structure.z);
      const type = world.structureTypes.get(structure.typeId);
      context.fillStyle = structure.owner === 1 ? '#6cf58a' : '#ff5c5c';
      const radius = type?.kind === 'pad' ? 4 : 2.5;
      context.beginPath();
      context.arc(point.x, point.y, radius, 0, Math.PI * 2);
      context.fill();
    }

    const vision = world.fogEnabled ? world.vision.find((item) => item.player === 1) : undefined;
    if (vision) {
      for (const contact of vision.contacts) {
        const point = toMap(contact.x, contact.z);
        context.fillStyle = '#c8c8c8';
        context.beginPath();
        context.arc(point.x, point.y, 3, 0, Math.PI * 2);
        context.fill();
      }
    }

    for (const marker of missionMarkers(world.mission)) {
      const point = toMap(marker.x, marker.z);
      const edge = toMap(marker.x + marker.radius, marker.z);
      context.strokeStyle = '#ffd23f';
      context.lineWidth = 2;
      context.beginPath();
      context.arc(point.x, point.y, Math.max(4, Math.hypot(edge.x - point.x, edge.y - point.y)), 0, Math.PI * 2);
      context.stroke();
    }

    for (const unit of world.units) {
      const point = toMap(unit.x, unit.z);
      context.fillStyle = unit.owner === 1 ? '#4ea3ff' : '#ff5c5c';
      context.beginPath();
      context.arc(point.x, point.y, unit.owner === 1 ? 3 : 2.5, 0, Math.PI * 2);
      context.fill();
    }

    // Fresh alerts ping their spot.
    const now = performance.now();
    for (const alert of this.ctx.getAlerts?.() ?? []) {
      const age = now - alert.at;
      if (age < 0 || age > PING_MS || alert.kind === 'notEnoughResources' || alert.kind === 'researchDone') {
        continue;
      }
      const point = toMap(alert.x, alert.z);
      const phase = (age % 1000) / 1000;
      context.strokeStyle = `rgba(255, 80, 80, ${1 - phase})`;
      context.lineWidth = 2;
      context.beginPath();
      context.arc(point.x, point.y, 4 + phase * 14, 0, Math.PI * 2);
      context.stroke();
    }

    const footprint = this.ctx.cameraFootprint();
    this.lastFootprint = footprint.map((point) => ({ ...point }));
    const visible = clipToMapSquare(footprint, half);
    if (visible.length >= 3) {
      context.strokeStyle = '#e8edf5';
      context.lineWidth = 1.5;
      context.beginPath();
      const first = visible[0];
      if (first) {
        const start = toMap(first.x, first.z);
        context.moveTo(start.x, start.y);
      }
      for (let index = 1; index < visible.length; index += 1) {
        const point = visible[index];
        if (!point) {
          continue;
        }
        const p = toMap(point.x, point.z);
        context.lineTo(p.x, p.y);
      }
      context.closePath();
      context.stroke();
    }

    this.minimapRedraws += 1;
  }

  /** Objective line: a new mission message for a few seconds, otherwise the current objective. */
  private refreshMission(): void {
    const mission = this.ctx.getWorld().mission;
    this.objectiveLine.hidden = !mission;
    if (!mission) {
      return;
    }
    const latest = mission.messages[mission.messages.length - 1];
    if (latest && latest.seq > this.messageSeq) {
      this.messageSeq = latest.seq;
      this.messageUntil = Date.now() + 6000;
      const message = el('span', 'hud-toast');
      if (latest.speaker) {
        message.append(el('strong', '', `${latest.speaker}: `));
      }
      message.append(document.createTextNode(latest.text));
      this.objectiveText.replaceChildren(message);
      this.objectiveLine.classList.add('message');
      this.objectiveText.dataset.showing = 'message';
      return;
    }
    if (this.objectiveText.dataset.showing === 'message' && Date.now() <= this.messageUntil) {
      return;
    }
    const current =
      mission.objectives.find((objective) => objective.kind === 'primary' && objective.status === 'active') ??
      mission.objectives.find((objective) => objective.status === 'active');
    const text = current ? current.text : 'Objectives complete';
    if (this.objectiveText.dataset.showing !== text) {
      this.objectiveText.dataset.showing = text;
      this.objectiveText.textContent = text;
      this.objectiveLine.classList.remove('message');
    }
  }

  private selectedAircraft(selection: readonly number[]) {
    const world = this.ctx.getWorld();
    return world.units.filter(
      (unit) => unit.owner === 1 && unit.hp > 0 && unit.air !== null && selection.includes(unit.id),
    );
  }

  private refreshAir(selection: readonly number[]): void {
    const craft = this.selectedAircraft(selection);
    const any = craft.length > 0;
    this.airButton.hidden = !any;
    this.airButton.disabled = !any;
    this.airInfo.hidden = !any;
    if (!any) {
      return;
    }
    const flying = craft.some((unit) => unit.air?.mode === 'flying' || unit.air?.mode === 'returning');
    const label = flying ? 'Recall' : 'Launch';
    const caption = this.airButton.querySelector('.hud-cmd-label');
    if (caption && caption.textContent !== label) {
      caption.textContent = label;
      this.airButton.setAttribute('aria-label', label);
    }
    this.airButton.disabled = false;
    const first = craft[0]?.air;
    if (first) {
      this.airInfo.textContent = `Ammo ${first.ammo} · Fuel ${Math.max(0, Math.round(first.fuelLeft))}s${
        first.mode === 'rearming' ? ' · rearming' : ''
      }`;
    }
  }

  private issueAir(): void {
    const craft = this.selectedAircraft(this.ctx.getSelection());
    if (craft.length === 0) {
      return;
    }
    const flying = craft.some((unit) => unit.air?.mode === 'flying' || unit.air?.mode === 'returning');
    this.ctx.sendCommand({
      kind: 'air',
      unitIds: craft.map((unit) => unit.id),
      action: flying ? 'recall' : 'launch',
      tick: this.ctx.getWorld().tick + 1,
      issuer: 1,
    });
  }

  private issueHold(): void {
    const selection = this.ctx.getSelection();
    if (selection.length === 0) {
      return;
    }
    const world = this.ctx.getWorld();
    this.ctx.sendCommand({
      kind: 'hold',
      unitIds: selection,
      tick: world.tick + 1,
      issuer: 1,
    });
  }

  private issueStop(): void {
    const selection = this.ctx.getSelection();
    if (selection.length === 0) {
      return;
    }
    const world = this.ctx.getWorld();
    this.ctx.sendCommand({
      kind: 'stop',
      unitIds: selection,
      tick: world.tick + 1,
      issuer: 1,
    });
  }

  private assignGroup(group: number, element: HTMLButtonElement): void {
    this.ctx.assignGroup(group);
    element.classList.add('assigned');
    window.setTimeout(() => {
      element.classList.remove('assigned');
    }, 600);
    this.refresh();
  }

  private attachGroupHandlers(element: HTMLButtonElement, group: number): void {
    let longFired = false;
    let timer: number | null = null;
    const clear = (): void => {
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
    };
    element.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      longFired = false;
      clear();
      timer = window.setTimeout(() => {
        timer = null;
        longFired = true;
        this.assignGroup(group, element);
      }, 450);
    });
    element.addEventListener('pointerup', (event) => {
      event.preventDefault();
      clear();
      if (longFired) {
        longFired = false;
        return;
      }
      const now = performance.now();
      if (
        this.lastGroupTap &&
        this.lastGroupTap.group === group &&
        now - this.lastGroupTap.time < 600
      ) {
        this.ctx.centerGroup(group);
        this.lastGroupTap = null;
      } else {
        this.ctx.selectGroup(group);
        this.lastGroupTap = { group, time: now };
      }
    });
    element.addEventListener('pointercancel', () => {
      clear();
      longFired = false;
    });
  }

  private readonly onMinimapDown = (event: PointerEvent): void => {
    event.preventDefault();
    event.stopPropagation();
    this.minimapPointer = event.pointerId;
    try {
      this.minimap.setPointerCapture(event.pointerId);
    } catch {
      // Best effort.
    }
    if (event.pointerType === 'mouse' && event.button === 2) {
      this.orderFromMinimap(event.clientX, event.clientY);
      return;
    }
    this.jumpFromMinimap(event.clientX, event.clientY);
  };

  private readonly onMinimapMove = (event: PointerEvent): void => {
    if (this.minimapPointer !== event.pointerId) {
      return;
    }
    event.preventDefault();
    this.jumpFromMinimap(event.clientX, event.clientY);
  };

  private readonly onMinimapUp = (event: PointerEvent): void => {
    if (this.minimapPointer === event.pointerId) {
      this.minimapPointer = null;
    }
  };

  private readonly onMinimapContext = (event: Event): void => {
    event.preventDefault();
  };

  private worldFromMinimap(clientX: number, clientY: number): { x: number; z: number } {
    const world = this.ctx.getWorld();
    const rect = this.minimap.getBoundingClientRect();
    const u = clamp01((clientX - rect.left) / Math.max(1, rect.width));
    const v = clamp01((clientY - rect.top) / Math.max(1, rect.height));
    return {
      x: (u - 0.5) * world.map.size,
      z: (v - 0.5) * world.map.size,
    };
  }

  private jumpFromMinimap(clientX: number, clientY: number): void {
    const point = this.worldFromMinimap(clientX, clientY);
    this.ctx.setCameraTarget(point.x, point.z);
  }

  private orderFromMinimap(clientX: number, clientY: number): void {
    const selection = this.ctx.getSelection();
    if (selection.length === 0) {
      return;
    }
    const world = this.ctx.getWorld();
    const point = this.worldFromMinimap(clientX, clientY);
    this.ctx.sendCommand({
      kind: 'move',
      unitIds: selection,
      x: point.x,
      z: point.z,
      queue: false,
      tick: world.tick + 1,
      issuer: 1,
    });
  }
}
