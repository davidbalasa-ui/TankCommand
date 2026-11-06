import { describe, expect, it } from 'vitest';
import rawManifest from '../../public/assets/manifest.json';
import units from '../../src/data/units.placeholder.json';
import structures from '../../src/data/structures.placeholder.json';
import maps from '../../src/data/maps.placeholder.json';
import { parseAssetManifest } from '../../src/assets/manifestSchema';
import { AssetRegistry } from '../../src/assets/registry';
import {
  loadMapTable,
  loadStructureTable,
  loadUnitTable,
  placeholderReport,
} from '../../src/data/dataRegistry';

const registry = new AssetRegistry(parseAssetManifest(rawManifest));
const rows = units as unknown[];

function cloneBase(): Record<string, unknown> {
  return JSON.parse(JSON.stringify(rows[0])) as Record<string, unknown>;
}

function weaponsOf(row: Record<string, unknown>): Array<Record<string, unknown>> {
  return row.weapons as Array<Record<string, unknown>>;
}

describe('unit data containers', () => {
  it('[DATA-01] placeholder table loads against the real asset manifest', () => {
    const table = loadUnitTable(units, registry);
    expect(table.size).toBe(20);
    expect([...table.keys()].sort()).toEqual([
      'unit.alien.dropper',
      'unit.alien.glider',
      'unit.alien.light_skimmer',
      'unit.alien.light_tank',
      'unit.alien.ore_miner',
      'unit.alien.radar',
      'unit.alien.repair',
      'unit.alien.saucer',
      'unit.alien.tug',
      'unit.alien.turret_packed',
      'unit.human.bomber',
      'unit.human.fighter',
      'unit.human.hover_tank',
      'unit.human.light_tank',
      'unit.human.ore_miner',
      'unit.human.radar',
      'unit.human.repair',
      'unit.human.scout',
      'unit.human.tug',
      'unit.human.turret_packed',
    ]);
    const structureTable = loadStructureTable(structures);
    expect(structureTable.size).toBe(12);
    const mapTable = loadMapTable(maps);
    expect(mapTable).toHaveLength(2);
    expect(mapTable[0]?.deposits.filter((d) => d.kind === 'ore')).toHaveLength(8);
    expect(mapTable[0]?.deposits.filter((d) => d.kind === 'metal')).toHaveLength(4);
  });

  it('[DATA-02] duplicate id is rejected', () => {
    expect(() => loadUnitTable([cloneBase(), cloneBase()], registry)).toThrow(/duplicate id/);
  });

  it('[DATA-02] missing modelAssetId in registry is rejected', () => {
    const row = cloneBase();
    row.modelAssetId = 'unit.human.missing_model';
    expect(() => loadUnitTable([row], registry)).toThrow(/missing model asset/);
  });

  it('[DATA-02] worker without carryCapacity is rejected', () => {
    const row = cloneBase();
    row.role = 'worker';
    delete row.carryCapacity;
    expect(() => loadUnitTable([row], registry)).toThrow(/carryCapacity/);
  });

  it('[DATA-02] ore miner without mining rate is rejected', () => {
    const row = cloneBase();
    row.workerKind = 'oreMiner';
    row.role = 'worker';
    row.carryCapacity = 10;
    delete row.miningRatePerSec;
    expect(() => loadUnitTable([row], registry)).toThrow(/miningRatePerSec/);
  });

  it('[DATA-02] sensorRange below sightRange is rejected', () => {
    const row = cloneBase();
    row.sightRange = 20;
    row.sensorRange = 19;
    expect(() => loadUnitTable([row], registry)).toThrow(/sensorRange/);
  });

  it('[DATA-02] accuracy above 1 is rejected', () => {
    const row = cloneBase();
    weaponsOf(row)[0]!.accuracy = 1.5;
    expect(() => loadUnitTable([row], registry)).toThrow(/accuracy|less than or equal/);
  });

  it('[DATA-02] empty targets array is rejected', () => {
    const row = cloneBase();
    weaponsOf(row)[0]!.targets = [];
    expect(() => loadUnitTable([row], registry)).toThrow(/targets|at least/);
  });

  it('[DATA-02] video source without ref is rejected', () => {
    const row = cloneBase();
    row.source = { kind: 'video' };
    expect(() => loadUnitTable([row], registry)).toThrow(/source\.ref/);
  });

  it('[DATA-03] placeholderReport lists placeholder rows and drops tuned rows', () => {
    const table = loadUnitTable(units, registry);
    expect(placeholderReport(table)).toEqual([
      'unit.alien.dropper',
      'unit.alien.glider',
      'unit.alien.light_skimmer',
      'unit.alien.light_tank',
      'unit.alien.ore_miner',
      'unit.alien.radar',
      'unit.alien.repair',
      'unit.alien.saucer',
      'unit.alien.tug',
      'unit.alien.turret_packed',
      'unit.human.bomber',
      'unit.human.fighter',
      'unit.human.hover_tank',
      'unit.human.light_tank',
      'unit.human.ore_miner',
      'unit.human.radar',
      'unit.human.repair',
      'unit.human.scout',
      'unit.human.tug',
      'unit.human.turret_packed',
    ]);

    const row = table.get('unit.human.light_tank');
    expect(row).toBeDefined();
    if (!row) {
      return;
    }
    const changed = new Map(table);
    changed.set(row.id, { ...row, source: { kind: 'tuned', ref: 'x' } });
    expect(placeholderReport(changed)).toEqual([
      'unit.alien.dropper',
      'unit.alien.glider',
      'unit.alien.light_skimmer',
      'unit.alien.light_tank',
      'unit.alien.ore_miner',
      'unit.alien.radar',
      'unit.alien.repair',
      'unit.alien.saucer',
      'unit.alien.tug',
      'unit.alien.turret_packed',
      'unit.human.bomber',
      'unit.human.fighter',
      'unit.human.hover_tank',
      'unit.human.ore_miner',
      'unit.human.radar',
      'unit.human.repair',
      'unit.human.scout',
      'unit.human.tug',
      'unit.human.turret_packed',
    ]);
  });
});
