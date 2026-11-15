import type { Command } from '../sim/commands';
import { step } from '../sim/world';
import type { AiDifficulty, PlayerId, WorldState } from '../sim/types';
import { createAiState, thinkAi } from './ai';

export function addAi(world: WorldState, player: PlayerId, difficulty: AiDifficulty): void {
  world.aiStates = [
    ...world.aiStates.filter((item) => item.player !== player),
    createAiState(player, difficulty, world.seed),
  ].sort((a, b) => a.player - b.player);
}

// Advance one tick with every AI side thinking first; AI commands go through the same validated
// command channel as the player's.
export function stepWithAi(world: WorldState, commands: Command[] = []): WorldState {
  const aiCommands: Command[] = [];
  const states = world.aiStates.map((state) => {
    const result = thinkAi(world, state);
    aiCommands.push(...result.commands);
    return result.state;
  });
  const next = step(world, [...commands, ...aiCommands]);
  next.aiStates = states;
  return next;
}
