import type { MapDef } from './map';

export type PlayerId = number;

export interface Point {
  x: number;
  z: number;
}

export type Order =
  | { kind: 'idle' }
  | { kind: 'move'; x: number; z: number; queue: boolean }
  | { kind: 'attack'; targetId: number };

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
  path: Point[];
  reloadLeft: number;
  stuckTicks: number;
  speed: number;
  replans: number;
  attackRepathTick: number;
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
  hp: number;
  armor: number;
  topSpeed: number;
  accel: number;
  turnDegPerSec: number;
  turretTurnDegPerSec: number;
  fireOnMove: boolean;
  sightRange: number;
  weapon: WeaponStats | null;
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
}

export interface WreckState {
  x: number;
  z: number;
  ttl: number;
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
}

export interface WorldState {
  tick: number;
  seed: number;
  rngState: number;
  counter: number;
  nextId: number;
  players: PlayerId[];
  map: MapDef;
  unitTypes: ReadonlyMap<string, SimUnitType>;
  units: UnitState[];
  projectiles: ProjectileState[];
  wrecks: WreckState[];
  result: WorldResult | null;
}
