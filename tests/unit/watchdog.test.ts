import { describe, expect, it } from 'vitest';
import {
  Watchdog,
  installGlobalErrorCapture,
  type CapturedError,
  type ErrorTarget,
  type WatchdogReport,
} from '../../src/platform/watchdog';

class FakeErrorTarget implements ErrorTarget {
  private readonly handlers = new Map<string, Set<(event: Event) => void>>();

  addEventListener(type: string, listener: (event: Event) => void): void {
    const set = this.handlers.get(type) ?? new Set<(event: Event) => void>();
    set.add(listener);
    this.handlers.set(type, set);
  }

  removeEventListener(type: string, listener: (event: Event) => void): void {
    this.handlers.get(type)?.delete(listener);
  }

  dispatch(type: string, event: Event): void {
    for (const handler of [...(this.handlers.get(type) ?? [])]) {
      handler(event);
    }
  }
}

describe('watchdog', () => {
  it('[WD-01] freeze fires once at the threshold, recover once, and a beat starts a new episode', () => {
    let now = 0;
    const freezes: WatchdogReport[] = [];
    const recovers: WatchdogReport[] = [];
    const watchdog = new Watchdog({
      now: () => now,
      onFreeze: (report) => freezes.push(report),
      onRecover: (report) => recovers.push(report),
    });

    now = 2001;
    watchdog.check();
    expect(freezes).toHaveLength(1);

    now = 4999;
    watchdog.check();
    expect(recovers).toHaveLength(0);

    now = 5001;
    watchdog.check();
    expect(recovers).toHaveLength(1);

    watchdog.check();
    expect(freezes).toHaveLength(1);
    expect(recovers).toHaveLength(1);

    watchdog.beat('sim');
    watchdog.beat('render');
    now = 8001;
    watchdog.check();
    expect(freezes).toHaveLength(2);
  });

  it('[WD-02] suspended mode suppresses freezes and unsuspending resets clocks', () => {
    let now = 0;
    const freezes: WatchdogReport[] = [];
    const watchdog = new Watchdog({
      now: () => now,
      onFreeze: (report) => freezes.push(report),
      onRecover: () => undefined,
    });

    watchdog.setSuspended(true);
    now = 10000;
    watchdog.check();
    expect(freezes).toHaveLength(0);

    watchdog.setSuspended(false);
    watchdog.check();
    expect(freezes).toHaveLength(0);

    now = 12001;
    watchdog.check();
    expect(freezes).toHaveLength(1);
  });

  it('[WD-03] global error capture records thrown errors and rejected promises', () => {
    const target = new FakeErrorTarget();
    const captured: CapturedError[] = [];
    installGlobalErrorCapture(target, (error) => captured.push(error));

    target.dispatch(
      'error',
      { message: 'boom', error: new Error('boom') } as unknown as ErrorEvent,
    );
    target.dispatch(
      'unhandledrejection',
      { reason: new Error('rejected') } as unknown as PromiseRejectionEvent,
    );

    expect(captured).toHaveLength(2);
    expect(captured[0]?.kind).toBe('error');
    expect(captured[0]?.message).toBe('boom');
    expect(captured[1]?.kind).toBe('unhandledrejection');
    expect(captured[1]?.message).toBe('rejected');
  });
});
