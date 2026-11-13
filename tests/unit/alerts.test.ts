// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { AlertCenter } from '../../src/ui/alerts';
import type { StructureState, WorldState } from '../../src/sim/types';
import { ALERT_TTL_SEC } from '../../src/sim/tuning';
import { makeWorld, metalStationType, padType } from './simHelpers';

describe('alerts', () => {
  let center: AlertCenter | null = null;

  afterEach(() => {
    center?.dispose();
    center = null;
  });

  it('[ALRT-01] under-attack and unit-lost fire from world changes, are rate-limited, and a toast jumps the camera', () => {
    let now = 0;
    const jumps: Array<{ x: number; z: number }> = [];
    center = new AlertCenter({
      host: document.body,
      now: () => now,
      rateLimitMs: 1000,
      ttlMs: 100000,
      onJump: (x, z) => jumps.push({ x, z }),
    });
    center.setEnabled(true);

    const world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 },
      { owner: 2, typeId: 'unit.test.tank', x: -40, z: -50 },
    ]);
    center.update(world);

    const damaged = {
      ...world,
      units: world.units.map((unit, index) =>
        index === 0 ? { ...unit, hp: unit.hp - 20 } : unit,
      ),
    };
    center.update(damaged);
    const afterDamage = center.list();
    expect(afterDamage.some((alert) => alert.kind === 'underAttack')).toBe(true);

    now = 1200;
    center.update({ ...damaged, units: damaged.units.slice(1) });
    const afterLoss = center.list();
    expect(afterLoss.some((alert) => alert.kind === 'unitLost')).toBe(true);

    now = 1300;
    const first = center.raiseAlert('depositEmpty', 10, -10);
    const second = center.raiseAlert('depositEmpty', 10, -10);
    expect(first).not.toBeNull();
    expect(second).toBeNull();

    const button = document.querySelector<HTMLButtonElement>(
      `[data-alert-id="${first?.id ?? 0}"]`,
    );
    expect(button).not.toBeNull();
    button?.click();
    expect(jumps.at(-1)).toEqual({ x: 10, z: -10 });
  });

  it('[ALRT-01] pad lost, structure lost, deposit empty and not enough resources fire from the economy state', () => {
    let now = 0;
    center = new AlertCenter({
      host: document.body,
      now: () => now,
      rateLimitMs: 1000,
      ttlMs: 100000,
      onJump: () => undefined,
    });
    center.setEnabled(true);

    const base = makeWorld(1, [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    const pad: StructureState = {
      id: 900, owner: 1, typeId: padType().id, x: 5, z: 6, hp: 200, containers: 0, fill: 0, depositId: null,
      upgrades: [], reloadLeft: 0, turretHeading: 0, work: null,
    };
    const station: StructureState = {
      ...pad, id: 901, typeId: metalStationType().id, x: 20, z: 21, hp: 100,
    };
    const world: WorldState = {
      ...base,
      structureTypes: new Map([
        [padType().id, padType()],
        [metalStationType().id, metalStationType()],
      ]),
      structures: [pad, station],
      alerts: [],
      lastCommandOutcome: null,
    };
    center.update(world);
    expect(center.list()).toEqual([]);

    center.update({ ...world, structures: [station] });
    expect(center.list().at(-1)).toMatchObject({ kind: 'padLost', x: 5, z: 6 });

    now = 1100;
    center.update({ ...world, structures: [] });
    expect(center.list().at(-1)).toMatchObject({ kind: 'structureLost', x: 20, z: 21 });

    now = 2200;
    const withAlerts: WorldState = {
      ...world,
      structures: [],
      alerts: [
        { kind: 'depositEmpty', owner: 1, x: 1, z: 2, ttl: ALERT_TTL_SEC },
        { kind: 'dropArrived', owner: 1, x: 3, z: 4, ttl: ALERT_TTL_SEC },
        { kind: 'dropArrived', owner: 2, x: 9, z: 9, ttl: ALERT_TTL_SEC },
      ],
    };
    center.update(withAlerts);
    const kinds = center.list().map((alert) => alert.kind);
    expect(kinds).toContain('depositEmpty');
    // Drop arrived is not an alert any more: the order's tile leaving the queue strip says it.
    expect(kinds).not.toContain('dropArrived');

    // The same sim alerts seen on a later frame are not raised again.
    now = 4000;
    const count = center.list().length;
    center.update(withAlerts);
    expect(center.list()).toHaveLength(count);

    center.update({
      ...withAlerts,
      lastCommandOutcome: { tick: world.tick, kind: 'buy', ok: false, reason: 'unaffordable' },
    });
    expect(center.list().at(-1)?.kind).toBe('notEnoughResources');
  });

  it('[ALRT-02] alerts share one line: repeats of a kind merge into a count, and the text fades to an icon', async () => {
    let now = 0;
    const jumps: Array<{ x: number; z: number }> = [];
    center = new AlertCenter({
      host: document.body,
      now: () => now,
      rateLimitMs: 1000,
      ttlMs: 50,
      onJump: (x, z) => jumps.push({ x, z }),
    });
    center.setEnabled(true);
    center.raiseAlert('unitLost', 1, 1);
    now = 400;
    center.raiseAlert('unitLost', 2, 2);
    now = 1500;
    center.raiseAlert('unitLost', 3, 3);
    const lines = document.querySelectorAll<HTMLButtonElement>('.alert-toast');
    expect(lines).toHaveLength(1);
    const line = lines[0]!;
    expect(line.hidden).toBe(false);
    expect(line.textContent).toContain('3 units lost');
    // A different kind starts a fresh line.
    now = 3000;
    center.raiseAlert('depositEmpty', 9, 9);
    expect(line.textContent).toContain('Deposit empty');
    expect(line.dataset.count).toBe('1');
    // The text fades but the icon stays, and a tap still jumps to the newest alert.
    await new Promise((resolve) => setTimeout(resolve, 80));
    expect(line.classList.contains('faded')).toBe(true);
    expect(line.hidden).toBe(false);
    line.click();
    expect(jumps.at(-1)).toEqual({ x: 9, z: 9 });
  });
});
