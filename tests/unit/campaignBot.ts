// A plain scripted player for campaign tests: mines, buys the best fighting unit it can, places
// tower kits round its pad, defends what it must keep, walks the army to each goal ring and then
// hunts down the enemy. It plays no better than an attentive beginner, so a mission it cannot win
// is too hard for its slot.
import { stepWithAi } from '../../src/ai/driver';
import { isFightingUnitType } from '../../src/sim/economy';
import { isHostile } from '../../src/sim/diplomacy';
import { isItemUnlocked } from '../../src/sim/research';
import { placementValidity } from '../../src/sim/spawn';
import { missionAllows, missionMarkers } from '../../src/sim/triggers';
import type { Command } from '../../src/sim/commands';
import type { Condition } from '../../src/sim/missionSchema';
import type { UnitState, WorldState } from '../../src/sim/types';

const THINK_EVERY = 40;
const DEFEND_RADIUS = 32;
const MAX_TOWERS = 3;

type Cmd = Command extends infer C ? (C extends Command ? Omit<C, 'tick' | 'issuer'> : never) : never;

function conditionsOf(cond: Condition, out: Condition[] = []): Condition[] {
  out.push(cond);
  if (cond.t === 'and' || cond.t === 'or') {
    cond.conds.forEach((c) => conditionsOf(c, out));
  } else if (cond.t === 'not') {
    conditionsOf(cond.cond, out);
  }
  return out;
}

export interface BotPlan {
  /** Ticks to gather the army at home before marching (unless a goal ring is waiting). */
  gatherTicks?: number;
  /** Army size to wait for before attacking an enemy that has a landing pad. */
  armySize?: number;
}

export function botCommands(w: WorldState, plan: BotPlan = {}): Command[] {
  if (w.tick % THINK_EVERY !== 1 || !w.mission) {
    return [];
  }
  const me = w.mission.humanSide;
  const out: Cmd[] = [];
  const mission = w.mission;
  const own = w.units.filter((u) => u.owner === me && u.hp > 0);
  const ownStructures = w.structures.filter((s) => s.owner === me && s.hp > 0);
  const pad = ownStructures.find((s) => w.structureTypes.get(s.typeId)?.kind === 'pad');
  const enemies = w.units.filter((u) => u.hp > 0 && u.owner !== me && isHostile(w, me, u.owner));
  const enemyStructures = w.structures.filter((s) => s.hp > 0 && s.owner !== me && isHostile(w, me, s.owner));

  // Units the mission wants kept safe or brought somewhere: never thrown into a fight.
  const triggers = mission.def.triggers.filter((t) => !mission.fired.includes(t.id));
  const escortTags = new Set<string>();
  const keepTags = new Set<string>();
  for (const t of mission.def.triggers) {
    for (const c of conditionsOf(t.when)) {
      if (c.t === 'unitEscorted') {
        escortTags.add(c.tag);
      }
      if (c.t === 'unitDestroyed' && t.do.some((a) => a.t === 'lose' || (a.t === 'setObjective' && a.status === 'failed'))) {
        keepTags.add(c.tag);
      }
    }
  }
  const protectedIds = new Set<number>();
  for (const tag of [...escortTags, ...keepTags]) {
    for (const id of mission.tags[tag] ?? []) {
      protectedIds.add(id);
    }
  }
  const ownProtected = own.filter((u) => protectedIds.has(u.id));

  // Economy.
  for (const u of own) {
    const type = w.unitTypes.get(u.typeId);
    if (type?.workerKind === 'oreMiner' && !u.job && u.order.kind === 'idle') {
      const ore = w.deposits
        .filter((d) => d.kind === 'ore' && d.amount > 0)
        .sort((a, b) => Math.hypot(a.x - u.x, a.z - u.z) - Math.hypot(b.x - u.x, b.z - u.z))[0];
      if (ore) {
        out.push({ kind: 'mine', unitIds: [u.id], depositId: ore.id });
      }
    }
  }

  // Shopping: a tower now and then while the mission allows them, otherwise the strongest tank.
  const stats = w.resources.find((r) => r.player === me);
  const faction = w.unitTypes.get(own[0]?.typeId ?? '')?.faction ?? (pad ? w.structureTypes.get(pad.typeId)?.faction : undefined);
  const busy = w.dropQueue.some((o) => o.owner === me);
  // Saving up is the objective: spend nothing.
  const saving = triggers.some((t) => conditionsOf(t.when).some((c) => c.t === 'resourceReached' && c.side === me));
  if (pad && stats && !busy && !saving) {
    const towers = ownStructures.filter((s) => w.structureTypes.get(s.typeId)?.kind === 'turret').length;
    const tower = [...w.structureTypes.values()].find(
      (t) => t.kind === 'turret' && t.faction === faction && missionAllows(w, me, t.id) && isItemUnlocked(w, me, t.id),
    );
    const tanks = [...w.unitTypes.values()]
      .filter(
        (t) =>
          t.faction === faction &&
          isFightingUnitType(t) &&
          (t.role === 'tank' || t.role === 'artillery') &&
          missionAllows(w, me, t.id) &&
          isItemUnlocked(w, me, t.id),
      )
      .sort((a, b) => b.oreCost - a.oreCost);
    const pendingKit = w.pendingKits.some((k) => k.owner === me);
    if (tower && towers < MAX_TOWERS && !pendingKit && enemyStructures.length === 0 && stats.ore >= tower.cost.ore) {
      out.push({ kind: 'buy', itemId: tower.id, padId: pad.id });
    } else {
      const tank = tanks.find((t) => stats.ore >= t.oreCost && stats.metal >= t.metalCost);
      if (tank) {
        out.push({ kind: 'buy', itemId: tank.id, padId: pad.id });
      }
    }
  }
  for (const kit of w.pendingKits.filter((k) => k.owner === me)) {
    const type = w.structureTypes.get(kit.structureTypeId);
    if (!type || !pad) {
      continue;
    }
    search: for (let ring = 0; ring < 6; ring += 1) {
      for (let step = 0; step < 16; step += 1) {
        const angle = (step / 16) * Math.PI * 2 + kit.id;
        const x = pad.x + Math.cos(angle) * (10 + ring * 4);
        const z = pad.z + Math.sin(angle) * (10 + ring * 4);
        if (placementValidity(w, me, type, x, z).valid) {
          out.push({ kind: 'placeKit', kitId: kit.id, x, z });
          break search;
        }
      }
    }
  }

  // The army.
  const army = own.filter((u) => {
    const type = w.unitTypes.get(u.typeId);
    return !protectedIds.has(u.id) && isFightingUnitType(type) && !type?.workerKind && !type?.deploysTo;
  });
  const ids = army.map((u) => u.id);
  const keep = [...ownStructures, ...ownProtected];
  const threat = enemies
    .map((e) => ({ e, d: Math.min(...keep.map((k) => Math.hypot(k.x - e.x, k.z - e.z))) }))
    .filter((item) => item.d < DEFEND_RADIUS)
    .sort((a, b) => a.d - b.d)[0]?.e;

  const markers = missionMarkers(mission);
  const escortGoal = triggers
    .flatMap((t) => conditionsOf(t.when))
    .find(
      (c): c is Extract<Condition, { t: 'unitEscorted' }> =>
        c.t === 'unitEscorted' && (mission.tags[c.tag] ?? []).some((id) => own.some((u) => u.id === id)),
    );
  const centre = (units: UnitState[]): { x: number; z: number } => ({
    x: units.reduce((s, u) => s + u.x, 0) / Math.max(1, units.length),
    z: units.reduce((s, u) => s + u.z, 0) / Math.max(1, units.length),
  });

  const enemyPad = enemyStructures.some((s) => w.structureTypes.get(s.typeId)?.kind === 'pad');
  const marching = army.some((u) => u.order.kind === 'attack');
  const ready = !enemyPad || marching || army.length >= (plan.armySize ?? 7);
  if (ids.length > 0) {
    if (threat) {
      out.push({ kind: 'attackMove', unitIds: ids, x: threat.x, z: threat.z });
    } else if (escortGoal) {
      // Clear the road a little ahead of the escorted units.
      const c = centre(ownProtected.length ? ownProtected : army);
      const dx = escortGoal.x - c.x;
      const dz = escortGoal.z - c.z;
      const d = Math.hypot(dx, dz) || 1;
      const ahead = Math.min(d, 14);
      out.push({ kind: 'attackMove', unitIds: ids, x: c.x + (dx / d) * ahead, z: c.z + (dz / d) * ahead });
    } else if (markers.length > 0) {
      const m = markers[0]!;
      out.push({ kind: 'attackMove', unitIds: ids, x: m.x, z: m.z });
    } else if (!ready && pad) {
      // An enemy that can rebuild is worth waiting for: gather a proper group by the pad first.
      out.push({ kind: 'attackMove', unitIds: ids, x: pad.x + 6, z: pad.z + 6 });
    } else if (w.tick >= (plan.gatherTicks ?? 0)) {
      const c = centre(army);
      const near = (p: { x: number; z: number }): number => Math.hypot(p.x - c.x, p.z - c.z);
      const foe = [...enemyStructures].sort((a, b) => near(a) - near(b))[0] ?? [...enemies].sort((a, b) => near(a) - near(b))[0];
      if (foe) {
        out.push({ kind: 'attack', unitIds: ids, targetId: foe.id });
      }
    }
  }

  // Escorted units trail the army; once the road is clear (no enemy close) they drive on.
  if (escortGoal) {
    const movers = own.filter((u) => (mission.tags[escortGoal.tag] ?? []).includes(u.id));
    const lead = army.length ? centre(army) : { x: escortGoal.x, z: escortGoal.z };
    const danger = enemies.some((e) => movers.some((u) => Math.hypot(e.x - u.x, e.z - u.z) < 25));
    if (movers.length && !danger) {
      const armyAtGoal = Math.hypot(lead.x - escortGoal.x, lead.z - escortGoal.z) < escortGoal.radius + 10;
      const goal = armyAtGoal || army.length === 0 ? escortGoal : lead;
      out.push({ kind: 'move', unitIds: movers.map((u) => u.id), x: goal.x, z: goal.z });
    } else if (movers.length && danger) {
      out.push({ kind: 'stop', unitIds: movers.map((u) => u.id) });
    }
  }

  return out.map((c) => ({ ...c, issuer: me, tick: w.tick + 1 }) as Command);
}

/** Play the mission to the end (or the tick cap). */
export function playMission(w: WorldState, maxTicks: number, plan: BotPlan = {}): WorldState {
  let world = w;
  while (!world.result && world.tick < maxTicks) {
    world = stepWithAi(world, botCommands(world, plan));
  }
  return world;
}
