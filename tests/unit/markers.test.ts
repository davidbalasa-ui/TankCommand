import { describe, expect, it } from 'vitest';
import { missionMarkers, type MissionState } from '../../src/sim/triggers';
import type { Trigger } from '../../src/sim/missionSchema';

function mission(triggers: Trigger[], fired: string[] = [], done: string[] = []): MissionState {
  return {
    def: { id: 'mission.test', triggers, timeLimitTicks: null },
    humanSide: 1,
    fired,
    objectives: done.map((id) => ({ id, text: id, kind: 'primary' as const, status: 'done' as const })),
    messages: [],
    nextMessage: 0,
    tags: {},
    reveals: [],
    failReason: null,
  };
}

const win = [{ t: 'win' as const }];

describe('mission markers', () => {
  it('[MSN-08] goal areas for the player are marked until their trigger fires; enemy and "not" areas are not', () => {
    const triggers: Trigger[] = [
      { id: 'reach', when: { t: 'areaEntered', side: 1, x: -25, z: -25, radius: 7 }, do: win },
      { id: 'enemy', when: { t: 'areaEntered', side: 2, x: 10, z: 10, radius: 5 }, do: win },
      { id: 'trap', when: { t: 'areaEntered', side: 1, x: 40, z: 40, radius: 6 }, do: [{ t: 'lose', reason: 'mines' }] },
      { id: 'avoid', when: { t: 'not', cond: { t: 'areaEntered', side: 1, x: 30, z: 0, radius: 4 } }, do: win },
      {
        id: 'escort',
        when: { t: 'and', conds: [{ t: 'time', tick: 10 }, { t: 'unitEscorted', tag: 'vip', x: 5, z: 6, radius: 3 }] },
        do: win,
      },
    ];
    expect(missionMarkers(mission(triggers))).toEqual([
      { x: -25, z: -25, radius: 7 },
      { x: 5, z: 6, radius: 3 },
    ]);
    expect(missionMarkers(mission(triggers, ['reach']))).toEqual([{ x: 5, z: 6, radius: 3 }]);
    expect(missionMarkers(null)).toEqual([]);
  });

  it('[MSN-08] a later step\'s ring stays hidden until the step before it is done', () => {
    const triggers: Trigger[] = [
      { id: 'first', when: { t: 'areaEntered', side: 1, x: 1, z: 1, radius: 4 }, do: win },
      {
        id: 'second',
        when: { t: 'and', conds: [{ t: 'objectiveDone', id: 'first' }, { t: 'areaEntered', side: 1, x: 9, z: 9, radius: 5 }] },
        do: win,
      },
    ];
    expect(missionMarkers(mission(triggers))).toEqual([{ x: 1, z: 1, radius: 4 }]);
    expect(missionMarkers(mission(triggers, ['first'], ['first']))).toEqual([{ x: 9, z: 9, radius: 5 }]);
  });
});
