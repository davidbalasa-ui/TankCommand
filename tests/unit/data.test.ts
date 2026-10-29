import { describe, expect, it } from 'vitest';
import rawManifest from '../../public/assets/manifest.json';
import units from '../../src/data/units.placeholder.json';
import { parseAssetManifest } from '../../src/assets/manifestSchema';
import { AssetRegistry } from '../../src/assets/registry';
import { loadUnitTable, placeholderReport } from '../../src/data/dataRegistry';

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
    expect(table.size).toBe(2);
    expect([...table.keys()].sort()).toEqual([
      'unit.alien.light_skimmer',
      'unit.human.light_tank',
    ]);
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
      'unit.alien.light_skimmer',
      'unit.human.light_tank',
    ]);

    const row = table.get('unit.human.light_tank');
    expect(row).toBeDefined();
    if (!row) {
      return;
    }
    const changed = new Map(table);
    changed.set(row.id, { ...row, source: { kind: 'tuned', ref: 'x' } });
    expect(placeholderReport(changed)).toEqual(['unit.alien.light_skimmer']);
  });
});
