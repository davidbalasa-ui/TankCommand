/**
 * Research (overhaul step 4). Each side researches one thing at a time, alongside its drops, with
 * no building needed: research is ordered straight from the locked card of the item it unlocks.
 * Tapping a card whose research needs a parent queues both ("Sensors, then Aviation"); each step
 * is paid when it starts, and a step that can't be afforded yet waits at the head of the queue.
 *
 * The lab is now only a campaign building (missions defend or destroy one); it is not required.
 */
import { SIM_TICK_HZ } from './constants';
import { addAlert, ensureSideStats } from './economy';
import { setOutcome } from './drops';
import type { Command } from './commands';
import type { PlayerId, ResearchNode, ResearchSideState, UpgradeKind, WorldState } from './types';

const DT = 1 / SIM_TICK_HZ;

/**
 * Research ids from before the step-4 tree, mapped to the new nodes that grant at least as much.
 * Used to convert old saves and old mission data.
 */
export const OLD_RESEARCH_IDS: Readonly<Record<string, string[]>> = {
  armor_plating: ['fortifications'],
  fire_control: ['missiles'],
  disc_flight: ['aviation'],
  // Aviation used to unlock the hover tank / glider too; that is Hover Drive now.
  aviation: ['aviation', 'hover_drive'],
};

/** Rewrites old research ids (research.<faction>.<name>) to the current tree, dropping duplicates. */
export function convertResearchIds(ids: readonly string[]): string[] {
  const out: string[] = [];
  for (const id of ids) {
    const match = /^research\.([a-z0-9]+)\.([a-z0-9_]+)$/.exec(id);
    const mapped = match && OLD_RESEARCH_IDS[match[2] ?? ''];
    const next = mapped ? mapped.map((name) => `research.${match[1]}.${name}`) : [id];
    for (const item of next) {
      if (!out.includes(item)) {
        out.push(item);
      }
    }
  }
  return out;
}

/**
 * Reads saved research. Saves from before step 4 have no active/queue fields, use the old ids, and
 * keep a running research on the lab structure; it becomes the side's active step.
 */
export function loadResearchSides(input: unknown, structures: unknown): ResearchSideState[] {
  const sides: ResearchSideState[] = Array.isArray(input)
    ? (input as Array<Partial<ResearchSideState> & { player: PlayerId }>).map((side) => ({
        player: side.player,
        done: convertResearchIds(Array.isArray(side.done) ? side.done : []),
        active: side.active ? { ...side.active } : null,
        queue: Array.isArray(side.queue) ? [...side.queue] : [],
      }))
    : [];
  if (Array.isArray(structures)) {
    for (const item of structures as Array<{ owner: PlayerId; research?: { nodeId: string; left: number } | null }>) {
      if (!item.research) {
        continue;
      }
      let side = sides.find((entry) => entry.player === item.owner);
      if (!side) {
        side = { player: item.owner, done: [], active: null, queue: [] };
        sides.push(side);
      }
      const nodeId = convertResearchIds([item.research.nodeId])[0];
      if (side.active === null && nodeId && !side.done.includes(nodeId)) {
        side.active = { nodeId, left: item.research.left };
      }
    }
  }
  return sides.sort((a, b) => a.player - b.player);
}

export function sideResearch(world: WorldState, player: PlayerId): ResearchSideState {
  const existing = world.research.find((side) => side.player === player);
  if (existing) {
    return existing;
  }
  const created: ResearchSideState = { player, done: [], active: null, queue: [] };
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

/**
 * The research steps still needed to finish `nodeId`, parents first and the node itself last
 * (empty when it is done). Null when the node is unknown for this side.
 */
export function researchPlan(world: WorldState, player: PlayerId, nodeId: string): ResearchNode[] | null {
  const nodes = new Map(nodesFor(world, player).map((node) => [node.id, node]));
  if (!nodes.has(nodeId)) {
    return null;
  }
  const done = researchDone(world, player);
  const plan: ResearchNode[] = [];
  const visit = (id: string, depth: number): void => {
    const node = nodes.get(id);
    if (!node || done.has(id) || plan.includes(node) || depth > 8) {
      return;
    }
    for (const req of node.requires) {
      visit(req, depth + 1);
    }
    plan.push(node);
  };
  visit(nodeId, 0);
  return plan;
}

/** What this side is researching now and what waits after it. */
export function researchStatus(
  world: WorldState,
  player: PlayerId,
): { active: { node: ResearchNode; left: number } | null; queue: ResearchNode[] } {
  const side = world.research.find((item) => item.player === player);
  const activeNode = side?.active ? world.researchTree.get(side.active.nodeId) : undefined;
  return {
    active: side?.active && activeNode ? { node: activeNode, left: side.active.left } : null,
    queue: (side?.queue ?? [])
      .map((id) => world.researchTree.get(id))
      .filter((node): node is ResearchNode => node !== undefined),
  };
}

export function researchRejection(world: WorldState, player: PlayerId, nodeId: string): string | null {
  const plan = researchPlan(world, player, nodeId);
  if (plan === null) {
    return 'unknownNode';
  }
  if (plan.length === 0) {
    return 'alreadyDone';
  }
  const side = world.research.find((item) => item.player === player);
  if (side && (side.active?.nodeId === nodeId || side.queue.includes(nodeId))) {
    return 'alreadyResearching';
  }
  if (side && (side.active !== null || side.queue.length > 0)) {
    return 'researchBusy';
  }
  const first = plan[0];
  const stats = ensureSideStats(world, player);
  if (!first || stats.ore < first.cost.ore || stats.metal < first.cost.metal) {
    return 'unaffordable';
  }
  return null;
}

export function applyResearchCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'research' }>,
): void {
  const reason = researchRejection(world, command.issuer, command.nodeId);
  const plan = researchPlan(world, command.issuer, command.nodeId);
  const first = plan?.[0];
  if (reason || !plan || !first) {
    setOutcome(world, command.tick, 'research', false, reason ?? 'unknownNode');
    return;
  }
  const side = sideResearch(world, command.issuer);
  const stats = ensureSideStats(world, command.issuer);
  stats.ore -= first.cost.ore;
  stats.metal -= first.cost.metal;
  side.active = { nodeId: first.id, left: first.timeSec };
  side.queue = plan.slice(1).map((node) => node.id);
  setOutcome(world, command.tick, 'research', true, 'ok');
}

/** Stops this side's research: the running step is refunded in full and the queue is dropped. */
export function applyCancelResearchCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'cancelResearch' }>,
): void {
  const side = world.research.find((item) => item.player === command.issuer);
  if (!side || (side.active === null && side.queue.length === 0)) {
    setOutcome(world, command.tick, 'cancelResearch', false, 'nothingToCancel');
    return;
  }
  const node = side.active ? world.researchTree.get(side.active.nodeId) : undefined;
  if (node) {
    const stats = ensureSideStats(world, command.issuer);
    stats.ore += node.cost.ore;
    stats.metal += node.cost.metal;
  }
  side.active = null;
  side.queue = [];
  setOutcome(world, command.tick, 'cancelResearch', true, 'ok');
}

// Where a side's "research done" alert points: a lab if it has one, else its first pad.
function alertSpot(world: WorldState, player: PlayerId): { x: number; z: number } {
  const own = world.structures.filter((item) => item.owner === player && item.hp > 0);
  const kind = (id: string): string | undefined => world.structureTypes.get(id)?.kind;
  const spot = own.find((item) => kind(item.typeId) === 'lab') ?? own.find((item) => kind(item.typeId) === 'pad') ?? own[0];
  return spot ? { x: spot.x, z: spot.z } : { x: 0, z: 0 };
}

export function updateResearch(world: WorldState): void {
  for (const side of world.research) {
    if (side.active) {
      side.active.left = Math.max(0, side.active.left - DT);
      if (side.active.left > 0) {
        continue;
      }
      if (!side.done.includes(side.active.nodeId)) {
        side.done.push(side.active.nodeId);
      }
      const spot = alertSpot(world, side.player);
      addAlert(world, 'researchDone', side.player, spot.x, spot.z);
      side.active = null;
    }
    // Start the next queued step once it is affordable (it waits at the head until then).
    while (side.queue.length > 0) {
      const next = world.researchTree.get(side.queue[0] ?? '');
      if (!next || side.done.includes(next.id)) {
        side.queue.shift();
        continue;
      }
      const stats = ensureSideStats(world, side.player);
      if (stats.ore >= next.cost.ore && stats.metal >= next.cost.metal) {
        stats.ore -= next.cost.ore;
        stats.metal -= next.cost.metal;
        side.active = { nodeId: next.id, left: next.timeSec };
        side.queue.shift();
      }
      break;
    }
  }
}
