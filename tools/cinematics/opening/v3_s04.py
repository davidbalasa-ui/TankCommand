"""Scene 4 (0:19-0:28): the beam hits the Terran flagship. Close and still on the flagship: the gold beam
strikes its blue shield, the shield warbles faster and faster, pops, and peels away; the beam burns through
the hull and out the far side; then a long hold on the burning ship as its lights die and it rolls over."""
from mathutils import Vector

import v3base as V
from v3base import fr
import v3_battle as B

Z = Vector((0, 0, 1))


def build(draft=True):
    sc = V.Scene(9.0, draft)
    sc.env()
    R = B.Rig(sc, {'dread', 'shell', 'corv0', 'corv1'})
    R.beam(1, fr(0.5), fr(3.0), fr(4.0), fr(5.2))
    b = R.beam
    d = b['d']
    perp = d.cross(Z).normalized()
    if perp.y < 0:
        perp = -perp
    en, ex = b['entry_w'], b['exit_w']
    mid = (en + ex) / 2
    cam = en - d * 34 + perp * 44 + Z * 15
    sc.shot('A', 1, sc.nf,
            [(1, cam, b['shield_w'] * 0.6 + mid * 0.4, 28),
             (fr(3.0), cam + perp * 3, mid, 28),
             (fr(5.2), cam + perp * 6 - d * 4, mid, 27),
             (sc.nf, cam + perp * 14 - d * 10 + Z * 4, R.world_at(R.obj['dread'], (0, 0, 0), sc.nf), 26)],
            shake=[(fr(3.0), 2.0, 16), (fr(4.0), 3.0, 20)])
    return sc
