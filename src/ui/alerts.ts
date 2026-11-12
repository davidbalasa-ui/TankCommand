import type { CommandOutcome, WorldState } from '../sim/types';
import { SIM_TICK_HZ } from '../sim/constants';
import {
  ALERT_RATE_LIMIT_MS,
  ALERT_TOAST_TTL_MS,
  ALERT_TTL_SEC,
} from '../sim/tuning';

const SIM_DT = 1 / SIM_TICK_HZ;

export type AlertKind =
  | 'underAttack'
  | 'unitLost'
  | 'structureLost'
  | 'padLost'
  | 'depositEmpty'
  | 'researchDone'
  | 'dropArrived'
  | 'objectiveUpdated'
  | 'notEnoughResources';

export interface AlertSnapshot {
  id: number;
  kind: AlertKind;
  message: string;
  x: number;
  z: number;
  at: number;
}

export interface AlertCenterOptions {
  host: HTMLElement;
  onJump: (x: number, z: number) => void;
  /** Where a map point is on screen (null when it is not), for the red edge flash. */
  locate?: (x: number, z: number) => { x: number; y: number } | null;
  onAlert?: (alert: AlertSnapshot) => void;
  now?: () => number;
  rateLimitMs?: number;
  ttlMs?: number;
}

interface PreviousUnit {
  hp: number;
  x: number;
  z: number;
  deploying?: boolean;
}

interface PreviousStructure extends PreviousUnit {
  pad: boolean;
}

/** Sim alert kinds (src/sim/economy.ts addAlert) that the toast layer shows as-is. */
// Drop arrived is not shown any more: the order's tile leaving the queue strip says it.
const SIM_ALERT_KINDS: ReadonlySet<string> = new Set(['depositEmpty']);

/** How long the alert line's text stays before only its icon is left. */
export const ALERT_TEXT_MS = 4000;
/** Alerts of one kind this close together merge into one counted line. */
export const ALERT_MERGE_MS = 8000;

/** "3 units under attack" for a merged line; null keeps "<message> ×3". */
function pluralMessage(message: string, count: number): string {
  const plurals: Record<string, string> = {
    'Unit under attack': 'units under attack',
    'Unit lost': 'units lost',
    'Structure lost': 'structures lost',
    'Base under attack': 'hits on your base',
    'Deposit empty': 'deposits empty',
  };
  const plural = plurals[message];
  return plural ? `${count} ${plural}` : `${message} ×${count}`;
}

function defaultMessage(kind: AlertKind): string {
  switch (kind) {
    case 'underAttack':
      return 'Unit under attack';
    case 'unitLost':
      return 'Unit lost';
    case 'structureLost':
      return 'Structure lost';
    case 'padLost':
      return 'Landing pad lost';
    case 'depositEmpty':
      return 'Deposit empty';
    case 'researchDone':
      return 'Research complete';
    case 'dropArrived':
      return 'Drop arrived';
    case 'objectiveUpdated':
      return 'Objective updated';
    case 'notEnoughResources':
      return 'Not enough resources';
  }
}

export class AlertCenter {
  private readonly root: HTMLDivElement;
  private readonly onJump: (x: number, z: number) => void;
  private readonly onAlert: ((alert: AlertSnapshot) => void) | null;
  private readonly now: () => number;
  private readonly rateLimitMs: number;
  private readonly ttlMs: number;
  private readonly previous = new Map<number, PreviousUnit>();
  private readonly previousStructures = new Map<number, PreviousStructure>();
  private readonly seenSimAlerts = new Set<string>();
  private lastOutcome: CommandOutcome | null = null;
  private readonly lastRaised = new Map<AlertKind, number>();
  private readonly history: AlertSnapshot[] = [];
  private readonly line: HTMLButtonElement;
  private readonly lineText: HTMLSpanElement;
  private readonly flash: HTMLDivElement;
  private readonly locate: ((x: number, z: number) => { x: number; y: number } | null) | null;
  private current: { alert: AlertSnapshot; key: string; count: number; at: number } | null = null;
  private textTimer: number | null = null;
  private flashTimer: number | null = null;
  private initialized = false;
  private nextId = 1;
  private enabled = false;

  constructor(options: AlertCenterOptions) {
    this.onJump = options.onJump;
    this.onAlert = options.onAlert ?? null;
    this.now = options.now ?? (() => performance.now());
    this.rateLimitMs = options.rateLimitMs ?? ALERT_RATE_LIMIT_MS;
    this.ttlMs = options.ttlMs ?? ALERT_TOAST_TTL_MS;
    this.locate = options.locate ?? null;
    // One line under the resource bar: the newest alert, merged with repeats of its kind. The
    // text fades after a few seconds; the icon stays, and a tap jumps to the newest alert.
    this.root = document.createElement('div');
    this.root.className = 'alert-toasts';
    this.root.dataset.alertToasts = 'true';
    this.line = document.createElement('button');
    this.line.type = 'button';
    this.line.className = 'alert-toast';
    this.line.hidden = true;
    const glyph = document.createElement('span');
    glyph.className = 'alert-icon';
    glyph.textContent = '!';
    this.lineText = document.createElement('span');
    this.lineText.className = 'alert-text';
    this.line.append(glyph, this.lineText);
    this.line.addEventListener('click', () => {
      const alert = this.current?.alert;
      if (alert) {
        this.onJump(alert.x, alert.z);
      }
    });
    this.root.append(this.line);
    this.flash = document.createElement('div');
    this.flash.className = 'alert-edge-flash';
    this.flash.hidden = true;
    options.host.append(this.root, this.flash);
    this.setEnabled(false);
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    this.root.style.display = enabled ? 'flex' : 'none';
  }

  reset(world?: WorldState): void {
    this.previous.clear();
    this.previousStructures.clear();
    this.seenSimAlerts.clear();
    this.lastOutcome = world?.lastCommandOutcome ?? null;
    this.initialized = false;
    this.clearLine();
    if (world) {
      this.capture(world);
      this.initialized = true;
    }
  }

  update(world: WorldState): void {
    const current = new Map<number, PreviousUnit>();
    for (const unit of world.units) {
      if (unit.owner === 1) {
        current.set(unit.id, { hp: unit.hp, x: unit.x, z: unit.z, deploying: unit.transform !== null });
      }
    }

    if (this.initialized && this.enabled) {
      for (const unit of world.units) {
        if (unit.owner !== 1) {
          continue;
        }
        const previous = this.previous.get(unit.id);
        if (previous && unit.hp < previous.hp) {
          this.raiseAlert('underAttack', unit.x, unit.z);
        }
      }
      for (const [id, previous] of this.previous) {
        // A unit that was unfolding into a tower became that tower; it was not lost.
        if (!current.has(id) && !previous.deploying) {
          this.raiseAlert('unitLost', previous.x, previous.z);
        }
      }
    }

    this.previous.clear();
    for (const [id, unit] of current) {
      this.previous.set(id, unit);
    }
    this.updateStructures(world);
    this.updateSimAlerts(world);
    this.updateOutcome(world);
    this.initialized = true;
  }

  /** Structure hits, structure lost and pad lost, from own structures between frames. */
  private updateStructures(world: WorldState): void {
    const current = new Map<number, PreviousStructure>();
    for (const structure of world.structures ?? []) {
      if (structure.owner !== 1 || structure.hp <= 0) {
        continue;
      }
      const pad = world.structureTypes.get(structure.typeId)?.kind === 'pad';
      current.set(structure.id, { hp: structure.hp, x: structure.x, z: structure.z, pad });
    }
    if (this.initialized && this.enabled) {
      for (const [id, now] of current) {
        const previous = this.previousStructures.get(id);
        if (previous && now.hp < previous.hp) {
          this.raiseAlert('underAttack', now.x, now.z, 'Base under attack');
        }
      }
      for (const [id, previous] of this.previousStructures) {
        if (!current.has(id)) {
          this.raiseAlert(previous.pad ? 'padLost' : 'structureLost', previous.x, previous.z);
        }
      }
    }
    this.previousStructures.clear();
    for (const [id, structure] of current) {
      this.previousStructures.set(id, structure);
    }
  }

  /**
   * Alerts the sim itself raises (deposit empty, drop arrived). Sim alerts carry
   * no id, so each is keyed by kind, place and the tick it was raised on.
   */
  private updateSimAlerts(world: WorldState): void {
    const live = new Set<string>();
    for (const alert of world.alerts ?? []) {
      if (alert.owner !== 1 || !SIM_ALERT_KINDS.has(alert.kind)) {
        continue;
      }
      const raisedTick = world.tick - Math.round((ALERT_TTL_SEC - alert.ttl) / SIM_DT);
      const key = `${alert.kind}:${raisedTick}:${alert.x.toFixed(2)}:${alert.z.toFixed(2)}`;
      live.add(key);
      if (this.seenSimAlerts.has(key)) {
        continue;
      }
      if (this.initialized && this.enabled) {
        this.raiseAlert(alert.kind, alert.x, alert.z);
      }
    }
    this.seenSimAlerts.clear();
    for (const key of live) {
      this.seenSimAlerts.add(key);
    }
  }

  /**
   * "Not enough resources" when a buy is refused as unaffordable. Only the
   * player issues buy commands today; once the enemy AI (WP-07) buys too, the
   * outcome needs an issuer field to filter on.
   */
  private updateOutcome(world: WorldState): void {
    const outcome = world.lastCommandOutcome ?? null;
    const previous = this.lastOutcome;
    this.lastOutcome = outcome;
    if (!outcome || !this.initialized || !this.enabled) {
      return;
    }
    if (previous && previous.tick === outcome.tick && previous.kind === outcome.kind) {
      return;
    }
    if (!outcome.ok && outcome.reason === 'unaffordable') {
      const unit = world.units.find((entry) => entry.owner === 1 && entry.hp > 0);
      this.raiseAlert('notEnoughResources', unit?.x ?? 0, unit?.z ?? 0);
    }
  }

  raiseAlert(kind: AlertKind, x: number, z: number, message?: string): AlertSnapshot | null {
    if (!this.enabled) {
      return null;
    }
    const at = this.now();
    const last = this.lastRaised.get(kind) ?? Number.NEGATIVE_INFINITY;
    if (at - last < this.rateLimitMs) {
      // Too soon for a new alert, but the line still counts it.
      const key = message ?? defaultMessage(kind);
      if (this.current && this.current.key === key) {
        this.current.count += 1;
        this.current.at = at;
        this.renderLine();
      }
      return null;
    }
    this.lastRaised.set(kind, at);

    const alert: AlertSnapshot = {
      id: this.nextId,
      kind,
      message: message ?? defaultMessage(kind),
      x,
      z,
      at,
    };
    this.nextId += 1;
    this.history.push(alert);
    while (this.history.length > 50) {
      this.history.shift();
    }
    this.show(alert);
    this.onAlert?.(alert);
    return alert;
  }

  list(): AlertSnapshot[] {
    return this.history.map((alert) => ({ ...alert }));
  }

  get(id: number): AlertSnapshot | null {
    const alert = this.history.find((entry) => entry.id === id);
    return alert ? { ...alert } : null;
  }

  dispose(): void {
    this.clearLine();
    this.root.remove();
    this.flash.remove();
  }

  private capture(world: WorldState): void {
    this.previous.clear();
    for (const unit of world.units) {
      if (unit.owner === 1) {
        this.previous.set(unit.id, { hp: unit.hp, x: unit.x, z: unit.z, deploying: unit.transform !== null });
      }
    }
  }

  private show(alert: AlertSnapshot): void {
    const key = alert.message;
    if (this.current && this.current.key === key && alert.at - this.current.at < ALERT_MERGE_MS) {
      this.current.count += 1;
      this.current.alert = alert;
      this.current.at = alert.at;
    } else {
      this.current = { alert, key, count: 1, at: alert.at };
    }
    this.renderLine();
    this.edgeFlash(alert);
  }

  private renderLine(): void {
    const current = this.current;
    if (!current) {
      return;
    }
    const text = current.count > 1 ? pluralMessage(current.key, current.count) : current.key;
    this.lineText.textContent = text;
    this.line.dataset.alertId = String(current.alert.id);
    this.line.dataset.alertKind = current.alert.kind;
    this.line.dataset.count = String(current.count);
    this.line.setAttribute('aria-label', `${text}. Tap to look.`);
    this.line.hidden = false;
    this.line.classList.remove('faded');
    if (this.textTimer !== null) {
      window.clearTimeout(this.textTimer);
    }
    this.textTimer = window.setTimeout(() => {
      this.textTimer = null;
      this.line.classList.add('faded');
    }, Math.min(ALERT_TEXT_MS, this.ttlMs));
  }

  /** A red glow on the screen edge the trouble is past, when it is off screen. */
  private edgeFlash(alert: AlertSnapshot): void {
    if (alert.kind === 'notEnoughResources' || alert.kind === 'researchDone') {
      return;
    }
    const point = this.locate?.(alert.x, alert.z) ?? null;
    if (!point) {
      return;
    }
    const width = window.innerWidth;
    const height = window.innerHeight;
    let side: 'left' | 'right' | 'top' | 'bottom' | null = null;
    if (point.x < 0) {
      side = 'left';
    } else if (point.x > width) {
      side = 'right';
    } else if (point.y < 0) {
      side = 'top';
    } else if (point.y > height) {
      side = 'bottom';
    }
    if (!side) {
      return;
    }
    this.flash.dataset.side = side;
    this.flash.hidden = false;
    this.flash.classList.remove('on');
    void this.flash.offsetWidth;
    this.flash.classList.add('on');
    if (this.flashTimer !== null) {
      window.clearTimeout(this.flashTimer);
    }
    this.flashTimer = window.setTimeout(() => {
      this.flashTimer = null;
      this.flash.hidden = true;
      this.flash.classList.remove('on');
    }, 1200);
  }

  private clearLine(): void {
    if (this.textTimer !== null) {
      window.clearTimeout(this.textTimer);
      this.textTimer = null;
    }
    if (this.flashTimer !== null) {
      window.clearTimeout(this.flashTimer);
      this.flashTimer = null;
    }
    this.current = null;
    this.line.hidden = true;
    this.flash.hidden = true;
  }
}
