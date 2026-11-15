"""Arcadian capital ship: launch deck (concept stills).

    /home/user/artenv/venv/bin/python arcadian_deck.py --view=game|eye --out=FILE.jpg
        [--res=960x540] [--samples=24] [--dist=158 --tx=18 --ty=-1]   (game camera)

One deck plan, two ways of looking at it:
    game   the RTS camera: high and angled, roof removed, walls cut flat at 6 m (walls = blocked ground)
    eye    cinematic, standing in the launch hall looking out through the force aperture to space

Plan (metres, +X = toward the launch maw, +Y = north):
    launch hall   ellipse at (44, 0), 66 x 46, with a 26 m throat east to the hull edge
    spine         15 m corridor west from the hall to the rotunda; force-field door at x = -6,
                  its generator in a niche north of the door
    rotunda       r = 18 at (-42, 0) with a hovering core in the middle (blocked)
    north arc     curved corridor from the rotunda to an overlook chamber open to space
    pod bay       south chamber with a launch well in the floor (open to space, thin field ring)

Style rules applied (David / coordinator review): tick-mark instrument rings ONLY on force apertures;
everything else uses flowing engraved inlays and broad flat crescent blades; cool silver-bronze
metal, dark recesses, yellow-gold light.
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arcadian_kit as K  # noqa: E402
from arcadian_kit import F, A  # noqa: E402

ARGS = K.args()
VIEW = ARGS.get('view', 'game')
RES = tuple(int(v) for v in ARGS.get('res', '960x540').split('x'))
OUT = ARGS.get('out', f'/home/user/work/arcadian-interiors/deck_{VIEW}.jpg')
GAME = VIEW == 'game'
H = 6.0 if GAME else 7.5              # wall height (game view: the cut plane)
rnd = random.Random(7)

# ------------------------------------------------------------------ plan
HULL_C, HULL_RX, HULL_RY = (-10.0, 0.0), 100.0, 52.0
HULL = K.ellipse(HULL_C, HULL_RX, HULL_RY, n=220)
HALL_C, HALL_RX, HALL_RY = (44.0, 0.0), 33.0, 23.0
THROAT = 13.0                                         # half width of the throat
AP_X = 85.0
ROT_C, ROT_R = (-42.0, 0.0), 18.0
DOOR_X = -6.0
GEN_C = (-6.0, 16.5)
OVER_C = (24.0, 41.0)
POD_C = (8.0, -34.0)
WELL_C, WELL_R = (15.0, -35.0), 5.5
ARC_C, ARC_R = (-8.0, -4.0), 44.0

ROOMS = [
    K.ellipse(HALL_C, HALL_RX, HALL_RY, n=180),
    K.capsule((66, 0), (125, 0), 2 * THROAT),         # throat, runs out through the hull edge
    K.capsule((20, 0), (-30, 0), 15),                 # spine
    K.ellipse(ROT_C, ROT_R, ROT_R, n=120),
    K.capsule((-55, 0), (-160, 0), 15),               # spine carries on west, deeper into the ship
    K.ellipse(GEN_C, 7.0, 7.0, n=48),                 # generator niche
    K.capsule((-6, 6), (-6, 12), 8, n=8),
    K.band(ARC_C, ARC_R, 60, 152, 12, n=48),          # north arc corridor
    K.ellipse(OVER_C, 15, 12.5, n=72),                # overlook, breaks the hull edge
    K.capsule((-35, -12), (-12, -32), 12),            # south branch
    K.superellipse(POD_C, 21, 11, p=3.2, n=120),      # pod bay
]
ISLAND = K.ellipse(ROT_C, 4.6, 4.6, n=48)             # rotunda centre is blocked by the core


def walkable(p):
    return any(K.inside(p, r) for r in ROOMS) and not K.inside(p, ISLAND)


def hall_half(x):
    """Half width of the launch hall + throat at station x."""
    w = 0.0
    u = (x - HALL_C[0]) / HALL_RX
    if abs(u) < 1:
        w = HALL_RY * math.sqrt(1 - u * u)
    if x > 66:
        w = max(w, THROAT)
    if x < 20:
        w = max(w, 7.5)
    return w


# ------------------------------------------------------------------ build
def build_deck():
    K.slab(HULL, [K.ellipse(WELL_C, WELL_R, WELL_R, n=64)], -3.0, 0.0, 'floor')
    loops = K.deck_walls(HULL, ROOMS, H)
    for loop in loops:
        p0, n0 = loop[len(loop) // 2]
        if walkable(p0 + n0 * 1.5):
            dress_wall(loop)
        else:
            sl = K.smooth_loop(loop, 1.5)
            K.strip(K.offset(sl, 0.0, H), 0.9, 0.4, 'pale')
            K.strip(K.offset(sl, 0.0, H + 0.24), 0.12, 0.1, 'line')
    build_hull_skirt()
    # the rotunda core stands on a low blocked plinth
    F.lathe([(4.6, 0.0), (4.5, 0.9), (3.9, 1.3), (0.01, 1.3)], 64, 'bronze', center=(ROT_C[0], ROT_C[1], 0), caps=False)
    K.ring_flat((ROT_C[0], ROT_C[1], 1.0), 4.6, 0.1, 0.1, 'line', n=64)
    K.ring_flat((ROT_C[0], ROT_C[1], 0.1), 4.9, 0.4, 0.16, 'silver', n=64)
    return loops


def build_hull_skirt():
    """Exterior hull plating falling away outside the deck edge, so the deck reads as one level cut
    out of a much larger ship (not a tray floating in space)."""
    cx, cy = HULL_C
    n = 220
    levels = [(1.0, 0.0), (1.012, -1.5), (1.09, -9.0), (1.24, -30.0), (1.45, -70.0), (1.7, -130.0)]
    rings = [[(cx + HULL_RX * k * math.cos(2 * math.pi * i / n), cy + HULL_RY * k * math.sin(2 * math.pi * i / n), z) for i in range(n)]
             for k, z in levels]
    F.loft(rings, 'bronze', caps=False)
    for li, (zone, w) in ((1, ('line', 0.12)), (2, ('silver', 0.7)), (3, ('silver', 1.0)), (4, ('silver', 1.2))):
        K.strip([Vector(p) + Vector((0, 0, 0.15)) for p in rings[li]], w, 0.3, zone)
    K.strip([Vector(p) + Vector((0, 0, 0.5)) for p in rings[3]], 0.14, 0.14, 'line')
    for i in range(0, n, 5):                               # plate seams running down the hull
        pts = [Vector(rings[l][i]) + Vector((0, 0, 0.12)) for l in (1, 2, 3, 4, 5)]
        K.strip(A.smooth_pts(pts, 5), 0.3, 0.2, 'under', closed=False)
    for i in range(2, n, 10):                              # broad crescent fins lying back along the plating
        a = 2 * math.pi * i / n
        d = Vector((math.cos(a), math.sin(a), 0))
        K.fin(Vector(rings[2][i]), d * 0.8 + Vector((0, 0, 0.5)), Vector((0, 0, -1)), 9.0, 5.0, 'silver', lean=0.7)


def dress_wall(loop):
    """Trim one wall loop: dark skirting with a glow line, silver cap with one consistent glowing
    gold line along the top, and flowing inlay lines on the floor that follow the wall."""
    sl = K.smooth_loop(loop)
    K.strip(K.offset(sl, 0.2, 0.4), 0.4, 0.8, 'bronze')
    K.strip(K.offset(sl, 0.43, 0.62), 0.06, 0.08, 'line')
    K.strip(K.offset(sl, -0.8, H + 0.02), 1.5, 0.12, 'silver')               # wall cap band
    K.strip(K.offset(sl, 0.02, H + 0.1), 0.22, 0.16, 'line')                  # glowing top line
    K.strip(K.offset(sl, -1.85, H + 0.04), 0.6, 0.14, 'pale')
    K.strip(K.offset(sl, 1.3, 0.02), 0.3, 0.06, 'inlay')                      # floor inlays
    K.strip(K.offset(sl, 1.85, 0.02), 0.06, 0.05, 'line')


def build_floor_marks():
    hx, hy = HALL_C
    # launch lane down the hall + throat: paler floor band, twin glowing rails, chevrons
    lane = [(x, y) for x, y in K.capsule((20, 0), (AP_X + 1.5, 0), 8.4, n=10) if x < AP_X + 1.6]
    K.slab(lane, [], 0.0, 0.05, 'floor2')
    for s in (-1, 1):
        K.strip([(18, s * 4.3, 0.06), (AP_X + 1.5, s * 4.3, 0.06)], 0.12, 0.06, 'line', closed=False)
        K.strip([(22, s * 4.8, 0.05), (AP_X + 1.5, s * 4.8, 0.05)], 0.3, 0.06, 'inlay', closed=False)
    for x in range(28, int(AP_X), 8):                 # chevrons pointing out
        for s in (-1, 1):
            K.strip([(x, s * 0.25, 0.07), (x - 1.8, s * 2.5, 0.07)], 0.22, 0.05, 'inlay', closed=False)
    for r, z in ((0.9, 'inlay'), (0.925, 'line')):
        o = K.ring_flat((0, 0, 0.04), 1.0, 0.012 if z == 'inlay' else 0.003, 0.05, z, n=160)
        F.xf(o, Matrix.Translation((hx, hy, 0)) @ Matrix.Diagonal((HALL_RX * r, HALL_RY * r, 1, 1)))
    # parking pads along the hall sides: each one drawn differently
    pads = []
    k = 0
    for x in (28.0, 42.5, 57.0):
        for s in (-1, 1):
            y = s * (hall_half(x) - 8.6)
            K.flow_pad((x, y), 4.7, style=k)
            # one broad crescent hovering behind the pad (touches nothing)
            o = F.crescent((0, 0, 0), 6.6, 90 - 38, 90 + 38, 1.5, 0.16, 'silver', n=20, tip=0.1)
            F.xf(o, Matrix.Translation((x, y, 2.6 + 0.3 * (k % 3))) @ Matrix.Rotation(math.radians(0 if s > 0 else 180), 4, 'Z'))
            o = F.crescent((0, 0, 0), 6.6, 90 - 32, 90 + 32, 0.1, 0.06, 'line', n=20, tip=0.4)
            F.xf(o, Matrix.Translation((x, y, 2.72 + 0.3 * (k % 3))) @ Matrix.Rotation(math.radians(0 if s > 0 else 180), 4, 'Z'))
            pads.append((x, y, -s * 90))
            k += 1
    # rotunda: rings and a great pinwheel of engraved strokes
    cx, cy = ROT_C
    for r, z, w in ((7.6, 'inlay', 0.3), (8.1, 'line', 0.06), (14.2, 'inlay', 0.3), (14.7, 'line', 0.06)):
        K.ring_flat((cx, cy, 0.04), r, w, 0.06, z, n=120)
    for j in range(6):
        K.swoosh((cx, cy), 8.6, 13.6, j * 60, j * 60 + 100, 0.55, 'inlay', 0.05)
        K.swoosh((cx, cy), 8.9, 13.3, j * 60 + 12, j * 60 + 92, 0.07, 'line', 0.06)
    # corridors: twin guide lines
    for (a, b) in (((-23, 0), (10, 0)), ((-61, 0), (-120, 0))):
        for s in (-1, 1):
            K.strip([(a[0], s * 0.9, 0.05), (b[0], s * 0.9, 0.05)], 0.08, 0.05, 'line', closed=False)
            K.strip([(a[0], s * 1.5, 0.04), (b[0], s * 1.5, 0.04)], 0.22, 0.05, 'inlay', closed=False)
    pts = [(ARC_C[0] + ARC_R * math.cos(math.radians(a)), ARC_C[1] + ARC_R * math.sin(math.radians(a)), 0.05) for a in range(64, 150, 2)]
    K.strip(pts, 0.1, 0.05, 'line', closed=False)
    K.strip([(-33, -14, 0.05), (-13, -31, 0.05)], 0.1, 0.05, 'line', closed=False)
    K.flow_pad(OVER_C, 6.0, style=2)
    # pod bay: the launch well is a force aperture, so it alone gets an exact ring with tick marks
    K.ring_flat((WELL_C[0], WELL_C[1], 0.1), WELL_R + 0.25, 0.4, 0.25, 'silver', n=96)
    K.ring_flat((WELL_C[0], WELL_C[1], 0.3), WELL_R - 0.05, 0.07, 0.07, 'white', n=96)
    K.ring_flat((WELL_C[0], WELL_C[1], 0.05), WELL_R + 1.4, 0.05, 0.05, 'line', n=96)
    K.ticks((WELL_C[0], WELL_C[1], 0.06), WELL_R + 1.45, WELL_R + 1.75, 120, 0.04, 0.04, 'line', every=10, long=0.4)
    K.raw_mesh('wellfield', [(WELL_C[0] + WELL_R * math.cos(2 * math.pi * k / 64), WELL_C[1] + WELL_R * math.sin(2 * math.pi * k / 64), 0.02)
                             for k in range(64)], [list(range(64))], K.door_mat('wellfilm', strength=0.25, clear=0.8))
    K.flow_pad((POD_C[0] - 11, POD_C[1] + 1), 3.6, style=3)
    return pads


def build_door():
    """Force-field door across the spine at DOOR_X with its generator in the north niche. The energy
    sheet is bowed in plan so it shows its face to a camera looking from any side, including from
    straight above; a bright threshold bar follows it and a lit conduit runs to the generator."""
    x = DOOR_X
    w = 7.5
    hh = H * 0.95
    sag = 3.4

    def px(y):
        return x + sag * (1 - (y / (w - 0.6)) ** 2)

    for s in (-1, 1):                                   # pylons: one broad flat fin each side
        K.fin((x - 0.4, s * (w - 0.25), 0.0), (0, 0, 1), (0.25, -s, 0), hh * 1.15, 3.0, 'silver', lean=0.22, curve=2.2)
        F.cyl((x, s * (w - 0.75), 0.2), (x, s * (w - 0.75), hh), 0.09, 6, 'white')
        K.orb((x, s * (w - 0.75), hh + 0.5), 0.5, light=0.6)
    n = 28
    ys = [-(w - 0.6) + 2 * (w - 0.6) * k / n for k in range(n + 1)]
    top = [(px(y), y, hh) for y in ys]
    verts = [(px(y), y, 0.05) for y in ys] + top
    faces = [[k, k + 1, n + 2 + k, n + 1 + k] for k in range(n)]
    K.raw_mesh('doorfilm', verts, faces, K.door_mat('doorfilm', strength=2.4 if GAME else 1.1, clear=0.3 if GAME else 0.55))
    K.strip(top, 0.1, 0.1, 'white', closed=False)
    K.strip([(px(y), y, 0.1) for y in ys], 0.5, 0.1, 'white', closed=False)          # threshold bar
    K.strip([(px(y) - 0.9, y, 0.05) for y in ys], 0.08, 0.05, 'line', closed=False)
    K.strip([(px(y) + 0.9, y, 0.05) for y in ys], 0.08, 0.05, 'line', closed=False)
    # generator: clean hovering core over a low bowl, three floating arcs, lit conduit to the door
    gx, gy = GEN_C
    c = K.core((gx, gy, 3.8), 1.6, rings=2, light=1.2)
    F.lathe([(3.2, 0.0), (3.1, 0.4), (2.2, 0.7), (1.2, 0.45), (0.01, 0.45)], 48, 'bronze', center=(gx, gy, 0), caps=False)
    K.ring_flat((gx, gy, 0.42), 3.2, 0.08, 0.08, 'line', n=64)
    for k in range(3):
        K.ring_flat((gx, gy, 1.6), 4.3, 0.7, 0.14, 'silver', n=16, a0=k * 120 + 100, a1=k * 120 + 190)
        K.ring_flat((gx, gy, 1.72), 4.3, 0.06, 0.05, 'line', n=16, a0=k * 120 + 104, a1=k * 120 + 186)
    cond = A.smooth_pts([(gx, gy - 3.3, 0.06), (gx, 8.6, 0.06), (x + 0.3, w - 0.2, 0.06)], 8)
    K.strip(cond, 0.34, 0.07, 'white', closed=False)
    K.strip(cond, 1.0, 0.04, 'inlay', closed=False)
    A.bolt(c + Vector((0, -1.7, 0.2)), (x, w - 0.75, hh + 0.5), rnd, width=0.12, jag=0.2, depth=5, branches=2, zone='thin')
    return c


def build_islands():
    """Machinery set into the solid mass between the halls (game view): dark, low-contrast domes,
    sunk rings and long engraved conduit strokes - rich close up, quiet from a distance."""
    spots = ((-62, -27, 4.0), (-65, 27, 4.0), (44, -35, 4.2), (52, 34, 4.0), (-24, 22.5, 3.2), (74, -23, 2.8), (-28, -30, 3.4),
             (20, 22, 2.6), (-8, -19, 2.6))
    for k, (x, y, r) in enumerate(spots):
        z = H
        F.lathe([(r, 0.0), (r * 0.95, 0.35), (r * 0.62, 0.55), (r * 0.5, 0.3), (r * 0.3, 0.6), (0.01, 0.75)], 40, 'under', center=(x, y, z), caps=False)
        K.ring_flat((x, y, z + 0.08), r * 1.3, 0.22, 0.1, 'bronze', n=48)
        K.ring_flat((x, y, z + 0.36), r * 0.56, 0.05, 0.05, 'soft', n=40)
        for j in range(3):
            K.swoosh((x, y), r * 1.5, r * 2.6, j * 120 + 40 * k, j * 120 + 40 * k + 120, 0.3, 'bronze', z + 0.05)
    for (c, r0, r1, a0, a1) in (((-10, 0), 62, 70, 200, 262), ((-10, 0), 60, 66, 100, 150), ((30, 0), 36, 40, 285, 340),
                                ((30, 0), 37, 41, 20, 70), ((-42, 0), 26, 31, 95, 150), ((-42, 0), 27, 33, 215, 265)):
        K.swoosh(c, r0, r1, a0, a1, 0.5, 'bronze', H + 0.05, n=40)
        K.swoosh(c, r0 + 1.2, r1 + 1.2, a0 + 3, a1 - 3, 0.07, 'soft', H + 0.07, n=40)


def build_rotunda_core():
    cx, cy = ROT_C
    c = K.core((cx, cy, 6.4), 2.7, rings=3, light=1.3)
    for k in range(4):                                     # broad arcs floating round the core
        K.ring_flat((cx, cy, 3.0 + 0.5 * (k % 2)), 6.3, 1.1, 0.16, 'silver', n=18, a0=k * 90 + 12, a1=k * 90 + 74)
        K.ring_flat((cx, cy, 3.12 + 0.5 * (k % 2)), 6.3, 0.07, 0.06, 'line', n=18, a0=k * 90 + 16, a1=k * 90 + 70)
    for k in range(2):
        a = math.radians(50 + 180 * k)
        A.bolt(c + Vector((math.cos(a) * 2.8, math.sin(a) * 2.8, 0.3)), (cx + math.cos(a + 0.5) * 6.3, cy + math.sin(a + 0.5) * 6.3, 3.3),
               rnd, width=0.12, jag=0.22, depth=5, branches=2, zone='thin')
    return c


def build_launch():
    """Aperture at the hull edge, two thin guide hoops over the lane, arcs at the energy points."""
    ap_c = Vector((AP_X, 0.0, 9.6 if not GAME else 7.6))
    r = 12.0
    K.aperture(ap_c, (1, 0, 0), r, sq=(1.0, 0.74 if not GAME else 0.6), rings=3, seed=4, bolts=6)
    hh = 20.0 if not GAME else 10.0
    for s in (-1, 1):
        # carrier: broad flat crescents either side of the aperture; they stop short of it
        K.fin((ap_c.x - 0.6, s * 12.9, 0.0), (0, 0, 1), (0, -s, 0), hh, 5.0, 'pale', lean=0.46, curve=2.0, rib=None)
        K.fin((ap_c.x - 3.4, s * 12.95, 0.0), (0, 0, 1), (0, -s, 0), hh * 0.62, 3.6, 'silver', lean=0.36, curve=2.0)
        K.orb((ap_c.x - 1.2, s * 10.9, 1.5), 0.9, light=1.0)
        K.ring_flat((ap_c.x - 1.2, s * 10.9, 1.5), 1.5, 0.12, 0.08, 'silver', n=32)
        A.bolt((ap_c.x - 1.2, s * 10.9, 2.4), (ap_c.x, s * 10.2, ap_c.z + (4.6 if not GAME else 1.5)), rnd, width=0.15, jag=0.16, depth=6,
               branches=2, zone='thin')
    hoops = []
    for k, x in enumerate((58.0, 71.0)):
        rr = (9.5 - 1.5 * k) if not GAME else (6.2 - 0.5 * k)
        c = Vector((x, 0, 9.0 if not GAME else 5.8))
        m = K.frame(c, (1, 0, 0))
        mk = F.mark()
        for j in range(3):
            K.ring_flat((0, 0, 0), rr, 0.22, 0.1, 'pale', n=30, a0=j * 120 + 50, a1=j * 120 + 150)
        K.ring_flat((0, 0, 0), rr - 0.4, 0.05, 0.05, 'line', n=120)
        for o in F.since(mk):
            F.xf(o, m)
        hoops.append((c, rr))
    (c0, r0), (c1, r1) = hoops
    for a in (40, 140) if not GAME else (40, 140, 220, 320):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        A.bolt(c0 + Vector((0, ca * r0, sa * r0)), c1 + Vector((0, ca * r1, sa * r1)), rnd, width=0.12, jag=0.07, depth=5, branches=1, zone='thin')
    return ap_c


def arch(x, t, h):
    """Point on the roof arch at station x: t in -1..1 from the south wall top over the apex."""
    w = hall_half(x) + 0.6
    a = math.pi / 2 * t
    return Vector((x, w * math.copysign(abs(math.sin(a)) ** 0.8, t), H + (h - H) * math.cos(a) ** 0.9))


def roof_h(x):
    u = (x - 11.0) / (AP_X + 3 - 11.0)
    return 15.0 + 14.0 * math.sin(math.pi * min(1.0, max(0.0, u)) ** 0.8) ** 0.7 + (7.0 if x > 70 else 7.0 * max(0.0, (x - 55) / 15.0))


def build_roof():
    """Vault over the hall for the eye-level view: a dark engraved shell, and a few broad silver arcs
    floating under it. The arcs touch neither the walls nor each other; each sweeps forward toward
    the aperture as it rises, and the two sides are staggered."""
    xs = [6 + 1.5 * k for k in range(56)]
    rings = [[tuple(arch(x, -1 + 2 * k / 40, roof_h(x) + 1.2)) for k in range(41)] for x in xs]
    F.loft(rings, 'vault', caps=False, closed=False)
    tips = []
    for s, stations in ((-1, (17.0, 34.0, 51.0, 66.0)), (1, (25.0, 42.0, 58.0, 72.0))):
        for i, x0 in enumerate(stations):
            n = 22
            pts = []
            for k in range(n + 1):
                u = k / n
                x = x0 + 9.0 * u ** 1.6
                pts.append(arch(x, s * (0.9 - 0.62 * u), roof_h(x) - 1.6 - 0.8 * math.sin(math.pi * u)))
            K.arc_band(pts, 2.2 - 0.25 * i, 0.22, 'pale' if i % 2 else 'silver', (1, 0, 0))
            tips.append(pts[-1])
            K.orb(tuple(pts[-1] + Vector((1.4, -s * 1.2, 0.5))), 0.5, light=0.8)
    for k in range(4):                                    # spine: a few orbs hovering in single rings
        x = 22 + 14.0 * k
        h = roof_h(x)
        K.orb((x, 0, h - 1.2), 0.75, light=1.6)
        K.ring_flat((x, 0, h - 1.2), 1.9, 0.3, 0.06, 'silver', n=48)
        K.ring_flat((x, 0, h - 1.14), 1.9, 0.04, 0.04, 'line', n=48)
    for k, j in enumerate((1, 2, 5, 6)):
        x = 22 + 14.0 * (k % 4)
        A.bolt(tips[j] + Vector((1.4, 0, 0.5)), (x, 0, roof_h(x) - 1.2), rnd, width=0.2, jag=0.18, depth=6, branches=3, zone='thin')
    for t in (-0.46, 0.46):                               # two glowing threads the length of the vault
        pts = [tuple(arch(x, t, roof_h(x) + 0.95)) for x in xs]
        F.sweep(pts, [(0.07, 0.07)] * len(pts), 'line', sides=4)
        pts = [tuple(arch(x, t * 1.02, roof_h(x) + 0.85)) for x in xs]
        F.sweep(pts, [(0.4, 0.14)] * len(pts), 'bronze', sides=4)
    # the throat end wall round the aperture: a dark collar so the opening reads against it
    cz = 9.6
    n = 72
    ring_o = [(AP_X + 1.2, 13.4 * math.cos(2 * math.pi * k / n), cz + 13.4 * 0.78 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    ring_b = [(AP_X + 1.2, 30 * math.cos(2 * math.pi * k / n), cz + 34 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    F.loft([ring_o, ring_b], 'vault', caps=False)


def space_ships():
    """Distant Arcadian ships and beam streaks beyond the aperture (built last: the fleet builders
    reset the forge material cache)."""
    K.finish()
    with A.gold_palette():
        for (loc, yaw, sc, pitch) in (((330, 60, -20), 200, 5.0, 8), ((520, -130, 60), 160, 5.0, -5)):
            ship, _ = A.arcadian_corvette()
            ship.location = loc
            ship.rotation_euler = (0, math.radians(pitch), math.radians(yaw))
            ship.scale = (sc,) * 3
        ship, _ = A.crescent_mothership_v2()
        ship.location = (1500, 260, 150)
        ship.rotation_euler = (math.radians(20), math.radians(-10), math.radians(215))
        ship.scale = (9,) * 3
    K._custom_mats()
    em = bpy.data.materials.new('beam')
    em.use_nodes = True
    b = em.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0, 0, 0, 1)
    b.inputs['Emission Color'].default_value = (1.0, 0.7, 0.22, 1)
    b.inputs['Emission Strength'].default_value = 40.0
    em2 = em.copy()
    em2.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.25, 0.7, 1.0, 1)
    for (p0, p1, wdt, mt) in (((1400, 230, 140), (700, -700, -150), 2.2, em), ((1450, 300, 160), (2500, 900, -500), 2.0, em),
                              ((900, -420, 260), (2400, 380, 420), 1.6, em2), ((700, 600, -260), (2300, -200, 30), 1.4, em2),
                              ((330, 60, -20), (1200, -520, -330), 0.6, em)):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        me = bpy.data.meshes.new('beam')
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=wdt, radius2=wdt * 0.5, depth=d.length)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new('beam', me)
        bpy.context.scene.collection.objects.link(o)
        o.location = (p0 + p1) / 2
        o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        o.data.materials.append(mt)
        o.visible_shadow = False


def main():
    K.init(samples=int(ARGS.get('samples', 24)), res=RES, env=float(ARGS.get('env', 0.75 if GAME else 0.2)), wall_h=H,
           warm=(0.95, 0.95, 1.0) if GAME else (0.72, 0.8, 0.95), floor_mode='light' if GAME else 'dark', stars=1.5, core_gain=3.5 if GAME else 6.0)
    build_deck()
    pads = build_floor_marks()
    gen = build_door()
    rot = build_rotunda_core()
    ap = build_launch()
    if GAME:
        build_islands()
    else:
        with K.layer('roof'):
            build_roof()
    K.finish()
    # vehicles
    names = ['stinger', 'carapace', 'glider', 'spitter', 'darter', 'mortar_beast']
    for k, (x, y, yaw) in enumerate(pads):
        if k == 3 or (not GAME and k < 2):
            continue                                     # one pad empty (and the two nearest the eye camera)
        K.unit(names[k % len(names)], (x, y, 0.75), yaw=yaw + (8 if k % 2 else -6))
    if GAME:
        K.unit('glider', (66, 0, 4.6), yaw=0, pitch=-3)  # lifting off down the lane
        K.unit('stinger', (-17, 3.3, 0.9), yaw=4)
        K.unit('darter', (5, -3.2, 0.9), yaw=-3)
        K.unit('carapace', (-42, -11.5, 0.9), yaw=35)
        K.unit('seer', (-52, 9, 0.9), yaw=-40)
        K.unit('ferrier', (-3, -35, 0.9), yaw=15)
        K.unit('disc', (WELL_C[0], WELL_C[1], 3.0), yaw=0)
        K.unit('weaver', (22, 39, 0.9), yaw=70)
        K.unit('gorger', (-2, 39.5, 0.9), yaw=200)
    else:
        K.unit('glider', (47, 0.5, 6.0), yaw=2, pitch=-4, roll=5)    # mid-launch, floating down the lane
        K.unit('halo', (104, -3, 10), yaw=5, roll=12)
        K.point((47, 0.5, 4.2), 1500, col=(1.0, 0.8, 0.45), r=1.0)
        r2 = random.Random(3)
        for dy in (-1.6, 1.8):                                         # lightning lift under it
            A.bolt((47.5, 0.5 + dy, 5.3), (47.5 + r2.uniform(-1.5, 1.5), 0.5 + dy * 2.2, 0.1), r2, width=0.045, jag=0.2, depth=5, branches=2, zone='thin')
        K.finish()
        space_ships()

    # ---------------------------------------------------------------- light + camera
    if GAME:
        K.light_orbs(0.3)
        K.sun((20, 0, 200), 2.3, col=(1.0, 0.96, 0.9), angle=8)
        K.sun((55, 0, 20), 0.8, col=(0.75, 0.84, 1.0), angle=20)
        K.point((AP_X, 0, 6), 4000, col=(1.0, 0.82, 0.5), r=1.0)
        K.point((DOOR_X + 2, 0, 3), 2500, col=(1.0, 0.8, 0.45), r=1.0)
        tgt = Vector((float(ARGS.get('tx', 11)), float(ARGS.get('ty', -1.0)), 0))
        el = math.radians(float(ARGS.get('el', 56)))
        dist = float(ARGS.get('dist', 158))
        K.camera(tgt + Vector((0, -math.cos(el) * dist, math.sin(el) * dist)), tgt, lens=float(ARGS.get('lens', 40)))
    else:
        K.ghost('roof')
        K.light_orbs(0.7)
        K.sun((25, 0, 250), 0.25, col=(0.85, 0.9, 1.0), angle=30)
        for x in (28, 42.5, 57):
            for s in (-1, 1):
                K.point((x, s * (hall_half(x) - 8.6), 5.5), 1100, col=(1.0, 0.9, 0.75), r=1.2)
        for x in (20, 36, 52, 68):
            K.point((x, 0, roof_h(x) - 5), 1800, col=(0.9, 0.93, 1.0), r=2.0)
        K.camera((13.0, 0.0, 4.4), (AP_X, 0.0, 9.6), lens=float(ARGS.get('lens', 24)))
    K.render(OUT, bloom_amt=float(ARGS.get('bloom', 0.75)))


main()
