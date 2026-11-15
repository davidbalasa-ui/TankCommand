"""Battle backdrop 6: boarding pods pushing through an enemy capital ship's shield (exterior view).

    PY=/home/user/artenv/venv/bin/python ; S=tools/cinematics/interiors/backdrop_06_shield_push.py
    $PY $S --effect=a|b --frame=40 --out=FILE.jpg [--final=1]   one still (final = 1920x1080)
    $PY $S --effect=a|b --stages=1 --dir=DIR [--final=1]         the six stage stills (1280x720 when final)
    $PY $S --effect=a|b --sheet=1 --dir=DIR --out=SHEET.jpg      contact sheet from the stage stills
    $PY $S --effect=a|b --clip=1 --dir=DIR [--f0 --f1 --step]    draft clip frames DIR/f_0001.jpg ...

a: Terran pods (cyan trails) through the ARCADIAN shield: a gold membrane that bows in ahead of the nose, gold
   lightning converging on the contact and crawling over the pod, precise rings rippling out, the pod slowing
   as if in thick liquid; then it punches through with a sharp ring snap and an iris of arcs seals the hole.
b: Arcadian pods (gold, lightning trails) through the TERRAN shield: the triangles round the contact flare
   white-blue and flex in, crack apart and tumble as shards, the neighbours ripple, the pod forces through,
   then replacement triangles flip back into place one by one.

World: the pods fly along +X; the shield is a sphere (radius RS, centre (RS, 0, 0)) whose surface passes through
the origin, where the hero pod meets it; the target ship's lit bay door is at (BX, 0, 0), facing the pods.
Concept art only: nothing here goes into the game.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backdrop_kit as K  # noqa: E402
import backdrop_stretch as ST  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

A = K.ARGS
EFFECT = A.get('effect', 'a')
DIR = A.get('dir', os.path.join(K.SCRATCH, 'push_' + EFFECT))
NF = 84
RS = 150.0
BX = float(A.get('bx', 44.0))
X = np.array((1.0, 0.0, 0.0))
# pods: (contact y, contact z, frame of first contact). The first is the hero.
PODS = [(0.0, 0.0, 14), (15.0, 5.5, -12), (-12.0, -6.0, 40), (30.0, -3.0, 62)]
CFG = {'a': dict(Tp=28, pmax=7.0, v0=1.6, acc=0.20, stages='10,20,32,41,44,52', hero=40),
       'b': dict(Tp=22, pmax=2.2, v0=1.6, acc=0.32, stages='10,22,32,36,42,58', hero=37)}[EFFECT]


# ====================================================================== small helpers
def M(nt, op, a, b=None):
    """A math node; a and b are sockets or numbers. Returns the output socket."""
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


def val(nt, name, v=0.0):
    nd = nt.nodes.new('ShaderNodeValue')
    nd.name = name
    nd.outputs[0].default_value = v
    return nd.outputs[0]


def attr(nt, name):
    nd = nt.nodes.new('ShaderNodeAttribute')
    nd.attribute_name = name
    return nd.outputs['Fac']


def additive(nt, col_socket_or_rgb, strength):
    """Output = see-through + emission (light added over what is behind)."""
    em = nt.nodes.new('ShaderNodeEmission')
    if isinstance(col_socket_or_rgb, tuple):
        em.inputs['Color'].default_value = (*col_socket_or_rgb, 1)
    else:
        nt.links.new(col_socket_or_rgb, em.inputs['Color'])
    nt.links.new(strength, em.inputs['Strength'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(add.outputs[0], out.inputs['Surface'])


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    for nd in list(m.node_tree.nodes):
        m.node_tree.nodes.remove(nd)
    return m, m.node_tree


def curve_obj(k, lines, width, mat):
    """lines: [(Nx3 points, relative width)] -> one thin tapering curve object."""
    cu = bpy.data.curves.new(k.uid('Zap'), 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = width
    cu.bevel_resolution = 0
    for pts, wk in lines:
        pts = np.asarray(pts, dtype=np.float64)
        n = len(pts)
        sp = cu.splines.new('POLY')
        sp.points.add(n - 1)
        sp.points.foreach_set('co', np.concatenate([pts, np.ones((n, 1))], axis=1).ravel())
        sp.points.foreach_set('radius', [wk * (1.0 - 0.6 * i / (n - 1)) for i in range(n)])
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


# ====================================================================== pods
class Pod:
    """A boarding pod on its way through the shield. state(f) gives where it is and how fast."""

    def __init__(self, k, faction, cy, cz, fc, seed):
        self.k, self.faction, self.cy, self.cz, self.fc, self.seed = k, faction, cy, cz, fc, seed
        self.x0 = float(sphere_x(cy, cz))                 # where the shield is at this pod's lane
        self.fx = []
        root = bpy.data.objects.new(k.uid('Pod'), None)
        bpy.context.scene.collection.objects.link(root)
        root.rotation_mode = 'QUATERNION'
        self.root = root
        if faction == 'terran':
            hull = K.metal_mat('PodHull', (0.3, 0.34, 0.4), 0.35, 0.9)
            dark = K.metal_mat('PodDark', (0.05, 0.06, 0.07), 0.5, 0.9)
            glow = K.C.emit_mat('PodGlow', (0.15, 0.7, 1.0), 18.0)
            eng = K.C.emit_mat('PodEngine', (0.75, 0.93, 1.0), 45.0)
            sx = 3.0
        else:
            hull = K.metal_mat('APodHull', (0.85, 0.56, 0.2), 0.3, 1.0)
            dark = K.metal_mat('APodDark', (0.25, 0.13, 0.04), 0.4, 1.0)
            glow = K.C.emit_mat('APodGlow', (1.0, 0.6, 0.15), 16.0)
            eng = K.C.emit_mat('APodEngine', (1.0, 0.85, 0.55), 40.0)
            sx = 3.3
        self.sx, self.sr = sx, 1.15
        o = K.C.uv_sphere(k.uid('PodH'), 1.0, seg=(24, 12), mat=hull, scale=(sx, 1.15, 1.15))
        o.parent = root
        for dx, mat, w in ((0.62, dark, 0.12), (0.25, glow, 0.035), (-0.35, glow, 0.035), (-0.7, dark, 0.1)):
            rr = (1 - dx * dx) ** 0.5 * 1.06
            b = K.C.uv_sphere(k.uid('PodBand'), 1.0, seg=(24, 6), mat=mat, scale=(w, rr, rr))
            b.parent = o
            b.location = (dx, 0, 0)
        e = K.C.uv_sphere(k.uid('PodEng'), 1.0, seg=(12, 6), mat=eng, scale=(0.5, 0.6, 0.6))
        e.parent = root
        e.location = (-sx + 0.1, 0, 0)
        self.trails = []
        if faction == 'terran':
            for col, r, kk in (((0.08, 0.5, 1.0), 0.72, 5.0), ((0.03, 0.3, 1.0), 1.15, 1.0)):
                nm = k.uid('PodTrail')
                t = K.C.uv_sphere(nm, 1.0, seg=(16, 8), mat=K.glow_mat(nm + 'M', col, kk, 1.6), scale=(1, r, r))
                t.parent = root
                t.visible_shadow = False
                self.trails.append((t, r))
        else:
            nm = k.uid('PodTrail')
            t = K.C.uv_sphere(nm, 1.0, seg=(16, 8), mat=K.glow_mat(nm + 'M', (1.0, 0.6, 0.15), 3.0, 1.6),
                              scale=(1, 0.22, 0.22))
            t.parent = root
            t.visible_shadow = False
            self.trails.append((t, 0.22))
            self.zmat = K.C.emit_mat(k.uid('PodZapM'), (1.0, 0.72, 0.32), 13.0)

    def nose_x(self, f):
        """Nose position along +X relative to this lane's shield surface."""
        t = f - self.fc
        Tp, pmax, v0, acc = CFG['Tp'], CFG['pmax'], CFG['v0'], CFG['acc']
        if t < 0:
            return v0 * t
        if t <= Tp:
            return pmax * (1 - (1 - t / Tp) ** 2.4)
        u = t - Tp
        return pmax + 0.3 * u + 0.5 * acc * u * u

    def state(self, f):
        xn = self.nose_x(f)
        sp = xn - self.nose_x(f - 1)
        far = BX - self.x0 - CFG['pmax']
        kk = smooth((xn - CFG['pmax']) / far) if xn > CFG['pmax'] else 0.0     # after the shield: make for the bay
        y, z = self.cy * (1 - kk), self.cz * (1 - kk)
        return dict(xn=xn, speed=sp, nose=np.array((self.x0 + xn, y, z)), t=f - self.fc, gone=self.x0 + xn > BX - 1.5)

    def pose(self, f):
        for o in self.fx:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.curves.remove(d)
        self.fx = []
        s = self.state(f)
        s2 = self.state(f + 1)
        d = Vector(s2['nose'] - s['nose'])
        d = d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))
        hide = bool(s['gone'] or s['nose'][0] < -70)
        for o in [self.root] + list(self.root.children_recursive):
            o.hide_render = hide
        self.root.location = Vector(s['nose']) - d * self.sx
        self.root.rotation_quaternion = d.to_track_quat('X', 'Z')
        sp = min(1.9, max(0.02, s['speed']))
        for i, (t, r) in enumerate(self.trails):               # the trail is as long as the pod is fast
            L = (9.0 if i == 0 else 13.0) * sp * (0.6 if self.faction == 'arcadian' else 1.0) + 0.6
            t.scale = (L / 2, r * (0.55 + 0.45 * min(1.0, sp / 1.2)), r * (0.55 + 0.45 * min(1.0, sp / 1.2)))
            t.location = (-self.sx - L / 2 + 0.3, 0, 0)
        s['d'] = np.array(d)
        if self.faction == 'arcadian' and not hide:             # lightning for a trail
            rnd = random.Random(self.seed * 131 + f // 2)
            tail = s['nose'] - s['d'] * (2 * self.sx)
            lines = []
            for _ in range(3):
                L = (6.0 + 10.0 * sp) * rnd.uniform(0.6, 1.0)
                off = np.array([0.0, rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5)])
                end = tail - s['d'] * L + off * 2.5
                lines.append((jag(tail + off, end, rnd, 0.2, 4), 1.0))
            self.fx.append(curve_obj(self.k, lines, 0.06, self.zmat))
        return s

    def hull_pt(self, s, u, phi):
        """A point on the hull: u = -1 (tail) .. 1 (nose), phi round the axis."""
        d = s['d']
        e1 = np.cross(d, (0, 0, 1.0))
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(d, e1)
        c = s['nose'] - d * self.sx
        r = self.sr * 1.05 * math.sqrt(max(0.0, 1 - u * u))
        return c + d * (u * self.sx) + (e1 * math.cos(phi) + e2 * math.sin(phi)) * r


# ====================================================================== A: the Arcadian membrane
def hex_image():
    """A tileable picture of thin hexagon lines (one lattice period: w x 3a)."""
    W, H = 512, 887
    a = 1.0
    w = math.sqrt(3) * a
    yy, xx = np.mgrid[0:H, 0:W]
    px, py = (xx + 0.5) / W * w, (yy + 0.5) / H * 3 * a
    ds = []
    for cx, cy in [(i * w, j * 3 * a) for i in (-1, 0, 1, 2) for j in (-1, 0, 1, 2)] + \
                  [(i * w + w / 2, j * 3 * a + 1.5 * a) for i in (-2, -1, 0, 1) for j in (-2, -1, 0, 1)]:
        ds.append(np.hypot(px - cx, py - cy))
    ds = np.sort(np.stack(ds), axis=0)
    line = np.clip(1.0 - (ds[1] - ds[0]) / 0.07, 0, 1)
    path = os.path.join(K.SCRATCH, '_cache', 'hexlines.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray((line * 255).astype(np.uint8)).convert('RGB').save(path)
    return path


class Membrane:
    NR = 4                                                   # ring slots per pod (3 ripples + the snap)

    def __init__(self, k, pods):
        self.k, self.pods = k, pods
        step = 0.42
        ys = np.arange(-58, 78, step)
        zs = np.arange(-44, 44, step)
        Y, Z = np.meshgrid(ys, zs, indexing='ij')
        self.Y, self.Z = Y.ravel(), Z.ravel()
        self.X0 = sphere_x(self.Y, self.Z)
        ny, nz = len(ys), len(zs)
        idx = np.arange(ny * nz).reshape(ny, nz)
        faces = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], axis=-1).reshape(-1, 4)
        me = bpy.data.meshes.new('Membrane')
        me.from_pydata(np.stack([self.X0, self.Y, self.Z], axis=1).tolist(), [], faces.tolist())
        for p in me.polygons:
            p.use_smooth = True
        me.attributes.new('bk_dent', 'FLOAT', 'POINT')
        ob = bpy.data.objects.new('Membrane', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.visible_shadow = False
        self.ob, self.me = ob, me
        me.materials.append(self._material())
        self.zmat = K.C.emit_mat('MemZapM', (1.0, 0.72, 0.32), 13.0)
        self.fx = []
        self.lights = []
        for p in pods:
            L = k.light((p.x0 + 2, p.cy, p.cz), (1.0, 0.7, 0.35), 0.0, 1.0)
            self.lights.append(L)

    def _material(self):
        m, nt = new_mat('MembraneM')
        self.nt = nt
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Position'], sep.inputs[0])
        y, z = sep.outputs['Y'], sep.outputs['Z']
        # fine hexagon lines over the whole surface
        co = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(M(nt, 'DIVIDE', y, 2.6), co.inputs[0])
        nt.links.new(M(nt, 'DIVIDE', z, 2.6 * math.sqrt(3)), co.inputs[1])
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(hex_image())
        tex.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(co.outputs[0], tex.inputs['Vector'])
        hexl = tex.outputs['Color']
        lw = nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.35
        dent = attr(nt, 'bk_dent')
        total = M(nt, 'ADD', M(nt, 'MULTIPLY', lw.outputs['Facing'], 0.10), 0.012)
        total = M(nt, 'ADD', total, M(nt, 'MULTIPLY', dent, 0.5))
        hexk = M(nt, 'ADD', 0.16, M(nt, 'MULTIPLY', dent, 2.2))
        holes = None
        for i, p in enumerate(self.pods):
            dy, dz = M(nt, 'SUBTRACT', y, p.cy), M(nt, 'SUBTRACT', z, p.cz)
            r = M(nt, 'SQRT', M(nt, 'ADD', M(nt, 'MULTIPLY', dy, dy), M(nt, 'MULTIPLY', dz, dz)))
            for j in range(self.NR):                               # crisp rings: radius, half width, strength
                R, w, s = val(nt, f'R{i}_{j}', 1.0), val(nt, f'W{i}_{j}', 0.1), val(nt, f'S{i}_{j}', 0.0)
                band = M(nt, 'MAXIMUM', M(nt, 'SUBTRACT', 1.0, M(nt, 'DIVIDE', M(nt, 'ABSOLUTE', M(nt, 'SUBTRACT', r, R)), w)), 0.0)
                total = M(nt, 'ADD', total, M(nt, 'MULTIPLY', band, s))
            g, gw = val(nt, f'G{i}', 0.0), val(nt, f'GW{i}', 4.0)   # glow round the contact, lights the hexagons up
            rr = M(nt, 'DIVIDE', r, gw)
            gl = M(nt, 'MULTIPLY', g, M(nt, 'DIVIDE', 1.0, M(nt, 'ADD', 1.0, M(nt, 'MULTIPLY', rr, rr))))
            hexk = M(nt, 'ADD', hexk, gl)
            total = M(nt, 'ADD', total, M(nt, 'MULTIPLY', gl, 0.12))
            h = val(nt, f'H{i}', 0.0)                              # the hole: nothing inside, a hard bright rim
            rim = M(nt, 'MAXIMUM', M(nt, 'SUBTRACT', 1.0, M(nt, 'DIVIDE', M(nt, 'ABSOLUTE', M(nt, 'SUBTRACT', r, M(nt, 'ADD', h, 0.1))), 0.11)), 0.0)
            total = M(nt, 'ADD', total, M(nt, 'MULTIPLY', rim, val(nt, f'HS{i}', 0.0)))
            outside = M(nt, 'GREATER_THAN', r, h)
            holes = outside if holes is None else M(nt, 'MULTIPLY', holes, outside)
        total = M(nt, 'ADD', total, M(nt, 'MULTIPLY', hexl, hexk))
        r0 = M(nt, 'SQRT', M(nt, 'ADD', M(nt, 'MULTIPLY', y, y), M(nt, 'MULTIPLY', z, z)))
        mr = nt.nodes.new('ShaderNodeMapRange')                    # the patch fades out before its own edge
        mr.inputs[1].default_value, mr.inputs[2].default_value = 26.0, 44.0
        mr.inputs[3].default_value, mr.inputs[4].default_value = 1.0, 0.0
        nt.links.new(M(nt, 'ABSOLUTE', z), mr.inputs[0])
        total = M(nt, 'MULTIPLY', M(nt, 'MULTIPLY', total, holes), mr.outputs[0])
        del r0
        additive(nt, (1.0, 0.62, 0.22), M(nt, 'MULTIPLY', total, float(A.get('memk', 1.0))))
        return m

    def set(self, f, states):
        for o in self.fx:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.curves.remove(d)
        self.fx = []
        nd = self.nt.nodes
        Tp, pmax = CFG['Tp'], CFG['pmax']
        disp = np.zeros_like(self.X0)
        lines, iris = [], []
        for i, (p, s) in enumerate(zip(self.pods, states)):
            t = s['t']
            r = np.hypot(self.Y - p.cy, self.Z - p.cz)
            rings = [(1.0, 0.1, 0.0)] * self.NR
            g, h, hs, light = 0.0, 0.0, 0.0, 0.0
            rnd = random.Random(p.seed * 7919 + f // 2)
            if -4 <= t <= Tp:                                   # the push
                pp = max(0.0, s['xn'])
                d = pp / (1.0 + (r / 2.3) ** 2) ** 1.4
                near = r < p.sr * 0.98
                wrap = pp - p.sx * (1 - np.sqrt(np.clip(1 - (r / p.sr) ** 2, 0, 1))) + 0.06     # clings to the nose
                d = np.where(near, np.maximum(d, wrap), d)
                disp += d
                k_ = max(0.0, t) / Tp
                g = 1.0 + 7.0 * k_
                light = 3e3 * k_
                if t >= 0:
                    rings = []
                    for j in range(3):                          # precise ripples leaving the contact
                        age = (t - j * 6.0) % 18.0
                        rings.append((1.2 + 1.05 * age, 0.10, (2.0 + 4.0 * k_) * (1 - age / 18.0) ** 1.5))
                    rings.append((1.0, 0.1, 0.0))
                    # gold lightning converging on the contact along the membrane, and crawling over the pod
                    for _ in range(2 + int(3 * k_)):
                        a = rnd.uniform(0, 2 * math.pi)
                        R1 = rnd.uniform(7, 15)
                        rs = np.linspace(R1, 1.25, 26)
                        aa = a + np.cumsum(np.array([rnd.uniform(-1, 1) for _ in rs]) * 0.06)
                        xx = p.x0 + pp / (1.0 + (rs / 2.3) ** 2) ** 1.4 - 0.12
                        pts = np.stack([xx + sphere_x(p.cy + rs * np.cos(aa), p.cz + rs * np.sin(aa)) - p.x0,
                                        p.cy + rs * np.cos(aa), p.cz + rs * np.sin(aa)], axis=1)
                        lines.append((pts[::-1], 1.0))
                    for _ in range(1 + int(2 * k_)):
                        ph = rnd.uniform(0, 2 * math.pi)
                        us = np.linspace(0.9, rnd.uniform(-0.9, 0.0), 12)
                        pts = np.array([p.hull_pt(s, u, ph + 0.5 * math.sin(3 * u + ph) + rnd.uniform(-0.15, 0.15)) for u in us])
                        lines.append((pts, 0.7))
            elif t > Tp:                                        # punched through: snap back, hole, iris
                u = t - Tp
                d = pmax * math.exp(-u / 2.2) * math.cos(u * 0.85) / (1.0 + (r / 2.6) ** 2) ** 1.4
                disp += d
                h = 2.5 * smooth(u / 2.0) * (1 - smooth((u - 5.0) / 11.0))
                hs = 14.0 if h > 0.03 else 0.0
                g = 8.0 * math.exp(-u / 6.0)
                light = 9e3 * math.exp(-u / 3.0)
                rings = [(1.0, 0.1, 0.0)] * 3 + [(2.0 + 2.3 * u, 0.16 + 0.01 * u, 26.0 * max(0.0, 1 - u / 14.0) ** 1.3)]
                if 1 <= u <= 16 and h > 0.15:                   # the iris of arcs that closes the hole
                    nb = 9
                    for b in range(nb):
                        a0 = 2 * math.pi * b / nb + 0.22 * u
                        a1 = a0 + 2.0
                        rr0 = h + 1.6
                        e0 = np.array((p.x0 - 0.1, p.cy + rr0 * math.cos(a0), p.cz + rr0 * math.sin(a0)))
                        e1 = np.array((p.x0 - 0.1, p.cy + h * math.cos(a1), p.cz + h * math.sin(a1)))
                        iris.append((jag(e0, e1, rnd, 0.06, 3), 1.0))
            for j, (R, w, st) in enumerate(rings):
                nd[f'R{i}_{j}'].outputs[0].default_value = R
                nd[f'W{i}_{j}'].outputs[0].default_value = w
                nd[f'S{i}_{j}'].outputs[0].default_value = st
            nd[f'G{i}'].outputs[0].default_value = g
            nd[f'H{i}'].outputs[0].default_value = h
            nd[f'HS{i}'].outputs[0].default_value = hs
            self.lights[i].data.energy = light
            self.lights[i].location = Vector(s['nose']) + Vector((-1.5, 0, 0)) if t <= Tp else Vector((p.x0 - 1, p.cy, p.cz))
        co = np.stack([self.X0 + disp, self.Y, self.Z], axis=1)
        self.me.vertices.foreach_set('co', co.astype(np.float32).ravel())
        self.me.attributes['bk_dent'].data.foreach_set('value', np.clip(np.abs(disp) / CFG['pmax'], 0, 1).astype(np.float32))
        self.me.update()
        if lines:
            self.fx.append(curve_obj(self.k, lines, 0.05, self.zmat))
        if iris:
            self.fx.append(curve_obj(self.k, iris, 0.06, self.zmat))


# ====================================================================== B: the Terran triangle shield
def rodrigues(v, axis, ang):
    """Rotate vectors v (T, n, 3) round unit axes (T, 3) by angles (T,)."""
    c, s = np.cos(ang)[:, None, None], np.sin(ang)[:, None, None]
    ax = axis[:, None, :]
    return v * c + np.cross(ax, v) * s + ax * (v * ax).sum(-1, keepdims=True) * (1 - c)


class Triangles:
    EDGE = 2.6
    HOLE = 3.5

    def __init__(self, k, pods):
        self.k, self.pods = k, pods
        e = self.EDGE
        hgt = e * math.sqrt(3) / 2
        tris = []
        for j in range(-int(44 / hgt), int(44 / hgt)):
            for i in range(-int(58 / e) - 1, int(78 / e) + 1):
                x0 = i * e + (e / 2 if j % 2 else 0.0)
                a, b, c, d = (x0, j * hgt), (x0 + e, j * hgt), (x0 + e / 2, (j + 1) * hgt), (x0 + 1.5 * e, (j + 1) * hgt)
                tris.append((a, b, c))
                tris.append((b, d, c))
        t2 = np.array(tris)                                         # (T, 3, 2) in the (y, z) plane
        P = np.concatenate([sphere_x(t2[..., 0], t2[..., 1])[..., None], t2], axis=-1)
        cen = P.mean(axis=1)
        P = cen[:, None, :] + (P - cen[:, None, :]) * 0.93           # a gap between plates: each is its own piece
        rnd = np.random.default_rng(5)
        self.sets, extra = [], []
        n0 = len(P)
        for p in pods:                                              # plates that will break, and their replacements
            r = np.hypot(cen[:, 1] - p.cy, cen[:, 2] - p.cz)
            ids = np.where(r < self.HOLE)[0]
            order = ids[np.argsort(-r[ids] + 0.02 * np.arctan2(cen[ids, 2] - p.cz, cen[ids, 1] - p.cy))]
            self.sets.append(dict(ids=ids, order=order, rep=n0 + len(extra) + np.arange(len(order)),
                                  vel=rnd.uniform(-1, 1, (len(ids), 3)), ax=rnd.normal(size=(len(ids), 3)),
                                  om=rnd.uniform(0.18, 0.5, len(ids))))
            extra += list(order)
        self.P0 = np.concatenate([P, P[np.array(extra, dtype=int)]]) if extra else P
        self.n0 = n0
        self.cen = self.P0.mean(axis=1)
        T = len(self.P0)
        self.fill = np.where(rnd.random(T) < 0.14, rnd.uniform(0.3, 1.0, T), 0.06)
        me = bpy.data.meshes.new('TriShield')
        me.from_pydata(self.P0.reshape(-1, 3).tolist(), [], np.arange(T * 3).reshape(T, 3).tolist())
        uv = me.uv_layers.new(name='bary')
        uv.data.foreach_set('uv', np.tile(np.array([0, 0, 1, 0, 0, 1], dtype=np.float32), T))
        for nm in ('bk_flare', 'bk_fill'):
            me.attributes.new(nm, 'FLOAT', 'POINT')
        me.attributes['bk_fill'].data.foreach_set('value', np.repeat(self.fill, 3).astype(np.float32))
        ob = bpy.data.objects.new('TriShield', me)
        bpy.context.scene.collection.objects.link(ob)
        ob.visible_shadow = False
        self.ob, self.me = ob, me
        me.materials.append(self._material())
        self.zmat = K.C.emit_mat('TriZapM', (1.0, 0.72, 0.32), 13.0)
        self.smat = K.C.emit_mat('TriSparkM', (0.7, 0.9, 1.0), 30.0)
        self.fx = []
        self.lights = [k.light((p.x0 - 2, p.cy, p.cz), (0.6, 0.85, 1.0), 0.0, 1.0) for p in pods]

    def _material(self):
        m, nt = new_mat('TriShieldM')
        uv = nt.nodes.new('ShaderNodeUVMap')
        uv.uv_map = 'bary'
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(uv.outputs[0], sep.inputs[0])
        u, v = sep.outputs['X'], sep.outputs['Y']
        w = M(nt, 'SUBTRACT', M(nt, 'SUBTRACT', 1.0, u), v)
        edge = M(nt, 'MINIMUM', M(nt, 'MINIMUM', u, v), w)
        line = M(nt, 'MAXIMUM', M(nt, 'SUBTRACT', 1.0, M(nt, 'DIVIDE', edge, 0.035)), 0.0)
        flare, fill = attr(nt, 'bk_flare'), attr(nt, 'bk_fill')
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        sp = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Position'], sp.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs[1].default_value, mr.inputs[2].default_value = 26.0, 44.0
        mr.inputs[3].default_value, mr.inputs[4].default_value = 1.0, 0.0
        nt.links.new(M(nt, 'ABSOLUTE', sp.outputs['Z']), mr.inputs[0])
        st = M(nt, 'ADD', M(nt, 'MULTIPLY', line, M(nt, 'ADD', 0.55, M(nt, 'MULTIPLY', flare, 7.0))),
               M(nt, 'ADD', M(nt, 'MULTIPLY', fill, 0.16), M(nt, 'MULTIPLY', flare, 1.6)))
        st = M(nt, 'MULTIPLY', M(nt, 'MULTIPLY', st, mr.outputs[0]), float(A.get('trik', 1.0)))
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.inputs[6].default_value = (0.08, 0.42, 1.0, 1)
        mix.inputs[7].default_value = (0.75, 0.92, 1.0, 1)
        nt.links.new(M(nt, 'MINIMUM', M(nt, 'MULTIPLY', flare, 0.6), 1.0), mix.inputs[0])
        additive(nt, mix.outputs[2], st)
        return m

    def set(self, f, states):
        for o in self.fx:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.curves.remove(d)
        self.fx = []
        Tp, pmax = CFG['Tp'], CFG['pmax']
        T = len(self.P0)
        off = np.zeros((T, 3))
        ang = np.zeros(T)
        axis = np.tile(np.array((0.0, 0.0, 1.0)), (T, 1))
        pivot = self.cen.copy()
        scale = np.ones(T)
        scale[self.n0:] = 0.0
        flare = np.zeros(T)
        zaps, sparks = [], []
        for i, (p, s, st) in enumerate(zip(self.pods, states, self.sets)):
            t = s['t']
            r = np.hypot(self.cen[:, 1] - p.cy, self.cen[:, 2] - p.cz)
            rnd = random.Random(p.seed * 7919 + f // 2)
            light = 0.0
            if t < -3:
                continue
            tc = float(Tp)
            # build-up: the plates under the nose flex in and flare, ripples run out through the neighbours
            push = min(max(0.0, s['xn']), pmax) if t <= tc else pmax * math.exp(-(t - tc) / 3.0)
            k_ = min(1.0, max(0.0, t) / tc)
            off[:, 0] += push * np.exp(-(r / 2.7) ** 2)
            if t <= tc + 4:
                flare += (0.3 + 2.2 * k_ ** 1.5) * np.exp(-(r / (2.2 + 2.0 * k_)) ** 2) * (1.0 if t <= tc else math.exp(-(t - tc) / 2.0))
            if 0 <= t <= tc:
                for j in range(4):
                    age = t - j * 5.5
                    if age > 0:
                        R = 1.1 * age
                        band = np.clip(1 - np.abs(r - R) / 1.6, 0, 1) * 0.9 * math.exp(-R / 9.0) * (0.5 + k_)
                        flare += band
                        off[:, 0] += 0.35 * band
                light = 2e3 * k_
                for _ in range(1 + int(3 * k_)):                    # the pod's lightning licking the plates
                    a = rnd.uniform(0, 2 * math.pi)
                    R1 = rnd.uniform(2.5, 6.5)
                    tip = s['nose'] - s['d'] * rnd.uniform(0.2, 1.5)
                    end = np.array((p.x0 - 0.1 + sphere_x(p.cy + R1 * math.cos(a), p.cz + R1 * math.sin(a)) - p.x0,
                                    p.cy + R1 * math.cos(a), p.cz + R1 * math.sin(a)))
                    zaps.append((jag(tip, end, rnd, 0.2, 4), 1.0))
            if t > tc:
                u = t - tc
                R = 1.7 * u                                         # the shock through the neighbours
                band = np.clip(1 - np.abs(r - R) / 2.6, 0, 1) * 2.6 * math.exp(-R / 15.0)
                flare += band
                off[:, 0] += 0.5 * band
                light = 2.5e4 * math.exp(-u / 2.5)
                ids = st['ids']                                     # the broken plates tumble away as shards
                us = u - 0.5 * r[ids]
                live = us > 0
                uu = np.clip(us, 0, None)
                rad = np.stack([np.zeros(len(ids)), self.cen[ids, 1] - p.cy, self.cen[ids, 2] - p.cz], axis=1)
                rad /= (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-6)
                vel = X * (0.55 + 0.35 * (st['vel'][:, :1] + 1)) + rad * (0.22 + 0.2 * (st['vel'][:, 1:2] + 1)) + st['vel'] * 0.08
                off[ids] += vel * (uu * np.exp(-uu / 40.0))[:, None]
                ax = st['ax'] / np.linalg.norm(st['ax'], axis=1, keepdims=True)
                axis[ids] = ax
                ang[ids] = st['om'] * uu
                scale[ids] = np.where(live, np.clip(1.25 - uu / 22.0, 0, 1), 1.0)
                flare[ids] += np.where(live, 3.0 * np.exp(-uu / 5.0) + 0.3, 0.0)
                if u < 7:                                           # white-blue sparks thrown from the break
                    for _ in range(7):
                        a = rnd.uniform(0, 2 * math.pi)
                        dr = np.array((rnd.uniform(0.1, 1.0), math.cos(a), math.sin(a)))
                        c0 = np.array((p.x0 + 0.5, p.cy, p.cz))
                        r0, r1 = 1.0 + u * rnd.uniform(0.6, 1.3), 2.6 + u * rnd.uniform(1.2, 1.9)
                        sparks.append((np.array([c0 + dr * r0, c0 + dr * r1]), 1.0))
                # replacements flip in one by one, hinged on an edge
                tr0 = 14.0
                for jx, (orig, rep) in enumerate(zip(st['order'], st['rep'])):
                    e_ = (u - tr0 - 1.3 * jx) / 5.0
                    if e_ <= 0:
                        continue
                    e_ = min(1.0, e_)
                    scale[rep] = 1.0
                    pv = self.P0[rep, 0]
                    hx = self.P0[rep, 1] - pv
                    axis[rep] = hx / np.linalg.norm(hx)
                    pivot[rep] = pv
                    ang[rep] = 2.1 * (1 - e_) ** 2 * (1 if jx % 2 else -1)
                    flare[rep] += 2.2 * (1 - e_) + 1.6 * math.exp(-max(0.0, u - tr0 - 1.3 * jx - 5.0) / 3.0) * (e_ >= 1.0)
            self.lights[i].data.energy = light
        cen = self.cen
        rel = (self.P0 - cen[:, None, :]) * scale[:, None, None] + (cen - pivot)[:, None, :]
        Pn = pivot[:, None, :] + rodrigues(rel, axis, ang) + off[:, None, :]
        self.me.vertices.foreach_set('co', Pn.reshape(-1, 3).astype(np.float32).ravel())
        self.me.attributes['bk_flare'].data.foreach_set('value', np.repeat(flare, 3).astype(np.float32))
        self.me.update()
        if zaps:
            self.fx.append(curve_obj(self.k, zaps, 0.07, self.zmat))
        if sparks:
            self.fx.append(curve_obj(self.k, sparks, 0.06, self.smat))


# ====================================================================== the scene
def place_ship(ob, local_pt, local_n, world_pt, tilt):
    """Turn the ship so its local direction local_n faces the pods (-X) and local_pt sits at world_pt."""
    q = Quaternion((1, 0, 0), math.radians(tilt)) @ Vector(local_n).normalized().rotation_difference(Vector((-1, 0, 0)))
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = q
    ob.location = Vector(world_pt) - q @ (Vector(local_pt) * ob.scale.x)
    bpy.context.view_layer.update()


def build():
    k = K.Kit(sun_dir=(0.5, 0.6, -0.5), sun_energy=5.0, planet=False, rim_dir=(-0.6, -0.6, 0.2), rim=1.6,
              fill_dir=(0.3, 1, -0.2), fill=2.0, tint='teal' if EFFECT == 'a' else 'blue', nebula=1.5)
    bpy.context.scene.frame_end = NF
    cp = [float(v) for v in A.get('cam', '-15,-27,8').split(',')]
    ct = [float(v) for v in A.get('tgt', '10,3,-1').split(',')]
    k.camera(cp, ct, lens=float(A.get('lens', 26)))
    if EFFECT == 'a':
        sh = k.ship('crescent', scale=2.0)
        a_deg, r = 238, 2.6
        a = math.radians(a_deg)
        rad = 0.35 + 5.2 * math.sin(math.pi * (a_deg - 36) / 288.0) ** 0.9
        n = Vector((math.cos(a), math.sin(a) * 1.12, 0)).normalized()
        c = Vector((17 * math.cos(a) * 1.12, 17 * math.sin(a), 0)) + n * (rad * 0.92)
        K.arcadian_bay(k, sh, c, n, r)
        place_ship(sh, c + n * 0.7, n, (BX, 0, 0), float(A.get('tilt', 22)))
        pods = [Pod(k, 'terran', cy, cz, fc, 11 + i) for i, (cy, cz, fc) in enumerate(PODS)]
        shield = Membrane(k, pods)
    else:
        sh = k.ship('dread', scale=2.2)
        bays = sorted([b for b in k.extra('dread') if b.y > 0], key=lambda b: b.x)
        for b in bays:
            K.terran_bay(k, sh, b, 1)
        b = bays[len(bays) // 2]
        place_ship(sh, b + Vector((0, 0.3, 0)), (0, 1, 0), (BX, 0, 0), float(A.get('tilt', 14)))
        pods = [Pod(k, 'arcadian', cy, cz, fc, 11 + i) for i, (cy, cz, fc) in enumerate(PODS)]
        shield = Triangles(k, pods)
    return k, pods, shield


def pose(pods, shield, f):
    shield.set(f, [p.pose(f) for p in pods])


def render(k, f, out, res, samples):
    sc = bpy.context.scene
    k.sh.render_settings(res, samples, blur=False)
    sc.cycles.adaptive_threshold = 0.05 if samples > 20 else 0.08
    sc.cycles.transparent_max_bounces = 24
    sc.cycles.max_bounces = 4
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = int(A.get('threads', 3))
    sc.render.use_persistent_data = A.get('persist', '1') == '1'     # keep the ship and the sky between frames
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.frame_set(f)
    raw = os.path.splitext(out)[0] + '_raw.png'
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    im = K.post(raw, 1.0, 0.2)
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
    pip = (255, 205, 110) if EFFECT == 'a' else (120, 200, 255)
    for i, im in enumerate(ims):
        x, y = g + (i % cols) * (w + g), g + (i // cols) * (h + g)
        sh.paste(im, (x, y))
        for j in range(i + 1):
            dr.rectangle((x + 22 + j * 20, y + h - 34, x + 22 + j * 20 + 11, y + h - 23), fill=pip)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sh.save(out, quality=92)
    print('WROTE', out, sh.size, flush=True)


STAGES = [int(v) for v in A.get('stage_frames', CFG['stages']).split(',')]
if A.get('sheet') == '1':
    sheet(A['out'], len(STAGES))
else:
    os.makedirs(DIR, exist_ok=True)
    k, pods, shield = build()
    if A.get('clip') == '1':
        for f in range(int(A.get('f0', 1)), int(A.get('f1', NF)) + 1, int(A.get('step', 1))):
            o = os.path.join(DIR, f'f_{f:04d}.jpg')
            if os.path.exists(o):
                continue
            pose(pods, shield, f)
            render(k, f, o, tuple(int(v) for v in A.get('clipres', '960x540').split('x')), int(A.get('samples', 12)))
    elif A.get('stages') == '1':
        for i, f in enumerate(STAGES):
            pose(pods, shield, f)
            render(k, f, os.path.join(DIR, f'stage_{i + 1}.jpg'), (1280, 720) if K.FINAL else (960, 540),
                   int(A.get('samples', 36 if K.FINAL else 12)))
    else:
        f = int(A.get('frame', CFG['hero']))
        pose(pods, shield, f)
        render(k, f, A.get('out', os.path.join(DIR, f'test_{f:03d}.jpg')), (1920, 1080) if K.FINAL else (960, 540),
               int(A.get('samples', 48 if K.FINAL else 12)))
