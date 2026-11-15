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
    expect(loaded.status).toBe('ok');
    let resumed = loaded.status === 'ok' ? loaded.save.world : createWorld(1);
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
    expect(loaded.status).toBe('ok');
    if (loaded.status === 'ok') {
      expect(loaded.save.world).toEqual(world);
    }
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

  it('[SAVE-06] five manual slots each restore an identical world hash', async () => {
    const kv = new MemoryKvStore();
    const manager = new SaveManager(kv);
    let world = createWorld(88);
    for (let i = 0; i < 50; i += 1) {
      world = step(world, []);
    }
    const savedHash = hashWorld(world);
    for (let index = 1; index <= 5; index += 1) {
      await manager.save(`manual-${index}`, world);
    }
    for (let index = 1; index <= 5; index += 1) {
      const loaded = await manager.load(`manual-${index}`);
      expect(loaded.status).toBe('ok');
      if (loaded.status === 'ok') {
        expect(hashWorld(loaded.save.world)).toBe(savedHash);
      }
    }
  });

  it('[SAVE-07] autosave cursor survives relaunch and never overwrites the newest autosave first', async () => {
    const kv = new MemoryKvStore();
    let clock = 0;
    const first = new SaveManager(kv, {
      now: () => new Date(1700000000000 + clock++ * 1000),
    });
    const base = createWorld(51);
    await first.autosave({ ...base, counter: 0 });
    await first.autosave({ ...base, counter: 1 });

    const relaunched = new SaveManager(kv, {
      now: () => new Date(1700000000000 + clock++ * 1000),
    });
    await relaunched.autosave({ ...base, counter: 2 });

    const auto0 = await relaunched.load('auto-0');
    const auto1 = await relaunched.load('auto-1');
    const auto2 = await relaunched.load('auto-2');
    expect(auto0.status).toBe('ok');
    expect(auto1.status).toBe('ok');
    expect(auto2.status).toBe('ok');
    if (auto0.status === 'ok' && auto1.status === 'ok' && auto2.status === 'ok') {
      expect(auto0.save.world.counter).toBe(0);
      expect(auto1.save.world.counter).toBe(1);
      expect(auto2.save.world.counter).toBe(2);
    }
  });

  it('[SAVE-08] load returns typed results for missing, corrupt and incompatible saves', async () => {
    const kv = new MemoryKvStore();
    const manager = new SaveManager(kv);
    expect(await manager.load('manual-1')).toEqual({ status: 'missing' });

    await kv.set('save:manual-1', 'not a save');
    expect(await manager.load('manual-1')).toEqual({ status: 'corrupt' });

    const valid = encodeSave(createWorld(9), {
      gameVersion: '0.1.0',
      savedAtIso: '2026-11-01T00:00:00.000Z',
    });
    const parsed = JSON.parse(valid) as { schema: number };
    parsed.schema = 999;
    await kv.set('save:manual-1', JSON.stringify(parsed));
    expect(await manager.load('manual-1')).toEqual({ status: 'incompatible' });
  });

  it('[SAVE-10] export/import round-trips a save and storage full is reported', async () => {
    const kv = new MemoryKvStore();
    const manager = new SaveManager(kv);
    let world = createWorld(12);
    for (let i = 0; i < 25; i += 1) {
      world = step(world, []);
    }
    await manager.save('manual-1', world);
    const exported = await manager.exportSlot('manual-1');
    expect(exported).not.toBeNull();
    if (!exported) {
      return;
    }
    const imported = await manager.importText('manual-2', exported);
    expect(imported.status).toBe('ok');
    const loaded = await manager.load('manual-2');
    expect(loaded.status).toBe('ok');
    if (loaded.status === 'ok') {
      expect(hashWorld(loaded.save.world)).toBe(hashWorld(world));
    }

    const tiny = new SaveManager(kv, { maxBytes: 10 });
    await expect(tiny.save('manual-3', world)).rejects.toBeInstanceOf(StorageFullError);
  });
});
