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

  /** Adds one unit (its world matrices must be current). `key` names its model and look. */
  add(key: string, root: THREE.Object3D): void {
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
      this.grow(batch, parts, Math.max(MIN_CAPACITY, batch.capacity * 2));
    }
    const slot = batch.count;
    parts.forEach((part, index) => {
      batch.meshes[index]?.setMatrixAt(slot, part.matrixWorld);
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

  private grow(batch: Batch, parts: THREE.Mesh[], capacity: number): void {
    const old = batch.meshes;
    batch.meshes = parts.map((part, index) => {
      const mesh = new THREE.InstancedMesh(part.geometry, part.material, capacity);
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
      this.scene.remove(mesh);
      mesh.dispose();
    }
    batch.capacity = capacity;
  }

  private drop(batch: Batch): void {
    for (const mesh of batch.meshes) {
      this.scene.remove(mesh);
      mesh.dispose();
    }
    batch.meshes = [];
    batch.capacity = 0;
  }
}
