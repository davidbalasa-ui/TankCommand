import { isAllied } from './diplomacy';
import { SIM_TICK_HZ } from './constants';
import { setOutcome } from './drops';
import type { Command } from './commands';
import type { WorldState } from './types';

const DT = 1 / SIM_TICK_HZ;

// Repair vehicles heal friendly units and structures in range, never above max hit points.
export function updateRepair(world: WorldState): void {
  for (const medic of world.units) {
    const type = world.unitTypes.get(medic.typeId);
    if (medic.hp <= 0 || !type?.repair || medic.transform) {
      continue;
    }
    const { radius, ratePerSec, unitsOnly } = type.repair;
    const amount = ratePerSec * DT;
    for (const unit of world.units) {
      if (unit.id === medic.id || !isAllied(world, medic.owner, unit.owner) || unit.hp <= 0) {
        continue;
      }
      const max = world.unitTypes.get(unit.typeId)?.hp ?? unit.hp;
      if (unit.hp < max && Math.hypot(unit.x - medic.x, unit.z - medic.z) <= radius) {
        unit.hp = Math.min(max, unit.hp + amount);
      }
    }
    for (const structure of unitsOnly ? [] : world.structures) {
      if (!isAllied(world, medic.owner, structure.owner) || structure.hp <= 0) {
        continue;
      }
      const max = world.structureTypes.get(structure.typeId)?.hp ?? structure.hp;
      if (structure.hp < max && Math.hypot(structure.x - medic.x, structure.z - medic.z) <= radius) {
        structure.hp = Math.min(max, structure.hp + amount);
      }
    }
  }
}

// Resolves a repair order into a destination and the repair vehicles that should drive there;
// the world step turns it into a normal move command.
export function resolveRepairCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'repair' }>,
): { x: number; z: number; unitIds: number[] } | null {
  const target =
    world.units.find((item) => item.id === command.targetId && item.owner === command.issuer && item.hp > 0) ??
    world.structures.find((item) => item.id === command.targetId && item.owner === command.issuer && item.hp > 0);
  const unitIds = world.units
    .filter(
      (item) =>
        command.unitIds.includes(item.id) &&
        item.owner === command.issuer &&
        item.hp > 0 &&
        world.unitTypes.get(item.typeId)?.repair,
    )
    .map((item) => item.id);
  if (!target || unitIds.length === 0) {
    setOutcome(world, command.tick, 'repair', false, target ? 'noRepairUnit' : 'unknownTarget');
    return null;
  }
  setOutcome(world, command.tick, 'repair', true, 'ok');
  return { x: target.x, z: target.z, unitIds };
}
