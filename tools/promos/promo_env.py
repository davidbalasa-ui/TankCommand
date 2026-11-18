"""Clip set dressing for the promo kit: terrain, ground materials, horizon backdrop, sky, haze
and the prop scatter. promo_kit.Promo.env()/ground_z()/flatten() delegate here.

Design
- Ground: one regular (non-uniform) grid, 0.25 m spacing near the middle growing to ~1 m at
  the edge. Relief comes from a numpy heightmap (layered gradient noise per biome: dunes,
  ridges, terraces, lava lobes) fed to the 'Displace' modifier through a float image, so
  flatten() keeps working through the modifier's 'Flat' vertex group, and scenes that edit
  ground vertices (radar hill, falcon canyon) still work.
- Fine detail (ripples, gravel, cracks, etched plates, ash, grass) is shader bump + colour, and
  3D gravel / stones / grass tufts instanced by a geometry-nodes scatter near the camera.
- Horizon: a far ring (to 8 km) with the same height function plus biome backdrop relief
  (mesas, mountains, spires, volcanic cones), hazed into the sky colour.
- Sky: one node group SkyColor(direction) used by the world AND by the haze on every surface,
  so far terrain fades exactly into the horizon.
- Props are placed at render time (finalize()), after every flatten() and after the actors
  have their paths, so nothing floats or ends up inside a unit's path.
"""
import math
import random

import bpy  # noqa: I001
import bmesh
import numpy as np
from mathutils import Matrix, Vector

# ----------------------------------------------------------------------------------- biomes
# palette keys g1/g2/sky/hor/sunc are read by scenes (dust colours): keep them.
BIOMES = {
    'desert': dict(
        g1=(0.36, 0.245, 0.145), g2=(0.2, 0.135, 0.08), sky=(0.17, 0.34, 0.68), hor=(0.74, 0.68, 0.6),
        sunc=(1.0, 0.92, 0.8), bg=1.0, clouds=0.35, cloud_col=(1.0, 0.97, 0.93), haze_d=2200.0, haze_max=0.94,
        cols=[(0.42, 0.29, 0.17), (0.3, 0.2, 0.12), (0.48, 0.35, 0.22)],
        gravel=[(0.2, 0.15, 0.11), (0.33, 0.27, 0.21), (0.13, 0.1, 0.08)], rock=(0.27, 0.19, 0.13),
        ripples=1.0, gravel_amt=0.35, cracks=0.0, etched=0.0, grass=0.0, ash=0.0,
        relief='dunes', backdrop='mesas', tufts=0.04, rock_tint=(0.36, 0.27, 0.19), dust=(0.48, 0.35, 0.22)),
    'highland': dict(
        g1=(0.2, 0.19, 0.12), g2=(0.1, 0.1, 0.07), sky=(0.15, 0.32, 0.66), hor=(0.62, 0.69, 0.76),
        sunc=(1.0, 0.95, 0.88), bg=1.0, clouds=0.55, cloud_col=(1.0, 1.0, 1.0), haze_d=1300.0, haze_max=0.92,
        cols=[(0.2, 0.15, 0.09), (0.12, 0.09, 0.06), (0.27, 0.22, 0.14)],
        gravel=[(0.2, 0.2, 0.19), (0.14, 0.13, 0.12), (0.27, 0.26, 0.24)], rock=(0.2, 0.2, 0.19),
        ripples=0.0, gravel_amt=0.4, cracks=0.0, etched=0.0, grass=1.0, ash=0.0,
        relief='hills', backdrop='mountains', tufts=1.0, rock_tint=(0.24, 0.24, 0.22), dust=(0.15, 0.17, 0.08)),
    'alien': dict(
        g1=(0.32, 0.27, 0.2), g2=(0.15, 0.13, 0.11), sky=(0.13, 0.3, 0.36), hor=(0.74, 0.68, 0.54),
        sunc=(1.0, 0.9, 0.74), bg=1.0, clouds=0.45, cloud_col=(1.0, 0.95, 0.85), haze_d=1300.0, haze_max=0.93,
        cols=[(0.4, 0.3, 0.19), (0.26, 0.19, 0.12), (0.47, 0.37, 0.24)],
        gravel=[(0.4, 0.34, 0.24), (0.18, 0.16, 0.14), (0.3, 0.3, 0.29)], rock=(0.24, 0.21, 0.17),
        ripples=0.25, gravel_amt=0.25, cracks=0.0, etched=1.0, grass=0.0, ash=0.0,
        relief='terraces', backdrop='spires', tufts=0.0, rock_tint=(0.3, 0.27, 0.22), dust=(0.4, 0.34, 0.25)),
    'dusk': dict(
        g1=(0.3, 0.175, 0.1), g2=(0.13, 0.075, 0.05), sky=(0.06, 0.13, 0.3), hor=(0.95, 0.52, 0.26),
        sunc=(1.0, 0.63, 0.36), bg=1.0, clouds=0.5, mid=(0.8, 0.42, 0.2), glow=0.16, cloud_col=(1.0, 0.62, 0.42), haze_d=1300.0, haze_max=0.95,
        cols=[(0.33, 0.19, 0.11), (0.22, 0.12, 0.07), (0.38, 0.24, 0.15)],
        gravel=[(0.18, 0.11, 0.07), (0.3, 0.2, 0.14), (0.12, 0.08, 0.06)], rock=(0.24, 0.14, 0.09),
        ripples=0.45, gravel_amt=0.3, cracks=1.0, etched=0.0, grass=0.0, ash=0.0,
        relief='flats', backdrop='mesas', tufts=0.04, rock_tint=(0.32, 0.2, 0.13), dust=(0.36, 0.22, 0.13)),
    'ash': dict(
        g1=(0.17, 0.16, 0.15), g2=(0.065, 0.06, 0.055), sky=(0.24, 0.26, 0.3), hor=(0.6, 0.53, 0.47),
        sunc=(1.0, 0.85, 0.7), bg=1.0, clouds=0.75, cloud_col=(0.75, 0.72, 0.7), haze_d=1700.0, haze_max=0.95,
        cols=[(0.13, 0.12, 0.115), (0.075, 0.07, 0.068), (0.24, 0.23, 0.22)],
        gravel=[(0.06, 0.055, 0.05), (0.12, 0.1, 0.09), (0.04, 0.035, 0.035)], rock=(0.09, 0.085, 0.08),
        ripples=0.15, gravel_amt=0.45, cracks=0.5, etched=0.0, grass=0.0, ash=1.0,
        relief='lava', backdrop='volcanoes', tufts=0.0, rock_tint=(0.12, 0.115, 0.11), dust=(0.3, 0.29, 0.28)),
}

SEG = 600            # ground grid segments per side
IMG = 1024           # heightmap resolution (0.31 m/px at radius 160)
FAR = 8000.0         # far ring outer radius


# ----------------------------------------------------------------------------------- noise
class Noise:
    """Vectorised 2D gradient noise (Perlin) + fBm/ridged helpers, seeded."""

    def __init__(self, seed):
        r = np.random.RandomState(seed & 0x7fffffff)
        p = r.permutation(256)
        self.perm = np.concatenate([p, p]).astype(np.int32)
        ang = r.uniform(0, 2 * np.pi, 256)
        self.gx, self.gy = np.cos(ang), np.sin(ang)

    def perlin(self, x, y):
        xi = np.floor(x).astype(np.int64)
        yi = np.floor(y).astype(np.int64)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        P = self.perm

        def g(ix, iy, dx, dy):
            h = P[P[ix] + iy]
            return self.gx[h] * dx + self.gy[h] * dy
        n00 = g(xi, yi, xf, yf)
        n10 = g((xi + 1) & 255, yi, xf - 1, yf)
        n01 = g(xi, (yi + 1) & 255, xf, yf - 1)
        n11 = g((xi + 1) & 255, (yi + 1) & 255, xf - 1, yf - 1)
        a = n00 + u * (n10 - n00)
        b = n01 + u * (n11 - n01)
        return (a + v * (b - a)) * 1.41

    def fbm(self, x, y, octaves=4, lac=2.03, gain=0.5):
        s, amp, tot = 0.0, 1.0, 0.0
        for i in range(octaves):
            s = s + amp * self.perlin(x + i * 17.3, y - i * 9.1)
            tot += amp
            x, y = x * lac, y * lac
            amp *= gain
        return s / tot

    def ridged(self, x, y, octaves=4, lac=2.1, gain=0.55):
        s, amp, tot, w = 0.0, 1.0, 0.0, 1.0
        for i in range(octaves):
            n = 1.0 - np.abs(self.perlin(x + i * 31.7, y + i * 7.7))
            n = n * n * w
            w = np.clip(n * 1.6, 0, 1)
            s = s + amp * n
            tot += amp
            x, y = x * lac, y * lac
            amp *= gain
        return s / tot


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------- height functions
def relief(kind, nz, x, y, clear, R):
    """Near/mid relief in metres (before flatten). Mild inside clear circles and near the
    middle (units drive there at z~0), bigger further out."""
    r = np.hypot(x, y)
    # amplitude envelope: calm action areas, livelier surroundings
    calm = np.ones_like(x)
    for cx, cy, cr in clear:
        d = np.hypot(x - cx, y - cy)
        calm = np.minimum(calm, 0.3 + 0.7 * sstep(cr, cr + 18, d))
    grow = 0.45 + 0.55 * sstep(20, 85, r)
    env = calm * grow
    wx = x + 18 * nz.fbm(x / 110, y / 110, 2)
    wy = y + 18 * nz.fbm(x / 110 + 40, y / 110, 2)
    small = 0.05 * nz.fbm(x / 3.2, y / 3.2, 2) + 0.018 * nz.fbm(x / 0.9, y / 0.9, 2)
    base = 1.5 * nz.fbm(wx / 70, wy / 70, 4) + 0.35 * nz.fbm(x / 15, y / 15, 3)
    if kind == 'dunes':
        th = 0.6
        s = (wx * math.cos(th) + wy * math.sin(th)) / 24.0 + 0.6 * nz.fbm(x / 60, y / 60, 2)
        t = s - np.floor(s)
        prof = np.where(t < 0.78, t / 0.78, (1 - t) / 0.22)
        prof = prof * prof * (3 - 2 * prof)
        mask = sstep(-0.15, 0.35, nz.fbm(x / 90 + 7, y / 90, 3))
        h = base + 3.2 * prof * mask * (0.3 + 0.7 * sstep(15, 70, r))
    elif kind == 'hills':
        rid = nz.ridged(x / 28, y / 28, 3)
        h = base * 1.6 + 2.2 * nz.fbm(wx / 130, wy / 130, 3) * sstep(30, 110, r) * 3 + 0.9 * rid * sstep(0.2, 0.6, nz.fbm(x / 70, y / 70, 2) + 0.4)
    elif kind == 'terraces':
        rid = nz.ridged(wx / 34, wy / 34, 4)
        tb = 2.2 * nz.fbm(wx / 90, wy / 90, 3) * (1 + 2 * sstep(40, 120, r))
        step = 0.9
        q = np.floor(tb / step) * step + step * sstep(0.7, 1.0, (tb / step) % 1.0)
        h = base * 0.7 + 0.6 * q + 1.1 * rid
    elif kind == 'flats':
        th = -0.4
        s = (wx * math.cos(th) + wy * math.sin(th)) / 30.0
        t = s - np.floor(s)
        prof = np.where(t < 0.75, t / 0.75, (1 - t) / 0.25)
        mask = sstep(0.0, 0.5, nz.fbm(x / 80 + 3, y / 80, 3))
        h = base * 0.9 + 0.8 * prof * mask * sstep(25, 80, r) + 1.5 * nz.fbm(x / 140, y / 140, 2) * sstep(40, 120, r) * 2
    else:  # lava
        lob = nz.ridged(wx / 22, wy / 22, 4)
        h = base + 1.3 * lob + 1.4 * nz.fbm(x / 120, y / 120, 2) * sstep(30, 110, r) * 2
    h = (h + small) * env
    return h


def backdrop(kind, nz, x, y, R, rng):
    """Far relief (mountains/mesas) in metres, 0 inside ~300 m."""
    r = np.hypot(x, y)
    start = max(320.0, 1.6 * R)
    m = sstep(start, start + 700, r)
    if not np.any(m > 0):
        return np.zeros_like(x)
    hills = 22 * (0.5 + 0.5 * nz.fbm(x / 500, y / 500, 4)) * sstep(start * 0.8, start + 400, r)
    if kind == 'mesas':
        n = nz.fbm(x / 650 + 11, y / 650, 4)
        n2 = nz.fbm(x / 200, y / 200, 3)
        top = sstep(0.12, 0.17, n + 0.06 * n2)
        talus = sstep(-0.05, 0.16, n + 0.06 * n2)
        steps = 0.75 + 0.25 * np.floor(4 * (0.5 + 0.5 * nz.fbm(x / 900, y / 900, 2))) / 3
        h = (75 * top * steps + 22 * talus) * sstep(start + 900, start + 2200, r) + hills
    elif kind == 'mountains':
        rid = nz.ridged(x / 1100, y / 1100, 6)
        h = 420 * rid ** 1.6 * sstep(start + 300, start + 2200, r) + hills * 1.5
    elif kind == 'spires':
        rid = nz.ridged(x / 1300, y / 1300, 6)
        n = nz.fbm(x / 700, y / 700, 4) + 0.05 * nz.fbm(x / 150, y / 150, 3)
        h = (240 * rid ** 1.8 + 70 * sstep(0.14, 0.19, n)) * sstep(start + 600, start + 2400, r) + hills
    else:  # volcanoes
        h = hills + 160 * nz.ridged(x / 700, y / 700, 5) ** 2 * sstep(start + 300, start + 1500, r)
        for i in range(5):
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(1700, 3600)
            cx, cy = d * math.cos(a), d * math.sin(a)
            rad = rng.uniform(700, 1300)
            hh = rng.uniform(260, 520)
            dd = np.hypot(x - cx, y - cy) / rad
            cone = np.clip(1 - dd, 0, 1) ** 1.6 * hh
            crater = np.clip(1 - dd / 0.14, 0, 1) ** 2 * hh * 0.18
            jag = 1 + 0.12 * nz.fbm(x / 120, y / 120, 3)
            h = np.maximum(h, cone * jag - crater)
    return h * m


# ----------------------------------------------------------------------------------- helpers
def _link(o, col=None):
    (col or bpy.context.scene.collection).objects.link(o)
    return o


class NB:
    """Tiny node-building helper for shader / geometry node trees."""

    def __init__(self, nt):
        self.nt = nt
        self.N = nt.nodes
        self.L = nt.links

    def node(self, kind, **inp):
        n = self.N.new(kind)
        for k, v in inp.items():
            self.set(n, k, v)
        return n

    def set(self, n, k, v):
        sock = self._in(n, k)
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        else:
            if isinstance(v, (tuple, list)) and len(v) == 3 and sock.type == 'RGBA':
                v = (*v, 1.0)
            sock.default_value = v

    @staticmethod
    def _in(n, k):
        if isinstance(k, int):
            return n.inputs[k]
        for s in n.inputs:
            if s.identifier == k and s.enabled:
                return s
        for s in n.inputs:
            if s.name == k and s.enabled:
                return s
        return n.inputs[k]

    @staticmethod
    def out(n, k=0):
        if isinstance(k, int):
            outs = [s for s in n.outputs if s.enabled]
            return outs[k]
        for s in n.outputs:
            if (s.identifier == k or s.name == k) and s.enabled:
                return s
        return n.outputs[k]

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.N.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        self.set(n, 0, a)
        if b is not None:
            self.set(n, 1, b)
        if c is not None:
            self.set(n, 2, c)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.N.new('ShaderNodeVectorMath')
        n.operation = op
        self.set(n, 0, a)
        if b is not None:
            self.set(n, 1, b)
        if scale is not None:
            self.set(n, 'Scale', scale)
        return n.outputs[1] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        n = self.N.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        self.set(n, 'Factor_Float', fac)
        self.set(n, 'A_Color', a)
        self.set(n, 'B_Color', b)
        return self.out(n, 'Result_Color')

    def maprange(self, v, a, b, c=0.0, d=1.0, smooth=True):
        n = self.N.new('ShaderNodeMapRange')
        if smooth:
            n.interpolation_type = 'SMOOTHSTEP'
        self.set(n, 'Value', v)
        n.inputs['From Min'].default_value = a
        n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c
        n.inputs['To Max'].default_value = d
        return n.outputs['Result']

    def noise(self, vec, scale, detail=2.0, rough=0.5, dist=0.0, out='Fac'):
        n = self.node('ShaderNodeTexNoise', Vector=vec, Scale=scale, Detail=detail, Roughness=rough, Distortion=dist)
        return n.outputs[out]

    def voronoi(self, vec, scale, feature='F1', rand=1.0, out='Distance'):
        n = self.N.new('ShaderNodeTexVoronoi')
        n.feature = feature
        self.set(n, 'Vector', vec)
        self.set(n, 'Scale', scale)
        self.set(n, 'Randomness', rand)
        return n.outputs[out]


# ---------------------------------------------------------------------------------- the sky
def sky_group(b, sun_dir):
    """Node group SkyColor: Dir (vector, from viewer) -> Color. Inputs: Clouds (0..1)."""
    ng = bpy.data.node_groups.new('SkyColor', 'ShaderNodeTree')
    ng.interface.new_socket('Dir', in_out='INPUT', socket_type='NodeSocketVector')
    ng.interface.new_socket('Clouds', in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    B = NB(ng)
    gi = B.node('NodeGroupInput')
    go = B.node('NodeGroupOutput')
    d = B.vmath('NORMALIZE', gi.outputs['Dir'])
    sep = B.node('ShaderNodeSeparateXYZ', Vector=d)
    z = sep.outputs['Z']
    hor, sky = b['hor'], b['sky']
    mid = b.get('mid') or tuple(0.5 * h + 0.5 * s for s, h in zip(sky, hor))
    # horizon -> zenith gradient
    ramp = B.N.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*hor, 1)
    el[1].position, el[1].color = 0.32, (*sky, 1)
    e = el.new(0.07)
    e.color = (*mid, 1)
    zz = B.math('MAXIMUM', z, 0.0)
    zz = B.math('POWER', zz, 0.8)
    B.L.new(zz, ramp.inputs['Fac'])
    col = ramp.outputs['Color']
    # below the horizon: slightly darker haze
    below = B.maprange(z, 0.0, -0.25, 0.0, 1.0)
    col = B.mix(below, col, tuple(c * 0.75 for c in hor))
    # sun glow (wide + tight)
    sdot = B.vmath('DOT_PRODUCT', d, tuple(sun_dir))
    sdot = B.math('MAXIMUM', sdot, 0.0)
    g1 = B.math('POWER', sdot, 6.0)
    g2 = B.math('POWER', sdot, 400.0)
    glow = B.math('ADD', B.math('MULTIPLY', g1, b.get('glow', 0.35)), B.math('MULTIPLY', g2, 0.6))
    sunc = b['sunc']
    col = B.mix(B.math('MINIMUM', glow, 1.0), col, sunc, 'ADD')
    # clouds: project onto a plane at altitude, two layers (cumulus puffs + cirrus streaks)
    zc = B.math('ADD', B.math('MAXIMUM', z, 0.0), 0.06)
    px = B.math('DIVIDE', sep.outputs['X'], zc)
    py = B.math('DIVIDE', sep.outputs['Y'], zc)
    pv = B.node('ShaderNodeCombineXYZ', X=px, Y=py, Z=0.0).outputs[0]
    c1 = B.noise(B.vmath('SCALE', pv, scale=1.0), 0.9, detail=8, rough=0.58, dist=0.25)
    cov = B.math('ADD', B.math('MULTIPLY', gi.outputs['Clouds'], -0.22), 0.66)
    cum = B.maprange(B.math('SUBTRACT', c1, cov), -0.02, 0.18)
    sx = B.node('ShaderNodeCombineXYZ', X=B.math('MULTIPLY', px, 0.25), Y=B.math('MULTIPLY', py, 2.2), Z=0.0).outputs[0]
    c2 = B.noise(sx, 0.7, detail=6, rough=0.6)
    cir = B.math('MULTIPLY', B.maprange(c2, 0.5, 0.75), 0.45)
    cl = B.math('MAXIMUM', cum, cir)
    fade = B.maprange(z, 0.015, 0.22)
    cl = B.math('MULTIPLY', B.math('MULTIPLY', cl, fade), gi.outputs['Clouds'])
    # cloud shading: lit colour toward the sun, grey underside otherwise
    cc = b['cloud_col']
    lit = B.mix(B.math('MINIMUM', B.math('MULTIPLY', g1, 1.5), 1.0), tuple(c * 0.62 for c in cc), cc)
    shade = B.mix(B.maprange(c1, 0.55, 0.9), lit, tuple(c * 0.7 for c in lit) if False else tuple(0.55 * a + 0.2 * h for a, h in zip(cc, hor)))
    col = B.mix(cl, col, shade)
    B.L.new(col, go.inputs['Color'])
    return ng


def build_world(b, sun_dir, strength):
    w = bpy.data.worlds.new('World')
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    B = NB(nt)
    tc = B.node('ShaderNodeTexCoord')
    grp = B.node('ShaderNodeGroup')
    grp.node_tree = bpy.data.node_groups['SkyColor'] if 'SkyColor' in bpy.data.node_groups else sky_group(b, sun_dir)
    B.set(grp, 'Dir', tc.outputs['Generated'])
    B.set(grp, 'Clouds', b['clouds'])
    bg = B.node('ShaderNodeBackground', Color=grp.outputs['Color'], Strength=strength)
    # Legacy gradient nodes (TexCoord -> SeparateXYZ -> MapRange -> ColorRamp), not connected to
    # the output: scenes that restyle the sky (e.g. star_vault's night sky) find and rewire them.
    sep = B.node('ShaderNodeSeparateXYZ', Vector=tc.outputs['Generated'])
    mp = B.maprange(sep.outputs['Z'], 0.0, 0.55, smooth=False)
    ramp = B.N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*b['hor'], 1)
    ramp.color_ramp.elements[1].position = 0.35
    ramp.color_ramp.elements[1].color = (*b['sky'], 1)
    B.L.new(mp, ramp.inputs['Fac'])
    out = B.node('ShaderNodeOutputWorld')
    B.L.new(bg.outputs[0], out.inputs['Surface'])
    return w


def haze_wrap(mat, b, strength, d0=55.0):
    """Aerial perspective: mix the material's surface shader toward the sky colour seen along
    the view ray, by camera distance. Works on any node material."""
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output), None)
    if out is None or not out.inputs['Surface'].links or mat.get('hazed'):
        return
    mat['hazed'] = 1
    B = NB(nt)
    src = out.inputs['Surface'].links[0].from_socket
    geo = B.node('ShaderNodeNewGeometry')
    view = B.vmath('SCALE', geo.outputs['Incoming'], scale=-1.0)
    grp = B.node('ShaderNodeGroup')
    grp.node_tree = bpy.data.node_groups['SkyColor']
    B.set(grp, 'Dir', view)
    B.set(grp, 'Clouds', 0.0)
    em = B.node('ShaderNodeEmission', Color=grp.outputs['Color'], Strength=strength)
    cam = B.node('ShaderNodeCameraData')
    dd = B.math('MAXIMUM', B.math('SUBTRACT', cam.outputs['View Distance'], d0), 0.0)
    f = B.math('SUBTRACT', 1.0, B.math('EXPONENT', B.math('DIVIDE', dd, -b['haze_d'])))
    f = B.math('MULTIPLY', f, b['haze_max'])
    mx = B.node('ShaderNodeMixShader')
    B.L.new(f, mx.inputs[0])
    B.L.new(src, mx.inputs[1])
    B.L.new(em.outputs[0], mx.inputs[2])
    B.L.new(mx.outputs[0], out.inputs['Surface'])


# ---------------------------------------------------------------------------- ground shader
def ground_material(b, name='GroundMat'):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    B = NB(nt)
    out = B.node('ShaderNodeOutputMaterial')
    bsdf = B.node('ShaderNodeBsdfPrincipled')
    B.L.new(bsdf.outputs[0], out.inputs['Surface'])
    tc = B.node('ShaderNodeTexCoord')
    P = tc.outputs['Object']
    geo = B.node('ShaderNodeNewGeometry')
    cam = B.node('ShaderNodeCameraData')
    vd = cam.outputs['View Distance']
    near = B.maprange(vd, 90.0, 22.0)      # 1 near the camera, 0 far: fades micro detail
    # world normal z for slopes
    nzs = B.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Normal']).outputs['Z']
    slope = B.maprange(nzs, 0.93, 0.72)
    # domain warp
    w = B.node('ShaderNodeTexNoise', Vector=P, Scale=0.03, Detail=2)
    wv = B.vmath('ADD', P, B.vmath('SCALE', B.vmath('SUBTRACT', w.outputs['Color'], (0.5, 0.5, 0.5)), scale=14.0))
    # macro colour: three tones
    c = b['cols']
    n1 = B.noise(wv, 0.022, detail=4)
    n2 = B.noise(wv, 0.09, detail=5)
    n3 = B.noise(P, 0.6, detail=6)
    col = B.mix(B.maprange(n1, 0.35, 0.65), c[1], c[0])
    col = B.mix(B.math('MULTIPLY', B.maprange(n2, 0.45, 0.72), 0.55), col, c[2])
    col = B.mix(B.math('MULTIPLY', B.maprange(n3, 0.3, 0.7), 0.25), col, tuple(x * 0.75 for x in c[1]), 'MIX')
    height = B.math('MULTIPLY', B.math('SUBTRACT', n3, 0.5), 0.012)
    rough = 0.92
    # patch masks
    gpatch = B.math('MULTIPLY', B.maprange(B.noise(wv, 0.055, detail=4), 0.62 - 0.25 * b['gravel_amt'], 0.7 - 0.25 * b['gravel_amt']), 1.0)
    gpatch = B.math('MAXIMUM', gpatch, B.math('MULTIPLY', slope, 0.8))
    # --- sand ripples (asymmetric, wind-oriented, broken up)
    if b['ripples'] > 0:
        mp = B.node('ShaderNodeMapping', Vector=wv)
        mp.inputs['Rotation'].default_value = (0, 0, 0.6)
        wave = B.node('ShaderNodeTexWave', Vector=mp.outputs[0], Scale=1.9, Distortion=3.5, Detail=2.0)
        wave.wave_profile = 'SAW'
        wave.inputs['Detail Scale'].default_value = 0.6
        rip = B.math('MULTIPLY', wave.outputs['Fac'], B.math('SUBTRACT', 1.0, gpatch))
        ripmask = B.maprange(B.noise(P, 0.18, detail=2), 0.3, 0.6)
        rip = B.math('MULTIPLY', rip, B.math('MULTIPLY', ripmask, b['ripples']))
        height = B.math('ADD', height, B.math('MULTIPLY', rip, 0.018))
        col = B.mix(B.math('MULTIPLY', rip, 0.18), col, tuple(min(1, x * 1.25) for x in c[2]))
    # --- gravel: two voronoi pebble layers, coloured per cell
    gr = b['gravel']
    for sc, amp, k in ((7.0, 0.022, 1.0), (19.0, 0.009, 0.8)):
        vo = B.N.new('ShaderNodeTexVoronoi')
        vo.feature = 'F1'
        B.set(vo, 'Vector', P)
        B.set(vo, 'Scale', sc)
        dome = B.maprange(vo.outputs['Distance'], 0.48, 0.12)
        cell = vo.outputs['Color']
        cs = B.node('ShaderNodeSeparateColor', Color=cell)
        keep = B.maprange(cs.outputs[0], 0.25, 0.3)        # only some cells hold a stone
        dens = B.math('MULTIPLY', keep, gpatch)
        stone = B.math('MULTIPLY', dome, dens)
        scol = B.mix(cs.outputs[1], gr[0], gr[1])
        scol = B.mix(B.maprange(cs.outputs[2], 0.6, 0.9), scol, gr[2])
        col = B.mix(B.math('MULTIPLY', B.maprange(stone, 0.02, 0.2), k), col, scol)
        height = B.math('ADD', height, B.math('MULTIPLY', stone, amp))
    # gravel patches are darker/coarser in tone overall
    col = B.mix(B.math('MULTIPLY', gpatch, 0.35), col, gr[0])
    # --- cracked earth (dusk / ash)
    if b['cracks'] > 0:
        flat = B.math('SUBTRACT', 1.0, B.math('MAXIMUM', gpatch, slope))
        cm = B.math('MULTIPLY', B.maprange(B.noise(wv, 0.04, detail=3), 0.42, 0.55), flat)
        for sc, wdt, dep in ((1.1, 0.035, 0.02), (3.3, 0.04, 0.008)):
            vo = B.N.new('ShaderNodeTexVoronoi')
            vo.feature = 'DISTANCE_TO_EDGE'
            B.set(vo, 'Vector', B.vmath('ADD', P, B.vmath('SCALE', B.vmath('SUBTRACT', B.node('ShaderNodeTexNoise', Vector=P, Scale=2.0, Detail=3).outputs['Color'], (0.5, 0.5, 0.5)), scale=0.12)))
            B.set(vo, 'Scale', sc)
            crack = B.maprange(vo.outputs['Distance'], wdt, 0.0)
            crack = B.math('MULTIPLY', crack, B.math('MULTIPLY', cm, b['cracks']))
            curl = B.math('MULTIPLY', B.maprange(vo.outputs['Distance'], 0.0, 0.3), B.math('MULTIPLY', cm, 0.006))
            height = B.math('ADD', height, B.math('SUBTRACT', curl, B.math('MULTIPLY', crack, dep)))
            col = B.mix(B.math('MULTIPLY', crack, 0.8), col, tuple(x * 0.35 for x in c[1]))
        # plates slightly paler
        col = B.mix(B.math('MULTIPLY', cm, 0.3), col, tuple(min(1, x * 1.2) for x in c[2]))
    # --- alien etched ground: bronze plates with fine etched channels and mica glints
    metal = 0.0
    if b['etched'] > 0:
        vo = B.N.new('ShaderNodeTexVoronoi')
        vo.feature = 'DISTANCE_TO_EDGE'
        B.set(vo, 'Vector', wv)
        B.set(vo, 'Scale', 0.45)
        vo.inputs['Randomness'].default_value = 0.75
        groove = B.maprange(vo.outputs['Distance'], 0.014, 0.002)
        # angular, crystalline etching: Chebychev cell borders (F2 - F1)
        fs = []
        for feat in ('F1', 'F2'):
            vv = B.N.new('ShaderNodeTexVoronoi')
            vv.feature = feat
            vv.distance = 'CHEBYCHEV'
            B.set(vv, 'Vector', B.vmath('ADD', P, B.vmath('SCALE', B.node('ShaderNodeTexNoise', Vector=P, Scale=0.6, Detail=2).outputs['Color'], scale=0.4)))
            B.set(vv, 'Scale', 1.6)
            fs.append(vv.outputs['Distance'])
        g2 = B.maprange(B.math('SUBTRACT', fs[1], fs[0]), 0.035, 0.0)
        pm = B.maprange(B.noise(wv, 0.05, detail=3), 0.45, 0.6)
        g2 = B.math('MULTIPLY', g2, pm)
        height = B.math('SUBTRACT', height, B.math('ADD', B.math('MULTIPLY', groove, 0.01), B.math('MULTIPLY', g2, 0.012)))
        col = B.mix(B.math('MULTIPLY', groove, 0.25), col, (0.14, 0.1, 0.06))
        col = B.mix(B.math('MULTIPLY', g2, 0.55), col, (0.17, 0.12, 0.07))
        # bronze sheen on the polished plates (very subtle) + glints
        plate = B.maprange(B.noise(P, 0.25, detail=3), 0.55, 0.7)
        col = B.mix(B.math('MULTIPLY', plate, 0.35), col, (0.5, 0.36, 0.2))
        glint = B.maprange(B.noise(P, 40.0, detail=0), 0.72, 0.78)
        metal = B.math('MULTIPLY', B.math('ADD', B.math('MULTIPLY', plate, 0.35), glint), near)
        rough = B.math('SUBTRACT', 0.9, B.math('MULTIPLY', B.math('ADD', B.math('MULTIPLY', plate, 0.35), B.math('MULTIPLY', glint, 0.5)), 1.0))
    # --- ash: pale drifts in the low ground, black cinders
    if b['ash'] > 0:
        drift = B.maprange(B.noise(wv, 0.07, detail=4), 0.5, 0.62)
        col = B.mix(B.math('MULTIPLY', drift, 0.65), col, b['cols'][2])
        cin = B.voronoi(P, 11.0)
        cind = B.math('MULTIPLY', B.maprange(cin, 0.35, 0.1), B.math('SUBTRACT', 1.0, drift))
        col = B.mix(B.math('MULTIPLY', cind, 0.5), col, (0.025, 0.022, 0.02))
        height = B.math('ADD', height, B.math('MULTIPLY', cind, 0.01))
    # --- highland grass: patchy dry/green grass with streaky fine bump
    if b['grass'] > 0:
        gm = B.maprange(B.noise(wv, 0.05, detail=4), 0.42, 0.52)
        gm = B.math('MULTIPLY', gm, B.math('SUBTRACT', 1.0, B.math('MAXIMUM', gpatch, slope)))
        gn = B.noise(B.vmath('MULTIPLY', P, (6.0, 6.0, 1.0)), 6.0, detail=3)
        gcol = B.mix(B.maprange(B.noise(wv, 0.2, detail=3), 0.4, 0.6), (0.075, 0.12, 0.025), (0.26, 0.22, 0.08))
        gcol = B.mix(B.math('MULTIPLY', gn, 0.5), gcol, (0.06, 0.07, 0.03))
        col = B.mix(gm, col, gcol)
        height = B.math('ADD', height, B.math('MULTIPLY', B.math('MULTIPLY', gn, gm), 0.012))
    # --- slopes / far relief: rock with strata bands
    zc = B.node('ShaderNodeSeparateXYZ', Vector=P).outputs['Z']
    strata = B.math('SINE', B.math('ADD', B.math('MULTIPLY', zc, 0.55), B.math('MULTIPLY', n1, 9.0)))
    rockc = B.mix(B.maprange(strata, -0.8, 0.9), tuple(x * 0.85 for x in b['rock']), tuple(min(1, x * 1.15) for x in b['rock']))
    col = B.mix(slope, col, rockc)
    # rock faces: layered ledges + rough breakup (scenes sculpt canyon walls and hills)
    rn = B.noise(B.vmath('MULTIPLY', P, (0.6, 0.6, 2.2)), 1.2, detail=6, rough=0.65)
    ledges = B.math('MULTIPLY', B.math('ADD', B.math('MULTIPLY', strata, 0.5), rn), slope)
    height = B.math('ADD', height, B.math('MULTIPLY', ledges, 0.09))
    col = B.mix(B.math('MULTIPLY', B.math('MULTIPLY', B.maprange(rn, 0.35, 0.7), slope), 0.5), col, tuple(x * 0.6 for x in b['rock']))
    # micro detail fades with distance (no shimmer far away)
    height = B.math('MULTIPLY', height, near)
    bump = B.node('ShaderNodeBump', Strength=1.0, Distance=1.0, Height=height)
    # low-frequency grain colour so close-up ground isn't flat
    grain = B.noise(P, 14.0, detail=2)
    col = B.mix(B.math('MULTIPLY', B.maprange(grain, 0.3, 0.7), 0.12), col, tuple(x * 0.7 for x in c[1]))
    B.set(bsdf, 'Base Color', col)
    B.set(bsdf, 'Roughness', rough)
    B.set(bsdf, 'Metallic', metal)
    B.set(bsdf, 'Normal', bump.outputs['Normal'])
    try:
        bsdf.inputs['Specular IOR Level'].default_value = 0.35
    except KeyError:
        pass
    return m


# --------------------------------------------------------------------------------- the mesh
def _axis(R, n=SEG):
    u = np.linspace(-1.0, 1.0, n + 1)
    c = min(1.0, 0.25 * n / (2 * R))
    return R * u * (c + (1 - c) * u * u)


def build_ground(P, R, H_img, b, mat):
    ax = _axis(R)
    n = len(ax)
    X, Y = np.meshgrid(ax, ax)        # row j = y index, col i = x index
    co = np.zeros((n * n, 3), np.float32)
    co[:, 0] = X.ravel()
    co[:, 1] = Y.ravel()
    me = bpy.data.meshes.new('Ground')
    me.vertices.add(n * n)
    me.vertices.foreach_set('co', co.ravel())
    q = n - 1
    jj, ii = np.meshgrid(np.arange(q), np.arange(q), indexing='ij')
    v0 = (jj * n + ii).ravel()
    loops = np.stack([v0, v0 + 1, v0 + n + 1, v0 + n], 1).ravel().astype(np.int32)
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', loops)
    me.polygons.add(q * q)
    me.polygons.foreach_set('loop_start', np.arange(0, len(loops), 4, dtype=np.int32))
    me.polygons.foreach_set('use_smooth', np.ones(q * q, bool))
    me.update(calc_edges=True)
    uv = me.uv_layers.new(name='UVMap')
    uvc = np.stack([(co[loops, 0] + R) / (2 * R), (co[loops, 1] + R) / (2 * R)], 1).astype(np.float32)
    uv.data.foreach_set('uv', uvc.ravel())
    g = _link(bpy.data.objects.new('Ground', me))
    me.materials.append(mat)
    # heightmap image -> Displace (strength 1 = metres)
    img = bpy.data.images.new('GroundHeight', IMG, IMG, alpha=False, float_buffer=True, is_data=True)
    px = np.repeat(H_img.astype(np.float32).ravel(), 4)
    px[3::4] = 1.0
    img.pixels.foreach_set(px)
    img.pack()
    tex = bpy.data.textures.new('GroundHeight', 'IMAGE')
    tex.image = img
    tex.extension = 'EXTEND'
    tex.use_interpolation = True
    vg = g.vertex_groups.new(name='Flat')
    vg.add(list(range(n * n)), 1.0, 'REPLACE')
    d = g.modifiers.new('Displace', 'DISPLACE')
    d.texture = tex
    d.texture_coords = 'UV'
    d.uv_layer = 'UVMap'
    d.direction = 'Z'
    d.strength = 1.0
    d.mid_level = 0.0
    d.vertex_group = 'Flat'
    P._ground_tex = tex
    P._env['axis'] = ax
    P._env['flat_w'] = np.ones(n * n, np.float32)
    return g


def build_far(P, R, kind, b, nz, mat, rng):
    nth = 720
    r0 = R * 0.66
    nr = 240
    radii = r0 * (FAR / r0) ** (np.linspace(0, 1, nr) ** 1.0)
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)
    RR, TT = np.meshgrid(radii, th, indexing='ij')
    X, Y = RR * np.cos(TT), RR * np.sin(TT)
    Z = relief(b['relief'], nz, X, Y, [], R) + backdrop(b['backdrop'], nz, X, Y, R, rng)
    # sit under the main ground where they overlap (|x|,|y| < R), meet it beyond
    inside = np.maximum(np.abs(X), np.abs(Y)) < R * 1.002
    Z = Z - np.where(inside, 0.6, 0.0) - 0.6 * (1 - sstep(R * 1.0, R * 1.5, RR))
    me = bpy.data.meshes.new('GroundFar')
    co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1).astype(np.float32)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    jj, ii = np.meshgrid(np.arange(nr - 1), np.arange(nth), indexing='ij')
    a = (jj * nth + ii).ravel()
    bb = (jj * nth + (ii + 1) % nth).ravel()
    loops = np.stack([a, bb, bb + nth, a + nth], 1).ravel().astype(np.int32)
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', loops)
    me.polygons.add(len(a))
    me.polygons.foreach_set('loop_start', np.arange(0, len(loops), 4, dtype=np.int32))
    me.polygons.foreach_set('use_smooth', np.ones(len(a), bool))
    me.update(calc_edges=True)
    o = _link(bpy.data.objects.new('GroundFar', me))
    me.materials.append(mat)
    return o


# ------------------------------------------------------------------- ground cover (GN scatter)
def _pebble_mesh(name, rnd, angular):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1 if angular else 2, radius=1.0)
    sx, sy, sz = 1.0, rnd.uniform(0.6, 1.0), rnd.uniform(0.4, 0.7)
    ph = [rnd.uniform(0, 10) for _ in range(3)]
    for v in bm.verts:
        x, y, z = v.co
        k = 1 + 0.18 * math.sin(3.1 * x + ph[0]) * math.cos(2.7 * y + ph[1]) + 0.12 * math.sin(4.3 * z + ph[2])
        if angular:
            k += rnd.uniform(-0.12, 0.12)
        v.co = Vector((x * sx * k, y * sy * k, z * sz * k))
    if angular:   # a couple of fracture planes
        for _ in range(2):
            n = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 1))).normalized()
            dcut = rnd.uniform(0.45, 0.7)
            for v in bm.verts:
                e = v.co.dot(n) - dcut
                if e > 0:
                    v.co -= n * e
    # origin ~30% up so the stone sits embedded
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + 0.3 * sz * 2
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = not angular
    return me


def stone_material(b, name='GroundStone'):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    B = NB(nt)
    bsdf = nt.nodes.get('Principled BSDF')
    oi = B.node('ShaderNodeObjectInfo')
    gr = b['gravel']
    col = B.mix(oi.outputs['Random'], gr[0], gr[1])
    col = B.mix(B.maprange(oi.outputs['Random'], 0.7, 0.95), col, gr[2])
    tc = B.node('ShaderNodeTexCoord')
    n = B.noise(tc.outputs['Object'], 3.0, detail=6)
    col = B.mix(B.math('MULTIPLY', n, 0.5), col, tuple(x * 0.6 for x in gr[0]))
    # dusty tops
    geo = B.node('ShaderNodeNewGeometry')
    top = B.maprange(B.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Normal']).outputs['Z'], 0.5, 0.95)
    col = B.mix(B.math('MULTIPLY', top, 0.45), col, b['dust'])
    B.set(bsdf, 'Base Color', col)
    B.set(bsdf, 'Roughness', 0.8)
    bump = B.node('ShaderNodeBump', Strength=0.5, Distance=0.02, Height=B.noise(tc.outputs['Object'], 9.0, detail=4))
    B.set(bsdf, 'Normal', bump.outputs['Normal'])
    return m


def _tuft_mesh(name, rnd, blades=26):
    """A clump of curved grass blades (two triangles each)."""
    bm = bmesh.new()
    for _ in range(blades):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = rnd.uniform(0, 0.06)
        h = rnd.uniform(0.18, 0.42)
        lean = rnd.uniform(0.1, 0.5) * h
        w = rnd.uniform(0.008, 0.014)
        d = Vector((math.cos(a), math.sin(a), 0))
        s = Vector((-d.y, d.x, 0)) * w
        base = d * r0
        mid = base + d * lean * 0.35 + Vector((0, 0, h * 0.55))
        tip = base + d * lean + Vector((0, 0, h))
        vs = [bm.verts.new(base - s), bm.verts.new(base + s), bm.verts.new(mid + s * 0.7), bm.verts.new(mid - s * 0.7), bm.verts.new(tip)]
        bm.faces.new((vs[0], vs[1], vs[2], vs[3]))
        bm.faces.new((vs[3], vs[2], vs[4]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def grass_material(b, name='GroundTuft'):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    B = NB(nt)
    bsdf = nt.nodes.get('Principled BSDF')
    oi = B.node('ShaderNodeObjectInfo')
    dry = (0.42, 0.34, 0.15) if b['grass'] else (0.46, 0.37, 0.22)
    green = (0.14, 0.2, 0.05) if b['grass'] else (0.32, 0.27, 0.15)
    col = B.mix(oi.outputs['Random'], green, dry)
    tc = B.node('ShaderNodeTexCoord')
    zz = B.node('ShaderNodeSeparateXYZ', Vector=tc.outputs['Object']).outputs['Z']
    col = B.mix(B.maprange(zz, 0.15, 0.0), col, tuple(x * 0.4 for x in green))
    B.set(bsdf, 'Base Color', col)
    B.set(bsdf, 'Roughness', 0.65)
    tr = B.node('ShaderNodeBsdfTranslucent', Color=col)
    mx = B.node('ShaderNodeMixShader', Fac=0.35)
    out = nt.nodes.get('Material Output')
    B.L.new(bsdf.outputs[0], mx.inputs[1])
    B.L.new(tr.outputs[0], mx.inputs[2])
    B.L.new(mx.outputs[0], out.inputs['Surface'])
    return m


def build_cover(P, b, rnd):
    """Instanced gravel, stones and grass tufts on the ground, density from the 'cover' point
    attribute (filled in finalize(), around the camera's path)."""
    hidden = bpy.data.collections.new('EnvCoverSrc')
    smat = stone_material(b)
    cols = {}
    for key, n_, ang in (('gravel', 6, False), ('stones', 5, True)):
        c = bpy.data.collections.new('Cover_' + key)
        for i in range(n_):
            me = _pebble_mesh(f'{key}_{i}', rnd, ang)
            me.materials.append(smat)
            o = bpy.data.objects.new(f'{key}_{i}', me)
            c.objects.link(o)
        cols[key] = c
    if b['tufts'] > 0:
        gm = grass_material(b)
        c = bpy.data.collections.new('Cover_tufts')
        for i in range(4):
            me = _tuft_mesh(f'tuft_{i}', rnd, blades=rnd.randint(18, 34))
            me.materials.append(gm)
            o = bpy.data.objects.new(f'tuft_{i}', me)
            c.objects.link(o)
        cols['tufts'] = c
    for c in cols.values():
        hidden.children.link(c)

    ng = bpy.data.node_groups.new('GroundCover', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    B = NB(ng)
    gi = B.node('NodeGroupInput')
    go = B.node('NodeGroupOutput')
    oi = B.node('GeometryNodeObjectInfo')
    oi.transform_space = 'RELATIVE'
    oi.inputs['Object'].default_value = P.ground
    attr = B.node('GeometryNodeInputNamedAttribute')
    attr.data_type = 'FLOAT'
    attr.inputs['Name'].default_value = 'cover'
    flat = B.node('GeometryNodeInputNamedAttribute')
    flat.data_type = 'FLOAT'
    flat.inputs['Name'].default_value = 'Flat'
    join = B.node('GeometryNodeJoinGeometry')
    specs = [('gravel', 9.0, (0.025, 0.07), 0.35, b['gravel_amt']), ('stones', 0.22, (0.08, 0.26), 0.8, 1.0)]
    if 'tufts' in cols:
        specs.append(('tufts', 4.5 * b['tufts'], (0.4, 1.0), 0.0, 1.0))
    for i, (key, dens, (s0, s1), patchy, amt) in enumerate(specs):
        dist = B.node('GeometryNodeDistributePointsOnFaces', Mesh=oi.outputs['Geometry'], Seed=11 + i)
        # density = base * cover * patch noise (gravel in patches, stones everywhere)
        pos = B.node('GeometryNodeInputPosition')
        nzn = B.node('ShaderNodeTexNoise', Vector=pos.outputs[0], Scale=0.07 + 0.05 * i, Detail=3)
        patch = B.node('ShaderNodeMapRange', Value=nzn.outputs['Fac'])
        patch.inputs['From Min'].default_value = 0.62 - 0.3 * amt if patchy else 0.2
        patch.inputs['From Max'].default_value = 0.68 - 0.3 * amt if patchy else 0.6
        patch.inputs['To Min'].default_value = 0.12 if patchy else 0.25
        d1 = B.math('MULTIPLY', attr.outputs['Attribute'], dens)
        d2 = B.math('MULTIPLY', d1, patch.outputs['Result'])
        # thinner in flattened action areas (Flat=0 there), never zero
        fl = B.math('ADD', B.math('MULTIPLY', flat.outputs['Attribute'], 0.6), 0.4)
        B.L.new(B.math('MULTIPLY', d2, fl), B._in(dist, 'Density'))
        rnd_rot = B.node('FunctionNodeRandomValue')
        rnd_rot.data_type = 'FLOAT_VECTOR'
        B.set(rnd_rot, 'Min', (-0.25, -0.25, 0.0) if key != 'tufts' else (-0.12, -0.12, 0.0))
        B.set(rnd_rot, 'Max', (0.25, 0.25, 6.283) if key != 'tufts' else (0.12, 0.12, 6.283))
        B.set(rnd_rot, 'Seed', 3 + i)
        rs = B.node('FunctionNodeRandomValue')
        rs.data_type = 'FLOAT'
        B.set(rs, 'Min', 0.0)
        B.set(rs, 'Max', 1.0)
        B.set(rs, 'Seed', 7 + i)
        sz = B.math('MULTIPLY_ADD', B.math('POWER', B.out(rs, 'Value'), 2.2), s1 - s0, s0)
        ci = B.node('GeometryNodeCollectionInfo', **{'Separate Children': True, 'Reset Children': True})
        ci.inputs['Collection'].default_value = cols[key]
        pick = B.node('FunctionNodeRandomValue')
        pick.data_type = 'INT'
        B.set(pick, 'Min', 0)
        B.set(pick, 'Max', 9)
        B.set(pick, 'Seed', 5 + i)
        inst = B.node('GeometryNodeInstanceOnPoints', Points=dist.outputs['Points'], Instance=ci.outputs[0])
        B.set(inst, 'Pick Instance', True)
        B.L.new(B.out(pick, 'Value'), B._in(inst, 'Instance Index'))
        B.L.new(B.out(rnd_rot, 'Value'), B._in(inst, 'Rotation'))
        B.L.new(sz, B._in(inst, 'Scale'))
        B.L.new(inst.outputs[0], join.inputs[0])
    B.L.new(join.outputs[0], go.inputs[0])
    me = bpy.data.meshes.new('GroundCover')
    o = _link(bpy.data.objects.new('GroundCover', me))
    md = o.modifiers.new('Cover', 'NODES')
    md.node_group = ng
    md.show_viewport = False     # it re-evaluates on every frame_set(); render only
    return o


# ------------------------------------------------------------------------------- the build
def build(P, kind='desert', sun=(42, 0, -35), sun_energy=4.0, radius=160, props=40, clear=None,
          deposits=None, seed=None):
    from promo_kit import resolve  # noqa: E402  (circular import at call time only)
    b = dict(BIOMES[kind])
    P.palette = b
    P._env = dict(kind=kind, props=props, radius=radius, deposits=[], finalized=False)
    seed_v = seed if seed is not None else P.rnd.random()
    rng = random.Random(seed_v)
    P._env['rng'] = random.Random(rng.random())
    nz = Noise(rng.randrange(1 << 30))
    P._clear = list(clear or [])
    # sun
    s = _link(bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')))
    s.data.energy = sun_energy
    s.data.color = b['sunc']
    s.data.angle = math.radians(1.5)
    s.rotation_euler = [math.radians(a) for a in sun]
    P.sun = s
    sun_dir = (s.rotation_euler.to_matrix() @ Vector((0, 0, 1))).normalized()
    # sky
    sky_group(b, sun_dir)
    build_world(b, sun_dir, b['bg'])
    # ground
    R = float(radius)
    lin = np.linspace(-R, R, IMG)
    X, Y = np.meshgrid(lin, lin)
    H = relief(b['relief'], nz, X, Y, P._clear, R) + backdrop(b['backdrop'], nz, X, Y, R, random.Random(rng.random()))
    mat = ground_material(b)
    haze_wrap(mat, b, b['bg'])
    P.ground = build_ground(P, R, H, b, mat)
    P._env['far'] = build_far(P, R, kind, b, nz, mat, random.Random(rng.random()))
    P._env['cover'] = build_cover(P, b, random.Random(rng.random()))
    # resource deposits: load now (scenes may use them), snap again in finalize()
    for kind_, at, k in (deposits or []):
        nm = 'deposit_ore' if kind_ == 'ore' else 'deposit_metal'
        a = P.load(nm, at=at, heading=rng.uniform(0, 360), size=resolve(nm)['size'] * k)
        a.root.location.z = P.ground_z(at[0], at[1]) - 0.2
        P._env['deposits'].append(a)
    return P


# ------------------------------------------------------------------------------ ground_z
def _eval_heights(P):
    g = P.ground
    me = g.data
    n = len(me.vertices)
    vs = me.vertices
    # cheap change detector: a strided sample of base z (scenes that sculpt the ground edit many
    # vertices), the modifier settings and the flatten() counter
    idx = P._env.get('probe')
    if idx is None or idx[-1] >= n:
        idx = list(range(0, n, 307)) + [n - 1]
        P._env['probe'] = idx
    zs = sum(vs[i].co.z for i in idx)
    d = g.modifiers.get('Displace')
    key = (n, round(zs, 5), d.strength if d else 0, d.mid_level if d else 0,
           P._env.get('flat_ver', 0), d.show_viewport if d else 0)
    c = P._env.get('zcache')
    if c and c[0] == key:
        return c[1]
    dg = bpy.context.evaluated_depsgraph_get()
    ev = g.evaluated_get(dg)
    em = ev.to_mesh()
    z = np.empty(len(em.vertices) * 3, np.float32)
    em.vertices.foreach_get('co', z)
    ev.to_mesh_clear()
    ax = P._env['axis']
    if len(z) // 3 != len(ax) ** 2:
        P._env['zcache'] = (key, None)
        return None
    Z = z[2::3].reshape(len(ax), len(ax)).astype(np.float64)
    P._env['zcache'] = (key, Z)
    return Z


def ground_z(P, x, y):
    if not getattr(P, 'ground', None):
        return 0.0
    Z = _eval_heights(P)
    if Z is None:     # topology changed by a scene: fall back to a ray cast
        dg = bpy.context.evaluated_depsgraph_get()
        ok, loc, _, _ = P.ground.evaluated_get(dg).ray_cast(Vector((x, y, 2000)), Vector((0, 0, -1)))
        return loc.z if ok else 0.0
    ax = P._env['axis']
    n = len(ax)
    if not (ax[0] <= x <= ax[-1] and ax[0] <= y <= ax[-1]):
        return 0.0
    i = min(max(int(np.searchsorted(ax, x)) - 1, 0), n - 2)
    j = min(max(int(np.searchsorted(ax, y)) - 1, 0), n - 2)
    tx = (x - ax[i]) / (ax[i + 1] - ax[i])
    ty = (y - ax[j]) / (ax[j + 1] - ax[j])
    # quads are split along (i,j)-(i+1,j+1)? Blender triangulates quads for rendering along the
    # shorter diagonal; bilinear is within millimetres here.
    z00, z10, z01, z11 = Z[j, i], Z[j, i + 1], Z[j + 1, i], Z[j + 1, i + 1]
    return float((z00 * (1 - tx) + z10 * tx) * (1 - ty) + (z01 * (1 - tx) + z11 * tx) * ty)


def ground_normal(P, x, y, e=0.6):
    zx = ground_z(P, x + e, y) - ground_z(P, x - e, y)
    zy = ground_z(P, x, y + e) - ground_z(P, x, y - e)
    return Vector((-zx, -zy, 2 * e)).normalized()


def flatten(P, x, y, r):
    P._clear.append((x, y, r))
    g = P.ground
    ax = P._env['axis']
    X, Y = np.meshgrid(ax, ax)
    d = np.hypot(X - x, Y - y).ravel()
    w = sstep(0.0, 1.0, (d - r) / (r * 0.8 + 4)).astype(np.float32)
    fw = np.minimum(P._env['flat_w'], w)
    changed = np.nonzero(fw < P._env['flat_w'] - 1e-4)[0]
    P._env['flat_w'] = fw
    vg = g.vertex_groups['Flat']
    q = np.round(fw[changed] * 255).astype(np.int32)
    for lvl in np.unique(q):
        idx = changed[q == lvl].tolist()
        vg.add(idx, float(lvl) / 255.0, 'REPLACE')
    mod = g.modifiers['Displace']
    mod.vertex_group = 'Flat'
    P._env['flat_ver'] = P._env.get('flat_ver', 0) + 1
    g.data.update()
    return P


# ------------------------------------------------------------------------------ finalize
def _sample_scene(P):
    """Camera and actor positions over the clip, sampled every few frames."""
    sc = bpy.context.scene
    cur = sc.frame_current
    cams, acts = [], []
    movers = [a for a in P.actors if not a.name.startswith('proto_') and a not in P._env['deposits']]
    for f in range(sc.frame_start, sc.frame_end + 1, 6):
        sc.frame_set(f)
        if P.cam:
            cams.append(P.cam.matrix_world.translation.copy())
        for a in movers:
            p = a.root.matrix_world.translation
            if p.z - ground_z(P, p.x, p.y) < 3.0:     # air units don't block props
                acts.append((p.x, p.y, a.size * 0.6 + 1.2))
    sc.frame_set(cur)
    return cams, acts


def _cover_density(P, cams):
    g = P.ground
    ax = P._env['axis']
    X, Y = np.meshgrid(ax, ax)
    X, Y = X.ravel(), Y.ravel()
    if cams:
        dmin = np.full(X.shape, 1e9)
        for c in cams:
            dmin = np.minimum(dmin, np.hypot(X - c.x, Y - c.y) - 0.0 * c.z)
        hmax = max(c.z for c in cams)
        reach = 34.0 + min(hmax, 30.0)
        dens = sstep(reach, reach * 0.6, dmin)
    else:
        dens = sstep(45.0, 25.0, np.hypot(X, Y))
    a = g.data.attributes.get('cover') or g.data.attributes.new('cover', 'FLOAT', 'POINT')
    a.data.foreach_set('value', dens.astype(np.float32))
    fa = g.data.attributes.get('Flat')
    # expose the flatten weights to geometry nodes too (vertex group is also readable, but be explicit)
    g.data.update()


def dress_prop_materials(objs, b, kd, done):
    """Biome blend on a loaded prop's materials: tint toward the biome rock colour, dust/moss on
    up-facing surfaces, a little macro variation, and aerial haze. Generic: works on whatever
    Principled materials the glb carries."""
    for o in objs:
        if o.type != 'MESH':
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None or m.name in done or not m.node_tree:
                continue
            done.add(m.name)
            nt = m.node_tree
            bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
            if bsdf is not None:
                B = NB(nt)
                bc = bsdf.inputs['Base Color']
                src = bc.links[0].from_socket if bc.links else tuple(bc.default_value)[:3]
                geo = B.node('ShaderNodeNewGeometry')
                upz = B.node('ShaderNodeSeparateXYZ', Vector=geo.outputs['Normal']).outputs['Z']
                tc = B.node('ShaderNodeTexCoord')
                nn = B.noise(tc.outputs['Generated'], 4.0, detail=4)
                isrock = kd in ('boulder', 'rock_cluster', 'cliff', 'slab')
                col = src
                if isrock:
                    col = B.mix(1.0, col, tuple(min(1.0, 2.1 * x) for x in b['rock_tint']), 'MULTIPLY')
                    col = B.mix(0.3, col, b['rock_tint'], 'MIX')
                    col = B.mix(B.math('MULTIPLY', B.maprange(nn, 0.35, 0.7), 0.35), col, tuple(x * 0.55 for x in b['rock_tint']))
                cover = b['dust'] if kd != 'shrub' else tuple(x * 0.8 for x in b['dust'])
                top = B.maprange(B.math('ADD', upz, B.math('MULTIPLY', B.math('SUBTRACT', nn, 0.5), 0.5)), 0.55, 0.85)
                amt = 0.3 if isrock else 0.2
                col = B.mix(B.math('MULTIPLY', top, amt), col, cover)
                # grounded base: darker, dustier lower part (Generated z is 0 at the mesh bottom)
                gz = B.node('ShaderNodeSeparateXYZ', Vector=tc.outputs['Generated']).outputs['Z']
                base = B.maprange(gz, 0.18, 0.0)
                col = B.mix(B.math('MULTIPLY', base, 0.5), col, tuple(x * 0.6 for x in b['g1']))
                B.set(bsdf, 'Base Color', col)
                if isrock:
                    try:
                        if not bsdf.inputs['Roughness'].links:
                            bsdf.inputs['Roughness'].default_value = max(0.75, bsdf.inputs['Roughness'].default_value)
                        bsdf.inputs['Metallic'].default_value = 0.0 if not bsdf.inputs['Metallic'].links else bsdf.inputs['Metallic'].default_value
                    except KeyError:
                        pass
                    nb = bsdf.inputs['Normal']
                    if not nb.links:
                        bump = B.node('ShaderNodeBump', Strength=0.35, Distance=0.05,
                                      Height=B.noise(tc.outputs['Object'], 6.0, detail=6))
                        B.L.new(bump.outputs['Normal'], nb)
            haze_wrap(m, b, b['bg'])


# props per biome: (kind, weight)
SCATTER = {
    'alien': dict(anchor=['boulder', 'rock_cluster', 'slab'], small=['boulder'], solo=['tendril', 'slab', 'tendril'], tree=None),
    'ash': dict(anchor=['boulder', 'rock_cluster'], small=['boulder'], solo=['dead_tree', 'boulder'], tree='dead_tree'),
}


def finalize(P):
    """Called at the start of render(): ground cover density from the camera path, deposit
    re-snap, and the clustered prop scatter (after all flatten() calls and actor paths)."""
    E = getattr(P, '_env', None)
    if not E or E.get('finalized') or not getattr(P, 'ground', None):
        return
    E['finalized'] = True
    b = P.palette
    rnd = E['rng']
    cams, acts = _sample_scene(P)
    _cover_density(P, cams)
    for a in E['deposits']:
        x, y = a.root.location.x, a.root.location.y
        r = a.size * 0.35
        zs = [ground_z(P, x + r * math.cos(t), y + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
        a.root.location.z = min(zs + [ground_z(P, x, y)]) - 0.2
    n = E['props']
    if not n:
        return
    from promo_kit import empty  # noqa: E402
    kind = E['kind']
    R = E['radius']
    if kind == 'alien':
        kinds = ['boulder', 'rock_cluster', 'slab', 'tendril']
    elif kind == 'ash':
        kinds = ['boulder', 'rock_cluster', 'dead_tree', 'shrub']
    else:
        kinds = ['boulder', 'rock_cluster', 'shrub', 'dead_tree']
    protos = {}
    done = set()
    for kd in kinds:
        try:
            a = P.load(kd, at=(0, 0), label='proto_' + kd)
        except Exception as e:  # a missing prop model must not break a clip
            print('promo_env: prop', kd, 'unavailable:', e)
            continue
        for o in [a.root] + list(a.root.children_recursive):
            o.hide_render = True
            o.hide_viewport = True
        dress_prop_materials(a.root.children_recursive, b, kd, done)
        protos[kd] = a
    if not protos:
        return
    blockers = [(x, y, r) for x, y, r in P._clear] + [(x, y, r) for x, y, r in acts] + [(c.x, c.y, 4.0) for c in cams]

    def free(x, y, rad):
        for bx, by, br in blockers:
            if (x - bx) ** 2 + (y - by) ** 2 < (br + rad) ** 2:
                return False
        return R * 0.97 > abs(x) and R * 0.97 > abs(y)

    placed = []

    def put(kd, x, y, s, tilt=True, sink=0.12, yaw=None):
        if kd not in protos:
            return False
        pr = protos[kd]
        foot = pr.size * s * 0.5
        if not free(x, y, foot * 0.8):
            return False
        for px, py, pr_ in placed:
            if (x - px) ** 2 + (y - py) ** 2 < (pr_ + foot * 0.6) ** 2 * 0.5:
                return False
        h = empty(f'prop_{kd}_{len(placed)}')
        P._instance(pr.root, h)
        # sit on the lowest point under the footprint so no edge floats, then sink a little
        rr = foot * 0.7
        zs = [ground_z(P, x + rr * math.cos(t), y + rr * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
        z0 = min(zs + [ground_z(P, x, y)])
        hgt = pr.entry.get('height', pr.size * 0.6) * s
        h.location = (x, y, z0 - sink * hgt)
        rot = Matrix.Rotation(yaw if yaw is not None else rnd.uniform(0, 2 * math.pi), 4, 'Z')
        if tilt:
            nrm = ground_normal(P, x, y, max(0.5, foot * 0.5))
            nrm = nrm.lerp(Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), 1)).normalized(), 0.5)
            rot = nrm.to_track_quat('Z', 'Y').to_matrix().to_4x4() @ rot
        h.rotation_euler = rot.to_euler()
        h.scale = (s, s, s)
        placed.append((x, y, foot))
        return True

    # cluster centres spread over the visible ground: more where the camera looks
    def pick_spot():
        for _ in range(60):
            if cams and rnd.random() < 0.75:
                c = rnd.choice(cams)
                ang = rnd.uniform(0, 2 * math.pi)
                d = rnd.uniform(10, min(R * 0.6, 75))
                x, y = c.x + d * math.cos(ang), c.y + d * math.sin(ang)
            else:
                rr = rnd.uniform(10, R * 0.6)
                ang = rnd.uniform(0, 2 * math.pi)
                x, y = rr * math.cos(ang), rr * math.sin(ang)
            if free(x, y, 2.5):
                return x, y
        return None

    alien = kind == 'alien'
    budget = n
    big = [k for k in ('boulder', 'rock_cluster', 'slab' if alien else 'rock_cluster') if k in protos]
    guard = 0
    while budget > 0 and guard < n * 6:
        guard += 1
        spot = pick_spot()
        if spot is None:
            break
        x, y = spot
        roll = rnd.random()
        if roll < 0.55 and big:
            # rock group: one anchor, satellites, scree
            kd = rnd.choice(big)
            s = rnd.uniform(0.9, 2.0) if kd != 'rock_cluster' else rnd.uniform(0.7, 1.4)
            if put(kd, x, y, s, sink=0.15):
                budget -= 1
            arad = protos[kd].size * s * 0.5
            for _ in range(rnd.randint(1, 4)):
                a_ = rnd.uniform(0, 2 * math.pi)
                d = arad * rnd.uniform(0.9, 1.8)
                if put('boulder', x + d * math.cos(a_), y + d * math.sin(a_), rnd.uniform(0.25, 0.6), sink=0.2):
                    budget -= 1
            for _ in range(rnd.randint(3, 8)):   # scree: cheap, not counted
                a_ = rnd.uniform(0, 2 * math.pi)
                d = arad * rnd.uniform(0.8, 2.6)
                put('boulder', x + d * math.cos(a_), y + d * math.sin(a_), rnd.uniform(0.06, 0.16), sink=0.25)
            if not alien and 'shrub' in protos and rnd.random() < 0.6:
                a_ = rnd.uniform(0, 2 * math.pi)
                d = arad * rnd.uniform(1.0, 1.6)
                if put('shrub', x + d * math.cos(a_), y + d * math.sin(a_), rnd.uniform(0.6, 1.1), tilt=False, sink=0.05):
                    budget -= 1
            if alien and 'tendril' in protos and rnd.random() < 0.5:
                a_ = rnd.uniform(0, 2 * math.pi)
                d = arad * rnd.uniform(1.0, 1.8)
                if put('tendril', x + d * math.cos(a_), y + d * math.sin(a_), rnd.uniform(0.5, 1.0), tilt=False, sink=0.05):
                    budget -= 1
        elif roll < 0.8:
            # shrubs / tendrils in loose groups
            kd = 'tendril' if alien else ('shrub' if kind != 'ash' or rnd.random() < 0.3 else 'boulder')
            for _ in range(rnd.randint(1, 4)):
                a_ = rnd.uniform(0, 2 * math.pi)
                d = rnd.uniform(0, 3.5)
                if put(kd, x + d * math.cos(a_), y + d * math.sin(a_), rnd.uniform(0.45, 1.1), tilt=kd == 'boulder', sink=0.05):
                    budget -= 1
        elif roll < 0.9:
            # lone tree (or slab) with a rock at its foot
            kd = 'slab' if alien else 'dead_tree'
            if put(kd, x, y, rnd.uniform(0.7, 1.25), tilt=alien, sink=0.04 if not alien else 0.15):
                budget -= 1
                a_ = rnd.uniform(0, 2 * math.pi)
                put('boulder', x + 1.4 * math.cos(a_), y + 1.4 * math.sin(a_), rnd.uniform(0.15, 0.35), sink=0.25)
        else:
            # lone small boulder
            if put('boulder', x, y, rnd.uniform(0.3, 0.8), sink=0.18):
                budget -= 1


# ------------------------------------------------------------------------------------ space
def _space_world(b, sun_dir, stars, nebula):
    w = bpy.data.worlds.new('Space')
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    B = NB(nt)
    tc = B.node('ShaderNodeTexCoord')
    d = B.vmath('NORMALIZE', tc.outputs['Generated'])
    neb = tuple(nebula)
    warm = (neb[2] * 0.9 + 0.02, neb[1] * 0.8 + 0.015, neb[0] * 0.5)       # complementary glow
    col = (0.0012, 0.0012, 0.0022)
    # nebula: two warped noise clouds, colour-shifted, cut by dark dust lanes
    wp = B.vmath('ADD', d, B.vmath('SCALE', B.node('ShaderNodeTexNoise', Vector=d, Scale=1.4, Detail=3).outputs['Color'], scale=0.6))
    n1 = B.noise(wp, 1.6, detail=8, rough=0.62)
    n2 = B.noise(wp, 3.3, detail=8, rough=0.6, dist=0.4)
    a1 = B.math('POWER', B.maprange(n1, 0.42, 0.8, smooth=False), 2.2)
    a2 = B.math('POWER', B.maprange(n2, 0.5, 0.85, smooth=False), 2.0)
    lanes = B.maprange(B.noise(wp, 5.0, detail=6, rough=0.7), 0.45, 0.6)
    lanes = B.math('SUBTRACT', 1.0, B.math('MULTIPLY', lanes, 0.85))
    col = B.mix(B.math('MULTIPLY', a1, 1.0), col, tuple(c * 1.3 for c in neb), 'ADD')
    col = B.mix(B.math('MULTIPLY', a2, 0.8), col, warm, 'ADD')
    col = B.mix(lanes, (0.0, 0.0, 0.0), col)
    # a faint galactic band along a tilted great circle (denser stars + glow)
    band_n = Vector((0.25, -0.55, 0.8)).normalized()
    bd = B.math('ABSOLUTE', B.vmath('DOT_PRODUCT', d, tuple(band_n)))
    band = B.math('MULTIPLY', B.maprange(bd, 0.28, 0.0), B.maprange(B.noise(wp, 2.2, detail=6), 0.35, 0.75))
    col = B.mix(B.math('MULTIPLY', band, 0.6), col, (0.05, 0.045, 0.05), 'ADD')
    col = B.mix(lanes, (0.0, 0.0, 0.0), col)
    if stars:
        for sc, thr, gain, seedv in ((900.0, 0.02, 7.0, 0.0), (420.0, 0.03, 3.0, 3.3), (160.0, 0.04, 1.4, 7.7)):
            vo = B.N.new('ShaderNodeTexVoronoi')
            vo.inputs['Scale'].default_value = sc
            B.set(vo, 'Vector', B.vmath('ADD', d, (seedv, seedv * 0.5, 0.0)))
            pt = B.maprange(vo.outputs['Distance'], thr, 0.0, smooth=False)
            pt = B.math('POWER', pt, 2.0)
            cs = B.node('ShaderNodeSeparateColor', Color=vo.outputs['Color'])
            keep = B.maprange(cs.outputs[0], 0.55 if sc > 500 else 0.75, 0.6 if sc > 500 else 0.8, smooth=False)
            dens = B.math('ADD', keep, B.math('MULTIPLY', band, 0.6))
            br = B.math('MULTIPLY', B.math('MULTIPLY', pt, B.math('MINIMUM', dens, 1.0)), B.math('MULTIPLY', cs.outputs[1], gain))
            tint = B.mix(cs.outputs[2], (0.7, 0.8, 1.0), (1.0, 0.85, 0.65))
            col = _add_scaled(B, col, tint, br)
    # the sun: small hot core + soft glow
    sdot = B.math('MAXIMUM', B.vmath('DOT_PRODUCT', d, tuple(sun_dir)), 0.0)
    glow = B.math('ADD', B.math('MULTIPLY', B.math('POWER', sdot, 2000.0), 6.0), B.math('MULTIPLY', B.math('POWER', sdot, 60.0), 0.18))
    col = _add_scaled(B, col, (1.0, 0.92, 0.8), glow)
    bg = B.node('ShaderNodeBackground', Color=col, Strength=1.0)
    out = B.node('ShaderNodeOutputWorld')
    B.L.new(bg.outputs[0], out.inputs['Surface'])
    return w


def _add_scaled(B, col, tint, amount):
    sc = B.node('ShaderNodeMix')
    sc.data_type = 'RGBA'
    sc.blend_type = 'MULTIPLY'
    B.set(sc, 'Factor_Float', 1.0)
    B.set(sc, 'A_Color', tint)
    cc = B.node('ShaderNodeCombineColor', Red=amount, Green=amount, Blue=amount)
    B.set(sc, 'B_Color', cc.outputs[0])
    return B.mix(1.0, col, B.out(sc, 'Result_Color'), 'ADD')


def _planet(x, y, z, r, c, sun_dir, rng):
    """Planet with procedural oceans/land/clouds, limb haze, lit atmosphere rim and a soft
    terminator (the sun lamp lights it; the rim glow follows the sun side)."""
    from promo_kit import link as _lk
    c = tuple(c)
    ocean = tuple(v * 0.55 for v in c)
    deep = tuple(v * 0.3 for v in c)
    lum = (c[0] + c[1] + c[2]) / 3
    land = (0.6 * lum + 0.12, 0.55 * lum + 0.09, 0.4 * lum + 0.05)
    land2 = (0.5 * lum + 0.06, 0.55 * lum + 0.08, 0.35 * lum + 0.03)
    atmo = tuple(min(1.0, 0.8 * v / max(c) + 0.05) for v in c) if max(c) > 0 else (0.35, 0.55, 1.0)
    m = bpy.data.materials.new('Planet')
    nt = m.node_tree
    B = NB(nt)
    bsdf = nt.nodes.get('Principled BSDF')
    tc = B.node('ShaderNodeTexCoord')
    P = B.vmath('NORMALIZE', tc.outputs['Object'])
    off = (rng.uniform(0, 50), rng.uniform(0, 50), rng.uniform(0, 50))
    Po = B.vmath('ADD', P, off)
    wp = B.vmath('ADD', Po, B.vmath('SCALE', B.node('ShaderNodeTexNoise', Vector=Po, Scale=1.5, Detail=4).outputs['Color'], scale=0.5))
    cont = B.noise(wp, 1.6, detail=10, rough=0.6)
    landm = B.maprange(cont, 0.53, 0.56)
    shelf = B.maprange(cont, 0.45, 0.53)
    col = B.mix(shelf, deep, ocean)
    lv = B.noise(wp, 6.0, detail=8)
    lc = B.mix(B.maprange(lv, 0.35, 0.65), land2, land)
    sepz = B.node('ShaderNodeSeparateXYZ', Vector=P).outputs['Z']
    ice = B.maprange(B.math('ADD', B.math('ABSOLUTE', sepz), B.math('MULTIPLY', B.math('SUBTRACT', lv, 0.5), 0.12)), 0.955, 0.975)
    col = B.mix(landm, col, lc)
    col = B.mix(ice, col, (0.45, 0.47, 0.5))
    # cloud bands: stretched along latitude, swirled
    cp = B.vmath('MULTIPLY', B.vmath('ADD', Po, B.vmath('SCALE', B.node('ShaderNodeTexNoise', Vector=Po, Scale=3.0, Detail=3).outputs['Color'], scale=0.25)), (1.0, 1.0, 3.2))
    cl = B.maprange(B.noise(cp, 4.0, detail=12, rough=0.66, dist=0.3), 0.56, 0.66)
    col = B.mix(B.math('MULTIPLY', cl, 0.8), col, (0.42, 0.44, 0.47))
    B.set(bsdf, 'Base Color', col)
    B.set(bsdf, 'Roughness', B.math('ADD', B.math('MULTIPLY', B.math('SUBTRACT', 1.0, landm), -0.25), 0.9))
    try:
        bsdf.inputs['Specular IOR Level'].default_value = 0.0
    except KeyError:
        pass
    # limb haze on the surface itself (lit side only)
    geo = B.node('ShaderNodeNewGeometry')
    lw = B.node('ShaderNodeLayerWeight', Blend=0.2)
    ndl = B.vmath('DOT_PRODUCT', geo.outputs['Normal'], tuple(sun_dir))
    lit = B.maprange(ndl, -0.15, 0.45)
    em = B.math('MULTIPLY', B.math('POWER', lw.outputs['Facing'], 2.5), lit)
    B.set(bsdf, 'Emission Color', atmo)
    B.set(bsdf, 'Emission Strength', B.math('MULTIPLY', B.math('POWER', em, 3.0), 0.2))
    pl = sphere_obj('Planet', r, m, (x, y, z), 192, 96)
    # atmosphere shell: transparent, additive rim, brightest at the sunlit limb, a thin
    # twilight band across the terminator
    am = bpy.data.materials.new('Atmo')
    nt = am.node_tree
    nt.nodes.clear()
    B = NB(nt)
    out = B.node('ShaderNodeOutputMaterial')
    geo = B.node('ShaderNodeNewGeometry')
    # f = 1 - |N.V|: the planet's limb sits at f_limb on this shell; glow peaks there, fades
    # out to the shell edge (no hard ring) and quickly inward over the disc
    kk = 1.03
    fl = 1 - math.sqrt(1 - 1 / kk ** 2)
    f = B.math('SUBTRACT', 1.0, B.math('ABSOLUTE', B.vmath('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming'])))
    ndl = B.vmath('DOT_PRODUCT', geo.outputs['Normal'], tuple(sun_dir))
    lit = B.maprange(ndl, -0.2, 0.45)
    inner = B.math('POWER', B.maprange(f, fl - 0.14, fl, smooth=False), 2.0)
    outer = B.math('POWER', B.maprange(f, 1.0, fl, smooth=False), 1.6)
    rim = B.math('MULTIPLY', inner, outer)
    amt = B.math('MULTIPLY', rim, lit)
    twi = B.math('MULTIPLY', B.maprange(B.math('ABSOLUTE', ndl), 0.15, 0.0), B.math('MULTIPLY', rim, 0.7))
    twc = (1.0, 0.5, 0.25)
    emi = B.node('ShaderNodeEmission', Color=atmo, Strength=B.math('MULTIPLY', amt, 1.0))
    emt = B.node('ShaderNodeEmission', Color=twc, Strength=B.math('MULTIPLY', twi, 1.2))
    add = B.node('ShaderNodeAddShader')
    B.L.new(emi.outputs[0], add.inputs[0])
    B.L.new(emt.outputs[0], add.inputs[1])
    tr = B.node('ShaderNodeBsdfTransparent')
    add2 = B.node('ShaderNodeAddShader')
    B.L.new(add.outputs[0], add2.inputs[0])
    B.L.new(tr.outputs[0], add2.inputs[1])
    B.L.new(add2.outputs[0], out.inputs['Surface'])
    at = sphere_obj('Atmosphere', r * kk, am, (x, y, z), 192, 96)
    at.visible_shadow = False
    return pl, at


def sphere_obj(name, r, mat, loc, seg, rings):
    from promo_kit import link as _lk
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    o = _lk(bpy.data.objects.new(name, me))
    o.location = loc
    return o


def build_space(P, stars=True, planet=None, nebula=(0.08, 0.03, 0.12), sun=(30, 0, 40), sun_energy=3.5):
    s = _link(bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')))
    s.data.energy = sun_energy
    s.data.angle = math.radians(0.6)
    s.rotation_euler = [math.radians(a) for a in sun]
    P.sun = s
    sun_dir = (s.rotation_euler.to_matrix() @ Vector((0, 0, 1))).normalized()
    _space_world(None, sun_dir, stars, nebula)
    P.ground = None
    P.env_kind = 'space'
    if planet:
        x, y, z, r, c = planet
        _planet(x, y, z, r, c, sun_dir, random.Random(int(abs(x) + abs(y) * 7 + r)))
    return P
