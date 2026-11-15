"""Terran capital ship - bridge / command deck with a big forward window (concept still, pass 2).

    python terran_bridge.py [--out=DIR] [--name=bridge] [--res=960x540] [--samples=20] [--final=PATH.jpg]

Vehicle-scale command deck: 60 m wide, 75 m deep, 28 m high. A rear upper tier (z = 3) carries the
command dais, a prow-shaped balcony that juts over the main deck; two 10 m ramps lead down either
side of it. The hero of the room is the central holo table under a ceiling projector ring. A raised
wrap-around console tier follows the angled line of the panoramic window; two different large
stations (tactical wall, sensor globe) stand on the main deck. Outside: the ship's own bow, big
Terran ships close by, a starfield and a few beams (placeholder backdrop).
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'art', 'v2'))
import terran_interior_kit as K  # noqa: E402
import terran_detail_kit as D  # noqa: E402

A = K.args()
OUT = A.get('out', '/home/user/work/terran-interiors')
NAME = A.get('name', 'bridge')
RES = tuple(int(v) for v in A.get('res', '960x540').split('x'))

W2 = 30.0
YB, YT, YW = -30.0, -8.0, 45.0        # rear wall, tier front edge, window
HT = 28.0
TIER = 3.0
PLAT = 1.2                            # height of the wrap-around console tier by the window
rnd = random.Random(5)
SCREENS = ['screen', 'screen_c', 'screen', 'screen_o']


def bar(mat, p0, p1, r):
    K.cyl(mat, p0, p1, r, n=4, smooth=False)


def frame(c, rot):
    """Local -> world placement helper for things built at an angle about Z."""
    R = K._rot(rot)

    def at(dx, dy, dz):
        v = R @ Vector((dx, dy, 0))
        return (c[0] + v.x, c[1] + v.y, c[2] + dz)
    return at


def screen_x(x, y, z, w, h, face, seed=0):
    """Wall display in the YZ plane at x, facing `face` (+1 / -1 along X). Abstract graphics only."""
    r = random.Random(seed)
    K.box('armor', (x, y, z), (0.4, w + 0.8, h + 0.8))
    K.box('screen_bg', (x + face * 0.21, y, z), (0.04, w, h))
    xx = x + face * 0.25
    for i in range(int(h / 0.5)):
        if r.random() < 0.6:
            L = r.uniform(0.15, 0.6) * w
            K.box(r.choice(SCREENS), (xx, y - w / 2 + 0.3 + L / 2 + r.uniform(0, w - L - 0.6), z - h / 2 + 0.3 + i * 0.5),
                  (0.02, L, 0.14))
    for k in range(2):
        cy, cz = y + r.uniform(-w * 0.3, w * 0.3), z + r.uniform(-h * 0.2, h * 0.2)
        rr = r.uniform(0.8, 1.6)
        for q in range(16):
            a0, a1 = 2 * math.pi * q / 16, 2 * math.pi * (q + 0.7) / 16
            bar('screen_c', (xx, cy + rr * math.cos(a0), cz + rr * math.sin(a0)),
                (xx, cy + rr * math.cos(a1), cz + rr * math.sin(a1)), 0.035)


def console(c, rot=0.0, w=4.0, col='screen', big=1.0):
    """Single console: plinth, sloped screen, back riser. The operator stands on its local -Y side."""
    at = frame(c, rot)
    K.box('armor', at(0, 0, 0.55 * big), (w, 1.6 * big, 1.1 * big), rot)
    K.box('hull_lt', at(0, -0.15 * big, 1.18 * big), (w - 0.1, 1.2 * big, 0.16), (18, 0, rot))
    K.box(col, at(0, -0.17 * big, 1.28 * big), (w - 0.5, 0.8 * big, 0.04), (18, 0, rot))
    K.box('armor', at(0, 0.7 * big, 1.0 * big), (w, 0.3, 1.6 * big), rot)
    K.box('screen_bg', at(0, 0.53 * big, 1.45 * big), (w - 0.4, 0.04, 0.6 * big), rot)
    K.box('neon', at(0, -0.82 * big, 0.2), (w - 0.2, 0.05, 0.08), rot)
    K.box('orange', at(w / 2 - 0.3, -0.82 * big, 0.9 * big), (0.18, 0.05, 0.1), rot)


def desk_run(a, b, z, seed=0, fin_every=3):
    """One long wrap-around console between two points (operators on the right-hand side of a->b,
    low back riser on the left so it never hides the window), with taller screen fins at intervals."""
    r = random.Random(seed)
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    d = b - a
    L = d.length
    ang = math.degrees(math.atan2(d.y, d.x))
    mid = (a + b) / 2
    at = frame((mid.x, mid.y, z), ang)
    K.box('armor', at(0, 0, 0.6), (L, 2.0, 1.2), ang)
    K.box('armor', at(0, 0.85, 1.05), (L, 0.35, 2.1), ang)
    K.box('neon', at(0, -1.03, 0.22), (L - 0.3, 0.05, 0.1), ang)
    K.box('neon_dim', at(0, 1.04, 1.9), (L - 0.3, 0.05, 0.08), ang)
    n = max(1, round(L / 3.4))
    seg = L / n
    for i in range(n):
        x = -L / 2 + (i + 0.5) * seg
        col = SCREENS[(i + seed) % 4]
        K.box('hull_lt', at(x, -0.2, 1.3), (seg - 0.25, 1.5, 0.18), (16, 0, ang))
        K.box(col, at(x, -0.22, 1.41), (seg - 0.9, 1.0, 0.04), (16, 0, ang))
        K.box('screen_bg', at(x, 0.66, 1.62), (seg - 0.5, 0.04, 0.7), ang)
        for k in range(2):
            w = r.uniform(0.25, 0.7) * (seg - 1.0)
            K.box(r.choice(SCREENS), at(x - (seg - 1.0) / 2 + w / 2 + r.uniform(0, seg - 1.0 - w), 0.63, 1.45 + k * 0.3),
                  (w, 0.02, 0.08), ang)
        K.box('orange' if i % 2 else 'cyan', at(x + seg / 2 - 0.3, -1.03, 0.85), (0.22, 0.05, 0.12), ang)
        for row in range(2):
            for q in range(int((seg - 0.9) / 0.16)):
                if r.random() < 0.8:
                    K.box(r.choice(['screen', 'screen_c', 'screen_o', 'dark']), at(x - (seg - 0.9) / 2 + q * 0.16 + 0.08, -0.86 + row * 0.14, 1.19 + row * 0.04),
                          (0.09, 0.08, 0.02), (16, 0, ang))
        D.seat(at(x, -2.0, 0), ang)
        K.cyl('steel', at(x - 0.5, 0.6, 2.1), at(x - 0.5, 0.75, 2.9), 0.04, 6)
        K.box('armor', at(x - 0.5, 0.8, 3.2), (1.3, 0.08, 0.8), ang)
        K.box('screen_bg', at(x - 0.5, 0.75, 3.2), (1.15, 0.02, 0.66), ang)
        K.box(col, at(x - 0.5, 0.735, 3.3), (0.8, 0.015, 0.06), ang)
        K.box('screen_o' if i % 3 == 0 else 'screen_c', at(x - 0.7, 0.735, 3.08), (0.5, 0.015, 0.05), ang)
    for i in range(0, n + 1, fin_every):
        x = -L / 2 + i * seg
        K.box('armor', at(x, 0.35, 1.6), (0.6, 2.4, 3.2), ang, taper=(1, 0.55))
        K.box('orange', at(x, -0.32, 2.7), (0.62, 0.08, 0.3), ang)
        K.box('screen_bg', at(x + 0.31 * (1 if i < n else -1), 0.3, 2.2), (0.04, 1.2, 1.2), ang)


def shell():
    K.box2('floor', (-W2 - 2, YT - 0.5, -1), (W2 + 2, YW + 8, 0))            # main deck
    K.box2('floor', (-W2 - 2, YB - 2, -1), (W2 + 2, YT, TIER))                # upper tier
    K.box2('hull_big', (-W2 - 2, YB - 2, HT), (W2 + 2, YW + 10, HT + 2))       # ceiling
    K.box2('hull_big', (-W2 - 2, YB - 2, 0), (W2 + 2, YB, HT))                # rear wall
    slope = math.degrees(math.atan2(TIER, 13.8))
    for s in (-1, 1):
        K.box2('hull_big', (s * W2, YB, 0), (s * (W2 + 2), 34, HT))
        K.prism('armor', [(s * W2, 0), (s * (W2 - 1.8), 0), (s * (W2 - 1.0), 1.5), (s * W2, 2.8)], YT, 34)
        # tier riser + low armoured parapet either side of the ramp
        for (x0, x1) in ((9.0, 12.5), (23.5, W2)):
            lo, hi = min(s * x0, s * x1), max(s * x0, s * x1)
            K.box2('armor', (lo, YT - 0.4, 0), (hi, YT + 0.25, TIER + 1.15))
            K.box2('neon', (lo, YT + 0.25, TIER - 0.4), (hi, YT + 0.31, TIER - 0.24))
            K.box2('hazard', (lo, YT + 0.25, 0.0), (hi, YT + 0.29, 0.7))
            K.box('orange', ((lo + hi) / 2, YT + 0.27, TIER + 0.8), (hi - lo - 0.8, 0.06, 0.1))
        # ramp (10 m wide) with cheeks, tread bars and marker lights
        K.prism('floor_dk', [(YT - 0.4, 0), (YT - 0.4, TIER), (YT + 0.2, TIER), (YT + 14, 0)], s * 13.0, s * 23.0, axis='x')
        for xc in (12.75, 23.25):
            K.prism('armor', [(YT - 0.4, 0), (YT - 0.4, TIER + 1.15), (YT + 1.5, TIER + 1.15), (YT + 14.6, 0.9), (YT + 14.6, 0)],
                    s * (xc - 0.3), s * (xc + 0.3), axis='x')
            bar('neon', (s * xc, YT + 1.6, TIER + 1.24), (s * xc, YT + 14.5, 0.99), 0.07)
            K.box('orange', (s * xc, YT + 14.7, 0.6), (0.6, 0.1, 0.3))
        for k in range(7):
            y = YT + 1.4 + k * 1.9
            z = TIER * (1 - (y - YT - 0.2) / 13.8)
            K.box('steel', (s * 18, y, z + 0.02), (9.6, 0.14, 0.06), (-slope, 0, 0))
            for sx in (13.7, 22.3):
                K.box('orange' if k % 2 else 'cyan', (s * sx, y + 0.9, z - 0.17), (0.4, 0.5, 0.08), (-slope, 0, 0))
        K.box2('hazard', (min(s * 13, s * 23), YT - 2.0, TIER), (max(s * 13, s * 23), YT - 1.0, TIER + 0.03))


def dais():
    """Command dais: a prow-shaped balcony off the upper tier, 0.8 m above it, jutting over the main
    deck, with crew stations on its edges and the command throne on a swivel plinth."""
    z1 = TIER + 0.8
    pts = [(-9, YT - 7), (9, YT - 7), (9, YT), (4.5, YT + 11), (-4.5, YT + 11), (-9, YT)]
    K.prism('armor', pts, 0, z1, axis='z')
    K.prism('floor_dk', [(p[0] * 0.92, YT - 7 + (p[1] - YT + 7) * 0.95 + 0.2) for p in pts], z1, z1 + 0.06, axis='z')
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if a[1] < YT - 1 and b[1] < YT - 1:
            continue
        bar('neon', (a[0], a[1], z1 - 0.35), (b[0], b[1], z1 - 0.35), 0.1)
        bar('neon_dim', (a[0], a[1], 1.2), (b[0], b[1], 1.2), 0.07)
        bar('armor', (a[0], a[1], 2.4), (b[0], b[1], 2.4), 0.3)
        d = Vector((b[0] - a[0], b[1] - a[1], 0))
        for q in range(int(d.length / 1.2)):
            pp = Vector((a[0], a[1], 0)) + d * ((q + 0.5) / int(d.length / 1.2))
            K.box('orange' if q % 3 == 0 else 'dark', (pp.x, pp.y, 1.8), (0.3, 0.3, 0.14))
    K.box('hazard', (0, YT + 11.03, 0.5), (8.6, 0.06, 1.0))
    for k in range(3):
        K.box2('armor', (-5, YT - 7.9 - k * 0.7, TIER), (5, YT - 7.0 - k * 0.7, z1 - (k + 1) * 0.2))
    D.crew_station((0, YT + 9.4, z1), 0, 4.6, 'screen_o', seed=1)
    D.crew_station((6.0, YT + 5.0, z1), -68, 4.6, 'screen_c', seed=2)
    D.crew_station((-6.0, YT + 5.0, z1), 68, 4.6, 'screen', seed=3)
    # --- command throne
    cx, cy = 0.0, YT + 0.2
    K.cyl('armor', (cx, cy, z1), (cx, cy, z1 + 0.45), 3.0, 8, smooth=False)
    K.cyl('hull_lt', (cx, cy, z1 + 0.45), (cx, cy, z1 + 0.65), 2.5, 8, smooth=False)
    for i in range(20):
        a0, a1 = 2 * math.pi * i / 20, 2 * math.pi * (i + 0.7) / 20
        bar('neon', (cx + 3.05 * math.cos(a0), cy + 3.05 * math.sin(a0), z1 + 0.25), (cx + 3.05 * math.cos(a1), cy + 3.05 * math.sin(a1), z1 + 0.25), 0.06)
    zt = z1 + 0.65
    D.seat((cx, cy + 0.2, zt), 0, s=1.7, mat='hull_lt')
    K.box('armor', (cx, cy - 1.15, zt + 2.3), (2.4, 0.6, 4.6), taper=(0.5, 1.0))            # high back
    K.box('hull', (cx, cy - 1.5, zt + 1.6), (3.2, 0.5, 3.2), taper=(0.6, 1.0))
    K.box('neon', (cx, cy - 1.77, zt + 2.2), (0.16, 0.05, 3.0))
    for sd in (-1, 1):
        K.box('armor', (cx + sd * 1.55, cy - 0.5, zt + 1.5), (0.35, 2.0, 3.0), rot=sd * 14, taper=(1.0, 0.45))   # wings
        K.box('neon', (cx + sd * 1.76, cy - 0.45, zt + 1.6), (0.05, 0.12, 2.2), rot=sd * 14)
        K.box('armor', (cx + sd * 1.25, cy + 0.6, zt + 0.75), (0.6, 2.0, 0.9))                              # arm consoles
        K.box('screen_c' if sd > 0 else 'screen_o', (cx + sd * 1.25, cy + 0.7, zt + 1.22), (0.44, 1.5, 0.03))
        for q in range(8):
            K.box(['orange', 'cyan', 'neon'][q % 3], (cx + sd * 1.25, cy - 0.2 + q * 0.16, zt + 1.24), (0.3, 0.07, 0.03))
        K.cyl('steel', (cx + sd * 1.3, cy + 1.6, zt + 1.2), (cx + sd * 1.7, cy + 2.0, zt + 2.0), 0.05, 6)          # swing monitor
        K.box('armor', (cx + sd * 1.8, cy + 2.05, zt + 2.3), (1.3, 0.08, 0.8), rot=-sd * 28)
        K.box('screen_bg', (cx + sd * 1.78, cy + 2.0, zt + 2.3), (1.16, 0.03, 0.66), rot=-sd * 28)
        K.box('screen_c', (cx + sd * 1.77, cy + 1.975, zt + 2.42), (0.8, 0.02, 0.06), rot=-sd * 28)
        K.box('screen_o', (cx + sd * 1.77, cy + 1.975, zt + 2.2), (0.5, 0.02, 0.06), rot=-sd * 28)
        K.box('orange', (cx + sd * 1.0, cy - 1.2, zt + 4.3), (0.3, 0.7, 0.1))
        # flanking status pylons with indicator ladders
        K.box('armor', (sd * 7.6, YT - 3.5, z1 + 1.3), (1.2, 1.2, 2.6), taper=(0.6, 0.6))
        K.box('neon', (sd * 7.6, YT - 2.88, z1 + 1.2), (0.12, 0.05, 1.8))
        for q in range(5):
            K.box('orange' if q % 2 else 'cyan', (sd * 7.6 - sd * 0.62, YT - 3.5, z1 + 0.6 + q * 0.35), (0.04, 0.5, 0.12))
    K.box('armor', (cx, cy - 0.9, zt + 4.75), (2.6, 2.2, 0.3), rot=(12, 0, 0), taper=(0.8, 0.8))            # canopy
    K.box('slot', (cx, cy - 0.6, zt + 4.55), (1.6, 0.9, 0.04), rot=(12, 0, 0))
    D.cable_loom((cx - 1.2, cy - 1.8, zt + 0.3), (cx - 4.5, cy - 5.5, z1 + 0.1), n=4, sag=0.2, r=0.05, seed=4)
    # back of the throne (what the camera sees): status panel, indicator rows, vents
    K.box('screen_bg', (cx, cy - 1.77, zt + 0.9), (2.0, 0.04, 0.9))
    for q in range(4):
        K.box(SCREENS[q], (cx - 0.5 + q * 0.2, cy - 1.8, zt + 0.7 + q * 0.14), (0.9, 0.02, 0.06))
    for sd in (-1, 1):
        for q in range(6):
            K.box('orange' if q % 2 else 'cyan', (cx + sd * 0.7, cy - 1.78, zt + 1.7 + q * 0.3), (0.3, 0.03, 0.1))
    K.spot('ThroneKey', (cx - 4, cy - 4, 23), (cx, cy, zt + 2), 14000, (0.6, 0.8, 1.0), angle=38, blend=0.6, r=0.6)
    # upper tier either side of the dais: two rows of crew stations, a plotting table, racks at the rear wall
    for sd in (-1, 1):
        for row, y in enumerate((-13.5, -19.5)):
            for q in range(3):
                D.crew_station((sd * (13.0 + q * 4.6), y, TIER), 0, 3.4, SCREENS[(row + q) % 4], seed=50 + row * 3 + q + (sd > 0) * 9)
            D.floor_trench((sd * 11.0, y - 2.4) + (0,), (sd * 25.0, y - 2.4) + (0,), w=0.6) if False else None
            K.box('dark', (sd * 18.0, y - 2.3, TIER + 0.012), (14.0, 0.6, 0.024))
            K.box('neon_dim', (sd * 18.0, y - 2.3, TIER + 0.03), (14.0, 0.08, 0.02))
        K.cyl('armor', (sd * 17.5, -25.5, TIER), (sd * 17.5, -25.5, TIER + 0.95), 2.6, 8, smooth=False)
        K.cyl('screen_bg', (sd * 17.5, -25.5, TIER + 0.95), (sd * 17.5, -25.5, TIER + 1.0), 2.3, 24, smooth=False)
        for i in range(20):
            a0, a1 = 2 * math.pi * i / 20, 2 * math.pi * (i + 0.7) / 20
            bar('cyan', (sd * 17.5 + 2.0 * math.cos(a0), -25.5 + 2.0 * math.sin(a0), TIER + 1.03), (sd * 17.5 + 2.0 * math.cos(a1), -25.5 + 2.0 * math.sin(a1), TIER + 1.03), 0.04)
        K.box('screen_o', (sd * 17.2, -25.3, TIER + 1.03), (1.2, 0.5, 0.02), rot=20)
        D.chevrons((sd * 18, -10.6, TIER), 90, n=2, s=1.1)
        for q in range(5):
            K.box('paint_w', (sd * (12.5 + q * 2.6), -9.3, TIER + 0.012), (1.6, 0.16, 0.02))
    D.dress_wall((-W2, YB + 0.05), 0, 60, TIER, TIER + 10.4, seed=40, cell=(3.0, 2.6), skip=lambda u, z: abs(u - 30) < 9.5)
    K.area('TierFill', (0, -19, 16), (50, 10), 12000, (0.4, 0.6, 1.0), spread=150)


def ceiling():
    """Heavy beams converging on the window, deep dark coffers, a few narrow blue light slots."""
    targets = [(-17.0, YW + 2), (-5.7, YW + 2), (5.7, YW + 2), (17.0, YW + 2), (-24.5, 38.5), (24.5, 38.5)]
    for (xw, yw) in targets:
        xr = xw * 0.55
        w0, w1, d0, d1 = 1.2, 1.5, 2.6, 4.2
        K.loft('armor', [(xr - w0, YB, HT - d0), (xr + w0, YB, HT - d0), (xr + w0, YB, HT), (xr - w0, YB, HT)],
               [(xw - w1, yw, HT - d1), (xw + w1, yw, HT - d1), (xw + w1, yw, HT), (xw - w1, yw, HT)])
        K.loft('hull', [(xr - w0 - 0.7, YB, HT - 0.9), (xr + w0 + 0.7, YB, HT - 0.9), (xr + w0 + 0.7, YB, HT), (xr - w0 - 0.7, YB, HT)],
               [(xw - w1 - 0.7, yw, HT - 1.2), (xw + w1 + 0.7, yw, HT - 1.2), (xw + w1 + 0.7, yw, HT), (xw - w1 - 0.7, yw, HT)])
        bar('neon', (xr, YB + 0.5, HT - d0 - 0.06), (xw, yw - 3.5, HT - d1 - 0.06), 0.1)
        # light slots tucked beside the beam
        for f in (0.18, 0.45, 0.72):
            x = xr + (xw - xr) * f
            y = YB + (yw - YB) * f
            for sd in (-1, 1):
                K.box('dark', (x + sd * 2.9, y, HT - 0.25), (0.9, 6.4, 0.5))
                K.box('slot', (x + sd * 2.9, y, HT - 0.52), (0.35, 5.6, 0.05))
    for y in (-19.0, -1.0, 33.0):
        K.box2('armor', (-W2, y - 1.0, HT - 2.0), (W2, y + 1.0, HT))
        K.box2('neon_dim', (-W2 + 2, y - 0.05, HT - 2.07), (W2 - 2, y + 0.05, HT - 2.0))
        for x in range(-24, 25, 8):
            K.box('orange', (x, y - 1.03, HT - 1.6), (0.9, 0.06, 0.14))
    for x, r in [(-27, 0.6), (27, 0.6), (-28.4, 0.3), (28.4, 0.3), (-25.6, 0.25), (25.6, 0.25)]:
        K.cyl('hull_lt', (x, YB, HT - 3.0), (x, 34, HT - 3.0), r, 10)
        for y in range(int(YB) + 4, 34, 6):
            K.cyl('dark', (x, y - 0.15, HT - 3.0), (x, y + 0.15, HT - 3.0), r * 1.3, 10)
    K.area('CeilA', (0, -18, HT - 0.4), (36, 12), 22000, (0.42, 0.62, 1.0), spread=140)
    K.area('CeilB', (0, 30, HT - 0.4), (44, 14), 22000, (0.42, 0.62, 1.0), spread=140)
    K.area('FillL', (-26, 8, 12), (30, 8), 9000, (0.3, 0.5, 1.0), rot=(0, -80, 0), spread=150)
    K.area('FillR', (26, 8, 12), (30, 8), 9000, (0.3, 0.5, 1.0), rot=(0, 80, 0), spread=150)


def window_wall():
    """Panoramic window: centre section flat, two wings angled back; leans outward towards the top."""
    z0, z1, lean = 2.4, 25.0, 7.0
    secs = [((-W2, 34), (-17, YW)), ((-17, YW), (17, YW)), ((17, YW), (W2, 34))]
    for k, (a, b) in enumerate(secs):
        a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
        d = (b - a)
        n = Vector((-d.y, d.x, 0)).normalized()       # outward
        up = Vector((0, 0, z1 - z0)) + n * lean
        Z = lambda h: Vector((0, 0, h))
        # sill: an armoured wedge with vents and lights (no desks, the view stays clear)
        K.loft('armor', [tuple(a - n * 1.6 + Z(-0.1)), tuple(b - n * 1.6 + Z(-0.1)), tuple(b + n * 2), tuple(a + n * 2)],
               [tuple(a - n * 0.2 + Z(z0)), tuple(b - n * 0.2 + Z(z0)), tuple(b + n * 2 + Z(z0)), tuple(a + n * 2 + Z(z0))])
        bar('neon', a + Z(z0 - 0.25) - n * 0.35, b + Z(z0 - 0.25) - n * 0.35, 0.1)
        cnt = int(d.length / 2.6)
        for q in range(cnt):
            p = a + d * ((q + 0.5) / cnt) - n * 1.05 + Z(PLAT + 0.55)
            K.box('orange' if q % 4 == 0 else 'dark', tuple(p), (1.4, 0.1, 0.22), rot=math.degrees(math.atan2(d.y, d.x)))
        # glass
        g0, g1 = a + Z(z0) + n * 0.8, b + Z(z0) + n * 0.8
        K.add('glass', [tuple(g0), tuple(g1), tuple(g1 + up), tuple(g0 + up)], [(0, 1, 2, 3)])
        # heavy header / brow above the glass
        h0, h1 = g0 + up, g1 + up
        K.loft('armor', [tuple(h0 - n * 2.4 + Z(-1.6)), tuple(h1 - n * 2.4 + Z(-1.6)), tuple(h1 + n * 1.0 + Z(-1.0)), tuple(h0 + n * 1.0 + Z(-1.0))],
               [tuple(h0 - n * 7.0 + Z(HT - z1)), tuple(h1 - n * 7.0 + Z(HT - z1)), tuple(h1 + n * 1.0 + Z(HT - z1)), tuple(h0 + n * 1.0 + Z(HT - z1))])
        bar('neon', h0 - n * 2.5 + Z(-1.66), h1 - n * 2.5 + Z(-1.66), 0.12)
        cnt = int(d.length / 4)
        for q in range(cnt):
            p = h0 + (h1 - h0) * ((q + 0.5) / cnt) - n * 3.6 + Z(-0.75)
            K.box('orange', tuple(p), (0.9, 0.3, 0.14), rot=math.degrees(math.atan2(d.y, d.x)))
        # mullions: few and heavy, tapering towards the top, each with a foot buttress
        m = max(1, round(d.length / 11.5))
        for q in range(m + 1):
            p = g0 + d * (q / m)
            w = 0.75 if 0 < q < m else 1.2
            K.cyl('armor', p - n * 0.4, p + up - n * 0.4, w * 1.25, 4, r1=w * 0.8, smooth=False)
            bar('neon', p - n * (0.4 + w * 1.3) + Z(1.2), p + up * 0.93 - n * (0.4 + w * 1.0), 0.07)
            K.cyl('hull', p - n * 2.6 + Z(-z0), p + up * 0.2 - n * 0.6, w * 1.3, 4, r1=w * 0.7, smooth=False)
            K.box('orange', tuple(p + up * 0.2 - n * (0.75 + w)), (0.3, 0.3, 0.16))
        K.cyl('armor', g0 + up * 0.72 - n * 0.2, g1 + up * 0.72 - n * 0.2, 0.4, 4, smooth=False)
    for (x, y) in [(-17, YW), (17, YW)]:
        K.box('armor', (x, y - 0.6, HT / 2), (3.0, 3.0, HT), taper=(0.75, 0.75))


def console_tier():
    """Raised wrap-around tier that follows the window line, with one long console run per section."""
    I = [(-30, 19), (-14, 32.5), (14, 32.5), (30, 19)]
    O = [(-30, 34), (-17, 45), (17, 45), (30, 34)]
    for k in range(3):
        quad = [I[k], I[k + 1], O[k + 1], O[k]]
        K.prism('armor', quad, 0, PLAT - 0.05, axis='z')
        K.prism('floor_dk', quad, PLAT - 0.05, PLAT, axis='z')
        bar('neon', (I[k][0], I[k][1], PLAT - 0.3), (I[k + 1][0], I[k + 1][1], PLAT - 0.3), 0.1)
        bar('hazard', (I[k][0], I[k][1], 0.25), (I[k + 1][0], I[k + 1][1], 0.25), 0.3)
    # short access ramp in the middle
    K.prism('floor_dk', [(27.0, 0), (32.6, PLAT), (32.6, 0)], -4.0, 4.0, axis='x')
    for s in (-1, 1):
        bar('neon', (s * 4.0, 27.0, 0.06), (s * 4.0, 32.6, PLAT + 0.06), 0.07)
    # console runs (operators face the window)
    desk_run((-28.2, 27.4), (-16.6, 37.4), PLAT, seed=1)
    desk_run((-12.5, 38.4), (-4.6, 38.4), PLAT, seed=2, fin_every=2)
    desk_run((4.6, 38.4), (12.5, 38.4), PLAT, seed=3, fin_every=2)
    desk_run((16.6, 37.4), (28.2, 27.4), PLAT, seed=4)


def stations():
    """Two large, different stations on the main deck."""
    # tactical wall (port side): a free-standing angled display slab with a console in front
    c, rot = (-21.0, 9.5, 0), -58
    at = frame(c, rot)
    K.box('armor', at(0, 0, 4.6), (11.0, 0.8, 8.4), rot, taper=(0.86, 1.0))
    K.box('screen_bg', at(0, -0.43, 4.9), (9.2, 0.04, 6.6), rot)
    r = random.Random(12)
    for i in range(11):
        L = r.uniform(1.2, 5.0)
        K.box(r.choice(SCREENS), at(-4.2 + L / 2 + r.uniform(0, 8.4 - L), -0.46, 2.1 + i * 0.55), (L, 0.02, 0.16), rot)
    for (dx, dz, w, h, m) in [(-2.6, 6.2, 2.6, 1.6, 'screen_o'), (2.4, 3.2, 3.0, 1.8, 'screen_c'), (2.8, 6.6, 1.6, 1.0, 'screen')]:
        for (ex, ez, sw, sh) in [(0, h / 2, w, 0.06), (0, -h / 2, w, 0.06), (w / 2, 0, 0.06, h), (-w / 2, 0, 0.06, h)]:
            K.box(m, at(dx + ex, -0.47, dz + ez), (sw, 0.02, sh), rot)
    for sx in (-5.2, 5.2):
        K.box('armor', at(sx, 0.8, 2.2), (1.0, 2.6, 4.4), rot, taper=(1, 0.4))
        K.box('neon', at(sx, -0.42, 4.6), (0.12, 0.05, 6.8), rot)
        K.box('orange', at(sx, -0.42, 8.5), (0.5, 0.05, 0.16), rot)
    for du in (-2.4, 2.4):
        D.crew_station(at(du, -4.0, 0), rot, 3.6, 'screen_c', seed=int(du * 10))
    K.box2('floor_dk', (-27, 2, 0), (-13, 17, 0.02))
    # sensor station (starboard): round plinth with a holographic globe
    cx, cy = 21.5, 15.0
    K.cyl('armor', (cx, cy, 0), (cx, cy, 1.2), 4.4, 8, smooth=False)
    K.cyl('hull_lt', (cx, cy, 1.2), (cx, cy, 1.5), 3.8, 8, smooth=False)
    K.cyl('screen_bg', (cx, cy, 1.5), (cx, cy, 1.56), 3.3, 24, smooth=False)
    n = 28
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.7) / n
        bar('cyan', (cx + 3.5 * math.cos(a0), cy + 3.5 * math.sin(a0), 1.6), (cx + 3.5 * math.cos(a1), cy + 3.5 * math.sin(a1), 1.6), 0.06)
        for (tilt, m) in ((0, 'holo'), (60, 'holo'), (-60, 'holo'), (90, 'holo')):
            R = K._rot((tilt, 0, 30 if tilt else 0))
            p0 = R @ Vector((2.6 * math.cos(a0), 2.6 * math.sin(a0), 0))
            p1 = R @ Vector((2.6 * math.cos(a1), 2.6 * math.sin(a1), 0))
            bar(m, (cx + p0.x, cy + p0.y, 5.0 + p0.z), (cx + p1.x, cy + p1.y, 5.0 + p1.z), 0.035)
    for (dx, dy, dz) in [(1.6, 0.8, 1.2), (-1.0, 1.9, -0.6), (0.4, -2.2, 0.9)]:
        K.cyl('holo_o', (cx + dx, cy + dy, 5.0 + dz - 0.2), (cx + dx, cy + dy, 5.0 + dz + 0.2), 0.2, 6)
    K.point('GlobeGlow', (cx, cy, 5.0), 2500, (0.2, 0.7, 1.0), r=1.5)
    for a in (200, 250, 300):
        rr = math.radians(a)
        D.crew_station((cx + 6.4 * math.cos(rr), cy + 6.4 * math.sin(rr), 0), a + 90, 3.2, 'screen_o' if a == 250 else 'screen', seed=a)
    K.cyl('hazard', (cx, cy, 0), (cx, cy, 0.04), 5.2, 8, smooth=False)


def side_walls():
    GZ = 10.5                                        # gallery deck height
    for s in (-1, 1):
        ribs = [-26, -15, -4, 7, 18, 29]
        for i, y in enumerate(ribs):
            K.prism('armor', [(s * W2, 0), (s * 27.0, 0), (s * 28.0, 16.0), (s * 24.5, 23.0), (s * 19.5, HT - 3.2),
                              (s * 19.5, HT), (s * W2, HT)], y - 0.8, y + 0.8)
            K.prism('hull', [(s * W2, 0), (s * 28.2, 0), (s * 29.0, 16.0), (s * 26.0, 22.4), (s * 19.5, HT - 2.2),
                             (s * 19.5, HT), (s * W2, HT)], y - 1.5, y + 1.5)
            z0 = TIER if y < YT else 0
            bar('neon', (s * 26.95, y, z0 + 0.8), (s * 27.6, y, GZ - 0.8), 0.1)
            bar('neon', (s * 27.75, y, GZ + 1.6), (s * 27.95, y, 15.7), 0.1)
            bar('neon', (s * 27.9, y, 16.3), (s * 24.6, y, 22.8), 0.1)
            K.box('orange', (s * 26.9, y, z0 + 0.5), (0.1, 0.5, 0.22))
            for q in range(6):                       # bolt collars + marker lights up the rib
                z = z0 + 2.0 + q * 2.3
                x = 27.0 + (z / 16.0) * 1.0
                K.box('hull_lt', (s * (x + 0.3), y, z), (1.1, 1.9, 0.3))
                K.box('cyan' if q % 2 else 'orange', (s * (x - 0.28), y + 0.5, z), (0.05, 0.2, 0.1))
            # gallery bracket truss from the rib
            K.prism('armor', [(s * 27.4, GZ - 3.2), (s * 24.0, GZ - 0.5), (s * 27.4, GZ - 0.5)], y - 0.25, y + 0.25)
        # mezzanine gallery with railing, crew stations and wall screens above it
        K.box2('floor_dk', (min(s * 24.0, s * W2), YB, GZ - 0.5), (max(s * 24.0, s * W2), 31.0, GZ))
        K.box2('paint_b', (min(s * 25.0, s * 25.2), YB, GZ), (max(s * 25.0, s * 25.2), 31.0, GZ + 0.02))
        K.box2('armor', (min(s * 23.7, s * 24.1), YB, GZ - 0.9), (max(s * 23.7, s * 24.1), 31.0, GZ + 0.15))
        K.box2('neon', (min(s * 23.62, s * 23.7), YB, GZ - 0.6), (max(s * 23.62, s * 23.7), 31.0, GZ - 0.42))
        D.handrail((s * 23.9, YB + 0.5, GZ), (s * 23.9, 30.5, GZ), post=2.2)
        for q in range(26):
            K.box('orange' if q % 4 == 0 else 'dark', (s * 23.6, YB + 2 + q * 2.3, GZ - 0.2), (0.05, 0.5, 0.1))
        for i, y in enumerate([-20.5, -9.5, 1.5, 12.5, 23.5]):
            D.crew_station((s * 28.3, y, GZ), -90 if s > 0 else 90, 3.4, SCREENS[i % 4], seed=10 + i + (s > 0) * 7)
            screen_x(s * (W2 - 0.25), y, GZ + 5.0, 6.6, 3.6, -s, seed=i * 2 + (s > 0))
            K.box('armor', (s * (W2 - 0.7), y, GZ + 7.3), (1.4, 7.4, 0.4))
            K.box('slot', (s * (W2 - 0.9), y, GZ + 7.08), (0.5, 6.0, 0.04))
        D.ladder((s * 24.6, 14.5, 0), 90 if s > 0 else -90, GZ - 0.5)
        # lower wall: stations, bays, lockers, pipes - nothing plain
        skip = (lambda u, z, s=s: ((YB + u) if s > 0 else (34 - u)) < YT and z < TIER)
        if s > 0:
            D.dress_wall((W2 - 0.05, YB), 90, 34 - YB, 0.0, GZ - 1.0, seed=31, cell=(2.75, 2.4), skip=skip)
            D.dress_wall((W2 - 0.05, YB), 90, 34 - YB, GZ + 9.0, 22.0, seed=33, cell=(2.75, 2.6))
        else:
            D.dress_wall((-W2 + 0.05, 34), -90, 34 - YB, 0.0, GZ - 1.0, seed=32, cell=(2.75, 2.4), skip=skip)
            D.dress_wall((-W2 + 0.05, 34), -90, 34 - YB, GZ + 9.0, 22.0, seed=34, cell=(2.75, 2.6))
        # under-gallery practicals
        for y in range(int(YB) + 3, 30, 5):
            K.box('slot', (s * 26.0, y, GZ - 0.55), (2.0, 0.3, 0.05))
        K.area('Under', (s * 26.0, 5, GZ - 0.8), (2.5, 50), 5000, (0.3, 0.55, 1.0), spread=160)
        K.area('GalWash', (s * 25.0, 0, 19.5), (3, 50), 7000, (0.3, 0.5, 1.0), rot=(0, s * 70, 0), spread=150)
    # rear wall: blast door + dressing
    K.box2('armor', (-9, YB, TIER), (9, YB + 0.8, TIER + 9.5))
    K.box2('hull', (-7, YB + 0.8, TIER), (7, YB + 1.0, TIER + 8))
    K.box2('hazard', (-7, YB + 1.0, TIER), (7, YB + 1.05, TIER + 0.8))


def window_extra():
    """Second pass on the window wall: collars and lights on the mullions, glazing seams, brow machinery."""
    z0, z1, lean = 2.4, 25.0, 7.0
    secs = [((-W2, 34), (-17, YW)), ((-17, YW), (17, YW)), ((17, YW), (W2, 34))]
    for k, (a, b) in enumerate(secs):
        a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
        d = b - a
        n = Vector((-d.y, d.x, 0)).normalized()
        up = Vector((0, 0, z1 - z0)) + n * lean
        ang = math.degrees(math.atan2(d.y, d.x))
        g0, g1 = a + Vector((0, 0, z0)) + n * 0.8, b + Vector((0, 0, z0)) + n * 0.8
        m = max(1, round(d.length / 11.5))
        for q in range(m + 1):
            p = g0 + d * (q / m)
            w = 0.75 if 0 < q < m else 1.2
            for t in (0.12, 0.3, 0.48, 0.66, 0.84):
                c = p + up * t - n * 0.4
                K.cyl('hull_lt', c, c + up * 0.018, w * 1.6, 4, smooth=False)
                K.box('cyan' if t in (0.3, 0.66) else 'orange', tuple(c - n * (w * 1.25) + up * 0.01), (0.22, 0.22, 0.12))
            # diagonal knee braces into the brow
            for sd in (-1, 1):
                K.cyl('armor', p + up * 0.8 - n * 0.5, p + up * 0.97 - n * 0.5 + d.normalized() * sd * 3.2, 0.3, 4, smooth=False)
        panes = max(2, round(d.length / 3.8))
        for q in range(1, panes):
            p = g0 + d * (q / panes)
            K.cyl('dark', p, p + up, 0.07, 4, smooth=False)
        for t in (0.36,):
            K.cyl('dark', g0 + up * t, g1 + up * t, 0.07, 4, smooth=False)
        # brow machinery: vent blocks, indicator rows, a recessed blue strip
        h0, h1 = g0 + up, g1 + up
        cnt = int(d.length / 3.0)
        for q in range(cnt):
            c = h0 + (h1 - h0) * ((q + 0.5) / cnt) - n * 4.6 + Vector((0, 0, 0.2))
            K.box('hull' if q % 2 else 'hull_lt', tuple(c), (2.2, 1.6, 1.0), rot=ang)
            for v in range(4):
                K.box('dark', tuple(c - n * 0.82 + Vector((0, 0, -0.3 + v * 0.2))), (1.8, 0.05, 0.08), rot=ang)
            K.box('orange' if q % 3 == 0 else 'cyan', tuple(c - n * 0.83 + Vector((0, 0, 0.42))), (0.5, 0.04, 0.08), rot=ang)
        bar('neon_dim', h0 - n * 5.6 + Vector((0, 0, 0.9)), h1 - n * 5.6 + Vector((0, 0, 0.9)), 0.08)
        # sill: louvres and small screens facing the room
        cnt = int(d.length / 2.6)
        for q in range(cnt):
            c = a + d * ((q + 0.5) / cnt) - n * 1.25 + Vector((0, 0, PLAT + 0.2))
            for v in range(3):
                K.box('dark', tuple(c + Vector((0, 0, -0.25 + v * 0.16))), (1.8, 0.06, 0.07), rot=ang)


def ceiling_extra():
    """Trusses between the beams, ducting, hanging cable looms and a few hanging monitor pods."""
    for y in (-10.0, 8.0, 26.0):
        D.truss((-W2 + 1, y, HT - 0.6), (W2 - 1, y, HT - 0.6), depth=2.4, width=1.4, mat='armor', r=0.13, bay=3.0)
        for x in range(-24, 25, 6):
            K.box('orange' if x % 12 == 0 else 'neon_dim', (x, y, HT - 3.08), (0.6, 0.12, 0.08))
    for x in (-13.0, 13.0):
        D.duct((x, YB + 1, HT - 1.2), (x, 30, HT - 1.2), w=1.6, h=1.0)
        D.duct((x * 1.7, YB + 1, HT - 3.9), (x * 1.7, 30, HT - 3.9), w=1.0, h=0.7, mat='hull')
    k = 0
    for (p0, p1, sag) in [((-13, -6, HT - 1.8), (-22, 2, HT - 4.2), 2.2), ((13, -6, HT - 1.8), (22, 2, HT - 4.2), 2.2),
                          ((-8, 12, 24.2), (-13, 4, HT - 1.8), 1.6), ((8, 12, 24.2), (13, 4, HT - 1.8), 1.6),
                          ((-13, 20, HT - 1.8), (-22.1, 26, HT - 4.2), 2.0), ((13, 20, HT - 1.8), (22.1, 26, HT - 4.2), 2.0),
                          ((-22.1, -12, HT - 4.2), (-27.5, -12, 20.0), 1.2), ((22.1, 12, HT - 4.2), (27.5, 12, 20.0), 1.2),
                          ((-4, 26, HT - 3), (4, 30, HT - 3), 1.8), ((0, -8, HT - 3), (0, -1, HT - 2.5), 2.6)]:
        D.cable_loom(p0, p1, n=5, sag=sag, r=0.07, seed=k)
        k += 1
    # monitor pods hanging over the two side stations
    for (x, y, rot) in [(-17.5, 6.5, -58), (19.0, 11.0, 30)]:
        K.cyl('steel', (x, y, 11.0), (x, y, HT - 2), 0.12, 6)
        f = D.Fr((x, y, 0), rot)
        for q in (-1, 0, 1):
            f.box('armor', q * 2.3, 0, 9.9, 2.1, 0.3, 1.5)
            f.box('screen_bg', q * 2.3, -0.17, 9.9, 1.9, 0.03, 1.3)
            f.box(SCREENS[q + 1], q * 2.3, -0.2, 10.2, 1.3, 0.02, 0.08)
            f.box('screen_o' if q == 0 else 'screen_c', q * 2.3 - 0.3, -0.2, 9.8, 0.8, 0.02, 0.08)
            f.box('screen', q * 2.3 + 0.2, -0.2, 9.5, 1.1, 0.02, 0.06)
        f.box('armor', 0, 0.1, 10.9, 7.2, 0.5, 0.4)


def floor_extra():
    for a in (45, 135, 225, 315):
        r = math.radians(a)
        p0 = (10.6 * math.cos(r), 17 + 10.6 * math.sin(r))
        K.box('dark', (p0[0] + 3.0 * math.cos(r), p0[1] + 3.0 * math.sin(r), 0.012), (6.0, 0.9, 0.024), rot=a)
        K.box('neon_dim', (p0[0] + 3.0 * math.cos(r), p0[1] + 3.0 * math.sin(r), 0.03), (6.0, 0.08, 0.02), rot=a)
    D.floor_trench((-27, 1.2), (27, 1.2), w=0.8)
    D.floor_trench((-9.6, 6.5), (-9.6, 26.5), w=0.7)
    D.floor_trench((9.6, 6.5), (9.6, 26.5), w=0.7)
    for s in (-1, 1):
        D.chevrons((s * 18, 8.5, 0), 90, n=3, s=1.3)
        K.box2('paint_w', (min(s * 12.6, s * 23.4), 6.9, 0), (max(s * 12.6, s * 23.4), 7.1, 0.02))
        for q in range(6):
            K.box('paint_b', (s * 12.0, 9 + q * 3.2, 0.012), (0.3, 1.8, 0.02))
    for i in range(40):
        a0, a1 = 2 * math.pi * i / 40, 2 * math.pi * (i + 0.5) / 40
        bar('paint_w', (13.2 * math.cos(a0), 17 + 13.2 * math.sin(a0), 0.012), (13.2 * math.cos(a1), 17 + 13.2 * math.sin(a1), 0.012), 0.07)


def holo_table(sc):
    """Hero piece: 17 m holo table with a tactical hologram, under a ceiling projector ring."""
    cx, cy = 0.0, 17.0
    K.cyl('hazard', (cx, cy, 0), (cx, cy, 0.04), 10.4, 8, smooth=False)
    K.cyl('armor', (cx, cy, 0), (cx, cy, 1.1), 8.6, 8, smooth=False)
    K.cyl('hull_lt', (cx, cy, 1.1), (cx, cy, 1.45), 7.9, 8, smooth=False)
    K.cyl('screen_bg', (cx, cy, 1.45), (cx, cy, 1.52), 7.2, 40, smooth=False)
    for r, n, m in [(7.0, 56, 'cyan'), (5.2, 36, 'screen'), (3.2, 20, 'screen_c'), (1.4, 10, 'screen_o')]:
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.7) / n
            bar(m, (cx + r * math.cos(a0), cy + r * math.sin(a0), 1.56), (cx + r * math.cos(a1), cy + r * math.sin(a1), 1.56), 0.07)
    for k in range(12):
        a = math.radians(30 * k)
        bar('screen', (cx + 1.6 * math.cos(a), cy + 1.6 * math.sin(a), 1.55), (cx + 6.8 * math.cos(a), cy + 6.8 * math.sin(a), 1.55), 0.025)
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        K.box('armor', (cx + 8.3 * math.cos(a), cy + 8.3 * math.sin(a), 1.4), (1.6, 1.1, 2.8), rot=math.degrees(a) + 90, taper=(0.7, 0.7))
        K.box('cyan', (cx + 7.85 * math.cos(a), cy + 7.85 * math.sin(a), 2.83), (0.7, 0.3, 0.06), rot=math.degrees(a) + 90)
        K.box('orange', (cx + 8.9 * math.cos(a), cy + 8.9 * math.sin(a), 1.6), (0.5, 0.06, 0.2), rot=math.degrees(a) + 90)
    # four operator podiums round the table
    for a in (225, 315, 135, 45):
        rr = math.radians(a)
        D.crew_station((cx + 11.6 * math.cos(rr), cy + 11.6 * math.sin(rr), 0), a + 90, 3.6, 'screen_c', seed=a)
    # ceiling projector ring
    zr = 23.6
    for k in range(8):
        a = math.radians(45 * k)
        K.box('armor', (cx + 8.2 * math.cos(a), cy + 8.2 * math.sin(a), zr), (2.2, 7.2, 1.8), rot=math.degrees(a), taper=(0.7, 1.0))
        K.box('cyan', (cx + 8.2 * math.cos(a), cy + 8.2 * math.sin(a), zr - 0.93), (0.5, 4.6, 0.06), rot=math.degrees(a))
        K.box('orange', (cx + 9.35 * math.cos(a), cy + 9.35 * math.sin(a), zr), (0.06, 1.6, 0.2), rot=math.degrees(a))
        b = math.radians(45 * k + 22.5)
        K.box('neon', (cx + 7.0 * math.cos(b), cy + 7.0 * math.sin(b), zr + 0.2), (0.1, 2.6, 0.1), rot=math.degrees(b))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        K.cyl('armor', (cx + 8.2 * math.cos(a), cy + 8.2 * math.sin(a), zr + 0.8),
              (cx + 10.5 * math.cos(a), cy + 10.5 * math.sin(a), HT), 0.7, 4, smooth=False)
    K.cyl('hull_lt', (cx, cy, zr + 0.3), (cx, cy, HT), 1.6, 8, r1=2.6, smooth=False)
    K.cyl('cyan', (cx, cy, zr + 0.2), (cx, cy, zr + 0.3), 1.2, 16, smooth=False)
    for k in range(4):
        a = math.radians(90 * k)
        K.cyl('hull', (cx + 1.6 * math.cos(a), cy + 1.6 * math.sin(a), zr + 0.6), (cx + 7.2 * math.cos(a), cy + 7.2 * math.sin(a), zr + 0.3), 0.35, 4, smooth=False)
    # tactical markers and range rings in the projection
    for (rr_, z) in ((8.6, 6.4), (5.6, 9.6)):
        for i in range(56):
            a0, a1 = 2 * math.pi * i / 56, 2 * math.pi * (i + 0.6) / 56
            bar('holo', (cx + rr_ * math.cos(a0), cy + rr_ * math.sin(a0), z), (cx + rr_ * math.cos(a1), cy + rr_ * math.sin(a1), z), 0.04)
    for (dx, dy, dz, m) in [(5.4, 2.6, 9.6, 'holo_o'), (6.4, -1.4, 8.4, 'holo_o'), (3.6, 4.6, 10.6, 'holo_o'), (-6.0, -2.2, 5.0, 'holo'),
                            (-4.6, 3.6, 6.0, 'holo')]:
        K.cyl(m, (cx + dx, cy + dy, dz), (cx + dx + 1.2, cy + dy - 0.4, dz), 0.36, 3, r1=0.02, smooth=False)
        K.cyl(m, (cx + dx, cy + dy, 1.6), (cx + dx, cy + dy, dz), 0.018, 4, smooth=False)
    K.point('HoloGlow', (cx, cy, 5.0), 12000, (0.15, 0.6, 1.0), r=2.5)
    K.point('HoloGlow2', (cx, cy, 15.0), 5000, (0.15, 0.6, 1.0), r=2.5)
    try:
        import forge as F
        import terran_fleet as T
        ship, _ = T.broadside_battleship()
        m = bpy.data.materials.new('HoloShip')
        t = K.NT(m)
        lw = t.n('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.35
        em = t.n('ShaderNodeEmission')
        em.inputs[0].default_value = (0.08, 0.6, 1.0, 1)
        t.link(t.m('ADD', 0.16, t.m('MULTIPLY', lw.outputs['Facing'], 2.4)), em.inputs[1])
        t.link(em.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
        ship.data.materials.clear()
        ship.data.materials.append(m)
        for p in ship.data.polygons:
            p.material_index = 0
        ship.scale = (0.34,) * 3
        ship.location = (cx - 0.4, cy, 7.6)
        ship.rotation_euler = (math.radians(10), math.radians(-7), math.radians(128))
        ship.visible_shadow = False
        K.NOFOG.append(ship)
    except Exception as e:
        print('HOLO SHIP SKIPPED', repr(e))


def outside(sc):
    K.space_world(sc, nebula=0.3, density=0.6, scale=150.0, size=0.07)
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 8.0
    sun.color = (1.0, 0.94, 0.86)
    sun.angle = math.radians(2)
    o = bpy.data.objects.new('Sun', sun)
    sc.collection.objects.link(o)
    o.rotation_euler = (math.radians(52), 0, math.radians(-35))
    # the ship's own bow: the bridge sits high on a tower, the foredeck runs out far below and ahead
    y0, y1 = YW + 14, YW + 1050
    zt0, zt1 = -15.0, -20.0
    K.loft('hull_big', [(-78, y0, zt0), (78, y0, zt0), (64, y0, zt0 - 40), (-64, y0, zt0 - 40)],
           [(-12, y1, zt1), (12, y1, zt1), (6, y1, zt1 - 24), (-6, y1, zt1 - 24)])
    K.loft('hull_lt', [(-26, y0, zt0 + 6), (26, y0, zt0 + 6), (32, y0, zt0), (-32, y0, zt0)],
           [(-5, y1 - 120, zt1 + 3), (5, y1 - 120, zt1 + 3), (8, y1 - 120, zt1), (-8, y1 - 120, zt1)])

    def edge(f, k=1.0):
        return (78 - 66 * f) * k, y0 + (y1 - y0) * f, zt0 + (zt1 - zt0) * f
    for s in (-1, 1):
        for k, r in ((0.985, 1.3), (0.8, 0.7), (0.38, 0.9)):
            xa, ya, za = edge(0.0, k)
            xb, yb, zb = edge(1.0, k)
            bar('neon', (s * xa, ya + 2, za + 0.4 + (6 if k < 0.5 and False else 0)), (s * xb, yb - 2, zb + 0.4), r)
        for q in range(60):
            x, y, z = edge((q + 0.5) / 60, 0.93)
            K.box('orange', (s * x, y, z + 0.8), (2.4, 2.4, 1.2))
        for q in range(30):
            x, y, z = edge((q + 0.5) / 30, 0.6)
            K.box('neon_dim', (s * x, y, z + 0.5), (1.6, 6.0, 0.6))
    for k, y in enumerate([YW + 190, YW + 360, YW + 560, YW + 780]):
        f = (y - y0) / (y1 - y0)
        z = zt0 + 6 + (zt1 + 3 - zt0 - 6) * min(1.0, (y - y0) / (y1 - 120 - y0))
        sc_ = 1.0 - 0.45 * f
        K.cyl('armor', (0, y, z), (0, y, z + 5 * sc_), 19 * sc_, 8, smooth=False)
        K.cyl('neon', (0, y, z + 0.6), (0, y, z + 1.4), 19.2 * sc_, 8, smooth=False)
        K.box('hull', (0, y + 3, z + 9 * sc_), (22 * sc_, 30 * sc_, 8 * sc_), taper=(0.7, 0.75))
        K.box('armor', (0, y - 6 * sc_, z + 14 * sc_), (12 * sc_, 10 * sc_, 4 * sc_), taper=(0.6, 0.7))
        K.box('orange', (0, y - 11.2 * sc_, z + 14 * sc_), (6 * sc_, 0.6, 1.0 * sc_))
        for dx in (-5.5, 5.5):
            K.cyl('steel', (dx * sc_, y + 12 * sc_, z + 9.5 * sc_), (dx * sc_, y + 70 * sc_, z + 13 * sc_), 2.1 * sc_, 12)
            K.cyl('hull_lt', (dx * sc_, y + 12 * sc_, z + 9.5 * sc_), (dx * sc_, y + 30 * sc_, z + 10.6 * sc_), 3.0 * sc_, 12)
            for q in range(4):
                yy = y + (38 + q * 7) * sc_
                zz = z + 9.5 * sc_ + (yy - y - 12 * sc_) * (3.5 / 58)
                K.cyl('cyan', (dx * sc_, yy, zz), (dx * sc_, yy + 1.6 * sc_, zz + 0.1 * sc_), 2.3 * sc_, 12)
    rr = random.Random(3)
    for k in range(700):
        f = rr.random() ** 1.3
        x, y, z = edge(f, rr.uniform(-0.92, 0.92))
        if abs(x) < (26 - 21 * min(1, f * 1.1)):
            z = zt0 + 6 + (zt1 + 3 - zt0 - 6) * min(1.0, f * 1.13)
        sx, sy, sz = rr.uniform(3, 12), rr.uniform(4, 18), rr.uniform(1.0, 5.0)
        K.box(rr.choice(['hull', 'armor', 'hull_lt', 'hull_lt']), (x, y, z + sz / 2), (sx, sy, sz))
        if rr.random() < 0.45:
            K.box(rr.choice(['orange', 'cyan', 'neon', 'neon']), (x, y, z + sz + 0.3), (1.2, 1.2, 0.5))
    for o in K.flush('Bow'):
        o.location.z = float(A.get('bow', 0.0))
        K.NOFOG.append(o)
    # Terran ships close outside + a few beams (placeholder backdrop)
    try:
        import forge as F
        import terran_fleet as T
        F.ST.update(parts=[], mats={}, group='Hull', seq=0)
        for (builder, loc, rz, sca, ry) in [(T.broadside_battleship, (230, 980, 48), 12, 13.0, 4),
                                            (T.terran_frigate_v2, (-190, 430, 30), 168, 11.0, 5),
                                            (T.terran_corvette, (-10, 520, 52), 18, 8.0, -8),
                                            (T.terran_corvette, (420, 600, 40), 160, 8.0, 6),
                                            (T.terran_frigate_v2, (330, 420, 14), 172, 9.0, -4),
                                            (T.terran_frigate_v2, (-520, 1100, 150), 15, 11.0, 6),
                                            (T.terran_corvette, (-330, 700, 110), 20, 8.0, 5),
                                            (T.terran_corvette, (-260, 760, 135), 20, 8.0, 5)]:
            r = builder()
            ship = r[0] if isinstance(r, tuple) else r
            for p in ship.data.polygons:
                p.use_smooth = True
            T.neon_lines(ship, col=(0.05, 0.35, 1.0), strength=7.0)
            ship.location = loc
            ship.rotation_euler = (0, math.radians(ry), math.radians(rz))
            ship.scale = (sca,) * 3
            K.NOFOG.append(ship)
    except Exception as e:
        print('SHIPS SKIPPED', repr(e))
    K._emit('BeamBlue', (0.05, 0.4, 1.0), 9.0)
    K._emit('BeamGold', (1.0, 0.4, 0.05), 9.0)
    for (p0, p1, r, m) in [((-300, 440, 38), (-2600, 1900, 400), 1.3, 'BeamBlue'), ((-300, 440, 26), (-2600, 1900, 360), 1.3, 'BeamBlue'),
                           ((2400, 2600, 520), (420, 600, 44), 1.4, 'BeamGold')]:
        K.MATDEF[m] = lambda n: bpy.data.materials[n]
        K.cyl(m, p0, p1, r, 6)
    K.NOFOG.extend(K.flush('Out'))


def main():
    K.E.update(neon=1.0, cyan=0.8, orange=2.2, white=1.0)
    K.MATDEF['neon'] = lambda n: K._emit(n, (0.008, 0.15, 1.0), 4.5)
    K.MATDEF['neon_dim'] = lambda n: K._emit(n, (0.008, 0.15, 1.0), 2.0)
    K.MATDEF['slot'] = lambda n: K._emit(n, (0.2, 0.5, 1.0), 4.0)
    K.MATDEF['glass'] = lambda n: K._holo(n, (0.1, 0.4, 1.0), 0.25, 0.05)
    K.MATDEF['screen'] = lambda n: K._emit(n, (0.04, 0.32, 1.0), 1.4)
    K.MATDEF['screen_c'] = lambda n: K._emit(n, (0.1, 0.75, 1.0), 1.5)
    K.MATDEF['screen_o'] = lambda n: K._emit(n, K.ORANGE, 2.2)
    sc, cam = K.reset(samples=int(A.get('samples', 20)), exposure=float(A.get('exposure', 1.0)))
    outside(sc)
    shell()
    dais()
    ceiling()
    window_wall()
    console_tier()
    stations()
    side_walls()
    window_extra()
    ceiling_extra()
    floor_extra()
    holo_table(sc)
    K.flush()
    K.tank('lancer', (19.0, 3.5, 0.0), rz=97)          # one vehicle, off to the side, for scale
    K.look(cam, (-13.5, -25.0, 13.6), (4.0, 34, 6.2), lens=float(A.get('lens', 22)))
    raw = os.path.join(OUT, '_raw', NAME + '.png')
    K.render(sc, raw, RES, depth_far=90.0)
    K.post(raw, A.get('final', os.path.join(OUT, NAME + '.jpg')), haze=float(A.get('haze', 0.3)),
           scatter=float(A.get('scatter', 0.2)), haze_col=(0.05, 0.2, 0.6))


main()
