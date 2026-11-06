import { isHostile } from '../sim/diplomacy';
import { cellState } from '../sim/vision';
import { heightAt } from '../sim/map';
import { SIM_TICK_HZ } from '../sim/constants';
import { UNIT_CAP } from '../sim/tuning';
import type { WorldState } from '../sim/types';
import { button } from './controls';
import { BasePanel, type BaseAction, type BaseView } from './basePanel';
import type {
  BuildItemView,
  DropQueueView,
  HudHandle,
  HudSnapshot,
  KitView,
  PlacementView,
  WorkerActions,
} from './router';

export interface HudCamera {
  targetX: number;
  targetZ: number;
  distance: number;
  yaw: number;
  pitch: number;
}

export interface HudContext {
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
}

const MINIMAP_SIZE = 240;
const MINIMAP_MARGIN = 10;
const MINIMAP_INTERVAL_MS = 200;

interface WorldPoint {
  x: number;
  z: number;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
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

export class Hud implements HudHandle {
  private readonly root: HTMLDivElement;
  private readonly ctx: HudContext;
  private readonly resources: HTMLSpanElement;
  private readonly workers: HTMLSpanElement;
  private readonly unitsLabel: HTMLSpanElement;
  private readonly clock: HTMLSpanElement;
  private readonly minimap: HTMLCanvasElement;
  private readonly selectionPanel: HTMLDivElement;
  private readonly groupsStrip: HTMLDivElement;
  private readonly attackButton: HTMLButtonElement;
  private readonly holdButton: HTMLButtonElement;
  private readonly stopButton: HTMLButtonElement;
  private readonly queueButton: HTMLButtonElement;
  private readonly groupsButton: HTMLButtonElement;
  private readonly buildButton: HTMLButtonElement;
  private readonly mineButton: HTMLButtonElement;
  private readonly assignButton: HTMLButtonElement;
  private readonly salvageButton: HTMLButtonElement;
  private readonly buildPanel: HTMLDivElement;
  private readonly basePanel: BasePanel;
  private readonly baseButton: HTMLButtonElement;
  private baseOpen = false;
  private readonly buildContent: HTMLDivElement;
  private readonly placementBar: HTMLDivElement;
  private readonly confirmPlacement: HTMLButtonElement;
  private readonly cancelPlacement: HTMLButtonElement;
  private readonly groupButtons: HTMLButtonElement[] = [];
  private readonly queueProgressRefs = new Map<number, HTMLSpanElement>();
  private readonly timer: number;
  private groupsOpen = false;
  private buildMenuOpen = false;
  private lastBuildSignature = '';
  private minimapRedraws = 0;
  private lastFootprint: Array<{ x: number; z: number }> = [];
  private minimapPointer: number | null = null;
  private lastGroupTap: { group: number; time: number } | null = null;

  constructor(host: HTMLElement, ctx: HudContext) {
    this.ctx = ctx;
    this.root = document.createElement('div');
    this.root.className = 'hud-shell';
    this.root.dataset.hudShell = 'true';

    const topbar = document.createElement('div');
    topbar.className = 'hud-topbar';
    topbar.dataset.hudItem = 'topbar';

    this.resources = document.createElement('span');
    this.resources.className = 'hud-resources';
    this.resources.textContent = 'O 0 · M 0';
    this.workers = document.createElement('span');
    this.workers.className = 'hud-workers';
    this.workers.textContent = 'W 0';
    this.unitsLabel = document.createElement('span');
    this.unitsLabel.className = 'hud-units';
    this.unitsLabel.textContent = `U 0/${UNIT_CAP}`;
    this.clock = document.createElement('span');
    this.clock.className = 'hud-clock';
    this.clock.textContent = '00:00';
    topbar.append(this.resources, this.workers, this.unitsLabel, this.clock);

    const deselect = button('inGame', 'deselect', 'Deselect', () => {
      ctx.setSelection([]);
    });
    const lefty = button('inGame', 'leftHanded', 'Lefty', () => {
      this.toggleLeftHanded();
    });
    const pause = button('inGame', 'pause', 'Pause', () => {
      ctx.pause();
    });
    topbar.append(deselect, lefty, pause);

    const minimapWrap = document.createElement('div');
    minimapWrap.className = 'hud-minimap';
    minimapWrap.dataset.hudItem = 'minimap';
    this.minimap = document.createElement('canvas');
    this.minimap.className = 'minimap-canvas';
    this.minimap.width = MINIMAP_SIZE;
    this.minimap.height = MINIMAP_SIZE;
    this.minimap.setAttribute('aria-label', 'Minimap');
    minimapWrap.append(this.minimap);
    this.minimap.addEventListener('pointerdown', this.onMinimapDown);
    this.minimap.addEventListener('pointermove', this.onMinimapMove);
    this.minimap.addEventListener('pointerup', this.onMinimapUp);
    this.minimap.addEventListener('pointercancel', this.onMinimapUp);
    this.minimap.addEventListener('contextmenu', this.onMinimapContext);

    const commandBar = document.createElement('div');
    commandBar.className = 'hud-commandbar';
    commandBar.dataset.hudItem = 'commandbar';

    this.attackButton = button('inGame', 'attackMove', 'Atk Move', () => {
      ctx.setAttackMoveArmed(!ctx.isAttackMoveArmed());
      this.refresh();
    });
    this.holdButton = button('inGame', 'hold', 'Hold', () => {
      this.issueHold();
    });
    this.stopButton = button('inGame', 'stop', 'Stop', () => {
      this.issueStop();
    });
    this.queueButton = button('inGame', 'queue', 'Queue', () => {
      ctx.setQueueMode(!ctx.isQueueMode());
      this.refresh();
    });
    this.groupsButton = button('inGame', 'groups', 'Groups', () => {
      this.groupsOpen = !this.groupsOpen;
      this.groupsStrip.classList.toggle('open', this.groupsOpen);
      this.refresh();
    });
    this.buildButton = button('inGame', 'buildMenu', 'Build', () => {
      this.setBuildMenu(!this.buildMenuOpen);
    });
    this.mineButton = button('inGame', 'mine', 'Mine', () => {
      this.refresh();
    });
    this.assignButton = button('inGame', 'assign', 'Assign', () => {
      this.refresh();
    });
    this.salvageButton = button('inGame', 'salvage', 'Salvage', () => {
      ctx.salvageSelected?.();
      this.refresh();
    });
    this.baseButton = button('inGame', 'base', 'Base', () => {
      this.setBase(!this.baseOpen);
    });
    commandBar.append(
      this.buildButton,
      this.baseButton,
      this.attackButton,
      this.holdButton,
      this.stopButton,
      this.queueButton,
      this.groupsButton,
      this.mineButton,
      this.assignButton,
      this.salvageButton,
    );

    this.groupsStrip = document.createElement('div');
    this.groupsStrip.className = 'hud-groups';
    this.groupsStrip.dataset.hudItem = 'groups';
    for (let group = 1; group <= 5; group += 1) {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'hud-group-button';
      element.textContent = String(group);
      element.dataset.controlId = `inGame.group${group}`;
      element.dataset.group = String(group);
      this.attachGroupHandlers(element, group);
      this.groupButtons.push(element);
      this.groupsStrip.append(element);
    }

    this.selectionPanel = document.createElement('div');
    this.selectionPanel.className = 'hud-selection';
    this.selectionPanel.dataset.hudItem = 'selection';

    this.buildPanel = document.createElement('div');
    this.buildPanel.className = 'hud-build-panel';
    this.buildPanel.dataset.hudItem = 'buildPanel';
    const buildHeader = document.createElement('div');
    buildHeader.className = 'build-header';
    const buildTitle = document.createElement('span');
    buildTitle.textContent = 'Orbital Drops';
    const buildClose = button('inGame', 'buildClose', 'Close', () => {
      this.setBuildMenu(false);
    });
    buildHeader.append(buildTitle, buildClose);
    this.buildContent = document.createElement('div');
    this.buildContent.className = 'build-content';
    this.buildPanel.append(buildHeader, this.buildContent);

    this.basePanel = new BasePanel(
      {
        getView: () =>
          this.ctx.getBaseView?.() ?? {
            labId: null,
            labBusy: false,
            nodes: [],
            structures: [],
            units: [],
            ore: 0,
            metal: 0,
          },
        act: (action) => this.ctx.baseAction?.(action) ?? false,
      },
      () => {
        this.setBase(false);
      },
    );

    this.placementBar = document.createElement('div');
    this.placementBar.className = 'hud-placement';
    this.placementBar.dataset.hudItem = 'placementBar';
    this.confirmPlacement = button('inGame', 'placeConfirm', 'Confirm', () => {
      this.ctx.confirmPlacement?.();
      this.refresh();
    });
    this.cancelPlacement = button('inGame', 'placeCancel', 'Cancel', () => {
      this.ctx.cancelPlacement?.();
      this.refresh();
    });
    this.placementBar.append(this.confirmPlacement, this.cancelPlacement);

    this.root.append(
      topbar,
      minimapWrap,
      commandBar,
      this.groupsStrip,
      this.selectionPanel,
      this.buildPanel,
      this.basePanel.element,
      this.placementBar,
    );
    host.append(this.root);

    this.update();
    this.timer = window.setInterval(() => {
      this.update();
    }, MINIMAP_INTERVAL_MS);
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
      groupsOpen: this.groupsOpen,
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
      kits: this.ctx.getKits?.() ?? [],
      selectedPadId: this.ctx.getSelectedPadId?.() ?? null,
      placementActive: this.ctx.getPlacement?.() !== null,
    };
  }

  dispose(): void {
    window.clearInterval(this.timer);
    this.root.remove();
  }

  refresh(): void {
    const selection = this.ctx.getSelection();
    const hasSelection = selection.length > 0;
    const actions: WorkerActions = this.ctx.getWorkerActions?.() ?? {
      canMine: false,
      canAssign: false,
      canSalvage: false,
    };
    this.attackButton.disabled = !hasSelection;
    this.holdButton.disabled = !hasSelection;
    this.stopButton.disabled = !hasSelection;
    this.queueButton.disabled = !hasSelection;
    this.groupsButton.disabled = !hasSelection;
    this.buildButton.disabled = false;
    this.mineButton.disabled = !actions.canMine;
    this.assignButton.disabled = !actions.canAssign;
    this.salvageButton.disabled = !actions.canSalvage;
    this.queueButton.classList.toggle('active', this.ctx.isQueueMode());
    this.attackButton.classList.toggle('active', this.ctx.isAttackMoveArmed());
    this.groupsButton.classList.toggle('active', this.groupsOpen);
    this.root.classList.toggle('left-handed', this.ctx.isLeftHanded());
    this.root.classList.toggle('build-open', this.buildMenuOpen);
    this.root.classList.toggle('base-open', this.baseOpen);
    const placing = this.ctx.getPlacement?.() !== null;
    this.root.classList.toggle('placing', placing);
    this.placementBar.classList.toggle('open', placing);
    this.groupsStrip.classList.toggle('open', this.groupsOpen);
    if (!hasSelection) {
      this.groupsOpen = false;
      this.groupsStrip.classList.remove('open');
    }

    for (const element of this.groupButtons) {
      const group = Number(element.dataset.group ?? '0');
      const members = this.ctx.groupMembers(group).slice().sort((a, b) => a - b);
      const selected = selection.slice().sort((a, b) => a - b);
      const same =
        members.length > 0 &&
        members.length === selected.length &&
        members.every((id, index) => id === selected[index]);
      element.classList.toggle('selected', same);
    }
    this.renderBuildMenu();
    this.basePanel.refresh();
  }

  private update(): void {
    const world = this.ctx.getWorld();
    this.clock.textContent = formatClock(world.tick / SIM_TICK_HZ);
    const selection = this.ctx.getSelection();
    const stats = world.resources.find((item) => item.player === 1);
    const ownUnits = world.units.filter((unit) => unit.owner === 1 && unit.hp > 0);
    const workers = ownUnits.filter((unit) => {
      const type = world.unitTypes.get(unit.typeId);
      return type?.workerKind !== null && type?.workerKind !== undefined;
    }).length;
    this.resources.textContent = `O ${stats?.ore ?? 0} · M ${stats?.metal ?? 0}`;
    this.workers.textContent = `W ${workers}`;
    this.unitsLabel.textContent = `U ${ownUnits.length}/${UNIT_CAP}`;
    this.refresh();
    this.renderSelection(world, selection);
    this.drawMinimap(world);
  }

  private setBase(open: boolean): void {
    this.baseOpen = open;
    if (open) {
      this.buildMenuOpen = false;
      this.groupsOpen = false;
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
    this.groupsOpen = false;
    this.groupsStrip.classList.remove('open');
    this.root.classList.toggle('build-open', open);
    this.refresh();
  }

  /**
   * Structural signature of the build menu: everything that requires the panel
   * to be rebuilt. Live values that only need in-place updates (queue progress)
   * are intentionally excluded.
   *
   * The panel used to be torn down and rebuilt on every 200 ms HUD tick, which
   * detached every button a few times per second. Playwright's `locator.tap()`
   * performs actionability checks across multiple frames; if the button was
   * detached mid-check the tap was retried forever and the test hung on
   * `build.item.*` and `build.place.*` clicks. Rebuilding only when the sig-
   * nature changes keeps the buttons stable across ticks.
   */
  private computeBuildSignature(): string {
    const items = this.ctx.getBuildItems?.() ?? [];
    const pads = this.ctx.getOwnPads?.() ?? [];
    const queue = this.ctx.getDropQueue?.() ?? [];
    const kits = this.ctx.getKits?.() ?? [];
    const selectedPad = this.ctx.getSelectedPadId?.() ?? null;
    const parts: string[] = [selectedPad === null ? 'pad:' : `pad:${selectedPad}`];
    parts.push(pads.map((pad) => pad.id).join(','));
    for (const item of items) {
      parts.push(
        `${item.id}|${item.name}|${item.kind}|${item.ore}|${item.metal}|${item.deliverySec}|${item.disabledReason ?? ''}`,
      );
    }
    parts.push('::queue::');
    for (const order of queue) {
      parts.push(`${order.id}|${order.itemId}|${order.name}`);
    }
    parts.push('::kits::');
    for (const kit of kits) {
      parts.push(`${kit.id}|${kit.name}`);
    }
    return parts.join(';');
  }

  /**
   * Section order (top to bottom) inside the bottom sheet:
   *   1. "Receive at" pad row — cheap context.
   *   2. "Ready to place" (only when a kit is waiting) — a delivered kit is the
   *      most urgent action; putting it above the catalogue means the Place
   *      button lands in the visible first screenful.
   *   3. "Queue" (only when non-empty) — a placed order needs a visible
   *      progress bar and Cancel button, again without scrolling.
   *   4. "Units" / "Structures" catalogue — scroll target for new buys.
   *
   * The previous layout pushed both "Queue" and "Ready to place" below the item
   * list, so on a 220 px phone sheet a purchase or a delivered kit left the
   * player staring at the top of the catalogue.
   */
  private renderBuildMenu(): void {
    if (!this.buildMenuOpen) {
      if (this.lastBuildSignature !== '') {
        this.buildContent.replaceChildren();
        this.queueProgressRefs.clear();
        this.lastBuildSignature = '';
      }
      return;
    }
    const signature = this.computeBuildSignature();
    if (signature === this.lastBuildSignature) {
      const queue = this.ctx.getDropQueue?.() ?? [];
      for (const order of queue) {
        const bar = this.queueProgressRefs.get(order.id);
        if (bar) {
          const pct = Math.round(Math.min(1, Math.max(0, order.progress)) * 100);
          bar.style.width = `${pct}%`;
        }
      }
      return;
    }
    this.lastBuildSignature = signature;
    this.queueProgressRefs.clear();
    this.buildContent.replaceChildren();

    const items = this.ctx.getBuildItems?.() ?? [];
    const pads = this.ctx.getOwnPads?.() ?? [];
    const selectedPad = this.ctx.getSelectedPadId?.() ?? null;

    const padRow = document.createElement('div');
    padRow.className = 'build-pad-row';
    const padLabel = document.createElement('span');
    padLabel.className = 'build-section-title';
    padLabel.textContent = 'Receive at';
    padRow.append(padLabel);
    for (const [index, pad] of pads.entries()) {
      const padButton = document.createElement('button');
      padButton.type = 'button';
      padButton.className = `build-pad${pad.id === selectedPad ? ' active' : ''}`;
      padButton.textContent = `Pad ${index + 1}`;
      padButton.dataset.controlId = `build.pad.${pad.id}`;
      padButton.addEventListener('click', () => {
        this.ctx.setSelectedPad?.(pad.id);
        this.renderBuildMenu();
      });
      padRow.append(padButton);
    }
    this.buildContent.append(padRow);

    const kits = this.ctx.getKits?.() ?? [];
    if (kits.length > 0) {
      const kitSection = document.createElement('div');
      kitSection.className = 'build-section';
      const kitTitle = document.createElement('div');
      kitTitle.className = 'build-section-title';
      kitTitle.textContent = 'Ready to place';
      kitSection.append(kitTitle);
      for (const kit of kits) {
        const place = document.createElement('button');
        place.type = 'button';
        place.className = 'build-place';
        place.textContent = `Place ${kit.name}`;
        place.dataset.controlId = `build.place.${kit.id}`;
        place.addEventListener('click', () => {
          if (this.ctx.startPlacement?.(kit.id)) {
            this.setBuildMenu(false);
          }
        });
        kitSection.append(place);
      }
      this.buildContent.append(kitSection);
    }

    const queue = this.ctx.getDropQueue?.() ?? [];
    if (queue.length > 0) {
      const queueSection = document.createElement('div');
      queueSection.className = 'build-section';
      const queueTitle = document.createElement('div');
      queueTitle.className = 'build-section-title';
      queueTitle.textContent = 'Queue';
      queueSection.append(queueTitle);
      for (const order of queue) {
        const row = document.createElement('div');
        row.className = 'build-queue-row';
        const info = document.createElement('span');
        info.className = 'build-queue-name';
        info.textContent = order.name;
        const bar = document.createElement('span');
        bar.className = 'queue-bar';
        const fill = document.createElement('span');
        fill.className = 'queue-fill';
        fill.style.width = `${Math.round(Math.min(1, Math.max(0, order.progress)) * 100)}%`;
        bar.append(fill);
        this.queueProgressRefs.set(order.id, fill);
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'build-cancel';
        cancel.textContent = 'Cancel';
        cancel.dataset.controlId = `build.cancel.${order.id}`;
        cancel.addEventListener('click', () => {
          this.ctx.cancelOrder?.(order.id);
          this.renderBuildMenu();
        });
        row.append(info, bar, cancel);
        queueSection.append(row);
      }
      this.buildContent.append(queueSection);
    }

    const groups: Array<{ label: string; kind: 'unit' | 'structure' }> = [
      { label: 'Units', kind: 'unit' },
      { label: 'Structures', kind: 'structure' },
    ];
    for (const group of groups) {
      const section = document.createElement('div');
      section.className = 'build-section';
      const title = document.createElement('div');
      title.className = 'build-section-title';
      title.textContent = group.label;
      section.append(title);
      const list = document.createElement('div');
      list.className = 'build-items';
      for (const item of items.filter((entry) => entry.kind === group.kind)) {
        const itemButton = document.createElement('button');
        itemButton.type = 'button';
        itemButton.className = 'build-item';
        itemButton.dataset.controlId = `build.item.${item.id}`;
        itemButton.disabled = item.disabledReason !== null;
        const name = document.createElement('span');
        name.className = 'build-item-name';
        name.textContent = item.name;
        const cost = document.createElement('span');
        cost.className = 'build-item-cost';
        cost.textContent = `${item.ore} ore · ${item.metal} metal · ${item.deliverySec.toFixed(0)}s`;
        itemButton.append(name, cost);
        if (item.disabledReason) {
          const reason = document.createElement('span');
          reason.className = 'build-reason';
          reason.textContent = item.disabledReason;
          itemButton.append(reason);
        }
        itemButton.addEventListener('click', () => {
          this.ctx.buyItem?.(item.id);
          this.renderBuildMenu();
        });
        list.append(itemButton);
      }
      section.append(list);
      this.buildContent.append(section);
    }
  }

  private renderSelection(world: WorldState, selection: number[]): void {
    this.selectionPanel.style.display = selection.length === 0 ? 'none' : '';
    this.selectionPanel.replaceChildren();
    if (selection.length === 0) {
      return;
    }
    const count = document.createElement('span');
    count.className = 'hud-selection-count';
    count.textContent = `Selected: ${selection.length}`;
    const list = document.createElement('div');
    list.className = 'hud-selection-list';

    for (const id of selection) {
      const unit = world.units.find((item) => item.id === id);
      if (!unit) {
        continue;
      }
      const type = world.unitTypes.get(unit.typeId);
      const maxHp = type?.hp ?? Math.max(1, unit.hp);
      const icon = document.createElement('button');
      icon.type = 'button';
      icon.className = 'selection-icon';
      icon.dataset.unitId = String(id);
      icon.setAttribute('aria-label', `Select unit ${id}`);
      const bar = document.createElement('span');
      bar.className = 'selection-hp';
      const fill = document.createElement('span');
      fill.className = 'selection-hp-fill';
      fill.style.width = `${clamp01(unit.hp / Math.max(1, maxHp)) * 100}%`;
      bar.append(fill);
      icon.append(bar);
      icon.addEventListener('click', () => {
        this.ctx.setSelection([id]);
      });
      list.append(icon);
    }

    this.selectionPanel.append(count, list);
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

    for (const unit of world.units) {
      const point = toMap(unit.x, unit.z);
      context.fillStyle = unit.owner === 1 ? '#4ea3ff' : '#ff5c5c';
      context.beginPath();
      context.arc(point.x, point.y, unit.owner === 1 ? 3 : 2.5, 0, Math.PI * 2);
      context.fill();
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

  private toggleLeftHanded(): void {
    this.ctx.setLeftHanded(!this.ctx.isLeftHanded());
    this.root.classList.toggle('left-handed', this.ctx.isLeftHanded());
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
        this.ctx.assignGroup(group);
        element.classList.add('assigned');
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
