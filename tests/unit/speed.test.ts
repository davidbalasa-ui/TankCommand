import { describe, expect, it } from 'vitest';
import { SPEED_OPTIONS, GameSpeed } from '../../src/game/speed';
import { SIM_SPEED_FAST, SIM_SPEED_NORMAL, SIM_SPEED_SLOW } from '../../src/sim/tuning';

describe('game speed', () => {
  it('[GAME-02] slow, normal and fast map to 0.5x, 1x and 2x and cycle in order', () => {
    expect(SPEED_OPTIONS.map((option) => option.multiplier)).toEqual([
      SIM_SPEED_SLOW,
      SIM_SPEED_NORMAL,
      SIM_SPEED_FAST,
    ]);
    const speed = new GameSpeed();
    expect(speed.multiplier).toBe(SIM_SPEED_NORMAL);
    speed.cycle();
    expect(speed.multiplier).toBe(SIM_SPEED_FAST);
    speed.cycle();
    expect(speed.multiplier).toBe(SIM_SPEED_SLOW);
    speed.set('normal');
    expect(speed.multiplier).toBe(SIM_SPEED_NORMAL);
    speed.setMultiplier(SIM_SPEED_SLOW);
    expect(speed.multiplier).toBe(SIM_SPEED_SLOW);
  });
});
