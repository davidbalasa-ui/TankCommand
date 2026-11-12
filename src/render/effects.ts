// Weapon and impact effects. Render-only: nothing here feeds back into the sim.
//
// Each weapon kind (WeaponStats.kind, carried on the projectile) gets its own look:
//   laser        Terran fighter: cyan energy bolts with a bright core, small cyan burst on impact.
//   bombs        Terran bomber: a dark finned bomb dropping from the bomber, a fireball, shock ring,
//                flying dirt and a scorch mark.
//   lightning    Kesh fighter: a jagged gold-white arc from the gun ports to the target, re-drawn
//                every frame so it crackles, gold sparks on impact.
//   ground_beam  Kesh saucer: a thick gold beam from the saucer to the ground that tears it open:
//                a big gold-white blast, shock ring, rock chunks thrown up and a deep scorch.
//   spore        Third faction (sample): a slow pulsing pod that bursts into a lingering spore cloud.
//   (anything else) tank shells: a short hot tracer and a small fiery flash.
import * as THREE from 'three';

type Palette = 'fire' | 'gold' | 'cyan' | 'spore';

const PALETTES: Record<Palette, { core: number; outer: number; ring: number }> = {
  fire: { core: 0xfff1c0, outer: 0xff6a1a, ring: 0xffb050 },
  gold: { core: 0xfffbe8, outer: 0xffb52a, ring: 0xffd27a },
  cyan: { core: 0xeaffff, outer: 0x36d6ff, ring: 0x8ff0ff },
  spore: { core: 0xf3ffb0, outer: 0xb6c94a, ring: 0xd8e57a },
};

interface Particle {
  mesh: THREE.Mesh;
  age: number;
  life: number;
  vx: number;
  vy: number;
  vz: number;
  gravity: number;
  spin: number;
  grow: number; // final scale multiplier (1 = no growth), eased out over the life
  baseScale?: THREE.Vector3;
  fade: number; // start opacity
  kind: 'ball' | 'ring' | 'chunk' | 'smoke' | 'scorch' | 'cloud';
}

function additive(color: number, opacity = 1): THREE.MeshBasicMaterial {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
}

export class Effects {
  private readonly particles: Particle[] = [];
  private readonly sphere = new THREE.IcosahedronGeometry(1, 1);
  private readonly ring = new THREE.RingGeometry(0.82, 1, 36);
  private readonly disc = new THREE.CircleGeometry(1, 20);
  private readonly chunk = new THREE.DodecahedronGeometry(1, 0);
  private readonly chunkMaterial = new THREE.MeshStandardMaterial({ color: 0x3a3028, roughness: 0.95, flatShading: true });
  private readonly glowChunkMaterial = new THREE.MeshStandardMaterial({
    color: 0x5a3a20,
    emissive: 0xff7a1a,
    emissiveIntensity: 0.8,
    roughness: 0.8,
    flatShading: true,
  });
  private readonly bolt = new THREE.CylinderGeometry(1, 1, 1, 6, 1, true).rotateX(Math.PI / 2);
  private readonly bombGeometry = (() => {
    const body = new THREE.CapsuleGeometry(0.22, 0.7, 3, 8).rotateX(Math.PI / 2);
    return body;
  })();
  private readonly bombMaterial = new THREE.MeshStandardMaterial({ color: 0x23272c, metalness: 0.7, roughness: 0.45 });

  constructor(private readonly scene: THREE.Scene) {}

  get count(): number {
    return this.particles.length;
  }

  // ---- projectiles ---------------------------------------------------------------------
  /** A mesh for a projectile in flight, by weapon kind. The caller positions and aims it (+Z forward). */
  projectileMesh(kind: string | undefined, human: boolean): THREE.Object3D {
    const group = new THREE.Group();
    if (kind === 'laser') {
      const outer = new THREE.Mesh(this.bolt, additive(0x2fd3ff, 0.75));
      outer.scale.set(0.16, 0.16, 2.6);
      const core = new THREE.Mesh(this.bolt, additive(0xf0ffff, 1));
      core.scale.set(0.06, 0.06, 2.4);
      group.add(outer, core);
    } else if (kind === 'bombs') {
      const bomb = new THREE.Mesh(this.bombGeometry, this.bombMaterial);
      bomb.castShadow = true;
      const band = new THREE.Mesh(this.sphere, additive(0xff7a1a, 0.9));
      band.scale.set(0.12, 0.12, 0.12);
      band.position.z = -0.5;
      group.add(bomb, band);
    } else if (kind === 'lightning' || kind === 'ground_beam') {
      // The arc or beam itself is drawn from the shooter each frame; this is the bright head.
      const head = new THREE.Mesh(this.sphere, additive(kind === 'lightning' ? 0xfff2c0 : 0xfffbe8, 1));
      head.scale.setScalar(kind === 'lightning' ? 0.22 : 0.45);
      group.add(head);
    } else if (kind === 'spore') {
      const pod = new THREE.Mesh(this.sphere, new THREE.MeshStandardMaterial({ color: 0x9aa83a, emissive: 0x6a7a10, roughness: 0.6 }));
      pod.scale.setScalar(0.4);
      group.add(pod);
    } else {
      const tracer = new THREE.Mesh(this.bolt, additive(human ? 0xffd27a : 0xffc04a, 0.95));
      tracer.scale.set(0.08, 0.08, 1.3);
      group.add(tracer);
    }
    return group;
  }

  disposeProjectileMesh(object: THREE.Object3D): void {
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial) {
        child.material.dispose();
      }
      if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial && child.material !== this.bombMaterial) {
        child.material.dispose();
      }
    });
  }

  /**
   * A jagged arc from a to b (Arcadian lightning). Lives one frame unless ttl is given, so calling it
   * every frame makes it crackle.
   */
  lightning(a: THREE.Vector3, b: THREE.Vector3, color = 0xffe7a0, ttl = 0.05, segments = 9, jitter = 0.5): void {
    const points: THREE.Vector3[] = [];
    const dir = new THREE.Vector3().subVectors(b, a);
    const side = new THREE.Vector3(-dir.z, 0, dir.x).normalize();
    for (let i = 0; i <= segments; i += 1) {
      const t = i / segments;
      const p = new THREE.Vector3().lerpVectors(a, b, t);
      if (i > 0 && i < segments) {
        const amount = jitter * Math.sin(Math.PI * t);
        p.addScaledVector(side, (Math.random() * 2 - 1) * amount);
        p.y += (Math.random() * 2 - 1) * amount * 0.7;
      }
      points.push(p);
    }
    // Thin additive tubes per segment: GL lines are 1px on most phones, too faint to read.
    const forward = new THREE.Vector3(0, 0, 1);
    for (let i = 0; i < segments; i += 1) {
      const p0 = points[i];
      const p1 = points[i + 1];
      if (!p0 || !p1) {
        continue;
      }
      const length = p0.distanceTo(p1);
      const mid = new THREE.Vector3().addVectors(p0, p1).multiplyScalar(0.5);
      const look = new THREE.Quaternion().setFromUnitVectors(forward, new THREE.Vector3().subVectors(p1, p0).normalize());
      for (const [width, opacity, tint] of [[0.05, 1, 0xffffff], [0.16, 0.6, color]] as const) {
        const mesh = new THREE.Mesh(this.bolt, additive(tint, opacity));
        mesh.position.copy(mid);
        mesh.quaternion.copy(look);
        mesh.scale.set(width, width, length + width);
        this.add(mesh, ttl, { fade: opacity, kind: 'ball' });
      }
    }
  }

  /** A straight beam from a to b (the saucer's ground beam) with a white core and a gold sheath. */
  beam(a: THREE.Vector3, b: THREE.Vector3, width: number, ttl = 0.05): void {
    const length = a.distanceTo(b);
    if (length < 0.01) {
      return;
    }
    const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
    const look = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3().subVectors(b, a).normalize());
    for (const [scale, color, opacity] of [[1, 0xffb52a, 0.5], [0.45, 0xfffbe8, 1]] as const) {
      const mesh = new THREE.Mesh(this.bolt, additive(color, opacity));
      mesh.position.copy(mid);
      mesh.quaternion.copy(look);
      const flicker = 0.85 + Math.random() * 0.3;
      mesh.scale.set(width * scale * flicker, width * scale * flicker, length);
      this.add(mesh, ttl, { fade: opacity, kind: 'ball' });
    }
  }

  // ---- impacts -------------------------------------------------------------------------
  /** Impact effect for a projectile that just ended at (x, y, z) on ground height gy. */
  impact(kind: string | undefined, x: number, y: number, z: number, gy: number, splash: number): void {
    if (kind === 'laser') {
      this.burst(x, y, z, 0.7, 'cyan', 0.22);
      this.sparks(x, y, z, 5, 0x9ff4ff, 5);
    } else if (kind === 'lightning') {
      this.burst(x, y, z, 0.8, 'gold', 0.22);
      this.sparks(x, y, z, 8, 0xffe08a, 7);
    } else if (kind === 'bombs') {
      const size = Math.max(2.2, splash);
      this.burst(x, gy + 0.6, z, size * 0.9, 'fire', 0.55);
      this.shockRing(x, gy + 0.15, z, size * 1.6, 'fire', 0.5);
      this.debris(x, gy, z, 10, 0.18, 9, false);
      this.smoke(x, gy + 1.0, z, size, 4);
      this.scorch(x, gy, z, size * 0.75, 9);
    } else if (kind === 'ground_beam') {
      const size = Math.max(3, splash);
      this.burst(x, gy + 0.8, z, size * 1.05, 'gold', 0.6);
      this.burst(x, gy + 0.4, z, size * 0.55, 'fire', 0.9);
      // An eruption column: the beam punches the ground and throws fire straight up.
      const column = new THREE.Mesh(this.sphere, additive(0xffc24a, 0.7));
      column.position.set(x, gy + size * 0.5, z);
      column.scale.set(size * 0.28, size * 0.9, size * 0.28);
      this.add(column, 0.55, { grow: 1.6, fade: 0.7, vy: 3 });
      this.shockRing(x, gy + 0.15, z, size * 1.5, 'gold', 0.6);
      this.debris(x, gy, z, 16, 0.26, 13, true);
      this.smoke(x, gy + 1.2, z, size * 1.1, 5);
      this.scorch(x, gy, z, size * 0.95, 14);
    } else if (kind === 'spore') {
      this.cloud(x, gy + 0.8, z, Math.max(2.5, splash));
    } else {
      this.burst(x, y, z, 0.75, 'fire', 0.22);
      if (splash > 0.6) {
        this.debris(x, gy, z, 4, 0.12, 6, false);
      }
    }
  }

  /**
   * A packed tower unfolding into its structure: a dust ring and a puff of smoke for Terran
   * builds, a gold glow ring and sparks for Arcadian ones. `size` is the structure's width.
   */
  deploy(x: number, gy: number, z: number, size: number, alien: boolean): void {
    if (alien) {
      this.shockRing(x, gy + 0.2, z, size * 1.3, 'gold', 0.8);
      this.burst(x, gy + 0.6, z, size * 0.5, 'gold', 0.5);
      this.sparks(x, gy + 0.5, z, 10, 0xffe08a, 5);
    } else {
      this.shockRing(x, gy + 0.15, z, size * 1.3, 'fire', 0.6);
      this.smoke(x, gy + 0.4, z, size * 0.3, 3);
      this.debris(x, gy, z, 8, 0.14, 6, false);
    }
  }

  /** A short muzzle flash where a shot leaves the gun. */
  muzzle(x: number, y: number, z: number, kind: string | undefined): void {
    const palette: Palette = kind === 'laser' ? 'cyan' : kind === 'lightning' || kind === 'ground_beam' ? 'gold' : 'fire';
    this.burst(x, y, z, kind === 'ground_beam' ? 1.2 : 0.45, palette, 0.12);
  }

  private burst(x: number, y: number, z: number, size: number, palette: Palette, life: number): void {
    const colors = PALETTES[palette];
    const core = new THREE.Mesh(this.sphere, additive(colors.core, 1));
    core.position.set(x, y, z);
    core.scale.setScalar(size * 0.45);
    this.add(core, life * 0.7, { grow: 1.9, fade: 1 });
    const outer = new THREE.Mesh(this.sphere, additive(colors.outer, 0.55));
    outer.position.set(x, y, z);
    outer.scale.setScalar(size * 0.6);
    this.add(outer, life, { grow: 1.7, fade: 0.55 });
  }

  private shockRing(x: number, y: number, z: number, size: number, palette: Palette, life: number): void {
    const ring = new THREE.Mesh(this.ring, additive(PALETTES[palette].ring, 0.85));
    ring.material.side = THREE.DoubleSide;
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(x, y, z);
    ring.scale.setScalar(size * 0.15);
    this.add(ring, life, { grow: 1 / 0.15, fade: 0.85, kind: 'ring' });
  }

  /**
   * Each particle is its own draw call, so in a big battle the optional bits (sparks, debris, smoke)
   * thin out: full detail up to 60 live particles, then fewer, none past 200.
   */
  private thin(count: number): number {
    const live = this.particles.length;
    if (live < 60) {
      return count;
    }
    return live > 200 ? 0 : Math.max(1, Math.round(count * (1 - (live - 60) / 140)));
  }

  private sparks(x: number, y: number, z: number, count: number, color: number, speed: number): void {
    count = this.thin(count);
    for (let i = 0; i < count; i += 1) {
      const spark = new THREE.Mesh(this.sphere, additive(color, 1));
      spark.position.set(x, y, z);
      spark.scale.setScalar(0.07);
      const a = Math.random() * Math.PI * 2;
      const up = Math.random() * 0.8 + 0.2;
      this.add(spark, 0.25 + Math.random() * 0.2, {
        vx: Math.cos(a) * speed * (1 - up * 0.5),
        vy: up * speed,
        vz: Math.sin(a) * speed * (1 - up * 0.5),
        gravity: 14,
        fade: 1,
      });
    }
  }

  private debris(x: number, gy: number, z: number, count: number, size: number, speed: number, glowing: boolean): void {
    count = this.thin(count);
    for (let i = 0; i < count; i += 1) {
      const rock = new THREE.Mesh(this.chunk, glowing && i % 3 === 0 ? this.glowChunkMaterial : this.chunkMaterial);
      rock.castShadow = true;
      rock.position.set(x + (Math.random() - 0.5), gy + 0.3, z + (Math.random() - 0.5));
      rock.scale.setScalar(size * (0.6 + Math.random() * 0.9));
      const a = Math.random() * Math.PI * 2;
      const up = 0.55 + Math.random() * 0.45;
      this.add(rock, 0.9 + Math.random() * 0.5, {
        vx: Math.cos(a) * speed * (1 - up * 0.6),
        vy: up * speed,
        vz: Math.sin(a) * speed * (1 - up * 0.6),
        gravity: 24,
        spin: 8 + Math.random() * 8,
        kind: 'chunk',
        ground: gy,
      });
    }
  }

  private smoke(x: number, y: number, z: number, size: number, count: number): void {
    count = this.thin(count);
    for (let i = 0; i < count; i += 1) {
      const puff = new THREE.Mesh(
        this.sphere,
        new THREE.MeshBasicMaterial({ color: 0x4a423a, transparent: true, opacity: 0.38, depthWrite: false }),
      );
      puff.position.set(x + (Math.random() - 0.5) * size, y + Math.random() * size * 0.4, z + (Math.random() - 0.5) * size);
      puff.scale.setScalar(size * (0.35 + Math.random() * 0.25));
      this.add(puff, 1.6 + Math.random(), { vy: 1.2 + Math.random(), grow: 2.2, fade: 0.38, kind: 'smoke' });
    }
  }

  private scorch(x: number, gy: number, z: number, radius: number, life: number): void {
    const mark = new THREE.Mesh(
      this.disc,
      new THREE.MeshBasicMaterial({ color: 0x0c0a08, transparent: true, opacity: 0.7, depthWrite: false }),
    );
    mark.rotation.x = -Math.PI / 2;
    mark.rotation.z = Math.random() * Math.PI;
    mark.position.set(x, gy + 0.04, z);
    mark.scale.set(radius, radius * (0.8 + Math.random() * 0.3), 1);
    this.add(mark, life, { fade: 0.7, kind: 'scorch' });
    const glow = new THREE.Mesh(this.disc, additive(0xff6a1a, 0.6));
    glow.rotation.x = -Math.PI / 2;
    glow.position.set(x, gy + 0.05, z);
    glow.scale.set(radius * 0.55, radius * 0.5, 1);
    this.add(glow, Math.min(2.5, life), { fade: 0.6, kind: 'scorch' });
  }

  private cloud(x: number, y: number, z: number, radius: number): void {
    for (let i = 0; i < 9; i += 1) {
      const puff = new THREE.Mesh(
        this.sphere,
        new THREE.MeshBasicMaterial({ color: i % 3 === 0 ? 0xe3ef8a : 0xa9b84a, transparent: true, opacity: 0.45, depthWrite: false }),
      );
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * radius * 0.6;
      puff.position.set(x + Math.cos(a) * r, y + Math.random() * radius * 0.5, z + Math.sin(a) * r);
      puff.scale.setScalar(radius * (0.3 + Math.random() * 0.25));
      this.add(puff, 3 + Math.random() * 1.5, { vy: 0.3, grow: 1.8, fade: 0.45, kind: 'cloud', spin: 0.6 });
    }
    this.burst(x, y, z, radius * 0.5, 'spore', 0.4);
  }

  private add(
    mesh: THREE.Mesh,
    life: number,
    options: Partial<Pick<Particle, 'vx' | 'vy' | 'vz' | 'gravity' | 'spin' | 'grow' | 'fade' | 'kind'>> & { ground?: number } = {},
  ): void {
    this.scene.add(mesh);
    mesh.userData.ground = options.ground;
    this.particles.push({
      mesh,
      age: 0,
      life,
      vx: options.vx ?? 0,
      vy: options.vy ?? 0,
      vz: options.vz ?? 0,
      gravity: options.gravity ?? 0,
      spin: options.spin ?? 0,
      grow: options.grow ?? 1,
      baseScale: mesh.scale.clone(),
      fade: options.fade ?? 1,
      kind: options.kind ?? 'ball',
    });
  }

  update(dt: number): void {
    for (let i = this.particles.length - 1; i >= 0; i -= 1) {
      const p = this.particles[i];
      if (!p) {
        continue;
      }
      p.age += dt;
      const t = p.age / p.life;
      const mesh = p.mesh;
      if (t >= 1) {
        this.remove(p);
        this.particles.splice(i, 1);
        continue;
      }
      p.vy -= p.gravity * dt;
      mesh.position.x += p.vx * dt;
      mesh.position.y += p.vy * dt;
      mesh.position.z += p.vz * dt;
      const ground = mesh.userData.ground as number | undefined;
      if (p.kind === 'chunk' && ground !== undefined && mesh.position.y < ground + 0.1) {
        mesh.position.y = ground + 0.1;
        p.vx *= 0.4;
        p.vz *= 0.4;
        p.vy = Math.abs(p.vy) * 0.25;
        p.spin *= 0.5;
      }
      if (p.spin) {
        mesh.rotation.x += p.spin * dt;
        mesh.rotation.y += p.spin * 0.7 * dt;
      }
      if (p.grow !== 1 && p.baseScale) {
        const eased = 1 - (1 - t) * (1 - t);
        mesh.scale.copy(p.baseScale).multiplyScalar(1 + (p.grow - 1) * eased);
      }
      const material = mesh.material as THREE.Material & { opacity?: number };
      if (p.kind !== 'chunk' && material.transparent) {
        const fadeIn = p.kind === 'smoke' || p.kind === 'cloud' ? Math.min(1, t * 6) : 1;
        material.opacity = p.fade * fadeIn * (p.kind === 'scorch' ? Math.min(1, (1 - t) * 3) : 1 - t);
      } else if (p.kind === 'chunk' && t > 0.8) {
        mesh.scale.multiplyScalar(0.9);
      }
    }
  }

  private remove(p: Particle): void {
    this.scene.remove(p.mesh);
    const material = p.mesh.material;
    if (material instanceof THREE.Material && material !== this.chunkMaterial && material !== this.glowChunkMaterial) {
      material.dispose();
    }
  }

  dispose(): void {
    for (const p of this.particles) {
      this.remove(p);
    }
    this.particles.length = 0;
    for (const g of [this.sphere, this.ring, this.disc, this.chunk, this.bolt, this.bombGeometry]) {
      g.dispose();
    }
    for (const m of [this.chunkMaterial, this.glowChunkMaterial, this.bombMaterial]) {
      m.dispose();
    }
  }
}
