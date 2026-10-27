import { Capacitor } from '@capacitor/core';
import { Directory, Encoding, Filesystem } from '@capacitor/filesystem';
import { Preferences } from '@capacitor/preferences';

export interface KvStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
  keys(): Promise<string[]>;
}

export class StorageFullError extends Error {
  constructor(message = 'Storage is full') {
    super(message);
    this.name = 'StorageFullError';
  }
}

export class MemoryKvStore implements KvStore {
  private readonly data = new Map<string, string>();

  async get(key: string): Promise<string | null> {
    return this.data.get(key) ?? null;
  }

  async set(key: string, value: string): Promise<void> {
    this.data.set(key, value);
  }

  async remove(key: string): Promise<void> {
    this.data.delete(key);
  }

  async keys(): Promise<string[]> {
    return [...this.data.keys()].sort();
  }
}

function isQuotaError(error: unknown): boolean {
  if (error instanceof DOMException && (error.name === 'QuotaExceededError' || error.code === 22)) {
    return true;
  }
  if (error instanceof Error) {
    return (
      error.name === 'QuotaExceededError' || error.message.toLowerCase().includes('quota')
    );
  }
  return false;
}

export class WebKvStore implements KvStore {
  private readonly storage: Storage;

  constructor(storage?: Storage) {
    this.storage = storage ?? globalThis.localStorage;
  }

  async get(key: string): Promise<string | null> {
    return this.storage.getItem(key);
  }

  async set(key: string, value: string): Promise<void> {
    try {
      this.storage.setItem(key, value);
    } catch (error) {
      if (isQuotaError(error)) {
        throw new StorageFullError();
      }
      throw error;
    }
  }

  async remove(key: string): Promise<void> {
    this.storage.removeItem(key);
  }

  async keys(): Promise<string[]> {
    const result: string[] = [];
    for (let i = 0; i < this.storage.length; i += 1) {
      const key = this.storage.key(i);
      if (key !== null) {
        result.push(key);
      }
    }
    return result;
  }
}

const SETTINGS_PREFIX = 'setting.';

export class NativeKvStore implements KvStore {
  async get(key: string): Promise<string | null> {
    if (key.startsWith(SETTINGS_PREFIX)) {
      const result = await Preferences.get({ key });
      return result.value;
    }
    try {
      const result = await Filesystem.readFile({
        path: `saves/${key}.json`,
        directory: Directory.Data,
        encoding: Encoding.UTF8,
      });
      return typeof result.data === 'string' ? result.data : null;
    } catch {
      return null;
    }
  }

  async set(key: string, value: string): Promise<void> {
    if (key.startsWith(SETTINGS_PREFIX)) {
      await Preferences.set({ key, value });
      return;
    }
    await Filesystem.writeFile({
      path: `saves/${key}.json`,
      directory: Directory.Data,
      data: value,
      encoding: Encoding.UTF8,
    });
  }

  async remove(key: string): Promise<void> {
    if (key.startsWith(SETTINGS_PREFIX)) {
      await Preferences.remove({ key });
      return;
    }
    try {
      await Filesystem.deleteFile({
        path: `saves/${key}.json`,
        directory: Directory.Data,
      });
    } catch {
      return;
    }
  }

  async keys(): Promise<string[]> {
    if (!Capacitor.isNativePlatform()) {
      return [];
    }

    const result: string[] = [];
    try {
      const listing = await Filesystem.readdir({
        path: 'saves',
        directory: Directory.Data,
      });
      const entries = listing.files as unknown as Array<string | { name: string }>;
      for (const entry of entries) {
        const name = typeof entry === 'string' ? entry : entry.name;
        if (name.endsWith('.json')) {
          result.push(name.slice(0, -5));
        }
      }
    } catch {
      // The saves directory may not exist yet.
    }

    const preferences = await Preferences.keys();
    result.push(...preferences.keys);
    return result;
  }
}

export function createKvStore(): KvStore {
  return Capacitor.isNativePlatform() ? new NativeKvStore() : new WebKvStore();
}
