import { Rng } from './rng';
import type { Command } from './commands';

export interface WorldState {
  tick: number;
  seed: number;
  rngState: number;
  counter: number;
}

export function createWorld(seed: number): WorldState {
  const rng = new Rng(seed);
  return {
    tick: 0,
    seed,
    rngState: rng.getState(),
    counter: 0,
  };
}

export function step(world: WorldState, commands: readonly Command[]): WorldState {
  const nextTick = world.tick + 1;
  let counter = world.counter;

  for (const command of commands) {
    if (command.kind === 'debug.addCounter' && command.tick === nextTick) {
      counter += command.amount;
    }
  }

  const rng = new Rng(world.seed);
  rng.setState(world.rngState);
  counter += rng.int(0, 3);

  return {
    tick: nextTick,
    seed: world.seed,
    rngState: rng.getState(),
    counter,
  };
}

export function snapshot(world: WorldState): Readonly<WorldState> {
  return Object.freeze({ ...world });
}

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(',')}]`;
  }
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record).sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}

export function fnv1aHex(input: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i) & 0xff;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}

export function hashWorld(world: WorldState): string {
  return fnv1aHex(
    canonicalJson({
      tick: world.tick,
      seed: world.seed,
      rngState: world.rngState,
      counter: world.counter,
    }),
  );
}
