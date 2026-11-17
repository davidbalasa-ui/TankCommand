"""Scenery and resource sites, art pass v2. One mesh each, origin at ground level in the centre."""
import math
import random

import bpy
from mathutils import Vector

import forge as F
import nature as NA
from forge import box, cyl, lathe, orb, rock, sweep, tube

ASSETS = {}


def nasset(path, label, size=512):
    """Scenery built with nature.py: sculpted high-poly baked onto a light mesh."""
    def deco(fn):
        def run(glb, render, report):
            NA.begin()
            kw = fn() or {}
            NA.finish(kw.pop('name'), glb, render=render, report=report, label=label, size=kw.pop('size', size), **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='props')
        return run
    return deco


def pebbles(rnd, n, centre, r0, r1, smin, smax, zone, seed, tris=28, ring=None):
    """Loose stones round a base: n pebbles between radius r0 and r1 of centre."""
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi) if ring is None else ring[0] + rnd.uniform(-ring[1], ring[1])
        d = rnd.uniform(r0, r1)
        s = rnd.uniform(smin, smax)
        NA.rock((centre[0] + math.cos(a) * d, centre[1] + math.sin(a) * d, s * 0.25), (s, s * rnd.uniform(0.7, 1.0), s * rnd.uniform(0.5, 0.8)),
                zone, seed=seed + k, tris=tris, cuts=6, chips=0, cracks=0, grain=0.004, round_=0.05, floor=-0.05, depth=(0.55, 0.85),
                yaw=rnd.uniform(0, 360), lumpy=0.15)


def asset(path, label, size=256):
    def deco(fn):
        def run(glb, render, report):
            F.begin('nature')
            kw = fn() or {}
            F.finish(kw.pop('name'), glb, render=render, report=report, label=label, size=kw.pop('size', size),
                     single=True, ao_floor=0.45, **kw)
        ASSETS[fn.__name__] = dict(fn=run, path=path, set='props')
        return run
    return deco


@nasset('props/boulder.glb', 'Boulder')
def boulder():
    rnd = random.Random(31)
    # A weathered block split along its bedding: the main mass, a slab that broke off and leans
    # against it, a smaller stone and loose chips at the foot.
    NA.rock((0.05, 0.05, 0.5), (1.22, 1.0, 0.98), 'granite', seed=3, tris=1150, cuts=10, chips=14, round_=0.025, depth=(0.55, 0.85),
            flat_top=0.3, yaw=12, tilt=(4, -6))
    NA.rock((0.92, -0.62, 0.32), (0.5, 0.36, 0.5), 'granite', seed=5, tris=360, cuts=9, chips=6, yaw=-30, tilt=(16, 10),
            depth=(0.5, 0.75), flat_top=0.5)
    NA.rock((-0.95, 0.58, 0.16), (0.36, 0.3, 0.3), 'granite', seed=8, tris=200, cuts=5, chips=4)
    pebbles(rnd, 7, (0, 0), 1.0, 1.3, 0.1, 0.22, 'granite', 50)
    return dict(name='Boulder')


@nasset('props/rock_cluster.glb', 'Rock cluster')
def rock_cluster():
    rnd = random.Random(4)
    # One dominant angular block off-centre, a slab-sided piece leaning on it, a low flat stone and
    # smaller fragments trailing away downhill.
    NA.rock((-0.35, 0.15, 0.48), (0.95, 0.78, 0.82), 'granite', seed=20, tris=820, cuts=10, chips=12, depth=(0.5, 0.8),
            yaw=20, tilt=(-6, 10))
    NA.rock((0.62, 0.38, 0.42), (0.62, 0.24, 0.6), 'granite', seed=21, tris=300, cuts=8, chips=6, depth=(0.55, 0.85),
            flat_top=0.6, yaw=35, tilt=(-26, 4))
    NA.rock((0.98, -0.5, 0.2), (0.46, 0.38, 0.36), 'granite', seed=23, tris=260, cuts=9, chips=5, depth=(0.5, 0.8), yaw=-15,
            tilt=(8, -12))
    NA.rock((-1.08, -0.55, 0.05), (0.44, 0.36, 0.17), 'granite', seed=24, tris=170, cuts=7, chips=4, flat_top=0.7, yaw=30,
            tilt=(4, 6))
    NA.rock((0.18, -0.85, 0.08), (0.26, 0.22, 0.2), 'granite', seed=25, tris=110, cuts=7, chips=3, depth=(0.5, 0.8))
    NA.rock((1.35, 0.15, 0.06), (0.2, 0.17, 0.15), 'granite', seed=26, tris=80, cuts=6, chips=2, depth=(0.5, 0.8))
    pebbles(rnd, 6, (0.9, -0.9), 0.05, 0.45, 0.07, 0.15, 'granite', 60)
    pebbles(rnd, 5, (0.0, 0.0), 1.05, 1.3, 0.06, 0.12, 'granite', 70)
    return dict(name='RockCluster')


@nasset('props/slab.glb', 'Rock slab')
def slab():
    # Bedrock breaking the surface: a broad tilted plate with layered edges, a second plate riding
    # over it and a split-off piece, grit along the joints.
    rnd = random.Random(11)
    st = (6.0, 0.035, 0.012)
    NA.rock((0.15, 0, 0.05), (2.55, 1.15, 0.32), 'crag', seed=11, tris=600, cuts=11, chips=12, strata=st, flat_top=0.9,
            yaw=4, tilt=(0, -3), crack_scale=0.7, depth=(0.5, 0.8), lumpy=0.04, round_=0.015)
    NA.rock((0.75, 0.15, 0.3), (1.4, 0.75, 0.18), 'crag', seed=12, tris=330, cuts=10, chips=8, strata=st, flat_top=0.9,
            yaw=-12, tilt=(2, -9), depth=(0.5, 0.8), lumpy=0.04, round_=0.015)
    NA.rock((-1.55, -0.4, 0.2), (0.65, 0.48, 0.2), 'crag', seed=13, tris=200, cuts=9, chips=5, strata=st, flat_top=0.85,
            yaw=25, tilt=(12, 4), depth=(0.5, 0.8), lumpy=0.04, round_=0.015)
    pebbles(rnd, 7, (0.2, -0.75), 0.1, 0.7, 0.07, 0.15, 'crag', 30)
    pebbles(rnd, 4, (-1.9, 0.3), 0.0, 0.3, 0.06, 0.12, 'crag', 40)
    return dict(name='Slab')


@nasset('props/cliff.glb', 'Cliff crag')
def cliff():
    rnd = random.Random(41)
    st = (2.3, 0.13, 0.03)    # beds ~43 cm thick, each receding under the lip of the bed above
    # One bedded massif: a tall central buttress with lower shoulders that merge into it (shared
    # beds, so the layers run on across the joints), blocky joint faces, an overhanging cap bed.
    NA.rock((0.0, 0.1, 1.4), (1.6, 1.0, 1.95), 'crag', seed=40, tris=1400, cuts=10, chips=14, strata=st,
            flat_top=0.55, taper=0.0, round_=0.02, crack_scale=0.8, depth=(0.6, 0.86))
    NA.rock((-1.55, 0.2, 0.8), (1.3, 0.95, 1.2), 'crag', seed=41, tris=760, cuts=9, chips=10, strata=st, flat_top=0.65,
            yaw=-12, tilt=(2, 4), round_=0.02, depth=(0.6, 0.86))
    NA.rock((1.55, 0.25, 0.9), (1.25, 0.9, 1.3), 'crag', seed=42, tris=760, cuts=9, chips=10, strata=st, flat_top=0.6,
            yaw=15, tilt=(-3, -5), round_=0.02, depth=(0.6, 0.86))
    # Cap bed jutting out over the front face, and a ledge bed on the left shoulder.
    NA.rock((0.35, -0.12, 2.95), (1.35, 0.9, 0.42), 'crag', seed=43, tris=360, cuts=10, chips=8, strata=(2.3, 0.04, 0.03),
            flat_top=0.7, yaw=18, tilt=(-4, 3), round_=0.02, depth=(0.5, 0.8))
    NA.rock((-0.65, 0.25, 2.72), (0.75, 0.62, 0.42), 'crag', seed=49, tris=200, cuts=9, chips=5, strata=st,
            flat_top=0.6, yaw=-25, tilt=(3, -4), round_=0.02, depth=(0.5, 0.8))
    NA.rock((-1.35, -0.3, 1.62), (0.95, 0.62, 0.26), 'crag', seed=44, tris=240, cuts=8, chips=6, yaw=-15, tilt=(-5, 3),
            flat_top=0.7, round_=0.02, depth=(0.65, 0.9))
    # Fallen blocks and a talus fan at the foot of the open face.
    NA.rock((0.95, -0.95, 0.28), (0.5, 0.4, 0.4), 'crag', seed=45, tris=200, cuts=9, chips=5, yaw=35, tilt=(14, -8),
            depth=(0.5, 0.8), strata=st)
    NA.rock((-0.6, -0.95, 0.2), (0.44, 0.34, 0.3), 'crag', seed=46, tris=170, cuts=9, chips=4, yaw=-10, tilt=(-12, 6),
            depth=(0.5, 0.8))
    NA.rock((2.5, -0.35, 0.18), (0.4, 0.33, 0.3), 'crag', seed=47, tris=140, cuts=8, chips=3, depth=(0.5, 0.8))
    NA.rock((-2.6, -0.3, 0.2), (0.38, 0.3, 0.32), 'crag', seed=48, tris=140, cuts=8, chips=3, depth=(0.5, 0.8))
    pebbles(rnd, 9, (0.35, -0.75), 0.15, 0.6, 0.1, 0.24, 'crag', 80)       # talus fan below the buttress
    pebbles(rnd, 6, (-1.3, -0.65), 0.1, 0.5, 0.08, 0.18, 'crag', 90)
    pebbles(rnd, 6, (0.0, -0.3), 0.85, 1.0, 0.06, 0.12, 'crag', 95, ring=(-math.pi / 2, 1.4))
    return dict(name='Cliff', ext=0.09)


def leaf(base, length, width, yaw, pitch, zone, curl=0.5, n=5):
    pts, sect = [], []
    for k in range(n):
        t = k / (n - 1)
        a = math.radians(pitch) * (1 - curl * t)
        pts.append((t * length * math.cos(a), 0, t * length * math.sin(a) - curl * 0.25 * length * t * t))
        w = width * (0.25 + math.sin(math.pi * min(t * 1.15, 1)) * 0.75) * (1 - t * 0.85)
        sect.append((max(w, 0.006), max(w * 0.14, 0.004)))
    o = sweep(pts, sect, zone, sides=4, up=(0, 0, 1), sharp=60)
    F.rot(o, 'Z', yaw)
    F.move(o, base)
    return o


def _veg_mat(name, build):
    def make():
        key = f'veg:{name}'
        if key in NA.ST['mats']:
            return NA.ST['mats'][key]
        mat = bpy.data.materials.new(f'n_{name}')
        mat.use_nodes = True
        n = F.N(mat)
        build(n)
        NA._ao_node(n, 0.25)
        NA.ST['mats'][key] = mat
        return mat
    NA.MATS[name] = make


def _grass_shader(n):
    t = NA.attr(n, 'st')
    v = NA.attr(n, 'sv')
    root, mid, tip = (0.07, 0.1, 0.03), (0.2, 0.3, 0.06), (0.42, 0.42, 0.14)
    col = n.mix(n.smooth(t, 0.0, 0.55), root, mid)
    col = n.mix(n.smooth(t, 0.5, 1.0), col, tip)
    # some blades greener, some dry straw, a few with a bronze alien tint
    col = n.mix(n.m('MULTIPLY', n.smooth(v, 0.72, 0.8), n.smooth(t, 0.1, 0.6)), col, (0.32, 0.26, 0.12))
    col = n.mix(n.m('MULTIPLY', n.smooth(v, 0.0, 0.12), 0.7), col, (0.06, 0.13, 0.05))
    col = n.mix(n.m('MULTIPLY', n.smooth(v, 0.45, 0.5), n.m('MULTIPLY', n.smooth(t, 0.55, 1.0), 0.6)), col, (0.32, 0.14, 0.06))
    vein = n.smooth(n.noise(60.0, 2.0, co=n.vscale(n.co, (1.0, 1.0, 0.08))), 0.55, 0.7)
    col = n.mix(n.m('MULTIPLY', vein, 0.25), col, (0.0, 0.0, 0.0))
    n.out(col, n.m('ADD', 0.55, n.m('MULTIPLY', t, 0.25)), 0.0)
    n.bump(vein, 0.2, 0.004, soft=False)


def _succulent_shader(n):
    t = NA.attr(n, 'st')
    v = NA.attr(n, 'sv')
    base, body, bloom = (0.06, 0.08, 0.03), (0.17, 0.25, 0.08), (0.3, 0.36, 0.2)
    col = n.mix(n.smooth(t, 0.0, 0.35), base, body)
    col = n.mix(n.m('MULTIPLY', n.smooth(n.noise(6.0, 3.0), 0.4, 0.7), 0.6), col, bloom)      # waxy bloom
    col = n.mix(n.m('MULTIPLY', n.smooth(t, 0.7, 0.98), 0.7), col, (0.42, 0.08, 0.13))    # wine-red tips
    col = n.mix(n.m('MULTIPLY', n.smooth(v, 0.8, 0.9), 0.5), col, (0.12, 0.13, 0.05))
    spk = n.smooth(n.noise(80.0, 2.0), 0.62, 0.66)
    col = n.mix(n.m('MULTIPLY', spk, 0.5), col, (0.3, 0.32, 0.28))
    n.out(col, n.m('ADD', 0.45, n.m('MULTIPLY', n.noise(20.0, 3.0), 0.2)), 0.0)
    n.bump(n.m('ADD', n.m('MULTIPLY', n.noise(25.0, 4.0), 0.4), spk), 0.25, 0.006, soft=False)


def _bark_shader(n):
    t = NA.attr(n, 'st')
    fis = n.noise(1.0, 6.0, co=n.vscale(n.co, (7.0, 7.0, 0.9)))
    fis2 = n.smooth(fis, 0.46, 0.58)
    weathered, dark = (0.32, 0.3, 0.27), (0.05, 0.04, 0.03)
    col = n.mix(n.smooth(n.noise(2.0, 4.0), 0.3, 0.7), (0.17, 0.15, 0.12), weathered)
    col = n.mix(n.m('MULTIPLY', n.m('SUBTRACT', 1.0, fis2), 0.7), col, dark)
    col = n.mix(n.m('MULTIPLY', n.smooth(t, 0.8, 1.0), 0.6), col, (0.34, 0.31, 0.26))      # bleached broken ends
    g = NA._geo(n)
    up = n.sep(g.outputs['Normal'])[2]
    lich = n.m('MULTIPLY', n.smooth(n.noise(9.0, 6.0), 0.6, 0.66), n.smooth(up, -0.2, 0.6))
    col = n.mix(n.m('MULTIPLY', lich, 0.9), col, (0.3, 0.33, 0.2))
    zz = n.sep(n.co)[2]
    col = n.mix(n.m('SUBTRACT', 1.0, n.smooth(zz, 0.0, 0.3)), col, NA.SOIL)
    n.out(col, 0.85, 0.0)
    n.bump(n.m('ADD', fis2, n.m('MULTIPLY', n.noise(40.0, 3.0), 0.15)), 1.0, 0.03, soft=False)


def _frond_shader(n):
    t = NA.attr(n, 'st')
    v = NA.attr(n, 'sv')
    stem, tipc = (0.06, 0.04, 0.08), (0.06, 0.13, 0.12)
    col = n.mix(n.smooth(t, 0.0, 1.0), stem, tipc)
    # bioluminescent bands along the stalk, denser and brighter towards the tip
    bands = n.m('FRACT', n.m('ADD', n.m('MULTIPLY', n.m('POWER', t, 0.7), 9.0), n.m('MULTIPLY', v, 3.0)))
    band = n.m('MULTIPLY', n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', bands, 0.5)), 0.42, 0.34), n.smooth(t, 0.35, 0.8))
    band = n.m('MULTIPLY', band, n.smooth(n.noise(4.0, 2.0), 0.35, 0.6))      # rings fade in and out
    spots = n.smooth(n.noise(30.0, 2.0), 0.66, 0.7)
    tipglow = n.smooth(t, 0.7, 1.0)
    glow = n.m('ADD', n.m('ADD', n.m('MULTIPLY', band, 0.7), n.m('MULTIPLY', spots, n.smooth(t, 0.2, 0.7))), n.m('MULTIPLY', tipglow, 0.6))
    e = (0.15, 0.85, 0.65)
    col = n.mix(n.m('MULTIPLY', glow, 0.5), col, (0.1, 0.35, 0.28))
    n.out(col, 0.35, 0.0, e, n.m('MULTIPLY', glow, 1.1))
    n.bump(n.m('MULTIPLY', band, -1.0), 0.3, 0.006, soft=False)


def _pod_shader(n):
    lw = n.nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.45
    core = n.m('SUBTRACT', 1.0, lw.outputs[1])
    vein = n.m('SUBTRACT', 1.0, n.smooth(n.voronoi(7.0, 'DISTANCE_TO_EDGE').outputs['Distance'], 0.0, 0.05))
    e = (0.18, 0.85, 0.62)
    col = n.mix(core, (0.04, 0.12, 0.11), (0.25, 0.7, 0.55))
    n.out(col, 0.25, 0.0, e, n.m('ADD', n.m('MULTIPLY', core, 0.9), n.m('MULTIPLY', vein, 0.35)))
    n.bump(vein, 0.3, 0.005, soft=False)


_veg_mat('grass2', _grass_shader)
_veg_mat('succulent', _succulent_shader)
_veg_mat('bark2', _bark_shader)
_veg_mat('frond2', _frond_shader)
_veg_mat('pod', _pod_shader)


@nasset('props/shrub.glb', 'Shrub', size=256)
def shrub():
    # A low alien succulent: thick blue-green leaves in three whorls, tips stained wine red, the outer
    # leaves splayed on the ground and curling up at the ends.
    rnd = random.Random(9)
    for ring, (count, pitch, ln, wd) in enumerate(((6, 72, 0.68, 0.085), (8, 44, 1.0, 0.12), (9, 16, 1.1, 0.13))):
        for k in range(count):
            a = math.radians(360.0 * k / count + rnd.uniform(-12, 12) + ring * 23)
            L = ln * rnd.uniform(0.8, 1.15)
            p = math.radians(pitch + rnd.uniform(-8, 8))
            curl = rnd.uniform(0.15, 0.35) * (1.0 if ring == 2 else 0.4)
            pts, wid = [], []
            for i in range(5):
                t = i / 4
                ang = p + curl * t * t * 1.2 - (0.25 * t if ring < 2 else 0.0)
                r = L * t * math.cos(ang) + 0.04
                z = 0.04 + L * t * math.sin(ang) * (1.0 if ring < 2 else 0.6) + (0.02 + 0.12 * t ** 2 * curl if ring == 2 else 0)
                pts.append((math.cos(a) * r, math.sin(a) * r, z))
                w = wd * (0.55 + 0.6 * math.sin(math.pi * min(t * 1.1, 1.0))) * (1 - t * 0.92)
                wid.append((max(w, 0.006), max(w * 0.42, 0.005)))
            NA.strand(pts, wid, 'succulent', sides=5, up=(0, 0, 1), sv=rnd.random(), caps=False)
    return dict(name='Shrub', ext=0.015)


@nasset('props/grass.glb', 'Grass tuft', size=256)
def grass():
    # A dense clump: short broad blades crowding the heart, longer ones arching out and drooping.
    rnd = random.Random(2)
    for k in range(40):
        a = math.radians(360.0 * k / 40 * 2.618 % 360 + rnd.uniform(-10, 10))
        inner = k % 3 != 0
        L = rnd.uniform(0.22, 0.42) if inner else rnd.uniform(0.4, 0.58)
        p = math.radians(rnd.uniform(62, 86) if inner else rnd.uniform(54, 74))
        droop = rnd.uniform(0.2, 0.6) if inner else rnd.uniform(0.35, 0.75)
        pts, wid = [], []
        r0 = rnd.uniform(0.0, 0.09)
        w0 = rnd.uniform(0.022, 0.034)
        for i in range(4):
            t = i / 3
            ang = p - droop * t * t
            r = r0 + L * t * math.cos(ang) * 1.15
            z = L * t * math.sin(ang)
            pts.append((math.cos(a) * r, math.sin(a) * r, z))
            wid.append(w0 * (1 - t * 0.8) + 0.002)
        NA.ribbon(pts, wid, 'grass2', fold=0.4, sv=rnd.random() * (0.7 if k % 7 else 1.0))
    return dict(name='Grass', ext=0.006, double=True)


@nasset('props/dead_tree.glb', 'Dead tree', size=256)
def dead_tree():
    # A wind-stripped snag: a twisting trunk forking low, two broken leaders, a few crooked limbs
    # and root flares gripping the ground.
    rnd = random.Random(6)
    def limb(p0, d, L, r0, r1, n, wob, sides, sv):
        pts, wid = [], []
        p = Vector(p0)
        dv = Vector(d).normalized()
        for i in range(n):
            t = i / (n - 1)
            pts.append(tuple(p))
            wid.append(r0 + (r1 - r0) * t)
            dv = (dv + Vector((rnd.uniform(-wob, wob), rnd.uniform(-wob, wob), rnd.uniform(-wob, wob) * 0.5))).normalized()
            p = p + dv * (L / (n - 1))
        NA.strand(pts, wid, 'bark2', sides=sides, sv=sv)
        return pts
    trunk = limb((0, 0, -0.08), (0.05, 0.02, 1), 1.15, 0.2, 0.135, 5, 0.12, 9, 0.1)
    top = Vector(trunk[-1])
    a = limb(tuple(top - Vector((0, 0, 0.3))), (0.34, 0.12, 1), 1.6, 0.125, 0.035, 6, 0.15, 7, 0.2)
    b = limb(tuple(top - Vector((0, 0, 0.25))), (-0.42, -0.08, 1), 1.15, 0.11, 0.05, 5, 0.12, 7, 0.3)   # snapped leader
    for (src, hh, yaw, ln, el) in ((a, 2, 40, 0.75, 0.45), (a, 3, 200, 0.5, 0.6), (a, 4, 300, 0.4, 0.7), (b, 2, 150, 0.7, 0.3),
                                    (b, 3, 250, 0.45, 0.5), (trunk, 3, 280, 0.65, 0.25), (trunk, 2, 100, 0.35, 0.1)):
        p0 = Vector(src[hh])
        ya = math.radians(yaw)
        tip = limb(tuple(p0), (math.cos(ya), math.sin(ya), el), ln, 0.045, 0.01, 4, 0.3, 5, 0.6)
        if ln > 0.5:
            limb(tip[2], (math.cos(ya + 0.9), math.sin(ya + 0.9), 0.7), 0.25, 0.018, 0.005, 3, 0.3, 4, 0.7)
    for k in range(5):   # root flares
        ya = math.radians(72 * k + rnd.uniform(-15, 15))
        L = rnd.uniform(0.45, 0.65)
        pts = [(math.cos(ya) * 0.05, math.sin(ya) * 0.05, 0.32), (math.cos(ya) * 0.2, math.sin(ya) * 0.2, 0.1),
               (math.cos(ya) * L * 0.65, math.sin(ya) * L * 0.65, 0.0), (math.cos(ya + 0.2) * L, math.sin(ya + 0.2) * L, -0.06)]
        NA.strand(pts, [(0.12, 0.08), (0.09, 0.06), (0.05, 0.035), (0.015, 0.012)], 'bark2', sides=6, sv=0.0)
    return dict(name='DeadTree', ext=0.02)


@nasset('props/tendril.glb', 'Glowing alien fronds', size=256)
def tendril():
    # Bioluminescent stalks rising from a dark knuckle of rock: tall ones arch out and end in glowing
    # seed pods, short ones are still coiled like fiddleheads.
    rnd = random.Random(12)
    NA.rock((0, 0, 0.1), (0.42, 0.38, 0.26), 'hostteal', seed=70, tris=160, cuts=6, chips=4, cracks=0.8, floor=-0.05)
    NA.rock((0.35, -0.3, 0.05), (0.18, 0.15, 0.12), 'hostteal', seed=71, tris=50, cuts=5, chips=2, cracks=0, floor=-0.05)
    for k in range(6):
        a = math.radians(360.0 * k / 6 + rnd.uniform(-15, 15))
        ln = rnd.uniform(1.05, 1.65)
        reach = rnd.uniform(0.45, 0.85)
        pts, wid = [], []
        for i in range(9):
            t = i / 8
            sway = math.sin(t * math.pi * 1.3) * 0.18
            r = reach * t ** 1.6 + 0.12
            pts.append((math.cos(a) * r - math.sin(a) * sway, math.sin(a) * r + math.cos(a) * sway, 0.12 + ln * (t ** 0.85) - reach * 0.25 * t ** 3))
            wid.append(0.055 * (1 - t) ** 0.8 + 0.016)
        NA.strand(pts, wid, 'frond2', sides=6, sv=rnd.random())
        tip = Vector(pts[-1])
        d = (Vector(pts[-1]) - Vector(pts[-2])).normalized()
        pod = NA._mesh('pod', *_pod_geo(tip + d * 0.07, d, 0.075, 0.13))
        NA.solid(pod, 'pod')
    for k in range(4):   # young coiled fronds
        a = math.radians(360.0 * k / 4 + 30 + rnd.uniform(-20, 20))
        pts, wid = [], []
        h = rnd.uniform(0.35, 0.55)
        for i in range(8):
            t = i / 7
            ang = t * math.pi * 1.6
            r = 0.15 + 0.12 * math.sin(ang) * t
            z = 0.12 + h * min(t * 1.4, 1.0) - 0.08 * max(0, t - 0.7) / 0.3
            pts.append((math.cos(a) * r, math.sin(a) * r, z))
            wid.append(0.03 * (1 - t) + 0.012)
        NA.strand(pts, wid, 'frond2', sides=5, sv=rnd.random())
    return dict(name='Tendril', ext=0.015)


def _pod_geo(c, d, r, h, seg=8, rings=5):
    """Teardrop seed pod along direction d."""
    d = Vector(d).normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    ax = d.cross(up).normalized()
    ay = d.cross(ax).normalized()
    verts = [tuple(c - d * h * 0.5)]
    for i in range(1, rings):
        t = i / rings
        rr = r * math.sin(math.pi * t) ** 0.8 * (1.0 - 0.35 * t)
        cc = c + d * (h * (t - 0.5))
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append(tuple(cc + (ax * math.cos(a) + ay * math.sin(a)) * rr))
    verts.append(tuple(c + d * h * 0.5))
    faces = []
    for k in range(seg):
        faces.append([0, 1 + (k + 1) % seg, 1 + k])
    for i in range(rings - 2):
        for k in range(seg):
            a0 = 1 + i * seg
            faces.append([a0 + k, a0 + (k + 1) % seg, a0 + seg + (k + 1) % seg, a0 + seg + k])
    last = len(verts) - 1
    a0 = 1 + (rings - 2) * seg
    for k in range(seg):
        faces.append([a0 + k, a0 + (k + 1) % seg, last])
    return verts, faces


# forge-built crystal helpers, kept for shard.py (the end-game Shard structure imports them).
def crystal(base, h, r, yaw, lean, zone, sides=6):
    """Faceted shard: a six-sided column with a slanted point, leaning out from its base."""
    a, l = math.radians(yaw), math.radians(lean)
    d = (math.cos(a) * math.sin(l), math.sin(a) * math.sin(l), math.cos(l))
    p0 = (base[0] - d[0] * 0.15, base[1] - d[1] * 0.15, base[2] - d[2] * 0.15)
    p1 = (base[0] + d[0] * h, base[1] + d[1] * h, base[2] + d[2] * h)
    o = tube(p0, p1, [(0, r * 0.8), (0.72, r), (0.86, r * 0.6), (1, r * 0.04)], sides, zone, sharp=15)
    return o


def cluster(c, n, h, r, zone, rnd, lean=28):
    crystal(c, h, r, rnd.uniform(0, 360), rnd.uniform(0, 8), zone)
    for k in range(n):
        yaw = 360.0 * k / n + rnd.uniform(-20, 20)
        a = math.radians(yaw)
        hh = h * rnd.uniform(0.4, 0.8)
        rr = r * rnd.uniform(0.5, 0.8)
        crystal((c[0] + math.cos(a) * r * 0.8, c[1] + math.sin(a) * r * 0.8, c[2]), hh, rr, yaw, lean + rnd.uniform(-10, 14), zone)


NA.MATS['gem_pink'] = lambda: NA.gem_mat('pink', (0.16, 0.004, 0.065), (0.8, 0.16, 0.45), (1.0, 0.08, 0.45), strength=1.7)
NA.MATS['gem_opal'] = lambda: NA.gem_mat('opal', (0.008, 0.025, 0.2), (0.18, 0.42, 0.95), (0.05, 0.32, 1.0), strength=2.2,
                                         opal=True, height=2.2)


def spray(rnd, c, n, h, r, zone, lean=(20, 40), broken=0.25, seed=0, centre=True):
    """A crystal cluster: one leader (optional) and n columns fanning out round it."""
    if centre:
        NA.crystal(c, h, r, rnd.uniform(0, 360), rnd.uniform(0, 8), zone, seed=seed)
    for k in range(n):
        yaw = 360.0 * k / n + rnd.uniform(-22, 22)
        a = math.radians(yaw)
        off = r * rnd.uniform(0.6, 1.1)
        NA.crystal((c[0] + math.cos(a) * off, c[1] + math.sin(a) * off, c[2]), h * rnd.uniform(0.35, 0.75),
                   r * rnd.uniform(0.45, 0.75), yaw, rnd.uniform(*lean), zone, seed=seed + k + 1,
                   broken=rnd.uniform(0.3, 1.0) if rnd.random() < broken else 0.0)


def shards(rnd, n, r0, r1, zone, size=(0.18, 0.42), seed=0):
    """Loose broken crystal pieces lying on the ground."""
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(r0, r1)
        h = rnd.uniform(*size)
        NA.crystal((math.cos(a) * d, math.sin(a) * d, 0.02), h, h * rnd.uniform(0.18, 0.3), rnd.uniform(0, 360),
                   rnd.uniform(62, 84), zone, sink=0.35, seed=seed + k, broken=rnd.uniform(0.2, 1.0) if rnd.random() < 0.5 else 0.0)


def host(rnd, zone, mound, plates, pr, seed):
    """Cracked host rock: a low mound and plates heaved up and tipped outward round it."""
    NA.rock((0, 0, mound[2] * 0.25), mound, zone, seed=seed, tris=520, cuts=7, chips=8, cracks=1.6, flat_top=0.5,
            crack_scale=1.3)
    for k in range(plates):
        a = 360.0 * k / plates + rnd.uniform(-18, 18)
        d = rnd.uniform(*pr)
        ar = math.radians(a)
        sz = (rnd.uniform(0.5, 0.8), rnd.uniform(0.35, 0.55), rnd.uniform(0.14, 0.22))
        NA.rock((math.cos(ar) * d, math.sin(ar) * d, 0.12), sz, zone, seed=seed + 1 + k, tris=130, cuts=6, chips=4,
                flat_top=0.6, yaw=a, tilt=(rnd.uniform(-8, 8), rnd.uniform(18, 34)), cracks=0.6)


@nasset('props/deposit_ore.glb', 'Ore site (pink crystal)')
def deposit_ore():
    rnd = random.Random(100)
    host(rnd, 'hostred', (1.55, 1.35, 0.6), 8, (1.35, 2.0), 300)
    spray(rnd, (0.15, 0.1, 0.35), 8, 3.3, 0.44, 'gem_pink', lean=(14, 42), seed=10, broken=0.35)
    for k in range(8):
        a = math.radians(360.0 * k / 8 + rnd.uniform(-18, 18))
        d = rnd.uniform(2.2, 3.9)
        c = (math.cos(a) * d, math.sin(a) * d)
        rs = rnd.uniform(0.32, 0.5)
        NA.rock((c[0], c[1], rs * 0.2), (rs, rs * 0.85, rs * 0.6), 'hostred', seed=320 + k, tris=110, cuts=6, chips=3,
                cracks=0.8)
        spray(rnd, (c[0], c[1], rs * 0.3), rnd.randint(2, 4), rnd.uniform(0.7, 1.35), rnd.uniform(0.15, 0.22), 'gem_pink',
              lean=(22, 44), seed=100 + k * 10)
    shards(rnd, 16, 1.4, 3.9, 'gem_pink', seed=400)
    pebbles(rnd, 14, (0, 0), 1.8, 3.8, 0.08, 0.18, 'hostred', 500)
    return dict(name='OreDeposit_pink')


@nasset('props/deposit_metal.glb', 'Metal site (blue opal)')
def deposit_metal():
    rnd = random.Random(200)
    host(rnd, 'hostdark', (1.3, 1.15, 0.5), 7, (1.15, 1.7), 600)
    # a big opal nodule breaking out of the host, crystals crowding round it
    NA.rock((0.0, 0.05, 0.75), (0.85, 0.72, 1.05), 'gem_opal', seed=610, tris=420, cuts=5, chips=0, cracks=0, grain=0.0,
            round_=0.18, lumpy=0.12, yaw=20, tilt=(8, -6), gem=True, floor=0.0)
    NA.crystal((-0.35, 0.45, 0.3), 3.1, 0.34, 120, 12, 'gem_opal', seed=19)
    spray(rnd, (0.15, 0.1, 0.3), 7, 3.0, 0.36, 'gem_opal', lean=(26, 46), seed=20, centre=False, broken=0.3)
    for k in range(6):
        a = math.radians(360.0 * k / 6 + rnd.uniform(-20, 20))
        d = rnd.uniform(1.9, 2.8)
        c = (math.cos(a) * d, math.sin(a) * d)
        rs = rnd.uniform(0.3, 0.45)
        NA.rock((c[0], c[1], rs * 0.2), (rs, rs * 0.85, rs * 0.6), 'hostdark', seed=620 + k, tris=110, cuts=6, chips=3,
                cracks=0.8)
        if k % 2 == 0:
            NA.rock((c[0] * 0.92, c[1] * 0.92, rs * 0.5), (rs * 0.6, rs * 0.5, rs * 0.7), 'gem_opal', seed=640 + k, tris=90,
                    cuts=3, chips=0, cracks=0, grain=0.0, round_=0.2, gem=True, floor=0.0)
        spray(rnd, (c[0], c[1], rs * 0.3), rnd.randint(2, 4), rnd.uniform(0.6, 1.2), rnd.uniform(0.13, 0.2), 'gem_opal',
              lean=(22, 44), seed=200 + k * 10)
    shards(rnd, 10, 1.2, 2.9, 'gem_opal', seed=700)
    pebbles(rnd, 10, (0, 0), 1.6, 2.7, 0.07, 0.16, 'hostdark', 800)
    return dict(name='OreDeposit_opal')
