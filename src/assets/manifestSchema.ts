import { z } from 'zod';

export const LICENSE_VALUES = ['CC0', 'CC-BY-4.0', 'CC-BY-3.0', 'ORIGINAL'] as const;
export type License = (typeof LICENSE_VALUES)[number];
export type AssetKind = 'model' | 'texture' | 'audio';

const assetEntrySchema = z.object({
  id: z.string().regex(/^[a-z0-9]+(\.[a-z0-9_]+)+$/),
  kind: z.enum(['model', 'texture', 'audio']),
  path: z.string(),
  bytes: z.number().int().positive(),
  faction: z.enum(['human', 'alien', 'neutral']).optional(),
  lod: z
    .object({
      level: z.union([z.literal(0), z.literal(1), z.literal(2)]),
      of: z.string(),
    })
    .optional(),
  tags: z.array(z.string()).optional(),
  credit: z.object({
    license: z.enum(LICENSE_VALUES),
    author: z.string().min(1),
    title: z.string().min(1),
    source: z.string().url().optional(),
    usedFor: z.string().min(1),
  }),
});

export type AssetEntry = z.infer<typeof assetEntrySchema>;

export interface AssetManifest {
  version: 1;
  assets: AssetEntry[];
}

export class AssetManifestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AssetManifestError';
  }
}

const topSchema = z.object({
  version: z.literal(1),
  assets: z.array(z.unknown()),
});

function extractId(raw: unknown): string {
  if (typeof raw === 'object' && raw !== null && 'id' in raw) {
    const value = (raw as { id?: unknown }).id;
    if (typeof value === 'string') {
      return value;
    }
  }
  return '<unknown>';
}

export function parseAssetManifest(input: unknown): AssetManifest {
  const top = topSchema.safeParse(input);
  if (!top.success) {
    throw new AssetManifestError(
      `Invalid manifest: ${top.error.issues.map((issue) => issue.message).join('; ')}`,
    );
  }

  const assets: AssetEntry[] = [];
  for (const raw of top.data.assets) {
    const id = extractId(raw);
    const parsed = assetEntrySchema.safeParse(raw);
    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      throw new AssetManifestError(`asset "${id}": ${issue?.message ?? 'invalid'}`);
    }
    assets.push(parsed.data);
  }

  const ids = new Set<string>();
  const paths = new Set<string>();

  for (const entry of assets) {
    if (ids.has(entry.id)) {
      throw new AssetManifestError(`asset "${entry.id}": duplicate id`);
    }
    ids.add(entry.id);

    if (paths.has(entry.path)) {
      throw new AssetManifestError(`asset "${entry.id}": duplicate path "${entry.path}"`);
    }
    paths.add(entry.path);

    if (
      !entry.path.startsWith('assets/') ||
      entry.path.startsWith('/') ||
      entry.path.split('/').includes('..')
    ) {
      throw new AssetManifestError(`asset "${entry.id}": invalid path`);
    }

    if (entry.credit.license.startsWith('CC-BY') && !entry.credit.source) {
      throw new AssetManifestError(`asset "${entry.id}": CC-BY licence requires source`);
    }

    if (entry.credit.source && !entry.credit.source.startsWith('https://')) {
      throw new AssetManifestError(`asset "${entry.id}": source must be an https URL`);
    }
  }

  for (const entry of assets) {
    if (entry.lod) {
      if (entry.lod.of === entry.id) {
        throw new AssetManifestError(`asset "${entry.id}": lod.of cannot point to itself`);
      }
      if (!ids.has(entry.lod.of)) {
        throw new AssetManifestError(`asset "${entry.id}": lod.of "${entry.lod.of}" not found`);
      }
    }
  }

  return { version: 1, assets };
}
