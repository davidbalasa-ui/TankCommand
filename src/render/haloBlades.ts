// The Kesh Halo fighter's scythe blades. Render-only.
//
// The baked model is the open ring and the moth core; the four blades are drawn here so they can
// sweep around the ring. Each blade is solid and flashes gold as it passes through the open front
// or back of the ring, and fades out at the sides where the ring halves hide it.
import * as THREE from 'three';

export const HALO_MODEL_ID = 'unit.alien.halo';

// Blade arc radius relative to the ring's half-width (from the art script: ring 3.16, blades 3.6).
const BLADE_RADIUS = 3.6 / 3.16;
const BLADE_SPAN = (64 * Math.PI) / 180;
const SPIN_FLYING = 3.2; // rad/s
const SPIN_LANDED = 0.6;

export interface HaloBlades {
  group: THREE.Group;
  blades: { solid: THREE.MeshStandardMaterial; flash: THREE.MeshBasicMaterial; base: number }[];
  angle: number;
  geometries: THREE.BufferGeometry[];
}

function bladeGeometry(radius: number): THREE.BufferGeometry {
  const outer: THREE.Vector2[] = [];
  const inner: THREE.Vector2[] = [];
  const steps = 8;
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const a = -BLADE_SPAN / 2 + BLADE_SPAN * t;
    const width = radius * (0.015 + 0.09 * Math.sin(Math.PI * t ** 0.8));
    outer.push(new THREE.Vector2(radius * Math.cos(a), radius * Math.sin(a)));
    inner.push(new THREE.Vector2((radius - width) * Math.cos(a), (radius - width) * Math.sin(a)));
  }
  const shape = new THREE.Shape([...outer, ...inner.reverse()]);
  // Shape is drawn in XY; lay it flat in the model's XZ plane (+X forward).
  return new THREE.ShapeGeometry(shape).rotateX(Math.PI / 2);
}

/** Adds the blades to a Halo model root (unrotated, at its spawn transform). */
export function attachHaloBlades(root: THREE.Object3D): HaloBlades {
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  box.applyMatrix4(root.matrixWorld.clone().invert());
  const halfWidth = (box.max.z - box.min.z) / 2;
  const centre = box.getCenter(new THREE.Vector3());
  const radius = halfWidth * BLADE_RADIUS;
  const geometry = bladeGeometry(radius);
  const edge = bladeGeometry(radius * 1.01);
  const group = new THREE.Group();
  group.name = 'HaloBlades';
  // The ring is centred on the model origin in the art script; its back edge is the bbox minimum.
  group.position.set(box.min.x + halfWidth, centre.y, centre.z);
  const blades: HaloBlades['blades'] = [];
  for (let k = 0; k < 4; k += 1) {
    const base = (k * Math.PI) / 2;
    const solid = new THREE.MeshStandardMaterial({
      color: 0x8a6a3a,
      metalness: 0.8,
      roughness: 0.35,
      emissive: 0x3a2508,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const flash = new THREE.MeshBasicMaterial({
      color: 0xffd770,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const blade = new THREE.Mesh(geometry, solid);
    const glow = new THREE.Mesh(edge, flash);
    glow.position.y = 0.01;
    const holder = new THREE.Group();
    holder.rotation.y = base;
    holder.add(blade, glow);
    group.add(holder);
    blades.push({ solid, flash, base });
  }
  root.add(group);
  return { group, blades, angle: 0, geometries: [geometry, edge] };
}

/** Spins the blades and sets each one's visibility from where it is around the ring. */
export function updateHaloBlades(halo: HaloBlades, dt: number, flying: boolean): void {
  halo.angle = (halo.angle + dt * (flying ? SPIN_FLYING : SPIN_LANDED)) % (Math.PI * 2);
  halo.group.rotation.y = halo.angle;
  for (const blade of halo.blades) {
    // rotation.y turns +X toward -Z, so this is the blade's bearing from the nose.
    const facing = Math.abs(Math.cos(blade.base + halo.angle));
    blade.solid.opacity = facing ** 6;
    blade.flash.opacity = facing ** 24 * 0.9;
    blade.solid.visible = blade.solid.opacity > 0.02;
  }
}

export function disposeHaloBlades(halo: HaloBlades): void {
  for (const geometry of halo.geometries) {
    geometry.dispose();
  }
  for (const blade of halo.blades) {
    blade.solid.dispose();
    blade.flash.dispose();
  }
}
