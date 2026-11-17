"""Scene 16 (1:56-2:04): escape and the final image.

0.0-2.7  the Terran way out: behind the battleship space is torn open (ragged slit, blue-white veins).
         The battleship and its last corvette drive into it; each is dragged out into a long thin streak as
         it crosses, and the wound slams shut behind them.
2.7-5.4  the Arcadian way out: ahead of the crescent a hard point of light opens into the black, precise
         rift. A corvette, then the crescent, slip in, drawn out into gold streaks into the dark; the rift
         closes to a point.
5.4-8.0  held final image: Vesper from high orbit, its night side glowing violet round the Shard, the last
         columns fading, empty space above.
"""
import math
import random

import bpy
from mathutils import Vector

import v3base as V
from v3base import key_loc, key_rot, key_scale, show
import space as SP
import portals
import fleet_life as FL
import v3_cull as K

F_A1, F_B1 = 64, 128
TEAR = Vector((-330.0, -20.0, 40.0))
TEAR_N = Vector((1.0, -0.42, 0.08)).normalized()
RIFT = Vector((560.0, 60.0, 80.0))
RIFT_N = Vector((-1.0, -0.3, 0.02)).normalized()
RS = 230.0                     # rift scale (void radius 0.5 * RS)


def stretch_into(sc, ob, d, plane_p, f_touch, f_gone, k=9.0, col=(0.6, 0.8, 1.0), name='S'):
    """Ship (nose on local +X, already travelling along d) dragged into a portal: from f_touch (nose on the
    portal plane) it is pulled out along d into a long thin streak whose tail slides in after the nose,
    then it is gone. Location keys before f_touch must already exist."""
    d = Vector(d).normalized()
    s0 = Vector(ob.scale)
    bpy.context.view_layer.update()
    xs = [v.co.x for v in ob.data.vertices]
    l = (max(xs) - min(xs)) * s0.x * 0.5
    sq = 1.0 / math.sqrt(k) * 1.2
    f_s = f_touch - 8
    fm = f_touch + max(2, (f_gone - f_touch) // 3)
    # nose / tail along d, measured from the portal plane (negative = still outside)
    nt = [(f_s, -60.0, -(2 * l + 60.0), 1.0), (f_touch, 0.0, -(2 * l + 38.0), 1.0),
          (fm, l * k * 0.8, -2.0 * l, 0.6), (f_gone, l * k * 2.0, 4.0, 1.0)]
    for f, nose, tail, _ in nt:
        sx = (nose - tail) / (2 * l)
        st_ = max(sq, min(1.0, 1.0 / math.sqrt(max(sx, 1.0)) * 1.2))
        ob.location = plane_p + d * ((nose + tail) / 2)
        ob.keyframe_insert('location', frame=f)
        ob.scale = (s0.x * sx, s0.y * st_, s0.z * st_)
        ob.keyframe_insert('scale', frame=f)
    ob.scale = s0
    ob.keyframe_insert('scale', frame=f_s - 1)
    V.C.set_interp(ob, 'BEZIER')
    K._hide_from(ob, f_gone + 1)
    # a light streak running ahead of it into the portal, and a flash on the plane as the tail goes in
    sm = V.soft_glow(f'{name}InStreakM', col, 3.5, 1.6)
    st = V.C.uv_sphere(f'{name}InStreak', 1.0, seg=(24, 10), mat=sm, scale=(l * k * 0.6, l * 0.08, l * 0.08))
    st.rotation_mode = 'QUATERNION'
    st.rotation_quaternion = d.to_track_quat('X', 'Z')
    st.visible_shadow = False
    key_loc(st, [(f_touch, plane_p + d * l * 0.5), (f_gone, plane_p + d * l * k * 0.9)], 'LINEAR')
    key_scale(st, [(f_touch, (l * 0.5, l * 0.05, l * 0.05)), (fm, (l * k * 0.6, l * 0.1, l * 0.1)),
                   (f_gone + 4, (l * k * 0.8, l * 0.02, l * 0.02))], 'LINEAR')
    show(st, f_touch, f_gone + 4)
    Lf = bpy.data.objects.new(f'{name}InL', bpy.data.lights.new(f'{name}InL', 'POINT'))
    V.link(Lf)
    Lf.location = plane_p - d * l * 1.5
    Lf.data.color = col
    Lf.data.shadow_soft_size = l
    for f, e in [(1, 0), (f_gone - 3, 0), (f_gone, 4e6), (f_gone + 8, 0)]:
        Lf.data.energy = e
        Lf.data.keyframe_insert('energy', frame=f)
    SP.lin(Lf.data)


def wrecks(sc, nf, keys, seed=9):
    """Ships the columns broke in scene 15, already in pieces and burning at frame 1."""
    ob = K.build_fleets(nf, which=set(keys))
    for i, k in enumerate(keys):
        K.break_ship(ob[k], 1, k in K.TERRAN, nf, seed=seed + i)
    return ob


def build(draft=True):
    sc = V.Scene(8.0, draft)
    sc.env()
    nf = sc.nf
    scn = bpy.context.scene
    # ================================================================ A: the Terrans tear their way out
    ob = K.build_fleets(nf, which={'bship', 'corv0'})
    bs, cv = ob['bship'], ob['corv0']
    dA = -TEAR_N
    side = TEAR_N.cross(Vector((0, 0, 1))).normalized()
    f_bt, f_bg = 40, 52
    f_ct, f_cg = 30, 39
    p_bs0 = TEAR + TEAR_N * 260 + side * 6 + Vector((0, 0, -6))
    p_cv0 = TEAR + TEAR_N * 200 + side * -40 + Vector((0, 0, 30))
    for o_, p0, ft, off in ((bs, p_bs0, f_bt, side * 6 + Vector((0, 0, -4))),
                            (cv, p_cv0, f_ct, side * -16 + Vector((0, 0, 14)))):
        yaw = math.degrees(math.atan2(dA.y, dA.x))
        pitch = -math.degrees(math.asin(dA.z))
        key_rot(o_, [(1, (0, pitch, yaw)), (nf, (0, pitch, yaw))])
        key_loc(o_, [(1, p0), (ft - 16, TEAR + off - dA * 150)], 'BEZIER')
    K.add_engines(ob, nf, thr=1.8)
    stretch_into(sc, bs, dA, TEAR + side * 6 + Vector((0, 0, -4)), f_bt, f_bg, k=9.0, name='BsIn')
    stretch_into(sc, cv, dA, TEAR + side * -16 + Vector((0, 0, 14)), f_ct, f_cg, k=11.0, name='CvIn')
    portals.terran_tear('Tear', TEAR, TEAR_N, 66.0, 6, f_bg + 5, seed=21)
    SP.boom(TEAR, f_bg + 9, 8.0, hot=(0.7, 0.9, 1.0), cool=(0.1, 0.3, 0.9), life=0.4)
    # behind them: burning halves of their fleet, and the last columns fading
    wrecks(sc, nf, ['frig2', 'corv1'], seed=31)
    K.column(-150, 60, -6, 20, r=6, name='ColLateA', seed=501, hold=14)
    K.column(-40, -110, 4, 10, r=5, name='ColLateB', seed=502, hold=10)
    camA = TEAR + TEAR_N * 340 + side * -60 + Vector((0, 0, 18))
    sc.shot('A', 1, F_A1,
            [(1, camA, TEAR + TEAR_N * 200, 30),
             (26, TEAR + TEAR_N * 215 + side * -72 + Vector((0, 0, 20)), TEAR + TEAR_N * 40, 26),
             (F_A1, TEAR + TEAR_N * 170 + side * -80 + Vector((0, 0, 22)), TEAR + TEAR_N * 5, 26)],
            shake=[(8, 2.0, 10), (14, 3.0, 10), (20, 4.0, 14), (f_bg, 3.0, 12), (f_bg + 6, 5.0, 14)])
    # ================================================================ B: the Arcadians slip into the rift
    ob2 = K.build_fleets(nf, which={'crescent', 'acorv0'})
    cr, ac = ob2['crescent'], ob2['acorv0']
    dB = -RIFT_N
    sideB = RIFT_N.cross(Vector((0, 0, 1))).normalized()
    f_open = 68
    rf = portals.arcadian_portal()
    rf.location = RIFT
    rf.rotation_mode = 'QUATERNION'
    rf.rotation_quaternion = RIFT_N.to_track_quat('Z', 'Y')
    f_shut = 116
    key_scale(rf, [(1, (0.01, 0.01, 1)), (f_open - 1, (0.01, 0.01, 1)), (f_open, (RS * 0.02, RS * 0.02, 1)),
                   (f_open + 5, (RS * 0.3, RS * 0.3, 1)), (f_open + 22, (RS, RS, 1)), (f_shut, (RS, RS, 1)),
                   (f_shut + 4, (RS * 0.4, RS * 0.4, 1)), (f_shut + 7, (RS * 0.02, RS * 0.02, 1))])
    show(rf, f_open, f_shut + 7)
    pt = V.C.uv_sphere('RiftSpark', 1.0, seg=(24, 12), mat=V.soft_glow('RiftSparkM', (0.85, 0.92, 1.0), 14.0, 2.0))
    pt.location = RIFT + RIFT_N * 6
    pt.visible_shadow = False
    key_scale(pt, [(f_open - 3, 0.5), (f_open, 26.0), (f_open + 3, 10.0), (f_open + 10, 0.5),
                   (f_shut + 5, 0.5), (f_shut + 7, 30.0), (f_shut + 11, 0.3)])
    show(pt, f_open - 3, f_shut + 11)
    L = bpy.data.objects.new('RiftLight', bpy.data.lights.new('RiftLight', 'POINT'))
    V.link(L)
    L.location = RIFT + RIFT_N * 120
    L.data.color = (0.75, 0.85, 1.0)
    L.data.shadow_soft_size = 60
    for f, e in [(1, 0), (f_open - 1, 0), (f_open, 3e7), (f_open + 8, 6e6), (f_open + 22, 1.0e7), (f_shut, 1.0e7),
                 (f_shut + 7, 0)]:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=f)
    portals.arcadian_arcs(RIFT, RIFT_N, RS * 0.5, f_open + 10, f_shut, seed=11, every=6)
    f_at, f_ag = 88, 96
    f_rt, f_rg = 100, 111
    yawB = math.degrees(math.atan2(dB.y, dB.x))
    for o_, ft, off, dist in ((ac, f_at, sideB * 40 + Vector((0, 0, 30)), 230), (cr, f_rt, sideB * -10, 300)):
        key_rot(o_, [(1, (0, 0, yawB)), (nf, (0, 0, yawB))])
        key_loc(o_, [(F_A1, RIFT + off + RIFT_N * dist), (ft - 14, RIFT + off + RIFT_N * 200)], 'BEZIER')
    for o_, ft in ((ac, f_at), (cr, f_rt)):     # thrusters cut as the rift takes hold (no smeared bolts)
        V.engines(o_, f'CEngB{o_.name}', K.GOLD, thr_keys=[(1, 1.4), (ft - 8, 1.4), (ft - 2, 0.0)],
                  len_keys=[(1, 0.7), (nf, 0.7)])
    stretch_into(sc, ac, dB, RIFT + sideB * 40 + Vector((0, 0, 30)), f_at, f_ag, k=12.0, col=(1.0, 0.8, 0.45),
                 name='AcIn')
    stretch_into(sc, cr, dB, RIFT + sideB * -10, f_rt, f_rg, k=9.0, col=(1.0, 0.8, 0.45), name='CrIn')
    camB = RIFT + RIFT_N * 330 + sideB * 230 + Vector((0, 0, 40))
    sc.shot('B', F_A1 + 1, F_B1,
            [(F_A1 + 1, camB, RIFT + RIFT_N * 200, 28),
             (96, camB - RIFT_N * 60 + sideB * -20, RIFT + RIFT_N * 90, 28),
             (F_B1, camB - RIFT_N * 90 + sideB * -30, RIFT + RIFT_N * 30, 28)],
            shake=[(f_open, 2.0, 12), (f_rg, 2.5, 14), (f_shut + 7, 1.5, 10)])
    # ================================================================ C: the final image
    shard_dir = Vector((0.3, -0.55, 0.78)).normalized()          # on the night side, seen from above it
    K.planet_glow(shard_dir, [(1, 0.35), (F_B1, 0.45), (F_B1 + 20, 1.0), (nf, 1.1)])
    camC = SP.PLANET_C + Vector((0.3, -0.95, 0.55)).normalized() * 3900
    yc, pc = math.radians(98.7), math.radians(13.5)
    tgtC0 = camC + Vector((math.cos(pc) * math.cos(yc), math.cos(pc) * math.sin(yc), math.sin(pc))) * 1000
    sc.shot('C', F_B1 + 1, nf,
            [(F_B1 + 1, camC, tgtC0, 24),
             (nf, camC + (tgtC0 - camC).normalized() * 120, tgtC0 + Vector((0, 0, 10)), 24)])
    return sc
