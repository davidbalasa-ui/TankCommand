import type { CommandOutcome, WorldState } from '../sim/types';
import { SIM_TICK_HZ } from '../sim/constants';
import {
  ALERT_MAX_TOASTS,
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
  onAlert?: (alert: AlertSnapshot) => void;
  now?: () => number;
  rateLimitMs?: number;
  ttlMs?: number;
}

interface PreviousUnit {
  hp: number;
  x: number;
  z: number;
}

interface PreviousStructure extends PreviousUnit {
  pad: boolean;
}

/** Sim alert kinds (src/sim/economy.ts addAlert) that the toast layer shows as-is. */
const SIM_ALERT_KINDS: ReadonlySet<string> = new Set(['depositEmpty', 'dropArrived']);

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
  private readonly visible = new Map<number, { element: HTMLButtonElement; timer: number }>();
  private initialized = false;
  private nextId = 1;
  private enabled = false;

  constructor(options: AlertCenterOptions) {
    this.onJump = options.onJump;
    this.onAlert = options.onAlert ?? null;
    this.now = options.now ?? (() => performance.now());
    this.rateLimitMs = options.rateLimitMs ?? ALERT_RATE_LIMIT_MS;
    this.ttlMs = options.ttlMs ?? ALERT_TOAST_TTL_MS;
    this.root = document.createElement('div');
    this.root.className = 'alert-toasts';
    this.root.dataset.alertToasts = 'true';
    options.host.append(this.root);
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
    for (const id of [...this.visible.keys()]) {
      this.dismiss(id);
    }
    if (world) {
      this.capture(world);
      this.initialized = true;
    }
  }

  update(world: WorldState): void {
    const current = new Map<number, PreviousUnit>();
    for (const unit of world.units) {
      if (unit.owner === 1) {
        current.set(unit.id, { hp: unit.hp, x: unit.x, z: unit.z });
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
        if (!current.has(id)) {
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
    for (const id of [...this.visible.keys()]) {
      this.dismiss(id);
    }
    this.root.remove();
  }

  private capture(world: WorldState): void {
    this.previous.clear();
    for (const unit of world.units) {
      if (unit.owner === 1) {
        this.previous.set(unit.id, { hp: unit.hp, x: unit.x, z: unit.z });
      }
    }
  }

  private show(alert: AlertSnapshot): void {
    if (this.visible.size >= ALERT_MAX_TOASTS) {
      const oldest = [...this.visible.keys()][0];
      if (oldest !== undefined) {
        this.dismiss(oldest);
      }
    }

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'alert-toast';
    button.dataset.alertId = String(alert.id);
    button.dataset.alertKind = alert.kind;
    button.textContent = alert.message;
    button.addEventListener('click', () => {
      this.onJump(alert.x, alert.z);
      this.dismiss(alert.id);
    });
    this.root.append(button);
    const timer = window.setTimeout(() => {
      this.dismiss(alert.id);
    }, this.ttlMs);
    this.visible.set(alert.id, { element: button, timer });
  }

  private dismiss(id: number): void {
    const entry = this.visible.get(id);
    if (!entry) {
      return;
    }
    window.clearTimeout(entry.timer);
    entry.element.remove();
    this.visible.delete(id);
  }
}
