"""Arcadian fleet for the pre-rendered cinematics ("rule of cool" pass, cinematics only).

Everything here is far more gold than the game's silver shells: the builders run inside
gold_palette(), which swaps the Arcadian ('kesh') forge zones for gold ones while a ship is built and
puts the game's values back afterwards (forge.py itself is untouched). Front is +X, up is +Z.

    crescent_mothership_v2()  bow-shaped horseshoe with a lance hull cutting through it, the core in
                              the mouth, a lightning "bowstring" from the horn tips to the lance tip.
    shell_mothership_v2()     the coiled shell uncoiled into a scythe: a long ram prow coming out of
                              the shell mouth, an open coil with a crest of blades, core in the hub.
    lens_mothership_v2()      ships_hd.kesh_mothership in gold plus mandible blades, a broken halo
                              ring, a hanging keel citadel with a second core, and lightning.
    squid_ship(pose=...)      armoured mantle with 10 floating segmented tentacles (see below).
    arcadian_corvette()       ~15 long: crescent hammerhead prow, slender neck, exposed core, engines.
    stingray_fighter()        ~1.5 long ray-shaped fighter with a segmented whip tail.

Each returns (ship, core_point_or_None) and sets ship['shapes'].

Squid tentacles are posable: tentacle_joints(pose, n, segs, targets) returns one list of joint
points per tentacle (ship-local), build_tentacle(joints, name) turns one list into an object, and
squid_ship(pose=..., joints=..., targets=...) builds body + tentacles. The tentacles are separate
objects parented to the body (names in ship['tentacles'], joint lists in ship['joints']), so an
animation can delete and rebuild them per frame from new joint lists.
"""
import contextlib
import functools
import math
import os
import random
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'art', 'v2'))
import forge as F  # noqa: E402
import ships as base  # noqa: E402
import arcadian_designs as D  # noqa: E402

GOLDGLOW = (1.0, 0.36, 0.03)
GOLD_ZONES = {
    # the three hull zones the older helpers use, re-tuned to gold
    'shell': dict(kind='etched', base=(0.9, 0.5, 0.11), base2=(0.66, 0.32, 0.06), rough=0.3, veins=0.3),
    'bronze': dict(kind='etched', base=(0.6, 0.29, 0.07), base2=(0.36, 0.15, 0.04), rough=0.3, veins=0.35),
    'under': dict(kind='etched', base=(0.2, 0.11, 0.04), base2=(0.09, 0.045, 0.02), rough=0.4, veins=0.3),
    'barrel': dict(kind='etched', base=(1.0, 0.8, 0.45), base2=(0.85, 0.55, 0.2), rough=0.2, veins=0.0, fine=True),
    # new zones
    'pale': dict(kind='etched', base=(1.0, 0.74, 0.36), base2=(0.88, 0.55, 0.2), rough=0.22, veins=0.15),
    'slat': dict(kind='ribs', emit=GOLDGLOW, strength=2.6, freq=6.0),
    'glow': dict(kind='glow', emit=GOLDGLOW, strength=3.5),
    'core': dict(kind='orb', emit=(1.0, 0.3, 0.02), strength=1.35),
    'arc': dict(kind='glow', emit=(1.0, 0.45, 0.06), strength=8.0),      # energy threads / bridges
    'bolt': dict(kind='glow', emit=(1.0, 0.62, 0.16), strength=30.0),    # lightning
}


@contextlib.contextmanager
def gold_palette():
    saved = dict(F.ZONES['kesh'])
    F.ZONES['kesh'].update(GOLD_ZONES)
    try:
        yield
    finally:
        F.ZONES['kesh'].clear()
        F.ZONES['kesh'].update(saved)


def _gold(fn):
    @functools.wraps(fn)
    def wrap(*a, **kw):
        with gold_palette():
            return fn(*a, **kw)
    return wrap


def tri_count(obj):
    n = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    return n + sum(tri_count(c) for c in obj.children if c.type == 'MESH')


# ------------------------------------------------------------------ shared helpers
def _perp(v, rnd):
    v = Vector(v).normalized()
    while True:
        r = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        p = r - v * r.dot(v)
        if p.length > 0.2:
            return p.normalized()


BOLT_SCALE = 0.55      # global thickness of lightning (the 2D bloom widens it again)


def bolt(p0, p1, rnd, width=0.14, jag=0.2, depth=5, branches=2, zone='bolt'):
    """Static lightning: a jagged emissive tube from p0 to p1 (midpoint displacement) with forks."""
    pts = [Vector(p0), Vector(p1)]
    for _ in range(depth):
        new = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            d = b - a
            mid = (a + b) / 2 + _perp(d, rnd) * d.length * jag * rnd.uniform(0.3, 1.0) if d.length > 1e-6 else a
            new += [mid, b]
        pts = new
    n = len(pts)
    F.sweep([tuple(p) for p in pts], [(width * BOLT_SCALE * (1.0 - 0.55 * k / (n - 1)),) * 2 for k in range(n)], zone,
            sides=4)
    total = (Vector(p1) - Vector(p0)).length
    for _ in range(branches):
        i = rnd.randrange(n // 5, max(n // 5 + 1, n * 4 // 5))
        d = (pts[min(i + 2, n - 1)] - pts[max(i - 2, 0)]).normalized()
        end = pts[i] + (d + _perp(d, rnd) * rnd.uniform(0.5, 1.1)).normalized() * total * rnd.uniform(0.18, 0.4)
        bolt(pts[i], end, rnd, width * 0.55, jag, max(2, depth - 2), max(0, branches - 2), zone)
    return pts


def smooth_pts(pts, n=8):
    """Catmull-Rom through control points, n samples per span."""
    P = [Vector(p) for p in pts]
    P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        for k in range(n):
            t = k / n
            a, b, c, d = P[i - 1], P[i], P[i + 1], P[i + 2]
            out.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                              + (-a + 3 * b - 3 * c + d) * t ** 3))
    out.append(P[-2])
    return out


def thread(pts, w, zone='arc', n=24):
    """Smooth energy thread through control points."""
    out = smooth_pts(pts, n)
    F.sweep([tuple(p) for p in out], [(w, w)] * len(out), zone, sides=5)
    return out


def blade(root, out, back, h, chord, thick, zone, lean=0.6, n=9, curve=1.8, tipk=0.04):
    """Curved fin blade: rises from root along `out`, sweeping toward `back`. chord lies in the
    out/back plane, thick across it."""
    root, out, back = Vector(root), Vector(out).normalized(), Vector(back).normalized()
    up = out.cross(back)
    if up.length < 1e-6:
        up = out.orthogonal()
    pts, sect = [], []
    for k in range(n):
        s = k / (n - 1)
        pts.append(tuple(root + out * (h * s) + back * (h * lean * s ** curve)))
        w = (1 - s) ** 0.75 * (0.6 + 0.4 * math.sin(math.pi * min(1.0, s * 1.6 + 0.2)))
        sect.append((chord * max(tipk, w), thick * max(tipk, (1 - s) ** 0.6)))
    return F.sweep(pts, sect, zone, sides=6, up=tuple(up.normalized()), power=0.7)


def oriented_ring(c, axis, r, width, thick, zone, n=32, gaps=0):
    """Ring round centre c whose plane is perpendicular to `axis`."""
    q = Vector(axis).normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
    if gaps:
        step = 360 / gaps
        objs = [F.crescent((0, 0, 0), r, k * step + 7, (k + 1) * step - 7, width, thick, zone,
                           n=max(8, n // gaps), tip=0.35) for k in range(gaps)]
    else:
        objs = [F.crescent((0, 0, 0), r, 0, 359, width, thick, zone, n=n, tip=1.0)]
    for o in objs:
        F.xf(o, q)
        F.move(o, tuple(c))
    return objs


def gyro_core(c, r, rings=3, halo=True):
    """Core orb in floating gyroscope rings with a bright equator band."""
    c = Vector(c)
    F.orb(tuple(c), r, 'core', seg=(32, 20))
    tilts = [(70, 0, 0), (25, 35, 20), (0, 60, 70), (90, 0, 45)]
    for k in range(rings):
        D.ring(tuple(c), r * (1.32 + 0.24 * k), ('pale', 'bronze', 'shell', 'bronze')[k % 4], tilt=tilts[k % 4],
               gaps=3 if k == 1 else 0, width=r * (0.09 + 0.02 * k), thick=r * 0.07)
    if halo:
        D.ring(tuple(c), r * 1.12, 'arc', tilt=(8, 0, 0), width=r * 0.035, thick=r * 0.035)
    return c


def _join_into(ship, parts):
    """Join extra forge parts into an already joined ship."""
    for o in parts:
        o.data.materials.clear()
        o.data.materials.append(F.zone_mat(o['zone']))
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    ship.select_set(True)
    bpy.context.view_layer.objects.active = ship
    bpy.ops.object.join()
    F.ST['parts'] = []
    return ship


# ================================================================== 1: crescent mothership v2
@_gold
def crescent_mothership_v2(name='CrescentMothershipV2'):
    rnd = random.Random(31)
    base._faction('kesh')
    m = F.mark()
    R = 17.0
    a0, a1 = math.radians(36), math.radians(324)    # open toward +X

    def path(u):
        a = a0 + (a1 - a0) * u
        return Vector((R * math.cos(a) * 1.12, R * math.sin(a), 0.0))

    def radius(u):
        return 0.35 + 5.2 * math.sin(math.pi * u) ** 0.9   # thick at the back, horns taper to points

    fn = D.tubefn(path, radius, sq=(1.0, 0.6))
    F.body(fn, 'under', nu=64, nv=24)
    D.plates(fn, 72, 0.015, 0.985, 15, 165, lambda u: int(radius(u) * 2.1) + 3,
             lambda i, j: 'bronze' if i % 9 == 4 else ('pale' if (i * 7 + j * 3) % 11 == 0 else 'shell'),
             thick=0.1, off=0.12, lift=0.08)
    D.plates(fn, 40, 0.04, 0.96, 195, 345, lambda u: int(radius(u) * 1.2) + 2,
             lambda i, j: rnd.choice(('bronze', 'under', 'bronze')), thick=0.12, off=0.12, lift=0.06)
    for k, v in enumerate([35, 90, 145, 180, 270]):               # bright energy seams along the arc
        pts = [tuple(fn(0.02 + 0.96 * t / 70, v, 0.3)) for t in range(71)]
        F.sweep(pts, [(0.07, 0.07)] * 71, 'arc' if k in (1, 3) else 'glow', sides=4)
    for u in (0.3, 0.4, 0.6, 0.7):                                # hangar maws on the inner face
        p = fn(u, 180, 0.2)
        F.orb(tuple(p), 1.1, 'glow', seg=(12, 8), sq=(1.0, 1.0, 0.45))
        oriented_ring(p, p - path(u), 1.5, 0.3, 0.3, 'bronze', n=20)
    for k in range(56):                                           # rim studs
        u = 0.03 + 0.94 * k / 55
        F.orb(tuple(fn(u, 0, 0.3)), 0.24, 'glow' if k % 3 == 0 else 'pale', seg=(6, 4), sq=(1, 1, 0.5))

    # --- crest: big floating fins (as in option A) with smaller blades between them
    tips = []
    big = {0.1: 5.5, 0.26: 7.5, 0.42: 9.5, 0.58: 9.5, 0.74: 7.5, 0.9: 5.5}
    for k in range(27):
        u = 0.06 + 0.88 * k / 26
        t = (path(u + 0.01) - path(u - 0.01)).normalized()
        outw = (path(u) - Vector((0, 0, 0))).normalized()
        key = min(big, key=lambda b: abs(b - u))
        is_big = abs(key - u) < 0.017
        h = big[key] if is_big else 1.2 + radius(u) * 0.35
        root = fn(u, 90, 1.3 if is_big else 0.25)
        back = (-outw * 0.2 + (t if u < 0.5 else -t)).normalized()   # sweep away from the horns
        blade(root, Vector((0, 0, 1)) + outw * 0.15, back, h, h * 0.36, 0.3 if is_big else 0.16,
              'pale' if is_big else 'shell', lean=0.55)
        if is_big:
            tips.append(root + (Vector((0, 0, 1)) + outw * 0.15).normalized() * h + back * h * 0.55)
            F.orb(tuple(root - Vector((0, 0, 0.55))), 0.3, 'arc', seg=(8, 6))
    for a, b in zip(tips, tips[1:]):                              # chain lightning across the fin tips
        bolt(a, b, rnd, width=0.11, jag=0.16, depth=5, branches=1)
    for tp, u in zip(tips, sorted(big)):
        bolt(tp, fn(u, 90, 0.3), rnd, width=0.07, jag=0.22, depth=4, branches=0)

    # --- the lance: a long blade hull cutting through the crescent from stern to mouth
    lance = F.lensfn(-33, 6.5, 2.3, 2.9, -2.3, 0.0, nose=0.8, tail=0.8)
    F.body(lance, 'under', nu=30, nv=18)
    D.plates(lance, 34, 0.03, 0.97, 0, 360, lambda u: 9, lambda i, j: 'bronze' if i % 5 == 2 else 'shell',
             thick=0.1, off=0.1, lift=0.08)
    D.seams(lance, [90, 0, 180], 0.04, 0.96, 0.25, n=40, w=0.08)
    for x, h in [(-27, 3.2), (-22.5, 4.6), (-12, 5.5), (-6, 4.2), (-0.5, 3.0)]:
        u = (6.5 - x) / 39.5
        blade(lance(u, 90, 0.4), (0, 0, 1), (-1, 0, 0), h, h * 0.42, 0.28, 'pale', lean=0.7)
        blade(lance(u, 270, 0.4), (0, 0, -1), (-1, 0, 0), h * 0.6, h * 0.3, 0.24, 'bronze', lean=0.7)
    F.orb((-33.6, 0, 0), 0.9, 'arc', seg=(12, 8), sq=(1.6, 1, 1))  # stern drive glow
    oriented_ring((-32.2, 0, 0), (1, 0, 0), 1.9, 0.35, 0.3, 'bronze', gaps=4)

    # --- core in the mouth, on the lance's line
    c = Vector((R * 1.12 * 0.72, 0, 0))
    gyro_core(c, 3.5, rings=3)
    for a in range(0, 360, 30):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        F.orb((c.x + ca * 7.4, c.y + sa * 7.4, c.z + math.sin(math.radians(a * 3)) * 1.2), 0.5, 'pale',
              seg=(10, 6), sq=(1.3, 1.0, 0.35))

    # (David 2026-11-13: no long pointed lance ahead of the core; the core is the bow weapon)
    tip = c + Vector((4.2, 0, 0))

    # --- the bowstring: energy threads + lightning from each horn tip to the lance tip, and
    #     heavy arcs from the horn tips into the core
    for s, u in ((1, 0.0), (-1, 1.0)):
        horn = path(u) + (path(u) - path(abs(u - 0.02))).normalized() * 0.4
        F.orb(tuple(horn), 0.55, 'bolt', seg=(10, 6))
        ring_pt = c + Vector((0.6, s * 4.9, 0.4))
        bolt(horn, ring_pt, rnd, width=0.26, jag=0.2, depth=5, branches=3)
        bolt(fn(abs(u - 0.2), 180, 0.3), c + Vector((-4.6, s * 1.5, 0.5)), rnd, width=0.12, jag=0.2, depth=5,
             branches=2)
    D.hanging_spires(rnd, [tuple(fn(u, 270, 0.0)) for u in (0.2, 0.35, 0.5, 0.65, 0.8)])
    ship = D._finish(m, name)
    ship['lance_tip'] = tuple(tip)
    return ship, c


# ================================================================== 2: shell mothership v2
@_gold
def shell_mothership_v2(name='ShellMothershipV2'):
    rnd = random.Random(32)
    base._faction('kesh')
    m = F.mark()
    C = Vector((-9, 0, 4.5))            # hub of the coil
    UP = 0.36                           # u < UP: prow (tip at u = 0); u >= UP: the open coil
    T, K, R0, SX = 0.75, 0.17, 13.0, 1.3   # under one turn, stretched along X: a hook, not a coil
    P0, P1, P2 = Vector((36, 0, -3.5)), Vector((12, 0, -9.3)), Vector((C.x, 0, C.z - R0))

    def path(u):
        if u < UP:
            t = u / UP
            return P0 * (1 - t) ** 2 + P1 * (2 * t * (1 - t)) + P2 * t * t
        s = (u - UP) / (1 - UP)
        th = -math.pi / 2 - s * T * 2 * math.pi
        r = R0 * math.exp(-K * s * T * 2 * math.pi)
        return C + Vector((r * math.cos(th) * SX, 0, r * math.sin(th)))

    def radius(u):
        if u < UP:
            return 0.12 + 3.5 * (u / UP) ** 0.85
        s = (u - UP) / (1 - UP)
        return 0.9 + 4.2 * (1 - s) ** 1.25 + 0.9 * math.sin(math.pi * min(1.0, s * 3.2))

    def frame(u):
        e = 2e-3
        t = (path(min(1.0, u + e)) - path(max(0.0, u - e))).normalized()
        return t, Vector((-t.z, 0, t.x))

    def fn(u, v, off=0.0):   # v: 0 = outer keel of the coil (belly of the prow), 90 = +Y, 180 = inner
        u = min(1.0, max(0.0, u))
        t, n = frame(u)
        r = radius(u) + off
        a = math.radians(v)
        return path(u) + n * (math.cos(a) * r) + Vector((0, 1, 0)) * (math.sin(a) * r * 0.72)

    F.body(fn, 'under', nu=110, nv=24)
    # --- prow: long lance plates
    D.plates(fn, 20, 0.015, UP - 0.01, 0, 360, lambda u: max(5, int(radius(u) * 2.2) + 2),
             lambda i, j: 'pale' if (j % 4 == 0) else ('bronze' if i % 4 == 3 else 'shell'),
             thick=0.12, off=0.1, lift=0.1, nu=4)
    # --- coil: big irregular chamber plates (sizes vary so the coil is not evenly segmented)
    u = UP + 0.005
    i = 0
    while u < 0.985:
        du = rnd.choice((0.014, 0.02, 0.028, 0.036)) * (0.55 + 0.45 * (1 - (u - UP) / (1 - UP)))
        n = max(5, int(radius(u) * rnd.choice((1.3, 1.8, 2.4))))
        for j in range(n):
            vc = 360 * (j + 0.5 * (i % 2)) / n
            zone = 'bronze' if (i % 5 == 3 or abs(((vc + 180) % 360) - 180) > 150) else \
                ('pale' if (i + j) % 6 == 0 else 'shell')
            F.shell(fn, u, min(1.0, u + du * 1.5), vc, 360 / n * 1.1, zone, nu=4, nv=3, thick=0.16,
                    off=0.1 + 0.03 * (j % 2), lift=0.16, shape=0.4, front=0.5, back=0.2)
        u += du
        i += 1
    for k, v in enumerate([45, 315, 90, 270]):                   # energy seams nose to coil tip
        pts = [tuple(fn(0.02 + 0.97 * t / 110, v, 0.42)) for t in range(111)]
        F.sweep(pts, [(0.07, 0.07)] * 111, 'arc' if k >= 2 else 'glow', sides=4)
    for uu in (UP + 0.16, UP + 0.36, UP + 0.52):                 # a few glowing rib rings
        t, n = frame(uu)
        o = F.crescent((0, 0, 0), radius(uu) + 0.45, 0, 359, 0.2, 0.2, 'glow', n=28, tip=1.0)
        F.scale(o, (0.72, 1, 1))
        q = t.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        # crescent ring lies in XY: X -> coil normal, Y -> ship Y after tracking Z along the tangent
        F.xf(o, q)
        F.move(o, tuple(path(uu)))

    # --- the shell mouth: flared bronze lip the prow comes out of, glowing throat
    t, n = frame(UP)
    for k, (du, rr, zone, w) in enumerate([(0.0, 5.6, 'bronze', 0.9), (-0.012, 5.0, 'glow', 0.25),
                                           (0.014, 5.9, 'pale', 0.5)]):
        o = F.crescent((0, 0, 0), rr, 0, 359, w, w * 0.8, zone, n=36, tip=1.0)
        F.scale(o, (0.72, 1, 1))
        F.xf(o, frame(UP + du)[0].to_track_quat('Z', 'Y').to_matrix().to_4x4())
        F.move(o, tuple(path(UP + du)))
    for k in range(10):          # fangs round the mouth, pointing forward along the prow
        a = 360 * k / 10 + 18
        root = fn(UP + 0.004, a, 0.9)
        outw = (root - path(UP + 0.004)).normalized()
        blade(root, -t + outw * 0.25, outw, 4.2 if k % 2 else 6.0, 1.3, 0.35, 'pale', lean=-0.12)

    # --- crest: twin rows of swept blades along the outer keel of the coil, a keel blade under the prow
    tips = []
    N = 19
    for k in range(N):
        uu = UP + 0.03 + 0.6 * (k / (N - 1)) ** 0.9
        t, n = frame(uu)
        s = (uu - UP) / (1 - UP)
        h = (3.2 + 5.5 * math.sin(math.pi * min(1.0, s * 1.5 + 0.12)) ** 1.5) * (1.0 if k % 2 == 0 else 0.6)
        for side in (-1, 1):
            if k % 2 and side < 0:
                continue
            v = side * (16 if k % 2 == 0 else 0)
            root = fn(uu, v, 0.1)
            outw = (root - path(uu)).normalized()
            blade(root, outw, -t, h, h * 0.4, 0.3, 'pale' if k % 2 == 0 else 'bronze', lean=0.75)
            if k % 4 == 0 and side > 0:
                tips.append(root + outw * h - t * h * 0.75)
    for a, b in zip(tips, tips[1:]):
        bolt(a, b, rnd, width=0.12, jag=0.15, depth=5, branches=1)
    for k in range(9):           # dorsal spines along the top of the prow
        uu = 0.07 + (UP - 0.1) * k / 8
        t, n = frame(uu)
        h = 1.0 + radius(uu) * 0.7
        blade(fn(uu, 180, 0.1), -n, t, h, h * 0.5, 0.2, 'pale', lean=0.8)
    for uu, h in ((0.2, 4.5), (0.29, 6.5)):                       # ventral keel blades
        t, n = frame(uu)
        blade(fn(uu, 0, 0.1), n, t, h, h * 0.5, 0.3, 'bronze', lean=0.9)

    # --- asymmetric wings: one great floating scythe to port, three staggered blades to starboard
    blade((-13, 6.2, -5), (0.15, 1, 0.25), (-1, 0, 0.1), 21, 6.5, 0.6, 'shell', lean=0.75, n=16)
    blade((-11.5, 7.2, -5.6), (0.15, 1, 0.18), (-1, 0, 0.1), 13, 3.2, 0.4, 'bronze', lean=0.8, n=12)
    for k, (x, h) in enumerate([(-2, 11.0), (-9, 8.5), (-15, 6.0)]):
        blade((x, -5.6 - 0.3 * k, -6 + 2.2 * k), (0.1, -1, 0.3 - 0.1 * k), (-1, 0, 0.15), h, h * 0.33, 0.4,
              'pale' if k == 0 else 'shell', lean=0.8, n=12)
        F.orb((x, -5.0 - 0.3 * k, -6 + 2.2 * k), 0.45, 'arc', seg=(8, 6))
    thread([(-13, 5.6, -5), (-15, 13, -3), (-21, 22, -0.5)], 0.09, 'arc', n=8)

    # --- the coil ends in a sting hanging over the prow
    te = path(1.0)
    tt, tn = frame(0.995)
    blade(te - tt * 0.3, tt, tn, 7.5, 1.1, 0.6, 'pale', lean=0.22, n=10)
    blade(te - tt * 0.6, tt - tn * 0.5, -tn, 3.6, 1.2, 0.4, 'bronze', lean=0.3, n=8)
    sting = te + tt * 7.5 + tn * 1.65
    F.orb(tuple(sting), 0.4, 'bolt', seg=(8, 6))
    bolt(sting, fn(0.2, 180, 0.2), rnd, width=0.2, jag=0.16, depth=6, branches=3)
    bolt(sting, fn(0.3, 180, 0.2), rnd, width=0.12, jag=0.2, depth=5, branches=2)
    # --- core floating in the hub of the coil, lightning into the whorls
    gyro_core(C, 2.6, rings=3)
    bolt(C + Vector((2.7, 0, 0.5)), te + tn * 0.5, rnd, width=0.16, jag=0.2, depth=5, branches=2)
    for a in (85, 150, 215, 270):
        th = math.radians(a)
        # nearest shell surface in that direction: march outward from the hub until inside the tube
        d = Vector((math.cos(th), 0, math.sin(th)))
        hit = None
        for k in range(1, 60):
            p = C + d * (3.0 + 0.25 * k)
            if min((p - path(UP + (1 - UP) * q / 80)).length - radius(UP + (1 - UP) * q / 80) for q in range(81)) < 0.2:
                hit = p
                break
        if hit is not None:
            for sy in (-1, 1):
                bolt(C + d * 3.0 + Vector((0, sy * 0.8, 0)), hit + Vector((0, sy * rnd.uniform(0.3, 2.0), 0)), rnd,
                     width=0.13, jag=0.24, depth=4, branches=2)
    # --- floating ram shards ahead of the prow tip, linked by an energy thread and lightning
    d = (P0 - P1).normalized()
    prev = path(0.0)
    for k in range(3):
        a = P0 + d * (1.6 + 4.6 * k)
        L = 3.6 - 0.7 * k
        o = F.tube(tuple(a), tuple(a + d * L), [(0, 0.05), (0.3, 0.6 - 0.12 * k), (1, 0.02)], 6, 'pale')
        F.orb(tuple(a - d * 0.5), 0.26, 'bolt', seg=(8, 6))
        bolt(prev, a + d * L * 0.3, rnd, width=0.07, jag=0.3, depth=3, branches=0)
        prev = a + d * L * 0.5
    thread([path(0.01), P0 + d * 14.5], 0.07, 'arc', n=6)
    tip = P0 + d * 14.5
    F.orb(tuple(tip), 0.4, 'bolt', seg=(8, 6))
    D.hanging_spires(rnd, [tuple(fn(uu, 0, 0.0)) for uu in (0.33, 0.4, 0.44)])
    ship = D._finish(m, name)
    ship['prow_tip'] = tuple(tip)
    return ship, C


# ================================================================== 3: lens mothership v2
@_gold
def lens_mothership_v2(name='LensMothershipV2'):
    import ships_hd as HD
    rnd = random.Random(33)
    ship, core = HD.kesh_mothership(name)        # built with the gold palette (calls base._faction)
    shapes = ship['shapes']
    bays = [tuple(b) for b in ship['bays']]
    m = F.mark()
    core = Vector(core)
    lens = F.lensfn(-20, 24, 13, 4.5, -3.5, 0.0, nose=0.7, tail=0.8)

    # --- mandibles: two great floating scythe blades sweeping forward past the nose, in two tiers
    mand_tips = []
    for s in (-1, 1):
        for k, (r, a_0, a_1, w, z, zone) in enumerate([(23.5, 28, 88, 2.5, 0.3, 'shell'),
                                                       (26.5, 40, 86, 1.9, -1.4, 'bronze'),
                                                       (21.2, 50, 84, 1.3, 1.7, 'pale')]):
            o = F.crescent((3, 0, z), r, a_0, a_1, w, 0.55, zone, n=30, sq=(1.3, 0.92))
            if s < 0:
                F.xf(o, F.Matrix.Diagonal((1, -1, 1, 1)))
            for q in range(a_0 + 6, a_1 - 4, 4):             # etched rib studs along each blade
                a = math.radians(q)
                F.orb((3 + r * 1.3 * math.cos(a), s * r * 0.92 * math.sin(a), z + 0.3), 0.2 - 0.03 * k,
                      'glow' if q % 12 == 0 else 'pale', seg=(6, 4), sq=(1, 1, 0.45))
            if k == 0:
                a = math.radians(a_0)
                mand_tips.append(Vector((3 + r * 1.3 * math.cos(a), s * r * 0.92 * math.sin(a), z)))
                pts = [(3 + (r + 0.2) * 1.3 * math.cos(math.radians(q)), s * (r + 0.2) * 0.92 * math.sin(math.radians(q)),
                        z + 0.33) for q in range(a_0 + 8, a_1 - 8, 3)]
                F.sweep(pts, [(0.12, 0.12)] * len(pts), 'arc', sides=4)
        for q in (50, 62, 74, 84):            # tethers: hull rim -> mandible, as light
            a = math.radians(q)
            p = Vector((3 + 21.6 * 1.3 * math.cos(a), s * 21.6 * 0.92 * math.sin(a), 0.3))
            h = lens(0.5 - (p.x - 2) / 44, 0 if s > 0 else 180, 0.6)
            if q in (50, 74):
                bolt(h, p, rnd, width=0.07, jag=0.16, depth=4, branches=1)

    # --- halo: a broken vertical ring standing round the hull behind the core
    hx, hr = -3.0, 21.0
    segs = []
    for k in range(6):
        a_0, a_1 = k * 60 + 9 - 90, (k + 1) * 60 - 9 - 90
        F.crescent((hx, 0, 0), hr, a_0, a_1, 1.5, 0.7, 'shell' if k % 2 else 'pale', n=18, plane='yz',
                   sq=(1.0, 0.86), tip=0.75)
        for q in range(int(a_0) + 5, int(a_1) - 3, 5):       # studs along the halo band
            F.orb((hx + 0.42, hr * math.cos(math.radians(q)), hr * 0.86 * math.sin(math.radians(q))), 0.2,
                  'glow' if q % 10 == 0 else 'bronze', seg=(6, 4), sq=(0.5, 1, 1))
        F.crescent((hx - 0.5, 0, 0), hr + 1.7, a_0 + 6, a_1 - 6, 0.8, 0.5, 'bronze', n=12, plane='yz',
                   sq=(1.0, 0.86), tip=0.2)
        pts = F.arc_pts((hx + 0.48, 0, 0), hr - 0.2, a_0 + 5, a_1 - 5, 14, 'yz', (1.0, 0.86))
        F.sweep(pts, [(0.13, 0.13)] * 14, 'arc', sides=4)
        e0 = Vector((hx, hr * math.cos(math.radians(a_0)), hr * 0.86 * math.sin(math.radians(a_0))))
        e1 = Vector((hx, hr * math.cos(math.radians(a_1)), hr * 0.86 * math.sin(math.radians(a_1))))
        segs.append((e0, e1))
    for k in (0, 1, 3, 4):                   # lightning jumping the side gaps of the halo
        bolt(segs[k][1], segs[(k + 1) % 6][0], rnd, width=0.18, jag=0.22, depth=4, branches=1)

    # --- crown: tall floating blades round the core, a spike above it, lightning core -> halo
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        d = Vector((math.cos(a), math.sin(a), 0))
        h = 9.0 if k % 2 == 0 else 6.0
        blade(core + d * 6.9 + Vector((0, 0, -2.0)), Vector((0, 0, 1)) - d * 0.1, -d, h, 1.9, 0.4,
              'pale' if k % 2 == 0 else 'shell', lean=0.3, curve=2.6)
    F.tube(tuple(core + Vector((0, 0, 5.2))), tuple(core + Vector((0, 0, 14.5))), [(0, 0.05), (0.18, 0.75), (1, 0.03)],
           8, 'pale')
    D.ring(tuple(core + Vector((0, 0, 6.6))), 1.9, 'bronze', gaps=4, width=0.5, thick=0.3)
    D.ring(tuple(core), 3.75, 'arc', width=0.16, thick=0.16)
    top = core + Vector((0, 0, 14.5))
    F.orb(tuple(top), 0.45, 'bolt', seg=(8, 6))
    for e in (segs[2][1], segs[3][0]):       # spike tip -> the upper halo arcs
        bolt(top, e, rnd, width=0.17, jag=0.14, depth=6, branches=3)
    for k in range(5):
        a = math.radians(k * 72 + 20)
        d = Vector((math.cos(a), math.sin(a), 0))
        bolt(core + d * 3.5 + Vector((0, 0, 1)), core + d * 7.2 + Vector((0, 0, 4.0 + rnd.uniform(0, 2))), rnd,
             width=0.09, jag=0.25, depth=4, branches=1)

    # --- keel citadel: a hanging inverted spire city under the belly with a second core at its tip
    kc = Vector((2, 0, -3.2))
    F.lathe([(0.0, -15.5), (0.5, -13.5), (1.3, -9.0), (2.4, -5.0), (4.2, -2.2), (6.2, -0.4), (6.6, 0.3)], 20, 'bronze',
            center=tuple(kc), caps=False)
    cone = lambda u, v, off=0.0: kc + Vector(((6.4 * (1 - u) ** 1.7 + 0.5 + off) * math.cos(math.radians(v)),  # noqa: E731
                                              (6.4 * (1 - u) ** 1.7 + 0.5 + off) * math.sin(math.radians(v)),
                                              -13.5 * u))
    D.plates(cone, 16, 0.0, 0.92, 0, 360, lambda u: max(5, int(12 * (1 - u) ** 1.2) + 4),
             lambda i, j: 'pale' if (i + j) % 5 == 0 else ('shell' if i % 3 else 'bronze'), thick=0.12, off=0.12,
             lift=0.12)
    for v in range(0, 360, 60):
        pts = [tuple(cone(t / 20 * 0.95, v, 0.36)) for t in range(21)]
        F.sweep(pts, [(0.09, 0.09)] * 21, 'arc', sides=4)
    for k in range(7):                       # ring of hanging blades round the citadel
        a = math.radians(k * 360 / 7)
        d = Vector((math.cos(a), math.sin(a), 0))
        h = 8.0 if k % 2 == 0 else 5.5
        blade(kc + d * 8.6 + Vector((0, 0, 0.6)), Vector((0, 0, -1)) + d * 0.05, -d, h, 1.7, 0.36,
              'shell' if k % 2 == 0 else 'bronze', lean=0.35, curve=2.4)
    for k, (z, r) in enumerate([(-4.0, 5.2), (-8.0, 3.4), (-11.5, 2.3)]):
        D.ring(tuple(kc + Vector((0, 0, z))), r, 'pale' if k % 2 == 0 else 'bronze', gaps=3 + k, width=0.55, thick=0.3)
    low = kc + Vector((0, 0, -18.2))
    F.orb(tuple(low), 1.5, 'core', seg=(24, 14))
    D.ring(tuple(low), 2.1, 'pale', tilt=(70, 0, 0), width=0.2, thick=0.16)
    D.ring(tuple(low), 2.5, 'bronze', tilt=(20, 40, 0), gaps=3, width=0.26, thick=0.16)
    for k in range(4):
        a = math.radians(k * 90 + 30)
        d = Vector((math.cos(a), math.sin(a), 0))
        bolt(low + d * 1.4 + Vector((0, 0, 0.6)), kc + d * 2.0 + Vector((0, 0, -8.0)), rnd, width=0.09, jag=0.22,
             depth=4, branches=1)
    for e in (segs[0][0], segs[5][1]):       # keel core -> the lower halo arcs
        bolt(low, e, rnd, width=0.15, jag=0.15, depth=6, branches=3)

    # --- nose: energy bridge between the mandible tips through a floating focus
    focus = Vector((34.5, 0, 0.3))
    F.orb(tuple(focus), 0.9, 'bolt', seg=(12, 8))
    D.ring(tuple(focus), 1.7, 'pale', tilt=(0, 90, 0), gaps=3, width=0.3, thick=0.2)
    for tp in mand_tips:
        bolt(tp, focus, rnd, width=0.2, jag=0.13, depth=5, branches=3)
    bolt(Vector((24.3, 0, 0.2)), focus, rnd, width=0.12, jag=0.1, depth=5, branches=2)

    extra = F.since(m)
    shapes += len(extra)
    _join_into(ship, list(extra))
    ship['shapes'] = shapes
    ship['bays'] = bays
    ship['keel_core'] = tuple(low)
    return ship, core


# ================================================================== 4: squid ship
SQUID_BASE_X = 2.6      # tentacle roots sit on a ring at this x, radius SQUID_BASE_R
SQUID_BASE_R = 2.25


def tentacle_joints(pose='reach', n=10, segs=13, seed=5, targets=None):
    """Joint points for the squid's n tentacles (ship-local), one list of segs + 1 Vectors each.
    pose: 'reach' (two long feeder arms stretch forward to grab, the rest fan out and curl),
          'grab'  (the feeder arms' tips meet at one point, smashing what they hold together),
          'idle'  (all arms trail forward, loosely curled).
    targets = {arm_index: (x, y, z)} overrides where an arm's tip goes. Arms 0 and n // 2 are the
    long feeder arms."""
    rnd = random.Random(seed)
    targets = dict(targets or {})
    X = Vector((1, 0, 0))
    out = []
    feeders = (0, n // 2)
    for i in range(n):
        phi = 2 * math.pi * (i + 0.25) / n
        o = Vector((0, math.cos(phi), math.sin(phi)))
        b = Vector((SQUID_BASE_X, 0, 0)) + o * SQUID_BASE_R
        side = Vector((0, -o.z, o.y))
        w = rnd.uniform(-1, 1)
        if i in feeders:
            s = 1 if o.y >= 0 else -1
            if pose == 'grab':
                tgt = Vector((25.0, s * 0.7, 1.2))
            elif pose == 'idle':
                tgt = b + X * 22 + o * 5
            else:
                tgt = Vector((26.0, s * 3.0, 1.6 + 0.9 * s))
            tgt = Vector(targets.get(i, tgt))
            L = (tgt - b).length
            p1 = b + (X * 0.55 + o).normalized() * L * 0.42
            p2 = tgt + Vector((-0.25, s * 0.95, 0.25)).normalized() * L * 0.36
        else:
            L = rnd.uniform(13.0, 18.0)
            if pose == 'idle':
                tgt = b + X * L * 0.9 + o * L * 0.22 + side * w * 2
                p1 = b + (X * 0.8 + o * 0.6).normalized() * L * 0.4
                p2 = tgt - X * L * 0.3 + o * L * 0.12
            else:
                fwd = rnd.uniform(0.5, 0.85)
                tgt = b + X * L * fwd + o * L * rnd.uniform(0.5, 0.72) + side * w * 3.5
                p1 = b + (X * 0.25 + o).normalized() * L * 0.45
                p2 = tgt + (o * 0.9 - X * 0.3 + side * w * 0.5).normalized() * L * 0.42
            if i in targets:
                tgt = Vector(targets[i])
                p2 = tgt + (o - X * 0.3).normalized() * (tgt - b).length * 0.35
        pts = []
        for k in range(segs + 1):
            t = (k / segs) ** 0.92
            p = b * (1 - t) ** 3 + p1 * (3 * t * (1 - t) ** 2) + p2 * (3 * t * t * (1 - t)) + tgt * t ** 3
            p = p + side * (math.sin(t * math.pi * 2 + w * 3) * 0.5 * math.sin(math.pi * t))
            pts.append(p)
        out.append(pts)
    return out


def build_tentacle(joints, name='Tentacle', r0=0.62, r1=0.16, claw=1.0, join=True):
    """One floating segmented tentacle through the joint points: armoured segments that do not
    touch, glowing joint nodes, an energy thread linking them and a three-finger claw at the tip.
    Uses whatever forge faction/palette is active (call inside gold_palette())."""
    m = F.mark()
    J = [Vector(p) for p in joints]
    n = len(J) - 1
    for k in range(n):
        a, b = J[k], J[k + 1]
        d = b - a
        if d.length < 1e-4:
            continue
        r = r0 + (r1 - r0) * (k / max(1, n - 1)) ** 0.8
        F.tube(tuple(a + d * 0.16), tuple(a + d * 0.86),
               [(0, r * 0.45), (0.12, r * 0.95), (0.3, r), (0.78, r * 0.72), (1, r * 0.38)], 8,
               ('shell', 'shell', 'bronze')[k % 3])
        F.tube(tuple(a + d * 0.3), tuple(a + d * 0.42), [(0, r * 1.12), (1, r * 1.08)], 8, 'pale', caps=True)
        t = d.normalized()
        ref = Vector((0, a.y, a.z))
        ref = ref.normalized() if ref.length > 0.3 else Vector((0, 0, 1))
        outw = ref - t * ref.dot(t)
        outw = outw.normalized() if outw.length > 1e-3 else t.orthogonal().normalized()
        blade(a + d * 0.42 + outw * r * 0.75, outw, -t, r * 1.25, r * 1.2, r * 0.3, 'pale', lean=0.9, n=5)
        F.orb(tuple(a + d * 0.0), r * 0.42, 'bolt' if k % 4 == 0 else 'arc', seg=(8, 5))
        F.orb(tuple(a + d * 0.6 - outw * r * 0.82), r * 0.22, 'glow', seg=(6, 4))   # sucker light, inner face
    w = r1 * 0.3
    F.sweep([tuple(p) for p in J], [(w * (1.6 - 0.6 * k / n),) * 2 for k in range(n + 1)], 'arc', sides=4)
    # claw
    tip = J[-1]
    t = (J[-1] - J[-2]).normalized()
    s0 = t.orthogonal().normalized()
    F.orb(tuple(tip), r1 * 1.5, 'bolt', seg=(10, 6))
    for q in range(3):
        a = 2 * math.pi * q / 3
        o = (s0 * math.cos(a) + t.cross(s0) * math.sin(a)).normalized()
        blade(tip + o * r1 * 2.4 - t * 0.1, t * 0.9 + o * 0.75, -o, 1.9 * claw, 0.6 * claw, 0.2 * claw, 'pale',
              lean=0.62, n=7, curve=2.2)
    parts = list(F.since(m))
    if not join:
        return parts
    del F.ST['parts'][m:]
    for o in parts:
        o.data.materials.clear()
        o.data.materials.append(F.zone_mat(o['zone']))
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    obj['shapes'] = len(parts)
    return obj


@_gold
def squid_ship(name='SquidShip', pose='reach', n=10, segs=13, joints=None, targets=None, seed=5):
    rnd = random.Random(34)
    base._faction('kesh')
    m = F.mark()
    # --- mantle: armoured teardrop, pointed stern, blunt open collar at the bow
    man = F.lensfn(-17, 5.5, 3.5, 3.3, -2.7, 0.0, nose=0.62, tail=0.9)
    U0 = 0.1
    F.body(man, 'under', nu=34, nv=24, u0=U0, u1=1.0)
    D.plates(man, 40, U0 + 0.01, 0.97, 0, 360, lambda u: max(5, int(abs(man(u, 0).y) * 3.0) + 3),
             lambda i, j: 'bronze' if (i % 7 == 5) else ('pale' if (i + 2 * j) % 9 == 0 else 'shell'),
             thick=0.1, off=0.09, lift=0.1)
    D.seams(man, [35, 90, 145, 215, 270, 325], U0 + 0.02, 0.97, 0.28, n=40, w=0.07)
    # dorsal crest and stern fins (floating, like the fins of a squid's mantle)
    for k in range(6):
        u = 0.42 + 0.48 * k / 5
        h = 0.9 + 1.5 * math.sin(math.pi * k / 5) ** 0.8
        blade(man(u, 90, 0.25), (0, 0, 1), (-1, 0, 0), h, h * 0.5, 0.2, 'pale' if k % 2 == 0 else 'shell', lean=0.9)
    for s in (-1, 1):
        blade((-9.5, s * 3.3, 0.2), (-0.1, s, 0.12), (-1, 0, 0), 8.0, 4.6, 0.4, 'shell', lean=0.95, n=12)
        blade((-12.5, s * 2.4, -0.3), (-0.1, s, -0.15), (-1, 0, 0), 5.0, 2.6, 0.3, 'bronze', lean=0.95, n=10)
        F.orb((-9.5, s * 2.9, 0.2), 0.3, 'arc', seg=(8, 6))
        # sensor eyes: gold lens in a bronze socket ring on each flank of the head
        e = man(0.2, 12 if s > 0 else 168, 0.0)
        F.orb(tuple(e), 0.85, 'core', seg=(16, 10), sq=(0.9, 0.55, 0.9))
        oriented_ring(e + Vector((0, s * 0.2, 0)), (0, s, 0.15), 1.0, 0.24, 0.3, 'bronze', n=20)
        oriented_ring(e + Vector((0, s * 0.45, 0)), (0, s, 0.15), 1.5, 0.2, 0.16, 'pale', n=20, gaps=3)
    F.orb((-17.4, 0, 0), 0.8, 'arc', seg=(12, 8), sq=(1.8, 1, 1))     # stern drive
    oriented_ring((-16.2, 0, 0), (1, 0, 0), 1.7, 0.3, 0.25, 'bronze', gaps=4)
    # --- collar and core "beak" at the bow, where the tentacles are rooted
    head = man(U0, 0, 0)
    hx, hr = head.x, abs(head.y)
    F.tube((hx - 0.4, 0, 0.2), (hx + 0.9, 0, 0.2), [(0, hr * 1.02), (0.5, hr * 1.12), (1, hr * 0.84)], 28, 'bronze',
           caps=False)
    F.tube((hx + 0.5, 0, 0.2), (hx + 0.7, 0, 0.2), [(0, hr * 0.9), (1, hr * 0.9)], 28, 'under')
    core = Vector((hx + 1.3, 0, 0.2))
    F.orb(tuple(core), 1.75, 'core', seg=(28, 16))
    oriented_ring(core + Vector((1.0, 0, 0)), (1, 0, 0), 1.75, 0.22, 0.2, 'pale', gaps=3)
    oriented_ring(core + Vector((-0.2, 0, 0)), (1, 0, 0), SQUID_BASE_R + 0.55, 0.3, 0.3, 'arc', n=36)
    for k in range(8):       # beak petals round the core
        a = 2 * math.pi * (k + 0.5) / 8
        o = Vector((0, math.cos(a), math.sin(a)))
        blade(core + o * 1.9 + Vector((-0.6, 0, 0)), Vector((1, 0, 0)) + o * 0.15, -o, 2.9, 1.0, 0.24, 'pale',
              lean=0.28, n=7, curve=2.4)
    body_parts = list(F.since(m))
    nbody = len(body_parts)
    ship = D._finish(m, name)

    # --- tentacles: separate objects so an animation can re-pose / rebuild them
    if joints is None:
        joints = tentacle_joints(pose, n=n, segs=segs, seed=seed, targets=targets)
    names, shapes = [], nbody
    feeders = (0, len(joints) // 2)
    for i, J in enumerate(joints):
        big = i in feeders
        t = build_tentacle(J, f'{name}_Tentacle{i:02d}', r0=1.0 if big else 0.8, r1=0.32 if big else 0.22,
                           claw=1.4 if big else 0.9)
        # a short lightning root from the collar ring to the first joint
        mm = F.mark()
        r0 = Vector(J[0])
        bolt(Vector((core.x - 0.2, r0.y * 1.2, r0.z * 1.2 + 0.2)), Vector(J[1]), rnd, width=0.06, jag=0.25, depth=3,
             branches=0)
        extra = list(F.since(mm))
        del F.ST['parts'][mm:]
        _join_into(t, extra)
        t.parent = ship
        shapes += t['shapes'] + len(extra)
        names.append(t.name)
    # lightning crackling between the two feeder claws
    mm = F.mark()
    ta, tb = Vector(joints[feeders[0]][-1]), Vector(joints[feeders[1]][-1])
    bolt(ta, tb, rnd, width=0.12, jag=0.18, depth=5, branches=3)
    bolt(tb, ta, rnd, width=0.07, jag=0.3, depth=4, branches=1)
    extra = list(F.since(mm))
    del F.ST['parts'][mm:]
    arcs = _join_into(extra[0], extra[1:]) if len(extra) > 1 else extra[0]
    arcs.data.materials.clear()
    arcs.data.materials.append(F.zone_mat('bolt'))
    arcs.name = f'{name}_ClawArc'
    arcs.parent = ship
    ship['claw_arc'] = arcs.name
    shapes += len(extra)
    ship['shapes'] = shapes
    ship['tentacles'] = names
    ship['joints'] = [[tuple(p) for p in J] for J in joints]
    ship['feeders'] = list(feeders)
    return ship, core


# ================================================================== 5: corvette
@_gold
def arcadian_corvette(name='ArcadianCorvette'):
    """~15 long escort: crescent hammerhead prow (horns forward) on a slender neck, the core exposed
    amidships inside gyroscope rings, flanking crescent blades and a cluster of ring engines."""
    rnd = random.Random(35)
    base._faction('kesh')
    m = F.mark()
    hullf = F.lensfn(-6.5, 5.2, 1.35, 1.0, -0.85, 0.0, nose=1.25, tail=0.85)   # fat aft, slim neck forward
    F.body(hullf, 'under', nu=30, nv=18)
    D.plates(hullf, 34, 0.03, 0.97, 10, 170, lambda u: max(3, int(abs(hullf(u, 0).y) * 4.5) + 2),
             lambda i, j: 'bronze' if i % 6 == 4 else ('pale' if (i + j) % 7 == 0 else 'shell'),
             thick=0.045, off=0.045, lift=0.04)
    D.plates(hullf, 20, 0.05, 0.95, 190, 350, lambda u: max(3, int(abs(hullf(u, 0).y) * 3) + 2),
             lambda i, j: rnd.choice(('bronze', 'under', 'bronze')), thick=0.05, off=0.045, lift=0.03)
    D.seams(hullf, [0, 180, 90, 60, 120], 0.03, 0.97, 0.11, n=40, w=0.03)
    # --- hammerhead: a crescent with its horns pointing forward
    Rh = 2.3
    h0, h1 = math.radians(62), math.radians(298)
    hc = Vector((6.4, 0, 0.05))

    def hpath(u):
        a = h0 + (h1 - h0) * u
        return hc + Vector((Rh * math.cos(a) * 1.25, Rh * math.sin(a), 0))

    hf = D.tubefn(hpath, lambda u: 0.07 + 0.62 * math.sin(math.pi * u) ** 0.8, sq=(1.0, 0.62))
    F.body(hf, 'under', nu=30, nv=14)
    D.plates(hf, 24, 0.02, 0.98, 0, 360, lambda u: 7,
             lambda i, j: 'pale' if i % 4 == 1 else ('bronze' if j % 4 == 3 else 'shell'), thick=0.04, off=0.04,
             lift=0.035)
    D.seams(hf, [0, 90, 180], 0.03, 0.97, 0.09, n=30, w=0.03)
    eye = hc + Vector((0.55, 0, 0))
    F.orb(tuple(eye), 0.5, 'core', seg=(20, 12))
    D.ring(tuple(eye), 0.72, 'pale', tilt=(0, 90, 0), gaps=3, width=0.09, thick=0.07)
    D.ring(tuple(eye), 0.86, 'bronze', tilt=(0, 0, 0), width=0.08, thick=0.06)
    horn_a, horn_b = hpath(0.0), hpath(1.0)
    for hp in (horn_a, horn_b):
        F.orb(tuple(hp), 0.11, 'bolt', seg=(8, 5))
        bolt(hp, eye + Vector((0.2, 0.45 if hp.y > 0 else -0.45, 0)), rnd, width=0.04, jag=0.2, depth=4, branches=1)
    bolt(horn_a, horn_b, rnd, width=0.04, jag=0.12, depth=5, branches=1)
    # --- core amidships, floating above a cradle
    core = Vector((-1.6, 0, 2.0))
    F.lathe([(0.0, 0.75), (0.75, 0.7), (1.05, 1.0), (0.9, 1.22), (0.6, 1.05)], 20, 'bronze', center=(-1.6, 0, 0),
            caps=False)
    gyro_core(core, 0.8, rings=3)
    for k in range(3):
        a = math.radians(k * 120 + 40)
        bolt(core + Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, -0.2)),
             Vector((-1.6 + math.cos(a) * 0.95, math.sin(a) * 0.95, 1.2)), rnd, width=0.03, jag=0.25, depth=3,
             branches=0)
    # --- dorsal fins and a ventral keel
    for x, h in [(-4.6, 2.5), (-3.4, 1.7), (1.2, 1.1), (2.4, 0.8)]:
        u = (5.2 - x) / 11.7
        blade(hullf(u, 90, 0.05), (0, 0, 1), (-1, 0, 0), h, h * 0.5, 0.11, 'pale', lean=0.8)
    blade((-2.5, 0, -0.9), (0, 0, -1), (-1, 0, 0), 2.4, 1.3, 0.14, 'bronze', lean=0.9)
    blade((-4.6, 0, -0.75), (0, 0, -1), (-1, 0, 0), 1.5, 0.8, 0.11, 'shell', lean=0.9)
    # --- flanking crescent blades, floating off the hull (two tiers each side)
    for s in (-1, 1):
        for k, (r, a_0, a_1, w, z, x) in enumerate([(7.0, 58, 120, 0.85, 0.15, -1.2), (6.2, 68, 116, 0.5, -0.5, -2.0)]):
            o = F.crescent((x, -r + 2.75 + 0.6 * k, z), r, a_0, a_1, w, 0.16, 'shell' if k == 0 else 'bronze', n=22)
            if s < 0:
                F.xf(o, F.Matrix.Diagonal((1, -1, 1, 1)))
        pts = F.arc_pts((-1.2, s * (-7.0 + 2.75), 0.27), 7.0, s * 64, s * 114, 16)
        F.sweep(pts, [(0.035, 0.035)] * 16, 'arc', sides=4)
        # side lance batteries: floating barrels under each blade
        for x in (-2.6, -0.4, 1.6):
            F.tube((x, s * 2.05, -0.25), (x + 1.7, s * 2.0, -0.25), [(0, 0.1), (0.2, 0.17), (0.85, 0.09), (1, 0.12)], 8,
                   'barrel')
            F.orb((x + 1.78, s * 2.0, -0.25), 0.08, 'bolt', seg=(6, 4))
            F.orb((x - 0.1, s * 2.05, -0.25), 0.16, 'bronze', seg=(8, 6))
    # --- dorsal turrets: orb + twin barrels
    for x in (0.3, 3.1):
        u = (5.2 - x) / 11.7
        p = hullf(u, 90, 0.05)
        F.orb(tuple(p + Vector((0, 0, 0.12))), 0.27, 'pale', seg=(12, 8), sq=(1, 1, 0.75))
        for s in (-1, 1):
            F.cyl(tuple(p + Vector((0.1, s * 0.1, 0.2))), tuple(p + Vector((0.95, s * 0.1, 0.3))), 0.045, 6, 'barrel')
            F.orb(tuple(p + Vector((0.98, s * 0.1, 0.3))), 0.05, 'glow', seg=(6, 4))
    # --- engines: three ring thrusters and floating petals round the stern
    for (y, z, r) in [(0, 0.25, 0.85), (-1.15, -0.25, 0.6), (1.15, -0.25, 0.6)]:
        F.tube((-6.2, y, z), (-7.7, y, z), [(0, r * 0.75), (0.5, r), (1, r * 1.1)], 16, 'bronze', caps=False)
        F.tube((-7.3, y, z), (-7.35, y, z), [(0, r * 1.0), (1, r * 1.0)], 16, 'bolt')
        F.tube((-7.4, y, z), (-9.4, y, z), [(0, r * 0.7), (1, 0.02)], 10, 'arc')
        oriented_ring((-8.2, y, z), (1, 0, 0), r * 1.45, r * 0.24, r * 0.2, 'pale', gaps=3)
    for k in range(6):
        a = math.radians(k * 60 + 30)
        o = Vector((0, math.cos(a), math.sin(a) * 0.8))
        blade(Vector((-5.9, 0, 0)) + o * 1.75, Vector((-1, 0, 0)) + o * 0.2, o, 2.6, 0.7, 0.12,
              'shell' if k % 2 else 'pale', lean=0.25, n=7)
    ship = D._finish(m, name)
    ship['eye'] = tuple(eye)
    return ship, core


# ================================================================== 6: stingray fighter
@_gold
def stingray_fighter(name='StingrayFighter'):
    """~1.5 long ray: swept diamond wing with up-curled tips, twin head horns round a gold emitter,
    core orb on the back, segmented floating whip tail with a glowing sting."""
    base._faction('kesh')
    m = F.mark()

    def le(s):           # leading edge x at span fraction s (-1..1)
        return 0.34 - 0.52 * abs(s) ** 1.45

    def chord(s):
        return 0.8 * (1 - abs(s)) ** 0.72 + 0.03

    def zc(s):
        a = abs(s)
        return 0.035 - 0.07 * a + 0.2 * a ** 3.2

    def wing(scale_t, zoff, zone, st=25, nsec=14, cs=1.0):
        rings = []
        for i in range(st):
            s = -1 + 2 * i / (st - 1)
            c = chord(s) * cs
            th = (0.085 * (1 - abs(s)) ** 1.1 + 0.008) * scale_t
            ring = []
            for k in range(nsec):
                a = 2 * math.pi * k / nsec
                xx = le(s) - (chord(s) - c) / 2 - c * (0.5 - 0.5 * math.cos(a))
                zz = zc(s) + zoff + th * math.sin(a) * (1.0 if math.sin(a) > 0 else 0.55)
                ring.append((xx, s * 0.76, zz))
            rings.append(ring)
        return F.loft(rings, zone, sharp=60)

    wing(1.0, 0.0, 'shell')
    wing(0.8, -0.03, 'under', cs=0.8)        # darker belly showing under the gold skin
    # plate lines and glow along the leading edge
    for s0 in (-1, 1):
        pts = [(le(s0 * k / 20) + 0.004, s0 * k / 20 * 0.76, zc(s0 * k / 20) + 0.004) for k in range(1, 21)]
        F.sweep(pts, [(0.011, 0.011)] * 20, 'arc', sides=4)
        for q, f in enumerate((0.3, 0.52, 0.72)):     # glowing gill slats across each wing
            x0 = le(f) - chord(f) * 0.22
            x1 = le(f) - chord(f) * 0.8
            z = zc(f) + 0.085 * (1 - f) ** 1.1 * 0.62
            F.sweep([(x0, s0 * f * 0.76, z), ((x0 + x1) / 2, s0 * (f + 0.03) * 0.76, z + 0.004),
                     (x1, s0 * (f + 0.05) * 0.76, z - 0.012)], [(0.012, 0.006)] * 3, 'glow', sides=4)
        # wing tip: floating crescent blade beyond the tip
        blade((le(1.0) + 0.03, s0 * 0.8, zc(1.0) + 0.01), (-0.45, s0 * 0.5, 0.75), (-1, 0, 0), 0.17, 0.06, 0.014, 'pale',
              lean=0.7, n=7)
        F.orb((le(1.0) - 0.0, s0 * 0.775, zc(1.0)), 0.016, 'bolt', seg=(6, 4))
        # head horns curving in round the emitter
        hp = smooth_pts([(0.2, s0 * 0.12, 0.035), (0.4, s0 * 0.165, 0.03), (0.53, s0 * 0.14, 0.02),
                         (0.61, s0 * 0.07, 0.008)], 5)
        nh = len(hp)
        F.sweep([tuple(p) for p in hp], [(0.034 * (1 - k / (nh - 1)) ** 0.7 + 0.003, 0.024 * (1 - k / (nh - 1)) ** 0.7
                                         + 0.003) for k in range(nh)], 'pale', sides=6)
        F.orb((0.27, s0 * 0.085, 0.085), 0.02, 'bolt', seg=(8, 5))                      # eyes
        F.orb((-0.44, s0 * 0.1, 0.035), 0.04, 'bolt', seg=(8, 5), sq=(1.2, 1.0, 0.45))  # engines
        F.tube((-0.46, s0 * 0.1, 0.035), (-0.66, s0 * 0.1, 0.04), [(0, 0.03), (1, 0.002)], 6, 'arc')
        blade((-0.2, s0 * 0.075, 0.1), (0, s0 * 0.25, 1), (-1, 0, 0), 0.15, 0.09, 0.012, 'pale', lean=0.9, n=6)
    # --- central body with scale plates, core orb on the back
    bodyf = F.lensfn(-0.5, 0.44, 0.15, 0.135, -0.06, 0.02, nose=0.8, tail=0.9)
    F.body(bodyf, 'bronze', nu=16, nv=14)
    D.plates(bodyf, 9, 0.04, 0.96, 15, 165, lambda u: 4, lambda i, j: 'pale' if (i + j) % 3 == 0 else 'shell',
             thick=0.012, off=0.008, lift=0.01)
    core = Vector((-0.03, 0, 0.15))
    F.orb(tuple(core), 0.075, 'core', seg=(20, 12))
    D.ring(tuple(core), 0.1, 'pale', width=0.018, thick=0.014)
    D.ring(tuple(core), 0.118, 'bronze', tilt=(62, 0, 25), gaps=3, width=0.016, thick=0.012)
    rnd = random.Random(36)
    emit = Vector((0.5, 0, 0.012))
    F.orb(tuple(emit), 0.022, 'bolt', seg=(10, 6))
    for s0 in (-1, 1):
        bolt((0.6, s0 * 0.075, 0.008), emit, rnd, width=0.006, jag=0.22, depth=3, branches=1)
    # --- whip tail: floating segments linked by a thread of light, sting at the end
    TJ = smooth_pts([(-0.48, 0, 0.03), (-0.66, 0, 0.012), (-0.84, 0, 0.03), (-0.98, 0, 0.085)], 3)
    nt = len(TJ) - 1
    for k in range(nt):
        a, b = TJ[k], TJ[k + 1]
        r = 0.036 * (1 - k / nt) ** 0.8 + 0.008
        F.tube(tuple(a + (b - a) * 0.14), tuple(a + (b - a) * 0.86), [(0, r * 0.5), (0.25, r), (1, r * 0.45)], 6,
               'shell' if k % 2 == 0 else 'bronze')
        F.orb(tuple(a), r * 0.42, 'arc', seg=(6, 4))
    F.sweep([tuple(p) for p in TJ], [(0.004, 0.004)] * len(TJ), 'arc', sides=4)
    d = (TJ[-1] - TJ[-2]).normalized()
    blade(TJ[-1], d, (0, 0, 1), 0.13, 0.04, 0.014, 'pale', lean=0.35, n=6)
    F.orb(tuple(TJ[-1]), 0.02, 'bolt', seg=(8, 5))
    ship = D._finish(m, name)
    ship['tail'] = [tuple(p) for p in TJ]
    ship['emitter'] = tuple(emit)
    return ship, core


BUILDERS = {
    'crescent': crescent_mothership_v2,
    'shell': shell_mothership_v2,
    'lens': lens_mothership_v2,
    'squid': squid_ship,
    'corvette': arcadian_corvette,
    'stingray': stingray_fighter,
}
