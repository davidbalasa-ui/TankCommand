import { it } from 'vitest';
import type { AiDifficulty } from '../../src/sim/types';
import { data } from '../unit/aiHelpers';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { CAMPAIGN_PLANS, playMissionAsync } from '../unit/campaignBot';

// Not part of CI: `SEEDS=5 npm run ai:soak -- missionSeeds`. Every mission attempt gets a new world
// seed, so this plays each campaign mission that has a computer opponent (ALL=1: every campaign
// mission; CAMPAIGN_ONLY=a,b: just those) once per seed with the scripted beginner bot and prints
// its win rate. PLAIN=1 plays the same seeds with the AI's seeded play style switched off.
// DIFFICULTIES=easy,normal,hard plays each campaign difficulty in turn (default: normal).
const SEEDS = Number(process.env.SEEDS ?? '5');
const FIRST = Number(process.env.SEED ?? '1');
const ONLY = process.env.CAMPAIGN_ONLY;
const PLAIN = process.env.PLAIN === '1';
const SEC = 20;
const DIFFICULTIES = (process.env.DIFFICULTIES ?? 'normal')
  .split(',')
  .filter((d): d is AiDifficulty => d === 'easy' || d === 'normal' || d === 'hard');

const rows = MISSIONS.filter(
  (m) =>
    m.campaign !== 'training' &&
    (process.env.ALL === '1' || m.sides.some((side) => side.controller === 'ai')) &&
    (!ONLY || ONLY.split(',').some((part) => m.id.includes(part))),
);

it('mission win rate across world seeds', async () => {
  const lines: string[] = [];
  for (const difficulty of DIFFICULTIES) for (const row of rows) {
    const outcomes: string[] = [];
    let wins = 0;
    for (let seed = FIRST; seed < FIRST + SEEDS; seed += 1) {
      const start = buildMissionWorld(data, row, seed, { difficulty });
      if (PLAIN) {
        // For comparison: the same seeds with the AI's play style turned off (only the dice vary).
        start.aiStates = start.aiStates.map(({ traitSeed: _trait, attackScale: _scale, ...plain }) => plain);
      }
      const w = await playMissionAsync(
        start,
        ((row.timeLimitSec ?? 900) + 5) * SEC,
        CAMPAIGN_PLANS[row.id] ?? {},
      );
      const won = w.result?.winner === w.mission?.humanSide;
      wins += won ? 1 : 0;
      outcomes.push(`${seed}:${won ? 'W' : `L(${w.mission?.failReason ?? 'timeout'})`}@${Math.round(w.tick / SEC)}s`);
    }
    const line = `${difficulty} ${row.id} ${wins}/${SEEDS} ${outcomes.join(' ')}`;
    console.log(line);
    lines.push(line);
  }
  console.log(`\n${lines.join('\n')}`);
});
