// Draws units of the same model and side as one instanced mesh per material, so 192 units cost
// a few dozen draw calls instead of several hundred.
//
// Each unit keeps its own Object3D hierarchy (root, turret pivot, barrel sleeves, missiles) for
// positioning, bounds, effects and moving parts; its model meshes are hidden and drawn by shared
// InstancedMeshes. A model's parts that share a material are merged into one geometry whose
// vertices carry their part's index; every frame each unit's part world matrices (and tread
// texture offsets) are written to a float texture, one row per unit, and the vertex shader places
// each vertex with its own part's matrix. So a tank whose sleeves, missiles and wheels all move on
// their own still costs one draw per batch, not one per part. Parts that cannot be merged (several
// materials on one mesh, geometry with different attributes) keep one instanced mesh per part.
// Meshes added to a unit later (cargo, Halo blades) are not marked as instanced and draw normally.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

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

/** Texels per part in the part texture: three rows of the world matrix, then the U offset. */
const TEXELS_PER_PART = 4;
const PART_ATTRIBUTE = 'tcPart';

/** Shared parts: one mesh drawing several parts, placed per vertex from the part texture. */
interface MergedGroup {
  kind: 'merged';
  /** Indexes of its parts in the model's instanced part list. */
  parts: number[];
  mesh: THREE.InstancedMesh;
  texture: THREE.DataTexture;
  /** Shared with the materials' shader uniforms, so a regrown texture reaches them. */
  uniform: { value: THREE.DataTexture };
}

/** One part drawn by its own instanced mesh (the per-instance matrix places it). */
interface SingleGroup {
  kind: 'single';
  part: number;
  mesh: THREE.InstancedMesh;
}

type Group = MergedGroup | SingleGroup;

interface Batch {
  groups: Group[];
  /** How many instanced parts the model has (a changed count rebuilds the batch). */
  partCount: number;
  capacity: number;
  count: number;
}

/**
 * Same look: parts with materials that match on all of this are drawn with one of them. A unit's
 * parts each get their own copy of the model's material, so identity cannot be used.
 */
function materialKey(material: THREE.Material): string {
  const m = material as Partial<THREE.MeshStandardMaterial> & THREE.Material;
  const texture = (value: THREE.Texture | null | undefined): string => (value ? value.uuid : '-');
  return [
    m.type,
    m.name,
    m.color?.getHexString() ?? '-',
    m.emissive?.getHexString() ?? '-',
    m.emissiveIntensity ?? '-',
    m.roughness ?? '-',
    m.metalness ?? '-',
    m.envMapIntensity ?? '-',
    m.opacity,
    m.transparent,
    m.alphaTest,
    m.side,
    m.vertexColors,
    m.flatShading ?? '-',
    texture(m.map),
    texture(m.normalMap),
    texture(m.roughnessMap),
    texture(m.metalnessMap),
    texture(m.emissiveMap),
    texture(m.aoMap),
  ].join('|');
}

/** Shader code that reads a vertex's part matrix and texture offset from the part texture. */
const PART_COMMON = `
uniform highp sampler2D tcParts;
attribute float ${PART_ATTRIBUTE};
mat4 tcPartMatrix() {
  int x = int(${PART_ATTRIBUTE} + 0.5) * ${TEXELS_PER_PART};
  vec4 r0 = texelFetch(tcParts, ivec2(x, gl_InstanceID), 0);
  vec4 r1 = texelFetch(tcParts, ivec2(x + 1, gl_InstanceID), 0);
  vec4 r2 = texelFetch(tcParts, ivec2(x + 2, gl_InstanceID), 0);
  return mat4(vec4(r0.x, r1.x, r2.x, 0.0), vec4(r0.y, r1.y, r2.y, 0.0), vec4(r0.z, r1.z, r2.z, 0.0), vec4(r0.w, r1.w, r2.w, 1.0));
}
float tcPartScroll() {
  return texelFetch(tcParts, ivec2(int(${PART_ATTRIBUTE} + 0.5) * ${TEXELS_PER_PART} + 3, gl_InstanceID), 0).x;
}
`;

/** Patches a material so each vertex is placed by its part's matrix from the part texture. */
function partMaterial<T extends THREE.Material>(material: T, uniform: { value: THREE.DataTexture }, key: string): T {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.tcParts = uniform;
    // The part matrix is fetched once per vertex, at the top of main, and reused below.
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `#include <common>\n${PART_COMMON}`)
      .replace('void main() {', 'void main() {\n\tmat4 tcM = tcPartMatrix();')
      .replace(
        '#include <beginnormal_vertex>',
        `#include <beginnormal_vertex>\nobjectNormal = mat3(tcM) * objectNormal;\n#ifdef USE_TANGENT\nobjectTangent = mat3(tcM) * objectTangent;\n#endif`,
      )
      .replace('#include <begin_vertex>', '#include <begin_vertex>\ntransformed = (tcM * vec4(transformed, 1.0)).xyz;')
      .replace('#include <uv_vertex>', '#include <uv_vertex>\n#ifdef USE_MAP\n\tvMapUv.x += tcPartScroll();\n#endif');
  };
  material.customProgramCacheKey = () => key;
  return material;
}

function partTexture(width: number, capacity: number, previous?: THREE.DataTexture, rows = 0): THREE.DataTexture {
  const data = new Float32Array(width * capacity * 4);
  if (previous) {
    data.set((previous.image.data as Float32Array).subarray(0, width * rows * 4));
  }
  const texture = new THREE.DataTexture(data, width, capacity, THREE.RGBAFormat, THREE.FloatType);
  texture.minFilter = THREE.NearestFilter;
  texture.magFilter = THREE.NearestFilter;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;
  return texture;
}

/** One geometry for several parts, each vertex tagged with its part's place in the group. */
function mergeParts(geometries: THREE.BufferGeometry[]): THREE.BufferGeometry | null {
  const tagged = geometries.map((source, index) => {
    const geometry = source.clone();
    for (const name of Object.keys(geometry.attributes)) {
      if (name === SCROLL_ATTRIBUTE) {
        geometry.deleteAttribute(name);
      }
    }
    const count = geometry.getAttribute('position').count;
    geometry.setAttribute(PART_ATTRIBUTE, new THREE.BufferAttribute(new Float32Array(count).fill(index), 1));
    return geometry;
  });
  // Indexed and unindexed parts cannot be merged together; index them all.
  if (tagged.some((geometry) => geometry.index) && tagged.some((geometry) => !geometry.index)) {
    for (const geometry of tagged) {
      if (!geometry.index) {
        const count = geometry.getAttribute('position').count;
        geometry.setIndex(Array.from({ length: count }, (_, i) => i));
      }
    }
  }
  const merged = mergeGeometries(tagged, false);
  for (const geometry of tagged) {
    geometry.dispose();
  }
  return merged;
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
    if (!batch || batch.partCount !== parts.length) {
      if (batch) {
        this.drop(batch);
      }
      batch = { groups: this.buildGroups(parts, geometries), partCount: parts.length, capacity: 0, count: 0 };
      this.batches.set(key, batch);
    }
    if (batch.count >= batch.capacity) {
      this.grow(batch, Math.max(MIN_CAPACITY, batch.capacity * 2), parts, geometries);
    }
    const slot = batch.count;
    for (const group of batch.groups) {
      if (group.kind === 'single') {
        const part = parts[group.part];
        if (!part) {
          continue;
        }
        group.mesh.setMatrixAt(slot, part.matrixWorld);
        const scroll = scrollAttribute(group.mesh);
        if (scroll) {
          scroll.setX(slot, typeof part.userData[UV_SCROLL] === 'number' ? part.userData[UV_SCROLL] : 0);
        }
        continue;
      }
      const data = group.texture.image.data as Float32Array;
      const width = group.parts.length * TEXELS_PER_PART;
      group.parts.forEach((partIndex, local) => {
        const part = parts[partIndex];
        if (!part) {
          return;
        }
        const e = part.matrixWorld.elements;
        let at = (slot * width + local * TEXELS_PER_PART) * 4;
        // Rows of the world matrix (it is stored by column), then the tread texture offset.
        for (let row = 0; row < 3; row += 1) {
          data[at] = e[row] ?? 0;
          data[at + 1] = e[row + 4] ?? 0;
          data[at + 2] = e[row + 8] ?? 0;
          data[at + 3] = e[row + 12] ?? 0;
          at += 4;
        }
        data[at] = typeof part.userData[UV_SCROLL] === 'number' ? part.userData[UV_SCROLL] : 0;
      });
    }
    batch.count += 1;
  }

  /** Ends a frame: uploads the matrices and sets how many instances each batch draws. */
  end(castShadow: boolean): void {
    for (const batch of this.batches.values()) {
      for (const group of batch.groups) {
        const mesh = group.mesh;
        mesh.count = batch.count;
        mesh.visible = batch.count > 0;
        mesh.castShadow = castShadow;
        if (group.kind === 'merged') {
          if (batch.count > 0) {
            group.texture.needsUpdate = true;
          }
          continue;
        }
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

  /** Which parts share a draw: same material and mergeable geometry; the rest go alone. */
  private buildGroups(parts: THREE.Mesh[], geometries?: readonly THREE.BufferGeometry[]): Group[] {
    const groups: Group[] = [];
    const byLook = new Map<string, number[]>();
    parts.forEach((part, index) => {
      if (Array.isArray(part.material)) {
        groups.push(this.single(part, index, geometries, 0));
        return;
      }
      const look = materialKey(part.material);
      const list = byLook.get(look) ?? [];
      list.push(index);
      byLook.set(look, list);
    });
    for (const list of byLook.values()) {
      const merged = list.length > 1 ? this.merged(parts, list, geometries) : null;
      if (merged) {
        groups.push(merged);
        continue;
      }
      for (const index of list) {
        const part = parts[index];
        if (part) {
          groups.push(this.single(part, index, geometries, 0));
        }
      }
    }
    return groups;
  }

  private merged(parts: THREE.Mesh[], list: number[], geometries?: readonly THREE.BufferGeometry[]): MergedGroup | null {
    const first = parts[list[0] ?? -1];
    if (!first || Array.isArray(first.material)) {
      return null;
    }
    const sources = list.map((index) => geometries?.[index] ?? parts[index]?.geometry);
    if (sources.some((geometry) => !geometry)) {
      return null;
    }
    const geometry = mergeParts(sources as THREE.BufferGeometry[]);
    if (!geometry) {
      return null;
    }
    const texture = partTexture(list.length * TEXELS_PER_PART, MIN_CAPACITY);
    const uniform = { value: texture };
    const material = partMaterial(first.material.clone(), uniform, 'tc-unit-parts');
    const mesh = new THREE.InstancedMesh(geometry, material, MIN_CAPACITY);
    // Every vertex is placed by the part texture; the instance matrices stay identity.
    mesh.customDepthMaterial = partMaterial(
      new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking }),
      uniform,
      'tc-unit-parts-depth',
    );
    mesh.frustumCulled = false;
    mesh.receiveShadow = true;
    mesh.name = 'UnitInstances';
    mesh.count = 0;
    this.scene.add(mesh);
    return { kind: 'merged', parts: list, mesh, texture, uniform };
  }

  private single(
    part: THREE.Mesh,
    index: number,
    geometries: readonly THREE.BufferGeometry[] | undefined,
    capacity: number,
  ): SingleGroup {
    return { kind: 'single', part: index, mesh: this.singleMesh(part, geometries?.[index] ?? part.geometry, Math.max(capacity, MIN_CAPACITY)) };
  }

  private singleMesh(part: THREE.Mesh, source: THREE.BufferGeometry, capacity: number, previous?: THREE.InstancedMesh, rows = 0): THREE.InstancedMesh {
    const scrolls = typeof part.userData[UV_SCROLL] === 'number' && !Array.isArray(part.material);
    // A scrolling part gets its own geometry copy to hold the per-instance offset.
    const geometry = scrolls ? source.clone() : source;
    if (scrolls) {
      const values = new THREE.InstancedBufferAttribute(new Float32Array(capacity), 1);
      values.setUsage(THREE.DynamicDrawUsage);
      const before = previous ? scrollAttribute(previous) : null;
      for (let i = 0; before && i < rows; i += 1) {
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
    mesh.count = 0;
    if (previous) {
      const matrix = new THREE.Matrix4();
      for (let i = 0; i < rows; i += 1) {
        previous.getMatrixAt(i, matrix);
        mesh.setMatrixAt(i, matrix);
      }
    }
    this.scene.add(mesh);
    return mesh;
  }

  private grow(batch: Batch, capacity: number, parts: THREE.Mesh[], geometries?: readonly THREE.BufferGeometry[]): void {
    batch.groups = batch.groups.map((group) => {
      if (group.kind === 'merged') {
        const width = group.parts.length * TEXELS_PER_PART;
        const texture = partTexture(width, capacity, group.texture, batch.count);
        group.texture.dispose();
        group.texture = texture;
        group.uniform.value = texture;
        if (capacity > group.mesh.instanceMatrix.count) {
          const mesh = new THREE.InstancedMesh(group.mesh.geometry, group.mesh.material, capacity);
          mesh.customDepthMaterial = group.mesh.customDepthMaterial;
          mesh.frustumCulled = false;
          mesh.receiveShadow = true;
          mesh.name = 'UnitInstances';
          this.scene.remove(group.mesh);
          group.mesh.dispose();
          this.scene.add(mesh);
          group.mesh = mesh;
        }
        return group;
      }
      if (capacity <= group.mesh.instanceMatrix.count) {
        return group;
      }
      const old = group.mesh;
      const part = parts[group.part];
      if (!part) {
        return group;
      }
      const mesh = this.singleMesh(part, geometries?.[group.part] ?? part.geometry, capacity, old, batch.count);
      this.release(group);
      return { ...group, mesh };
    });
    batch.capacity = capacity;
  }

  private release(group: Group): void {
    this.scene.remove(group.mesh);
    if (group.kind === 'merged') {
      group.mesh.geometry.dispose();
      (group.mesh.material as THREE.Material).dispose();
      group.mesh.customDepthMaterial?.dispose();
      group.texture.dispose();
    } else if (scrollAttribute(group.mesh)) {
      // Only the scrolling parts own their geometry copy; the rest share the model's.
      group.mesh.geometry.dispose();
    }
    group.mesh.dispose();
  }

  private drop(batch: Batch): void {
    for (const group of batch.groups) {
      this.release(group);
    }
    batch.groups = [];
    batch.capacity = 0;
  }
}
