import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { isAllied, isHostile, relation } from '../../src/sim/diplomacy';
import type { Command } from '../../src/sim/commands';
import type { SideState, StartUnit, WorldState } from '../../src/sim/types';
import { padType, tankType } from './simHelpers';

type Untimed = Command extends infer C ? (C extends Command ? Omit<C, 'tick'> : never) : never;

function side(player: number, controller: SideState['controller'], team = player, extra: Partial<SideState> = {}): SideState {
  return { player, controller, team, groupId: null, provokable: true, forgiveAfterSec: null, ...extra };
}

function build(sides: SideState[], units: StartUnit[], pads = true): WorldState {
  const tank = tankType();
  const pad = padType();
  return createWorld(1, {
    unitTypes: new Map([[tank.id, tank]]),
    structureTypes: new Map([[pad.id, pad]]),
    sides,
    startUnits: units,
    startStructures: pads
      ? sides
          .filter((item) => item.controller === 'human' || item.controller === 'ai')
          .map((item, index) => ({ owner: item.player, typeId: pad.id, x: -60 + index * 5, z: -60 }))
      : [],
    factions: sides.map((item) => ({ player: item.player, faction: 'human' as const })),
  });
}

function run(world: WorldState, commands: Untimed[], ticks: number): WorldState {
  let state = world;
  const stamped = commands.map((command) => ({ ...command, tick: world.tick + 1 }) as Command);
  for (let i = 0; i < ticks; i += 1) {
    state = step(state, i === 0 ? stamped : []);
  }
  return state;
}

const unit = (owner: number, x: number, z: number): StartUnit => ({ owner, typeId: 'unit.test.tank', x, z });
const hp = (world: WorldState, owner: number): number[] =>
  world.units.filter((item) => item.owner === owner).map((item) => item.hp);

describe('diplomacy', () => {
  it('[DIP-01] every ordered pair has a relation, defaults follow teams and controllers, and it survives save/load', () => {
    const world = build(
      [side(1, 'human', 1), side(2, 'ai', 2), side(3, 'ai', 1), side(4, 'scripted')],
      [unit(1, 0, 20), unit(2, 0, 28)],
    );
    expect(world.relations).toHaveLength(12);
    expect(relation(world, 1, 3)).toBe('allied');
    expect(relation(world, 1, 2)).toBe('hostile');
    expect(relation(world, 1, 4)).toBe('neutral');
    expect(relation(world, 4, 2)).toBe('neutral');
    const restored = decodeSave(encodeSave(world, { gameVersion: 't', savedAtIso: 'x' }));
    expect(restored.ok).toBe(true);
    if (restored.ok) {
      expect(hashWorld(restored.world)).toBe(hashWorld(world));
      expect(isHostile(restored.world, 1, 2)).toBe(true);
    }
    for (const file of ['src/sim/world.ts', 'src/sim/structures.ts', 'src/sim/repair.ts']) {
      const text = readFileSync(file, 'utf8');
      expect(text).not.toMatch(/owner (===|!==) (unit|turret|projectile|medic)\.owner/);
    }
  });

  it('[DIP-02] units engage only hostile targets', () => {
    const world = build(
      [side(1, 'human'), side(2, 'ai'), side(3, 'ai', 1), side(4, 'scripted')],
      [unit(1, 0, 20), unit(3, 0, 22), unit(4, 15, 24), unit(2, 0, 28)],
    );
    const after = run(world, [], 10 * 20);
    expect(Math.min(...hp(after, 2))).toBeLessThan(hp(world, 2)[0] ?? 0);
    expect(hp(after, 4)).toEqual(hp(world, 4));
  });

  it('[DIP-03] hitting a neutral turns it hostile toward the attacker only, its group follows, set and forgive work', () => {
    let world = build(
      [
        side(1, 'human'),
        side(2, 'ai'),
        side(4, 'scripted', 4, { groupId: 'town' }),
        side(5, 'scripted', 5, { groupId: 'town', forgiveAfterSec: 10 }),
        side(6, 'scripted', 6),
      ],
      [unit(1, 0, 20), unit(4, 0, 28), unit(5, 30, 28), unit(6, 40, 28)],
    );
    const target = world.units.find((item) => item.owner === 4)?.id ?? 0;
    const attacker = world.units.find((item) => item.owner === 1)?.id ?? 0;
    world = run(world, [{ kind: 'attack', issuer: 1, unitIds: [attacker], targetId: target }], 6 * 20);
    expect(relation(world, 4, 1)).toBe('hostile');
    expect(relation(world, 5, 1)).toBe('hostile');
    expect(relation(world, 6, 1)).toBe('neutral');
    expect(relation(world, 4, 2)).toBe('neutral');
    world = run(world, [{ kind: 'diplomacy.set', issuer: 1, a: 4, b: 2, relation: 'allied', oneWay: true }], 1);
    expect(relation(world, 4, 2)).toBe('allied');
    expect(relation(world, 2, 4)).toBe('neutral');
    expect(isAllied(world, 4, 2)).toBe(true);
    // Group member 5 has a forgive timer; once the fight stops it calms down.
    world = run(world, [{ kind: 'stop', issuer: 1, unitIds: [attacker] }], 12 * 20);
    expect(relation(world, 5, 1)).toBe('neutral');
  });

  it('[DIP-05] a world with three armed sides and a neutral keeps a team result and the hash across save/load', () => {
    let world = build(
      [side(1, 'human', 1), side(2, 'ai', 1), side(3, 'ai', 3), side(4, 'scripted')],
      [unit(1, 0, 20), unit(2, 5, 20), unit(3, 0, 28), unit(4, 40, 40)],
    );
    world = run(world, [], 40);
    const restored = decodeSave(encodeSave(world, { gameVersion: 't', savedAtIso: 'x' }));
    expect(restored.ok).toBe(true);
    if (!restored.ok) {
      return;
    }
    expect(hashWorld(restored.world)).toBe(hashWorld(world));
    const a = run(world, [], 20 * 90);
    const b = run(restored.world, [], 20 * 90);
    expect(hashWorld(a)).toBe(hashWorld(b));
    const reduced = a;
    reduced.units = reduced.units.filter((item) => item.owner !== 3);
    reduced.structures = reduced.structures.filter((item) => item.owner !== 3);
    reduced.result = null;
    const finished = run(reduced, [], 2);
    expect([1, 2]).toContain(finished.result?.winner);
    const neutralOnly = build([side(4, 'scripted')], [unit(4, 0, 20)], false);
    expect(run(neutralOnly, [], 5).result).toBeNull();
  });
});
