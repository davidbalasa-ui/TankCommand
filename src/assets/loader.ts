import type { AssetEntry } from './manifestSchema';
import type { AssetRegistry } from './registry';

export type AssetDecoder<T> = (buffer: ArrayBuffer, entry: AssetEntry) => Promise<T>;

export interface AssetDecoders<M, T, A> {
  model: AssetDecoder<M>;
  texture: AssetDecoder<T>;
  audio: AssetDecoder<A>;
}

export type DecodedAsset<M, T, A> = M | T | A;

export interface AssetLoaderOptions<M, T, A> {
  registry: AssetRegistry;
  fetchBytes: (url: string) => Promise<ArrayBuffer>;
  decoders: AssetDecoders<M, T, A>;
  baseUrl: string;
  dispose?: (asset: DecodedAsset<M, T, A>) => void;
}

export interface PreloadProgress {
  loaded: number;
  total: number;
  id: string;
}

interface CacheEntry<M, T, A> {
  refCount: number;
  resolved: boolean;
  asset?: DecodedAsset<M, T, A>;
  promise: Promise<DecodedAsset<M, T, A>>;
}

export class AssetLoadError extends Error {
  public readonly id: string;
  public override readonly cause: unknown;

  constructor(id: string, cause: unknown) {
    super(`Failed to load asset "${id}"`);
    this.name = 'AssetLoadError';
    this.id = id;
    this.cause = cause;
  }
}

export class AssetLoader<M = unknown, T = unknown, A = unknown> {
  private readonly options: AssetLoaderOptions<M, T, A>;
  private readonly cache = new Map<string, CacheEntry<M, T, A>>();

  constructor(options: AssetLoaderOptions<M, T, A>) {
    this.options = options;
  }

  load(id: string): Promise<DecodedAsset<M, T, A>> {
    const entry = this.options.registry.get(id);
    const existing = this.cache.get(id);
    if (existing) {
      existing.refCount += 1;
      return existing.promise;
    }

    const cacheEntry: Partial<CacheEntry<M, T, A>> = {
      refCount: 1,
      resolved: false,
    };

    const promise = this.loadInternal(entry).then(
      (asset) => {
        cacheEntry.resolved = true;
        cacheEntry.asset = asset;
        return asset;
      },
      (error: unknown) => {
        this.cache.delete(id);
        if (error instanceof AssetLoadError) {
          throw error;
        }
        throw new AssetLoadError(id, error);
      },
    );

    cacheEntry.promise = promise;
    this.cache.set(id, cacheEntry as CacheEntry<M, T, A>);
    return promise;
  }

  release(id: string): void {
    const entry = this.cache.get(id);
    if (!entry) {
      return;
    }
    entry.refCount -= 1;
    if (entry.refCount > 0) {
      return;
    }
    this.cache.delete(id);
    if (entry.resolved) {
      this.options.dispose?.(entry.asset as DecodedAsset<M, T, A>);
    }
  }

  async preload(ids: readonly string[], onProgress?: (progress: PreloadProgress) => void): Promise<void> {
    const total = ids.length;
    let loaded = 0;
    const failures: Array<{ id: string; error: unknown }> = [];

    await Promise.all(
      ids.map(async (id) => {
        try {
          await this.load(id);
        } catch (error) {
          failures.push({ id, error });
        } finally {
          loaded += 1;
          onProgress?.({ loaded, total, id });
        }
      }),
    );

    if (failures.length > 0) {
      const message = `Failed to preload assets: ${failures.map((failure) => failure.id).join(', ')}`;
      throw new AggregateError(
        failures.map((failure) => failure.error),
        message,
      );
    }
  }

  isCached(id: string): boolean {
    return this.cache.has(id);
  }

  private async loadInternal(entry: AssetEntry): Promise<DecodedAsset<M, T, A>> {
    const url = this.urlFor(entry);
    const buffer = await this.options.fetchBytes(url);
    if (buffer.byteLength !== entry.bytes) {
      throw new Error(`size mismatch for ${entry.id}: expected ${entry.bytes}, got ${buffer.byteLength}`);
    }

    if (entry.kind === 'model') {
      return this.options.decoders.model(buffer, entry);
    }
    if (entry.kind === 'texture') {
      return this.options.decoders.texture(buffer, entry);
    }
    return this.options.decoders.audio(buffer, entry);
  }

  private urlFor(entry: AssetEntry): string {
    const base = this.options.baseUrl.endsWith('/')
      ? this.options.baseUrl
      : `${this.options.baseUrl}/`;
    return `${base}${entry.path}`;
  }
}
