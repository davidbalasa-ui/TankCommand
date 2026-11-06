import { SIM_TICK_HZ } from './constants';
import { addAlert, ensureSideStats } from './economy';
import { setOutcome } from './drops';
import type { Command } from './commands';
import type { PlayerId, ResearchNode, ResearchSideState, UpgradeKind, WorldState } from './types';

const DT = 1 / SIM_TICK_HZ;

function sideResearch(world: WorldState, player: PlayerId): ResearchSideState {
  const existing = world.research.find((side) => side.player === player);
  if (existing) {
    return existing;
  }
  const created: ResearchSideState = { player, done: [] };
  world.research.push(created);
  world.research.sort((a, b) => a.player - b.player);
  return created;
}

export function researchDone(world: WorldState, player: PlayerId): ReadonlySet<string> {
  return new Set(world.research.find((side) => side.player === player)?.done ?? []);
}

function factionOf(world: WorldState, player: PlayerId): string | null {
  return world.factions.find((entry) => entry.player === player)?.faction ?? null;
}

function nodesFor(world: WorldState, player: PlayerId): ResearchNode[] {
  const faction = factionOf(world, player);
  return [...world.researchTree.values()].filter((node) => faction === null || node.faction === faction);
}

// The first unfinished node that unlocks the item, or null when the item is free to use.
export function unlockingNode(
  world: WorldState,
  player: PlayerId,
  itemId: string,
): ResearchNode | null {
  const done = researchDone(world, player);
  const gating = nodesFor(world, player).filter((node) => node.unlocks.includes(itemId));
  if (gating.length === 0 || gating.some((node) => done.has(node.id))) {
    return null;
  }
  return gating[0] ?? null;
}

export function isItemUnlocked(world: WorldState, player: PlayerId, itemId: string): boolean {
  return unlockingNode(world, player, itemId) === null;
}

// An upgrade is available once a node granting it is done. Upgrades that no node grants stay free.
export function isUpgradeAvailable(
  world: WorldState,
  player: PlayerId,
  upgrade: UpgradeKind,
): boolean {
  const done = researchDone(world, player);
  const granting = nodesFor(world, player).filter((node) => node.upgrades.includes(upgrade));
  return granting.length === 0 || granting.some((node) => done.has(node.id));
}

export function researchRejection(
  world: WorldState,
  player: PlayerId,
  labId: number,
  nodeId: string,
): string | null {
  const lab = world.structures.find((item) => item.id === labId && item.owner === player && item.hp > 0);
  const type = lab ? world.structureTypes.get(lab.typeId) : undefined;
  if (!lab || type?.kind !== 'lab') {
    return 'noLab';
  }
  if (lab.research !== null || lab.work !== null) {
    return 'labBusy';
  }
  const node = nodesFor(world, player).find((item) => item.id === nodeId);
  if (!node) {
    return 'unknownNode';
  }
  const done = researchDone(world, player);
  if (done.has(node.id)) {
    return 'alreadyDone';
  }
  if (world.structures.some((item) => item.owner === player && item.research?.nodeId === nodeId)) {
    return 'alreadyResearching';
  }
  if (node.requires.some((req) => !done.has(req))) {
    return 'prerequisite';
  }
  const stats = ensureSideStats(world, player);
  if (stats.ore < node.cost.ore || stats.metal < node.cost.metal) {
    return 'unaffordable';
  }
  return null;
}

export function applyResearchCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'research' }>,
): void {
  const reason = researchRejection(world, command.issuer, command.labId, command.nodeId);
  if (reason) {
    setOutcome(world, command.tick, 'research', false, reason);
    return;
  }
  const lab = world.structures.find((item) => item.id === command.labId);
  const node = world.researchTree.get(command.nodeId);
  if (!lab || !node) {
    return;
  }
  const stats = ensureSideStats(world, command.issuer);
  stats.ore -= node.cost.ore;
  stats.metal -= node.cost.metal;
  lab.research = { nodeId: node.id, left: node.timeSec };
  setOutcome(world, command.tick, 'research', true, 'ok');
}

export function applyCancelResearchCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'cancelResearch' }>,
): void {
  const lab = world.structures.find(
    (item) => item.id === command.labId && item.owner === command.issuer && item.hp > 0,
  );
  const node = lab?.research ? world.researchTree.get(lab.research.nodeId) : undefined;
  if (!lab || !node) {
    setOutcome(world, command.tick, 'cancelResearch', false, 'nothingToCancel');
    return;
  }
  const stats = ensureSideStats(world, command.issuer);
  stats.ore += node.cost.ore;
  stats.metal += node.cost.metal;
  lab.research = null;
  setOutcome(world, command.tick, 'cancelResearch', true, 'ok');
}

export function updateResearch(world: WorldState): void {
  for (const lab of world.structures) {
    if (!lab.research || lab.hp <= 0) {
      continue;
    }
    lab.research.left = Math.max(0, lab.research.left - DT);
    if (lab.research.left > 0) {
      continue;
    }
    const side = sideResearch(world, lab.owner);
    if (!side.done.includes(lab.research.nodeId)) {
      side.done.push(lab.research.nodeId);
    }
    addAlert(world, 'researchDone', lab.owner, lab.x, lab.z);
    lab.research = null;
  }
}
