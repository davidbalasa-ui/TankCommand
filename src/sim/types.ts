import type { MissionState } from './triggers';
import type { MapDef, MapFeatures, MovementClass } from './map';

export type PlayerId = number;
export type Faction = 'human' | 'alien';
export type Stance = 'free' | 'hold';
export type UnitRole = 'worker' | 'scout' | 'tank' | 'artillery' | 'support' | 'air' | 'structure';
export type WorkerKind = 'oreMiner' | 'tug';
export type StructureKind = 'pad' | 'metalStation' | 'turret' | 'radar' | 'lab' | 'airBase';
export type DepositKind = 'ore' | 'metal';
export type UpgradeKind = 'fireRate' | 'armor' | 'stealth';

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
  | 'unloading'
  | 'waiting';

export interface WorkerJob {
  kind: WorkerKind;
  targetId: number;
  stage: WorkerStage;
  load: number;
  progress: number;
  reportedEmpty: boolean;
  // Delivery line at a landing pad: which pad, when this worker joined its line (tick),
  // and the unload time left once it is at the dock.
  dockPadId?: number | null;
  dockSide?: number; // which of the pad's three docks (index into PadLayout.docks)
  queuedAt?: number;
  unloadLeft?: number;
  // Haulers only: what they collect from ('station' = metal containers, 'deposit' = the ore
  // crates miners stack beside a deposit) and what they carry now.
  source?: 'station' | 'deposit';
  cargo?: 'ore' | 'metal';
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
  // Workers: the spot the current path was planned for (its end may stop short of a blocked
  // goal), and where that path ended, so a path set by anything else is never mistaken for it.
  pathGoal?: { x: number; z: number; endX: number; endZ: number };
  reloadLeft: number;
  stuckTicks: number;
  /** Ticks spent waiting for an oncoming friend at a narrow spot (0 when not waiting). */
  yieldTicks?: number;
  speed: number;
  replans: number;
  attackRepathTick: number;
  job: WorkerJob | null;
  upgrades: string[];
  // A packed turret deploying back into a structure. Null otherwise.
  transform: { left: number } | null;
  /** A packed structure vehicle on its way to unpack here (overhaul step 5). */
  deployTarget?: { x: number; z: number; tries: number } | null;
  air: AirState | null;
}

export type WeaponTarget = 'ground' | 'air' | 'structure';

export interface WeaponStats {
  // Render-only: which effect to draw (laser, bombs, lightning, ground_beam ...). The sim never reads it.
  kind?: string;
  targets?: WeaponTarget[];
  damage: number;
  range: number;
  reloadSec: number;
  projectileSpeed: number;
  accuracy: number;
  splashRadius: number;
}

export interface SimUnitType {
  id: string;
  // Render-only: the asset id of the unit's model. The sim never reads it.
  modelId?: string;
  // Render-only: drawn length relative to a light tank.
  visualScale?: number;
  // Ground footprint radius for avoidance and spacing (metres). Defaults to UNIT_RADIUS.
  radius?: number;
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
  sensorRange: number;
  weapon: WeaponStats | null;
  oreCost: number;
  metalCost: number;
  deliverySec: number;
  workerKind: WorkerKind | null;
  miningRatePerSec: number;
  carryCapacity: number;
  salvageRefundPercent: number;
  repair: { radius: number; ratePerSec: number; unitsOnly?: boolean } | null;
  // Set on a packed structure: the structure type it deploys back into.
  deploysTo: string | null;
  deploySec: number;
  upgrades: string[];
  movement: MovementClass;
  air: AirStats | null;
}

export interface AirStats {
  ammo: number;
  fuelSec: number;
  rearmSec: number;
  cruiseHeight: number;
}

export type AirMode = 'parked' | 'flying' | 'returning' | 'rearming';

export interface AirState {
  ammo: number;
  fuelLeft: number;
  homeId: number | null;
  mode: AirMode;
  rearmLeft: number;
  patrol: Point | null;
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
  weapon: WeaponStats | null;
  turretTurnDegPerSec: number;
  packSec: number;
  packedUnitId: string | null;
  dismantleSec: number;
  dismantleRefundPercent: number;
  sensorRange: number;
  upgrades: string[];
  airCapacity: number;
  /** False for mission-only structures that are never for sale. */
  buyable: boolean;
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
  upgrades: string[];
  reloadLeft: number;
  turretHeading: number;
  // Pack or dismantle in progress; the structure can't fire while it runs.
  work: { kind: 'pack' | 'dismantle'; left: number } | null;
  // Landing pads only: the unit that just came down and is still driving off, and how long
  // the pad keeps waiting for it before the next delivery may land anyway.
  padUnitId?: number | null;
  padClearLeft?: number;
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
  // Render-only: the firing weapon's kind and the shooter, so the view can draw the right effect
  // from the right place (an aircraft's gun is up in the air).
  kind?: string;
  shooterId?: number;
  aimDistance?: number;
}

export interface RubbleState {
  x: number;
  z: number;
  radius: number;
  ttl: number;
}

export interface ResearchNode {
  id: string;
  name: string;
  faction: Faction;
  cost: { ore: number; metal: number };
  timeSec: number;
  requires: string[];
  unlocks: string[];
  upgrades: string[];
}

export interface ResearchSideState {
  player: PlayerId;
  done: string[];
  /** The step being researched now (paid when it started). */
  active: { nodeId: string; left: number } | null;
  /** Steps that start after it, each paid when it starts (a parent, then the item tapped). */
  queue: string[];
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
  // Render-only flavour: 'arrive' (default) is the touchdown flash; 'ore' / 'metal' is a cargo
  // pod lifting off a pad's dock. `total` is the starting ttl.
  kind?: 'arrive' | 'ore' | 'metal';
  total?: number;
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

// Ore that miners have packed into crates beside a deposit, waiting for a hauler. Kept per owner
// because sides can mine the same deposit.
export interface OreCrates {
  owner: PlayerId;
  ore: number;
}

export interface DepositState extends DepositDef {
  id: number;
  maxAmount: number;
  crates?: OreCrates[];
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
  // Set once the delivery is coming down onto the pad: seconds into the descent.
  landingSec?: number;
}

export type AlertKind =
  | 'depositEmpty'
  | 'dropArrived'
  | 'unitLost'
  | 'structureLost'
  | 'researchDone';

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

export interface GhostStructure {
  id: number;
  typeId: string;
  owner: PlayerId;
  x: number;
  z: number;
}

export interface SensorContact {
  x: number;
  z: number;
}

// One digit per cell: 0 unexplored, 1 explored, 2 visible. Allied sides share the same viewers.
export interface VisionSideState {
  player: PlayerId;
  cells: string;
  signature: string;
  visibleUnits: number[];
  contacts: SensorContact[];
  ghosts: GhostStructure[];
}

export type AiDifficulty = 'easy' | 'normal' | 'hard';

// Saved with the match. The AI module owns the contents; the sim only stores and hashes them.
export interface AiState {
  player: PlayerId;
  difficulty: AiDifficulty;
  rngState: number;
  scoutId: number | null;
  groupIds: number[];
  groupStartValue: number;
  waypoint: number;
  lastPads: Array<{ x: number; z: number }>;
  spent: number;
}

export type Controller = 'human' | 'ai' | 'scripted' | 'none';
export type DiplomacyRelation = 'allied' | 'neutral' | 'hostile';

export interface SideState {
  player: PlayerId;
  controller: Controller;
  team: number;
  groupId: string | null;
  provokable: boolean;
  forgiveAfterSec: number | null;
}

// Relation of side `a` toward side `b` (ordered pair).
export interface RelationState {
  a: PlayerId;
  b: PlayerId;
  relation: DiplomacyRelation;
  forgiveLeft: number | null;
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
  fogEnabled: boolean;
  aiStates: AiState[];
  vision: VisionSideState[];
  sides: SideState[];
  relations: RelationState[];
  map: MapDef;
  mapFeatures: MapFeatures;
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
  rubble: RubbleState[];
  researchTree: ReadonlyMap<string, ResearchNode>;
  research: ResearchSideState[];
  lastCommandOutcome: CommandOutcome | null;
  result: WorldResult | null;
  mission: MissionState | null;
}
