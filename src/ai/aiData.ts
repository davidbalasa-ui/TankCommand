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
  /** Researches new units and towers (one at a time, like the player). */
  research: boolean;
  maxStations: number;
  defends: boolean;
  // Air: build an air base once the army has this many fighting units (0 = never use aircraft).
  airBaseAfterFighters: number;
  // Aircraft launch together once this many are parked and ready.
  airStrikeSize: number;
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
    research: false,
    maxStations: 1,
    defends: false,
    airBaseAfterFighters: 0,
    airStrikeSize: 2,
  },
  normal: {
    strategicEveryTicks: 40,
    attackThresholdValue: 700,
    reserveOre: 40,
    minersWanted: 2,
    focusFire: true,
    retreatLossFraction: 0.6,
    fightersPerTurret: 5,
    research: true,
    maxStations: 2,
    defends: true,
    airBaseAfterFighters: 5,
    airStrikeSize: 2,
  },
  hard: {
    strategicEveryTicks: 30,
    attackThresholdValue: 800,
    reserveOre: 60,
    minersWanted: 3,
    focusFire: true,
    retreatLossFraction: 0.7,
    fightersPerTurret: 4,
    research: true,
    maxStations: 2,
    defends: true,
    airBaseAfterFighters: 4,
    airStrikeSize: 2,
  },
};

// The order the computer researches in (node names without the faction): the units it fights with
// first, then towers, sensors and air.
export const AI_RESEARCH_ORDER = [
  'missiles',
  'heavy_armor',
  'fortifications',
  'hover_drive',
  'heavy_ordnance',
  'sensors',
  'field_repair',
  'aviation',
];

export const TACTICAL_EVERY_TICKS = 2;
export const RETREAT_HP_FRACTION = 0.3;
export const DEFEND_RADIUS = 35;
export const KIT_RING_RADIUS = 16;
export const UNIT_ORDER_PERIOD = 10; // a unit gets at most one tactical order per 10 tactical steps
