import { describe, expect, it } from 'vitest';
import { createSkirmishWorld } from '../../src/data/simData';
import { thinkAi } from '../../src/ai/ai';
import { addUnit } from '../../src/sim/spawn';
import { step } from '../../src/sim/world';
import type { Command } from '../../src/sim/commands';
import type { UnitState, WorldState } from '../../src/sim/types';
import { data } from './aiHelpers';

function world(controller: 'human' | 'ai' = 'human'): WorldState {
  return createSkirmishWorld(
    data,
    5,
    [
      { player: 1, faction: 'human', controller, difficulty: 'hard' },
      { player: 2, faction: 'alien', controller: 'human' },
    ],
    { fog: false },
  );
}

function flying(state: WorldState, x: number, z: number): UnitState {
  const fighter = addUnit(state, { owner: 2, typeId: 'unit.alien.fighter', x, z })!;
  fighter.air!.mode = 'flying';
  fighter.order = { kind: 'move', x: x + 40, z: z + 40, queue: false };
  return fighter;
}

const attack = (state: WorldState, unitIds: number[], targetId: number): Command => ({
  kind: 'attack',
  unitIds,
  targetId,
  tick: state.tick + 1,
  issuer: 1,
});

describe('attack orders', () => {
  it('[ORD-04] units that cannot hit the target ignore an attack order; workers keep their jobs', () => {
    let state = world();
    const tank = addUnit(state, { owner: 1, typeId: 'unit.human.light_tank', x: -30, z: -30 })!;
    const missile = addUnit(state, { owner: 1, typeId: 'unit.human.missile_tank', x: -28, z: -34 })!;
    const miner = state.units.find((unit) => unit.owner === 1 && state.unitTypes.get(unit.typeId)?.workerKind === 'oreMiner')!;
    const deposit = state.deposits.find((item) => item.kind === 'ore')!;
    state = step(state, [{ kind: 'mine', unitIds: [miner.id], depositId: deposit.id, tick: state.tick + 1, issuer: 1 }]);
    const fighter = flying(state, -20, -30);
    const tankOrder = state.units.find((unit) => unit.id === tank.id)!.order;

    state = step(state, [attack(state, [tank.id, miner.id, missile.id], fighter.id)]);
    const after = (id: number): UnitState => state.units.find((unit) => unit.id === id)!;
    // The missile tank hits air and takes the order; the cannon tank and the miner don't.
    expect(state.unitTypes.get(missile.typeId)?.weapon?.targets).toContain('air');
    expect(after(missile.id).order).toEqual({ kind: 'attack', targetId: fighter.id });
    expect(after(tank.id).order).toEqual(tankOrder);
    expect(after(miner.id).order.kind).not.toBe('attack');
    expect(after(miner.id).job?.kind).toBe('oreMiner');

    // Nobody in the selection can hit it: the order is refused with a reason.
    state = step(state, [attack(state, [tank.id, miner.id], fighter.id)]);
    expect(state.lastCommandOutcome).toMatchObject({ kind: 'attack', ok: false, reason: 'cannotHit' });
    expect(after(tank.id).order.kind).not.toBe('attack');

    // A ground target is still fair game for the tank.
    const enemyTank = addUnit(state, { owner: 2, typeId: 'unit.alien.light_tank', x: -10, z: -10 })!;
    state = step(state, [attack(state, [tank.id, miner.id], enemyTank.id)]);
    expect(after(tank.id).order).toEqual({ kind: 'attack', targetId: enemyTank.id });
    expect(after(miner.id).job?.kind).toBe('oreMiner');
  });

  it('[ORD-05] repeating an attack order on the same target keeps the unit driving at speed', () => {
    const run = (every: number): number => {
      let state = world();
      const tank = addUnit(state, { owner: 1, typeId: 'unit.human.heavy_tank', x: -30, z: -40 })!;
      const target = addUnit(state, { owner: 2, typeId: 'unit.alien.light_tank', x: 30, z: -40 })!;
      target.stance = 'hold';
      state = step(state, [attack(state, [tank.id], target.id)]);
      const start = state.units.find((unit) => unit.id === tank.id)!;
      const from = { x: start.x, z: start.z };
      for (let tick = 1; tick < 10 * 20; tick += 1) {
        state = step(state, every > 0 && tick % every === 0 ? [attack(state, [tank.id], target.id)] : []);
      }
      const end = state.units.find((unit) => unit.id === tank.id)!;
      return Math.hypot(end.x - from.x, end.z - from.z);
    };
    const once = run(0);
    expect(once).toBeGreaterThan(20);
    // Re-sent every half second (a player tapping again to confirm): the same distance covered.
    expect(run(10)).toBeGreaterThan(once * 0.95);
  });

  it('[AI-14] the AI never sends ground-only guns after aircraft in flight', () => {
    const state = world('ai');
    const tanks = [
      addUnit(state, { owner: 1, typeId: 'unit.human.light_tank', x: -20, z: -20 })!,
      addUnit(state, { owner: 1, typeId: 'unit.human.heavy_tank', x: -22, z: -18 })!,
    ];
    const missile = addUnit(state, { owner: 1, typeId: 'unit.human.missile_tank', x: -18, z: -22 })!;
    const fighter = flying(state, -16, -16);
    fighter.order = { kind: 'idle' };
    state.tick = 6000;
    let aiState = state.aiStates.find((entry) => entry.player === 1)!;
    const orders: Command[] = [];
    for (let tick = state.tick; tick < state.tick + 400; tick += 1) {
      const result = thinkAi({ ...state, tick }, aiState);
      aiState = result.state;
      orders.push(...result.commands);
    }
    const onFighter = orders.filter((command) => command.kind === 'attack' && command.targetId === fighter.id);
    for (const command of onFighter) {
      if (command.kind === 'attack') {
        for (const tank of tanks) {
          expect(command.unitIds).not.toContain(tank.id);
        }
      }
    }
    // The missile tank, which can hit air, is still sent at it.
    expect(onFighter.some((command) => command.kind === 'attack' && command.unitIds.includes(missile.id))).toBe(true);
  });
});
