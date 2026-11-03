import { describe, expect, it } from 'vitest';
import {
  DEFAULT_SETTINGS,
  SettingsStore,
  type SettingsState,
  type StorageLike,
} from '../../src/platform/settings';

class MemoryStorage implements StorageLike {
  private readonly data = new Map<string, string>();

  getItem(key: string): string | null {
    return this.data.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }
}

describe('settings', () => {
  it('[SET-01] every setting persists across reload and updates immediately', () => {
    const storage = new MemoryStorage();
    const settings = new SettingsStore(storage);
    expect(settings.get()).toEqual(DEFAULT_SETTINGS);

    const values: Partial<SettingsState> = {
      masterVolume: 0.31,
      musicVolume: 0.22,
      effectsVolume: 0.61,
      graphicsQuality: 'high',
      healthBars: 'always',
      edgeScroll: false,
      edgeScrollSpeed: 2.3,
      cameraSensitivity: 0.7,
      keyBindings: { move: 'm' },
      leftHanded: true,
      textSize: 'large',
      colourBlind: true,
      haptics: false,
    };

    settings.set('masterVolume', 0.31);
    expect(settings.getValue('masterVolume')).toBe(0.31);
    settings.set('musicVolume', 0.22);
    settings.set('effectsVolume', 0.61);
    settings.set('graphicsQuality', 'high');
    settings.set('healthBars', 'always');
    settings.set('edgeScroll', false);
    settings.set('edgeScrollSpeed', 2.3);
    settings.set('cameraSensitivity', 0.7);
    settings.set('keyBindings', { move: 'm' });
    settings.set('leftHanded', true);
    settings.set('textSize', 'large');
    settings.set('colourBlind', true);
    settings.set('haptics', false);

    for (const [key, value] of Object.entries(values)) {
      expect(settings.get()[key as keyof SettingsState]).toEqual(value);
    }

    const reloaded = new SettingsStore(storage);
    expect(reloaded.get()).toEqual(settings.get());
  });
});
