"""Scene 3 (0:16-0:19): the gold ship fires. Close on the hooked shell ship: energy gathers at its hook,
gold lightning crawls along it, and the beam lances out toward the Terran flagship (off frame)."""
from mathutils import Vector

import v3base as V
from v3base import fr
import v3_battle as B

Z = Vector((0, 0, 1))


def build(draft=True):
    sc = V.Scene(3.0, draft)
    sc.env()
    R = B.Rig(sc, {'dread', 'shell', 'crescent', 'lens', 'acorv0', 'acorv1'})
    R.gold_shields(vis=0.12)
    f_beam = fr(2.1)
    R.beam(fr(0.2), f_beam, f_beam + 60, f_beam + 80, f_beam + 100)
    tip = R.world_at(R.obj['shell'], R.shell_tip_local, f_beam)
    d = R.beam['d']
    side = d.cross(Z).normalized()
    if side.y > 0:
        side = -side
    sc.shot('A', 1, sc.nf,
            [(1, tip - d * 95 + side * 120 + Z * 34, tip - d * 40, 24),
             (f_beam - 4, tip - d * 80 + side * 100 + Z * 28, tip - d * 25, 26),
             (sc.nf, tip - d * 70 + side * 92 + Z * 26, tip + d * 20, 26)],
            shake=[(f_beam, 2.5, 18)])
    return sc
