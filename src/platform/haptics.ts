import { Capacitor, registerPlugin } from '@capacitor/core';

interface HapticsPlugin {
  impact(options: { style: 'light' | 'medium' | 'heavy' }): Promise<void>;
  notification(options: { type: 'success' | 'warning' | 'error' }): Promise<void>;
}

const Haptics = registerPlugin<HapticsPlugin>('Haptics');

export class HapticsService {
  private enabled: boolean;

  constructor(enabled = true) {
    this.enabled = enabled;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  async selection(): Promise<void> {
    await this.impact('light');
  }

  async order(): Promise<void> {
    await this.impact('medium');
  }

  async alert(): Promise<void> {
    if (!this.active()) {
      return;
    }
    try {
      await Haptics.notification({ type: 'warning' });
    } catch {
      // Haptics are optional and absent on the web.
    }
  }

  private async impact(style: 'light' | 'medium' | 'heavy'): Promise<void> {
    if (!this.active()) {
      return;
    }
    try {
      await Haptics.impact({ style });
    } catch {
      // Haptics are optional and absent on the web.
    }
  }

  private active(): boolean {
    return this.enabled && Capacitor.isNativePlatform();
  }
}
