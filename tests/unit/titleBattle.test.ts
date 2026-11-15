import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { createSkirmishWorld } from '../../src/data/simData';
import { TitleBattle } from '../../src/titleBattle';

describe('title screen battle', () => {
  it('[TITLE-01] raiders reach the pad and fight; new waves keep coming and the scene never ends', () => {
    const world = createSkirmishWorld(
      data,
      7,
      [
        { player: 1, faction: 'human', controller: 'human' },
        { player: 2, faction: 'alien', controller: 'ai', difficulty: 'normal' },
      ],
      { fog: false, resources: 'normal', force: 'padForce' },
    );
    const battle = new TitleBattle(world);
    const startHp = battle
      .current()
      .units.filter((unit) => unit.owner === 1 && !unit.job)
      .reduce((sum, unit) => sum + unit.hp, 0);
    let damaged = false;
    for (let second = 0; second < 240; second += 1) {
      for (let i = 0; i < 20; i += 1) {
        battle.advance(1 / 20);
      }
      const now = battle.current();
      const hp = now.units.filter((unit) => unit.owner === 1 && !unit.job).reduce((sum, unit) => sum + unit.hp, 0);
      if (hp < startHp || now.units.some((unit) => unit.owner === 2 && unit.hp <= 0)) {
        damaged = true;
      }
      expect(now.result).toBeNull();
    }
    expect(damaged).toBe(true);
    expect(battle.raids()).toBeGreaterThan(1);
  });
});
