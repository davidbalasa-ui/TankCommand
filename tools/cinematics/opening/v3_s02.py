"""Scene 2 (0:08-0:16): the Terrans gather.

Three Terran groups climb in from different parts of the planet on blue engine trails and close into one
defensive line facing the Arcadians (gold ships far off at the rift). 0.0-4.6 wide over the planet's curve;
4.6-8.0 close along the line as engines throttle down and the blue shields flicker on, ship after ship.
"""
import math
import random

import bpy
from mathutils import Vector

import v3base as V
from v3base import fr, key_loc, key_rot, show
import space as SP
import arcadian_fleet as AF

BLUE = (0.35, 0.7, 1.0)
HOLD = {
    'dread': Vector((-150, 0, 18)), 'bship': Vector((-135, -70, -4)), 'frigate': Vector((-170, 62, 6)),
    'missile': Vector((-190, 120, -14)), 'corv0': Vector((-120, 34, 30)), 'corv1': Vector((-118, -36, 34)),
    'corv2': Vector((-125, 95, 26)), 'corv3': Vector((-128, -110, 22)),
}
# group start points (out over the planet) and arrival times
GROUPS = [
    (('dread', 'corv1', 'corv3'), Vector((-760, -980, -230)), 0.0, 5.4),
    (('bship', 'frigate', 'corv2'), Vector((-520, 1020, -260)), 0.4, 5.8),
    (('missile', 'corv0'), Vector((-1350, 150, -200)), 0.8, 6.0),
]


def _yaw_to(d):
    return math.degrees(math.atan2(d.y, d.x))


def build(draft=True):
    sc = V.Scene(8.0, draft)
    sc.env()
    o = {}
    o['dread'], _ = V.terran_ship('dread')
    o['bship'], _ = V.terran_ship('bship')
    o['frigate'], _ = V.terran_ship('frigate')
    o['missile'], _ = V.terran_ship('missile')
    cv, _ = V.terran_ship('corvette')
    o['corv0'] = cv
    for i in (1, 2, 3):
        o[f'corv{i}'] = V.copy_tree(cv, f'TCorv{i}')
    bpy.context.view_layer.update()
    rnd = random.Random(3)
    for names, start, t0, t1 in GROUPS:
        for j, k in enumerate(names):
            ob = o[k]
            hold = HOLD[k]
            off = Vector((rnd.uniform(-30, 30), rnd.uniform(-30, 30), rnd.uniform(-15, 15))) * (1 if j else 0)
            p0 = start + off
            mid = p0.lerp(hold, 0.55) + Vector((0, 0, 90))
            a, b = fr(t0 + 0.1 * j), fr(t1 + 0.15 * j)
            key_loc(ob, [(1, p0 - (mid - p0).normalized() * 30), (a, p0), ((a + b) // 2, mid), (b, hold),
                         (sc.nf, hold + Vector((8, 0, 0)))], 'BEZIER')
            y0 = _yaw_to(mid - p0)
            y1 = _yaw_to(hold - mid)
            pitch = -math.degrees(math.atan2((mid - p0).z, (mid - p0).xy.length)) * 0.6
            key_rot(ob, [(1, (0, pitch, y0)), (a, (0, pitch, y0)), ((a + b) // 2, (0, 0, y1)), (b - 6, (0, 0, 2)),
                         (b + 8, (0, 0, 0))])
            V.engines(ob, f'Eng{k}', BLUE, thr_keys=[(1, 1.6), (b - 12, 1.6), (b + 6, 0.35), (sc.nf, 0.3)],
                      len_keys=[(1, 1.6), (b - 12, 1.6), (b + 6, 0.4)])
            # long fading trail behind each ship while it climbs
            tm = V.soft_glow(f'Trail{k}M', BLUE, 1.6, 1.4)
            SP.add_fade(tm, 'vis', 1.0)
            dims = Vector(ob.dimensions)
            tr = V.C.uv_sphere(f'Trail{k}', 1.0, seg=(16, 8), mat=tm, scale=(dims.x * 4, max(dims.y, 6) * 0.08,
                                                                              max(dims.z, 6) * 0.08))
            tr.parent = ob
            tr.location = (-dims.x / ob.scale.x * 2.6, 0, 0)
            tr.visible_shadow = False
            SP.key_node(tm, 'vis', [(1, 1.0), (b - 20, 1.0), (b + 4, 0.0)])
            V.terran_shield(ob, f'TSh{k}', fr(6.0) + {'dread': 0, 'bship': 5, 'frigate': 10, 'missile': 14}.get(k, 18 + j * 3))
    # the gold fleet, far off at the rift, waiting
    with AF.gold_palette():
        cres, _ = AF.crescent_mothership_v2()
        shell, _ = AF.shell_mothership_v2()
        lens, _ = AF.lens_mothership_v2()
    for ob, s, p in ((cres, 2.6, (390, 30, 70)), (shell, 1.4, (300, -70, 10)), (lens, 1.8, (420, 150, 90))):
        ob.scale = (s,) * 3
        ob.location = p
        ob.rotation_euler = (0, 0, math.pi)
    sc.obj = o
    # ---------------------------------------------------------------- shots
    sc.shot('A', 1, fr(4.6) - 1,
            [(1, Vector((-560, -330, 150)), Vector((-300, 60, -60)), 20),
             (fr(2.4), Vector((-540, -300, 130)), Vector((-230, 30, -30)), 21),
             (fr(4.6) - 1, Vector((-520, -270, 110)), Vector((-160, 10, 0)), 22)])
    sc.shot('B', fr(4.6), sc.nf,
            [(fr(4.6), Vector((-95, -190, 34)), Vector((-150, -20, 10)), 24),
             (fr(6.2), Vector((-80, -150, 40)), Vector((-155, 20, 10)), 24),
             (sc.nf, Vector((-70, -110, 44)), Vector((-165, 60, 8)), 24)])
    return sc
