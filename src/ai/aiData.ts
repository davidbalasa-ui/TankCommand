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
    // Hard waits for a bigger first wave than Normal (and Normal's earlier, smaller attack breaks
    // on it), then rolls on: with 800 it traded evenly and Normal won as often as Hard.
    attackThresholdValue: 1000,
    reserveOre: 60,
    // A third miner costs the early army more than it earns back before the first fights: with
    // three, Hard lost every soak match to Normal.
    minersWanted: 2,
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

/** How far past its pad's rally point (toward the map centre) the AI parks units it sends home, m. */
export const HOME_PAST_RALLY = 8;

/**
 * How much one match's computer opponent differs from the next (drawn from the world seed, so a
 * replay or a save plays out the same). Every range is centred on the plain behaviour, so each
 * difficulty stays as strong on average.
 */
export const AI_VARIETY = {
  /** The attack threshold is scaled by a fresh factor in this range for every attack. */
  attackScaleMin: 0.8,
  attackScaleMax: 1.2,
  /** Per unit type preference in the army mix (a weight of 1.25 buys about a quarter more of it). */
  mixWeightMin: 0.8,
  mixWeightMax: 1.25,
  /** Chance an attack swings out round one side instead of going straight at the target. */
  flankChance: 2 / 3,
  /** Sideways offset of the flank waypoint, as a fraction of the distance to the target. */
  flankOffsetMin: 0.15,
  flankOffsetMax: 0.35,
  /** No flanking when the target is closer than this, m. */
  flankMinDistance: 40,
  /** A flank route may be at most this much longer than the direct route. */
  flankMaxDetour: 1.6,
  /** Targets count as comparable within this factor (plus the slack in metres) of the nearest. */
  targetSlackFactor: 1.3,
  targetSlackMetres: 10,
  /** Scout waypoints shift by up to this fraction of the map size. */
  scoutJitter: 0.06,
};
