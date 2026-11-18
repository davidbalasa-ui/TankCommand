import { describe, expect, it } from 'vitest';
import { createSkirmishWorld } from '../../src/data/simData';
import { thinkAi } from '../../src/ai/ai';
import { sideAlive, sideStranded } from '../../src/sim/match';
import { step } from '../../src/sim/world';
import type { WorldState } from '../../src/sim/types';
import { data } from './aiHelpers';

// A mined-out Utopia Basin: every ore field empty, both sides down to a few units and pocket change.
function minedOut(controller: 'human' | 'ai'): WorldState {
  const world = createSkirmishWorld(
    data,
    2006,
    [
      { player: 1, faction: 'human', controller, difficulty: 'hard' },
      { player: 2, faction: 'alien', controller, difficulty: 'hard' },
    ],
    { mapId: 'map.wp02_skirmish', fog: false },
  );
  for (const deposit of world.deposits) {
    deposit.amount = deposit.kind === 'ore' ? 0 : deposit.amount;
  }
  for (const entry of world.resources) {
    entry.ore = 30;
    entry.metal = 0;
  }
  return world;
}

function removeUnits(world: WorldState, player: number, keep: (role: string) => boolean): void {
  world.units = world.units.filter(
    (unit) => unit.owner !== player || keep(world.unitTypes.get(unit.typeId)?.role ?? ''),
  );
}

describe('skirmish endgame', () => {
  it('[MATCH-03] a side left with only a pad, no fighters, no money and no ore to mine is eliminated', () => {
    const world = minedOut('human');
    removeUnits(world, 2, () => false);
    expect(sideAlive(world, 2)).toBe(true);
    expect(sideStranded(world, 2)).toBe(true);
    const next = step(world, []);
    expect(next.result).toEqual({ winner: 1 });
  });

  it('[MATCH-03b] a pad-only side stays in while it can still buy a fighter, mine ore, or get one delivered', () => {
    // Enough money for a tank.
    const rich = minedOut('human');
    removeUnits(rich, 2, () => false);
    rich.resources.find((entry) => entry.player === 2)!.ore = 100;
    expect(sideStranded(rich, 2)).toBe(false);
    expect(step(rich, []).result).toBeNull();

    // Ore still in the ground and a miner to dig it.
    const mining = minedOut('human');
    removeUnits(mining, 2, (role) => role === 'worker');
    mining.deposits.find((deposit) => deposit.kind === 'ore')!.amount = 200;
    expect(sideStranded(mining, 2)).toBe(false);

    // Workers it could salvage for the price of a tank still count as a way back.
    const salvage = minedOut('human');
    removeUnits(salvage, 2, (role) => role === 'worker');
    salvage.resources.find((entry) => entry.player === 2)!.ore = 60;
    expect(sideStranded(salvage, 2)).toBe(false);

    // A fighting unit keeps the side alive.
    const armed = minedOut('human');
    expect(sideStranded(armed, 2)).toBe(false);

    // Missions keep their own rule (sideAlive, used by the mission triggers): a pad is enough there,
    // since scripted reinforcements may still come.
    const mission = minedOut('human');
    removeUnits(mission, 1, () => false);
    expect(sideStranded(mission, 1)).toBe(true);
    expect(sideAlive(mission, 1)).toBe(true);
  });

  it('[AI-13] once the ore is gone and nothing more can be bought, the AI attacks with whatever army is left', () => {
    const world = minedOut('ai');
    // One light tank left: far below any attack threshold.
    let kept = false;
    world.units = world.units.filter((unit) => {
      if (unit.owner !== 1 || world.unitTypes.get(unit.typeId)?.role !== 'tank') {
        return true;
      }
      if (kept) {
        return false;
      }
      kept = true;
      return true;
    });
    world.tick = 20 * 60 * 20;
    const tank = world.units.find((unit) => unit.owner === 1 && world.unitTypes.get(unit.typeId)?.role === 'tank')!;
    const state = world.aiStates.find((entry) => entry.player === 1)!;
    const attacks = [];
    for (let tick = world.tick; tick < world.tick + 200; tick += 1) {
      const commands = thinkAi({ ...world, tick }, state).commands;
      attacks.push(...commands.filter((command) => command.kind === 'attackMove' && command.unitIds.includes(tank.id)));
    }
    expect(attacks.length).toBeGreaterThan(0);

    // With ore still in the ground the same lone tank waits for reinforcements.
    const waiting = minedOut('ai');
    waiting.deposits.find((deposit) => deposit.kind === 'ore')!.amount = 400;
    waiting.units = waiting.units.filter((unit) => unit.owner !== 1 || unit.id === tank.id || waiting.unitTypes.get(unit.typeId)?.role !== 'tank');
    const waitState = waiting.aiStates.find((entry) => entry.player === 1)!;
    const early = [];
    for (let tick = world.tick; tick < world.tick + 200; tick += 1) {
      const commands = thinkAi({ ...waiting, tick }, waitState).commands;
      early.push(...commands.filter((command) => command.kind === 'attackMove' && command.unitIds.includes(tank.id)));
    }
    expect(early).toHaveLength(0);
  });
});
