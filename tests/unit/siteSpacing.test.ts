import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { isBlockedAt } from '../../src/sim/map';
import skirmishMaps from '../../src/data/maps.placeholder.json';

// Ore and metal sites sit at least 12 m clear of every landing pad's edge, so pad traffic
// (arrivals driving off, haulers queueing at the delivery spots) has room.
const MIN_GAP = 12;
const PAD_HALF = 6;

function padGap(px: number, pz: number, x: number, z: number): number {
  return Math.hypot(Math.max(0, Math.abs(x - px) - PAD_HALF), Math.max(0, Math.abs(z - pz) - PAD_HALF));
}

describe('[SITE-01] ore and metal sites stand clear of landing pads', () => {
  it('[SITE-01] skirmish maps keep every site 12 m or more from both start pads', () => {
    for (const map of skirmishMaps as Array<{ id: string; starts: Array<{ x: number; z: number }>; deposits: Array<{ x: number; z: number }> }>) {
      for (const start of map.starts) {
        for (const site of map.deposits) {
          expect(padGap(start.x, start.z, site.x, site.z), `${map.id} (${site.x},${site.z})`).toBeGreaterThanOrEqual(MIN_GAP);
        }
      }
    }
  });

  it('[SITE-01] every campaign mission keeps sites 12 m or more from its pads, on open ground', () => {
    const campaign = MISSIONS.filter((m) => m.campaign !== 'training');
    expect(campaign.length).toBeGreaterThan(0);
    for (const row of campaign) {
      const world = buildMissionWorld(data, row, 1);
      const pads = world.structures.filter((s) => world.structureTypes.get(s.typeId)?.kind === 'pad');
      for (const site of world.deposits) {
        expect(isBlockedAt(world.map, site.x, site.z), `${row.id} site (${site.x},${site.z}) on blocked ground`).toBe(false);
        for (const pad of pads) {
          expect(padGap(pad.x, pad.z, site.x, site.z), `${row.id} pad (${pad.x},${pad.z}) site (${site.x},${site.z})`).toBeGreaterThanOrEqual(MIN_GAP);
        }
      }
    }
  });
});
