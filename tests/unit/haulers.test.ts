import { describe, expect, it } from 'vitest';
import { createSkirmishWorld } from '../../src/data/simData';
import { addStructure } from '../../src/sim/spawn';
import { step } from '../../src/sim/world';
import type { WorldState } from '../../src/sim/types';
import { data } from './aiHelpers';

// Utopia Basin's real corners: the first metal station on each side sits where the planned path
// ends a little over STATION_REACH from the station centre (the QA soak's frozen-hauler spot).
function stationWorld(seed: number): WorldState {
  const world = createSkirmishWorld(
    data,
    seed,
    [
      { player: 1, faction: 'human', controller: 'human' },
      { player: 2, faction: 'alien', controller: 'human' },
    ],
    { mapId: 'map.wp02_skirmish', fog: false },
  );
  addStructure(world, { owner: 1, typeId: 'structure.human.metal_station', x: -70, z: -56 });
  addStructure(world, { owner: 2, typeId: 'structure.alien.metal_station', x: 70, z: 56 });
  return world;
}

describe('haulers', () => {
  it('[ECO-07] a hauler loops metal station -> pad -> station again and again without stalling', () => {
    for (const seed of [1000, 1001, 2006]) {
      let world = stationWorld(seed);
      const tugs = world.units.filter((unit) => world.unitTypes.get(unit.typeId)?.workerKind === 'tug');
      expect(tugs).toHaveLength(2);
      const deliveries = new Map<number, number>(tugs.map((tug) => [tug.owner, 0]));
      const late = new Map<number, number>(tugs.map((tug) => [tug.owner, 0]));
      const ticks = 3 * 60 * 20;
      const lastMetal = new Map<number, number>(world.resources.map((entry) => [entry.player, entry.metal]));
      // Three game minutes (before the 250-metal site runs dry): a working hauler makes many trips.
      for (let tick = 0; tick < ticks; tick += 1) {
        world = step(world, []);
        for (const entry of world.resources) {
          if (entry.metal > (lastMetal.get(entry.player) ?? 0)) {
            deliveries.set(entry.player, (deliveries.get(entry.player) ?? 0) + 1);
            if (tick >= ticks / 2) {
              late.set(entry.player, (late.get(entry.player) ?? 0) + 1);
            }
          }
          lastMetal.set(entry.player, entry.metal);
        }
      }
      for (const [player, count] of deliveries) {
        expect(count, `seed ${seed} side ${player} metal deliveries`).toBeGreaterThanOrEqual(10);
        // Still hauling in the second half: the loop keeps going, it doesn't freeze after a trip.
        expect(late.get(player) ?? 0, `seed ${seed} side ${player} late deliveries`).toBeGreaterThanOrEqual(5);
      }
    }
  });
});
