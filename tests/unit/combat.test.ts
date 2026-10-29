import { describe, expect, it } from 'vitest';
import { generateMap, heightAt, isBlockedAt, lineOfSightClear } from '../../src/sim/map';
import { step } from '../../src/sim/world';
import type { ProjectileState } from '../../src/sim/types';
import {
  angleDiff,
  dummyType,
  makeSkirmishWorld,
  makeWorld,
  tankType,
  worldWithTypes,
} from './simHelpers';

function projectile(overrides: Partial<ProjectileState>): ProjectileState {
  return {
    id: 1000,
    owner: 1,
    x: -50,
    y: 0,
    z: -50,
    vx: 0,
    vy: 0,
    vz: 0,
    damage: 100,
    ttl: 5,
    splashRadius: 0.5,
    ...overrides,
  };
}

describe('combat', () => {
  it('[CMB-01] turrets turn at their rate independently of the hull', () => {
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, heading: 0 },
      { owner: 2, typeId: 'unit.test.tank', x: -50, z: -40, heading: Math.PI },
    ]);
    const before = world.units[0];
    expect(before).toBeDefined();
    if (!before) {
      return;
    }
    const hull = before.heading;
    const turret = before.turretHeading;
    world = step(world, []);
    const after = world.units[0];
    expect(after).toBeDefined();
    if (!after) {
      return;
    }
    expect(after.heading).toBeCloseTo(hull, 6);
    const delta = Math.abs(angleDiff(after.turretHeading, turret));
    expect(delta).toBeGreaterThan(0);
    expect(delta).toBeLessThanOrEqual((120 * Math.PI) / 180 / 20 + 0.000001);
  });

  it('[CMB-02] a tank waits for alignment and reload before firing', () => {
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, heading: 0, turretHeading: 0 },
      { owner: 2, typeId: 'unit.test.tank', x: -50, z: -40, heading: Math.PI },
    ]);
    const target = world.units[1];
    expect(target).toBeDefined();
    if (!target) {
      return;
    }
    target.hp = 100000;
    const firstTicks: number[] = [];
    for (let i = 0; i < 300; i += 1) {
      const before = world.projectiles.length;
      world = step(world, []);
      if (world.projectiles.length > before) {
        firstTicks.push(world.tick);
      }
    }
    expect(firstTicks.length).toBeGreaterThanOrEqual(2);
    expect(firstTicks[0] ?? 0).toBeGreaterThan(1);
    const interval = (firstTicks[1] ?? 0) - (firstTicks[0] ?? 0);
    expect(interval).toBeGreaterThanOrEqual(49);
    expect(interval).toBeLessThanOrEqual(51);
  });

  it('[CMB-03] armor clamps damage, kills leave a wreck and wrecks expire', () => {
    let world = makeWorld(1, [{ owner: 2, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    const victimId = world.units[0]?.id;
    expect(victimId).toBeDefined();
    if (victimId === undefined) {
      return;
    }
    const initial = world.units[0]?.hp ?? 0;
    world.projectiles.push(
      projectile({
        owner: 1,
        x: -50,
        y: heightAt(world.map, -50, -50) + 1.5,
        z: -50,
        vx: 40,
        damage: 3,
      }),
    );
    world = step(world, []);
    expect(world.units.find((unit) => unit.id === victimId)?.hp).toBe(initial - 1);

    let killWorld = makeWorld(1, [{ owner: 2, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    const killId = killWorld.units[0]?.id;
    expect(killId).toBeDefined();
    if (killId === undefined) {
      return;
    }
    const victim = killWorld.units[0];
    if (!victim) {
      return;
    }
    victim.hp = 5;
    killWorld.projectiles.push(
      projectile({
        owner: 1,
        x: -50,
        y: heightAt(killWorld.map, -50, -50) + 1.5,
        z: -50,
        vx: 40,
        damage: 100,
      }),
    );
    killWorld = step(killWorld, []);
    expect(killWorld.units.find((unit) => unit.id === killId)).toBeUndefined();
    expect(killWorld.wrecks.length).toBe(1);
    for (let i = 0; i < 220; i += 1) {
      killWorld = step(killWorld, []);
    }
    expect(killWorld.wrecks.length).toBe(0);
  });

  it('[CMB-04] terrain blocks direct fire while open ground does not', () => {
    const map = generateMap(1);
    const candidates: Array<{ x: number; z: number }> = [];
    for (let x = -16; x <= 16; x += 2) {
      for (let z = -16; z <= 16; z += 2) {
        if (!isBlockedAt(map, x, z)) {
          candidates.push({ x, z });
        }
      }
    }
    let pair: { a: { x: number; z: number }; b: { x: number; z: number } } | null = null;
    for (const a of candidates) {
      if (a.x + a.z >= -6) {
        continue;
      }
      for (const b of candidates) {
        if (b.x + b.z <= 6) {
          continue;
        }
        const distance = Math.hypot(b.x - a.x, b.z - a.z);
        if (distance < 8 || distance > 28) {
          continue;
        }
        const clear = lineOfSightClear(
          map,
          a.x,
          a.z,
          heightAt(map, a.x, a.z) + 1.5,
          b.x,
          b.z,
          heightAt(map, b.x, b.z) + 1,
        );
        if (!clear) {
          pair = { a, b };
          break;
        }
      }
      if (pair) {
        break;
      }
    }
    expect(pair).not.toBeNull();
    if (!pair) {
      return;
    }

    const longRange = {
      weapon: {
        damage: 30,
        range: 30,
        reloadSec: 0.5,
        projectileSpeed: 40,
        accuracy: 1,
        splashRadius: 0.5,
      },
    };
    const bearing = Math.atan2(pair.b.z - pair.a.z, pair.b.x - pair.a.x);
    let blockedWorld = makeWorld(
      1,
      [
        {
          owner: 1,
          typeId: 'unit.test.tank',
          x: pair.a.x,
          z: pair.a.z,
          heading: bearing,
          turretHeading: bearing,
        },
        {
          owner: 2,
          typeId: 'unit.test.tank',
          x: pair.b.x,
          z: pair.b.z,
          heading: bearing + Math.PI,
          turretHeading: bearing + Math.PI,
        },
      ],
      longRange,
    );
    const blockedTarget = blockedWorld.units[1];
    expect(blockedTarget).toBeDefined();
    if (!blockedTarget) {
      return;
    }
    const blockedHp = blockedTarget.hp;
    for (let i = 0; i < 120; i += 1) {
      blockedWorld = step(blockedWorld, []);
    }
    expect(blockedWorld.units.find((unit) => unit.id === blockedTarget.id)?.hp).toBe(blockedHp);

    let openWorld = makeWorld(
      1,
      [
        { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, turretHeading: 0 },
        { owner: 2, typeId: 'unit.test.tank', x: -45, z: -50 },
      ],
      longRange,
    );
    const openTarget = openWorld.units[1];
    expect(openTarget).toBeDefined();
    if (!openTarget) {
      return;
    }
    const openHp = openTarget.hp;
    for (let i = 0; i < 40; i += 1) {
      openWorld = step(openWorld, []);
    }
    expect(openWorld.units.find((unit) => unit.id === openTarget.id)?.hp ?? 0).toBeLessThan(openHp);
  });

  it('[CMB-05] inaccuracy misses and perfect accuracy does not', () => {
    function shoot(accuracy: number): number {
      const shooter = tankType({
        armor: 0,
        weapon: {
          damage: 10,
          range: 20,
          reloadSec: 0.05,
          projectileSpeed: 100,
          accuracy,
          splashRadius: 0.5,
        },
      });
      let world = worldWithTypes(
        1,
        [
          { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, turretHeading: 0 },
          { owner: 2, typeId: 'unit.test.dummy', x: -45, z: -50 },
        ],
        [shooter, dummyType()],
      );
      const target = world.units[1];
      if (!target) {
        return 0;
      }
      const initial = target.hp;
      for (let i = 0; i < 250; i += 1) {
        world = step(world, []);
      }
      const current = world.units.find((unit) => unit.id === target.id);
      return initial - (current?.hp ?? initial);
    }
    const perfect = shoot(1);
    const inaccurate = shoot(0);
    expect(perfect).toBe(2500);
    expect(inaccurate).toBeGreaterThan(0);
    expect(inaccurate).toBeLessThan(perfect);
  });

  it('[CMB-06] splash damage hits friendly units too', () => {
    const type = tankType({
      weapon: {
        damage: 30,
        range: 12,
        reloadSec: 0.2,
        projectileSpeed: 40,
        accuracy: 1,
        splashRadius: 5,
      },
    });
    let world = makeWorld(
      1,
      [
        { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, turretHeading: 0 },
        { owner: 2, typeId: 'unit.test.tank', x: -45, z: -50 },
        { owner: 1, typeId: 'unit.test.tank', x: -44, z: -50 },
      ],
      type,
    );
    const enemy = world.units[1];
    const friendly = world.units[2];
    expect(enemy).toBeDefined();
    expect(friendly).toBeDefined();
    if (!enemy || !friendly) {
      return;
    }
    enemy.hp = 1000;
    friendly.hp = 1000;
    const initial = friendly.hp;
    for (let i = 0; i < 100; i += 1) {
      world = step(world, []);
    }
    const after = world.units.find((unit) => unit.id === friendly.id);
    expect(after?.hp ?? 0).toBeLessThan(initial);
  });

  it('[CMB-07] a skirmish ends, a wipe yields winner 1 and simultaneous kills draw', () => {
    let world = makeSkirmishWorld(1);
    const ids = world.units.filter((unit) => unit.owner === 1).map((unit) => unit.id);
    world = step(world, [{ kind: 'move', unitIds: ids, x: 50, z: 50, tick: 1, issuer: 1 }]);
    for (let i = 0; i < 12000 && !world.result; i += 1) {
      world = step(world, []);
    }
    expect(world.result).not.toBeNull();

    let wipe = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, turretHeading: 0 },
      { owner: 1, typeId: 'unit.test.tank', x: -48, z: -50, turretHeading: 0 },
      { owner: 2, typeId: 'unit.test.tank', x: -45, z: -50 },
    ]);
    const enemy = wipe.units[2];
    expect(enemy).toBeDefined();
    if (!enemy) {
      return;
    }
    enemy.hp = 1;
    const attackers = wipe.units.filter((unit) => unit.owner === 1).map((unit) => unit.id);
    wipe = step(wipe, [
      { kind: 'attack', unitIds: attackers, targetId: enemy.id, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 1000 && !wipe.result; i += 1) {
      wipe = step(wipe, []);
    }
    expect(wipe.result).toEqual({ winner: 1 });

    let draw = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 },
      { owner: 2, typeId: 'unit.test.tank', x: -45, z: -50 },
    ]);
    const one = draw.units[0];
    const two = draw.units[1];
    expect(one).toBeDefined();
    expect(two).toBeDefined();
    if (!one || !two) {
      return;
    }
    one.hp = 1;
    two.hp = 1;
    draw.projectiles.push(
      projectile({
        id: 2000,
        owner: 1,
        x: -48,
        y: heightAt(draw.map, -48, -50) + 1,
        z: -50,
        vx: 40,
        damage: 100,
      }),
      projectile({
        id: 2001,
        owner: 2,
        x: -47,
        y: heightAt(draw.map, -47, -50) + 1,
        z: -50,
        vx: -40,
        damage: 100,
      }),
    );
    draw = step(draw, []);
    expect(draw.result).toEqual({ winner: null });
  });
});
