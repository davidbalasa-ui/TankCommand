"""Scene 15 (1:48-1:56): the cull.

0.0-1.4  fleet level, low behind a Terran frigate: the two lines still trading fire over Vesper's cloud
         deck. Under the frigate the clouds start to glow violet...
1.4-2.75 ...and a column of the Shard's light rips up through it: skewered, lit violet, it snaps in two in
         a blue blast. Across the gap an Arcadian corvette goes the same way, then a Terran corvette.
2.75-5.0 close on the Arcadian line: the hooked shell mothership is cut in half in front of the camera,
         a corvette, the lens mothership, stingray fighters.
5.0-8.0  the wide: both fleets countable above the clouds, columns rising all over the field. Of ten ships
         a side two are left: the Terran battleship and a corvette, the Arcadian crescent and a corvette.
"""
import random

import bpy
from mathutils import Vector

import v3base as V
from v3base import fr
import space as SP
import fleet_life as FL
import v3_cull as K

BLUE, GOLD = K.BLUE, K.GOLD
F_A1, F_B1 = 66, 120

# (ship, frame of the hit): eight of ten die on each side
KILLS = [('frig1', 34), ('acorv1', 44), ('corv4', 54),
         ('shell', 78), ('acorv2', 90), ('lens', 102),
         ('frig2', 126), ('acorv3', 131), ('corv1', 137), ('acorv5', 142), ('acorv4', 147), ('corv2', 152),
         ('acorv6', 157), ('corv3', 162), ('corv5', 167), ('missile', 172)]


def build(draft=True):
    sc = V.Scene(8.0, draft)
    sc.env()
    nf = sc.nf
    ob = K.build_fleets(nf)
    K.add_engines(ob, nf)
    for n_, (k, o) in enumerate(ob.items()):
        if k != 'bship':
            FL.hull_life(o, 1, nf, seed=40 + n_, roll_deg=2.0, pitch_deg=1.0, rcs=False)
    stings = K.stingrays(10, Vector((175, -45, 45)), Vector((40, 35, 18)), nf, seed=4)
    rnd = random.Random(15)
    scn = bpy.context.scene

    def at(k, f):
        scn.frame_set(f)
        return ob[k].matrix_world.translation.copy()
    dead = dict(KILLS)
    # ---------------------------------------------------------------- the fight before the cull
    T = [k for k in ob if k in K.TERRAN]
    A = [k for k in ob if k in K.ARCAD]
    for i in range(26):
        f = 1 + int(i * 1.5)
        src_k = T[rnd.randrange(len(T))]
        tgt_k = A[rnd.randrange(len(A))]
        if dead.get(src_k, 999) <= f + 2 or dead.get(tgt_k, 999) <= f + 12:
            continue
        src = at(src_k, f) + Vector((8, 0, 2))
        tgt = at(tgt_k, f + 10) + Vector((rnd.uniform(-8, 8), rnd.uniform(-8, 8), rnd.uniform(-4, 4)))
        FL.fire_bolt(src, tgt, f, 'cannon', BLUE, speed=420, seed=i)
    for i in range(10):
        f = 3 + i * 4
        src_k = ['acorv0', 'acorv1', 'acorv5', 'acorv3', 'acorv2'][i % 5]
        tgt_k = T[rnd.randrange(len(T))]
        if dead.get(src_k, 999) <= f + 3 or dead.get(tgt_k, 999) <= f + 3:
            continue
        src = at(src_k, f) + Vector((-10, 0, 1))
        tgt = at(tgt_k, f + 1) + Vector((rnd.uniform(-4, 4), rnd.uniform(-4, 4), rnd.uniform(-2, 2)))
        FL.arc_shot(src, tgt, f, frames=3, seed=i * 13, width=0.45, name='CArc')
    # ---------------------------------------------------------------- the cull
    for i, (k, f) in enumerate(KILLS):
        K.kill(ob[k], f, k in K.TERRAN, nf, key=k, seed=100 + i * 11)
    # stingrays caught by thin columns
    for j, s in enumerate(stings[:8]):
        f = 96 + j * 4 if j < 4 else 140 + j * 5
        p = at_obj(s, f)
        K.column(p.x, p.y, f, p.z, r=2.5, name=f'ColSting{j}', seed=300 + j, hold=8)
        K.break_ship(s, f + 2, False, nf, seed=400 + j, sep=1.5, burn=False)
        SP.gold_boom(p, f + 2, 3.5, life=0.7)
    # ---------------------------------------------------------------- shots
    pA = Vector((-112, -116, 8))
    sc.shot('A', 1, F_A1,
            [(1, pA, Vector((10, -40, -24)), 30),
             (30, pA + Vector((8, 3, 0)), Vector((16, -38, -22)), 30),
             (F_A1, pA + Vector((20, 8, 2)), Vector((30, -34, -16)), 30)],
            shake=[(35, 3.5, 18), (45, 1.0, 10), (55, 2.5, 14)])
    pB = Vector((128, -195, 32))
    sc.shot('B', F_A1 + 1, F_B1,
            [(F_A1 + 1, pB, Vector((215, 60, 18)), 28),
             (F_B1, pB + Vector((-22, 8, 6)), Vector((215, 70, 22)), 28)],
            shake=[(79, 4.0, 20), (91, 1.2, 10), (103, 2.5, 16)])
    pC = Vector((40, -470, 150))
    sc.shot('C', F_B1 + 1, nf,
            [(F_B1 + 1, pC, Vector((40, 10, 0)), 30),
             (nf, pC + Vector((-10, -30, 15)), Vector((40, 10, 5)), 30)],
            shake=[(127, 0.6, 12), (152, 0.5, 10)])
    return sc


def at_obj(o, f):
    bpy.context.scene.frame_set(f)
    return o.matrix_world.translation.copy()
