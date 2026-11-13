import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { collectPartMotions, pivotIsSpinner, readPartMotion, updatePartMotions } from '../../src/render/partMotion';
import { UnitInstances, markInstanced } from '../../src/render/unitInstances';

const idle = { mining: false, working: false, moving: false };

function model(anim: unknown, name = 'DrumPivot'): { root: THREE.Object3D; node: THREE.Object3D } {
  const root = new THREE.Object3D();
  const node = new THREE.Object3D();
  node.name = name;
  node.rotation.set(0, 0.5, 0);
  node.userData.anim = anim;
  root.add(node);
  // Models are cloned per unit; the anim extras must survive the clone.
  const clone = root.clone();
  return { root: clone, node: clone.getObjectByName(name) as THREE.Object3D };
}

describe('moving model parts', () => {
  it('[PART-01] reads spin and swing extras and rejects malformed ones', () => {
    expect(readPartMotion({ type: 'spin', axis: [1, 0, 0], speed: 6, when: 'mining' })?.when).toBe('mining');
    expect(readPartMotion({ type: 'swing', axis: [0, 0, 1], amp: 0.4, speed: 9, when: 'always' })?.amp).toBe(0.4);
    expect(readPartMotion({ type: 'spin', axis: [0, 0, 0], speed: 1 })).toBeNull();
    expect(readPartMotion({ type: 'wobble', axis: [1, 0, 0], speed: 1 })).toBeNull();
    expect(readPartMotion({ type: 'swing', axis: [1, 0, 0], speed: 1 })).toBeNull();
    expect(readPartMotion(null)).toBeNull();
  });

  it('[PART-01] a mining drum spins up only while mining, about its own axis on top of its rest pose', () => {
    const { root, node } = model({ type: 'spin', axis: [1, 0, 0], speed: 6, when: 'mining' });
    const parts = collectPartMotions(root);
    expect(parts).toHaveLength(1);
    const rest = node.quaternion.clone();
    for (let i = 0; i < 30; i += 1) {
      updatePartMotions(parts, idle, 1 / 30);
    }
    expect(node.quaternion.angleTo(rest)).toBeLessThan(1e-6);
    for (let i = 0; i < 10; i += 1) {
      updatePartMotions(parts, { ...idle, mining: true }, 1 / 30);
    }
    const turned = node.quaternion.angleTo(rest);
    expect(turned).toBeGreaterThan(0.05);
    // The turn is purely about the part's own X axis: undoing the rest pose leaves an X rotation.
    const local = rest.clone().invert().multiply(node.quaternion);
    expect(Math.abs(local.y)).toBeLessThan(1e-6);
    expect(Math.abs(local.z)).toBeLessThan(1e-6);
    // Stopping winds it down; it stays where it stopped instead of snapping back.
    for (let i = 0; i < 60; i += 1) {
      updatePartMotions(parts, idle, 1 / 30);
    }
    const stopped = node.quaternion.clone();
    updatePartMotions(parts, idle, 1 / 30);
    expect(node.quaternion.angleTo(stopped)).toBeLessThan(1e-6);
  });

  it('[PART-01] busySpeed replaces speed while working, and a swing stays within its amplitude', () => {
    const spin = model({ type: 'spin', axis: [0, 1, 0], speed: 1, busySpeed: 4, when: 'always' }, 'TurretPivot');
    const parts = collectPartMotions(spin.root);
    expect(pivotIsSpinner(parts)).toBe(true);
    updatePartMotions(parts, idle, 0.05);
    const slow = parts[0]?.phase ?? 0;
    updatePartMotions(parts, { ...idle, working: true }, 0.05);
    expect((parts[0]?.phase ?? 0) - slow).toBeCloseTo(slow * 4, 5);

    const wing = model({ type: 'swing', axis: [1, 0, 0], amp: 0.3, speed: 9, when: 'always' }, 'WingLPivot');
    const wings = collectPartMotions(wing.root);
    expect(pivotIsSpinner(wings)).toBe(false);
    const rest = wing.node.quaternion.clone();
    let most = 0;
    for (let i = 0; i < 120; i += 1) {
      updatePartMotions(wings, idle, 1 / 60);
      most = Math.max(most, wing.node.quaternion.angleTo(rest));
    }
    expect(most).toBeGreaterThan(0.25);
    expect(most).toBeLessThanOrEqual(0.3 + 1e-6);
  });

  it('[PART-01] treads scroll their texture per unit while moving, drawn in one instanced batch', () => {
    const make = (): { root: THREE.Object3D; parts: ReturnType<typeof collectPartMotions> } => {
      const root = new THREE.Object3D();
      const hull = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
      const tread = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial({ map: new THREE.Texture() }));
      tread.name = 'Tread';
      tread.userData.anim = { type: 'scroll', speed: 3, when: 'moving' };
      root.add(hull, tread);
      const clone = root.clone();
      markInstanced(clone);
      return { root: clone, parts: collectPartMotions(clone) };
    };
    const a = make();
    const b = make();
    expect(a.parts).toHaveLength(1);
    expect(pivotIsSpinner(a.parts)).toBe(false);
    const tread = a.root.getObjectByName('Tread') as THREE.Mesh;
    const rest = tread.quaternion.clone();
    for (let i = 0; i < 20; i += 1) {
      updatePartMotions(a.parts, { ...idle, moving: true, pace: 1 }, 1 / 60);
      updatePartMotions(b.parts, idle, 1 / 60);
    }
    // The node itself never turns; only the texture offset moves.
    expect(tread.quaternion.angleTo(rest)).toBeLessThan(1e-9);
    expect(tread.userData.uvScroll).toBeGreaterThan(0);
    expect((b.root.getObjectByName('Tread') as THREE.Mesh).userData.uvScroll).toBe(0);

    const scene = new THREE.Scene();
    const instances = new UnitInstances(scene);
    instances.begin();
    a.root.updateMatrixWorld(true);
    b.root.updateMatrixWorld(true);
    instances.add('tank', a.root);
    instances.add('tank', b.root);
    instances.end(false);
    const meshes = scene.children.filter((item): item is THREE.InstancedMesh => item instanceof THREE.InstancedMesh);
    expect(meshes).toHaveLength(2);
    const scrolled = meshes.find((mesh) => mesh.geometry.getAttribute('instanceUvScroll'));
    expect(scrolled).toBeDefined();
    const values = scrolled?.geometry.getAttribute('instanceUvScroll');
    expect(values?.getX(0)).toBeCloseTo(tread.userData.uvScroll as number, 6);
    expect(values?.getX(1)).toBe(0);
    // The hull keeps the model's own geometry; only the tread gets a copy.
    const hull = meshes.find((mesh) => mesh !== scrolled);
    expect(hull?.geometry.getAttribute('instanceUvScroll')).toBeUndefined();
  });
});
