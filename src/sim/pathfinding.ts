import {
  cellCenter,
  isBlockedAt,
  isBlockedCell,
  worldToCell,
  type MapDef,
} from './map';
import type { Point } from './types';

interface Cell {
  cx: number;
  cz: number;
}

interface HeapItem {
  key: number;
  f: number;
}

class MinHeap {
  private readonly items: HeapItem[] = [];

  push(item: HeapItem): void {
    this.items.push(item);
    let index = this.items.length - 1;
    while (index > 0) {
      const parent = (index - 1) >> 1;
      const parentItem = this.items[parent];
      const itemAt = this.items[index];
      if (!parentItem || !itemAt || parentItem.f <= itemAt.f) {
        break;
      }
      this.items[parent] = itemAt;
      this.items[index] = parentItem;
      index = parent;
    }
  }

  pop(): HeapItem | undefined {
    const first = this.items[0];
    const last = this.items.pop();
    if (!first || !last) {
      return first;
    }
    if (this.items.length > 0) {
      this.items[0] = last;
      let index = 0;
      for (;;) {
        const left = index * 2 + 1;
        const right = left + 1;
        let smallest = index;
        const atSmallest = this.items[smallest];
        const atLeft = this.items[left];
        const atRight = this.items[right];
        if (atLeft && atSmallest && atLeft.f < atSmallest.f) {
          smallest = left;
        }
        const atNewSmallest = this.items[smallest];
        if (atRight && atNewSmallest && atRight.f < atNewSmallest.f) {
          smallest = right;
        }
        if (smallest === index) {
          break;
        }
        const a = this.items[index];
        const b = this.items[smallest];
        if (!a || !b) {
          break;
        }
        this.items[index] = b;
        this.items[smallest] = a;
        index = smallest;
      }
    }
    return first;
  }

  get size(): number {
    return this.items.length;
  }
}

function keyOf(map: MapDef, cx: number, cz: number): number {
  return cz * map.cols + cx;
}

function cellOfKey(map: MapDef, key: number): Cell {
  const cz = Math.floor(key / map.cols);
  const cx = key - cz * map.cols;
  return { cx, cz };
}

function heuristic(map: MapDef, key: number, goalKey: number): number {
  const a = cellOfKey(map, key);
  const b = cellOfKey(map, goalKey);
  const dx = Math.abs(a.cx - b.cx);
  const dz = Math.abs(a.cz - b.cz);
  return dx + dz + (Math.SQRT2 - 2) * Math.min(dx, dz);
}

function neighbors(map: MapDef, cell: Cell): Array<{ cell: Cell; cost: number }> {
  const result: Array<{ cell: Cell; cost: number }> = [];
  for (let dz = -1; dz <= 1; dz += 1) {
    for (let dx = -1; dx <= 1; dx += 1) {
      if (dx === 0 && dz === 0) {
        continue;
      }
      const cx = cell.cx + dx;
      const cz = cell.cz + dz;
      if (isBlockedCell(map, cx, cz)) {
        continue;
      }
      if (dx !== 0 && dz !== 0) {
        if (isBlockedCell(map, cell.cx + dx, cell.cz) || isBlockedCell(map, cell.cx, cell.cz + dz)) {
          continue;
        }
      }
      result.push({
        cell: { cx, cz },
        cost: dx !== 0 && dz !== 0 ? Math.SQRT2 : 1,
      });
    }
  }
  return result;
}

function nearestOpenCell(map: MapDef, start: Cell): Cell | null {
  if (!isBlockedCell(map, start.cx, start.cz)) {
    return start;
  }
  const seen = new Set<number>();
  const queue: Cell[] = [start];
  seen.add(keyOf(map, start.cx, start.cz));
  for (let index = 0; index < queue.length; index += 1) {
    const current = queue[index];
    if (!current) {
      continue;
    }
    if (!isBlockedCell(map, current.cx, current.cz)) {
      return current;
    }
    for (const item of neighbors(map, current)) {
      const key = keyOf(map, item.cell.cx, item.cell.cz);
      if (!seen.has(key)) {
        seen.add(key);
        queue.push(item.cell);
      }
    }
    if (queue.length > 400) {
      break;
    }
  }
  return null;
}

// Connected areas of open cells, labelled once per map view. Obstacle views are rebuilt each
// tick (obstacles.ts), so every path planned in the same tick shares one labelling instead of
// flood-filling the whole map per path. Diagonal steps follow the same corner rule as A*, so two
// cells share a label exactly when a path between them exists.
const componentCache = new WeakMap<MapDef, Int32Array>();

function componentLabels(map: MapDef): Int32Array {
  const cached = componentCache.get(map);
  if (cached) {
    return cached;
  }
  const total = map.cols * map.rows;
  const labels = new Int32Array(total);
  const queue = new Int32Array(total);
  let next = 0;
  for (let seed = 0; seed < total; seed += 1) {
    if (labels[seed] !== 0) {
      continue;
    }
    const seedCell = cellOfKey(map, seed);
    if (isBlockedCell(map, seedCell.cx, seedCell.cz)) {
      labels[seed] = -1;
      continue;
    }
    next += 1;
    labels[seed] = next;
    let head = 0;
    let tail = 0;
    queue[tail] = seed;
    tail += 1;
    while (head < tail) {
      const key = queue[head] ?? 0;
      head += 1;
      for (const item of neighbors(map, cellOfKey(map, key))) {
        const neighbourKey = keyOf(map, item.cell.cx, item.cell.cz);
        if (labels[neighbourKey] !== 0) {
          continue;
        }
        labels[neighbourKey] = next;
        queue[tail] = neighbourKey;
        tail += 1;
      }
    }
  }
  componentCache.set(map, labels);
  return labels;
}

function reachableFrom(map: MapDef, start: Cell): Uint8Array {
  const reachable = new Uint8Array(map.cols * map.rows);
  if (isBlockedCell(map, start.cx, start.cz)) {
    return reachable;
  }
  const labels = componentLabels(map);
  const label = labels[keyOf(map, start.cx, start.cz)];
  for (let key = 0; key < labels.length; key += 1) {
    if (labels[key] === label) {
      reachable[key] = 1;
    }
  }
  return reachable;
}

function nearestReachableCell(
  map: MapDef,
  target: Cell,
  reachable: Uint8Array,
  maxRadius = 40,
): Cell | null {
  const seen = new Set<number>();
  const queue: Array<{ cell: Cell; depth: number }> = [{ cell: target, depth: 0 }];
  seen.add(keyOf(map, target.cx, target.cz));
  for (let index = 0; index < queue.length; index += 1) {
    const item = queue[index];
    if (!item) {
      continue;
    }
    const { cell, depth } = item;
    if (
      depth <= maxRadius &&
      cell.cx >= 0 &&
      cell.cz >= 0 &&
      cell.cx < map.cols &&
      cell.cz < map.rows &&
      reachable[keyOf(map, cell.cx, cell.cz)] === 1 &&
      !isBlockedCell(map, cell.cx, cell.cz)
    ) {
      return cell;
    }
    if (depth >= maxRadius) {
      continue;
    }
    // Spread over every cell, blocked or not: the target itself is often inside a building or
    // a cliff, and the nearest open cell can be several blocked cells away.
    for (let dz = -1; dz <= 1; dz += 1) {
      for (let dx = -1; dx <= 1; dx += 1) {
        const cx = cell.cx + dx;
        const cz = cell.cz + dz;
        if ((dx === 0 && dz === 0) || cx < 0 || cz < 0 || cx >= map.cols || cz >= map.rows) {
          continue;
        }
        const key = keyOf(map, cx, cz);
        if (!seen.has(key)) {
          seen.add(key);
          queue.push({ cell: { cx, cz }, depth: depth + 1 });
        }
      }
    }
  }
  return null;
}

/** Path-grid key of the cell holding (x, z); the key findPath's `avoid` set uses. */
export function cellKeyAt(map: MapDef, x: number, z: number): number {
  const cell = worldToCell(map, x, z);
  return keyOf(map, cell.cx, cell.cz);
}

/** Extra cost of driving through a cell another unit is parked in (in cells of plain driving). */
export const AVOID_CELL_COST = 6;

function astar(map: MapDef, start: Cell, goal: Cell, avoid?: ReadonlySet<number>): Cell[] | null {
  const startKey = keyOf(map, start.cx, start.cz);
  const goalKey = keyOf(map, goal.cx, goal.cz);
  if (startKey === goalKey) {
    return [start];
  }

  const total = map.cols * map.rows;
  const gScore = new Float64Array(total);
  gScore.fill(Number.POSITIVE_INFINITY);
  const cameFrom = new Int32Array(total);
  cameFrom.fill(-1);
  const closed = new Uint8Array(total);
  const open = new MinHeap();

  gScore[startKey] = 0;
  open.push({ key: startKey, f: heuristic(map, startKey, goalKey) });

  while (open.size > 0) {
    const current = open.pop();
    if (!current) {
      break;
    }
    if (closed[current.key] === 1) {
      continue;
    }
    if (current.key === goalKey) {
      const path: Cell[] = [];
      let key = goalKey;
      while (key !== -1) {
        path.push(cellOfKey(map, key));
        key = cameFrom[key] ?? -1;
      }
      path.reverse();
      return path;
    }
    closed[current.key] = 1;
    const currentCell = cellOfKey(map, current.key);
    const currentG = gScore[current.key] ?? Number.POSITIVE_INFINITY;
    for (const neighbour of neighbors(map, currentCell)) {
      const nKey = keyOf(map, neighbour.cell.cx, neighbour.cell.cz);
      if (closed[nKey] === 1) {
        continue;
      }
      const tentative = currentG + neighbour.cost + (avoid?.has(nKey) ? AVOID_CELL_COST : 0);
      if (tentative < (gScore[nKey] ?? Number.POSITIVE_INFINITY)) {
        gScore[nKey] = tentative;
        cameFrom[nKey] = current.key;
        open.push({ key: nKey, f: tentative + heuristic(map, nKey, goalKey) });
      }
    }
  }
  return null;
}

function lineClear(map: MapDef, a: Cell, b: Cell, avoid?: ReadonlySet<number>): boolean {
  const start = cellCenter(map, a.cx, a.cz);
  const end = cellCenter(map, b.cx, b.cz);
  const distance = Math.hypot(end.x - start.x, end.z - start.z);
  const samples = Math.max(1, Math.ceil(distance / (map.cellSize / 2)));
  for (let i = 1; i < samples; i += 1) {
    const t = i / samples;
    const x = start.x + (end.x - start.x) * t;
    const z = start.z + (end.z - start.z) * t;
    if (isBlockedAt(map, x, z)) {
      return false;
    }
    if (avoid && avoid.size > 0) {
      const cell = worldToCell(map, x, z);
      if (avoid.has(keyOf(map, cell.cx, cell.cz))) {
        return false;
      }
    }
  }
  return true;
}

function smoothCells(map: MapDef, cells: Cell[], avoid?: ReadonlySet<number>): Cell[] {
  if (cells.length <= 2) {
    return cells;
  }
  const result: Cell[] = [];
  const first = cells[0];
  if (!first) {
    return cells;
  }
  result.push(first);
  let index = 0;
  while (index < cells.length - 1) {
    let next = cells.length - 1;
    for (; next > index + 1; next -= 1) {
      const a = cells[index];
      const b = cells[next];
      if (a && b && lineClear(map, a, b, avoid)) {
        break;
      }
    }
    const chosen = cells[next];
    if (!chosen) {
      break;
    }
    result.push(chosen);
    index = next;
  }
  return result;
}

export function findPath(
  map: MapDef,
  startX: number,
  startZ: number,
  goalX: number,
  goalZ: number,
  avoid?: ReadonlySet<number>,
): Point[] | null {
  if (map.movement === 'air') {
    const half = map.size / 2;
    return [{ x: Math.min(half, Math.max(-half, goalX)), z: Math.min(half, Math.max(-half, goalZ)) }];
  }
  const startCellRaw = worldToCell(map, startX, startZ);
  const start = nearestOpenCell(map, startCellRaw);
  if (!start) {
    return null;
  }
  const reachable = reachableFrom(map, start);
  const targetRaw = worldToCell(map, goalX, goalZ);
  const half = map.size / 2;
  const goalInside = goalX >= -half && goalX <= half && goalZ >= -half && goalZ <= half;
  const goalOpen =
    goalInside &&
    !isBlockedAt(map, goalX, goalZ) &&
    reachable[targetRaw.cz * map.cols + targetRaw.cx] === 1;

  let goal: Cell | null = null;
  if (
    !isBlockedCell(map, targetRaw.cx, targetRaw.cz) &&
    reachable[targetRaw.cz * map.cols + targetRaw.cx] === 1
  ) {
    goal = targetRaw;
  }
  if (!goal) {
    goal = nearestReachableCell(map, targetRaw, reachable);
  }
  if (!goal) {
    return null;
  }

  const cells = astar(map, start, goal, avoid);
  if (!cells) {
    return null;
  }
  // Shortcuts may cross a cell a parked unit stands in only where the route itself goes through it.
  let routeAvoid: Set<number> | undefined;
  if (avoid && avoid.size > 0) {
    const onRoute = new Set(cells.map((c) => keyOf(map, c.cx, c.cz)));
    routeAvoid = new Set([...avoid].filter((key) => !onRoute.has(key)));
  }
  const smoothed = smoothCells(map, cells, routeAvoid);
  const points = smoothed.map((cell) => cellCenter(map, cell.cx, cell.cz));
  const last = points[points.length - 1];
  if (goalOpen && (!last || Math.hypot(last.x - goalX, last.z - goalZ) > 0.000001)) {
    points.push({ x: goalX, z: goalZ });
  }
  return points;
}
