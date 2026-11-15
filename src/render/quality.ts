/**
 * Dynamic quality controller.
 *
 * A software-rendered 1920x1080 frame with shadows can take more than a second.
 * A slow frame is not a freeze, but it does make the page unresponsive: input is
 * delivered on the main thread between frames, so a click can wait seconds for
 * its turn. Dropping effects when the frame budget is repeatedly missed keeps the
 * game interactive on low-end hardware.
 *
 * The controller is a pure state machine over frame times, with no DOM and no
 * three.js, so it can be exercised in Node with synthetic input.
 */

export interface QualityStep {
  /** Multiplier for the directional shadow map resolution; 0 disables shadows. */
  shadowMapScale: number;
  /** Upper bound on the renderer pixel ratio at this level. */
  pixelRatioCap: number;
}

/** Lowest render scale the controller will ever ask for. */
export const MIN_PIXEL_RATIO = 0.5;

/**
 * Capability ladder, cheapest last. The index is the quality level, so the
 * order is: halve the shadow map, then disable shadows, then drop the render
 * scale in three steps ending at `MIN_PIXEL_RATIO`.
 */
export const QUALITY_LADDER: readonly QualityStep[] = [
  { shadowMapScale: 1, pixelRatioCap: 2 }, // full quality
  { shadowMapScale: 0.5, pixelRatioCap: 2 }, // half-resolution shadow map
  { shadowMapScale: 0, pixelRatioCap: 2 }, // shadows off
  { shadowMapScale: 0, pixelRatioCap: 1 }, // native pixels
  { shadowMapScale: 0, pixelRatioCap: 0.75 },
  { shadowMapScale: 0, pixelRatioCap: MIN_PIXEL_RATIO }, // lowest render scale
];

const FALLBACK_STEP: QualityStep = {
  shadowMapScale: 0,
  pixelRatioCap: MIN_PIXEL_RATIO,
};

export interface QualityView {
  level: number;
  pixelRatio: number;
  shadows: boolean;
}

function clampLevel(level: number): number {
  if (!Number.isFinite(level)) {
    return 0;
  }
  const last = QUALITY_LADDER.length - 1;
  return Math.min(Math.max(Math.trunc(level), 0), last);
}

export function qualityStep(level: number): QualityStep {
  return QUALITY_LADDER[clampLevel(level)] ?? FALLBACK_STEP;
}

/**
 * The concrete settings a level means for a given device pixel ratio. The
 * reported `pixelRatio` is what the renderer is actually using, so a test can
 * assert the drop without knowing the device's DPR.
 */
export function qualityViewFor(level: number, basePixelRatio: number): QualityView {
  const clamped = clampLevel(level);
  const step = QUALITY_LADDER[clamped] ?? FALLBACK_STEP;
  const capped = Math.min(basePixelRatio, step.pixelRatioCap);
  return {
    level: clamped,
    pixelRatio: Math.max(MIN_PIXEL_RATIO, capped),
    shadows: step.shadowMapScale > 0,
  };
}

export interface QualityControllerOptions {
  /** Rolling average above this means "too slow" (default 50 ms, i.e. 20 fps). */
  slowFrameMs?: number;
  /** Rolling average below this means "has headroom" (default 25 ms, i.e. 40 fps). */
  fastFrameMs?: number;
  /** How long the average must stay slow before stepping down (default 1000 ms). */
  slowHoldMs?: number;
  /** How long the average must stay fast before stepping up (default 3000 ms). */
  fastHoldMs?: number;
  /** Hard floor between two changes (default 1000 ms). */
  minChangeIntervalMs?: number;
  /** Length of the rolling-average window (default 1000 ms). */
  windowMs?: number;
}

const DEFAULTS = {
  slowFrameMs: 50,
  fastFrameMs: 25,
  slowHoldMs: 1000,
  fastHoldMs: 3000,
  minChangeIntervalMs: 1000,
  windowMs: 1000,
} as const;

export class QualityController {
  private readonly slowFrameMs: number;
  private readonly fastFrameMs: number;
  private readonly slowHoldMs: number;
  private readonly fastHoldMs: number;
  private readonly minChangeIntervalMs: number;
  private readonly windowMs: number;

  private readonly samples: number[] = [];
  private windowTotal = 0;
  private elapsedTotal = 0;
  private slowAccum = 0;
  private fastAccum = 0;
  private lastChangeAt = Number.NEGATIVE_INFINITY;
  private currentLevel = 0;

  constructor(options: QualityControllerOptions = {}) {
    this.slowFrameMs = options.slowFrameMs ?? DEFAULTS.slowFrameMs;
    this.fastFrameMs = options.fastFrameMs ?? DEFAULTS.fastFrameMs;
    this.slowHoldMs = options.slowHoldMs ?? DEFAULTS.slowHoldMs;
    this.fastHoldMs = options.fastHoldMs ?? DEFAULTS.fastHoldMs;
    this.minChangeIntervalMs = options.minChangeIntervalMs ?? DEFAULTS.minChangeIntervalMs;
    this.windowMs = options.windowMs ?? DEFAULTS.windowMs;
  }

  /** Current quality level; 0 is full quality, `QUALITY_LADDER.length - 1` the floor. */
  get level(): number {
    return this.currentLevel;
  }

  /** Total frame time fed in so far, in milliseconds. */
  get elapsedMs(): number {
    return this.elapsedTotal;
  }

  reset(): void {
    this.samples.length = 0;
    this.windowTotal = 0;
    this.elapsedTotal = 0;
    this.slowAccum = 0;
    this.fastAccum = 0;
    this.lastChangeAt = Number.NEGATIVE_INFINITY;
    this.currentLevel = 0;
  }

  /**
   * Feeds one frame time. Returns true when the level changed, so the caller can
   * apply the new settings once rather than polling every frame.
   */
  sample(frameMs: number): boolean {
    if (!Number.isFinite(frameMs) || frameMs <= 0) {
      return false;
    }

    this.elapsedTotal += frameMs;
    this.samples.push(frameMs);
    this.windowTotal += frameMs;
    while (this.samples.length > 1 && this.windowTotal > this.windowMs) {
      const oldest = this.samples.shift();
      if (oldest === undefined) {
        break;
      }
      this.windowTotal -= oldest;
    }

    const average = this.windowTotal / this.samples.length;
    if (average > this.slowFrameMs) {
      this.slowAccum += frameMs;
      this.fastAccum = 0;
    } else if (average < this.fastFrameMs) {
      this.fastAccum += frameMs;
      this.slowAccum = 0;
    } else {
      this.slowAccum = 0;
      this.fastAccum = 0;
    }

    const canChange = this.elapsedTotal - this.lastChangeAt >= this.minChangeIntervalMs;
    if (!canChange) {
      return false;
    }

    if (this.slowAccum >= this.slowHoldMs && this.currentLevel < QUALITY_LADDER.length - 1) {
      this.currentLevel += 1;
      this.commit();
      return true;
    }
    if (this.fastAccum >= this.fastHoldMs && this.currentLevel > 0) {
      this.currentLevel -= 1;
      this.commit();
      return true;
    }
    return false;
  }

  /**
   * A change invalidates the measurement that produced it: the next frame times
   * describe the new settings, not the old ones. Clearing the window also means
   * one bad second can only cost one level.
   */
  private commit(): void {
    this.lastChangeAt = this.elapsedTotal;
    this.samples.length = 0;
    this.windowTotal = 0;
    this.slowAccum = 0;
    this.fastAccum = 0;
  }
}
