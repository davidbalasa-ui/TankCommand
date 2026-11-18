import { describe, expect, it } from 'vitest';
import { createSkirmishWorld } from '../../src/data/simData';
import { thinkAi } from '../../src/ai/ai';
import { padLayout } from '../../src/sim/pad';
import { addUnit } from '../../src/sim/spawn';
import type { Command } from '../../src/sim/commands';
import type { AiState } from '../../src/sim/types';
import { data } from './aiHelpers';

describe('AI home spot', () => {
  it('[AI-15] units the AI sends home park past the pad exit, never on the landing pad', () => {
    const world = createSkirmishWorld(
      data,
      3,
      [
        { player: 1, faction: 'human', controller: 'ai', difficulty: 'hard' },
        { player: 2, faction: 'alien', controller: 'human' },
      ],
      { fog: false },
    );
    const pad = world.structures.find((item) => item.owner === 1)!;
    // A scout out on the map: with the enemy base already in view it is called home.
    const scout = addUnit(world, { owner: 1, typeId: 'unit.human.scout', x: 0, z: 0 })!;
    let state: AiState = { ...world.aiStates.find((entry) => entry.player === 1)!, scoutId: scout.id };
    const moves: Command[] = [];
    for (let tick = 0; tick < 200; tick += 1) {
      const result = thinkAi({ ...world, tick }, state);
      state = result.state;
      moves.push(...result.commands.filter((command) => command.kind === 'move' && command.unitIds.includes(scout.id)));
    }
    expect(moves.length).toBeGreaterThan(0);
    const layout = padLayout(world, pad);
    for (const command of moves) {
      if (command.kind !== 'move') {
        continue;
      }
      const fromPad = Math.hypot(command.x - pad.x, command.z - pad.z);
      const fromRally = Math.hypot(layout.rallyX - pad.x, layout.rallyZ - pad.z);
      expect(fromPad).toBeGreaterThan(fromRally);
    }
  });
});
