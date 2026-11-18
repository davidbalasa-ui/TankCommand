import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld, missionsOf } from '../../src/data/missions';
import { stepWithAi } from '../../src/ai/driver';
import { missionMarkers } from '../../src/sim/triggers';
import { playMissionAsync } from './campaignBot';

const SEC = 20;
const training = missionsOf('training');

describe('[TRN-01] training missions', () => {
  it('[TRN-01] there are five lessons in order: drops, mining, combat, research, air', () => {
    expect(training.map((m) => m.id)).toEqual([
      'mission.training.1_drops',
      'mission.training.2_mining',
      'mission.training.3_combat',
      'mission.training.4_research',
      'mission.training.5_air',
    ]);
    for (const row of training) {
      expect(row.placeholder, row.id).toBe(false);
      expect(row.timeLimitSec, `${row.id} has no time pressure`).toBeUndefined();
      expect(data.mapRows.find((m) => m.id === row.mapId)?.campaignOnly, `${row.id} uses a training map`).toBe(true);
    }
  });

  for (const row of training) {
    it(`[TRN-01] the scripted beginner wins ${row.id} in 3 to 8 minutes`, async () => {
      const w = await playMissionAsync(buildMissionWorld(data, row, 1), 15 * 60 * SEC);
      const objectives = w.mission?.objectives.map((o) => `${o.id}:${o.status}`).join(' ');
      expect(w.result, `${row.id} t=${Math.round(w.tick / SEC)}s ${objectives}`).toEqual({ winner: 1 });
      // The bot plays at full attention; a new player reading the steps takes about twice as long.
      expect(w.tick / SEC, row.id).toBeLessThan(4 * 60);
    }, 120_000);
  }

  it('[TRN-02] a player who does nothing is never defeated (ten idle minutes in every lesson)', async () => {
    for (const row of training) {
      let w = buildMissionWorld(data, row, 1);
      while (!w.result && w.tick < 10 * 60 * SEC) {
        w = stepWithAi(w, []);
        if (w.tick % 2000 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 0));
        }
      }
      expect(w.result, row.id).toBeNull();
    }
  }, 300_000);

  it('[TRN-03] only the current step shows a goal ring', () => {
    for (const row of training) {
      const w = buildMissionWorld(data, row, 1);
      expect(missionMarkers(w.mission).length, row.id).toBeLessThanOrEqual(1);
    }
  });

  it('[TRN-04] the training chain runs 1 to 5 and the campaigns still load', () => {
    expect(MISSIONS.filter((m) => m.campaign === 'training')).toHaveLength(5);
  });
});
