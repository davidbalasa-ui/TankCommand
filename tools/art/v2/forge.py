"""Art pass v2 ("forge"): modelling + baking library for every game asset.

Front is +X, up is +Z (Blender). Each primitive registers a part tagged with a surface zone and a
group (Hull, Turret ...). finish() joins everything, unwraps once, bakes the procedural zone shaders
to one base / normal / ORM / emissive set, splits the groups back out under their pivots, exports a
.glb and renders a two-view preview sheet.

    import forge as F
    F.begin('terran')
    F.box((0, 0, 1), (2, 1, 0.5), 'hull', bevel=0.05)
    with F.group('Turret'):
        ...
    F.finish('Lancer', 'out/lancer.glb', pivot=('Turret', (0.2, 0, 1.6)), render='renders/lancer.png')
"""
import contextlib
import json
import math
import os

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ST = dict(parts=[], faction=None, mats={}, group='Hull', seq=0)
EMIT_SCALE = 4.0


def begin(faction):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ST.update(parts=[], faction=faction, mats={}, group='Hull', seq=0)


@contextlib.contextmanager
def group(name):
    old = ST['group']
    ST['group'] = name
    try:
        yield
    finally:
        ST['group'] = old


# ------------------------------------------------------------------ geometry
def _new(verts, faces, zone, bevel=0.0, seg=1, sharp=35.0, name=None, merge=True, recalc=True):
    ST['seq'] += 1
    name = name or f'p{ST["seq"]}'
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [list(f) for f in faces])
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    if merge:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        dead = [f for f in bm.faces if f.calc_area() < 1e-9]
        if dead:
            bmesh.ops.delete(bm, geom=dead, context='FACES')
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(18)]
        if edges:
            layer = bm.faces.layers.float.new('cham')
            res = bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=seg, affect='EDGES', profile=0.5,
                                  clamp_overlap=True)
            for f in res['faces']:
                f[layer] = 1.0
    thr = math.radians(sharp)
    for e in bm.edges:
        e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0) < thr
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    if 'cham' not in me.attributes:
        me.attributes.new('cham', 'FLOAT', 'FACE')
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj['zone'] = zone
    obj['group'] = ST['group']
    ST['parts'].append(obj)
    return obj


def xf(obj, m):
    obj.data.transform(m)
    if m.determinant() < 0:
        obj.data.flip_normals()
    obj.data.update()
    return obj


def move(obj, d):
    return xf(obj, Matrix.Translation(Vector(d)))


def rot(obj, axis, deg, about=(0, 0, 0)):
    a = Vector(about)
    return xf(obj, Matrix.Translation(a) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-a))


def scale(obj, s, about=(0, 0, 0)):
    a = Vector(about)
    s = (s, s, s) if isinstance(s, (int, float)) else s
    return xf(obj, Matrix.Translation(a) @ Matrix.Diagonal((*s, 1)) @ Matrix.Translation(-a))


def copy(obj):
    ST['seq'] += 1
    o = obj.copy()
    o.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(o)
    o['zone'], o['group'] = obj['zone'], obj['group']
    ST['parts'].append(o)
    return o


def mirror(obj):
    """Copy of obj mirrored across the XZ plane (left/right)."""
    return xf(copy(obj), Matrix.Diagonal((1, -1, 1, 1)))


def sym(*objs):
    out = []
    for o in objs:
        for item in (o if isinstance(o, (list, tuple)) else [o]):
            out += [item, mirror(item)]
    return out


def spin(obj, n, about=(0, 0, 0), axis='Z', start=1):
    """n copies in total around an axis (obj is the first)."""
    out = [obj]
    for k in range(start, n):
        out.append(rot(copy(obj), axis, 360.0 * k / n, about))
    return out


def mark():
    return len(ST['parts'])


def since(m):
    return ST['parts'][m:]


def rot_all(m, axis, deg, about=(0, 0, 0)):
    for o in since(m):
        rot(o, axis, deg, about)


def move_all(m, d):
    for o in since(m):
        move(o, d)


def mirror_all(m):
    for o in list(since(m)):
        mirror(o)


def rezone(m, zone):
    for o in since(m):
        o['zone'] = zone


def loft(rings, zone, caps=True, closed=True, **kw):
    """Skin a list of rings (each a list of (x, y, z), same count)."""
    n = len(rings[0])
    verts = [p for r in rings for p in r]
    faces = []
    for i in range(len(rings) - 1):
        for k in range(n if closed else n - 1):
            j = (k + 1) % n
            faces.append([i * n + k, i * n + j, (i + 1) * n + j, (i + 1) * n + k])
    if caps:
        faces.append(list(range(n))[::-1])
        faces.append(list(range((len(rings) - 1) * n, len(rings) * n)))
    return _new(verts, faces, zone, **kw)


def symring(half):
    """Half cross-section [(y, z)...] from the bottom centre round the +Y side to the top centre."""
    inner = [p for p in half[::-1] if p[0] > 1e-9]
    return list(half) + [(-y, z) for y, z in inner]


def hull(sections, zone, **kw):
    """Angular body along X: sections = [(x, half_profile)], half_profile as for symring."""
    return loft([[(x, y, z) for y, z in symring(h)] for x, h in sections], zone, **kw)


def prism(profile, y0, y1, zone, taper=1.0, **kw):
    """Extrude a side profile [(x, z)...] between y0 and y1; taper < 1 leans the upper sides in."""
    zs = [z for _, z in profile]
    zlo, zhi = min(zs), max(zs)
    yc = (y0 + y1) / 2

    def ty(y, z):
        return yc + (y - yc) * (1 - (1 - taper) * (z - zlo) / (zhi - zlo + 1e-9))
    return loft([[(x, ty(y0, z), z) for x, z in profile], [(x, ty(y1, z), z) for x, z in profile]], zone, **kw)


def plate(outline, z0, z1, zone, inset=0.0, **kw):
    """Extrude a top-down outline [(x, y)...] from z0 to z1; inset shrinks the top (sloped sides)."""
    cx = sum(p[0] for p in outline) / len(outline)
    cy = sum(p[1] for p in outline) / len(outline)
    top = [(cx + (x - cx) * (1 - inset), cy + (y - cy) * (1 - inset), z1) for x, y in outline]
    return loft([[(x, y, z0) for x, y in outline], top], zone, **kw)


def box(c, s, zone, taper=1.0, **kw):
    (cx, cy, cz), (sx, sy, sz) = c, s
    prof = [(cx - sx, cz - sz), (cx + sx, cz - sz), (cx + sx, cz + sz), (cx - sx, cz + sz)]
    return prism(prof, cy - sy, cy + sy, zone, taper, **kw)


def _frame(d):
    d = Vector(d).normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    a = d.cross(up).normalized()
    b = d.cross(a).normalized()
    return d, a, b


def tube(p0, p1, profile, sides, zone, caps=True, sharp=50.0, **kw):
    """Lathe along the axis p0->p1. profile = [(t, r)] with t in 0..1 along the axis (barrels, wheels)."""
    p0, p1 = Vector(p0), Vector(p1)
    d, a, b = _frame(p1 - p0)
    rings = []
    for t, r in profile:
        c = p0 + (p1 - p0) * t
        rings.append([tuple(c + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * r)
                      for k in range(sides)])
    return loft(rings, zone, caps=caps, sharp=sharp, **kw)


def cyl(p0, p1, r, sides, zone, r1=None, **kw):
    return tube(p0, p1, [(0, r), (1, r if r1 is None else r1)], sides, zone, **kw)


def lathe(profile, sides, zone, center=(0, 0, 0), sq=(1, 1), arc=(0, 360), sharp=50.0, caps=False, **kw):
    """Revolve [(r, z)...] round the vertical axis. arc limits the sweep (open, for petals)."""
    cx, cy, cz = center
    full = abs(arc[1] - arc[0]) >= 359.9
    cols = sides if full else sides + 1
    rings = []
    for r, z in profile:
        ring = []
        for k in range(cols):
            a = math.radians(arc[0] + (arc[1] - arc[0]) * k / sides)
            ring.append((cx + r * math.cos(a) * sq[0], cy + r * math.sin(a) * sq[1], cz + z))
        rings.append(ring)
    return loft(rings, zone, closed=full, caps=full and caps, sharp=sharp, **kw)


def orb(c, r, zone, seg=(16, 10), sq=(1, 1, 1), **kw):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=r)
    verts = [(v.co.x * sq[0] + c[0], v.co.y * sq[1] + c[1], v.co.z * sq[2] + c[2]) for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return _new(verts, faces, zone, sharp=180, **kw)


def ico(c, r, zone, sub=1, sq=(1, 1, 1), jitter=0.0, seed=0, sharp=20, **kw):
    """Faceted lump (rocks, crystals base): icosphere with optional vertex jitter."""
    import random
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    verts = []
    for v in bm.verts:
        k = 1 + (rnd.random() - 0.5) * 2 * jitter
        verts.append((v.co.x * sq[0] * k + c[0], v.co.y * sq[1] * k + c[1], v.co.z * sq[2] * k + c[2]))
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return _new(verts, faces, zone, sharp=sharp, **kw)


def rock(c, r, zone, sq=(1, 1, 1), seed=0, sub=2, rough=0.38, cuts=5, floor=None, sharp=28, **kw):
    """Chiselled rock: a noise-displaced icosphere with a few flat plane cuts. floor clamps the base."""
    import random
    from mathutils import noise
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    pts = []
    for v in bm.verts:
        p = v.co.copy()
        k = 1 + rough * noise.noise(p * 1.25 + off) + rough * 0.45 * noise.noise(p * 3.1 + off)
        pts.append(p * k)
    for _ in range(cuts):
        nrm = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.2, 1))).normalized()
        d = rnd.uniform(0.62, 0.92)
        pts = [p - nrm * (p.dot(nrm) - d) if p.dot(nrm) > d else p for p in pts]
    verts = []
    for p in pts:
        z = c[2] + p.z * r * sq[2]
        if floor is not None:
            z = max(z, floor)
        verts.append((c[0] + p.x * r * sq[0], c[1] + p.y * r * sq[1], z))
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return _new(verts, faces, zone, sharp=sharp, merge=False, **kw)


def sweep(path, sect, zone, sides=8, up=(0, 0, 1), caps=True, power=1.0, sharp=60.0, **kw):
    """Sweep an elliptical section along a path. sect = [(w, h)] per point (w sideways, h along up).
    power < 1 gives a pointed lens section (blades), > 1 a boxy one."""
    pts = [Vector(p) for p in path]
    upv = Vector(up).normalized()
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(upv)
        if side.length < 1e-6:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        nrm = side.cross(t).normalized()
        w, h = sect[i] if isinstance(sect[i], (tuple, list)) else (sect[i], sect[i])
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ca, sa = math.cos(a), math.sin(a)
            ca = math.copysign(abs(ca) ** power, ca)
            sa = math.copysign(abs(sa) ** power, sa)
            ring.append(tuple(p + side * (w * ca) + nrm * (h * sa)))
        rings.append(ring)
    return loft(rings, zone, caps=caps, sharp=sharp, **kw)


def arc_pts(c, r, a0, a1, n, plane='xy', sq=(1, 1)):
    """Points on an arc (degrees) in a plane through c."""
    out = []
    for k in range(n):
        a = math.radians(a0 + (a1 - a0) * k / (n - 1))
        u, v = r * math.cos(a) * sq[0], r * math.sin(a) * sq[1]
        if plane == 'xy':
            out.append((c[0] + u, c[1] + v, c[2]))
        elif plane == 'xz':
            out.append((c[0] + u, c[1], c[2] + v))
        else:
            out.append((c[0], c[1] + u, c[2] + v))
    return out


def crescent(c, r, a0, a1, width, thick, zone, n=14, plane='xy', sq=(1, 1), up=None, tip=0.08, **kw):
    """Crescent blade: widest in the middle, tapering to points at both ends."""
    pts = arc_pts(c, r, a0, a1, n, plane, sq)
    sect = []
    for k in range(n):
        s = max(0.0, math.sin(math.pi * k / (n - 1))) ** 0.8
        sect.append((width * (tip + (1 - tip) * s), thick * (tip + (1 - tip) * s)))
    if up is None:
        up = (0, 0, 1) if plane == 'xy' else ((0, 1, 0) if plane == 'xz' else (1, 0, 0))
    # width lies in the plane of the arc (radially), thick is out of the plane.
    return sweep(pts, sect, zone, sides=6, up=up, power=0.75, **kw)


def lensfn(x0, x1, w, zt, zb, zc, nose=0.6, tail=1.0, pw=1.0):
    """Surface function for a pointed lens hull: f(u, v) -> point. u 0..1 from the nose (x1) to the
    tail (x0); v in degrees round the body (0 = +Y side, 90 = top, 270 = bottom)."""
    def f(u, v, off=0.0):
        k = max(0.0, math.sin(math.pi * min(1.0, max(0.0, u)) ** nose)) ** tail if 0 < u < 1 else 0.0
        a = math.radians(v)
        ca, sa = math.cos(a), math.sin(a)
        y = (w * k + off) * math.copysign(abs(ca) ** pw, ca)
        h = (zt - zc) if sa >= 0 else (zc - zb)
        z = zc + (h * k + off) * math.copysign(abs(sa) ** pw, sa)
        return Vector((x1 + (x0 - x1) * u, y, z))
    return f


def discfn(R, zt, zc, cx=0.0, cy=0.0, p=1.0, sq=(1, 1)):
    """Surface function for a dome / disc top: u 0..1 from the centre to the rim, v the angle."""
    def f(u, v, off=0.0):
        a = math.radians(v)
        k = max(0.0, math.cos(math.pi / 2 * min(1.0, max(0.0, u)))) ** p
        return Vector((cx + R * u * math.cos(a) * sq[0], cy + R * u * math.sin(a) * sq[1], zc + (zt - zc) * k + off))
    return f


def body(fn, zone, nu=14, nv=16, u0=0.0, u1=1.0, off=0.0, **kw):
    """Closed body from a surface function."""
    rings = []
    for i in range(nu + 1):
        u = u0 + (u1 - u0) * i / nu
        rings.append([tuple(fn(u, 360.0 * k / nv, off)) for k in range(nv)])
    return loft(rings, zone, sharp=kw.pop('sharp', 80), **kw)


def shell(fn, u0, u1, vc, vw, zone, nu=10, nv=6, thick=0.07, off=0.05, lift=0.0, shape=0.6, skew=0.0,
          front=0.0, back=0.0, **kw):
    """Curved armour plate lying on a surface function: a leaf-shaped patch from u0..u1, centred on
    angle vc and vw degrees wide at its widest. lift raises the trailing (u1) end so plates overlap
    like scales; skew shears the leaf round the body; front/back (0..1) keep the ends blunt."""
    top, bot = [], []
    for i in range(nu + 1):
        s = i / nu
        u = u0 + (u1 - u0) * s
        wsh = max(0.0, math.sin(math.pi * s)) ** shape
        ends = front * (1 - s) ** 2 + back * s ** 2
        wk = max(wsh, min(1.0, ends)) if (front or back) else wsh
        rt, rb = [], []
        for j in range(nv + 1):
            t = j / nv - 0.5
            v = vc + skew * (s - 0.5) + t * vw * max(wk, 0.02)
            edge = 1 - (abs(t) * 2) ** 3
            o = off + lift * s
            rt.append(tuple(fn(u, v, o + thick * (0.35 + 0.65 * edge))))
            rb.append(tuple(fn(u, v, o - thick * 0.5)))
        top.append(rt)
        bot.append(rb)
    n = nv + 1
    verts = [p for r in top for p in r] + [p for r in bot for p in r]
    base = (nu + 1) * n
    faces = []
    for i in range(nu):
        for j in range(nv):
            a, b, c, d = i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j
            faces.append([a, b, c, d])
            faces.append([base + d, base + c, base + b, base + a])
    for i in range(nu):  # side walls
        faces.append([i * n, (i + 1) * n, base + (i + 1) * n, base + i * n])
        faces.append([(i + 1) * n + nv, i * n + nv, base + i * n + nv, base + (i + 1) * n + nv])
    for j in range(nv):  # end walls
        faces.append([j + 1, j, base + j, base + j + 1])
        faces.append([nu * n + j, nu * n + j + 1, base + nu * n + j + 1, base + nu * n + j])
    return _new(verts, faces, zone, sharp=kw.pop('sharp', 50), **kw)


# ------------------------------------------------------------------ shaders
class N:
    """Tiny node-tree helper."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.bsdf = self.nt.nodes['Principled BSDF']
        self.tc = self.nt.nodes.new('ShaderNodeTexCoord')
        self.co = self.tc.outputs['Object']

    def link(self, a, b):
        self.nt.links.new(a, b)

    def m(self, op, a, b=None, clamp=False):
        n = self.nt.nodes.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, s in enumerate((a, b)):
            if s is None:
                continue
            if isinstance(s, (int, float)):
                n.inputs[i].default_value = s
            else:
                self.link(s, n.inputs[i])
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.nt.nodes.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.clamp_factor = True
        for idx, s in ((0, fac), (6, a), (7, b)):
            if isinstance(s, (int, float)):
                n.inputs[idx].default_value = s
            elif isinstance(s, (tuple, list)):
                n.inputs[idx].default_value = (s[0], s[1], s[2], 1)
            else:
                self.link(s, n.inputs[idx])
        return n.outputs[2]

    def vscale(self, v, s):
        n = self.nt.nodes.new('ShaderNodeVectorMath')
        n.operation = 'MULTIPLY'
        self.link(v, n.inputs[0])
        n.inputs[1].default_value = s
        return n.outputs[0]

    def sep(self, v):
        n = self.nt.nodes.new('ShaderNodeSeparateXYZ')
        self.link(v, n.inputs[0])
        return n.outputs

    def noise(self, scale, detail=4.0, co=None, rough=0.55):
        n = self.nt.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        self.link(co or self.co, n.inputs['Vector'])
        return n.outputs[0]

    def voronoi(self, scale, feature='F1', distance='EUCLIDEAN', co=None, rand=1.0):
        n = self.nt.nodes.new('ShaderNodeTexVoronoi')
        n.feature = feature
        if feature != 'DISTANCE_TO_EDGE':
            n.distance = distance
        n.inputs['Scale'].default_value = scale
        n.inputs['Randomness'].default_value = rand
        self.link(co or self.co, n.inputs['Vector'])
        return n

    def wave(self, scale, distortion, detail=2.0, dscale=1.0, co=None):
        n = self.nt.nodes.new('ShaderNodeTexWave')
        n.inputs['Scale'].default_value = scale
        n.inputs['Distortion'].default_value = distortion
        n.inputs['Detail'].default_value = detail
        n.inputs['Detail Scale'].default_value = dscale
        self.link(co or self.co, n.inputs['Vector'])
        return n.outputs[0]

    def pointy(self, lo=0.52, hi=0.62):
        g = self.nt.nodes.new('ShaderNodeNewGeometry')
        return self.smooth(g.outputs['Pointiness'], lo, hi)

    def upness(self):
        g = self.nt.nodes.new('ShaderNodeNewGeometry')
        return self.sep(g.outputs['Normal'])[2]

    def smooth(self, v, lo, hi):
        n = self.nt.nodes.new('ShaderNodeMapRange')
        n.interpolation_type = 'SMOOTHSTEP'
        n.inputs['From Min'].default_value = lo
        n.inputs['From Max'].default_value = hi
        self.link(v, n.inputs['Value'])
        return n.outputs[0]

    def bevel(self, radius=0.03):
        if not hasattr(self, '_bev'):
            bv = self.nt.nodes.new('ShaderNodeBevel')
            bv.samples = 4
            bv.inputs['Radius'].default_value = radius
            self._bev = bv.outputs[0]
        return self._bev

    def edge(self, amount=1.0, radius=0.07, lo=0.0, hi=0.035):
        """Register this zone's edge mask (bevelled normal vs true normal) for the wear pass."""
        g = self.nt.nodes.new('ShaderNodeNewGeometry')
        d = self.nt.nodes.new('ShaderNodeVectorMath')
        d.operation = 'DOT_PRODUCT'
        self.link(self.bevel(radius), d.inputs[0])
        self.link(g.outputs['Normal'], d.inputs[1])
        e = self.smooth(self.m('SUBTRACT', 1.0, d.outputs['Value']), lo, hi)
        at = self.nt.nodes.new('ShaderNodeAttribute')
        at.attribute_name = 'cham'
        e = self.m('MAXIMUM', e, at.outputs['Fac'])
        brk = self.m('ADD', 0.35, self.m('MULTIPLY', self.smooth(self.noise(5.0, 5.0), 0.3, 0.65), 0.65))
        out = self.nt.nodes.new('ShaderNodeMath')
        out.operation = 'MULTIPLY'
        out.name = 'EdgeMask'
        self.link(self.m('MULTIPLY', e, brk), out.inputs[0])
        out.inputs[1].default_value = amount
        return out.outputs[0]

    def bump(self, height, strength=0.5, dist=0.02, soft=True):
        n = self.nt.nodes.new('ShaderNodeBump')
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = dist
        self.link(height, n.inputs['Height'])
        if soft:
            self.link(self.bevel(), n.inputs['Normal'])
        self.link(n.outputs[0], self.bsdf.inputs['Normal'])

    def out(self, color=None, rough=None, metal=None, emit=None, emit_strength=None):
        for key, val in (('Base Color', color), ('Roughness', rough), ('Metallic', metal),
                         ('Emission Color', emit), ('Emission Strength', emit_strength)):
            if val is None:
                continue
            sock = self.bsdf.inputs[key]
            if isinstance(val, (int, float)):
                sock.default_value = val
            elif isinstance(val, (tuple, list)):
                sock.default_value = (val[0], val[1], val[2], 1)
            else:
                self.link(val, sock)


UV_PRIORITY = {'track': 0.5, 'wheel': 0.6, 'dark': 0.6, 'under': 0.6, 'slat': 0.6, 'glow': 0.45, 'amber': 0.45,
               'red': 0.45, 'coil': 0.7}
EDGE = {'terran': (0.16, 0.17, 0.19, 2.5), 'kesh': (0.5, 0.45, 0.36, 1.2), 'nature': (0.06, 0.055, 0.05, 1.5)}
CYAN = (0.03, 0.62, 1.0)
AMBER = (1.0, 0.2, 0.012)
GOLD = (1.0, 0.3, 0.02)

ZONES = {
    'terran': {
        'hull': dict(kind='panel', base=(0.036, 0.04, 0.048), rough=0.5, metal=0.7, scale=0.8, var=0.16, wear=0.75, dirt=0.3),
        'armor': dict(kind='panel', base=(0.058, 0.063, 0.074), rough=0.44, metal=0.75, scale=1.3, var=0.15, wear=0.9, dirt=0.15),
        'plate': dict(kind='panel', base=(0.088, 0.093, 0.105), rough=0.4, metal=0.8, scale=1.8, var=0.12, wear=1.0, dirt=0.1),
        'dark': dict(kind='panel', base=(0.016, 0.018, 0.022), rough=0.6, metal=0.6, scale=2.6, var=0.3, wear=0.4, dirt=0.35),
        'track': dict(kind='panel', base=(0.022, 0.021, 0.022), rough=0.75, metal=0.5, scale=4.0, var=0.2, wear=1.0, dirt=0.8),
        'wheel': dict(kind='panel', base=(0.04, 0.043, 0.05), rough=0.55, metal=0.7, scale=3.0, var=0.2, wear=1.0, dirt=0.6),
        'barrel': dict(kind='panel', base=(0.075, 0.08, 0.09), rough=0.32, metal=0.95, scale=0.5, var=0.1, wear=0.8, dirt=0.0, rings=4.0),
        'vent': dict(kind='slats', base=(0.05, 0.055, 0.06), freq=9.0, axis=0),
        'grille': dict(kind='slats', base=(0.05, 0.055, 0.06), freq=9.0, axis=1),
        'glow': dict(kind='glow', emit=CYAN, strength=3.2),
        'amber': dict(kind='glow', emit=AMBER, strength=3.2),
        'red': dict(kind='glow', emit=(1.0, 0.03, 0.02), strength=1.3),
        'coil': dict(kind='coil', emit=CYAN, strength=3.5, freq=7.0),
        'glass': dict(kind='glass', base=(0.008, 0.02, 0.03), emit=CYAN, strength=0.14),
        'hazard': dict(kind='hazard', a=(0.75, 0.42, 0.03), b=(0.03, 0.03, 0.035)),
        'concrete': dict(kind='concrete', base=(0.3, 0.3, 0.29)),
        'deck': dict(kind='concrete', base=(0.12, 0.125, 0.135), metal=0.4, grid=0.9),
    },
    'kesh': {
        'shell': dict(kind='etched', base=(0.66, 0.63, 0.6), base2=(0.5, 0.4, 0.3), rough=0.3, veins=0.2),
        'bronze': dict(kind='etched', base=(0.52, 0.34, 0.16), base2=(0.3, 0.17, 0.08), rough=0.32, veins=0.3),
        'under': dict(kind='etched', base=(0.16, 0.11, 0.075), base2=(0.08, 0.05, 0.04), rough=0.42, veins=0.25),
        'barrel': dict(kind='etched', base=(0.72, 0.62, 0.45), base2=(0.55, 0.4, 0.2), rough=0.22, veins=0.0, fine=True),
        'slat': dict(kind='ribs', emit=GOLD, strength=1.7, freq=6.0),
        'glow': dict(kind='glow', emit=GOLD, strength=2.0),
        'core': dict(kind='orb', emit=GOLD, strength=1.5),
        'violet': dict(kind='glow', emit=(0.35, 0.08, 1.0), strength=2.0),
    },
    'nature': {
        'rock': dict(kind='rock', base=(0.2, 0.18, 0.16), base2=(0.33, 0.3, 0.26), moss=0.35),
        'rockdark': dict(kind='rock', base=(0.1, 0.09, 0.085), base2=(0.2, 0.18, 0.17), moss=0.0),
        'cliff': dict(kind='rock', base=(0.24, 0.2, 0.16), base2=(0.4, 0.34, 0.27), moss=0.2, strata=3.0),
        'bark': dict(kind='bark', base=(0.11, 0.08, 0.06)),
        'leaf': dict(kind='leaf', base=(0.07, 0.17, 0.045), base2=(0.16, 0.26, 0.06)),
        'grass': dict(kind='leaf', base=(0.1, 0.2, 0.05), base2=(0.3, 0.34, 0.1)),
        'frond': dict(kind='frond', base=(0.07, 0.04, 0.12), emit=(0.25, 0.9, 0.7), strength=2.2),
        'gem_pink': dict(kind='gem', base=(0.75, 0.05, 0.3), base2=(1.0, 0.72, 0.86), emit=(1.0, 0.08, 0.3), strength=0.55),
        'gem_opal': dict(kind='gem', base=(0.08, 0.22, 0.75), base2=(0.85, 0.93, 1.0), emit=(0.08, 0.3, 1.0), strength=0.5, opal=True),
        'redrock': dict(kind='rock', base=(0.2, 0.07, 0.05), base2=(0.38, 0.16, 0.11), moss=0.0),
        'metalrock': dict(kind='rock', base=(0.12, 0.14, 0.18), base2=(0.3, 0.34, 0.4), moss=0.0, metal=0.6),
    },
}


def _dirt(n, col, amount, zref=0.0, h=1.4, tint=(0.13, 0.1, 0.07)):
    """Blend ground dust into the lowest part of a vehicle (object Z below zref + h)."""
    if amount <= 0:
        return col
    z = n.sep(n.co)[2]
    low = n.m('SUBTRACT', 1.0, n.smooth(z, zref + 0.05, zref + h))
    spl = n.smooth(n.noise(3.0, 5.0), 0.35, 0.7)
    return n.mix(n.m('MULTIPLY', n.m('MULTIPLY', low, spl), amount, clamp=True), col, tint)


def zone_mat(zone):
    table = ZONES[ST['faction']]
    if zone not in table:
        for other in ZONES.values():
            if zone in other:
                table = other
                break
    z = table[zone]
    if zone in ST['mats']:
        return ST['mats'][zone]
    mat = bpy.data.materials.new(f'zone_{zone}')
    mat.use_nodes = True
    n = N(mat)
    kind = z['kind']
    fine = n.noise(22.0, 5.0)
    if kind == 'panel':
        sc = z['scale']
        co = n.vscale(n.co, (sc, sc * 1.25, sc * 1.6))
        v1 = n.voronoi(1.0, 'F1', 'CHEBYCHEV', co, rand=0.25)
        v2 = n.voronoi(1.0, 'F2', 'CHEBYCHEV', co, rand=0.25)
        d = n.m('SUBTRACT', v2.outputs['Distance'], v1.outputs['Distance'])
        seam = n.m('SUBTRACT', 1.0, n.smooth(d, 0.025 * sc, 0.05 * sc))
        rnd = n.sep(v1.outputs['Color'])[0]
        b = z['base']
        lo_k, hi_k = 1 - z['var'], 1 + z['var']
        col = n.mix(rnd, (b[0] * lo_k, b[1] * lo_k, b[2] * lo_k), (b[0] * hi_k, b[1] * hi_k, b[2] * hi_k))
        grime = n.smooth(n.noise(2.2, 6.0), 0.45, 0.8)
        col = n.mix(n.m('MULTIPLY', grime, 0.18), col, (b[0] * 0.5, b[1] * 0.48, b[2] * 0.45))
        col = n.mix(n.m('MULTIPLY', seam, 0.9), col, (0.004, 0.005, 0.007))
        col = _dirt(n, col, z.get('dirt', 0))
        height = n.m('ADD', n.m('MULTIPLY', fine, 0.05), n.m('SUBTRACT', n.m('MULTIPLY', rnd, 0.1), seam))
        if z.get('rings'):
            x = n.sep(n.co)[0]
            ring = n.m('GREATER_THAN', n.m('FRACT', n.m('MULTIPLY', x, z['rings'])), 0.86)
            height = n.m('SUBTRACT', height, n.m('MULTIPLY', ring, 0.5))
            col = n.mix(n.m('MULTIPLY', ring, 0.6), col, (0.01, 0.01, 0.012))
        n.bump(height, 0.5, 0.03)
        n.edge(z['wear'])
        rough = n.m('ADD', z['rough'] - 0.08, n.m('ADD', n.m('MULTIPLY', fine, 0.12), n.m('MULTIPLY', grime, 0.2)))
        n.out(col, rough, z['metal'])
    elif kind == 'slats':
        ax = n.sep(n.co)[z['axis']]
        f = n.m('FRACT', n.m('MULTIPLY', ax, z['freq']))
        slot = n.m('LESS_THAN', f, 0.45)
        b = z['base']
        n.out(n.mix(slot, (b[0] * 2, b[1] * 2, b[2] * 2), (0.004, 0.004, 0.005)), 0.5, 0.8)
        n.bump(n.m('SUBTRACT', 1.0, slot), 1.0, 0.04)
    elif kind == 'glow':
        e = z['emit']
        n.out((e[0] * 0.5, e[1] * 0.5, e[2] * 0.5), 0.3, 0.0, e, z['strength'])
    elif kind == 'coil':
        x = n.sep(n.co)[0]
        f = n.m('FRACT', n.m('MULTIPLY', x, z['freq']))
        on = n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', f, 0.5)), 0.38, 0.2)
        e = z['emit']
        n.out(n.mix(on, (0.01, 0.012, 0.015), (e[0] * 0.5, e[1] * 0.5, e[2] * 0.5)), 0.3, 0.3, e,
              n.m('MULTIPLY', on, z['strength']))
        n.bump(on, 0.8, 0.03)
    elif kind == 'glass':
        up = n.smooth(n.upness(), -0.2, 1.0)
        n.out(z['base'], 0.06, 0.3, z['emit'], n.m('MULTIPLY', up, z['strength']))
    elif kind == 'hazard':
        s = n.sep(n.co)
        f = n.m('FRACT', n.m('MULTIPLY', n.m('ADD', n.m('ADD', s[0], s[1]), s[2]), 1.6))
        col = n.mix(n.m('GREATER_THAN', f, 0.5), z['a'], z['b'])
        col = n.mix(n.m('MULTIPLY', n.smooth(n.noise(6.0, 5.0), 0.45, 0.75), 0.6), col, (0.05, 0.05, 0.05))
        n.out(col, 0.6, 0.3)
        n.bump(fine, 0.2, 0.01)
    elif kind == 'concrete':
        b = z['base']
        big = n.noise(1.5, 5.0)
        col = n.mix(big, (b[0] * 0.6, b[1] * 0.6, b[2] * 0.6), (b[0] * 1.3, b[1] * 1.3, b[2] * 1.3))
        g = z.get('grid', 0.5)
        v1 = n.voronoi(g, 'F1', 'CHEBYCHEV', rand=0.0)
        v2 = n.voronoi(g, 'F2', 'CHEBYCHEV', rand=0.0)
        joint = n.m('LESS_THAN', n.m('SUBTRACT', v2.outputs['Distance'], v1.outputs['Distance']), 0.03)
        col = n.mix(n.m('MULTIPLY', joint, 0.8), col, (0.012, 0.012, 0.014))
        stain = n.smooth(n.noise(4.0, 6.0), 0.55, 0.8)
        col = n.mix(n.m('MULTIPLY', stain, 0.5), col, (0.04, 0.035, 0.03))
        n.out(col, n.m('ADD', 0.6, n.m('MULTIPLY', fine, 0.3)), z.get('metal', 0.0))
        n.bump(n.m('SUBTRACT', n.m('MULTIPLY', fine, 0.3), joint), 0.5, 0.02)
    elif kind == 'etched':
        broad = n.noise(1.1, 3.0)
        b, b2 = z['base'], z['base2']
        col = n.mix(n.smooth(broad, 0.35, 0.7), b, b2)
        if z.get('fine'):
            x = n.sep(n.co)[0]
            eng = n.m('GREATER_THAN', n.m('FRACT', n.m('MULTIPLY', x, 4.0)), 0.88)
            vein = 0.0
        else:
            w = n.wave(1.15, 7.0, 2.5, 1.6)
            sw = n.m('SUBTRACT', 1.0, n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', w, 0.5)), 0.03, 0.075))
            w2 = n.wave(3.4, 5.0, 2.0, 2.2, n.vscale(n.co, (1.0, 1.3, 0.8)))
            sw2 = n.m('SUBTRACT', 1.0, n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', w2, 0.5)), 0.02, 0.06))
            cr = n.m('SUBTRACT', 1.0, n.smooth(n.voronoi(2.2, 'DISTANCE_TO_EDGE').outputs['Distance'], 0.006, 0.02))
            eng = n.m('MAXIMUM', sw, n.m('MAXIMUM', n.m('MULTIPLY', sw2, 0.6), n.m('MULTIPLY', cr, 0.35)))
            sel = n.smooth(n.noise(0.7, 2.0), 0.74 - z['veins'] * 0.3, 0.8 - z['veins'] * 0.3)
            vein = n.m('MULTIPLY', sw, sel)
        col = n.mix(n.m('MULTIPLY', eng, 0.92), col, (b2[0] * 0.1, b2[1] * 0.08, b2[2] * 0.07))
        n.edge(0.8)
        n.out(col, n.m('ADD', z['rough'] - 0.06, n.m('ADD', n.m('MULTIPLY', fine, 0.14), n.m('MULTIPLY', eng, 0.25))),
              0.92, GOLD, n.m('MULTIPLY', vein, 1.7) if vein != 0.0 else 0.0)
        n.bump(n.m('SUBTRACT', n.m('MULTIPLY', fine, 0.05), eng), 0.6, 0.025)
    elif kind == 'ribs':
        x = n.sep(n.co)[0]
        f = n.m('FRACT', n.m('MULTIPLY', x, z['freq']))
        on = n.m('ADD', 0.45, n.m('MULTIPLY', n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', f, 0.5)), 0.5, 0.38), 0.55))
        flick = n.m('ADD', 0.35, n.m('MULTIPLY', n.noise(1.2, 3.0), 1.1))
        e = z['emit']
        n.out(n.mix(on, (0.03, 0.018, 0.01), (e[0] * 0.6, e[1] * 0.6, e[2] * 0.6)), 0.4, 0.6, e,
              n.m('MULTIPLY', n.m('MULTIPLY', on, flick), z['strength']))
        n.bump(n.m('SUBTRACT', 1.0, on), 0.9, 0.04)
    elif kind == 'orb':
        lw = n.nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.4
        core = n.m('SUBTRACT', 1.0, lw.outputs[1])
        swirl = n.smooth(n.wave(3.0, 6.0, 2.0, 1.0), 0.3, 0.7)
        e = z['emit']
        n.out((e[0] * 0.7, e[1] * 0.7, e[2] * 0.7), 0.2, 0.0,
              n.mix(core, e, (1.0, 0.7, 0.25)),
              n.m('ADD', z['strength'] * 0.8, n.m('MULTIPLY', core, z['strength'])))
    elif kind == 'rock':
        b, b2 = z['base'], z['base2']
        big = n.noise(1.4, 6.0)
        col = n.mix(n.smooth(big, 0.3, 0.7), b, b2)
        if z.get('strata'):
            zz = n.sep(n.co)[2]
            band = n.smooth(n.m('FRACT', n.m('ADD', n.m('MULTIPLY', zz, z['strata']), n.m('MULTIPLY', big, 1.5))), 0.0, 0.5)
            col = n.mix(n.m('MULTIPLY', band, 0.35), col, (b[0] * 0.4, b[1] * 0.4, b[2] * 0.4))
        cr = n.m('SUBTRACT', 1.0, n.smooth(n.voronoi(2.6, 'DISTANCE_TO_EDGE').outputs['Distance'], 0.0, 0.035))
        col = n.mix(n.m('MULTIPLY', cr, 0.7), col, (b[0] * 0.25, b[1] * 0.25, b[2] * 0.25))
        n.edge(0.7, radius=0.06)
        if z.get('moss', 0) > 0:
            m = n.m('MULTIPLY', n.smooth(n.upness(), 0.45, 0.85), n.smooth(n.noise(2.2, 5.0), 0.4, 0.6))
            col = n.mix(n.m('MULTIPLY', m, z['moss'] * 2, clamp=True), col, (0.09, 0.14, 0.04))
        n.out(col, n.m('ADD', 0.72, n.m('MULTIPLY', fine, 0.2)), z.get('metal', 0.0))
        n.bump(n.m('SUBTRACT', n.m('ADD', n.m('MULTIPLY', big, 0.6), n.m('MULTIPLY', fine, 0.25)), cr), 0.9, 0.05)
    elif kind == 'bark':
        w = n.noise(3.0, 6.0, n.vscale(n.co, (6.0, 6.0, 0.7)))
        b = z['base']
        n.out(n.mix(w, (b[0] * 0.4, b[1] * 0.4, b[2] * 0.4), (b[0] * 2.2, b[1] * 2.1, b[2] * 2.0)), 0.85, 0.0)
        n.bump(w, 1.0, 0.05)
    elif kind == 'leaf':
        w = n.noise(5.0, 4.0)
        zz = n.smooth(n.sep(n.co)[2], 0.0, 1.0)
        col = n.mix(n.m('MULTIPLY', n.m('ADD', w, zz), 0.6, clamp=True), z['base'], z['base2'])
        n.out(col, 0.7, 0.0)
        n.bump(w, 0.5, 0.03)
    elif kind == 'frond':
        zz = n.smooth(n.sep(n.co)[2], 0.2, 1.6)
        v = n.m('SUBTRACT', 1.0, n.smooth(n.voronoi(5.0, 'DISTANCE_TO_EDGE').outputs['Distance'], 0.01, 0.05))
        n.out(n.mix(zz, z['base'], (0.1, 0.25, 0.3)), 0.4, 0.0, z['emit'],
              n.m('MULTIPLY', n.m('ADD', n.m('MULTIPLY', zz, 0.6), n.m('MULTIPLY', v, 0.6)), z['strength']))
    elif kind == 'gem':
        lw = n.nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.5
        fac = lw.outputs[1]
        b, e = z['base'], z['emit']
        w = n.wave(z.get('bands', 2.6), 5.5, 2.5, 1.3)
        band = n.smooth(n.m('ABSOLUTE', n.m('SUBTRACT', n.m('FRACT', n.m('MULTIPLY', w, 3.0)), 0.5)), 0.12, 0.34)
        col = n.mix(band, z['base2'], b)
        if z.get('opal'):
            col = n.mix(n.smooth(n.noise(1.8, 2.0), 0.5, 0.7), col, (0.45, 0.85, 0.7))
        col = n.mix(n.m('MULTIPLY', fac, 0.35), col, (1.0, 0.95, 1.0))
        n.out(col, 0.14, 0.0, e, n.m('MULTIPLY', n.m('ADD', 0.25, n.m('MULTIPLY', band, 0.75)), z['strength']))
        n.bump(band, 0.25, 0.02, soft=False)
    ST['mats'][zone] = mat
    return mat


# ------------------------------------------------------------------ bake
def _png(path, arr):
    import struct
    import zlib
    rgb = (np.clip(arr[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8)[::-1]
    h, w = rgb.shape[:2]
    raw = b''.join(b'\x00' + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def _srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def _down(a, k):
    if k == 1:
        return a
    h, w = a.shape[0] // k, a.shape[1] // k
    return a[:h * k, :w * k].reshape(h, k, w, k, -1).mean(axis=(1, 3))


def _bake(obj, kind, size, **kw):
    img = bpy.data.images.new(f'bake_{kind}', size, size, alpha=False, float_buffer=True)
    if kind == 'NORMAL':
        img.colorspace_settings.name = 'Non-Color'
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        node = nt.nodes.get('BakeTarget') or nt.nodes.new('ShaderNodeTexImage')
        node.name = 'BakeTarget'
        node.image = img
        for x in nt.nodes:
            x.select = False
        node.select = True
        nt.nodes.active = node
    bpy.ops.object.bake(type=kind, margin=max(4, size // 128), use_clear=True, **kw)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)
    bpy.data.images.remove(img)
    return arr


def _route(obj, socket):
    """Feed a Principled input, or the zone's EdgeMask node, into emission for an exact EMIT bake."""
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        bsdf = nt.nodes['Principled BSDF']
        ec, es = bsdf.inputs['Emission Color'], bsdf.inputs['Emission Strength']
        for link in list(nt.links):
            if link.to_socket in (ec, es):
                nt.links.remove(link)
        es.default_value = 1.0
        if socket == 'EdgeMask':
            node = nt.nodes.get('EdgeMask')
            if node:
                nt.links.new(node.outputs[0], ec)
            else:
                ec.default_value = (0, 0, 0, 1)
            continue
        src = bsdf.inputs[socket]
        if src.is_linked:
            nt.links.new(src.links[0].from_socket, ec)
        else:
            v = src.default_value
            ec.default_value = (v[0], v[1], v[2], 1) if hasattr(v, '__len__') else (v, v, v, 1)


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def finish(name, out_glb, pivot=None, size=512, single=False, render=None, gem=None, label=None,
           ao_floor=0.35, views=None, report=None, crevice=None, supersample=2, edge_color=None):
    """pivot = (group_name, (x, y, z)) puts that group under an empty called TurretPivot.
    single = one mesh named `name` with no parent (props). gem = zone name kept as a second
    material called OreGem (deposits)."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    parts = ST['parts']
    groups = []
    for o in parts:
        if o['group'] not in groups:
            groups.append(o['group'])
    for o in parts:
        me = o.data
        me.materials.clear()
        me.materials.append(zone_mat(o['zone']))
        att = me.attributes.new('grp', 'INT', 'FACE')
        gi = groups.index(o['group']) + (100 if gem and o['zone'] == gem else 0)
        att.data.foreach_set('value', [gi] * len(me.polygons))
        uk = me.attributes.new('uvk', 'FLOAT', 'FACE')
        uk.data.foreach_set('value', [float(o.get('uv', UV_PRIORITY.get(o['zone'], 1.0)))] * len(me.polygons))
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    me = obj.data
    while len(me.uv_layers) > 0:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Texel priority: shrink the islands of low-value parts (tracks, wheels, recesses), then re-pack.
    uvk = np.zeros(len(me.polygons), dtype=np.float32)
    me.attributes['uvk'].data.foreach_get('value', uvk)
    counts = np.zeros(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get('loop_total', counts)
    per_loop = np.repeat(uvk, counts)
    uv = np.zeros(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2) * per_loop[:, None]
    me.uv_layers.active.data.foreach_set('uv', uv.ravel())
    me.attributes.remove(me.attributes['uvk'])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(margin=0.003, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    tris = tri_count(obj)

    if scene.world is None:
        scene.world = bpy.data.worlds.new('w')
    bs = size * supersample
    scene.cycles.samples = 64
    ao = _bake(obj, 'AO', size)
    scene.cycles.samples = 6
    rough = _bake(obj, 'ROUGHNESS', bs)
    normal = _bake(obj, 'NORMAL', bs, normal_space='TANGENT')
    emit = _bake(obj, 'EMIT', bs)
    _route(obj, 'Base Color')
    diffuse = _bake(obj, 'EMIT', bs)
    _route(obj, 'Metallic')
    metal = _bake(obj, 'EMIT', bs)
    _route(obj, 'EdgeMask')
    edge = _bake(obj, 'EMIT', bs)

    if os.environ.get('FORGE_DEBUG'):
        _png(os.path.join(os.path.dirname(out_glb), f'{name.lower()}_edge.png'), _down(edge, supersample))
        _png(os.path.join(os.path.dirname(out_glb), f'{name.lower()}_ao.png'), ao)
    k = supersample
    rough, normal, emit, diffuse, metal, edge = (_down(x, k) for x in (rough, normal, emit, diffuse, metal, edge))
    a = np.clip(ao[..., :3], 0, 1) ** 1.3
    base = diffuse[..., :3]
    # Worn edges: bare bright metal on exposed (not occluded) edges only.
    wear = np.clip(edge[..., :1], 0, 1) * np.clip((ao[..., :1] - 0.45) / 0.25, 0, 1)
    ec = np.array(edge_color or EDGE[ST['faction']], np.float32)
    base = base + (np.maximum(base * ec[3] + ec[:3], base) - base) * wear
    rough = rough * (1 - 0.35 * wear)
    base = base * (ao_floor + (1 - ao_floor) * a)
    if crevice is not None:  # tint the occluded gaps (warm bronze shadow for Kesh)
        base = base * (1 - (1 - a) * (1 - np.array(crevice, np.float32)))
    nv = normal[..., :3] * 2 - 1
    nv /= np.maximum(np.linalg.norm(nv, axis=-1, keepdims=True), 1e-6)
    normal = nv * 0.5 + 0.5
    em = np.clip(emit[..., :3] / EMIT_SCALE, 0, 1)
    orm = np.stack([ao[..., 0], np.clip(rough[..., 0], 0.04, 1), metal[..., 0]], axis=-1)
    bake_dir = os.path.join(os.path.dirname(out_glb), '_bake')
    os.makedirs(bake_dir, exist_ok=True)
    stem = os.path.join(bake_dir, name.lower())
    imgs = {}
    for key, arr, srgb in (('base', _srgb(base), True), ('normal', normal, False), ('orm', orm, False),
                           ('emissive', _srgb(em), True)):
        _png(f'{stem}_{key}.png', arr)
        im = bpy.data.images.load(f'{stem}_{key}.png')
        im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
        imgs[key] = im

    def final_mat(mname, with_emit=True):
        mat = bpy.data.materials.new(mname)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes['Principled BSDF']
        t = {}
        for key in imgs:
            t[key] = nt.nodes.new('ShaderNodeTexImage')
            t[key].image = imgs[key]
        nm = nt.nodes.new('ShaderNodeNormalMap')
        sp = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(t['base'].outputs['Color'], bsdf.inputs['Base Color'])
        nt.links.new(t['normal'].outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        nt.links.new(t['orm'].outputs['Color'], sp.inputs['Color'])
        nt.links.new(sp.outputs['Green'], bsdf.inputs['Roughness'])
        nt.links.new(sp.outputs['Blue'], bsdf.inputs['Metallic'])
        nt.links.new(t['emissive'].outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = EMIT_SCALE
        return mat
    main = final_mat(f'{name}Mat')
    me.materials.clear()
    me.materials.append(main)
    grp = np.zeros(len(me.polygons), dtype=np.int32)
    me.attributes['grp'].data.foreach_get('value', grp)
    if gem:
        me.materials.append(final_mat('OreGem'))
        me.polygons.foreach_set('material_index', (grp >= 100).astype(np.int32))
    else:
        me.polygons.foreach_set('material_index', np.zeros(len(me.polygons), dtype=np.int32))
    grp = grp % 100

    # Split the groups back out.
    made = {}
    if single or len(groups) == 1 and single:
        made[groups[0]] = obj
    else:
        for gi, g in enumerate(groups):
            o = obj.copy()
            o.data = obj.data.copy()
            scene.collection.objects.link(o)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            layer = bm.faces.layers.int['grp']
            dead = [f for f in bm.faces if f[layer] % 100 != gi]
            if dead:
                bmesh.ops.delete(bm, geom=dead, context='FACES')
            bm.to_mesh(o.data)
            bm.free()
            o.name = g
            o.data.name = g
            made[g] = o
        bpy.data.objects.remove(obj)
    for o in made.values():
        if 'grp' in o.data.attributes:
            o.data.attributes.remove(o.data.attributes['grp'])
    root = None
    pivots = {}
    if not single:
        root = bpy.data.objects.new(name, None)
        scene.collection.objects.link(root)
        for g, o in made.items():
            o.parent = root
        plist = [pivot] if pivot and isinstance(pivot[0], str) else (pivot or [])
        for i, (g, loc) in enumerate(plist):
            e = bpy.data.objects.new('TurretPivot' if i == 0 else f'Pivot{i}', None)
            scene.collection.objects.link(e)
            e.parent = root
            e.location = loc
            made[g].parent = e
            made[g].location = tuple(-c for c in loc)
            pivots[g] = e
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_yup=True, export_apply=True,
                              export_image_format='JPEG', export_jpeg_quality=88, export_animations=False)
    info = dict(name=name, file=os.path.basename(out_glb), triangles=tris, texture=size,
                bytes=os.path.getsize(out_glb), parts=len(made))
    print('FORGE', json.dumps(info))
    if report:
        os.makedirs(os.path.dirname(report), exist_ok=True)
        with open(report, 'w') as f:
            json.dump(info, f)
    if render:
        preview(list(made.values()), pivots, render, label or name, tris, views)
    return info


# ------------------------------------------------------------------ preview
def preview(meshes, pivots, path, label, tris, views=None, res=(960, 640), samples=32):
    scene = bpy.context.scene
    for e in pivots.values():
        e.rotation_euler = (0, 0, math.radians(-18))
    bpy.context.view_layer.update()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    c = (lo + hi) / 2
    size = max(hi.x - lo.x, hi.y - lo.y, (hi.z - lo.z) * 1.35)
    rad = (hi - lo).length / 2
    world = bpy.data.worlds.new('Sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    tcn = nt.nodes.new('ShaderNodeTexCoord')
    sepn = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tcn.outputs['Generated'], sepn.inputs[0])
    nt.links.new(sepn.outputs[2], ramp.inputs[0])
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.5, 0.52, 0.5, 1)
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (0.22, 0.38, 0.62, 1)
    nt.links.new(ramp.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.9
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 3.6
    sun.data.angle = math.radians(3)
    sun.data.color = (1.0, 0.95, 0.85)
    sun.rotation_euler = (math.radians(48), math.radians(8), math.radians(-25))
    scene.collection.objects.link(sun)
    bpy.ops.mesh.primitive_plane_add(size=size * 60, location=(c.x, c.y, min(lo.z, 0.0) - 0.002))
    g = bpy.context.object
    gm = bpy.data.materials.new('Ground')
    gm.use_nodes = True
    gn = N(gm)
    nz = gn.noise(0.35 / max(size / 8, 0.3), 8.0)
    gn.out(gn.mix(nz, (0.1, 0.13, 0.05), (0.21, 0.17, 0.1)), 0.95, 0.0)
    gn.bump(gn.noise(3.0, 8.0), 0.6, 0.05)
    g.data.materials.append(gm)
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    shots = []
    for i, v in enumerate(views or ('front34', 'rts')):
        if v == 'front34':
            d, lens = Vector((1.0, -0.85, 0.42)).normalized() * rad * 3.3, 55
        elif v == 'side':
            d, lens = Vector((0.05, -1.0, 0.2)).normalized() * rad * 3.0, 55
        elif v == 'rear34':
            d, lens = Vector((-1.0, 0.8, 0.5)).normalized() * rad * 2.9, 55
        else:
            d, lens = Vector((0.55, -0.8, 1.15)).normalized() * rad * 3.5, 50
        cam.location = c + d
        dd = c - cam.location
        cam.rotation_euler = (math.atan2(math.hypot(dd.x, dd.y), -dd.z), 0, math.atan2(dd.y, dd.x) - math.pi / 2)
        cam.data.lens = lens
        p = f'{path[:-4]}_{i}.png'
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        shots.append(p)
    try:
        from PIL import Image, ImageDraw, ImageFont
        ims = [Image.open(p).convert('RGB') for p in shots]
        sheet = Image.new('RGB', (sum(i.width for i in ims) + 6 * (len(ims) - 1), ims[0].height), (20, 20, 22))
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width + 6
        dr = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
        except OSError:
            font = ImageFont.load_default()
        text = f'{label}  ·  {tris:,} triangles'
        w = dr.textlength(text, font=font)
        dr.rectangle((0, 0, w + 28, 46), fill=(0, 0, 0))
        dr.text((14, 8), text, fill=(255, 255, 255), font=font)
        sheet.save(path, quality=90)
        for p in shots:
            os.remove(p)
    except ImportError:
        pass
