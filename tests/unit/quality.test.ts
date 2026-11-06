import { describe, expect, it } from 'vitest';
import {
  MIN_PIXEL_RATIO,
  QUALITY_LADDER,
  QualityController,
  qualityViewFor,
} from '../../src/render/quality';

interface Change {
  level: number;
  atMs: number;
}

function feed(controller: QualityController, count: number, frameMs: number): Change[] {
  const changes: Change[] = [];
  for (let index = 0; index < count; index += 1) {
    if (controller.sample(frameMs)) {
      changes.push({ level: controller.level, atMs: controller.elapsedMs });
    }
  }
  return changes;
}

function expectSpacedAtLeastOneSecond(changes: readonly Change[]): void {
  for (let index = 1; index < changes.length; index += 1) {
    const previous = changes[index - 1];
    const current = changes[index];
    if (!previous || !current) {
      continue;
    }
    expect(
      current.atMs - previous.atMs,
      `change at ${current.atMs} ms followed the one at ${previous.atMs} ms too closely`,
    ).toBeGreaterThanOrEqual(1000);
  }
}

describe('dynamic quality', () => {
  it('[PERF-01] sustained slow frames step quality down one level at a time', () => {
    const controller = new QualityController();
    // 100 ms frames are 10 fps: below the 20 fps budget on every single sample.
    const changes = feed(controller, 60, 100);

    expect(changes.map((change) => change.level)).toEqual([1, 2, 3, 4, 5]);
    expectSpacedAtLeastOneSecond(changes);
    expect(controller.level).toBe(QUALITY_LADDER.length - 1);
  });

  it('[PERF-01] fast frames step quality back up, never faster than once per second', () => {
    const controller = new QualityController();
    const down = feed(controller, 30, 100);
    expect(controller.level).toBe(3);

    const up = feed(controller, 1000, 10);
    expect(controller.level).toBe(0);
    expect(up.map((change) => change.level)).toEqual([2, 1, 0]);
    expectSpacedAtLeastOneSecond([...down, ...up]);
  });

  it('[PERF-01] frames between the two thresholds never change quality', () => {
    const controller = new QualityController();
    // 35 ms is 28 fps: above the 25 ms "headroom" mark and below the 50 ms
    // "too slow" mark, so neither hold accumulates.
    const changes = feed(controller, 600, 35);
    expect(changes).toEqual([]);
    expect(controller.level).toBe(0);
  });

  it('[PERF-01] the ladder halves the shadow map, then disables shadows, then lowers the render scale', () => {
    const full = QUALITY_LADDER[0];
    const half = QUALITY_LADDER[1];
    const none = QUALITY_LADDER[2];
    expect(full).toBeDefined();
    expect(half).toBeDefined();
    expect(none).toBeDefined();
    if (!full || !half || !none) {
      return;
    }

    expect(half.shadowMapScale).toBe(full.shadowMapScale / 2);
    expect(none.shadowMapScale).toBe(0);

    expect(qualityViewFor(0, 2)).toEqual({ level: 0, pixelRatio: 2, shadows: true });
    expect(qualityViewFor(1, 2).shadows).toBe(true);
    expect(qualityViewFor(2, 2)).toEqual({ level: 2, pixelRatio: 2, shadows: false });

    const floorLevel = QUALITY_LADDER.length - 1;
    expect(qualityViewFor(floorLevel, 2).pixelRatio).toBe(MIN_PIXEL_RATIO);
    expect(MIN_PIXEL_RATIO).toBe(0.5);
    expect(qualityViewFor(floorLevel, 1).pixelRatio).toBe(MIN_PIXEL_RATIO);

    for (let index = 1; index < QUALITY_LADDER.length; index += 1) {
      const previous = QUALITY_LADDER[index - 1];
      const current = QUALITY_LADDER[index];
      if (!previous || !current) {
        continue;
      }
      expect(current.pixelRatioCap).toBeLessThanOrEqual(previous.pixelRatioCap);
      expect(current.shadowMapScale).toBeLessThanOrEqual(previous.shadowMapScale);
    }
  });

  it('[PERF-01] a discontinuity (paused loop, hidden tab) is ignored', () => {
    const controller = new QualityController();
    expect(controller.sample(Number.NaN)).toBe(false);
    expect(controller.sample(0)).toBe(false);
    expect(controller.sample(-16)).toBe(false);
    expect(controller.level).toBe(0);
  });
});
