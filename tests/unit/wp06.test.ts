import { describe, expect, it } from 'vitest';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { heightAt, lineOfSightClear } from '../../src/sim/map';
import { cellState, perceivedUnits, updateVision } from '../../src/sim/vision';
import { STEALTH_SIGHT_FACTOR } from '../../src/sim/tuning';
import type { SideState, SimUnitType, StartUnit, WorldState } from '../../src/sim/types';
import { padType, tankType } from './simHelpers';

function side(player: number, team = player, controller: SideState['controller'] = 'ai'): SideState {
  return { player, controller, team, groupId: null, provokable: true, forgiveAfterSec: null };
}

function scout(): SimUnitType {
  return tankType({ id: 'unit.test.scout', weapon: null, sightRange: 14, sensorRange: 30 });
}

function radar(): SimUnitType {
  return tankType({ id: 'unit.test.radar', weapon: null, sightRange: 10, sensorRange: 70 });
}

function build(units: StartUnit[], sides: SideState[] = [side(1, 1, 'human'), side(2)]): WorldState {
  const types = new Map<string, SimUnitType>();
  for (const t of [tankType({ weapon: null }), scout(), radar()]) {
    types.set(t.id, t);
  }
  const pad = padType();
  return createWorld(1, {
    unitTypes: types,
    structureTypes: new Map([[pad.id, pad]]),
    sides,
    startUnits: units,
    startStructures: [],
    factions: sides.map((item) => ({ player: item.player, faction: 'human' as const })),
  });
}

const u = (owner: number, typeId: string, x: number, z: number): StartUnit => ({ owner, typeId, x, z });

function run(world: WorldState, ticks: number): WorldState {
  let state = world;
  for (let i = 0; i < ticks; i += 1) {
    state = step(state, []);
  }
  return state;
}

function findPair(world: WorldState, wantClear: boolean): { a: [number, number]; b: [number, number] } {
  for (let x = -90; x < 90; x += 3) {
    for (let z = -90; z < 90; z += 3) {
      const b: [number, number] = [x + 10, z];
      const clear = lineOfSightClear(
        world.map, x, z, heightAt(world.map, x, z) + 1.5, b[0], b[1], heightAt(world.map, b[0], b[1]) + 1,
      );
      if (clear === wantClear) {
        return { a: [x, z], b };
      }
    }
  }
  throw new Error('no pair');
}

describe('vision', () => {
  it('[FOG-01] cells are unexplored, explored or visible and explored cells stay explored', () => {
    let world = build([u(1, 'unit.test.tank', 0, 0), u(2, 'unit.test.tank', 80, 80)]);
    expect(cellState(world, 1, 0, 0)).toBe(2);
    expect(cellState(world, 1, 60, 60)).toBe(0);
    const unit = world.units[0];
    if (!unit) {
      throw new Error('missing');
    }
    unit.x = 50;
    unit.z = 50;
    world = run(world, 8);
    expect(cellState(world, 1, 0, 0)).toBe(1);
    expect(cellState(world, 1, 50, 50)).toBe(2);
    world = run(world, 40);
    expect(cellState(world, 1, 0, 0)).toBe(1);
  });

  it('[FOG-02] a ridge blocks sight but open ground does not', () => {
    const base = build([]);
    const blocked = findPair(base, false);
    const open = findPair(base, true);
    const test = (pair: { a: [number, number]; b: [number, number] }): boolean => {
      const world = build([u(1, 'unit.test.tank', pair.a[0], pair.a[1]), u(2, 'unit.test.tank', pair.b[0], pair.b[1])]);
      return perceivedUnits(world, 1).units.some((unit) => unit.owner === 2);
    };
    expect(test(blocked)).toBe(false);
    expect(test(open)).toBe(true);
  });

  it('[FOG-03] enemies in sensor range but outside sight are anonymous contacts; radar extends it', () => {
    let world = build([u(1, 'unit.test.scout', 0, 0), u(2, 'unit.test.tank', 24, 0)]);
    let view = perceivedUnits(world, 1);
    expect(view.units.some((unit) => unit.owner === 2)).toBe(false);
    expect(view.contacts).toHaveLength(1);
    expect(Object.keys(view.contacts[0] ?? {}).sort()).toEqual(['x', 'z']);
    world = build([u(1, 'unit.test.tank', 0, 0), u(2, 'unit.test.tank', 50, 0)]);
    expect(perceivedUnits(world, 1).contacts).toHaveLength(0);
    world = build([u(1, 'unit.test.tank', 0, 0), u(1, 'unit.test.radar', 0, 4), u(2, 'unit.test.tank', 50, 0)]);
    expect(perceivedUnits(world, 1).contacts).toHaveLength(1);
  });

  it('[FOG-04] stealthed units are never contacts and are seen only at reduced range', () => {
    const near = 14 * STEALTH_SIGHT_FACTOR - 1;
    let world = build([u(1, 'unit.test.scout', 0, 0), u(2, 'unit.test.tank', 24, 0)]);
    const sneaky = world.units.find((unit) => unit.owner === 2);
    if (!sneaky) {
      throw new Error('missing');
    }
    sneaky.upgrades = ['stealth'];
    updateVision(world, true);
    expect(perceivedUnits(world, 1).contacts).toHaveLength(0);
    sneaky.x = 10;
    updateVision(world, true);
    expect(perceivedUnits(world, 1).units.some((unit) => unit.owner === 2)).toBe(false);
    sneaky.x = near;
    updateVision(world, true);
    expect(perceivedUnits(world, 1).units.some((unit) => unit.owner === 2)).toBe(true);
    world = run(world, 1);
  });

  it('[FOG-06] perceivedUnits never leaks hidden enemies: moving a hidden one changes nothing', () => {
    const world = build([u(1, 'unit.test.tank', -80, -80), u(2, 'unit.test.tank', 70, 70)]);
    const before = JSON.stringify(perceivedUnits(world, 1));
    for (const [x, z] of [[80, 80], [60, 90], [90, 40], [40, 90]] as const) {
      const moved = structuredClone(world) as WorldState;
      const enemy = moved.units.find((unit) => unit.owner === 2);
      if (enemy) {
        enemy.x = x;
        enemy.z = z;
      }
      expect(JSON.stringify(perceivedUnits(moved, 1))).toBe(before);
    }
    expect(JSON.stringify(perceivedUnits(world, 1))).not.toContain('"owner":2');
  });

  it('[FOG-06] remembered structures stay as ghosts out of sight and vanish when seen destroyed', () => {
    const pad = padType();
    const types = new Map<string, SimUnitType>([[scout().id, scout()]]);
    let world = createWorld(1, {
      unitTypes: types,
      structureTypes: new Map([[pad.id, pad]]),
      sides: [side(1, 1, 'human'), side(2)],
      startUnits: [u(1, 'unit.test.scout', 0, 0)],
      startStructures: [{ owner: 2, typeId: pad.id, x: 8, z: 0 }],
    });
    expect(perceivedUnits(world, 1).structures).toHaveLength(1);
    const scoutUnit = world.units[0];
    if (!scoutUnit) {
      throw new Error('missing');
    }
    scoutUnit.x = -80;
    scoutUnit.z = -80;
    world = run(world, 8);
    const away = perceivedUnits(world, 1);
    expect(away.structures).toHaveLength(0);
    expect(away.ghosts).toHaveLength(1);
    const enemyPad = world.structures[0];
    const scoutNow = world.units[0];
    if (enemyPad && scoutNow) {
      enemyPad.hp = 0;
      scoutNow.x = 0;
      scoutNow.z = 0;
    }
    world = run(world, 8);
    expect(perceivedUnits(world, 1).ghosts).toHaveLength(0);
  });

  it('[DIP-04] allied sides share vision; neutral and hostile do not', () => {
    const sides = [side(1, 1, 'human'), side(2, 1), side(3), side(4, 4, 'scripted')];
    const world = build(
      [
        u(1, 'unit.test.tank', -70, -70),
        u(2, 'unit.test.tank', 60, 60),
        u(3, 'unit.test.tank', 62, 60),
        u(4, 'unit.test.tank', 58, 60),
      ],
      sides,
    );
    const owners = perceivedUnits(world, 1).units.map((unit) => unit.owner).sort();
    expect(owners).toEqual([1, 2, 3, 4]);
    const loner = build(
      [u(1, 'unit.test.tank', -70, -70), u(3, 'unit.test.tank', 62, 60), u(4, 'unit.test.tank', 58, 60)],
      sides,
    );
    expect(perceivedUnits(loner, 1).units.map((unit) => unit.owner)).toEqual([1]);
  });

  it('[DET-04] vision is deterministic and survives save/load with an identical hash', () => {
    const world = run(build([u(1, 'unit.test.scout', 0, 0), u(2, 'unit.test.tank', 24, 0)]), 30);
    const restored = decodeSave(encodeSave(world, { gameVersion: 't', savedAtIso: 'x' }));
    expect(restored.ok).toBe(true);
    if (!restored.ok) {
      return;
    }
    expect(hashWorld(restored.world)).toBe(hashWorld(world));
    expect(hashWorld(run(restored.world, 40))).toBe(hashWorld(run(world, 40)));
  });
});
