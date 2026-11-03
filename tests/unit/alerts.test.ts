// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { AlertCenter } from '../../src/ui/alerts';
import { makeWorld } from './simHelpers';

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
});
