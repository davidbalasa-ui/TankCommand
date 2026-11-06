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

function toError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }
  return new Error(String(error));
}

export class MemoryKvStore implements KvStore {
  private readonly data = new Map<string, string>();

  get(key: string): Promise<string | null> {
    return Promise.resolve(this.data.get(key) ?? null);
  }

  set(key: string, value: string): Promise<void> {
    this.data.set(key, value);
    return Promise.resolve();
  }

  remove(key: string): Promise<void> {
    this.data.delete(key);
    return Promise.resolve();
  }

  keys(): Promise<string[]> {
    return Promise.resolve([...this.data.keys()].sort());
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

  get(key: string): Promise<string | null> {
    try {
      return Promise.resolve(this.storage.getItem(key));
    } catch (error) {
      return Promise.reject(toError(error));
    }
  }

  set(key: string, value: string): Promise<void> {
    try {
      this.storage.setItem(key, value);
      return Promise.resolve();
    } catch (error) {
      if (isQuotaError(error)) {
        return Promise.reject(new StorageFullError());
      }
      return Promise.reject(toError(error));
    }
  }

  remove(key: string): Promise<void> {
    try {
      this.storage.removeItem(key);
      return Promise.resolve();
    } catch (error) {
      return Promise.reject(toError(error));
    }
  }

  keys(): Promise<string[]> {
    try {
      const result: string[] = [];
      for (let i = 0; i < this.storage.length; i += 1) {
        const key = this.storage.key(i);
        if (key !== null) {
          result.push(key);
        }
      }
      return Promise.resolve(result);
    } catch (error) {
      return Promise.reject(toError(error));
    }
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
