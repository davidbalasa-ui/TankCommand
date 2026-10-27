export type WatchdogChannel = 'sim' | 'render';

export interface WatchdogReport {
  channel: WatchdogChannel;
  stalledMs: number;
  lastBeats: Record<WatchdogChannel, number>;
}

export interface WatchdogOptions {
  now: () => number;
  freezeMs?: number;
  recoverMs?: number;
  onFreeze: (report: WatchdogReport) => void;
  onRecover: (report: WatchdogReport) => void;
}

interface ChannelState {
  lastBeat: number;
  freezeFired: boolean;
  recoverFired: boolean;
}

export class Watchdog {
  private readonly opts: WatchdogOptions;
  private readonly freezeMs: number;
  private readonly recoverMs: number;
  private readonly states: Record<WatchdogChannel, ChannelState>;
  private suspended = false;

  constructor(opts: WatchdogOptions) {
    this.opts = opts;
    this.freezeMs = opts.freezeMs ?? 2000;
    this.recoverMs = opts.recoverMs ?? 5000;
    const now = opts.now();
    this.states = {
      sim: { lastBeat: now, freezeFired: false, recoverFired: false },
      render: { lastBeat: now, freezeFired: false, recoverFired: false },
    };
  }

  beat(channel: WatchdogChannel): void {
    const state = this.states[channel];
    state.lastBeat = this.opts.now();
    state.freezeFired = false;
    state.recoverFired = false;
  }

  setSuspended(suspended: boolean): void {
    this.suspended = suspended;
    if (!suspended) {
      const now = this.opts.now();
      for (const channel of ['sim', 'render'] as const) {
        const state = this.states[channel];
        state.lastBeat = now;
        state.freezeFired = false;
        state.recoverFired = false;
      }
    }
  }

  check(): void {
    if (this.suspended) {
      return;
    }

    const now = this.opts.now();
    const stalled = (['sim', 'render'] as const).map((channel) => {
      const state = this.states[channel];
      return {
        channel,
        state,
        stalledMs: now - state.lastBeat,
      };
    });

    const freeze = stalled.find(
      (item) => item.stalledMs >= this.freezeMs && !item.state.freezeFired,
    );
    if (freeze) {
      for (const item of stalled) {
        if (item.stalledMs >= this.freezeMs) {
          item.state.freezeFired = true;
        }
      }
      this.opts.onFreeze({
        channel: freeze.channel,
        stalledMs: freeze.stalledMs,
        lastBeats: {
          sim: this.states.sim.lastBeat,
          render: this.states.render.lastBeat,
        },
      });
    }

    const recover = stalled.find(
      (item) => item.stalledMs >= this.recoverMs && !item.state.recoverFired,
    );
    if (recover) {
      for (const item of stalled) {
        if (item.stalledMs >= this.recoverMs) {
          item.state.recoverFired = true;
        }
      }
      this.opts.onRecover({
        channel: recover.channel,
        stalledMs: recover.stalledMs,
        lastBeats: {
          sim: this.states.sim.lastBeat,
          render: this.states.render.lastBeat,
        },
      });
    }
  }
}

export interface CapturedError {
  message: string;
  stack?: string;
  kind: 'error' | 'unhandledrejection';
}

export interface ErrorTarget {
  addEventListener(type: string, listener: (event: Event) => void): void;
  removeEventListener?(type: string, listener: (event: Event) => void): void;
}

export function installGlobalErrorCapture(
  target: ErrorTarget,
  onError: (error: CapturedError) => void,
): () => void {
  const errorHandler = (event: Event): void => {
    const errorEvent = event as ErrorEvent;
    const error = errorEvent.error;
    onError({
      message: errorEvent.message || (error instanceof Error ? error.message : 'Unknown error'),
      stack: error instanceof Error ? error.stack : undefined,
      kind: 'error',
    });
  };

  const rejectionHandler = (event: Event): void => {
    const rejection = event as PromiseRejectionEvent;
    const reason = rejection.reason;
    const error = reason instanceof Error ? reason : undefined;
    onError({
      message: error?.message ?? String(reason),
      stack: error?.stack,
      kind: 'unhandledrejection',
    });
  };

  target.addEventListener('error', errorHandler);
  target.addEventListener('unhandledrejection', rejectionHandler);

  return () => {
    target.removeEventListener?.('error', errorHandler);
    target.removeEventListener?.('unhandledrejection', rejectionHandler);
  };
}
