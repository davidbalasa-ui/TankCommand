import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { isBlockedAt } from '../../src/sim/map';
import { hashWorld, step } from '../../src/sim/world';
import type { Command } from '../../src/sim/commands';
import type { Point, WorldState } from '../../src/sim/types';
import { makeWorld } from './simHelpers';

const NEAR = 3;

function closest(track: readonly Point[], point: Point): number {
  return Math.min(...track.map((p) => Math.hypot(p.x - point.x, p.z - point.z)));
}

// Drives one unit through queued moves and returns where it went.
function drive(waypoints: readonly Point[], kind: 'move' | 'attackMove', saveAt?: number, clearAt?: number): { world: WorldState; track: Point[] } {
  let world = makeWorld(1, [
    { owner: 1, typeId: 'unit.test.tank', x: -50, z: -50 },
    { owner: 2, typeId: 'unit.test.tank', x: 60, z: 60 },
  ]);
  const id = world.units[0]?.id ?? 0;
  const commands: Command[] = waypoints.map((point, index) => ({
    kind,
    unitIds: [id],
    x: point.x,
    z: point.z,
    tick: 1,
    issuer: 1,
    queue: index > 0,
  }));
  const track: Point[] = [];
  for (let i = 0; i < 3000; i += 1) {
    world = step(world, i === 0 ? commands : []);
    if (saveAt !== undefined && world.tick === saveAt) {
      const loaded = decodeSave(encodeSave(world, { gameVersion: 't', savedAtIso: 'x' }));
      expect(loaded.ok).toBe(true);
      if (loaded.ok) {
        expect(hashWorld(loaded.world)).toBe(hashWorld(world));
        world = loaded.world;
      }
    }
    const unit = world.units.find((u) => u.id === id);
    if (!unit) {
      break;
    }
    if (world.tick === clearAt) {
      // What engaging an enemy on an attack-move does: the path is dropped and planned again later.
      unit.path = [];
    }
    track.push({ x: unit.x, z: unit.z });
    if (unit.order.kind === 'idle') {
      break;
    }
  }
  return { world, track };
}

describe('queued legs', () => {
  // A zig-zag: the straight line to the last point passes nowhere near the middle ones.
  const zigzag = [
    { x: -30, z: -50 },
    { x: -30, z: -30 },
    { x: -50, z: -30 },
  ];

  it('[ORD-03] a unit passes within a few metres of every queued waypoint, in order', () => {
    for (const point of zigzag) {
      expect(isBlockedAt(makeWorld(1, []).map, point.x, point.z)).toBe(false);
    }
    const { world, track } = drive(zigzag, 'move');
    expect(world.units[0]?.order.kind).toBe('idle');
    const hits = zigzag.map((point) => track.findIndex((p) => Math.hypot(p.x - point.x, p.z - point.z) <= NEAR));
    for (const [index, point] of zigzag.entries()) {
      expect(closest(track, point), `waypoint ${index}`).toBeLessThanOrEqual(NEAR);
    }
    expect(hits[0]).toBeLessThan(hits[1] ?? -1);
    expect(hits[1]).toBeLessThan(hits[2] ?? -1);
  });

  it('[ORD-03] a unit whose path is dropped mid-leg (engaging, replanning) resumes that leg', () => {
    const { track } = drive(zigzag, 'attackMove', undefined, 20);
    for (const [index, point] of zigzag.entries()) {
      expect(closest(track, point), `waypoint ${index}`).toBeLessThanOrEqual(NEAR);
    }
  });

  it('[ORD-03] a route that loops back to its start drives the whole loop, and save/load keeps the legs', () => {
    const loop = [...zigzag, { x: -50, z: -50 }];
    const straight = drive(loop, 'attackMove');
    for (const [index, point] of loop.entries()) {
      expect(closest(straight.track, point), `waypoint ${index}`).toBeLessThanOrEqual(NEAR);
    }
    expect(straight.track.length).toBeGreaterThan(100);
    const resumed = drive(loop, 'attackMove', 60);
    expect(hashWorld(resumed.world)).toBe(hashWorld(straight.world));
  });

  it('[AI-17] an AI attack sent round a flank point drives through it before going on', () => {
    const row = MISSIONS.find((m) => m.id === 'mission.human.14_counterpunch');
    expect(row).toBeDefined();
    if (!row) {
      return;
    }
    let world = buildMissionWorld(data, row, 1);
    world.aiStates = [];
    const ai = world.sides.find((side) => side.controller === 'ai')?.player ?? 2;
    const group = world.units.filter((u) => u.owner === ai && data.unitTypes.get(u.typeId)?.role === 'tank').map((u) => u.id);
    expect(group.length).toBeGreaterThan(1);
    const centre = world.units.find((u) => u.id === group[0]) ?? { x: 0, z: 0 };
    // The same pair of orders the AI gives: out to a point to one side, then on to the target.
    const via = { x: centre.x - 40, z: centre.z - 10 };
    const target = { x: centre.x - 60, z: centre.z + 40 };
    expect(isBlockedAt(world.map, via.x, via.z)).toBe(false);
    world = step(world, [
      { kind: 'attackMove', unitIds: group, x: via.x, z: via.z, tick: 1, issuer: ai },
      { kind: 'attackMove', unitIds: group, x: target.x, z: target.z, tick: 1, issuer: ai, queue: true },
    ]);
    // Each unit's own flank point (the group spreads out in formation round it).
    const legEnds = new Map(world.units.filter((u) => group.includes(u.id)).map((u) => [u.id, u.legs?.[0]]));
    for (const id of group) {
      expect(legEnds.get(id), `unit ${id} has a flank leg`).toBeDefined();
    }
    const tracks = new Map<number, Point[]>(group.map((id) => [id, []]));
    for (let i = 0; i < 1600; i += 1) {
      world = step(world, []);
      for (const unit of world.units) {
        tracks.get(unit.id)?.push({ x: unit.x, z: unit.z });
      }
    }
    for (const id of group) {
      const leg = legEnds.get(id);
      const track = tracks.get(id) ?? [];
      if (leg && track.length > 0) {
        expect(closest(track, leg), `unit ${id}`).toBeLessThanOrEqual(NEAR);
      }
    }
  }, 60_000);
});
