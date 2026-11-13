// Burning wrecks. When a vehicle dies its own model stays behind, blackened and tilted, with the
// turret knocked askew, burning for a few seconds and then smoking before it sinks away. Wrecks are
// render-only (the sim's wreck list just marks where one died) and are drawn instanced per model.
import * as THREE from 'three';
import { markInstanced, type UnitInstances } from './unitInstances';
import type { Burner, Effects } from './effects';

const WRECK_LIFE_SEC = 30;
const SINK_SEC = 4;
const MAX_WRECKS = 48;
const TOSS_SEC = 0.9;

interface Wreck {
  root: THREE.Object3D;
  key: string;
  age: number;
  baseY: number;
  burner: Burner | null;
  pivot: THREE.Object3D | null;
  toss: { base: THREE.Vector3; dx: number; dz: number; spin: number; tiltX: number; tiltZ: number } | null;
}

const rand = (a: number, b: number): number => a + Math.random() * (b - a);

export class WreckField {
  private readonly wrecks: Wreck[] = [];
  /** One blackened copy per unit type; every wreck of that type clones it and shares its materials. */
  private readonly templates = new Map<string, THREE.Object3D>();

  constructor(
    private readonly group: THREE.Group,
    private readonly instances: UnitInstances,
    private readonly effects: Effects,
    private readonly darken: (root: THREE.Object3D) => void,
  ) {}

  get count(): number {
    return this.wrecks.length;
  }

  /**
   * Leaves a wreck where a unit died. `source` is the dead unit's posed model; `gy` is the ground
   * under it; `size` is its visual scale; `air` crashes it in from the sky.
   */
  add(source: THREE.Object3D, typeId: string, gy: number, size: number, air: boolean): void {
    let template = this.templates.get(typeId);
    if (!template) {
      template = source.clone(true);
      this.darken(template);
      this.templates.set(typeId, template);
    }
    const root = template.clone(true);
    markInstanced(root);
    root.position.set(source.position.x, gy, source.position.z);
    root.rotation.copy(source.rotation);
    root.scale.copy(source.scale);
    // Settled at an angle, a little lower: it sagged on broken tracks or dropped out of the sky.
    root.rotation.x += rand(-0.1, 0.1) + (air ? rand(-0.35, 0.35) : 0);
    root.rotation.z += rand(-0.08, 0.08) + (air ? rand(-0.25, 0.1) : 0);
    const baseY = gy - (air ? 0.35 : 0.12) * size;
    root.position.y = baseY;
    const pivot = root.getObjectByName('TurretPivot') ?? null;
    const sourcePivot = source.getObjectByName('TurretPivot');
    if (pivot && sourcePivot) {
      pivot.rotation.copy(sourcePivot.rotation);
      pivot.position.copy(sourcePivot.position);
    }
    const toss =
      pivot && !air && Math.random() < 0.65
        ? {
            base: pivot.position.clone(),
            dx: rand(-0.6, -0.2),
            dz: rand(-0.3, 0.3),
            spin: rand(-1.5, 1.5),
            tiltX: rand(-0.35, 0.35),
            tiltZ: rand(0.15, 0.4),
          }
        : null;
    this.group.add(root);
    const burner = this.effects.addBurner(root.position.x, gy + 0.9 * size, root.position.z, size, rand(6, 9), rand(16, 20));
    this.wrecks.push({ root, key: `wreck|${typeId}`, age: 0, baseY, burner, pivot, toss });
    while (this.wrecks.length > MAX_WRECKS) {
      const oldest = this.wrecks.shift();
      if (oldest) {
        this.remove(oldest);
      }
    }
  }

  update(dt: number, shadows: boolean): void {
    this.instances.begin();
    for (let i = this.wrecks.length - 1; i >= 0; i -= 1) {
      const wreck = this.wrecks[i];
      if (!wreck) {
        continue;
      }
      wreck.age += dt;
      if (wreck.age >= WRECK_LIFE_SEC) {
        this.remove(wreck);
        this.wrecks.splice(i, 1);
        continue;
      }
      const sinking = wreck.age - (WRECK_LIFE_SEC - SINK_SEC);
      wreck.root.position.y = wreck.baseY - (sinking > 0 ? (sinking / SINK_SEC) * 2 * wreck.root.scale.y : 0);
      if (wreck.toss && wreck.pivot) {
        // The turret is blown up and drops back askew on the hull.
        const t = Math.min(1, wreck.age / TOSS_SEC);
        const { base } = wreck.toss;
        const height = 4 * t * (1 - t) * 1.6;
        wreck.pivot.position.set(base.x + wreck.toss.dx * t, base.y + height, base.z + wreck.toss.dz * t);
        wreck.pivot.rotation.x = wreck.toss.tiltX * t;
        wreck.pivot.rotation.z = wreck.toss.tiltZ * t + (t < 1 ? Math.sin(t * Math.PI) * wreck.toss.spin * 0.6 : 0);
        if (t >= 1) {
          wreck.toss = null;
        }
      }
      wreck.root.updateMatrixWorld(true);
      this.instances.add(wreck.key, wreck.root);
    }
    this.instances.end(shadows);
  }

  private remove(wreck: Wreck): void {
    this.group.remove(wreck.root);
    if (wreck.burner) {
      wreck.burner.alive = false;
    }
  }

  clear(): void {
    for (const wreck of this.wrecks) {
      this.remove(wreck);
    }
    this.wrecks.length = 0;
    this.templates.clear();
  }
}
