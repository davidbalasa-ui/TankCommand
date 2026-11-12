import { SIM_TICK_HZ } from './constants';
import { relation, setRelation } from './diplomacy';
import { assignHome } from './air';
import { addBeam } from './drops';
import { ensureSideStats } from './economy';
import { sideAlive } from './match';
import { addUnit, findNearestFreeSpot } from './spawn';
import type { Action, Condition, Trigger } from './missionSchema';
import type { PlayerId, WorldState } from './types';

export interface ObjectiveState {
  id: string;
  text: string;
  kind: 'primary' | 'optional';
  status: 'active' | 'done' | 'failed';
}

export interface MissionMessage {
  seq: number;
  tick: number;
  speaker: string | null;
  text: string;
}

export interface RevealState {
  x: number;
  z: number;
  radius: number;
  untilTick: number | null;
}

// `def` never changes during play; everything else is saved and hashed.
export interface MissionState {
  def: {
    id: string;
    triggers: Trigger[];
    timeLimitTicks: number | null;
    /** Per side (player number as a string): the only items it may buy in this mission. */
    available?: Record<string, string[]>;
  };
  humanSide: PlayerId;
  fired: string[];
  objectives: ObjectiveState[];
  messages: MissionMessage[];
  nextMessage: number;
  tags: Record<string, number[]>;
  reveals: RevealState[];
  failReason: string | null;
}

export interface TriggerDeps {
  attackMove: (world: WorldState, side: PlayerId, unitIds: number[], x: number, z: number) => void;
}

const MAX_MESSAGES = 12;

/** False when the mission limits what this side may buy and the item is not on its list. */
export function missionAllows(world: WorldState, player: PlayerId, itemId: string): boolean {
  const list = world.mission?.def.available?.[String(player)];
  return !list || list.includes(itemId);
}

export function cloneMission(mission: MissionState): MissionState {
  return {
    def: mission.def,
    humanSide: mission.humanSide,
    fired: [...mission.fired],
    objectives: mission.objectives.map((o) => ({ ...o })),
    messages: mission.messages.map((m) => ({ ...m })),
    nextMessage: mission.nextMessage,
    tags: Object.fromEntries(Object.entries(mission.tags).map(([k, v]) => [k, [...v]])),
    reveals: mission.reveals.map((r) => ({ ...r })),
    failReason: mission.failReason,
  };
}

export function tagUnit(mission: MissionState, tag: string, id: number): void {
  const list = mission.tags[tag] ?? [];
  list.push(id);
  mission.tags[tag] = list;
}

function aliveIds(world: WorldState, ids: readonly number[]): number[] {
  const alive = new Set(world.units.filter((u) => u.hp > 0).map((u) => u.id));
  return ids.filter((id) => alive.has(id));
}

function inCircle(x: number, z: number, cx: number, cz: number, r: number): boolean {
  return Math.hypot(x - cx, z - cz) <= r;
}

export function evalCondition(world: WorldState, mission: MissionState, cond: Condition): boolean {
  switch (cond.t) {
    case 'time':
      return world.tick >= cond.tick;
    case 'areaEntered': {
      const tagged = cond.tag ? new Set(mission.tags[cond.tag] ?? []) : null;
      return world.units.some(
        (u) =>
          u.hp > 0 &&
          u.owner === cond.side &&
          (!cond.unitType || u.typeId === cond.unitType) &&
          (!tagged || tagged.has(u.id)) &&
          inCircle(u.x, u.z, cond.x, cond.z, cond.radius),
      );
    }
    case 'unitDestroyed': {
      const ids = mission.tags[cond.tag] ?? [];
      return ids.length > 0 && aliveIds(world, ids).length === 0;
    }
    case 'allDestroyed': {
      const units = world.units.some(
        (u) => u.hp > 0 && u.owner === cond.side && (!cond.unitType || u.typeId === cond.unitType),
      );
      const structures = world.structures.some(
        (s) => s.hp > 0 && s.owner === cond.side && (!cond.unitType || s.typeId === cond.unitType),
      );
      return !units && !structures;
    }
    case 'resourceReached': {
      const stats = world.resources.find((r) => r.player === cond.side);
      return !!stats && stats.ore >= (cond.ore ?? 0) && stats.metal >= (cond.metal ?? 0);
    }
    case 'objectiveDone':
      return mission.objectives.some((o) => o.id === cond.id && o.status === 'done');
    case 'structureBuilt': {
      const count = world.structures.filter(
        (s) => s.hp > 0 && s.owner === cond.side && s.typeId === cond.structureType && !s.work,
      ).length;
      return count >= (cond.count ?? 1);
    }
    case 'relationIs':
      return relation(world, cond.a, cond.b) === cond.relation;
    case 'unitsAlive': {
      let count: number;
      if (cond.tag) {
        count = aliveIds(world, mission.tags[cond.tag] ?? []).length;
      } else {
        count = world.units.filter((u) => u.hp > 0 && u.owner === cond.side).length;
      }
      return cond.op === '>=' ? count >= cond.count : count <= cond.count;
    }
    case 'unitEscorted': {
      const alive = world.units.filter(
        (u) => u.hp > 0 && (mission.tags[cond.tag] ?? []).includes(u.id),
      );
      return (
        alive.length > 0 && alive.every((u) => inCircle(u.x, u.z, cond.x, cond.z, cond.radius))
      );
    }
    case 'and':
      return cond.conds.every((c) => evalCondition(world, mission, c));
    case 'or':
      return cond.conds.some((c) => evalCondition(world, mission, c));
    case 'not':
      return !evalCondition(world, mission, cond.cond);
  }
}

function setObjective(mission: MissionState, action: Extract<Action, { t: 'setObjective' }>): void {
  const existing = mission.objectives.find((o) => o.id === action.id);
  if (action.status === 'add') {
    if (!existing) {
      mission.objectives.push({
        id: action.id,
        text: action.text ?? action.id,
        kind: action.kind ?? 'primary',
        status: 'active',
      });
    }
    return;
  }
  if (existing && existing.status === 'active') {
    existing.status = action.status === 'done' ? 'done' : 'failed';
  }
}

export function runAction(
  world: WorldState,
  mission: MissionState,
  action: Action,
  deps: TriggerDeps,
): void {
  switch (action.t) {
    case 'spawn':
      for (let i = 0; i < action.count; i += 1) {
        const spot = findNearestFreeSpot(world, action.x, action.z);
        const unit = addUnit(world, {
          owner: action.side,
          typeId: action.unitType,
          x: spot.x,
          z: spot.z,
          heading: 0,
        });
        if (unit) {
          assignHome(world, unit);
          if (action.tag) {
            tagUnit(mission, action.tag, unit.id);
          }
          if (action.drop) {
            addBeam(world, action.side, spot.x, spot.z);
          }
        }
      }
      return;
    case 'message':
      mission.messages.push({
        seq: mission.nextMessage,
        tick: world.tick,
        speaker: action.speaker ?? null,
        text: action.text,
      });
      mission.nextMessage += 1;
      if (mission.messages.length > MAX_MESSAGES) {
        mission.messages.shift();
      }
      return;
    case 'revealArea':
      mission.reveals.push({
        x: action.x,
        z: action.z,
        radius: action.radius,
        untilTick: action.forSec ? world.tick + Math.round(action.forSec * SIM_TICK_HZ) : null,
      });
      return;
    case 'setObjective':
      setObjective(mission, action);
      return;
    case 'grant': {
      const stats = ensureSideStats(world, action.side);
      stats.ore += action.ore ?? 0;
      stats.metal += action.metal ?? 0;
      return;
    }
    case 'win':
      world.result = { winner: mission.humanSide };
      return;
    case 'lose':
      mission.failReason = action.reason ?? null;
      world.result = { winner: null };
      return;
    case 'aiOrder': {
      const ids = aliveIds(world, mission.tags[action.tag] ?? []);
      const owners = new Set(world.units.filter((u) => ids.includes(u.id)).map((u) => u.owner));
      for (const owner of owners) {
        const own = world.units.filter((u) => ids.includes(u.id) && u.owner === owner).map((u) => u.id);
        deps.attackMove(world, owner, own, action.x, action.z);
      }
      return;
    }
    case 'setRelation':
      setRelation(world, action.a, action.b, action.relation);
      return;
  }
}

export function updateMission(world: WorldState, deps: TriggerDeps): void {
  const mission = world.mission;
  if (!mission || world.result) {
    return;
  }
  mission.reveals = mission.reveals.filter((r) => r.untilTick === null || world.tick < r.untilTick);

  for (const trigger of mission.def.triggers) {
    if (world.result) {
      return;
    }
    if (!trigger.repeat && mission.fired.includes(trigger.id)) {
      continue;
    }
    if (!evalCondition(world, mission, trigger.when)) {
      continue;
    }
    if (!mission.fired.includes(trigger.id)) {
      mission.fired.push(trigger.id);
    }
    for (const action of trigger.do) {
      runAction(world, mission, action, deps);
    }
  }
  if (world.result) {
    return;
  }

  const primaries = mission.objectives.filter((o) => o.kind === 'primary');
  if (primaries.some((o) => o.status === 'failed')) {
    world.result = { winner: null };
    return;
  }
  if (primaries.length > 0 && primaries.every((o) => o.status === 'done')) {
    world.result = { winner: mission.humanSide };
    return;
  }
  if (mission.def.timeLimitTicks !== null && world.tick >= mission.def.timeLimitTicks) {
    mission.failReason = mission.failReason ?? 'timeout';
    world.result = { winner: null };
    return;
  }
  if (!sideAlive(world, mission.humanSide)) {
    mission.failReason = mission.failReason ?? 'defeated';
    world.result = { winner: null };
  }
}

export interface MissionMarker {
  x: number;
  z: number;
  radius: number;
}

/**
 * Areas the player is meant to reach: every areaEntered (for the player's side) or unitEscorted
 * condition in a trigger that hasn't fired yet. Conditions under `not`, and triggers that lose the
 * mission or fail an objective, are skipped because they describe places to avoid. Read-only; the renderer and minimap draw these as goal rings.
 */
export function missionMarkers(mission: MissionState | null): MissionMarker[] {
  if (!mission || mission.failReason !== null) {
    return [];
  }
  const result: MissionMarker[] = [];
  const seen = new Set<string>();
  const visit = (cond: Condition): void => {
    if (cond.t === 'and' || cond.t === 'or') {
      cond.conds.forEach(visit);
      return;
    }
    if ((cond.t === 'areaEntered' && cond.side === mission.humanSide) || cond.t === 'unitEscorted') {
      const key = `${cond.x},${cond.z},${cond.radius}`;
      if (!seen.has(key)) {
        seen.add(key);
        result.push({ x: cond.x, z: cond.z, radius: cond.radius });
      }
    }
  };
  for (const trigger of mission.def.triggers) {
    // A trigger that loses the mission or fails an objective marks a place to avoid, not a goal.
    const bad = trigger.do.some((a) => a.t === 'lose' || (a.t === 'setObjective' && a.status === 'failed'));
    if (!mission.fired.includes(trigger.id) && !bad) {
      visit(trigger.when);
    }
  }
  return result;
}
