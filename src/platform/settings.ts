import { z } from 'zod';

const STORAGE_KEY = 'setting.gameSettings';
const LEGACY_LEFT_HANDED_KEY = 'setting.leftHanded';

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const settingsSchema = z.object({
  masterVolume: z.number().min(0).max(1),
  musicVolume: z.number().min(0).max(1),
  effectsVolume: z.number().min(0).max(1),
  graphicsQuality: z.enum(['low', 'medium', 'high', 'auto']),
  healthBars: z.enum(['damaged', 'always']),
  edgeScroll: z.boolean(),
  edgeScrollSpeed: z.number().min(0.2).max(3),
  cameraSensitivity: z.number().min(0.2).max(3),
  keyBindings: z.record(z.string(), z.string()),
  leftHanded: z.boolean(),
  textSize: z.enum(['normal', 'large']),
  colourBlind: z.boolean(),
  haptics: z.boolean(),
});

export type SettingsState = z.infer<typeof settingsSchema>;

export const DEFAULT_SETTINGS: SettingsState = {
  masterVolume: 0.8,
  musicVolume: 0.45,
  effectsVolume: 0.75,
  graphicsQuality: 'auto',
  healthBars: 'damaged',
  edgeScroll: true,
  edgeScrollSpeed: 1,
  cameraSensitivity: 1,
  keyBindings: {},
  leftHanded: false,
  textSize: 'normal',
  colourBlind: false,
  haptics: true,
};

const partialSettingsSchema = settingsSchema.partial();

function defaultStorage(): StorageLike | null {
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

export class SettingsStore {
  private readonly storage: StorageLike | null;
  private readonly listeners = new Set<(state: SettingsState) => void>();
  private state: SettingsState;

  constructor(storage: StorageLike | null = defaultStorage()) {
    this.storage = storage;
    const legacyLeftHanded = storage?.getItem(LEGACY_LEFT_HANDED_KEY) === 'true';
    let loaded: SettingsState = {
      ...DEFAULT_SETTINGS,
      keyBindings: { ...DEFAULT_SETTINGS.keyBindings },
      leftHanded: legacyLeftHanded || DEFAULT_SETTINGS.leftHanded,
    };

    const raw = storage?.getItem(STORAGE_KEY) ?? null;
    if (raw) {
      try {
        const parsed: unknown = JSON.parse(raw);
        const result = partialSettingsSchema.safeParse(parsed);
        if (result.success) {
          loaded = {
            ...loaded,
            ...result.data,
            keyBindings: {
              ...loaded.keyBindings,
              ...(result.data.keyBindings ?? {}),
            },
          };
        }
      } catch {
        // Invalid settings are ignored; defaults keep the game playable.
      }
    }
    this.state = loaded;
  }

  get(): Readonly<SettingsState> {
    return { ...this.state, keyBindings: { ...this.state.keyBindings } };
  }

  getValue<K extends keyof SettingsState>(key: K): SettingsState[K] {
    return this.state[key];
  }

  set<K extends keyof SettingsState>(key: K, value: SettingsState[K]): void {
    const candidate = { ...this.state, [key]: value };
    const parsed = settingsSchema.safeParse(candidate);
    if (!parsed.success) {
      return;
    }
    this.state = parsed.data;
    this.persist();
    for (const listener of this.listeners) {
      listener(this.get());
    }
  }

  subscribe(listener: (state: SettingsState) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private persist(): void {
    try {
      this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.state));
      this.storage?.setItem(LEGACY_LEFT_HANDED_KEY, this.state.leftHanded ? 'true' : 'false');
    } catch {
      // Storage may be unavailable or full; the in-memory settings still apply.
    }
  }
}
