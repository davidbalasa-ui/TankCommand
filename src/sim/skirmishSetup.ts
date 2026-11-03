import {
  SKIRMISH_METAL,
  SKIRMISH_MINER_OFFSET,
  SKIRMISH_ORE,
  SKIRMISH_TANK_HEADING,
  SKIRMISH_TANK_OFFSETS,
  SKIRMISH_TUG_OFFSET,
} from './tuning';
import type {
  DepositDef,
  Faction,
  FactionAssignment,
  PlayerId,
  SimStructureType,
  SimUnitType,
  StartResources,
  StartStructure,
  StartUnit,
} from './types';

export interface SkirmishMapData {
  size: number;
  cellSize: number;
  starts: Array<{ player: PlayerId; x: number; z: number }>;
  deposits: DepositDef[];
}

export interface SkirmishSetup {
  size: number;
  cellSize: number;
  factions: FactionAssignment[];
  resources: StartResources[];
  startUnits: StartUnit[];
  startStructures: StartStructure[];
  deposits: DepositDef[];
}

function unitsOf(
  unitTypes: ReadonlyMap<string, SimUnitType>,
  faction: Faction,
): SimUnitType[] {
  return [...unitTypes.values()].filter((type) => type.faction === faction);
}

function structuresOf(
  structureTypes: ReadonlyMap<string, SimStructureType>,
  faction: Faction,
): SimStructureType[] {
  return [...structureTypes.values()].filter((type) => type.faction === faction);
}

export function buildSkirmishSetup(
  unitTypes: ReadonlyMap<string, SimUnitType>,
  structureTypes: ReadonlyMap<string, SimStructureType>,
  map: SkirmishMapData,
  factions: Array<{ player: PlayerId; faction: Faction }>,
): SkirmishSetup {
  const startUnits: StartUnit[] = [];
  const startStructures: StartStructure[] = [];

  for (const assignment of factions) {
    const start = map.starts.find((item) => item.player === assignment.player);
    if (!start) {
      continue;
    }
    const units = unitsOf(unitTypes, assignment.faction);
    const structures = structuresOf(structureTypes, assignment.faction);
    const pad = structures.find((type) => type.kind === 'pad');
    if (pad) {
      startStructures.push({
        owner: assignment.player,
        typeId: pad.id,
        x: start.x,
        z: start.z,
      });
    }
    const fighters = units.filter((type) => type.role === 'tank');
    const fallback = units.find((type) => type.weapon !== null && type.weapon.damage > 0);
    const tank = fighters[0] ?? fallback;
    if (tank) {
      for (const offset of SKIRMISH_TANK_OFFSETS) {
        startUnits.push({
          owner: assignment.player,
          typeId: tank.id,
          x: start.x + offset.x,
          z: start.z + offset.z,
          heading: Math.atan2(-start.z, -start.x),
        });
      }
    }
    const miner = units.find((type) => type.workerKind === 'oreMiner');
    if (miner) {
      startUnits.push({
        owner: assignment.player,
        typeId: miner.id,
        x: start.x + SKIRMISH_MINER_OFFSET.x,
        z: start.z + SKIRMISH_MINER_OFFSET.z,
        heading: SKIRMISH_TANK_HEADING,
      });
    }
    const tug = units.find((type) => type.workerKind === 'tug');
    if (tug) {
      startUnits.push({
        owner: assignment.player,
        typeId: tug.id,
        x: start.x + SKIRMISH_TUG_OFFSET.x,
        z: start.z + SKIRMISH_TUG_OFFSET.z,
        heading: SKIRMISH_TANK_HEADING,
      });
    }
  }

  return {
    size: map.size,
    cellSize: map.cellSize,
    factions: factions.map((entry) => ({ ...entry })),
    resources: factions.map((entry) => ({
      player: entry.player,
      ore: SKIRMISH_ORE,
      metal: SKIRMISH_METAL,
    })),
    startUnits,
    startStructures,
    deposits: map.deposits.map((deposit) => ({ ...deposit })),
  };
}
