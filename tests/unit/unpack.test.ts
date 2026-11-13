import { describe, expect, it } from 'vitest';
import { data, stepWithAi } from './aiHelpers';
import { createSkirmishWorld } from '../../src/data/simData';
import type { Command } from '../../src/sim/commands';
import type { WorldState } from '../../src/sim/types';

// Overhaul step 5: every structure but the landing pad lands packed and drives out to unpack.
function match(): WorldState {
  const world = createSkirmishWorld(
    data,
    3,
    [
      { player: 1, faction: 'human', controller: 'human' },
      { player: 2, faction: 'alien', controller: 'ai', difficulty: 'easy' },
    ],
    { fog: false },
  );
  for (const stats of world.resources) {
    stats.ore = 5000;
    stats.metal = 1000;
  }
  const side = world.research.find((item) => item.player === 1);
  const done = ['research.human.sensors', 'research.human.fortifications'];
  if (side) {
    side.done.push(...done);
  } else {
    world.research.push({ player: 1, done, active: null, queue: [] });
  }
  expect(world.result).toBeNull();
  return world;
}

function run(world: WorldState, commands: Command[], ticks: number): WorldState {
  let next = world;
  for (let i = 0; i < ticks; i += 1) {
    next = stepWithAi(next, i === 0 ? commands.map((c) => ({ ...c, tick: next.tick + 1 })) : []);
  }
  return next;
}

function pad(world: WorldState): { id: number; x: number; z: number } {
  const found = world.structures.find((s) => s.owner === 1 && world.structureTypes.get(s.typeId)?.kind === 'pad');
  if (!found) {
    throw new Error('no pad');
  }
  return found;
}

const SEC = 20;

describe('structures as vehicles', () => {
  it('[PACK-01] a bought building lands packed at 40% health, drives to a suggested spot and unpacks there by itself', () => {
    let world = match();
    const home = pad(world);
    world = run(world, [{ kind: 'buy', tick: 0, issuer: 1, itemId: 'structure.human.radar', padId: home.id } as Command], 1);
    expect(world.lastCommandOutcome).toMatchObject({ kind: 'buy', ok: true });
    expect(world.result).toBeNull();
    // Wait for the drop to come down.
    let packed = world.units.find((u) => u.typeId === 'unit.human.radar_tower_packed');
    for (let i = 0; i < 120 && !packed; i += 1) {
      world = run(world, [], SEC);
      packed = world.units.find((u) => u.typeId === 'unit.human.radar_tower_packed');
    }
    expect(packed).toBeDefined();
    expect(world.pendingKits.filter((k) => k.owner === 1)).toHaveLength(0);
    const radarType = world.structureTypes.get('structure.human.radar');
    expect(packed?.hp).toBe(Math.round((radarType?.hp ?? 0) * 0.4));
    expect(packed?.deployTarget).toBeTruthy();
    // It unpacks on its own, away from the pad, at full health.
    let radar = world.structures.find((s) => s.typeId === 'structure.human.radar');
    for (let i = 0; i < 60 && !radar; i += 1) {
      world = run(world, [], SEC);
      radar = world.structures.find((s) => s.typeId === 'structure.human.radar');
    }
    expect(radar).toBeDefined();
    expect(radar?.hp).toBe(radarType?.hp);
    expect(Math.hypot((radar?.x ?? 0) - home.x, (radar?.z ?? 0) - home.z)).toBeGreaterThan(8);
    expect(world.units.some((u) => u.typeId === 'unit.human.radar_tower_packed')).toBe(false);
  });

  it('[PACK-01] a metal station drives to the nearest free metal site', () => {
    let world = match();
    const home = pad(world);
    world = run(world, [{ kind: 'buy', tick: 0, issuer: 1, itemId: 'structure.human.metal_station', padId: home.id } as Command], 1);
    let station = world.structures.find((s) => s.owner === 1 && s.typeId === 'structure.human.metal_station');
    for (let i = 0; i < 180 && !station; i += 1) {
      world = run(world, [], SEC);
      station = world.structures.find((s) => s.owner === 1 && s.typeId === 'structure.human.metal_station');
    }
    expect(station).toBeDefined();
    const site = world.deposits.find((d) => d.id === station?.depositId);
    expect(site?.kind).toBe('metal');
    const nearest = world.deposits
      .filter((d) => d.kind === 'metal')
      .sort((a, b) => Math.hypot(a.x - home.x, a.z - home.z) - Math.hypot(b.x - home.x, b.z - home.z))[0];
    expect(site?.id).toBe(nearest?.id);
  });

  it('[PACK-02] tapping the ground redirects a packed building; it unpacks there, and packed buildings never count as army', () => {
    let world = match();
    const home = pad(world);
    world = run(world, [{ kind: 'buy', tick: 0, issuer: 1, itemId: 'structure.human.turret', padId: home.id } as Command], 1);
    let packed = world.units.find((u) => u.typeId === 'unit.human.turret_packed');
    for (let i = 0; i < 120 && !packed; i += 1) {
      world = run(world, [], 5);
      packed = world.units.find((u) => u.typeId === 'unit.human.turret_packed');
    }
    expect(packed).toBeDefined();
    if (!packed) {
      return;
    }
    const goal = { x: home.x + (home.x > 0 ? -30 : 30), z: home.z };
    world = run(world, [{ kind: 'move', tick: 0, issuer: 1, unitIds: [packed.id], x: goal.x, z: goal.z } as Command], 1);
    const target = world.units.find((u) => u.id === packed?.id)?.deployTarget;
    expect(target).toBeTruthy();
    expect(Math.hypot((target?.x ?? 0) - goal.x, (target?.z ?? 0) - goal.z)).toBeLessThan(19);
    let tower = world.structures.find((s) => s.owner === 1 && s.typeId === 'structure.human.turret');
    for (let i = 0; i < 60 && !tower; i += 1) {
      world = run(world, [], SEC);
      tower = world.structures.find((s) => s.owner === 1 && s.typeId === 'structure.human.turret');
    }
    expect(tower).toBeDefined();
    expect(Math.hypot((tower?.x ?? 0) - (target?.x ?? 0), (tower?.z ?? 0) - (target?.z ?? 0))).toBeLessThan(0.01);

    // Stop keeps a packed building packed where it is.
    world = run(world, [{ kind: 'pack', tick: 0, issuer: 1, structureId: tower?.id ?? 0 } as Command], 6 * SEC);
    const repacked = world.units.find((u) => u.owner === 1 && u.typeId === 'unit.human.turret_packed');
    expect(repacked).toBeDefined();
    const before = world.units.filter((u) => u.owner === 1).length;
    world = run(world, [{ kind: 'stop', tick: 0, issuer: 1, unitIds: [repacked?.id ?? 0] } as Command], 10 * SEC);
    expect(world.units.find((u) => u.id === repacked?.id)?.deployTarget ?? null).toBeNull();
    expect(world.units.filter((u) => u.owner === 1)).toHaveLength(before);
  });
});
