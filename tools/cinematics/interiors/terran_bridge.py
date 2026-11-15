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
    for i in range(0, n + 1, fin_every):
        x = -L / 2 + i * seg
        K.box('armor', at(x, 0.35, 1.9), (0.6, 2.4, 3.8), ang, taper=(1, 0.55))
        K.box('orange', at(x, -0.32, 3.3), (0.62, 0.08, 0.3), ang)
        K.box('screen_bg', at(x + 0.31 * (1 if i < n else -1), 0.3, 2.6), (0.04, 1.2, 1.4), ang)


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
    """Command dais: a prow-shaped balcony off the upper tier, 0.8 m above it, jutting over the main deck."""
    z1 = TIER + 0.8
    pts = [(-9, YT - 7), (9, YT - 7), (9, YT), (4.5, YT + 11), (-4.5, YT + 11), (-9, YT)]
    K.prism('armor', pts, 0, z1, axis='z')
    K.prism('floor_dk', [(p[0] * 0.92, YT - 7 + (p[1] - YT + 7) * 0.95 + 0.2) for p in pts], z1, z1 + 0.06, axis='z')
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if a[1] < YT - 1 and b[1] < YT - 1:
            continue
        bar('neon', (a[0], a[1], z1 - 0.35), (b[0], b[1], z1 - 0.35), 0.1)
        bar('neon_dim', (a[0], a[1], 1.2), (b[0], b[1], 1.2), 0.07)
    K.box('hazard', (0, YT + 11.03, 0.5), (8.6, 0.06, 1.0))
    for x in (-3.6, -1.2, 1.2, 3.6):
        K.box('orange', (x, YT + 11.05, z1 - 0.9), (0.8, 0.06, 0.16))
    # steps up from the tier at the back
    for k in range(3):
        K.box2('armor', (-5, YT - 7.9 - k * 0.7, TIER), (5, YT - 7.0 - k * 0.7, z1 - (k + 1) * 0.2))
    # wrap-around command consoles on the prow edges
    console((0, YT + 9.3, z1), 0, 6.4, 'screen_o', big=0.95)
    console((5.7, YT + 5.2, z1), -68, 7.0, 'screen_c', big=0.95)
    console((-5.7, YT + 5.2, z1), 68, 7.0, 'screen', big=0.95)
    # command throne (placeholder block, no figure): tall angular back with a neon spine
    cy = YT + 0.6
    K.box('armor', (0, cy, z1 + 0.5), (3.4, 3.4, 1.0), taper=(0.85, 0.85))
    K.box('hull_lt', (0, cy + 0.3, z1 + 1.3), (2.0, 1.8, 0.6))
    K.box('armor', (0, cy - 1.0, z1 + 2.1), (2.6, 0.8, 3.2), taper=(0.5, 1.0))
    K.box('neon', (0, cy - 1.42, z1 + 2.2), (0.14, 0.05, 2.2))
    K.box('orange', (0, cy - 0.58, z1 + 3.4), (0.5, 0.05, 0.14))
    for s in (-1, 1):
        K.box('armor', (s * 1.5, cy + 0.4, z1 + 1.5), (0.6, 2.2, 1.0))
        K.box('screen_c', (s * 1.5, cy + 0.6, z1 + 2.03), (0.4, 1.4, 0.04))
        # flanking status pylons
        K.box('armor', (s * 7.6, YT - 3.5, z1 + 1.2), (1.2, 1.2, 2.4), taper=(0.6, 0.6))
        K.box('neon', (s * 7.6, YT - 2.88, z1 + 1.2), (0.12, 0.05, 1.8))
        K.box('orange', (s * 7.6, YT - 3.5, z1 + 2.5), (0.5, 0.5, 0.2))


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
    console(at(0, -4.0, 0), rot, 8.0, 'screen_c', big=1.15)
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
        console((cx + 6.4 * math.cos(rr), cy + 6.4 * math.sin(rr), 0), a + 90, 4.2, 'screen_o' if a == 250 else 'screen', big=1.0)
    K.cyl('hazard', (cx, cy, 0), (cx, cy, 0.04), 5.2, 8, smooth=False)


def side_walls():
    for s in (-1, 1):
        for i, y in enumerate([-26, -15, -4, 7, 18, 29]):
            K.prism('armor', [(s * W2, 0), (s * 27.0, 0), (s * 28.0, 16.0), (s * 24.5, 23.0), (s * 19.5, HT - 3.2),
                              (s * 19.5, HT), (s * W2, HT)], y - 0.8, y + 0.8)
            K.prism('hull', [(s * W2, 0), (s * 28.2, 0), (s * 29.0, 16.0), (s * 26.0, 22.4), (s * 19.5, HT - 2.2),
                             (s * 19.5, HT), (s * W2, HT)], y - 1.5, y + 1.5)
            z0 = TIER if y < YT else 0
            bar('neon', (s * 26.95, y, z0 + 0.8), (s * 27.95, y, 15.7), 0.1)
            bar('neon', (s * 27.9, y, 16.3), (s * 24.6, y, 22.8), 0.1)
            K.box('orange', (s * 26.9, y, z0 + 0.5), (0.1, 0.5, 0.22))
        for i, y in enumerate([-20.5, 1.5, 23.5]):
            z0 = TIER if y < YT else (PLAT if y > 20 else 0)
            screen_x(s * (W2 - 0.2), y, z0 + 8.5, 7.6, 6.4, -s, seed=i * 2 + (s > 0))
            K.box2('neon_dim', (s * (W2 - 0.15), y - 4.0, z0 + 4.7), (s * (W2 - 0.08), y + 4.0, z0 + 4.82))
        for y in (-9.5, 12.5):         # pipe bundles in the other bays
            for q in range(4):
                K.cyl('hull_lt' if q % 2 else 'steel', (s * (W2 - 0.6), y - 2.4 + q * 1.6, 2.8), (s * (W2 - 0.6), y - 2.4 + q * 1.6, 15.5), 0.42, 10)
                K.cyl('dark', (s * (W2 - 0.6), y - 2.4 + q * 1.6, 9.0), (s * (W2 - 0.6), y - 2.4 + q * 1.6, 9.5), 0.56, 10)
        K.greeble_wall(rnd, s * (W2 - 0.1), YB + 1, 33, 16.5, 22.5, 50, facing=-s, depth=0.8)
    # rear wall: blast door + big screens
    K.box2('armor', (-9, YB, TIER), (9, YB + 0.8, TIER + 9.5))
    K.box2('hull', (-7, YB + 0.8, TIER), (7, YB + 1.0, TIER + 8))
    K.box2('hazard', (-7, YB + 1.0, TIER), (7, YB + 1.05, TIER + 0.8))


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
        console((cx + 11.6 * math.cos(rr), cy + 11.6 * math.sin(rr), 0), a + 90, 4.4, 'screen_c', big=1.0)
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
    # the ship's own bow stretching ahead below the window
    y0, y1 = YW + 9, YW + 330
    K.loft('hull_big', [(-46, y0, -6), (46, y0, -6), (46, y0, -40), (-46, y0, -40)],
           [(-9, y1, -14), (9, y1, -14), (9, y1, -30), (-9, y1, -30)])
    K.loft('hull_lt', [(-20, y0, -1.5), (20, y0, -1.5), (24, y0, -6), (-24, y0, -6)],
           [(-4, y1 - 60, -10.5), (4, y1 - 60, -10.5), (6, y1 - 60, -13), (-6, y1 - 60, -13)])
    for s in (-1, 1):
        bar('neon', (s * 44, y0 + 4, -5.7), (s * 9.6, y1 - 4, -13.7), 0.5)
        bar('neon', (s * 19, y0 + 4, -1.2), (s * 4.4, y1 - 64, -10.2), 0.4)
        bar('neon', (s * 9, y0 + 4, -1.2), (s * 2.0, y1 - 64, -10.2), 0.25)
        for k in range(22):
            f = (k + 0.5) / 22
            K.box('orange', (s * (44 - 34.6 * f) * 0.93, y0 + 4 + (y1 - y0 - 8) * f, -5.5 - 8 * f), (1.2, 1.2, 0.6))
    for k, y in enumerate([YW + 30, YW + 70, YW + 120, YW + 180]):
        f = (y - y0) / (y1 - 60 - y0)
        z = -1.5 - 9 * f
        K.cyl('armor', (0, y, z), (0, y, z + 2.2), 7.0 - 2.5 * f, 8, smooth=False)
        K.box('hull', (0, y + 1, z + 3.6), (8 - 2.5 * f, 10 - 3 * f, 3.0), taper=(0.7, 0.8))
        K.box('neon', (0, y - 4.1 + 1.5 * f, z + 3.6), (5 - 1.5 * f, 0.2, 0.3))
        for dx in (-1.8, 1.8):
            K.cyl('steel', (dx, y + 4, z + 3.9), (dx, y + 22 - 5 * f, z + 5.0), 0.65, 10)
            K.cyl('cyan', (dx, y + 13 - 3 * f, z + 4.4), (dx, y + 13.8 - 3 * f, z + 4.45), 0.74, 10)
    rr = random.Random(3)
    for k in range(200):
        f = rr.random()
        y = y0 + 6 + (y1 - y0 - 80) * f
        wdt = 22 - 17 * f
        x = rr.uniform(-wdt, wdt) + (20 if rr.random() < 0.5 else -20) * (1 - f)
        zt = -6 - 8 * f if abs(x) > (20 - 16 * f) else -1.5 - 9 * f
        sx, sy, sz = rr.uniform(1.5, 6), rr.uniform(2, 9), rr.uniform(0.5, 2.4)
        K.box(rr.choice(['hull', 'armor', 'hull_lt']), (x, y, zt + sz / 2), (sx, sy, sz))
        if rr.random() < 0.4:
            K.box(rr.choice(['orange', 'cyan', 'neon']), (x, y, zt + sz + 0.1), (0.6, 0.6, 0.25))
    for o in K.flush('Bow'):
        o.location.z = float(A.get('bow', 11.0))
        K.NOFOG.append(o)
    # Terran ships close outside + a few beams (placeholder backdrop)
    try:
        import forge as F
        import terran_fleet as T
        F.ST.update(parts=[], mats={}, group='Hull', seq=0)
        for (builder, loc, rz, sca, ry) in [(T.broadside_battleship, (230, 980, 48), 12, 13.0, 4),
                                            (T.terran_frigate_v2, (-190, 430, 30), 168, 11.0, 5),
                                            (T.terran_corvette, (-10, 520, 52), 18, 8.0, -8),
                                            (T.terran_corvette, (420, 600, 40), 160, 8.0, 6)]:
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
    holo_table(sc)
    K.flush()
    K.tank('lancer', (19.0, 3.5, 0.0), rz=97)          # one vehicle, off to the side, for scale
    K.look(cam, (-12.0, -25.5, 13.2), (3.0, 34, 7.0), lens=float(A.get('lens', 22)))
    raw = os.path.join(OUT, '_raw', NAME + '.png')
    K.render(sc, raw, RES, depth_far=90.0)
    K.post(raw, A.get('final', os.path.join(OUT, NAME + '.jpg')), haze=float(A.get('haze', 0.22)),
           scatter=float(A.get('scatter', 0.12)), haze_col=(0.05, 0.2, 0.6))


main()
