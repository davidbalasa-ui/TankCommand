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
    K.MATDEF['plasma'] = lambda n: K._emit(n, (0.1, 0.65, 1.0), 4.0)
    K.MATDEF['plasma_core'] = lambda n: K._emit(n, (0.5, 0.9, 1.0), 8.0)
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


def main():
    K.E.update(neon=1.1, cyan=1.0, orange=2.0, white=0.8)
    sc, cam = K.reset(samples=int(A.get('samples', 20)), exposure=float(A.get('exposure', 0.5)))
    K.space_world(sc)
    chamber()
    core()
    deck_props()
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
