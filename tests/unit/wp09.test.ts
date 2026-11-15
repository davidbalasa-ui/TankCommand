import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld, loadMissionTable, nextMission } from '../../src/data/missions';
import { parseMission, type Action, type Condition, type Trigger } from '../../src/sim/missionSchema';
import { evalCondition, runAction, updateMission, tagUnit, type MissionState } from '../../src/sim/triggers';
import { stepWithAi } from '../../src/ai/driver';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { relation } from '../../src/sim/diplomacy';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import type { Command } from '../../src/sim/commands';
import type { StartUnit, WorldState } from '../../src/sim/types';
import { padType, tankType } from './simHelpers';
import { playMission } from './campaignBot';

const SEC = 20;

function mission(triggers: Trigger[], extra: Partial<MissionState['def']> = {}): MissionState {
  return {
    def: { id: 'mission.test.x', triggers, timeLimitTicks: null, ...extra },
    humanSide: 1,
    fired: [],
    objectives: [
      { id: 'a', text: 'A', kind: 'primary', status: 'active' },
      { id: 'o', text: 'O', kind: 'optional', status: 'active' },
    ],
    messages: [],
    nextMessage: 1,
    tags: {},
    reveals: [],
    failReason: null,
  };
}

function miniWorld(triggers: Trigger[], units: StartUnit[] = [], extra: Partial<MissionState['def']> = {}): WorldState {
  return createWorld(5, {
    unitTypes: new Map([['unit.test.tank', tankType()]]),
    structureTypes: new Map([['structure.test.pad', padType()]]),
    startUnits: units,
    startStructures: [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
    ],
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
    startResources: [
      { player: 1, ore: 100, metal: 0 },
      { player: 2, ore: 0, metal: 0 },
    ],
    sides: [
      { player: 1, controller: 'human', team: 1, groupId: null, provokable: true, forgiveAfterSec: null },
      { player: 2, controller: 'ai', team: 2, groupId: null, provokable: true, forgiveAfterSec: null },
      { player: 3, controller: 'none', team: 3, groupId: 'citizens', provokable: true, forgiveAfterSec: null },
    ],
    mission: mission(triggers, extra),
  });
}

const deps = { attackMove: () => undefined };

function tick(world: WorldState, n = 1): WorldState {
  let w = world;
  for (let i = 0; i < n; i += 1) {
    w = step(w, []);
  }
  return w;
}

describe('mission data', () => {
  it('[MSN-01] every shipped mission validates and all references exist', () => {
    expect(MISSIONS.length).toBeGreaterThanOrEqual(4);
    for (const row of MISSIONS) {
      const world = buildMissionWorld(data, row, 1);
      expect(world.mission?.def.id).toBe(row.id);
    }
  });

  it('[MSN-01] an invalid mission is rejected with the field named', () => {
    const base = JSON.parse(JSON.stringify(MISSIONS[0]));
    base.triggers[0].when = { t: 'time', tick: 'soon' };
    expect(() => parseMission(base)).toThrow(/triggers\.0\.when/);
    const noTitle = JSON.parse(JSON.stringify(MISSIONS[0]));
    delete noTitle.title;
    expect(() => parseMission(noTitle)).toThrow(/title/);
    const dup = JSON.parse(JSON.stringify(MISSIONS[0]));
    expect(() => loadMissionTable([dup, dup])).toThrow(/Duplicate/);
  });
});

describe('triggers', () => {
  const tank = (owner: number, x: number, z: number): StartUnit => ({ owner, typeId: 'unit.test.tank', x, z });

  it('[MSN-02] every condition type evaluates', () => {
    const w = miniWorld([], [tank(1, 0, 0), tank(1, 30, 30), tank(2, 40, 40)]);
    const m = w.mission as MissionState;
    const ids = w.units.map((u) => u.id);
    tagUnit(m, 'vip', ids[0] ?? 0);
    tagUnit(m, 'dead', 9999);
    const cases: Array<[Condition, boolean]> = [
      [{ t: 'time', tick: 0 }, true],
      [{ t: 'time', tick: 5 }, false],
      [{ t: 'areaEntered', side: 1, x: 0, z: 0, radius: 3 }, true],
      [{ t: 'areaEntered', side: 2, x: 0, z: 0, radius: 3 }, false],
      [{ t: 'areaEntered', side: 1, x: 0, z: 0, radius: 3, unitType: 'unit.test.tank', tag: 'vip' }, true],
      [{ t: 'unitDestroyed', tag: 'dead' }, true],
      [{ t: 'unitDestroyed', tag: 'vip' }, false],
      [{ t: 'allDestroyed', side: 3 }, true],
      [{ t: 'allDestroyed', side: 2 }, false],
      [{ t: 'resourceReached', side: 1, ore: 100 }, true],
      [{ t: 'resourceReached', side: 1, ore: 101 }, false],
      [{ t: 'objectiveDone', id: 'a' }, false],
      [{ t: 'structureBuilt', side: 1, structureType: 'structure.test.pad' }, true],
      [{ t: 'structureBuilt', side: 1, structureType: 'structure.test.pad', count: 2 }, false],
      [{ t: 'relationIs', a: 1, b: 2, relation: 'hostile' }, true],
      [{ t: 'relationIs', a: 1, b: 3, relation: 'neutral' }, true],
      [{ t: 'unitsAlive', side: 1, op: '>=', count: 2 }, true],
      [{ t: 'unitsAlive', side: 1, op: '<=', count: 1 }, false],
      [{ t: 'unitEscorted', tag: 'vip', x: 0, z: 0, radius: 3 }, true],
      [{ t: 'unitEscorted', tag: 'vip', x: 20, z: 20, radius: 3 }, false],
      [{ t: 'and', conds: [{ t: 'time', tick: 0 }, { t: 'time', tick: 9 }] }, false],
      [{ t: 'or', conds: [{ t: 'time', tick: 0 }, { t: 'time', tick: 9 }] }, true],
      [{ t: 'not', cond: { t: 'time', tick: 9 } }, true],
    ];
    for (const [cond, expected] of cases) {
      expect(evalCondition(w, m, cond), JSON.stringify(cond)).toBe(expected);
    }
  });

  it('[MSN-02] every action type runs', () => {
    const w = miniWorld([], [tank(2, 40, 40)]);
    const m = w.mission as MissionState;
    const calls: number[] = [];
    const d = { attackMove: (_w: WorldState, _s: number, ids: number[]) => void calls.push(...ids) };
    const run = (a: Action) => runAction(w, m, a, d);
    run({ t: 'spawn', side: 1, unitType: 'unit.test.tank', count: 2, x: 0, z: 0, tag: 'new', drop: true });
    expect(m.tags.new).toHaveLength(2);
    expect(w.dropBeams.length).toBe(2);
    run({ t: 'message', text: 'hi', speaker: 'HQ' });
    expect(m.messages[0]?.speaker).toBe('HQ');
    run({ t: 'revealArea', x: 0, z: 0, radius: 10, forSec: 5 });
    expect(m.reveals).toHaveLength(1);
    run({ t: 'setObjective', id: 'new', status: 'add', text: 'New', kind: 'optional' });
    expect(m.objectives.some((o) => o.id === 'new')).toBe(true);
    run({ t: 'setObjective', id: 'new', status: 'done' });
    expect(m.objectives.find((o) => o.id === 'new')?.status).toBe('done');
    run({ t: 'grant', side: 1, ore: 50, metal: 5 });
    expect(w.resources.find((r) => r.player === 1)?.ore).toBe(150);
    run({ t: 'aiOrder', tag: 'new', mode: 'attack', x: 5, z: 5 });
    expect(calls).toHaveLength(2);
    run({ t: 'setRelation', a: 1, b: 3, relation: 'allied' });
    expect(relation(w, 1, 3)).toBe('allied');
    run({ t: 'lose', reason: 'x' });
    expect(w.result).toEqual({ winner: null });
    w.result = null;
    run({ t: 'win' });
    expect(w.result).toEqual({ winner: 1 });
  });

  it('[MSN-02] triggers fire once unless repeat, in order, and objectives decide the result', () => {
    const w = miniWorld([
      { id: 'once', when: { t: 'time', tick: 0 }, do: [{ t: 'grant', side: 1, ore: 10 }] },
      { id: 'again', when: { t: 'time', tick: 0 }, repeat: true, do: [{ t: 'grant', side: 1, metal: 1 }] },
      { id: 'done', when: { t: 'time', tick: 3 }, do: [{ t: 'setObjective', id: 'a', status: 'done' }] },
    ]);
    const later = tick(w, 5);
    const stats = later.resources.find((r) => r.player === 1);
    expect(stats?.ore).toBe(110);
    expect((stats?.metal ?? 0)).toBeGreaterThanOrEqual(3);
    expect(later.result).toEqual({ winner: 1 });
    expect(later.mission?.fired).toContain('once');
  });

  it('[MSN-02] a failed primary objective or an expired time limit loses', () => {
    const failed = tick(
      miniWorld([{ id: 'f', when: { t: 'time', tick: 1 }, do: [{ t: 'setObjective', id: 'a', status: 'failed' }] }]),
      3,
    );
    expect(failed.result).toEqual({ winner: null });
    const late = tick(miniWorld([], [], { timeLimitTicks: 3 }), 5);
    expect(late.result).toEqual({ winner: null });
    expect(late.mission?.failReason).toBe('timeout');
  });

  it('[MSN-02] revealArea shows the area through fog and expires', () => {
    const w = miniWorld([{ id: 'r', when: { t: 'time', tick: 0 }, do: [{ t: 'revealArea', x: 40, z: -40, radius: 10, forSec: 1 }] }]);
    w.fogEnabled = true;
    const a = tick(w, 8);
    const cell = (world: WorldState) => {
      const half = world.map.size / 2;
      const cx = Math.floor((40 + half) / world.map.cellSize);
      const cz = Math.floor((-40 + half) / world.map.cellSize);
      return world.vision.find((v) => v.player === 1)?.cells.charCodeAt(cz * world.map.cols + cx);
    };
    expect(cell(a)).toBe(50);
    const b = tick(a, 40);
    expect(cell(b)).toBe(49);
  });
});

describe('[MSN-07] neutral armed side', () => {
  const triggers: Trigger[] = [
    { id: 'lost', when: { t: 'unitsAlive', tag: 'citizens', op: '<=', count: 1 }, do: [{ t: 'lose', reason: 'citizens' }] },
    { id: 'ally', when: { t: 'time', tick: 4000 }, do: [{ t: 'setRelation', a: 1, b: 3, relation: 'allied' }] },
  ];
  function setup(): WorldState {
    const w = miniWorld(triggers, [
      { owner: 1, typeId: 'unit.test.tank', x: 0, z: 0 },
      { owner: 1, typeId: 'unit.test.tank', x: 0, z: 3 },
      { owner: 1, typeId: 'unit.test.tank', x: 0, z: -3 },
      { owner: 3, typeId: 'unit.test.tank', x: 8, z: 0 },
      { owner: 3, typeId: 'unit.test.tank', x: 8, z: 4 },
    ]);
    for (const u of w.units.filter((x) => x.owner === 3)) {
      tagUnit(w.mission as MissionState, 'citizens', u.id);
    }
    return w;
  }

  it('[MSN-07] attacking a neutral turns it hostile and it fights back; unitsAlive fails the mission', () => {
    let w = setup();
    expect(relation(w, 1, 3)).toBe('neutral');
    const mine = w.units.find((u) => u.owner === 1);
    const target = w.units.find((u) => u.owner === 3);
    const command: Command = { kind: 'attack', issuer: 1, tick: w.tick + 1, unitIds: w.units.filter((u) => u.owner === 1).map((u) => u.id), targetId: target?.id ?? 0 };
    w = step(w, [command]);
    for (let i = 0; i < 80 * SEC && !w.result; i += 1) {
      w = step(w, []);
    }
    expect(relation(w, 3, 1)).toBe('hostile');
    expect(w.result).toEqual({ winner: null });
    expect(w.mission?.failReason).toBe('citizens');
  });

  it('[MSN-07] setRelation and relationIs work from trigger data', () => {
    const w = tick(setup(), 4010);
    expect(relation(w, 1, 3)).toBe('allied');
    expect(evalCondition(w, w.mission as MissionState, { t: 'relationIs', a: 1, b: 3, relation: 'allied' })).toBe(true);
  });
});

describe('placeholder missions', () => {
  it('[MSN-04] every shipped mission has a time limit or a lose action', () => {
    for (const row of MISSIONS) {
      const hasLose = row.triggers.some((t) => t.do.some((a) => a.t === 'lose'));
      expect(row.timeLimitSec !== undefined || hasLose, row.id).toBe(true);
      expect(row.objectives.some((o) => o.kind === 'primary'), row.id).toBe(true);
    }
  });

  for (const row of MISSIONS) {
    it(`[MSN-03] ${row.id} can be lost by doing nothing`, async () => {
      let w = buildMissionWorld(data, row, 3);
      const limit = ((row.timeLimitSec ?? 900) + 5) * SEC;
      while (!w.result && w.tick < limit) {
        w = stepWithAi(w);
        if (w.tick % 1000 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 0));
        }
      }
      expect(w.result, row.id).toEqual({ winner: null });
    }, 600_000);
  }

  it('[MSN-03] training missions are won by scripted commands', () => {
    const t1 = MISSIONS.find((m) => m.id === 'mission.training.1_drops');
    const t2 = MISSIONS.find((m) => m.id === 'mission.training.2_mining');
    if (!t1 || !t2) {
      throw new Error('missing');
    }
    let w = buildMissionWorld(data, t1, 4);
    const pad = w.structures.find((s) => s.owner === 1);
    w = step(w, [{ kind: 'buy', issuer: 1, tick: w.tick + 1, itemId: 'unit.human.light_tank', padId: pad?.id ?? 0 }]);
    const tank = w.units.find((u) => u.owner === 1);
    w = step(w, [{ kind: 'move', issuer: 1, tick: w.tick + 1, unitIds: [tank?.id ?? 0], x: -25, z: -25 }]);
    for (let i = 0; i < 120 * SEC && !w.result; i += 1) {
      w = step(w, []);
    }
    expect(w.result).toEqual({ winner: 1 });

    let m = buildMissionWorld(data, t2, 4);
    const miner = m.units.find((u) => u.owner === 1);
    const deposit = m.deposits.filter((d) => d.kind === 'ore').sort(
      (a, b) => Math.hypot(a.x + 50, a.z + 50) - Math.hypot(b.x + 50, b.z + 50),
    )[0];
    m = step(m, [{ kind: 'mine', issuer: 1, tick: m.tick + 1, unitIds: [miner?.id ?? 0], depositId: deposit?.id ?? 0 }]);
    for (let i = 0; i < 600 * SEC && !m.result; i += 1) {
      m = step(m, []);
    }
    expect(m.result).toEqual({ winner: 1 });
  }, 120_000);

  it('[MSN-03] the combat missions can be won by a scripted attack', () => {
    // The scripted player lives in campaignBot.ts; CMP-01 runs it on every campaign mission.
    for (const id of ['mission.human.04_first_strike', 'mission.alien.07_root_and_ruin']) {
      const row = MISSIONS.find((m) => m.id === id);
      if (!row) {
        throw new Error(id);
      }
      const w = playMission(buildMissionWorld(data, row, 2), (row.timeLimitSec ?? 1500) * SEC);
      expect(w.result, `${id} ${w.mission?.failReason} t=${w.tick}`).toEqual({ winner: 1 });
    }
  }, 300_000);

  it('[MSN-05] each campaign has an ordered chain and nextMission walks it', () => {
    const first = MISSIONS.find((m) => m.id === 'mission.training.1_drops');
    expect(first && nextMission(first)?.id).toBe('mission.training.2_mining');
    const last = MISSIONS.find((m) => m.id === 'mission.training.2_mining');
    expect(last && nextMission(last)).toBeNull();
  });
});

describe('[DET-07] mission state is saved and deterministic', () => {
  it('[DET-07] save/load mid-mission keeps the hash and the future', () => {
    const row = MISSIONS.find((m) => m.id === 'mission.human.04_first_strike');
    if (!row) {
      throw new Error('missing');
    }
    let w = buildMissionWorld(data, row, 7);
    for (let i = 0; i < 4000; i += 1) {
      w = stepWithAi(w);
    }
    expect(w.mission?.fired).toContain('wave');
    const decoded = decodeSave(encodeSave(w, { gameVersion: 't', savedAtIso: '2026-01-01T00:00:00Z' }));
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) {
      return;
    }
    expect(hashWorld(decoded.world)).toBe(hashWorld(w));
    let a = w;
    let b = decoded.world;
    for (let i = 0; i < 300; i += 1) {
      a = stepWithAi(a);
      b = stepWithAi(b);
    }
    expect(hashWorld(b)).toBe(hashWorld(a));
  }, 60_000);
});
