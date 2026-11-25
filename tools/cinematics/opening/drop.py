"""Shot 8a (0:35-0:38): the drop. Lives in the shared space scene.

0:35    the camera carries on the tilt down from 07d until Vesper fills the frame, then falls in
        behind one drop ship; Terran drop ships and Arcadian seed pods fall side by side, one pod
        level with our ship
0:36    both hit the air: orange fire round the ship, gold-white round the pod, long burning trails;
        the camera shakes
0:37    they punch into the cloud tops (the stitch whites the screen out from 0:36.85)
Fixed seeds, all motion baked on the global clock.
"""
import math
import random

import bpy
from mathutils import Vector, Quaternion

import space as SP
import common as C
import new_pieces as NP
import barrage_pieces as BP
from squid import bake, ramp

fr = SP.fr
FPS = SP.FPS
DS_K = 2.8
POD_K = 2.6
# where 07d leaves the camera (probed from the squid scene, frame 840)
CAM0 = Vector((229.0, 1353.1, 151.0))
LOOK0 = Vector((119.9, 1311.1, -230.1))
T0, T1 = fr(35.0), fr(38.0) - 1
T_FIRE = fr(35.95)
T_CLOUD = fr(36.9)
ORANGE = (1.0, 0.38, 0.06)
GOLDW = (1.0, 0.72, 0.3)
BLUE = (0.3, 0.7, 1.0)


def cloud_mat(name):
    m, n = BP._new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    nz = n.node('ShaderNodeTexNoise', Scale=0.004, Detail=9.0, Roughness=0.62)
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    dens = n.maprange(nz.outputs['Fac'], 0.4, 0.62, 0.0, 1.0)
    d = n.node('ShaderNodeBsdfDiffuse')
    d.inputs['Color'].default_value = (0.95, 0.85, 0.88, 1)
    em = n.node('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.95, 0.8, 0.85, 1)
    em.inputs['Strength'].default_value = 0.35
    add = n.node('ShaderNodeAddShader')
    n.set(add.inputs[0], d.outputs[0])
    n.set(add.inputs[1], em.outputs[0])
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    n.set(mx.inputs[0], dens)
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], add.outputs[0])
    n.set(out.inputs['Surface'], mx.outputs[0])
    return m


def fire_tail(parent, name, L, R, x0, seed, hot=(1.0, 0.78, 0.4), mid=(1.0, 0.32, 0.03),
              cool=(0.22, 0.03, 0.005)):
    """Re-entry wake streaming back (-X, parent-local) from x0: a few ragged strands of plasma,
    white-gold at the hull, orange, then dull red as they tear into wisps. Returns the strands
    (scale z = how far grown, 0..1)."""
    import ships as base
    import forge as F
    rnd = random.Random(seed)
    out = []
    base._faction('terran')
    for j, (lk, rk, ang, sp) in enumerate([(1.0, 1.0, 0, 0), (0.75, 0.8, 6, 70), (0.6, 0.7, 8, 200),
                                            (0.85, 0.6, 5, 300)]):
        Lj = L * lk
        prof = [(0.0, 0.3), (R * rk, 0.0), (R * rk * 1.15, -0.15 * Lj), (R * rk * 0.8, -0.6 * Lj), (0.0, -Lj)]
        tl = base._join([F.lathe(prof, 24, 'glow')], f'{name}Tail{j}')
        tl.rotation_euler = (math.radians(sp), math.radians(90 + ang * math.cos(math.radians(sp))),
                             math.radians(ang * math.sin(math.radians(sp))))
        tl.parent = parent
        tl.location = (x0, 0, 0)
        m, n = BP._new_mat(f'{name}TailM{j}')
        tc = n.node('ShaderNodeTexCoord')
        sep = n.node('ShaderNodeSeparateXYZ')
        n.set(sep.inputs[0], tc.outputs['Object'])
        along = n.maprange(sep.outputs[2], -Lj, 0.0, 0.0, 1.0)
        tt = BP.time_value(m, 'time', 3.0)
        st = n.node('ShaderNodeVectorMath', operation='MULTIPLY')
        n.set(st.inputs[0], tc.outputs['Object'])
        st.inputs[1].default_value = (1.4 / R, 1.4 / R, 0.06 * 18.0 / Lj)
        nz = n.node('ShaderNodeTexNoise', Scale=1.0, Detail=6.0)
        nz.noise_dimensions = '4D'
        n.set(nz.inputs['Vector'], st.outputs[0])
        n.set(nz.inputs['W'], n.math('ADD', tt, seed + j * 1.3))
        thr = n.math('MULTIPLY_ADD', n.math('SUBTRACT', 1.0, along), 0.25, 0.4)
        streak = n.maprange(n.math('SUBTRACT', nz.outputs['Fac'], thr), 0.0, 0.2, 0.0, 1.0)
        lw = n.node('ShaderNodeLayerWeight', Blend=0.4)
        soft = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 2.0)
        sval = n.math('MULTIPLY', n.math('MULTIPLY', n.math('POWER', along, 1.6), streak), soft)
        sval = n.math("MULTIPLY", sval, 2.6 if j == 0 else 1.8)
        ramp_ = n.node('ShaderNodeValToRGB')
        n.set(ramp_.inputs[0], along)
        ramp_.color_ramp.elements[0].color = (*cool, 1)
        ramp_.color_ramp.elements[1].color = (*hot, 1)
        e = ramp_.color_ramp.elements.new(0.6)
        e.color = (*mid, 1)
        BP._add_out(n, sval, ramp_.outputs[0])
        tl.data.materials.clear()
        tl.data.materials.append(m)
        tl.visible_shadow = False
        out.append(tl)
    return out


class Drop:
    def __init__(self, S):
        self.S = S
        S.drop_data = self
        self.rnd = random.Random(3500)
        h0 = CAM0 + Vector((-45, -25, -150))
        self.D = (SP.PLANET_C - h0).normalized()
        D = self.D
        self.e1 = D.cross(Vector((0, 0, 1))).normalized()
        self.e2 = self.e1.cross(D).normalized()
        self.h0 = h0
        import planet as PL
        self.s_cloud = (h0 - SP.PLANET_C).length - (PL.R + PL.CLOUD_H)   # fall distance to the cloud tops
        self.frames = list(range(T0 - 2, T1 + 3))
        self.hero_path = {f: self.fall(h0, f, 1.0) for f in self.frames}
        self.build()

    def fall(self, p0, f, k, lag=0.0):
        t = max(0.0, (f - T0) / FPS + lag)
        s = (70 * t + 118 * t * t) * k
        cap = self.s_cloud + 40.0                      # air braking: they slow inside the cloud deck
        if s > cap - 60:
            x = s - (cap - 60)
            s = cap - 60 + 60 * (1 - math.exp(-x / 60.0))
        return p0 + self.D * s

    def build(self):
        rnd = self.rnd
        D, e1, e2 = self.D, self.e1, self.e2
        q = D.to_track_quat('X', 'Z')
        ship_src = NP.drop_ship('DropSpaceSrc', cargo=True, hot=True)
        pod_src = NP.seed_pod('PodSpaceSrc', hot=True)
        for src in (ship_src, pod_src):
            src.location = (0, 0, -9000)
            for o in [src] + list(src.children_recursive):
                o.hide_render = True
        self.ships = []
        # (kind, lateral e1, lateral e2, lag s, speed k)
        plan = [('ship', 0, 0, 0.0, 1.0), ('pod', 48, -26, 0.0, 1.0),
                ('ship', -70, 25, 0.25, 0.98), ('pod', 95, -30, 0.15, 1.02), ('ship', -150, -40, 0.4, 0.97),
                ('pod', 170, 50, 0.3, 1.0), ('ship', 60, 90, 0.5, 0.99), ('pod', -110, -95, 0.55, 1.01),
                ('ship', 210, -80, 0.65, 0.98), ('pod', -230, 60, 0.7, 1.0), ('ship', -40, -160, 0.8, 1.0),
                ('pod', 130, 170, 0.85, 0.99)]
        for i, (kind, a, b, lag, k) in enumerate(plan):
            src = ship_src if kind == 'ship' else pod_src
            o = SP.copy_tree(src, f'Fall{i}')
            for c in [o] + list(o.children_recursive):
                c.hide_render = False
                c.visible_shadow = False             # their shadows smeared long dark shapes over the clouds
            o.scale = (DS_K if kind == 'ship' else POD_K,) * 3
            p0 = self.h0 + e1 * a + e2 * b - D * 0.0
            locs, quats = [], []
            ph = rnd.uniform(0, 6.3)
            for f in self.frames:
                p = self.fall(p0, f, k, -lag)
                shake = ramp(f, T_FIRE, T_FIRE + 6) * 0.03
                spin = (0.15 * (f - T0) / FPS) if kind == 'pod' else 0.0
                quats.append(q @ Quaternion((1, 0, 0), spin + ph * (kind == 'pod'))
                             @ Quaternion((0, 1, 0), shake * math.sin(f * 2.1 + ph))
                             @ Quaternion((0, 0, 1), shake * math.sin(f * 1.7 + ph * 2)))
                locs.append(p)
            bake(o, self.frames, locs, quats)
            SP.show(o, T0 - 2, T1 + 2)
            # sheath: grows in as they hit the air; burning trail behind
            sh = next((c for c in o.children if c.name.endswith('_Sheath') or '_Sheath' in c.name), None)
            fi = T_FIRE + int(lag * 8) + rnd.randint(0, 3)
            if sh is not None:
                s0 = sh.scale.copy()
                SP.key_scale(sh, [(T0, (s0.x * 0.3, s0.y * 0.3, 0.01)), (fi, (s0.x * 0.3, s0.y * 0.3, 0.01)),
                                  (fi + 8, tuple(s0))], 'BEZIER')
                SP.show(sh, fi, T1 + 2, tree=False)
                for tl in fire_tail(o, o.name, 26.0 if kind == 'ship' else 30.0, 2.8 if kind == 'ship' else 2.2,
                                    sh.location.x - 13.0, 3600 + i,
                                    hot=(1.0, 0.55, 0.18) if kind == "ship" else (1.0, 0.75, 0.35),
                                    mid=ORANGE if kind == 'ship' else (1.0, 0.6, 0.15)):
                    SP.key_scale(tl, [(fi + 1, (1, 1, 0.02)), (fi + 14, (1, 1, 0.6)), (fi + 30, (1, 1, 1))], 'BEZIER')
                    SP.show(tl, fi + 1, T1 + 2, tree=False)
            # fire light on the hull, blue engine dots / gold glow before the fire
            L = bpy.data.objects.new(o.name + '_FireL', bpy.data.lights.new(o.name + '_FireL', 'POINT'))
            SP.link(L)
            L.parent = o
            L.location = (6.0, 0, 0)
            L.data.color = ORANGE if kind == 'ship' else GOLDW
            L.data.shadow_soft_size = 3.0
            for f_, e in [(T0, 0), (fi, 0), (fi + 8, 2.5e4)]:
                L.data.energy = e
                L.data.keyframe_insert('energy', frame=f_)
            if kind == 'ship':
                hm = BP._halo_mat(SP._uid('EngDot'), BLUE, 4.0)
                for (lx, ly) in ((-3.1, 3.2), (-3.1, -3.2), (1.5, 3.2), (1.5, -3.2)):
                    g = C.uv_sphere(SP._uid('EngDot'), 0.32, seg=(12, 6), mat=hm)
                    g.parent = o
                    g.location = (lx - 1.4, ly, 0)
                    g.visible_shadow = False
                    SP.show(g, T0 - 2, T1 + 2)
            self.ships.append(o)
        # the cloud tops are the planet's own cloud shell (planet.py), no stand-in planes

    def camera(self, sid):
        D, e1, e2 = self.D, self.e1, self.e2
        rnd = random.Random(3501)
        keys = []
        H = self.hero_path
        for f in range(T0, T1 + 1):
            t_in = ramp(f, fr(35.0), fr(35.9))
            sm = t_in * t_in * (3 - 2 * t_in)
            # phase 1: carry on 07d's tilt while falling slowly; phase 2: behind our drop ship
            p1 = CAM0 + D * (25 * (f - T0) / FPS)
            l1 = LOOK0.lerp(H[f] + D * 40, ramp(f, fr(35.0), fr(35.6)))
            p2 = H[f] - D * 30 + e2 * 78 + e1 * 50
            l2 = H[f] + D * 10 - e2 * 2
            p = p1.lerp(p2, sm)
            l_ = l1.lerp(l2, sm)
            sk = ramp(f, T_FIRE, T_FIRE + 6) * 0.7
            p = p + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * sk
            roll = rnd.uniform(-1, 1) * 0.02 * (sk / 0.7)
            keys.append((f, p, l_, 24 + 4 * sm, roll))
        return keys
