"""Scene 10 (1:07-1:12): pods launch. Close on a mothership's flank, twice: explosive bolts blow the clamps
and the pods blast off its sides one after another, toward the planet. 0-2.5 s the Arcadian crescent sheds
gold seed pods; 2.5-5 s the Terran missile ship kicks out drop ships on blue thrusters."""
import random

import bpy
from mathutils import Vector

import v3base as V
from v3base import fr, key_loc, show
import space as SP
import new_pieces as NP
import v3_battle as B


def launch(ship, src, n, t0, gap, side_sign, col, name, k, out_v, seed):
    """Copies of src clamped along ship's flank (local -Y if side_sign < 0) blast off in turn."""
    rnd = random.Random(seed)
    bb = [Vector(b) for b in ship.bound_box]
    xs = [b.x for b in bb]
    y_edge = min(b.y for b in bb) if side_sign < 0 else max(b.y for b in bb)
    zc = (min(b.z for b in bb) + max(b.z for b in bb)) / 2
    x0, x1 = min(xs) * 0.6, max(xs) * 0.6
    sk = 1.0 / ship.scale.x
    for i in range(n):
        o = SP.copy_tree(src, f'{name}{i}')
        for c in [o] + list(o.children_recursive):
            c.hide_render = False
        o.parent = ship
        o.scale = (k * sk,) * 3
        x = x0 + (x1 - x0) * i / max(1, n - 1)
        p0 = Vector((x, y_edge + side_sign * 1.5, zc - 2 + rnd.uniform(-2, 2)))
        f = fr(t0 + gap * i)
        out = Vector((0, side_sign, -0.6)).normalized()
        key_loc(o, [(1, p0), (f, p0), (f + 4, p0 + out * 3 * sk), (f + 24, p0 + out * out_v * sk),
                    (f + 60, p0 + out * out_v * 3.2 * sk)], 'BEZIER')
        V.key_rot(o, [(1, (0, 0, 0)), (f, (0, 0, 0)), (f + 60, (rnd.uniform(-20, 20), rnd.uniform(-10, 10), 0))])
        # explosive bolts at the clamps: a hard flash and a ring of sparks
        w = lambda p_: ship.matrix_world @ p_   # noqa: E731
        bpy.context.scene.frame_set(f)
        pw = w(p0)
        SP.boom(pw, f, 3.0 * k, hot=(1.0, 0.9, 0.7), cool=(0.4, 0.2, 0.1), life=0.5, light=1e5)
        SP.spark_stream(pw, f, f + 2, (1.0, 0.8, 0.5), ship.matrix_world.to_3x3() @ out, seed + i, n=12, size=0.5,
                        speed=40, life=0.6)
        # its thruster fires once clear
        g = V.C.uv_sphere(f'{name}Jet{i}', 1.0, seg=(16, 8), mat=V.soft_glow(f'{name}JetM', col, 5.0, 1.5),
                          scale=(2.4, 0.6, 0.6))
        g.parent = o
        g.location = (-4.5, 0, 0)
        g.visible_shadow = False
        show(g, f + 6, f + 80)
    bpy.context.scene.frame_set(1)


def build(draft=True):
    sc = V.Scene(5.0, draft)
    sc.env()
    R = B.Rig(sc, {'crescent', 'missile'}, drift=False)
    cres, ms = R.obj['crescent'], R.obj['missile']
    pod = NP.seed_pod('PodSrc', hot=False)
    ds = NP.drop_ship('DropSrc', cargo=True, hot=False)
    for s_ in (pod, ds):
        s_.location = (0, 0, -9000)
        for o in [s_] + list(s_.children_recursive):
            o.hide_render = True
    launch(cres, pod, 6, 0.6, 0.28, 1, (1.0, 0.75, 0.35), 'APod', 2.6, 40, 31)
    launch(ms, ds, 4, 3.0, 0.32, -1, (0.4, 0.75, 1.0), 'TDrop', 2.2, 30, 32)
    fl = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'SUN'))
    V.link(fl)
    fl.data.energy = 1.5
    fl.data.color = (0.7, 0.8, 1.0)
    fl.rotation_euler = (1.2, 0, 0.3)
    cw = B.HOLD_A['crescent'][0]
    mw = B.HOLD_T['missile']
    sc.shot('A', 1, fr(2.5) - 1,
            [(1, cw + Vector((-60, -150, -30)), cw + Vector((0, -40, -10)), 26),
             (fr(2.5) - 1, cw + Vector((-50, -140, -36)), cw + Vector((10, -50, -20)), 26)],
            shake=[(fr(0.6 + 0.28 * i), 1.0, 8) for i in range(6)])
    sc.shot('B', fr(2.5), sc.nf,
            [(fr(2.5), mw + Vector((10, -55, -6)), mw + Vector((0, -8, -4)), 26),
             (sc.nf, mw + Vector((14, -60, -12)), mw + Vector((0, -20, -10)), 26)],
            shake=[(fr(3.0 + 0.32 * i), 1.2, 8) for i in range(4)])
    return sc
