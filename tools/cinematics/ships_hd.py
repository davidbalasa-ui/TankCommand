"""High-detail capital ships (5,000+ separate shapes each), shared by the cinematics and the
backstory campaign's fleet view. Same designs, builder names and return values as ships.py:

    terran_dreadnought() -> (ship, muzzles)    muzzles = local turret-tip points
    terran_frigate()     -> ship               (from ships.py, unchanged)
    kesh_mothership()    -> (ship, core_point) core_point = local centre of the gold orb
    kesh_cruiser()       -> (ship, core_point) (from ships.py, unchanged)

Front is +X, up is +Z. Each builder joins its parts into one object and stores the number of
separate shapes it was built from in ship['shapes'].
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

terran_frigate = base.terran_frigate
kesh_cruiser = base.kesh_cruiser


def _finish(m, name):
    parts = F.since(m)
    n = len(parts)
    ship = base._join(parts, name)
    ship['shapes'] = n
    return ship


# ================================================================== Terran
# Hull cross-sections (x, half width, bottom z, top z), as in ships.py.
T_SECS = [(-17, 2.6, -1.3, 1.5), (-12, 3.4, -1.7, 2.0), (-4, 3.8, -1.9, 2.2),
          (6, 3.3, -1.6, 1.8), (13, 2.2, -1.0, 1.2), (18, 0.7, -0.3, 0.5)]


def _tsec(x):
    """Interpolated (w, zb, zt) of the Terran hull at x."""
    s = T_SECS
    if x <= s[0][0]:
        return s[0][1:]
    for a, b in zip(s, s[1:]):
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
    return s[-1][1:]


def _greeble(rnd, x, y, z, scale, zones=('armor', 'plate', 'dark')):
    """One small machine detail sitting on a flat surface at (x, y, z). Returns shapes made."""
    k = rnd.random()
    zone = rnd.choice(zones)
    if k < 0.45:
        sx, sy, sz = (rnd.uniform(0.08, 0.35) * scale, rnd.uniform(0.06, 0.25) * scale, rnd.uniform(0.03, 0.14) * scale)
        F.box((x, y, z + sz), (sx, sy, sz), zone, taper=rnd.uniform(0.7, 1.0))
    elif k < 0.6:
        r = rnd.uniform(0.03, 0.09) * scale
        L = rnd.uniform(0.3, 1.0) * scale
        F.cyl((x - L / 2, y, z + r), (x + L / 2, y, z + r), r, 6, rnd.choice(('barrel', 'dark')))
    elif k < 0.72:
        F.box((x, y, z + 0.03 * scale), (rnd.uniform(0.1, 0.3) * scale, rnd.uniform(0.1, 0.2) * scale, 0.03 * scale), 'vent')
    elif k < 0.82:
        r = rnd.uniform(0.06, 0.16) * scale
        F.cyl((x, y, z), (x, y, z + rnd.uniform(0.05, 0.2) * scale), r, 8, zone)
    elif k < 0.9:
        h = rnd.uniform(0.3, 0.9) * scale
        F.cyl((x, y, z), (x, y, z + h), 0.02 * scale, 4, 'barrel')
        if rnd.random() < 0.5:
            F.orb((x, y, z + h), 0.035 * scale, 'amber', seg=(6, 4))
    else:
        F.box((x, y, z + 0.02 * scale), (rnd.uniform(0.15, 0.4) * scale, 0.025 * scale, 0.02 * scale),
              rnd.choice(('glow', 'amber')))
    return 1


def terran_dreadnought(name='Dreadnought'):
    """~38 long. Dark angular wedge, twin spinal guns, many turret batteries, armour terraces,
    side hangar bays with cyan force fields and pod launch rails, cyan strips, amber lights."""
    rnd = random.Random(11)
    base._faction('terran')
    m = F.mark()
    secs = [(x, [(0, zb), (w * 0.62, zb * 0.92), (w, zb * 0.25), (w * 0.92, zt * 0.45), (w * 0.55, zt), (0, zt * 1.08)])
            for x, w, zb, zt in T_SECS]
    F.hull(secs, 'hull', bevel=0.06)

    # --- armour plating on the flat top and both upper flanks
    x = -16.6
    while x < 15.5:
        w, zb, zt = _tsec(x)
        L = rnd.uniform(0.7, 1.5)
        nrow = max(2, int(w * 1.1 / 0.55))
        for j in range(nrow):
            y = -w * 0.5 + (j + 0.5) * (w * 1.0 / nrow)
            if rnd.random() < 0.85:
                F.box((x + L / 2, y, zt * 1.04), (L / 2 - 0.04, w * 0.5 / nrow - 0.04, 0.05),
                      rnd.choice(('armor', 'plate', 'hull')), taper=0.85)
        for s in (-1, 1):  # sloped flank: plates following the face
            p0 = Vector((x + L / 2, s * w * 0.92, zt * 0.45))
            p1 = Vector((x + L / 2, s * w * 0.55, zt))
            for t in (0.25, 0.7):
                c = p0.lerp(p1, t)
                o = F.box((0, 0, 0), (L / 2 - 0.05, 0.22, 0.04), rnd.choice(('armor', 'plate')))
                ang = math.degrees(math.atan2(p1.z - p0.z, abs(p1.y - p0.y)))
                F.rot(o, 'X', s * ang, (0, 0, 0))
                F.move(o, c + Vector((0, s * 0.03, 0.03)))
        x += L

    # --- window rows and panel lines on the vertical sides (two decks)
    for s in (-1, 1):
        for deck, frac in enumerate((0.05, 0.3)):
            x = -16.0
            while x < 14.5:
                w, zb, zt = _tsec(x)
                z = zb * 0.25 + (zt * 0.45 - zb * 0.25) * (0.3 + frac)
                if not (-9 < x < 3 and deck == 0):  # leave room for the hangar bays
                    F.box((x, s * (w * 0.97), z), (0.06, 0.03, 0.035), rnd.choice(('amber', 'glass', 'glass', 'glow')))
                x += 0.32
        x = -16.2
        while x < 15:
            w, zb, zt = _tsec(x)
            F.box((x, s * w * 0.985, (zb * 0.25 + zt * 0.45) / 2), (0.02, 0.02, (zt * 0.45 - zb * 0.25) * 0.42), 'dark')
            x += rnd.uniform(0.9, 1.6)
        # lower hull: keel ribs
        x = -15.5
        while x < 12:
            w, zb, zt = _tsec(x)
            F.box((x, s * w * 0.8, zb * 0.6), (0.08, 0.06, 0.25), 'armor')
            x += 0.7

    # --- armour sponsons along both sides (as ships.py) with greebles on top
    for x0, x1 in [(-14, -10.5), (2.5, 8)]:
        F.sym(F.box(((x0 + x1) / 2, 3.75, -0.2), ((x1 - x0) / 2, 0.55, 0.85), 'armor', taper=0.8, bevel=0.06))
        F.sym(F.box(((x0 + x1) / 2, 4.31, 0.05), ((x1 - x0) / 2 - 0.4, 0.02, 0.06), 'glow'))
        for _ in range(70):
            gx = rnd.uniform(x0 + 0.2, x1 - 0.2)
            gy = rnd.uniform(3.35, 4.15)
            _greeble(rnd, gx, gy, 0.65, 0.6)
            _greeble(rnd, gx, -gy, 0.65, 0.6)

    # --- hangar bays: 2 per side between the sponsons, framed, cyan force field, pod rails
    bays = []
    for bx in (-7.2, -1.6):
        for s in (-1, 1):
            w, zb, zt = _tsec(bx)
            y = s * (w + 0.25)
            F.box((bx, y, -0.15), (2.4, 0.35, 0.95), 'armor', bevel=0.04)          # bay housing
            F.box((bx, y + s * 0.34, -0.15), (2.1, 0.03, 0.75), 'dark')              # recess
            F.box((bx, y + s * 0.38, -0.15), (2.0, 0.01, 0.68), 'glass')             # force field
            for dz in (-0.9, 0.6):                                                   # hazard lintels
                F.box((bx, y + s * 0.37, dz), (2.2, 0.03, 0.06), 'hazard')
            for dx in (-2.25, 2.25):
                F.box((bx + dx, y + s * 0.37, -0.15), (0.08, 0.04, 0.9), 'plate')
            for k in range(9):                                                       # field emitters
                F.box((bx - 2.0 + k * 0.5, y + s * 0.4, 0.68), (0.05, 0.03, 0.03), 'glow')
                F.box((bx - 2.0 + k * 0.5, y + s * 0.4, -0.98), (0.05, 0.03, 0.03), 'glow')
            for dz in (-0.5, 0.2):                                                   # launch rails
                F.box((bx, y + s * 0.6, dz), (1.8, 0.25, 0.03), 'plate')
                for k in range(7):
                    F.box((bx - 1.5 + k * 0.5, y + s * 0.8, dz + 0.04), (0.04, 0.04, 0.02), 'amber')
            bays.append(Vector((bx, y + s * 0.4, -0.15)))

    # --- dorsal superstructure: stepped tower, bridge, masts, dishes
    F.box((-9, 0, 2.5), (5.0, 1.6, 0.6), 'armor', taper=0.75, bevel=0.05)
    F.box((-10.5, 0, 3.4), (2.8, 1.1, 0.5), 'plate', taper=0.7, bevel=0.05)
    F.box((-11.2, 0, 4.15), (1.4, 0.8, 0.35), 'armor', taper=0.7, bevel=0.04)
    F.box((-10.05, 0, 4.2), (0.18, 0.62, 0.12), 'glass')
    for k in range(14):
        F.sym(F.box((-13.2 + k * 0.6, 1.62, 2.6), (0.22, 0.03, 0.04), rnd.choice(('glass', 'amber'))))
        F.sym(F.box((-12.6 + k * 0.35, 1.12, 3.5), (0.1, 0.03, 0.03), 'glass'))
    for k in range(4):
        F.sym(F.box((-13 + k * 1.6, 1.62, 2.3), (0.6, 0.04, 0.2), 'vent'))
    F.cyl((-12, 0, 4.4), (-12, 0, 6.6), 0.08, 6, 'barrel')
    F.orb((-12, 0, 6.65), 0.12, 'amber')
    for k in range(6):
        F.sym(F.cyl((-12, 0, 4.8 + k * 0.3), (-12, 0.4 + k * 0.05, 4.8 + k * 0.3), 0.02, 4, 'barrel'))
    for (dx, dy) in [(-9.5, 0.9), (-8.2, -0.8)]:
        F.lathe([(0.0, 0.0), (0.45, 0.12), (0.5, 0.2)], 12, 'plate', center=(dx, dy, 3.95))
        F.cyl((dx, dy, 3.9), (dx, dy, 4.25), 0.03, 4, 'barrel')
    for _ in range(420):
        gx, gy = rnd.uniform(-13.8, -4.2), rnd.uniform(-1.3, 1.3)
        _greeble(rnd, gx, gy, 3.1 if abs(gx + 9) < 4.8 and abs(gy) < 1.2 else 2.6, 0.5)

    # --- greebles on the open deck
    for _ in range(6200):
        gx = rnd.uniform(-16.5, 15)
        w, zb, zt = _tsec(gx)
        gy = rnd.uniform(-w * 0.5, w * 0.5)
        if -14.2 < gx < -3.8 and abs(gy) < 1.7:
            continue
        if -2.5 < gx < 9 and abs(gy) < 1.4:
            continue
        _greeble(rnd, gx, gy, zt * 1.09 + 0.05, 0.55)

    # --- twin spinal guns on the bow with coil rings
    for y in (-0.75, 0.75):
        F.cyl((-2, y, 2.25), (19.5, y, 1.6), 0.32, 12, 'barrel')
        F.cyl((19.5, y, 1.6), (20.3, y, 1.57), 0.38, 12, 'armor')
        for k in range(18):
            t = k / 17
            px = 2 + 16 * t
            pz = 2.25 + (1.6 - 2.25) * (px + 2) / 21.5
            F.cyl((px - 0.08, y, pz), (px + 0.08, y, pz), 0.38, 12, 'coil' if k % 3 == 0 else 'armor')
    F.box((3, 0, 2.15), (5.5, 1.3, 0.35), 'armor', taper=0.7, bevel=0.05)
    for k in range(20):
        F.sym(F.box((-1.5 + k * 0.5, 1.15, 2.2), (0.15, 0.05, 0.2), 'plate'))

    # --- turret batteries: heavy dorsal + sponson + point defence along the deck edges
    muzzles = []

    def turret(x, y, z, r, barrels=2):
        F.orb((x, y, z), r, 'plate', seg=(12, 6), sq=(1, 1, 0.45))
        F.box((x + 0.18 * r, y, z + 0.62 * r), (1.1 * r, 0.8 * r, 0.4 * r), 'armor', taper=0.7, bevel=0.03 * r)
        F.box((x - 0.6 * r, y, z + 0.75 * r), (0.2 * r, 0.6 * r, 0.12 * r), 'vent')
        offs = [0] if barrels == 1 else [(-0.3 + 0.6 * i / (barrels - 1)) * r for i in range(barrels)]
        for dy in offs:
            F.cyl((x + 0.7 * r, y + dy, z + 0.7 * r), (x + 3.6 * r, y + dy, z + 0.75 * r), 0.12 * r, 6, 'barrel')
            F.cyl((x + 3.3 * r, y + dy, z + 0.75 * r), (x + 3.7 * r, y + dy, z + 0.76 * r), 0.16 * r, 6, 'dark')
        F.box((x + 0.95 * r, y, z + 0.9 * r), (0.15 * r, 0.3 * r, 0.03 * r), 'glow')
        muzzles.append(Vector((x + 3.7 * r, y, z + 0.75 * r)))

    for (x, y, z) in [(-2.5, 0, 2.55), (-16, 0, 2.0)]:
        turret(x, y, z, 0.55)
    for x in (-13.5, -11, 3.2, 5.5, 7.5):
        for s in (-1, 1):
            turret(x, s * 3.75, 0.7, 0.5)
    x = -15.5
    while x < 13:
        w, zb, zt = _tsec(x)
        for s in (-1, 1):
            turret(x, s * w * 0.62, zt * 0.98 + 0.05, 0.18, barrels=rnd.choice((1, 2, 3)))
        x += 1.7

    # --- engines: 4 big + 6 small, with rings, vanes and glow
    for (y, z, r) in [(0, 0.2, 1.15), (-2.1, -0.5, 0.8), (2.1, -0.5, 0.8), (0, -1.3, 0.7),
                      (-1.3, 1.1, 0.45), (1.3, 1.1, 0.45), (-2.6, 0.6, 0.4), (2.6, 0.6, 0.4),
                      (-1.2, -1.4, 0.35), (1.2, -1.4, 0.35)]:
        F.tube((-16.6, y, z), (-18.6, y, z), [(0, r * 0.9), (0.3, r), (1, r * 1.12)], 16, 'dark', caps=False)
        F.cyl((-18.0, y, z), (-18.1, y, z), r * 0.95, 16, 'glow')
        for k in range(4):
            F.cyl((-16.8 - k * 0.45, y, z), (-16.95 - k * 0.45, y, z), r * (1.05 + 0.03 * k), 16, 'armor')
        for a in range(0, 360, 45):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            F.box((-17.9, y + ca * r * 0.5, z + sa * r * 0.5), (0.05, 0.02 + abs(sa) * r * 0.4, 0.02 + abs(ca) * r * 0.4), 'plate')

    # --- running lights along the hull edges, belly glow
    x = -16
    while x < 16:
        w, zb, zt = _tsec(x)
        F.sym(F.orb((x, w * 0.92, zt * 0.45), 0.06, 'amber' if int(x) % 3 else 'red', seg=(6, 4)))
        x += 1.0
    F.box((10, 0, -1.55), (4, 0.12, 0.05), 'glow')
    for _ in range(900):  # belly: hatches, pipes and sensor bumps
        gx = rnd.uniform(-16, 13)
        w, zb, zt = _tsec(gx)
        gy = rnd.uniform(-w * 0.55, w * 0.55)
        F.box((gx, gy, zb * 0.95), (rnd.uniform(0.1, 0.5), rnd.uniform(0.08, 0.3), 0.06),
              rnd.choice(('armor', 'dark', 'plate', 'vent')))

    ship = _finish(m, name)
    ship['bays'] = [tuple(b) for b in bays]
    return ship, muzzles


# ================================================================== Arcadian (kesh)
def kesh_mothership(name='Mothership'):
    """~46 across. Hovering lens of etched silver scale plates in overlapping rows, bronze belly
    plates, layered crescent fins all round, floating rings of petals round the gold core orb,
    hanging bronze spires below, gold seams, and four hangar maws with gold force fields."""
    rnd = random.Random(23)
    base._faction('kesh')
    m = F.mark()
    lens = F.lensfn(-20, 24, 13, 4.5, -3.5, 0.0, nose=0.7, tail=0.8)
    F.body(lens, 'under', nu=26, nv=32)

    # --- scale armour: rows of small overlapping leaf plates over the top surface
    rows = 80
    for i in range(rows):
        u0 = 0.03 + 0.94 * i / rows
        u = u0 + 0.5 / rows
        span = 150  # degrees of the top covered
        n = max(4, int(abs(lens(u, 0).y) * 3.6))
        for j in range(n):
            vc = 15 + span * (j + 0.5 * (i % 2)) / n
            if vc > 165:
                continue
            band = 'bronze' if (i // 10) % 3 == 2 and abs(vc - 90) > 25 else 'shell'
            F.shell(lens, u0, u0 + 1.5 / rows, vc, span / n * 1.1, band,
                    nu=3, nv=3, thick=0.07, off=0.12 + 0.02 * (j % 2), lift=0.09, shape=0.5)
    # --- belly: bronze scale rows and gold seams
    for i in range(46):
        u0 = 0.06 + 0.88 * i / 46
        n = max(4, int(abs(lens(u0, 0).y) * 1.6))
        for j in range(n):
            vc = 200 + 140 * (j + 0.5 * (i % 2)) / n
            if vc > 340:
                continue
            F.shell(lens, u0, u0 + 1.5 / 46, vc, 140 / n * 1.1, rnd.choice(('bronze', 'under', 'bronze')),
                    nu=3, nv=3, thick=0.09, off=0.2, lift=0.08)
    for k in range(14):  # glowing seams running nose to tail on top and belly
        v = 20 + k * 10.5 if k < 7 else 200 + (k - 7) * 22
        pts = [tuple(lens(0.04 + 0.92 * t / 30, v, 0.3)) for t in range(31)]
        F.sweep(pts, [(0.05, 0.05)] * 31, 'slat' if k % 2 else 'glow', sides=4)

    # --- rim: layered crescent fins all round (3 tiers, both sides) plus small rim blades
    for k, (r, a0, a1, z) in enumerate([(14.2, 70, 175, 0.4), (15.4, 95, 200, -0.6), (16.6, 120, 215, -1.5)]):
        F.crescent((1, 0, z), r, a0, a1, 1.3 - k * 0.15, 0.45, 'shell', n=26, sq=(1.25, 1.0))
        F.crescent((1, 0, z), r, -a1, -a0, 1.3 - k * 0.15, 0.45, 'shell', n=26, sq=(1.25, 1.0))
        for a in range(int(a0) + 6, int(a1) - 4, 7):  # etched ribs on each fin
            for s in (-1, 1):
                ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
                c = (1 + r * ca * 1.25, s * r * sa, z + 0.3)
                F.orb(c, 0.16, 'glow' if a % 21 == 0 else 'bronze', seg=(6, 4), sq=(1, 1, 0.4))
    for j in range(72):
        v = j * 5
        a = math.radians(v)
        u = 0.5 - 0.5 * math.cos(a)  # walk the rim: nose -> tail -> nose
        side = 0 if math.sin(a) >= 0 else 180
        q = lens(u, side, 0.1)
        if abs(q.y) < 1.5:
            continue
        F.crescent((q.x, q.y, q.z), 1.2, -40, 40, 0.25, 0.1, rnd.choice(('shell', 'bronze')), n=8, plane='xy',
                   sq=(0.6, 1.0))

    # --- tall dorsal fins with etched ribs
    for x, h in [(-6, 7.5), (2, 9.5), (-12, 5.0)]:
        F.crescent((x - 8, 0, 3.0), h, -10, 80, 1.1, 0.4, 'bronze', n=18, plane='xz', up=(0, 1, 0))
        for a in range(0, 80, 6):
            c = (x - 8 + h * math.cos(math.radians(a)), 0, 3.0 + h * math.sin(math.radians(a)))
            F.sym(F.orb((c[0], 0.28, c[2]), 0.12, 'glow' if a % 18 == 0 else 'shell', seg=(6, 4), sq=(1, 0.4, 1)))

    # --- core: cradle, orb, floating segmented petal rings (disconnected, suspended)
    F.lathe([(0.0, 5.2), (3.4, 5.0), (4.6, 6.0), (4.2, 6.8), (3.8, 6.4), (2.6, 5.6)], 32, 'bronze',
            center=(8, 0, 0), caps=False)
    core = Vector((8, 0, 8.4))
    F.orb(tuple(core), 3.4, 'core', seg=(32, 20))
    F.orb(tuple(core), 3.9, 'glow', seg=(6, 4), sq=(1, 1, 0.05))
    for a in range(0, 360, 30):
        F.crescent(tuple(core), 4.6, a - 12, a + 12, 0.5, 0.25, 'shell', n=8, plane='xy')
    for ring, (R, z, n, tilt) in enumerate([(6.0, 0.2, 12, 0.0), (4.9, 3.6, 8, 0.0)]):
        for k in range(n):
            a = 360 * k / n
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            F.crescent((core.x, core.y, core.z + z), R, a - 360 / n * 0.36, a + 360 / n * 0.36, 0.9, 0.3,
                       'bronze' if (k + ring) % 2 else 'shell', n=6, plane='xy')
            F.orb((core.x + ca * (R + 0.75), core.y + sa * (R + 0.75), core.z + z), 0.1, 'glow', seg=(6, 4))
    for k in range(12):  # floating shards above the core
        a = math.radians(k * 30)
        F.ico((core.x + 2.2 * math.cos(a), 2.2 * math.sin(a), core.z + 4.3 + 0.3 * (k % 2)), 0.25, 'shell', sub=1,
              sq=(0.5, 0.5, 1.6))

    # --- hanging bronze spires and gold drips under the belly
    for _ in range(60):
        u, v = rnd.uniform(0.15, 0.85), rnd.uniform(215, 325)
        p = lens(u, v, 0.1)
        L = rnd.uniform(1.0, 3.2)
        F.cyl(tuple(p), (p.x, p.y, p.z - L), rnd.uniform(0.12, 0.3), 6, 'bronze', r1=0.02)
        if rnd.random() < 0.6:
            F.orb((p.x, p.y, p.z - L - 0.25), 0.14, 'glow', seg=(6, 4))
    # --- suspended rim arcs: segmented bronze/silver bands floating above the rim (not attached)
    for tier, (lift, gap) in enumerate([(1.1, 0.0), (2.0, 0.5)]):
        for k in range(40):
            u0 = 0.08 + 0.84 * k / 40 + gap / 40
            for side in (40 - tier * 12, 140 + tier * 12):
                F.shell(lens, u0, u0 + 0.017, side, 12, 'bronze' if tier else 'shell', nu=3, nv=3, thick=0.1,
                        off=lift, lift=0.0, front=0.8, back=0.8)
    # --- hangar maws: 2 per side, bronze rings, gold force fields, glowing guide lights
    bays = []
    for u in (0.38, 0.62):
        for side in (0, 180):
            p = lens(u, side, 0.2)
            s = 1 if side == 0 else -1
            c = Vector((p.x, p.y + s * 0.2, p.z))
            F.tube(tuple(c - Vector((0, s * 0.6, 0))), tuple(c + Vector((0, s * 0.5, 0))),
                   [(0, 1.9), (0.5, 2.1), (1, 1.8)], 24, 'bronze', caps=False)
            F.tube(tuple(c + Vector((0, s * 0.1, 0))), tuple(c + Vector((0, s * 0.15, 0))),
                   [(0, 1.75), (1, 1.75)], 24, 'under', caps=True)          # dark recess
            F.tube(tuple(c + Vector((0, s * 0.35, 0))), tuple(c + Vector((0, s * 0.4, 0))),
                   [(0, 1.7), (1, 1.78)], 24, 'glow', caps=False)          # thin gold field rim
            for k in range(16):
                a = math.radians(k * 22.5)
                F.orb((c.x + 2.25 * math.cos(a), c.y + s * 0.5, c.z + 2.25 * math.sin(a)), 0.12, 'glow', seg=(6, 4))
                F.crescent((c.x, c.y + s * 0.5, c.z), 2.6, k * 22.5 - 8, k * 22.5 + 8, 0.3, 0.12, 'shell',
                           n=5, plane='xz')
            bays.append(tuple(c + Vector((0, s * 0.5, 0))))

    # --- gold seam studs over the whole hull
    for _ in range(1500):
        u, v = rnd.uniform(0.04, 0.96), rnd.uniform(0, 360)
        p = lens(u, v, 0.3 if 10 < v < 170 else 0.32)
        F.orb(tuple(p), rnd.uniform(0.05, 0.11), 'glow' if rnd.random() < 0.35 else 'barrel', seg=(6, 4))

    F.body(F.lensfn(-18, 21, 11.9, 0.3, -3.25, 0.0, nose=0.7, tail=0.8), 'slat', nu=14, nv=16, u0=0.1, u1=0.9)
    ship = _finish(m, name)
    ship['bays'] = bays
    return ship, core
