"""Scenes 8+9 (0:48-1:07): the fighter run and the Orb.

 0.0- 5.5  chase cam behind two Terran twin-X fighters on an attack run at an Arcadian frigate: their
           bolts hit its gold shield again and again (flares, ripples), then they pull off, up and right.
 5.5- 9.5  the camera pulls back: the Orb streaks in from the side, legs swept back, every thruster
           burning; it flings its legs forward, grabs the first fighter and tears it apart.
 9.5-12.5  it spins its legs round to swing over (thrusters firing sideways), lunges, grabs the second
           fighter and tears it apart.
12.5-16.0  it turns toward a Terran frigate and sprints at it: the frigate lights it up and destroys it.
16.0-19.0  hold on the wreck burning out, the frigate sliding past.
One Blender scene with its own clock (frame 1 = 0:48).
"""
import math
import random

import bpy
from mathutils import Vector, Matrix

import v3base as V
from v3base import fr, key_loc, key_rot, key_scale, show, copy_tree
import space as SP
import arcadian_fleet as AF
import orb_fighter as OF

Z0 = Vector((150.0, 700.0, 80.0))           # a quiet patch above the planet
BLUE = (0.35, 0.7, 1.0)
GOLD = (1.0, 0.62, 0.18)
FK = 4.0                                     # fighters drawn 4x so they read
UP = Vector((0, 0, 1))


def P(x, y, z):
    return Z0 + Vector((x, y, z))


def bake_facing(ob, f0, f1, up=UP, roll_k=0.0, look_ahead=2):
    """Key ob's rotation every frame so its local +X points along its motion (with optional banking)."""
    sc = bpy.context.scene
    pos = {}
    for f in range(f0 - look_ahead, f1 + look_ahead + 2):
        sc.frame_set(f)
        pos[f] = ob.matrix_world.translation.copy()
    prev = None
    ob.rotation_mode = 'QUATERNION'
    for f in range(f0, f1 + 1):
        d = pos[f + look_ahead] - pos[f - look_ahead]
        if d.length < 1e-4:
            q = prev
            if q is None:       # not moving yet: face along the first motion
                fn = next((g for g in range(f, f1 + look_ahead) if (pos[g + 1] - pos[g]).length > 1e-4), None) \
                    if f1 + look_ahead - 1 > f else None
                q = (pos[fn + 1] - pos[fn]).normalized().to_track_quat('X', 'Z') if fn is not None else V.Quaternion()
        else:
            q = d.normalized().to_track_quat('X', 'Z')
            if roll_k:
                d0 = pos[f] - pos[f - look_ahead]
                d1 = pos[f + look_ahead] - pos[f]
                turn = d0.normalized().cross(d1.normalized()).z if d0.length > 1e-4 and d1.length > 1e-4 else 0
                q = q @ V.Quaternion((1, 0, 0), max(-1.2, min(1.2, -turn * roll_k)))
        if prev is not None and q.dot(prev) < 0:
            q = -q
        ob.rotation_quaternion = q
        ob.keyframe_insert('rotation_quaternion', frame=f)
        prev = q
    sc.frame_set(1)


def follow_pos(target_fn, f0, f1, ob):
    """Key ob's location every frame from target_fn(frame) -> world point."""
    sc = bpy.context.scene
    pts = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        pts.append((f, target_fn(f)))
    for f, p in pts:
        ob.location = p
        ob.keyframe_insert('location', frame=f)
    sc.frame_set(1)


def build(draft=True):
    sc = V.Scene(19.0, draft)
    sc.env()
    nf = sc.nf
    rnd = random.Random(8)
    # ---------------------------------------------------------------- Arcadian frigate + shield
    with AF.gold_palette():
        afr, _ = AF.arcadian_corvette()
    afr.scale = (2.2,) * 3
    A_AT = P(300, 0, 0)
    key_loc(afr, [(1, A_AT), (nf, A_AT + Vector((-25, 4, 0)))], 'LINEAR')
    key_rot(afr, [(1, (0, 0, 180)), (nf, (0, 0, 182))])
    bpy.context.view_layer.update()
    import new_pieces as NP
    dx, dy, dz = (v / afr.scale.x for v in afr.dimensions)
    size = (dx * 0.7, dy * 1.2 + 2, dz * 1.4 + 2)
    cen = sum((Vector(b) for b in afr.bound_box), Vector()) / 8
    gsh = NP.shield_dome(size=size, hit=(size[0] * 0.95, 0, 0), name='AFrigShield')
    gsh.scale = size
    gsh.parent = afr
    gsh.location = cen
    gm = gsh.data.materials[0]
    SP.add_fade(gm, 'vis', 0.35)
    shield_r = size[0] * afr.scale.x                  # world radius toward the fighters
    # ---------------------------------------------------------------- the two fighters
    core, wname = V.terran_ship('twinx', 'TwinX')
    core.location = (0, 0, -99999)
    for ob in [core] + list(core.children_recursive):
        ob.hide_render = True
    F = []
    paths = [
        [(1, P(0, -7, 0)), (fr(1.5), P(110, -6, 2)), (fr(4.3), P(235, -5, 3)), (fr(5.2), P(262, 30, 28)),
         (fr(6.4), P(250, 95, 55)), (fr(7.9), P(215, 140, 62))],
        [(1, P(-6, 8, -3)), (fr(1.5), P(104, 7, -1)), (fr(4.4), P(230, 7, 0)), (fr(5.3), P(257, 40, 22)),
         (fr(6.6), P(240, 110, 42)), (fr(8.4), P(200, 160, 48)), (fr(10.4), P(165, 185, 52))],
    ]
    for i, pth in enumerate(paths):
        c = copy_tree(core, f'Fighter{i}')
        c.scale = (FK,) * 3
        for ob in [c] + list(c.children_recursive):
            ob.hide_render = False
        key_loc(c, pth, 'BEZIER')
        wings = [ch for ch in c.children_recursive if ch.name.startswith(wname)]
        for w in wings:
            w.rotation_mode = 'XYZ'
            key_rot(w, [(1, (0, 0, 0)), (nf, (360 * 20, 0, 0))], 'LINEAR')
        V.engines(c, f'FEng{i}', BLUE, n=1, r=0.07, length=0.9, thr_keys=[(1, 1.0), (nf, 1.0)])
        F.append(c)
    # the second fighter keeps flying after the first is taken: extend its path
    # ---------------------------------------------------------------- the Orb (pose objects on one rig)
    rig = bpy.data.objects.new('OrbRig', None)
    V.link(rig)
    orb, legs = OF.orb_rig('Orb')
    orb.parent = rig
    ORB_K = 1.5
    rig.scale = (ORB_K,) * 3
    # timing (seconds)
    T_IN, T_REACH1, T_GRAB1, T_TEAR1 = 5.5, 7.4, 8.0, 8.8
    T_SWING, T_REACH2, T_GRAB2, T_TEAR2 = 9.4, 10.6, 11.0, 11.8
    T_TURN3, T_DASH, T_HIT, T_DIE = 12.6, 13.3, 14.3, 15.2
    # where the fighters are when grabbed
    sc_ = bpy.context.scene

    def at(ob, t):
        sc_.frame_set(fr(t))
        return ob.matrix_world.translation.copy()
    g1 = at(F[0], T_GRAB1)
    g2 = at(F[1], T_GRAB2)
    TF_AT = P(40, 260, 70)                          # the Terran frigate, coming up behind the fighters
    nose = Vector((OF.X0 + 1.2, 0, 0)) * ORB_K      # grab point in front of the core (rig space, scaled)
    rk = [(1, P(150, -260, 10)), (fr(T_IN), P(150, -260, 10)), (fr(T_IN + 1.0), P(200, -90, 30)),
          (fr(T_REACH1), g1 + (g1 - P(200, -90, 30)).normalized() * -9.0), (fr(T_GRAB1), g1 - Vector((nose.length, 0, 0))),
          (fr(T_TEAR1), g1 + Vector((6, 8, 3))),
          (fr(T_SWING), g1 + Vector((-4, 20, 14))), (fr(T_REACH2), g2 + Vector((12, -14, -2))),
          (fr(T_GRAB2), g2 + Vector((4, -6, 0))), (fr(T_TEAR2), g2 + Vector((-6, 4, 2))),
          (fr(T_TURN3), g2 + Vector((-14, 8, 4))), (fr(T_DASH), g2 + Vector((-30, 24, 8))),
          (fr(T_HIT), TF_AT + Vector((95, -60, -12))), (fr(T_DIE), TF_AT + Vector((60, -36, -6)))]
    # dodging the frigate's bolts: three snap jinks across its line of charge, each a different way
    pa, pb = g2 + Vector((-30, 24, 8)), TF_AT + Vector((95, -60, -12))
    lane = (pb - pa).normalized()
    s1_ = lane.cross(Vector((0, 0, 1))).normalized()
    s2_ = s1_.cross(lane).normalized()

    def on_line(t):
        return pa.lerp(pb, (t - T_DASH) / (T_HIT - T_DASH))
    jinks = [(T_HIT - 0.55, s1_ * 8 + s2_ * 3), (T_HIT - 0.33, -s1_ * 5 + s2_ * 7), (T_HIT - 0.12, s1_ * 2 - s2_ * 6)]
    rk = rk[:-2] + [(fr(t), on_line(t) + o) for t, o in jinks] + rk[-2:]
    key_loc(rig, rk, 'BEZIER')
    bake_facing(rig, 1, fr(T_DIE) + 2, look_ahead=2, roll_k=0.9)
    # leg motion: every leg on its own clock (stroke, reach, clutch, swirl), see orb_fighter.animate_orb
    # every leg on its own physics, stroke clock and thruster; two grabs with different legs
    hold = Vector((OF.X0 + 2.4, 0, 0))
    OF.animate_orb(orb, legs, 1, fr(T_DIE) + 31, seed=8, scale=ORB_K, f_die=fr(T_DIE),
                   grabs=[dict(f_reach=fr(T_REACH1) - 4, f_grab=fr(T_GRAB1), f_tear=fr(T_TEAR1), hold=hold,
                               legs=[0, 1, 3, 4, 6]),
                          dict(f_reach=fr(T_REACH2) - 4, f_grab=fr(T_GRAB2), f_tear=fr(T_TEAR2), hold=hold,
                               legs=[1, 2, 5, 6, 7])])
    # ---------------------------------------------------------------- attack run: bolts on the shield
    hits = []
    for k in range(14):
        t = 1.6 + k * 0.2
        i = k % 2
        f0 = fr(t)
        src = at(F[i], t)
        tgt_c = at(afr, t + 0.25)
        toward = (src - tgt_c).normalized()
        hp = tgt_c + toward * shield_r * 0.92 + Vector((0, rnd.uniform(-5, 5), rnd.uniform(-4, 4)))
        n_ = max(3, int((hp - src).length / 140 * 24))
        SP.bolt(src + (hp - src).normalized() * 3, hp, f0, n_, BLUE, size=(3.0, 0.16, 0.16), strength=24.0)
        fh = f0 + n_
        SP.impact_flare(hp, -toward, fh, fh + 5, (1.0, 0.7, 0.3), 5.0, f'ShHit{k}')
        SP.spark_stream(hp, fh, fh + 2, (1.0, 0.75, 0.35), toward, 900 + k, n=6, size=0.5, speed=40, life=0.5)
        hits.append(fh)
    vk = [(1, 0.35)]
    for fh in hits:
        vk += [(fh - 1, 0.4), (fh, 1.0), (fh + 4, 0.5)]
    vk += [(hits[-1] + 12, 0.35)]
    SP.key_node(gm, 'vis', vk)
    # ---------------------------------------------------------------- the kills
    def tear(fi, t_grab, t_tear, seed):
        f = F[fi]
        fg, ft = fr(t_grab), fr(t_tear)
        # held in the Orb's legs, just in front of its core, from grab to tear
        hold_local = Vector((OF.X0 + 2.4, 0, 0))
        follow_pos(lambda fr_: rig.matrix_world @ hold_local, fg, ft, f)
        sc_.frame_set(ft)
        pw = f.matrix_world.translation.copy()
        sc_.frame_set(1)
        # torn apart: the hull halves and wings fly off spinning, burning
        hull_children = list(f.children)
        drift = [Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 1))).normalized() * rnd.uniform(14, 26)
                 for _ in hull_children]
        for ch, d in zip(hull_children, drift):
            mw = ch.matrix_world.copy()
            ch.keyframe_insert('location', frame=ft)
            ch.rotation_mode = 'XYZ'
            ch.keyframe_insert('rotation_euler', frame=ft)
            sc_.frame_set(ft)
            loc0 = ch.location.copy()
            ch.location = loc0 + (f.matrix_world.inverted().to_3x3() @ d)
            ch.keyframe_insert('location', frame=ft + 36)
            ch.rotation_euler = (rnd.uniform(-9, 9), rnd.uniform(-9, 9), rnd.uniform(-9, 9))
            ch.keyframe_insert('rotation_euler', frame=ft + 36)
        f.keyframe_insert('location', frame=ft + 1)
        f.location = pw + (rig.matrix_world.to_3x3() @ Vector((0, 0, 0))) + Vector((0, 0, -4))
        f.keyframe_insert('location', frame=ft + 36)
        SP.blue_boom(pw, ft, 7.0, life=1.0, light=8e4)
        SP.boom(pw + Vector((0, 0, 1)), ft + 2, 5.0, life=1.2, follow=Vector((0, 0, 3)), seed=seed)
        SP.shards(pw, ft, 40, (0.4, 0.75, 1.0), 0.5, 30, seed=seed, life=1.4)
        SP.spark_stream(pw, ft, ft + 6, (1.0, 0.6, 0.25), Vector((0, 0, 0.3)), seed + 1, n=10, size=0.6, speed=45,
                        life=0.9)
        show(f, 1, ft + 36, tree=False)
        # the grab itself: a jolt of light where the harpoons go in
        SP.impact_flare(pw, Vector((1, 0, 0)), fg, fg + 6, (1.0, 0.75, 0.35), 3.0, f'Grab{fi}')
        return pw
    w1 = tear(0, T_GRAB1, T_TEAR1, 41)
    w2 = tear(1, T_GRAB2, T_TEAR2, 52)
    # ---------------------------------------------------------------- the Terran frigate lights it up
    tf, _ = V.terran_ship('frigate')
    tf.scale = (1.3,) * 3
    key_loc(tf, [(1, TF_AT + Vector((-120, 60, 0))), (fr(T_DASH), TF_AT), (nf, TF_AT + Vector((110, -40, 4)))], 'LINEAR')
    sc_.frame_set(fr(T_DASH))
    yaw = math.degrees(math.atan2(-60, 95))
    key_rot(tf, [(1, (0, 0, -20)), (fr(T_DASH), (0, 0, -25)), (fr(T_HIT) - 6, (0, 0, yaw)), (nf, (0, 0, yaw + 6))])
    V.engines(tf, 'TFEng', BLUE, thr_keys=[(1, 0.5), (nf, 0.5)], len_keys=[(1, 0.5)])
    for k in range(12):
        t = T_HIT - 0.55 + k * 0.08
        f0 = fr(t)
        src = at(tf, t) + Vector((rnd.uniform(-4, 4), rnd.uniform(-3, 3), rnd.uniform(0, 3)))
        # aimed where it would be on its straight charge: it jinks out of the way (the late ones connect)
        tgt = (on_line(t + 0.15) if t + 0.15 < T_HIT else at(rig, t + 0.15)) + \
            Vector((rnd.uniform(-2, 2), rnd.uniform(-2, 2), rnd.uniform(-2, 2)))
        n_ = max(3, int((tgt - src).length / 160 * 24))
        SP.bolt(src, tgt, f0, n_, BLUE, size=(4.0, 0.22, 0.22), strength=30.0)
        if k % 2 == 0:
            SP.blue_boom(tgt, f0 + n_, 2.5, life=0.4)
    # its main gun: a lance of blue light
    sc_.frame_set(fr(T_HIT))
    s0 = tf.matrix_world @ Vector((12, 0, 1))
    s1 = rig.matrix_world.translation.copy()
    d = (s1 - s0).normalized()
    SP.beam(s0, d, 'TFLance', BLUE, (0.85, 0.95, 1.0), 1.2,
            [(fr(T_HIT), 0.5, 1.0), (fr(T_HIT) + 3, (s1 - s0).length + 20, 1.0), (fr(T_DIE) - 2, (s1 - s0).length + 20, 1.1),
             (fr(T_DIE) + 2, (s1 - s0).length + 20, 0.0)], strength=20.0, glow=4.0)
    sc_.frame_set(fr(T_DIE))
    pd = rig.matrix_world.translation.copy()
    sc_.frame_set(1)
    SP.impact_flare(pd, -d, fr(T_HIT) + 3, fr(T_DIE), (0.6, 0.8, 1.0), 6.0, 'OrbHit')
    SP.gold_boom(pd, fr(T_DIE), 16.0, life=1.8, light=6e5)
    SP.blue_boom(pd, fr(T_DIE) - 1, 9.0, life=0.6, light=3e5)
    SP.shards(pd, fr(T_DIE), 90, (1.0, 0.7, 0.3), 0.9, 45, seed=77, life=2.2, kind='hex', strength=10.0)
    SP.spark_stream(pd, fr(T_DIE), fr(T_DIE) + 10, (1.0, 0.6, 0.2), Vector((0, 0, 0)), 78, n=14, size=0.8, speed=60,
                    life=1.2)
    # the Orb breaks: core and thrusters die, legs fling out as it swells apart, then it is gone
    for o in orb.children_recursive:
        if 'Plume' in o.name or 'Core' in o.name:
            o.hide_render = False
            o.keyframe_insert('hide_render', frame=1)
            o.hide_render = True
            o.keyframe_insert('hide_render', frame=fr(T_DIE))
            SP._interp_where(o, 'hide_render', 'CONSTANT')
    # v4 (David 2026-11-28: the explosion needed work): the core flashes white-gold, fire races out along
    # every arm in a chain of blasts, gold lightning discharges outward, a shock ring spreads, and the
    # body is consumed: the burning pieces fly apart instead of the old swelling puff
    f_d = fr(T_DIE)
    rig.keyframe_insert('scale', frame=f_d)
    rig.scale = (ORB_K * 1.35, ORB_K * 1.35, ORB_K * 1.35)
    rig.keyframe_insert('scale', frame=f_d + 8)
    for x in [orb] + list(orb.children_recursive):
        x.hide_render = False
        x.keyframe_insert('hide_render', frame=1) if 'Plume' not in x.name and 'Core' not in x.name else None
        x.hide_render = True
        x.keyframe_insert('hide_render', frame=f_d + 9)
        SP._interp_where(x, 'hide_render', 'CONSTANT')
    sc_.frame_set(f_d)
    bpy.context.view_layer.update()
    segs = [o for o in orb.children_recursive if o.type == 'MESH' and 'Plume' not in o.name and 'Core' not in o.name]
    pts = []
    for o in segs:
        bb = [o.matrix_world @ Vector(b) for b in o.bound_box]
        pts.append(sum(bb, Vector()) / 8)
    sc_.frame_set(1)
    rnd_d = random.Random(91)
    reach = max([(q - pd).length for q in pts] + [1.0])
    flash = V.C.uv_sphere('OrbFlash', 1.0, seg=(24, 12), mat=V.soft_glow('OrbFlashM', (1.0, 0.9, 0.65), 18.0, 1.6))
    flash.location = pd
    flash.visible_shadow = False
    key_scale(flash, [(f_d - 1, 0.5), (f_d + 1, reach * 0.5), (f_d + 4, reach * 0.8), (f_d + 9, 0.2)])
    show(flash, f_d - 1, f_d + 9)
    chain = sorted(rnd_d.sample(pts, min(16, len(pts))), key=lambda q: (q - pd).length)
    for i, q in enumerate(chain):
        fq = f_d + 1 + int(8 * (q - pd).length / reach)
        out = (q - pd).normalized() if (q - pd).length > 1e-3 else Vector((0, 0, 1))
        SP.gold_boom(q, fq, rnd_d.uniform(2.5, 4.5), life=1.2, follow=out * rnd_d.uniform(6, 12), seed=200 + i)
    for j in range(8):                     # burning pieces flung outward, trailing fire and smoke
        out = Vector((rnd_d.gauss(0, 1), rnd_d.gauss(0, 1), rnd_d.gauss(0, 0.6))).normalized()
        p1 = pd + out * reach * rnd_d.uniform(1.6, 2.6)
        for k_ in range(5):
            f_ = f_d + 4 + k_ * 6
            q = pd.lerp(p1, (k_ + 1) / 5.5)
            SP.boom(q, f_, 1.6 - k_ * 0.2, life=0.9, seed=300 + j * 7 + k_)
    SP.flicker_lightning([(pd, pd + Vector((rnd_d.gauss(0, 1), rnd_d.gauss(0, 1), rnd_d.gauss(0, 0.7))).normalized()
                           * reach * rnd_d.uniform(1.0, 1.7)) for _ in range(7)], 92, f_d, f_d + 16, every=1,
                         width=0.35, name='OrbDischarge', zone_col=(1.0, 0.75, 0.3), strength=8.0)
    rm = V.soft_glow('OrbShockM', (1.0, 0.8, 0.45), 1.2, 4.0)
    SP.add_fade(rm, 'vis', 1.0)
    ring = V.C.uv_sphere('OrbShock', 1.0, seg=(48, 8), mat=rm, scale=(1, 1, 0.06))
    ring.location = pd
    ring.rotation_euler = (math.radians(70), 0, math.radians(30))
    ring.visible_shadow = False
    key_scale(ring, [(f_d, (1, 1, 0.06)), (f_d + 14, (reach * 3.0, reach * 3.0, 0.4))])
    SP.key_node(rm, 'vis', [(f_d, 1.0), (f_d + 14, 0.0)])
    show(ring, f_d, f_d + 14)
    SP.shards(pd, f_d + 2, 60, (1.0, 0.6, 0.2), 1.6, 38, seed=79, life=3.0, kind='hex', strength=6.0)
    # ---------------------------------------------------------------- cameras
    def cam_follow(ob, t, off, look_off=Vector((0, 0, 0))):
        p = at(ob, t)
        return p + off, p + look_off

    k = []
    for t in (0.0, 1.5, 3.0, 4.3, 5.4):
        mid = (at(F[0], t) + at(F[1], t)) / 2
        k.append((fr(t), mid + Vector((-15, -6, 4.5)), mid + Vector((60, 0, -2)), 26))
    sc.shot('A', 1, fr(5.5) - 1, k, shake=[(hits[0], 0.6, 70)])
    # B: pulled back, side-on; the Orb comes in from the side and takes the first fighter
    c0 = (g1 + P(200, -90, 30)) / 2
    sc.shot('B', fr(5.5), fr(9.4) - 1,
            [(fr(5.5), g1 + Vector((-70, -45, 18)), at(F[0], 5.5) + Vector((0, -30, 0)), 26),
             (fr(6.6), g1 + Vector((-55, -42, 15)), at(rig, 6.6) * 0.5 + at(F[0], 6.6) * 0.5, 28),
             (fr(T_GRAB1), g1 + Vector((-32, -26, 9)), g1, 30),
             (fr(9.4) - 1, g1 + Vector((-28, -24, 8)), at(rig, 9.3), 30)],
            shake=[(fr(T_GRAB1), 1.2, 12), (fr(T_TEAR1), 2.0, 16)])
    # C: close on the Orb as it swings over and takes the second
    sc.shot('C', fr(9.4), fr(12.6) - 1,
            [(fr(9.4), g2 + Vector((-30, -36, 12)), at(rig, 9.4), 28),
             (fr(T_REACH2), g2 + Vector((-24, -28, 9)), g2, 30),
             (fr(12.6) - 1, g2 + Vector((-22, -26, 8)), at(rig, 12.5), 30)],
            shake=[(fr(T_GRAB2), 1.2, 12), (fr(T_TEAR2), 2.0, 16)])
    # D: over the frigate's shoulder as the Orb charges it, and dies
    sc.shot('D', fr(12.6), fr(T_HIT) - 1,
            [(f_, at(rig, f_ / 24.0 - 1 / 24.0) - lane * 34 + s1_ * 20 + s2_ * 8,
              at(rig, f_ / 24.0 - 1 / 24.0) + lane * 18, 28) for f_ in range(fr(12.6), fr(T_HIT), 3)] +
            [(fr(T_HIT) - 1, at(rig, T_HIT - 1 / 24.0) - lane * 34 + s1_ * 20 + s2_ * 8, at(rig, T_HIT) + lane * 18, 28)],
            shake=[(fr(T_HIT - 0.55), 0.8, 20)])
    # D2: over the frigate's shoulder as its lance connects, and the Orb dies
    sc.shot('D2', fr(T_HIT), fr(16.0) - 1,
            [(fr(T_HIT), at(tf, T_HIT) + Vector((-50, 44, 26)), at(rig, T_HIT) * 0.7 + at(tf, T_HIT) * 0.3, 26),
             (fr(16.0) - 1, at(tf, 16.0) + Vector((-55, 48, 28)), pd * 0.7 + at(tf, 16.0) * 0.3, 26)],
            shake=[(fr(T_HIT), 1.5, 14), (fr(T_DIE), 4.0, 24)])
    sc.shot('E', fr(16.0), nf,
            [(fr(16.0), pd + Vector((-70, -60, 20)), pd, 26), (nf, pd + Vector((-80, -75, 24)), at(tf, 18.0) * 0.4 + pd * 0.6, 26)])
    return sc
