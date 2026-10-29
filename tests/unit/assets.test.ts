import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import rawManifest from '../../public/assets/manifest.json';
import {
  AssetManifestError,
  parseAssetManifest,
  type AssetEntry,
  type AssetManifest,
} from '../../src/assets/manifestSchema';
import { AssetRegistry } from '../../src/assets/registry';
import { AssetLoadError, AssetLoader } from '../../src/assets/loader';

function baseEntry(): Record<string, unknown> {
  return {
    id: 'unit.test.tank',
    kind: 'model',
    path: 'assets/models/test.glb',
    bytes: 4,
    credit: {
      license: 'ORIGINAL',
      author: 'Test Author',
      title: 'Test Asset',
      usedFor: 'Tests',
    },
  };
}

function makeEntry(overrides: Partial<AssetEntry> = {}): AssetEntry {
  const base = baseEntry();
  return {
    id: typeof base.id === 'string' ? base.id : 'unit.test.tank',
    kind: 'model',
    path: typeof base.path === 'string' ? base.path : 'assets/models/test.glb',
    bytes: 4,
    credit: {
      license: 'ORIGINAL',
      author: 'Test Author',
      title: 'Test Asset',
      usedFor: 'Tests',
    },
    ...overrides,
  };
}

function manifestWith(assets: AssetEntry[]): AssetManifest {
  return { version: 1, assets };
}

function registryWith(assets: AssetEntry[]): AssetRegistry {
  return new AssetRegistry(parseAssetManifest(manifestWith(assets)));
}

describe('asset containers', () => {
  it('[ASSET-01] real public asset manifest validates', () => {
    const parsed = parseAssetManifest(rawManifest);
    expect(parsed.assets).toHaveLength(1);
    expect(parsed.assets[0]?.id).toBe('unit.human.poc_tank');
  });

  it('[ASSET-02] duplicate id is rejected with the offending id in the message', () => {
    const one = baseEntry();
    const two = { ...baseEntry(), path: 'assets/models/other.glb' };
    expect(() => parseAssetManifest({ version: 1, assets: [one, two] })).toThrow(
      /unit\.test\.tank/,
    );
  });

  it('[ASSET-02] duplicate path is rejected with the offending id in the message', () => {
    const one = baseEntry();
    const two = { ...baseEntry(), id: 'unit.test.duplicate_path' };
    expect(() => parseAssetManifest({ version: 1, assets: [one, two] })).toThrow(
      /unit\.test\.duplicate_path/,
    );
  });

  it('[ASSET-02] unknown licence is rejected with the offending id in the message', () => {
    const one = {
      ...baseEntry(),
      id: 'unit.test.bad_license',
      credit: { ...(baseEntry().credit as Record<string, unknown>), license: 'CC-BY-NC-4.0' },
    };
    expect(() => parseAssetManifest({ version: 1, assets: [one] })).toThrow(
      /unit\.test\.bad_license/,
    );
  });

  it('[ASSET-02] CC-BY without source is rejected with the offending id in the message', () => {
    const one = {
      ...baseEntry(),
      id: 'unit.test.ccby_no_source',
      credit: {
        license: 'CC-BY-4.0',
        author: 'Author',
        title: 'Title',
        usedFor: 'Tests',
      },
    };
    expect(() => parseAssetManifest({ version: 1, assets: [one] })).toThrow(
      /unit\.test\.ccby_no_source/,
    );
  });

  it('[ASSET-02] lod.of missing target is rejected with the offending id in the message', () => {
    const one = {
      ...baseEntry(),
      id: 'unit.test.lod_missing',
      lod: { level: 0, of: 'unit.test.not_there' },
    };
    expect(() => parseAssetManifest({ version: 1, assets: [one] })).toThrow(
      /unit\.test\.lod_missing/,
    );
  });

  it('[ASSET-02] lod.of self reference is rejected with the offending id in the message', () => {
    const one = {
      ...baseEntry(),
      id: 'unit.test.lod_self',
      lod: { level: 0, of: 'unit.test.lod_self' },
    };
    expect(() => parseAssetManifest({ version: 1, assets: [one] })).toThrow(
      /unit\.test\.lod_self/,
    );
  });

  it('[ASSET-02] path with parent traversal is rejected with the offending id in the message', () => {
    const one = { ...baseEntry(), id: 'unit.test.dotdot', path: 'assets/../evil.glb' };
    expect(() => parseAssetManifest({ version: 1, assets: [one] })).toThrow(
      /unit\.test\.dotdot/,
    );
  });

  it('[ASSET-02] absolute path is rejected with the offending id in the message', () => {
    const one = { ...baseEntry(), id: 'unit.test.absolute', path: '/assets/evil.glb' };
    expect(() => parseAssetManifest({ version: 1, assets: [one] })).toThrow(
      /unit\.test\.absolute/,
    );
  });

  it('[ASSET-03] every real manifest file exists and has the recorded byte size', () => {
    const parsed = parseAssetManifest(rawManifest);
    for (const entry of parsed.assets) {
      const file = join(process.cwd(), 'public', entry.path);
      expect(existsSync(file)).toBe(true);
      expect(statSync(file).size).toBe(entry.bytes);
    }
  });

  it('[ASSET-04] concurrent loads for one id share one fetch', async () => {
    const entry = makeEntry({ id: 'unit.test.dedupe' });
    const registry = registryWith([entry]);
    const fetchBytes = vi.fn(async () => new ArrayBuffer(4));
    const loader = new AssetLoader({
      registry,
      fetchBytes,
      baseUrl: './',
      decoders: {
        model: async () => 'model',
        texture: async () => 'texture',
        audio: async () => new ArrayBuffer(0),
      },
    });

    const values = await Promise.all(Array.from({ length: 5 }, () => loader.load(entry.id)));
    expect(values).toEqual(['model', 'model', 'model', 'model', 'model']);
    expect(fetchBytes).toHaveBeenCalledTimes(1);
  });

  it('[ASSET-05] failed loads are not cached and retry can succeed', async () => {
    const entry = makeEntry({ id: 'unit.test.retry' });
    const registry = registryWith([entry]);
    let calls = 0;
    const fetchBytes = vi.fn(async (): Promise<ArrayBuffer> => {
      calls += 1;
      if (calls === 1) {
        throw new Error('network down');
      }
      return new ArrayBuffer(4);
    });
    const loader = new AssetLoader({
      registry,
      fetchBytes,
      baseUrl: './',
      decoders: {
        model: async () => 'ok',
        texture: async () => 'texture',
        audio: async () => new ArrayBuffer(0),
      },
    });

    await expect(loader.load(entry.id)).rejects.toBeInstanceOf(AssetLoadError);
    await expect(loader.load(entry.id)).resolves.toBe('ok');
    expect(fetchBytes).toHaveBeenCalledTimes(2);
  });

  it('[ASSET-06] refcount keeps cache until the final release and disposes once', async () => {
    const entry = makeEntry({ id: 'unit.test.refcount' });
    const registry = registryWith([entry]);
    const fetchBytes = vi.fn(async () => new ArrayBuffer(4));
    const dispose = vi.fn();
    const loader = new AssetLoader({
      registry,
      fetchBytes,
      baseUrl: './',
      dispose,
      decoders: {
        model: async () => ({ id: 'asset' }),
        texture: async () => 'texture',
        audio: async () => new ArrayBuffer(0),
      },
    });

    await loader.load(entry.id);
    await loader.load(entry.id);
    expect(fetchBytes).toHaveBeenCalledTimes(1);

    loader.release(entry.id);
    expect(dispose).not.toHaveBeenCalled();
    expect(fetchBytes).toHaveBeenCalledTimes(1);

    loader.release(entry.id);
    expect(dispose).toHaveBeenCalledTimes(1);

    await loader.load(entry.id);
    expect(fetchBytes).toHaveBeenCalledTimes(2);
  });

  it('[ASSET-07] preload reports each id, rejects with all failures and caches successes', async () => {
    const goodOne = makeEntry({ id: 'unit.test.good_one', path: 'assets/good-one.bin' });
    const goodTwo = makeEntry({ id: 'unit.test.good_two', path: 'assets/good-two.bin' });
    const bad = makeEntry({ id: 'unit.test.bad_size', path: 'assets/bad.bin' });
    const registry = registryWith([goodOne, goodTwo, bad]);
    const fetchBytes = vi.fn(async (url: string): Promise<ArrayBuffer> => {
      if (url.includes('bad.bin')) {
        return new ArrayBuffer(2);
      }
      return new ArrayBuffer(4);
    });
    const loader = new AssetLoader({
      registry,
      fetchBytes,
      baseUrl: './',
      decoders: {
        model: async (_buffer, entry) => entry.id,
        texture: async () => 'texture',
        audio: async () => new ArrayBuffer(0),
      },
    });

    const progress: Array<{ loaded: number; total: number; id: string }> = [];
    let caught: unknown;
    try {
      await loader.preload(
        [goodOne.id, goodTwo.id, bad.id],
        (update) => {
          progress.push(update);
        },
      );
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(AggregateError);
    expect((caught as AggregateError).message).toContain(bad.id);
    expect(progress).toHaveLength(3);
    expect(progress.every((update) => update.total === 3)).toBe(true);
    expect(new Set(progress.map((update) => update.id))).toEqual(
      new Set([goodOne.id, goodTwo.id, bad.id]),
    );

    const fetchCount = fetchBytes.mock.calls.length;
    await expect(loader.load(goodOne.id)).resolves.toBe(goodOne.id);
    expect(fetchBytes).toHaveBeenCalledTimes(fetchCount);
  });

  it('[ASSET-08] byte size mismatch rejects with AssetLoadError', async () => {
    const entry = makeEntry({ id: 'unit.test.size_mismatch', bytes: 4 });
    const registry = registryWith([entry]);
    const loader = new AssetLoader({
      registry,
      fetchBytes: async () => new ArrayBuffer(3),
      baseUrl: './',
      decoders: {
        model: async () => 'model',
        texture: async () => 'texture',
        audio: async () => new ArrayBuffer(0),
      },
    });

    await expect(loader.load(entry.id)).rejects.toBeInstanceOf(AssetLoadError);
  });

  it('[ASSET-09] credits check passes on committed files and fails when the manifest changes', () => {
    const root = process.cwd();
    const committed = spawnSync(process.execPath, ['scripts/credits.mjs', '--check'], {
      cwd: root,
      encoding: 'utf8',
    });
    expect(committed.status).toBe(0);

    const temp = mkdtempSync(join(tmpdir(), 'tc-credits-'));
    try {
      const manifestPath = join(temp, 'manifest.json');
      const outPath = join(temp, 'CREDITS.md');
      const parsed = parseAssetManifest(rawManifest);
      writeFileSync(manifestPath, JSON.stringify(parsed, null, 2), 'utf8');

      execFileSync(process.execPath, ['scripts/credits.mjs', '--manifest', manifestPath, '--out', outPath], {
        cwd: root,
      });
      const passing = spawnSync(
        process.execPath,
        ['scripts/credits.mjs', '--manifest', manifestPath, '--out', outPath, '--check'],
        { cwd: root, encoding: 'utf8' },
      );
      expect(passing.status).toBe(0);

      const changed = {
        ...parsed,
        assets: [
          ...parsed.assets,
          makeEntry({ id: 'unit.test.extra_credit', path: 'assets/models/extra.glb' }),
        ],
      };
      writeFileSync(manifestPath, JSON.stringify(changed, null, 2), 'utf8');
      const failing = spawnSync(
        process.execPath,
        ['scripts/credits.mjs', '--manifest', manifestPath, '--out', outPath, '--check'],
        { cwd: root, encoding: 'utf8' },
      );
      expect(failing.status).not.toBe(0);
      expect(`${failing.stdout}${failing.stderr}`).toContain('Stale credits');
    } finally {
      rmSync(temp, { recursive: true, force: true });
    }
  });

  it('[ASSET-02] manifest errors expose a stable error class', () => {
    expect(() => parseAssetManifest({ version: 1, assets: [baseEntry(), baseEntry()] })).toThrow(
      AssetManifestError,
    );
  });
});
