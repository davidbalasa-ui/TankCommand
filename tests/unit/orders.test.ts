import { describe, expect, it } from 'vitest';
import { step } from '../../src/sim/world';
import { makeWorld } from './simHelpers';

describe('orders', () => {
  it('[ORD-01] hold stops a moving unit, fires at enemies in range and never moves', () => {
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, heading: 0, turretHeading: 0 },
      { owner: 2, typeId: 'unit.test.tank', x: -45, z: -50, heading: Math.PI, turretHeading: Math.PI },
    ]);
    const ownId = world.units[0]?.id ?? 0;
    const enemyId = world.units[1]?.id ?? 0;
    expect(ownId).toBeGreaterThan(0);
    expect(enemyId).toBeGreaterThan(0);

    world = step(world, [
      { kind: 'move', unitIds: [ownId], x: 50, z: 50, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 10; i += 1) {
      world = step(world, []);
    }
    const moving = world.units.find((u) => u.id === ownId);
    expect(moving).toBeDefined();
    if (!moving) return;
    expect(moving.order.kind).toBe('move');

    world = step(world, [
      { kind: 'hold', unitIds: [ownId], tick: world.tick + 1, issuer: 1 },
    ]);
    const afterHold = world.units.find((u) => u.id === ownId);
    expect(afterHold).toBeDefined();
    if (!afterHold) return;
    expect(afterHold.stance).toBe('hold');
    expect(afterHold.order.kind).toBe('idle');

    const freezeX = afterHold.x;
    const freezeZ = afterHold.z;
    const enemyHpStart = world.units.find((u) => u.id === enemyId)?.hp ?? 0;
    const ownHpStart = afterHold.hp;

    for (let i = 0; i < 120; i += 1) {
      world = step(world, []);
    }
    const final = world.units.find((u) => u.id === ownId);
    const enemyFinal = world.units.find((u) => u.id === enemyId);
    expect(final).toBeDefined();
    if (!final) return;
    expect(final.x).toBeCloseTo(freezeX, 5);
    expect(final.z).toBeCloseTo(freezeZ, 5);

    // It fired at the enemy while holding.
    expect(enemyFinal).toBeDefined();
    if (!enemyFinal) return;
    expect(enemyFinal.hp).toBeLessThan(enemyHpStart);
    // And it was attacked (it took damage) without moving.
    expect(final.hp).toBeLessThan(ownHpStart);
  });

  it('[ORD-02] attack-move engages an enemy met on the way then continues', () => {
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, heading: 0, turretHeading: 0 },
      { owner: 2, typeId: 'unit.test.tank', x: -20, z: -50 },
    ]);
    const ownId = world.units[0]?.id ?? 0;
    const enemyId = world.units[1]?.id ?? 0;
    // The intruder is weak enough to be cleared before it can kill the attacker.
    const intruder = world.units.find((u) => u.id === enemyId);
    expect(intruder).toBeDefined();
    if (!intruder) return;
    intruder.hp = 60;

    world = step(world, [
      { kind: 'attackMove', unitIds: [ownId], x: 20, z: -50, tick: 1, issuer: 1 },
    ]);
    let killed = false;
    for (let i = 0; i < 4000; i += 1) {
      world = step(world, []);
      if (!world.units.some((u) => u.id === enemyId)) {
        killed = true;
        break;
      }
    }
    expect(killed, 'the intruder was engaged and destroyed on the way').toBe(true);

    for (let i = 0; i < 4000; i += 1) {
      world = step(world, []);
      const own = world.units.find((u) => u.id === ownId);
      if (!own) break;
      if (own.order.kind === 'idle') break;
    }
    const final = world.units.find((u) => u.id === ownId);
    expect(final).toBeDefined();
    if (!final) return;
    expect(Math.hypot(final.x - 20, final.z + 50)).toBeLessThan(20);
  });

  it('[ORD-03] queued waypoints append to the order and are followed in order', () => {
    // The world needs a living opponent for the *whole* test. `step` ignores
    // commands once `world.result` is set, and a world whose only player is
    // player 1 is decided on the very first tick — a later queued order would
    // then be silently dropped and the unit would still hold its original,
    // non-queued move. A single distant enemy keeps the skirmish open without
    // letting either side engage.
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 },
      { owner: 2, typeId: 'unit.test.tank', x: 50, z: 50 },
    ]);
    const ownId = world.units.find((unit) => unit.owner === 1)?.id ?? 0;
    expect(ownId).toBeGreaterThan(0);

    // Both waypoints sit inside the flat disc `generateMap` flattens around the
    // player start, so `findPath` accepts them verbatim and the last point of
    // each path is the exact waypoint. The second waypoint is a right-angle turn
    // away from the first, so "in order" is a real ordering, not a collinear
    // coincidence.
    const firstWaypoint = { x: -40, z: -50 };
    const secondWaypoint = { x: -50, z: -40 };

    world = step(world, [
      {
        kind: 'move',
        unitIds: [ownId],
        x: firstWaypoint.x,
        z: firstWaypoint.z,
        tick: 1,
        issuer: 1,
        queue: false,
      },
    ]);
    for (let i = 0; i < 3; i += 1) {
      world = step(world, []);
    }
    expect(world.result, 'the match is still running so commands are accepted').toBeNull();

    const pending = world.units.find((unit) => unit.id === ownId);
    expect(pending).toBeDefined();
    if (!pending) return;
    expect(pending.order.kind).toBe('move');
    expect(pending.path.length).toBeGreaterThan(0);

    world = step(world, [
      {
        kind: 'move',
        unitIds: [ownId],
        x: secondWaypoint.x,
        z: secondWaypoint.z,
        tick: world.tick + 1,
        issuer: 1,
        queue: true,
      },
    ]);

    const queued = world.units.find((unit) => unit.id === ownId);
    expect(queued).toBeDefined();
    if (!queued) return;
    expect(queued.order.kind, 'a queued waypoint keeps the move order').toBe('move');
    if (queued.order.kind === 'move') {
      expect(queued.order.queue, 'the order is the queued one').toBe(true);
      expect(
        Math.hypot(queued.order.x - secondWaypoint.x, queued.order.z - secondWaypoint.z),
        'the queued order targets the second waypoint',
      ).toBeLessThan(1.5);
    }

    // Appended, not replacing: the first waypoint is still in the path, and it
    // comes before the queued one. `followPath` consumes the path front to back,
    // so this is the order the unit drives through.
    const firstIndex = queued.path.findIndex(
      (point) => Math.hypot(point.x - firstWaypoint.x, point.z - firstWaypoint.z) <= 1.5,
    );
    const secondIndex = queued.path.findIndex(
      (point) => Math.hypot(point.x - secondWaypoint.x, point.z - secondWaypoint.z) <= 1.5,
    );
    expect(firstIndex, 'the first waypoint is still in the appended path').toBeGreaterThanOrEqual(0);
    expect(secondIndex, 'the queued waypoint is in the appended path').toBeGreaterThan(firstIndex);

    for (let i = 0; i < 2000; i += 1) {
      world = step(world, []);
      const unit = world.units.find((item) => item.id === ownId);
      if (!unit || unit.order.kind === 'idle') {
        break;
      }
    }
    const final = world.units.find((unit) => unit.id === ownId);
    expect(final).toBeDefined();
    if (!final) return;
    expect(
      Math.hypot(final.x - secondWaypoint.x, final.z - secondWaypoint.z),
      'the unit finished at the queued waypoint',
    ).toBeLessThanOrEqual(1);
  });
});
