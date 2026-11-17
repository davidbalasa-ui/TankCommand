// Terran muzzle blast for the line-up viewer: soft layered sprites instead of the solid flash mesh.
// Everything is a pure function of `u` = seconds since the shot, so frame-by-frame clips are exact.
// Layers (per shot; S = gun size in metres, H = 0..1 how heavy the gun is):
//   core     white-hot bloom in a wide cyan halo, full on the shot frame, gone in ~0.1 s
//   tongue   a cyan-white plasma tongue from the (recoiling) muzzle down the barrel line, ~0.13 s
//   brake    two short side jets out of the muzzle brake, ~0.08 s
//   ring     a pale cyan shock ring racing outward, tilted toward the camera so it never goes edge-on
//   sparks   hot orange/white streaks thrown forward, falling, ~0.3 s
//   ember    the muzzle itself stays orange-hot and cools over ~0.9 s (rides the barrel tip)
//   smoke    grey-blue puffs pushed forward, dragging to a stop, rising and spreading, ~1.5-2.2 s
//   dust     heavy guns only: a flat dust ring and low dust puffs blown off the ground under the gun
//   light    a point light that flashes the gun and the ground for a few frames
// The game's version lives in src/render/effects.ts (muzzle); this is the look to port.
import * as THREE from 'three';

export const LIFE = 2.3;

// Baked into a DataTexture rather than a canvas: a canvas stores premultiplied alpha, which crushes
// the RGB of faint texels into a few levels and shows as contour rings on big soft sprites.
const canvasTex = (w, h, draw) => {
  const data = new Uint8Array(w * h * 4);
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const v = draw(x / (w - 1), 1 - y / (h - 1)); // draw() gets y = 0 at the top of the image
      const a = Array.isArray(v) ? v[1] : v;
      const l = Array.isArray(v) ? v[0] : 1;
      const i = (y * w + x) * 4;
      data[i] = data[i + 1] = data[i + 2] = Math.round(Math.max(0, Math.min(1, l)) * 255);
      data[i + 3] = Math.round(Math.max(0, Math.min(1, a)) * 255);
    }
  }
  const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat);
  t.magFilter = THREE.LinearFilter;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.generateMipmaps = true;
  t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  return t;
};
const hash = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const noise2 = (x, y) => {
  const xi = Math.floor(x); const yi = Math.floor(y); const xf = x - xi; const yf = y - yi;
  const h = (a, b) => hash(a * 57.3 + b * 131.9);
  const sx = xf * xf * (3 - 2 * xf); const sy = yf * yf * (3 - 2 * yf);
  return (h(xi, yi) * (1 - sx) + h(xi + 1, yi) * sx) * (1 - sy) + (h(xi, yi + 1) * (1 - sx) + h(xi + 1, yi + 1) * sx) * sy;
};
const smooth = (a, b, x) => { const k = Math.max(0, Math.min(1, (x - a) / (b - a))); return k * k * (3 - 2 * k); };

// Alpha masks (shape in alpha; colour comes from the material; smoke also carries shading in RGB).
const TEX = {};
const textures = () => {
  if (TEX.glow) return TEX;
  TEX.glow = canvasTex(256, 256, (x, y) => { const r = Math.hypot(x - 0.5, y - 0.5) * 2; return Math.pow(Math.max(0, 1 - r), 2.2); });
  // Tongue along +x: soft base, fat body tapering to a point, streaky turbulence.
  TEX.jet = canvasTex(256, 64, (x, y) => {
    const w = Math.min(1, x * 5 + 0.3) * Math.pow(Math.max(0, 1 - x * x), 0.5);
    const d = Math.abs(y - 0.5) * 2 / Math.max(0.02, w);
    const streak = 0.7 + 0.3 * noise2(x * 9, y * 22);
    return Math.pow(Math.max(0, 1 - d), 1.4) * Math.pow(1 - x, 0.3) * streak * smooth(0, 0.1, x);
  });
  // Soft elongated blob along +x (blunt jets: no needle tips).
  TEX.puff = canvasTex(128, 64, (x, y) => { const r = Math.hypot((x - 0.5) * 2, (y - 0.5) * 2); return Math.pow(Math.max(0, 1 - r), 1.6) * (0.8 + 0.2 * noise2(x * 8, y * 6)); });
  TEX.ring = canvasTex(128, 128, (x, y) => {
    const r = Math.hypot(x - 0.5, y - 0.5) * 2;
    const d = Math.abs(r - 0.66) / 0.42;
    return r > 1 ? 0 : (Math.pow(Math.max(0, 1 - d), 2) * 0.8 + 0.2 * Math.pow(Math.max(0, 1 - r), 1.5)) * smooth(1, 0.85, r) * Math.pow(noise2((x - 0.5) / Math.max(r, 1e-3) * 3 + 5, (y - 0.5) / Math.max(r, 1e-3) * 3 + 5) * (0.7 + 0.3 * noise2(x * 18, y * 18)), 1.6);
  });
  // Smoke puff: lumpy edge, lit from the top (RGB brighter at the top, darker underneath).
  // Smoke puff: a cauliflower of soft lobes with fine billow detail, lit from the top
  // (RGB brighter on top, darker underneath; the material colour tints it).
  const lobes = [[0.5, 0.52, 0.3], [0.36, 0.42, 0.2], [0.63, 0.4, 0.21], [0.42, 0.62, 0.2], [0.6, 0.62, 0.19], [0.5, 0.33, 0.18]];
  const dens = (x, y) => {
    let d = 0;
    for (const [cx, cy, rr] of lobes) d += Math.exp(-(((x - cx) ** 2 + (y - cy) ** 2) / (rr * rr)) * 2.2);
    return d;
  };
  TEX.smoke = canvasTex(256, 256, (x, y) => {
    const n = noise2(x * 6, y * 6) * 0.55 + noise2(x * 13 + 7, y * 13) * 0.3 + noise2(x * 27 + 3, y * 27 + 5) * 0.15;
    const d = dens(x, y) * (0.75 + 0.5 * n);
    const edge = Math.hypot(x - 0.5, y - 0.5) * 2;
    const a = smooth(0.25, 1.6, d) * smooth(1, 0.8, edge);
    const lit = Math.max(0, Math.min(1, 0.5 + 1.2 * (dens(x, y + 0.06) - dens(x, y - 0.06))));
    return [Math.min(1, (0.62 + 0.22 * (1 - y) + 0.16 * (n - 0.5)) * (0.9 + 0.1 * lit)), a];
  });
  // Dust: a flat, lumpy soft blob (no lit rim, so it never reads as a bubble).
  TEX.dust = canvasTex(128, 128, (x, y) => {
    const r = Math.hypot(x - 0.5, y - 0.5) * 2;
    const n = noise2(x * 6 + 2, y * 6) * 0.65 + noise2(x * 14, y * 14 + 4) * 0.35;
    return Math.pow(Math.max(0, 1 - r * (0.75 + 0.45 * n)), 1.8) * (0.5 + 0.5 * n);
  });
  TEX.streak = canvasTex(64, 16, (x, y) => Math.pow(Math.max(0, 1 - Math.abs(y - 0.5) * 2), 2) * Math.pow(x, 0.6) * Math.min(1, (1 - x) * 8));
  return TEX;
};

const C = {
  white: new THREE.Color(1, 1, 1), hot: new THREE.Color(0.75, 0.97, 1), cyan: new THREE.Color(0.1, 0.5, 1),
  halo: new THREE.Color(0.45, 0.88, 1), spark: new THREE.Color(1, 0.9, 0.6),
  orange: new THREE.Color(1, 0.58, 0.2), ember: new THREE.Color(1, 0.35, 0.08), smoke: new THREE.Color(0.86, 0.9, 1),
  dust: new THREE.Color(0.92, 0.82, 0.64),
};
const ease = (x) => 1 - (1 - x) ** 3;
// Envelope: rises over `a` (0 = full at once), then falls to 0 at `life`.
const env = (u, a, life, p = 1.5) => (u < 0 || u > life ? 0 : u < a ? u / a : (1 - (u - a) / (life - a)) ** p);

// Quad with its base at x=0 and its length along +x, for axis-aligned billboards.
const quadAlong = new THREE.PlaneGeometry(1, 1).translate(0.5, 0, 0);
const quad = new THREE.PlaneGeometry(1, 1);
const Z = new THREE.Vector3(0, 0, 1);

export class Blast {
  constructor(scene) {
    this.scene = scene;
    this.pool = [];
    this.used = 0;
    this.lights = [];
    this.lightUsed = 0;
    textures();
  }

  begin() {
    this.used = 0;
    this.lightUsed = 0;
  }

  end() {
    for (let i = this.used; i < this.pool.length; i += 1) this.pool[i].visible = false;
    for (let i = this.lightUsed; i < this.lights.length; i += 1) this.lights[i].intensity = 0;
  }

  // Hot layers are additive and drawn over the gun (no depth test: a bloom, not a solid);
  // smoke and dust are alpha-blended and depth-tested.
  sprite(tex, additive) {
    let m = this.pool[this.used];
    if (!m) {
      m = new THREE.Mesh(quad, new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
      m.matrixAutoUpdate = false;
      m.frustumCulled = false;
      this.scene.add(m);
      this.pool.push(m);
    }
    this.used += 1;
    m.visible = true;
    m.material.map = tex;
    m.material.blending = additive ? THREE.AdditiveBlending : THREE.NormalBlending;
    m.material.depthTest = !additive;
    m.material.needsUpdate = true;
    m.renderOrder = additive ? 11 : 10;
    return m;
  }

  // The sprite just drawn ignores depth and draws after the smoke (alpha-blended glow over the gun).
  overGun(order = 10.5, depthTest = false) {
    const m = this.pool[this.used - 1];
    m.material.depthTest = depthTest;
    m.renderOrder = order;
  }

  // Camera-facing square at p.
  bill(cam, tex, p, size, color, alpha, roll = 0, additive = true) {
    const m = this.sprite(tex, additive);
    m.geometry = quad;
    m.material.color.copy(color);
    m.material.opacity = alpha;
    const q = cam.quaternion.clone().multiply(new THREE.Quaternion().setFromAxisAngle(Z, roll));
    m.matrix.compose(p, q, new THREE.Vector3(size, size, size));
  }

  // Quad stretched from p along dir, turned round dir to face the camera.
  along(cam, tex, p, dir, len, width, color, alpha, additive = true) {
    const m = this.sprite(tex, additive);
    m.geometry = quadAlong;
    m.material.color.copy(color);
    m.material.opacity = alpha;
    const toCam = cam.position.clone().sub(p).normalize();
    const side = new THREE.Vector3().crossVectors(dir, toCam);
    if (side.lengthSq() < 1e-6) side.set(0, 1, 0);
    side.normalize();
    const n = new THREE.Vector3().crossVectors(dir, side).normalize();
    m.matrix.makeBasis(dir.clone().multiplyScalar(len), side.multiplyScalar(width), n).setPosition(p);
  }

  // Flat quad facing `normal`.
  flat(tex, p, normal, size, color, alpha, additive = true, roll = 0) {
    const m = this.sprite(tex, additive);
    m.geometry = quad;
    m.material.color.copy(color);
    m.material.opacity = alpha;
    const q = new THREE.Quaternion().setFromUnitVectors(Z, normal).multiply(new THREE.Quaternion().setFromAxisAngle(Z, roll));
    m.matrix.compose(p, q, new THREE.Vector3(size, size, size));
  }

  light(p, color, intensity, range) {
    let l = this.lights[this.lightUsed];
    if (!l) { l = new THREE.PointLight(0xffffff, 0, 1, 2); this.scene.add(l); this.lights.push(l); }
    this.lightUsed += 1;
    l.position.copy(p);
    l.color.copy(color);
    l.intensity = intensity;
    l.distance = range;
  }

  /**
   * Draw one shot `u` seconds old. p = muzzle when it fired, dir = unit fire direction,
   * pm = where the muzzle is now (it recoils), S = gun size (m), H = heaviness 0..1, seed varies it.
   */
  shot(cam, p, dir, S, u, seed, pm = p, H = 0, groundY = 0) {
    if (u < 0 || u > LIFE) return;
    const T = TEX;
    const r = (k) => hash(seed * 13.7 + k * 3.1);
    const at = (d) => p.clone().addScaledVector(dir, d);
    const up = new THREE.Vector3(0, 1, 0);
    let side = new THREE.Vector3().crossVectors(dir, up);
    if (side.lengthSq() < 1e-6) side.set(0, 0, 1);
    side.normalize();
    const lift = new THREE.Vector3().crossVectors(side, dir).normalize();
    const flatDir = new THREE.Vector3(dir.x, 0, dir.z).normalize();
    const toCam = cam.position.clone().sub(p).normalize();
    // Light guns get a relatively punchier flash (it has to read at game zoom), heavy ones get mass instead.
    const P = 1 + 0.25 * (1 - H);

    // Ground dust (heavy guns): drawn first, under everything.
    if (H > 0) {
      // The pressure wave hits the ground under the barrel, between the tank and the muzzle.
      const g = new THREE.Vector3(p.x, groundY + 0.03, p.z).addScaledVector(flatDir, -0.9 * Math.max(0, p.y - groundY));
      const dk = u / (0.9 + 0.4 * H);
      if (dk < 1) this.flat(T.dust, g.clone().addScaledVector(flatDir, 1.5 * S * ease(dk)), up, S * (2 + 7 * H * ease(dk)), C.dust, 0.35 * H * Math.min(1, u / 0.06) * (1 - dk) ** 1.5, false, r(200) * 6.28);
      const n = Math.round(3 + 5 * H);
      for (let i = 0; i < n; i += 1) {
        const x = u - 0.02 - r(i + 210) * 0.05;
        const life = 1.2 + 0.8 * r(i + 220);
        if (x < 0 || x > life) continue;
        const ang = ((i + 0.5) / n - 0.5) * 3.6 + (r(i + 230) - 0.5) * 0.4;
        const d = flatDir.clone().applyAxisAngle(up, ang);
        const travel = (4 + 3 * r(i + 240)) * S * (1 - Math.exp(-x * 4)) * (0.55 + 0.45 * Math.cos(ang));
        const size = S * (1.4 + 3 * H * ease(Math.min(1, x * 1.2)));
        const pos = g.clone().addScaledVector(d, 0.6 * S + travel);
        pos.y = groundY + size * 0.25 + x * 0.4 * S;
        this.bill(cam, T.dust, pos, size, C.dust, 0.35 * H * Math.min(1, x / 0.08) * (1 - x / life) ** 1.4, r(i + 250) * 6.28, false);
      }
    }

    // Smoke (drawn under the hot layers).
    const nSmoke = Math.round(7 + 3 * H);
    for (let i = 0; i < nSmoke; i += 1) {
      const x = u - 0.01 - i * 0.012;
      if (x < 0) continue;
      const life = (1.2 + 0.8 * H) * (0.75 + 0.5 * r(i));
      if (x > life) continue;
      const k = x / life;
      const v0 = (0.6 + 13 * ((i + 0.5) / nSmoke) ** 1.5 * (0.75 + 0.5 * r(i + 10))) * S * (1 - 0.45 * H);
      const drag = 3.5;
      const travel = (v0 * (1 - Math.exp(-x * drag))) / drag;
      const spread = (r(i + 20) - 0.5) * 1.8;
      const pos = at(0.3 * S + travel).addScaledVector(side, spread * travel * 0.5).addScaledVector(lift, (r(i + 30) - 0.4) * travel * 0.5).addScaledVector(side, (r(i + 35) - 0.5) * S * 0.8);
      pos.y += (0.5 + 0.5 * r(i + 40)) * S * 2.4 * x * x / (0.3 + x); // buoyant rise once it slows
      const size = S * (0.7 + (2.0 + 0.5 * H) * ease(Math.min(1, x * 1.2))) * (0.55 + 0.9 * r(i + 50));
      pos.y = Math.max(pos.y, groundY + size * 0.32);
      const a = (0.55 - 0.15 * H) * (0.65 + 0.35 * r(i + 55)) * Math.min(1, x / 0.05) * (1 - k) ** 1.7;
      const tint = C.smoke.clone().lerp(C.hot, Math.max(0, 0.5 - x * 5));
      const roll = (r(i + 60) - 0.5) * 0.9 + x * (r(i + 70) - 0.5) * 1.2;
      this.bill(cam, T.smoke, pos, size, tint, a, roll, false);
    }

    // Lingering smoke: the hot bore keeps venting slow puffs at the muzzle for a while, so the plume
    // stays joined to the gun and drifts off instead of leaving a gap (heavy guns vent longer).
    const nLinger = Math.round(2 + 8 * H);
    for (let i = 0; i < nLinger; i += 1) {
      const born = 0.06 + i * (0.07 + 0.05 * H);
      const x = u - born;
      const life = (1.0 + 1.0 * H) * (0.8 + 0.4 * r(i + 300));
      if (x < 0 || x > life) continue;
      const k = x / life;
      const pos = at(0.5 * S + (0.8 + 1.2 * r(i + 310)) * S * x).addScaledVector(side, (r(i + 320) - 0.5) * S * (0.4 + x));
      pos.y += S * (0.3 + 0.5 * r(i + 330)) * x * 2;
      const size = S * (0.9 + (1.6 + 0.6 * H) * ease(Math.min(1, x * 1.3))) * (0.75 + 0.5 * r(i + 340));
      pos.y = Math.max(pos.y, groundY + size * 0.32);
      const a = (0.45 + 0.05 * H) * (1 - 0.5 * i / nLinger) * Math.min(1, x / 0.08) * (1 - k) ** 1.4; // later vents thinner
      this.bill(cam, T.smoke, pos, size, C.smoke, a, (r(i + 350) - 0.5) * 0.9 + x * 0.4, false);
    }

    // Muzzle stays hot and cools (rides the recoiling barrel tip).
    const cool = env(u, 0, 0.9, 2);
    if (cool > 0) {
      this.bill(cam, T.glow, pm, 1.4 * S, C.ember, 0.9 * cool);
      this.bill(cam, T.glow, pm, 0.6 * S, C.orange, cool * cool);
    }

    // Shock ring, tilted toward the camera.
    const rk = u / (0.15 + 0.04 * H);
    if (rk < 1) {
      const nrm = dir.clone().add(toCam.clone().multiplyScalar(1.2)).normalize();
      this.flat(T.ring, at(0.9 * S + rk * 1.2 * S), nrm, S * (1.6 + (3.4 + H) * ease(rk)), C.hot, 0.2 * (1 - rk) ** 1.5 * Math.min(1, u / 0.02), true, r(7) * 6.28);
    }

    // Plasma tongue from the muzzle (as it recoils) out along the barrel line.
    const j = env(u, 0, 0.1, 1.4);
    if (j > 0) {
      const reach = S * (3 + 0.8 * r(1) + 0.8 * H) * P * (0.75 + 0.25 * Math.min(1, u / 0.035));
      const base = at(-0.2 * S);
      // Outer tongue alpha-blended (reads cyan on any ground), white-hot inner tongue additive.
      this.along(cam, T.jet, base, dir, reach, S * (2.2 + 0.6 * H) * P, C.halo, Math.min(1, 0.75 * P) * j, false);
      this.overGun();
      this.along(cam, T.jet, base, dir, reach * 0.7, S * 1.1 * P, C.white, j);
      // The barrel snaps back faster than the flash dies: plasma keeps pouring out of the live tip and
      // joins the bloom, so the blast is never seen floating ahead of a retracted barrel.
      const gap = pm.distanceTo(base);
      const w = env(u, 0, 0.1, 1.6);
      if (gap > 0.2 * S && w > 0) {
        const bd = p.clone().addScaledVector(dir, 0.6 * S).sub(pm);
        const bl = bd.length();
        bd.normalize();
        this.along(cam, T.puff, pm.clone().addScaledVector(bd, -0.4 * S), bd, bl + 0.6 * S, S * 1.3, C.halo, 0.8 * w, false);
        this.overGun();
        this.along(cam, T.puff, pm.clone().addScaledVector(bd, -0.2 * S), bd, bl + 0.3 * S, S * 0.55, C.white, w);
        this.bill(cam, T.glow, pm, S * 1.8, C.cyan, 0.8 * w);
      }
      for (let s = -1; s <= 1; s += 2) {
        const dd = dir.clone().addScaledVector(side, s * (0.25 + 0.1 * r(2 + s))).addScaledVector(lift, 0.15 * (r(4 + s) - 0.5)).normalize();
        this.along(cam, T.puff, at(0.1 * S), dd, reach * 0.5, S * 1.1, C.hot, 0.5 * j);
      }
    }
    // Muzzle-brake side jets.
    const b = env(u, 0, 0.08);
    if (b > 0) {
      for (let s = -1; s <= 1; s += 2) {
        const d = side.clone().multiplyScalar(s).addScaledVector(dir, 0.45).normalize();
        this.along(cam, T.puff, p.clone().addScaledVector(d, -0.2 * S), d, S * (1.8 + 0.8 * H), S * 0.9, C.cyan, 0.9 * b);
      }
    }
    // White-hot core in a wide cyan halo.
    const c = env(u, 0, 0.1, 2);
    if (c > 0) {
      // The halo is alpha-blended so it reads cyan over any ground (additive cyan on grass turns lime).
      this.bill(cam, T.glow, at(0.5 * S), S * (4.5 + 1.2 * H) * P * (1.15 - 0.15 * c), C.halo, Math.min(0.75, 0.5 * P) * c, 0, false);
      this.overGun();
      this.bill(cam, T.glow, at(0.5 * S), S * (3.5 + 1.0 * H) * P, C.cyan, 0.7 * c);
      this.bill(cam, T.glow, at(0.4 * S), S * (1.7 + 0.6 * H) * P, C.white, Math.min(1, 1.5 * c));
    }
    // Sparks.
    const nSparks = Math.round(9 + 8 * H);
    for (let i = 0; i < nSparks; i += 1) {
      const x = u - r(i + 80) * 0.03;
      const life = 0.18 + r(i + 90) * 0.18;
      if (x < 0 || x > life) continue;
      const d = dir.clone().addScaledVector(side, (r(i + 100) - 0.5) * 1.8).addScaledVector(lift, (r(i + 110) - 0.35) * 1.4).normalize();
      const v = (14 + 18 * r(i + 120)) * S;
      const pos = at(0.4 * S).addScaledVector(d, v * x * (1 - x * 1.2));
      pos.y -= 4.9 * x * x;
      const a = (1 - x / life) ** 1.2;
      // Alpha-blended: additive orange on grass goes lime.
      this.along(cam, T.streak, pos, d.clone().multiplyScalar(-1), S * (0.5 + v * 0.03 * (1 - x / life)), S * 0.26, i % 3 ? C.orange : C.spark, a, false);
      this.overGun(10.6, true);
    }
    // Light.
    const l = env(u, 0, 0.14, 2);
    if (l > 0) this.light(at(0.8 * S).setY(p.y + 0.5 * S), C.hot, 14 * S * S * (1 + 0.6 * H) * l, 7 * S);
  }
}
