import { ARMOR_MIN_DAMAGE_FRACTION, UPGRADE_FIRE_RATE_FACTOR } from './tuning';
import { SIM_TICK_HZ } from './constants';

const DT = 1 / SIM_TICK_HZ;
import type { WeaponStats } from './types';

/**
 * Each weapon fires in its own rhythm: a burst of `burst` shots spaced
 * `burstIntervalSec` apart, then a `reloadSec` pause before the next burst.
 * A single-shot weapon is just a burst of one. The fire-rate upgrade shortens
 * the reload only, never the spacing inside a burst, so a burst keeps its feel.
 */
export interface WeaponCycleState {
  reloadLeft: number;
  /** Shots still to come in the burst under way (0 between bursts). */
  burstLeft?: number;
}

export function burstSize(weapon: WeaponStats): number {
  return Math.max(1, Math.floor(weapon.burst ?? 1));
}

/** Seconds from the first shot of one burst to the first shot of the next (no upgrade). */
export function weaponCycleSec(weapon: WeaponStats): number {
  return (burstSize(weapon) - 1) * (weapon.burstIntervalSec ?? 0) + weapon.reloadSec;
}

/** True when the shot about to be fired is the last of its burst. */
export function isLastShotOfBurst(state: WeaponCycleState, weapon: WeaponStats): boolean {
  const left = state.burstLeft ?? 0;
  return left === 1 || (left === 0 && burstSize(weapon) === 1);
}

/** Call right after a shot: sets the wait before the next one. */
export function afterShot(state: WeaponCycleState, weapon: WeaponStats, fireRateUpgrade: boolean): void {
  const left = state.burstLeft ?? 0;
  state.burstLeft = left > 0 ? left - 1 : burstSize(weapon) - 1;
  if (state.burstLeft > 0) {
    state.reloadLeft = weapon.burstIntervalSec ?? 0;
  } else {
    state.reloadLeft = fireRateUpgrade ? weapon.reloadSec * UPGRADE_FIRE_RATE_FACTOR : weapon.reloadSec;
  }
}

/**
 * Damage after armor. Armor takes a flat amount off each hit, but never more
 * than (1 - ARMOR_MIN_DAMAGE_FRACTION) of it, so light rapid-fire guns still
 * scratch heavy armor instead of doing nothing.
 */
export function damageAfterArmor(damage: number, armor: number): number {
  return Math.max(1, damage * ARMOR_MIN_DAMAGE_FRACTION, damage - armor);
}

/** One tick off a reload timer. Float dust below a microsecond counts as ready, so 0.4 s is 8 ticks, not 9. */
export function tickReload(left: number): number {
  const next = left - DT;
  return next < 1e-6 ? 0 : next;
}

/**
 * Indirect-fire weapons (the Longbow's and the Mortar Beast's shells) lob their round onto the
 * aimed point: in the sim a miss bursts there instead of flying on, and the view draws the shell on
 * a ballistic arc.
 */
export function isArcingWeapon(kind: string | undefined): boolean {
  return kind === 'shell';
}
