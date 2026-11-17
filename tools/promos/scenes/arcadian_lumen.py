"""Lumen (Arcadian light tank): a pack of three Lumens skims in low on gold-lightning lifters,
weaving together like a school of fish. A Lancer guarding the far side of a boulder fires at
the pack; they split around the rock and its shell smashes the stone where they were. They
fan out into a pincer, each pecking at the Lancer with quick, light gold bolts at its own
rhythm, then all three lances fire at once and the bolts converge: the Lancer dies. The pack
streams past the wreck, weaving through each other, and settles into an echelon facing the camera.

0-1.5   low tracking shot: the V formation rushes past camera, revealing the rock and Lancer.
1.5-4.5 reverse angle over the Lancer's shoulder: its shell hits the rock, the pack splits,
        fans out and pecks at it; camera swings round to the south; converging kill at 4.0.
4.5-6   low hero angle: the pack sweeps past the burning wreck and settles in echelon."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from promo_kit import COL, Promo, emit_mat, polyline, show_between, link  # noqa: E402

P = Promo('arcadian_lumen', seconds=6.0, seed=11)
P.env('highland', sun=(55, 0, 60), clear=[(-8, 0, 24), (16, -2, 16)], props=30)
P.flatten(-8, 0, 24)
P.flatten(16, -2, 16)

GOLD = COL['arc_gold']
DEEP_GOLD = (1.0, 0.5, 0.06)
HOVER = 1.0

# ------------------------------------------------------------------ the rock and the Lancer
ROCK = (-2.0, 0.0)
rock = P.load('boulder', at=ROCK, heading=30, size=6.0, label='rock')
rock.root.location.z = -0.3

LANCER = (14.0, 0.0)
lancer = P.load('lancer', at=LANCER, heading=180, label='lancer')
lancer.split_barrels()

# ------------------------------------------------------------------ the pack
# A lead, B left wing (north), C right wing (south). Formation offsets (-3.2, +-2.6).
PATHS = {
    'A': [(0.0, (-27.0, 0.0)), (0.6, (-20.5, 0.9)), (1.2, (-14.0, 0.2)), (1.7, (-8.6, -1.5)),
          (2.1, (-4.0, -4.6)), (2.5, (0.5, -5.6)), (3.0, (5.0, -4.8)), (3.5, (7.5, -3.0)),
          (4.0, (8.5, -1.2)), (4.5, (11.8, -4.2)), (5.2, (16.8, -6.6)), (6.0, (19.1, -8.3))],
    'B': [(0.0, (-30.2, 2.6)), (0.6, (-23.7, 3.5)), (1.2, (-17.2, 2.8)), (1.7, (-11.5, 2.6)),
          (2.1, (-6.5, 4.6)), (2.5, (-1.5, 5.6)), (3.0, (3.5, 6.6)), (3.5, (7.5, 6.8)),
          (4.0, (10.0, 5.8)), (4.5, (14.5, 4.6)), (5.2, (19.2, -0.6)), (6.0, (21.0, -5.0))],
    'C': [(0.0, (-30.2, -2.6)), (0.6, (-23.7, -1.7)), (1.2, (-17.2, -2.4)), (1.7, (-11.8, -4.2)),
          (2.1, (-7.5, -7.5)), (2.5, (-2.5, -9.5)), (3.0, (3.0, -10.0)), (3.5, (7.5, -8.6)),
          (4.0, (11.0, -6.5)), (4.5, (13.8, -8.0)), (5.2, (16.0, -10.4)), (6.0, (17.2, -11.6))],
}
# Last key: all three settle on heading 20, in an echelon that trails away from the camera
pack = {}
for i, k in enumerate('ABC'):
    keys = list(PATHS[k])
    t_end, p_end = keys[-1]
    keys[-1] = (t_end, p_end, 20.0)
    a = P.load('lumen', at=keys[0][1], heading=0, label=f'lumen{k}')
    a.path(keys, z=HOVER)
    a.hover_bob(0.06, 1.1 + 0.13 * i)
    a.split_barrels()
    pack[k] = a
A, B, C = pack['A'], pack['B'], pack['C']

# ---- gold lightning lifters: thin crackling arcs that splay from under the hull to the ground,
# re-drawn every frame (a flickering skirt of lightning, never steady "legs")
bolt_mat = emit_mat('LifterBolt', DEEP_GOLD, 1.8)
glow_mat = emit_mat('LifterGlow', DEEP_GOLD, 0.7, alpha=0.18)
pad_mat = emit_mat('LifterPad', DEEP_GOLD, 1.2, alpha=0.5)
EMIT = [(0.8, 0.45), (0.8, -0.45), (-0.9, 0.5), (-0.9, -0.5)]


def jag(p0, p1, segs, amp, rnd):
    pts = []
    for s in range(segs + 1):
        u = s / segs
        q = p0.lerp(p1, u)
        if 0 < s < segs:
            e = math.sin(math.pi * u)
            q += Vector((rnd.uniform(-amp, amp), rnd.uniform(-amp, amp), rnd.uniform(-amp, amp) * 0.4)) * e
        pts.append(q)
    return pts


def lifters(a, n=3):
    rnd = P.rnd
    for ex, ey in EMIT:
        pad = polyline('LifterPadRing', [Vector((ex - 0.14, ey, 0.06)), Vector((ex + 0.14, ey, 0.06))], 0.05, pad_mat)
        pad.parent = a.model_root
    for f in range(1, P.nf + 2):
        for k in range(n):
            if rnd.random() < 0.2:
                continue
            ex, ey = EMIT[rnd.randrange(4)]
            p0 = Vector((ex + rnd.uniform(-.1, .1), ey + rnd.uniform(-.08, .08), 0.06))
            ang = math.atan2(ey, ex) + rnd.uniform(-0.6, 0.6)
            r = rnd.uniform(0.7, 1.6)
            p1 = Vector((ex + r * math.cos(ang) - rnd.uniform(0.0, 0.5), ey + r * math.sin(ang), -HOVER + 0.03))
            pts = jag(p0, p1, 7, 0.22, rnd)
            objs = [polyline('Lifter', pts, 0.011, bolt_mat), polyline('LifterHalo', pts, 0.035, glow_mat)]
            if rnd.random() < 0.5:   # a little fork
                i = rnd.randint(2, 5)
                q = pts[i] + Vector((rnd.uniform(-.35, .35), rnd.uniform(-.35, .35), rnd.uniform(-.25, 0)))
                objs.append(polyline('LifterFork', jag(pts[i], q, 3, 0.08, rnd), 0.008, bolt_mat))
            for o in objs:
                o.parent = a.model_root
                show_between(o, f, f + 1)
    L = link(bpy.data.objects.new('LiftLight', bpy.data.lights.new('LiftLight', 'POINT')))
    L.parent = a.model_root
    L.location = (0, 0, -0.35)
    L.data.color = GOLD
    L.data.energy = 140
    L.data.shadow_soft_size = 0.8


for a in (A, B, C):
    lifters(a)
    P.dust(a, 0.0, 6.0, every=0.14, size=0.5)

# ------------------------------------------------------------------ the fight
# Lancer: fires at the pack as it reaches the rock -> shell smashes the rock face.
lancer.aim(1.55, (-2.0, -0.5, 1.6), dur=0.5)
lancer.fire(1.65, (-0.3, -0.6, 1.4), kind='cannon')
# Second shot at the north wing, which jinks: it lands behind it.
lancer.aim(2.85, B, dur=0.55)
lancer.fire(2.9, (2.0, 8.6, 0.2), kind='cannon')
lancer.aim(3.85, A, dur=0.6)

# Lumens: light, quick bolts, each at its own rhythm; then one converging volley at 4.0.
SHOTS = {
    'A': [2.40, 2.74, 3.08, 3.42, 3.76],
    'B': [2.55, 2.93, 3.31, 3.69],
    'C': [2.62, 3.04, 3.46],
}
T_KILL = 4.0
for k, a in pack.items():
    for t in SHOTS[k]:
        a.aim(t, lancer, dur=0.22)
        a.fire(t, lancer, kind='lightning', size=0.7, kick=1.5, spread=0.7)
    a.aim(T_KILL, lancer, dur=0.2)
    a.fire(T_KILL, lancer, kind='lightning', size=1.0, kick=2.2)
lancer.destroy(T_KILL + 0.04)
P.cam_shake(T_KILL + 0.04, 0.12)
for k, a in pack.items():
    a.aim(5.0, a.pos_at(6.0) + Vector((14 * math.cos(math.radians(20)), 14 * math.sin(math.radians(20)), 1)), dur=0.7)

# ------------------------------------------------------------------ camera
P.camera([
    # shot 1: low beside the line, formation rushes past, reveal rock + Lancer
    (0.0, (-17.0, -6.0, 1.1), (-26.0, 0.6, 1.4), 36),
    (0.8, (-16.5, -6.2, 1.2), (-19.0, 1.0, 1.4), 32),
    (1.45, (-15.0, -6.5, 1.9), (-5.0, -1.0, 1.4), 28),
    (1.5 - 1 / 24, (-15.0, -6.5, 1.9), (-5.0, -1.0, 1.4), 28),
    # shot 2: over the Lancer's shoulder, swinging south
    (1.5, (27.0, 2.6, 3.4), (-2.0, -0.3, 0.6), 46),
    (2.0, (25.5, 0.6, 3.5), (0.0, -1.0, 0.6), 40),
    (2.6, (22.5, -4.5, 3.6), (4.0, -0.5, 0.6), 32),
    (3.5, (19.5, -9.5, 3.9), (8.0, -0.5, 1.1), 30),
    (4.3, (16.8, -13.2, 4.2), (10.5, 0.0, 1.2), 30),
    (4.5 - 1 / 24, (16.6, -13.4, 4.3), (10.8, 0.0, 1.3), 30),
    # shot 3: low 3/4 hero angle, the pack streams past the wreck and settles in echelon
    (4.5, (31.5, -4.0, 1.3), (15.0, -2.5, 1.5), 30),
    (6.0, (30.6, -6.9, 1.25), (18.6, -7.0, 1.55), 35),
], cuts=(1.5, 4.5), shake=0.03)

# ---- sound cues for effects drawn in this script (promo_audio.py hears the kit calls itself)
P.sfx(0.0, 'crackle_loop', gain=0.3, dur=6.0)         # lifter bolts fizzing under the pack
P.sfx(1.84, 'boom_small', gain=0.55, rate=1.1)        # shell smashes the rock face: stone shatters

P.render()
