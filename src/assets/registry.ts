import type { AssetEntry, AssetManifest, AssetKind } from './manifestSchema';

export interface AssetFilter {
  kind?: AssetKind;
  faction?: 'human' | 'alien' | 'neutral';
  tag?: string;
}

export class UnknownAssetError extends Error {
  public readonly id: string;

  constructor(id: string) {
    super(`Unknown asset: ${id}`);
    this.name = 'UnknownAssetError';
    this.id = id;
  }
}

export class AssetRegistry {
  private readonly byId = new Map<string, AssetEntry>();

  constructor(manifest: AssetManifest) {
    for (const entry of manifest.assets) {
      this.byId.set(entry.id, entry);
    }
  }

  get(id: string): AssetEntry {
    const entry = this.byId.get(id);
    if (!entry) {
      throw new UnknownAssetError(id);
    }
    return entry;
  }

  list(filter: AssetFilter = {}): AssetEntry[] {
    return [...this.byId.values()].filter((entry) => {
      if (filter.kind && entry.kind !== filter.kind) {
        return false;
      }
      if (filter.faction && entry.faction !== filter.faction) {
        return false;
      }
      if (filter.tag && !(entry.tags ?? []).includes(filter.tag)) {
        return false;
      }
      return true;
    });
  }

  lodsOf(id: string): AssetEntry[] {
    this.get(id);
    return [...this.byId.values()]
      .filter((entry) => entry.lod?.of === id)
      .sort((a, b) => (a.lod?.level ?? 0) - (b.lod?.level ?? 0));
  }
}
