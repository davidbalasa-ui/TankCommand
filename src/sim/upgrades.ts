import { setOutcome } from './drops';
import { ensureSideStats } from './economy';
import { isUpgradeAvailable } from './research';
import { UPGRADE_ARMOR_BONUS, UPGRADE_COST_METAL, UPGRADE_COST_ORE, UPGRADE_FIRE_RATE_FACTOR } from './tuning';
import type { Command } from './commands';
import type { SimStructureType, SimUnitType, UnitState, UpgradeKind, WorldState } from './types';

export { UPGRADE_FIRE_RATE_FACTOR };

export function unitArmor(unit: UnitState, type: SimUnitType | undefined): number {
  return (type?.armor ?? 0) + (unit.upgrades.includes('armor') ? UPGRADE_ARMOR_BONUS : 0);
}

export function structureArmor(
  upgrades: readonly string[],
  type: SimStructureType,
): number {
  return type.armor + (upgrades.includes('armor') ? UPGRADE_ARMOR_BONUS : 0);
}

export function reloadSeconds(unit: UnitState, base: number): number {
  return unit.upgrades.includes('fireRate') ? base * UPGRADE_FIRE_RATE_FACTOR : base;
}

export function upgradeRejection(
  world: WorldState,
  player: number,
  targetId: number,
  upgrade: UpgradeKind,
): string | null {
  const unit = world.units.find((item) => item.id === targetId && item.owner === player && item.hp > 0);
  const structure = unit
    ? undefined
    : world.structures.find((item) => item.id === targetId && item.owner === player && item.hp > 0);
  const upgrades = unit ? unit.upgrades : structure?.upgrades;
  const allowed = unit
    ? world.unitTypes.get(unit.typeId)?.upgrades
    : structure
      ? world.structureTypes.get(structure.typeId)?.upgrades
      : undefined;
  if (!upgrades || !allowed) {
    return 'unknownTarget';
  }
  if (!allowed.includes(upgrade)) {
    return 'notAvailable';
  }
  if (upgrades.includes(upgrade)) {
    return 'alreadyHave';
  }
  if (!isUpgradeAvailable(world, player, upgrade)) {
    return 'notResearched';
  }
  const stats = ensureSideStats(world, player);
  if (stats.ore < UPGRADE_COST_ORE || stats.metal < UPGRADE_COST_METAL) {
    return 'unaffordable';
  }
  return null;
}

export function applyUpgradeCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'upgrade' }>,
): void {
  const reason = upgradeRejection(world, command.issuer, command.targetId, command.upgrade);
  if (reason) {
    setOutcome(world, command.tick, 'upgrade', false, reason);
    return;
  }
  const unit = world.units.find((item) => item.id === command.targetId);
  const target = unit ?? world.structures.find((item) => item.id === command.targetId);
  if (!target) {
    return;
  }
  const stats = ensureSideStats(world, command.issuer);
  stats.ore -= UPGRADE_COST_ORE;
  stats.metal -= UPGRADE_COST_METAL;
  target.upgrades.push(command.upgrade);
  setOutcome(world, command.tick, 'upgrade', true, 'ok');
}
