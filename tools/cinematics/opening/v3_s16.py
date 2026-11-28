"""Scene 16 (v4): the retreat and the last image. David 2026-11-28: rushed, needs better visuals.

 0.0- 4.6  E  the battleship breaks off: it heaves round (reaction jets), its drives flare and it runs for a
              Terran tear ripping open ahead; a beam erupts right behind it and chases it; it plunges in
              and the tear slams shut.
 4.6- 8.3  F  the burning Crescent swings round for its black portal on lightning thrusters; a beam slices
              one horn clean off; the maimed ship slides into the portal, which irises shut.
 8.3-11.0  G  far and still over Vesper: wreckage tumbling, the last beams thinning back into the clouds,
              the sky empty. Hold.
Own clock.
"""
import math
import random

import bpy
from mathutils import Vector

import v3base as V
from v3base import fr
import v3_battle as B
import space as SP
import common as C
import slicer as SL
import portals
from v3_s15 import bounds

Z = Vector((0, 0, 1))
GOLD = (1.0, 0.72, 0.28)


def hide_from(ob, f):
    for o in [ob] + list(ob.children_recursive):
        o.hide_render = False
        o.keyframe_insert('hide_render', frame=f - 1)
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=f)
        SP._interp_where(o, 'hide_render', 'CONSTANT')


def build(draft=True):
    sc = V.Scene(11.0, draft)
    nf = sc.nf
    sc.env()
    rnd = random.Random(1600)
    R = B.Rig(sc, {'bship', 'crescent', 'acorv0', 'corv0'}, drift=False)
    R.terran_shields(keys=('bship',))
    o = R.obj
    # ---------------------------------------------------------------- E: the battleship runs
    fE1 = fr(4.6)
    bs = o['bship']
    bs.animation_data_clear()
    p0 = Vector(B.HOLD_T['bship'])
    tear_at = p0 + Vector((-150, -95, 30))
    f_turn0, f_turn1, f_in = 6, 40, fE1 - 12
    yaw0 = 0.0
    run = (tear_at - p0)
    yaw1 = math.degrees(math.atan2(run.y, run.x))
    SP.key_rot(bs, [(1, (0, 0, yaw0)), (f_turn0, (0, 0, yaw0)), (f_turn1, (6, -4, yaw1)), (f_in, (0, 0, yaw1))],
               'BEZIER')
    frames = list(range(1, f_in + 9))
    for f in frames:                      # barely moving while it turns, then real acceleration
        t = max(0.0, (f - f_turn1 + 10) / (f_in - f_turn1 + 10))
        k = t ** 2.4
        bs.location = p0 + run * k * 1.08 + Vector((0, 0, 4 * math.sin(math.pi * min(1, f / f_in))))
        bs.keyframe_insert('location', frame=f)
    C.set_interp(bs, 'LINEAR')
    V.engines(bs, 'BsRun', (0.3, 0.6, 1.0), thr_keys=[(1, 0.25), (f_turn1 - 6, 0.3), (f_turn1 + 4, 2.0), (nf, 2.0)],
              len_keys=[(1, 0.3), (f_turn1 - 6, 0.3), (f_turn1 + 4, 1.8)])
    for side, f0 in ((1, f_turn0), (-1, f_turn1 - 8)):          # reaction jets: start the turn, stop it
        for j in range(3):
            SP.boom(p0 + Vector((side * 12, -side * 8, 2 + j * 2)), f0 + j * 2, 1.6, hot=(0.7, 0.9, 1.0),
                    cool=(0.1, 0.3, 0.8), life=0.4, follow=(side * 6, -side * 8, 0))
    root = portals.terran_tear('RunTear', tear_at, (-run).normalized(), 34.0, 10, f_in + 8, seed=21)
    hide_from(bs, f_in + 7)
    SP.boom(tear_at, f_in + 13, 8.0, hot=(0.7, 0.9, 1.0), cool=(0.1, 0.3, 0.9), life=0.5, light=2e6)
    # a beam bursts up just behind it and chases it to the tear
    chase = [(f_turn1 + 2, p0 + run * 0.02)]
    for f in (f_turn1 + 20, f_in - 6, f_in + 6):
        bpy.context.scene.frame_set(f)
        q = bs.location - run.normalized() * 34
        chase.append((f, q))
    SL.column([(f, (q.x, q.y)) for f, q in chase], f_turn1 + 2, f_in + 18, top_z=120, r=3.0)
    camE = p0 + Vector((40, 75, 22))
    sc.shot('E', 1, fE1,
            [(1, camE, p0, 30), (f_turn1, camE + Vector((-8, -4, 2)), p0 + run * 0.1, 30),
             (f_in - 10, camE + Vector((-30, -30, 4)), p0 + run * 0.85, 24),
             (fE1, camE + Vector((-40, -40, 4)), tear_at - Vector((0, 0, 10)), 24)],
            shake=[(f_turn1 + 2, 0.4, 14), (f_in + 8, 0.6, 14)])
    # ---------------------------------------------------------------- F: the Crescent loses a horn
    fF0, fF1 = fE1 + 1, fr(8.3)
    cr = o['crescent']
    cr.animation_data_clear()
    cp, cs = bounds(cr, 1)
    pA = Vector(B.HOLD_A['crescent'][0])
    s = B.HOLD_A['crescent'][1]
    cr.scale = (s,) * 3
    rift = SP.RIFT_AT
    f_c0, f_c1, f_cin = fF0 - 20, fF0 + 40, fF1 - 10
    SP.key_rot(cr, [(1, (0, 0, 180)), (f_c0, (0, 0, 180)), (f_c1, (-8, 3, 360 - 14)), (f_cin, (0, 0, 360))], 'BEZIER')
    for f in range(1, f_cin + 12):
        t = max(0.0, (f - f_c1 + 16) / (f_cin - f_c1 + 16))
        cr.location = pA.lerp(rift + Vector((40, 0, 0)), t ** 2.2)
        cr.keyframe_insert('location', frame=f)
    C.set_interp(cr, 'LINEAR')
    V.lightning_engines(cr, 'CrRun', [(-cs * 0.3 / s, y, 0) for y in (-cs * 0.12 / s, cs * 0.12 / s)],
                        r=cs * 0.025 / s, length=cs * 0.25 / s, thr_keys=[(1, 0.3), (f_c1 - 10, 1.8)], seed=4)
    fm = SP.gas_fireball_mat('CrescentFire', (1.0, 0.5, 0.08), (0.35, 0.03, 0.005))
    C.key_value(fm, 'S', 1, 3.0)
    C.key_value(fm, 'V', 1, 1.0)
    for i in range(4):
        fo = C.uv_sphere(f'CrescentFire{i}', 1.0, seg=(16, 10), mat=fm, scale=(2.2, 2.2, 2.2))
        fo.parent = cr
        fo.location = (rnd.uniform(-8, 8), rnd.uniform(-14, 14), rnd.uniform(0, 3))
        SP.key_rot(fo, [(1, (0, 0, 0)), (nf, (200 + i * 40, 160, 300))], 'LINEAR')
        fo.visible_shadow = False
    rf = portals.arcadian_portal()
    rf.location = rift
    rf.rotation_mode = 'QUATERNION'
    rf.rotation_quaternion = Vector((-1, 0, 0.05)).to_track_quat('Z', 'Y')
    S = 260.0
    SP.key_scale(rf, [(1, (S, S, 1)), (f_cin + 6, (S, S, 1)), (f_cin + 12, (S * 0.5, S * 0.5, 1)),
                      (f_cin + 18, (0.01, 0.01, 1))], 'BEZIER')
    SP.show(rf, 1, f_cin + 18)
    portals.arcadian_arcs(rift, Vector((-1, 0, 0.05)), S * 0.5, 1, f_cin + 12, seed=11, every=7)
    SP.boom(rift, f_cin + 18, 14.0, hot=(0.85, 0.5, 1.0), cool=(0.3, 0.05, 0.4), life=0.5)
    # the horn comes off
    f_cut = fF0 + 30
    bpy.context.scene.frame_set(f_cut)
    bpy.context.view_layer.update()
    loc_pts = [Vector(b) for b in cr.bound_box]
    ymax = max(p.y for p in loc_pts)
    n_l = Vector((0.25, 1, 0)).normalized()
    off_l = Vector((0, ymax * 0.55, 0))
    halves = SL.slice_ship(cr, n_l, f_cut, plane_off_l=off_l, sweep_l=Vector((1, -0.25, 0)).normalized(),
                           f_sweep0=f_cut - 10, sep=cs * 0.15, spin=25.0, end_f=nf, seed=1610, terran=False,
                           follow=True, move=(1.0, 0.0))
    hide_from(halves[1], f_cin + 9)
    pc = cr.matrix_world @ off_l
    sw = cr.matrix_world.to_3x3() @ Vector((1, -0.25, 0))
    sw = Vector((sw.x, sw.y, 0)).normalized()
    SL.column([(f_cut - 12, ((pc - sw * cs * 0.5).x, (pc - sw * cs * 0.5).y)),
               (f_cut + 4, ((pc + sw * cs * 0.4).x, (pc + sw * cs * 0.4).y))], f_cut - 14, f_cut + 22,
              top_z=pc.z + 300, r=5.0)
    SP.flicker_lightning([(pc + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 0.2))) * cs * 0.15,
                           pc + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 0.2))) * cs * 0.3)
                          for _ in range(5)], 1615, f_cut, f_cut + 36, every=1, width=cs * 0.004, name='HornSpill',
                         zone_col=GOLD, strength=6.0)
    camF = pA + Vector((-150, -150, 40))
    sc.shot('F', fF0, fF1,
            [(fF0, camF, pA, 30), (f_cut, camF + Vector((10, 5, 5)), pA + Vector((20, 0, 0)), 30),
             (fF1, camF + Vector((40, -20, 20)), rift, 26)],
            shake=[(f_cut, 1.2, 16)])
    # ---------------------------------------------------------------- G: the last image
    fG0 = fF1 + 1
    for (x, y), f0, f1 in [((40, -40), 1, fG0 + 30), ((180, 70), 1, fG0 + 18), ((-60, 120), fG0 - 20, fG0 + 42)]:
        SL.column([(1, (x, y)), (nf, (x + 4, y))], f0 + 1, f1, top_z=300, r=4.0)
    for k, terran in (('corv0', True), ('acorv0', False)):
        ob = o[k]
        c, size = bounds(ob, fG0)
        SL.slice_ship(ob, Vector((1, 0.3, 0)).normalized(), fG0 - 30, sep=size * 0.4, spin=40.0, end_f=nf,
                      seed=1620 + len(k), terran=terran, boom=False)
    camG = Vector((40, -820, 160))
    sc.shot('G', fG0, nf, [(fG0, camG, Vector((80, 0, 20)), 26), (nf, camG + Vector((0, -30, 40)), Vector((80, 0, 0)), 26)])
    return sc
