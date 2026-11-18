// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { GameServices, type GameServicesHost } from '../../src/game/services';
import { MemoryKvStore } from '../../src/platform/kv';
import { SettingsStore } from '../../src/platform/settings';
import { createWorld, hashWorld } from '../../src/sim/world';
import type { WorldState } from '../../src/sim/types';

interface Harness {
  services: GameServices;
  kv: MemoryKvStore;
  setWorld(world: WorldState): void;
  loaded: WorldState[];
}

const open: GameServices[] = [];

function harness(kv = new MemoryKvStore()): Harness {
  let world = createWorld(1);
  const loaded: WorldState[] = [];
  const host: GameServicesHost = {
    getWorld: () => world,
    loadWorld: (next) => {
      world = next;
      loaded.push(next);
    },
    currentScreen: () => 'inGame',
    inMatch: () => true,
    setCameraTarget: () => undefined,
    setSimSpeed: () => undefined,
    getSimSpeed: () => 1,
    freezeReport: () => null,
    applySettings: () => undefined,
    describeWorld: (w) => `match ${w.seed}`,
  };
  const services = new GameServices(host, { kv, settings: new SettingsStore(null), mount: document.body });
  open.push(services);
  return {
    services,
    kv,
    setWorld: (next) => {
      world = next;
    },
    loaded,
  };
}

afterEach(() => {
  for (const services of open.splice(0)) {
    services.dispose();
  }
});

describe('[SAVE-09] continue, quit-save and save slots', () => {
  it('[SAVE-09] Save & quit goes to the autosave rotation, never to a manual slot', async () => {
    const h = harness();
    h.services.beginMatch();
    h.setWorld(createWorld(7));
    expect((await h.services.quitSave()).status).toBe('ok');
    const slots = await h.services.listSaveSlots();
    expect(slots.every((slot) => slot.status === 'missing')).toBe(true);
    const latest = await h.services.latestAutosave();
    expect(latest?.slot.startsWith('auto-')).toBe(true);
    expect(latest?.title).toBe('match 7');
  });

  it('[SAVE-09] Continue skips a match that ended and keeps an older unfinished one', async () => {
    const h = harness();
    // Match A is saved and left.
    h.services.beginMatch();
    h.setWorld(createWorld(11));
    await h.services.quitSave();
    // Match B autosaves, then ends: Continue goes back to A.
    h.services.beginMatch();
    h.setWorld(createWorld(22));
    await h.services.requestAutosave();
    expect((await h.services.latestAutosave())?.title).toBe('match 22');
    await h.services.finishMatch();
    expect((await h.services.latestAutosave())?.title).toBe('match 11');

    // Resuming A and finishing it leaves nothing to continue.
    const resumed = await h.services.resumeLastGame();
    expect(resumed.status).toBe('ok');
    await h.services.requestAutosave();
    await h.services.finishMatch();
    expect(await h.services.latestAutosave()).toBeNull();
  });

  it('[SAVE-09] an autosave holding a finished result is never offered', async () => {
    const h = harness();
    h.services.beginMatch();
    const ended = createWorld(5);
    ended.result = { winner: 1 };
    h.setWorld(ended);
    await h.services.requestAutosave();
    expect(await h.services.latestAutosave()).toBeNull();
  });

  it('[SAVE-06] slots list what was played, delete removes one, import never overwrites', async () => {
    const h = harness();
    h.services.beginMatch();
    h.setWorld(createWorld(3));
    expect((await h.services.saveToSlot('manual-2')).message).toBe('Saved to slot 2.');
    let slots = await h.services.listSaveSlots();
    const second = slots.find((slot) => slot.slot === 'manual-2');
    expect(second).toMatchObject({ status: 'ok', title: 'match 3', playSeconds: 0 });

    expect((await h.services.deleteSlot('manual-2')).status).toBe('ok');
    slots = await h.services.listSaveSlots();
    expect(slots.every((slot) => slot.status === 'missing')).toBe(true);

    // Fill every manual slot, then import: the manual saves stay as they were.
    for (let index = 1; index <= 5; index += 1) {
      h.setWorld(createWorld(100 + index));
      await h.services.saveToSlot(`manual-${index}`);
    }
    const before = await Promise.all([1, 2, 3, 4, 5].map((index) => h.kv.get(`save:manual-${index}`)));
    h.setWorld(createWorld(999));
    const text = await h.services.exportSave();
    expect((await h.services.importSave(text)).status).toBe('ok');
    const after = await Promise.all([1, 2, 3, 4, 5].map((index) => h.kv.get(`save:manual-${index}`)));
    expect(after).toEqual(before);
    expect((await h.services.latestAutosave())?.title).toBe('match 999');
  });

  it('[SAVE-06] loading a slot from the title starts the saved match', async () => {
    const kv = new MemoryKvStore();
    const first = harness(kv);
    first.services.beginMatch();
    const world = createWorld(42);
    first.setWorld(world);
    await first.services.saveToSlot('manual-1');

    const second = harness(kv);
    const result = await second.services.loadFromSlot('manual-1');
    expect(result.status).toBe('ok');
    expect(second.loaded).toHaveLength(1);
    expect(hashWorld(second.loaded[0] as WorldState)).toBe(hashWorld(world));
  });
});
