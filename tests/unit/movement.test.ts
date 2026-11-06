import { describe, expect, it } from 'vitest';
import { generateMap, isBlockedAt, isBlockedCell, cellCenter } from '../../src/sim/map';
import { hashWorld, step } from '../../src/sim/world';
import { Rng } from '../../src/sim/rng';
import { UNIT_RADIUS } from '../../src/sim/tuning';
import { makeWorld } from './simHelpers';

describe('movement', () => {
  it('[MOVE-01] a single tank arrives within 0.5 units in the expected time', () => {
    let world = makeWorld(1, [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    const goal = { x: -40, z: -50 };
    world = step(world, [
      { kind: 'move', unitIds: [1], x: goal.x, z: goal.z, tick: 1, issuer: 1 },
    ]);
    let ticks = 1;
    while (ticks < 2000 && world.units[0]?.order.kind !== 'idle') {
      world = step(world, []);
      ticks += 1;
    }
    const unit = world.units[0];
    expect(unit).toBeDefined();
    if (!unit) {
      return;
    }
    expect(Math.hypot(unit.x - goal.x, unit.z - goal.z)).toBeLessThanOrEqual(0.5);
    expect(ticks / 20).toBeLessThan((10 / 8) * 2 + 5);
  });

  it('[MOVE-02] a tank routed behind the ridge goes around and never enters a blocked cell', () => {
    let world = makeWorld(1, [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    world = step(world, [
      { kind: 'move', unitIds: [1], x: 50, z: 50, tick: 1, issuer: 1 },
    ]);
    const unit = world.units[0];
    expect(unit).toBeDefined();
    if (!unit) {
      return;
    }
    const start = { x: -50, z: -50 };
    let pathLength = 0;
    let previous = start;
    for (const point of unit.path) {
      pathLength += Math.hypot(point.x - previous.x, point.z - previous.z);
      previous = point;
    }
    expect(pathLength).toBeGreaterThan(Math.hypot(100, 100));

    for (let i = 0; i < 3000; i += 1) {
      world = step(world, []);
      const current = world.units[0];
      if (!current) {
        break;
      }
      expect(isBlockedAt(world.map, current.x, current.z)).toBe(false);
      if (current.order.kind === 'idle' && i > 50) {
        break;
      }
    }
  });

  it('[MOVE-03] orders outside the map are clamped and units never leave the map', () => {
    let world = makeWorld(1, [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    const rng = new Rng(99);
    for (let tick = 0; tick < 5000; tick += 1) {
      if (tick % 50 === 0) {
        const x = (rng.next() * 2 - 1) * 400;
        const z = (rng.next() * 2 - 1) * 400;
        world = step(world, [
          { kind: 'move', unitIds: [1], x, z, tick: world.tick + 1, issuer: 1 },
        ]);
      } else {
        world = step(world, []);
      }
      const unit = world.units[0];
      expect(unit).toBeDefined();
      if (!unit) {
        return;
      }
      expect(unit.x).toBeGreaterThanOrEqual(-80);
      expect(unit.x).toBeLessThanOrEqual(80);
      expect(unit.z).toBeGreaterThanOrEqual(-80);
      expect(unit.z).toBeLessThanOrEqual(80);
      if (unit.order.kind === 'move') {
        expect(unit.order.x).toBeGreaterThanOrEqual(-80);
        expect(unit.order.x).toBeLessThanOrEqual(80);
        expect(unit.order.z).toBeGreaterThanOrEqual(-80);
        expect(unit.order.z).toBeLessThanOrEqual(80);
      }
    }
  });

  it('[MOVE-04] twelve tanks settle without overlaps and without active orders', () => {
    const starts = Array.from({ length: 12 }, (_, index) => ({
      owner: 1,
      typeId: 'unit.test.tank',
      x: -50 + (index % 4) * 4,
      z: -50 + Math.floor(index / 4) * 4,
    }));
    let world = makeWorld(1, starts);
    const ids = world.units.map((unit) => unit.id);
    world = step(world, [
      { kind: 'move', unitIds: ids, x: -20, z: -20, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 5000; i += 1) {
      world = step(world, []);
      if (world.units.every((unit) => unit.order.kind === 'idle')) {
        break;
      }
    }
    for (const unit of world.units) {
      expect(unit.order.kind).toBe('idle');
    }
    for (let i = 0; i < world.units.length; i += 1) {
      for (let j = i + 1; j < world.units.length; j += 1) {
        const a = world.units[i];
        const b = world.units[j];
        if (!a || !b) {
          continue;
        }
        expect(Math.hypot(a.x - b.x, a.z - b.z)).toBeGreaterThanOrEqual(
          UNIT_RADIUS * 2 - 0.05,
        );
      }
    }
  });

  it('[MOVE-05] a destination inside a blocked area stops at the nearest reachable cell', () => {
    const map = generateMap(1);
    let blocked: { x: number; z: number } | null = null;
    for (let cz = 0; cz < map.rows && !blocked; cz += 1) {
      for (let cx = 0; cx < map.cols; cx += 1) {
        if (isBlockedCell(map, cx, cz)) {
          blocked = cellCenter(map, cx, cz);
          break;
        }
      }
    }
    expect(blocked).not.toBeNull();
    if (!blocked) {
      return;
    }
    let world = makeWorld(1, [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 }]);
    world = step(world, [
      { kind: 'move', unitIds: [1], x: blocked.x, z: blocked.z, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 3000; i += 1) {
      world = step(world, []);
      if (world.units[0]?.order.kind === 'idle') {
        break;
      }
    }
    const unit = world.units[0];
    expect(unit).toBeDefined();
    if (!unit) {
      return;
    }
    expect(isBlockedAt(world.map, unit.x, unit.z)).toBe(false);
    expect(Math.hypot(unit.x - blocked.x, unit.z - blocked.z)).toBeLessThan(20);
  });

  it('[MOVE-06] commands for units the issuer does not own change nothing', () => {
    const starts = [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 }];
    let a = makeWorld(1, starts);
    let b = makeWorld(1, starts);
    a = step(a, [
      { kind: 'move', unitIds: [1], x: -40, z: -40, tick: 1, issuer: 2 },
    ]);
    b = step(b, []);
    expect(hashWorld(a)).toBe(hashWorld(b));
  });
});
