import { heightAt } from '../sim/map';
import { SIM_TICK_HZ } from '../sim/constants';
import type { WorldState } from '../sim/types';
import { button } from './controls';
import type { HudHandle, HudSnapshot } from './router';

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

/**
 * Sutherland–Hodgman against the map square.
 *
 * The camera footprint is the ground under the four corners of the view, which
 * at anything past mid zoom runs well off the map. Clamping each corner
 * independently (the WP-03 first pass) collapses the quadrilateral onto the map
 * border — at full zoom-out, with the view yawed 45°, it degenerated into a
 * single diagonal slash across the minimap. Clipping keeps the *visible* part of
 * the footprint, which is what the minimap is actually meant to outline.
 */
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
  private readonly clock: HTMLSpanElement;
  private readonly minimap: HTMLCanvasElement;
  private readonly selectionPanel: HTMLDivElement;
  private readonly groupsStrip: HTMLDivElement;
  private readonly attackButton: HTMLButtonElement;
  private readonly holdButton: HTMLButtonElement;
  private readonly stopButton: HTMLButtonElement;
  private readonly queueButton: HTMLButtonElement;
  private readonly groupsButton: HTMLButtonElement;
  private readonly groupButtons: HTMLButtonElement[] = [];
  private readonly timer: number;
  private groupsOpen = false;
  private minimapRedraws = 0;
  private lastFootprint: Array<{ x: number; z: number }> = [];
  private minimapPointer: number | null = null;
  private lastGroupTap: { group: number; time: number } | null = null;

  constructor(host: HTMLElement, ctx: HudContext) {
    this.ctx = ctx;
    this.root = document.createElement('div');
    this.root.className = `hud-shell${ctx.isLeftHanded() ? ' left-handed' : ''}`;
    this.root.dataset.hudShell = 'true';

    const topbar = document.createElement('div');
    topbar.className = 'hud-topbar';
    topbar.dataset.hudItem = 'topbar';

    const resources = document.createElement('span');
    resources.className = 'hud-resources';
    resources.textContent = 'Ore — · Metal —';
    this.clock = document.createElement('span');
    this.clock.className = 'hud-clock';
    this.clock.textContent = '00:00';
    topbar.append(resources, this.clock);

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
    commandBar.append(
      this.attackButton,
      this.holdButton,
      this.stopButton,
      this.queueButton,
      this.groupsButton,
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

    this.root.append(topbar, minimapWrap, commandBar, this.groupsStrip, this.selectionPanel);
    host.append(this.root);

    this.update();
    this.timer = window.setInterval(() => {
      this.update();
    }, MINIMAP_INTERVAL_MS);
  }

  snapshot(): HudSnapshot {
    const world = this.ctx.getWorld();
    const selection = this.ctx.getSelection();
    return {
      leftHanded: this.ctx.isLeftHanded(),
      groupsOpen: this.groupsOpen,
      queueMode: this.ctx.isQueueMode(),
      attackMoveArmed: this.ctx.isAttackMoveArmed(),
      selectedCount: selection.length,
      ownUnits: world.units.filter((unit) => unit.owner === 1).length,
      enemyUnits: world.units.filter((unit) => unit.owner !== 1).length,
      minimapFootprint: this.lastFootprint.map((point) => ({ x: point.x, z: point.z })),
      minimapRedraws: this.minimapRedraws,
      // Reflect the DOM state rather than "was the selection empty at snapshot
      // time": a slow tick would otherwise let the snapshot report true while
      // the buttons were still enabled, which is exactly what HUD-01 does not
      // want.
      commandButtonsDisabled: this.attackButton.disabled,
    };
  }

  dispose(): void {
    window.clearInterval(this.timer);
    this.root.remove();
  }

  /** Refresh the disabled state of the command bar from the current selection. */
  refresh(): void {
    const selection = this.ctx.getSelection();
    const hasSelection = selection.length > 0;
    this.attackButton.disabled = !hasSelection;
    this.holdButton.disabled = !hasSelection;
    this.stopButton.disabled = !hasSelection;
    this.queueButton.disabled = !hasSelection;
    this.groupsButton.disabled = !hasSelection;
    this.queueButton.classList.toggle('active', this.ctx.isQueueMode());
    this.attackButton.classList.toggle('active', this.ctx.isAttackMoveArmed());
    this.groupsButton.classList.toggle('active', this.groupsOpen);
    this.root.classList.toggle('left-handed', this.ctx.isLeftHanded());
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
  }

  private update(): void {
    const world = this.ctx.getWorld();
    this.clock.textContent = formatClock(world.tick / SIM_TICK_HZ);
    const selection = this.ctx.getSelection();
    this.refresh();
    this.renderSelection(world, selection);
    this.drawMinimap(world);
  }

  private renderSelection(world: WorldState, selection: number[]): void {
    // An empty selection panel is a large, contentless block parked over the
    // battlefield; only show it while there is something in it.
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

    for (const unit of world.units) {
      const point = toMap(unit.x, unit.z);
      context.fillStyle = unit.owner === 1 ? '#4ea3ff' : '#ff5c5c';
      context.beginPath();
      context.arc(point.x, point.y, unit.owner === 1 ? 3 : 2.5, 0, Math.PI * 2);
      context.fill();
    }

    // `lastFootprint` stays the raw, unclipped footprint (the panel/`hud()`
    // contract that MM-01 reads); only the drawn outline is clipped to the map
    // square so it stays a proper polygon instead of a diagonal slash.
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
