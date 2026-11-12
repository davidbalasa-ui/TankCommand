// A plain scripted player for campaign tests: mines, buys the best fighting unit it can, places
// tower kits round its pad, defends what it must keep, walks the army to each goal ring and then
// hunts down the enemy. It plays no better than an attentive beginner, so a mission it cannot win
// is too hard for its slot.
import { stepWithAi } from '../../src/ai/driver';
import { isFightingUnitType } from '../../src/sim/economy';
import { isHostile } from '../../src/sim/diplomacy';
import { hasFreeAirSlot } from '../../src/sim/air';
import { isItemUnlocked, researchDone } from '../../src/sim/research';
import { PAD_RALLY_DISTANCE, padLayout } from '../../src/sim/pad';
import { placementValidity } from '../../src/sim/spawn';
import { missionAllows, missionMarkers } from '../../src/sim/triggers';
import type { Command } from '../../src/sim/commands';
import type { Condition } from '../../src/sim/missionSchema';
import type { UnitState, WorldState } from '../../src/sim/types';

const THINK_EVERY = 40;
const DEFEND_RADIUS = 32;
/** Enemy fighters this close to the army's centre are dealt with before anything else. */
const FIELD_RADIUS = 30;
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

const RESEARCH_SAVINGS = 250;

export interface BotPlan {
  /** Ticks to gather the army at home before marching (unless a goal ring is waiting). */
  gatherTicks?: number;
  /** Army size to wait for before attacking an enemy that has a landing pad. */
  armySize?: number;
  /** How far past the pad's exit edge the army gathers at home (default: the rally point). */
  gatherOffEdge?: number;
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
  const keep = [...ownStructures, ...ownProtected];
  const threat = enemies
    .map((e) => ({ e, d: Math.min(...keep.map((k) => Math.hypot(k.x - e.x, k.z - e.z))) }))
    .filter((item) => item.d < DEFEND_RADIUS)
    .sort((a, b) => a.d - b.d)[0]?.e;

  // Economy.
  for (const u of own) {
    const type = w.unitTypes.get(u.typeId);
    // A miner whose site ran dry waits for orders (the 'mine empty' alert); send it to the next one.
    const dry = u.job?.kind === 'oreMiner' && u.job.reportedEmpty === true;
    if (type?.workerKind === 'oreMiner' && (!u.job || dry) && u.order.kind === 'idle') {
      const ore = w.deposits
        .filter((d) => d.kind === 'ore' && d.amount > 0)
        .sort((a, b) => Math.hypot(a.x - u.x, a.z - u.z) - Math.hypot(b.x - u.x, b.z - u.z))[0];
      if (ore) {
        out.push({ kind: 'mine', unitIds: [u.id], depositId: ore.id });
      }
    }
  }

  // Shopping. Structures an objective asks for come first, then a tower now and then while the
  // mission allows them, otherwise the strongest tank.
  const stats = w.resources.find((r) => r.player === me);
  const faction = w.unitTypes.get(own[0]?.typeId ?? '')?.faction ?? (pad ? w.structureTypes.get(pad.typeId)?.faction : undefined);
  const busy = w.dropQueue.some((o) => o.owner === me);
  const open = triggers.flatMap((t) => conditionsOf(t.when));
  // Saving up is the objective: spend nothing.
  const saving = open.some((c) => c.t === 'resourceReached' && c.side === me);
  const usable = (id: string): boolean => missionAllows(w, me, id) && isItemUnlocked(w, me, id);
  const built = (c: Extract<Condition, { t: 'structureBuilt' }>): number =>
    ownStructures.filter(
      (s) =>
        s.typeId === c.structureType &&
        (c.radius === undefined || Math.hypot(s.x - (c.x ?? 0), s.z - (c.z ?? 0)) <= c.radius),
    ).length;
  const wanted = open.filter(
    (c): c is Extract<Condition, { t: 'structureBuilt' }> =>
      c.t === 'structureBuilt' && c.side === me && built(c) < (c.count ?? 1) && usable(c.structureType),
  );
  // Research needs a lab, and a lab's research needs metal: a station and a hauler.
  const researching = open.some((c) => c.t === 'researchDone' && c.side === me);
  const lab = ownStructures.find((s) => w.structureTypes.get(s.typeId)?.kind === 'lab');
  const station = ownStructures.find((s) => w.structureTypes.get(s.typeId)?.kind === 'metalStation');
  const needs: string[] = wanted.map((c) => c.structureType);
  if (researching && faction) {
    if (!lab) {
      needs.push(`structure.${faction}.lab`);
    }
    if (!station) {
      needs.push(`structure.${faction}.metal_station`);
    }
  }
  const kitsComing = new Set([
    ...w.pendingKits.filter((k) => k.owner === me).map((k) => k.structureTypeId),
    ...w.dropQueue.filter((o) => o.owner === me).map((o) => o.itemId),
  ]);
  const need = needs.find((id) => !kitsComing.has(id) && usable(id));
  if (pad && stats && !busy && !saving) {
    const towers = ownStructures.filter((s) => w.structureTypes.get(s.typeId)?.kind === 'turret').length;
    const tower = [...w.structureTypes.values()].find((t) => t.kind === 'turret' && t.faction === faction && usable(t.id));
    // Against aircraft, guns that can hit them come first.
    const enemyAir = enemies.some((u) => u.air !== null);
    const hitsAir = (t: { weapon: { targets?: readonly string[] } | null }): number =>
      t.weapon?.targets?.includes('air') ? 1 : 0;
    const tanks = [...w.unitTypes.values()]
      .filter(
        (t) =>
          t.faction === faction &&
          isFightingUnitType(t) &&
          (t.role === 'tank' || t.role === 'artillery' || (t.role === 'air' && hasFreeAirSlot(w, me))) &&
          usable(t.id),
      )
      .sort((a, b) => (enemyAir ? hitsAir(b) - hitsAir(a) : 0) || b.oreCost - a.oreCost);
    const pendingKit = w.pendingKits.some((k) => k.owner === me);
    const needType = need ? w.structureTypes.get(need) : undefined;
    // A second miner and a hauler for each miner, as soon as the mission sells them.
    const workerOf = (kind: string) =>
      [...w.unitTypes.values()].find((t) => t.faction === faction && t.workerKind === kind && usable(t.id));
    const minerType = workerOf('oreMiner');
    const tugType = workerOf('tug');
    const minerCount = own.filter((u) => w.unitTypes.get(u.typeId)?.workerKind === 'oreMiner').length;
    const tugCount = own.filter((u) => w.unitTypes.get(u.typeId)?.workerKind === 'tug').length;
    const worker = minerType && minerCount < 2 && minerCount <= tugCount ? minerType : tugType && tugCount < minerCount ? tugType : null;
    if (needType) {
      if (stats.ore >= needType.cost.ore) {
        out.push({ kind: 'buy', itemId: needType.id, padId: pad.id });
      }
    } else if (worker && !threat && stats.ore >= worker.oreCost) {
      out.push({ kind: 'buy', itemId: worker.id, padId: pad.id });
    } else if (tower && towers < MAX_TOWERS && !pendingKit && enemyStructures.length === 0 && stats.ore >= tower.cost.ore) {
      out.push({ kind: 'buy', itemId: tower.id, padId: pad.id });
    } else {
      // While a research goal waits on a free lab, keep enough ore back to start it.
      const saving = lab && researching && !lab.research ? RESEARCH_SAVINGS : 0;
      const tank = tanks.find((t) => stats.ore >= t.oreCost + saving && stats.metal >= t.metalCost);
      if (tank) {
        out.push({ kind: 'buy', itemId: tank.id, padId: pad.id });
      }
    }
  }
  if (lab && researching && !lab.research && stats) {
    const done = researchDone(w, me);
    const goal = open.find((c): c is Extract<Condition, { t: 'researchDone' }> => c.t === 'researchDone' && c.side === me);
    const node = [...w.researchTree.values()]
      .filter((n) => n.id.startsWith(`research.${faction}.`) && !done.has(n.id) && n.requires.every((r) => done.has(r)))
      .filter((n) => !goal?.node || n.id === goal.node)
      .sort((a, b) => a.cost.ore + a.cost.metal * 3 - (b.cost.ore + b.cost.metal * 3))[0];
    if (node && stats.ore >= node.cost.ore && stats.metal >= node.cost.metal) {
      out.push({ kind: 'research', labId: lab.id, nodeId: node.id });
    }
  }
  const stations = ownStructures.filter((s) => w.structureTypes.get(s.typeId)?.kind === 'metalStation');
  const tugs = own.filter((u) => w.unitTypes.get(u.typeId)?.workerKind === 'tug' && !u.job && u.order.kind === 'idle');
  // Haulers carry the miners' ore by themselves; only spare ones go to the metal stations.
  const miners = own.filter((u) => w.unitTypes.get(u.typeId)?.workerKind === 'oreMiner').length;
  const allTugs = own.filter((u) => w.unitTypes.get(u.typeId)?.workerKind === 'tug').length;
  tugs.slice(0, Math.max(0, allTugs - miners)).forEach((tug, index) => {
    const target = stations[index % Math.max(1, stations.length)];
    if (target && !protectedIds.has(tug.id)) {
      out.push({ kind: 'assign', unitIds: [tug.id], stationId: target.id });
    }
  });
  for (const kit of w.pendingKits.filter((k) => k.owner === me)) {
    const type = w.structureTypes.get(kit.structureTypeId);
    if (!type || !pad) {
      continue;
    }
    if (type.buildOnMetalDeposit) {
      // Goal rings first, then the deposit nearest home.
      const goals = wanted.filter((c) => c.structureType === type.id && c.radius !== undefined);
      const score = (d: { x: number; z: number }): number =>
        goals.some((c) => Math.hypot(d.x - (c.x ?? 0), d.z - (c.z ?? 0)) <= (c.radius ?? 0))
          ? Math.hypot(d.x - pad.x, d.z - pad.z) - 10_000
          : Math.hypot(d.x - pad.x, d.z - pad.z);
      const offsets: Array<[number, number]> = [[0, 0], [3, 0], [-3, 0], [0, 3], [0, -3], [3, 3], [-3, -3], [3, -3], [-3, 3]];
      const spot = w.deposits
        .filter((d) => d.kind === 'metal')
        .sort((a, b) => score(a) - score(b))
        .flatMap((d) => offsets.map(([dx, dz]) => ({ x: d.x + dx, z: d.z + dz, id: d.id })))
        .find((p) => {
          const check = placementValidity(w, me, type, p.x, p.z);
          return check.valid && check.depositId === p.id;
        });
      if (spot) {
        out.push({ kind: 'placeKit', kitId: kit.id, x: spot.x, z: spot.z });
      }
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

  // Aircraft sit on their base until launched; send up any that are armed.
  const parked = own.filter((u) => u.air?.mode === 'parked' && u.air.ammo > 0).map((u) => u.id);
  if (parked.length > 0) {
    out.push({ kind: 'air', unitIds: parked, action: 'launch' });
  }

  // The army.
  const army = own.filter((u) => {
    const type = w.unitTypes.get(u.typeId);
    return !protectedIds.has(u.id) && isFightingUnitType(type) && !type?.workerKind && !type?.deploysTo;
  });
  const ids = army.map((u) => u.id);

  // Goal rings, minus building sites already claimed.
  const claimed = open.filter(
    (c): c is Extract<Condition, { t: 'structureBuilt' }> =>
      c.t === 'structureBuilt' && c.side === me && c.radius !== undefined && built(c) >= (c.count ?? 1),
  );
  const markers = missionMarkers(mission).filter((m) => !claimed.some((c) => c.x === m.x && c.z === m.z));
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
  const marching = army.some(
    (u) => u.order.kind === 'attack' && enemyStructures.some((st) => u.order.kind === 'attack' && st.id === u.order.targetId),
  );
  // Wait for a bigger group against more than one base; a dwindling attack falls back to regroup.
  const enemyPads = enemyStructures.filter((st) => w.structureTypes.get(st.typeId)?.kind === 'pad').length;
  const wantSize = plan.armySize ?? (enemyPads > 1 ? 12 : 7);
  // Late on, with no miners left and no ore to buy more, waiting only loses: go with what there is.
  const broke =
    w.tick > 600 * 20 &&
    (w.resources.find((r) => r.player === me)?.ore ?? 0) < 100 &&
    !own.some((u) => w.unitTypes.get(u.typeId)?.workerKind === 'oreMiner');
  const ready = !enemyPad || (marching && army.length >= 4) || army.length >= wantSize || (broke && army.length >= 4);
  if (ids.length > 0) {
    // Enemy fighters close to the army get fought first, before it drives on past them.
    const c0 = centre(army);
    const skirmish = enemies
      .filter((e) => !e.air && isFightingUnitType(w.unitTypes.get(e.typeId)) && !w.unitTypes.get(e.typeId)?.workerKind)
      .map((e) => ({ e, d: Math.hypot(e.x - c0.x, e.z - c0.z) }))
      .filter((item) => item.d < FIELD_RADIUS)
      .sort((a, b) => a.d - b.d)[0]?.e;
    if (threat) {
      out.push({ kind: 'attackMove', unitIds: ids, x: threat.x, z: threat.z });
    } else if (skirmish && !escortGoal) {
      out.push({ kind: 'attackMove', unitIds: ids, x: skirmish.x, z: skirmish.z });
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
      // An enemy that can rebuild is worth waiting for: gather a proper group at the pad's rally
      // point first (the deck itself is solid now).
      const home = gatherSpot(w, pad, plan.gatherOffEdge);
      out.push({ kind: 'attackMove', unitIds: ids, x: home.x, z: home.z });
    } else if (w.tick >= (plan.gatherTicks ?? 0)) {
      const c = centre(army);
      const near = (p: { x: number; z: number }): number => Math.hypot(p.x - c.x, p.z - c.z);
      // Enemy units are only worth chasing when an objective asks for kills; otherwise stay home.
      const killGoal = open.some(
        (c) =>
          (c.t === 'allDestroyed' && c.side !== me) ||
          (c.t === 'unitDestroyed' && (mission.tags[c.tag] ?? []).some((id) => enemies.some((u) => u.id === id))),
      );
      const foe =
        [...enemyStructures].sort((a, b) => near(a) - near(b))[0] ??
        (killGoal ? [...enemies].sort((a, b) => near(a) - near(b))[0] : undefined);
      if (foe) {
        out.push({ kind: 'attack', unitIds: ids, targetId: foe.id });
      } else if (pad && Math.hypot(c.x - pad.x, c.z - pad.z) > 20) {
        const home = gatherSpot(w, pad, plan.gatherOffEdge);
        out.push({ kind: 'attackMove', unitIds: ids, x: home.x, z: home.z });
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

/** Where the army gathers at home: just off the pad's exit edge (the deck itself is solid). */
function gatherSpot(
  w: WorldState,
  pad: { x: number; z: number; id: number },
  offEdge = PAD_RALLY_DISTANCE,
): { x: number; z: number } {
  const layout = padLayout(w, pad as Parameters<typeof padLayout>[1]);
  const fx = Math.cos(layout.facing);
  const fz = Math.sin(layout.facing);
  return { x: pad.x + fx * (layout.half + offEdge), z: pad.z + fz * (layout.half + offEdge) };
}

/** Play the mission to the end (or the tick cap). */
export function playMission(w: WorldState, maxTicks: number, plan: BotPlan = {}): WorldState {
  let world = w;
  while (!world.result && world.tick < maxTicks) {
    world = stepWithAi(world, botCommands(world, plan));
  }
  return world;
}

/** playMission, yielding to the event loop now and then so the test runner stays responsive. */
export async function playMissionAsync(w: WorldState, maxTicks: number, plan: BotPlan = {}): Promise<WorldState> {
  let world = w;
  while (!world.result && world.tick < maxTicks) {
    world = stepWithAi(world, botCommands(world, plan));
    if (world.tick % 1000 === 0) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  }
  return world;
}
