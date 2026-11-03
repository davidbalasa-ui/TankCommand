import type { MapDef } from './map';

export type PlayerId = number;
export type Faction = 'human' | 'alien';
export type Stance = 'free' | 'hold';
export type UnitRole = 'worker' | 'scout' | 'tank' | 'artillery' | 'support' | 'air' | 'structure';
export type WorkerKind = 'oreMiner' | 'tug';
export type StructureKind = 'pad' | 'metalStation';
export type DepositKind = 'ore' | 'metal';

export interface Point {
  x: number;
  z: number;
}

export type Order =
  | { kind: 'idle' }
  | { kind: 'move'; x: number; z: number; queue: boolean }
  | { kind: 'attackMove'; x: number; z: number; queue: boolean }
  | { kind: 'attack'; targetId: number };

export type WorkerStage =
  | 'toDeposit'
  | 'digging'
  | 'toPad'
  | 'toStation'
  | 'loading'
  | 'waiting';

export interface WorkerJob {
  kind: WorkerKind;
  targetId: number;
  stage: WorkerStage;
  load: number;
  progress: number;
  reportedEmpty: boolean;
}

export interface UnitState {
  id: number;
  owner: PlayerId;
  typeId: string;
  x: number;
  z: number;
  heading: number;
  turretHeading: number;
  hp: number;
  order: Order;
  stance: Stance;
  path: Point[];
  reloadLeft: number;
  stuckTicks: number;
  speed: number;
  replans: number;
  attackRepathTick: number;
  job: WorkerJob | null;
}

export interface WeaponStats {
  damage: number;
  range: number;
  reloadSec: number;
  projectileSpeed: number;
  accuracy: number;
  splashRadius: number;
}

export interface SimUnitType {
  id: string;
  faction: Faction;
  role: UnitRole;
  hp: number;
  armor: number;
  topSpeed: number;
  accel: number;
  turnDegPerSec: number;
  turretTurnDegPerSec: number;
  fireOnMove: boolean;
  sightRange: number;
  weapon: WeaponStats | null;
  oreCost: number;
  metalCost: number;
  deliverySec: number;
  workerKind: WorkerKind | null;
  miningRatePerSec: number;
  carryCapacity: number;
  salvageRefundPercent: number;
}

export interface SimStructureType {
  id: string;
  name: string;
  faction: Faction;
  kind: StructureKind;
  cost: { ore: number; metal: number };
  deliverySec: number;
  hp: number;
  armor: number;
  footprint: { cellsX: number; cellsZ: number };
  sightRange: number;
  modelId: string;
  buildOnMetalDeposit: boolean;
  metalRatePerSec: number;
  containerSize: number;
  maxContainers: number;
}

export interface StructureState {
  id: number;
  owner: PlayerId;
  typeId: string;
  x: number;
  z: number;
  hp: number;
  containers: number;
  fill: number;
  depositId: number | null;
}

export interface ProjectileState {
  id: number;
  owner: PlayerId;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  damage: number;
  ttl: number;
  splashRadius: number;
  // Set only when the projectile was fired at a structure. When absent (the
  // usual case: a shot fired at a unit), the projectile can damage units along
  // its path but never a structure it happens to graze — otherwise a pad sitting
  // near a target unit soaks every shot aimed at that unit and the unit can
  // never take damage at all.
  targetStructureId?: number;
}

export interface WreckState {
  x: number;
  z: number;
  ttl: number;
}

export interface DropBeamState {
  owner: PlayerId;
  x: number;
  z: number;
  ttl: number;
}

export interface SideStats {
  player: PlayerId;
  ore: number;
  metal: number;
  oreGathered: number;
  metalGathered: number;
  unitsBuilt: number;
  unitsLost: number;
}

export interface DepositDef {
  kind: DepositKind;
  x: number;
  z: number;
  amount: number;
}

export interface DepositState extends DepositDef {
  id: number;
  maxAmount: number;
}

export interface PendingKit {
  id: number;
  owner: PlayerId;
  structureTypeId: string;
}

export interface DropOrder {
  id: number;
  owner: PlayerId;
  itemId: string;
  itemKind: 'unit' | 'structure';
  padId: number;
  remainingSec: number;
  totalSec: number;
  costOre: number;
  costMetal: number;
}

export type AlertKind = 'depositEmpty' | 'dropArrived' | 'unitLost' | 'structureLost';

export interface SimAlert {
  kind: AlertKind;
  owner: PlayerId;
  x: number;
  z: number;
  ttl: number;
}

export interface CommandOutcome {
  tick: number;
  kind: string;
  ok: boolean;
  reason: string;
}

export interface FactionAssignment {
  player: PlayerId;
  faction: Faction;
}

export interface StartResources {
  player: PlayerId;
  ore: number;
  metal: number;
}

export interface WorldResult {
  winner: PlayerId | null;
}

export interface StartUnit {
  owner: PlayerId;
  typeId: string;
  x: number;
  z: number;
  heading?: number;
  turretHeading?: number;
  stance?: Stance;
}

export interface StartStructure {
  owner: PlayerId;
  typeId: string;
  x: number;
  z: number;
  depositId?: number | null;
}

export interface WorldState {
  tick: number;
  seed: number;
  rngState: number;
  counter: number;
  nextId: number;
  players: PlayerId[];
  factions: FactionAssignment[];
  map: MapDef;
  unitTypes: ReadonlyMap<string, SimUnitType>;
  structureTypes: ReadonlyMap<string, SimStructureType>;
  units: UnitState[];
  structures: StructureState[];
  deposits: DepositState[];
  pendingKits: PendingKit[];
  dropQueue: DropOrder[];
  dropBeams: DropBeamState[];
  alerts: SimAlert[];
  resources: SideStats[];
  projectiles: ProjectileState[];
  wrecks: WreckState[];
  lastCommandOutcome: CommandOutcome | null;
  result: WorldResult | null;
}
