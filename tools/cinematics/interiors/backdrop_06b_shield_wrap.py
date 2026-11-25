"""Battle backdrop 6b (rework): Arcadian boarding pods passing THROUGH the Terran triangle shield.

    PY=/home/user/artenv/venv/bin/python ; S=tools/cinematics/interiors/backdrop_06b_shield_wrap.py
    $PY $S --frame=30 --out=FILE.jpg [--final=1]      one still (final = 1920x1080)
    $PY $S --stages=1 --dir=DIR [--final=1]            the six stage stills (1280x720 when final)
    $PY $S --sheet=1 --dir=DIR --out=SHEET.jpg         contact sheet from the stage stills
    $PY $S --clip=1 --dir=DIR [--f0 --f1 --step]       draft clip frames DIR/f_0001.jpg ...

David: "The shield can't shatter. The shield has to still kind of go around the vehicle and that vehicle kind
of penetrates through it." So the shield here is ONE continuous surface the whole time: no plates break off,
there is never a hole. The pod presses in, the tessellated skin bows and hugs the hull (its triangles split
into smaller connected ones near the hull and merge back afterwards), the pod slides through a tight bright
contour ring where hull meets shield, the triangles round it glow saturated blue-cyan and a brightness wave
steps outward triangle by triangle, gold lightning skitters at the contour; when the tail clears the skin
springs back flat with a ripple.

World: pods fly along +X; the shield is a sphere (radius RS, centre (RS, 0, 0)) through the origin, where the
hero pod meets it; the dreadnought's lit bay door is at (BX, 0, 0). Concept art only.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
import backdrop_stretch as ST  # noqa: E402
import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

A = K.ARGS
DIR = A.get('dir', os.path.join(K.SCRATCH, 'wrap_b'))
NF = 90
RS = 150.0
BX = float(A.get('bx', 44.0))
PODS = [(0.0, 0.0, 12), (15.0, 5.5, -20), (-12.0, -6.0, 44), (30.0, -3.0, 66)]   # contact y, z, first-contact frame
TP = 34.0            # frames from first touch to the tail clearing the shield
DMAX = 3.4           # how far the skin is dragged in
LP, RP = 7.0, 1.15   # pod length and greatest radius
SCUT = 0.94          # the hull ends (nozzle) at this fraction of LP
STAGES = [int(v) for v in A.get('stage_frames', '8,18,30,38,48,58').split(',')]
HERO = 36


# ====================================================================== small helpers
def M(nt, op, a, b=None):
    nd = nt.nodes.new('ShaderNodeMath')
    nd.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            nd.inputs[i].default_value = v
        else:
            nt.links.new(v, nd.inputs[i])
    return nd.outputs[0]


def attr(nt, name):
    nd = nt.nodes.new('ShaderNodeAttribute')
    nd.attribute_name = name
    return nd.outputs['Fac']


def curve_obj(k, lines, width, mat, cyclic=False):
    cu = bpy.data.curves.new(k.uid('Crv'), 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = width
    cu.bevel_resolution = 1 if cyclic else 0
    for pts, wk in lines:
        pts = np.asarray(pts, dtype=np.float64)
        n = len(pts)
        sp = cu.splines.new('POLY')
        sp.points.add(n - 1)
        sp.points.foreach_set('co', np.concatenate([pts, np.ones((n, 1))], axis=1).ravel())
        sp.points.foreach_set('radius', [wk if cyclic else wk * (1.0 - 0.6 * i / (n - 1)) for i in range(n)])
        sp.use_cyclic_u = cyclic
    cu.materials.append(mat)
    o = bpy.data.objects.new(cu.name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.visible_shadow = False
    return o


def jag(p0, p1, rnd, j=0.16, depth=4):
    return np.array(ST._jag(p0, p1, rnd, j, depth))


def sphere_x(y, z):
    return RS - np.sqrt(RS * RS - y * y - z * z)


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


_GMAX = max((s ** 0.55) * (1 - s) ** 0.35 for s in np.linspace(0.01, 0.99, 400))


def hull_r(u):
    """Hull radius at distance u behind the nose (0 outside the hull)."""
    s = np.clip(np.asarray(u, dtype=np.float64) / LP, 0.0, 1.0)
    r = RP * (s ** 0.55) * (1 - s) ** 0.35 / _GMAX
    return np.where((np.asarray(u) > 0) & (np.asarray(u) < SCUT * LP), r, 0.0)


# ====================================================================== the Arcadian pod
def build_pod(k):
    """Curved, etched gold seed with three small crescent fins and a lightning nozzle. Nose at the origin,
    pointing +X; the hull runs back to x = -SCUT * LP."""
    root = bpy.data.objects.new(k.uid('APod'), None)
    bpy.context.scene.collection.objects.link(root)
    root.rotation_mode = 'QUATERNION'
    gold = K.metal_mat('APodGold2', (0.95, 0.62, 0.2), 0.34, 0.9, emit=(1.0, 0.5, 0.1), emit_k=0.09)
    bronze = K.metal_mat('APodBronze2', (0.28, 0.15, 0.05), 0.42, 1.0)
    inlay = K.C.emit_mat('APodInlay', (1.0, 0.55, 0.12), 4.0)
    core = K.C.emit_mat('APodCore', (1.0, 0.85, 0.55), 38.0)
    me = bpy.data.meshes.new('APodHull')
    bm = bmesh.new()
    segs, st = 40, 56
    us = np.linspace(0.0, SCUT * LP, st)
    us[0] = 0.004
    rings = []
    for u in us:
        r = float(hull_r(u))
        rings.append([bm.verts.new((-u, r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs)))
                      for i in range(segs)])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segs):
            bm.faces.new((a[i], a[(i + 1) % segs], b[(i + 1) % segs], b[i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    hull = bpy.data.objects.new('APodHull', me)
    bpy.context.scene.collection.objects.link(hull)
    me.materials.append(gold)
    hull.parent = root
    # etched inlay: three slow spirals and two fine rings, set just proud of the hull, glowing faintly
    lines = []
    for j in range(3):
        uu = np.linspace(0.5, SCUT * LP - 0.5, 60)
        ph = 2 * math.pi * j / 3 + 1.7 * uu / LP
        rr = hull_r(uu) + 0.012
        lines.append((np.stack([-uu, rr * np.cos(ph), rr * np.sin(ph)], axis=1), 1.0))
        ph2 = 2 * math.pi * (j + 0.5) / 3 - 1.1 * uu / LP
        lines.append((np.stack([-uu, rr * np.cos(ph2), rr * np.sin(ph2)], axis=1), 0.6))
    for uu in (1.5, 5.1):
        a = np.linspace(0, 2 * math.pi, 49)[:-1]
        rr = float(hull_r(uu)) + 0.012
        lines.append((np.stack([np.full_like(a, -uu), rr * np.cos(a), rr * np.sin(a)], axis=1), 0.8))
    cu = bpy.data.curves.new('APodEtch', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.02
    cu.bevel_resolution = 0
    for pts, wk in lines:
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        sp.points.foreach_set('co', np.concatenate([pts, np.ones((len(pts), 1))], axis=1).ravel())
        sp.points.foreach_set('radius', [wk] * len(pts))
        sp.use_cyclic_u = len(pts) == 48
    cu.materials.append(inlay)
    et = bpy.data.objects.new('APodEtch', cu)
    bpy.context.scene.collection.objects.link(et)
    et.parent = root
    et.visible_shadow = False
    for uu, w in ((2.6, 0.10), (5.6, 0.14)):                       # bronze collars
        K.C.uv_sphere(k.uid('APodBand'), 1.0, seg=(32, 6), mat=bronze,
                      scale=(w, float(hull_r(uu)) + 0.03, float(hull_r(uu)) + 0.03)).parent = root
        bpy.context.scene.collection.objects[-1].location = (-uu, 0, 0)
    # three small crescent fins near the tail
    fm = bpy.data.meshes.new('APodFin')
    bm = bmesh.new()
    n = 14
    outer = [(1.25 * math.cos(a) - 0.2, 1.25 * math.sin(a)) for a in np.linspace(math.radians(18), math.radians(150), n)]
    inner = [(1.75 * math.cos(a) + 0.15, 1.75 * math.sin(a) - 0.82) for a in np.linspace(math.radians(138), math.radians(50), n)]
    vs = [bm.verts.new((x, 0.0, z)) for x, z in outer + inner]
    bm.faces.new(vs)
    bm.to_mesh(fm)
    bm.free()
    fm.materials.append(gold)
    for j in range(3):
        f = bpy.data.objects.new(k.uid('APodFin'), fm)
        bpy.context.scene.collection.objects.link(f)
        f.parent = root
        md = f.modifiers.new('sol', 'SOLIDIFY')
        md.thickness = 0.06
        md.offset = 0.0
        a = 2 * math.pi * j / 3 + 0.5
        f.rotation_euler = (a - math.pi / 2, 0, 0)
        rr = float(hull_r(5.3)) - 0.42
        f.location = (-5.3, -rr * math.sin(a - math.pi / 2), rr * math.cos(a - math.pi / 2))
        f.scale = (1.05, 1, 0.8)
    nz = K.C.uv_sphere(k.uid('APodNoz'), 1.0, seg=(24, 6), mat=bronze, scale=(0.22, 0.5, 0.5))
    nz.parent = root
    nz.location = (-SCUT * LP - 0.05, 0, 0)
    cr = K.C.uv_sphere(k.uid('APodCore'), 1.0, seg=(12, 6), mat=core, scale=(0.3, 0.3, 0.3))
    cr.parent = root
    cr.location = (-SCUT * LP - 0.25, 0, 0)
    cr.visible_shadow = False
    return root


class Pod:
    def __init__(self, k, cy, cz, fc, seed):
        self.k, self.cy, self.cz, self.fc, self.seed = k, cy, cz, fc, seed
        self.x0 = float(sphere_x(cy, cz))
        self.root = build_pod(k)
        self.zmat = K.C.emit_mat(k.uid('PodZapM'), (1.0, 0.68, 0.26), 9.0)
        self.fx = []

    def nose_x(self, f):
        t = f - self.fc
        if t < 0:
            return 1.6 * t
        xe = SCUT * LP + DMAX + 0.4
        if t <= TP:
            s = t / TP
            return xe * (0.8 * s + 0.2 * s ** 3)
        u = t - TP
        return xe + 0.43 * u + 0.5 * 0.3 * u * u

    def state(self, f):
        xn = self.nose_x(f)
        t = f - self.fc
        far = BX - self.x0 - 10.0
        kk = smooth((xn - 10.0) / far) if xn > 10.0 else 0.0
        y, z = self.cy * (1 - kk), self.cz * (1 - kk)
        # the skin: dragged in by D; it meets the hull u behind the nose, on a ring of radius rc
        if 0 <= t <= TP:
            D = DMAX * (1 - math.exp(-xn / 1.4))
            u = xn - D
            rc = float(hull_r(u))
            eng = True
        else:
            D, u, rc, eng = 0.0, 0.0, 0.0, False
        return dict(xn=xn, speed=xn - self.nose_x(f - 1), nose=np.array((self.x0 + xn, y, z)), t=t, D=D, u=u, rc=rc,
                    eng=eng, gone=bool(self.x0 + xn > BX - 1.0))

    def pose(self, f):
        for o in self.fx:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.curves.remove(d)
        self.fx = []
        s = self.state(f)
        d = Vector(self.state(f + 1)['nose'] - s['nose'])
        d = d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))
        hide = bool(s['gone'] or s['nose'][0] < -70)
        for o in [self.root] + list(self.root.children_recursive):
            o.hide_render = hide
        self.root.location = Vector(s['nose'])
        self.root.rotation_quaternion = d.to_track_quat('X', 'Z')
        s['d'] = np.array(d)
        if not hide:                                             # lightning thruster
            rnd = random.Random(self.seed * 131 + f // 2)
            sp = min(1.9, max(0.05, s['speed']))
            tail = s['nose'] - s['d'] * (SCUT * LP + 0.3)
            lines = []
            for _ in range(4):
                L = (2.5 + 8.0 * sp) * rnd.uniform(0.5, 1.0)
                off = np.array([0.0, rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5)])
                lines.append((jag(tail + off * 0.3, tail - s['d'] * L + off * (1.0 + 1.2 * sp), rnd, 0.2, 4), 1.0))
            self.fx.append(curve_obj(self.k, lines, 0.06, self.zmat))
        return s


# ====================================================================== the shield: one connected tessellated skin
class Skin:
    EDGE = 2.6

    def __init__(self, k, pods):
        self.k, self.pods = k, pods
        e = self.EDGE
        hgt = e * math.sqrt(3) / 2
        I3 = np.eye(3)
        P, B0, B1, B2, C1 = [], [], [], [], []

        def sub(v, b0, b1, b2, c1, lvl, depth):
            if lvl == depth:
                P.append(v)
                B0.append(b0)
                B1.append(b1 if b1 is not None else b0)
                B2.append(b2 if b2 is not None else (b1 if b1 is not None else b0))
                C1.append(c1 if c1 is not None else v.mean(axis=0))
                return
            m = lambda a: np.array([(a[0] + a[1]) / 2, (a[1] + a[2]) / 2, (a[2] + a[0]) / 2])  # noqa: E731
            vm, m0 = m(v), m(b0)
            m1 = m(b1) if b1 is not None else None
            for ids in (('c0', 'm0', 'm2'), ('m0', 'c1', 'm1'), ('m2', 'm1', 'c2'), ('m0', 'm1', 'm2')):
                pick = lambda a, am: np.array([a[int(i[1])] if i[0] == 'c' else am[int(i[1])] for i in ids])  # noqa: E731
                cv = pick(v, vm)
                nl = lvl + 1
                nb1 = I3 if nl == 1 else (pick(b1, m1) if b1 is not None else None)
                nb2 = I3 if nl == 2 else (pick(b2, m(b2)) if b2 is not None else None)
                nc1 = cv.mean(axis=0) if nl == 1 else c1
                sub(cv, pick(b0, m0), nb1, nb2, nc1, nl, depth)

        for j in range(-int(44 / hgt), int(44 / hgt)):
            for i in range(-int(58 / e) - 1, int(78 / e) + 1):
                x0 = i * e + (e / 2 if j % 2 else 0.0)
                a, b, c, d = (x0, j * hgt), (x0 + e, j * hgt), (x0 + e / 2, (j + 1) * hgt), (x0 + 1.5 * e, (j + 1) * hgt)
                for tri in ((a, b, c), (b, d, c)):
                    v = np.array(tri)
                    cen = v.mean(axis=0)
                    near = min(math.hypot(cen[0] - p.cy, cen[1] - p.cz) for p in pods)
                    sub(v, I3, None, None, None, 0, 3 if near < 10.5 else 0)
        self.YZ = np.array(P)                                    # (T, 3, 2): never changes
        self.X0 = sphere_x(self.YZ[..., 0], self.YZ[..., 1])
        self.C1 = np.array(C1)                                   # centre of each triangle's mid-size parent
        T = len(P)
        rnd = np.random.default_rng(5)
        me = bpy.data.meshes.new('Skin')
        co = np.concatenate([self.X0[..., None], self.YZ], axis=-1).reshape(-1, 3)
        me.from_pydata(co.tolist(), [], np.arange(T * 3).reshape(T, 3).tolist())
        for nm, bb in (('b0', B0), ('b1', B1), ('b2', B2)):
            uv = me.uv_layers.new(name=nm)
            uv.data.foreach_set('uv', np.array(bb)[:, :, :2].astype(np.float32).ravel())
        for nm in ('bk_flare', 'bk_fill', 'bk_split'):
            me.attributes.new(nm, 'FLOAT', 'POINT')
        # a few plates are faintly filled, as on the ships' shields (chosen per coarse plate)
        key = np.round(self.C1 * 7.0).astype(np.int64)
        h = ((key[:, 0] * 73856093) ^ (key[:, 1] * 19349663)) % 1000 / 1000.0
        fill = np.where(h < 0.14, 0.3 + 0.7 * ((h * 97) % 1.0), 0.06)
        me.attributes['bk_fill'].data.foreach_set('value', np.repeat(fill, 3).astype(np.float32))
        del rnd
        ob = bpy.data.objects.new('Skin', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.visible_shadow = False
        self.ob, self.me = ob, me
        me.materials.append(self._material())
        self.zmat = K.C.emit_mat('SkinZapM', (1.0, 0.68, 0.26), 9.0)
        self.cmat = K.C.emit_mat('SkinContourM', (0.5, 0.92, 1.0), 45.0)
        self.fx = []
        self.lights = [k.light((p.x0 - 2, p.cy, p.cz), (0.3, 0.75, 1.0), 0.0, 1.0) for p in pods]

    def _material(self):
        m = bpy.data.materials.new('SkinM')
        m.use_nodes = True
        nt = m.node_tree
        for nd in list(nt.nodes):
            nt.nodes.remove(nd)

        def line(uvname, width):
            uv = nt.nodes.new('ShaderNodeUVMap')
            uv.uv_map = uvname
            sep = nt.nodes.new('ShaderNodeSeparateXYZ')
            nt.links.new(uv.outputs[0], sep.inputs[0])
            u, v = sep.outputs['X'], sep.outputs['Y']
            w = M(nt, 'SUBTRACT', M(nt, 'SUBTRACT', 1.0, u), v)
            edge = M(nt, 'MINIMUM', M(nt, 'MINIMUM', u, v), w)
            return M(nt, 'MAXIMUM', M(nt, 'SUBTRACT', 1.0, M(nt, 'DIVIDE', edge, width)), 0.0)
        l0, l1, l2 = line('b0', 0.035), line('b1', 0.055), line('b2', 0.085)
        flare, fill, split = attr(nt, 'bk_flare'), attr(nt, 'bk_fill'), attr(nt, 'bk_split')
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        sp = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Position'], sp.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs[1].default_value, mr.inputs[2].default_value = 26.0, 44.0
        mr.inputs[3].default_value, mr.inputs[4].default_value = 1.0, 0.0
        nt.links.new(M(nt, 'ABSOLUTE', sp.outputs['Z']), mr.inputs[0])
        lk = M(nt, 'ADD', 0.55, M(nt, 'MULTIPLY', flare, float(A.get('flarek', 1.6))))
        st = M(nt, 'MULTIPLY', l0, lk)
        fine = M(nt, 'ADD', M(nt, 'MULTIPLY', l1, M(nt, 'MINIMUM', M(nt, 'MULTIPLY', split, 2.0), 1.0)),
                 M(nt, 'MULTIPLY', l2, M(nt, 'MAXIMUM', M(nt, 'SUBTRACT', M(nt, 'MULTIPLY', split, 2.0), 0.8), 0.0)))
        st = M(nt, 'ADD', st, M(nt, 'MULTIPLY', fine, M(nt, 'MULTIPLY', lk, 0.45)))
        st = M(nt, 'ADD', st, M(nt, 'ADD', M(nt, 'MULTIPLY', fill, 0.16), M(nt, 'MULTIPLY', flare, float(A.get('facek', 0.6)))))
        st = M(nt, 'MULTIPLY', M(nt, 'MULTIPLY', st, mr.outputs[0]), float(A.get('trik', 1.0)))
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.inputs[6].default_value = (0.06, 0.38, 1.0, 1)          # stays blue: deep blue -> blue-cyan, never white
        mix.inputs[7].default_value = (0.05, 0.62, 1.0, 1)
        nt.links.new(M(nt, 'MINIMUM', flare, 1.0), mix.inputs[0])
        em = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(mix.outputs[2], em.inputs['Color'])
        nt.links.new(st, em.inputs['Strength'])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        add = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(tr.outputs[0], add.inputs[0])
        nt.links.new(em.outputs[0], add.inputs[1])
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(add.outputs[0], out.inputs['Surface'])
        return m

    @staticmethod
    def dent(r, s):
        """How far the skin is pushed in at distance r from a pod's lane."""
        if s['eng']:
            # glove fit: the skin hugs the hull and fillets into the sphere within a short wall (no funnel)
            w = float(A.get('glove_w', 0.7)) + 0.12 * s['D']
            x = np.clip(1 - np.clip(r - s['rc'], 0, None) / w, 0, 1)
            return s['D'] * x * x * (1.6 - 0.6 * x)
        tau = s['t'] - TP
        if 0 < tau < 40:                                           # the tail is clear: spring back, ringing
            # snap: the released sleeve whips back, overshoots outward hard and rings (widening as it goes)
            wid = 1.6 + 0.35 * tau
            return DMAX * 1.05 * math.exp(-tau / 4.5) * math.cos(tau * 0.62) * np.exp(-(r / wid) ** 2) \
                + 0.35 * math.exp(-tau / 9.0) * np.sin(np.clip(1.5 * tau - r, 0, None) * 1.3) * np.exp(-r / 9.0) * (r < 1.5 * tau)
        return np.zeros_like(r)

    def set(self, f, states):
        for o in self.fx:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.curves.remove(d)
        self.fx = []
        Y, Z = self.YZ[..., 0], self.YZ[..., 1]
        disp = np.zeros_like(self.X0)
        flare = np.zeros(len(self.C1))
        split = np.zeros_like(self.X0)
        zaps, rings = [], []
        for i, (p, s) in enumerate(zip(self.pods, states)):
            t = s['t']
            light = 0.0
            if t < 0 or t > TP + 40:
                self.lights[i].data.energy = 0.0
                continue
            r = np.hypot(Y - p.cy, Z - p.cz)
            r1 = np.hypot(self.C1[:, 0] - p.cy, self.C1[:, 1] - p.cz)       # per mid-size triangle: stepped look
            disp += self.dent(r, s)
            rnd = random.Random(p.seed * 7919 + f // 2)
            if s['eng']:
                rc = s['rc']
                kin = smooth(t / 5.0) * smooth((TP - t) / 3.0 + 0.4)
                flare += 1.15 * kin * np.exp(-((r1 - rc) / 1.5) ** 2)       # the triangles touching the hull
                for j in range(6):                                         # brightness wave, triangle by triangle
                    age = t - j * 6.0
                    if age > 0:
                        R = rc + 0.95 * age
                        flare += np.clip(1 - np.abs(r1 - R) / 1.5, 0, 1) * 0.8 * math.exp(-(R - rc) / 9.0)
                split = np.maximum(split, kin * np.exp(-(np.clip(r - rc, 0, None) / 3.6) ** 2))
                light = 1.2e3 * kin
                if rc > 0.05:
                    # the contour: a tight bright ring where hull meets shield
                    a = np.linspace(0, 2 * math.pi, 65)[:-1]
                    cx = p.x0 + s['D']
                    rings.append((np.stack([np.full_like(a, cx), s['nose'][1] + (rc + 0.03) * np.cos(a),
                                            s['nose'][2] + (rc + 0.03) * np.sin(a)], axis=1), 1.0))
                    for _ in range(3):                                     # gold lightning skittering at the contour
                        a0 = rnd.uniform(0, 2 * math.pi)
                        rs = np.linspace(rc + 0.05, rc + rnd.uniform(1.8, 4.5), 16)
                        aa = a0 + np.cumsum(np.array([rnd.uniform(-1, 1) for _ in rs]) * 0.12)
                        yy, zz = p.cy + rs * np.cos(aa), p.cz + rs * np.sin(aa)
                        xx = sphere_x(yy, zz) + self.dent(rs, s) - 0.07
                        zaps.append((np.stack([xx, yy, zz], axis=1), 1.0))
                    if s['u'] < SCUT * LP - 0.8:                           # and along the hull still outside
                        ph = rnd.uniform(0, 2 * math.pi)
                        uu = np.linspace(s['u'], min(SCUT * LP, s['u'] + rnd.uniform(1.5, 3.5)), 10)
                        pa = ph + np.cumsum(np.array([rnd.uniform(-1, 1) for _ in uu]) * 0.18)
                        rr = hull_r(uu) + 0.05
                        zaps.append((np.stack([s['nose'][0] - uu, s['nose'][1] + rr * np.cos(pa),
                                               s['nose'][2] + rr * np.sin(pa)], axis=1), 0.8))
            else:
                tau = t - TP
                R = 1.5 * tau                                               # the release ripple
                flare += np.clip(1 - np.abs(r1 - R) / 1.7, 0, 1) * 1.1 * math.exp(-R / 14.0)
                flare += 1.4 * math.exp(-tau / 3.0) * np.exp(-(r1 / 2.6) ** 2)      # snap flash
                flare += 0.6 * abs(math.cos(tau * 0.62)) * math.exp(-tau / 5.0) * np.exp(-(r1 / 3.5) ** 2)
                split = np.maximum(split, math.exp(-tau / 5.0) * np.exp(-(r / 3.6) ** 2))
                light = 2.5e3 * math.exp(-tau / 3.0)
            self.lights[i].data.energy = light
            self.lights[i].location = (p.x0 - 1.5, p.cy, p.cz)
        co = np.concatenate([(self.X0 + disp)[..., None], self.YZ], axis=-1)
        self.me.vertices.foreach_set('co', co.reshape(-1, 3).astype(np.float32).ravel())
        self.me.attributes['bk_flare'].data.foreach_set('value', np.repeat(np.clip(flare, 0, 1.6), 3).astype(np.float32))
        self.me.attributes['bk_split'].data.foreach_set('value', split.astype(np.float32).ravel())
        self.me.update()
        if zaps:
            self.fx.append(curve_obj(self.k, zaps, 0.045, self.zmat))
        if rings:
            self.fx.append(curve_obj(self.k, rings, 0.085, self.cmat, cyclic=True))


# ====================================================================== the scene
def place_ship(ob, local_pt, local_n, world_pt, tilt):
    q = Quaternion((1, 0, 0), math.radians(tilt)) @ Vector(local_n).normalized().rotation_difference(Vector((-1, 0, 0)))
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = q
    ob.location = Vector(world_pt) - q @ (Vector(local_pt) * ob.scale.x)
    bpy.context.view_layer.update()


def build():
    k = K.Kit(sun_dir=(0.5, 0.6, -0.5), sun_energy=5.0, planet=False, rim_dir=(-0.6, -0.6, 0.2), rim=1.6,
              fill_dir=(0.3, 1, -0.2), fill=2.0, tint='blue', nebula=1.5)
    bpy.context.scene.frame_end = NF
    cp = [float(v) for v in A.get('cam', '-15,-27,8').split(',')]
    ct = [float(v) for v in A.get('tgt', '10,3,-1').split(',')]
    k.camera(cp, ct, lens=float(A.get('lens', 26)))
    sh = k.ship('dread', scale=2.2)
    bays = sorted([b for b in k.extra('dread') if b.y > 0], key=lambda b: b.x)
    for b in bays:
        K.terran_bay(k, sh, b, 1)
    b = bays[len(bays) // 2]
    place_ship(sh, b + Vector((0, 0.3, 0)), (0, 1, 0), (BX, 0, 0), float(A.get('tilt', 14)))
    pods = [Pod(k, cy, cz, fc, 11 + i) for i, (cy, cz, fc) in enumerate(PODS)]
    return k, pods, Skin(k, pods)


def pose(pods, skin, f):
    skin.set(f, [p.pose(f) for p in pods])


def render(k, f, out, res, samples):
    sc = bpy.context.scene
    k.sh.render_settings(res, samples, blur=False)
    sc.cycles.adaptive_threshold = 0.05 if samples > 20 else 0.08
    sc.cycles.transparent_max_bounces = 24
    sc.cycles.max_bounces = 4
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = int(A.get('threads', 3))
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.frame_set(f)
    raw = os.path.splitext(out)[0] + '_raw.png'
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    im = K.post(raw, float(A.get('bloom', 0.8)), 0.2)
    im.save(out, quality=92)
    os.remove(raw)
    print('WROTE', out, flush=True)


def sheet(out, n):
    ims = [Image.open(os.path.join(DIR, f'stage_{i + 1}.jpg')).convert('RGB') for i in range(n)]
    w, h = ims[0].size
    g, cols = 14, 3
    rows = (len(ims) + cols - 1) // cols
    sh = Image.new('RGB', (cols * w + (cols + 1) * g, rows * h + (rows + 1) * g), (6, 7, 9))
    dr = ImageDraw.Draw(sh)
    for i, im in enumerate(ims):
        x, y = g + (i % cols) * (w + g), g + (i // cols) * (h + g)
        sh.paste(im, (x, y))
        for j in range(i + 1):
            dr.rectangle((x + 22 + j * 20, y + h - 34, x + 22 + j * 20 + 11, y + h - 23), fill=(120, 200, 255))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sh.save(out, quality=92)
    print('WROTE', out, sh.size, flush=True)


if A.get('sheet') == '1':
    sheet(A['out'], len(STAGES))
else:
    os.makedirs(DIR, exist_ok=True)
    k, pods, skin = build()
    if A.get('clip') == '1':
        for f in range(int(A.get('f0', 1)), int(A.get('f1', NF)) + 1, int(A.get('step', 1))):
            o = os.path.join(DIR, f'f_{f:04d}.jpg')
            if os.path.exists(o):
                continue
            pose(pods, skin, f)
            render(k, f, o, (960, 540), int(A.get('samples', 10)))
    elif A.get('stages') == '1':
        for i, f in enumerate(STAGES):
            pose(pods, skin, f)
            render(k, f, os.path.join(DIR, f'stage_{i + 1}.jpg'), (1280, 720) if K.FINAL else (960, 540),
                   int(A.get('samples', 36 if K.FINAL else 12)))
    else:
        f = int(A.get('frame', HERO))
        pose(pods, skin, f)
        render(k, f, A.get('out', os.path.join(DIR, f'test_{f:03d}.jpg')), (1920, 1080) if K.FINAL else (960, 540),
               int(A.get('samples', 40 if K.FINAL else 12)))
