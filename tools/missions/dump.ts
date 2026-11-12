// Dumps a mission's starting world (terrain, blocked cells, entities, goal areas) as JSON for
// tools/missions/preview.py. Run: npx vite-node tools/missions/dump.ts <mission id|all> <out dir>
import { writeFileSync } from 'node:fs';
import { parseAssetManifest } from '../../src/assets/manifestSchema';
import { AssetRegistry } from '../../src/assets/registry';
import rawManifest from '../../public/assets/manifest.json';
import { loadSimData } from '../../src/data/simData';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { isBlockedCell, isWaterAt, mapFor } from '../../src/sim/map';
import type { Condition } from '../../src/sim/missionSchema';

const data = loadSimData(new AssetRegistry(parseAssetManifest(rawManifest)));
const [which = 'all', out = '.'] = process.argv.slice(2);

function areas(cond: Condition, list: Array<{ x: number; z: number; r: number; side: number }>): void {
  if (cond.t === 'areaEntered') list.push({ x: cond.x, z: cond.z, r: cond.radius, side: cond.side });
  if (cond.t === 'unitEscorted') list.push({ x: cond.x, z: cond.z, r: cond.radius, side: 1 });
  if (cond.t === 'and' || cond.t === 'or') cond.conds.forEach((c) => areas(c, list));
  if (cond.t === 'not') areas(cond.cond, list);
}

for (const row of MISSIONS.filter((m) => which === 'all' || m.id === which)) {
  const w = buildMissionWorld(data, row, 1);
  const tracked = mapFor(w.map, 'tracked');
  const hover = mapFor(w.map, 'hover');
  const blocked: number[] = [];
  const hoverOnly: number[] = [];
  const water: number[] = [];
  const half = w.map.size / 2;
  for (let cz = 0; cz < w.map.rows; cz += 1) {
    for (let cx = 0; cx < w.map.cols; cx += 1) {
      const i = cz * w.map.cols + cx;
      const t = isBlockedCell(tracked, cx, cz);
      if (t) blocked.push(i);
      if (t && !isBlockedCell(hover, cx, cz)) hoverOnly.push(i);
      if (isWaterAt(w.map, -half + (cx + 0.5) * w.map.cellSize, -half + (cz + 0.5) * w.map.cellSize)) water.push(i);
    }
  }
  const goal: Array<{ x: number; z: number; r: number; side: number }> = [];
  for (const trigger of row.triggers) {
    areas(trigger.when, goal);
    for (const action of trigger.do) {
      if (action.t === 'spawn') goal.push({ x: action.x, z: action.z, r: 3, side: -action.side });
    }
  }
  writeFileSync(
    `${out}/${row.id}.json`,
    JSON.stringify({
      id: row.id,
      title: row.title,
      size: w.map.size,
      cols: w.map.cols,
      heights: Array.from(w.map.heights),
      blocked,
      hoverOnly,
      water,
      units: w.units.map((u) => ({ owner: u.owner, type: u.typeId, x: u.x, z: u.z })),
      structures: w.structures.map((s) => ({ owner: s.owner, type: s.typeId, x: s.x, z: s.z })),
      deposits: w.deposits.map((d) => ({ kind: d.kind, x: d.x, z: d.z })),
      goal,
    }),
  );
  console.log('dumped', row.id);
}
