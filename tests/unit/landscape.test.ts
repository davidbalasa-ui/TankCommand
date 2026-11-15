import { describe, expect, it } from 'vitest';
import { scatterProps } from '../../src/render/landscape';
import { generateMap, isBlockedAt, isWaterAt } from '../../src/sim/map';

const BIG = new Set(['prop.nature.cliff', 'prop.nature.boulder']);

describe('[LND] map scenery', () => {
  it('[LND-01] scenery is fixed per map, big rocks only on undrivable ground, nothing in water', () => {
    const map = generateMap(42);
    const a = scatterProps(map);
    const b = scatterProps(generateMap(42));
    expect(a.length).toBeGreaterThan(100);
    expect(a.map((p) => `${p.prop}@${p.x.toFixed(3)},${p.z.toFixed(3)}`)).toEqual(
      b.map((p) => `${p.prop}@${p.x.toFixed(3)},${p.z.toFixed(3)}`),
    );
    for (const placed of a) {
      expect(isWaterAt(map, placed.x, placed.z)).toBe(false);
      if (BIG.has(placed.prop)) {
        expect(isBlockedAt(map, placed.x, placed.z), `${placed.prop} at ${placed.x},${placed.z}`).toBe(true);
      }
    }
  });
});
