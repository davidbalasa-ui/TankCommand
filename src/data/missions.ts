import { addAi } from '../ai/driver';
import { parseMission, type Condition, type MissionRow } from '../sim/missionSchema';
import { SIM_TICK_HZ } from '../sim/constants';
import { createWorld } from '../sim/world';
import { tagUnit, type MissionState } from '../sim/triggers';
import { convertResearchIds, sideResearch } from '../sim/research';
import type { SimData } from './simData';
import type { AiDifficulty, WorldState } from '../sim/types';
import { TRAINING_MISSIONS } from './missions/training';
import { CAMPAIGN_MISSIONS } from './missions/campaign';

export function loadMissionTable(json: readonly unknown[]): MissionRow[] {
  const rows = json.map((entry) => parseMission(entry));
  const ids = new Set<string>();
  for (const row of rows) {
    if (ids.has(row.id)) {
      throw new Error(`Duplicate mission id ${row.id}`);
    }
    ids.add(row.id);
  }
  return rows.sort((a, b) => a.campaign.localeCompare(b.campaign) || a.order - b.order);
}

export const MISSIONS: MissionRow[] = loadMissionTable([...TRAINING_MISSIONS, ...CAMPAIGN_MISSIONS]);

export function missionsOf(campaign: MissionRow['campaign']): MissionRow[] {
  return MISSIONS.filter((mission) => mission.campaign === campaign);
}

export function nextMission(mission: MissionRow): MissionRow | null {
  return missionsOf(mission.campaign).find((item) => item.order === mission.order + 1) ?? null;
}

/** Throws on a unit or structure type named in a trigger, a spawn or a buy list that the loaded
 *  data does not have: a typo there would otherwise leave a condition that can never come true. */
export function checkMissionReferences(data: SimData, mission: MissionRow): void {
  const unit = (id: string | undefined, where: string): void => {
    if (id !== undefined && !data.unitTypes.has(id)) {
      throw new Error(`Mission ${mission.id}: unknown unit ${id} in ${where}`);
    }
  };
  const structure = (id: string, where: string): void => {
    if (!data.structureTypes.has(id)) {
      throw new Error(`Mission ${mission.id}: unknown structure ${id} in ${where}`);
    }
  };
  const walk = (cond: Condition, where: string): void => {
    switch (cond.t) {
      case 'areaEntered':
      case 'unitsAlive':
        unit(cond.unitType, where);
        break;
      case 'allDestroyed':
        // Counts the side's units and structures, so either kind of type is fine.
        if (cond.unitType !== undefined && !data.structureTypes.has(cond.unitType)) {
          unit(cond.unitType, where);
        }
        break;
      case 'structureBuilt':
        structure(cond.structureType, where);
        break;
      case 'and':
      case 'or':
        cond.conds.forEach((c) => walk(c, where));
        break;
      case 'not':
        walk(cond.cond, where);
        break;
      default:
        break;
    }
  };
  for (const trigger of mission.triggers) {
    walk(trigger.when, `trigger ${trigger.id}`);
    for (const action of trigger.do) {
      if (action.t === 'spawn') {
        unit(action.unitType, `trigger ${trigger.id}`);
      }
    }
  }
  for (const side of mission.sides) {
    for (const id of side.available ?? []) {
      if (!data.unitTypes.has(id) && !data.structureTypes.has(id)) {
        throw new Error(`Mission ${mission.id}: unknown item ${id} in side ${side.player}'s buy list`);
      }
    }
  }
}

/**
 * Every attempt at a mission plays on the same ground (terrain noise and props come from this
 * seed, as the briefing preview does); the world seed only drives combat dice and the AI's choices.
 */
export const MISSION_MAP_SEED = 1;

/**
 * Build a mission's world. `seed` varies per attempt: scripted beats (units, triggers, waves) are
 * fixed by the mission data, while combat and the computer opponents' choices follow the seed.
 */
const LEVELS: readonly AiDifficulty[] = ['easy', 'normal', 'hard'];

/**
 * Campaign difficulty. Normal is each mission exactly as written. Easy and Hard move every AI
 * side's level one step (within easy..hard) and scale the starting ore and metal of the enemy
 * AI sides; most missions' enemies are scripted rather than AI, so the player's own starting
 * ore is scaled the other way too, which is the lever every mission has.
 */
export const DIFFICULTY_TUNING: Record<AiDifficulty, { aiStep: number; aiStock: number; playerOre: number }> = {
  easy: { aiStep: -1, aiStock: 0.75, playerOre: 1.25 },
  normal: { aiStep: 0, aiStock: 1, playerOre: 1 },
  hard: { aiStep: 1, aiStock: 1.25, playerOre: 0.8 },
};

function shiftLevel(level: AiDifficulty, step: number): AiDifficulty {
  const index = Math.min(LEVELS.length - 1, Math.max(0, LEVELS.indexOf(level) + step));
  return LEVELS[index] ?? level;
}

export function buildMissionWorld(
  data: SimData,
  mission: MissionRow,
  seed: number,
  options: { fog?: boolean; difficulty?: AiDifficulty } = {},
): WorldState {
  const difficulty = options.difficulty ?? 'normal';
  const tuning = DIFFICULTY_TUNING[difficulty];
  const startStock = (side: MissionRow['sides'][number]): { ore: number; metal: number } => {
    if (side.controller === 'human') {
      return { ore: Math.round(side.ore * tuning.playerOre), metal: side.metal };
    }
    if (side.controller === 'ai') {
      return { ore: Math.round(side.ore * tuning.aiStock), metal: Math.round(side.metal * tuning.aiStock) };
    }
    return { ore: side.ore, metal: side.metal };
  };
  const mapRow = data.mapRows.find((row) => row.id === mission.mapId);
  if (!mapRow) {
    throw new Error(`Mission ${mission.id}: unknown map ${mission.mapId}`);
  }
  for (const unit of mission.units) {
    if (!data.unitTypes.has(unit.unitType)) {
      throw new Error(`Mission ${mission.id}: unknown unit ${unit.unitType}`);
    }
  }
  for (const structure of mission.structures) {
    if (!data.structureTypes.has(structure.structureType)) {
      throw new Error(`Mission ${mission.id}: unknown structure ${structure.structureType}`);
    }
  }
  checkMissionReferences(data, mission);
  const human = mission.sides.find((side) => side.controller === 'human');
  if (!human) {
    throw new Error(`Mission ${mission.id}: no human side`);
  }
  const state: MissionState = {
    def: {
      id: mission.id,
      triggers: mission.triggers,
      timeLimitTicks: mission.timeLimitSec ? Math.round(mission.timeLimitSec * SIM_TICK_HZ) : null,
      // Normal leaves the field out, so a Normal mission is byte-for-byte the mission as written.
      ...(difficulty !== 'normal' ? { difficulty } : {}),
      ...(mission.sides.some((side) => side.available)
        ? {
            available: Object.fromEntries(
              mission.sides.filter((side) => side.available).map((side) => [String(side.player), side.available ?? []]),
            ),
          }
        : {}),
    },
    humanSide: human.player,
    fired: [],
    objectives: mission.objectives.map((o) => ({ ...o, status: 'active' as const })),
    messages: [],
    nextMessage: 1,
    tags: {},
    reveals: [],
    failReason: null,
  };
  const world = createWorld(seed, {
    mapSeed: MISSION_MAP_SEED,
    unitTypes: data.unitTypes,
    structureTypes: data.structureTypes,
    researchTree: data.researchTree,
    startUnits: mission.units.map((unit) => ({
      owner: unit.side,
      typeId: unit.unitType,
      x: unit.x,
      z: unit.z,
      heading: unit.heading ?? 0,
    })),
    startStructures: mission.structures.map((structure) => ({
      owner: structure.side,
      typeId: structure.structureType,
      x: structure.x,
      z: structure.z,
    })),
    deposits: mapRow.deposits.map((deposit) => ({ ...deposit })),
    factions: mission.sides.map((side) => ({ player: side.player, faction: side.faction })),
    startResources: mission.sides.map((side) => ({ player: side.player, ...startStock(side) })),
    size: mapRow.size,
    cellSize: mapRow.cellSize,
    fog: options.fog ?? false,
    mapFeatures: mapRow.features,
    sides: mission.sides.map((side) => ({
      player: side.player,
      controller: side.controller,
      team: side.team ?? side.player,
      groupId: side.groupId ?? null,
      provokable: side.provokable ?? true,
      forgiveAfterSec: side.forgiveAfterSec ?? null,
    })),
    relations: mission.relations ?? [],
    mission: state,
  });
  mission.units.forEach((unit, index) => {
    const spawned = world.units[index];
    if (unit.tag && spawned && world.mission) {
      tagUnit(world.mission, unit.tag, spawned.id);
    }
  });
  for (const side of mission.sides) {
    if (side.researchDone && side.researchDone.length > 0) {
      const entry = sideResearch(world, side.player);
      for (const id of convertResearchIds(side.researchDone)) {
        if (!entry.done.includes(id)) {
          entry.done.push(id);
        }
      }
    }
    if (side.controller === 'ai') {
      addAi(world, side.player, shiftLevel(side.difficulty ?? 'normal', tuning.aiStep), side.aiAttackScale ? { attackScaleRange: side.aiAttackScale } : {});
    }
  }
  return world;
}
