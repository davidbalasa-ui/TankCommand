import { describe, expect, it } from 'vitest';
import { generateMap, isBlockedAt, slopeAt } from '../../src/sim/map';
import { findPath } from '../../src/sim/pathfinding';
import { MAX_SLOPE } from '../../src/sim/tuning';

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
