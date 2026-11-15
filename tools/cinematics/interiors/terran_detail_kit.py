"""Film-set detail layer for the Terran interior stills (cinematic views only, never the game views).

Wall dressing modules (layered plates, recessed bays behind grilles, vents, hatches, pipe bundles,
cable runs, indicator panels, lockers), structure (trusses, ducts, hanging cable looms, handrails,
ladders) and props (crew seats and stations, tool carts, ammo / fuel racks, loader arms, maintenance
drones, charging umbilicals, floor chevrons). Everything is batched through terran_interior_kit.
"""
import math
import random

from mathutils import Vector

import terran_interior_kit as K


class Fr:
    """Local frame on a wall or at a prop: u runs along, n points out (left of u), z is up."""

    def __init__(self, origin, ang):
        self.o = Vector((origin[0], origin[1], origin[2] if len(origin) > 2 else 0.0))
        self.ang = ang
        a = math.radians(ang)
        self.u = Vector((math.cos(a), math.sin(a), 0))
        self.n = Vector((-math.sin(a), math.cos(a), 0))

    def at(self, u, n, z):
        p = self.o + self.u * u + self.n * n
        return (p.x, p.y, p.z + z)

    def box(self, mat, u, n, z, su, sn, sz, taper=None, tilt=0.0):
        K.box(mat, self.at(u, n, z), (su, sn, sz), (tilt, 0, self.ang) if tilt else self.ang, taper)

    def cyl(self, mat, a, b, r, sides=8, r1=None, smooth=True):
        K.cyl(mat, self.at(*a), self.at(*b), r, sides, r1=r1, smooth=smooth)


def bar(mat, p0, p1, r):
    K.cyl(mat, p0, p1, r, n=4, smooth=False)


# ------------------------------------------------------------------ wall modules
def _plate(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    f.box(r.choice(['hull', 'armor', 'hull_lt']), cu, 0.07, cz, w - 0.14, 0.14, h - 0.14)
    k = r.random()
    if k < 0.5:
        f.box(r.choice(['armor', 'hull']), cu + r.uniform(-0.1, 0.1) * w, 0.18, cz, w * r.uniform(0.45, 0.75), 0.22, h * r.uniform(0.5, 0.8))
    else:
        for q in (-1, 1):
            f.box('armor', cu + q * w * 0.24, 0.17, cz, w * 0.34, 0.2, h * 0.72)
        f.box('dark', cu, 0.15, cz, 0.08, 0.06, h * 0.72)
    for a in (-1, 1):
        for b in (-1, 1):
            f.box('steel', cu + a * (w / 2 - 0.28), 0.16, cz + b * (h / 2 - 0.28), 0.1, 0.06, 0.1)
    if r.random() < 0.3:
        for q in range(3):
            f.box('paint_y', cu - 0.5 + q * 0.5, 0.3, z0 + 0.42, 0.12, 0.02, 0.5, tilt=0)


def _bay(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    f.box('dark', cu, 0.02, cz, w - 0.3, 0.04, h - 0.3)
    for (du, sw, dz, sh) in [(-(w / 2 - 0.22), 0.3, 0, h - 0.1), (w / 2 - 0.22, 0.3, 0, h - 0.1), (0, w - 0.1, h / 2 - 0.2, 0.3),
                             (0, w - 0.1, -(h / 2 - 0.2), 0.3)]:
        f.box('armor', cu + du, 0.22, cz + dz, sw, 0.44, sh)
    n = max(2, int((w - 0.8) / 0.45))
    for q in range(n):
        uu = u0 + 0.55 + q * (w - 1.1) / max(1, n - 1)
        f.cyl(r.choice(['steel', 'hull_lt', 'crate_o', 'rubber']), (uu, 0.14, z0 + 0.35), (uu, 0.14, z1 - 0.35), r.uniform(0.05, 0.11), 6)
    for q in range(int((h - 0.8) / 0.34)):
        if q % 3 != 2:
            f.box('dark', cu, 0.36, z0 + 0.5 + q * 0.34, w - 0.6, 0.04, 0.07)
    f.box('neon_dim', cu, 0.3, z1 - 0.42, w - 0.9, 0.05, 0.06)
    f.box('orange', u1 - 0.5, 0.45, z0 + 0.5, 0.14, 0.03, 0.1)


def _vent(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    f.box('armor', cu, 0.1, cz, w - 0.2, 0.2, h - 0.2)
    f.box('dark', cu, 0.2, cz, w - 0.6, 0.04, h - 0.6)
    for q in range(int((h - 0.7) / 0.22)):
        f.box('hull_lt', cu, 0.25, z0 + 0.42 + q * 0.22, w - 0.7, 0.14, 0.05, tilt=-25)
    f.box('steel', cu, 0.26, cz, 0.08, 0.1, h - 0.6)
    f.box('orange', u0 + 0.36, 0.22, z1 - 0.36, 0.12, 0.03, 0.12)


def _hatch(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    hw, hh = min(w - 0.5, 1.9), h - 0.5
    f.box('armor', cu, 0.08, cz, w - 0.14, 0.16, h - 0.14)
    f.box('hull_lt', cu, 0.2, cz, hw, 0.12, hh)
    f.box('dark', cu, 0.21, cz, hw + 0.12, 0.1, hh + 0.12)
    f.box('hazard', cu, 0.27, cz - hh / 2 + 0.2, hw - 0.1, 0.02, 0.26)
    f.cyl('steel', (cu + hw / 2 - 0.25, 0.36, cz - 0.4), (cu + hw / 2 - 0.25, 0.36, cz + 0.4), 0.04, 6)
    for dz in (-0.4, 0.4):
        f.box('steel', cu + hw / 2 - 0.25, 0.31, cz + dz, 0.08, 0.1, 0.08)
    for dz in (-hh / 2 + 0.4, hh / 2 - 0.4):
        f.box('dark', cu - hw / 2 - 0.02, 0.28, cz + dz, 0.16, 0.12, 0.3)
    f.box('screen_bg', cu - hw / 2 + 0.4, 0.27, cz + hh / 2 - 0.4, 0.5, 0.02, 0.3)
    f.box(r.choice(['orange', 'cyan']), cu - hw / 2 + 0.4, 0.29, cz + hh / 2 - 0.4, 0.3, 0.02, 0.06)


def _pipes(f, r, u0, u1, z0, z1):
    w = u1 - u0
    f.box('armor', (u0 + u1) / 2, 0.04, (z0 + z1) / 2, w - 0.14, 0.08, z1 - z0 - 0.14)
    n = r.randint(3, 5)
    for q in range(n):
        uu = u0 + 0.45 + q * (w - 0.9) / (n - 1)
        rr = r.uniform(0.09, 0.2)
        f.cyl(r.choice(['hull_lt', 'steel', 'hull_lt', 'crate_o', 'crate_b']), (uu, 0.12 + rr, z0), (uu, 0.12 + rr, z1), rr, 8)
        zz = z0 + r.uniform(0.3, z1 - z0 - 0.3)
        f.cyl('dark', (uu, 0.12 + rr, zz - 0.08), (uu, 0.12 + rr, zz + 0.08), rr * 1.35, 8)
    for zz in (z0 + 0.35, z1 - 0.35):
        f.box('dark', (u0 + u1) / 2, 0.2, zz, w - 0.3, 0.42, 0.12)
    if r.random() < 0.5:
        f.box('armor', u0 + 0.6, 0.45, (z0 + z1) / 2, 0.6, 0.5, 0.6)
        f.cyl('orange', (u0 + 0.6, 0.72, (z0 + z1) / 2), (u0 + 0.6, 0.76, (z0 + z1) / 2), 0.12, 8)


def _cables(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    f.box(r.choice(['hull', 'armor']), cu, 0.05, cz, w - 0.14, 0.1, h - 0.14)
    n = r.randint(4, 7)
    for q in range(n):
        zz = z0 + 0.4 + q * (h - 0.9) / n
        sag = r.uniform(0.05, 0.25)
        pts = [(u0 + (u1 - u0) * k / 6, 0.16 + 0.03 * (q % 2), zz - sag * math.sin(math.pi * k / 6)) for k in range(7)]
        m = r.choice(['rubber', 'rubber', 'crate_o', 'crate_b', 'steel'])
        for a, b in zip(pts[:-1], pts[1:]):
            f.cyl(m, a, b, r.uniform(0.025, 0.05), 5)
    for uu in (u0 + 0.12, u1 - 0.12):
        f.box('dark', uu, 0.16, cz, 0.16, 0.22, h - 0.5)
    f.box('armor', cu, 0.25, z1 - 0.45, 0.8, 0.4, 0.5)
    f.box('cyan', cu, 0.46, z1 - 0.45, 0.3, 0.02, 0.08)


def _indicators(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    f.box('armor', cu, 0.1, cz, w - 0.16, 0.2, h - 0.16)
    f.box('screen_bg', cu, 0.21, cz + h * 0.14, w - 0.7, 0.03, h * 0.45)
    for q in range(int(h * 0.45 / 0.2) - 1):
        L = r.uniform(0.2, 0.8) * (w - 1.0)
        f.box(r.choice(['screen', 'screen', 'screen_c', 'screen_o']), u0 + 0.5 + L / 2 + r.uniform(0, w - 1.0 - L), 0.235,
              cz + h * 0.14 - h * 0.2 + 0.12 + q * 0.2, L, 0.02, 0.06)
    cols = int((w - 0.7) / 0.24)
    for row in range(2):
        for q in range(cols):
            if r.random() < 0.8:
                f.box(r.choice(['orange', 'orange', 'cyan', 'neon', 'dark']), u0 + 0.45 + q * 0.24, 0.215, z0 + 0.42 + row * 0.22, 0.12, 0.03, 0.08)
    f.box('hull_lt', cu, 0.3, z0 + 0.95, w - 0.8, 0.3, 0.08)


def _locker(f, r, u0, u1, z0, z1):
    cu, cz, w, h = (u0 + u1) / 2, (z0 + z1) / 2, u1 - u0, z1 - z0
    d = r.uniform(0.45, 0.8)
    f.box(r.choice(['hull_lt', 'crate', 'armor']), cu, d / 2, cz, w - 0.3, d, h - 0.3)
    n = max(1, int((w - 0.3) / 1.0))
    for q in range(n + 1):
        f.box('dark', u0 + 0.15 + q * (w - 0.3) / n, d + 0.01, cz, 0.05, 0.04, h - 0.34)
    for q in range(n):
        uu = u0 + 0.15 + (q + 0.5) * (w - 0.3) / n
        f.box('steel', uu + 0.3, d + 0.05, cz, 0.05, 0.06, 0.4)
        f.box('orange' if q % 2 else 'cyan', uu - 0.25, d + 0.02, cz + h / 2 - 0.5, 0.16, 0.02, 0.06)
        for k in range(3):
            f.box('dark', uu, d + 0.02, z0 + 0.45 + k * 0.1, 0.5, 0.03, 0.04)
    f.box('dark', cu, d / 2, z1 - 0.12, w - 0.2, d + 0.1, 0.08)


MODULES = [(_plate, 5), (_bay, 3), (_vent, 2), (_hatch, 2), (_pipes, 3), (_cables, 2), (_indicators, 2), (_locker, 2)]


def dress_wall(origin, ang, length, z0, z1, seed=0, cell=(3.0, 2.6), skip=None, weights=None, trim=True):
    """Tile a wall rectangle with random detail modules so that no bare panel is left.
    origin = (x, y) of the wall's start, ang = direction of u in degrees (the room is on the left)."""
    r = random.Random(seed)
    f = Fr((origin[0], origin[1], 0), ang)
    mods = [m for m, k in (weights or MODULES) for _ in range(k)]
    nu = max(1, round(length / cell[0]))
    nz = max(1, round((z1 - z0) / cell[1]))
    cw, ch = length / nu, (z1 - z0) / nz
    for i in range(nu):
        j = 0
        while j < nz:
            span = 2 if (j + 1 < nz and r.random() < 0.25) else 1
            a, b = z0 + j * ch, z0 + (j + span) * ch
            if not (skip and skip(i * cw + cw / 2, (a + b) / 2)):
                m = r.choice(mods)
                if span == 2 and m in (_vent, _indicators):
                    m = _pipes
                m(f, r, i * cw, (i + 1) * cw, a, b)
            j += span
    if trim:
        for j in range(nz + 1):                      # horizontal trim rails between the rows
            f.box('dark', length / 2, 0.1, z0 + j * ch, length, 0.2, 0.1)
        for i in range(nu + 1):
            f.box('dark', i * cw, 0.12, (z0 + z1) / 2, 0.1, 0.24, z1 - z0)


# ------------------------------------------------------------------ structure
def truss(p0, p1, depth=1.6, width=0.0, mat='armor', r=0.12, bay=None):
    """Lattice girder between two points (top chord on the line, bottom chord `depth` below)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    n = max(2, round(L / (bay or depth * 1.2)))
    dn = Vector((0, 0, -depth))
    side = Vector((-d.y, d.x, 0))
    side = side.normalized() * (width / 2) if side.length > 1e-6 else Vector((width / 2, 0, 0))
    for s in ((-1, 1) if width else (0,)):
        o = side * s
        bar(mat, p0 + o, p1 + o, r)
        bar(mat, p0 + o + dn, p1 + o + dn, r)
        for i in range(n):
            a, b = p0 + o + d * (i / n), p0 + o + d * ((i + 1) / n)
            bar(mat, a, a + dn, r * 0.7)
            bar(mat, a + dn if i % 2 else a, b if i % 2 else b + dn, r * 0.7)
        bar(mat, p1 + o, p1 + o + dn, r * 0.7)
    if width:
        for i in range(n + 1):
            a = p0 + d * (i / n)
            bar(mat, a - side, a + side, r * 0.6)
            bar(mat, a - side + dn, a + side + dn, r * 0.6)


def cable_loom(p0, p1, n=5, sag=1.5, r=0.05, seed=0, spread=0.25):
    """Bundle of hanging cables between two points (catenary-ish), with a couple of clamps."""
    rr = random.Random(seed)
    p0, p1 = Vector(p0), Vector(p1)
    for q in range(n):
        off = Vector((rr.uniform(-spread, spread), rr.uniform(-spread, spread), rr.uniform(-spread, spread) * 0.5))
        sg = sag * rr.uniform(0.7, 1.3)
        m = rr.choice(['rubber', 'rubber', 'rubber', 'crate_o', 'crate_b'])
        pts = [p0 + (p1 - p0) * (k / 8) + off * math.sin(math.pi * k / 8) + Vector((0, 0, -sg * math.sin(math.pi * k / 8))) for k in range(9)]
        for a, b in zip(pts[:-1], pts[1:]):
            K.cyl(m, a, b, r * rr.uniform(0.6, 1.2), 5)
    for p in (p0, p1):
        K.box('dark', p, (0.5, 0.5, 0.4))


def duct(p0, p1, w=1.2, h=0.8, mat='hull_lt', flange=3.0):
    """Rectangular duct along X or Y with flanges and a few grilles."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    alongx = abs(d.x) > abs(d.y)
    c = (p0 + p1) / 2
    K.box(mat, c, (abs(d.x) + (0 if alongx else w), abs(d.y) + (w if alongx else 0), h) if False else
          ((abs(d.x), w, h) if alongx else (w, abs(d.y), h)))
    n = int(d.length / flange)
    for i in range(n + 1):
        p = p0 + d * (i / max(n, 1))
        K.box('dark', p, (0.14, w + 0.16, h + 0.16) if alongx else (w + 0.16, 0.14, h + 0.16))
        if i < n and i % 2 == 0:
            q = p0 + d * ((i + 0.5) / max(n, 1))
            K.box('dark', (q.x, q.y, q.z - h / 2 - 0.01), (1.2, w * 0.6, 0.04) if alongx else (w * 0.6, 1.2, 0.04))


def handrail(p0, p1, h=1.1, post=2.0, mat='steel'):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    n = max(1, round(d.length / post))
    for i in range(n + 1):
        p = p0 + d * (i / n)
        K.box(mat, (p.x, p.y, p.z + h / 2), (0.07, 0.07, h))
    for z in (h, h * 0.55):
        K.cyl(mat, p0 + Vector((0, 0, z)), p1 + Vector((0, 0, z)), 0.04, 6)


def ladder(base, ang, h, cage=True):
    f = Fr(base, ang)
    for du in (-0.35, 0.35):
        f.box('steel', du, 0.25, h / 2, 0.07, 0.07, h)
    for k in range(int(h / 0.38)):
        f.box('steel', 0, 0.25, 0.4 + k * 0.38, 0.7, 0.05, 0.05)
    if cage:
        for k in range(int((h - 2.4) / 1.4)):
            z = 2.6 + k * 1.4
            for a, b in [((-0.45, 0.25), (-0.5, 0.9)), ((-0.5, 0.9), (0.5, 0.9)), ((0.5, 0.9), (0.45, 0.25))]:
                f.cyl('steel', (a[0], a[1], z), (b[0], b[1], z), 0.025, 4)


# ------------------------------------------------------------------ crew furniture
def seat(c, ang, s=1.0, mat='armor'):
    """Crew seat facing along +n of its frame (pedestal, cushion, back, headrest, armrests)."""
    f = Fr(c, ang)
    f.cyl('steel', (0, 0, 0), (0, 0, 0.45 * s), 0.12 * s, 8)
    f.cyl('dark', (0, 0, 0), (0, 0, 0.06), 0.4 * s, 8)
    f.box(mat, 0, 0, 0.55 * s, 0.62 * s, 0.6 * s, 0.16 * s)
    f.box('rubber', 0, 0.02, 0.65 * s, 0.5 * s, 0.5 * s, 0.06 * s)
    f.box(mat, 0, -0.3 * s, 1.05 * s, 0.6 * s, 0.14 * s, 0.9 * s, tilt=-8)
    f.box('rubber', 0, -0.22 * s, 1.05 * s, 0.46 * s, 0.05 * s, 0.7 * s, tilt=-8)
    f.box(mat, 0, -0.36 * s, 1.62 * s, 0.34 * s, 0.14 * s, 0.24 * s)
    for du in (-0.36, 0.36):
        f.box('dark', du * s, 0.02, 0.82 * s, 0.08 * s, 0.5 * s, 0.06 * s)


def crew_station(c, ang, w=3.2, col='screen', seed=0, seats=True, z=0.0):
    """Console for seated crew: desk with a lit key panel, two or three monitors on arms, side
    module with indicator rows, and a seat. The operator sits on the -n side, facing +n."""
    r = random.Random(seed)
    f = Fr((c[0], c[1], c[2] if len(c) > 2 else z), ang)
    f.box('armor', 0, 0.2, 0.42, w, 1.0, 0.84)
    f.box('dark', 0, -0.28, 0.2, w - 0.3, 0.1, 0.4)
    f.box('hull_lt', 0, 0.02, 0.9, w + 0.1, 1.3, 0.1)
    f.box('screen_bg', 0, -0.25, 0.97, w - 0.5, 0.5, 0.04, tilt=12)
    nk = int((w - 0.7) / 0.14)
    for row in range(3):
        for q in range(nk):
            if r.random() < 0.85:
                f.box(r.choice(['screen', 'screen', 'screen_c', 'screen_o', 'dark']), -(w - 0.7) / 2 + q * 0.14 + 0.07,
                      -0.4 + row * 0.13, 0.985 + (0.12 - (-0.4 + row * 0.13 + 0.25)) * 0.0 + row * 0.027, 0.08, 0.07, 0.02, tilt=12)
    nm = 3 if w > 2.8 else 2
    mw = (w - 0.3) / nm
    for q in range(nm):
        uu = -(w - 0.3) / 2 + (q + 0.5) * mw
        f.cyl('steel', (uu, 0.45, 0.95), (uu, 0.5, 1.35), 0.04, 6)
        f.box('armor', uu, 0.52, 1.62, mw - 0.12, 0.08, 0.72, tilt=-8)
        f.box('screen_bg', uu, 0.47, 1.62, mw - 0.22, 0.02, 0.6, tilt=-8)
        c2 = [col, 'screen_c', 'screen_o', 'screen'][(q + seed) % 4]
        for k in range(4):
            L = r.uniform(0.25, 0.8) * (mw - 0.4)
            f.box(c2 if k else 'screen_o', uu - (mw - 0.4) / 2 + L / 2 + r.uniform(0, mw - 0.4 - L), 0.455 + 0.02 * (k - 1.5) * 0.3,
                  1.42 + k * 0.13, L, 0.015, 0.05, tilt=-8)
    f.box('armor', w / 2 + 0.3, 0.15, 0.7, 0.5, 0.9, 1.4)
    for row in range(4):
        for q in range(3):
            f.box(r.choice(['orange', 'cyan', 'neon', 'dark']), w / 2 + 0.3 - 0.14 + q * 0.14, -0.31, 0.75 + row * 0.16, 0.07, 0.02, 0.07)
    f.box('neon', 0, -0.31, 0.06, w - 0.2, 0.03, 0.05)
    if seats:
        p = f.at(0, -1.05, 0)
        seat(p, ang)


# ------------------------------------------------------------------ hangar / workshop props
def tool_cart(c, ang, seed=0):
    r = random.Random(seed)
    f = Fr(c, ang)
    f.box('crate_o', 0, 0, 0.75, 1.9, 1.0, 0.9)
    f.box('dark', 0, 0, 0.26, 1.7, 0.9, 0.12)
    for du in (-0.75, 0.75):
        for dn in (-0.4, 0.4):
            f.cyl('rubber', (du, dn - 0.06, 0.14), (du, dn + 0.06, 0.14), 0.14, 8)
    for k in range(3):
        f.box('dark', 0, -0.51, 0.5 + k * 0.26, 1.7, 0.03, 0.03)
        f.box('steel', 0, -0.54, 0.62 + k * 0.26, 0.5, 0.04, 0.04)
    f.box('steel', 0, 0, 1.22, 2.0, 1.1, 0.05)
    for k in range(5):
        f.box(r.choice(['steel', 'dark', 'crate_b', 'paint_y']), r.uniform(-0.8, 0.8), r.uniform(-0.4, 0.4), 1.3, r.uniform(0.15, 0.5),
              r.uniform(0.1, 0.3), 0.12)
    f.cyl('steel', (-1.0, -0.4, 1.0), (-1.0, 0.4, 1.0), 0.03, 6)
    f.box('cyan', 0.6, -0.52, 1.05, 0.2, 0.02, 0.06)


def ammo_rack(c, ang, rows=3, cols=6, seed=0):
    """Open rack of shells (orange-banded) on a wheeled frame."""
    f = Fr(c, ang)
    w = cols * 0.42 + 0.3
    f.box('dark', 0, 0, 0.12, w, 1.5, 0.16)
    for du in (-w / 2 + 0.06, w / 2 - 0.06):
        for dn in (-0.65, 0.65):
            f.box('armor', du, dn, 1.1, 0.12, 0.12, 2.0)
    for row in range(rows):
        z = 0.5 + row * 0.62
        f.box('steel', 0, 0, z - 0.22, w - 0.1, 1.4, 0.05)
        for q in range(cols):
            uu = -w / 2 + 0.36 + q * 0.42
            f.cyl('hull_lt', (uu, -0.6, z), (uu, 0.35, z), 0.17, 10)
            f.cyl('steel', (uu, 0.35, z), (uu, 0.72, z), 0.17, 10, r1=0.03)
            f.cyl('orange' if (q + row) % 3 == 0 else 'paint_y', (uu, 0.2, z), (uu, 0.28, z), 0.175, 10)
    f.box('hazard', 0, -0.76, 1.1, w, 0.03, 0.3)
    f.box('armor', 0, 0, 2.14, w + 0.1, 1.5, 0.08)


def fuel_rack(c, ang, n=4):
    """Row of upright fuel / coolant cells with hoses, on a pallet."""
    f = Fr(c, ang)
    f.box('dark', 0, 0, 0.1, n * 1.05 + 0.3, 1.3, 0.2)
    for q in range(n):
        uu = -(n - 1) * 0.525 + q * 1.05
        f.cyl('crate_b' if q % 2 else 'hull_lt', (uu, 0, 0.2), (uu, 0, 1.9), 0.45, 12)
        for z in (0.5, 1.1, 1.6):
            f.cyl('dark', (uu, 0, z), (uu, 0, z + 0.07), 0.48, 12)
        f.cyl('steel', (uu, 0, 1.9), (uu, 0, 2.15), 0.2, 8)
        f.box('cyan', uu, -0.46, 1.35, 0.1, 0.02, 0.4)
        f.box('orange', uu, -0.46, 0.85, 0.16, 0.02, 0.08)
    f.cyl('steel', (-(n - 1) * 0.525, 0, 2.1), ((n - 1) * 0.525, 0, 2.1), 0.07, 6)
    f.box('hazard', 0, -0.66, 0.2, n * 1.05 + 0.3, 0.02, 0.22)


def loader_arm(c, ang, reach=5.0, lift=4.0, seed=0, load=True):
    """Articulated loader / maintenance arm on a turntable base, optionally holding a module."""
    f = Fr(c, ang)
    f.cyl('hazard', (0, 0, 0), (0, 0, 0.05), 1.7, 8, smooth=False)
    f.cyl('armor', (0, 0, 0), (0, 0, 0.7), 1.2, 8, smooth=False)
    f.cyl('hull_lt', (0, 0, 0.7), (0, 0, 1.3), 0.8, 8, smooth=False)
    sh = (0, 0, 1.6)
    el = (0, reach * 0.35, lift + 1.2)
    wr = (0, reach, lift)
    f.cyl('steel', (-0.6, 0, 1.6), (0.6, 0, 1.6), 0.4, 10)
    f.cyl('crate_o', sh, el, 0.38, 4, r1=0.3, smooth=False)
    f.cyl('steel', (-0.45, el[1], el[2]), (0.45, el[1], el[2]), 0.34, 10)
    f.cyl('armor', el, wr, 0.28, 4, r1=0.2, smooth=False)
    f.cyl('steel', (0.3, 0.3, 1.9), (0.3, el[1] * 0.8, el[2] - 0.6), 0.09, 6)
    f.cyl('rubber', (-0.3, 0.2, 1.7), (-0.3, el[1], el[2] - 0.1), 0.05, 5)
    f.cyl('rubber', (-0.3, el[1], el[2] - 0.1), (-0.2, wr[1] - 0.3, wr[2] + 0.2), 0.05, 5)
    f.box('hazard', 0, reach * 0.17, (1.6 + el[2]) / 2 - 0.1, 0.82, 0.3, 0.7)
    f.box('armor', 0, reach, lift - 0.3, 0.9, 0.9, 0.5)
    f.box('orange', 0, reach, lift + 0.02, 0.3, 0.3, 0.14)
    for du in (-0.5, 0.5):
        f.box('steel', du, reach, lift - 1.0, 0.12, 0.7, 1.0)
        f.box('steel', du * 0.75, reach, lift - 1.5, 0.3, 0.6, 0.12)
    f.box('white', 0, reach + 0.3, lift - 0.57, 0.3, 0.2, 0.04)
    f.box('armor', -1.0, -0.6, 1.0, 0.7, 0.7, 1.4)
    f.box('screen_c', -1.0, -0.96, 1.4, 0.4, 0.02, 0.25)
    if load:
        f.box('crate_b', 0, reach, lift - 2.2, 1.3, 1.6, 1.3)
        f.box('dark', 0, reach, lift - 2.2, 1.36, 1.3, 0.1)
        f.box('cyan', 0.66, reach, lift - 1.9, 0.02, 0.4, 0.08)


def drone(c, ang=0.0, s=1.0, beam=None):
    """Hovering maintenance drone: body, four thruster pods, sensor eye, tool arm, work light."""
    f = Fr(c, ang)
    f.box('armor', 0, 0, 0, 1.1 * s, 1.5 * s, 0.5 * s, taper=(0.7, 0.8))
    f.box('hull_lt', 0, 0, -0.3 * s, 0.8 * s, 1.1 * s, 0.2 * s)
    for du in (-1, 1):
        for dn in (-1, 1):
            f.cyl('steel', (du * 0.35 * s, dn * 0.5 * s, 0), (du * 0.85 * s, dn * 0.8 * s, 0.05 * s), 0.06 * s, 5)
            f.cyl('dark', (du * 0.85 * s, dn * 0.8 * s, -0.12 * s), (du * 0.85 * s, dn * 0.8 * s, 0.2 * s), 0.3 * s, 10)
            f.cyl('cyan', (du * 0.85 * s, dn * 0.8 * s, -0.15 * s), (du * 0.85 * s, dn * 0.8 * s, -0.12 * s), 0.22 * s, 10)
    f.cyl('cyan_hot', (0, 0.74 * s, 0.02 * s), (0, 0.78 * s, 0.02 * s), 0.13 * s, 8)
    f.box('orange', 0, -0.7 * s, 0.2 * s, 0.3 * s, 0.1 * s, 0.08 * s)
    f.cyl('steel', (0.2 * s, 0.5 * s, -0.4 * s), (0.3 * s, 1.0 * s, -0.9 * s), 0.05 * s, 5)
    f.cyl('steel', (0.3 * s, 1.0 * s, -0.9 * s), (0.25 * s, 1.3 * s, -1.2 * s), 0.035 * s, 5)
    f.cyl('steel', (0, 0, 0.25 * s), (0, -0.1 * s, 0.8 * s), 0.02 * s, 4)
    if beam:
        K.spot('DroneLight', f.at(0, 0.3 * s, -0.4 * s), beam, 900, (0.7, 0.9, 1.0), angle=50, blend=0.6, r=0.1)
        f.box('white', 0, 0.3 * s, -0.42 * s, 0.2 * s, 0.2 * s, 0.03)


def umbilical(socket, plug, seed=0, n=3):
    """Charging / data umbilicals from a floor or wall socket box to a vehicle, with a glowing connector."""
    rr = random.Random(seed)
    s, p = Vector(socket), Vector(plug)
    K.box('armor', (s.x, s.y, s.z + 0.35), (0.9, 0.9, 0.7))
    K.box('hazard', (s.x, s.y, s.z + 0.02), (1.5, 1.5, 0.04))
    K.box('cyan', (s.x, s.y, s.z + 0.72), (0.4, 0.4, 0.04))
    K.box('orange', (s.x + 0.46, s.y, s.z + 0.5), (0.03, 0.2, 0.1))
    top = s + Vector((0, 0, 0.6))
    for q in range(n):
        off = Vector((rr.uniform(-0.2, 0.2), rr.uniform(-0.2, 0.2), 0))
        d = p - top
        pts = []
        for k in range(9):
            t = k / 8
            q_ = top + d * t + off * math.sin(math.pi * t)
            q_.z = top.z + (p.z - top.z) * t - min(top.z, p.z) * 0.9 * math.sin(math.pi * t) * (0.6 + 0.2 * q)
            q_.z = max(q_.z, 0.06 + 0.05 * q)
            pts.append(q_)
        m = ['rubber', 'crate_o', 'rubber'][q % 3]
        for a, b in zip(pts[:-1], pts[1:]):
            K.cyl(m, a, b, 0.06 - 0.01 * q, 6)
    K.box('armor', p, (0.4, 0.4, 0.4))
    K.box('cyan_hot', (p.x, p.y, p.z + 0.22), (0.2, 0.2, 0.04))


def chevrons(c, ang, n=3, s=1.0, mat='paint_y', gap=1.1):
    """Floor chevrons pointing along +u of the frame."""
    f = Fr(c, ang)
    for k in range(n):
        for sd in (-1, 1):
            K.box(mat, f.at(k * gap * s - 0.35 * s, sd * 0.55 * s, 0.012), (1.5 * s, 0.26 * s, 0.02), ang - sd * 40)


def floor_trench(p0, p1, w=0.9, light='neon_dim'):
    """Cable trench with a grille cover and a strip light inside, along X or Y."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    alongx = abs(d.x) > abs(d.y)
    c = (p0 + p1) / 2
    L = d.length
    K.box('dark', (c.x, c.y, 0.012), (L, w, 0.024) if alongx else (w, L, 0.024))
    K.box(light, (c.x, c.y, 0.03), (L, 0.08, 0.02) if alongx else (0.08, L, 0.02))
    n = int(L / 0.3)
    for i in range(n):
        p = p0 + d * ((i + 0.5) / n)
        K.box('steel', (p.x, p.y, 0.045), (0.06, w, 0.03) if alongx else (w, 0.06, 0.03))
    for s in (-1, 1):
        o = Vector((0, s * w / 2, 0)) if alongx else Vector((s * w / 2, 0, 0))
        K.box('armor', (c.x + o.x, c.y + o.y, 0.03), (L, 0.1, 0.06) if alongx else (0.1, L, 0.06))
