import { describe, expect, it } from 'vitest';
import { createSkirmishWorld } from '../../src/data/simData';
import { addUnit } from '../../src/sim/spawn';
import { step } from '../../src/sim/world';
import { SIM_TICK_HZ } from '../../src/sim/constants';
import { PROJECTILE_RANGE_OVERSHOOT } from '../../src/sim/tuning';
import type { WorldState } from '../../src/sim/types';
import { data } from './aiHelpers';

// Fire `shooterType` at a target `distance` m away for a while; return how far each shot got from
// its shooter before it ended, and the hp of a bystander standing far behind the target.
function shots(shooterType: string, distance: number): { reach: number[]; bystanderHurt: boolean; speed: number; range: number } {
  let world: WorldState = createSkirmishWorld(
    data,
    11,
    [
      { player: 1, faction: 'human', controller: 'human' },
      { player: 2, faction: 'alien', controller: 'human' },
    ],
    { fog: false },
  );
  const shooter = addUnit(world, { owner: 1, typeId: shooterType, x: -36, z: -20 })!;
  const target = addUnit(world, { owner: 2, typeId: 'unit.alien.heavy_tank', x: -36 + distance, z: -20 })!;
  const bystander = addUnit(world, { owner: 2, typeId: 'unit.alien.heavy_tank', x: -36 + distance + 30, z: -20 })!;
  target.stance = 'hold';
  bystander.stance = 'hold';
  world = step(world, [{ kind: 'attack', unitIds: [shooter.id], targetId: target.id, tick: world.tick + 1, issuer: 1 }]);
  const last = new Map<number, { x: number; z: number }>();
  const reach: number[] = [];
  for (let tick = 0; tick < 40 * SIM_TICK_HZ; tick += 1) {
    world = step(world, []);
    const live = new Set(world.projectiles.map((p) => p.id));
    for (const [id, at] of last) {
      if (!live.has(id)) {
        reach.push(Math.hypot(at.x - shooter.x, at.z - shooter.z));
        last.delete(id);
      }
    }
    for (const p of world.projectiles) {
      if (p.owner === 1) {
        last.set(p.id, { x: p.x, z: p.z });
      }
    }
    const t = world.units.find((unit) => unit.id === target.id);
    if (t) {
      t.hp = world.unitTypes.get(t.typeId)!.hp; // keep the target standing
    }
  }
  const weapon = world.unitTypes.get(shooterType)!.weapon!;
  const hurt = world.units.find((unit) => unit.id === bystander.id);
  return {
    reach,
    bystanderHurt: !hurt || hurt.hp < world.unitTypes.get(hurt.typeId)!.hp,
    speed: weapon.projectileSpeed,
    range: weapon.range,
  };
}

describe('projectile range', () => {
  it('[CMB-10] a missed shell bursts at the aimed point and a missed direct shot dies just past its range', () => {
    const shell = shots('unit.human.artillery', 26);
    expect(shell.reach.length).toBeGreaterThan(5);
    for (const reach of shell.reach) {
      // One tick of flight is the most a burst can be off the aimed point.
      expect(reach).toBeLessThanOrEqual(26 + shell.speed / SIM_TICK_HZ + 0.5);
    }
    expect(shell.bystanderHurt).toBe(false);

    const cannon = shots('unit.human.light_tank', 10);
    expect(cannon.reach.length).toBeGreaterThan(5);
    for (const reach of cannon.reach) {
      expect(reach).toBeLessThanOrEqual(cannon.range * PROJECTILE_RANGE_OVERSHOOT + cannon.speed / SIM_TICK_HZ + 0.5);
    }
    expect(cannon.bystanderHurt).toBe(false);
  });
});
