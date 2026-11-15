"""Terran capital ship - a boarding deck seen from the GAME CAMERA (roof removed, RTS angle).

    python terran_deck.py [--out=DIR] [--name=deck] [--res=960x540] [--samples=20] [--view=wide|close|gen]
                          [--final=PATH.jpg]

The deck is laid out on the game's 2 m cell grid: every cell is floor (drivable), wall (blocked) or
window. Corridors are 16 m wide (three tanks abreast). Map is 140 x 92 m; the far (+Y) and right (+X)
sides are the outer hull. LAYOUT below is the single source of truth for the map.
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
NAME = A.get('name', 'deck')
RES = tuple(int(v) for v in A.get('res', '960x540').split('x'))
VIEW = A.get('view', 'wide')

C = 2.0
NX, NY = 70, 46
H = 6.0
rnd = random.Random(11)

# drivable rectangles (x0, y0, x1, y1) in metres
ROOMS = {
    'hangar': (46, 52, 94, 88),
    'corridor': (0, 28, 136, 44),
    'reactor': (4, 52, 40, 88),
    'command': (100, 52, 136, 88),
    'store': (4, 4, 30, 22),
    'genroom': (36, 12, 50, 28),
    'lift': (54, 4, 90, 22),
    'workshop': (94, 4, 136, 22),
}
DOORS = {   # openings through walls: (x0, y0, x1, y1)
    'hangar': (62, 44, 78, 52),
    'reactor': (14, 44, 30, 52),
    'command': (110, 44, 126, 52),
    'store': (10, 22, 22, 28),
    'lift': (64, 22, 80, 28),
    'workshop': (106, 22, 122, 28),
    'bay': (56, 88, 84, 92),          # the port in the outer hull (force field)
}
WINDOWS = [(8, 88, 18, 92), (26, 88, 36, 92), (104, 88, 116, 92), (120, 88, 132, 92),
           (136, 56, 140, 68), (136, 72, 140, 84)]

FLOOR, WALL, WIN = 0, 1, 2
grid = [[WALL] * NY for _ in range(NX)]


def carve(r, v=FLOOR):
    for i in range(int(r[0] / C), int(r[2] / C)):
        for j in range(int(r[1] / C), int(r[3] / C)):
            grid[i][j] = v


def cell(i, j):
    if 0 <= i < NX and 0 <= j < NY:
        return grid[i][j]
    return None


def bar(mat, p0, p1, r):
    K.cyl(mat, p0, p1, r, n=4, smooth=False)


# ------------------------------------------------------------------ structure
def structure():
    for r in list(ROOMS.values()) + list(DOORS.values()):
        carve(r)
    for r in WINDOWS:
        carve(r, WIN)
    K.box2('deck', (0, 0, -1.5), (NX * C, NY * C, 0))
    # how deep inside a wall mass each wall cell is
    for i in range(NX):
        for j in range(NY):
            if grid[i][j] != WALL:
                continue
            x, y = i * C, j * C
            edge = any(cell(i + a, j + b) in (FLOOR, WIN) for a in (-1, 0, 1) for b in (-1, 0, 1))
            if edge:
                K.box2('hull', (x, y, 0), (x + C, y + C, H))
                K.box2('walltop', (x, y, H), (x + C, y + C, H + 0.12))
            else:
                h = H - 1.0
                K.box2('armor', (x, y, 0), (x + C, y + C, h))
                k = rnd.random()
                if k < 0.22:
                    s = rnd.uniform(0.8, 1.7)
                    K.box('hull', (x + 1, y + 1, h + 0.3), (s, rnd.uniform(0.8, 1.7), 0.6))
                elif k < 0.3:
                    K.box('hull_lt', (x + 1, y + 1, h + 0.2), (1.4, 1.4, 0.4))
                    for q in range(4):
                        K.box('dark', (x + 1, y + 0.55 + q * 0.3, h + 0.42), (1.2, 0.1, 0.06))
                elif k < 0.34:
                    K.cyl('hull_lt', (x + 1, y + 1, h), (x + 1, y + 1, h + 0.7), 0.6, 10)
                elif k < 0.37:
                    K.box(rnd.choice(('orange', 'cyan')), (x + 1, y + 1, h + 0.06), (0.3, 0.3, 0.12))
            # neon trim along every top edge that borders open floor + a skirt at the wall foot
            for (a, b) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = cell(i + a, j + b)
                if nb not in (FLOOR, WIN):
                    continue
                cx, cy = x + C / 2 + a * (C / 2 - 0.22), y + C / 2 + b * (C / 2 - 0.22)
                sx, sy = (0.1, C) if a else (C, 0.1)
                K.box('neon', (cx, cy, H + 0.16), (sx, sy, 0.1))
                if nb == FLOOR:
                    fx, fy = x + C / 2 + a * (C / 2 + 0.2), y + C / 2 + b * (C / 2 + 0.2)
                    K.box('armor', (fx, fy, 0.45), ((0.4, C) if a else (C, 0.4)) + (0.9,), taper=None)
    # pipe runs across the big wall masses
    for (p0, p1) in [((42, 60), (42, 86)), ((43.2, 60), (43.2, 86)), ((97, 58), (97, 86)), ((2, 6), (2, 24)),
                     ((32, 6), (32, 20)), ((33.2, 2), (33.2, 20)), ((52, 2), (52, 22)), ((92, 2), (92, 24)),
                     ((138, 2), (138, 50)), ((4, 2), (134, 2)), ((2, 48), (10, 48)), ((34, 48), (58, 48)),
                     ((82, 48), (106, 48)), ((130, 48), (138, 48)), ((2, 90), (4, 90)), ((40, 90), (54, 90)),
                     ((86, 90), (102, 90))]:
        K.cyl('hull_lt', (p0[0], p0[1], H - 0.6), (p1[0], p1[1], H - 0.6), 0.32, 8)
        d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0))
        n = int(d.length / 4)
        for q in range(n + 1):
            p = Vector((p0[0], p0[1], H - 0.6)) + d * (q / max(n, 1))
            K.box('dark', p, (0.9, 0.9, 0.9))


def wall_faces():
    """Dress the wall faces the camera sees (those facing -Y) and, lighter, the side faces."""
    for i in range(NX):
        for j in range(1, NY):
            if grid[i][j] != WALL or grid[i][j - 1] != FLOOR:
                continue
            x, y = i * C, j * C
            k = (i * 7 + j * 3) % 8
            if k == 0:                       # vertical neon accent
                K.box('dark', (x + 1, y - 0.06, 3.0), (0.5, 0.12, 4.6))
                K.box('neon', (x + 1, y - 0.13, 3.0), (0.14, 0.06, 4.2))
            elif k == 3:                     # vent
                K.box('armor', (x + 1, y - 0.1, 3.4), (1.6, 0.2, 1.8))
                for q in range(5):
                    K.box('dark', (x + 1, y - 0.21, 2.75 + q * 0.33), (1.4, 0.04, 0.12))
            elif k == 5:                     # locker / panel + status lights
                K.box('hull_lt', (x + 1, y - 0.12, 2.2), (1.5, 0.24, 2.6))
                K.box('orange', (x + 0.6, y - 0.25, 3.0), (0.2, 0.04, 0.12))
                K.box('cyan', (x + 1.3, y - 0.25, 3.0), (0.2, 0.04, 0.12))
            elif k == 6:
                K.box('screen_bg', (x + 1, y - 0.06, 3.4), (1.7, 0.1, 1.3))
                K.box('screen', (x + 1, y - 0.12, 3.4), (1.3, 0.04, 0.12))
                K.box('screen_c', (x + 0.8, y - 0.12, 3.75), (0.9, 0.04, 0.1))
            K.box('armor', (x + 1, y - 0.08, 5.3), (C, 0.16, 0.5))
    # horizontal pipes along the far walls of the corridor
    for (x0, x1, y) in [(4, 14, 44), (30, 62, 44), (78, 110, 44), (126, 136, 44)]:
        K.cyl('steel', (x0, y - 0.25, 4.6), (x1, y - 0.25, 4.6), 0.14, 8)
        K.cyl('crate_o', (x0, y - 0.2, 4.2), (x1, y - 0.2, 4.2), 0.09, 8)


def doorway(name, r, field=False):
    """Armoured jambs + threshold stripes at an opening. Vertical openings in this map all run along X."""
    x0, y0, x1, y1 = r
    ym = (y0 + y1) / 2
    for (x, s) in ((x0, -1), (x1, 1)):
        K.box2('armor', (min(x, x + s * 1.2), y0 - 0.3, 0), (max(x, x + s * 1.2), y1 + 0.3, H + 1.3))
        K.box('walltop', (x + s * 0.6, ym, H + 1.36), (1.2, y1 - y0 + 0.6, 0.12))
        K.box2('hull_lt', (min(x, x - s * 0.5), y0 - 0.5, 0), (max(x, x - s * 0.5), y1 + 0.5, 2.6))     # inner pilaster
        K.box('orange', (x - s * 0.52, y0 - 0.52, 2.0), (0.3, 0.06, 0.5))
        K.box('orange', (x + s * 0.6, y0 - 0.32, H + 0.9), (0.6, 0.06, 0.2))
        K.box('neon', (x + s * 0.6, ym, H + 1.44), (0.16, y1 - y0 + 0.2, 0.08))
    for y in (y0 - 0.2, y1 + 0.2):
        K.box('hazard', ((x0 + x1) / 2, y, 0.02), (x1 - x0 - 1.0, 1.0, 0.04))
    if field:
        yf = ym
        for (x, s) in ((x0, 1), (x1, -1)):
            K.box('armor', (x + s * 0.35, yf, 3.0), (0.7, 1.4, 6.0))
            for z in (1.0, 2.5, 4.0, 5.5):
                K.box('cyan_hot', (x + s * 0.72, yf, z), (0.06, 0.8, 0.7))
        K.box('dark', ((x0 + x1) / 2, yf, 0.03), (x1 - x0, 0.7, 0.06))
        K.box('cyan', ((x0 + x1) / 2, yf, 0.07), (x1 - x0, 0.22, 0.04))
        K.force_field('Field_' + name, (x0 + 0.7, yf, 0.1), (1, 0, 0), (0, 0, 1), x1 - x0 - 1.4, H + 0.6, tri=2.0,
                      strength=2.6, edge=7.0, alpha=(0.1, 0.5), gap=0.07, seed=len(name))
        K.area('FG_' + name, ((x0 + x1) / 2, yf - 0.4, 3), (x1 - x0, 5), 2500, (0.2, 0.6, 1.0), rot=(90, 0, 0))


def conduit(pts, w=0.5):
    """Glowing power line let into the floor (generator -> door), with junction boxes at the corners."""
    for a, b in zip(pts[:-1], pts[1:]):
        lo = (min(a[0], b[0]) - w / 2, min(a[1], b[1]) - w / 2, 0)
        hi = (max(a[0], b[0]) + w / 2, max(a[1], b[1]) + w / 2, 0.05)
        K.box2('dark', (lo[0] - 0.35, lo[1] - 0.35, 0), (hi[0] + 0.35, hi[1] + 0.35, 0.04))
        K.box2('cyan', lo, hi[:2] + (0.07,))
    for p in pts:
        K.cyl('armor', (p[0], p[1], 0), (p[0], p[1], 0.18), 1.0, 8, smooth=False)
        K.cyl('cyan_hot', (p[0], p[1], 0.18), (p[0], p[1], 0.22), 0.5, 8, smooth=False)


def generator(c, r=4.2, name='Gen'):
    """Force-field generator, a mission target: three heavy dark claws (orange armour bands, blue
    spine lines, orange tip beacons) gripping a faceted blue crystal. Three-fold star from above,
    so it cannot be mistaken for the round banded reactor."""
    x, y = c
    K.cyl('hazard', (x, y, 0), (x, y, 0.06), r * 1.45, 6, smooth=False)
    K.cyl('armor', (x, y, 0), (x, y, 0.9), r * 0.6, 6, smooth=False)
    K.cyl('walltop', (x, y, 0.9), (x, y, 1.1), r * 0.48, 6, smooth=False)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        ca, sa = math.cos(a), math.sin(a)
        foot = Vector((x + ca * r * 1.2, y + sa * r * 1.2, 0.0))
        top = Vector((x + ca * r * 0.42, y + sa * r * 0.42, 8.2))
        d = top - foot
        K.box('armor', (foot.x, foot.y, 0.7), (2.6, 2.6, 1.4), rot=math.degrees(a))
        K.cyl('armor', foot + Vector((0, 0, 0.6)), top, 1.25, 4, r1=0.6, smooth=False)
        K.cyl('paint_y', foot + d * 0.38, foot + d * 0.56, 1.15, 4, r1=1.0, smooth=False)
        out = Vector((ca, sa, 0))
        bar('neon', foot + d * 0.6 + out * 0.75, foot + d * 0.95 + out * 0.6, 0.1)
        K.box('orange', (top.x, top.y, top.z + 0.15), (0.6, 0.6, 0.3), rot=math.degrees(a))
        K.box('orange', (foot.x + ca * 1.35, foot.y + sa * 1.35, 0.9), (0.12, 0.9, 0.3), rot=math.degrees(a))
        # inward talon towards the crystal
        K.cyl('steel', top, (x + ca * 0.5, y + sa * 0.5, 6.6), 0.35, 4, r1=0.1, smooth=False)
    # faceted crystal (two pyramids) with brighter edges
    zb, zm, zt, rc = 1.6, 4.0, 6.4, 1.7
    K.cyl('crystal', (x, y, zb), (x, y, zm), 0.05, 4, r1=rc, smooth=False)
    K.cyl('crystal', (x, y, zm), (x, y, zt), rc, 4, r1=0.05, smooth=False)
    for q in range(4):
        a0, a1 = math.radians(90 * q), math.radians(90 * q + 90)
        p0 = (x + rc * math.cos(a0), y + rc * math.sin(a0), zm)
        p1 = (x + rc * math.cos(a1), y + rc * math.sin(a1), zm)
        bar('cyan', p0, p1, 0.05)
        bar('cyan', p0, (x, y, zt), 0.05)
        bar('cyan', p0, (x, y, zb), 0.05)
    K.point(name + 'Glow', (x, y, 7.5), 500, (0.15, 0.55, 1.0), r=1.0)


def window(r):
    x0, y0, x1, y1 = r
    alongx = (x1 - x0) > (y1 - y0)
    K.box2('armor', (x0, y0, 0), (x1, y1, 1.3))
    K.box2('walltop', (x0, y0, 1.3), (x1, y1, 1.4))
    if alongx:
        ym = (y0 + y1) / 2 + 0.6
        K.box2('glass', (x0, ym - 0.05, 1.4), (x1, ym + 0.05, H - 0.3))
        K.box2('armor', (x0, ym - 0.3, H - 0.4), (x1, ym + 0.3, H + 0.1))
        K.box('neon', ((x0 + x1) / 2, ym, H + 0.14), (x1 - x0, 0.14, 0.08))
        x = x0
        while x <= x1 + 0.01:
            K.box('armor', (x, ym, 3.5), (0.35, 0.5, 4.4))
            x += (x1 - x0) / max(1, round((x1 - x0) / 3.3))
        K.box('neon_dim', ((x0 + x1) / 2, y0 + 0.1, 1.44), (x1 - x0 - 0.5, 0.12, 0.06))
    else:
        xm = (x0 + x1) / 2 + 0.6
        K.box2('glass', (xm - 0.05, y0, 1.4), (xm + 0.05, y1, H - 0.3))
        K.box2('armor', (xm - 0.3, y0, H - 0.4), (xm + 0.3, y1, H + 0.1))
        K.box('neon', (xm, (y0 + y1) / 2, H + 0.14), (0.14, y1 - y0, 0.08))
        y = y0
        while y <= y1 + 0.01:
            K.box('armor', (xm, y, 3.5), (0.5, 0.35, 4.4))
            y += (y1 - y0) / max(1, round((y1 - y0) / 3.3))
        K.box('neon_dim', (x0 + 0.1, (y0 + y1) / 2, 1.44), (0.12, y1 - y0 - 0.5, 0.06))


def hull_outside():
    """Outer armour beyond the far and right walls, so the deck reads as cut out of a ship."""
    X1, Y1 = NX * C, NY * C
    K.prism('hull_big', [(Y1, H), (Y1 + 5, 3.0), (Y1 + 9, -6), (Y1 + 9, -30), (Y1, -30)], -10, X1 + 9, axis='x')
    K.prism('hull_big', [(X1, H), (X1 + 5, 3.0), (X1 + 9, -6), (X1 + 9, -30), (X1, -30)], -10, Y1, axis='z') if False else None
    K.loft('hull_big', [(X1, 0, H), (X1 + 5, 0, 3.0), (X1 + 9, 0, -6), (X1 + 9, 0, -30), (X1, 0, -30)],
           [(X1, Y1 + 9, H), (X1 + 5, Y1 + 9, 3.0), (X1 + 9, Y1 + 9, -6), (X1 + 9, Y1 + 9, -30), (X1, Y1 + 9, -30)])
    for x in range(-8, int(X1) + 8, 6):
        if 54 < x < 86:
            continue
        K.box('armor', (x, Y1 + 3.2, 4.0), (3.8, 4.8, 1.0), rot=(-31, 0, 0))
        K.box('orange' if x % 4 else 'cyan', (x, Y1 + 5.4, 2.9), (0.5, 0.3, 0.3))
    bar('neon', (-8, Y1 + 5.3, 3.0), (54, Y1 + 5.3, 3.0), 0.18)
    bar('neon', (86, Y1 + 5.3, 3.0), (X1 + 5.3, Y1 + 5.3, 3.0), 0.18)
    bar('neon', (X1 + 5.3, 0, 3.0), (X1 + 5.3, Y1 + 5.3, 3.0), 0.18)
    for y in range(3, int(Y1), 6):
        K.box('armor', (X1 + 3.2, y, 4.0), (4.8, 3.8, 1.0), rot=(0, 31, 0))
        K.box('orange', (X1 + 5.4, y + 3, 2.9), (0.3, 0.5, 0.3))
    # landing lip outside the bay door
    K.box2('armor', (54, Y1, -1.5), (86, Y1 + 16, 0))
    K.box2('floor_dk', (56, Y1, 0), (84, Y1 + 15, 0.05))
    for x in (56.4, 83.6):
        K.box2('neon', (x - 0.12, Y1, 0.05), (x + 0.12, Y1 + 15, 0.12))
        for k in range(6):
            K.box('orange', (x + (1.2 if x > 70 else -1.2), Y1 + 1.5 + k * 2.6, 0.12), (0.5, 0.5, 0.24))
    K.box2('hazard', (58, Y1 + 13, 0.05), (82, Y1 + 14.2, 0.08))
    # cut faces on the near and left sides (the ship carries on)
    K.box2('dark', (-0.3, 0, -1.5), (0, Y1, H - 0.9))
    K.box2('dark', (0, -0.3, -1.5), (X1, 0, H - 0.9))


# ------------------------------------------------------------------ floor graphics & room contents
def lane(p0, p1, w=0.3, dash=3.0, mat='paint_w'):
    p0, p1 = Vector((*p0, 0.02)), Vector((*p1, 0.02))
    d = p1 - p0
    n = int(d.length / (dash * 2))
    ang = math.degrees(math.atan2(d.y, d.x))
    for q in range(n):
        c = p0 + d * ((q + 0.5) / n)
        K.box(mat, c, (dash, w, 0.03), rot=ang)


def edge_line(r, inset=1.4, mat='paint_b', w=0.28, skip=()):
    x0, y0, x1, y1 = r
    x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    for (a, b, side) in [((x0, y0), (x1, y0), 's'), ((x0, y1), (x1, y1), 'n'), ((x0, y0), (x0, y1), 'w'),
                         ((x1, y0), (x1, y1), 'e')]:
        if side in skip:
            continue
        K.box2(mat, (min(a[0], b[0]) - w / 2, min(a[1], b[1]) - w / 2, 0.0),
               (max(a[0], b[0]) + w / 2, max(a[1], b[1]) + w / 2, 0.03))


def ring(c, r, mat='cyan', w=0.12, n=36, z=0.05, fill=0.65):
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + fill) / n
        bar(mat, (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0), z), (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1), z), w)


def console(c, rot=0, w=3.0, col='screen'):
    K.box('armor', (c[0], c[1], 0.6), (w, 1.3, 1.2), rot=rot)
    K.box('hull_lt', (c[0], c[1], 1.3), (w - 0.2, 1.1, 0.2), rot=rot)
    K.box(col, (c[0], c[1], 1.42), (w - 0.6, 0.6, 0.05), rot=rot)


def floors():
    # corridor: darker centre runway, dashed centre line, blue edge lines
    K.box2('deck_dk', (0, 31, 0), (136, 41, 0.02))
    lane((2, 36), (134, 36))
    for y in (30.2, 41.8):
        K.box2('paint_b', (0, y - 0.15, 0), (136, y + 0.15, 0.035))
    for x in range(8, 136, 16):
        for s in (-1, 1):
            K.box('paint_y', (x + 0.9 * 1, 36 + s * 2.0, 0.03), (0.4, 3.2, 0.02), rot=s * 40)
    for name in ('hangar', 'reactor', 'command'):
        r = DOORS[name]
        K.box2('deck_dk', (r[0] + 2, r[1], 0), (r[2] - 2, r[3], 0.02))
    for name in ('store', 'lift', 'workshop'):
        r = DOORS[name]
        K.box2('deck_dk', (r[0] + 2, r[1], 0), (r[2] - 2, r[3], 0.02))

    # hangar
    hx0, hy0, hx1, hy1 = ROOMS['hangar']
    K.box2('deck_dk', (62, hy0, 0), (78, 92, 0.02))
    lane((70, hy0 + 1), (70, 86))
    for x in (62.3, 77.7):
        K.box2('neon_dim', (x - 0.12, hy0, 0.02), (x + 0.12, 88, 0.06))
    ring((70, 78), 6.2)
    ring((70, 78), 5.0, 'paint_w', 0.09, 18, 0.03, 0.5)
    K.cyl('floor_dk', (70, 78, 0), (70, 78, 0.03), 6.0, 36, smooth=False)
    K.box2('hazard', (57, 85.6, 0.0), (83, 86.8, 0.04))
    for (xa, xb) in ((47.5, 60), (80, 92.5)):
        for k in range(3):
            yc = 58 + k * 10.0
            K.box2('deck_dk', (xa + 1, yc - 3.4, 0), (xb - 1, yc + 3.4, 0.025))
            K.box2('paint_w', (xa, yc - 4.2, 0), (xb, yc - 4.0, 0.03))
            K.box2('paint_w', (xa, yc + 4.0, 0), (xb, yc + 4.2, 0.03))
            for q in range(-2, 3):
                xe = xb - 0.4 if xa < 60 else xa + 0.4
                K.box('cyan' if (k + q) % 3 else 'orange', (xe, yc + q * 0.5, 0.05), (0.5, 0.2, 0.06))
    for (x, y) in [(48, 86), (92, 54), (48, 54)]:
        K.crate((x, y, 1.2), rot=rnd.uniform(-8, 8), kind=rnd.choice(['crate', 'crate_b', 'crate_o']))
        K.crate((x + (2.8 if x < 70 else -2.8), y, 1.2), kind=rnd.choice(['crate', 'crate_b']))
        K.barrel((x + (1.2 if x < 70 else -1.2), y + (-2.4 if y > 70 else 2.4), 0))

    # reactor room
    rx, ry = 22, 71
    K.cyl('floor_dk', (rx, ry, 0), (rx, ry, 0.03), 13.0, 48, smooth=False)
    ring((rx, ry), 13.0, 'paint_y', 0.14, 48, 0.05, 0.5)
    ring((rx, ry), 9.2, 'cyan', 0.14, 40, 0.06, 0.7)
    K.cyl('armor', (rx, ry, 0), (rx, ry, 1.0), 6.6, 12, smooth=False)
    K.cyl('hull_lt', (rx, ry, 1.0), (rx, ry, 1.5), 5.6, 12, smooth=False)
    K.cyl('steel', (rx, ry, 1.5), (rx, ry, 9.0), 3.0, 24)
    for z in (2.2, 3.6, 5.0, 6.4, 7.8):
        K.cyl('cyan', (rx, ry, z), (rx, ry, z + 0.5), 3.08, 24)
        K.cyl('armor', (rx, ry, z + 0.5), (rx, ry, z + 0.75), 3.3, 12, smooth=False)
    K.cyl('armor', (rx, ry, 9.0), (rx, ry, 9.8), 3.6, 12, smooth=False)
    K.cyl('cyan', (rx, ry, 9.8), (rx, ry, 9.9), 2.2, 24)
    K.point('ReactorGlow', (rx, ry, 11.5), 12000, (0.25, 0.8, 1.0), r=2.0)
    for k in range(6):
        a = math.radians(30 + 60 * k)
        ca, sa = math.cos(a), math.sin(a)
        K.cyl('armor', (rx + ca * 5.6, ry + sa * 5.6, 1.0), (rx + ca * 3.6, ry + sa * 3.6, 8.8), 0.7, 4, r1=0.45, smooth=False)
        bar('neon', (rx + ca * 5.0, ry + sa * 5.0, 1.8), (rx + ca * 3.2, ry + sa * 3.2, 8.4), 0.1)
        K.pipe('hull_lt', [(rx + ca * 6.0, ry + sa * 6.0, 0.5), (rx + ca * 11.5, ry + sa * 11.5, 0.5)], 0.35, 8)
        K.box('armor', (rx + ca * 12.0, ry + sa * 12.0, 1.1), (2.2, 2.2, 2.2), rot=math.degrees(a))
        K.box('cyan', (rx + ca * 12.0, ry + sa * 12.0, 2.25), (1.2, 1.2, 0.08), rot=math.degrees(a))
    for (x, y, rot) in [(8, 56, 0), (36, 56, 0), (7, 84, 0), (37, 84, 0)]:
        console((x, y), rot, 4.0, 'screen_c')
    edge_line(ROOMS['reactor'], 1.2)

    # command annex (windows on two sides): holo table, console rows
    cx, cy = 118, 70
    K.cyl('armor', (cx, cy, 0), (cx, cy, 0.9), 4.6, 8, smooth=False)
    K.cyl('screen_bg', (cx, cy, 0.9), (cx, cy, 1.0), 4.0, 8, smooth=False)
    ring((cx, cy), 3.4, 'cyan', 0.1, 24, 1.05)
    ring((cx, cy), 2.0, 'screen', 0.08, 12, 1.05)
    K.cyl('holo', (cx, cy, 1.1), (cx, cy, 4.2), 3.0, 8, r1=3.4, caps=False, smooth=False)
    K.box('holo_o', (cx + 0.6, cy - 0.3, 2.6), (1.6, 0.5, 0.3), rot=25)
    K.box('holo', (cx - 1.0, cy + 0.8, 2.9), (1.1, 0.4, 0.25), rot=-40)
    K.point('HoloGlow', (cx, cy, 3.5), 4000, (0.25, 0.8, 1.0), r=1.0)
    for x in range(104, 134, 5):
        console((x, 85.6), 0, 3.6, 'screen' if x % 2 else 'screen_c')
    for y in range(56, 86, 5):
        console((133.6, y), 90, 3.6, 'screen')
    for (x, y) in [(104, 58), (104, 64)]:
        console((x, y), 90, 4.0, 'screen_o')
    edge_line(ROOMS['command'], 1.2)
    ring((cx, cy), 8.0, 'paint_w', 0.1, 32, 0.03, 0.5)

    # store room: crate grid
    for i in range(4):
        for j in range(2):
            if (i, j) == (1, 1):
                continue
            x, y = 8 + i * 5.6, 8 + j * 5.5
            if 10 < x < 22 and y > 16:
                continue
            kind = rnd.choice(['crate', 'crate', 'crate_b', 'crate_o'])
            K.crate((x, y, 1.2), kind=kind, rot=rnd.uniform(-4, 4))
            if rnd.random() < 0.5:
                K.crate((x, y, 3.4), (2.2, 2.2, 2.0), kind=rnd.choice(['crate', 'crate_b']), rot=rnd.uniform(-10, 10))
    for k in range(5):
        K.barrel((26 + rnd.uniform(-1.5, 1.5), 7 + k * 1.4, 0))
    edge_line(ROOMS['store'], 1.0, 'paint_w', 0.2)

    # lift bay: big vehicle elevator
    lx0, ly0, lx1, ly1 = 60, 6, 84, 20
    K.box2('hazard', (lx0 - 1, ly0 - 1, 0), (lx1 + 1, ly1 + 1, 0.03))
    K.box2('floor_dk', (lx0, ly0, 0), (lx1, ly1, 0.06))
    K.box2('steel', (lx0 + 2, ly0 + 2, 0.06), (lx1 - 2, ly1 - 2, 0.08))
    K.box2('floor_dk', (lx0 + 2.3, ly0 + 2.3, 0.06), (lx1 - 2.3, ly1 - 2.3, 0.1))
    for (x, y) in [(lx0, ly0), (lx1, ly0), (lx0, ly1), (lx1, ly1)]:
        K.box('armor', (x, y, 1.0), (1.6, 1.6, 2.0))
        K.box('orange', (x, y, 2.08), (0.6, 0.6, 0.16))
    for s in (-1, 1):
        K.box('paint_y', (72 + s * 2.4, 13, 0.11), (0.6, 6.0, 0.02), rot=s * 35)
    for x in (56.5, 87.5):
        for k in range(3):
            console((x, 7 + k * 5), 90, 3.2, 'screen_o' if k == 1 else 'screen')

    # workshop: service gantry over a repair bay, benches, parts
    wx0, wy0, wx1, wy1 = ROOMS['workshop']
    for k, x in enumerate((102, 116, 129)):
        K.box2('floor_dk', (x - 4.4, 7, 0), (x + 4.4, 19, 0.03))
        K.box2('hazard', (x - 4.8, 6.4, 0), (x + 4.8, 7, 0.035))
        if abs(x - 114) < 9 and False:
            continue
    for x in (96.5, 122.5):
        for y in (7.2, 19):
            K.box('armor', (x, y, 3.6), (0.8, 0.8, 7.2))
        K.box('crate_o', (x, 13.1, 7.0), (0.9, 12.6, 0.9))
    K.box('crate_o', (109.5, 13.1, 7.6), (27, 1.4, 1.0))
    K.box('hazard', (109.5, 13.1, 8.14), (27, 1.5, 0.08))
    K.box('armor', (112, 13.1, 6.6), (2.6, 2.4, 1.2))
    K.box('white', (112, 13.1, 5.96), (1.4, 1.2, 0.06))
    for (x, y) in [(134, 8), (134, 12), (134, 16)]:
        console((x, y), 90, 3.0, 'screen_o')
    for k in range(4):
        K.barrel((95.2 + k * 1.2, 20.6, 0), mat_='crate_o')
    edge_line(ROOMS['workshop'], 1.0, 'paint_w', 0.2)

    # generator alcove
    gx0, gy0, gx1, gy1 = ROOMS['genroom']
    K.box2('floor_dk', (gx0, gy0, 0), (gx1, gy1, 0.02))
    K.box2('hazard', (gx0, gy1 - 0.6, 0.0), (gx1, gy1 + 0.6, 0.035))
    for y in (14, 18):
        console((37.4, y), 90, 3.0, 'screen_c')
        console((48.6, y), 90, 3.0, 'screen_c')


def floor_details():
    """Access hatches, grates and small marker lights so the open floor is not one flat tile field."""
    for i in range(NX):
        for j in range(NY):
            if grid[i][j] != FLOOR:
                continue
            x, y = i * C + 1, j * C + 1
            nearwall = [(a, b) for (a, b) in ((1, 0), (-1, 0), (0, 1), (0, -1)) if cell(i + a, j + b) == WALL]
            k = rnd.random()
            if nearwall and (i + j) % 2 == 0:
                a, b = nearwall[0]
                K.box('dark', (x + a * 0.25, y + b * 0.25, 0.02), (0.5, 0.5, 0.05))
                K.box('white' if (i + j) % 6 else 'orange', (x + a * 0.25, y + b * 0.25, 0.05), (0.26, 0.26, 0.04))
            elif not nearwall and k < 0.05:
                K.box('deck_dk', (x, y, 0.012), (1.7, 1.7, 0.03))
                for (a, b) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    K.box('steel', (x + a * 0.7, y + b * 0.7, 0.03), (0.12, 0.12, 0.03))
            elif not nearwall and k < 0.075:
                K.box('dark', (x, y, 0.012), (1.6, 1.0, 0.03))
                for q in range(5):
                    K.box('steel', (x, y - 0.4 + q * 0.2, 0.03), (1.5, 0.05, 0.03))
    # barricades: Terran defensive blocks in the corridor
    for (x, y, r) in [(34, 33, 90), (34, 39.5, 90), (56, 32.5, 75), (84, 39.5, 105), (58.5, 47.5, 0), (81.5, 47.5, 0)]:
        K.box('armor', (x, y, 0.9), (4.4, 1.1, 1.8), rot=r, taper=(1, 0.5))
        K.box('hazard', (x, y, 0.3), (4.5, 1.2, 0.5), rot=r)
        K.box('orange', (x, y, 1.84), (0.5, 0.3, 0.1), rot=r)


def lighting(sc):
    def sun(name, rot, energy, col, angle=6.0):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.color = col
        ld.angle = math.radians(angle)
        o = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(o)
        o.rotation_euler = [math.radians(a) for a in rot]
    sun('Key', (38, 0, -32), 5.0, (0.86, 0.92, 1.0), 8)       # from the near-left, shadows fall up-right
    sun('Top', (0, 0, 0), 2.6, (0.6, 0.75, 1.0), 40)
    sun('Rim', (-50, 0, 150), 0.6, (0.4, 0.6, 1.0), 20)
    # practical pools of light at doors and rooms
    for name, r in DOORS.items():
        K.point('D_' + name, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 5.0), 5000, (0.75, 0.88, 1.0), r=1.0)


def units():
    T = lambda k, x, y, rz: K.tank(k, (x, y, 0), rz)
    Al = lambda k, x, y, rz: K.tank(k, (x, y, 0), rz, faction='alien')
    T('bulwark', 53.5, 58, 0)
    T('outrider', 53, 78, 0)
    T('lancer', 86.5, 68, 180)
    T('lancer', 53.5, 68, 0)
    T('javelin', 86.5, 58, 180)
    T('longbow', 86.5, 78, 180)
    T('bulwark', 70, 60, 92)       # defenders facing the bay door
    T('lancer', 63.5, 64, 80)
    T('lancer', 77, 63, 103)
    Al('carapace', 70, 81, -90)    # boarders, just through the field
    Al('darter', 64.5, 85, -80)
    Al('stinger', 75.5, 96, -95)   # next one arriving on the lip
    T('bulwark', 22, 38, 85)       # holding the reactor door
    T('javelin', 12, 35, 60)
    T('outrider', 100, 34.5, 180)
    T('lancer', 92, 38.5, 180)
    T('hauler', 72, 13, 90)
    T('mender', 102, 12.5, 90)
    T('lancer', 116, 13, 90)
    T('skimmer', 118, 57, 200)


def main():
    K.E.update(neon=2.6, cyan=1.3, orange=4.0, white=1.2)
    K.MATDEF['glass'] = lambda n: K._holo(n, (0.1, 0.4, 1.0), 0.5, 0.22)
    K.MATDEF['neon'] = lambda n: K._emit(n, (0.008, 0.16, 1.0), 7.0)
    K.MATDEF['crystal'] = lambda n: K._emit(n, (0.015, 0.24, 1.0), 4.5)
    K.MATDEF['deck'] = lambda n: K._panel(n, (0.13, 0.145, 0.17), rough=0.45, S=4.0, w=0.05, var=0.35, metal=0.2,
                                          fine=0.5, line=0.8)
    K.MATDEF['deck_dk'] = lambda n: K._panel(n, (0.09, 0.1, 0.12), rough=0.42, S=2.0, w=0.04, var=0.3, metal=0.2,
                                             fine=0.5, line=0.8)
    sc, cam = K.reset(samples=int(A.get('samples', 20)), exposure=float(A.get('exposure', 0.7)))
    K.space_world(sc, nebula=0.1, density=0.55, scale=170.0, size=0.07)
    structure()
    wall_faces()
    hull_outside()
    for r in WINDOWS:
        window(r)
    for name, r in DOORS.items():
        if name == 'bay':
            continue
        doorway(name, r, field=(name == 'reactor'))
    # the port: force field in the outer hull
    doorway('bay', (56, 88, 84, 92), field=True)
    floors()
    floor_details()
    generator((43, 19), name='GenA')        # powers the reactor-room field door
    conduit([(43, 24), (43, 36), (22, 36), (22, 46.5)])
    generator((88.5, 83), r=3.4, name='GenB')   # powers the bay field
    conduit([(88.5, 87.2), (84.5, 87.2)], w=0.4)
    K.flush()
    lighting(sc)
    units()
    pitch = math.radians(float(A.get('pitch', 52)))
    if VIEW == 'wide':
        tgt, D = Vector((70, 44, 0)), float(A.get('dist', 108))
    elif VIEW == 'close':
        tgt, D = Vector((66, 70, 0)), float(A.get('dist', 62))
    else:
        tgt, D = Vector((32, 34, 0)), float(A.get('dist', 58))
    loc = tgt + Vector((0, -math.cos(pitch) * D, math.sin(pitch) * D))
    K.look(cam, loc, tgt, lens=22.7)       # 48 deg vertical FOV, as the game camera
    raw = os.path.join(OUT, '_raw', NAME + '.png')
    K.render(sc, raw, RES)
    K.post(raw, A.get('final', os.path.join(OUT, NAME + '.jpg')), bloom=0.8, thresh=0.7, vignette=0.15)


main()
