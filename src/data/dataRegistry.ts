import type { AssetRegistry } from '../assets/registry';
import { unitRowSchema, type UnitRow } from './unitSchema';

export class UnitDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'UnitDataError';
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

export function placeholderReport(table: ReadonlyMap<string, UnitRow>): string[] {
  return [...table.values()]
    .filter((row) => row.source.kind === 'placeholder')
    .map((row) => row.id)
    .sort();
}
