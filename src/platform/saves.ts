import type { WorldState } from '../sim/world';
import { canonicalJson, fnv1aHex } from '../sim/world';
import type { KvStore } from './kv';
import { StorageFullError } from './kv';

export interface SaveMeta {
  gameVersion: string;
  savedAtIso: string;
}

export type DecodeFailureReason = 'corrupt' | 'checksum' | 'incompatible' | 'not-a-save';

export type DecodeSaveResult =
  | { ok: true; world: WorldState; meta: SaveMeta }
  | { ok: false; reason: DecodeFailureReason };

export interface LoadedSave {
  world: WorldState;
  meta: SaveMeta;
}

export const CURRENT_SAVE_SCHEMA = 1;
export const migrations: Record<number, (payload: unknown) => unknown> = {};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isWorldState(value: unknown): value is WorldState {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.tick === 'number' &&
    Number.isInteger(value.tick) &&
    typeof value.seed === 'number' &&
    Number.isFinite(value.seed) &&
    typeof value.rngState === 'number' &&
    Number.isFinite(value.rngState) &&
    typeof value.counter === 'number' &&
    Number.isFinite(value.counter)
  );
}

export function encodeSave(world: WorldState, meta: SaveMeta): string {
  const payload: WorldState = {
    tick: world.tick,
    seed: world.seed,
    rngState: world.rngState,
    counter: world.counter,
  };
  const checksum = fnv1aHex(canonicalJson(payload));
  return JSON.stringify({
    format: 'tcsave',
    schema: CURRENT_SAVE_SCHEMA,
    gameVersion: meta.gameVersion,
    savedAtIso: meta.savedAtIso,
    checksum,
    payload,
  });
}

export function decodeSave(text: string): DecodeSaveResult {
  try {
    const parsed: unknown = JSON.parse(text);
    if (!isRecord(parsed)) {
      return { ok: false, reason: 'not-a-save' };
    }
    if (parsed.format !== 'tcsave') {
      return { ok: false, reason: 'not-a-save' };
    }

    const schema = parsed.schema;
    if (typeof schema !== 'number' || !Number.isInteger(schema)) {
      return { ok: false, reason: 'corrupt' };
    }
    if (schema > CURRENT_SAVE_SCHEMA) {
      return { ok: false, reason: 'incompatible' };
    }

    let payload: unknown = parsed.payload;
    let version = schema;
    while (version < CURRENT_SAVE_SCHEMA) {
      const migrate = migrations[version];
      if (!migrate) {
        return { ok: false, reason: 'incompatible' };
      }
      payload = migrate(payload);
      version += 1;
    }

    const checksum = parsed.checksum;
    if (typeof checksum !== 'string') {
      return { ok: false, reason: 'corrupt' };
    }
    if (fnv1aHex(canonicalJson(payload)) !== checksum) {
      return { ok: false, reason: 'checksum' };
    }

    if (!isWorldState(payload)) {
      return { ok: false, reason: 'corrupt' };
    }

    const gameVersion = parsed.gameVersion;
    const savedAtIso = parsed.savedAtIso;
    if (typeof gameVersion !== 'string' || typeof savedAtIso !== 'string') {
      return { ok: false, reason: 'corrupt' };
    }

    return {
      ok: true,
      world: payload,
      meta: { gameVersion, savedAtIso },
    };
  } catch {
    return { ok: false, reason: 'corrupt' };
  }
}

export interface SaveManagerOptions {
  maxBytes?: number;
  gameVersion?: string;
  now?: () => Date;
}

const encoder = new TextEncoder();

function byteLength(text: string): number {
  return encoder.encode(text).byteLength;
}

export class SaveManager {
  private readonly kv: KvStore;
  private readonly maxBytes: number;
  private readonly gameVersion: string;
  private readonly now: () => Date;
  private readonly bytes = new Map<string, number>();
  private totalBytes = 0;
  private loaded = false;
  private autoCursor = 0;
  private lastAutoSlot: string | null = null;

  constructor(kv: KvStore, options: SaveManagerOptions = {}) {
    this.kv = kv;
    this.maxBytes = options.maxBytes ?? 5 * 1024 * 1024;
    this.gameVersion = options.gameVersion ?? '0.1.0';
    this.now = options.now ?? (() => new Date());
  }

  async save(slot: string, world: WorldState): Promise<void> {
    await this.ensureLoaded();
    const text = encodeSave(world, {
      gameVersion: this.gameVersion,
      savedAtIso: this.now().toISOString(),
    });
    const key = this.key(slot);
    const size = byteLength(text);
    const previous = this.bytes.get(key) ?? 0;

    if (this.totalBytes - previous + size > this.maxBytes) {
      throw new StorageFullError();
    }

    await this.kv.set(key, text);
    this.bytes.set(key, size);
    this.totalBytes = this.totalBytes - previous + size;
  }

  async load(slot: string): Promise<LoadedSave | null> {
    const text = await this.kv.get(this.key(slot));
    if (text === null) {
      return null;
    }
    const decoded = decodeSave(text);
    if (!decoded.ok) {
      throw new Error(`Cannot load save "${slot}": ${decoded.reason}`);
    }
    return { world: decoded.world, meta: decoded.meta };
  }

  async listSlots(): Promise<string[]> {
    await this.ensureLoaded();
    return [...this.bytes.keys()]
      .filter((key) => key.startsWith('save:'))
      .map((key) => key.slice('save:'.length))
      .sort();
  }

  async autosave(world: WorldState): Promise<void> {
    await this.ensureLoaded();
    const slot = `auto-${this.autoCursor % 3}`;
    await this.save(slot, world);
    this.lastAutoSlot = slot;
    this.autoCursor = (this.autoCursor + 1) % 3;
  }

  async latestAutosave(): Promise<LoadedSave | null> {
    await this.ensureLoaded();
    const slots = (await this.listSlots()).filter((slot) => slot.startsWith('auto-'));
    const first = slots[0];
    if (!first) {
      return null;
    }

    if (this.lastAutoSlot && slots.includes(this.lastAutoSlot)) {
      return this.load(this.lastAutoSlot);
    }

    let latestSlot = first;
    let latestIso = '';
    for (const slot of slots) {
      const loaded = await this.load(slot);
      if (loaded && loaded.meta.savedAtIso > latestIso) {
        latestIso = loaded.meta.savedAtIso;
        latestSlot = slot;
      }
    }
    return this.load(latestSlot);
  }

  private key(slot: string): string {
    return `save:${slot}`;
  }

  private async ensureLoaded(): Promise<void> {
    if (this.loaded) {
      return;
    }
    this.loaded = true;
    this.totalBytes = 0;
    this.bytes.clear();
    const keys = await this.kv.keys();
    for (const key of keys) {
      const text = await this.kv.get(key);
      if (text !== null) {
        const size = byteLength(text);
        this.bytes.set(key, size);
        this.totalBytes += size;
      }
    }
  }
}
