"""Scene 6 (0:37-0:42): engines ignite. Two angles: behind the Terran line as every engine lights blue and
the ships surge forward; then the gold fleet's drives flare and it comes on."""
from mathutils import Vector

import v3base as V
from v3base import fr, key_loc
import v3_battle as B

BLUE = (0.35, 0.7, 1.0)
GOLD = (1.0, 0.6, 0.18)
T_IGN_T, T_IGN_A = 0.6, 2.9


def build(draft=True):
    sc = V.Scene(5.0, draft)
    sc.env()
    ships = {'bship', 'frigate', 'missile', 'corv0', 'corv1', 'corv2', 'corv3', 'crescent', 'lens', 'acorv0',
             'acorv1', 'acorv2'}
    R = B.Rig(sc, ships, drift=False)
    nf = sc.nf
    R.terran_shields(('bship', 'frigate', 'missile'), 1)
    R.gold_shields(('crescent', 'lens'), vis=0.3)
    for i, (k, ob) in enumerate(R.obj.items()):
        terran = k in B.HOLD_T
        p = B.HOLD_T[k] if terran else B.HOLD_A[k][0]
        t0 = (T_IGN_T if terran else T_IGN_A) + 0.08 * (i % 5)
        d = Vector((1, 0, 0)) if terran else Vector((-1, 0, 0))
        v = 45.0 if terran else 30.0
        # still, then a surge: distance grows with the square of time after ignition
        keys = [(1, p), (fr(t0), p)]
        for dt in (0.5, 1.0, 1.5, 2.0, 3.0, 4.4):
            if t0 + dt <= 5.2:
                keys.append((fr(t0 + dt), p + d * v * dt * dt * 0.5))
        key_loc(ob, keys, 'BEZIER')
        if k == 'bship':
            V.key_rot(ob, [(1, (0, 0, 90)), (nf, (0, 0, 90))])     # still broadside after its turn
            continue
        # v4 pass 3: the gold drives were a blown-out cream blob filling the frame; keep them to crackling
        # bolts the length of the ship's stern
        lk = 1.0 if terran else 0.55
        V.engines(ob, f'Eng{k}', BLUE if terran else GOLD, hot=(0.85, 0.95, 1.0) if terran else (1.0, 0.9, 0.7),
                  thr_keys=[(1, 0.0), (fr(t0) - 1, 0.0), (fr(t0), 3.0 if terran else 2.0), (fr(t0) + 4, 1.4), (nf, 1.6)],
                  len_keys=[(1, 0.05), (fr(t0) - 1, 0.05), (fr(t0) + 3, 1.6 * lk), (fr(t0) + 10, 1.2 * lk), (nf, 1.4 * lk)])
    dw = R.world_at(R.obj['frigate'], (0, 0, 0), fr(T_IGN_T))
    sc.shot('A', 1, fr(2.6) - 1,
            [(1, Vector((-222, 38, 15)), Vector((-130, 62, 4)), 24),
             (fr(2.6) - 1, Vector((-200, 40, 15)), Vector((-60, 62, 4)), 24)],
            shake=[(fr(T_IGN_T), 1.2, 30)])
    sc.shot('B', fr(2.6), nf,
            [(fr(2.6), Vector((520, -150, 40)), Vector((360, 30, 50)), 24),
             (nf, Vector((500, -140, 38)), Vector((300, 30, 48)), 24)],
            shake=[(fr(T_IGN_A), 1.0, 30)])
    return sc
