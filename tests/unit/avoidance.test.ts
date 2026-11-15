import { describe, expect, it } from 'vitest';
import { hashWorld, step } from '../../src/sim/world';
import { UNIT_RADIUS } from '../../src/sim/tuning';
import type { Command } from '../../src/sim/commands';
import type { WorldState } from '../../src/sim/types';
import { makeWorld as makeHillyWorld } from './simHelpers';

const TANK = 'unit.test.tank';

// Flat ground, so paths are straight lines and only the units shape the routes.
function makeWorld(...args: Parameters<typeof makeHillyWorld>): WorldState {
  const world = makeHillyWorld(...args);
  world.map.heights.fill(0);
  return world;
}
const SEC = 20;

function closestPair(world: WorldState): number {
  let best = Infinity;
  const ground = world.units.filter((unit) => !unit.air && unit.hp > 0);
  for (let i = 0; i < ground.length; i += 1) {
    for (let j = i + 1; j < ground.length; j += 1) {
      const a = ground[i];
      const b = ground[j];
      if (a && b) {
        best = Math.min(best, Math.hypot(a.x - b.x, a.z - b.z));
      }
    }
  }
  return best;
}

function run(world: WorldState, ticks: number, first: Command[] = []): { world: WorldState; closest: number } {
  let state = step(world, first);
  let closest = closestPair(state);
  for (let i = 1; i < ticks; i += 1) {
    state = step(state, []);
    closest = Math.min(closest, closestPair(state));
  }
  return { world: state, closest };
}

// Commands must carry the tick they run on (the world's next tick).
function move(ids: number[], x: number, z: number, tick = 1): Command {
  return { kind: 'move', unitIds: ids, x, z, tick, issuer: 1 };
}

describe('[AVD] unit avoidance', () => {
  it('[AVD-01] two friendly tanks driving head-on pass each other instead of colliding', () => {
    const world = makeWorld(3, [
      { owner: 1, typeId: TANK, x: -20, z: 0 },
      { owner: 1, typeId: TANK, x: 20, z: 0 },
    ]);
    const [a, b] = world.units;
    let state = step(world, [move([a!.id], 20, 0), move([b!.id], -20, 0)]);
    let closest = Infinity;
    for (let i = 0; i < 20 * SEC; i += 1) {
      state = step(state, []);
      closest = Math.min(closest, closestPair(state));
    }
    // They steer apart before touching, passing with a gap rather than being shoved apart.
    expect(closest).toBeGreaterThan(UNIT_RADIUS * 2 + 0.2);
    const endA = state.units.find((u) => u.id === a!.id);
    const endB = state.units.find((u) => u.id === b!.id);
    expect(Math.hypot((endA?.x ?? 0) - 20, endA?.z ?? 99)).toBeLessThan(3);
    expect(Math.hypot((endB?.x ?? 0) + 20, endB?.z ?? 99)).toBeLessThan(3);
  });

  it('[AVD-02] a parked friendly tank steps aside for one driving through it', () => {
    const world = makeWorld(3, [
      { owner: 1, typeId: TANK, x: -20, z: 0 },
      { owner: 1, typeId: TANK, x: 0, z: 0 },
    ]);
    const [mover, parked] = world.units;
    const { world: end, closest } = run(world, 15 * SEC, [move([mover!.id], 20, 0)]);
    expect(closest).toBeGreaterThan(UNIT_RADIUS * 2 + 0.2);
    const moved = end.units.find((u) => u.id === mover!.id);
    expect(Math.hypot((moved?.x ?? 0) - 20, moved?.z ?? 99)).toBeLessThan(3);
    const stood = end.units.find((u) => u.id === parked!.id);
    expect(stood?.order.kind).toBe('idle');
  });

  it('[AVD-03] a crowd ordered onto one spot settles: everyone stops, nobody overlaps', () => {
    const start = [];
    for (let i = 0; i < 12; i += 1) {
      start.push({ owner: 1 as const, typeId: TANK, x: -30 + (i % 4) * 4, z: -6 + Math.floor(i / 4) * 4 });
    }
    const world = makeWorld(5, start);
    const ids = world.units.map((u) => u.id);
    const { world: end } = run(world, 40 * SEC, [move(ids, 20, 0)]);
    for (const unit of end.units) {
      expect(unit.order.kind, `unit ${unit.id}`).toBe('idle');
      expect(unit.speed).toBeLessThan(0.1);
    }
    expect(closestPair(end)).toBeGreaterThan(UNIT_RADIUS * 2 - 0.05);
    // They gathered at the goal rather than stalling on the way.
    const cx = end.units.reduce((sum, u) => sum + u.x, 0) / end.units.length;
    expect(cx).toBeGreaterThan(10);
  });

  it('[AVD-04] avoidance is deterministic', () => {
    const start = [];
    for (let i = 0; i < 10; i += 1) {
      start.push({ owner: 1 as const, typeId: TANK, x: -30 + (i % 5) * 4, z: -4 + Math.floor(i / 5) * 6 });
    }
    start.push({ owner: 1 as const, typeId: TANK, x: 25, z: 0 });
    const world = makeWorld(9, start);
    const ids = world.units.slice(0, 10).map((u) => u.id);
    const last = world.units[10]!.id;
    const cmds = [move(ids, 25, 0), move([last], -30, 0)];
    const a = run(world, 30 * SEC, cmds).world;
    const b = run(makeWorld(9, start), 30 * SEC, cmds).world;
    expect(hashWorld(a)).toBe(hashWorld(b));
  });
});
