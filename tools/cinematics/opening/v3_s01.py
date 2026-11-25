"""Scene 1 (0:00-0:08): the Arcadians arrive.

0.0-2.6  dawn: the sun breaks over Vesper's limb; a hard point of light opens into the black portal.
2.6-8.0  close at the portal, rim filling the frame: each ship is pulled out of the portal's depth as a
         long thin streak, snaps to its shape as it clears the rim and sweeps past the camera
         (shake + light wash): the crescent flagship, then the hooked shell ship and the lens ship,
         then corvettes and a flock of stingrays.
"""
import math
import random

import bpy
from mathutils import Vector

import v3base as V
from v3base import fr, key_loc, key_rot, key_scale, show, copy_tree
import space as SP
import portals
import arcadian_fleet as AF

RIFT = SP.RIFT_AT
NRM = Vector((-1, 0, 0.05)).normalized()
S = 260.0                       # portal scale (void radius = 0.5 * S)
T_OPEN = 1.5


def build(draft=True):
    sc = V.Scene(8.0, draft)
    sun = sc.env()
    # ---------------------------------------------------------------- portal
    rf = portals.arcadian_portal()
    rf.location = RIFT
    rf.rotation_mode = 'QUATERNION'
    rf.rotation_quaternion = NRM.to_track_quat('Z', 'Y')
    key_scale(rf, [(1, (0.01, 0.01, 1)), (fr(T_OPEN) - 1, (0.01, 0.01, 1)), (fr(T_OPEN), (S * 0.02, S * 0.02, 1)),
                   (fr(T_OPEN + 0.25), (S * 0.3, S * 0.3, 1)), (fr(T_OPEN + 1.3), (S, S, 1)), (sc.nf, (S, S, 1))])
    show(rf, fr(T_OPEN), sc.nf)
    pt = V.C.uv_sphere('RiftSpark', 1.0, seg=(24, 12), mat=V.soft_glow('RiftSparkM', (0.85, 0.92, 1.0), 14.0, 2.0))
    pt.location = RIFT + NRM * 6
    pt.visible_shadow = False
    key_scale(pt, [(fr(T_OPEN) - 3, 0.5), (fr(T_OPEN), 30.0), (fr(T_OPEN) + 3, 12.0), (fr(T_OPEN + 0.5), 0.5)])
    show(pt, fr(T_OPEN) - 3, fr(T_OPEN + 0.5))
    L = bpy.data.objects.new('RiftLight', bpy.data.lights.new('RiftLight', 'POINT'))
    V.link(L)
    L.location = RIFT + NRM * 120
    L.data.color = (0.75, 0.85, 1.0)
    L.data.shadow_soft_size = 60
    for f, e in [(1, 0), (fr(T_OPEN) - 1, 0), (fr(T_OPEN), 3e7), (fr(T_OPEN + 0.5), 6e6), (fr(T_OPEN + 1.3), 1.2e7)]:
        L.data.energy = e
        L.data.keyframe_insert('energy', frame=f)
    portals.arcadian_arcs(RIFT, NRM, S * 0.5, fr(T_OPEN + 0.6), sc.nf, seed=11, every=7)
    # ---------------------------------------------------------------- shot A: dawn over the limb
    camA = RIFT + Vector((-1500, -1150, 40))
    tgtA = RIFT + Vector((0, 0, -60))
    vd = (tgtA - camA).normalized()
    rt = vd.cross(Vector((0, 0, 1))).normalized()
    upc = rt.cross(vd).normalized()

    def sun_dir(az, el):
        v = vd.copy()
        v.rotate(V.Quaternion(upc, math.radians(-az)))
        v.rotate(V.Quaternion(rt, math.radians(el)))
        return v
    # rises out from behind Vesper's limb, left of the portal
    sun_objs = sc.sun_disc(camA, sun_dir(-17, -9.5), keys=[(1, sun_dir(-17, -9.5)), (fr(1.4), sun_dir(-17.5, -7.0)),
                                                 (fr(2.6), sun_dir(-18, -5.0))])
    for o_ in sun_objs:
        show(o_, 1, fr(2.6) - 1)
    # ---------------------------------------------------------------- ships
    with AF.gold_palette():
        cres, _ = AF.crescent_mothership_v2()
        shell, _ = AF.shell_mothership_v2()
        lens, _ = AF.lens_mothership_v2()
        acv, _ = AF.arcadian_corvette()
        sting, _ = AF.stingray_fighter()
    cres.scale = (2.6,) * 3
    shell.scale = (1.4,) * 3
    lens.scale = (1.8,) * 3
    bpy.context.view_layer.update()
    d = Vector((-1, 0, 0.05)).normalized()
    side = Vector((0, -1, 0))
    camB = RIFT + Vector((-430, -250, -25))

    def arrive(ob, off, t_in, t_out, hold, k=10.0, nm=None):
        key_rot(ob, [(1, (0, 0, 180)), (sc.nf, (0, 0, 180))])
        p_out = RIFT + off - d * 0 + d * 40
        p_in = RIFT + off - d * 260
        sc.stretch_through(ob, d, p_in, p_out, hold, fr(t_in), fr(t_out), fr(t_out + 1.6), k=k, name=nm)
        show(ob, fr(t_in), sc.nf)
    # the flagship: sweeps out, low and right past the camera
    arrive(cres, Vector((0, 0, 0)), 2.7, 3.5, RIFT + Vector((-320, -140, -20)), k=12, nm='Cres')
    # after it settles, it keeps coming: slides past the camera's left shoulder and out of frame
    for f, p in ((fr(6.6), RIFT + Vector((-600, -330, 10))),):
        cres.location = p
        cres.keyframe_insert('location', frame=f)
    arrive(shell, Vector((0, 45, 25)), 5.0, 5.5, RIFT + Vector((-300, 70, 35)), nm='Shell')
    arrive(lens, Vector((0, -50, 45)), 5.5, 6.0, RIFT + Vector((-330, -40, 100)), nm='Lens')
    rnd = random.Random(5)
    for i in range(3):
        a = acv if i == 0 else copy_tree(acv, f'ACorv{i}')
        off = Vector((0, rnd.uniform(-60, 60), rnd.uniform(-40, 40)))
        arrive(a, off, 6.2 + 0.25 * i, 6.55 + 0.25 * i, RIFT + Vector((-360, off.y * 2.5, off.z * 2 - 20)), k=14,
               nm=f'ACorv{i}')
    sting.location = (0, 0, -9999)
    for i in range(18):
        s = copy_tree(sting, f'Sting{i}')
        s.scale = (SP.FIGHTER_K,) * 3
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(15, 100)
        off = Vector((0, math.cos(a) * r, math.sin(a) * r * 0.7))
        t0 = 6.9 + rnd.uniform(0, 0.8)
        key_rot(s, [(1, (0, 0, 180)), (sc.nf, (rnd.uniform(-20, 20), 0, 180 + rnd.uniform(-15, 15)))])
        sc.stretch_through(s, d, RIFT + off - d * 120, RIFT + off + d * 20,
                           RIFT + off * 3 + d * rnd.uniform(300, 420) + side * rnd.uniform(-60, 120),
                           fr(t0), fr(t0 + 0.2), fr(t0 + 1.2), k=16, name=f'Sting{i}', streak_r=1.2)
        show(s, fr(t0), sc.nf)
    sting.hide_render = True
    # light wash as the flagship clears the rim, close to camera
    W = bpy.data.objects.new('WashLight', bpy.data.lights.new('WashLight', 'POINT'))
    V.link(W)
    W.location = RIFT + d * 120 + Vector((0, -80, -20))
    W.data.color = (1.0, 0.8, 0.5)
    W.data.shadow_soft_size = 40
    for f, e in [(1, 0), (fr(3.4), 0), (fr(3.6), 4e7), (fr(4.4), 0), (fr(5.0), 0), (fr(5.15), 1.5e7), (fr(5.6), 0)]:
        W.data.energy = e
        W.data.keyframe_insert('energy', frame=f)
    # ---------------------------------------------------------------- shots
    sc.shot('A', 1, fr(2.6) - 1, [(1, camA, tgtA, 30), (fr(2.6) - 1, camA + Vector((60, 40, 6)), tgtA, 31)],
            shake=[(fr(T_OPEN), 2.0, 14)])
    sc.shot('B', fr(2.6), sc.nf,
            [(fr(2.6), camB, RIFT + Vector((-60, 0, 0)), 20),
             (fr(4.0), camB + Vector((10, 5, 2)), RIFT + Vector((-150, -20, -5)), 20),
             (fr(5.2), camB + Vector((20, 10, 4)), RIFT + Vector((-110, 0, 10)), 20),
             (sc.nf, camB + Vector((40, 20, 8)), RIFT + Vector((-150, 0, 20)), 21)],
            shake=[(fr(3.45), 4.0, 20), (fr(5.4), 8.0, 24), (fr(5.95), 2.5, 14), (fr(6.45), 1.5, 30)])
    return sc
