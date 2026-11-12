import type { Command } from '../sim/commands';
import { isHostile } from '../sim/diplomacy';
import { isFightingUnitType } from '../sim/economy';
import { hasFreeAirSlot, isAirborne } from '../sim/air';
import { Rng } from '../sim/rng';
import { isItemUnlocked, researchDone } from '../sim/research';
import { placementValidity } from '../sim/spawn';
import { perceivedUnits } from '../sim/vision';
import type {
  AiDifficulty,
  AiState,
  PlayerId,
  SimStructureType,
  SimUnitType,
  StructureState,
  UnitState,
  WorldState,
} from '../sim/types';
import { AI_DATA, UNIT_ORDER_PERIOD, DEFEND_RADIUS, KIT_RING_RADIUS, RETREAT_HP_FRACTION, TACTICAL_EVERY_TICKS } from './aiData';

type Untimed = Command extends infer C ? (C extends Command ? Omit<C, 'tick' | 'issuer'> : never) : never;

export function createAiState(player: PlayerId, difficulty: AiDifficulty, seed: number): AiState {
  return {
    player,
    difficulty,
    rngState: (seed * 2654435761 + player * 40503) >>> 0,
    scoutId: null,
    groupIds: [],
    groupStartValue: 0,
    waypoint: 0,
    lastPads: [],
    spent: 0,
  };
}

function faction(world: WorldState, player: PlayerId): string | null {
  return world.factions.find((entry) => entry.player === player)?.faction ?? null;
}

function valueOf(type: SimUnitType | undefined): number {
  return type ? type.oreCost + type.metalCost : 0;
}

class Planner {
  readonly commands: Untimed[] = [];
  private ore: number;
  private metal: number;
  metalReserve = 0;
  private readonly rng: Rng;

  constructor(
    readonly world: WorldState,
    readonly state: AiState,
  ) {
    const stats = world.resources.find((item) => item.player === state.player);
    this.ore = stats?.ore ?? 0;
    this.metal = stats?.metal ?? 0;
    this.rng = new Rng(state.rngState);
  }

  get player(): PlayerId {
    return this.state.player;
  }

  endRng(): number {
    return this.rng.getState();
  }

  ownUnits(): UnitState[] {
    return this.world.units.filter((unit) => unit.owner === this.player && unit.hp > 0);
  }

  ownStructures(): StructureState[] {
    return this.world.structures.filter((item) => item.owner === this.player && item.hp > 0);
  }

  structureKind(item: StructureState): string | undefined {
    return this.world.structureTypes.get(item.typeId)?.kind;
  }

  unitType(unit: UnitState): SimUnitType | undefined {
    return this.world.unitTypes.get(unit.typeId);
  }

  myTypes(): SimUnitType[] {
    const f = faction(this.world, this.player);
    return [...this.world.unitTypes.values()].filter((type) => type.faction === f && type.deploysTo === null);
  }

  myStructureTypes(): SimStructureType[] {
    const f = faction(this.world, this.player);
    return [...this.world.structureTypes.values()].filter((type) => type.faction === f && type.buyable);
  }

  canAfford(ore: number, metal: number, reserve: number, useMetalReserve = true): boolean {
    return this.ore - reserve >= ore && this.metal - (useMetalReserve ? this.metalReserve : 0) >= metal;
  }

  queued(itemId: string): number {
    return this.world.dropQueue.filter((o) => o.owner === this.player && o.itemId === itemId).length;
  }

  buy(itemId: string, ore: number, metal: number, reserve: number, useMetalReserve = true): boolean {
    const pad = this.ownStructures().find((s) => this.structureKind(s) === 'pad');
    if (!pad || !isItemUnlocked(this.world, this.player, itemId) || !this.canAfford(ore, metal, reserve, useMetalReserve)) {
      return false;
    }
    if (this.world.dropQueue.filter((o) => o.owner === this.player).length >= 3) {
      return false;
    }
    this.ore -= ore;
    this.metal -= metal;
    this.state.spent += ore + metal;
    this.commands.push({ kind: 'buy', itemId, padId: pad.id });
    return true;
  }

  buyUnit(type: SimUnitType, reserve: number): boolean {
    return this.buy(type.id, type.oreCost, type.metalCost, reserve);
  }

  buyStructure(type: SimStructureType, reserve: number, useMetalReserve = true): boolean {
    return this.buy(type.id, type.cost.ore, type.cost.metal, reserve, useMetalReserve);
  }
}

function isMiner(type: SimUnitType | undefined): boolean {
  return type?.workerKind === 'oreMiner';
}

function isTug(type: SimUnitType | undefined): boolean {
  return type?.workerKind === 'tug';
}

function isFighter(type: SimUnitType | undefined, desperate = false): boolean {
  return isFightingUnitType(type) && (type?.role === 'tank' || type?.role === 'artillery' || (desperate && type?.role === 'scout'));
}

// Metal deposits the AI believes are taken by someone else's station: only stations it can see now
// or remembers as ghosts count (perception API), never hidden ones.
function foreignStationDeposits(planner: Planner): Set<number> {
  const { world } = planner;
  const view = perceivedUnits(world, planner.player);
  const spots = [
    ...view.structures.filter((st) => st.owner !== planner.player && st.hp > 0),
    ...view.ghosts.filter((g) => g.owner !== planner.player),
  ].filter((st) => world.structureTypes.get(st.typeId)?.kind === 'metalStation');
  const taken = new Set<number>();
  for (const deposit of world.deposits) {
    if (deposit.kind === 'metal' && spots.some((st) => Math.hypot(st.x - deposit.x, st.z - deposit.z) < 3)) {
      taken.add(deposit.id);
    }
  }
  return taken;
}

// A deposit we could still build a station on, as far as we know.
function freeMetalDeposit(planner: Planner, depositId: number, taken: ReadonlySet<number>): boolean {
  const deposit = planner.world.deposits.find((d) => d.id === depositId);
  return (
    deposit !== undefined &&
    deposit.kind === 'metal' &&
    deposit.amount > 1 &&
    !taken.has(deposit.id) &&
    !planner.ownStructures().some((st) => st.depositId === deposit.id && planner.structureKind(st) === 'metalStation')
  );
}

function placeKits(planner: Planner): void {
  const { world } = planner;
  const pad = planner.ownStructures().find((s) => planner.structureKind(s) === 'pad');
  for (const kit of world.pendingKits.filter((item) => item.owner === planner.player)) {
    const type = world.structureTypes.get(kit.structureTypeId);
    if (!type || !pad) {
      continue;
    }
    if (type.buildOnMetalDeposit) {
      const taken = foreignStationDeposits(planner);
      const deposit = world.deposits
        .filter((d) => freeMetalDeposit(planner, d.id, taken))
        .sort(
          (a, b) =>
            Math.hypot(a.x - pad.x, a.z - pad.z) - Math.hypot(b.x - pad.x, b.z - pad.z) || a.id - b.id,
        )[0];
      if (deposit) {
        const offsets: Array<[number, number]> = [[0, 0], [3, 0], [-3, 0], [0, 3], [0, -3], [3, 3], [-3, -3], [3, -3], [-3, 3]];
        const spot = offsets
          .map(([dx, dz]) => ({ x: deposit.x + dx, z: deposit.z + dz }))
          .find((point) => {
            const check = placementValidity(world, planner.player, type, point.x, point.z);
            return check.valid && check.depositId === deposit.id;
          });
        if (spot) {
          planner.commands.push({ kind: 'placeKit', kitId: kit.id, x: spot.x, z: spot.z });
        } else {
          // Something is standing on the deposit: send our own idle units home.
          const blockers = planner
            .ownUnits()
            .filter((u) => u.order.kind === 'idle' && Math.hypot(u.x - deposit.x, u.z - deposit.z) < 8)
            .map((u) => u.id);
          if (blockers.length > 0) {
            planner.commands.push({ kind: 'move', unitIds: blockers, x: pad.x, z: pad.z });
          }
        }
      }
      continue;
    }
    // Rings of growing radius around the pad; bigger structures and crowded bases need the outer rings.
    search: for (let ring = 0; ring < 6; ring += 1) {
      const radius = KIT_RING_RADIUS + ring * 5;
      for (let step = 0; step < 24; step += 1) {
        const angle = (step / 24) * Math.PI * 2 + planner.state.waypoint * 0.7;
        const x = pad.x + Math.cos(angle) * radius;
        const z = pad.z + Math.sin(angle) * radius;
        if (placementValidity(world, planner.player, type, x, z).valid) {
          planner.commands.push({ kind: 'placeKit', kitId: kit.id, x, z });
          break search;
        }
      }
    }
  }
}

function assignWorkers(planner: Planner): void {
  const { world } = planner;
  const miners = planner.ownUnits().filter((u) => isMiner(planner.unitType(u)));
  const busy = new Map<number, number>();
  // A miner whose deposit ran dry sits in 'waiting' with nothing left to dig: send it elsewhere.
  const dry = (unit: UnitState): boolean =>
    unit.job !== null &&
    unit.job.stage === 'waiting' &&
    unit.job.load <= 0 &&
    !world.deposits.some((d) => d.id === unit.job?.targetId && d.amount > 0);
  for (const unit of miners) {
    if (unit.job && !dry(unit)) {
      busy.set(unit.job.targetId, (busy.get(unit.job.targetId) ?? 0) + 1);
    }
  }
  for (const unit of miners) {
    if ((unit.job && !dry(unit)) || unit.order.kind !== 'idle') {
      continue;
    }
    const deposit = world.deposits
      .filter((d) => d.kind === 'ore' && d.amount > 0)
      .sort(
        (a, b) =>
          (busy.get(a.id) ?? 0) - (busy.get(b.id) ?? 0) ||
          Math.hypot(a.x - unit.x, a.z - unit.z) - Math.hypot(b.x - unit.x, b.z - unit.z) ||
          a.id - b.id,
      )[0];
    if (deposit) {
      busy.set(deposit.id, (busy.get(deposit.id) ?? 0) + 1);
      planner.commands.push({ kind: 'mine', unitIds: [unit.id], depositId: deposit.id });
    }
  }
  const stations = planner.ownStructures().filter((s) => planner.structureKind(s) === 'metalStation');
  const tugs = planner.ownUnits().filter((u) => isTug(planner.unitType(u)) && !u.job && u.order.kind === 'idle');
  tugs.forEach((tug, index) => {
    const station = stations[index % Math.max(1, stations.length)];
    if (station) {
      planner.commands.push({ kind: 'assign', unitIds: [tug.id], stationId: station.id });
    }
  });
}

function knownEnemyStructures(world: WorldState, player: PlayerId): Array<{ x: number; z: number; kind: string; id: number }> {
  const view = perceivedUnits(world, player);
  const result: Array<{ x: number; z: number; kind: string; id: number }> = [];
  for (const item of view.structures) {
    if (isHostile(world, player, item.owner)) {
      result.push({ x: item.x, z: item.z, kind: world.structureTypes.get(item.typeId)?.kind ?? 'pad', id: item.id });
    }
  }
  for (const ghost of view.ghosts) {
    if (isHostile(world, player, ghost.owner)) {
      result.push({ x: ghost.x, z: ghost.z, kind: world.structureTypes.get(ghost.typeId)?.kind ?? 'pad', id: ghost.id });
    }
  }
  return result;
}

function waypoints(world: WorldState, home: { x: number; z: number }): Array<{ x: number; z: number }> {
  const e = world.map.size * 0.38;
  const all = [
    { x: e, z: e },
    { x: -e, z: e },
    { x: e, z: -e },
    { x: -e, z: -e },
    { x: 0, z: 0 },
  ];
  return all.sort(
    (a, b) => Math.hypot(b.x - home.x, b.z - home.z) - Math.hypot(a.x - home.x, a.z - home.z),
  );
}

function isAircraft(type: SimUnitType | undefined): boolean {
  return type?.air !== null && type?.air !== undefined;
}

function hitsAir(type: SimUnitType | undefined): boolean {
  return type?.weapon?.targets?.includes('air') ?? false;
}

// Air base, aircraft purchases and air strikes. Aircraft fly from their base to a target and come
// home by themselves when ammunition or fuel runs low (sim/air.ts), so the AI only buys and launches.
function airOps(
  planner: Planner,
  fighterCount: number,
  known: Array<{ x: number; z: number; kind: string; id: number }>,
  hasKit: boolean,
): void {
  const { world, state } = planner;
  const data = AI_DATA[state.difficulty];
  if (data.airBaseAfterFighters <= 0) {
    return;
  }
  const baseType = planner.myStructureTypes().find((t) => t.kind === 'airBase');
  const bases = planner.ownStructures().filter((s) => planner.structureKind(s) === 'airBase');
  if (
    baseType &&
    bases.length === 0 &&
    !hasKit &&
    fighterCount >= data.airBaseAfterFighters &&
    planner.queued(baseType.id) === 0 &&
    isItemUnlocked(world, planner.player, baseType.id)
  ) {
    planner.buyStructure(baseType, data.reserveOre);
    return;
  }
  if (bases.length === 0) {
    return;
  }
  const view = perceivedUnits(world, planner.player);
  const enemyAir = view.units.filter(
    (u) => isHostile(world, planner.player, u.owner) && isAirborne(u),
  );
  const airTypes = planner
    .myTypes()
    .filter((t) => isAircraft(t) && t.weapon !== null && isItemUnlocked(world, planner.player, t.id))
    .sort((a, b) => a.id.localeCompare(b.id));
  const queuedAir = airTypes.reduce((sum, t) => sum + planner.queued(t.id), 0);
  if (airTypes.length > 0 && queuedAir === 0 && hasFreeAirSlot(world, planner.player)) {
    const owned = planner.ownUnits();
    const pick =
      (enemyAir.length > 0 ? airTypes.find((t) => hitsAir(t)) : undefined) ??
      airTypes
        .map((t) => ({ t, count: owned.filter((u) => u.typeId === t.id).length }))
        .sort((x, y) => x.count - y.count || x.t.id.localeCompare(y.t.id))[0]?.t;
    if (pick) {
      planner.buyUnit(pick, data.reserveOre);
    }
  }

  const ready = planner.ownUnits().filter((u) => {
    const type = planner.unitType(u);
    return (
      u.air !== null &&
      u.air.mode === 'parked' &&
      type?.air &&
      u.air.ammo >= type.air.ammo &&
      u.air.fuelLeft >= type.air.fuelSec
    );
  });
  if (ready.length === 0) {
    return;
  }
  // Interceptors first: anything that can hit air goes after enemy aircraft near our holdings.
  const pad = planner.ownStructures().find((s) => planner.structureKind(s) === 'pad');
  const intruder = pad
    ? enemyAir
        .filter((u) => Math.hypot(u.x - pad.x, u.z - pad.z) < DEFEND_RADIUS * 2)
        .sort((a, b) => Math.hypot(a.x - pad.x, a.z - pad.z) - Math.hypot(b.x - pad.x, b.z - pad.z) || a.id - b.id)[0]
    : undefined;
  if (intruder) {
    const interceptors = ready.filter((u) => hitsAir(planner.unitType(u))).map((u) => u.id);
    if (interceptors.length > 0) {
      planner.commands.push({ kind: 'air', unitIds: interceptors, action: 'launch' });
      planner.commands.push({ kind: 'attack', unitIds: interceptors, targetId: intruder.id });
      return;
    }
  }
  if (ready.length < data.airStrikeSize) {
    return;
  }
  // Strike: radar and turrets first (they blind and guard), then pads; workers if no structure is known.
  const rank = (kind: string): number => (kind === 'radar' ? 0 : kind === 'turret' ? 1 : kind === 'metalStation' ? 2 : kind === 'pad' ? 3 : 4);
  const home = bases[0] ?? pad;
  const target = [...known]
    .sort(
      (a, b) =>
        rank(a.kind) - rank(b.kind) ||
        (home ? Math.hypot(a.x - home.x, a.z - home.z) - Math.hypot(b.x - home.x, b.z - home.z) : 0) ||
        a.id - b.id,
    )[0];
  const worker = view.units.find((u) => isHostile(world, planner.player, u.owner) && u.job !== null);
  const ids = ready.map((u) => u.id);
  if (target) {
    planner.commands.push({ kind: 'air', unitIds: ids, action: 'launch' });
    planner.commands.push({ kind: 'attackMove', unitIds: ids, x: target.x, z: target.z });
  } else if (worker) {
    planner.commands.push({ kind: 'air', unitIds: ids, action: 'launch' });
    planner.commands.push({ kind: 'attack', unitIds: ids, targetId: worker.id });
  }
}

function strategic(planner: Planner): void {
  const { world, state } = planner;
  const data = AI_DATA[state.difficulty];
  const units = planner.ownUnits();
  const types = planner.myTypes();
  const structures = planner.ownStructures();
  const pad = structures.find((s) => planner.structureKind(s) === 'pad');
  if (!pad) {
    return;
  }

  placeKits(planner);
  assignWorkers(planner);

  const stationTypeEarly = planner.myStructureTypes().find((t) => t.kind === 'metalStation');
  const taken = foreignStationDeposits(planner);
  const freeMetal = world.deposits.some((d) => freeMetalDeposit(planner, d.id, taken));
  const stationCount = structures.filter((s) => planner.structureKind(s) === 'metalStation').length;
  if (stationTypeEarly && stationCount < data.maxStations && freeMetal && !world.pendingKits.some((k) => k.owner === planner.player)) {
    planner.metalReserve = stationTypeEarly.cost.metal;
  }
  const minerType = types.find((t) => isMiner(t));
  const miners = units.filter((u) => isMiner(planner.unitType(u))).length + (minerType ? planner.queued(minerType.id) : 0);
  if (minerType && miners < data.minersWanted) {
    planner.buyUnit(minerType, 0);
  }

  const stationType = planner.myStructureTypes().find((t) => t.kind === 'metalStation');
  const hasStation = structures.some((s) => {
    if (planner.structureKind(s) !== 'metalStation') {
      return false;
    }
    const deposit = world.deposits.find((d) => d.id === s.depositId);
    return deposit !== undefined && deposit.amount > 1;
  });
  // A station kit with nowhere left to go must not block every other purchase forever.
  const hasKit = world.pendingKits.some(
    (k) =>
      k.owner === planner.player &&
      !(world.structureTypes.get(k.structureTypeId)?.buildOnMetalDeposit === true && !freeMetal),
  );
  if (
    stationType &&
    stationCount < data.maxStations &&
    !hasKit &&
    planner.queued(stationType.id) === 0 &&
    freeMetal
  ) {
    planner.buyStructure(stationType, 0, false);
  }
  const tugType = types.find((t) => isTug(t));
  // Haulers carry both the miners' ore crates and the stations' metal to the pad: about one per
  // miner plus one for metal.
  const minerCount = units.filter((u) => isMiner(planner.unitType(u))).length;
  const tugCount = units.filter((u) => isTug(planner.unitType(u))).length;
  const tugsWanted = Math.min(5, Math.max(1, minerCount) + (hasStation || hasKit ? 1 : 0));
  if (tugType && tugCount < tugsWanted && planner.queued(tugType.id) === 0) {
    planner.buyUnit(tugType, 0);
  }

  // Metal is still reachable if one of our stations sits on a non-empty deposit or a free deposit
  // is left to build on. Deposits held by an enemy station don't count.
  const metalLeft =
    freeMetal ||
    world.deposits.some(
      (d) =>
        d.kind === 'metal' &&
        d.amount > 1 &&
        structures.some((st) => st.depositId === d.id && planner.structureKind(st) === 'metalStation'),
    );
  const cheapestTankMetal = Math.min(...types.filter((t) => isFighter(t)).map((t) => t.metalCost), Infinity);
  const desperate = !metalLeft && planner.canAfford(0, cheapestTankMetal, 0, false) === false;
  const fighters = units.filter((u) => isFighter(planner.unitType(u), desperate));
  const armyValue = fighters.reduce((sum, u) => sum + valueOf(planner.unitType(u)), 0);
  const known = knownEnemyStructures(world, planner.player);

  // Scout until an enemy structure is known.
  const scoutType = types.filter((t) => t.role === 'scout').sort((a, b) => valueOf(a) - valueOf(b))[0];
  const scoutUnit = units.find((u) => planner.unitType(u)?.role === 'scout');
  if (scoutUnit) {
    state.scoutId = scoutUnit.id;
  } else if (known.length === 0 && scoutType && planner.queued(scoutType.id) === 0) {
    planner.buyUnit(scoutType, data.reserveOre);
  }
  const activeScout = units.find((u) => u.id === state.scoutId);
  if (activeScout) {
    if (known.length > 0) {
      state.scoutId = null;
      planner.commands.push({ kind: 'move', unitIds: [activeScout.id], x: pad.x, z: pad.z });
    } else if (activeScout.order.kind === 'idle') {
      const points = waypoints(world, pad);
      const point = points[state.waypoint % points.length];
      state.waypoint += 1;
      if (point) {
        planner.commands.push({ kind: 'move', unitIds: [activeScout.id], x: point.x, z: point.z });
      }
    }
  }

  // Army, research and defences.
  const labType = planner.myStructureTypes().find((t) => t.kind === 'lab');
  const lab = structures.find((s) => planner.structureKind(s) === 'lab');
  if (data.useLab && labType && !lab && !hasKit && fighters.length >= 3 && planner.queued(labType.id) === 0) {
    planner.buyStructure(labType, data.reserveOre);
  }
  if (lab && lab.research === null && lab.work === null) {
    const done = researchDone(world, planner.player);
    const node = [...world.researchTree.values()]
      .filter((n) => n.faction === faction(world, planner.player) && !done.has(n.id) && n.requires.every((r) => done.has(r)))
      .sort((a, b) => a.cost.ore + a.cost.metal - (b.cost.ore + b.cost.metal) || a.id.localeCompare(b.id))[0];
    if (node && planner.canAfford(node.cost.ore, node.cost.metal, data.reserveOre + 100)) {
      planner.commands.push({ kind: 'research', labId: lab.id, nodeId: node.id });
    }
  }
  // Every other defence is anti-air once enemy aircraft have shown up (and it is unlocked).
  const turretTypes = planner
    .myStructureTypes()
    .filter((t) => t.kind === 'turret' && isItemUnlocked(world, planner.player, t.id))
    .sort((a, b) => a.id.localeCompare(b.id));
  const ownTurrets = structures.filter((s) => planner.structureKind(s) === 'turret');
  const turrets = ownTurrets.length;
  const enemyAirSeen = perceivedUnits(world, planner.player).units.some(
    (u) => isHostile(world, planner.player, u.owner) && u.air !== null,
  );
  const antiAir = turretTypes.find((t) => t.weapon?.targets?.includes('air'));
  const groundGun = turretTypes.find((t) => !t.weapon?.targets?.includes('air')) ?? turretTypes[0];
  const antiAirCount = ownTurrets.filter((s) => s.typeId === antiAir?.id).length;
  const turretType = enemyAirSeen && antiAir && antiAirCount * 2 <= turrets ? antiAir : groundGun;
  const turretQueued = turretTypes.some((t) => planner.queued(t.id) > 0);
  if (turretType && !hasKit && turrets < Math.floor(fighters.length / data.fightersPerTurret) && !turretQueued) {
    planner.buyStructure(turretType, data.reserveOre + 100);
  }
  const combat = types
    .filter((t) => isFighter(t, desperate))
    .sort((a, b) => a.id.localeCompare(b.id));
  if (combat.length > 0) {
    const order = combat
      .map((t) => ({ t, count: units.filter((u) => u.typeId === t.id).length + planner.queued(t.id) }))
      .sort((x, y) => x.count - y.count || x.t.id.localeCompare(y.t.id));
    for (const entry of order) {
      if (planner.buyUnit(entry.t, data.reserveOre)) {
        break;
      }
    }
  }

  airOps(planner, fighters.length, known, hasKit);

  // Retreat a mauled attack group.
  if (state.groupIds.length > 0) {
    const alive = fighters.filter((u) => state.groupIds.includes(u.id) && u.order.kind !== 'idle');
    const value = alive.reduce((sum, u) => sum + valueOf(planner.unitType(u)), 0);
    if (alive.length === 0) {
      state.groupIds = [];
      state.groupStartValue = 0;
    } else if (value < state.groupStartValue * (1 - data.retreatLossFraction)) {
      planner.commands.push({ kind: 'move', unitIds: alive.map((u) => u.id), x: pad.x, z: pad.z });
      state.groupIds = [];
    }
  }

  // Defend, otherwise attack once the army is big enough.
  const view = perceivedUnits(world, planner.player);
  const holdings = [...units.map((u) => ({ x: u.x, z: u.z })), ...structures.map((st) => ({ x: st.x, z: st.z }))];
  const threats = view.units
    .filter(
      (u) =>
        isHostile(world, planner.player, u.owner) &&
        holdings.some((h) => Math.hypot(h.x - u.x, h.z - u.z) < DEFEND_RADIUS) &&
        Math.hypot(pad.x - u.x, pad.z - u.z) < DEFEND_RADIUS * 2,
    )
    .sort((a, b) => Math.hypot(pad.x - a.x, pad.z - a.z) - Math.hypot(pad.x - b.x, pad.z - b.z) || a.id - b.id);
  const idle = fighters.filter((u) => u.order.kind === 'idle');
  const threat = data.defends ? threats[0] : undefined;
  if (threat) {
    const defenders = fighters.filter(
      (u) => u.order.kind === 'idle' || (u.order.kind === 'attackMove' && Math.hypot(u.x - pad.x, u.z - pad.z) < DEFEND_RADIUS * 2),
    );
    if (defenders.length > 0) {
      planner.commands.push({ kind: 'attackMove', unitIds: defenders.map((u) => u.id), x: threat.x, z: threat.z });
    }
    return;
  }
  const decay = Math.max(0.15, 1 - world.tick / (15 * 1200));
  const threshold = data.attackThresholdValue * decay;
  const idleValue = idle.reduce((sum, u) => sum + valueOf(planner.unitType(u)), 0);
  if (idle.length > 0 && (idleValue >= threshold || (armyValue >= threshold && state.groupIds.length === 0))) {
    let target: { x: number; z: number } | undefined;
    const workers = view.units.filter((u) => isHostile(world, planner.player, u.owner) && (u.job !== null));
    const worker = workers[0];
    if (worker) {
      target = { x: worker.x, z: worker.z };
    } else {
      const rank = (kind: string): number => (kind === 'radar' ? 0 : kind === 'pad' ? 1 : 2);
      const pick = [...known].sort(
        (a, b) => rank(a.kind) - rank(b.kind) || Math.hypot(a.x - pad.x, a.z - pad.z) - Math.hypot(b.x - pad.x, b.z - pad.z) || a.id - b.id,
      )[0];
      if (pick) {
        target = { x: pick.x, z: pick.z };
        state.lastPads = [{ x: pick.x, z: pick.z }];
      } else {
        const points = waypoints(world, pad);
        target = points[state.waypoint % points.length];
        state.waypoint += 1;
      }
    }
    if (target && idle.length > 0) {
      planner.commands.push({ kind: 'attackMove', unitIds: idle.map((u) => u.id), x: target.x, z: target.z });
      state.groupIds = idle.map((u) => u.id);
      state.groupStartValue = idleValue;
    }
  }
}

function tactical(planner: Planner): void {
  const { world, state } = planner;
  const data = AI_DATA[state.difficulty];
  const view = perceivedUnits(world, planner.player);
  const enemies = view.units.filter((u) => isHostile(world, planner.player, u.owner));
  const repairer = planner.ownUnits().find((u) => planner.unitType(u)?.repair);
  for (const unit of planner.ownUnits()) {
    const type = planner.unitType(unit);
    if (!type || !isFighter(type, true) || unit.transform || (Math.floor((world.tick + state.player * 7) / TACTICAL_EVERY_TICKS) + unit.id) % UNIT_ORDER_PERIOD !== 0) {
      continue;
    }
    if (data.focusFire && repairer && unit.hp < type.hp * RETREAT_HP_FRACTION && unit.order.kind !== 'move') {
      const home = repairer;
      if (home) {
        planner.commands.push({ kind: 'move', unitIds: [unit.id], x: home.x, z: home.z });
        continue;
      }
    }
    if (!type.weapon || unit.order.kind === 'attack' || unit.order.kind === 'move') {
      continue;
    }
    const range = type.weapon.range;
    const structureInRange = view.structures
      .filter((e) => isHostile(world, planner.player, e.owner) && Math.hypot(e.x - unit.x, e.z - unit.z) <= range + 2)
      .sort((a, b) => a.hp - b.hp || a.id - b.id)[0];
    const anyEnemyNear = enemies.some((e) => Math.hypot(e.x - unit.x, e.z - unit.z) <= range + 4);
    if (structureInRange && !anyEnemyNear) {
      planner.commands.push({ kind: 'attack', unitIds: [unit.id], targetId: structureInRange.id });
      continue;
    }
    const inRange = enemies
      .filter((e) => Math.hypot(e.x - unit.x, e.z - unit.z) <= range)
      .sort((a, b) => a.hp - b.hp || a.id - b.id)[0];
    if (inRange && data.focusFire) {
      planner.commands.push({ kind: 'attack', unitIds: [unit.id], targetId: inRange.id });
    }
  }
}

// One AI decision step for one side. Reads only the perception API and its own side's state and
// returns commands; the caller applies them through the normal command channel.
export function thinkAi(world: WorldState, input: AiState): { commands: Command[]; state: AiState } {
  const state: AiState = { ...input, groupIds: [...input.groupIds], lastPads: input.lastPads.map((p) => ({ ...p })) };
  const planner = new Planner(world, state);
  const data = AI_DATA[state.difficulty];
  const offset = state.player * 7;
  if ((world.tick + offset) % data.strategicEveryTicks === 0) {
    strategic(planner);
  }
  if ((world.tick + offset) % TACTICAL_EVERY_TICKS === 0) {
    tactical(planner);
  }
  state.rngState = planner.endRng();
  const commands = planner.commands.map((c) => ({ ...c, tick: world.tick + 1, issuer: state.player }));
  return { commands, state };
}
