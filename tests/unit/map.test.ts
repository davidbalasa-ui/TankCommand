import { describe, expect, it } from 'vitest';
import { generateMap, isBlockedAt, mapFor, slopeAt } from '../../src/sim/map';
import { findPath } from '../../src/sim/pathfinding';
import { MAX_SLOPE } from '../../src/sim/tuning';
import { createSkirmishWorld } from '../../src/data/simData';
import { data } from './aiHelpers';

describe('map', () => {
  it('[MAP-01] same seed produces identical heights and different seeds differ', () => {
    const a = generateMap(123);
    const b = generateMap(123);
    const c = generateMap(124);
    expect(Array.from(a.heights)).toEqual(Array.from(b.heights));
    expect(Array.from(a.heights)).not.toEqual(Array.from(c.heights));
  });

  it('[MAP-02] start areas are flat and connected by an A* path', () => {
    const map = generateMap(7);
    for (const center of [
      { x: -50, z: -50 },
      { x: 50, z: 50 },
    ]) {
      for (let dz = -10; dz <= 10; dz += 5) {
        for (let dx = -10; dx <= 10; dx += 5) {
          expect(slopeAt(map, center.x + dx, center.z + dz)).toBeLessThan(MAX_SLOPE);
          expect(isBlockedAt(map, center.x + dx, center.z + dz)).toBe(false);
        }
      }
    }
    const path = findPath(map, -50, -50, 50, 50);
    expect(path).not.toBeNull();
    expect(path?.length ?? 0).toBeGreaterThan(1);
  });
});

describe('skirmish maps', () => {
  const skirmishMaps = data.mapRows.filter((row) => !row.campaignOnly);
  const allSpecs = [1, 2, 3, 4].map((player) => ({
    player,
    faction: (player % 2 === 1 ? 'human' : 'alien') as 'human' | 'alien',
    controller: 'human' as const,
  }));

  it('[MAP-03] ground units can drive between every pair of start positions on every skirmish map', () => {
    expect(skirmishMaps.length).toBeGreaterThanOrEqual(6);
    expect(skirmishMaps.filter((row) => row.starts.length === 4).length).toBeGreaterThanOrEqual(2);
    for (const row of skirmishMaps) {
      // A side on every start the map has (two or four); two-start maps also get the two extra
      // corners createSkirmishWorld falls back on for a third or fourth side.
      const specs = allSpecs.slice(0, Math.max(row.starts.length, row.placeholder ? 4 : 2));
      for (const seed of [1, 7, 1000, 1001, 2006, 424242]) {
        const world = createSkirmishWorld(data, seed, specs, { mapId: row.id, fog: false });
        // Terrain alone decides whether the bases are joined; buildings and sites only add detours.
        const view = mapFor(world.map, 'tracked');
        const anchors = specs.map((spec) => {
          const pad = world.structures.find(
            (structure) => structure.owner === spec.player && world.structureTypes.get(structure.typeId)?.kind === 'pad',
          );
          expect(pad, `${row.id} side ${spec.player}`).toBeDefined();
          return pad ?? { x: 0, z: 0 };
        });
        for (let a = 0; a < anchors.length; a += 1) {
          for (let b = 0; b < anchors.length; b += 1) {
            const from = anchors[a];
            const to = anchors[b];
            if (a === b || !from || !to) {
              continue;
            }
            const path = findPath(view, from.x, from.z, to.x, to.z);
            const end = path?.[path.length - 1];
            const gap = end ? Math.hypot(end.x - to.x, end.z - to.z) : Number.POSITIVE_INFINITY;
            expect(gap, `${row.id} seed ${seed}: start ${a + 1} -> start ${b + 1}`).toBeLessThan(1);
          }
        }
      }
    }
  });

  it('[SKR-01] four-player maps seat at most three sides, and side 3 sits as far from side 1 as from side 2', () => {
    // Three AI sides (four sides of 64 units, 256) would go past the 192-unit stress test (C-08), so a
    // four-player map seats you plus up to two AI; start 4 stays empty.
    for (const row of skirmishMaps.filter((r) => r.starts.length === 4 && !r.placeholder)) {
      const [p1, p2, p3] = row.starts;
      const d = (a: { x: number; z: number }, b: { x: number; z: number }): number => Math.hypot(a.x - b.x, a.z - b.z);
      expect(Math.abs(d(p3!, p1!) - d(p3!, p2!)), row.id).toBeLessThan(0.5);
      // Sides 1 and 2 face each other across the map, so a one-on-one match is corner to corner.
      expect(d(p1!, p2!), row.id).toBeGreaterThan(d(p3!, p1!));
    }
  });
});
