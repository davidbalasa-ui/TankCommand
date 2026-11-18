import { describe, expect, it } from 'vitest';
import { planShellArc, shellArcPoint } from '../../src/render/shellArc';
import { isArcingWeapon } from '../../src/sim/weaponCycle';
import { data } from './aiHelpers';

describe('shell arc', () => {
  it('[PART-03] artillery shells leave the muzzle, arc up and land on the burst point without ever flying backwards', () => {
    // Both factions' artillery (Longbow, Mortar Beast) fire arcing shells; direct-fire guns don't.
    const artillery = [...data.unitTypes.values()].filter((type) => type.role === 'artillery');
    expect(artillery.length).toBeGreaterThanOrEqual(2);
    for (const type of artillery) {
      expect(isArcingWeapon(type.weapon?.kind), type.id).toBe(true);
    }
    expect(isArcingWeapon(data.unitTypes.get('unit.human.light_tank')?.weapon?.kind)).toBe(false);

    const launch = { x: -36, y: 1.5, z: -36 };
    // Fired along +x; the Longbow's barrel tip sits ~5 m ahead and 4 m up.
    const muzzle = { x: -31, y: 5.5, z: -35.6 };
    for (const aim of [28, 9, 4]) {
      const arc = planShellArc(launch, muzzle, 25, 0, aim, 1);
      const start = shellArcPoint(arc, 0);
      const end = shellArcPoint(arc, 1);
      if (aim > 9) {
        expect(start.x).toBeCloseTo(muzzle.x, 6);
        expect(start.y).toBeCloseTo(muzzle.y, 6);
      }
      expect(end.x).toBeCloseTo(launch.x + aim, 6);
      expect(end.y).toBeCloseTo(1, 6);
      let previous = start;
      let top = start.y;
      for (let i = 1; i <= 50; i += 1) {
        const point = shellArcPoint(arc, i / 50);
        // Always forward along the line of fire, even at point-blank range.
        expect(point.x - previous.x, `aim ${aim} step ${i}`).toBeGreaterThan(0);
        top = Math.max(top, point.y);
        previous = point;
      }
      // A real arc: it climbs above both ends.
      expect(top).toBeGreaterThan(Math.max(start.y, end.y) + 0.3);
    }
  });
});
