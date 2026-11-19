import { Capacitor } from '@capacitor/core';
import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics';

/** The part of the official Haptics plugin the game uses (injectable for tests). */
export interface HapticsBackend {
  impact(options: { style: ImpactStyle }): Promise<void>;
  notification(options: { type: NotificationType }): Promise<void>;
}

export interface HapticsDeps {
  backend?: HapticsBackend;
  /** True in the Android app; on the web every call is a silent no-op. */
  isNative?: () => boolean;
}

/**
 * Light vibration for selection, orders and alerts (gameplay SOR, Audio and feedback), off when
 * the Haptics setting is off. Only the native app vibrates: the plugin's web fallback would call
 * navigator.vibrate, which the web build does not want. A device without a vibrator, or a plugin
 * call that fails, is ignored.
 */
export class HapticsService {
  private enabled: boolean;
  private readonly backend: HapticsBackend;
  private readonly isNative: () => boolean;

  constructor(enabled = true, deps: HapticsDeps = {}) {
    this.enabled = enabled;
    this.backend = deps.backend ?? Haptics;
    this.isNative = deps.isNative ?? (() => Capacitor.isNativePlatform());
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  async selection(): Promise<void> {
    await this.impact(ImpactStyle.Light);
  }

  async order(): Promise<void> {
    await this.impact(ImpactStyle.Medium);
  }

  async alert(): Promise<void> {
    if (!this.active()) {
      return;
    }
    try {
      await this.backend.notification({ type: NotificationType.Warning });
    } catch {
      // Haptics are optional: no vibrator, or the plugin is missing.
    }
  }

  private async impact(style: ImpactStyle): Promise<void> {
    if (!this.active()) {
      return;
    }
    try {
      await this.backend.impact({ style });
    } catch {
      // Haptics are optional: no vibrator, or the plugin is missing.
    }
  }

  private active(): boolean {
    return this.enabled && this.isNative();
  }
}
