"""Scene 7 (0:42-0:48): exchange of fire. The lines close; gold beams lance out of the crescent and lens,
blue bolts and comets pour back; shields flare, a corvette on each side blows apart. Wide between the
fleets, then low over a Terran ship with the gold beams coming at the camera."""
import random

from mathutils import Vector

import v3base as V
from v3base import fr, key_loc
import space as SP
import v3_battle as B

BLUE = (0.35, 0.7, 1.0)
GOLD = (1.0, 0.6, 0.18)
SHIFT_T, SHIFT_A = Vector((70, 0, 0)), Vector((-60, 0, 0))


def build(draft=True):
    sc = V.Scene(6.0, draft)
    sc.env()
    ships = {'bship', 'frigate', 'missile', 'corv0', 'corv1', 'corv2', 'crescent', 'lens', 'acorv0', 'acorv1',
             'acorv2'}
    R = B.Rig(sc, ships, drift=False)
    nf = sc.nf
    rnd = random.Random(7)
    R.terran_shields(('bship', 'frigate', 'missile'), 1)
    R.gold_shields(('crescent', 'lens'), vis=0.35)
    pos = {}
    for k, ob in R.obj.items():
        terran = k in B.HOLD_T
        p = (B.HOLD_T[k] + SHIFT_T) if terran else (B.HOLD_A[k][0] + SHIFT_A)
        d = Vector((1, 0, 0)) if terran else Vector((-1, 0, 0))
        key_loc(ob, [(1, p), (nf, p + d * 70)], 'LINEAR')
        pos[k] = (p, d * 70 / (nf - 1))
        if k == 'bship':
            V.key_rot(ob, [(1, (0, 0, 90)), (nf, (0, 0, 90))])
        else:
            V.engines(ob, f'Eng{k}', BLUE if terran else GOLD, thr_keys=[(1, 1.2), (nf, 1.2)])

    def at(k, f):
        p, v = pos[k]
        return p + v * (f - 1)
    T = [k for k in R.obj if k in B.HOLD_T]
    A = [k for k in R.obj if k not in B.HOLD_T]
    # gold beams: each burns for ~0.7 s, sweeping a little
    for i in range(7):
        f0 = fr(0.4 + i * 0.75)
        src_k = ('crescent', 'lens', 'acorv0', 'crescent', 'lens', 'acorv1', 'crescent')[i]
        tgt_k = T[i % len(T)]
        src = at(src_k, f0) + Vector((-30 if src_k != 'acorv0' else -8, 0, 0))
        tgt = at(tgt_k, f0 + 6) + Vector((0, rnd.uniform(-4, 4), rnd.uniform(-3, 3)))
        d = (tgt - src).normalized()
        L = (tgt - src).length
        SP.beam(src, d, f'XBeam{i}', GOLD, (1.0, 0.9, 0.6), 1.3 if src_k != 'acorv0' else 0.6,
                [(f0, 0.5, 1.0), (f0 + 3, L, 1.0), (f0 + 16, L, 1.05), (f0 + 18, L, 0.0)], strength=18.0, glow=3.0)
        SP.impact_flare(tgt - d * 4, d, f0 + 3, f0 + 16, (1.0, 0.65, 0.25), 7.0, f'XHit{i}')
        SP.spark_stream(tgt - d * 3, f0 + 3, f0 + 16, (1.0, 0.7, 0.3), -d, 400 + i, n=5, size=0.5, speed=40)
    # blue bolts: volleys from every Terran ship
    for i in range(70):
        f0 = fr(rnd.uniform(0.2, 5.4))
        sk = T[i % len(T)]
        tk = A[rnd.randrange(len(A))]
        src = at(sk, f0) + Vector((rnd.uniform(5, 12), rnd.uniform(-6, 6), rnd.uniform(-3, 4)))
        tgt = at(tk, f0 + 10) + Vector((rnd.uniform(-12, 12), rnd.uniform(-10, 10), rnd.uniform(-6, 6)))
        n_ = max(4, int((tgt - src).length / 260 * 24))
        SP.bolt(src, tgt, f0, n_, BLUE, size=(5.0, 0.28, 0.28), strength=26.0)
        if i % 3 == 0:
            SP.blue_boom(tgt, f0 + n_, rnd.uniform(3, 6), life=0.5)
    # a corvette on each side dies
    for k, t in (('corv2', 3.4), ('acorv2', 4.3)):
        f = fr(t)
        p = at(k, f)
        (SP.blue_boom if k.startswith('c') else SP.gold_boom)(p, f, 14.0, life=1.4, light=4e5)
        SP.boom(p, f + 2, 10.0, life=1.6, follow=Vector((0, 0, 4)), seed=3)
        SP.shards(p, f, 60, (0.4, 0.75, 1.0) if k.startswith('c') else (1.0, 0.7, 0.3), 1.0, 50, seed=f, life=1.8)
        SP.show(R.obj[k], 1, f + 1)
    mid = (at('bship', 1) + at('crescent', 1)) / 2
    sc.shot('A', 1, fr(3.0) - 1,
            [(1, mid + Vector((-20, -330, 60)), mid + Vector((0, 0, 10)), 18),
             (fr(3.0) - 1, mid + Vector((0, -300, 55)), mid + Vector((10, 0, 10)), 19)],
            shake=[(fr(1.0), 0.8, 40)])
    fp = at('frigate', fr(3.0))
    sc.shot('B', fr(3.0), nf,
            [(fr(3.0), fp + Vector((-30, -26, 12)), fp + Vector((200, -40, 30)), 22),
             (nf, at('frigate', nf) + Vector((-26, -24, 11)), at('frigate', nf) + Vector((200, -30, 30)), 22)],
            shake=[(fr(3.4), 3.0, 20), (fr(4.0), 1.5, 30)])
    return sc
