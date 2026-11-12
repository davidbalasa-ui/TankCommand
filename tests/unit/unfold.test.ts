import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { applyUnfold, readUnfold, type UnfoldData } from '../../src/render/unfold';

function box(name: string, w: number, h: number): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, w));
  mesh.name = name;
  return mesh;
}

// The art pipeline's tower layout: Base, Carrier (hidden once deployed), TurretPivot > Turret,
// each moving part carrying its packed pose in extras (userData after GLTFLoader).
function tower(): THREE.Group {
  const root = new THREE.Group();
  const base = box('Base', 2, 1);
  base.position.set(0, 0.5, 0);
  base.userData.packed = { p: [-0.6, 1.3, 0], r: [0, 0, 0, 1], s: [0.6, 0.5, 0.6] };
  const carrier = box('Carrier', 4, 1);
  carrier.scale.set(0.5, 0.08, 0.5);
  carrier.userData.packed = { p: [0, 0.5, 0], r: [0, 0, 0, 1], s: [1, 1, 1] };
  carrier.userData.hideWhenDeployed = 1;
  const pivot = new THREE.Object3D();
  pivot.name = 'TurretPivot';
  pivot.position.set(0, 1.5, 0);
  pivot.userData.packed = { p: [-0.6, 2, 0], r: [0, -1, 0, 0], s: [0.7, 0.7, 0.7] };
  pivot.add(box('Turret', 1, 0.5));
  root.add(base, carrier, pivot);
  return root;
}

describe('tower fold-out', () => {
  it('[UNF-01] reads fold data, leaves the deployed pose and hides the carrier', () => {
    const model = tower();
    const result = readUnfold(model);
    expect(result).not.toBeNull();
    expect(result!.data.parts.map((part) => part.name).sort()).toEqual(['Base', 'Carrier', 'TurretPivot']);
    expect(model.getObjectByName('Carrier')!.visible).toBe(false);
    expect(model.getObjectByName('Base')!.position.y).toBeCloseTo(0.5);
    // Deployed bounds leave the carrier out: the 2 m base is the widest part.
    const size = new THREE.Vector3();
    result!.bounds.getSize(size);
    expect(size.x).toBeCloseTo(2);
    // The packed pose is the 4 m carrier.
    expect(readUnfold(new THREE.Group())).toBeNull();
  });

  it('[UNF-02] starts on the packed pose and ends on the deployed pose with aim applied', () => {
    const model = tower();
    const read = readUnfold(model)!;
    const data: UnfoldData = { ...read.data, normScale: 0.5 };
    const start = { packedScale: 0.9, yaw: 1.2 };
    expect(applyUnfold(model, data, 0, start, 0)).toBe(false);
    expect(model.scale.x).toBeCloseTo(0.9);
    expect(model.rotation.y).toBeCloseTo(1.2);
    expect(model.getObjectByName('Base')!.position.y).toBeCloseTo(1.3);
    expect(model.getObjectByName('Carrier')!.visible).toBe(true);

    expect(applyUnfold(model, data, 0.5, start, 0)).toBe(false);
    const midY = model.getObjectByName('Base')!.position.y;
    expect(midY).toBeGreaterThan(0.5);
    expect(midY).toBeLessThan(1.3);

    expect(applyUnfold(model, data, 1, start, 0.7)).toBe(true);
    expect(model.scale.x).toBeCloseTo(0.5);
    expect(model.rotation.y).toBeCloseTo(0);
    expect(model.getObjectByName('Base')!.position.y).toBeCloseTo(0.5);
    expect(model.getObjectByName('Carrier')!.visible).toBe(false);
    const pivot = model.getObjectByName('TurretPivot')!;
    expect(new THREE.Euler().setFromQuaternion(pivot.quaternion, 'YXZ').y).toBeCloseTo(0.7);
  });
});
