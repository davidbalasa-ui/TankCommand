// Solid things on the ground that units steer around: buildings, and for fighting units the
// ore and metal sites too (workers drive in to mine them). Landing pads are not solid: units land
// on them and drive off.
//
// Terrain blocking lives in map.ts. This adds the obstacles on top as a per-tick view of the map
// (`MapDef.obstacles`), so pathfinding, steering and the step check all see them without the
// saved world.map ever changing. Shapes are inflated (half a hull for buildings, a full hull for
// sites), so a unit's centre staying outside a shape keeps its hull clear. Deterministic: built from world state
// in world order, cached for the current tick only.
import { isBlockedAt, mapFor, type MapDef, type MapObstacles, type MovementClass, type ObstacleShape } from './map';
import { UNIT_RADIUS } from './tuning';
import type { UnitState, WorldState } from './types';

/** Solid core of an ore or metal site, before the unit-radius margin. */
export const DEPOSIT_SOLID_RADIUS = 2.4;

interface ObstacleCache {
  world: WorldState;
  tick: number;
  views: Map<string, MapDef>;
}

let cache: ObstacleCache | null = null;

export function resetObstacleCache(): void {
  cache = null;
}

function buildShapes(world: WorldState, withDeposits: boolean): ObstacleShape[] {
  const shapes: ObstacleShape[] = [];
  // Half a hull: enough that a tank doesn't sink into a wall, small enough that the 2 m path
  // grid still has an open cell within worker reach (STATION_REACH) of a 2x2 station.
  const margin = UNIT_RADIUS * 0.5;
  for (const structure of world.structures) {
    if (structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type || type.kind === 'pad') {
      continue;
    }
    shapes.push({
      x: structure.x,
      z: structure.z,
      hx: (type.footprint.cellsX * world.map.cellSize) / 2 + margin,
      hz: (type.footprint.cellsZ * world.map.cellSize) / 2 + margin,
      round: false,
    });
  }
  if (withDeposits) {
    for (const deposit of world.deposits) {
      if (deposit.amount <= 0) {
        continue;
      }
      const r = DEPOSIT_SOLID_RADIUS + UNIT_RADIUS;
      shapes.push({ x: deposit.x, z: deposit.z, hx: r, hz: r, round: true });
    }
  }
  return shapes;
}

export function shapeContains(shape: ObstacleShape, x: number, z: number): boolean {
  const dx = x - shape.x;
  const dz = z - shape.z;
  if (shape.round) {
    return dx * dx + dz * dz < shape.hx * shape.hx;
  }
  return Math.abs(dx) < shape.hx && Math.abs(dz) < shape.hz;
}

function buildObstacles(world: WorldState, withDeposits: boolean): MapObstacles {
  const map = world.map;
  const shapes = buildShapes(world, withDeposits);
  const cells = new Uint8Array(map.cols * map.rows);
  const half = map.size / 2;
  for (const shape of shapes) {
    const x0 = Math.max(0, Math.floor((shape.x - shape.hx + half) / map.cellSize));
    const x1 = Math.min(map.cols - 1, Math.floor((shape.x + shape.hx + half) / map.cellSize));
    const z0 = Math.max(0, Math.floor((shape.z - shape.hz + half) / map.cellSize));
    const z1 = Math.min(map.rows - 1, Math.floor((shape.z + shape.hz + half) / map.cellSize));
    for (let cz = z0; cz <= z1; cz += 1) {
      for (let cx = x0; cx <= x1; cx += 1) {
        const centreX = -half + (cx + 0.5) * map.cellSize;
        const centreZ = -half + (cz + 0.5) * map.cellSize;
        if (shapeContains(shape, centreX, centreZ)) {
          cells[cz * map.cols + cx] = 1;
        }
      }
    }
  }
  return { shapes, cells };
}

/** The map as a unit of this movement class sees it, with buildings (and sites) made solid. */
export function obstacleMap(world: WorldState, movement: MovementClass, withDeposits: boolean): MapDef {
  if (!cache || cache.world !== world || cache.tick !== world.tick) {
    cache = { world, tick: world.tick, views: new Map() };
  }
  const key = `${movement}|${withDeposits ? 1 : 0}`;
  let view = cache.views.get(key);
  if (!view) {
    const base = mapFor(world.map, movement);
    view = movement === 'air' ? base : { ...base, obstacles: buildObstacles(world, withDeposits) };
    cache.views.set(key, view);
  }
  return view;
}

/** Workers drive into ore and metal sites to mine and haul; everyone else goes round them. */
export function avoidsDeposits(world: WorldState, unit: UnitState): boolean {
  const type = world.unitTypes.get(unit.typeId);
  return !type?.workerKind;
}

/** Inside a building (or, for fighting units, a site) right now. */
export function insideObstacle(map: MapDef, x: number, z: number): boolean {
  const shapes = map.obstacles?.shapes;
  if (!shapes) {
    return false;
  }
  for (const shape of shapes) {
    if (shapeContains(shape, x, z)) {
      return true;
    }
  }
  return false;
}

/** How fast a parked unit slides out of a building that appeared round it (m per tick). */
const PUSH_OUT_STEP = 0.15;

/**
 * Parked ground units caught inside a building or (fighting units) a site slide out to the
 * nearest edge, a little each tick, so nothing sits inside a model. Moving units are left to
 * followPath, which already lets them drive out.
 */
export function pushOutOfObstacles(world: WorldState): void {
  for (const unit of world.units) {
    if (unit.hp <= 0 || unit.air || unit.speed > 0.01) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
    if (!type || type.movement === 'air') {
      continue;
    }
    const map = obstacleMap(world, type.movement, avoidsDeposits(world, unit));
    const shape = map.obstacles?.shapes.find((item) => shapeContains(item, unit.x, unit.z));
    if (!shape) {
      continue;
    }
    let dirX: number;
    let dirZ: number;
    let depth: number;
    const dx = unit.x - shape.x;
    const dz = unit.z - shape.z;
    if (shape.round) {
      const distance = Math.hypot(dx, dz);
      if (distance < 0.0001) {
        const angle = ((unit.id * 37) % 360) * (Math.PI / 180);
        dirX = Math.cos(angle);
        dirZ = Math.sin(angle);
      } else {
        dirX = dx / distance;
        dirZ = dz / distance;
      }
      depth = shape.hx - distance;
    } else {
      const outX = shape.hx - Math.abs(dx);
      const outZ = shape.hz - Math.abs(dz);
      if (outX < outZ) {
        dirX = dx >= 0 ? 1 : -1;
        dirZ = 0;
        depth = outX;
      } else {
        dirX = 0;
        dirZ = dz >= 0 ? 1 : -1;
        depth = outZ;
      }
    }
    const step = Math.min(PUSH_OUT_STEP, depth + 0.01);
    const nextX = unit.x + dirX * step;
    const nextZ = unit.z + dirZ * step;
    if (isBlockedAt(mapFor(world.map, type.movement), nextX, nextZ)) {
      continue;
    }
    unit.x = nextX;
    unit.z = nextZ;
  }
}
