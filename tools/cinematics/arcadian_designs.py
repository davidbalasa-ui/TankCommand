"""Three alternative Arcadian mothership designs for David to pick from (cinematics only).

All keep the faction language: etched silver shell plates with seams, bronze belly, gold seams and a
glowing gold core orb, with parts that float free of the hull. Front is +X, up is +Z.

    A  crescent_mothership  - horseshoe hull open at the bow, core orb floating in the mouth inside
                              gyroscope rings, floating fins over the horns.
    B  nautilus_mothership  - coiled ammonite shell lying on its side, chambered plates, the core
                              glowing in the shell's mouth, floating tail fins behind.
    C  manta_mothership     - wide flat manta wing with detached crescent wingtips, the core orb on
                              the back inside three floating rings, hanging spires underneath.
Each returns (ship, core_point) like ships.kesh_mothership.
"""
import math
import os
import random
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'art', 'v2'))
import forge as F  # noqa: E402
import ships as base  # noqa: E402


def _finish(m, name):
    parts = F.since(m)
    n = len(parts)
    ship = base._join(parts, name)
    ship['shapes'] = n
    return ship


def tubefn(path, radius, sq=(1.0, 1.0), up=Vector((0, 0, 1)), flip=False):
    """Surface function round a curve: path(u) -> point, radius(u) -> r. v in degrees, 0 = outward
    side (path's left), 90 = up. Same calling convention as forge.lensfn (u, v, off)."""
    def f(u, v, off=0.0):
        u = min(1.0, max(0.0, u))
        e = 1e-3
        p = path(u)
        t = (path(min(1.0, u + e)) - path(max(0.0, u - e))).normalized()
        a = t.cross(up)
        if a.length < 1e-6:
            a = t.orthogonal()
        a.normalize()
        b = a.cross(t).normalized()
        r = radius(u) + off
        ang = math.radians(-v if flip else v)
        return p + a * (math.cos(ang) * r * sq[0]) + b * (math.sin(ang) * r * sq[1])
    return f


def plates(fn, rows, u0, u1, v0, v1, per_row, zone_fn, thick=0.12, off=0.1, lift=0.1, nu=3, nv=3):
    """Overlapping scale plates over part of a surface, staggered row to row."""
    for i in range(rows):
        a = u0 + (u1 - u0) * i / rows
        span = (v1 - v0)
        n = max(3, per_row(a))
        for j in range(n):
            vc = v0 + span * (j + 0.5 + 0.5 * (i % 2)) / n
            if vc > v1:
                continue
            F.shell(fn, a, a + 1.6 * (u1 - u0) / rows, vc, span / n * 1.12, zone_fn(i, j),
                    nu=nu, nv=nv, thick=thick, off=off + 0.02 * (j % 2), lift=lift, shape=0.5)


def seams(fn, vs, u0, u1, off, n=30, w=0.06):
    for k, v in enumerate(vs):
        pts = [tuple(fn(u0 + (u1 - u0) * t / n, v, off)) for t in range(n + 1)]
        F.sweep(pts, [(w, w)] * (n + 1), 'glow' if k % 2 == 0 else 'slat', sides=4)


def ring(c, r, zone, tilt=(0, 0, 0), gaps=0, width=0.5, thick=0.3, n=40):
    """Floating ring (optionally broken into arcs) round centre c, tilted by euler degrees."""
    if gaps:
        step = 360 / gaps
        objs = [F.crescent((0, 0, 0), r, k * step + 8, (k + 1) * step - 8, width, thick, zone, n=max(8, n // gaps),
                           tip=0.5) for k in range(gaps)]
    else:
        objs = [F.crescent((0, 0, 0), r, 0, 359, width, thick, zone, n=n, tip=1.0)]
    for o in objs:
        for ax, deg in zip('XYZ', tilt):
            if deg:
                F.rot(o, ax, deg)
        F.move(o, c)
    return objs


def core(c, r, rings=3):
    F.orb(c, r, 'core', seg=(32, 20))
    for k in range(rings):
        ring(c, r * (1.35 + 0.28 * k), 'bronze' if k % 2 else 'shell', tilt=(70 - 35 * k, 20 * k, 30 * k),
             gaps=3 if k == 1 else 0, width=0.35 + 0.1 * k, thick=0.25)
    for a in range(0, 360, 30):   # small floating petals in the core's halo
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        F.orb((c[0] + ca * r * 2.3, c[1] + sa * r * 2.3, c[2] + math.sin(math.radians(a * 3)) * r * 0.4),
              r * 0.16, 'shell', seg=(10, 6), sq=(1.3, 1.0, 0.35))


def hanging_spires(rnd, pts, zone='bronze'):
    for (x, y, z) in pts:
        h = rnd.uniform(1.5, 4.0)
        F.cyl((x, y, z), (x, y, z - h), rnd.uniform(0.18, 0.35), 6, zone, r1=0.02)
        F.orb((x, y, z - h * 0.6), 0.14, 'glow', seg=(6, 4))


# ================================================================== A: crescent
def crescent_mothership(name='CrescentMothership'):
    rnd = random.Random(11)
    base._faction('kesh')
    m = F.mark()
    R = 17.0
    a0, a1 = math.radians(48), math.radians(312)    # open toward +X

    def path(u):
        a = a0 + (a1 - a0) * u
        return Vector((R * math.cos(a) * 1.1, R * math.sin(a), 0.0))

    def radius(u):
        return 1.5 + 4.2 * math.sin(math.pi * u) ** 0.8   # thick at the back, tapering horns

    fn = tubefn(path, radius, sq=(1.0, 0.62))
    F.body(fn, 'under', nu=56, nv=24)
    # silver plates over the top half, bronze over the belly
    plates(fn, 70, 0.02, 0.98, 15, 165, lambda u: int(radius(u) * 2.2) + 3,
           lambda i, j: 'bronze' if i % 9 == 4 else 'shell', thick=0.1, off=0.12, lift=0.08)
    plates(fn, 40, 0.05, 0.95, 195, 345, lambda u: int(radius(u) * 1.2) + 2,
           lambda i, j: rnd.choice(('bronze', 'under')), thick=0.12, off=0.12, lift=0.06)
    seams(fn, [40, 90, 140, 270], 0.03, 0.97, 0.3, n=60)
    # inner face hangar maws glowing gold
    for u in (0.3, 0.42, 0.58, 0.7):
        p = fn(u, 180, 0.2)
        F.orb(tuple(p), 1.0, 'glow', seg=(12, 8), sq=(1.0, 1.0, 0.45))
    # floating fins above each horn and the spine, detached from the hull
    for u, h in [(0.12, 6), (0.88, 6), (0.5, 9), (0.35, 7), (0.65, 7)]:
        p = fn(u, 90, 1.2)
        t = (path(u + 0.01) - path(u - 0.01)).normalized()
        yaw = math.degrees(math.atan2(t.y, t.x))
        o = F.crescent((0, 0, 0), h, -5, 75, 1.0, 0.35, 'shell', n=14, plane='xz', up=(0, 1, 0))
        F.rot(o, 'Z', yaw + 180)
        F.move(o, (p.x, p.y, p.z + 0.6))
    # rim blades along the outer edge
    for k in range(48):
        u = 0.03 + 0.94 * k / 47
        p = fn(u, 0, 0.3)
        F.orb(tuple(p), 0.22, 'glow' if k % 4 == 0 else 'bronze', seg=(6, 4), sq=(1, 1, 0.5))
    # core in the mouth
    c = Vector((R * 1.1 * 0.62, 0, 1.5))
    core(c, 4.2)
    hanging_spires(rnd, [tuple(fn(u, 270, 0.0)) for u in (0.2, 0.35, 0.5, 0.65, 0.8)])
    return _finish(m, name), c


# ================================================================== B: nautilus
def nautilus_mothership(name='NautilusMothership'):
    rnd = random.Random(12)
    base._faction('kesh')
    m = F.mark()
    turns = 1.6
    k = 0.21

    def path(u):   # spiral in the XZ plane, coiling from the mouth (u=0) inward
        th = u * turns * 2 * math.pi
        r = 16.0 * math.exp(-k * th)
        return Vector((r * math.cos(th) - 2, 0.0, r * math.sin(th)))

    def radius(u):
        th = u * turns * 2 * math.pi
        return 6.0 * math.exp(-k * th) + 0.3

    fn = tubefn(path, radius, sq=(1.15, 0.9), up=Vector((0, 1, 0)), flip=True)
    F.body(fn, 'under', nu=70, nv=26)
    # chambered plates: rings of shell segments with gold septa between chambers
    nch = 26
    for i in range(nch):
        u0 = 0.01 + 0.95 * i / nch
        n = max(6, int(radius(u0) * 3.2))
        for j in range(n):
            vc = 360 * (j + 0.5 * (i % 2)) / n
            F.shell(fn, u0, u0 + 0.95 / nch * 0.92, vc, 360 / n * 1.05,
                    'bronze' if (j % 7 == 0) else 'shell', nu=4, nv=3, thick=0.16, off=0.12, lift=0.06,
                    shape=0.35, front=0.6, back=0.6)
        p = path(u0)
        t = (path(u0 + 0.005) - path(u0)).normalized()
        o = F.crescent((0, 0, 0), radius(u0) + 0.25, 0, 359, 0.18, 0.14, 'glow' if i % 3 == 0 else 'slat', n=24,
                       tip=1.0)
        # orient the septum ring perpendicular to the tube
        q = t.to_track_quat('Z', 'Y')
        F.xf(o, q.to_matrix().to_4x4())
        F.move(o, p)
    # the mouth: core orb glowing inside the opening, bronze lip
    mouth = path(0.0)
    t0 = (path(0.01) - mouth).normalized()
    lip = F.crescent((0, 0, 0), radius(0) * 1.05, 0, 359, 0.7, 0.5, 'bronze', n=36, tip=1.0)
    F.xf(lip, t0.to_track_quat('Z', 'Y').to_matrix().to_4x4())
    F.move(lip, mouth)
    c = mouth - t0 * 2.5
    core(c, 3.6, rings=2)
    # floating fins trailing behind / above the coil, and a keel of hanging spires
    for i, (x, z, h) in enumerate([(-20, 8, 7), (-23, 3, 6), (-21, -3, 5)]):
        o = F.crescent((0, 0, 0), h, 100, 175, 1.0, 0.35, 'shell', n=14, plane='xz', up=(0, 1, 0))
        F.move(o, (-x - 4, 0, z))
        for s in (-1, 1):
            o2 = F.crescent((0, 0, 0), h * 0.8, 110, 170, 0.8, 0.3, 'bronze', n=12, plane='xy')
            F.move(o2, (-x - 2, s * 2.0, z - 0.5))
    for s in (-1, 1):   # side pods (paired lens drones docked against the shell, floating)
        lens = F.lensfn(-7, 7, 1.6, 1.0, -0.8, 0.0)
        o = F.body(lens, 'shell', nu=12, nv=12)
        F.move(o, (2, s * 8.5, -4))
        F.orb((9.2, s * 8.5, -4), 0.6, 'glow', seg=(10, 6))
    hanging_spires(rnd, [(x, 0, -14.5) for x in (-6, -2, 2)])
    return _finish(m, name), c


# ================================================================== C: manta
def manta_mothership(name='MantaMothership'):
    rnd = random.Random(13)
    base._faction('kesh')
    m = F.mark()
    wing = F.lensfn(-22, 22, 21, 1.3, -0.9, 0.0, nose=0.45, tail=0.55, pw=1.0)
    F.body(wing, 'under', nu=34, nv=32)
    plates(wing, 60, 0.03, 0.97, 12, 168, lambda u: int(abs(wing(u, 0).y) * 1.9) + 3,
           lambda i, j: 'bronze' if (i + j) % 11 == 0 else 'shell', thick=0.09, off=0.1, lift=0.08)
    plates(wing, 34, 0.06, 0.94, 195, 345, lambda u: int(abs(wing(u, 0).y) * 1.0) + 2,
           lambda i, j: rnd.choice(('bronze', 'under', 'bronze')), thick=0.1, off=0.1, lift=0.05)
    seams(wing, [30, 60, 120, 150, 90], 0.03, 0.97, 0.28, n=50)
    # dorsal ridge spine
    spine = F.lensfn(-18, 14, 2.2, 3.8, -0.5, 0.0, nose=0.6, tail=0.8)
    F.body(spine, 'bronze', nu=20, nv=14)
    plates(spine, 18, 0.05, 0.95, 20, 160, lambda u: 5, lambda i, j: 'shell', thick=0.1, off=0.08, lift=0.1)
    # detached crescent wingtips floating off each edge, 2 tiers
    for s in (-1, 1):
        for k, (r, a0, a1, z, dy) in enumerate([(12, 40, 140, 0.0, 22.5), (9, 55, 125, -1.2, 25.0)]):
            o = F.crescent((0, 0, 0), r, a0, a1, 1.4 - 0.3 * k, 0.45, 'shell', n=22)
            if s < 0:
                F.xf(o, F.Matrix.Diagonal((1, -1, 1, 1)))
            F.move(o, (-4 - 3 * k, s * (dy - r), z))
        for x in range(-16, 18, 4):   # glowing rim nodes
            q = wing(0.5 - x / 44, 0 if s > 0 else 180, 0.2)
            F.orb(tuple(q), 0.25, 'glow', seg=(6, 4))
    # tail fins (floating)
    for s in (-1, 1):
        o = F.crescent((0, 0, 0), 8, 95, 165, 0.9, 0.35, 'bronze', n=14, plane='xz', up=(0, 1, 0))
        F.move(o, (-12, s * 3.5, 1.5))
    # core on the back inside floating gyroscope rings
    c = Vector((4, 0, 8.5))
    F.lathe([(0.0, 3.6), (2.8, 3.4), (3.6, 4.4), (3.0, 5.0)], 28, 'bronze', center=(4, 0, 0))
    core(c, 3.4, rings=3)
    # hangar maws on the belly, hanging spires
    for x in (-8, 0, 8):
        for s in (-1, 1):
            F.orb((x, s * 7, -1.4), 1.1, 'glow', seg=(12, 8), sq=(1.4, 1.0, 0.3))
    hanging_spires(rnd, [(x, y, -1.5) for x in (-14, -6, 2, 10) for y in (-12, 0, 12)])
    return _finish(m, name), c


DESIGNS = {'A': crescent_mothership, 'B': nautilus_mothership, 'C': manta_mothership}
