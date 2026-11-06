import { isAllied } from './diplomacy';
import { heightAt, lineOfSightClear } from './map';
import { STEALTH_SIGHT_FACTOR, TARGET_HEIGHT, VIEWER_EYE_HEIGHT, VISION_INTERVAL_TICKS } from './tuning';
import type {
  GhostStructure,
  PlayerId,
  SensorContact,
  StructureState,
  UnitState,
  VisionSideState,
  WorldState,
} from './types';

interface Viewer {
  x: number;
  z: number;
  sight: number;
  sensor: number;
}

function cellIndex(world: WorldState, x: number, z: number): number {
  const { map } = world;
  const half = map.size / 2;
  const cx = Math.min(map.cols - 1, Math.max(0, Math.floor((x + half) / map.cellSize)));
  const cz = Math.min(map.rows - 1, Math.max(0, Math.floor((z + half) / map.cellSize)));
  return cz * map.cols + cx;
}

export function emptyCells(world: WorldState): string {
  return '0'.repeat(world.map.cols * world.map.rows);
}

function visionOf(world: WorldState, player: PlayerId): VisionSideState | undefined {
  return world.vision.find((item) => item.player === player);
}

// 0 unexplored, 1 explored, 2 visible.
export function cellState(world: WorldState, player: PlayerId, x: number, z: number): 0 | 1 | 2 {
  if (!world.fogEnabled) {
    return 2;
  }
  const vision = visionOf(world, player);
  if (!vision) {
    return 0;
  }
  const char = vision.cells.charAt(cellIndex(world, x, z));
  return char === '2' ? 2 : char === '1' ? 1 : 0;
}

function viewersFor(world: WorldState, player: PlayerId): Viewer[] {
  const viewers: Viewer[] = [];
  for (const unit of world.units) {
    if (unit.hp <= 0 || !isAllied(world, player, unit.owner)) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
    if (type) {
      viewers.push({ x: unit.x, z: unit.z, sight: type.sightRange, sensor: type.sensorRange });
    }
  }
  for (const structure of world.structures) {
    if (structure.hp <= 0 || !isAllied(world, player, structure.owner)) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (type) {
      viewers.push({
        x: structure.x,
        z: structure.z,
        sight: type.sightRange,
        sensor: Math.max(type.sightRange, type.sensorRange),
      });
    }
  }
  return viewers;
}

function markVisible(world: WorldState, viewer: Viewer, visible: Uint8Array): void {
  const { map } = world;
  const half = map.size / 2;
  const reach = Math.ceil(viewer.sight / map.cellSize);
  const originCx = Math.floor((viewer.x + half) / map.cellSize);
  const originCz = Math.floor((viewer.z + half) / map.cellSize);
  const eye = heightAt(map, viewer.x, viewer.z) + VIEWER_EYE_HEIGHT;
  for (let cz = Math.max(0, originCz - reach); cz <= Math.min(map.rows - 1, originCz + reach); cz += 1) {
    for (let cx = Math.max(0, originCx - reach); cx <= Math.min(map.cols - 1, originCx + reach); cx += 1) {
      const index = cz * map.cols + cx;
      if (visible[index] === 1) {
        continue;
      }
      const tx = -half + (cx + 0.5) * map.cellSize;
      const tz = -half + (cz + 0.5) * map.cellSize;
      if (Math.hypot(tx - viewer.x, tz - viewer.z) > viewer.sight) {
        continue;
      }
      const own = cx === originCx && cz === originCz;
      if (own || lineOfSightClear(map, viewer.x, viewer.z, eye, tx, tz, heightAt(map, tx, tz) + TARGET_HEIGHT)) {
        visible[index] = 1;
      }
    }
  }
}

function isStealthed(unit: UnitState): boolean {
  return unit.upgrades.includes('stealth');
}

function computeSide(world: WorldState, player: PlayerId, previous: VisionSideState | undefined): VisionSideState {
  const total = world.map.cols * world.map.rows;
  const visible = new Uint8Array(total);
  const viewers = viewersFor(world, player);
  for (const viewer of viewers) {
    markVisible(world, viewer, visible);
  }
  const old = previous?.cells ?? emptyCells(world);
  let cells = '';
  for (let i = 0; i < total; i += 1) {
    cells += visible[i] === 1 ? '2' : old.charAt(i) === '0' || old.charAt(i) === '' ? '0' : '1';
  }

  const visibleUnits: number[] = [];
  const contacts: SensorContact[] = [];
  for (const unit of world.units) {
    if (unit.hp <= 0 || isAllied(world, player, unit.owner)) {
      continue;
    }
    const stealth = isStealthed(unit);
    let seen = false;
    let sensed = false;
    if (visible[cellIndex(world, unit.x, unit.z)] === 1) {
      seen = !stealth || viewers.some((v) => Math.hypot(v.x - unit.x, v.z - unit.z) <= v.sight * STEALTH_SIGHT_FACTOR);
    }
    if (!seen && !stealth) {
      sensed = viewers.some((v) => Math.hypot(v.x - unit.x, v.z - unit.z) <= v.sensor);
    }
    if (seen) {
      visibleUnits.push(unit.id);
    } else if (sensed) {
      contacts.push({ x: unit.x, z: unit.z });
    }
  }

  const ghosts: GhostStructure[] = (previous?.ghosts ?? []).filter((ghost) => {
    if (visible[cellIndex(world, ghost.x, ghost.z)] !== 1) {
      return true;
    }
    return world.structures.some((item) => item.id === ghost.id && item.hp > 0);
  });
  for (const structure of world.structures) {
    if (structure.hp <= 0 || isAllied(world, player, structure.owner)) {
      continue;
    }
    if (visible[cellIndex(world, structure.x, structure.z)] !== 1) {
      continue;
    }
    const entry: GhostStructure = {
      id: structure.id,
      typeId: structure.typeId,
      owner: structure.owner,
      x: structure.x,
      z: structure.z,
    };
    const at = ghosts.findIndex((ghost) => ghost.id === structure.id);
    if (at >= 0) {
      ghosts[at] = entry;
    } else {
      ghosts.push(entry);
    }
  }
  ghosts.sort((a, b) => a.id - b.id);
  return { player, cells, visibleUnits, contacts, ghosts };
}

export function updateVision(world: WorldState, force = false): void {
  if (!world.fogEnabled) {
    return;
  }
  if (!force && world.tick % VISION_INTERVAL_TICKS !== 0) {
    return;
  }
  world.vision = world.players.map((player) =>
    computeSide(world, player, visionOf(world, player)),
  );
}

export interface PerceivedView {
  units: UnitState[];
  contacts: SensorContact[];
  ghosts: GhostStructure[];
  structures: StructureState[];
}

// Everything a side may know. Rendering, HUD, minimap and AI use this and nothing else about enemies.
export function perceivedUnits(world: WorldState, player: PlayerId): PerceivedView {
  if (!world.fogEnabled) {
    return {
      units: world.units.filter((unit) => unit.hp > 0),
      contacts: [],
      ghosts: [],
      structures: world.structures.filter((structure) => structure.hp > 0),
    };
  }
  const vision = visionOf(world, player);
  const seen = new Set(vision?.visibleUnits ?? []);
  const units = world.units.filter(
    (unit) => unit.hp > 0 && (isAllied(world, player, unit.owner) || seen.has(unit.id)),
  );
  const structures = world.structures.filter(
    (structure) =>
      structure.hp > 0 &&
      (isAllied(world, player, structure.owner) || cellState(world, player, structure.x, structure.z) === 2),
  );
  const visibleIds = new Set(structures.map((structure) => structure.id));
  return {
    units,
    contacts: vision?.contacts.map((c) => ({ ...c })) ?? [],
    ghosts: (vision?.ghosts ?? []).filter((ghost) => !visibleIds.has(ghost.id)),
    structures,
  };
}

export function canPerceiveUnit(world: WorldState, player: PlayerId, unit: UnitState): boolean {
  if (!world.fogEnabled || isAllied(world, player, unit.owner)) {
    return true;
  }
  return visionOf(world, player)?.visibleUnits.includes(unit.id) ?? false;
}
