import { describe, expect, it } from 'vitest';
import { step } from '../../src/sim/world';
import { afterShot, damageAfterArmor, isLastShotOfBurst, weaponCycleSec } from '../../src/sim/weaponCycle';
import { buildUnitTypes, buildStructureTypes } from '../../src/data/simData';
import { loadStructureTable, loadUnitTable } from '../../src/data/dataRegistry';
import rawManifest from '../../public/assets/manifest.json';
import { parseAssetManifest } from '../../src/assets/manifestSchema';
import { AssetRegistry } from '../../src/assets/registry';
import units from '../../src/data/units.placeholder.json';
import structures from '../../src/data/structures.placeholder.json';
import type { WeaponStats } from '../../src/sim/types';
import { makeWorld } from './simHelpers';

const salvo: WeaponStats = {
  damage: 20,
  range: 12,
  reloadSec: 3,
  burst: 3,
  burstIntervalSec: 0.4,
  projectileSpeed: 40,
  accuracy: 1,
  splashRadius: 0.5,
  targets: ['ground', 'structure'],
};

function shotTicks(weapon: WeaponStats, ticks: number): number[] {
  let world = makeWorld(
    1,
    [
      { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, heading: Math.PI / 2, turretHeading: Math.PI / 2 },
      { owner: 2, typeId: 'unit.test.tank', x: -50, z: -42, heading: Math.PI },
    ],
    { weapon },
  );
  const target = world.units[1];
  if (target) {
    target.hp = 1_000_000;
  }
  const fired: number[] = [];
  for (let i = 0; i < ticks; i += 1) {
    const before = world.projectiles.filter((p) => p.owner === 1).length;
    world = step(world, []);
    const after = world.projectiles.filter((p) => p.owner === 1).length;
    if (after > before) {
      fired.push(world.tick);
    }
  }
  return fired;
}

describe('firing rhythm', () => {
  it('[CMB-08] a burst weapon fires its salvo at the set spacing, then reloads', () => {
    const ticks = shotTicks(salvo, 200);
    expect(ticks.length).toBeGreaterThanOrEqual(6);
    const gaps = ticks.slice(1).map((tick, i) => tick - (ticks[i] ?? 0));
    // 20 Hz: 0.4 s inside the salvo = 8 ticks; 3 s reload = 60 ticks.
    expect(gaps.slice(0, 5)).toEqual([8, 8, 60, 8, 8]);
  });

  it('[CMB-08] the fire-rate upgrade shortens the reload but not the burst spacing', () => {
    const state = { reloadLeft: 0, burstLeft: 0 };
    afterShot(state, salvo, true);
    expect(state.reloadLeft).toBeCloseTo(0.4, 6);
    afterShot(state, salvo, true);
    expect(state.reloadLeft).toBeCloseTo(0.4, 6);
    afterShot(state, salvo, true);
    expect(state.reloadLeft).toBeLessThan(3);
    expect(state.burstLeft).toBe(0);
    expect(weaponCycleSec(salvo)).toBeCloseTo(3.8, 6);
  });

  it('[CMB-08] aircraft spend one ammo per burst, not per shot', () => {
    const state = { reloadLeft: 0, burstLeft: 0 };
    let ammoSpent = 0;
    for (let shot = 0; shot < 6; shot += 1) {
      if (isLastShotOfBurst(state, salvo)) {
        ammoSpent += 1;
      }
      afterShot(state, salvo, false);
    }
    expect(ammoSpent).toBe(2);
  });

  it('[CMB-03] armor never stops more than 75% of a hit', () => {
    expect(damageAfterArmor(8, 9)).toBe(2);
    expect(damageAfterArmor(70, 9)).toBe(61);
    expect(damageAfterArmor(3, 4)).toBe(1);
  });

  it('[CMB-09] every armed unit and turret has a role-fitting firing pattern', () => {
    const unitTypes = buildUnitTypes(loadUnitTable(units, new AssetRegistry(parseAssetManifest(rawManifest))));
    const structureTypes = buildStructureTypes(loadStructureTable(structures));
    const weapon = (id: string): WeaponStats => {
      const found = unitTypes.get(id)?.weapon ?? structureTypes.get(id)?.weapon;
      if (!found) {
        throw new Error(`no weapon on ${id}`);
      }
      return found;
    };
    for (const side of ['human', 'alien']) {
      const scout = weapon(side === 'human' ? 'unit.human.scout' : 'unit.alien.light_skimmer');
      const heavy = weapon(`unit.${side}.heavy_tank`);
      const artillery = weapon(`unit.${side}.artillery`);
      const light = weapon(`unit.${side}.light_tank`);
      // Scouts: rapid, light shots.
      expect(scout.burst ?? 1).toBeGreaterThan(1);
      expect(scout.damage).toBeLessThan(light.damage / 2);
      // Heavy tanks: one big shot at a time, the hardest single hit of any tank.
      expect(heavy.burst ?? 1).toBe(1);
      expect(heavy.damage).toBeGreaterThan(light.damage * 2);
      // Artillery: three shells within about a second, then a reload of about three.
      expect(artillery.burst).toBe(3);
      expect((artillery.burst! - 1) * (artillery.burstIntervalSec ?? 0)).toBeLessThanOrEqual(1);
      expect(artillery.reloadSec).toBeCloseTo(3, 1);
    }
    // No two different roles in a faction share the same pattern.
    for (const side of ['human', 'alien']) {
      const seen = new Map<string, string>();
      for (const type of unitTypes.values()) {
        if (type.faction !== side || !type.weapon) {
          continue;
        }
        const w = type.weapon;
        const key = `${w.damage}/${w.burst ?? 1}/${w.burstIntervalSec ?? 0}/${w.reloadSec}`;
        const other = seen.get(key);
        expect(other, `${type.id} fires exactly like ${other}`).toBeUndefined();
        seen.set(key, type.id);
      }
    }
  });
});
