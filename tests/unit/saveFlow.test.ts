// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { GameServices, type GameServicesHost } from '../../src/game/services';
import { MemoryKvStore } from '../../src/platform/kv';
import { SettingsStore } from '../../src/platform/settings';
import { encodeSave } from '../../src/platform/saves';
import { createWorld, hashWorld } from '../../src/sim/world';
import type { WorldState } from '../../src/sim/types';

interface Harness {
  services: GameServices;
  kv: MemoryKvStore;
  setWorld(world: WorldState): void;
  loaded: WorldState[];
  /** The skirmish setup record handed over with each load. */
  setups: unknown[];
  setSetup(setup: unknown): void;
}

const open: GameServices[] = [];

function harness(kv = new MemoryKvStore()): Harness {
  let world = createWorld(1);
  let setup: unknown = undefined;
  const loaded: WorldState[] = [];
  const setups: unknown[] = [];
  const host: GameServicesHost = {
    getWorld: () => world,
    loadWorld: (next, _start, skirmish) => {
      world = next;
      loaded.push(next);
      setups.push(skirmish);
    },
    matchSetup: () => setup,
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
    setups,
    setSetup: (next) => {
      setup = next;
    },
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

  it('[SAVE-09] a loaded autosave from before match ids is cleared when its match ends', async () => {
    const h = harness();
    await h.services.writeRawSave('auto-0', encodeSave(createWorld(31), { gameVersion: 't', savedAtIso: '2026-01-01T00:00:00Z' }));
    expect((await h.services.resumeLastGame()).status).toBe('ok');
    await h.services.finishMatch();
    expect(await h.services.latestAutosave()).toBeNull();
  });

  it('[SAVE-09] an old autosave resumed, saved & quit and resumed again is cleared when the match ends', async () => {
    const h = harness();
    await h.services.writeRawSave('auto-0', encodeSave(createWorld(33), { gameVersion: 't', savedAtIso: '2026-01-01T00:00:00Z' }));
    expect((await h.services.resumeLastGame()).status).toBe('ok');
    await h.services.quitSave();
    expect((await h.services.resumeLastGame()).status).toBe('ok');
    await h.services.finishMatch();
    expect(await h.services.latestAutosave()).toBeNull();
  });

  it('[SAVE-09] an autosave still being written when the match ends is cleared too', async () => {
    const h = harness();
    h.services.beginMatch();
    h.setWorld(createWorld(32));
    const writing = h.services.requestAutosave();
    await h.services.finishMatch();
    await writing;
    expect(await h.services.latestAutosave()).toBeNull();
  });

  it('[SAVE-09] quit without saving and restart drop the match from Continue, older saves stay', async () => {
    const h = harness();
    h.services.beginMatch();
    h.setWorld(createWorld(41));
    await h.services.quitSave();
    // A second match autosaves, then is abandoned (Quit without saving, or Restart).
    h.services.beginMatch();
    h.setWorld(createWorld(42));
    await h.services.requestAutosave();
    await h.services.discardMatch();
    expect((await h.services.latestAutosave())?.title).toBe('match 41');
    // Nothing more of the abandoned match is written while it is being dropped.
    await h.services.requestAutosave();
    expect((await h.services.latestAutosave())?.title).toBe('match 41');
  });

  it('[SAVE-11] a skirmish save carries its setup, handed back on load', async () => {
    const h = harness();
    h.services.beginMatch();
    const setup = { config: { faction: 'alien', opponents: [{ faction: 'human', difficulty: 'hard' }], resources: 'low', force: 'padOnly', mapId: 'm', fog: false }, mapId: 'm', fog: false, ai: true };
    h.setSetup(setup);
    h.setWorld(createWorld(51));
    await h.services.saveToSlot('manual-1');
    expect((await h.services.loadFromSlot('manual-1')).status).toBe('ok');
    expect(h.setups.at(-1)).toEqual(setup);
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
    const imported = await h.services.importSave(text);
    expect(imported.status).toBe('ok');
    // It says where the save went when no manual slot was free.
    expect(imported.message).toMatch(/autosave.*Continue/);
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
