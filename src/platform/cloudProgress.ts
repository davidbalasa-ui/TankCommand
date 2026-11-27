import { Capacitor, registerPlugin } from '@capacitor/core';
import {
  emptyProgress,
  mergeProgress,
  parseProgress,
  progressScore,
  sameProgress,
  type CampaignProgress,
} from './progress';

/**
 * Cloud saves through Google Play Games (Saved Games), in the Android app only.
 *
 * Sign-in is optional and never blocks play: the game always keeps its own copy on the device.
 * When the player is signed in, the device copy and the cloud copy are merged (every mission won
 * on either side stays won; see mergeProgress) at start, after sign-in and after each change, so
 * progress follows the player to a new phone. Google stores the snapshot; there is no server of
 * our own. On the web, or in a build without a Play Games project id, it reports "unavailable".
 */

/** The snapshot's name in Saved Games. */
export const CLOUD_SNAPSHOT_NAME = 'campaign-progress';

export interface PlayGamesStatus {
  configured: boolean;
  signedIn: boolean;
  playerName?: string;
}

/** The native side (android/app/.../PlayGamesPlugin.java). */
export interface PlayGamesBackend {
  status(): Promise<PlayGamesStatus>;
  signIn(): Promise<PlayGamesStatus>;
  read(options: { name: string }): Promise<{ exists: boolean; data: string }>;
  write(options: { name: string; data: string; description: string; progress: number }): Promise<void>;
}

const PlayGames = registerPlugin<PlayGamesBackend>('PlayGames');

export type CloudState = 'unavailable' | 'signedOut' | 'signingIn' | 'syncing' | 'synced' | 'offline';

export interface CloudSaveDeps {
  isNative?: boolean;
  backend?: PlayGamesBackend;
}

export class CloudProgressSync {
  private readonly isNative: boolean;
  private readonly backend: PlayGamesBackend;
  private stateValue: CloudState = 'unavailable';
  private player: string | undefined;
  private readonly listeners = new Set<() => void>();
  /** Cloud calls run one after another. */
  private queue: Promise<unknown> = Promise.resolve();

  constructor(deps: CloudSaveDeps = {}) {
    this.isNative = deps.isNative ?? (Capacitor.isNativePlatform() && Capacitor.isPluginAvailable('PlayGames'));
    this.backend = deps.backend ?? PlayGames;
    if (this.isNative) {
      this.stateValue = 'signedOut';
    }
  }

  state(): CloudState {
    return this.stateValue;
  }

  playerName(): string | undefined {
    return this.player;
  }

  /** True where cloud saves can work at all (the Play build with Play Games set up). */
  available(): boolean {
    return this.stateValue !== 'unavailable';
  }

  signedIn(): boolean {
    return this.stateValue === 'syncing' || this.stateValue === 'synced' || this.stateValue === 'offline';
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private set(state: CloudState): void {
    this.stateValue = state;
    for (const listener of this.listeners) {
      listener();
    }
  }

  private serial<T>(task: () => Promise<T>): Promise<T> {
    const run = this.queue.then(task, task);
    this.queue = run.catch(() => undefined);
    return run;
  }

  private apply(status: PlayGamesStatus): void {
    if (!status.configured) {
      this.player = undefined;
      this.set('unavailable');
      return;
    }
    this.player = status.signedIn ? status.playerName : undefined;
    this.set(status.signedIn ? 'syncing' : 'signedOut');
  }

  /**
   * At start: Play Games signs the player in silently when they have used it before. Returns
   * the merged progress when anything changed on this device, otherwise null.
   */
  start(local: () => CampaignProgress): Promise<CampaignProgress | null> {
    if (!this.isNative) {
      return Promise.resolve(null);
    }
    return this.serial(async () => {
      try {
        this.apply(await this.backend.status());
      } catch {
        this.set('unavailable');
        return null;
      }
      return this.signedIn() ? this.syncNow(local()) : null;
    });
  }

  /** The player's tap on "Sign in". Same answer as start(). */
  signIn(local: () => CampaignProgress): Promise<CampaignProgress | null> {
    if (!this.available()) {
      return Promise.resolve(null);
    }
    return this.serial(async () => {
      this.set('signingIn');
      try {
        this.apply(await this.backend.signIn());
      } catch {
        this.set('signedOut');
        return null;
      }
      return this.signedIn() ? this.syncNow(local()) : null;
    });
  }

  /** Pull, merge and push. Same answer as start(). */
  sync(local: () => CampaignProgress): Promise<CampaignProgress | null> {
    if (!this.signedIn()) {
      return Promise.resolve(null);
    }
    return this.serial(() => this.syncNow(local()));
  }

  /** After the progress changed on this device: upload it (merged with the cloud copy). */
  push(local: () => CampaignProgress): Promise<CampaignProgress | null> {
    return this.sync(local);
  }

  private async syncNow(local: CampaignProgress): Promise<CampaignProgress | null> {
    this.set('syncing');
    let cloud: CampaignProgress;
    try {
      const snapshot = await this.backend.read({ name: CLOUD_SNAPSHOT_NAME });
      cloud = snapshot.exists ? parseProgress(snapshot.data) : emptyProgress();
    } catch {
      this.set('offline');
      return null;
    }
    // A fresh install has nothing to prefer: take the difficulty from the cloud copy.
    const merged =
      progressScore(local) === 0 && progressScore(cloud) > 0 ? mergeProgress(cloud, local) : mergeProgress(local, cloud);
    if (!sameProgress(merged, cloud)) {
      try {
        await this.backend.write({
          name: CLOUD_SNAPSHOT_NAME,
          data: JSON.stringify(merged),
          description: `${progressScore(merged)} missions won`,
          progress: progressScore(merged),
        });
      } catch {
        this.set('offline');
        return sameProgress(merged, local) ? null : merged;
      }
    }
    this.set('synced');
    return sameProgress(merged, local) ? null : merged;
  }
}
