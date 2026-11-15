import { describe, expect, it } from 'vitest';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { defaultStartUnits } from '../../src/sim/world';
import { hashWorld, step } from '../../src/sim/world';
import type { Command } from '../../src/sim/commands';
import { makeSkirmishWorld } from './simHelpers';

function scriptedCommands(world: ReturnType<typeof makeSkirmishWorld>): Command[] {
  const own = world.units.filter((unit) => unit.owner === 1).map((unit) => unit.id);
  const enemy = world.units.find((unit) => unit.owner === 2);
  const commands: Command[] = [
    { kind: 'move', unitIds: own, x: 50, z: 50, tick: 1, issuer: 1 },
  ];
  if (enemy) {
    commands.push({ kind: 'attack', unitIds: own, targetId: enemy.id, tick: 300, issuer: 1 });
  }
  return commands;
}

describe('determinism', () => {
  it('[DET-01] scripted battles are bit-identical and save/load at tick 600 matches', () => {
    let a = makeSkirmishWorld(1);
    let b = makeSkirmishWorld(1);
    const commands = scriptedCommands(a);
    for (let i = 0; i < 2000; i += 1) {
      a = step(a, commands);
      b = step(b, commands);
    }
    expect(hashWorld(a)).toBe(hashWorld(b));

    let uninterrupted = makeSkirmishWorld(1);
    const sameCommands = scriptedCommands(uninterrupted);
    for (let i = 0; i < 2000; i += 1) {
      uninterrupted = step(uninterrupted, sameCommands);
    }

    let first = makeSkirmishWorld(1);
    const firstCommands = scriptedCommands(first);
    for (let i = 0; i < 600; i += 1) {
      first = step(first, firstCommands);
    }
    const text = encodeSave(first, {
      gameVersion: 'test',
      savedAtIso: '2026-11-03T00:00:00.000Z',
    });
    const decoded = decodeSave(text);
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) {
      return;
    }
    let resumed = decoded.world;
    for (let i = 600; i < 2000; i += 1) {
      resumed = step(resumed, firstCommands);
    }
    expect(hashWorld(resumed)).toBe(hashWorld(uninterrupted));
    expect(defaultStartUnits().length).toBe(8);
  });
});
