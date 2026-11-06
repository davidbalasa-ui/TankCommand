import type { AiDifficulty } from '../sim/types';

// Difficulty data. Every value is a placeholder until Stage 0. No difficulty gets a resource bonus.
export interface AiDifficultyData {
  strategicEveryTicks: number;
  attackThresholdValue: number;
  reserveOre: number;
  minersWanted: number;
  focusFire: boolean;
  retreatLossFraction: number;
  fightersPerTurret: number;
  useLab: boolean;
  maxStations: number;
  defends: boolean;
}

export const AI_DATA: Record<AiDifficulty, AiDifficultyData> = {
  easy: {
    strategicEveryTicks: 100,
    attackThresholdValue: 1500,
    reserveOre: 0,
    minersWanted: 1,
    focusFire: false,
    retreatLossFraction: 0.6,
    fightersPerTurret: 99,
    useLab: false,
    maxStations: 1,
    defends: false,
  },
  normal: {
    strategicEveryTicks: 40,
    attackThresholdValue: 900,
    reserveOre: 40,
    minersWanted: 2,
    focusFire: true,
    retreatLossFraction: 0.6,
    fightersPerTurret: 5,
    useLab: true,
    maxStations: 2,
    defends: true,
  },
  hard: {
    strategicEveryTicks: 30,
    attackThresholdValue: 800,
    reserveOre: 60,
    minersWanted: 3,
    focusFire: true,
    retreatLossFraction: 0.7,
    fightersPerTurret: 4,
    useLab: true,
    maxStations: 2,
    defends: true,
  },
};

export const TACTICAL_EVERY_TICKS = 2;
export const RETREAT_HP_FRACTION = 0.3;
export const DEFEND_RADIUS = 35;
export const KIT_RING_RADIUS = 16;
export const UNIT_ORDER_PERIOD = 10; // a unit gets at most one tactical order per 10 tactical steps
