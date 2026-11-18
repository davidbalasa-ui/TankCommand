import { describe, expect, it } from 'vitest';
import { data, runMatch } from './aiHelpers';
import { createSkirmishWorld } from '../../src/data/simData';

// The designed skirmish maps (tools/missions/skirmish.py): two AIs play each one to the end.
const maps = data.mapRows.filter((row) => !row.campaignOnly && !row.placeholder);
const SEEDS = [1, 2];
const LIMIT_MIN = 30;

describe('[MAP-04] AI-vs-AI on every designed skirmish map', () => {
  it('[MAP-04] there are at least four designed maps, two of them for four sides', () => {
    expect(maps.length).toBeGreaterThanOrEqual(4);
    expect(maps.filter((row) => row.starts.length === 4).length).toBeGreaterThanOrEqual(2);
  });

  for (const row of maps) {
    for (const seed of SEEDS) {
      it(`[MAP-04] ${row.name} seed ${seed}: the match ends with a winner inside ${LIMIT_MIN} minutes`, () => {
        // Factions swap with the seed so each side of the map is played by both.
        const first = seed % 2 === 1 ? 'human' : 'alien';
        const second = first === 'human' ? 'alien' : 'human';
        const world = createSkirmishWorld(
          data,
          seed,
          [
            { player: 1, faction: first, controller: 'ai', difficulty: 'normal' },
            { player: 2, faction: second, controller: 'ai', difficulty: 'normal' },
          ],
          { mapId: row.id },
        );
        const { world: end, tick } = runMatch(world, LIMIT_MIN);
        expect(end.result?.winner ?? null, `${row.id} seed ${seed} after ${(tick / 1200).toFixed(1)} min`).not.toBeNull();
      }, 300_000);
    }
  }
});
