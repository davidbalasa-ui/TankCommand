export interface FixedStepResult {
  steps: number;
  alpha: number;
}

export interface FixedStepOptions {
  tickHz: number;
  maxStepsPerFrame: number;
  step: () => void;
}

export class FixedStepLoop {
  private accumulator = 0;
  private readonly tickMs: number;
  private readonly maxSteps: number;
  private readonly opts: FixedStepOptions;

  constructor(opts: FixedStepOptions) {
    if (!(opts.tickHz > 0)) {
      throw new Error('tickHz must be greater than zero');
    }
    this.opts = opts;
    this.tickMs = 1000 / opts.tickHz;
    this.maxSteps = Math.max(1, Math.floor(opts.maxStepsPerFrame));
  }

  advance(elapsedMs: number): FixedStepResult {
    const elapsed = Number.isFinite(elapsedMs) && elapsedMs > 0 ? elapsedMs : 0;
    this.accumulator += elapsed;

    const rawSteps = Math.floor(this.accumulator / this.tickMs);
    let steps = rawSteps;
    if (rawSteps > this.maxSteps) {
      steps = this.maxSteps;
      this.accumulator = 0;
    } else {
      this.accumulator -= steps * this.tickMs;
    }

    for (let i = 0; i < steps; i += 1) {
      this.opts.step();
    }

    const alpha = Math.min(Math.max(this.accumulator / this.tickMs, 0), 0.999999);
    return { steps, alpha };
  }
}
