import units from './units.placeholder.json';
import structures from './structures.placeholder.json';
import maps from './maps.placeholder.json';
import campaignMaps from './maps.campaign.json';
import research from './research.placeholder.json';
import type { AssetRegistry } from '../assets/registry';
import { loadMapTable, loadResearchTable, loadStructureTable, loadUnitTable } from './dataRegistry';
import type { MapRow } from './mapSchema';
import type { StructureRow } from './structureSchema';
import type { UnitRow } from './unitSchema';
import { DEFAULT_DISMANTLE_REFUND_PERCENT, DEFAULT_DISMANTLE_SEC, UNIT_RADIUS } from '../sim/tuning';
import type { ResearchNode, SimStructureType, SimUnitType, WorldState } from '../sim/types';
import { addAi } from '../ai/driver';
import { buildSkirmishSetup } from '../sim/skirmishSetup';
import { createWorld } from '../sim/world';

export function buildUnitTypes(table: ReadonlyMap<string, UnitRow>): ReadonlyMap<string, SimUnitType> {
  const result = new Map<string, SimUnitType>();
  for (const row of table.values()) {
    const weapon = row.weapons[0];
    result.set(row.id, {
      id: row.id,
      modelId: row.modelAssetId,
      visualScale: row.modelScale ?? row.visualScale,
      // Bigger models take more room: footprint follows drawn size, within limits.
      radius: UNIT_RADIUS * Math.min(1.4, Math.max(0.85, row.visualScale ?? 1)),
      faction: row.faction,
      role: row.role,
      hp: row.hp,
      armor: row.armor,
      topSpeed: row.speed.top,
      accel: row.speed.accel,
      turnDegPerSec: row.speed.turnDegPerSec,
      turretTurnDegPerSec: row.turretTurnDegPerSec,
      fireOnMove: row.fireOnMove,
      sightRange: row.sightRange,
      sensorRange: row.sensorRange,
      weapon: weapon
        ? {
            kind: weapon.id,
            damage: weapon.damage,
            range: weapon.range,
            reloadSec: weapon.reloadSec,
            projectileSpeed: weapon.projectileSpeed,
            accuracy: weapon.accuracy,
            splashRadius: weapon.splashRadius,
            targets: [...weapon.targets],
          }
        : null,
      oreCost: row.cost.ore,
      metalCost: row.cost.metal,
      deliverySec: row.deliverySec,
      workerKind: row.workerKind ?? null,
      miningRatePerSec: row.miningRatePerSec ?? 0,
      carryCapacity: row.carryCapacity ?? 0,
      salvageRefundPercent: row.salvageRefundPercent ?? 0,
      repair: row.repair
        ? { radius: row.repair.radius, ratePerSec: row.repair.ratePerSec, unitsOnly: row.repair.unitsOnly ?? false }
        : null,
      deploysTo: row.deploysTo ?? null,
      deploySec: row.deploySec ?? 0,
      upgrades: [...row.upgrades],
      movement: row.movement ?? 'tracked',
      air: row.air ? { ...row.air } : null,
    });
  }
  return result;
}

export function buildStructureTypes(
  table: ReadonlyMap<string, StructureRow>,
): ReadonlyMap<string, SimStructureType> {
  const result = new Map<string, SimStructureType>();
  for (const row of table.values()) {
    result.set(row.id, {
      id: row.id,
      name: row.name,
      faction: row.faction,
      kind: row.kind,
      cost: { ore: row.cost.ore, metal: row.cost.metal },
      deliverySec: row.deliverySec,
      hp: row.hp,
      armor: row.armor,
      footprint: { cellsX: row.footprint.cellsX, cellsZ: row.footprint.cellsZ },
      sightRange: row.sightRange,
      modelId: row.modelId,
      buildOnMetalDeposit: row.buildOnMetalDeposit,
      metalRatePerSec: row.metalRatePerSec ?? 0,
      containerSize: row.containerSize ?? 0,
      maxContainers: row.maxContainers ?? 0,
      weapon: row.weapon ? { ...row.weapon } : null,
      turretTurnDegPerSec: row.turretTurnDegPerSec ?? 0,
      packSec: row.packSec ?? 0,
      packedUnitId: row.packedUnitId ?? null,
      dismantleSec: row.dismantleSec ?? DEFAULT_DISMANTLE_SEC,
      dismantleRefundPercent: row.dismantleRefundPercent ?? DEFAULT_DISMANTLE_REFUND_PERCENT,
      sensorRange: row.sensorRange ?? row.sightRange,
      upgrades: [...(row.upgrades ?? [])],
      airCapacity: row.airCapacity ?? 0,
      buyable: row.buyable ?? true,
    });
  }
  return result;
}


export interface SimData {
  unitTypes: ReadonlyMap<string, SimUnitType>;
  structureTypes: ReadonlyMap<string, SimStructureType>;
  unitRows: UnitRow[];
  structureRows: StructureRow[];
  researchTree: ReadonlyMap<string, ResearchNode>;
  mapData: MapRow;
  mapRows: MapRow[];
}

export function loadSimData(registry: AssetRegistry): SimData {
  const table = loadUnitTable(units, registry);
  const structureTable = loadStructureTable(structures);
  const mapRows = loadMapTable([...maps, ...campaignMaps]);
  const mapData = mapRows[0];
  if (!mapData) {
    throw new Error('No map data available');
  }
  const researchTable = loadResearchTable(
    research,
    new Set([...table.keys(), ...structureTable.keys()]),
  );
  return {
    unitTypes: buildUnitTypes(table),
    structureTypes: buildStructureTypes(structureTable),
    unitRows: [...table.values()],
    structureRows: [...structureTable.values()],
    researchTree: new Map(
      [...researchTable.values()].map((row) => [
        row.id,
        {
          id: row.id,
          name: row.name,
          faction: row.faction,
          cost: { ore: row.cost.ore, metal: row.cost.metal },
          timeSec: row.timeSec,
          requires: [...row.requires],
          unlocks: [...row.unlocks],
          upgrades: [...row.upgrades],
        },
      ]),
    ),
    mapData,
    mapRows,
  };
}

export interface SkirmishSideSpec {
  player: number;
  faction: 'human' | 'alien';
  controller: 'human' | 'ai';
  difficulty?: 'easy' | 'normal' | 'hard';
}

export type SkirmishResources = 'low' | 'normal' | 'high';
export type SkirmishForce = 'padOnly' | 'padForce';

export interface SkirmishOptions {
  fog?: boolean;
  mapId?: string;
  resources?: SkirmishResources;
  force?: SkirmishForce;
}

const RESOURCE_SCALE: Record<SkirmishResources, number> = { low: 0.5, normal: 1, high: 2 };

// Extra start corners for matches with three or four sides; the map row only lists two.
const EXTRA_STARTS = [
  { player: 3, x: 50, z: -50 },
  { player: 4, x: -50, z: 50 },
];

function cornerDeposits(x: number, z: number): MapRow['deposits'] {
  const a = Math.sign(x);
  const b = Math.sign(z);
  return [
    { kind: 'ore', x: a * 57, z: b * 44, amount: 500 },
    { kind: 'ore', x: a * 44, z: b * 57, amount: 500 },
    { kind: 'ore', x: a * 60, z: b * 50, amount: 500 },
    { kind: 'ore', x: a * 50, z: b * 60, amount: 500 },
    { kind: 'metal', x: a * 58, z: b * 52, amount: 250 },
    { kind: 'metal', x: a * 52, z: b * 58, amount: 250 },
  ];
}

// Builds a skirmish world from the placeholder data. Used by the app and by headless AI tests.
export function createSkirmishWorld(
  data: SimData,
  seed: number,
  specs: SkirmishSideSpec[],
  options: SkirmishOptions = {},
): WorldState {
  const mapRow = data.mapRows.find((row) => row.id === options.mapId) ?? data.mapData;
  const starts = [...mapRow.starts];
  const deposits = mapRow.deposits.map((deposit) => ({ ...deposit }));
  for (const extra of EXTRA_STARTS) {
    if (specs.some((spec) => spec.player === extra.player) && !starts.some((s) => s.player === extra.player)) {
      starts.push(extra);
      deposits.push(...cornerDeposits(extra.x, extra.z));
    }
  }
  const setup = buildSkirmishSetup(
    data.unitTypes,
    data.structureTypes,
    { size: mapRow.size, cellSize: mapRow.cellSize, starts, deposits },
    specs.map((spec) => ({ player: spec.player, faction: spec.faction })),
  );
  const scale = RESOURCE_SCALE[options.resources ?? 'normal'];
  const world = createWorld(seed, {
    unitTypes: data.unitTypes,
    structureTypes: data.structureTypes,
    researchTree: data.researchTree,
    startUnits: options.force === 'padOnly' ? [] : setup.startUnits,
    startStructures: setup.startStructures,
    deposits: setup.deposits,
    factions: setup.factions,
    startResources: setup.resources.map((entry) => ({
      player: entry.player,
      ore: Math.round(entry.ore * scale),
      metal: Math.round(entry.metal * scale),
    })),
    size: setup.size,
    cellSize: setup.cellSize,
    fog: options.fog ?? true,
    mapFeatures: mapRow.features,
    sides: specs.map((spec) => ({
      player: spec.player,
      controller: spec.controller,
      team: spec.player,
      groupId: null,
      provokable: true,
      forgiveAfterSec: null,
    })),
  });
  for (const spec of specs) {
    if (spec.controller === 'ai') {
      addAi(world, spec.player, spec.difficulty ?? 'normal');
    }
  }
  return world;
}
