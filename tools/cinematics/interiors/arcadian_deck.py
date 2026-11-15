"""Arcadian capital ship: launch deck (concept stills).

    /home/user/artenv/venv/bin/python arcadian_deck.py --view=game|eye --out=FILE.jpg
        [--res=960x540] [--samples=24] [--dist=158 --tx=18 --ty=-1]   (game camera)

One deck plan, two ways of looking at it:
    game   the RTS camera: high and angled, roof removed, walls cut flat at 6 m (walls = blocked ground)
    eye    cinematic, standing in the launch hall looking out through the force aperture to space

Plan (metres, +X = toward the launch maw, +Y = north). Vehicles are 8-10 m, so every route is at
least two vehicles wide and the main route (spine - hall - lane - aperture) at least three:
    launch hall   ellipse at (46, 0), 72 x 54, with a 32 m throat east to the hull edge; the landing
                  lane is a flush 26 m band (no rails, no raised edges), aperture 30 m wide
    spine         28 m corridor west from the hall to the rotunda; 28 m force-field door at x = -4,
                  its generator in a niche north of the door
    rotunda       r = 26 at (-50, 0) with a hovering core in the middle (blocked), 20 m ring
    north arc     20 m curved corridor from the rotunda to an overlook chamber open to space
    pod bay       south chamber (20 m branch) with a launch well in the floor

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
from shapely.geometry import Point, Polygon          # noqa: E402
from shapely.geometry.polygon import orient          # noqa: E402
from shapely.ops import unary_union                  # noqa: E402

HULL_C, HULL_RX, HULL_RY = (-10.0, 0.0), 104.0, 64.0
HULL = K.ellipse(HULL_C, HULL_RX, HULL_RY, n=220)
HALL_C, HALL_RX, HALL_RY = (46.0, 0.0), 36.0, 27.0
THROAT = 16.0                                         # half width of the throat
LANE = 13.0                                           # half width of the flush landing lane
AP_X = 89.0
AP_R = 15.0                                           # aperture half width
AP_SQ = 0.5 if GAME else 0.62
AP_Z = 7.6 if GAME else 9.6
ROT_C, ROT_R = (-50.0, 0.0), 26.0
ISL_R = 5.5
DOOR_X, DOOR_W = -4.0, 14.0
GEN_C = (-4.0, 22.5)
OVER_C = (27.0, 49.0)
POD_C = (4.0, -45.0)
WELL_C, WELL_R = (13.0, -46.0), 5.5
ARC_C, ARC_R = (-8.0, -4.0), 50.0

ROOMS = [
    K.ellipse(HALL_C, HALL_RX, HALL_RY, n=180),
    K.capsule((66, 0), (130, 0), 2 * THROAT),         # throat, runs out through the hull edge
    K.capsule((20, 0), (-34, 0), 28),                 # spine (main route: three abreast)
    K.ellipse(ROT_C, ROT_R, ROT_R, n=120),
    K.capsule((-64, 0), (-170, 0), 28),               # spine carries on west, deeper into the ship
    K.ellipse(GEN_C, 6.5, 6.5, n=48),                 # generator niche (not a route)
    K.capsule((-4, 12), (-4, 17), 8, n=8),
    K.band(ARC_C, ARC_R, 60, 152, 20, n=48),          # north arc corridor
    K.ellipse(OVER_C, 17, 15, n=72),                  # overlook, breaks the hull edge
    K.capsule((-42, -16), (-12, -42), 20),            # south branch
    K.superellipse(POD_C, 24, 13, p=3.2, n=120),      # pod bay
]
ISLAND = K.ellipse(ROT_C, ISL_R, ISL_R, n=48)         # rotunda centre is blocked by the core

# One walkable outline: the union of the rooms, "closed" by 3.5 m so that every wall nose where two
# rooms meet is rounded (clean wall caps, no mitre notches at corners).
_u = unary_union([Polygon(r).buffer(0) for r in ROOMS])
_u = _u.buffer(3.5, 24).buffer(-3.5, 24).simplify(0.03)
if _u.geom_type != 'Polygon':
    _u = max(_u.geoms, key=lambda g: g.area)
WALK = orient(Polygon(_u.exterior), 1.0)
WALK_OUT = [(float(x), float(y)) for x, y in list(WALK.exterior.coords)[:-1]]
_ISL = Polygon(ISLAND)
# The solid mass is the hull minus the walkable outline, "opened" by 2.2 m: that rounds every wall
# nose - also where a room breaks through the hull edge - and removes knife-edge slivers.
_s = Polygon(HULL).buffer(0).difference(WALK).buffer(-2.2, 24).buffer(2.2, 24).simplify(0.03)
SOLIDS = [orient(Polygon(g.exterior), 1.0) for g in (_s.geoms if _s.geom_type == 'MultiPolygon' else [_s]) if g.area > 60]


def walkable(p):
    q = Point(float(p[0]), float(p[1]))
    return WALK.contains(q) and not _ISL.contains(q)


def solid(x, y, m):
    """True when (x, y) is in the solid mass, at least m from any walkable floor and from the hull edge."""
    u, v = (x - HULL_C[0]) / (HULL_RX - m - 1.5), (y - HULL_C[1]) / (HULL_RY - m - 1.5)
    return u * u + v * v < 1.0 and WALK.distance(Point(x, y)) > m


def hall_half(x):
    """Half width of the launch hall + throat at station x."""
    w = 0.0
    u = (x - HALL_C[0]) / HALL_RX
    if abs(u) < 1:
        w = HALL_RY * math.sqrt(1 - u * u)
    if x > 66:
        w = max(w, THROAT)
    if x < 20:
        w = max(w, 14.0)
    return w


# ------------------------------------------------------------------ build
def build_deck():
    K.slab(HULL, [K.ellipse(WELL_C, WELL_R, WELL_R, n=64)], -3.0, 0.0, 'floor')
    loops = []
    for g in SOLIDS:
        loops += K.deck_walls([(float(x), float(y)) for x, y in list(g.exterior.coords)[:-1]], [], H)
    for loop in loops:
        sl = K.smooth_loop(loop)
        face = [walkable(p + n * 1.5) for p, n in sl]       # True where the wall faces walkable floor
        n = len(sl)
        if all(face):
            dress_wall(sl, True)
            continue
        start = next(i for i in range(n) if face[i] != face[i - 1])
        run, kind = [], face[start]
        for k in range(n + 1):
            i = (start + k) % n
            if k < n and face[i] == kind:
                run.append(sl[i])
                continue
            if len(run) > 4:
                if kind:
                    dress_wall(run, False)
                else:                                        # wall top along the outer hull edge
                    K.strip(K.offset(run, -0.5, H), 0.9, 0.4, 'pale', closed=False)
                    K.strip(K.offset(run, -0.5, H + 0.24), 0.12, 0.1, 'line', closed=False)
            run, kind = [sl[i]], face[i]
    build_hull_skirt()
    # the rotunda core stands on a low blocked plinth
    F.lathe([(ISL_R, 0.0), (ISL_R - 0.1, 0.9), (ISL_R - 0.8, 1.3), (0.01, 1.3)], 64, 'bronze', center=(ROT_C[0], ROT_C[1], 0), caps=False)
    K.ring_flat((ROT_C[0], ROT_C[1], 1.0), ISL_R, 0.1, 0.1, 'line', n=64)
    K.ring_flat((ROT_C[0], ROT_C[1], 0.1), ISL_R + 0.3, 0.4, 0.16, 'silver', n=64)
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


def dress_wall(sl, closed=True):
    """Trim one (smoothed) wall run: dark skirting with a glow line, silver cap with one consistent
    glowing gold line along the top, and flowing inlay lines on the floor that follow the wall."""
    K.strip(K.offset(sl, 0.2, 0.4), 0.4, 0.8, 'bronze', closed=closed)
    K.strip(K.offset(sl, 0.43, 0.62), 0.06, 0.08, 'line', closed=closed)
    K.strip(K.offset(sl, -0.8, H + 0.02), 1.5, 0.12, 'silver', closed=closed)   # wall cap band
    K.strip(K.offset(sl, 0.02, H + 0.1), 0.22, 0.16, 'line', closed=closed)      # glowing top line
    K.strip(K.offset(sl, -1.85, H + 0.04), 0.6, 0.14, 'pale', closed=closed)
    K.strip(K.offset(sl, 1.3, 0.02), 0.3, 0.04, 'inlay', closed=closed)          # floor inlays
    K.strip(K.offset(sl, 1.85, 0.02), 0.06, 0.04, 'line', closed=closed)


def flow_line(ctl, w, zone, h=0.03, steps=8):
    K.strip(A.smooth_pts([Vector(c) for c in ctl], steps), w, h, zone, closed=False)


def braid(x0, x1, amp, wl, z=0.03):
    """Two long engraved strokes weaving along a corridor centre (flush with the floor)."""
    for ph in (0.0, math.pi):
        pts = [(x0 + (x1 - x0) * k / 60, amp * math.sin(2 * math.pi * (x1 - x0) * k / 60 / wl + ph), z) for k in range(61)]
        K.strip(pts, 0.32, 0.03, 'inlay', closed=False)
        if ph == 0.0:
            K.strip([(x, y, z + 0.01) for x, y, _ in pts], 0.07, 0.03, 'line', closed=False)


def build_floor_marks():
    hx, hy = HALL_C
    # landing lane: a broad flush band three vehicles wide, hairlines at its edges and wide flowing
    # chevrons across the whole width. Nothing here is raised: vehicles cross it anywhere.
    lane = [(x, y) for x, y in K.capsule((30, 0), (AP_X + 1.5, 0), 2 * LANE, n=12) if x < AP_X + 1.6]
    K.slab(lane, [], 0.0, 0.025, 'floor2')
    for s in (-1, 1):
        K.strip([(31, s * LANE, 0.03), (AP_X + 1.5, s * LANE, 0.03)], 0.1, 0.03, 'line', closed=False)
    for k, x in enumerate(range(28, int(AP_X) - 3, 10)):
        for s in (-1, 1):
            flow_line([(x + 4.0, s * 0.3, 0.035), (x + 2.2, s * 4.5, 0.035), (x - 2.6, s * (LANE - 2.2), 0.035)], 0.42, 'inlay')
            if k % 2 == 0:
                flow_line([(x + 5.2, s * 0.3, 0.04), (x + 3.4, s * 4.5, 0.04), (x - 1.4, s * (LANE - 2.2), 0.04)], 0.07, 'line')
    for r, z in ((0.93, 'inlay'), (0.948, 'line')):
        o = K.ring_flat((0, 0, 0.03), 1.0, 0.01 if z == 'inlay' else 0.003, 0.03, z, n=160, a0=28, a1=332)
        F.xf(o, Matrix.Translation((hx, hy, 0)) @ Matrix.Diagonal((HALL_RX * r, HALL_RY * r, 1, 1)))
    # parking pads along the hall sides, clear of the lane: each one drawn differently
    pads = []
    k = 0
    for x in (33.0, 46.0, 59.0):
        for s in (-1, 1):
            y = s * (hall_half(x) - 6.6)
            K.flow_pad((x, y), 4.3, style=k)
            # one broad crescent hovering behind the pad (touches nothing)
            o = F.crescent((0, 0, 0), 5.6, 90 - 38, 90 + 38, 1.4, 0.16, 'silver', n=20, tip=0.1)
            F.xf(o, Matrix.Translation((x, y, 2.6 + 0.3 * (k % 3))) @ Matrix.Rotation(math.radians(0 if s > 0 else 180), 4, 'Z'))
            o = F.crescent((0, 0, 0), 5.6, 90 - 32, 90 + 32, 0.1, 0.06, 'line', n=20, tip=0.4)
            F.xf(o, Matrix.Translation((x, y, 2.72 + 0.3 * (k % 3))) @ Matrix.Rotation(math.radians(0 if s > 0 else 180), 4, 'Z'))
            pads.append((x, y, -s * 90))
            k += 1
    # arrival apron at the west end of the hall: flowing strokes that fan out from the lane
    for s in (-1, 1):
        for j, (yy, ww) in enumerate(((5.0, 0.4), (10.5, 0.3), (16.0, 0.22))):
            flow_line([(29, s * yy * 0.55, 0.035), (22, s * yy * 0.8, 0.035), (15 + 2 * j, s * yy, 0.035), (13 + 3 * j, s * (yy + 3), 0.035)], ww, 'inlay')
    # rotunda: rings and a great pinwheel of engraved strokes
    cx, cy = ROT_C
    for r, z, w in ((9.0, 'inlay', 0.3), (9.5, 'line', 0.06), (22.0, 'inlay', 0.3), (22.5, 'line', 0.06)):
        K.ring_flat((cx, cy, 0.03), r, w, 0.03, z, n=140)
    for j in range(7):
        K.swoosh((cx, cy), 10.4, 21.0, j * 360 / 7, j * 360 / 7 + 105, 0.7, 'inlay', 0.03, h=0.03)
        K.swoosh((cx, cy), 10.9, 20.4, j * 360 / 7 + 12, j * 360 / 7 + 96, 0.07, 'line', 0.04, h=0.03)
    # corridors: weaving engraved strokes down the middle (flush)
    braid(-22, -9, 3.2, 26.0)
    braid(4, 15, 3.2, 22.0)
    braid(-150, -78, 3.6, 36.0)
    pts = [(ARC_C[0] + ARC_R * math.cos(math.radians(a)), ARC_C[1] + ARC_R * math.sin(math.radians(a)), 0.035) for a in range(66, 146, 2)]
    K.strip(pts, 0.1, 0.03, 'line', closed=False)
    for dr in (-3.2, 3.2):
        pts = [(ARC_C[0] + (ARC_R + dr) * math.cos(math.radians(a)), ARC_C[1] + (ARC_R + dr) * math.sin(math.radians(a)), 0.03) for a in range(70, 142, 2)]
        K.strip(pts, 0.3, 0.03, 'inlay', closed=False)
    flow_line([(-39, -19, 0.035), (-30, -24, 0.035), (-24, -33, 0.035), (-14, -39, 0.035)], 0.3, 'inlay')
    flow_line([(-37, -21, 0.04), (-28, -26, 0.04), (-22, -35, 0.04), (-12, -41, 0.04)], 0.08, 'line')
    K.flow_pad(OVER_C, 7.0, style=2)
    # pod bay: the launch well is a force aperture, so it alone gets an exact ring with tick marks
    K.ring_flat((WELL_C[0], WELL_C[1], 0.1), WELL_R + 0.25, 0.4, 0.25, 'silver', n=96)
    K.ring_flat((WELL_C[0], WELL_C[1], 0.3), WELL_R - 0.05, 0.07, 0.07, 'white', n=96)
    K.ring_flat((WELL_C[0], WELL_C[1], 0.05), WELL_R + 1.4, 0.05, 0.05, 'line', n=96)
    K.ticks((WELL_C[0], WELL_C[1], 0.06), WELL_R + 1.45, WELL_R + 1.75, 120, 0.04, 0.04, 'line', every=10, long=0.4)
    K.raw_mesh('wellfield', [(WELL_C[0] + WELL_R * math.cos(2 * math.pi * k / 64), WELL_C[1] + WELL_R * math.sin(2 * math.pi * k / 64), 0.02)
                             for k in range(64)], [list(range(64))], K.door_mat('wellfilm', strength=0.25, clear=0.8))
    K.flow_pad((POD_C[0] - 14, POD_C[1] + 1), 4.2, style=3)
    return pads


def build_door():
    """Force-field door across the spine at DOOR_X with its generator in the north niche. The energy
    sheet is bowed in plan so it shows its face to a camera looking from any side, including from
    straight above; a bright threshold bar follows it and a lit conduit runs to the generator."""
    x = DOOR_X
    w = DOOR_W
    hh = H * 0.95
    sag = 5.0

    def px(y):
        return x + sag * (1 - (y / (w - 0.6)) ** 2)

    for s in (-1, 1):                                   # pylons: one broad flat fin each side
        K.fin((x - 0.4, s * (w - 0.25), 0.0), (0, 0, 1), (0.25, -s, 0), hh * 1.15, 3.0, 'silver', lean=0.22, curve=2.2)
        F.cyl((x, s * (w - 0.75), 0.2), (x, s * (w - 0.75), hh), 0.09, 6, 'white')
        K.orb((x, s * (w - 0.75), hh + 0.5), 0.5, light=0.6)
    n = 44
    ys = [-(w - 0.6) + 2 * (w - 0.6) * k / n for k in range(n + 1)]
    top = [(px(y), y, hh) for y in ys]
    verts = [(px(y), y, 0.05) for y in ys] + top
    faces = [[k, k + 1, n + 2 + k, n + 1 + k] for k in range(n)]
    K.raw_mesh('doorfilm', verts, faces, K.door_mat('doorfilm', strength=2.4 if GAME else 1.1, clear=0.3 if GAME else 0.55))
    K.strip(top, 0.1, 0.1, 'white', closed=False)
    K.strip([(px(y), y, 0.06) for y in ys], 0.6, 0.06, 'white', closed=False)          # threshold bar
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
    cond = A.smooth_pts([(gx, gy - 3.3, 0.06), (gx + 0.2, 17.0, 0.06), (x + 0.3, w - 0.2, 0.06)], 8)
    K.strip(cond, 0.34, 0.07, 'white', closed=False)
    K.strip(cond, 1.0, 0.04, 'inlay', closed=False)
    A.bolt(c + Vector((0, -1.7, 0.2)), (x, w - 0.75, hh + 0.5), rnd, width=0.12, jag=0.2, depth=5, branches=2, zone='thin')
    return c


def build_islands():
    """Machinery set into the solid mass between the halls (game view). Dark and low in contrast, but
    built as working alien plant rather than ornament: reservoirs held in crescent clamps, banks of
    capacitor pods on a common rail, fans of cooling vanes, stepped coil stacks, and bundles of
    conduit that run from one machine to the next. Placed procedurally wherever the mass is deep."""
    r3 = random.Random(21)
    nodes = []
    for _ in range(20000):
        x, y = r3.uniform(-112, 92), r3.uniform(-62, 62)
        r = r3.uniform(2.2, 3.9)
        if not solid(x, y, r * 1.35 + 1.2):
            continue
        if any((x - a) ** 2 + (y - b) ** 2 < (r * 1.5 + c * 1.5 + 2.5) ** 2 for a, b, c in nodes):
            continue
        nodes.append((x, y, r))
        if len(nodes) >= 110:
            break
    z = H
    for k, (x, y, r) in enumerate(nodes):
        kind = k % 4
        a0 = r3.uniform(0, 360)
        if kind == 0:                                   # reservoir dome in three crescent clamps
            F.lathe([(r, 0.0), (r * 0.96, 0.4), (r * 0.7, 0.95), (r * 0.3, 1.2), (0.01, 1.25)], 40, 'under', center=(x, y, z), caps=False)
            K.ring_flat((x, y, z + 0.06), r * 1.22, 0.3, 0.12, 'bronze', n=48)
            for j in range(3):
                o = F.crescent((0, 0, 0), r * 1.45, -38, 38, r * 0.34, 0.5, 'bronze', n=14, tip=0.15)
                F.xf(o, Matrix.Translation((x, y, z + 0.05)) @ Matrix.Rotation(math.radians(a0 + j * 120), 4, 'Z'))
            K.ring_flat((x, y, z + 0.98), r * 0.66, 0.05, 0.04, 'soft', n=40)
        elif kind == 1:                                 # bank of capacitor pods on a curved rail
            n = 6
            for j in range(n):
                a = math.radians(a0 + (j - (n - 1) / 2) * 17)
                px, py = x + r * 1.1 * math.cos(a) - r * 0.9 * math.cos(math.radians(a0)), y + r * 1.1 * math.sin(a) - r * 0.9 * math.sin(math.radians(a0))
                ln = r * (0.75 - 0.07 * abs(j - (n - 1) / 2))
                o = F.orb((0, 0, 0), 1.0, 'under', seg=(12, 6), sq=(ln, 0.42, 0.5))
                F.xf(o, Matrix.Translation((px, py, z + 0.3)) @ Matrix.Rotation(a, 4, 'Z'))
                o = F.orb((0, 0, 0), 1.0, 'soft', seg=(8, 4), sq=(0.16, 0.16, 0.1))
                F.xf(o, Matrix.Translation((px + ln * 0.8 * math.cos(a), py + ln * 0.8 * math.sin(a), z + 0.62)))
            K.ring_flat((x - r * 0.9 * math.cos(math.radians(a0)), y - r * 0.9 * math.sin(math.radians(a0)), z + 0.04), r * 0.5, 0.5, 0.3, 'bronze',
                        n=20, a0=a0 - 52, a1=a0 + 52)
            K.ring_flat((x - r * 0.9 * math.cos(math.radians(a0)), y - r * 0.9 * math.sin(math.radians(a0)), z + 0.04), r * 2.0, 0.22, 0.14, 'bronze',
                        n=24, a0=a0 - 50, a1=a0 + 50)
        elif kind == 2:                                 # fan of cooling vanes between two arcs
            n = 13
            for j in range(n):
                a = math.radians(a0 + (j - (n - 1) / 2) * 8)
                b = a + 0.35                             # vanes sweep, they are not radial spokes
                p0 = (x + r * 0.55 * math.cos(a), y + r * 0.55 * math.sin(a), z + 0.3)
                p1 = (x + r * 1.5 * math.cos(b), y + r * 1.5 * math.sin(b), z + 0.3)
                K.strip([p0, p1], 0.1, 0.6, 'under' if j % 2 else 'bronze', closed=False)
            K.ring_flat((x, y, z + 0.05), r * 0.45, 0.4, 0.5, 'bronze', n=20, a0=a0 - 58, a1=a0 + 58)
            K.ring_flat((x, y, z + 0.05), r * 1.62, 0.2, 0.2, 'bronze', n=24, a0=a0 - 38, a1=a0 + 68)
            F.orb((x, y, z + 0.2), r * 0.3, 'under', seg=(12, 6), sq=(1, 1, 0.7))
        else:                                           # stepped coil stack with a tap line
            for j in range(5):
                rr = r * (1.0 - 0.17 * j)
                K.ring_flat((x, y, z + 0.14 + 0.24 * j), rr, r * 0.15, 0.24, 'under' if j % 2 else 'bronze', n=40)
            F.orb((x, y, z + 1.1), r * 0.2, 'soft', seg=(10, 6), sq=(1, 1, 0.5))
            K.swoosh((x, y), r * 1.1, r * 1.9, a0, a0 + 150, 0.3, 'bronze', z + 0.05, h=0.2)
    # conduit bundles from machine to machine
    done = set()
    for i, (x, y, r) in enumerate(nodes):
        near = sorted(range(len(nodes)), key=lambda j: (nodes[j][0] - x) ** 2 + (nodes[j][1] - y) ** 2)[1:3]
        for j in near:
            if (min(i, j), max(i, j)) in done:
                continue
            a, b = Vector((x, y, 0)), Vector((nodes[j][0], nodes[j][1], 0))
            d = b - a
            if d.length > 46 or d.length < 8:
                continue
            side = Vector((-d.y, d.x, 0)).normalized()
            path = None
            for bow in (0.14, -0.14, 0.0):
                ctl = [a + d * 0.12, a + d * 0.5 + side * d.length * bow, b - d * 0.12]
                pts = A.smooth_pts(ctl, 10)
                if all(solid(p.x, p.y, 1.8) for p in pts):
                    path = pts
                    break
            if path is None:
                continue
            done.add((min(i, j), max(i, j)))
            nb = 3 if (i + j) % 2 else 2
            for q in range(nb):
                off = (q - (nb - 1) / 2) * 0.75
                line = []
                for m, p in enumerate(path):
                    t = (path[min(m + 1, len(path) - 1)] - path[max(m - 1, 0)]).normalized()
                    line.append((p.x - t.y * off, p.y + t.x * off, z + 0.28))
                F.sweep(line, [(0.27, 0.27)] * len(line), 'under', sides=6)
            for m in range(4, len(path) - 4, 6):        # collars clamping the bundle
                t = (path[m + 1] - path[m - 1]).normalized()
                w = nb * 0.75 + 0.5
                K.strip([(path[m].x - t.y * w / 2, path[m].y + t.x * w / 2, z + 0.3), (path[m].x + t.y * w / 2, path[m].y - t.x * w / 2, z + 0.3)],
                        0.5, 0.66, 'bronze', closed=False)


def build_rotunda_core():
    cx, cy = ROT_C
    c = K.core((cx, cy, 6.6), 3.1, rings=3, light=1.4)
    for k in range(4):                                     # broad arcs floating round the core
        K.ring_flat((cx, cy, 3.0 + 0.5 * (k % 2)), 7.0, 1.1, 0.16, 'silver', n=18, a0=k * 90 + 12, a1=k * 90 + 74)
        K.ring_flat((cx, cy, 3.12 + 0.5 * (k % 2)), 7.0, 0.07, 0.06, 'line', n=18, a0=k * 90 + 16, a1=k * 90 + 70)
    for k in range(2):
        a = math.radians(50 + 180 * k)
        A.bolt(c + Vector((math.cos(a) * 2.8, math.sin(a) * 2.8, 0.3)), (cx + math.cos(a + 0.5) * 7.0, cy + math.sin(a + 0.5) * 7.0, 3.3),
               rnd, width=0.12, jag=0.22, depth=5, branches=2, zone='thin')
    return c


def build_launch():
    """Aperture at the hull edge: 30 m wide, as wide as the lane that leads to it. Nothing stands in
    or over the lane; the carrier fins lie flat against the throat walls and the two feed orbs hover
    high beside the lip."""
    ap_c = Vector((AP_X, 0.0, AP_Z))
    K.aperture(ap_c, (1, 0, 0), AP_R, sq=(1.0, AP_SQ), rings=3, seed=4, bolts=8)
    hh = 21.0 if not GAME else 10.0
    for s in (-1, 1):
        K.fin((ap_c.x - 1.0, s * (THROAT - 0.25), 0.0), (0, 0, 1), (-1, 0, 0), hh, 6.0, 'pale', lean=0.3, curve=2.0, rib=None)
        K.fin((ap_c.x - 7.5, s * (THROAT - 0.2), 0.0), (0, 0, 1), (-1, 0, 0), hh * 0.6, 4.5, 'silver', lean=0.26, curve=2.0)
        oz = AP_Z + AP_R * AP_SQ * 0.55
        K.orb((ap_c.x - 1.6, s * (AP_R - 0.4), oz), 0.9, light=1.0)
        K.ring_flat((ap_c.x - 1.6, s * (AP_R - 0.4), oz), 1.5, 0.12, 0.08, 'silver', n=32)
        A.bolt((ap_c.x - 1.6, s * (AP_R - 0.4), oz + 0.9), (ap_c.x, s * AP_R * 0.72, AP_Z + AP_R * AP_SQ * 0.7), rnd, width=0.15, jag=0.16,
               depth=6, branches=2, zone='thin')
        A.bolt((ap_c.x - 1.6, s * (AP_R - 0.4), oz - 0.9), (ap_c.x, s * AP_R * 0.93, AP_Z - AP_R * AP_SQ * 0.35), rnd, width=0.1, jag=0.16,
               depth=5, branches=1, zone='thin')
    K.strip([(AP_X - 0.4, -AP_R * 0.97, 0.05), (AP_X - 0.4, AP_R * 0.97, 0.05)], 0.5, 0.05, 'white', closed=False)   # threshold bar
    K.strip([(AP_X - 1.6, -AP_R * 0.97, 0.04), (AP_X - 1.6, AP_R * 0.97, 0.04)], 0.08, 0.04, 'line', closed=False)
    return ap_c


def arch(x, t, h):
    """Point on the roof arch at station x: t in -1..1 from the south wall top over the apex."""
    w = hall_half(x) + 0.6
    a = math.pi / 2 * t
    return Vector((x, w * math.copysign(abs(math.sin(a)) ** 0.8, t), H + (h - H) * math.cos(a) ** 0.9))


def roof_h(x):
    u = (x - 11.0) / (AP_X + 3 - 11.0)
    return 17.0 + 15.0 * math.sin(math.pi * min(1.0, max(0.0, u)) ** 0.8) ** 0.7 + (7.0 if x > 70 else 7.0 * max(0.0, (x - 55) / 15.0))


def build_roof():
    """Vault over the hall for the eye-level view: a dark engraved shell, and a few broad silver arcs
    floating under it. The arcs touch neither the walls nor each other; each sweeps forward toward
    the aperture as it rises, and the two sides are staggered."""
    xs = [6 + 1.5 * k for k in range(59)]
    rings = [[tuple(arch(x, -1 + 2 * k / 40, roof_h(x) + 1.2)) for k in range(41)] for x in xs]
    F.loft(rings, 'vault', caps=False, closed=False)
    tips = []
    for s, stations in ((-1, (17.0, 34.0, 51.0, 68.0)), (1, (25.0, 42.0, 59.0, 76.0))):
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
    for k in range(5):                                    # spine: a few orbs hovering in single rings
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
    cz = AP_Z
    n = 72
    ro = AP_R + 1.4
    ring_o = [(AP_X + 1.2, ro * math.cos(2 * math.pi * k / n), cz + ro * (AP_SQ + 0.03) * math.sin(2 * math.pi * k / n)) for k in range(n)]
    ring_b = [(AP_X + 1.2, 36 * math.cos(2 * math.pi * k / n), cz + 40 * math.sin(2 * math.pi * k / n)) for k in range(n)]
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
    # vehicles: enough of them, side by side, to prove the widths
    names = ['stinger', 'carapace', 'glider', 'spitter', 'darter', 'mortar_beast']
    for k, (x, y, yaw) in enumerate(pads):
        if k == 3 or (not GAME and k < 2):
            continue                                     # one pad empty (and the two beside the eye camera)
        K.unit(names[k % len(names)], (x, y, 0.75), yaw=yaw + (8 if k % 2 else -6))
    if GAME:
        for (n_, x, y, yw) in (('stinger', 71, -9.0, 0), ('carapace', 73.5, 0.0, 0), ('darter', 70.5, 9.0, 0),      # three abreast in the lane
                               ('spitter', 52, -6.0, 178), ('seer', 49, 5.5, 183),                                # two arriving, side by side
                               ('stinger', 19, -8.5, 205), ('mortar_beast', 16.5, 1.0, 180), ('darter', 20, 9.5, 158),  # fanning out
                               ('carapace', -3.5, 6.2, 180), ('stinger', -1.5, -6.2, 0),                           # two abreast through the door
                               ('spitter', -20, -6.5, 0), ('glider', -23, 7.0, 180),
                               ('carapace', -51, -16, 5), ('seer', -62, 12, 215), ('darter', -40, 15, 130),
                               ('ferrier', -10, -44, 15), ('weaver', 23, 45, 70), ('gorger', 33, 53, 30),
                               ('stinger', -15.8, 40.3, 12), ('darter', -17.6, 50.2, 192),                         # passing in the north arc
                               ('carapace', -24, -25.6, -41), ('spitter', -30, -32.4, 139)):                       # and in the south branch
            K.unit(n_, (x, y, 0.9), yaw=yw)
        K.unit('glider', (82, -4, 5.0), yaw=0, pitch=-3)  # lifting off toward the aperture
        K.unit('disc', (WELL_C[0], WELL_C[1], 3.0), yaw=0)
    else:
        r2 = random.Random(3)
        for (n_, x, y, zz, yw, pt, rl) in (('carapace', 39, -9.2, 1.0, 0, 0, 0), ('glider', 46, 2.5, 4.9, 2, -4, 5), ('stinger', 38, 9.2, 1.0, 0, 0, 0),
                                           ('darter', 60, -5.5, 3.4, 0, -3, -4), ('spitter', 62, 6.0, 2.6, 0, -2, 3),
                                           ('seer', 79, 0.5, 7.0, 0, -3, 0)):
            K.unit(n_, (x, y, zz), yaw=yw, pitch=pt, roll=rl)
            if zz > 4:
                K.point((x, y, zz - 1.6), 900, col=(1.0, 0.8, 0.45), r=1.0)
                for dy in (-1.6, 1.8):                                     # lightning lift under it
                    A.bolt((x + 0.5, y + dy, zz - 0.7), (x + 0.5 + r2.uniform(-1.5, 1.5), y + dy * 2.0, 0.1), r2, width=0.045, jag=0.2, depth=5,
                           branches=2, zone='thin')
        K.unit('halo', (112, -5, 10), yaw=5, roll=12)
        K.finish()
        space_ships()

    # ---------------------------------------------------------------- light + camera
    if GAME:
        K.light_orbs(0.3)
        K.sun((20, 0, 200), 2.3, col=(1.0, 0.96, 0.9), angle=8)
        K.sun((55, 0, 20), 0.8, col=(0.75, 0.84, 1.0), angle=20)
        K.point((AP_X, 0, 6), 4000, col=(1.0, 0.82, 0.5), r=1.0)
        K.point((DOOR_X + 3, 0, 3), 4000, col=(1.0, 0.8, 0.45), r=1.0)
        tgt = Vector((float(ARGS.get('tx', 40)), float(ARGS.get('ty', -2.0)), 0))
        el = math.radians(float(ARGS.get('el', 56)))
        dist = float(ARGS.get('dist', 150))
        K.camera(tgt + Vector((0, -math.cos(el) * dist, math.sin(el) * dist)), tgt, lens=float(ARGS.get('lens', 40)))
    else:
        K.ghost('roof')
        K.light_orbs(0.7)
        K.sun((25, 0, 250), 0.25, col=(0.85, 0.9, 1.0), angle=30)
        for x in (33, 46, 59):
            for s in (-1, 1):
                K.point((x, s * (hall_half(x) - 6.6), 5.5), 1100, col=(1.0, 0.9, 0.75), r=1.2)
        for x in (20, 36, 52, 68, 82):
            K.point((x, 0, roof_h(x) - 5), 1800, col=(0.9, 0.93, 1.0), r=2.0)
        K.camera((float(ARGS.get('cx', 18.0)), float(ARGS.get('cy', -2.5)), float(ARGS.get('cz', 6.4))), (AP_X, 0.5, 8.6), lens=float(ARGS.get('lens', 22)))
    K.render(OUT, bloom_amt=float(ARGS.get('bloom', 0.75)))


main()
