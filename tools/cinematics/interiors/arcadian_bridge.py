"""Arcadian capital ship: bridge / command chamber (concept still).

    /home/user/artenv/venv/bin/python arcadian_bridge.py --out=FILE.jpg [--res=960x540] [--samples=24]
        [--view=wide|core]

The command heart of the capital ship: a domed chamber 92 x 88 m and 34 m high, scaled for hover
vehicles. The whole forward part of the dome is one wrap-around force aperture (hair-thin hot lip,
tick marks, no glass). Layers, front to back: floating crescent consoles with small tactical
displays; the command core - a great orb in floating rings, satellites and crescents, fed with
lightning from the oculus; a second arc of consoles; then the view: the ship's own bow horns, the
fleet close by, beams. Floating sail-blades line the sides and broad arcs hang under an engraved vault.

    --cam=A   axial, from the rear gallery        --cam=B   low three-quarter from the port side
    --cam=C   high, looking down across the floor
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
VIEW = ARGS.get('view', 'wide')
RES = tuple(int(v) for v in ARGS.get('res', '960x540').split('x'))
OUT = ARGS.get('out', f'/home/user/work/arcadian-interiors/bridge_{VIEW}.jpg')
rnd = random.Random(11)

RX, RY, HW, HT = 46.0, 44.0, 8.0, 34.0
NA = 144                      # azimuth steps (2.5 deg)
ROWS = [('z', 0.0), ('z', 1.8), ('z', HW)] + [('t', k / 30) for k in range(1, 29)]
WIN_A = 77.5                  # window half angle
WIN_R0, WIN_R1 = 1, 2 + 21    # window rows: sill row .. top row
CORE = Vector((2.0, 0, 10.5))
CAM = ARGS.get('cam', 'A')


def dome(a_deg, row, shrink=0.0):
    """Point on the chamber shell at azimuth a (0 = forward) and (fractional) row index."""
    i = int(math.floor(row))
    f = row - i
    if f > 1e-6 and i + 1 < len(ROWS):
        return dome(a_deg, i, shrink).lerp(dome(a_deg, i + 1, shrink), f)
    kind, v = ROWS[min(i, len(ROWS) - 1)]
    a = math.radians(a_deg)
    if kind == 'z':
        k, z = 1.0, v
    else:
        k, z = math.cos(v * math.pi / 2) ** 0.7, HW + (HT - HW) * math.sin(v * math.pi / 2)
    k -= shrink
    return Vector((RX * k * math.cos(a), RY * k * math.sin(a), z))


def in_window(ai, ri):
    a = (ai + 0.5) * 360.0 / NA
    a = a - 360 if a > 180 else a
    return abs(a) < WIN_A and WIN_R0 <= ri < WIN_R1


def build_shell():
    nr = len(ROWS)
    verts = [tuple(dome(ai * 360.0 / NA, ri)) for ri in range(nr) for ai in range(NA)]
    wall, vault, film = [], [], []
    for ri in range(nr - 1):
        for ai in range(NA):
            aj = (ai + 1) % NA
            f = [ri * NA + ai, (ri + 1) * NA + ai, (ri + 1) * NA + aj, ri * NA + aj]
            if in_window(ai, ri):
                film.append(f)
            elif ri < 2:
                wall.append(f)
            else:
                vault.append(f)
    F._new(verts, wall, 'wall', merge=False)
    F._new(verts, vault, 'vault', merge=False)
    K.raw_mesh('bridgefilm', verts, film, K.door_mat('bridgefilm', strength=0.02, clear=0.93))
    # floor + a sunk outer ring
    F.lathe([(0.01, 0.0), (1.0, 0.0)], NA, 'floor', sq=(RX, RY), caps=False)
    # aperture lip: hot hair line, gold carrier, tick marks, a second exact line further out
    a0, a1 = -WIN_A, WIN_A
    path = []
    for k in range(51):
        path.append((a0 + (a1 - a0) * k / 50, WIN_R0))
    for k in range(1, 35):
        path.append((a1, WIN_R0 + (WIN_R1 - WIN_R0) * k / 34))
    for k in range(1, 51):
        path.append((a1 - (a1 - a0) * k / 50, WIN_R1))
    for k in range(1, 34):
        path.append((a0, WIN_R1 - (WIN_R1 - WIN_R0) * k / 34))
    K.strip([dome(a, r, 0.006) for a, r in path], 0.09, 0.09, 'white')
    K.strip([dome(a + (1.2 if a > 0 else -1.2) * (abs(a) > WIN_A - 0.1), r + (0.0 if abs(a) > WIN_A - 0.1 else (-0.25 if r <= WIN_R0 else 0.45)), 0.012)
             for a, r in path], 0.5, 0.35, 'pale')
    for k in range(0, 101):
        a = a0 + (a1 - a0) * k / 100
        big = k % 10 == 0
        for r, d in ((WIN_R0, 1), (WIN_R1, -1)):
            p0 = dome(a, r + d * 0.12, 0.008)
            p1 = dome(a, r + d * (0.55 if big else 0.3) * (1.0 if r == WIN_R1 else 0.4), 0.008)
            K.strip([p0, p1], 0.05 if not big else 0.09, 0.05, 'line', closed=False)
    K.strip([dome(a, WIN_R1 + 1.6, 0.01) for a in [a0 - 4 + (a1 - a0 + 8) * k / 60 for k in range(61)]], 0.06, 0.06, 'line', closed=False)
    K.strip([dome(a, WIN_R1 + 1.9, 0.012) for a in [a0 - 4 + (a1 - a0 + 8) * k / 60 for k in range(61)]], 0.3, 0.12, 'shell', closed=False)
    # two slim floating mullion blades in front of the opening (they touch nothing)
    for a in (-42, 42):
        pts = [dome(a, WIN_R0 + 0.3 + (WIN_R1 - WIN_R0 - 0.6) * k / 20, 0.03) for k in range(21)]
        sect = [(0.9 * max(0.07, math.sin(math.pi * k / 20)) ** 0.7, 0.14) for k in range(21)]
        rad = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        F.sweep([tuple(p) for p in pts], sect, 'pale', sides=6, up=tuple(Vector((0, 0, 1)).cross(rad)), power=0.6)
    # window end posts: one broad flat crescent each side with a hovering orb
    for s in (-1, 1):
        a = s * (WIN_A + 3.0)
        p = dome(a, 0, 0.03)
        rad = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        K.fin(p, Vector((0, 0, 1)), -rad, 21.0, 6.0, 'pale', lean=0.42, curve=2.0, rib=None)
        K.fin(dome(a + s * 6, 0, 0.03), Vector((0, 0, 1)), -rad, 12.0, 4.4, 'silver', lean=0.36, curve=2.0)
        c = dome(a - s * 1.5, 0, 0.12) + Vector((0, 0, 1.8))
        K.orb(tuple(c), 0.9, light=1.0)
        K.ring_flat(tuple(c), 1.5, 0.14, 0.08, 'silver', n=32)


def dome_stroke(a0, sw, r0, r1, w, zone, sh=0.004, n=26):
    """Flowing engraved stroke on the vault: sweeps sideways as it climbs, tapered at both ends."""
    pts, sect = [], []
    for k in range(n + 1):
        t = k / n
        pts.append(tuple(dome(a0 + sw * t ** 1.4, 2 + r0 + (r1 - r0) * t, sh)))
        ww = w * max(0.12, max(0.0, math.sin(math.pi * t)) ** 0.6)
        sect.append((ww, ww))
    F.sweep(pts, sect, zone, sides=4)


def build_vault():
    """Dark vault engraved with long flowing gold strokes; two tiers of broad arcs float under it
    (they touch nothing), a ring of small orbs hangs round the open oculus."""
    rear = ((88, 24), (112, -20), (136, 22), (160, -18), (180, 20), (200, -18), (224, 22), (248, -20), (272, -24))
    for i, (a0, sw) in enumerate(rear):
        n = 22
        pts = [dome(a0 + sw * (k / n) ** 1.5, 2 + 2.5 + 13.5 * k / n, 0.05 + 0.02 * math.sin(math.pi * k / n)) for k in range(n + 1)]
        rad = Vector((math.cos(math.radians(a0)), math.sin(math.radians(a0)), 0))
        K.arc_band(pts, 2.4, 0.26, 'pale' if i % 2 else 'silver', Vector((0, 0, 1)).cross(rad))
        K.orb(tuple(dome(a0 + sw * 1.15, 2 + 17.5, 0.06)), 0.5, light=0.9)
    for i in range(8):                                     # upper tier, all the way round
        a0, sw = 22.5 + 45 * i, (30 if i % 2 else -30)
        n = 18
        pts = [dome(a0 + sw * (k / n), 2 + 22.6 + 4.6 * k / n, 0.07) for k in range(n + 1)]
        rad = Vector((math.cos(math.radians(a0)), math.sin(math.radians(a0)), 0))
        K.arc_band(pts, 1.5, 0.2, 'silver' if i % 2 else 'pale', Vector((0, 0, 1)).cross(rad))
    r5 = random.Random(8)
    for i in range(26):                                    # engraving behind the lower arcs
        a0 = 82 + i * (196 / 25)
        sw = (1 if i % 2 else -1) * r5.uniform(26, 44)
        r0 = r5.uniform(0.4, 4.0)
        dome_stroke(a0, sw, r0, r0 + r5.uniform(9, 15), 0.3, 'inlay')
        if i % 2:
            dome_stroke(a0 + 2.5, sw * 0.92, r0 + 0.6, r0 + 11, 0.07, 'line', sh=0.006)
    for i in range(14):                                    # and over the window
        a0 = -72 + i * (144 / 13)
        sw = (1 if i % 2 else -1) * r5.uniform(20, 34)
        dome_stroke(a0, sw, 22.4, 27.6, 0.26, 'inlay')
        if i % 3 == 0:
            dome_stroke(a0 + 3, sw * 0.9, 22.6, 27.0, 0.06, 'line', sh=0.006)
    lo, hi = int(WIN_A) + 3, 360 - int(WIN_A) - 2
    for t in (9, 21.9):
        pts = [dome(a, 2 + t, 0.004) for a in (range(lo, hi, 2) if t < 17 else range(0, 362, 2))]
        K.strip(pts, 0.07, 0.07, 'line', closed=False)
        pts = [dome(a, 2 + t + 0.25, 0.003) for a in (range(lo, hi, 2) if t < 17 else range(0, 362, 2))]
        K.strip(pts, 0.4, 0.14, 'bronze', closed=False)
    for z, w, h, zone, sh in ((0.4, 0.45, 0.8, 'bronze', 0.008), (0.62, 0.06, 0.08, 'line', 0.016), (HW, 0.6, 0.3, 'silver', 0.01),
                              (HW + 0.2, 0.14, 0.12, 'line', 0.014), (HW * 0.55, 0.1, 0.1, 'line', 0.012)):
        pts = [Vector((RX * (1 - sh) * math.cos(math.radians(a)), RY * (1 - sh) * math.sin(math.radians(a)), z)) for a in range(lo, hi, 2)]
        K.strip(pts, w, h, zone, closed=False)
    oz = HT - 1.6
    for k in range(3):
        K.ring_flat((0, 0, oz), 9.6, 1.1, 0.22, 'silver', n=24, a0=k * 120 + 8, a1=k * 120 + 112)
    K.ring_flat((0, 0, oz - 0.2), 8.5, 0.08, 0.08, 'white', n=120)
    K.ring_flat((0, 0, oz - 1.8), 6.0, 0.4, 0.12, 'pale', n=96)
    K.ring_flat((0, 0, oz - 3.2), 3.8, 0.25, 0.1, 'silver', n=96)
    for k in range(8):                                     # orbs hanging in the air round the oculus
        a = math.radians(45 * k + 12)
        c = (13.5 * math.cos(a), 13.5 * math.sin(a), oz - 3.5 - 2.2 * (k % 2))
        K.orb(c, 0.5, light=1.0)
        K.ring_flat(c, 1.1, 0.1, 0.05, 'silver', n=32)
    return oz


def console(p, a, size=1.0, tilt=-12):
    """A crescent console hovering over its floor mark, with a small tactical display floating on it."""
    d = Vector((math.cos(a), math.sin(a), 0))
    R = 3.4 * size
    m = Matrix.Translation(p + Vector((0, 0, 1.5 * size)) - d * R) @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Rotation(math.radians(tilt), 4, 'Y')
    F.xf(F.crescent((0, 0, 0), R, -42, 42, 1.6 * size, 0.2 * size, 'silver', n=20, tip=0.1), m)
    F.xf(F.crescent((0, 0, 0.14 * size), R - 0.4 * size, -36, 36, 0.1, 0.05, 'line', n=20, tip=0.4), m)
    F.xf(F.crescent((0, 0, 0.14 * size), R + 0.35 * size, -32, 32, 0.06, 0.05, 'line', n=20, tip=0.4), m)
    F.xf(F.crescent((0, 0, -0.5 * size), R + 0.2 * size, -30, 30, 0.9 * size, 0.12 * size, 'pale', n=16, tip=0.1), m)   # second leaf floating under it
    hp = p + Vector((0, 0, 3.1 * size))
    K.orb(tuple(hp), 0.3 * size, light=0.7)
    mk = F.mark()
    K.ring_flat((0, 0, 0), 1.15 * size, 0.03, 0.03, 'line', n=48)
    K.ring_flat((0, 0, 0), 0.75 * size, 0.02, 0.02, 'line', n=40, a0=20, a1=250)
    K.ring_flat((0, 0, 0), 1.5 * size, 0.1 * size, 0.03, 'pale', n=20, a0=200, a1=300)
    for o in F.since(mk):
        F.xf(o, Matrix.Translation(hp) @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Rotation(math.radians(64), 4, 'Y'))
    K.ring_flat((p.x, p.y, 0.03), 1.9 * size, 0.1, 0.04, 'inlay', n=40)
    K.ring_flat((p.x, p.y, 0.04), 2.3 * size, 0.04, 0.04, 'line', n=40, a0=math.degrees(a) + 100, a1=math.degrees(a) + 260)
    F.orb((p.x, p.y, 0.0), 0.9 * size, 'soft', seg=(12, 6), sq=(1, 1, 0.06))


def build_core(oz):
    """The command core: a great orb in three floating rings, a broken ring of satellites, three
    broad crescents turning round it and a cradle of floating rings over a low dais; consoles hover
    in two arcs, one toward the view and one behind."""
    c = K.core(CORE, 3.6, rings=3, light=1.7)
    sats = []
    for k in range(7):                                     # satellites and the broken ring they ride
        a = math.radians(k * 360 / 7 + 14)
        q = CORE + Vector((9.0 * math.cos(a), 9.0 * math.sin(a), 0.9 * math.sin(k * 2.4)))
        K.orb(tuple(q), 0.42, light=0.9)
        sats.append(q)
        K.ring_flat((CORE.x, CORE.y, CORE.z - 0.5), 9.0, 0.5, 0.1, 'silver', n=14, a0=k * 360 / 7 + 22, a1=k * 360 / 7 + 57)
        K.ring_flat((CORE.x, CORE.y, CORE.z - 0.42), 9.0, 0.05, 0.05, 'line', n=14, a0=k * 360 / 7 + 24, a1=k * 360 / 7 + 55)
    for z, r in ((1.0, 7.4), (2.1, 5.6), (3.4, 4.0), (4.9, 2.6)):      # cradle of floating rings
        K.ring_flat((CORE.x, CORE.y, z), r, 0.6, 0.12, 'silver', n=96)
        K.ring_flat((CORE.x, CORE.y, z + 0.1), r, 0.06, 0.05, 'line', n=96)
    K.point((CORE.x, CORE.y, 2.0), 2500, col=(1.0, 0.8, 0.45), r=1.5)
    F.lathe([(15.0, 0.0), (14.0, 0.5), (0.01, 0.5)], 96, 'floor2', center=(CORE.x, CORE.y, 0), caps=False)
    for r, zone, w in ((13.5, 'inlay', 0.3), (13.0, 'line', 0.06), (8.6, 'inlay', 0.4), (3.2, 'white', 0.08)):
        K.ring_flat((CORE.x, CORE.y, 0.52), r, w, 0.06, zone, n=140)
    for j in range(7):
        K.swoosh((CORE.x, CORE.y), 9.4, 12.6, j * 360 / 7, j * 360 / 7 + 110, 0.5, 'inlay', 0.52)
        K.swoosh((CORE.x, CORE.y), 3.8, 8.0, j * 360 / 7 + 30, j * 360 / 7 + 150, 0.4, 'inlay', 0.52)
        K.swoosh((CORE.x, CORE.y), 4.1, 7.7, j * 360 / 7 + 44, j * 360 / 7 + 140, 0.06, 'line', 0.54)
    A.bolt((0.6, 0.3, oz - 3.2), c + Vector((0.3, 0.2, 3.7)), rnd, width=0.2, jag=0.12, depth=6, branches=4, zone='thin')
    A.bolt((-5.4, 1.5, oz - 1.8), c + Vector((-2.6, 1.2, 5.0)), rnd, width=0.1, jag=0.16, depth=6, branches=2, zone='thin')
    for k in (0, 2, 3, 5):
        dq = (sats[k] - c).normalized()
        A.bolt(c + dq * 3.7, sats[k], rnd, width=0.07, jag=0.2, depth=5, branches=2, zone='thin')
    # consoles: forward arc and rear arc
    for k in range(6):
        a = math.radians(-60 + 24 * k)
        console(Vector((CORE.x + 24.0 * math.cos(a), 24.0 * math.sin(a), 0)), a, 1.0)
    for k in range(6):
        a = math.radians(122 + 23.2 * k)
        console(Vector((CORE.x + 26.0 * math.cos(a), 26.0 * math.sin(a), 0)), a + math.pi, 1.5, tilt=12)
    # floor: rings, two layers of pinwheel strokes and long strokes running out to the walls
    for r, zone, w in ((19.0, 'line', 0.07), (30.5, 'inlay', 0.4), (31.2, 'line', 0.07), (38.0, 'inlay', 0.25)):
        o = K.ring_flat((0, 0, 0.03), 1.0, w / r, 0.05, zone, n=180)
        F.xf(o, Matrix.Diagonal((r * RX / RY, r, 1, 1)))
    for j in range(10):
        K.swoosh((CORE.x, 0), 19.8, 29.4, j * 36 + 6, j * 36 + 62, 0.6, 'inlay', 0.04, n=36)
        K.swoosh((CORE.x, 0), 20.3, 28.9, j * 36 + 14, j * 36 + 56, 0.07, 'line', 0.05, n=36)
    for j in range(16):
        K.swoosh((0, 0), 32.0, 41.5, j * 22.5 + 4, j * 22.5 - 30, 0.45, 'inlay', 0.04, n=30)
        if j % 2:
            K.swoosh((0, 0), 32.4, 40.5, j * 22.5 + 9, j * 22.5 - 22, 0.06, 'line', 0.05, n=30)
    # floating sail-blades down both sides, growing toward the rear
    for s in (-1, 1):
        for k in range(4):
            a = s * (97 + 21 * k)
            rad = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
            p = dome(a, 0, 0.13) + Vector((0, 0, 1.6))
            K.fin(p, Vector((0, 0, 1)), -rad, 9.0 + 2.6 * k, 4.2 + 0.5 * k, 'silver' if k % 2 else 'pale', lean=0.34, curve=2.0)
            K.orb(tuple(p + Vector((0, 0, -0.75)) - rad * 0.6), 0.34, light=0.8)
    return c


def build_outside():
    """The ship's own bow seen through the aperture (two great horns with a lightning bowstring), the
    fleet and beam streaks. Built last: the fleet builders reset forge's material cache."""
    tips = []
    for s in (-1, 1):
        ctl = [(34, s * 62, -12), (95, s * 70, -2), (160, s * 58, 7), (215, s * 30, 14), (245, s * 8, 17)]
        pts = A.smooth_pts(ctl, 10)
        n = len(pts)
        sect = [(7.0 * (1 - 0.9 * (k / (n - 1)) ** 1.4) + 0.4, 5.0 * (1 - 0.9 * (k / (n - 1)) ** 1.4) + 0.3) for k in range(n)]
        F.sweep([tuple(p) for p in pts], sect, 'shell', sides=10, power=0.8)
        F.sweep([tuple(p + Vector((0, 0, sect[k][1] * 0.98))) for k, p in enumerate(pts)], [(0.25, 0.25)] * n, 'glow', sides=4)
        tips.append(pts[-1])
        F.orb(tuple(pts[-1]), 1.6, 'bolt', seg=(12, 8))
        K.point(pts[-1], 3e5, col=(1.0, 0.8, 0.45), r=2.0)
    r2 = random.Random(5)
    A.bolt(tips[0], tips[1], r2, width=0.7, jag=0.18, depth=6, branches=4)
    K.finish()
    with A.gold_palette():
        for (loc, yaw, sc, pitch, roll) in (((250, -100, 38), 150, 9.0, -4, 16), ((370, -260, 72), 205, 9.0, 3, -12), ((560, -130, 150), 165, 10.0, 0, 8), ((520, 420, 70), 225, 10.0, 0, 14)):
            ship, _ = A.arcadian_corvette()
            ship.location = loc
            ship.rotation_euler = (math.radians(roll), math.radians(pitch), math.radians(yaw))
            ship.scale = (sc,) * 3
        ship, _ = A.crescent_mothership_v2()
        ship.location = (640, 275, 160)
        ship.rotation_euler = (math.radians(25), math.radians(-12), math.radians(200))
        ship.scale = (12,) * 3
    K._custom_mats()
    em = bpy.data.materials.new('beam')
    em.use_nodes = True
    b = em.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0, 0, 0, 1)
    b.inputs['Emission Color'].default_value = (1.0, 0.7, 0.22, 1)
    b.inputs['Emission Strength'].default_value = 40.0
    em2 = em.copy()
    em2.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.25, 0.7, 1.0, 1)
    for (p0, p1, wdt, mt) in (((630, 265, 160), (2600, -900, 100), 3.0, em), ((250, -100, 38), (2200, -800, 500), 0.9, em), ((2600, 2200, 500), (700, 520, 120), 1.6, em2),
                              ((640, 285, 155), (2500, 1500, 700), 2.4, em), ((370, -260, 72), (2300, -1100, 400), 0.9, em),
                              ((3000, 900, 600), (700, 380, 60), 2.0, em2), ((2800, -1500, 100), (1300, -420, 260), 2.2, em2),
                              ((560, -130, 150), (2900, -300, 600), 1.2, em)):
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
    K.init(samples=int(ARGS.get('samples', 24)), res=RES, env=float(ARGS.get('env', 0.2)), wall_h=HW, warm=(0.72, 0.8, 0.95), stars=2.5,
           core_scale=0.4)
    with K.layer('shell'):
        build_shell()
    oz = build_vault()
    build_core(oz)
    K.finish()
    K.unit('carapace', (12.0, -28.0, 0.8), yaw=22)
    K.unit('stinger', (9.0, 28.5, 0.8), yaw=-22)
    K.unit('seer', (-10.0, 33.0, 0.8), yaw=-8)
    build_outside()
    K.ghost('shell', glossy=True)
    K.light_orbs(1.0)
    K.sun((28, 0, 200), 0.25, col=(0.85, 0.9, 1.0), angle=30)
    for k in range(8):
        a = math.radians(45 * k + 22)
        K.point((31 * math.cos(a), 30 * math.sin(a), 6.5), 2600, col=(1.0, 0.88, 0.68), r=1.5)
    K.point((36, 0, 14), 3500, col=(0.75, 0.84, 1.0), r=3.0)
    cams = {'A': ((-37.0, 0.0, 8.5), (30.0, 0.0, 17.0), 18.0),
            'B': ((-27.0, -15.0, 4.4), (28.0, 8.0, 14.0), 17.0),
            'C': ((-33.0, 10.0, 20.0), (26.0, -4.0, 7.5), 20.0)}
    loc, tgt, lens = cams[CAM]
    K.camera(loc, tgt, lens=float(ARGS.get('lens', lens)))
    K.render(OUT, bloom_amt=float(ARGS.get('bloom', 0.75)))


main()
