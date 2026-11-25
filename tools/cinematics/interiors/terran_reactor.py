"""Terran capital ship - reactor / core chamber, a mission objective (concept still).

    python terran_reactor.py [--out=DIR] [--name=reactor] [--res=960x540] [--samples=20] [--final=PATH.jpg]

A 16-sided chamber 68 m across and 40 m high. The core is a plasma column inside a triangle
containment field, held by clamp arms from the walls; a ring deck (wide enough for tanks) runs
round an open pit, with six injector towers and two catwalk rings above.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import terran_interior_kit as K  # noqa: E402
import terran_detail_kit as D  # noqa: E402

A = K.args()
OUT = A.get('out', '/home/user/work/terran-interiors')
NAME = A.get('name', 'reactor')
RES = tuple(int(v) for v in A.get('res', '960x540').split('x'))

R, HT, PIT, N = 34.0, 40.0, 12.0, 16
rnd = random.Random(9)


def P(r, a, z=0.0):
    a = math.radians(a)
    return (r * math.cos(a), r * math.sin(a), z)


def bar(mat, p0, p1, r):
    K.cyl(mat, p0, p1, r, n=4, smooth=False)


def ring(r, z, mat, w, n=48, fill=0.7):
    for i in range(n):
        bar(mat, P(r, 360 * i / n, z), P(r, 360 * (i + fill) / n, z), w)


def arc_box(mat, r0, r1, a0, a1, z0, z1):
    K.loft(mat, [P(r0, a0, z0), P(r1, a0, z0), P(r1, a1, z0), P(r0, a1, z0)],
           [P(r0, a0, z1), P(r1, a0, z1), P(r1, a1, z1), P(r0, a1, z1)])


def chamber():
    step = 360 / N
    for i in range(N):
        a0, a1 = i * step - step / 2, (i + 1) * step - step / 2
        am = (a0 + a1) / 2
        arc_box('floor', PIT, R + 2, a0, a1, -1, 0)                       # ring deck
        arc_box('hull_big', R, R + 2, a0, a1, 0, HT)                      # wall facet
        arc_box('hull_big', 0, R + 2, a0, a1, HT, HT + 2)                 # ceiling
        arc_box('armor', PIT - 0.6, PIT, a0, a1, -14, 0.5)                # pit lining + kerb
        arc_box('hazard', PIT, PIT + 1.2, a0, a1, 0.0, 0.03)
        arc_box('armor', R - 1.6, R, a0, a1, 0, 2.6)                      # wall base
        arc_box('armor', R - 0.6, R, a0, a1, 17.5, 19.0)
        arc_box('hull', R - 1.0, R, a0, a1, 31, 33)
        bar('neon', P(R - 1.65, a0 + 1, 2.3), P(R - 1.65, a1 - 1, 2.3), 0.09)
        bar('neon_dim', P(R - 0.65, a0 + 1, 18.2), P(R - 0.65, a1 - 1, 18.2), 0.08)
        # rib at each corner, running up and over to the ceiling ring
        c0, c1 = a0 - 1.4, a0 + 1.4
        K.loft('armor', [P(R, c0, 0), P(R - 2.6, c0, 0), P(R - 2.6, c1, 0), P(R, c1, 0)],
               [P(R, c0, 30), P(R - 1.4, c0, 30), P(R - 1.4, c1, 30), P(R, c1, 30)])
        K.loft('armor', [P(R, c0, 30), P(R - 1.4, c0, 30), P(R - 1.4, c1, 30), P(R, c1, 30)],
               [P(R - 12, c0, HT), P(R - 15, c0, HT - 1.8), P(R - 15, c1, HT - 1.8), P(R - 12, c1, HT)])
        K.loft('armor', [P(R - 12, c0, HT), P(R - 15, c0, HT - 1.8), P(R - 15, c1, HT - 1.8), P(R - 12, c1, HT)],
               [P(9, c0 - 3, HT), P(9, c0 - 3, HT - 1.8), P(9, c1 + 3, HT - 1.8), P(9, c1 + 3, HT)])
        bar('neon', P(R - 2.62, a0, 3.0), P(R - 1.45, a0, 29.6), 0.1)
        bar('neon', P(R - 1.5, a0, 30.3), P(R - 14.6, a0, HT - 1.9), 0.1)
        K.box('orange', P(R - 2.7, a0, 1.6), (0.3, 0.3, 0.3))
        # catwalk rings with railings
        for z in (12.0, 24.0):
            arc_box('hull_lt', R - 3.6, R, a0, a1, z - 0.4, z)
            bar('neon', P(R - 3.66, a0 + 0.5, z - 0.25), P(R - 3.66, a1 - 0.5, z - 0.25), 0.07)
            for q in range(4):
                K.box('steel', P(R - 3.5, a0 + (q + 0.5) * step / 4, z + 0.55), (0.08, 0.08, 1.1))
            bar('steel', P(R - 3.5, a0, z + 1.1), P(R - 3.5, a1, z + 1.1), 0.04)
            bar('steel', P(R - 3.5, a0, z + 0.6), P(R - 3.5, a1, z + 0.6), 0.04)
        # wall dressing per facet: screens, pipes, lockers, lit windows
        k = i % 4
        if k == 0:
            arc_box('screen_bg', R - 0.25, R, am - 7, am + 7, 4.5, 9.5)
            for q in range(9):
                L = rnd.uniform(2, 9)
                s = rnd.uniform(-6, 6 - L)
                bar(rnd.choice(['screen', 'screen_c', 'screen_o']), P(R - 0.3, am + s, 5 + q * 0.5), P(R - 0.3, am + s + L, 5 + q * 0.5), 0.05)
        elif k == 1:
            for q in range(5):
                K.cyl('hull_lt' if q % 2 else 'steel', P(R - 0.6, am - 5 + q * 2.5, 2.6), P(R - 0.6, am - 5 + q * 2.5, 17.5), 0.45, 10)
                K.cyl('dark', P(R - 0.6, am - 5 + q * 2.5, 8), P(R - 0.6, am - 5 + q * 2.5, 8.5), 0.6, 10)
        elif k == 2:
            arc_box('armor', R - 0.5, R, am - 6, am + 6, 12, 16.5)
            arc_box('white_dim', R - 0.56, R - 0.5, am - 5.5, am + 5.5, 13.3, 15.2)
            for q in range(1, 6):
                K.box('armor', P(R - 0.55, am - 5.5 + q * 11 / 6, 14.2), (0.35, 0.35, 2.4))
        else:
            for q in range(3):
                arc_box('crate', R - 2.4, R - 0.2, am - 6 + q * 4.2, am - 2.6 + q * 4.2, 2.6, 6.0 + q % 2)
                K.box('cyan', P(R - 2.45, am - 4.3 + q * 4.2, 5.0), (0.12, 0.5, 0.2))
        # ceiling light segments
        arc_box('white', 18, 21, a0 + 3, a1 - 3, HT - 0.25, HT - 0.15)
        # radial floor seams and inlaid lights
        bar('dark', P(PIT + 1.4, a0, 0.02), P(R - 2.8, a0, 0.02), 0.14)
        for r in (17, 22, 27):
            K.box('cyan' if (i + r) % 3 else 'orange', P(r, a0, 0.03), (0.3, 0.3, 0.06))
    ring(PIT + 1.6, 0.05, 'neon', 0.1, 64, 0.75)
    ring(R - 4.2, 0.04, 'paint_w', 0.1, 96, 0.5)
    ring(22.5, 0.04, 'paint_b', 0.12, 80, 0.6)


def core():
    # base housing down in the pit
    K.cyl('armor', (0, 0, -14), (0, 0, 2.0), 7.5, 16, r1=6.0, smooth=False)
    K.cyl('hull_lt', (0, 0, 2.0), (0, 0, 3.4), 6.0, 16, r1=4.6, smooth=False)
    K.cyl('cyan', (0, 0, 3.4), (0, 0, 3.5), 4.2, 32, smooth=False)
    # plasma column
    K.MATDEF['plasma'] = lambda n: K._emit(n, (0.06, 0.5, 1.0), 3.2)
    K.MATDEF['plasma_core'] = lambda n: K._emit(n, (0.3, 0.8, 1.0), 6.0)
    K.cyl('plasma', (0, 0, 3.4), (0, 0, 28.6), 1.7, 20)
    K.cyl('plasma_core', (0, 0, 3.4), (0, 0, 28.6), 0.7, 12)
    # collars
    for z in (9.0, 16.0, 23.0):
        K.cyl('armor', (0, 0, z - 0.7), (0, 0, z + 0.7), 5.4, 16, smooth=False)
        K.cyl('hull_lt', (0, 0, z - 1.0), (0, 0, z + 1.0), 4.9, 16, smooth=False)
        ring(5.46, z, 'neon', 0.09, 32, 0.6)
        for k in range(8):
            K.box('orange', P(5.45, 22.5 + 45 * k, z + 0.45), (0.2, 0.4, 0.14), rot=22.5 + 45 * k)
    # upper housing hanging from the ceiling
    K.cyl('hull_lt', (0, 0, 28.6), (0, 0, 30.0), 4.6, 16, r1=6.0, smooth=False)
    K.cyl('armor', (0, 0, 30.0), (0, 0, HT), 6.0, 16, r1=9.0, smooth=False)
    K.cyl('cyan', (0, 0, 28.5), (0, 0, 28.6), 4.2, 32, smooth=False)
    for z in (32, 35, 38):
        ring(6.2 + (z - 30) * 0.3, z, 'neon_dim', 0.1, 40, 0.7)
    # triangle containment field: 12 flat facets round the column
    n = 12
    rr = 4.4
    for k in range(n):
        a0, a1 = 360 * k / n, 360 * (k + 1) / n
        p0, p1 = Vector(P(rr, a0, 0)), Vector(P(rr, a1, 0))
        for (zb, zt) in ((3.6, 8.2), (9.8, 15.2), (16.8, 22.2), (23.8, 28.4)):
            K.force_field(f'Cont{k}_{int(zb)}', (p0.x, p0.y, zb), p1 - p0, (0, 0, 1), (p1 - p0).length, zt - zb,
                          tri=(p1 - p0).length, strength=0.6, edge=2.2, alpha=(0.04, 0.25), gap=0.07, seed=k * 7 + int(zb))
    for z, e in ((6, 90000), (13, 120000), (20, 120000), (26, 90000)):
        for a in (0, 120, 240):
            K.point('CoreGlow', P(5.2, a + z * 10, z), e / 16, (0.12, 0.6, 1.0), r=1.5)
    # clamp arms from the walls to the collars
    for k in range(4):
        a = 45 + 90 * k
        for (zc, zw) in ((16.0, 21.0),):
            c0, c1 = a - 3.0, a + 3.0
            K.loft('armor', [P(R, c0, zw - 2.5), P(R, c1, zw - 2.5), P(R, c1, zw + 2.5), P(R, c0, zw + 2.5)],
                   [P(5.2, a - 12, zc - 0.9), P(5.2, a + 12, zc - 0.9), P(5.2, a + 12, zc + 0.9), P(5.2, a - 12, zc + 0.9)])
            bar('neon', P(R - 0.5, a, zw - 2.6), P(5.6, a, zc - 1.0), 0.12)
            K.box('hull_lt', P(18, a, (zc + zw) / 2 + 0.3), (5.0, 3.6, 3.8), rot=a)
            K.box('orange', P(18, a, (zc + zw) / 2 - 1.75), (1.0, 0.5, 0.12), rot=a)
            K.cyl('steel', P(R - 1, a - 6, zw - 6), P(9, a - 6, 30.5), 0.3, 8)
            K.cyl('steel', P(R - 1, a + 6, zw - 6), P(9, a + 6, 30.5), 0.3, 8)
    # six injector towers on the ring deck firing thin beams into the core
    for k in range(6):
        a = 60 * k
        b, t = Vector(P(15.5, a, 0)), Vector(P(11.5, a, 11.5))
        K.cyl('armor', b, b + Vector((0, 0, 1.6)), 2.4, 6, smooth=False)
        K.cyl('hull_lt', b + Vector((0, 0, 1.6)), b + Vector((0, 0, 2.2)), 2.0, 6, smooth=False)
        K.cyl('armor', b + Vector((0, 0, 2.2)), t, 1.3, 4, r1=0.7, smooth=False)
        d = (Vector((0, 0, 13)) - t).normalized()
        K.cyl('steel', t, t + d * 2.2, 0.5, 8, r1=0.3)
        K.cyl('cyan_hot', t + d * 2.2, (0, 0, 13), 0.07, 6)
        K.cyl('cyan_hot', t + d * 2.0, t + d * 2.3, 0.4, 8)
        bar('neon', b + Vector((0, 0, 2.6)) + (t - b).normalized() * 0.5 - Vector(P(1.0, a, 0)) * 0.9,
            t - Vector(P(1.0, a, 0)) * 0.55, 0.08)
        ring_pts = 12
        for q in range(ring_pts):
            bar('hazard', (b.x + 3.1 * math.cos(2 * math.pi * q / ring_pts), b.y + 3.1 * math.sin(2 * math.pi * q / ring_pts), 0.03),
                (b.x + 3.1 * math.cos(2 * math.pi * (q + 1) / ring_pts), b.y + 3.1 * math.sin(2 * math.pi * (q + 1) / ring_pts), 0.03), 0.14)
        K.pipe('hull_lt', [P(17.9, a, 0.5), P(R - 2.4, a, 0.5)], 0.4, 8)
        K.box('orange', (t.x, t.y, t.z + 0.6), (0.4, 0.4, 0.25))
    # pit glow far below
    K.cyl('plasma', (0, 0, -13.9), (0, 0, -13.8), 11.0, 24, smooth=False) if False else None
    ring(10.6, -6, 'cyan', 0.2, 32, 0.7)
    ring(10.6, -11, 'cyan', 0.2, 32, 0.7)
    K.point('PitGlow', (8, 0, -9), 30000, (0.2, 0.7, 1.0), r=2.0)
    K.point('PitGlow', (-8, 0, -9), 30000, (0.2, 0.7, 1.0), r=2.0)


def deck_props():
    # entry causeway markings (camera side, -Y)
    for s in (-1, 1):
        K.box2('paint_w', (s * 7.0 - 0.12, -R + 2, 0.0), (s * 7.0 + 0.12, -PIT - 1.4, 0.02))
        K.box2('neon', (s * 8.0 - 0.07, -R + 2, 0.02), (s * 8.0 + 0.07, -PIT - 1.4, 0.07))
    for y in range(-30, -14, 4):
        for s in (-1, 1):
            K.box('paint_y', (s * 2.4, y, 0.02), (0.45, 3.6, 0.02), rot=s * 38)
    # railing round the pit with gaps
    for i in range(48):
        a = 360 * i / 48
        if 255 < a < 285:
            pass
        K.box('steel', P(PIT + 0.3, a, 0.9), (0.1, 0.1, 1.2))
    ring(PIT + 0.3, 1.5, 'steel', 0.05, 48, 1.0)
    ring(PIT + 0.3, 1.0, 'steel', 0.05, 48, 1.0)
    # control consoles facing the core
    for a in (232, 308, 200, 340, 110, 70):
        p = P(PIT + 3.4, a, 0)
        K.box('armor', (p[0], p[1], 0.6), (3.6, 1.4, 1.2), rot=a + 90)
        K.box('screen_c', (p[0], p[1], 1.24), (3.0, 0.8, 0.05), rot=a + 90)
        q = P(PIT + 4.0, a, 0)
        K.box('armor', (q[0], q[1], 1.3), (3.6, 0.3, 2.2), rot=a + 90)
        qq = P(PIT + 3.83, a, 0)
        K.box('screen_bg', (qq[0], qq[1], 1.75), (3.2, 0.04, 1.0), rot=a + 90)
        K.box('screen_o' if a in (232, 308) else 'screen', (qq[0] * 0.999, qq[1] * 0.999, 1.9), (2.2, 0.04, 0.1), rot=a + 90)
    # crates, barrels, coolant tanks
    for (r, a) in [(28, 238), (29, 246), (28.5, 300), (27, 197), (29, 163), (28, 20), (29, 340)]:
        p = P(r, a, 1.2)
        K.crate(p, kind=rnd.choice(['crate', 'crate_b', 'crate_o']), rot=a + rnd.uniform(-10, 10))
        if rnd.random() < 0.6:
            K.crate(P(r - 0.2, a + 5.5, 1.1), (2.2, 2.2, 2.2), kind='crate', rot=a)
        for k in range(rnd.randint(1, 3)):
            K.barrel(P(r - 2.5, a - 3 - k * 2.2, 0), mat_=rnd.choice(['crate_b', 'crate_o']))
    for a in (215, 325, 145, 35):
        p = P(26.5, a, 0)
        K.cyl('hull_lt', (p[0], p[1], 0.4), (p[0], p[1], 7.5), 2.4, 16)
        K.cyl('armor', (p[0], p[1], 0), (p[0], p[1], 0.5), 2.8, 8, smooth=False)
        K.cyl('armor', (p[0], p[1], 7.5), (p[0], p[1], 8.2), 2.5, 8, r1=1.2, smooth=False)
        for z in (2, 4, 6):
            K.cyl('dark', (p[0], p[1], z), (p[0], p[1], z + 0.25), 2.5, 16)
        K.cyl('cyan', (p[0], p[1], 3.0), (p[0], p[1], 3.5), 2.44, 16)


def detail():
    """Film-set pass: dressed wall facets, catwalk stations and ladders, looms, conduits, props, drones."""
    step = 360 / N
    chord = 2 * (R - 0.05) * math.sin(math.radians(step / 2))
    for i in range(N):
        a0 = i * step - step / 2
        am = a0 + step / 2
        o = P(R - 0.05, a0)
        k = i % 4
        zones = [(19.2, 23.4), (24.6, 30.8)]
        if k == 2:
            zones.append((2.7, 11.4))
        if k == 3:
            zones.append((7.2, 11.4))
        if k in (0, 3):
            zones.append((12.3, 17.4))
        if k == 0:
            zones.append((9.9, 11.4))
        for j, (za, zb) in enumerate(zones):
            D.dress_wall((o[0], o[1]), am + 90, chord, za, zb, seed=i * 7 + j, cell=(2.6, 2.3 if zb - za < 6 else 2.9))
        # catwalk furniture
        for z in (12.0, 24.0):
            if (i + (z > 20)) % 2 == 0:
                pc = P(R - 1.5, am, z)
                D.crew_station(pc, am - 90, 3.0, ['screen', 'screen_c', 'screen_o'][i % 3], seed=i + int(z))
            else:
                pc = P(R - 1.2, am + 3, z + 0.8)
                K.crate(pc, (1.4, 1.4, 1.6), 'crate', rot=am)
            K.prism('armor', [(0, 0)] * 3, 0, 0) if False else None
            b0, b1 = P(R - 0.2, a0 + 2.2, z - 3.0), P(R - 3.4, a0 + 2.2, z - 0.45)
            bar('armor', b0, b1, 0.16)
            bar('armor', P(R - 0.2, a0 + step - 2.2, z - 3.0), P(R - 3.4, a0 + step - 2.2, z - 0.45), 0.16)
            for q in range(4):
                K.box('orange' if q % 2 else 'cyan', P(R - 3.7, a0 + (q + 0.5) * step / 4, z - 0.2), (0.12, 0.4, 0.1), rot=am)
        if i % 4 == 1:
            lb = P(R - 3.9, am - 6, 0)
            D.ladder((lb[0], lb[1], 0), am + 90, 11.6)
            lb = P(R - 3.9, am + 6, 12)
            D.ladder((lb[0], lb[1], 12.0), am + 90, 11.6)
        # looms sagging between the catwalk levels and from the roof ribs
        D.cable_loom(P(R - 3.4, a0 + 1.5, 23.4), P(R - 3.4, a0 + step - 1.5, 23.4), n=3, sag=1.8, r=0.06, seed=i)
        if i % 2 == 0:
            D.cable_loom(P(R - 13, a0, HT - 2.2), P(7.5, a0 + step, 33.0), n=5, sag=3.0, r=0.08, seed=20 + i)
            D.cable_loom(P(R - 1.2, am, 31.0), P(R - 9, am, HT - 1.2), n=4, sag=1.6, r=0.07, seed=40 + i)
        # wall wash
        K.area('Wash', P(R - 4.6, am, 1.2), (8.0, 0.5), 2200, (0.3, 0.6, 1.0), rot=(55, 0, am - 90), spread=150)
        K.area('WashHi', P(R - 5.0, am, 25.6), (8.0, 0.5), 3200, (0.3, 0.6, 1.0), rot=(60, 0, am - 90), spread=150)
    # core dressing: conduits up the base housing, collar indicator rows, vent rings
    for k in range(16):
        a = 22.5 * k
        K.cyl('hull_lt' if k % 2 else 'steel', P(6.6, a, -3.0), P(5.2, a, 3.2), 0.22, 8)
        K.box('dark', P(6.25, a, 0.6), (0.7, 0.7, 0.4), rot=a)
        for z in (9.0, 16.0, 23.0):
            K.box('cyan' if k % 4 else 'orange', P(5.47, a + 11, z - 0.45), (0.06, 0.5, 0.12), rot=a + 11)
            K.box('dark', P(5.2, a, z + 1.15), (0.9, 1.0, 0.3), rot=a)
        K.box('dark', P(8.2 - 0.0, a, 34.0), (0.5, 1.6, 2.6), rot=a)
        K.box('neon_dim', P(8.5, a + 6, 36.5), (0.08, 0.3, 1.6), rot=a + 6)
    for k in range(8):
        a = 45 * k + 22.5
        K.cyl('crate_o' if k % 2 else 'crate_b', P(6.9, a, 30.4), P(5.6, a, 23.9), 0.16, 6)
        K.cyl('rubber', P(6.9, a + 5, 30.4), P(5.6, a + 5, 23.9), 0.1, 6)
    # clamp arms: service catwalk + rail + conduits along each
    for k in range(4):
        a = 45 + 90 * k
        p0, p1 = Vector(P(R - 1, a - 3.5, 23.6)), Vector(P(7.0, a - 14, 17.3))
        bar('steel', p0, p1, 0.12)
        bar('crate_o', p0 + Vector((0, 0, -4.9)), p1 + Vector((0, 0, -2.0)), 0.14)
        for q in range(8):
            pp = p0 + (p1 - p0) * ((q + 0.5) / 8)
            K.box('orange' if q % 2 else 'cyan', (pp.x, pp.y, pp.z + 0.2), (0.3, 0.3, 0.14))
    # ring deck: stations, trenches, racks, loader, drones, umbilicals to the guard tanks
    for a in (232, 308, 200, 340, 110, 70):
        pc = P(PIT + 6.3, a, 0)
        D.seat(pc, a + 90)
    for k in range(8):
        a = 22.5 + 45 * k
        p0, p1 = P(PIT + 2.2, a, 0), P(R - 3.2, a, 0)
        K.box('dark', P((PIT + R) / 2 - 0.5, a, 0.012), (R - PIT - 5.4, 0.8, 0.024), rot=a)
        K.box('neon_dim', P((PIT + R) / 2 - 0.5, a, 0.03), (R - PIT - 5.4, 0.08, 0.02), rot=a)
        for q in range(int((R - PIT - 5.4) / 0.4)):
            K.box('steel', P(PIT + 2.9 + q * 0.4, a, 0.045), (0.06, 0.8, 0.03), rot=a)
    D.chevrons((0, -27.5, 0), 90, n=4, s=1.5)
    D.chevrons((-4.5, -24, 0), 90, n=2, s=0.9, mat='paint_w')
    D.chevrons((4.5, -24, 0), 90, n=2, s=0.9, mat='paint_w')
    for (r_, a, kind) in [(25.5, 252, 'fuel'), (25.5, 288, 'cart'), (24.5, 222, 'ammo'), (24.5, 318, 'fuel'), (20.5, 178, 'cart'),
                          (21.0, 5, 'fuel'), (26, 95, 'cart'), (25, 128, 'fuel'), (26, 60, 'ammo')]:
        pc = P(r_, a, 0)
        if kind == 'fuel':
            D.fuel_rack(pc, a + 90, n=3)
        elif kind == 'cart':
            D.tool_cart(pc, a + 70, seed=int(a))
        else:
            D.ammo_rack(pc, a + 90, rows=2, cols=5, seed=int(a))
    lp = P(21.5, 212, 0)
    D.loader_arm(lp, 212 + 110, reach=5.0, lift=5.0, seed=3)
    lp = P(20.5, 330, 0)
    D.loader_arm(lp, 330 + 90, reach=4.5, lift=6.0, seed=4, load=False)
    D.umbilical((12.5, -21.0, 0), (9.8, -19.3, 1.5), seed=1)
    D.umbilical((-13.5, -18.5, 0), (-11.0, -16.6, 1.5), seed=2)
    D.drone((6.5, -9.5, 9.0), 150, s=1.3, beam=(3.5, -4.0, 9.0))
    D.drone((-8.5, -8.0, 14.5), 210, s=1.2, beam=(-4.0, -3.5, 16.0))
    D.drone((11.0, -3.0, 20.0), 120, s=1.2, beam=(5.0, 0, 23.0))
    D.drone((-14.0, -19.0, 6.0), 20, s=1.1, beam=(-11.0, -15.5, 2.5))
    # injector towers: hazard bands, indicator ladders, coolant feed
    for k in range(6):
        a = 60 * k
        b, t = Vector(P(15.5, a, 0)), Vector(P(11.5, a, 11.5))
        d = t - (b + Vector((0, 0, 2.2)))
        for f_ in (0.2, 0.5, 0.8):
            c = b + Vector((0, 0, 2.2)) + d * f_
            K.cyl('hazard' if f_ == 0.5 else 'hull_lt', c - d.normalized() * 0.25, c + d.normalized() * 0.25, 1.35 - 0.55 * f_, 4, smooth=False)
        out = Vector(P(1.0, a, 0))
        for q in range(7):
            c = b + Vector((0, 0, 3.0)) + d * (q / 8) + out * (1.05 - 0.4 * q / 8)
            K.box('orange' if q % 3 == 0 else 'cyan', tuple(c), (0.1, 0.4, 0.14), rot=a)
        K.cyl('crate_b', b + out * 1.9 + Vector((0, 0, 0.3)), t + out * 0.7, 0.14, 6)
        K.cyl('rubber', b + out * 1.7 + Vector((0.3, 0.3, 0.3)), t + out * 0.6, 0.09, 6)


def main():
    K.E.update(neon=1.1, cyan=1.0, orange=2.2, white=0.8)
    K.MATDEF['neon'] = lambda n: K._emit(n, (0.012, 0.19, 1.0), 4.8)
    K.MATDEF['neon_dim'] = lambda n: K._emit(n, (0.012, 0.19, 1.0), 2.2)
    sc, cam = K.reset(samples=int(A.get('samples', 20)), exposure=float(A.get('exposure', 0.5)))
    K.space_world(sc)
    chamber()
    core()
    deck_props()
    detail()
    K.flush()
    for i in range(N):
        a = (i + 0.5) * 360 / N - 360 / N / 2
        if i % 2 == 0:
            K.area('Ceil', P(19.5, a, HT - 0.5), (3, 6), 6000, (0.6, 0.8, 1.0), rot=(0, 0, a), spread=150)
    K.spot('Fore', (0, -30, 16), (0, -22, 0), 16000, (0.75, 0.88, 1.0), angle=90, blend=0.7, r=1.0)
    K.tank('bulwark', (9.5, -17.5, 0), rz=105)
    K.tank('lancer', (-10.5, -15.0, 0), rz=65)
    K.tank('javelin', (-21.5, 6, 0), rz=-20)
    K.look(cam, (-4.2, -32.4, 3.8), (0.8, 0, 13.0), lens=16)
    raw = os.path.join(OUT, '_raw', NAME + '.png')
    K.render(sc, raw, RES, depth_far=75.0)
    K.post(raw, A.get('final', os.path.join(OUT, NAME + '.jpg')), haze=float(A.get('haze', 0.35)),
           scatter=float(A.get('scatter', 0.12)), haze_col=(0.06, 0.3, 0.6))


main()
