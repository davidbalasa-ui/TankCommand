import { SIM_SPEED_FAST, SIM_SPEED_NORMAL, SIM_SPEED_SLOW } from '../sim/tuning';

export type SpeedId = 'slow' | 'normal' | 'fast';

export interface SpeedOption {
  id: SpeedId;
  multiplier: number;
  label: string;
}

export const SPEED_OPTIONS: readonly SpeedOption[] = [
  { id: 'slow', multiplier: SIM_SPEED_SLOW, label: 'Slow' },
  { id: 'normal', multiplier: SIM_SPEED_NORMAL, label: 'Normal' },
  { id: 'fast', multiplier: SIM_SPEED_FAST, label: 'Fast' },
];

const FALLBACK: SpeedOption = { id: 'normal', multiplier: 1, label: 'Normal' };

export class GameSpeed {
  private index = 1;

  get current(): SpeedOption {
    return SPEED_OPTIONS[this.index] ?? FALLBACK;
  }

  get multiplier(): number {
    return this.current.multiplier;
  }

  get label(): string {
    return this.current.label;
  }

  set(id: SpeedId): void {
    const index = SPEED_OPTIONS.findIndex((option) => option.id === id);
    if (index >= 0) {
      this.index = index;
    }
  }

  setMultiplier(multiplier: number): void {
    let bestIndex = this.index;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let index = 0; index < SPEED_OPTIONS.length; index += 1) {
      const option = SPEED_OPTIONS[index];
      if (!option) {
        continue;
      }
      const distance = Math.abs(option.multiplier - multiplier);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    }
    this.index = bestIndex;
  }

  cycle(): SpeedOption {
    this.index = (this.index + 1) % SPEED_OPTIONS.length;
    return this.current;
  }
}
