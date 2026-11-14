"""Shot 11 (0:55-1:00): made small. Lives in the shared space scene.

0:55    hard cut to a far, still view from orbit: both fleets small against the planet, still
        firing. Half a second in, violet beams burst up through the clouds; the first two strike a
        Terran corvette and an Arcadian corvette
0:56    more beams rise and sweep through both lines; about four in five ships on each side die
0:57    survivors run: on the left a Terran gate snaps open (a flat ring of blue triangles unfolding,
        a calm mirror inside); on the right the Arcadians turn back to their rift
0:58    the camera drifts up. The battleship and a few Terran ships plunge through the gate, the
        burning Crescent leads the rest into the rift; a last beam catches a straggler. The gate
        folds flat to a line and vanishes, the rift curls shut
0:59    empty sky and stars where a logo can go (the stitch fades to black over the last 0.5 s)
Fixed seeds, all motion keyed on the global clock.
"""
import math
import random

import bpy
from mathutils import Vector, Matrix

import space as SP
import common as C
import barrage_pieces as BP

fr = SP.fr
NF = SP.NF
F55 = fr(55.0)
VIO = (0.62, 0.25, 1.0)
VCORE = (0.55, 0.22, 1.0)
BLUE = (0.3, 0.7, 1.0)
GATE_AT = Vector((-290.0, -30.0, 40.0))
GATE_N = Vector((1.0, -0.55, 0.05)).normalized()     # faces the fleet, turned toward the camera
GATE_R = 95.0
T_GATE = fr(57.0)
T_GATE_FOLD = fr(58.15)
T_RIFT_SHUT = fr(58.3)
CAM_P = Vector((150.0, -1150.0, 250.0))
CAM_T = Vector((150.0, 0.0, -10.0))


def _hide_from(ob, f, tree=True):
    """Hidden from frame f on, without disturbing whatever visibility keys came before."""
    sc = bpy.context.scene
    objs = [ob] + (list(ob.children_recursive) if tree else [])
    sc.frame_set(f - 1)
    was = {x.name: x.hide_render for x in objs}
    for x in objs:
        x.hide_render = was[x.name]
        x.keyframe_insert('hide_render', frame=f - 1)
        x.hide_render = True
        x.keyframe_insert('hide_render', frame=f)
        C.set_interp(x, 'CONSTANT')


class Ending:
    def __init__(self, S):
        self.S = S
        self.o = S.obj
        self.rnd = random.Random(5500)
        sc = bpy.context.scene
        sc.frame_set(F55)
        self.p55 = {k: ob.matrix_world.translation.copy() for k, ob in self.o.items()}
        self.beams()
        self.gate()
        self.escape()
        self.rift_shut()
        sc.frame_set(1)

    # ------------------------------------------------------------ the Shard's beams
    def column(self, x, y, f_hit, top_z, seed, sweep=None):
        """A violet beam bursting up through the clouds under (x, y): rises in 3 frames, holds,
        thins out. sweep=(deg0, deg1, f0, f1) swings it round the camera axis."""
        base = Vector((x, y, -260.0))
        L = top_z - base.z + 900.0
        keys = [(f_hit - 3, 1.0, 0.4), (f_hit, L, 1.0), (f_hit + 10, L, 1.0), (f_hit + 16, L, 0.0)]
        if sweep:
            keys = [(sweep[2] - 3, 1.0, 0.4), (sweep[2], L, 1.0), (sweep[3], L, 1.0), (sweep[3] + 6, L, 0.0)]
        b = SP.beam(base, Vector((0, 0, 1)), SP._uid('ShardBeam'), VIO, VCORE, 15.0, keys, strength=5.0, glow=6.0)
        b.data.materials[0] = SP.flow_emit(SP._uid('ShardBeamFlow'), (0.55, 0.2, 1.0), 4.5, scale=0.05, speed=6.0)
        if sweep:
            piv = bpy.data.objects.new(SP._uid('BeamPivot'), None)
            SP.link(piv)
            piv.location = base
            b.parent = piv
            b.location = (0, 0, 0)
            a0, a1, f0, f1 = sweep
            SP.key_rot(piv, [(1, (0, a0, 0)), (f0, (0, a0, 0)), (f1, (0, a1, 0))], 'LINEAR')
        Lt = bpy.data.objects.new(SP._uid('ShardBeamL'), bpy.data.lights.new(SP._uid('ShardBeamL'), 'POINT'))
        SP.link(Lt)
        Lt.location = Vector((x, y, top_z - 30))
        Lt.data.color = VIO
        Lt.data.shadow_soft_size = 40
        f0 = keys[0][0]
        f1 = keys[-1][0]
        for f, e in [(1, 0), (f0, 0), (f0 + 3, 4e6), (f1 - 6, 4e6), (f1, 0)]:
            Lt.data.energy = e
            Lt.data.keyframe_insert('energy', frame=f)
        SP.lin(Lt.data)
        return b

    def kill(self, key, f_hit, terran):
        ob = self.o[key]
        bpy.context.scene.frame_set(f_hit)
        p = ob.matrix_world.translation.copy()
        size = max(ob.dimensions)
        self.column(p.x + self.rnd.uniform(-3, 3), p.y, f_hit, p.z, 5600 + len(key))
        (SP.blue_boom if terran else SP.gold_boom)(p, f_hit + 1, max(30.0, size * 1.2), life=1.4, light=6e6)
        SP.violet_boom(p + Vector((0, 0, size * 0.2)), f_hit + 2, max(18.0, size * 0.6), life=1.0)
        for j in range(3 if size > 40 else 1):           # big ships go up in a chain of blasts
            q = p + Vector((self.rnd.uniform(-0.4, 0.4) * size, self.rnd.uniform(-0.2, 0.2) * size, 0))
            (SP.blue_boom if terran else SP.gold_boom)(q, f_hit + 3 + 3 * j, size * 0.7, life=1.2)
        SP.shards(p, f_hit + 1, 40, BLUE if terran else (1.0, 0.75, 0.3), 2.2 + size * 0.03, 40 + size * 0.4,
                  seed=5700 + len(key) * 7, life=1.8, kind='tri' if terran else 'hex')
        _hide_from(ob, f_hit + 3)

    def beams(self):
        # 0:55.5 the first two, 0:56 more, sweeping through both lines
        self.kill('corvette2', F55 + 12, True)
        self.kill('acorv1', F55 + 12, False)
        plan = [('dread', 25, True), ('lens', 28, False), ('missile_ship', 31, True), ('acorv2', 34, False),
                ('corvette3', 37, True)]
        for key, df, t in plan:
            self.kill(key, F55 + df, t)
        # the shell ship's wreck (torn apart by the barrage) is caught too
        for nm in ('ShellAft', 'ShellMid', 'ShellFore', 'ShellHook', 'ShellChunk'):
            ob = bpy.data.objects.get(nm)
            if ob is None:
                continue
            bpy.context.scene.frame_set(F55 + 30)
            p = ob.matrix_world.translation.copy()
            SP.gold_boom(p, F55 + 31, 34.0, life=1.2)
            _hide_from(ob, F55 + 33)
        self.column(300.0, -60.0, F55 + 30, 40.0, 5650)
        # two beams sweeping across the lines
        self.column(-140.0, 0.0, 0, 30.0, 5660, sweep=(-22.0, 18.0, F55 + 22, F55 + 44))
        self.column(330.0, 60.0, 0, 60.0, 5661, sweep=(20.0, -16.0, F55 + 26, F55 + 46))

    # ------------------------------------------------------------ the Terran gate
    def gate(self):
        """The Terran way out: space torn open by brute force (shared with every Terran exit, portals.py)."""
        import portals
        root = portals.terran_tear('Gate', GATE_AT, GATE_N, GATE_R * 1.3, T_GATE, T_GATE_FOLD, seed=21)
        SP.boom(GATE_AT, T_GATE_FOLD + 5, 6.0, hot=(0.7, 0.9, 1.0), cool=(0.1, 0.3, 0.9), life=0.4)
        self.gate_root = root

    # ------------------------------------------------------------ the survivors run
    def run_to(self, key, target, through, f0, f1, yaw0, yaw1, enter_flash):
        ob = self.o[key]
        sc = bpy.context.scene
        sc.frame_set(f0)
        p0 = ob.matrix_world.translation.copy()
        mid = p0.lerp(target, 0.35) + Vector((0, 0, 12))
        SP.key_loc(ob, [(f0, p0), (f0 + (f1 - f0) // 2, mid), (f1, target), (f1 + 10, through)], 'BEZIER')
        rz = ob.rotation_euler.copy()
        SP.key_rot(ob, [(f0, (math.degrees(rz.x), math.degrees(rz.y), yaw0)),
                        (f0 + 14, (math.degrees(rz.x), math.degrees(rz.y), yaw1)),
                        (NF, (math.degrees(rz.x), math.degrees(rz.y), yaw1))], 'BEZIER')
        _hide_from(ob, f1 + 3)
        enter_flash(target, f1 + 2)

    def escape(self):
        T0 = fr(56.6)
        gate_in = GATE_AT + GATE_N * 5
        gate_out = GATE_AT - GATE_N * 120

        def blue_flash(p, f):
            SP.boom(p, f, 10.0, hot=(0.6, 0.85, 1.0), cool=(0.05, 0.2, 0.8), life=0.4)
        bpy.context.scene.frame_set(T0)
        bz = math.degrees(self.o['bship'].rotation_euler.z)
        self.run_to('bship', gate_in, gate_out, T0, fr(58.0), bz, bz + 180, blue_flash)
        self.run_to('corvette0', gate_in + Vector((0, 0, 14)), gate_out, T0 + 4, fr(57.85), 0, 180, blue_flash)
        # the straggler: turns to run, a last beam catches it
        cv = self.o['corvette1']
        bpy.context.scene.frame_set(T0)
        p0 = cv.matrix_world.translation.copy()
        f_hit = fr(58.05)
        p1 = p0.lerp(gate_in, 0.45)
        SP.key_loc(cv, [(T0 + 6, p0), (f_hit, p1), (NF, p1 + (gate_in - p0).normalized() * 50)], 'BEZIER')
        SP.key_rot(cv, [(T0 + 6, (0, 0, 0)), (T0 + 18, (0, 0, 180))], 'BEZIER')
        self.kill('corvette1', f_hit, True)
        # Arcadians back to the rift: the burning Crescent leads
        rift = SP.RIFT_AT
        r_in = rift + Vector((-25, 0, 0))
        r_out = rift + Vector((140, 0, 0))

        def gold_flash(p, f):
            SP.boom(p, f, 14.0, hot=(1.0, 0.75, 0.35), cool=(0.4, 0.05, 0.4), life=0.5)
        cz = math.degrees(self.o['crescent'].rotation_euler.z)
        self.run_to('crescent', r_in, r_out, T0 - 2, fr(58.15), cz, cz + 180, gold_flash)
        self.run_to('acorv0', r_in + Vector((0, 30, 10)), r_out, T0 + 3, fr(58.0), 180, 360, gold_flash)
        # the Crescent burns: its shield is gone
        fm = SP.gas_fireball_mat('CrescentFire', (1.0, 0.5, 0.08), (0.35, 0.03, 0.005))
        C.key_value(fm, 'S', 1, 3.0)
        C.key_value(fm, 'V', 1, 1.0)
        cres = self.o['crescent']
        for i, lp in enumerate([(4, 10, 2), (-6, -14, 1), (10, 2, -2)]):
            fo = C.uv_sphere(f'CrescentFire{i}', 1.0, seg=(16, 10), mat=fm, scale=(3.0, 3.0, 3.0))
            fo.parent = cres
            fo.location = lp
            SP.key_rot(fo, [(F55, (0, 0, 0)), (NF, (200 + i * 40, 160, 300))], 'LINEAR')
            SP.show(fo, F55, NF)
            fo.visible_shadow = False

    def rift_shut(self):
        rf = self.S.rift
        bpy.context.scene.frame_set(T_RIFT_SHUT)
        s = rf.scale.copy()
        SP.key_scale(rf, [(T_RIFT_SHUT, tuple(s)), (T_RIFT_SHUT + 5, (s.x * 0.5, s.y * 0.15, 1)),
                          (T_RIFT_SHUT + 10, (0.01, 0.01, 1))], 'BEZIER')
        _hide_from(rf, T_RIFT_SHUT + 11)
        L = bpy.data.objects.get('RiftLight')
        if L is not None:
            for f, e in [(T_RIFT_SHUT, 3e7), (T_RIFT_SHUT + 10, 0)]:
                L.data.energy = e
                L.data.keyframe_insert('energy', frame=f)
        SP.boom(SP.RIFT_AT, T_RIFT_SHUT + 10, 20.0, hot=(0.85, 0.5, 1.0), cool=(0.3, 0.05, 0.4), life=0.5)

    # ------------------------------------------------------------ camera
    def camera(self, sid):
        up = CAM_P + Vector((0, 120, 120))
        return [(F55, CAM_P, CAM_T, 38), (fr(57.5), CAM_P, CAM_T, 38),
                (fr(59.0), up, CAM_T + Vector((0, 0, 700)), 38), (NF, up, CAM_T + Vector((0, 0, 700)), 38)]
