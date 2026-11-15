"""Arcadian capital ship: reactor / core chamber (concept still) - the mission objective room.

    /home/user/artenv/venv/bin/python arcadian_reactor.py --out=FILE.jpg [--res=960x540] [--samples=24]

A round chamber 66 m across and 46 m high. The reactor is a great gold core hovering over an open
well inside floating gyroscope rings, cradled by hovering silver petals that touch nothing. Eight
emitter pylons (paired crescent blades) stand on the ring deck where vehicles fight; lightning runs
from the pylons to the core. A crown of blades hangs over it from the dark vault.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arcadian_kit as K  # noqa: E402
from arcadian_kit import F, A  # noqa: E402

ARGS = K.args()
RES = tuple(int(v) for v in ARGS.get('res', '960x540').split('x'))
OUT = ARGS.get('out', '/home/user/work/arcadian-interiors/reactor.jpg')
rnd = random.Random(23)

R, HW, HT = 44.0, 9.0, 50.0
WELL = 12.5
CORE = Vector((0, 0, 15.0))
CR = 6.2


def dome(a_deg, t, shrink=0.0):
    a = math.radians(a_deg)
    k = math.cos(t * math.pi / 2) ** 0.62 - shrink
    return Vector((R * k * math.cos(a), R * k * math.sin(a), HW + (HT - HW) * math.sin(t * math.pi / 2) ** 0.9))


def build_shell():
    F.lathe([(R, 0.0), (R, HW)], 144, 'wall', caps=False)
    F.lathe([(R * math.cos(t * math.pi / 2) ** 0.62 + 0.01, HW + (HT - HW) * math.sin(t * math.pi / 2) ** 0.9) for t in [k / 32 for k in range(33)]],
            144, 'vault', caps=False)


def build_room():
    # ring deck, well lip, the well shaft falling away with glowing rings down it
    F.lathe([(WELL, 0.0), (R, 0.0)], 144, 'floor', caps=False)
    F.lathe([(WELL, 0.0), (WELL - 0.6, -1.2), (WELL - 0.2, -3.0), (WELL - 1.2, -40.0)], 96, 'vault', caps=False)
    F.lathe([(0.01, -40.0), (WELL - 1.2, -40.0)], 48, 'soft', caps=False)
    for z in (-3.5, -8, -14, -22, -31):
        K.ring_flat((0, 0, z), WELL - 0.25 + z * 0.025, 0.14, 0.14, 'line', n=96)
    K.ring_flat((0, 0, 0.15), WELL + 0.35, 0.7, 0.3, 'silver', n=144)
    K.ring_flat((0, 0, 0.34), WELL + 0.0, 0.1, 0.08, 'white', n=144)
    K.ring_flat((0, 0, 0.04), WELL + 3.0, 0.4, 0.06, 'inlay', n=144)
    K.ring_flat((0, 0, 0.04), WELL + 3.6, 0.07, 0.05, 'line', n=144)
    for r, zone, w in ((32.5, 'inlay', 0.4), (33.2, 'line', 0.07), (41.0, 'inlay', 0.4), (41.6, 'line', 0.07)):
        K.ring_flat((0, 0, 0.04), r, w, 0.05, zone, n=160)
    for j in range(12):                                   # great engraved strokes sweeping round the deck
        K.swoosh((0, 0), WELL + 5.0, 31.0, j * 30, j * 30 + 75, 0.7, 'inlay', 0.04, n=40)
        K.swoosh((0, 0), WELL + 5.6, 30.4, j * 30 + 8, j * 30 + 70, 0.07, 'line', 0.05, n=40)
    for z, w, h, zone, sh in ((0.4, 0.45, 0.8, 'bronze', 0.25), (0.62, 0.06, 0.08, 'line', 0.5), (HW, 0.7, 0.35, 'silver', 0.1),
                              (HW + 0.22, 0.16, 0.12, 'line', 0.3)):
        K.ring_flat((0, 0, z), R - sh, w, h, zone, n=144)
    # vault: a few broad arcs floating under the dark shell, sweeping sideways as they rise
    for i in range(10):
        a0 = 36 * i + 8
        sw = 26 if i % 2 else -22
        n = 22
        pts = [dome(a0 + sw * (k / n) ** 1.5, 0.08 + 0.5 * k / n, 0.05) for k in range(n + 1)]
        rad = Vector((math.cos(math.radians(a0)), math.sin(math.radians(a0)), 0))
        K.arc_band(pts, 2.8, 0.25, 'pale' if i % 2 else 'silver', Vector((0, 0, 1)).cross(rad))
        K.orb(tuple(dome(a0 + sw * 1.12, 0.62, 0.06)), 0.5, light=0.7)
    for t in (0.3, 0.66):
        K.strip([dome(a, t, 0.004) for a in range(0, 360, 2)], 0.08, 0.08, 'line')
        K.strip([dome(a, t + 0.012, 0.003) for a in range(0, 360, 2)], 0.45, 0.16, 'bronze')


def build_reactor():
    c = K.core(CORE, CR, rings=3, light=1.0)
    # one hair-thin equatorial line and three broad arcs floating round the core
    K.ring_flat(tuple(c), CR * 2.45, 0.07, 0.07, 'white', n=200)
    for k in range(3):
        K.ring_flat(tuple(c), CR * 2.75, 1.6, 0.3, 'silver', n=30, a0=k * 120 + 10, a1=k * 120 + 100)
        K.ring_flat((c.x, c.y, c.z + 0.2), CR * 2.75, 0.1, 0.08, 'line', n=30, a0=k * 120 + 14, a1=k * 120 + 96)
    # cradle: three broad rings stepping down into the well under the core (they touch nothing)
    for k, (dz, rr) in enumerate(((-8.5, 8.6), (-11.5, 6.6), (-14.5, 4.6))):
        K.ring_flat((0, 0, c.z + dz), rr, 1.1, 0.2, 'pale' if k % 2 == 0 else 'silver', n=96)
        K.ring_flat((0, 0, c.z + dz + 0.14), rr, 0.07, 0.06, 'line', n=96)
    # crown: plain floating rings under the vault with one orb feeding the core from above
    top = HT - 6.0
    for k, rr in enumerate((9.0, 6.6, 4.2)):
        K.ring_flat((0, 0, top - 2.2 * k), rr, 1.0, 0.2, 'silver' if k % 2 == 0 else 'pale', n=96)
        K.ring_flat((0, 0, top - 2.2 * k - 0.14), rr, 0.07, 0.06, 'line', n=96)
    K.orb((0, 0, top - 8.0), 1.3, light=1.0)
    A.bolt((0, 0, top - 9.3), c + Vector((0.6, 0.4, CR * 1.02)), rnd, width=0.3, jag=0.12, depth=6, branches=3, zone='thin')
    # emitters: six broad crescent arcs hovering over the deck (no pylons, nothing touches the floor);
    # an orb rides the inner edge of each and throws lightning to the core
    orbs = []
    for k in range(6):
        a = 60 * k + 30
        d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        zc = 9.5 + 2.0 * (k % 2)
        F.xf(F.crescent((0, 0, 0), 25.0, a - 17, a + 17, 3.6, 0.3, 'pale', n=24, tip=0.08), Matrix.Translation((0, 0, zc)))
        F.xf(F.crescent((0, 0, 0), 23.3, a - 14, a + 14, 0.12, 0.08, 'line', n=24, tip=0.4), Matrix.Translation((0, 0, zc + 0.2)))
        F.xf(F.crescent((0, 0, 0), 27.6, a - 11, a + 11, 1.4, 0.2, 'silver', n=20, tip=0.08), Matrix.Translation((0, 0, zc - 1.5)))
        o = d * 22.4 + Vector((0, 0, zc + 0.2))
        K.orb(tuple(o), 0.9, light=1.0)
        K.ring_flat(tuple(o), 1.5, 0.14, 0.08, 'silver', n=32)
        K.flow_pad((d.x * 25.0, d.y * 25.0), 3.6, style=k)
        orbs.append(o)
    for k, o in enumerate(orbs):
        tgt = c + (o - c).normalized() * CR * (2.4 if k % 2 else 1.5)
        A.bolt(o, tgt, rnd, width=0.22 if k % 2 else 0.3, jag=0.16, depth=6, branches=3, zone='thin')
    return c


def main():
    K.init(samples=int(ARGS.get('samples', 24)), res=RES, env=float(ARGS.get('env', 0.18)), wall_h=HW, warm=(0.72, 0.8, 0.95),
           core_scale=0.2, core_gain=6.0)
    with K.layer('shell'):
        build_shell()
    build_room()
    c = build_reactor()
    K.finish()
    K.ghost('shell', glossy=True)
    K.unit('carapace', (-21.0, -8.5, 0.8), yaw=150)
    K.unit('stinger', (-23.0, 7.5, 0.8), yaw=205)
    K.unit('glider', (-6, -22, 0.9), yaw=120)
    K.light_orbs(0.5)
    K.sun((20, 0, 215), 0.2, col=(0.85, 0.9, 1.0), angle=30)
    K.point((0, 0, -12), 6000, col=(1.0, 0.75, 0.35), r=3.0)
    for k in range(8):
        a = math.radians(45 * k)
        K.point((36 * math.cos(a), 36 * math.sin(a), 6.5), 1800, col=(1.0, 0.93, 0.82), r=1.5)
    K.camera((-42.5, -5.0, 10.5), (0, 0.5, 13.5), lens=float(ARGS.get('lens', 18)))
    K.render(OUT, bloom_amt=float(ARGS.get('bloom', 0.75)))


main()
