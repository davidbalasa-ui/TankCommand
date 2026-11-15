// Draws units of the same model and side as one instanced mesh per model part, so 192 units cost
// a few dozen draw calls instead of several hundred.
//
// Each unit keeps its own Object3D hierarchy (root, turret pivot) for positioning, bounds and
// effects; its model meshes are hidden and their world matrices are copied into the shared
// InstancedMesh slots every frame. Meshes added to a unit later (cargo, Halo blades) are not
// marked as instanced and draw normally.
import * as THREE from 'three';

const INSTANCED = 'tcInstanced';
const MIN_CAPACITY = 16;
/** Per-mesh texture scroll (tank treads), set by partMotion.ts as userData.uvScroll. */
const UV_SCROLL = 'uvScroll';
const SCROLL_ATTRIBUTE = 'instanceUvScroll';

const scrollMaterials = new WeakMap<THREE.Material, THREE.Material>();

/**
 * A copy of the material that adds a per-instance offset along U to its texture, so every unit's
 * treads run at their own pace while they are all drawn in one call.
 */
function scrollMaterial(source: THREE.Material): THREE.Material {
  const known = scrollMaterials.get(source);
  if (known) {
    return known;
  }
  const material = source.clone();
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `#include <common>\nattribute float ${SCROLL_ATTRIBUTE};`)
      .replace('#include <uv_vertex>', `#include <uv_vertex>\n#ifdef USE_MAP\n\tvMapUv.x += ${SCROLL_ATTRIBUTE};\n#endif`);
  };
  material.customProgramCacheKey = () => 'tc-uv-scroll';
  scrollMaterials.set(source, material);
  return material;
}

function scrollAttribute(mesh: THREE.InstancedMesh): THREE.InstancedBufferAttribute | null {
  const attribute = mesh.geometry.getAttribute(SCROLL_ATTRIBUTE);
  return attribute instanceof THREE.InstancedBufferAttribute ? attribute : null;
}

interface Batch {
  meshes: THREE.InstancedMesh[];
  capacity: number;
  count: number;
}

/** Marks a freshly cloned unit model's meshes for instancing and hides them. */
export function markInstanced(root: THREE.Object3D): void {
  root.traverse((object) => {
    if (object instanceof THREE.Mesh && !(object instanceof THREE.InstancedMesh)) {
      object.userData[INSTANCED] = true;
      object.visible = false;
    }
  });
}

/** True for a unit model mesh that is hidden because an InstancedMesh draws it. */
export function isInstancedPart(object: THREE.Object3D): boolean {
  return object.userData[INSTANCED] === true;
}

function instancedParts(root: THREE.Object3D): THREE.Mesh[] {
  const parts: THREE.Mesh[] = [];
  root.traverse((object) => {
    if (object instanceof THREE.Mesh && object.userData[INSTANCED] === true) {
      parts.push(object as THREE.Mesh);
    }
  });
  return parts;
}

export class UnitInstances {
  private readonly batches = new Map<string, Batch>();

  constructor(private readonly scene: THREE.Scene) {}

  /** Starts a frame: every batch is emptied and refilled by add(). */
  begin(): void {
    for (const batch of this.batches.values()) {
      batch.count = 0;
    }
  }

  /**
   * Adds one unit (its world matrices must be current). `key` names its model and look. `geometries`
   * swaps in other geometry per instanced part, in traversal order (low-detail models share the
   * full model's node layout, so the part matrices still fit); give it its own key.
   */
  add(key: string, root: THREE.Object3D, geometries?: readonly THREE.BufferGeometry[]): void {
    const parts = instancedParts(root);
    if (parts.length === 0) {
      return;
    }
    let batch = this.batches.get(key);
    if (!batch || batch.meshes.length !== parts.length) {
      if (batch) {
        this.drop(batch);
      }
      batch = { meshes: [], capacity: 0, count: 0 };
      this.batches.set(key, batch);
    }
    if (batch.count >= batch.capacity) {
      this.grow(batch, parts, Math.max(MIN_CAPACITY, batch.capacity * 2), geometries);
    }
    const slot = batch.count;
    parts.forEach((part, index) => {
      const mesh = batch.meshes[index];
      mesh?.setMatrixAt(slot, part.matrixWorld);
      const scroll = mesh ? scrollAttribute(mesh) : null;
      if (scroll) {
        scroll.setX(slot, typeof part.userData[UV_SCROLL] === 'number' ? part.userData[UV_SCROLL] : 0);
      }
    });
    batch.count += 1;
  }

  /** Ends a frame: uploads the matrices and sets how many instances each batch draws. */
  end(castShadow: boolean): void {
    for (const batch of this.batches.values()) {
      for (const mesh of batch.meshes) {
        mesh.count = batch.count;
        mesh.visible = batch.count > 0;
        mesh.castShadow = castShadow;
        mesh.instanceMatrix.needsUpdate = true;
        const scroll = scrollAttribute(mesh);
        if (scroll) {
          scroll.needsUpdate = true;
        }
      }
    }
  }

  /** Forgets all batches (models reloaded, colour-blind mode changed). Materials belong to units. */
  clear(): void {
    for (const batch of this.batches.values()) {
      this.drop(batch);
    }
    this.batches.clear();
  }

  private grow(
    batch: Batch,
    parts: THREE.Mesh[],
    capacity: number,
    geometries?: readonly THREE.BufferGeometry[],
  ): void {
    const old = batch.meshes;
    batch.meshes = parts.map((part, index) => {
      const source = geometries?.[index] ?? part.geometry;
      const scrolls = typeof part.userData[UV_SCROLL] === 'number' && !Array.isArray(part.material);
      // A scrolling part gets its own geometry copy to hold the per-instance offset.
      const geometry = scrolls ? source.clone() : source;
      if (scrolls) {
        const values = new THREE.InstancedBufferAttribute(new Float32Array(capacity), 1);
        values.setUsage(THREE.DynamicDrawUsage);
        const before = old[index] ? scrollAttribute(old[index]) : null;
        for (let i = 0; before && i < batch.count; i += 1) {
          values.setX(i, before.getX(i));
        }
        geometry.setAttribute(SCROLL_ATTRIBUTE, values);
      }
      const material = scrolls ? scrollMaterial(part.material as THREE.Material) : part.material;
      const mesh = new THREE.InstancedMesh(geometry, material, capacity);
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      // Instances spread over the whole map; per-instance culling is not worth it at this count.
      mesh.frustumCulled = false;
      mesh.receiveShadow = true;
      mesh.name = 'UnitInstances';
      const previous = old[index];
      if (previous) {
        const matrix = new THREE.Matrix4();
        for (let i = 0; i < batch.count; i += 1) {
          previous.getMatrixAt(i, matrix);
          mesh.setMatrixAt(i, matrix);
        }
      }
      this.scene.add(mesh);
      return mesh;
    });
    for (const mesh of old) {
      this.release(mesh);
    }
    batch.capacity = capacity;
  }

  private release(mesh: THREE.InstancedMesh): void {
    this.scene.remove(mesh);
    if (scrollAttribute(mesh)) {
      // Only the scrolling parts own their geometry copy; the rest share the model's.
      mesh.geometry.dispose();
    }
    mesh.dispose();
  }

  private drop(batch: Batch): void {
    for (const mesh of batch.meshes) {
      this.release(mesh);
    }
    batch.meshes = [];
    batch.capacity = 0;
  }
}
