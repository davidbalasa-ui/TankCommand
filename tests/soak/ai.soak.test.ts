import { it } from 'vitest';
import { aiMatch, runMatch } from '../unit/aiHelpers';

// Not part of CI: `MATCHES=20 SEED=100 npm run ai:soak`. Prints winner, duration and stuck units.
const MATCHES = Number(process.env.MATCHES ?? '10');
const SEED = Number(process.env.SEED ?? '1');
const LEVELS = ['easy', 'normal', 'hard'] as const;

it('AI soak', () => {
  for (let i = 0; i < MATCHES; i += 1) {
    const a = LEVELS[i % 3] ?? 'normal';
    const b = LEVELS[(i + 1) % 3] ?? 'normal';
    const { world, tick } = runMatch(aiMatch(SEED + i, a, b), 45);
    const stuck = world.units.filter((unit) => unit.stuckTicks > 600).length;
    console.log(
      `seed ${SEED + i} ${a}-vs-${b}: winner ${String(world.result?.winner ?? 'none')} after ${(tick / 1200).toFixed(1)} min, stuck units ${stuck}`,
    );
  }
});
