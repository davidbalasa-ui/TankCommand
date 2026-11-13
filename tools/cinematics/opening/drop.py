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
        self.frames = list(range(T0 - 2, T1 + 3))
        self.hero_path = {f: self.fall(h0, f, 1.0) for f in self.frames}
        self.build()

    def fall(self, p0, f, k, lag=0.0):
        t = max(0.0, (f - T0) / FPS + lag)
        s = (70 * t + 118 * t * t) * k
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
        plan = [('ship', 0, 0, 0.0, 1.0), ('pod', 30, 4, 0.0, 1.0),
                ('ship', -70, 25, 0.25, 0.98), ('pod', 95, -30, 0.15, 1.02), ('ship', -150, -40, 0.4, 0.97),
                ('pod', 170, 50, 0.3, 1.0), ('ship', 60, 90, 0.5, 0.99), ('pod', -110, -95, 0.55, 1.01),
                ('ship', 210, -80, 0.65, 0.98), ('pod', -230, 60, 0.7, 1.0), ('ship', -40, -160, 0.8, 1.0),
                ('pod', 130, 170, 0.85, 0.99)]
        for i, (kind, a, b, lag, k) in enumerate(plan):
            src = ship_src if kind == 'ship' else pod_src
            o = SP.copy_tree(src, f'Fall{i}')
            for c in [o] + list(o.children_recursive):
                c.hide_render = False
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
                tr = bpy.data.objects.new(o.name + '_Trail', sh.data)
                SP.link(tr)
                tr.parent = o
                tr.location = sh.location - Vector((2.0, 0, 0))
                tr.rotation_euler = sh.rotation_euler
                tl = 14.0 if kind == 'ship' else 18.0
                SP.key_scale(tr, [(fi + 2, (0.6, 0.55, 0.01)), (fi + 10, (0.85, 0.8, tl * 0.5)), (fi + 24, (0.9, 0.85, tl))],
                             'BEZIER')
                tr.data.materials[0]  # same sheath material (hot nose -> red open end)
                tr.visible_shadow = False
                SP.show(tr, fi + 2, T1 + 2, tree=False)
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
                    g = C.uv_sphere(SP._uid('EngDot'), 0.9, seg=(12, 6), mat=hm)
                    g.parent = o
                    g.location = (lx - 1.4, ly, 0)
                    g.visible_shadow = False
                    SP.show(g, T0 - 2, T1 + 2)
            self.ships.append(o)
        # cloud tops: two decks across the fall line; the hero ship punches through at ~0:36.9
        hc = self.hero_path[T_CLOUD]
        cm = cloud_mat('DropCloudM')
        for j, ds in enumerate((6.0, 40.0, 90.0)):
            bpy.ops.mesh.primitive_plane_add(size=1)
            pl = bpy.context.active_object
            pl.name = f'DropCloud{j}'
            pl.scale = (5000, 5000, 1)
            pl.location = hc + D * ds
            pl.rotation_mode = 'QUATERNION'
            pl.rotation_quaternion = (-D).to_track_quat('Z', 'Y')
            pl.data.materials.append(cm)
            pl.visible_shadow = False
            SP.show(pl, T0 - 2, T1 + 2)

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
            p2 = H[f] - D * 34 + e2 * 9 + e1 * 5
            l2 = H[f] + D * 70 + e2 * 2
            p = p1.lerp(p2, sm)
            l_ = l1.lerp(l2, sm)
            sk = ramp(f, T_FIRE, T_FIRE + 6) * 0.7
            p = p + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * sk
            roll = rnd.uniform(-1, 1) * 0.02 * (sk / 0.7)
            keys.append((f, p, l_, 24 + 4 * sm, roll))
        return keys
