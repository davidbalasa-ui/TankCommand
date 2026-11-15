import { describe, expect, it } from 'vitest';
import { Lifecycle, type LifecycleSource } from '../../src/platform/lifecycle';

class FakeSource implements LifecycleSource {
  public hidden = false;
  private readonly handlers = new Map<string, Set<() => void>>();

  addEventListener(type: string, listener: () => void): void {
    const set = this.handlers.get(type) ?? new Set<() => void>();
    set.add(listener);
    this.handlers.set(type, set);
  }

  removeEventListener(type: string, listener: () => void): void {
    this.handlers.get(type)?.delete(listener);
  }

  isHidden(): boolean {
    return this.hidden;
  }

  dispatch(type: string): void {
    for (const handler of [...(this.handlers.get(type) ?? [])]) {
      handler();
    }
  }
}

describe('lifecycle', () => {
  it('[LIFE-01] hidden pauses, visible resumes, duplicate pauses collapse, back emits pause plus back', () => {
    const source = new FakeSource();
    const lifecycle = new Lifecycle(source);
    const events: string[] = [];
    lifecycle.on('pause', () => events.push('pause'));
    lifecycle.on('resume', () => events.push('resume'));
    lifecycle.on('back', () => events.push('back'));

    source.hidden = true;
    source.dispatch('visibilitychange');
    expect(events).toEqual(['pause']);

    source.dispatch('visibilitychange');
    expect(events).toEqual(['pause']);

    source.hidden = false;
    source.dispatch('visibilitychange');
    expect(events).toEqual(['pause', 'resume']);

    source.dispatch('backButton');
    expect(events).toEqual(['pause', 'resume', 'pause', 'back']);
  });
});
