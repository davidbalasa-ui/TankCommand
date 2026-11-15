import { SIM_TICK_HZ } from './constants';
import type {
  DiplomacyRelation,
  PlayerId,
  RelationState,
  SideState,
  WorldState,
} from './types';

// Every "is this an enemy" decision in the sim, AI, fog and UI goes through these queries.

export const MAX_SIDES = 8;

export function sideOf(world: WorldState, player: PlayerId): SideState | undefined {
  return world.sides.find((side) => side.player === player);
}

export function isCompetitor(side: SideState | undefined): boolean {
  return side?.controller === 'human' || side?.controller === 'ai';
}

export function defaultSide(player: PlayerId): SideState {
  return {
    player,
    controller: player === 1 ? 'human' : 'ai',
    team: player,
    groupId: null,
    provokable: true,
    forgiveAfterSec: null,
  };
}

export function defaultRelation(world: WorldState, a: PlayerId, b: PlayerId): DiplomacyRelation {
  if (a === b) {
    return 'allied';
  }
  const sideA = sideOf(world, a) ?? defaultSide(a);
  const sideB = sideOf(world, b) ?? defaultSide(b);
  if (sideA.team === sideB.team) {
    return 'allied';
  }
  if (!isCompetitor(sideA) || !isCompetitor(sideB)) {
    return 'neutral';
  }
  return 'hostile';
}

function entry(world: WorldState, a: PlayerId, b: PlayerId): RelationState | undefined {
  return world.relations.find((item) => item.a === a && item.b === b);
}

export function relation(world: WorldState, a: PlayerId, b: PlayerId): DiplomacyRelation {
  if (a === b) {
    return 'allied';
  }
  return entry(world, a, b)?.relation ?? defaultRelation(world, a, b);
}

export function isHostile(world: WorldState, a: PlayerId, b: PlayerId): boolean {
  return relation(world, a, b) === 'hostile';
}

export function isAllied(world: WorldState, a: PlayerId, b: PlayerId): boolean {
  return relation(world, a, b) === 'allied';
}

// Rebuild the full table of ordered pairs from the sides, keeping explicit overrides.
export function buildRelations(
  world: WorldState,
  overrides: ReadonlyArray<{ a: PlayerId; b: PlayerId; relation: DiplomacyRelation }>,
): void {
  const relations: RelationState[] = [];
  for (const a of world.players) {
    for (const b of world.players) {
      if (a === b) {
        continue;
      }
      const override = overrides.find((item) => item.a === a && item.b === b);
      relations.push({
        a,
        b,
        relation: override?.relation ?? defaultRelation(world, a, b),
        forgiveLeft: null,
      });
    }
  }
  world.relations = relations;
}

function setDirected(
  world: WorldState,
  a: PlayerId,
  b: PlayerId,
  value: DiplomacyRelation,
  forgiveLeft: number | null,
): void {
  if (a === b) {
    return;
  }
  const found = entry(world, a, b);
  if (found) {
    found.relation = value;
    found.forgiveLeft = forgiveLeft;
    return;
  }
  world.relations.push({ a, b, relation: value, forgiveLeft });
  world.relations.sort((x, y) => x.a - y.a || x.b - y.b);
}

export function setRelation(
  world: WorldState,
  a: PlayerId,
  b: PlayerId,
  value: DiplomacyRelation,
  oneWay = false,
): void {
  setDirected(world, a, b, value, null);
  if (!oneWay) {
    setDirected(world, b, a, value, null);
  }
}

// A neutral side's unit or structure was damaged by `attacker`: that neutral side (and its group)
// turns hostile toward the attacker only. Allies of the attacker are left alone.
export function provoke(world: WorldState, victim: PlayerId, attacker: PlayerId): void {
  if (victim === attacker || relation(world, victim, attacker) !== 'neutral') {
    return;
  }
  const side = sideOf(world, victim);
  if (!side || !side.provokable || isCompetitor(side)) {
    return;
  }
  const group = side.groupId === null ? [victim] : world.sides.filter((item) => item.groupId === side.groupId).map((item) => item.player);
  for (const member of group) {
    const memberSide = sideOf(world, member);
    const forgive =
      memberSide?.forgiveAfterSec === null || memberSide === undefined
        ? null
        : Math.round(memberSide.forgiveAfterSec * SIM_TICK_HZ);
    if (relation(world, member, attacker) === 'neutral') {
      setDirected(world, member, attacker, 'hostile', forgive);
      setDirected(world, attacker, member, 'hostile', forgive);
    }
  }
}

// Called when a victim was hurt: keeps forgiveness timers fresh while the fight continues.
export function touchProvocation(world: WorldState, victim: PlayerId, attacker: PlayerId): void {
  const found = entry(world, victim, attacker);
  const side = sideOf(world, victim);
  if (found && found.forgiveLeft !== null && side?.forgiveAfterSec) {
    const refreshed = Math.round(side.forgiveAfterSec * SIM_TICK_HZ);
    found.forgiveLeft = refreshed;
    const reverse = entry(world, attacker, victim);
    if (reverse) {
      reverse.forgiveLeft = refreshed;
    }
  }
}

export function updateDiplomacy(world: WorldState): void {
  for (const item of world.relations) {
    if (item.forgiveLeft === null) {
      continue;
    }
    item.forgiveLeft -= 1;
    if (item.forgiveLeft <= 0) {
      item.forgiveLeft = null;
      item.relation = defaultRelation(world, item.a, item.b);
    }
  }
}
