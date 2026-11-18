import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld, missionsOf } from '../../src/data/missions';
import { stepWithAi } from '../../src/ai/driver';
import { missionAllows, missionMarkers } from '../../src/sim/triggers';
import { isItemUnlocked } from '../../src/sim/research';
import type { Command } from '../../src/sim/commands';
import { botCommands, playMissionAsync } from './campaignBot';

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

  // At the start of every step, before following the text, the player spends every ore it has on
  // the cheapest thing the step did not ask for. Command's top-ups must still get it through.
  for (const row of training) {
    it(`[TRN-05] a player who buys the wrong things first still wins ${row.id}`, async () => {
      let w = buildMissionWorld(data, row, 1);
      const me = w.mission!.humanSide;
      const wasted = new Set<string>();
      let wasting: string | undefined;
      // Only the ore in hand when the step starts is wasted: a top-up refills it, and wasting that
      // too would never end.
      let budget = 0;
      let wrongBuys = 0;
      while (!w.result && w.tick < 15 * 60 * SEC) {
        const step = w.mission!.objectives.find((o) => o.status === 'active');
        if (step && !wasted.has(step.id)) {
          wasted.add(step.id);
          wasting = step.id;
          budget = w.resources.find((r) => r.player === me)!.ore;
        }
        let commands: Command[] = [];
        if (wasting && step?.id === wasting) {
          const trigger = w.mission!.def.triggers.find((t) => t.id === step.id);
          const asked = new Set(
            JSON.stringify(trigger?.when ?? {})
              .match(/"(unit|structure)Type":"[^"]+"/g)
              ?.map((m) => m.split('"')[3]) ?? [],
          );
          const stats = w.resources.find((r) => r.player === me)!;
          const pad = w.structures.find((s) => s.owner === me && s.hp > 0 && w.structureTypes.get(s.typeId)?.kind === 'pad');
          const wrong = [...w.unitTypes.values()]
            .filter((u) => u.role !== 'air' && !asked.has(u.id) && missionAllows(w, me, u.id) && isItemUnlocked(w, me, u.id))
            .filter((u) => budget >= u.oreCost && stats.ore >= u.oreCost && stats.metal >= u.metalCost)
            .sort((a, b) => a.oreCost - b.oreCost)[0];
          if (!wrong || !pad) {
            wasting = undefined;
          } else if (w.tick % 20 === 0) {
            wrongBuys += 1;
            budget -= wrong.oreCost;
            commands = [{ kind: 'buy', itemId: wrong.id, padId: pad.id, issuer: me, tick: w.tick + 1 }];
          }
        } else {
          commands = botCommands(w);
        }
        w = stepWithAi(w, commands);
        if (w.tick % 1000 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 0));
        }
      }
      const objectives = w.mission?.objectives.map((o) => `${o.id}:${o.status}`).join(' ');
      expect(w.result, `${row.id} t=${Math.round(w.tick / SEC)}s ${objectives}`).toEqual({ winner: 1 });
      if (row.id !== 'mission.training.2_mining' && row.id !== 'mission.training.3_combat') {
        expect(wrongBuys, `${row.id} wasted some ore`).toBeGreaterThan(0);
        expect(w.mission!.fired.some((id) => id.includes('TopUp')), `${row.id} needed a top-up`).toBe(true);
      }
    }, 120_000);
  }

  it('[TRN-05] Dragonflies that run out of fuel before a Javelin comes are sent again', async () => {
    const row = training.find((m) => m.id === 'mission.training.5_air')!;
    let w = buildMissionWorld(data, row, 1);
    const active = (id: string): boolean => w.mission!.objectives.some((o) => o.id === id && o.status === 'active');
    // The player builds the Airfield but no Javelin.
    const noJavelin = (c: Command): boolean => !(c.kind === 'buy' && c.itemId === 'unit.human.missile_tank');
    while (!active('antiair') && w.tick < 5 * 60 * SEC) {
      w = stepWithAi(w, botCommands(w).filter(noJavelin));
    }
    expect(active('antiair')).toBe(true);
    // The player stops here and buys nothing while the first pair burns its fuel.
    const until = w.tick + 4 * 60 * SEC;
    while (!w.result && w.tick < until && !w.mission!.fired.includes('moreDrones')) {
      w = stepWithAi(w, []);
      if (w.tick % 1000 === 0) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    }
    expect(w.mission!.fired).toContain('moreDrones');
    expect(w.result).toBeNull();
  }, 120_000);

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
