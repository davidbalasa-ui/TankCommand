import { describe, expect, it } from 'vitest';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { MemoryKvStore, StorageFullError, WebKvStore } from '../../src/platform/kv';
import { SaveManager, decodeSave, encodeSave } from '../../src/platform/saves';

describe('save envelopes', () => {
  it('[SAVE-01] save after 500 steps and continue 500 more matches an uninterrupted run', async () => {
    let uninterrupted = createWorld(321);
    for (let i = 0; i < 1000; i += 1) {
      uninterrupted = step(uninterrupted, []);
    }

    let firstHalf = createWorld(321);
    for (let i = 0; i < 500; i += 1) {
      firstHalf = step(firstHalf, []);
    }

    const kv = new MemoryKvStore();
    const manager = new SaveManager(kv);
    await manager.save('slot-a', firstHalf);
    const loaded = await manager.load('slot-a');
    expect(loaded).not.toBeNull();
    let resumed = loaded?.world ?? createWorld(1);
    for (let i = 0; i < 500; i += 1) {
      resumed = step(resumed, []);
    }

    expect(hashWorld(resumed)).toBe(hashWorld(uninterrupted));
  });

  it('[SAVE-02] decodeSave returns correct reasons for malformed input and never throws', () => {
    const valid = encodeSave(createWorld(1), {
      gameVersion: 'test',
      savedAtIso: '2026-10-27T00:00:00.000Z',
    });

    expect(decodeSave('random bytes')).toEqual({ ok: false, reason: 'corrupt' });
    expect(decodeSave(valid.slice(0, valid.length - 10))).toEqual({
      ok: false,
      reason: 'corrupt',
    });
    expect(decodeSave('{}')).toEqual({ ok: false, reason: 'not-a-save' });

    const schema999 = JSON.parse(valid) as { schema: number };
    schema999.schema = 999;
    expect(decodeSave(JSON.stringify(schema999))).toEqual({
      ok: false,
      reason: 'incompatible',
    });

    const flipped = JSON.parse(valid) as { payload: { counter: number } };
    flipped.payload.counter += 1;
    expect(decodeSave(JSON.stringify(flipped))).toEqual({ ok: false, reason: 'checksum' });

    for (let i = 0; i < 1000; i += 1) {
      const text = `${Math.random().toString(36).slice(2)}-${i}`;
      expect(() => decodeSave(text)).not.toThrow();
      const result = decodeSave(text);
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(['corrupt', 'checksum', 'incompatible', 'not-a-save']).toContain(result.reason);
      }
    }
  });

  it('[SAVE-03] autosave rotation keeps exactly three slots and latestAutosave is the fifth', async () => {
    const kv = new MemoryKvStore();
    let clock = 0;
    const manager = new SaveManager(kv, {
      now: () => new Date(1700000000000 + clock++ * 1000),
    });
    const base = createWorld(17);

    for (let i = 0; i < 5; i += 1) {
      await manager.autosave({ ...base, counter: i });
    }

    const slots = await manager.listSlots();
    expect(slots.filter((slot) => slot.startsWith('auto-')).sort()).toEqual([
      'auto-0',
      'auto-1',
      'auto-2',
    ]);
    const latest = await manager.latestAutosave();
    expect(latest?.world.counter).toBe(4);
  });

  it('[SAVE-04] exceeding maxBytes rejects and leaves previous saves intact', async () => {
    const world = createWorld(44);
    const now = new Date('2026-10-27T12:00:00.000Z');
    const sample = encodeSave(world, {
      gameVersion: '0.1.0',
      savedAtIso: now.toISOString(),
    });
    const size = new TextEncoder().encode(sample).byteLength;
    const kv = new MemoryKvStore();
    const manager = new SaveManager(kv, {
      maxBytes: size + 5,
      gameVersion: '0.1.0',
      now: () => now,
    });

    await manager.save('a', world);
    await expect(manager.save('b', world)).rejects.toBeInstanceOf(StorageFullError);
    const loaded = await manager.load('a');
    expect(loaded?.world).toEqual(world);
  });

  it('[SAVE-05] WebKvStore maps quota failures to StorageFullError', async () => {
    const storage = {
      getItem: () => null,
      setItem: () => {
        const error = new Error('quota');
        error.name = 'QuotaExceededError';
        throw error;
      },
      removeItem: () => undefined,
      key: () => null,
      length: 0,
      clear: () => undefined,
    } as unknown as Storage;

    const store = new WebKvStore(storage);
    await expect(store.set('a', 'b')).rejects.toBeInstanceOf(StorageFullError);
  });
});
