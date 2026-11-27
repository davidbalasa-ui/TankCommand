import { describe, expect, it } from 'vitest';
import { CloudProgressSync, type PlayGamesBackend, type PlayGamesStatus } from '../../src/platform/cloudProgress';
import { emptyProgress, mergeProgress, recordWin, type CampaignProgress } from '../../src/platform/progress';

function fakeBackend(options: { configured?: boolean; signedIn?: boolean; cloud?: string | null; failRead?: boolean } = {}) {
  const state = {
    configured: options.configured ?? true,
    signedIn: options.signedIn ?? true,
    cloud: options.cloud ?? null,
    writes: 0,
  };
  const status = (): PlayGamesStatus => ({ configured: state.configured, signedIn: state.signedIn, playerName: 'Ace' });
  const backend: PlayGamesBackend = {
    status: () => Promise.resolve(status()),
    signIn: () => {
      state.signedIn = true;
      return Promise.resolve(status());
    },
    read: () =>
      options.failRead
        ? Promise.reject(new Error('offline'))
        : Promise.resolve({ exists: state.cloud !== null, data: state.cloud ?? '' }),
    write: ({ data }) => {
      state.cloud = data;
      state.writes += 1;
      return Promise.resolve();
    },
  };
  return { backend, state };
}

const won = (ids: string[], base: CampaignProgress = emptyProgress()): CampaignProgress =>
  ids.reduce((progress, id) => recordWin(progress, id, 100), base);

describe('mergeProgress', () => {
  it('keeps every mission won on either side, with the best record of each', () => {
    const phone = recordWin(won(['h1', 'h2']), 'h2', 50, 'hard');
    const cloud = { ...won(['h1', 'a1']), difficulty: 'easy' as const };
    const merged = mergeProgress(phone, cloud);
    expect(Object.keys(merged.completed).sort()).toEqual(['a1', 'h1', 'h2']);
    expect(merged.completed['h2']).toEqual({ bestTimeSec: 50, wins: 2, bestDifficulty: 'hard' });
    expect(merged.difficulty).toBe('normal');
  });
});

describe('CloudProgressSync', () => {
  it('is unavailable on the web', async () => {
    const sync = new CloudProgressSync({ isNative: false, backend: fakeBackend().backend });
    expect(sync.available()).toBe(false);
    expect(await sync.start(() => won(['h1']))).toBeNull();
  });

  it('is unavailable when the build has no Play Games id', async () => {
    const sync = new CloudProgressSync({ isNative: true, backend: fakeBackend({ configured: false }).backend });
    await sync.start(() => emptyProgress());
    expect(sync.available()).toBe(false);
  });

  it('brings cloud progress to a fresh phone, including the difficulty', async () => {
    const cloud = { ...won(['h1', 'h2', 'h3']), difficulty: 'hard' as const };
    const { backend, state } = fakeBackend({ cloud: JSON.stringify(cloud) });
    const sync = new CloudProgressSync({ isNative: true, backend });
    const merged = await sync.start(() => emptyProgress());
    expect(merged && Object.keys(merged.completed).length).toBe(3);
    expect(merged?.difficulty).toBe('hard');
    expect(state.writes).toBe(0);
    expect(sync.state()).toBe('synced');
  });

  it('uploads device progress the cloud lacks, and never loses cloud progress', async () => {
    const { backend, state } = fakeBackend({ cloud: JSON.stringify(won(['a1'])) });
    const sync = new CloudProgressSync({ isNative: true, backend });
    const merged = await sync.start(() => won(['h1']));
    expect(merged && Object.keys(merged.completed).sort()).toEqual(['a1', 'h1']);
    expect(state.writes).toBe(1);
    expect(Object.keys((JSON.parse(state.cloud ?? '{}') as CampaignProgress).completed).sort()).toEqual(['a1', 'h1']);
  });

  it('waits for the player to sign in, then syncs', async () => {
    const { backend, state } = fakeBackend({ signedIn: false });
    const sync = new CloudProgressSync({ isNative: true, backend });
    await sync.start(() => won(['h1']));
    expect(sync.state()).toBe('signedOut');
    expect(state.writes).toBe(0);
    await sync.signIn(() => won(['h1']));
    expect(sync.state()).toBe('synced');
    expect(sync.playerName()).toBe('Ace');
    expect(state.writes).toBe(1);
  });

  it('reports offline and keeps playing when the cloud cannot be reached', async () => {
    const sync = new CloudProgressSync({ isNative: true, backend: fakeBackend({ failRead: true }).backend });
    expect(await sync.start(() => won(['h1']))).toBeNull();
    expect(sync.state()).toBe('offline');
  });
});
