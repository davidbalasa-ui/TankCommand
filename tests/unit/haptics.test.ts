// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { ImpactStyle, NotificationType } from '@capacitor/haptics';
import { GameServices, type GameServicesHost } from '../../src/game/services';
import { HapticsService, type HapticsBackend } from '../../src/platform/haptics';
import { MemoryKvStore } from '../../src/platform/kv';
import { SettingsStore } from '../../src/platform/settings';
import { createWorld } from '../../src/sim/world';

class FakeHaptics implements HapticsBackend {
  readonly calls: string[] = [];
  fail = false;

  impact(options: { style: ImpactStyle }): Promise<void> {
    this.calls.push(`impact:${options.style}`);
    return this.fail ? Promise.reject(new Error('no vibrator')) : Promise.resolve();
  }

  notification(options: { type: NotificationType }): Promise<void> {
    this.calls.push(`notification:${options.type}`);
    return this.fail ? Promise.reject(new Error('no vibrator')) : Promise.resolve();
  }
}

const open: GameServices[] = [];

afterEach(() => {
  for (const services of open.splice(0)) {
    services.dispose();
  }
});

function services(haptics: HapticsService, settings = new SettingsStore(null)): GameServices {
  const world = createWorld(1);
  const host: GameServicesHost = {
    getWorld: () => world,
    loadWorld: () => undefined,
    currentScreen: () => 'inGame',
    inMatch: () => true,
    setCameraTarget: () => undefined,
    setSimSpeed: () => undefined,
    getSimSpeed: () => 1,
    freezeReport: () => null,
    applySettings: () => undefined,
  };
  const created = new GameServices(host, { kv: new MemoryKvStore(), settings, haptics, mount: document.body });
  open.push(created);
  return created;
}

describe('[HAP-01] haptics through the official plugin', () => {
  it('[HAP-01] selection, orders and alerts vibrate in the app', async () => {
    const fake = new FakeHaptics();
    const haptics = new HapticsService(true, { backend: fake, isNative: () => true });
    await haptics.selection();
    await haptics.order();
    await haptics.alert();
    expect(fake.calls).toEqual([
      `impact:${ImpactStyle.Light}`,
      `impact:${ImpactStyle.Medium}`,
      `notification:${NotificationType.Warning}`,
    ]);
  });

  it('[HAP-01] the web build never vibrates', async () => {
    const fake = new FakeHaptics();
    const haptics = new HapticsService(true, { backend: fake, isNative: () => false });
    await haptics.selection();
    await haptics.order();
    await haptics.alert();
    expect(fake.calls).toEqual([]);
  });

  it('[HAP-01] a failing or missing plugin is ignored', async () => {
    const fake = new FakeHaptics();
    fake.fail = true;
    const haptics = new HapticsService(true, { backend: fake, isNative: () => true });
    await expect(haptics.selection()).resolves.toBeUndefined();
    await expect(haptics.alert()).resolves.toBeUndefined();
  });

  it('[HAP-01] the game wires selection, order and alert events to haptics, and the setting turns them off', async () => {
    const fake = new FakeHaptics();
    const game = services(new HapticsService(true, { backend: fake, isNative: () => true }));
    game.playSound({ type: 'selection' });
    game.playSound({ type: 'orderAck' });
    game.setMatchActive(true);
    game.raiseAlert('underAttack', 10, 10);
    await Promise.resolve();
    expect(fake.calls).toContain(`impact:${ImpactStyle.Light}`);
    expect(fake.calls).toContain(`impact:${ImpactStyle.Medium}`);
    expect(fake.calls).toContain(`notification:${NotificationType.Warning}`);

    fake.calls.length = 0;
    game.setSetting('haptics', false);
    game.playSound({ type: 'selection' });
    game.playSound({ type: 'orderAck' });
    game.raiseAlert('unitLost', -10, -10);
    await Promise.resolve();
    expect(fake.calls).toEqual([]);
  });

  it('[HAP-01] a stored Haptics: off holds from the start', async () => {
    const fake = new FakeHaptics();
    const settings = new SettingsStore(null);
    settings.set('haptics', false);
    const game = services(new HapticsService(true, { backend: fake, isNative: () => true }), settings);
    game.playSound({ type: 'selection' });
    await Promise.resolve();
    expect(fake.calls).toEqual([]);
  });
});
