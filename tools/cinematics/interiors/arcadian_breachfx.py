"""Arcadian force aperture under attack: the animated parts (shared by arcadian_breach.py and the
game-view still in arcadian_deck.py).

The Arcadian field is an elastic skin, not glass: an intruder bows it inward like a taut membrane,
concentric gold ripples run out to the rim, the exact tick rings spin up and tighten, lightning snaps
from the rim to the hull, and when it gives way it opens a clean round hole with a crisp ring pulse,
then irises closed again. (The Terran field, by contrast, shatters into triangles.)

    Membrane   the skin: a fine disc mesh, displaced and painted (vertex colours) every frame
    Rings      the instrument rings round the lip as separate objects that can spin / tighten
    Intruder   a Terran game unit with its measured nose, hull front and surface sample points
    dyn_bolts  lightning that is rebuilt every frame
"""
import math
import os
import random

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

import arcadian_kit as K
from arcadian_kit import F, A


def _line(x, w):
    """1 on integer values of x, falling to 0 within w (as a fraction of the period)."""
    tri = np.abs((x - np.floor(x)) - 0.5) * 2.0
    return np.clip((tri - (1.0 - w)) / w, 0.0, 1.0)


def membrane_mat(strength=6.0):
    mat = bpy.data.materials.new('breach_membrane')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'fx'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(at.outputs['Color'], sep.inputs[0])
    m1 = nt.nodes.new('ShaderNodeMix')
    m1.data_type = 'RGBA'
    m1.inputs[6].default_value = (1, 1, 1, 1)
    m1.inputs[7].default_value = (0.72, 0.68, 0.6, 1)
    nt.links.new(sep.outputs[1], m1.inputs[0])
    m2 = nt.nodes.new('ShaderNodeMix')
    m2.data_type = 'RGBA'
    m2.inputs[7].default_value = (0.2, 0.13, 0.04, 1)
    nt.links.new(m1.outputs[2], m2.inputs[6])
    nt.links.new(sep.outputs[2], m2.inputs[0])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    nt.links.new(m2.outputs[2], tr.inputs['Color'])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.68, 0.18, 1)
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = strength
    nt.links.new(sep.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs['Strength'])
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    return mat


class Membrane:
    def __init__(self, c, r, sq, nr=200, na=320, strength=6.0):
        self.M = K.frame(Vector(c), (1, 0, 0))
        self.Mi = self.M.inverted()
        self.r, self.sq = r, sq
        rr = np.arange(1, nr + 1) / nr
        ang = np.arange(na) * 2 * math.pi / na
        x = np.concatenate([[0.0], (r * rr[:, None] * np.cos(ang)[None, :]).ravel()])
        y = np.concatenate([[0.0], (r * sq * rr[:, None] * np.sin(ang)[None, :]).ravel()])
        self.base = np.stack([x, y, np.zeros_like(x)], axis=1)
        self.rn = np.concatenate([[0.0], np.repeat(rr, na)])
        faces = [(0, 1 + k, 1 + (k + 1) % na) for k in range(na)]
        for i in range(nr - 1):
            a, b = 1 + i * na, 1 + (i + 1) * na
            faces += [(a + k, b + k, b + (k + 1) % na, a + (k + 1) % na) for k in range(na)]
        me = bpy.data.meshes.new('breach_membrane')
        me.from_pydata(self.base.tolist(), [], faces)
        for p in me.polygons:
            p.use_smooth = True
        me.color_attributes.new('fx', 'FLOAT_COLOR', 'POINT')
        self.obj = bpy.data.objects.new('breach_membrane', me)
        bpy.context.scene.collection.objects.link(self.obj)
        self.obj.matrix_world = self.M
        self.obj.visible_shadow = False
        me.materials.append(membrane_mat(strength))
        self.update(c, 0.0)

    def rim(self, a, k=1.035):
        return self.M @ Vector((self.r * k * math.cos(a), self.r * self.sq * k * math.sin(a), 0))

    def update(self, contact, depth, tent=0.0, a=3.3, strain=0.0, t=0.0, hole=0.0, pulse=None, wobble=0.0, tent_at=None, body=0.0):
        """contact: world point where the intruder presses; depth: how far the skin is pushed in over
        the hull front; tent: extra length pulled over a thin nose (gun); a: radius of the hull front;
        strain 0..1 drives the light; hole: radius of the opening; pulse: (radius, amplitude) of the
        crisp ring; wobble: whole-skin elastic swing after it lets go (metres, signed)."""
        cl = self.Mi @ Vector(contact)
        dx = self.base[:, 0] - cl.x
        dy = (self.base[:, 1] - cl.y) / 0.72
        rho = np.sqrt(dx * dx + dy * dy)
        L = 2.2 + 0.45 * abs(depth)
        over = np.maximum(rho - a, 0.0)
        prof = np.where(rho < a, 1.0, np.exp(-over / L))
        rimf = np.clip(1.0 - self.rn ** 3, 0.0, 1.0)
        tl = self.Mi @ Vector(tent_at if tent_at is not None else contact)
        rt = np.sqrt((self.base[:, 0] - tl.x) ** 2 + (self.base[:, 1] - tl.y) ** 2)
        disp = depth * prof * rimf + 0.8 * tent * np.exp(-(rt / 0.85) ** 2.6) + 0.2 * tent * np.exp(-(rt / 2.2) ** 2)
        disp = disp + wobble * rimf * np.cos(self.rn * math.pi / 2)
        co = self.base.copy()
        co[:, 2] = -disp
        me = self.obj.data
        me.vertices.foreach_set('co', co.ravel())
        # light
        e = 0.05 * _line(self.rn * 9.0, 0.08) * (0.25 + 0.75 * self.rn ** 2)
        if strain > 0:
            e = e + strain * 0.9 * _line((rho - 5.5 * t) / 2.4, 0.10) * (0.3 + 0.7 * np.exp(-rho / 8.0))
            e = e + strain * 0.02 * np.exp(-over / L) + 0.6 * strain * np.exp(-((rho - a) / 0.18) ** 2)
            e = e + body * (prof * rimf + np.exp(-(rt / 1.6) ** 2) * (tent > 0.3))
            th = np.arctan2(dy, dx)
            e = e + strain * 0.16 * _line(th * 14 / (2 * math.pi) + 0.25 * np.sin(th * 3), 0.22) * np.exp(-over / (1.3 * L)) * (rho > a) * np.clip(over / 1.5, 0, 1)
            e = e + strain * 0.02 * (rho < a)
        g = np.ones_like(e)
        if hole > 0.05:
            g = (rho >= hole).astype(float)
            e = e * g + 9.0 * np.exp(-((rho - hole) / 0.14) ** 2) * g
        if pulse:
            e = e + pulse[1] * np.exp(-((rho - pulse[0]) / 0.12) ** 2) * g
        b = np.clip(0.5 * strain * prof ** 0.5, 0.0, 1.0) * g
        col = np.stack([e, g, b, np.ones_like(e)], axis=1).astype(np.float32)
        me.color_attributes['fx'].data.foreach_set('color', col.ravel())
        me.update()


class Rings:
    """Lip (static) + three instrument rings that can be spun and tightened (rotate, then squash)."""

    def __init__(self, c, r, sq, scale_ticks=1.0):
        self.M = K.frame(Vector(c), (1, 0, 0))
        self.S = Matrix.Diagonal((sq[0], sq[1], 1.0, 1.0))
        K.finish()
        mk = F.mark()
        K.ring_flat((0, 0, 0), r, r * 0.012, r * 0.012, 'white', n=160)
        K.ring_flat((0, 0, 0), r * 1.035, r * 0.03, r * 0.05, 'inlay', n=160)
        for o in F.since(mk):
            F.xf(o, self.M @ self.S)
        K.finish()
        self.objs = []
        builders = (
            lambda: K.ticks((0, 0, 0), r * 1.06, r * 1.09, int(180 * scale_ticks), r * 0.006, r * 0.01, 'line', every=15, long=r * 0.035),
            lambda: (K.ring_flat((0, 0, 0), r * 1.2, r * 0.006, r * 0.006, 'line', n=160),
                     K.ticks((0, 0, 0), r * 1.2, r * 1.225, int(72 * scale_ticks), r * 0.008, r * 0.008, 'line', every=6, long=r * 0.04)),
            lambda: ([(K.ring_flat((0, 0, 0), r * 1.36, r * 0.022, r * 0.03, 'pale', n=30, a0=k * 90 + 12, a1=k * 90 + 78),
                       K.ring_flat((0, 0, 0), r * 1.385, r * 0.004, r * 0.004, 'line', n=30, a0=k * 90 + 14, a1=k * 90 + 76)) for k in range(4)],
                     K.ticks((0, 0, 0), r * 1.4, r * 1.43, int(240 * scale_ticks), r * 0.004, r * 0.006, 'soft', every=10, long=r * 0.03)),
        )
        for i, b in enumerate(builders):
            with K.layer(f'apring{i}'):
                b()
            self.objs.append(K.finish().get(f'apring{i}', []))
        self.update((0, 0, 0), (1, 1, 1))

    def update(self, angles, scales):
        for objs, ang, sc in zip(self.objs, angles, scales):
            m = self.M @ self.S @ Matrix.Rotation(math.radians(ang), 4, 'Z') @ Matrix.Diagonal((sc, sc, 1.0, 1.0))
            for o in objs:
                o.matrix_world = m


class Intruder:
    """A Terran game unit, facing -X (into the hall). x is the position of its gun tip."""

    def __init__(self, name='bulwark', scale=1.0):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=os.path.join(K.REPO, 'public', 'assets', 'models', 'human', name + '.glb'))
        new = [o for o in bpy.data.objects if o not in before]
        bpy.context.view_layer.update()
        pts = []
        for o in new:
            if o.type == 'MESH':
                pts += [o.matrix_world @ v.co for v in o.data.vertices]
                for mt in o.data.materials:
                    if mt and mt.use_nodes:
                        b = mt.node_tree.nodes.get('Principled BSDF')
                        if b and not b.inputs['Emission Strength'].is_linked:
                            b.inputs['Emission Strength'].default_value = max(b.inputs['Emission Strength'].default_value, 1.0) * 4.0
        self.piv = bpy.data.objects.new('intruder', None)
        bpy.context.scene.collection.objects.link(self.piv)
        for o in new:
            if o.parent is None:
                o.parent = self.piv
        self.piv.scale = (scale,) * 3
        xs = [p.x for p in pts]
        self.tip = max(xs) * scale
        self.front = max(p.x for p in pts if abs(p.y) > 1.2) * scale
        self.tail = min(xs) * scale
        self.h = max(p.z for p in pts) * scale
        self.half = max(abs(p.y) for p in pts) * scale
        self.gun_z = sum(p.z for p in pts if p.x > self.front / scale + 0.5) / max(1, sum(1 for p in pts if p.x > self.front / scale + 0.5)) * scale
        rnd = random.Random(2)
        self.local = [rnd.choice(pts) * scale for _ in range(400)]
        self.mat = Matrix.Identity(4)

    def place(self, tip_x, y, z, pitch=0.0, roll=0.0, yaw=180.0):
        e = Euler((math.radians(roll), math.radians(pitch), math.radians(yaw)))
        rot = e.to_matrix().to_4x4()
        loc = Vector((tip_x, y, z)) - rot @ Vector((self.tip, 0, 0)) + Vector((0, 0, 0))
        loc.z = z
        self.mat = Matrix.Translation(loc) @ rot
        self.piv.location = loc
        self.piv.rotation_euler = e
        return loc

    def surface(self, rnd, front=False):
        for _ in range(60):
            p = rnd.choice(self.local)
            if not front or p.x > self.front * 0.3:
                break
        return self.mat @ p

    def gun_tip(self):
        return self.mat @ Vector((self.tip, 0, self.gun_z))


_DYN = []


def dyn_bolts(specs, seed):
    """Replace the frame's lightning. specs: (p0, p1, width, jag, branches)."""
    for o in _DYN:
        bpy.data.objects.remove(o, do_unlink=True)
    _DYN.clear()
    if not specs:
        return
    K.finish()
    rnd = random.Random(seed)
    with K.layer('dyn'):
        for (p0, p1, w, jag, br) in specs:
            A.bolt(Vector(p0), Vector(p1), rnd, width=w, jag=jag, depth=5, branches=br, zone='thin')
    objs = K.finish().get('dyn', [])
    K.ST['layers']['dyn'] = []
    _DYN.extend(objs)


def breach_bolts(mem, intr, strain, seed, n_rim=6, n_crawl=8, width=0.06):
    """Lightning from the rim to the intruder and crawling over its hull, scaled by strain."""
    rnd = random.Random(seed)
    specs = []
    for _ in range(int(round(n_rim * strain))):
        a = rnd.uniform(0, 2 * math.pi)
        specs.append((mem.rim(a), intr.surface(rnd, front=True), width * rnd.uniform(0.7, 1.3), 0.2, 2))
    for _ in range(int(round(n_crawl * strain))):
        p = intr.surface(rnd)
        q = intr.surface(rnd)
        if (p - q).length < 5:
            specs.append((p + Vector((0, 0, 0.15)), q + Vector((0, 0, 0.15)), width * 0.45, 0.35, 1))
    return specs
