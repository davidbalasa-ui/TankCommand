import type { AssetRegistry } from '../assets/registry';
import { unitRowSchema, type UnitRow } from './unitSchema';
import { structureRowSchema, type StructureRow } from './structureSchema';
import { mapRowSchema, type MapRow } from './mapSchema';

export class UnitDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'UnitDataError';
  }
}

export class StructureDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'StructureDataError';
  }
}

export class MapDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'MapDataError';
  }
}

export function loadUnitTable(json: unknown, assetRegistry: AssetRegistry): ReadonlyMap<string, UnitRow> {
  if (!Array.isArray(json)) {
    throw new UnitDataError('Unit table must be an array');
  }

  const table = new Map<string, UnitRow>();

  for (const [index, raw] of json.entries()) {
    const parsed = unitRowSchema.safeParse(raw);
    if (!parsed.success) {
      const id =
        typeof raw === 'object' && raw !== null && 'id' in raw
          ? String((raw as { id?: unknown }).id)
          : `row ${index}`;
      throw new UnitDataError(`${id}: ${parsed.error.issues[0]?.message ?? 'invalid row'}`);
    }

    const row = parsed.data;
    if (table.has(row.id)) {
      throw new UnitDataError(`${row.id}: duplicate id`);
    }

    try {
      assetRegistry.get(row.modelAssetId);
    } catch {
      throw new UnitDataError(`${row.id}: missing model asset ${row.modelAssetId}`);
    }

    table.set(row.id, row);
  }

  return table;
}

export function loadStructureTable(json: unknown): ReadonlyMap<string, StructureRow> {
  if (!Array.isArray(json)) {
    throw new StructureDataError('Structure table must be an array');
  }
  const table = new Map<string, StructureRow>();
  for (const [index, raw] of json.entries()) {
    const parsed = structureRowSchema.safeParse(raw);
    if (!parsed.success) {
      const id =
        typeof raw === 'object' && raw !== null && 'id' in raw
          ? String((raw as { id?: unknown }).id)
          : `row ${index}`;
      throw new StructureDataError(`${id}: ${parsed.error.issues[0]?.message ?? 'invalid row'}`);
    }
    const row = parsed.data;
    if (table.has(row.id)) {
      throw new StructureDataError(`${row.id}: duplicate id`);
    }
    table.set(row.id, row);
  }
  return table;
}

export function loadMapTable(json: unknown): MapRow[] {
  if (!Array.isArray(json)) {
    throw new MapDataError('Map table must be an array');
  }
  const rows: MapRow[] = [];
  const ids = new Set<string>();
  for (const [index, raw] of json.entries()) {
    const parsed = mapRowSchema.safeParse(raw);
    if (!parsed.success) {
      const id =
        typeof raw === 'object' && raw !== null && 'id' in raw
          ? String((raw as { id?: unknown }).id)
          : `row ${index}`;
      throw new MapDataError(`${id}: ${parsed.error.issues[0]?.message ?? 'invalid row'}`);
    }
    if (ids.has(parsed.data.id)) {
      throw new MapDataError(`${parsed.data.id}: duplicate id`);
    }
    ids.add(parsed.data.id);
    rows.push(parsed.data);
  }
  return rows;
}

export function placeholderReport(table: ReadonlyMap<string, UnitRow>): string[] {
  return [...table.values()]
    .filter((row) => row.source.kind === 'placeholder')
    .map((row) => row.id)
    .sort();
}
