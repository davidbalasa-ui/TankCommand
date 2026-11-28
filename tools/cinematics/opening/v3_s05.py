"""Scene 5 (0:28-0:37): the battleship answers.

Close on the broadside battleship, no enemy in view. It makes ONE deliberate turn (about 22 deg on X and
45 deg on Z, eased, reaction thrusters starting and stopping it) and stops dead. Its shield drops in a wave
bow to stern. The three massive cannons run out, then slowly charge: they were caught off guard, so power
takes time to build: energy crawls up the barrels, light and arcs grow. Then BOOM, BOOM, BOOM: each shot a
heavy blast with recoil, muzzle flash and a shockwave. Last: the shots strike the hooked shell ship.
"""
import math
import random

import bpy
from mathutils import Vector, Matrix

import v3base as V
from v3base import fr, key_loc, key_rot, key_scale, show
import space as SP
import barrage_pieces as BP
import terran_fleet as T
import forge as F
import ships as base
import v3_battle as B

BLUE = (0.35, 0.7, 1.0)
T_TURN0, T_TURN1 = 0.6, 2.8
T_SHDROP = 2.9
T_RUNOUT = 3.3
T_CHARGE0, T_CHARGE1 = 3.8, 6.3
T_SHOTS = (6.3, 6.9, 7.5)
ROT0, ROT1 = (-22, 0, 45), (0, 0, 90)


def split_guns(bs, f_out0, f_out1):
    from terran_fleet import B_GUNS, B_ROOT_Y

    def grp(c):
        if c.y < -(B_ROOT_Y + 0.4) and abs(c.z) < 3.2:
            for n_, gx in enumerate(B_GUNS):
                if abs(c.x - gx) < 2.9:
                    return 1 + n_
        return 0
    parts = SP.split_mesh(bs, grp, names=['BshipHull'] + [f'BshipGun{n_}' for n_ in range(len(B_GUNS))])
    old = bs.data
    bs.data = parts[0].data
    bpy.data.objects.remove(parts[0])
    bpy.data.meshes.remove(old)
    guns = []
    for n_, (g, gx) in enumerate(zip(parts[1:], B_GUNS)):
        root = Vector((gx, -B_ROOT_Y, 0.0))
        g.data.transform(Matrix.Translation(-root))
        g.parent = bs
        g.matrix_parent_inverse.identity()
        g.location = root
        g.rotation_euler = (0, 0, 0)
        g.scale = (1, 1, 1)
        d = 3 * n_
        key_scale(g, [(1, (0.82, 0.33, 0.82)), (f_out0 + d, (0.82, 0.33, 0.82)), (f_out1 - 4 + d, (1.0, 1.06, 1.0)),
                      (f_out1 + d, (1.0, 1.0, 1.0))])
        guns.append((g, root))
    return guns


def build(draft=True):
    sc = V.Scene(9.0, draft)
    sc.env()
    R = B.Rig(sc, {'bship', 'shell'}, drift=False)
    bs, shell = R.obj['bship'], R.obj['shell']
    BP0 = B.HOLD_T['bship']
    key_rot(bs, [(1, ROT0), (fr(T_TURN0), ROT0), (fr(T_TURN1), ROT1), (sc.nf, ROT1)])
    key_loc(bs, [(1, BP0), (sc.nf, BP0 + Vector((2, 0, 0)))], 'LINEAR')
    nf = sc.nf
    rnd = random.Random(5)
    # reaction thrusters: a burst to start the turn, a counter-burst to stop it dead
    tm = V.soft_glow('RCSM', (0.6, 0.85, 1.0), 6.0, 1.5)
    for i, (lp, f0) in enumerate([((22, 10.5, 2), fr(T_TURN0)), ((-22, -10.5, -2), fr(T_TURN0)),
                                  ((22, -10.5, 2), fr(T_TURN1) - 10), ((-22, 10.5, -2), fr(T_TURN1) - 10)]):
        o = V.C.uv_sphere(f'RCS{i}', 1.0, seg=(16, 8), mat=tm, scale=(1.0, 3.5, 1.0))
        o.parent = bs
        o.location = Vector(lp) + Vector((0, 3.0 if lp[1] > 0 else -3.0, 0))
        o.visible_shadow = False
        key_scale(o, [(f0, (0.2, 0.2, 0.2)), (f0 + 2, (1.2, 4.0, 1.2)), (f0 + 10, (0.8, 3.0, 0.8)), (f0 + 14, (0.1, 0.1, 0.1))])
        show(o, f0, f0 + 14)
    V.engines(bs, 'BsEng', BLUE, thr_keys=[(1, 0.5), (nf, 0.5)], len_keys=[(1, 0.6)])
    # its shield: on, then dropped in a wave bow to stern
    R.terran_shields(('bship',), 1)
    bsm = R.tsh['bship'].data.materials[0]
    SP.key_node(bsm, 'hole', [(1, 0.0), (fr(T_SHDROP), 0.0), (fr(T_SHDROP) + 1, 0.08), (fr(T_SHDROP) + 12, 2.2)])
    SP.key_node(bsm, 'vis', [(1, 0.55), (fr(T_SHDROP), 0.55), (fr(T_SHDROP) + 2, 0.9), (fr(T_SHDROP) + 12, 0.0)])
    # cannons run out
    guns = split_guns(bs, fr(T_RUNOUT), fr(T_RUNOUT + 0.5))
    muz = R.muzzles
    # ---------------------------------------------------------------- the slow charge
    base._faction('terran')
    rib_m = SP.emit('ChargeRibM', (0.3, 0.65, 1.0), 3.0)
    f_c0, f_c1 = fr(T_CHARGE0), fr(T_CHARGE1)
    bpy.context.scene.frame_set(f_c0)
    bpy.context.view_layer.update()
    for ci, (g, root) in enumerate(guns):
        mz = muz[ci]
        L = abs(mz.y - root.y)
        # energy crawling from the breech to the muzzle: 6 helix bands appear one after another
        for b in range(6):
            pts = []
            for k in range(40):
                t = k / 39
                a = t * 3 * 2 * math.pi + b * 1.05
                y = root.y - (b / 6 + t / 6) * L
                pts.append((mz.x + 1.9 * math.cos(a), y, mz.z + 1.9 * math.sin(a)))
            r = F.sweep(pts, [(0.035, 0.035)] * 40, 'glow', sides=4)
            ro = base._join([r], f'Charge{ci}_{b}')
            ro.data.materials.clear()
            ro.data.materials.append(rib_m)
            ro.parent = bs
            ro.visible_shadow = False
            fa = f_c0 + int((f_c1 - f_c0) * b / 7) + ci * 3
            show(ro, fa, T_SHOTS[ci] * 24 + 1)
        # blue arcs crawling over the barrel, more and more of them as the charge builds
        for stage in range(3):
            pairs = []
            rr = random.Random(700 + ci * 10 + stage)
            for q in range(3 + stage * 3):
                t = rr.uniform(0.05, 0.95)
                a0 = rr.uniform(0, 2 * math.pi)
                a1 = a0 + rr.uniform(-1.2, 1.2)
                y0 = root.y - t * L
                y1 = y0 - rr.uniform(0.8, 2.6)
                pairs.append((bs.matrix_world @ Vector((mz.x + 2.15 * math.cos(a0), y0, mz.z + 2.15 * math.sin(a0))),
                              bs.matrix_world @ Vector((mz.x + 2.15 * math.cos(a1), y1, mz.z + 2.15 * math.sin(a1)))))
            fa = f_c0 + int((f_c1 - f_c0) * stage / 3) + ci * 2
            arcs = SP.flicker_lightning(pairs, 720 + ci * 10 + stage, fa, fr(T_SHOTS[ci]), every=1, width=0.05,
                                        name=f'BarrelArc{ci}_{stage}', zone_col=(0.35, 0.7, 1.0), strength=5.0)
            mwi = bs.matrix_world.inverted()
            for a in arcs:                    # ride with the ship
                a.parent = bs
                a.matrix_parent_inverse = mwi
        # glow building in the muzzle
        g_ = V.C.uv_sphere(f'MuzGlow{ci}', 1.0, seg=(24, 12), mat=V.soft_glow(f'MuzGlowM{ci}', (0.5, 0.8, 1.0), 2.5, 2.5))
        g_.parent = bs
        g_.location = mz + Vector((0, -1.2, 0))
        g_.visible_shadow = False
        fs = fr(T_SHOTS[ci])
        key_scale(g_, [(f_c0, 0.2), (f_c0 + 30, 0.8), (fs - 8, 1.6), (fs - 1, 2.3), (fs + 1, 0.4), (fs + 6, 0.05)])
        show(g_, f_c0, fs + 6)
    # a hum of light: a point light at the guns rising through the charge
    Lg = bpy.data.objects.new('ChargeLight', bpy.data.lights.new('ChargeLight', 'POINT'))
    V.link(Lg)
    Lg.parent = bs
    Lg.location = (0, -20, 4)
    Lg.data.color = BLUE
    for f, e in [(1, 0), (f_c0, 0), (f_c1, 3e5), (fr(T_SHOTS[2]) + 2, 4e5), (fr(T_SHOTS[2]) + 12, 0)]:
        Lg.data.energy = e
        Lg.data.keyframe_insert('energy', frame=f)
    # ---------------------------------------------------------------- BOOM BOOM BOOM
    sh_cen_l = sum((Vector(v) for v in shell.bound_box), Vector()) / 8
    R.gold_shields(('shell',), vis=0.4)
    sm = R.gsh['shell'].data.materials[0]
    hit_frames = []
    for ci, t in enumerate(T_SHOTS):
        fs = fr(t)
        g, root = guns[ci]
        # recoil: barrel slams back, then eases forward
        g.keyframe_insert('location', frame=fs - 1)
        g.location = root + Vector((0, 2.8, 0))
        g.keyframe_insert('location', frame=fs + 1)
        g.location = root
        g.keyframe_insert('location', frame=fs + 14)
        src = R.world_at(bs, muz[ci], fs)
        fire = (R.world_at(bs, muz[ci] + Vector((0, -1, 0)), fs) - src).normalized()
        cw = R.world_at(shell, sh_cen_l, fs + 30)
        toward = (src - cw).normalized()
        tgt = cw + toward * R.gsh['shell'].scale.x * shell.scale.x * 0.95 + Vector((0, rnd.uniform(-6, 6), rnd.uniform(-5, 5)))
        fh = fs + 30
        cm = BP.comet(f'Comet{ci}', scale=3.4, seed=ci)
        cm.rotation_mode = 'QUATERNION'
        cm.rotation_quaternion = SP.aim_quat(tgt - src)
        key_loc(cm, [(fs, src + fire * 4), (fh, tgt)], 'LINEAR')
        show(cm, fs, fh)
        # its crackling arcs flicker on their own keys: keep them hidden outside the shot's flight
        # (they used to hang at the muzzles through the whole charge as big stray white bolts)
        for a in [c for c in cm.children_recursive if 'Arc' in c.name]:
            for f in list(range(1, fs)) + list(range(fh + 1, nf + 1)):
                a.hide_render = True
                a.keyframe_insert('hide_render', frame=f)
            SP._interp_where(a, 'hide_render', 'CONSTANT')
        fl = T.muzzle_flash(f'MFlash{ci}', scale=3.6, bolt=False)
        fl.location = src
        fl.rotation_mode = 'QUATERNION'
        fl.rotation_quaternion = SP.aim_quat(fire)
        show(fl, fs, fs + 4)
        # shockwave: a flat ring of light racing out from the muzzle
        rm = V.soft_glow(f'ShockM{ci}', (0.7, 0.88, 1.0), 0.8, 4.0)
        SP.add_fade(rm, 'vis', 1.0)
        ring = V.C.uv_sphere(f'Shock{ci}', 1.0, seg=(48, 8), mat=rm, scale=(1, 1, 0.08))
        ring.location = src + fire * 3
        ring.rotation_mode = 'QUATERNION'
        ring.rotation_quaternion = fire.to_track_quat('Z', 'Y')
        ring.visible_shadow = False
        key_scale(ring, [(fs, (1, 1, 0.08)), (fs + 10, (22, 22, 0.6))])
        SP.key_node(rm, 'vis', [(fs, 1.0), (fs + 10, 0.0)])
        show(ring, fs, fs + 10)
        SP.boom(src + fire * 2, fs, 4.0, hot=(0.7, 0.9, 1.0), cool=(0.1, 0.2, 0.4), life=0.6, light=2e5)
        # impact on the shell ship
        SP.blue_boom(tgt, fh, 12.0 + 3 * ci, life=1.0, light=4e5)
        SP.shards(tgt, fh, 40, (1.0, 0.7, 0.3), 1.8, 50, seed=80 + ci, life=1.4, kind='hex')
        hit_frames.append((fh, tgt))
    vk = [(1, 0.4)]
    for fh, _ in hit_frames[:2]:
        vk += [(fh - 1, 0.4), (fh, 1.0), (fh + 4, 0.6)]
    vk += [(hit_frames[2][0] - 1, 0.6), (hit_frames[2][0], 1.2), (hit_frames[2][0] + 1, 0.0)]
    SP.key_node(sm, 'vis', vk)
    fh3, t3 = hit_frames[2]
    SP.gold_boom(R.world_at(shell, sh_cen_l, fh3 + 3), fh3 + 3, 30.0, life=1.6, light=8e5)
    SP.shards(R.world_at(shell, sh_cen_l, fh3), fh3, 120, (1.0, 0.7, 0.3), 1.0, 70, seed=88, life=2.0, kind='hex',
              strength=10.0)
    bpy.context.scene.frame_set(1)
    # ---------------------------------------------------------------- cameras
    Bw = lambda f: R.world_at(bs, (0, 0, 0), f)       # noqa: E731
    mid_mz = lambda f: sum((R.world_at(bs, m, f) for m in muz), Vector()) / 3   # noqa: E731
    # A: close, between the battleship and the enemy, looking back at it: the guns swing round toward us
    sc.shot('A', 1, fr(T_CHARGE0) - 1,
            [(1, Bw(1) + Vector((52, -22, 15)), Bw(1) + Vector((0, 0, 2)), 26),
             (fr(T_TURN1), Bw(fr(T_TURN1)) + Vector((48, -28, 13)), Bw(fr(T_TURN1)) + Vector((4, 0, 0)), 27),
             (fr(T_CHARGE0) - 1, Bw(fr(T_CHARGE0)) + Vector((44, -30, 11)), mid_mz(fr(T_CHARGE0)), 30)],
            shake=[(fr(T_TURN0), 0.4, 10), (fr(T_TURN1) - 10, 0.5, 12)])
    # B: tight on the cannons through the slow charge
    m0 = mid_mz(f_c0)
    sc.shot('B', fr(T_CHARGE0), fr(T_SHOTS[0]) - 1,
            [(fr(T_CHARGE0), m0 + Vector((22, -26, 9)), m0 + Vector((-14, 6, 0)), 32),
             (fr(T_SHOTS[0]) - 1, m0 + Vector((16, -20, 6)), m0 + Vector((-8, 4, 0)), 36)])
    # C: the three shots, wider, beside the guns
    sc.shot('C', fr(T_SHOTS[0]), fr(T_SHOTS[2]) + 5,
            [(fr(T_SHOTS[0]), m0 + Vector((-6, -52, 14)), m0 + Vector((40, 4, 0)), 26),
             (fr(T_SHOTS[2]) + 5, m0 + Vector((-10, -60, 16)), m0 + Vector((60, 4, 0)), 26)],
            shake=[(fr(t), 5.0, 14) for t in T_SHOTS])
    # D: the shots strike the shell ship
    sw = R.world_at(shell, sh_cen_l, hit_frames[0][0])
    sc.shot('D', fr(T_SHOTS[2]) + 6, nf,
            [(fr(T_SHOTS[2]) + 6, sw + Vector((-95, -135, 32)), sw, 24), (nf, sw + Vector((-105, -150, 36)), sw, 24)],
            shake=[(fh3, 3.0, 20)])
    return sc
