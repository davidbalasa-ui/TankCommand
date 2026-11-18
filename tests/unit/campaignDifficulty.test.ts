import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { canonicalJson, worldToPayload } from '../../src/sim/world';
import {
  emptyProgress,
  parseProgress,
  recordWin,
  setCampaignDifficulty,
} from '../../src/platform/progress';
import { playMissionAsync, type BotPlan } from './campaignBot';

const SEC = 20;

function mission(id: string) {
  const row = MISSIONS.find((item) => item.id === id);
  if (!row) {
    throw new Error(`no mission ${id}`);
  }
  return row;
}

function sideOre(world: ReturnType<typeof buildMissionWorld>, player: number) {
  const side = world.resources.find((item) => item.player === player);
  return { ore: side?.ore ?? -1, metal: side?.metal ?? -1 };
}

describe('[MSN-05] campaign difficulty', () => {
  it('[MSN-05] difficulty is saved with the progress and old progress reads as Normal', () => {
    expect(parseProgress(JSON.stringify({ version: 1, completed: {} })).difficulty).toBe('normal');
    expect(parseProgress(JSON.stringify({ version: 1, completed: {}, difficulty: 'silly' })).difficulty).toBe('normal');
    const hard = setCampaignDifficulty(emptyProgress(), 'hard');
    expect(parseProgress(JSON.stringify(hard)).difficulty).toBe('hard');

    let progress = recordWin(hard, 'm1', 300, 'hard');
    progress = recordWin(progress, 'm1', 200, 'easy');
    const record = parseProgress(JSON.stringify(progress)).completed['m1'];
    expect(record).toEqual({ bestTimeSec: 200, wins: 2, bestDifficulty: 'hard' });
    expect(progress.difficulty).toBe('hard');
  });

  it('[MSN-05] Normal is exactly the mission as written', () => {
    for (const row of MISSIONS) {
      const plain = canonicalJson(worldToPayload(buildMissionWorld(data, row, 1)));
      const normal = canonicalJson(worldToPayload(buildMissionWorld(data, row, 1, { difficulty: 'normal' })));
      expect(normal, row.id).toBe(plain);
    }
  });

  it('[MSN-05] Easy and Hard move the AI a level and scale the starting stock (Hard: also the AI)', () => {
    const row = mission('mission.human.14_counterpunch');
    const ai = row.sides.find((side) => side.controller === 'ai');
    const human = row.sides.find((side) => side.controller === 'human');
    expect(ai?.difficulty).toBe('normal');
    const easy = buildMissionWorld(data, row, 1, { difficulty: 'easy' });
    const hard = buildMissionWorld(data, row, 1, { difficulty: 'hard' });
    expect(easy.aiStates.map((state) => state.difficulty)).toEqual(['easy']);
    expect(hard.aiStates.map((state) => state.difficulty)).toEqual(['hard']);
    expect(easy.mission?.def.difficulty).toBe('easy');
    expect(hard.mission?.def.difficulty).toBe('hard');
    expect(sideOre(easy, human?.player ?? 1).ore).toBe(Math.round((human?.ore ?? 0) * 1.25));
    expect(sideOre(hard, human?.player ?? 1).ore).toBe(Math.round((human?.ore ?? 0) * 0.8));
    // Easy leaves the AI's stock as written (a poorer AI turtles, which made Easy harder).
    expect(sideOre(easy, ai?.player ?? 2).metal).toBe(ai?.metal ?? 0);
    expect(sideOre(hard, ai?.player ?? 2).metal).toBe(Math.round((ai?.metal ?? 0) * 1.25));

    // Levels stop at the ends of the scale, and a side's hardDifficulty replaces the step up on
    // Hard (Brood War keeps its northern side at Easy so two bases stay beatable).
    const broodWar = mission('mission.human.20_brood_war');
    expect(buildMissionWorld(data, broodWar, 1, { difficulty: 'hard' }).aiStates.map((s) => s.difficulty)).toEqual(['hard', 'easy']);
    const stepped = { ...broodWar, sides: broodWar.sides.map(({ hardDifficulty: _hard, ...side }) => side) };
    expect(buildMissionWorld(data, stepped, 1, { difficulty: 'hard' }).aiStates.map((s) => s.difficulty)).toEqual(['hard', 'normal']);
    // Easy leaves a Hard side as it is (the Normal level hits harder early than Hard).
    expect(buildMissionWorld(data, broodWar, 1, { difficulty: 'easy' }).aiStates.map((s) => s.difficulty)).toEqual(['hard', 'easy']);
  });
});

// A sample across both campaigns, early and late, scripted enemies and AI ones. (Every mission
// with an AI enemy is played on Easy, Normal and Hard over several world seeds by the
// missionSeeds soak, DIFFICULTIES=easy,normal,hard.)
const EASY_SAMPLE: Array<[string, BotPlan]> = [
  ['mission.human.04_first_strike', {}],
  ['mission.human.14_counterpunch', {}],
  ['mission.human.21_anchor_point', {}],
  ['mission.alien.07_root_and_ruin', {}],
  ['mission.alien.14_breach', {}],
  ['mission.alien.21_citadel_walls', {}],
  ['mission.human.10_river_run', {}],
];

describe('[CMP-01] campaign missions on Easy', () => {
  for (const [id, plan] of EASY_SAMPLE) {
    it(`[CMP-01] a scripted beginner wins ${id} on Easy`, async () => {
      const row = mission(id);
      const w = await playMissionAsync(buildMissionWorld(data, row, 1, { difficulty: 'easy' }), ((row.timeLimitSec ?? 900) + 5) * SEC, plan);
      const objectives = w.mission?.objectives.map((o) => `${o.id}:${o.status}`).join(' ');
      expect(w.result, `${id} ${w.mission?.failReason} t=${Math.round(w.tick / SEC)}s ${objectives}`).toEqual({
        winner: w.mission?.humanSide,
      });
    }, 900_000);
  }
});
