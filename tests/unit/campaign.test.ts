import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { playMissionAsync, type BotPlan } from './campaignBot';

const SEC = 20;
const ONLY = process.env.CAMPAIGN_ONLY;
// Per-mission bot tuning. Mission 20 (two enemy bases) goes better with the army waiting right
// at the pad's exit edge rather than out at the rally point.
const PLANS: Record<string, BotPlan> = {
  'mission.human.20_brood_war': { gatherOffEdge: 2 },
  'mission.alien.20_two_banners': { gatherOffEdge: 2 },
};
const campaign = MISSIONS.filter((m) => m.campaign !== 'training' && (!ONLY || m.id.includes(ONLY)));

describe('[CMP-01] campaign missions', () => {
  for (const row of campaign) {
    it(`[CMP-01] a scripted beginner wins ${row.id}`, async () => {
      const w = await playMissionAsync(buildMissionWorld(data, row, 1), ((row.timeLimitSec ?? 900) + 5) * SEC, PLANS[row.id] ?? {});
      const objectives = w.mission?.objectives.map((o) => `${o.id}:${o.status}`).join(' ');
      expect(w.result, `${row.id} ${w.mission?.failReason} t=${Math.round(w.tick / SEC)}s ${objectives}`).toEqual({
        winner: w.mission?.humanSide,
      });
    }, 900_000);
  }
});
