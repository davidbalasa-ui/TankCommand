"""Arcadian capital ship: bridge / command chamber (concept still).

    /home/user/artenv/venv/bin/python arcadian_bridge.py --out=FILE.jpg [--res=960x540] [--samples=24]
        [--view=wide|core]

A domed chamber 64 x 60 m, scaled for hover vehicles. The whole forward third of the dome is one
wrap-around force aperture (hair-thin hot lip, tick marks, no glass). In the middle the command core
floats over a low dais inside a tactical orrery of thin exact rings; crescent consoles hover round
it. Slim blade ribs rise up the dark vault and stop short of a floating oculus ring that feeds the
core with lightning. Through the aperture: the ship's own bow horns, the fleet, beam streaks.
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

RX, RY, HW, HT = 32.0, 30.0, 7.0, 25.0
NA = 144                      # azimuth steps (2.5 deg)
ROWS = [('z', 0.0), ('z', 3.4), ('z', HW)] + [('t', k / 30) for k in range(1, 29)]
WIN_A = 62.5                  # window half angle
WIN_R0, WIN_R1 = 1, 2 + 17    # window rows: sill row .. top row
CORE = Vector((0, 0, 7.6))


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
    for a in (-31, 31):
        pts = [dome(a, WIN_R0 + 0.3 + (WIN_R1 - WIN_R0 - 0.6) * k / 20, 0.03) for k in range(21)]
        sect = [(0.9 * max(0.07, math.sin(math.pi * k / 20)) ** 0.7, 0.14) for k in range(21)]
        rad = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        F.sweep([tuple(p) for p in pts], sect, 'pale', sides=6, up=tuple(Vector((0, 0, 1)).cross(rad)), power=0.6)
    # window end posts: one broad flat crescent each side with a hovering orb
    for s in (-1, 1):
        a = s * (WIN_A + 3.0)
        p = dome(a, 0, 0.03)
        rad = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        K.fin(p, Vector((0, 0, 1)), -rad, 15.0, 4.6, 'pale', lean=0.42, curve=2.0, rib=None)
        K.fin(dome(a + s * 6, 0, 0.03), Vector((0, 0, 1)), -rad, 9.0, 3.4, 'silver', lean=0.36, curve=2.0)
        c = dome(a - s * 1.5, 0, 0.12) + Vector((0, 0, 1.8))
        K.orb(tuple(c), 0.9, light=1.0)
        K.ring_flat(tuple(c), 1.5, 0.14, 0.08, 'silver', n=32)


def build_vault():
    """Dark engraved vault with a few broad arcs floating under it (they touch nothing and sweep
    sideways as they rise), two glowing threads, and plain floating rings under the open oculus."""
    for i, (a0, sw) in enumerate(((84, 26), (118, -22), (150, 24), (182, -20), (212, 24), (246, -22), (276, -26))):
        n = 22
        pts = [dome(a0 + sw * (k / n) ** 1.5, 2 + 2.5 + 14.5 * k / n, 0.05 + 0.02 * math.sin(math.pi * k / n)) for k in range(n + 1)]
        rad = Vector((math.cos(math.radians(a0)), math.sin(math.radians(a0)), 0))
        K.arc_band(pts, 1.9, 0.22, 'pale' if i % 2 else 'silver', Vector((0, 0, 1)).cross(rad))
        K.orb(tuple(dome(a0 + sw * 1.15, 2 + 18.5, 0.06)), 0.45, light=0.8)
    for t in (9, 20):
        pts = [dome(a, 2 + t, 0.004) for a in range(66, 295, 2)]
        K.strip(pts, 0.07, 0.07, 'line', closed=False)
        pts = [dome(a, 2 + t + 0.25, 0.003) for a in range(66, 295, 2)]
        K.strip(pts, 0.4, 0.14, 'bronze', closed=False)
    for z, w, h, zone, sh in ((0.4, 0.45, 0.8, 'bronze', 0.008), (0.62, 0.06, 0.08, 'line', 0.016), (HW, 0.6, 0.3, 'silver', 0.01),
                              (HW + 0.2, 0.14, 0.12, 'line', 0.014)):
        pts = [Vector((RX * (1 - sh) * math.cos(math.radians(a)), RY * (1 - sh) * math.sin(math.radians(a)), z)) for a in range(64, 297, 2)]
        K.strip(pts, w, h, zone, closed=False)
    oz = HT - 1.6
    for k in range(3):
        K.ring_flat((0, 0, oz), 7.4, 0.9, 0.2, 'silver', n=24, a0=k * 120 + 8, a1=k * 120 + 112)
    K.ring_flat((0, 0, oz - 0.2), 6.5, 0.07, 0.07, 'white', n=120)
    K.ring_flat((0, 0, oz - 1.6), 4.6, 0.3, 0.1, 'pale', n=96)
    return oz


def build_core(oz):
    """One clean hovering orb in three floating rings over a low dais; five calm crescent consoles
    hover in an arc between it and the view."""
    c = K.core(CORE, 3.0, rings=3, light=1.4)
    F.lathe([(12.0, 0.0), (11.0, 0.45), (0.01, 0.45)], 96, 'floor2', caps=False)
    K.ring_flat((0, 0, 0.47), 10.6, 0.25, 0.07, 'inlay', n=120)
    K.ring_flat((0, 0, 0.5), 10.1, 0.06, 0.05, 'line', n=120)
    K.ring_flat((0, 0, 0.5), 3.6, 0.5, 0.1, 'silver', n=96)
    K.ring_flat((0, 0, 0.56), 3.6, 0.07, 0.06, 'white', n=96)
    for j in range(5):
        K.swoosh((0, 0), 4.6, 9.4, j * 72, j * 72 + 120, 0.5, 'inlay', 0.5)
        K.swoosh((0, 0), 4.9, 9.1, j * 72 + 14, j * 72 + 110, 0.06, 'line', 0.52)
    A.bolt((0.5, 0.3, oz - 1.6), c + Vector((0.3, 0.2, 3.1)), rnd, width=0.16, jag=0.12, depth=6, branches=3, zone='thin')
    A.bolt((-4.3, 1.5, oz - 1.6), c + Vector((-2.4, 1.2, 4.2)), rnd, width=0.08, jag=0.16, depth=6, branches=2, zone='thin')
    for k in range(5):
        a = math.radians(-64 + 32 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        p = d * 19.0
        m = Matrix.Translation(p + Vector((0, 0, 1.5)) - d * 3.4) @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Rotation(math.radians(-12), 4, 'Y')
        F.xf(F.crescent((0, 0, 0), 3.4, -40, 40, 1.5, 0.2, 'silver', n=18, tip=0.1), m)
        F.xf(F.crescent((0, 0, 0.14), 3.0, -34, 34, 0.1, 0.05, 'line', n=18, tip=0.4), m)
        F.xf(F.crescent((0, 0, 0.14), 3.75, -30, 30, 0.06, 0.05, 'line', n=18, tip=0.4), m)
        K.orb(tuple(p + Vector((0, 0, 2.6))), 0.3, light=0.6)
        K.ring_flat((p.x, p.y, 0.03), 1.8, 0.1, 0.05, 'inlay', n=40)
        F.orb((p.x, p.y, 0.0), 0.9, 'soft', seg=(12, 6), sq=(1, 1, 0.06))
    for r, zone, w in ((14.0, 'line', 0.07), (22.5, 'inlay', 0.35), (23.1, 'line', 0.07)):
        o = K.ring_flat((0, 0, 0.03), 1.0, w / r, 0.05, zone, n=160)
        F.xf(o, Matrix.Diagonal((r * RX / 30.0, r, 1, 1)))
    for j in range(8):
        K.swoosh((0, 0), 14.6, 21.8, j * 45 + 10, j * 45 + 70, 0.5, 'inlay', 0.04, n=36)
        K.swoosh((0, 0), 15.0, 21.4, j * 45 + 18, j * 45 + 64, 0.06, 'line', 0.05, n=36)
    return c


def build_outside():
    """The ship's own bow seen through the aperture (two great horns with a lightning bowstring), the
    fleet and beam streaks. Built last: the fleet builders reset forge's material cache."""
    tips = []
    for s in (-1, 1):
        ctl = [(20, s * 46, -8), (70, s * 54, 1), (130, s * 46, 9), (185, s * 24, 15), (215, s * 7, 18)]
        pts = A.smooth_pts(ctl, 10)
        n = len(pts)
        sect = [(7.0 * (1 - 0.9 * (k / (n - 1)) ** 1.4) + 0.4, 5.0 * (1 - 0.9 * (k / (n - 1)) ** 1.4) + 0.3) for k in range(n)]
        F.sweep([tuple(p) for p in pts], sect, 'shell', sides=10, power=0.8)
        F.sweep([tuple(p + Vector((0, 0, sect[k][1] * 0.98))) for k, p in enumerate(pts)], [(0.25, 0.25)] * n, 'glow', sides=4)
        for k in range(4, n - 6, 5):
            t = (pts[k + 1] - pts[k - 1]).normalized()
            A.blade(pts[k] + Vector((0, 0, sect[k][1] * 0.8)), Vector((0, 0, 1)), -t, 4.0 + sect[k][0] * 1.3, 4.0, 0.5,
                    'pale' if k % 2 else 'bronze', lean=0.6)
        tips.append(pts[-1])
        F.orb(tuple(pts[-1]), 1.6, 'bolt', seg=(12, 8))
        K.point(pts[-1], 3e5, col=(1.0, 0.8, 0.45), r=2.0)
    r2 = random.Random(5)
    A.bolt(tips[0], tips[1], r2, width=0.7, jag=0.18, depth=6, branches=4)
    K.finish()
    with A.gold_palette():
        for (loc, yaw, sc, pitch, roll) in (((240, -120, 62), 150, 6.0, -4, 14), ((310, 150, 75), 212, 6.0, 3, -10), ((560, -330, 150), 165, 7.0, 0, 6), ((620, 420, 130), 225, 7.0, 0, 12)):
            ship, _ = A.arcadian_corvette()
            ship.location = loc
            ship.rotation_euler = (math.radians(roll), math.radians(pitch), math.radians(yaw))
            ship.scale = (sc,) * 3
        ship, _ = A.crescent_mothership_v2()
        ship.location = (900, 60, 300)
        ship.rotation_euler = (math.radians(25), math.radians(-12), math.radians(200))
        ship.scale = (11,) * 3
    K._custom_mats()
    em = bpy.data.materials.new('beam')
    em.use_nodes = True
    b = em.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0, 0, 0, 1)
    b.inputs['Emission Color'].default_value = (1.0, 0.7, 0.22, 1)
    b.inputs['Emission Strength'].default_value = 40.0
    em2 = em.copy()
    em2.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.25, 0.7, 1.0, 1)
    for (p0, p1, wdt, mt) in (((890, 50, 300), (2600, -900, 100), 3.0, em), ((240, -120, 62), (2200, -800, 500), 0.9, em), ((2600, 2200, 500), (700, 520, 120), 1.6, em2),
                              ((3000, 900, 600), (700, 380, 60), 2.0, em2), ((2800, -1500, 100), (1300, -420, 260), 2.2, em2),
                              ((560, -330, 150), (2900, -300, 600), 1.2, em)):
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
    K.unit('carapace', (6.0, -18.5, 0.8), yaw=25)
    K.unit('stinger', (3.0, 19.5, 0.8), yaw=-25)
    build_outside()
    K.ghost('shell', glossy=True)
    K.light_orbs(0.7)
    K.sun((28, 0, 200), 0.25, col=(0.85, 0.9, 1.0), angle=30)
    for k in range(6):
        a = math.radians(60 * k + 30)
        K.point((22 * math.cos(a), 22 * math.sin(a), 6.0), 1500, col=(1.0, 0.92, 0.8), r=1.5)
    K.point((24, 0, 12), 2500, col=(0.75, 0.84, 1.0), r=3.0)
    K.camera((-27.5, -6.0, 4.8), (22, 2.5, 9.2), lens=float(ARGS.get('lens', 19)))
    K.render(OUT, bloom_amt=float(ARGS.get('bloom', 0.75)))


main()
