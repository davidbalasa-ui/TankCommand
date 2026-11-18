import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import manifest from '../../public/assets/manifest.json';
import { LANDSCAPE_LOD_IDS, Landscape, PROP_IDS, scatterProps } from '../../src/render/landscape';
import type { WorldState } from '../../src/sim/types';
import { generateMap, isBlockedAt, isWaterAt } from '../../src/sim/map';

const BIG = new Set(['prop.nature.cliff', 'prop.nature.boulder']);

describe('[LND] map scenery', () => {
  it('[LND-01] scenery is fixed per map, big rocks only on undrivable ground, nothing in water', () => {
    const map = generateMap(42);
    const a = scatterProps(map);
    const b = scatterProps(generateMap(42));
    expect(a.length).toBeGreaterThan(100);
    expect(a.map((p) => `${p.prop}@${p.x.toFixed(3)},${p.z.toFixed(3)}`)).toEqual(
      b.map((p) => `${p.prop}@${p.x.toFixed(3)},${p.z.toFixed(3)}`),
    );
    for (const placed of a) {
      expect(isWaterAt(map, placed.x, placed.z)).toBe(false);
      if (BIG.has(placed.prop)) {
        expect(isBlockedAt(map, placed.x, placed.z), `${placed.prop} at ${placed.x},${placed.z}`).toBe(true);
      }
    }
  });
});

describe('[LND] scenery level of detail', () => {
  it('[LND-02] every prop and site has a low-detail model in the manifest', () => {
    const ids = new Set(manifest.assets.map((asset: { id: string }) => asset.id));
    for (const id of LANDSCAPE_LOD_IDS) {
      expect(ids.has(id), id).toBe(true);
      expect(ids.has(id.replace(/\.lod$/, '')), id).toBe(true);
    }
  });

  it('[LND-03] full models only near the camera on high quality, low-detail everywhere otherwise', () => {
    const map = generateMap(42);
    const landscape = new Landscape(new THREE.Scene(), map, {
      uFog: { value: null },
      uFogOn: { value: 0 },
      uFogSize: { value: map.size },
    });
    const model = (): THREE.Object3D => {
      const root = new THREE.Group();
      root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial()));
      return root;
    };
    for (const id of PROP_IDS) {
      landscape.addModel(id, model());
      landscape.addModel(`${id}.lod`, model());
    }
    const world = { structures: [], deposits: [], structureTypes: new Map() } as unknown as WorldState;
    landscape.sync(world, 0, 0);
    const total = landscape.propCount();
    const near = landscape.detailCounts();
    expect(near.full).toBeGreaterThan(0);
    expect(near.low).toBeGreaterThan(near.full);
    expect(near.full + near.low).toBe(total);
    landscape.setFullDetail(false);
    expect(landscape.detailCounts()).toEqual({ full: 0, low: total });
    landscape.setFullDetail(true);
    // Moving the camera target moves the full-detail circle (out here only edge scenery, always low).
    landscape.sync(world, map.size, map.size);
    expect(landscape.detailCounts().full).toBe(0);
    // Zoomed far out, everything is low-detail.
    landscape.sync(world, 0, 0, 120);
    expect(landscape.detailCounts()).toEqual({ full: 0, low: total });
    landscape.sync(world, 0, 0, 40);
    expect(landscape.detailCounts().full).toBe(near.full);
    expect(landscape.propCount()).toBe(total);
  });
});
