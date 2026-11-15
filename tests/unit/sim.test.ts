import { describe, expect, it } from 'vitest';
import { Rng } from '../../src/sim/rng';
import { validateCommand, type Command } from '../../src/sim/commands';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { FixedStepLoop } from '../../src/sim/loop';

describe('sim shell', () => {
  it('[SIM-01] same seed same command list produces identical hash after 10000 steps', () => {
    const commands: Command[] = [
      { kind: 'debug.addCounter', amount: 5, tick: 1, issuer: 1 },
      { kind: 'noop', tick: 5000, issuer: 1 },
      { kind: 'debug.addCounter', amount: 9, tick: 10000, issuer: 1 },
    ];

    let a = createWorld(12345);
    let b = createWorld(12345);
    for (let i = 0; i < 10000; i += 1) {
      a = step(a, commands);
      b = step(b, commands);
    }

    expect(hashWorld(a)).toBe(hashWorld(b));
  });

  it('[SIM-02] different seeds produce different hashes after 100 steps', () => {
    let a = createWorld(1);
    let b = createWorld(2);
    for (let i = 0; i < 100; i += 1) {
      a = step(a, []);
      b = step(b, []);
    }
    expect(hashWorld(a)).not.toBe(hashWorld(b));
  });

  it('[SIM-03] step does not mutate its input and accepts frozen input', () => {
    const world = createWorld(9);
    const before = { ...world };
    const frozen = Object.freeze({ ...world });
    expect(() => step(frozen, [])).not.toThrow();
    const result = step(world, []);
    expect(world).toEqual(before);
    expect(result).not.toBe(world);
  });

  it('[SIM-04] debug.addCounter applies only on its tick and past ticks are ignored', () => {
    const world = createWorld(4);
    const command: Command = {
      kind: 'debug.addCounter',
      amount: 7,
      tick: 1,
      issuer: 1,
    };
    const withCommand = step(world, [command]);
    const withoutCommand = step(world, []);
    expect(withCommand.counter).toBe(withoutCommand.counter + 7);

    const past = step(withCommand, [{ ...command, tick: 1 }]);
    const pastBaseline = step(withCommand, []);
    expect(past.counter).toBe(pastBaseline.counter);
  });

  it('[SIM-05] validateCommand rejects unknown kind, fractional tick, infinite amount, missing issuer and null', () => {
    expect(validateCommand({ kind: 'unknown', tick: 1, issuer: 1 })).toBeNull();
    expect(validateCommand({ kind: 'noop', tick: 1.5, issuer: 1 })).toBeNull();
    expect(
      validateCommand({ kind: 'debug.addCounter', amount: Number.POSITIVE_INFINITY, tick: 1, issuer: 1 }),
    ).toBeNull();
    expect(validateCommand({ kind: 'noop', tick: 1 })).toBeNull();
    expect(validateCommand(null)).toBeNull();
  });

  it('[SIM-06] fixed-step loop accumulates, caps and ignores invalid elapsed time', () => {
    let steps = 0;
    const loop = new FixedStepLoop({
      tickHz: 20,
      maxStepsPerFrame: 5,
      step: () => {
        steps += 1;
      },
    });

    const first = loop.advance(125);
    expect(first.steps).toBe(2);
    expect(first.alpha).toBeCloseTo(0.5);
    expect(steps).toBe(2);

    const capped = loop.advance(10_000);
    expect(capped.steps).toBe(5);
    expect(steps).toBe(7);

    const negative = loop.advance(-5);
    expect(negative.steps).toBe(0);
    const nan = loop.advance(Number.NaN);
    expect(nan.steps).toBe(0);
  });

  it('[SIM-07] Rng is reproducible, state resumes, and int upper bound is exclusive', () => {
    const a = new Rng(77);
    const b = new Rng(77);
    const first: number[] = [];
    for (let i = 0; i < 1000; i += 1) {
      const av = a.next();
      const bv = b.next();
      expect(av).toBe(bv);
      first.push(av);
    }

    const rng = new Rng(99);
    for (let i = 0; i < 10; i += 1) {
      rng.nextU32();
    }
    const state = rng.getState();
    const nextValues: number[] = [];
    for (let i = 0; i < 10; i += 1) {
      nextValues.push(rng.nextU32());
    }
    rng.setState(state);
    for (const value of nextValues) {
      expect(rng.nextU32()).toBe(value);
    }

    const bounds = new Rng(5);
    for (let i = 0; i < 100_000; i += 1) {
      expect(bounds.int(0, 3)).not.toBe(3);
    }
  });
});
