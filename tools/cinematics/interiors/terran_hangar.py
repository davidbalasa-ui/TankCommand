"""Terran capital ship - hangar bay with a triangle force-field door open to space (concept still).

    python terran_hangar.py [--out=DIR] [--name=hangar] [--res=960x540] [--samples=20] [--view=door|side]
                            [--final=PATH.jpg]

Space: 64 m wide (X), 120 m long (Y, bay door at +Y), 24 m high. Tanks are ~8 m long.
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
NAME = A.get('name', 'hangar')
RES = tuple(int(v) for v in A.get('res', '960x540').split('x'))
VIEW = A.get('view', 'door')

W2, LEN, HT = 32.0, 120.0, 24.0
DOOR_W2, DOOR_H, DOOR_CH = 23.0, 15.5, 5.0
RIBS = [10 + 15 * k for k in range(7)]
rnd = random.Random(7)


def bar(mat, p0, p1, r):
    K.cyl(mat, p0, p1, r, n=4, smooth=False)


def shell():
    K.box2('floor', (-W2 - 2, -12, -1), (W2 + 2, LEN + 6, 0))
    K.box2('hull_big', (-W2 - 2, -12, HT), (W2 + 2, LEN + 6, HT + 2))
    for s in (-1, 1):
        K.box2('hull_big', (s * W2, -12, 0), (s * (W2 + 2), LEN + 6, HT))
        # sloped armoured wall base
        K.prism('armor', [(s * W2, 0), (s * (W2 - 2.2), 0), (s * (W2 - 1.4), 1.6), (s * W2, 3.2)], -12, LEN)
        # mid wall belt + recessed upper band
        K.box2('armor', (s * (W2 - 0.5), -12, 12.2), (s * W2, LEN, 13.4))
        K.box2('hull', (s * (W2 - 0.9), -12, 18.6), (s * W2, LEN, 20.0))
    K.box2('hull_big', (-W2 - 2, -12, 0), (W2 + 2, -10, HT))


def ribs():
    for y in RIBS:
        for s in (-1, 1):
            pts = [(s * W2, 0), (s * 26.2, 0), (s * 27.0, 2.6), (s * 28.6, 15.0), (s * 25.0, 20.4), (s * 19.0, 21.8),
                   (s * 19.0, HT), (s * W2, HT)]
            K.prism('armor', pts, y - 0.9, y + 0.9)
            # flange plates either side of the rib
            pts2 = [(s * W2, 0), (s * 27.4, 0), (s * 28.0, 2.6), (s * 29.4, 15.0), (s * 26.0, 19.6), (s * 19.0, 21.0),
                    (s * 19.0, HT), (s * W2, HT)]
            K.prism('hull', pts2, y - 1.5, y + 1.5)
            # neon line up the rib's inner edge
            bar('neon', (s * 26.9, y, 3.0), (s * 28.45, y, 14.6), 0.11)
            bar('neon', (s * 28.4, y, 15.4), (s * 25.1, y, 20.2), 0.11)
            K.box('orange', (s * 26.55, y, 1.5), (0.1, 0.5, 0.22))
            K.box('dark', (s * 26.6, y, 1.5), (0.12, 0.8, 0.5))
            # bolts
            for z in (4, 6.5, 9, 11.5, 14):
                x = 27.0 + (z - 2.6) * (28.6 - 27.0) / 12.4
                for dy in (-1.2, 1.2):
                    K.box('steel', (s * (x + 0.9), y + dy, z), (0.25, 0.25, 0.25))
        # ceiling beam across + truss webbing
        K.box2('armor', (-19.2, y - 0.9, 21.9), (19.2, y + 0.9, HT))
        K.box2('hull', (-19.2, y - 1.3, 23.2), (19.2, y + 1.3, HT))
        K.box2('neon_dim', (-18.5, y - 0.07, 21.82), (18.5, y + 0.07, 21.9))
        for i in range(-4, 5):
            K.box('dark', (i * 4.2, y, 22.5), (0.5, 2.0, 0.7))


def ceiling():
    # light panels between the ribs
    ys = [(a + b) / 2 for a, b in zip([RIBS[0] - 15] + RIBS, RIBS + [RIBS[-1] + 15])]
    for y in ys:
        for x in (-11.5, 11.5):
            K.box('dark', (x, y, 23.75), (4.2, 10.4, 0.5))
            K.box('white', (x, y, 23.5), (3.4, 9.6, 0.08))
            for k in range(-2, 3):
                K.box('dark', (x, y + k * 2.0, 23.42), (3.6, 0.1, 0.12))
            K.area('Ceil', (x, y, 23.3), (3.4, 9.6), 5200, (0.68, 0.82, 1.0), spread=150)
        K.box('dark', (0, y, 23.7), (2.0, 6.0, 0.6))
        K.box('white_dim', (0, y, 23.38), (1.2, 5.0, 0.06))
    # ducts and pipe runs along the ceiling
    for x, r, m in [(-16.5, 0.55, 'hull_lt'), (-15.2, 0.3, 'steel'), (16.5, 0.55, 'hull_lt'), (15.2, 0.3, 'steel'),
                    (-5.5, 0.4, 'hull_lt'), (5.5, 0.4, 'hull_lt'), (-4.6, 0.18, 'crate_o'), (4.6, 0.18, 'crate_b')]:
        K.cyl(m, (x, -10, 23.1), (x, LEN - 2, 23.1), r, 10)
        for y in range(0, int(LEN), 5):
            K.cyl('dark', (x, y - 0.12, 23.1), (x, y + 0.12, 23.1), r * 1.25, 10)
    for s in (-1, 1):
        K.box2('hull', (s * 7.0, -10, 23.0), (s * 8.6, LEN - 2, 23.9))


def gallery():
    """Catwalk gallery along both walls at 9.5 m with railings, a neon line under its lip."""
    for s in (-1, 1):
        K.box2('hull_lt', (s * 27.6, -10, 9.2), (s * W2, LEN - 2.5, 9.6))
        K.box2('armor', (s * 27.3, -10, 8.7), (s * 27.7, LEN - 2.5, 9.75))
        K.box2('neon', (s * 27.24, -10, 9.12), (s * 27.3, LEN - 2.5, 9.3))
        K.box2('neon', (s * (W2 - 1.45), -10, 1.65), (s * (W2 - 1.35), LEN - 2.5, 1.8))    # wall-base line
        K.box2('neon_dim', (s * (W2 - 0.56), -10, 12.7), (s * (W2 - 0.5), LEN - 2.5, 12.9))
        y = -8.0
        while y < LEN - 3:
            K.box('steel', (s * 27.5, y, 10.35), (0.08, 0.08, 1.2))
            y += 2.5
        for z in (10.4, 10.95):
            K.cyl('steel', (s * 27.5, -10, z), (s * 27.5, LEN - 2.5, z), 0.05, 6)
        # brackets under the gallery
        for yb in range(0, int(LEN), 5):
            K.prism('armor', [(s * W2, 6.5), (s * 27.8, 9.2), (s * W2, 9.2)], yb - 0.15, yb + 0.15)
        # gallery-level doors / lockers / lit windows on the wall
        for i, y0 in enumerate([a + 3.2 for a in RIBS[:-1]]):
            if (i + (s > 0)) % 2 == 0:
                K.box2('armor', (s * (W2 - 0.4), y0, 9.6), (s * W2, y0 + 8.6, 12.0))
                K.box2('white_dim', (s * (W2 - 0.45), y0 + 0.6, 10.6), (s * (W2 - 0.4), y0 + 8.0, 11.6))
                for k in range(1, 5):
                    K.box('armor', (s * (W2 - 0.45), y0 + 0.6 + k * 1.48, 11.1), (0.12, 0.16, 1.1))
            else:
                K.box2('armor', (s * (W2 - 0.5), y0 + 2, 9.6), (s * W2, y0 + 5, 12.0))
                K.box('orange', (s * (W2 - 0.52), y0 + 3.5, 12.1), (0.06, 1.2, 0.1))
        # upper control room (one per side, different places)
        y0 = 62 if s > 0 else 32
        K.prism('armor', [(s * W2, 13.4), (s * 28.4, 14.4), (s * 28.0, 18.0), (s * W2, 18.6)], y0, y0 + 11)
        K.box2('screen_bg', (s * 28.05, y0 + 0.6, 15.0), (s * 28.3, y0 + 10.4, 17.4))
        K.box2('white_dim', (s * 28.1, y0 + 0.8, 15.2), (s * 28.22, y0 + 10.2, 17.2))
        for k in range(1, 6):
            K.box('armor', (s * 28.1, y0 + 0.6 + k * 1.63, 16.2), (0.3, 0.2, 2.6))
        K.box2('neon', (s * 28.15, y0, 14.3), (s * 28.3, y0 + 11, 14.42))
        # horizontal pipe runs on the wall
        for z, r, m in [(6.2, 0.22, 'steel'), (5.6, 0.14, 'crate_o'), (16.9, 0.3, 'hull_lt'), (17.6, 0.16, 'steel')]:
            K.cyl(m, (s * (W2 - 0.55 - r), -10, z), (s * (W2 - 0.55 - r), LEN - 3, z), r, 8)


def crane():
    for s in (-1, 1):
        K.box2('steel', (s * 20.4, -10, 19.3), (s * 21.6, LEN - 4, 20.0))
        K.box2('dark', (s * 20.7, -10, 20.0), (s * 21.3, LEN - 4, 20.5))
    y = 70.0
    for dy in (-1.5, 1.5):
        K.box2('crate_o', (-21.8, y + dy - 0.45, 18.0), (21.8, y + dy + 0.45, 19.3))
        K.box2('dark', (-21.8, y + dy - 0.5, 18.55), (21.8, y + dy + 0.5, 18.75))
    K.box2('hazard', (-21.9, y - 2.0, 17.75), (21.9, y + 2.0, 18.0))
    for s in (-1, 1):
        K.box('dark', (s * 21.0, y, 19.0), (2.2, 4.6, 1.8))
        K.box('orange', (s * 19.85, y, 18.5), (0.12, 0.6, 0.3))
    tx = 11.0
    K.box('armor', (tx, y, 18.9), (4.6, 4.2, 1.9))
    K.box('hull_lt', (tx, y, 17.5), (3.0, 2.6, 1.0))
    K.box('orange', (tx - 2.35, y, 18.2), (0.1, 1.0, 0.25))
    K.box('orange', (tx + 2.35, y, 18.2), (0.1, 1.0, 0.25))
    K.box('white', (tx, y, 16.98), (1.6, 1.2, 0.06))
    K.spot('CraneSpot', (tx, y, 16.8), (tx, y, 0), 9000, (0.75, 0.88, 1.0), angle=70, blend=0.7)
    zc = 9.6          # carried container top
    for dx in (-1.1, 1.1):
        for dy in (-0.8, 0.8):
            K.cyl('dark', (tx + dx, y + dy, 17.0), (tx + dx, y + dy, zc + 0.9), 0.05, 6)
    K.box('armor', (tx, y, zc + 0.7), (3.4, 2.4, 0.5))
    K.box('hazard', (tx, y, zc + 0.38), (3.6, 2.6, 0.16))
    for dx in (-1.6, 1.6):
        K.box('steel', (tx + dx, y, zc - 0.3), (0.2, 2.7, 1.6))
    K.crate((tx, y, zc - 1.5), (5.6, 2.5, 2.6), 'crate_b', rot=90)


def bay_door():
    y0, y1 = LEN - 2.5, LEN + 3.5
    for s in (-1, 1):
        K.box2('hull_big', (s * DOOR_W2, y0, 0), (s * (W2 + 2), y1, HT))
        # chamfered upper corner of the opening
        K.prism('hull_big', [(s * DOOR_W2, DOOR_H - DOOR_CH), (s * DOOR_W2, DOOR_H), (s * (DOOR_W2 - DOOR_CH), DOOR_H)],
                y0, y1)
        # armoured frame collar on the inside face
        K.box2('armor', (s * DOOR_W2, y0 - 1.0, 0), (s * (DOOR_W2 + 3.0), y0, DOOR_H + 3.0))
        K.box2('hazard', (s * (DOOR_W2 + 0.1), y0 - 1.06, 0.2), (s * (DOOR_W2 + 2.9), y0 - 1.0, 4.0))
        bar('neon', (s * (DOOR_W2 + 0.5), y0 - 1.05, 4.6), (s * (DOOR_W2 + 0.5), y0 - 1.05, DOOR_H - DOOR_CH + 0.2), 0.16)
        bar('neon', (s * (DOOR_W2 + 0.5), y0 - 1.05, DOOR_H - DOOR_CH + 0.2),
            (s * (DOOR_W2 - DOOR_CH + 0.2), y0 - 1.05, DOOR_H + 0.5), 0.16)
        K.prism('armor', [(s * (DOOR_W2 + 0.1), DOOR_H - DOOR_CH - 0.4), (s * (DOOR_W2 + 3.0), DOOR_H - DOOR_CH + 2),
                          (s * (DOOR_W2 + 3.0), DOOR_H + 3), (s * (DOOR_W2 - DOOR_CH - 2), DOOR_H + 3),
                          (s * (DOOR_W2 - DOOR_CH - 0.4), DOOR_H + 0.1)], y0 - 1.0, y0)
        # field emitter nodes down each jamb (inside the opening)
        for z in [1.6 + 2.2 * i for i in range(5)]:
            K.box('armor', (s * (DOOR_W2 - 0.35), LEN + 0.5, z), (0.7, 2.2, 1.3))
            K.box('cyan_hot', (s * (DOOR_W2 - 0.72), LEN + 0.5, z), (0.06, 1.2, 0.5))
        # status light columns beside the door
        for z in [5 + 1.2 * i for i in range(7)]:
            K.box('orange' if z < 8 else 'cyan', (s * (DOOR_W2 + 2.2), y0 - 1.05, z), (0.5, 0.06, 0.25))
        # big angular buttress
        K.prism('hull', [(s * (DOOR_W2 + 3.0), 0), (s * (DOOR_W2 + 3.0), 19), (s * W2, 21), (s * W2, 0)], y0 - 2.2, y0 - 1.0)
    K.box2('hull_big', (-DOOR_W2, y0, DOOR_H), (DOOR_W2, y1, HT))
    K.box2('armor', (-DOOR_W2 + DOOR_CH - 2, y0 - 1.0, DOOR_H), (DOOR_W2 - DOOR_CH + 2, y0, DOOR_H + 3.0))
    bar('neon', (-DOOR_W2 + DOOR_CH - 0.2, y0 - 1.05, DOOR_H + 0.5), (DOOR_W2 - DOOR_CH + 0.2, y0 - 1.05, DOOR_H + 0.5), 0.16)
    for x in [-15 + 3 * i for i in range(11)]:
        K.box('armor', (x, LEN + 0.5, DOOR_H - 0.3), (1.4, 2.2, 0.6))
        K.box('cyan_hot', (x, LEN + 0.5, DOOR_H - 0.62), (0.6, 1.2, 0.06))
    # lintel machinery: retracted blast-door slabs + lights
    for i in range(6):
        K.box2('armor', (-DOOR_W2 + 2 + i * 7.4, y0 - 1.5 - 0.0, DOOR_H + 3.4), (-DOOR_W2 + 8.6 + i * 7.4, y0, HT - 2.6))
        K.box('orange', (-DOOR_W2 + 5.3 + i * 7.4, y0 - 1.53, DOOR_H + 3.9), (1.6, 0.06, 0.16))
    K.box2('hazard', (-DOOR_W2 + DOOR_CH, y0 - 1.06, DOOR_H + 2.2), (DOOR_W2 - DOOR_CH, y0 - 1.0, DOOR_H + 2.9))
    # threshold + outside landing lip
    K.box2('hazard', (-DOOR_W2, y0 - 6, 0.0), (DOOR_W2, y0 - 4.6, 0.02))
    K.box2('armor', (-DOOR_W2, y0, -1), (DOOR_W2, y1 + 16, 0.0))
    K.box2('floor_dk', (-DOOR_W2 + 2, y1, 0.0), (DOOR_W2 - 2, y1 + 15, 0.05))
    for s in (-1, 1):
        K.box2('neon', (s * (DOOR_W2 - 2.2), y1, 0.05), (s * (DOOR_W2 - 2.0), y1 + 15, 0.12))
        for k in range(6):
            K.box('orange', (s * (DOOR_W2 - 1.0), y1 + 1.5 + k * 2.6, 0.1), (0.5, 0.5, 0.2))
    K.box2('cyan', (-DOOR_W2 + 0.4, LEN + 0.42, 0.0), (DOOR_W2 - 0.4, LEN + 0.58, 0.04))

    def inside(a, b):
        x = a - DOOR_W2
        return abs(x) + b < DOOR_W2 + DOOR_H - DOOR_CH
    K.force_field('BayField', (-DOOR_W2, LEN + 0.5, 0), (1, 0, 0), (0, 0, 1), 2 * DOOR_W2, DOOR_H, tri=2.3,
                  inside=inside, strength=float(A.get('field', 0.7)), edge=2.6, alpha=(0.02, 0.2), gap=0.055)
    K.area('FieldGlow', (0, LEN - 3, 7.5), (40, 13), 14000, (0.2, 0.55, 1.0), rot=(90, 0, 0), spread=160)


def floor_marks():
    # central taxi lane to the door
    K.box2('floor_dk', (-7.5, -10, 0.0), (7.5, LEN - 2.5, 0.015))
    for s in (-1, 1):
        K.box2('dark', (s * 7.5, -10, 0.0), (s * 8.3, LEN - 8, 0.03))
        K.box2('neon', (s * 7.8, -10, 0.02), (s * 8.0, LEN - 8, 0.06))
        K.box2('paint_w', (s * 9.0, -10, 0.0), (s * 9.25, LEN - 8, 0.02))
        K.box2('floor_dk', (s * 25.0, -10, 0.0), (s * 26.4, LEN - 3, 0.02))
    y = -6.0
    while y < LEN - 12:
        K.box2('paint_w', (-0.15, y, 0.015), (0.15, y + 3.0, 0.03))
        y += 6.0
    # chevrons pointing at the door
    for y in range(8, int(LEN) - 14, 15):
        for s in (-1, 1):
            K.box('paint_y', (s * 2.6, y + 15.0 / 2 - 6, 0.025), (0.5, 4.6, 0.02), rot=s * 38)
    # parking bays (between ribs) with outlines, numbers replaced by bar codes of light, tie-down points
    for i, y0 in enumerate(RIBS[:-1]):
        yc = y0 + 7.5
        for s in (-1, 1):
            xa, xb = s * 11.0, s * 24.6
            K.box2('paint_w', (min(xa, xb), yc - 5.2, 0.0), (max(xa, xb), yc - 5.0, 0.02))
            K.box2('paint_w', (min(xa, xb), yc + 5.0, 0.0), (max(xa, xb), yc + 5.2, 0.02))
            K.box2('hazard', (min(xa, xa + s * 0.6), yc - 5.2, 0.0), (max(xa, xa + s * 0.6), yc + 5.2, 0.025))
            K.box2('floor_dk', (min(s * 12.5, s * 23.5), yc - 3.6, 0.0), (max(s * 12.5, s * 23.5), yc + 3.6, 0.03))
            for k in range(-2, 3):
                K.box('cyan' if (i + k) % 3 else 'orange', (s * 11.9, yc + k * 0.5, 0.03), (0.5, 0.2, 0.04))
            for dx in (13.5, 22.5):
                for dy in (-3.0, 3.0):
                    K.cyl('steel', (s * dx, yc + dy, 0.0), (s * dx, yc + dy, 0.06), 0.3, 8)
                    K.box('orange', (s * dx, yc + dy, 0.07), (0.16, 0.16, 0.04))
    # arrival pad just inside the door
    yp = LEN - 20
    n = 40
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.62) / n
        for r, m, w in [(6.4, 'cyan', 0.16), (5.2, 'paint_w', 0.1)]:
            if m == 'paint_w' and i % 2:
                continue
            p0 = (r * math.cos(a0), yp + r * math.sin(a0), 0.04)
            p1 = (r * math.cos(a1), yp + r * math.sin(a1), 0.04)
            bar(m, p0, p1, w)
    K.cyl('floor_dk', (0, yp, 0.0), (0, yp, 0.03), 6.2, 40, smooth=False)
    for a in range(0, 360, 90):
        K.box('paint_y', (3.4 * math.cos(math.radians(a + 45)), yp + 3.4 * math.sin(math.radians(a + 45)), 0.04),
              (2.6, 0.4, 0.02), rot=a + 45)
    # floor grates / drains along the lane
    for y in range(0, int(LEN) - 10, 10):
        for s in (-1, 1):
            K.box('dark', (s * 10.1, y + 5, 0.01), (0.9, 3.0, 0.03))
            for k in range(6):
                K.box('steel', (s * 10.1, y + 3.75 + k * 0.5, 0.03), (0.8, 0.08, 0.03))


def props():
    # crate stacks tucked against ribs
    for y in RIBS:
        for s in (-1, 1):
            if rnd.random() < 0.85:
                n = rnd.randint(1, 3)
                for j in range(n):
                    kind = rnd.choice(['crate', 'crate', 'crate_b', 'crate_o'])
                    sz = rnd.choice([(2.4, 2.4, 2.4), (2.0, 3.6, 2.2), (2.4, 2.4, 1.6)])
                    x = s * (24.4 - j * 0.1)
                    yy = y + rnd.choice([-1, 1]) * (2.6 + rnd.random() * 0.4) if j == 0 else y + rnd.uniform(-3.5, 3.5)
                    z = sz[2] / 2 + (2.4 if j == 2 else 0)
                    if j == 1:
                        x = s * 21.6
                    K.crate((x, yy, z), sz, kind, rot=rnd.uniform(-6, 6))
            for k in range(rnd.randint(0, 4)):
                K.barrel((s * (25.6 - rnd.random() * 1.5), y + rnd.uniform(-4.5, 4.5), 0), mat_=rnd.choice(['crate_b', 'crate_o', 'steel']))
    # service gantry arms reaching over two bays
    for (s, y) in [(-1, 47.5), (1, 77.5), (1, 32.5)]:
        K.box('armor', (s * 25.6, y - 4.6, 4.0), (1.2, 1.2, 8.0))
        K.box('hull_lt', (s * 21.5, y - 4.6, 7.4), (9.4, 0.7, 0.7))
        K.prism('steel', [(s * 25.0, 4.2), (s * 25.0, 4.8), (s * 18.0, 7.6), (s * 18.0, 7.1)], y - 4.75, y - 4.45)
        K.box('armor', (s * 17.2, y - 4.6, 6.6), (1.4, 1.2, 2.2))
        K.box('white', (s * 17.2, y - 4.6, 5.47), (0.9, 0.8, 0.05))
        K.spot('ArmSpot', (s * 17.2, y - 4.4, 5.3), (s * 17.5, y, 0), 2600, (0.8, 0.9, 1.0), angle=95, blend=0.6)
        K.pipe('rubber', [(s * 25.0, y - 4.2, 7.0), (s * 22, y - 4.1, 6.3), (s * 19.5, y - 3.2, 3.0), (s * 19.0, y - 2.4, 0.3)], 0.09, 6)
    # tool carts / fuel bowsers / generators on the apron
    for (x, y, r) in [(-10.6, 20.5, 4), (10.4, 50, -8), (-10.4, 83, 3), (10.6, 95, 0), (10.8, 22, 6)]:
        K.box('crate_o', (x, y, 0.95), (1.5, 2.6, 1.1), rot=r)
        K.box('dark', (x, y, 0.35), (1.3, 2.9, 0.3), rot=r)
        K.box('steel', (x, y + 0.5, 1.7), (1.1, 1.0, 0.4), rot=r)
        K.box('cyan', (x - 0.76 * (1 if x < 0 else -1), y, 1.2), (0.04, 0.8, 0.14), rot=r)
        K.cyl('crate_b', (x, y - 0.9, 1.5), (x, y - 0.9, 2.3), 0.3, 10)
    # ladders up to the gallery
    for (s, y) in [(-1, 19), (1, 19), (-1, 79), (1, 94)]:
        for dy in (-0.4, 0.4):
            K.box('steel', (s * 27.2, y + dy, 5.0), (0.08, 0.08, 9.4))
        for k in range(22):
            K.box('steel', (s * 27.2, y, 0.6 + k * 0.42), (0.06, 0.8, 0.06))


def detail():
    """Film-set pass: dressed walls, ceiling trusses and looms, maintenance props, umbilicals, drones."""
    L = LEN - 2.6 + 10
    for s in (-1, 1):
        ctrl = 62 if s > 0 else 32
        ycoord = (lambda u, s=s: (-10 + u) if s > 0 else (LEN - 2.6 - u))
        skip_hi = (lambda u, z, yc=ycoord, c=ctrl: c - 1 < yc(u) < c + 12)
        if s > 0:
            org, ang = (W2 - 0.05, -10), 90
        else:
            org, ang = (-W2 + 0.05, LEN - 2.6), -90
        D.dress_wall(org, ang, L, 3.3, 8.6, seed=11 + s, cell=(3.0, 2.65))
        D.dress_wall(org, ang, L, 13.5, 18.5, seed=13 + s, cell=(3.0, 2.5), skip=skip_hi)
        D.dress_wall(org, ang, L, 20.1, HT - 0.2, seed=15 + s, cell=(3.0, 3.7), trim=False,
                     weights=[(D._pipes, 3), (D._plate, 3), (D._vent, 2), (D._cables, 2)])
        # door-wall buttress faces
        D.dress_wall((s * 32 if s > 0 else -26, LEN - 4.75), 180, 6.0, 0.2, 18.0, seed=17 + s, cell=(3.0, 2.55))
        # longitudinal ceiling trusses + hanging looms
        for x in (3.2, 19.6):
            D.truss((s * x, -10, 23.0), (s * x, LEN - 3, 23.0), depth=1.7, width=1.0, mat='armor', r=0.1, bay=2.5)
        for k, y in enumerate(range(4, int(LEN) - 8, 15)):
            D.cable_loom((s * 19.6, y + 3, 21.4), (s * 26.5, y + 3 + (k % 2) * 2, 19.0), n=4, sag=1.6, r=0.06, seed=k + s)
            D.cable_loom((s * 5.5, y + 6, 22.6), (s * 15.2, y + 9, 22.8), n=4, sag=1.3, r=0.06, seed=20 + k + s)
            D.cable_loom((s * 27.4, y + 1, 9.0), (s * 27.4, y + 7.5, 9.0), n=3, sag=0.9, r=0.045, seed=40 + k + s, spread=0.12)
        # gallery furniture: stations under the lit windows, lockers, crates
        for i, y0 in enumerate([a + 3.2 for a in RIBS[:-1]]):
            if (i + (s > 0)) % 2 == 0:
                for q in range(2):
                    D.crew_station((s * 31.0, y0 + 2.4 + q * 3.8, 9.6), -90 if s > 0 else 90, 3.0, 'screen_c', seed=i * 2 + q)
            else:
                K.crate((s * 30.4, y0 + 7.0, 10.5), (1.6, 1.6, 1.8), 'crate', rot=4)
                K.barrel((s * 30.6, y0 + 1.0, 9.6), r=0.35, h=1.0)
        # bay front trenches with strip lights
        D.floor_trench((s * 10.4, -8), (s * 10.4, LEN - 9), w=0.7)
    # wall washes so the dressed walls and roof structure read
    for y0 in [RIBS[0] - 15] + RIBS:
        yc = y0 + 7.5
        for s in (-1, 1):
            K.area('WashLo', (s * 27.0, yc, 2.2), (0.6, 9.0), 2600, (0.35, 0.6, 1.0), rot=(0, s * 125, 0), spread=150)
            K.area('WashHi', (s * 25.5, yc, 12.4), (0.6, 9.0), 6000, (0.35, 0.6, 1.0), rot=(0, s * 118, 0), spread=150)
            K.box('dark', (s * 27.3, yc, 12.1), (0.5, 9.2, 0.3))
            K.box('slot', (s * 27.5, yc, 12.28), (0.2, 8.6, 0.05))
            K.point('Roof', (s * 22.5, yc, 20.6), 1500, (0.4, 0.62, 1.0), r=0.6)
    # track and tyre marks, scuffed turn-ins to the bays
    K.MATDEF['scuffmark'] = lambda n: K._plain(n, (0.018, 0.019, 0.022), rough=0.8)
    rs = random.Random(21)
    for x in (-4.6, -1.9, 1.3, 4.0, -6.4, 6.3):
        y = -8.0
        while y < LEN - 12:
            Lm = rs.uniform(6, 22)
            K.box('scuffmark', (x + rs.uniform(-0.15, 0.15), y + Lm / 2, 0.021), (rs.uniform(0.35, 0.6), Lm, 0.004), rot=rs.uniform(-1.2, 1.2))
            y += Lm + rs.uniform(1, 9)
    for y0 in RIBS[:-1]:
        for s in (-1, 1):
            for dy in (-1.3, 1.3):
                for q in range(5):
                    a = q * 16
                    K.box('scuffmark', (s * (7.2 + q * 1.7), y0 + 7.5 + dy - (4 - q) * 1.5, 0.021), (0.5, 2.6, 0.004), rot=-s * (20 + a))
    for y in range(-4, int(LEN) - 14, 6):
        for s in (-1, 1):
            K.box('dark', (s * 6.6, y, 0.02), (0.5, 0.5, 0.04))
            K.box('cyan' if (y // 6) % 3 else 'orange', (s * 6.6, y, 0.045), (0.26, 0.26, 0.03))
    # every parked tank is on charge: socket box by the bay wall, umbilicals to the hull
    i = 0
    for y0 in RIBS[:-1]:
        yc = y0 + 7.5
        for s in (-1, 1):
            if (y0, s) == (55, -1):
                continue
            D.umbilical((s * 24.2, yc - 3.4, 0), (s * 20.6, yc - 1.9, 1.5), seed=i)
            for sd in (-1, 1):                                     # wheel chocks
                K.box('paint_y', (s * 14.2, yc + sd * 2.4, 0.15), (0.5, 0.9, 0.3), taper=(0.4, 1))
            if i % 3 == 0:
                D.ammo_rack((s * 23.6, yc + 3.3, 0), 90 if s < 0 else -90, seed=i)
            elif i % 3 == 1:
                D.fuel_rack((s * 24.0, yc + 3.4, 0), 90 if s < 0 else -90, n=3)
            else:
                D.tool_cart((s * 22.8, yc + 3.6, 0), 20 * s, seed=i)
            D.chevrons((s * 11.6, yc, 0), 180 if s > 0 else 0, n=2, s=0.9)
            i += 1
    # the empty bay (port side, y 62.5) is a maintenance pit: loader arm with a module, racks, parts
    D.loader_arm((-21.5, 60.5, 0), -60, reach=5.5, lift=4.6, seed=1)
    D.ammo_rack((-15.5, 66.2, 0), 180, seed=3)
    D.ammo_rack((-19.2, 66.4, 0), 180, rows=2, seed=4)
    D.fuel_rack((-23.5, 66.0, 0), 180, n=4)
    D.tool_cart((-14.0, 60.0, 0), 75, seed=5)
    K.crate((-16.5, 62.0, 0.7), (2.6, 1.8, 1.4), 'crate_b', rot=12)
    D.umbilical((-24.2, 59.2, 0), (-18.0, 62.2, 1.5), seed=9)
    # second arm on the starboard side working over a parked tank
    D.loader_arm((23.4, 51.5, 0), 125, reach=5.0, lift=5.2, seed=2, load=False)
    # hero tank in the foreground: cart, umbilical, drone with a work light
    D.tool_cart((9.6, 50.5, 0), -15, seed=6)
    D.umbilical((10.2, 55.5, 0), (7.6, 54.0, 1.5), seed=7)
    D.drone((6.5, 56.0, 6.2), 200, s=1.2, beam=(5.6, 54.5, 2.0))
    D.drone((-17.0, 64.0, 7.0), 30, s=1.1, beam=(-17.5, 62.0, 1.0))
    D.drone((15.5, 78.5, 6.0), -60, s=1.0, beam=(18.0, 77.5, 2.5))
    D.drone((-9.0, 92.0, 9.5), 80, s=1.0)
    D.drone((-15.0, 79.0, 5.6), -30, s=1.0, beam=(-17.5, 77.5, 2.5))
    # apron clutter along the lane edges
    for k, (x, y, r) in enumerate([(-10.9, 55.0, 5), (10.9, 66.0, -6), (-10.9, 73.0, 3), (10.9, 88.0, 0), (-10.9, 44.0, 0), (10.9, 44.5, 8)]):
        if k % 2:
            D.tool_cart((x, y, 0), 90 + r, seed=k)
        else:
            D.fuel_rack((x, y, 0), 90 if x < 0 else -90, n=2)
    # crane: maintenance cab, cable festoon along the girder, more beacons
    for x in range(-18, 19, 4):
        D.cable_loom((x, 70 + 2.1, 18.0), (x + 4, 70 + 2.1, 18.0), n=2, sag=0.9, r=0.05, seed=x, spread=0.05)
    K.box('armor', (-15.5, 70, 16.9), (3.0, 3.2, 1.9))
    K.box('screen_bg', (-15.5, 68.38, 17.0), (2.4, 0.04, 0.9))
    K.box('screen_c', (-15.5, 68.35, 17.2), (1.6, 0.02, 0.08))
    K.box('screen_o', (-15.9, 68.35, 16.9), (0.8, 0.02, 0.08))
    K.box('orange', (-15.5, 70, 15.9), (1.0, 1.0, 0.12))
    D.ladder((-15.5, 71.7, 17.9), 0, 1.6, cage=False)
    # door frame: maintenance platforms either side of the opening with railings and consoles
    for s in (-1, 1):
        K.box2('hull_lt', (min(s * 23.5, s * 31.5), LEN - 9.5, 5.6), (max(s * 23.5, s * 31.5), LEN - 3.6, 6.0))
        D.handrail((s * 23.7, LEN - 9.4, 6.0), (s * 31.3, LEN - 9.4, 6.0))
        D.handrail((s * 23.7, LEN - 9.4, 6.0), (s * 23.7, LEN - 3.8, 6.0))
        D.crew_station((s * 27.5, LEN - 5.0, 6.0), 180, 3.4, 'screen_c', seed=70 + s)
        for x in (24.0, 31.0):
            K.box('armor', (s * x, LEN - 9.2, 2.8), (0.5, 0.5, 5.6))
        D.ladder((s * 29.5, LEN - 9.6, 0), 180, 5.8)
        K.box('slot', (s * 27.5, LEN - 6.5, 5.55), (5.0, 0.4, 0.05))
        K.area('PlatU', (s * 27.5, LEN - 6.5, 5.4), (6, 3), 1500, (0.3, 0.55, 1.0))


def vehicles():
    kinds = ['bulwark', 'lancer', 'javelin', 'lancer', 'longbow', 'bulwark', 'outrider', 'javelin', 'lancer', 'skimmer',
             'bulwark', 'longbow']
    i = 0
    for y0 in RIBS[:-1]:
        for s in (-1, 1):
            yc = y0 + 7.5
            if (y0, s) in [(55, -1)]:         # empty bay (its tank is rolling out)
                continue
            k = kinds[i % len(kinds)]
            i += 1
            K.tank(k, (s * 18.0, yc, 0.0), rz=(0 if s < 0 else 180) + rnd.uniform(-3, 3))
    for y0 in RIBS[:-1]:                                   # a pool of light over every parking bay
        for s in (-1, 1):
            K.box('dark', (s * 26.6, y0 + 7.5, 8.5), (1.6, 3.0, 0.4))
            K.box('white', (s * 26.4, y0 + 7.5, 8.28), (1.0, 2.4, 0.05))
            K.spot('Bay', (s * 26.0, y0 + 7.5, 8.2), (s * 17.5, y0 + 7.5, 0), 5200, (0.78, 0.9, 1.0), angle=100, blend=0.6, r=0.5)
            K.area('Wash', (s * 29.5, y0 + 7.5, 10.2), (1.0, 9.0), 900, (0.25, 0.5, 1.0), rot=(0, s * 150, 0), spread=140)
    K.tank('bulwark', (1.0, 79, 0.0), rz=90)               # rolling out along the lane
    K.tank('lancer', (-3.2, 88, 0.0), rz=92)
    K.tank('bulwark', (5.4, 53.0, 0.0), rz=96)             # foreground hero
    K.tank('condor', (0, LEN - 20, 5.2), rz=-90)           # dropship settling on the arrival pad


def outside(sc):
    K.space_world(sc, nebula=0.5)
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 5.0
    sun.color = (1.0, 0.93, 0.85)
    sun.angle = math.radians(1.5)
    o = bpy.data.objects.new('Sun', sun)
    sc.collection.objects.link(o)
    o.rotation_euler = (math.radians(-64), 0, math.radians(14))    # shines in through the door
    try:
        sys.path.insert(0, os.path.join(HERE, '..'))
        sys.path.insert(0, os.path.join(HERE, '..', '..', 'art', 'v2'))
        import forge as F
        import terran_fleet as T
        F.ST.update(parts=[], mats={}, group='Hull', seq=0)
        for (builder, loc, rz, sca, ry) in [(T.terran_frigate_v2, (-70, LEN + 520, 62), 205, 9.0, 8),
                                            (T.terran_corvette, (60, LEN + 260, 18), 160, 7.0, -12),
                                            (T.broadside_battleship, (260, LEN + 1500, 190), 170, 14.0, 5)]:
            r = builder()
            ship = r[0] if isinstance(r, tuple) else r
            for p in ship.data.polygons:
                p.use_smooth = True
            T.neon_lines(ship)
            ship.location = loc
            ship.rotation_euler = (0, math.radians(ry), math.radians(rz))
            ship.scale = (sca,) * 3
    except Exception as e:      # the ships are only set dressing
        print('SHIPS SKIPPED', repr(e))


def main():
    K.E.update(neon=1.0, cyan=1.0, orange=1.8, white=1.0)
    K.MATDEF['neon'] = lambda n: K._emit(n, (0.012, 0.19, 1.0), 4.5)
    K.MATDEF['neon_dim'] = lambda n: K._emit(n, (0.012, 0.19, 1.0), 2.0)
    K.MATDEF['slot'] = lambda n: K._emit(n, (0.2, 0.5, 1.0), 4.0)
    sc, cam = K.reset(samples=int(A.get('samples', 20)), exposure=float(A.get('exposure', 0.6)))
    outside(sc)
    shell()
    ribs()
    ceiling()
    gallery()
    crane()
    bay_door()
    floor_marks()
    props()
    detail()
    K.flush()
    vehicles()
    if VIEW == 'door':
        K.look(cam, (-4.8, 41.0, 3.1), (1.0, 112, 7.6), lens=20)
    elif VIEW == 'side':
        K.look(cam, (-24.0, 52, 12.6), (5, 108, 3.0), lens=19)
    else:
        K.look(cam, (0, 40, 60), (0, 70, 0), lens=18)
    raw = os.path.join(OUT, '_raw', NAME + '.png')
    K.render(sc, raw, RES, depth_far=130.0)
    K.post(raw, A.get('final', os.path.join(OUT, NAME + '.jpg')), haze=float(A.get('haze', 0.45)),
           scatter=float(A.get('scatter', 0.22)), haze_col=(0.08, 0.25, 0.6))


if __name__ == '__main__':
    main()
