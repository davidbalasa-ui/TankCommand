import { describe, expect, it } from 'vitest';
import { FREE_CONTENT, isFreeContent, needsFullGame } from '../../src/data/fullGame';
import { MISSIONS, missionsOf } from '../../src/data/missions';
import { FULL_GAME_PRODUCT_ID, PurchaseService, type FlagStore, type StoreBackend } from '../../src/platform/purchases';
import rawMaps from '../../src/data/maps.placeholder.json';

class MemoryFlag implements FlagStore {
  value = false;
  writes: boolean[] = [];
  get(): Promise<boolean> {
    return Promise.resolve(this.value);
  }
  set(value: boolean): Promise<void> {
    this.value = value;
    this.writes.push(value);
    return Promise.resolve();
  }
}

class FakeStore implements StoreBackend {
  ownedValue = false;
  ownedError: Error | null = null;
  buyOutcome: 'purchased' | 'pending' | Error = 'purchased';
  priceValue: string | null = '€4.99';
  calls: string[] = [];
  price(): Promise<string | null> {
    this.calls.push('price');
    return Promise.resolve(this.priceValue);
  }
  buy(): Promise<'purchased' | 'pending'> {
    this.calls.push('buy');
    return this.buyOutcome instanceof Error ? Promise.reject(this.buyOutcome) : Promise.resolve(this.buyOutcome);
  }
  owned(): Promise<boolean> {
    this.calls.push('owned');
    return this.ownedError ? Promise.reject(this.ownedError) : Promise.resolve(this.ownedValue);
  }
}

const flush = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 0));

const skirmishMaps = (rawMaps as Array<{ id: string; name: string; campaignOnly?: boolean }>).filter((map) => !map.campaignOnly);

describe('[IAP-01] free and full-game content', () => {
  it('[IAP-01] all training, the first five missions of each campaign and two skirmish maps are free', () => {
    expect(FREE_CONTENT.freeMissionsPerCampaign).toBe(5);
    for (const mission of missionsOf('training')) {
      expect(isFreeContent({ kind: 'mission', campaign: 'training', order: mission.order })).toBe(true);
    }
    for (const campaign of ['human', 'alien'] as const) {
      const missions = missionsOf(campaign);
      expect(missions.length).toBeGreaterThan(5);
      const free = missions.filter((mission) => isFreeContent({ kind: 'mission', campaign, order: mission.order }));
      expect(free.map((mission) => mission.order)).toEqual([1, 2, 3, 4, 5]);
    }
    const freeMaps = skirmishMaps.filter((map) => isFreeContent({ kind: 'skirmishMap', mapId: map.id }));
    expect(freeMaps.map((map) => map.name).sort()).toEqual(['Cinder Basin', 'Lakeside Crossing']);
    expect(skirmishMaps.length).toBeGreaterThan(freeMaps.length);
  });

  it('[IAP-01] every free map id exists, so a renamed map cannot silently lock everything', () => {
    for (const id of FREE_CONTENT.freeSkirmishMaps) {
      expect(skirmishMaps.some((map) => map.id === id)).toBe(true);
    }
  });

  it('[IAP-01] the unlock opens everything and the rule is one table', () => {
    const locked = MISSIONS.filter((mission) => needsFullGame({ kind: 'mission', campaign: mission.campaign, order: mission.order }, false));
    expect(locked.length).toBe(MISSIONS.length - missionsOf('training').length - 10);
    expect(locked.every((mission) => mission.campaign !== 'training' && mission.order > 5)).toBe(true);
    expect(MISSIONS.some((mission) => needsFullGame({ kind: 'mission', campaign: mission.campaign, order: mission.order }, true))).toBe(false);
    expect(skirmishMaps.some((map) => needsFullGame({ kind: 'skirmishMap', mapId: map.id }, true))).toBe(false);
    // Changing the table changes the split.
    const wider = { ...FREE_CONTENT, freeMissionsPerCampaign: 7 };
    expect(isFreeContent({ kind: 'mission', campaign: 'human', order: 7 }, wider)).toBe(true);
    expect(isFreeContent({ kind: 'mission', campaign: 'human', order: 7 })).toBe(false);
  });
});

describe('[IAP-02] full game purchase service', () => {
  it('[IAP-02] the web build is unlocked and never calls the store', async () => {
    const store = new FakeStore();
    const service = new PurchaseService({ isNative: false, backend: store, flag: new MemoryFlag() });
    await service.init();
    expect(service.isUnlocked()).toBe(true);
    expect(service.canPurchase()).toBe(false);
    expect(await service.price()).toBeNull();
    expect((await service.buy()).status).toBe('unavailable');
    expect(store.calls).toEqual([]);
  });

  it('[IAP-02] the test override can lock the web build', async () => {
    const service = new PurchaseService({ isNative: false, backend: new FakeStore(), flag: new MemoryFlag() });
    let changes = 0;
    service.subscribe(() => {
      changes += 1;
    });
    service.setTestOverride(false);
    expect(service.isUnlocked()).toBe(false);
    expect((await service.restore()).status).toBe('unavailable');
    service.setTestOverride(null);
    expect(service.isUnlocked()).toBe(true);
    expect(changes).toBe(2);
  });

  it('[IAP-02] in the app the cached flag answers at once and a restore at startup refreshes it', async () => {
    const flag = new MemoryFlag();
    flag.value = true;
    const store = new FakeStore();
    store.ownedValue = true;
    const service = new PurchaseService({ isNative: true, backend: store, flag });
    expect(service.isUnlocked()).toBe(false);
    await service.init();
    expect(service.isUnlocked()).toBe(true);
    await flush();
    expect(store.calls).toContain('owned');
    expect(service.isUnlocked()).toBe(true);
  });

  it('[IAP-02] a refund seen by Play relocks; Play unreachable keeps the cached unlock', async () => {
    const flag = new MemoryFlag();
    flag.value = true;
    const offline = new FakeStore();
    offline.ownedError = new Error('SERVICE_UNAVAILABLE');
    const kept = new PurchaseService({ isNative: true, backend: offline, flag });
    await kept.init();
    await flush();
    expect(kept.isUnlocked()).toBe(true);
    expect(flag.value).toBe(true);
    const failed = await kept.restore();
    expect(failed.status).toBe('unavailable');
    expect(kept.isUnlocked()).toBe(true);

    const refunded = new FakeStore();
    refunded.ownedValue = false;
    const relocked = new PurchaseService({ isNative: true, backend: refunded, flag });
    await relocked.init();
    await flush();
    expect(relocked.isUnlocked()).toBe(false);
    expect(flag.value).toBe(false);
  });

  it('[IAP-02] buying unlocks and stores the flag; cancel, pending and errors do not', async () => {
    const cases: Array<['purchased' | 'pending' | Error, string, boolean]> = [
      ['purchased', 'unlocked', true],
      ['pending', 'pending', false],
      [new Error('USER_CANCELED'), 'cancelled', false],
      [Object.assign(new Error('Item already owned'), { code: 'ITEM_ALREADY_OWNED' }), 'unlocked', true],
      [new Error('BILLING_UNAVAILABLE'), 'unavailable', false],
      [new Error('something odd'), 'error', false],
    ];
    for (const [outcome, status, unlocked] of cases) {
      const flag = new MemoryFlag();
      const store = new FakeStore();
      store.buyOutcome = outcome;
      const service = new PurchaseService({ isNative: true, backend: store, flag });
      const result = await service.buy();
      expect(result.status).toBe(status);
      expect(result.message.length).toBeGreaterThan(0);
      expect(service.isUnlocked()).toBe(unlocked);
      expect(flag.value).toBe(unlocked);
    }
  });

  it('[IAP-02] restore finds a purchase on this account; the price comes from the store', async () => {
    const store = new FakeStore();
    store.ownedValue = true;
    const service = new PurchaseService({ isNative: true, backend: store, flag: new MemoryFlag() });
    expect((await service.restore()).status).toBe('unlocked');
    expect(service.isUnlocked()).toBe(true);
    expect(await service.price()).toBe('€4.99');
    store.priceValue = null;
    expect(await service.price()).toBe('€4.99');
    store.ownedValue = false;
    expect((await service.restore()).status).toBe('notOwned');
    expect(FULL_GAME_PRODUCT_ID).toBe('full_game_unlock');
  });

  it('[IAP-02] store calls run one at a time', async () => {
    let active = 0;
    let most = 0;
    const slow: StoreBackend = {
      price: async () => {
        active += 1;
        most = Math.max(most, active);
        await flush();
        active -= 1;
        return '€1';
      },
      buy: async () => {
        active += 1;
        most = Math.max(most, active);
        await flush();
        active -= 1;
        return 'purchased';
      },
      owned: async () => {
        active += 1;
        most = Math.max(most, active);
        await flush();
        active -= 1;
        return true;
      },
    };
    const service = new PurchaseService({ isNative: true, backend: slow, flag: new MemoryFlag() });
    await Promise.all([service.init(), service.price(), service.buy(), service.restore()]);
    await flush();
    expect(most).toBe(1);
  });
});
