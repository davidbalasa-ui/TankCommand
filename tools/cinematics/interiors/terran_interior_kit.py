"""Shared kit for the Terran capital-ship interior concept stills (design work only, never in the game).

Batched geometry (boxes / prisms / cylinders collected per material and turned into one mesh each),
Terran materials (panelled gunmetal, neon blue / cyan / orange emitters, deck paint, glass), the
triangle force field, tank import, scene / render setup, a cheap depth pass and the 2D post
(bloom + depth haze + vignette).

Units are metres, +Z up. Used by terran_hangar.py, terran_deck.py, terran_bridge.py, terran_reactor.py.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from PIL import Image, ImageFilter

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
MODELS = os.path.join(REPO, 'public', 'assets', 'models')

BUF = {}          # (material name, smooth) -> [verts list, faces list]
NOFOG = []        # objects hidden in the depth pass (shields, glass)

NEON = (0.03, 0.28, 1.0)
CYAN = (0.15, 0.85, 1.0)
ORANGE = (1.0, 0.42, 0.06)


# ------------------------------------------------------------------ geometry batching
def _buf(mat, smooth=False):
    return BUF.setdefault((mat, smooth), [[], []])


def _rot(rot):
    if rot is None:
        return None
    if isinstance(rot, (int, float)):
        rot = (0, 0, rot)
    return Euler([math.radians(a) for a in rot]).to_matrix()


def add(mat, verts, faces, smooth=False):
    vs, fs = _buf(mat, smooth)
    n = len(vs)
    vs.extend(verts)
    fs.extend([tuple(i + n for i in f) for f in faces])


_BOXF = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


def box(mat, c, s, rot=None, taper=None):
    """Box centred at c with full size s. rot = degrees about Z or (rx, ry, rz). taper = (tx, ty)
    scale of the top face."""
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    R = _rot(rot)
    vs = []
    for iz in (0, 1):
        for iy in (0, 1):
            for ix in (0, 1):
                tx, ty = (taper if (taper and iz) else (1, 1))
                v = Vector(((ix * 2 - 1) * hx * tx, (iy * 2 - 1) * hy * ty, (iz * 2 - 1) * hz))
                if R:
                    v = R @ v
                vs.append((v.x + c[0], v.y + c[1], v.z + c[2]))
    add(mat, vs, _BOXF)


def box2(mat, lo, hi):
    """Axis-aligned box from two corners."""
    box(mat, [(a + b) / 2 for a, b in zip(lo, hi)], [abs(b - a) for a, b in zip(lo, hi)])


def loft(mat, r0, r1, caps=True, smooth=False):
    n = len(r0)
    vs = list(r0) + list(r1)
    fs = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    if caps:
        fs.append(tuple(reversed(range(n))))
        fs.append(tuple(range(n, 2 * n)))
    add(mat, vs, fs, smooth)


def prism(mat, pts, a0, a1, axis='y'):
    """2D profile extruded along an axis. axis 'y': pts are (x, z); 'z': (x, y); 'x': (y, z)."""
    def p3(p, a):
        if axis == 'y':
            return (p[0], a, p[1])
        if axis == 'z':
            return (p[0], p[1], a)
        return (a, p[0], p[1])
    loft(mat, [p3(p, a0) for p in pts], [p3(p, a1) for p in pts])


def cyl(mat, p0, p1, r, n=16, r1=None, caps=True, smooth=True):
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0).normalized()
    a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(a).normalized()
    v = d.cross(u)
    r1 = r if r1 is None else r1
    ring = lambda p, rr: [tuple(p + (u * math.cos(t) + v * math.sin(t)) * rr)
                          for t in [2 * math.pi * i / n for i in range(n)]]
    loft(mat, ring(p0, r), ring(p1, r1), caps, smooth)


def pipe(mat, pts, r, n=10):
    """Polyline pipe with ball-ish joints (short overlapping cylinders)."""
    for a, b in zip(pts[:-1], pts[1:]):
        cyl(mat, a, b, r, n)
    for p in pts[1:-1]:
        cyl(mat, (p[0], p[1], p[2] - r), (p[0], p[1], p[2] + r), r * 1.25, n)


def flush(prefix='Geo'):
    """Turn every batch into a mesh object. Returns the objects."""
    out = []
    for (mname, smooth), (vs, fs) in list(BUF.items()):
        if not vs:
            continue
        me = bpy.data.meshes.new(f'{prefix}_{mname}')
        me.from_pydata(vs, [], fs)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        me.materials.append(mat(mname))
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        if mname.startswith(('glass', 'holo')):
            NOFOG.append(ob)
        if mname.startswith('holo'):
            ob.visible_shadow = False
        out.append(ob)
    BUF.clear()
    return out


# ------------------------------------------------------------------ materials
class NT:
    """Tiny node-tree helper."""

    def __init__(self, m):
        m.use_nodes = True
        self.t = m.node_tree
        self.t.nodes.clear()

    def n(self, kind, **kw):
        nd = self.t.nodes.new(kind)
        for k, v in kw.items():
            if hasattr(nd, k):
                setattr(nd, k, v)
            else:
                sock = nd.inputs[int(k[1:])] if k.startswith('i') and k[1:].isdigit() else nd.inputs[k]
                if hasattr(v, 'links') or hasattr(v, 'is_linked'):
                    self.t.links.new(v, sock)
                else:
                    sock.default_value = v
        return nd

    def link(self, a, b):
        self.t.links.new(a, b)

    def m(self, op, a, b=None, c=None, clamp=False):
        nd = self.t.nodes.new('ShaderNodeMath')
        nd.operation = op
        nd.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.t.links.new(v, nd.inputs[i])
        return nd.outputs[0]

    def vm(self, op, a, b=None):
        nd = self.t.nodes.new('ShaderNodeVectorMath')
        nd.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                nd.inputs[i].default_value = v
            else:
                self.t.links.new(v, nd.inputs[i])
        return nd


def _panel(name, base, rough=0.42, metal=0.9, S=4.0, w=0.035, var=0.35, line=0.75, fine=0.25, bump=0.5,
           spec=0.5, coat=0.0, scuff=0.5, bolts=True):
    """Gunmetal plating in world space: a panel grid (cut lines darkened and recessed, every panel
    its own shade, some panels standing proud), irregular sub-panels, bolt heads at the panel
    corners, chipped bright wear along the cut lines and directional scuffing in colour/roughness."""
    m = bpy.data.materials.new(name)
    t = NT(m)
    geo = t.n('ShaderNodeNewGeometry')
    nsc = t.vm('SCALE', geo.outputs['True Normal'])
    nsc.inputs['Scale'].default_value = 0.03
    pos = t.vm('SUBTRACT', geo.outputs['Position'], nsc.outputs[0])
    P = pos.outputs[0]
    sp = t.n('ShaderNodeSeparateXYZ')
    t.link(P, sp.inputs[0])
    sn = t.n('ShaderNodeSeparateXYZ')
    t.link(geo.outputs['True Normal'], sn.inputs[0])
    perp = [t.m('GREATER_THAN', t.m('ABSOLUTE', sn.outputs[i]), 0.7) for i in range(3)]
    inpl = [t.m('SUBTRACT', 1.0, perp[i]) for i in range(3)]

    def terms(scale, offs=(0.0, 0.0, 0.0)):       # distance (m) to the nearest grid line, per axis
        out = []
        for i in range(3):
            f = t.m('FRACT', t.m('ADD', t.m('DIVIDE', sp.outputs[i], scale), offs[i]))
            out.append(t.m('MULTIPLY', t.m('SUBTRACT', 0.5, t.m('ABSOLUTE', t.m('SUBTRACT', f, 0.5))), scale))
        return out

    def band(T, lo, hi):
        acc = None
        for i in range(3):
            v = t.m('MULTIPLY', t.m('LESS_THAN', T[i], hi), inpl[i])
            if lo > 0:
                v = t.m('MULTIPLY', v, t.m('GREATER_THAN', T[i], lo))
            acc = v if acc is None else t.m('MAXIMUM', acc, v)
        return acc

    T1 = terms(S)
    T2 = terms(S * fine, (0.37, 0.37, 0.37))
    L1 = band(T1, 0, w)
    cell = t.vm('FLOOR', t.vm('DIVIDE', P, (S, S, S)).outputs[0]).outputs[0]
    wn = t.n('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
    t.link(cell, wn.inputs['Vector'])
    rnd = wn.outputs['Value']
    L2 = t.m('MULTIPLY', band(T2, 0, w * 0.5), t.m('GREATER_THAN', rnd, 0.35))
    cell2 = t.vm('FLOOR', t.vm('DIVIDE', P, (S * fine,) * 3).outputs[0]).outputs[0]
    wn2 = t.n('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
    t.link(cell2, wn2.inputs['Vector'])
    noise = t.n('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 0.6
    noise.inputs['Detail'].default_value = 6.0
    t.link(P, noise.inputs['Vector'])
    stretch = t.vm('MULTIPLY', P, (0.35, 3.0, 3.0))
    sc = t.n('ShaderNodeTexNoise')
    sc.inputs['Scale'].default_value = 1.6
    sc.inputs['Detail'].default_value = 8.0
    sc.inputs['Roughness'].default_value = 0.7
    t.link(stretch.outputs[0], sc.inputs['Vector'])
    scf = t.m('SUBTRACT', sc.outputs[0], 0.5)
    shade = t.m('ADD', 1.0 - var / 2, t.m('MULTIPLY', rnd, var))
    shade = t.m('MULTIPLY', shade, t.m('ADD', 0.9, t.m('MULTIPLY', wn2.outputs['Value'], 0.2)))
    shade = t.m('MULTIPLY', shade, t.m('ADD', 1.0, t.m('MULTIPLY', scf, 0.9 * scuff)))
    shade = t.m('MULTIPLY', shade, t.m('SUBTRACT', 1.0, t.m('MULTIPLY', L1, line)))
    shade = t.m('MULTIPLY', shade, t.m('SUBTRACT', 1.0, t.m('MULTIPLY', L2, line * 0.5)))
    # chipped wear next to the cut lines and bolt heads
    wear = t.m('MULTIPLY', band(T1, w, w + 0.06), t.m('GREATER_THAN', noise.outputs[0], 0.52))
    extra = t.m('MULTIPLY', wear, 1.6)
    bolt = None
    if bolts:
        for i in range(3):
            v = t.m('MAXIMUM', t.m('LESS_THAN', t.m('ABSOLUTE', t.m('SUBTRACT', T1[i], w + 0.2)), 0.045), perp[i])
            bolt = v if bolt is None else t.m('MULTIPLY', bolt, v)
        extra = t.m('ADD', extra, t.m('MULTIPLY', bolt, 1.2))
    shade = t.m('MULTIPLY', shade, t.m('ADD', 1.0, extra))
    col = t.vm('SCALE', (*base[:3],))
    col.inputs[0].default_value = base[:3]
    t.link(shade, col.inputs['Scale'])
    bs = t.n('ShaderNodeBsdfPrincipled')
    t.link(col.outputs[0], bs.inputs['Base Color'])
    bs.inputs['Metallic'].default_value = metal
    r = t.m('ADD', rough - 0.12, t.m('MULTIPLY', noise.outputs[0], 0.24))
    r = t.m('ADD', r, t.m('MULTIPLY', t.m('SUBTRACT', rnd, 0.5), 0.12))
    r = t.m('ADD', r, t.m('MULTIPLY', scf, 0.5 * scuff), clamp=True)
    t.link(r, bs.inputs['Roughness'])
    if coat:
        bs.inputs['Coat Weight'].default_value = coat
    h = t.m('SUBTRACT', t.m('MULTIPLY', t.m('GREATER_THAN', rnd, 0.62), 0.5), t.m('ADD', L1, t.m('MULTIPLY', L2, 0.4)))
    if bolts:
        h = t.m('ADD', h, t.m('MULTIPLY', bolt, 0.6))
    bp = t.n('ShaderNodeBump')
    bp.inputs['Strength'].default_value = bump
    bp.inputs['Distance'].default_value = 0.08
    t.link(h, bp.inputs['Height'])
    t.link(bp.outputs[0], bs.inputs['Normal'])
    out = t.n('ShaderNodeOutputMaterial')
    t.link(bs.outputs[0], out.inputs[0])
    return m


def _plain(name, col, rough=0.5, metal=0.0, emit=None, estr=0.0):
    m = bpy.data.materials.new(name)
    t = NT(m)
    bs = t.n('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (*col, 1)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    if emit:
        bs.inputs['Emission Color'].default_value = (*emit, 1)
        bs.inputs['Emission Strength'].default_value = estr
    out = t.n('ShaderNodeOutputMaterial')
    t.link(bs.outputs[0], out.inputs[0])
    return m


def _emit(name, col, strength):
    m = bpy.data.materials.new(name)
    t = NT(m)
    em = t.n('ShaderNodeEmission')
    em.inputs[0].default_value = (*col, 1)
    em.inputs[1].default_value = strength
    t.link(em.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
    return m


def _holo(name, col, strength, alpha):
    m = bpy.data.materials.new(name)
    t = NT(m)
    em = t.n('ShaderNodeEmission')
    em.inputs[0].default_value = (*col, 1)
    em.inputs[1].default_value = strength
    mix = t.n('ShaderNodeMixShader')
    mix.inputs[0].default_value = alpha
    t.link(t.n('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
    t.link(em.outputs[0], mix.inputs[2])
    t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
    return m


def _glass(name, tint=(0.55, 0.75, 1.0), alpha=0.12):
    m = bpy.data.materials.new(name)
    t = NT(m)
    gl = t.n('ShaderNodeBsdfGlossy')
    gl.inputs['Color'].default_value = (*tint, 1)
    gl.inputs['Roughness'].default_value = 0.05
    tr = t.n('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (0.9, 0.95, 1.0, 1)
    mix = t.n('ShaderNodeMixShader')
    mix.inputs[0].default_value = alpha
    t.link(tr.outputs[0], mix.inputs[1])
    t.link(gl.outputs[0], mix.inputs[2])
    t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
    return m


def _stripes(name, a, b, S=1.2):
    """Diagonal hazard stripes in world XY (+ a little Z so walls get them too)."""
    m = bpy.data.materials.new(name)
    t = NT(m)
    geo = t.n('ShaderNodeNewGeometry')
    sp = t.n('ShaderNodeSeparateXYZ')
    t.link(geo.outputs['Position'], sp.inputs[0])
    s = t.m('ADD', t.m('ADD', sp.outputs[0], sp.outputs[1]), sp.outputs[2])
    f = t.m('GREATER_THAN', t.m('FRACT', t.m('DIVIDE', s, S)), 0.5)
    mx = t.n('ShaderNodeMix', data_type='RGBA')
    t.link(f, mx.inputs[0])
    mx.inputs[6].default_value = (*a, 1)
    mx.inputs[7].default_value = (*b, 1)
    bs = t.n('ShaderNodeBsdfPrincipled')
    t.link(mx.outputs[2], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.55
    t.link(bs.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
    return m


E = dict(neon=1.0, cyan=1.0, orange=1.0, white=1.0)     # per-scene emitter gain (set before first use)

MATDEF = {
    'hull': lambda n: _panel(n, (0.045, 0.05, 0.06), rough=0.42, S=4.0),
    'hull_big': lambda n: _panel(n, (0.04, 0.045, 0.055), rough=0.45, S=8.0, w=0.06, fine=0.25),
    'hull_lt': lambda n: _panel(n, (0.11, 0.12, 0.14), rough=0.4, S=3.0),
    'armor': lambda n: _panel(n, (0.022, 0.025, 0.032), rough=0.36, S=2.5, var=0.5),
    'floor': lambda n: _panel(n, (0.075, 0.082, 0.095), rough=0.34, S=4.0, w=0.04, var=0.3, metal=0.85, fine=0.5,
                              scuff=1.0),
    'floor_dk': lambda n: _panel(n, (0.035, 0.04, 0.048), rough=0.3, S=2.0, w=0.03, var=0.4, metal=0.85, fine=0.5),
    'floor_lt': lambda n: _panel(n, (0.16, 0.175, 0.2), rough=0.42, S=4.0, w=0.045, var=0.22, metal=0.6, fine=0.5,
                                 line=0.8),
    'walltop': lambda n: _panel(n, (0.012, 0.014, 0.018), rough=0.5, S=3.0, w=0.05, var=0.4, metal=0.8),
    'steel': lambda n: _plain(n, (0.2, 0.21, 0.23), rough=0.35, metal=1.0),
    'dark': lambda n: _plain(n, (0.012, 0.013, 0.016), rough=0.5, metal=0.8),
    'rubber': lambda n: _plain(n, (0.01, 0.01, 0.011), rough=0.8),
    'paint_w': lambda n: _plain(n, (0.55, 0.58, 0.62), rough=0.55),
    'paint_y': lambda n: _plain(n, (0.75, 0.42, 0.03), rough=0.55),
    'paint_b': lambda n: _plain(n, (0.03, 0.16, 0.45), rough=0.5, emit=NEON, estr=0.15),
    'hazard': lambda n: _stripes(n, (0.75, 0.42, 0.03), (0.012, 0.012, 0.014)),
    'crate': lambda n: _panel(n, (0.09, 0.1, 0.11), rough=0.5, S=1.3, w=0.03, var=0.5, metal=0.6),
    'crate_b': lambda n: _panel(n, (0.03, 0.09, 0.2), rough=0.5, S=1.3, w=0.03, var=0.5, metal=0.5),
    'crate_o': lambda n: _panel(n, (0.35, 0.16, 0.03), rough=0.55, S=1.3, w=0.03, var=0.4, metal=0.3),
    'neon': lambda n: _emit(n, NEON, 4.5 * E['neon']),
    'neon_dim': lambda n: _emit(n, NEON, 2.2 * E['neon']),
    'cyan': lambda n: _emit(n, CYAN, 6.0 * E['cyan']),
    'cyan_hot': lambda n: _emit(n, (0.3, 0.9, 1.0), 16.0 * E['cyan']),
    'orange': lambda n: _emit(n, ORANGE, 14.0 * E['orange']),
    'white': lambda n: _emit(n, (0.72, 0.85, 1.0), 5.0 * E['white']),
    'white_dim': lambda n: _emit(n, (0.72, 0.85, 1.0), 2.5 * E['white']),
    'screen': lambda n: _emit(n, (0.1, 0.5, 1.0), 2.2),
    'screen_c': lambda n: _emit(n, (0.2, 0.9, 1.0), 2.6),
    'screen_o': lambda n: _emit(n, ORANGE, 2.6),
    'screen_bg': lambda n: _plain(n, (0.004, 0.01, 0.02), rough=0.15, emit=(0.02, 0.12, 0.3), estr=0.35),
    'glass': lambda n: _glass(n),
    'holo': lambda n: _holo(n, CYAN, 5.0, 0.35),
    'holo_b': lambda n: _holo(n, NEON, 4.0, 0.22),
    'holo_o': lambda n: _holo(n, ORANGE, 6.0, 0.6),
}


def mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    return MATDEF[name](name)


# ------------------------------------------------------------------ force field (triangles)
def force_field(name, origin, u, v, w, h, tri=2.2, inside=None, strength=5.0, edge=14.0, gap=0.1,
                seed=1, alpha=(0.1, 0.5), col=None):
    """Translucent blue field of equilateral triangles in the plane origin + a*u + b*v (0..w, 0..h).
    Every triangle has its own brightness, plus a bright rim. inside(a, b) clips the outline."""
    rnd = random.Random(seed)
    o, u, v = Vector(origin), Vector(u).normalized(), Vector(v).normalized()
    hh = tri * math.sqrt(3) / 2
    fv, ff, fr, ev, ef = [], [], [], [], []
    rows = int(math.ceil(h / hh))
    cols = int(math.ceil(w / (tri / 2))) + 1
    for r in range(rows):
        for c in range(-1, cols):
            up = (r + c) % 2 == 0
            x0 = c * tri / 2
            if up:
                t3 = [(x0, r * hh), (x0 + tri, r * hh), (x0 + tri / 2, (r + 1) * hh)]
            else:
                t3 = [(x0, (r + 1) * hh), (x0 + tri / 2, r * hh), (x0 + tri, (r + 1) * hh)]
            cx = sum(p[0] for p in t3) / 3
            cy = sum(p[1] for p in t3) / 3
            if not (0 <= cx <= w and 0 <= cy <= h) or (inside and not inside(cx, cy)):
                continue
            t3 = [(min(max(a, 0), w), min(max(b, 0), h)) for a, b in t3]
            inner = [(cx + (a - cx) * (1 - gap), cy + (b - cy) * (1 - gap)) for a, b in t3]
            n = len(fv)
            fv += [tuple(o + u * a + v * b) for a, b in inner]
            ff.append((n, n + 1, n + 2))
            fr.append(rnd.random() ** 1.6)
            n = len(ev)
            ev += [tuple(o + u * a + v * b) for a, b in t3 + inner]
            ef += [(n + i, n + (i + 1) % 3, n + 3 + (i + 1) % 3, n + 3 + i) for i in range(3)]
    col = col or NEON
    objs = []
    me = bpy.data.meshes.new(name + '_faces')
    me.from_pydata(fv, [], ff)
    at = me.attributes.new('r', 'FLOAT', 'FACE')
    at.data.foreach_set('value', fr)
    m = bpy.data.materials.new(name + '_face')
    t = NT(m)
    a = t.n('ShaderNodeAttribute', attribute_name='r')
    em = t.n('ShaderNodeEmission')
    em.inputs[0].default_value = (*col, 1)
    t.link(t.m('MULTIPLY', t.m('ADD', 0.35, a.outputs['Fac']), strength), em.inputs[1])
    mix = t.n('ShaderNodeMixShader')
    t.link(t.m('ADD', alpha[0], t.m('MULTIPLY', a.outputs['Fac'], alpha[1] - alpha[0])), mix.inputs[0])
    t.link(t.n('ShaderNodeBsdfTransparent').outputs[0], mix.inputs[1])
    t.link(em.outputs[0], mix.inputs[2])
    t.link(mix.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
    me.materials.append(m)
    objs.append(bpy.data.objects.new(me.name, me))
    me = bpy.data.meshes.new(name + '_edges')
    me.from_pydata(ev, [], ef)
    me.materials.append(_emit(name + '_edge', tuple(0.6 * c + 0.4 * k for c, k in zip(col, CYAN)), edge))
    objs.append(bpy.data.objects.new(me.name, me))
    for ob in objs:
        bpy.context.scene.collection.objects.link(ob)
        ob.visible_shadow = False
        NOFOG.append(ob)
    return objs


# ------------------------------------------------------------------ props shared by the rooms
def neon_strip(p0, p1, w=0.12, mat_='neon', housing=True, normal=(0, 0, 1)):
    """Emissive bar between two points with a thin dark housing behind it."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    c = (p0 + p1) / 2
    n = Vector(normal)
    ax = [abs(d.x), abs(d.y), abs(d.z)]
    k = ax.index(max(ax))
    s = [w, w, w]
    s[k] = d.length
    box(mat_, c, s)
    if housing:
        s2 = [w * 2.6, w * 2.6, w * 2.6]
        s2[k] = d.length + w
        for i in range(3):
            if abs(n[i]) > 0.5:
                s2[i] = w * 0.8
        box('dark', c - n * w * 0.5, s2)


def crate(c, s=(2.4, 2.4, 2.4), kind='crate', rot=0.0, light=True):
    """Cargo container: body, corner posts, ribs, a small status light."""
    x, y, z = c
    R = _rot(rot)
    box(kind, c, s, rot)
    for sx in (-1, 1):
        for sy in (-1, 1):
            o = Vector((sx * (s[0] / 2 - 0.06), sy * (s[1] / 2 - 0.06), 0))
            o = R @ o if R else o
            box('dark', (x + o.x, y + o.y, z), (0.22, 0.22, s[2] + 0.08), rot)
    for k in (-0.3, 0.0, 0.3):
        box('dark', (x, y, z + k * s[2]), (s[0] + 0.07, s[1] + 0.07, 0.08), rot)
    if light:
        o = Vector((s[0] / 2 + 0.03, s[1] * 0.3, s[2] * 0.3))
        o = R @ o if R else o
        box('cyan', (x + o.x, y + o.y, z + o.z), (0.1, 0.3, 0.1), rot)


def barrel(c, r=0.45, h=1.3, mat_='crate_b'):
    cyl(mat_, (c[0], c[1], c[2]), (c[0], c[1], c[2] + h), r, 12)
    for k in (0.15, 0.5, 0.85):
        cyl('dark', (c[0], c[1], c[2] + h * k - 0.04), (c[0], c[1], c[2] + h * k + 0.04), r * 1.06, 12)


def greeble_wall(rnd, x, y0, y1, z0, z1, n, facing=1, depth=0.6, mats=('hull', 'armor', 'hull_lt')):
    """Random boxes / vents / little lights on a wall in the YZ plane at x; facing = +1 (towards +X)."""
    for _ in range(n):
        sy = rnd.uniform(0.6, 3.2)
        sz = rnd.uniform(0.4, 2.2)
        d = rnd.uniform(0.15, depth)
        y = rnd.uniform(y0 + sy / 2, y1 - sy / 2)
        z = rnd.uniform(z0 + sz / 2, z1 - sz / 2)
        box(rnd.choice(mats), (x + facing * d / 2, y, z), (d, sy, sz))
        k = rnd.random()
        if k < 0.3:      # vent slats
            for i in range(int(sz / 0.25)):
                box('dark', (x + facing * (d + 0.02), y, z - sz / 2 + 0.15 + i * 0.25), (0.04, sy * 0.8, 0.08))
        elif k < 0.5:
            box(rnd.choice(('orange', 'cyan', 'neon')), (x + facing * (d + 0.02), y + sy * 0.3, z + sz * 0.25),
                (0.05, 0.18, 0.12))


def import_model(path, loc, rz=0.0, scale=1.0):
    """Import a .glb and place its root; returns the new root objects."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    for o in roots:
        o.rotation_mode = 'XYZ'
        o.location = Vector(loc) + o.location * scale
        o.rotation_euler = (o.rotation_euler[0], o.rotation_euler[1], math.radians(rz))
        o.scale = o.scale * scale
    return new


def tank(kind, loc, rz=0.0, scale=1.0, faction='human'):
    return import_model(os.path.join(MODELS, faction, kind + '.glb'), loc, rz, scale)


# ------------------------------------------------------------------ scene / render
def reset(samples=24, exposure=0.0, threads=3, look='AgX - Punchy'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    BUF.clear()
    NOFOG.clear()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.samples = samples
    cy.use_denoising = True
    cy.use_adaptive_sampling = False
    cy.max_bounces = 5
    cy.diffuse_bounces = 3
    cy.glossy_bounces = 3
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 12
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 4.0
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = threads
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = look
    sc.view_settings.exposure = exposure
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20000
    return sc, cam


def space_world(sc, base=(0.004, 0.006, 0.014), star=(0.9, 0.95, 1.2), scale=260.0, density=0.5, size=0.05,
                nebula=0.0):
    """Starfield world (does almost no lighting)."""
    w = bpy.data.worlds.new('Space')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    t = NT.__new__(NT)
    t.t = nt
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    vo.inputs['Scale'].default_value = scale
    nt.links.new(tc.outputs['Generated'], vo.inputs['Vector'])
    core = t.m('SUBTRACT', 1.0, t.m('DIVIDE', vo.outputs['Distance'], size), clamp=True)
    core = t.m('POWER', core, 2.0)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(vo.outputs['Color'], sep.inputs[0])
    on = t.m('GREATER_THAN', sep.outputs[0], 1.0 - density)
    br = t.m('MULTIPLY', t.m('MULTIPLY', core, on), t.m('ADD', 0.15, t.m('POWER', sep.outputs[1], 3.0)))
    col = t.vm('SCALE', star)
    col.inputs[0].default_value = star
    nt.links.new(t.m('MULTIPLY', br, 6.0), col.inputs['Scale'])
    addn = t.vm('ADD', col.outputs[0], base)
    addn.inputs[1].default_value = base
    last = addn.outputs[0]
    if nebula > 0:
        no = nt.nodes.new('ShaderNodeTexNoise')
        no.inputs['Scale'].default_value = 1.6
        no.inputs['Detail'].default_value = 5.0
        nt.links.new(tc.outputs['Generated'], no.inputs['Vector'])
        nb = t.vm('SCALE', (0.05, 0.16, 0.4))
        nb.inputs[0].default_value = (0.05, 0.16, 0.4)
        nt.links.new(t.m('MULTIPLY', t.m('POWER', no.outputs[0], 3.0), nebula), nb.inputs['Scale'])
        a2 = t.vm('ADD', last, nb.outputs[0])
        last = a2.outputs[0]
    nt.links.new(last, bg.inputs[0])
    return w


def area(name, loc, size, energy, col=(0.7, 0.85, 1.0), rot=(0, 0, 0), spread=180.0, cam_vis=False):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = size
    ld.energy = energy
    ld.color = col
    ld.spread = math.radians(spread)
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    o.visible_camera = cam_vis
    return o


def point(name, loc, energy, col=(0.7, 0.85, 1.0), r=0.3):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = energy
    ld.color = col
    ld.shadow_soft_size = r
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o


def spot(name, loc, target, energy, col=(0.7, 0.85, 1.0), angle=60.0, blend=0.5, r=0.3):
    ld = bpy.data.lights.new(name, 'SPOT')
    ld.energy = energy
    ld.color = col
    ld.spot_size = math.radians(angle)
    ld.spot_blend = blend
    ld.shadow_soft_size = r
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def look(cam, loc, target, lens=24.0, roll=0.0):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if roll:
        cam.rotation_euler.rotate_axis('Z', math.radians(roll))
    cam.data.lens = lens


def render(sc, path, res, depth_far=None):
    """Beauty render to path (PNG). With depth_far also renders <path>_z.png: linear camera depth
    (0 = at the camera or open space, 1 = depth_far) used by post() for the haze."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('WROTE', path, flush=True)
    if depth_far:
        m = bpy.data.materials.new('DepthOverride')
        t = NT(m)
        cd = t.n('ShaderNodeCameraData')
        em = t.n('ShaderNodeEmission')
        t.link(t.m('DIVIDE', cd.outputs['View Z Depth'], depth_far, clamp=True), em.inputs[0])
        t.link(em.outputs[0], t.n('ShaderNodeOutputMaterial').inputs[0])
        vl = bpy.context.view_layer
        keep = (sc.cycles.samples, sc.view_settings.view_transform, sc.view_settings.look,
                sc.view_settings.exposure, sc.cycles.use_denoising, sc.world)
        hidden = [o for o in NOFOG if not o.hide_render]
        for o in hidden:
            o.hide_render = True
        lights = [o for o in sc.objects if o.type == 'LIGHT' and not o.hide_render]
        for o in lights:
            o.hide_render = True
        vl.material_override = m
        sc.cycles.samples = 4
        sc.cycles.use_denoising = False
        sc.view_settings.view_transform = 'Raw'
        sc.view_settings.look = 'None'
        sc.view_settings.exposure = 0
        bw = bpy.data.worlds.new('Black')
        bw.use_nodes = True
        bw.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
        sc.world = bw
        sc.render.filepath = path[:-4] + '_z.png'
        bpy.ops.render.render(write_still=True)
        vl.material_override = None
        for o in hidden + lights:
            o.hide_render = False
        (sc.cycles.samples, sc.view_settings.view_transform, sc.view_settings.look,
         sc.view_settings.exposure, sc.cycles.use_denoising, sc.world) = keep
    return path


def post(path, out, haze=0.0, haze_col=(0.1, 0.3, 0.7), scatter=0.0, bloom=1.0, thresh=0.62, vignette=0.25,
         quality=92, gamma=1.0, lift=0.0):
    """Bloom + depth haze (flat colour + blurred-image light scatter) + vignette. Saves a JPG."""
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255.0
    H, W = a.shape[:2]
    k = W / 1280.0
    zp = path[:-4] + '_z.png'
    if (haze or scatter) and os.path.exists(zp):
        z = np.asarray(Image.open(zp).convert('RGB')).astype(np.float32)[..., :1] / 255.0
        z = z ** 1.3
        blur = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(40 * k))).astype(np.float32) / 255.0
        f = z * haze
        a = a * (1 - f * 0.6) + np.array(haze_col, np.float32) * f * 0.35 + blur * z * scatter
    if lift:
        a = a + lift * (1 - a)
    if gamma != 1.0:
        a = np.clip(a, 0, 1) ** gamma
    a = np.clip(a, 0, 1)
    lum = a.max(axis=2, keepdims=True)
    b = Image.fromarray((np.clip((lum - thresh) / (1 - thresh), 0, 1) * a * 255).astype(np.uint8))
    glow = np.zeros_like(a)
    for r, w in [(3, 0.5), (10, 0.4), (28, 0.35), (70, 0.25)]:
        glow += np.asarray(b.filter(ImageFilter.GaussianBlur(r * k))).astype(np.float32) / 255.0 * w
    a = 1 - (1 - a) * (1 - np.clip(glow * bloom, 0, 1))
    if vignette:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r2 = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
        a = a * (1 - vignette * np.clip(r2 - 0.35, 0, 1.5) ** 1.2)[..., None]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(out, quality=quality)
    print('POST', out, flush=True)
    return out


def args():
    import sys
    return dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
