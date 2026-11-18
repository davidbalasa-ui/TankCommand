import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { UnitInstances, markInstanced } from '../../src/render/unitInstances';

// A tank whose hull, two barrel sleeves and tread share one look, plus a glowing part that differs.
function tank(): { root: THREE.Object3D; sleeve: THREE.Object3D; tread: THREE.Mesh } {
  const material = new THREE.MeshStandardMaterial({ color: 0x556655, map: new THREE.Texture() });
  const root = new THREE.Object3D();
  const hull = new THREE.Mesh(new THREE.BoxGeometry(4, 1, 2), material.clone());
  const turret = new THREE.Object3D();
  turret.name = 'TurretPivot';
  turret.position.set(0, 1, 0);
  const sleeves = [1, 2].map((k) => {
    const pivot = new THREE.Object3D();
    pivot.name = `Barrel${k}Pivot`;
    pivot.position.set(1.5, 0.3, 0);
    pivot.add(new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 1), material.clone()));
    turret.add(pivot);
    return pivot;
  });
  const tread = new THREE.Mesh(new THREE.BoxGeometry(4, 0.4, 0.5), material.clone());
  tread.name = 'Tread';
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.2), new THREE.MeshStandardMaterial({ color: 0x00ffff, emissive: 0x00ffff }));
  root.add(hull, turret, tread, lamp);
  markInstanced(root);
  tread.userData.uvScroll = 0;
  return { root, sleeve: sleeves[1] as THREE.Object3D, tread };
}

describe('unit instancing', () => {
  it('[PERF-01] parts sharing a look draw in one call however many move, each placed by its own matrix', () => {
    const scene = new THREE.Scene();
    const instances = new UnitInstances(scene);
    const a = tank();
    const b = tank();
    // The second unit's outer sleeve has recoiled and its treads have run on.
    b.sleeve.position.x -= 0.8;
    b.tread.userData.uvScroll = 0.25;
    a.root.updateMatrixWorld(true);
    b.root.updateMatrixWorld(true);
    instances.begin();
    instances.add('tank', a.root);
    instances.add('tank', b.root);
    instances.end(false);

    const meshes = scene.children.filter((item): item is THREE.InstancedMesh => item instanceof THREE.InstancedMesh);
    // Hull, two sleeves and tread share one draw; the differently lit lamp keeps its own.
    expect(meshes).toHaveLength(2);
    const merged = meshes.find((mesh) => mesh.geometry.getAttribute('tcPart'));
    expect(merged?.count).toBe(2);
    const texture = merged ? findPartTexture(merged) : null;
    expect(texture).not.toBeNull();
    if (!merged || !texture) {
      return;
    }
    const data = texture.image.data as Float32Array;
    const width = texture.image.width;
    // Part order follows the model: hull, sleeve 1, sleeve 2, tread. Row 0 is unit a, row 1 unit b.
    const translationX = (row: number, part: number): number => data[(row * width + part * 4) * 4 + 3] ?? NaN;
    const scroll = (row: number, part: number): number => data[(row * width + part * 4 + 3) * 4] ?? NaN;
    const sleeveA = a.sleeve.children[0] as THREE.Mesh;
    const sleeveB = b.sleeve.children[0] as THREE.Mesh;
    expect(translationX(0, 2)).toBeCloseTo(sleeveA.matrixWorld.elements[12] ?? NaN, 6);
    expect(translationX(1, 2)).toBeCloseTo(sleeveB.matrixWorld.elements[12] ?? NaN, 6);
    expect(translationX(1, 2) - translationX(0, 2)).toBeCloseTo(-0.8, 6);
    // The first sleeve did not move.
    expect(translationX(1, 1)).toBeCloseTo(translationX(0, 1), 6);
    expect(scroll(0, 3)).toBe(0);
    expect(scroll(1, 3)).toBeCloseTo(0.25, 6);

    // Two hundred units of the same model still cost the same two draws.
    instances.begin();
    for (let i = 0; i < 200; i += 1) {
      instances.add('tank', i % 2 === 0 ? a.root : b.root);
    }
    instances.end(false);
    const after = scene.children.filter((item): item is THREE.InstancedMesh => item instanceof THREE.InstancedMesh);
    expect(after).toHaveLength(2);
    expect(after.every((mesh) => mesh.count === 200)).toBe(true);
  });
});

/** The part texture is handed to the shader through the material's compile hook; read it back. */
function findPartTexture(mesh: THREE.InstancedMesh): THREE.DataTexture | null {
  const shader = { uniforms: {} as Record<string, { value: unknown }>, vertexShader: '', fragmentShader: '' };
  (mesh.material as THREE.Material).onBeforeCompile(shader as unknown as THREE.WebGLProgramParametersWithUniforms, {} as THREE.WebGLRenderer);
  const value = shader.uniforms.tcParts?.value;
  return value instanceof THREE.DataTexture ? value : null;
}
