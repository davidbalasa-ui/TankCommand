import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';

export type LifecycleEventName = 'pause' | 'resume' | 'back';

export interface LifecycleSource {
  addEventListener(type: string, listener: () => void): void;
  removeEventListener?(type: string, listener: () => void): void;
  isHidden(): boolean;
}

export class Lifecycle {
  private readonly listeners = new Map<LifecycleEventName, Set<() => void>>();
  private paused = false;
  private readonly source: LifecycleSource;

  constructor(source: LifecycleSource) {
    this.source = source;
    source.addEventListener('visibilitychange', this.onVisibility);
    source.addEventListener('pause', this.onPause);
    source.addEventListener('resume', this.onResume);
    source.addEventListener('backButton', this.onBackButton);
  }

  on(event: LifecycleEventName, listener: () => void): () => void {
    const set = this.listeners.get(event) ?? new Set<() => void>();
    set.add(listener);
    this.listeners.set(event, set);
    return () => {
      set.delete(listener);
    };
  }

  destroy(): void {
    this.source.removeEventListener?.('visibilitychange', this.onVisibility);
    this.source.removeEventListener?.('pause', this.onPause);
    this.source.removeEventListener?.('resume', this.onResume);
    this.source.removeEventListener?.('backButton', this.onBackButton);
  }

  private emit(event: LifecycleEventName): void {
    for (const listener of this.listeners.get(event) ?? []) {
      listener();
    }
  }

  private readonly onVisibility = (): void => {
    if (this.source.isHidden()) {
      this.handlePause();
    } else {
      this.handleResume();
    }
  };

  private readonly onPause = (): void => {
    this.handlePause();
  };

  private readonly onResume = (): void => {
    this.handleResume();
  };

  private readonly onBackButton = (): void => {
    this.handlePause();
    this.emit('back');
  };

  private handlePause(): void {
    if (this.paused) {
      return;
    }
    this.paused = true;
    this.emit('pause');
  }

  private handleResume(): void {
    if (!this.paused) {
      return;
    }
    this.paused = false;
    this.emit('resume');
  }
}

export function bindLifecycleToBrowserAndCapacitor(): Lifecycle {
  const source: LifecycleSource = {
    addEventListener: (type, listener) => {
      if (type === 'visibilitychange') {
        document.addEventListener(type, listener);
        return;
      }
      if (type === 'pause' || type === 'resume' || type === 'backButton') {
        if (!Capacitor.isNativePlatform()) {
          return;
        }
        if (type === 'pause') {
          void App.addListener('pause', () => listener());
        } else if (type === 'resume') {
          void App.addListener('resume', () => listener());
        } else {
          void App.addListener('backButton', () => listener());
        }
      }
    },
    removeEventListener: (type, listener) => {
      if (type === 'visibilitychange') {
        document.removeEventListener(type, listener);
      }
    },
    isHidden: () => document.hidden,
  };

  return new Lifecycle(source);
}
