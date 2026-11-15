import rawManifest from '../../public/assets/manifest.json';
import { parseAssetManifest } from '../../src/assets/manifestSchema';
import { AssetRegistry } from '../../src/assets/registry';
import { createSkirmishWorld, loadSimData } from '../../src/data/simData';
import { stepWithAi } from '../../src/ai/driver';
import { hashWorld } from '../../src/sim/world';
import type { AiDifficulty, WorldState } from '../../src/sim/types';

export const data = loadSimData(new AssetRegistry(parseAssetManifest(rawManifest)));

export function aiMatch(seed: number, a: AiDifficulty, b: AiDifficulty, fog = true): WorldState {
  return createSkirmishWorld(
    data,
    seed,
    [
      { player: 1, faction: 'human', controller: 'ai', difficulty: a },
      { player: 2, faction: 'alien', controller: 'ai', difficulty: b },
    ],
    { fog },
  );
}

export function runMatch(world: WorldState, maxMinutes: number): { world: WorldState; tick: number } {
  let state = world;
  const limit = maxMinutes * 60 * 20;
  while (state.result === null && state.tick < limit) {
    state = stepWithAi(state);
  }
  return { world: state, tick: state.tick };
}

export { hashWorld, stepWithAi };
