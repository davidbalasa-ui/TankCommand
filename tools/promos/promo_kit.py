"""Promo kit: build a short unit promo scene in Blender (bpy) with a few calls. See README.md.

Conventions: Z up, model front +X, metres, time in seconds (24 fps, frame = t * 24), angles in degrees.
A scene script declares actors, paths, shots and camera moves, then calls P.render().
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time

import bpy
import bmesh
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
FPS = 24
REGISTRY = json.load(open(os.path.join(HERE, 'models.json')))
SEARCH = [p for p in os.environ.get('PROMO_MODELS', '').split(':') if p] + ['/mnt/project-files/promos/models/', os.path.join(REPO, 'public', 'assets', 'models')]

TERRAN_BLUE = (0.25, 0.75, 1.0)
TERRAN_ORANGE = (1.0, 0.55, 0.15)
GOLD = (1.0, 0.72, 0.22)
WHITE_HOT = (1.0, 0.95, 0.8)
SHARD = (0.55, 0.95, 1.0)
SKY_GAIN = float(os.environ.get('SKY_GAIN', 0.25))

TOD = {  # sun elevation, azimuth, sun strength, sun colour, sky strength, horizon haze colour
    'noon': (55, 40, 4.0, (1.0, 0.97, 0.9), 0.6, (0.62, 0.70, 0.78)),
    'morning': (28, -60, 3.5, (1.0, 0.9, 0.78), 0.55, (0.70, 0.72, 0.74)),
    'golden': (12, 110, 3.6, (1.0, 0.72, 0.45), 0.5, (0.80, 0.62, 0.48)),
    'dusk': (4, 150, 2.4, (1.0, 0.55, 0.35), 0.45, (0.55, 0.42, 0.45)),
    'overcast': (60, 20, 1.6, (0.9, 0.93, 1.0), 0.9, (0.60, 0.63, 0.66)),
    'night': (35, -120, 0.7, (0.6, 0.72, 1.0), 0.06, (0.05, 0.07, 0.11)),
}
GROUND = {  # two base colours and a dirt colour
    'dry': ((0.27, 0.23, 0.09), (0.20, 0.19, 0.07), (0.14, 0.10, 0.05)),
    'grass': ((0.10, 0.17, 0.04), (0.22, 0.21, 0.08), (0.12, 0.09, 0.04)),
    'ash': ((0.07, 0.07, 0.075), (0.12, 0.11, 0.10), (0.03, 0.03, 0.03)),
    'red': ((0.30, 0.11, 0.05), (0.22, 0.12, 0.06), (0.12, 0.05, 0.03)),
    'snow': ((0.75, 0.78, 0.82), (0.55, 0.58, 0.62), (0.25, 0.24, 0.22)),
}

# style: shell | tracer | missile | mortar | laser | lightning | beam | bomb | sting
# kick = (hull pitch radians, slide metres, recover seconds); barrel = collapse fraction; boom = impact size
WEAPONS = {
    'cannon': dict(style='shell', speed=40, kick=(0.035, 0.12, 0.5), barrel=0.8, boom=0.9, flash=1.0),
    'heavy_cannon': dict(style='shell', speed=38, kick=(0.07, 0.3, 0.8), barrel=0.8, boom=1.7, flash=1.9, shake=0.12),
    'autocannon': dict(style='tracer', speed=55, kick=(0.012, 0.03, 0.2), barrel=0.8, boom=0.3, flash=0.5, burst=3, interval=0.15),
    'missile': dict(style='missile', speed=30, kick=(0.015, 0.04, 0.3), barrel=0.0, boom=0.9, flash=0.6, burst=4, interval=0.2, pause=0.35),
    'shell': dict(style='mortar', speed=25, kick=(0.16, 0.5, 1.0), barrel=0.8, boom=2.2, flash=2.0, burst=3, interval=0.4, shake=0.15),
    'laser': dict(style='laser', speed=45, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=0.3, flash=0.4, burst=2, interval=0.15),
    'lightning': dict(style='lightning', speed=1e9, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=0.35, flash=0.5, burst=2, interval=0.15),
    'ground_beam': dict(style='beam', speed=1e9, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=1.2, flash=0.8, burst=4, interval=0.12),
    'bombs': dict(style='bomb', speed=20, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=2.4, flash=0.0, burst=3, interval=0.25, shake=0.12),
    'sting': dict(style='lightning', speed=1e9, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=0.5, flash=0.6),
    'shard': dict(style='beam', speed=1e9, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=2.2, flash=1.5, shake=0.15),
    'ship_cannon': dict(style='shell', speed=120, kick=(0.0, 0.0, 0.3), barrel=0.8, boom=2.5, flash=2.5),
    'ship_laser': dict(style='laser', speed=220, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=1.0, flash=1.0),
    'ship_missile': dict(style='missile', speed=60, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=3.0, flash=1.2, burst=4, interval=0.2, pause=0.35),
    'ship_beam': dict(style='beam', speed=1e9, kick=(0.0, 0.0, 0.2), barrel=0.0, boom=3.0, flash=2.0),
}


# ---------------------------------------------------------------- small helpers
def V(p, z=None):
    if isinstance(p, Vector):
        return p.copy()
    p = tuple(p)
    if len(p) == 2:
        return Vector((p[0], p[1], 0.0 if z is None else z))
    return Vector(p[:3])


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return a + (b - a) * k


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def frame_of(t):
    return int(round(t * FPS))


def key(obj, path, t, value=None, index=-1):
    """Set a property (optional) and keyframe it at time t seconds."""
    if value is not None:
        if index >= 0:
            getattr(obj, path)[index] = value
        else:
            setattr(obj, path, value)
    obj.keyframe_insert(path, frame=t * FPS, index=index)


def _kf(obj, path, f, value):
    setattr(obj, path, value)
    obj.keyframe_insert(path, frame=f)


def show(obj, t0, t1, scale=1.0):
    """Visible (at `scale`) only from t0 to t1."""
    s = (scale,) * 3 if isinstance(scale, (int, float)) else tuple(scale)
    f0, f1 = frame_of(t0), max(frame_of(t0), frame_of(t1))
    _kf(obj, 'scale', f0 - 1, (0, 0, 0))
    _kf(obj, 'scale', f0, s)
    _kf(obj, 'scale', f1, s)
    _kf(obj, 'scale', f1 + 1, (0, 0, 0))


def hit_curve(x, attack=0.05, recover=0.45):
    if x < 0:
        return 0.0
    if x < attack:
        return x / attack
    u = (x - attack) / recover
    return (1 - u) ** 2 if u < 1 else 0.0


def gl_vec(v):  # glTF (Y up) vector -> Blender
    return Vector((v[0], -v[2], v[1]))


def gl_quat(q):  # glTF [x,y,z,w] -> Blender Quaternion
    return Quaternion((q[3], q[0], -q[2], q[1]))


def plain(v):
    try:
        return v.to_dict()
    except Exception:
        try:
            return list(v)
        except Exception:
            return v


def resolve(target, t):
    """World position of a target (Actor, point, or function of time) at time t."""
    if isinstance(target, Actor):
        return target.center(t)
    if callable(target):
        return V(target(t))
    return V(target)


class Path:
    """Smooth timed path through (t, x, y[, z]) waypoints. Holds position before the first and after the last."""

    def __init__(self, pts, z=0.0):
        pts = sorted(pts, key=lambda p: p[0])
        self.t = [p[0] for p in pts]
        self.p = [Vector((p[1], p[2], p[3] if len(p) > 3 else z)) for p in pts]
        n = len(pts)
        self.m = []
        for i in range(n):
            if i == 0 or i == n - 1:
                self.m.append(Vector((0, 0, 0)) if n < 2 else ((self.p[1] - self.p[0]) / max(1e-6, self.t[1] - self.t[0]) if i == 0 else (self.p[-1] - self.p[-2]) / max(1e-6, self.t[-1] - self.t[-2])) * 0.0)
            else:
                a, b = self.p[i] - self.p[i - 1], self.p[i + 1] - self.p[i]
                if a.length < 1e-4 or b.length < 1e-4:
                    self.m.append(Vector((0, 0, 0)))
                else:
                    self.m.append((self.p[i + 1] - self.p[i - 1]) / (self.t[i + 1] - self.t[i - 1]))

    def moving_ends(self):
        """Keep speed at the first and last waypoint (enter and leave the frame moving)."""
        if len(self.p) > 1:
            self.m[0] = (self.p[1] - self.p[0]) / (self.t[1] - self.t[0])
            self.m[-1] = (self.p[-1] - self.p[-2]) / (self.t[-1] - self.t[-2])
        return self

    def __call__(self, t):
        if t <= self.t[0]:
            return self.p[0] + self.m[0] * (t - self.t[0])
        if t >= self.t[-1]:
            return self.p[-1] + self.m[-1] * (t - self.t[-1])
        i = max(j for j in range(len(self.t)) if self.t[j] <= t)
        h = self.t[i + 1] - self.t[i]
        u = (t - self.t[i]) / h
        u2, u3 = u * u, u * u * u
        return ((2 * u3 - 3 * u2 + 1) * self.p[i] + (u3 - 2 * u2 + u) * h * self.m[i] + (-2 * u3 + 3 * u2) * self.p[i + 1] + (u3 - u2) * h * self.m[i + 1])


# ---------------------------------------------------------------- materials
_MATS = {}


def blob_mat(kind):
    """Soft-edged blob material coloured by the object's colour (rgb) and faded by its alpha.
    kinds: glow (emission 6), hot (30), beam (hard-edged emission 14), smoke (lit, noisy), shield."""
    if kind in _MATS:
        return _MATS[kind]
    m = bpy.data.materials.new('fx_' + kind)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    out = N('ShaderNodeOutputMaterial')
    info = N('ShaderNodeObjectInfo')
    lw = N('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    inv = N('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])
    pw = N('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6 if kind != 'smoke' else 1.1
    nt.links.new(inv.outputs[0], pw.inputs[0])
    mul = N('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(info.outputs['Alpha'], mul.inputs[0])
    tr = N('ShaderNodeBsdfTransparent')
    mix = N('ShaderNodeMixShader')
    if kind == 'smoke':
        sh = N('ShaderNodeBsdfDiffuse')
        nt.links.new(info.outputs['Color'], sh.inputs['Color'])
        tc = N('ShaderNodeTexCoord')
        nz = N('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.2; nz.inputs['Detail'].default_value = 3
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        rmp = N('ShaderNodeMapRange'); rmp.inputs[1].default_value = 0.35; rmp.inputs[2].default_value = 0.7
        nt.links.new(nz.outputs[0], rmp.inputs[0])
        m2 = N('ShaderNodeMath'); m2.operation = 'MULTIPLY'
        nt.links.new(pw.outputs[0], m2.inputs[0]); nt.links.new(rmp.outputs[0], m2.inputs[1])
        nt.links.new(m2.outputs[0], mul.inputs[1])
    elif kind == 'shield':
        sh = N('ShaderNodeEmission'); sh.inputs['Strength'].default_value = 3.0
        nt.links.new(info.outputs['Color'], sh.inputs['Color'])
        tc = N('ShaderNodeTexCoord')
        vor = N('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 7.0
        nt.links.new(tc.outputs['Object'], vor.inputs['Vector'])
        edge = N('ShaderNodeMapRange'); edge.inputs[1].default_value = 0.0; edge.inputs[2].default_value = 0.06; edge.inputs[3].default_value = 1.0; edge.inputs[4].default_value = 0.0
        nt.links.new(vor.outputs['Distance'], edge.inputs[0])
        rim = N('ShaderNodeMath'); rim.operation = 'POWER'; rim.inputs[1].default_value = 2.5
        nt.links.new(lw.outputs['Facing'], rim.inputs[0])
        add = N('ShaderNodeMath'); add.operation = 'ADD'
        nt.links.new(rim.outputs[0], add.inputs[0])
        e2 = N('ShaderNodeMath'); e2.operation = 'MULTIPLY'; e2.inputs[1].default_value = 0.55
        nt.links.new(edge.outputs[0], e2.inputs[0]); nt.links.new(e2.outputs[0], add.inputs[1])
        base = N('ShaderNodeMath'); base.operation = 'ADD'; base.inputs[1].default_value = 0.04
        nt.links.new(add.outputs[0], base.inputs[0])
        nt.links.new(base.outputs[0], mul.inputs[1])
    else:
        sh = N('ShaderNodeEmission')
        sh.inputs['Strength'].default_value = {'glow': 6.0, 'hot': 30.0, 'beam': 14.0}[kind]
        nt.links.new(info.outputs['Color'], sh.inputs['Color'])
        if kind == 'beam':
            mul.inputs[1].default_value = 1.0
        else:
            nt.links.new(pw.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(sh.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    _MATS[kind] = m
    return m


def solid_mat(name, color, rough=0.8, emit=None, strength=1.0):
    k = 'solid_' + name
    if k in _MATS:
        return _MATS[k]
    m = bpy.data.materials.new(k)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = strength
    _MATS[k] = m
    return m


_MESH = {}


def _mesh(kind):
    if kind in _MESH:
        return _MESH[kind]
    bm = bmesh.new()
    if kind == 'ball':
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    elif kind == 'chunk':
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        r = random.Random(4)
        for v in bm.verts:
            v.co *= r.uniform(0.6, 1.2)
    elif kind == 'rod':  # unit length along +X from the origin, radius 1
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=1.0, radius2=1.0, depth=1.0)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0.5, 0, 0))
    elif kind == 'disc':
        bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=1.0)
    elif kind == 'shell':
        bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    me = bpy.data.meshes.new('fx_' + kind)
    bm.to_mesh(me)
    bm.free()
    if kind in ('ball', 'shell', 'rod'):
        for p in me.polygons:
            p.use_smooth = True
    _MESH[kind] = me
    return me


# ---------------------------------------------------------------- actor
class Actor:
    """One loaded model. Hierarchy: root (path position + heading) > body (kick, bob, bank) > model (scaled import)."""

    def __init__(self, promo, name, at, heading, scale, glow):
        self.P = promo
        self.name = name
        self.info = dict(REGISTRY.get(name, {}))
        self.faction = self.info.get('faction', 'neutral')
        self.kind = self.info.get('kind', 'prop')
        self.root = bpy.data.objects.new(name + '_root', None)
        self.body = bpy.data.objects.new(name + '_body', None)
        for o in (self.root, self.body):
            promo.scene.collection.objects.link(o)
            o.empty_display_size = 0.2
        self.body.parent = self.root
        self.root.rotation_mode = 'ZYX'
        self.model, self.objects, self.fire_tag = promo._import(name)
        self.model.parent = self.body
        self.parts = {}
        for o in self.objects:
            base = o.name.split('.')[0]
            self.parts.setdefault(base, o)
        lo, hi = self._bounds()
        self.native_lo, self.native_hi = lo, hi
        native = max(hi.x - lo.x, hi.y - lo.y, 1e-6) if self.kind != 'ship' else 1.0
        size = self.info.get('size')
        self.scale = scale if scale else (size / native if size and self.kind != 'ship' else 1.0)
        self.model.scale = (self.scale,) * 3
        self.length = (hi.x - lo.x) * self.scale
        self.width = (hi.y - lo.y) * self.scale
        self.height = (hi.z - lo.z) * self.scale
        self.radius = 0.5 * max(self.length, self.width)
        self.mid = (lo + hi) * 0.5 * self.scale  # local centre
        z0 = at[2] if len(at) > 2 else (promo.air_height if self.kind == 'air' and promo.env == 'ground' else 0.0)
        self.path = Path([(0.0, at[0], at[1], z0)])
        self.heading0 = math.radians(heading)
        self.reverse = False
        self.faces = []      # heading overrides (t0, t1, target, until)
        self.rot_keys = None  # explicit (t, yaw, pitch, roll)
        self.aims = []       # turret (t0, t1, target, until)
        self.shots = []      # (t, yaw, kick, barrel index, collapse, volley start)
        self.volleys = []
        self.states = {'mining': [], 'working': []}
        self.t_show, self.t_hide = None, None
        self.skip = set()
        self.unfold = None
        self.bob = 0.06 if self.kind == 'hover' else 0.15 if self.kind == 'air' else 0.0
        self.bank = 0.5 if self.kind in ('air', 'ship') else 0.12 if self.kind == 'hover' else 0.0
        self.dust = self.kind == 'ground' and promo.env == 'ground' and self.faction != 'neutral'
        self.turn_rate = math.radians(240)
        self._hd = None
        self._boost(glow)
        self.pivot = self.parts.get('TurretPivot')
        self.barrels, self.muzzles = [], []
        self._shot_n = 0
        if self.kind in ('ground', 'hover', 'air', 'tower', 'structure') and self.info.get('weapon'):
            self._find_barrels()
        self._tags = self._read_tags()
        self._auto_fx()

    # ---- setup
    def _bounds(self, skip=()):
        bpy.context.view_layer.update()
        inv = self.model.matrix_world.inverted()
        lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
        for o in self.objects:
            if o.type != 'MESH' or o.name in skip or o.get('hideWhenDeployed'):
                continue
            for c in o.bound_box:
                w = inv @ (o.matrix_world @ Vector(c))
                lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        if lo.x > hi.x:
            lo = hi = Vector((0, 0, 0))
        return lo, hi

    def _boost(self, glow):
        if not glow or glow == 1.0:
            return
        for o in self.objects:
            if o.type != 'MESH':
                continue
            for s in o.material_slots:
                m = s.material
                if not m or not m.use_nodes or m.get('promo_boost'):
                    continue
                for n in m.node_tree.nodes:
                    if n.type == 'BSDF_PRINCIPLED' and (n.inputs['Emission Color'].is_linked or n.inputs['Emission Strength'].default_value > 0):
                        n.inputs['Emission Strength'].default_value = max(1.0, n.inputs['Emission Strength'].default_value) * glow
                m['promo_boost'] = 1

    def _find_barrels(self):
        """Split gun barrels out of the turret mesh so they can telescope. Works on loose mesh islands."""
        src = [o for o in self.objects if o.type == 'MESH' and o.parent == self.pivot] if self.pivot else []
        tagged = any(k.startswith('Barrel') for k in self.parts)
        if tagged or not src:
            self._default_muzzle()
            return
        t = src[0]
        me = t.data
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        seen, islands = set(), []
        for v in bm.verts:
            if v.index in seen:
                continue
            stack, isl = [v], []
            seen.add(v.index)
            while stack:
                a = stack.pop(); isl.append(a.index)
                for e in a.link_edges:
                    b = e.other_vert(a)
                    if b.index not in seen:
                        seen.add(b.index); stack.append(b)
            cs = [bm.verts[i].co for i in isl]
            lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
            hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
            islands.append((isl, lo, hi))
        px = (t.matrix_local.inverted() @ Vector((0, 0, 0))).x
        txmax = max(i[2].x for i in islands)
        reach = txmax - px
        cands = []
        for isl, lo, hi in islands:
            L, thick = hi.x - lo.x, max(hi.y - lo.y, hi.z - lo.z)
            if L > 2.2 * thick and L > 0.25 * reach and hi.x > px + 0.55 * reach:
                cands.append((isl, lo, hi))
        clusters = []
        for c in cands:
            cy, cz = (c[1].y + c[2].y) / 2, (c[1].z + c[2].z) / 2
            tol = max(c[2].y - c[1].y, c[2].z - c[1].z) * 1.2
            for cl in clusters:
                if abs(cl['y'] - cy) < tol and abs(cl['z'] - cz) < tol:
                    cl['isl'].append(c); break
            else:
                clusters.append(dict(y=cy, z=cz, isl=[c], tol=tol))
        used = {id(c[0]) for c in cands}
        for cl in clusters:
            xmin = min(c[1].x for c in cl['isl']); xmax = max(c[2].x for c in cl['isl'])
            for isl in islands:
                if id(isl[0]) in used:
                    continue
                c = (isl[1] + isl[2]) / 2
                d = max(isl[2].x - isl[1].x, isl[2].y - isl[1].y, isl[2].z - isl[1].z)
                if abs(c.y - cl['y']) < cl['tol'] and abs(c.z - cl['z']) < cl['tol'] and c.x > xmin + 0.3 * (xmax - xmin) and d < 0.5 * (xmax - xmin):
                    cl['isl'].append(isl); used.add(id(isl[0]))
            cl['xmin'] = xmin
            cl['xmax'] = max(c[2].x for c in cl['isl'])
        bm.free()
        if not clusters:
            self._default_muzzle()
            return
        clusters.sort(key=lambda c: -c['y'])
        allb = set()
        for cl in clusters:
            idx = set(i for c in cl['isl'] for i in c[0])
            allb |= idx
            nm = me.copy()
            b2 = bmesh.new(); b2.from_mesh(nm); b2.verts.ensure_lookup_table()
            bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.index not in idx], context='VERTS')
            breech = Vector((cl['xmin'], cl['y'], cl['z']))
            bmesh.ops.translate(b2, verts=b2.verts, vec=-breech)
            b2.to_mesh(nm); b2.free()
            ob = bpy.data.objects.new(self.name + '_barrel', nm)
            self.P.scene.collection.objects.link(ob)
            ob.parent = self.pivot
            ob.matrix_local = t.matrix_local @ Matrix.Translation(breech)
            self.objects.append(ob)
            self.barrels.append(ob)
            tip = t.matrix_local @ Vector((cl['xmax'], cl['y'], cl['z']))
            self.muzzles.append(self.pivot.matrix_local @ tip)
        b3 = bmesh.new(); b3.from_mesh(me); b3.verts.ensure_lookup_table()
        bmesh.ops.delete(b3, geom=[v for v in b3.verts if v.index in allb], context='VERTS')
        b3.to_mesh(me); b3.free()

    def _default_muzzle(self):
        flashes = [o for n, o in self.parts.items() if n.startswith('Flash')]
        bpy.context.view_layer.update()
        inv = self.model.matrix_world.inverted()
        if flashes:
            self.muzzles = [inv @ o.matrix_world.translation for o in flashes]
            return
        src = [o for o in self.objects if o.type == 'MESH' and self.pivot and o.parent == self.pivot]
        if src:
            pts = [inv @ (o.matrix_world @ Vector(c)) for o in src for c in o.bound_box]
            self.muzzles = [Vector((max(p.x for p in pts), sum(p.y for p in pts) / len(pts), (min(p.z for p in pts) + max(p.z for p in pts)) / 2))]
        else:
            lo, hi = self.native_lo, self.native_hi
            self.muzzles = [Vector((hi.x * 0.9, 0, (lo.z + hi.z) / 2))]

    def _read_tags(self):
        tags = []
        for o in self.objects:
            a = o.get('anim')
            if a is not None:
                tags.append((o, plain(a)))
        return tags

    def _auto_fx(self):
        if self.P.env == 'ground' and self.faction == 'arcadian' and self.kind == 'hover':
            lo, hi = self.native_lo * self.scale, self.native_hi * self.scale
            gap = max(0.15, lo.z)
            for x in (lo.x * 0.45, hi.x * 0.35):
                self.arcs([(x, 0, lo.z + 0.05)], direction=(0, 0, -1), length=gap * 1.1, width=0.03, spread=0.6)
        if self.faction == 'arcadian' and self.kind == 'air':
            lo, hi = self.native_lo * self.scale, self.native_hi * self.scale
            self.arcs([(lo.x * 0.9, 0, (lo.z + hi.z) / 2)], direction=(-1, 0, 0), length=self.length * 0.3, width=0.04, spread=0.5)
        if self.faction == 'terran' and self.kind == 'air':
            lo, hi = self.native_lo * self.scale, self.native_hi * self.scale
            self.engines([(lo.x * 0.95, s * self.width * 0.12, (lo.z + hi.z) / 2) for s in (-1, 1)], size=self.width * 0.05)

    # ---- queries
    def part(self, name, manual=True):
        """Blender object of a named model node. manual=True stops the kit's own animation of that node."""
        o = self.parts.get(name)
        if o is None:
            raise KeyError(f'{self.name} has no part {name}; parts: {sorted(self.parts)}')
        if manual:
            self.skip.add(o.name)
        return o

    def has(self, name):
        return name in self.parts

    def pos(self, t):
        return self.path(t)

    def center(self, t):
        return self.path(t) + Vector((0, 0, self.mid.z))

    def top(self, t):
        return self.path(t) + Vector((0, 0, self.native_hi.z * self.scale))

    def _headings(self):
        if self._hd is not None:
            return self._hd
        n = self.P.frames + 1
        out, h = [], self.heading0
        dt = 1.0 / FPS
        for f in range(-12, n):
            t = f * dt
            v = (self.path(t + dt * 0.5) - self.path(t - dt * 0.5)) / dt
            want = h
            if Vector((v.x, v.y)).length > 0.4:
                want = math.atan2(v.y, v.x) + (math.pi if self.reverse else 0)
            for (t0, t1, tgt, until) in self.faces:
                if t0 <= t <= until:
                    d = resolve(tgt, t) - self.path(t)
                    want = h + wrap(math.atan2(d.y, d.x) - h) * smooth((t - t0) / max(1e-3, t1 - t0))
            step = self.turn_rate * dt
            d = wrap(want - h)
            h += max(-step, min(step, d)) if f >= 0 else d
            if f >= 0:
                out.append(h)
        self._hd = out
        return out

    def heading(self, t):
        hd = self._headings()
        x = max(0.0, min(len(hd) - 1.001, t * FPS))
        i = int(x)
        return hd[i] + wrap(hd[i + 1] - hd[i]) * (x - i)

    def speed(self, t):
        return ((self.path(t + 0.02) - self.path(t - 0.02)) / 0.04).length

    def local(self, p, t):
        """World position of a body-local point (metres, already scaled) at time t (ignores pitch/bank)."""
        return self.path(t) + Matrix.Rotation(self.heading(t), 3, 'Z') @ V(p)

    def muzzle(self, t, toward=None, i=0):
        """World position of muzzle i at time t with the turret pointing at `toward`."""
        m = self.muzzles[i % len(self.muzzles)] * self.scale if self.muzzles else Vector((self.length / 2, 0, self.height / 2))
        h = self.heading(t)
        if self.pivot is not None and toward is not None:
            pv = self.pivot.matrix_local.translation * self.scale
            d = toward - self.local(pv, t)
            yaw = math.atan2(d.y, d.x)
            return self.local(Vector((pv.x, pv.y, 0)), t) + Matrix.Rotation(yaw, 3, 'Z') @ Vector((m.x - pv.x, m.y - pv.y, 0)) + Vector((0, 0, m.z))
        return self.local(m, t)

    # ---- declarations
    def drive(self, pts, reverse=False, keep_speed=False):
        """Move through (t, x, y) waypoints (ground/hover) with the nose following the path."""
        z = self.path.p[0].z
        self.path = Path([(p[0], p[1], p[2], p[3] if len(p) > 3 else z) for p in pts])
        if keep_speed:
            self.path.moving_ends()
        self.reverse = reverse
        self._hd = None
        return self

    def fly(self, pts, keep_speed=True):
        """Move through (t, x, y, z) waypoints with heading, pitch and bank from the path."""
        self.path = Path(pts)
        if keep_speed:
            self.path.moving_ends()
        self._hd = None
        return self

    def face(self, target, t0, t1, until=None):
        """Turn the whole hull to face a target between t0 and t1, then keep facing it until `until`."""
        self.faces.append((t0, t1, target, until if until is not None else t1))
        self._hd = None
        return self

    def rotate(self, keys):
        """Explicit orientation keys (t, yaw, pitch, roll) in degrees, replacing path-derived orientation (ships)."""
        self.rot_keys = sorted(keys)
        return self

    def aim(self, target, t0, t1=None, until=None):
        """Slew the turret onto a target between t0 and t1 and track it until `until` (default: end of clip)."""
        t1 = t0 + 0.5 if t1 is None else t1
        self.aims.append((t0, t1, target, until if until is not None else 1e9))
        return self

    def state(self, name, t0, t1):
        """Mark an interval as 'mining' or 'working' so tagged parts (drill drum, crane, repair arm) run."""
        self.states.setdefault(name, []).append((t0, t1))
        return self

    def appear(self, t):
        self.t_show = t
        return self

    def vanish(self, t):
        self.t_hide = t
        return self

    def visible(self, t):
        return (self.t_show is None or t >= self.t_show) and (self.t_hide is None or t < self.t_hide)

    def set_unfold(self, t0, t1):
        """Tower: stay in the packed (vehicle) pose until t0, then unfold into the structure by t1."""
        self.unfold = (t0, t1)
        parts = [o for o in self.objects if o.get('packed') is not None]
        keep = [(o, o.location.copy(), o.rotation_mode, o.rotation_quaternion.copy(), o.rotation_euler.copy(), o.scale.copy()) for o in parts]
        lo, hi = self._bounds()
        self._dc = (lo + hi) / 2
        for o in parts:
            pk = plain(o['packed'])
            o.rotation_mode = 'QUATERNION'
            o.location = gl_vec(pk['p']); o.rotation_quaternion = gl_quat(pk['r']); o.scale = (pk['s'][0], pk['s'][2], pk['s'][1])
        hid = [o for o in self.objects if o.get('hideWhenDeployed')]
        for o in hid:
            o['_h'] = o.pop('hideWhenDeployed')
        lo, hi = self._bounds()
        for o in hid:
            o['hideWhenDeployed'] = o.pop('_h')
        self._pc = (lo + hi) / 2
        for o, l, rm, q, e, sc in keep:
            o.location = l; o.rotation_quaternion = q; o.rotation_mode = rm; o.rotation_euler = e; o.scale = sc
        return self

    def arcs(self, points, direction=(-1, 0, 0), length=1.0, width=0.04, color=GOLD, spread=0.5, t0=0.0, t1=None, when=None):
        """Flickering lightning at body-local points (Arcadian lift and thrust). when='moving' shows it only while moving."""
        for p in points:
            self.P._arc_emitter(self, V(p), V(direction).normalized(), length, width, color, spread, t0, t1, when)
        return self

    def engines(self, points=None, size=None, color=TERRAN_BLUE, length=4.0, t0=0.0, t1=None):
        """Terran engine glow (blue-white ion flame) at body-local points; default one at the stern."""
        lo, hi = self.native_lo * self.scale, self.native_hi * self.scale
        size = size or self.width * 0.08
        points = points or [(lo.x, 0, (lo.z + hi.z) / 2)]
        for p in points:
            self.P._engine(self, V(p), size, color, length, t0, t1)
        return self

    def fire(self, t, target, weapon=None, burst=None, interval=None, pause=None, speed=None, miss=None, damage=True,
             kills=False, boom=None, color=None, muzzle=None, aim=True):
        """Fire a volley at `target` starting at time t. Returns the list of impact times.
        weapon: a WEAPONS preset name (default: this model's game weapon id). burst/interval/pause/speed override it.
        miss=(dx,dy,dz) offsets the impact point; damage=False skips hit sparks on the target; kills=True destroys it
        at the last impact; muzzle=(x,y,z) body-local override for models without a turret."""
        info = self.info.get('weapon', {})
        wname = weapon or info.get('id') or ('cannon' if self.kind != 'ship' else 'ship_laser')
        w = dict(WEAPONS[wname])
        burst = burst or info.get('burst') if weapon is None and burst is None else (burst or w.get('burst', 1))
        burst = burst or w.get('burst', 1)
        interval = interval if interval is not None else (info.get('burstIntervalSec') if weapon is None else None) or w.get('interval', 0.2)
        pause = pause if pause is not None else w.get('pause', 0.0)
        spd = speed or (info.get('projectileSpeed') if weapon is None and w['speed'] < 1e8 else None) or w['speed']
        if aim and self.pivot is not None and not any(a[0] <= t <= a[3] for a in self.aims):
            self.aim(target, max(0.0, t - 0.6), t, until=t + pause + burst * interval + 0.5)
        impacts = []
        self.volleys.append(t)
        for i in range(burst):
            ts = t + pause + i * interval
            tp = resolve(target, ts)
            if muzzle is not None:
                org = self.local(V(muzzle), ts)
            else:
                org = self.muzzle(ts, tp, self._shot_n)
            fl = (tp - org).length / spd
            if w['style'] in ('mortar', 'bomb'):
                fl = max(fl, 0.9) if w['style'] == 'mortar' else math.sqrt(max(0.1, 2 * max(0.5, org.z - tp.z) / 9.8))
            tp = resolve(target, ts + fl)
            if miss is not None:
                tp = tp + V(miss)
            d = tp - org
            yaw = math.atan2(d.y, d.x)
            bi = self._shot_n % max(1, len(self.barrels)) if self.barrels else 0
            self.shots.append(dict(t=ts, yaw=yaw, kick=w['kick'], barrel=bi, collapse=w['barrel'] if self.faction == 'terran' else min(w['barrel'], 0.25)))
            self._shot_n += 1
            ti = self.P._projectile(self, w, org, tp, ts, fl, target, color, boom if boom is not None else w['boom'], i)
            impacts.append(ti)
            if w.get('shake'):
                self.P.shake(ts if w['style'] != 'bomb' else ti, w['shake'], 0.35)
            if isinstance(target, Actor) and damage and miss is None:
                target.hit(ti, pos=tp, size=0.25 + 0.2 * (boom if boom is not None else w['boom']), spark_only=True)
        if kills and isinstance(target, Actor):
            target.destroy(impacts[-1])
        return impacts

    def hit(self, t, pos=None, size=0.5, spark_only=False):
        """Show a hit on this actor at time t."""
        p = V(pos) if pos is not None else self.center(t) + Vector((self.P.rng.uniform(-.3, .3), self.P.rng.uniform(-.3, .3), self.P.rng.uniform(0, .3))) * self.radius
        self.P.sparks(p, t, size)
        if not spark_only:
            self.P.explosion(p, t, size, ground=False)
        return self

    def destroy(self, t, size=None, wreck=True):
        """Blow the actor up at time t: explosion, then it is gone, leaving a burning wreck on the ground."""
        size = size or max(1.2, self.radius * 0.9)
        c = self.center(t)
        on_ground = self.P.env == 'ground' and c.z < 3.0
        self.P.explosion(c, t, size, ground=on_ground)
        self.P.shake(t, 0.1 + 0.03 * size, 0.5)
        self.vanish(t + 1.5 / FPS)
        if wreck and on_ground:
            self.P.wreck(self.pos(t), t, self.radius)
        elif wreck and self.P.env == 'ground':
            self.P.falling_wreck(c, (self.path(t) - self.path(t - 0.05)) / 0.05, t, self.radius)
        return self

    # ---- baking
    def _state(self, when, t):
        if when in (None, 'always'):
            return True
        if when == 'moving':
            return self.speed(t) > 0.3
        return any(a <= t <= b for a, b in self.states.get(when, []))

    def _bake(self):
        P = self.P
        n = P.frames
        hd = self._headings()
        dt = 1.0 / FPS
        rest = {o.name: (o.location.copy(), o.rotation_euler.copy() if o.rotation_mode != 'QUATERNION' else None, o.scale.copy(), o.rotation_quaternion.copy()) for o in self.objects}
        turret_yaw = None
        phases = {}
        rng = random.Random(hash(self.name) % 1000 + len(P.actors))
        flick = {}
        unfold_parts = []
        if self.unfold:
            for o in self.objects:
                pk = o.get('packed')
                if pk is not None:
                    pk = plain(pk)
                    o.rotation_mode = 'QUATERNION'
                    bpy.context.view_layer.update()
                    unfold_parts.append((o, gl_vec(pk['p']), gl_quat(pk['r']), Vector((pk['s'][0], pk['s'][2], pk['s'][1])),
                                         o.location.copy(), o.rotation_quaternion.copy(), o.scale.copy()))
        bob_ph = rng.uniform(0, 6.28)
        pivot_rest = (self.pivot.rotation_quaternion.copy() if self.pivot.rotation_mode == 'QUATERNION' else self.pivot.rotation_euler.to_quaternion()) if self.pivot is not None else None
        scroll = self._tread_setup() if any(a.get('type') == 'scroll' for _, a in self._tags) else None
        scroll_x = 0.0
        prev_bank = 0.0
        for f in range(0, n + 1):
            t = f * dt
            p = self.path(t)
            h = hd[min(f, len(hd) - 1)]
            vis = self.visible(t)
            # root
            pitch = roll = 0.0
            if self.rot_keys:
                ks = self.rot_keys
                if t <= ks[0][0]:
                    yw, pitch, roll = ks[0][1:4]
                elif t >= ks[-1][0]:
                    yw, pitch, roll = ks[-1][1:4]
                else:
                    i = max(j for j in range(len(ks)) if ks[j][0] <= t)
                    u = smooth((t - ks[i][0]) / (ks[i + 1][0] - ks[i][0]))
                    yw, pitch, roll = (lerp(ks[i][k], ks[i + 1][k], u) for k in (1, 2, 3))
                h, pitch, roll = math.radians(yw), math.radians(pitch), math.radians(roll)
            elif self.kind in ('air', 'ship'):
                v = (self.path(t + dt) - self.path(t - dt)) / (2 * dt)
                hs = Vector((v.x, v.y)).length
                if hs > 0.5:
                    pitch = math.atan2(v.z, hs)
            if self.bank and not self.rot_keys:
                h0 = hd[max(0, f - 2)]; h1 = hd[min(len(hd) - 1, f + 2)]
                rate = wrap(h1 - h0) / (4 * dt)
                want = max(-1.0, min(1.0, -rate * self.bank * (0.5 if self.kind != 'hover' else 0.3)))
                prev_bank = lerp(prev_bank, want, 0.25)
                roll = -prev_bank
            self.root.location = p
            self.root.rotation_euler = Euler((roll, -pitch, h), 'ZYX')
            self.root.keyframe_insert('location', frame=f)
            self.root.keyframe_insert('rotation_euler', frame=f)
            # body: visibility, bob, kick
            kx = ky = sl_x = sl_y = 0.0
            for s in self.shots:
                x = t - s['t']
                if x < 0 or x > 2.5:
                    continue
                kick, slide, rec = s['kick']
                if kick == 0 and slide == 0:
                    continue
                a = 0.05
                amp = x / a if x < a else math.exp(-4 * (x - a) / rec) * math.cos(6 * (x - a) / rec)
                phi = s['yaw'] - h
                kx += kick * amp * math.sin(phi); ky += -kick * amp * math.cos(phi)
                sl_x += -slide * amp * math.cos(phi); sl_y += -slide * amp * math.sin(phi)
            bz = self.bob * math.sin(t * 2.2 + bob_ph) if self.bob else 0.0
            self.body.location = (sl_x, sl_y, bz)
            self.body.rotation_euler = (kx, ky, 0)
            self.body.scale = (1, 1, 1) if vis else (0, 0, 0)
            self.body.keyframe_insert('location', frame=f)
            self.body.keyframe_insert('rotation_euler', frame=f)
            self.body.keyframe_insert('scale', frame=f)
            # turret
            if self.pivot is not None and self.pivot.name not in self.skip and not any(o is self.pivot and a.get('type') == 'spin' for o, a in self._tags):
                want = h
                for (t0, t1, tgt, until) in self.aims:
                    if t0 <= t <= until:
                        pv = self.local(self.pivot.matrix_local.translation * self.scale, t)
                        d = resolve(tgt, t) - pv
                        cur = turret_yaw if turret_yaw is not None else h
                        want = cur + wrap(math.atan2(d.y, d.x) - cur) * smooth((t - t0) / max(1e-3, t1 - t0))
                if turret_yaw is None:
                    turret_yaw = want
                step = math.radians(200) * dt
                turret_yaw += max(-step, min(step, wrap(want - turret_yaw)))
                if not (self.unfold and t < self.unfold[1]):
                    self.pivot.rotation_mode = 'QUATERNION'
                    self.pivot.rotation_quaternion = pivot_rest @ Quaternion((0, 0, 1), wrap(turret_yaw - h))
                    self.pivot.keyframe_insert('rotation_quaternion', frame=f)
            # barrels (auto-detected): telescope back toward the breech
            for bi, b in enumerate(self.barrels):
                c = 0.0
                for s in self.shots:
                    if s['barrel'] == bi:
                        c = max(c, s['collapse'] * hit_curve(t - s['t'], 0.05, 0.55))
                b.scale = (1 - c, 1, 1)
                b.keyframe_insert('scale', frame=f)
            # unfold
            if self.unfold:
                t0, t1 = self.unfold
                u = (t - t0) / max(1e-3, t1 - t0)
                body_k = 1.0 if u >= 1 else smooth(u / 0.4)
                k = 1.0 if u >= 1 else smooth((u - 0.2) / 0.8)
                cc = self._pc.lerp(self._dc, body_k)
                self.model.location = (-cc.x * self.scale, -cc.y * self.scale, 0)
                self.model.keyframe_insert('location', frame=f)
                for i, (o, pp, pq, ps, dp, dq, ds) in enumerate(unfold_parts):
                    if o is self.pivot and u >= 1.0:
                        continue
                    o.location = pp.lerp(dp, k)
                    o.rotation_quaternion = pq.slerp(dq, k)
                    sc = ps.lerp(ds, k)
                    if o.get('hideWhenDeployed') and u >= 1.0:
                        sc = Vector((0, 0, 0))
                    o.scale = sc
                    o.keyframe_insert('location', frame=f)
                    o.keyframe_insert('rotation_quaternion', frame=f)
                    o.keyframe_insert('scale', frame=f)
            elif f == 0:
                for o in self.objects:
                    if o.get('hideWhenDeployed'):
                        o.scale = (0, 0, 0)
            # tagged parts
            tf = min([t - v for v in self.volleys if t >= v] or [1e9])
            tick_cache = {}
            for o, a in self._tags:
                if o.name in self.skip or (self.unfold and o.get('packed') is not None and t < self.unfold[1]):
                    continue
                ty = a.get('type')
                on = self._state(a.get('when'), t)
                r = rest[o.name]
                if ty == 'spin':
                    sp = a.get('speed', 1.0)
                    if a.get('busySpeed') and self._state('working', t):
                        sp = a['busySpeed']
                    ph = phases.get(o.name, 0.0) + (sp * dt if on else 0.0)
                    phases[o.name] = ph
                    o.rotation_mode = 'QUATERNION'
                    o.rotation_quaternion = r[3] @ Quaternion(gl_vec(a.get('axis', [0, 1, 0])), ph)
                    o.keyframe_insert('rotation_quaternion', frame=f)
                elif ty == 'swing':
                    ang = a.get('amp', 0.2) * math.sin(2 * math.pi * a.get('speed', 1.0) * t + a.get('phase', 0.0)) if on else 0.0
                    if a.get('snap'):
                        ang += a['snap'] * hit_curve(tf, a.get('attack', 0.1), a.get('recover', 0.5))
                    o.rotation_mode = 'QUATERNION'
                    o.rotation_quaternion = r[3] @ Quaternion(gl_vec(a.get('axis', [0, 1, 0])), ang)
                    o.keyframe_insert('rotation_quaternion', frame=f)
                elif ty == 'recoil':
                    amt = 0.0
                    for k in range(int(a.get('repeat', 1))):
                        amt = max(amt, hit_curve(tf - a.get('delay', 0.0) - k * a.get('every', 0.0), a.get('attack', 0.04), a.get('recover', 0.45)))
                    o.location = r[0] - (r[3] if o.rotation_mode == 'QUATERNION' else r[1].to_quaternion()) @ gl_vec(a.get('axis', [1, 0, 0])) * a.get('dist', 0.3) * amt
                    o.keyframe_insert('location', frame=f)
                elif ty == 'flash':
                    vis_f = any(0 <= tf - a.get('delay', 0.0) - k * a.get('every', 0.0) < max(a.get('dur', 0.08), 1.0 / FPS) for k in range(int(a.get('repeat', 1))))
                    o.scale = r[2] * rng.uniform(0.8, 1.2) if vis_f else (0, 0, 0)
                    o.keyframe_insert('scale', frame=f)
                elif ty == 'launch':
                    x = tf - a.get('delay', 0.0)
                    off, sc = 0.0, 1.0
                    if 0 <= x < a.get('dur', 0.45):
                        off = a.get('travel', 9.0) * (x / a.get('dur', 0.45)) ** 2
                    elif x >= a.get('dur', 0.45) and tf < a.get('reload', 2.4):
                        sc = 0.0
                    o.location = r[0] + gl_vec(a.get('axis', [1, 0, 0])) * off
                    o.scale = r[2] * sc
                    o.keyframe_insert('location', frame=f); o.keyframe_insert('scale', frame=f)
                elif ty == 'flicker':
                    gk = (a.get('slots', 1), a.get('rate', 18.0), a.get('when'))
                    tick = int(t * a.get('rate', 18.0))
                    ck = gk + (tick,)
                    if ck not in flick:
                        duty = a.get('duty', 0.75) if on else a.get('idle', 0.1)
                        flick[ck] = random.Random(hash(ck) & 0xffff).randrange(a.get('slots', 1)) if random.Random((hash(ck) >> 3) & 0xffff).random() < duty else -1
                    o.scale = r[2] if flick[ck] == a.get('slot', 0) or (a.get('fireOn') and tf < a['fireOn']) else (0, 0, 0)
                    o.keyframe_insert('scale', frame=f)
                elif ty == 'scroll' and scroll is not None:
                    top = self.info.get('speed', 6.0) * 0.5
                    scroll_x += a.get('speed', 3.0) * dt * min(1.5, self.speed(t) / max(0.1, top)) * (-1 if self.reverse else 1)
                    scroll.inputs['Location'].default_value[0] = scroll_x
                    scroll.inputs['Location'].keyframe_insert('default_value', frame=f, index=0)
            # dust
            if self.dust and vis and f % 3 == 0 and self.speed(t) > 1.0:
                back = self.local(Vector((-self.length * 0.4, P.rng.uniform(-1, 1) * self.width * 0.35, 0.15)), t)
                P.puff(back, t, 0.5 + 0.08 * self.speed(t), P.dust_color, life=0.9, rise=0.6, alpha=0.35)

    def _tread_setup(self):
        tread = self.parts.get('Tread')
        if tread is None or not tread.material_slots or not tread.material_slots[0].material:
            return None
        m = tread.material_slots[0].material.copy()
        tread.material_slots[0].material = m
        nt = m.node_tree
        mp = nt.nodes.new('ShaderNodeMapping')
        uv = nt.nodes.new('ShaderNodeTexCoord')
        nt.links.new(uv.outputs['UV'], mp.inputs['Vector'])
        for nd in nt.nodes:
            if nd.type == 'TEX_IMAGE':
                nt.links.new(mp.outputs[0], nd.inputs['Vector'])
        return mp


# ---------------------------------------------------------------- shield
class Shield:
    """Translucent bubble that never shatters: pushers dent it, it stretches around them and springs back."""

    def __init__(self, P, owner, radius, color, scale, strength):
        self.P, self.owner, self.radius = P, owner, radius
        ob = bpy.data.objects.new('shield', _mesh('shell').copy())
        P.scene.collection.objects.link(ob)
        ob.data.materials.append(blob_mat('shield'))
        ob.scale = Vector(scale) * radius if not isinstance(scale, (int, float)) else (radius * scale,) * 3
        ob.color = (*color, strength)
        self.ob, self.color, self.strength = ob, color, strength
        self.sx = Vector(ob.scale)
        if isinstance(owner, Actor):
            ob.parent = owner.body
            ob.location = owner.mid
        else:
            ob.location = V(owner)
        self.n = 0

    def centre(self, t):
        return self.owner.local(self.owner.mid, t) if isinstance(self.owner, Actor) else V(self.owner)

    def flare(self, t, pos=None, size=None, dur=0.5):
        """Light the shield up where something hits it (ripple of light, no cracks)."""
        c = self.centre(t)
        p = V(pos) if pos is not None else c + Vector((self.radius, 0, 0))
        d = (p - c)
        surf = c + d.normalized() * (self.sx.x if d.length == 0 else self.radius * 1.0)
        s = size or self.radius * 0.25
        self.P.blob(surf, t, t + dur, (s * 0.3, s * 1.6), self.color, kind='glow', alpha=(0.9, 0.0), parent=self.owner if isinstance(self.owner, Actor) else None)
        self.P.light_flash(surf, t, 300 * s * s, self.color, dur)
        f = frame_of(t)
        for ff, a in ((f - 1, self.strength), (f, min(1.0, self.strength * 2.5)), (f + int(dur * FPS), self.strength)):
            self.ob.color = (*self.color, a)
            self.ob.keyframe_insert('color', frame=ff)
        return self

    def push(self, pusher, t0, t1, radius=None, depth=None):
        """Something (Actor, point or function of time) presses through the skin between t0 and t1.
        The skin dents ahead of it, wraps around it, then closes behind and springs back."""
        r = radius or (pusher.radius * 1.3 if isinstance(pusher, Actor) else self.radius * 0.3)
        self.n += 1
        emp = bpy.data.objects.new('shield_push', None)
        self.P.scene.collection.objects.link(emp)
        tex = bpy.data.textures.new('shield_push', 'BLEND')
        tex.progression = 'SPHERICAL'
        mod = self.ob.modifiers.new('push%d' % self.n, 'DISPLACE')
        mod.texture = tex
        mod.texture_coords = 'OBJECT'
        mod.texture_coords_object = emp
        mod.direction = 'NORMAL'
        mod.mid_level = 0.0
        unit = self.sx.x
        for f in range(frame_of(t0) - 2, frame_of(t1) + 14):
            t = f / FPS
            c = self.centre(t)
            p = resolve(pusher, min(max(t, t0), t1))
            d = p - c
            dist = d.length
            sd = dist - self.radius  # + outside, - inside
            emp.location = c + d.normalized() * self.radius if dist > 1e-4 else c
            emp.scale = (r * 1.6,) * 3
            if t < t0 or t > t1:
                x = (t0 - t) if t < t0 else (t - t1)
                amt = 0.0 if t < t0 else -0.35 * math.exp(-7 * x) * math.cos(22 * x) * (depth or r)
            else:
                amt = -max(-(depth or r) * 1.2, min((depth or r) * 1.2, (r - abs(sd)) * (1 if sd > 0 else -1) if abs(sd) < r else 0.0))
                amt = -(max(0.0, r - abs(sd))) * (1.0 if sd > 0 else -1.0)
            mod.strength = amt / unit
            emp.keyframe_insert('location', frame=f); emp.keyframe_insert('scale', frame=f)
            mod.keyframe_insert('strength', frame=f)
        self.flare(t0, resolve(pusher, t0), r * 0.6, dur=max(0.3, t1 - t0))
        return self


# ---------------------------------------------------------------- promo
class Promo:
    def __init__(self, name, env='ground', tod='noon', ground='dry', seconds=6.0, seed=1, planet=None, props=30, clear=22.0,
                 air_height=7.0, stars=1.0):
        """env 'ground' or 'space'. tod: noon, morning, golden, dusk, overcast, night. ground: dry, grass, ash, red, snow.
        planet (space): dict(pos=(x,y,z), radius=, color=(r,g,b), color2=) or None. props: scatter count; clear: radius kept free."""
        ap = argparse.ArgumentParser()
        ap.add_argument('--quality', default='draft', choices=['draft', 'mid', 'final'])
        ap.add_argument('--frames', default=None, help='a-b (frames, 24 per second)')
        ap.add_argument('--stills', default=None, help='comma list of frames; renders only those plus a sheet')
        ap.add_argument('--out', default=None)
        ap.add_argument('--threads', type=int, default=0)
        ap.add_argument('--samples', type=int, default=0)
        ap.add_argument('--save-blend', action='store_true')
        ap.add_argument('--no-render', action='store_true')
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
        self.args = ap.parse_args(argv)
        self.name, self.env, self.seconds = name, env, seconds
        self.frames = int(round(seconds * FPS))
        self.rng = random.Random(seed)
        self.air_height = air_height
        self.actors, self.cam_segs, self.shakes = [], [], []
        self._cache = {}
        bpy.ops.wm.read_factory_settings(use_empty=True)
        try:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
        except Exception:
            pass
        self.scene = sc = bpy.context.scene
        sc.render.fps = FPS
        sc.frame_start, sc.frame_end = 0, self.frames - 1
        self.cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
        sc.collection.objects.link(self.cam)
        sc.camera = self.cam
        self.cam.data.lens = 35
        self.cam.data.clip_end = 20000
        self.cam.rotation_mode = 'QUATERNION'
        self.dust_color = (0.42, 0.36, 0.26)
        if env == 'ground':
            self._ground_env(tod, ground)
            if props:
                self.scatter(props, clear)
        else:
            self._space_env(planet, stars)

    # ---- environments
    def _ground_env(self, tod, ground):
        elev, az, sun_s, sun_c, sky_s, haze = TOD[tod]
        c1, c2, c3 = GROUND[ground]
        self.dust_color = tuple(min(1, 0.5 * (a + b) * 1.6 + 0.08) for a, b in zip(c1, c2))
        w = bpy.data.worlds.new('World'); self.scene.world = w; w.use_nodes = True
        nt = w.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
        tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Generated'], sep.inputs[0])
        if tod in ('noon', 'morning', 'golden', 'dusk'):
            sky = nt.nodes.new('ShaderNodeTexSky')
            sky.sky_type = 'MULTIPLE_SCATTERING'
            sky.sun_disc = False
            sky.sun_elevation = math.radians(max(2, elev))
            sky.sun_rotation = math.radians(90 - az)
            sky.aerosol_density = 2.0 if tod in ('golden', 'dusk') else 1.0
            nt.links.new(sky.outputs[0], bg.inputs['Color'])
            sky_s = sky_s * SKY_GAIN
        else:
            ramp = nt.nodes.new('ShaderNodeValToRGB')
            top = tuple(h * k for h, k in zip(haze, (0.45, 0.62, 0.95)))
            ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*haze, 1)
            ramp.color_ramp.elements[1].position = 0.45; ramp.color_ramp.elements[1].color = (*top, 1)
            nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
            nt.links.new(ramp.outputs[0], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = sky_s * 1.6
        nt.links.new(bg.outputs[0], out.inputs['Surface'])
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        self.scene.collection.objects.link(sun)
        sun.data.energy = sun_s; sun.data.color = sun_c; sun.data.angle = math.radians(3)
        sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(az + 90))
        self.sun = sun
        # ground
        me = bpy.data.meshes.new('ground'); bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=600); bm.to_mesh(me); bm.free()
        g = bpy.data.objects.new('Ground', me); self.scene.collection.objects.link(g)
        m = bpy.data.materials.new('ground'); m.use_nodes = True; nt = m.node_tree
        b = nt.nodes.get('Principled BSDF'); b.inputs['Roughness'].default_value = 0.95
        tco = nt.nodes.new('ShaderNodeTexCoord')
        n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.035; n1.inputs['Detail'].default_value = 6
        n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 0.6; n2.inputs['Detail'].default_value = 8
        n3 = nt.nodes.new('ShaderNodeTexNoise'); n3.inputs['Scale'].default_value = 6.0; n3.inputs['Detail'].default_value = 4
        for nn in (n1, n2, n3):
            nt.links.new(tco.outputs['Object'], nn.inputs['Vector'])
        r1 = nt.nodes.new('ShaderNodeValToRGB'); r1.color_ramp.elements[0].position = 0.38; r1.color_ramp.elements[1].position = 0.62
        r1.color_ramp.elements[0].color = (*c1, 1); r1.color_ramp.elements[1].color = (*c2, 1)
        nt.links.new(n1.outputs[0], r1.inputs['Fac'])
        r2 = nt.nodes.new('ShaderNodeMapRange'); r2.inputs[1].default_value = 0.52; r2.inputs[2].default_value = 0.72
        nt.links.new(n2.outputs[0], r2.inputs[0])
        mx = nt.nodes.new('ShaderNodeMixRGB'); mx.inputs['Color2'].default_value = (*c3, 1)
        nt.links.new(r2.outputs[0], mx.inputs['Fac']); nt.links.new(r1.outputs[0], mx.inputs['Color1'])
        # fade to haze far away
        geo = nt.nodes.new('ShaderNodeCameraData')
        far = nt.nodes.new('ShaderNodeMapRange'); far.inputs[1].default_value = 90; far.inputs[2].default_value = 500; far.inputs[4].default_value = 0.9
        nt.links.new(geo.outputs['View Distance'], far.inputs[0])
        mh = nt.nodes.new('ShaderNodeMixRGB'); mh.inputs['Color2'].default_value = (*[h * 0.55 for h in haze], 1)
        nt.links.new(far.outputs[0], mh.inputs['Fac']); nt.links.new(mx.outputs[0], mh.inputs['Color1'])
        nt.links.new(mh.outputs[0], b.inputs['Base Color'])
        bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35; bump.inputs['Distance'].default_value = 0.2
        add = nt.nodes.new('ShaderNodeMath'); add.operation = 'ADD'
        nt.links.new(n2.outputs[0], add.inputs[0]); nt.links.new(n3.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], bump.inputs['Height']); nt.links.new(bump.outputs[0], b.inputs['Normal'])
        me.materials.append(m)
        self.ground_mat = m
        # distant hills
        hm = bpy.data.meshes.new('hills'); bm = bmesh.new()
        rr = random.Random(self.rng.random())
        ph = [rr.uniform(0, 6.28) for _ in range(6)]
        rings, segs = 10, 96
        vs = []
        for i in range(rings):
            r = 150 + i * 40
            row = []
            for j in range(segs):
                a = j / segs * 2 * math.pi
                k = math.sin(math.pi * i / (rings - 1))
                hgt = k * (18 + 14 * math.sin(3 * a + ph[0]) + 9 * math.sin(7 * a + ph[1] + i * 0.3) + 5 * math.sin(13 * a + ph[2] + i))
                row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), max(-1.0, hgt))))
            vs.append(row)
        for i in range(rings - 1):
            for j in range(segs):
                bm.faces.new((vs[i][j], vs[i][(j + 1) % segs], vs[i + 1][(j + 1) % segs], vs[i + 1][j]))
        bm.to_mesh(hm); bm.free()
        for p in hm.polygons:
            p.use_smooth = True
        hills = bpy.data.objects.new('Hills', hm); self.scene.collection.objects.link(hills)
        hm.materials.append(m)

    def _space_env(self, planet, stars):
        w = bpy.data.worlds.new('World'); self.scene.world = w; w.use_nodes = True
        nt = w.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 260
        nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs[1].default_value = 0.0; mr.inputs[2].default_value = 0.045; mr.inputs[3].default_value = 1.0; mr.inputs[4].default_value = 0.0
        nt.links.new(vor.outputs['Distance'], mr.inputs[0])
        pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3.0
        nt.links.new(mr.outputs[0], pw.inputs[0])
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 5
        nt.links.new(tc.outputs['Generated'], nz.inputs['Vector'])
        neb = nt.nodes.new('ShaderNodeValToRGB'); neb.color_ramp.elements[0].position = 0.5; neb.color_ramp.elements[0].color = (0, 0, 0, 1)
        neb.color_ramp.elements[1].position = 0.9; neb.color_ramp.elements[1].color = (0.012, 0.02, 0.045, 1)
        nt.links.new(nz.outputs[0], neb.inputs['Fac'])
        m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; m1.inputs[1].default_value = 3.0 * stars
        nt.links.new(pw.outputs[0], m1.inputs[0])
        addc = nt.nodes.new('ShaderNodeMixRGB'); addc.blend_type = 'ADD'; addc.inputs['Fac'].default_value = 1.0
        nt.links.new(neb.outputs[0], addc.inputs['Color1']); nt.links.new(m1.outputs[0], addc.inputs['Color2'])
        nt.links.new(addc.outputs[0], bg.inputs['Color'])
        # stars must not light the ships: camera rays only
        lp = nt.nodes.new('ShaderNodeLightPath'); mixs = nt.nodes.new('ShaderNodeMixShader')
        amb = nt.nodes.new('ShaderNodeBackground'); amb.inputs['Color'].default_value = (0.02, 0.03, 0.05, 1); amb.inputs['Strength'].default_value = 1.0
        nt.links.new(lp.outputs['Is Camera Ray'], mixs.inputs['Fac'])
        nt.links.new(amb.outputs[0], mixs.inputs[1]); nt.links.new(bg.outputs[0], mixs.inputs[2])
        nt.links.new(mixs.outputs[0], out.inputs['Surface'])
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); self.scene.collection.objects.link(sun)
        sun.data.energy = 5.0; sun.data.color = (1.0, 0.96, 0.9); sun.rotation_euler = (math.radians(55), 0, math.radians(130))
        fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'SUN')); self.scene.collection.objects.link(fill)
        fill.data.energy = 0.7; fill.data.color = (0.5, 0.65, 1.0); fill.rotation_euler = (math.radians(120), 0, math.radians(-40))
        self.sun = sun
        if planet:
            self.planet(**planet)

    def planet(self, pos=(900, 600, -500), radius=600, color=(0.16, 0.30, 0.45), color2=(0.42, 0.36, 0.22), clouds=0.5):
        """Add a planet (space scenes). Avoid mauve: it reads purple."""
        me = bpy.data.meshes.new('planet'); bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0); bm.to_mesh(me); bm.free()
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new('Planet', me); self.scene.collection.objects.link(ob)
        ob.location = pos; ob.scale = (radius,) * 3
        m = bpy.data.materials.new('planet'); m.use_nodes = True; nt = m.node_tree
        b = nt.nodes.get('Principled BSDF'); b.inputs['Roughness'].default_value = 0.8
        tc = nt.nodes.new('ShaderNodeTexCoord')
        n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 2.2; n1.inputs['Detail'].default_value = 9
        n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 4.0; n2.inputs['Detail'].default_value = 8; n2.inputs['Distortion'].default_value = 1.2
        nt.links.new(tc.outputs['Object'], n1.inputs['Vector']); nt.links.new(tc.outputs['Object'], n2.inputs['Vector'])
        r = nt.nodes.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].position = 0.47; r.color_ramp.elements[1].position = 0.56
        r.color_ramp.elements[0].color = (*color, 1); r.color_ramp.elements[1].color = (*color2, 1)
        nt.links.new(n1.outputs[0], r.inputs['Fac'])
        cr = nt.nodes.new('ShaderNodeMapRange'); cr.inputs[1].default_value = 0.52; cr.inputs[2].default_value = 0.75; cr.inputs[4].default_value = clouds
        nt.links.new(n2.outputs[0], cr.inputs[0])
        mx = nt.nodes.new('ShaderNodeMixRGB'); mx.inputs['Color2'].default_value = (0.9, 0.92, 0.95, 1)
        nt.links.new(cr.outputs[0], mx.inputs['Fac']); nt.links.new(r.outputs[0], mx.inputs['Color1'])
        lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.25
        mx2 = nt.nodes.new('ShaderNodeMixRGB'); mx2.inputs['Color2'].default_value = (0.35, 0.6, 1.0, 1)
        nt.links.new(lw.outputs['Facing'], mx2.inputs['Fac']); nt.links.new(mx.outputs[0], mx2.inputs['Color1'])
        nt.links.new(mx2.outputs[0], b.inputs['Base Color'])
        me.materials.append(m)
        return ob

    def scatter(self, count=30, clear=22.0, radius=110.0, kinds=('boulder', 'rock_cluster', 'shrub', 'grass', 'slab', 'dead_tree')):
        """Scatter scenery props around the action, keeping `clear` metres around the origin empty."""
        for i in range(count):
            a = self.rng.uniform(0, 2 * math.pi)
            r = math.sqrt(self.rng.uniform((clear / radius) ** 2, 1.0)) * radius
            k = self.rng.choice(kinds)
            s = self.prop(k, (r * math.cos(a), r * math.sin(a)), heading=self.rng.uniform(0, 360), scale_mul=self.rng.uniform(0.8, 1.6))

    def prop(self, name, at, heading=0.0, scale_mul=1.0):
        """Place a static prop/model without Actor overhead (linked copy). Returns its root object."""
        model, objs, _ = self._import(name)
        info = REGISTRY.get(name, {})
        bpy.context.view_layer.update()
        lo = Vector((1e9,) * 3); hi = -lo
        for o in objs:
            if o.type == 'MESH':
                for c in o.bound_box:
                    w = o.matrix_world @ Vector(c)
                    lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        native = max(hi.x - lo.x, hi.y - lo.y, 1e-6)
        s = info.get('size', native) / native * scale_mul
        model.scale = (s,) * 3
        model.location = V(at)
        model.rotation_euler = (0, 0, math.radians(heading))
        return model

    # ---- loading
    def _find(self, name):
        info = REGISTRY.get(name)
        cands = info['files'] if info else [name]
        for base in SEARCH:
            for c in cands:
                for p in (os.path.join(base, c), os.path.join(base, os.path.basename(c))):
                    if os.path.exists(p):
                        return p
        raise FileNotFoundError(f'model {name}: none of {cands} found in {SEARCH}')

    def _import(self, name):
        """Import a model; returns (root empty, all objects, scene fire tag). Later copies are linked duplicates."""
        if name in self._cache:
            src_root, src_objs, tag = self._cache[name]
            mp = {}
            for o in src_objs + [src_root]:
                c = o.copy()
                if o.type == 'ARMATURE' or (o.animation_data and o.animation_data.action):
                    pass
                self.scene.collection.objects.link(c)
                mp[o] = c
            for o, c in mp.items():
                if o.parent in mp:
                    c.parent = mp[o.parent]
                    c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
                for md in c.modifiers:
                    if getattr(md, 'object', None) in mp:
                        md.object = mp[md.object]
            self._template_hide(src_root)
            return mp[src_root], [mp[o] for o in src_objs], tag
        path = self._find(name)
        before = set(bpy.data.objects)
        tag = None
        if path.endswith('.blend'):
            with bpy.data.libraries.load(path) as (src, dst):
                dst.objects = list(src.objects)
            for o in dst.objects:
                if o is not None and o.type not in ('CAMERA', 'LIGHT') or (o is not None and o.parent is not None):
                    self.scene.collection.objects.link(o)
        else:
            if 'fire' in self.scene:
                del self.scene['fire']
            bpy.ops.import_scene.gltf(filepath=path)
            if 'fire' in self.scene:
                tag = plain(self.scene['fire'])
        objs = [o for o in bpy.data.objects if o not in before and o.name in self.scene.collection.all_objects]
        root = bpy.data.objects.new(name + '_model', None)
        self.scene.collection.objects.link(root)
        for o in objs:
            if o.parent is None:
                o.parent = root
            o.select_set(False)
        # keep an untouched template for later copies
        tmpl = {}
        for o in objs + [root]:
            c = o.copy(); tmpl[o] = c
        for o, c in tmpl.items():
            if o.parent in tmpl:
                c.parent = tmpl[o.parent]; c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
            for md in c.modifiers:
                if getattr(md, 'object', None) in tmpl:
                    md.object = tmpl[md.object]
        self._cache[name] = (tmpl[root], [tmpl[o] for o in objs], tag)
        return root, objs, tag

    def _template_hide(self, root):
        pass

    def load(self, name, at=(0, 0), heading=0.0, scale=None, glow=2.5):
        """Load a registered model as an Actor at (x, y[, z]) facing `heading` degrees (0 = +X)."""
        a = Actor(self, name, at, heading, scale, glow)
        self.actors.append(a)
        return a

    def deploy(self, packed, tower_name, t0, t1):
        """Swap a packed tower vehicle for its structure at t0 and unfold it by t1. Returns the tower Actor."""
        c = packed.local(Vector((packed.mid.x, packed.mid.y, 0)), t0)
        h = math.degrees(packed.heading(t0))
        tower = self.load(tower_name, at=(c.x, c.y, c.z), heading=h)
        tower.set_unfold(t0, t1)
        tower.appear(t0)
        packed.vanish(t0)
        return tower

    # ---- fx primitives
    def blob(self, pos, t0, t1, size, color, kind='glow', alpha=(1.0, 0.0), move=None, color2=None, parent=None, stretch=None):
        """Soft blob from t0 to t1. size and alpha may be (start, end). move = world offset travelled over its life."""
        ob = bpy.data.objects.new('fx', _mesh('ball'))
        self.scene.collection.objects.link(ob)
        ob.data.materials.append(blob_mat(kind)) if not ob.data.materials else None
        ob.active_material = blob_mat(kind) if ob.data.materials[0] != blob_mat(kind) else ob.active_material
        if ob.data.materials[0] != blob_mat(kind):
            ob.data = _mesh('ball').copy(); ob.data.materials.clear(); ob.data.materials.append(blob_mat(kind))
        s0, s1 = size if isinstance(size, (tuple, list)) else (size, size)
        a0, a1 = alpha if isinstance(alpha, (tuple, list)) else (alpha, alpha)
        p0 = V(pos)
        if parent is not None:
            ob.parent = parent.body
            ob.matrix_parent_inverse = Matrix.Identity(4)
            p0 = Matrix.Rotation(-parent.heading(t0), 3, 'Z') @ (p0 - parent.pos(t0))
            move = None
        p1 = p0 + V(move) if move is not None else p0
        st = Vector(stretch) if stretch else Vector((1, 1, 1))
        f0, f1 = frame_of(t0), max(frame_of(t0) + 1, frame_of(t1))
        c2 = color2 or color
        _kf(ob, 'scale', f0 - 1, (0, 0, 0))
        for f, s, a, p, c in ((f0, s0, a0, p0, color), (f1, s1, a1, p1, c2)):
            ob.scale = st * s; ob.location = p; ob.color = (*c, a)
            ob.keyframe_insert('scale', frame=f); ob.keyframe_insert('location', frame=f); ob.keyframe_insert('color', frame=f)
        _kf(ob, 'scale', f1 + 1, (0, 0, 0))
        return ob

    def puff(self, pos, t, size, color=(0.25, 0.25, 0.25), life=1.5, rise=1.5, alpha=0.7, drift=(0, 0, 0)):
        """One smoke/dust puff that grows, rises and fades."""
        return self.blob(pos, t, t + life, (size * 0.4, size * 1.6), color, kind='smoke', alpha=(alpha, 0.0), move=Vector(drift) + Vector((0, 0, rise)))

    def light_flash(self, pos, t, energy, color=(1.0, 0.75, 0.4), dur=0.25):
        ld = bpy.data.lights.new('flash', 'POINT'); ld.color = color; ld.shadow_soft_size = 0.5
        ob = bpy.data.objects.new('flash', ld); self.scene.collection.objects.link(ob)
        ob.location = V(pos)
        f = frame_of(t)
        for ff, e in ((f - 1, 0.0), (f, energy), (f + max(1, int(dur * FPS)), 0.0)):
            ld.energy = e; ld.keyframe_insert('energy', frame=ff)
        return ob

    def sparks(self, pos, t, size=0.5, color=WHITE_HOT, n=5):
        p = V(pos)
        self.blob(p, t, t + 0.12, (size * 0.9, size * 0.2), color, kind='hot', alpha=(1, 0.3))
        for i in range(n):
            d = Vector((self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), self.rng.uniform(0.1, 1))).normalized() * size * self.rng.uniform(2, 5)
            self.blob(p, t, t + self.rng.uniform(0.2, 0.4), (size * 0.12, size * 0.03), TERRAN_ORANGE, kind='hot', alpha=(1, 0.0), move=d)

    def explosion(self, pos, t, size=1.0, ground=None, color=(1.0, 0.5, 0.12), smoke=True):
        """Explosion at pos: flash, fireball, smoke, sparks, light. size ~ fireball radius in metres."""
        p = V(pos)
        r = self.rng
        if ground is None:
            ground = self.env == 'ground' and p.z < 1.5
        space = self.env == 'space'
        self.light_flash(p + Vector((0, 0, 0.5 * size)), t, 2500 * size * size, (1.0, 0.7, 0.35), 0.35)
        self.blob(p, t, t + 0.16, (size * 0.5, size * 1.7), WHITE_HOT, kind='hot', alpha=(1.0, 0.0))
        for i in range(5):
            o = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0 if ground else -1, 1))) * size * 0.45
            self.blob(p + o, t + i * 0.015, t + r.uniform(0.45, 0.7), (size * 0.35, size * r.uniform(0.9, 1.3)), color, kind='glow',
                      alpha=(1.0, 0.0), color2=(0.5, 0.08, 0.02), move=o * 1.2 + Vector((0, 0, 0 if space else size * 0.8)))
        if smoke:
            for i in range(5):
                o = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0 if ground else -1, 1))) * size * 0.6
                g = r.uniform(0.05, 0.14)
                self.blob(p + o, t + 0.06 + i * 0.03, t + r.uniform(1.6, 2.6), (size * 0.5, size * r.uniform(1.4, 2.0)), (g, g, g), kind='smoke',
                          alpha=(0.75 if not space else 0.35, 0.0), move=o * (1.0 if not space else 3.0) + Vector((0, 0, 0 if space else size * r.uniform(1.2, 2.4))))
        for i in range(8):
            d = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0.2 if ground else -1, 1.2))).normalized() * size * r.uniform(3, 7)
            self.blob(p, t, t + r.uniform(0.3, 0.7), (size * 0.1, size * 0.02), TERRAN_ORANGE, kind='hot', alpha=(1, 0.0), move=d - (Vector((0, 0, size * 1.5)) if not space else Vector()))
        if ground:
            self.scorch(p, t, size * 1.4)
            for i in range(4):
                a = r.uniform(0, 6.28)
                self.puff(p + Vector((math.cos(a), math.sin(a), 0.1)) * size * 0.8, t + 0.03, size * 0.7, self.dust_color, life=1.2, rise=0.8, alpha=0.45, drift=(math.cos(a) * size, math.sin(a) * size, 0))

    def scorch(self, pos, t, radius):
        ob = bpy.data.objects.new('scorch', _mesh('disc')); self.scene.collection.objects.link(ob)
        if not ob.data.materials:
            ob.data.materials.append(solid_mat('scorch', (0.012, 0.011, 0.01), 1.0))
        p = V(pos); ob.location = (p.x, p.y, 0.02 + self.rng.uniform(0, 0.01))
        show(ob, t, 1e4, radius)
        return ob

    def wreck(self, pos, t, radius):
        """Burning debris and a smoke column where a ground unit died."""
        p = V(pos); r = self.rng
        for i in range(6):
            ob = bpy.data.objects.new('wreck', _mesh('chunk')); self.scene.collection.objects.link(ob)
            if not ob.data.materials:
                ob.data.materials.append(solid_mat('wreck', (0.02, 0.02, 0.02), 0.7))
            a = r.uniform(0, 6.28); d = r.uniform(0.1, 0.9) * radius
            s = radius * r.uniform(0.12, 0.3)
            ob.location = p + Vector((math.cos(a) * d, math.sin(a) * d, s * 0.3))
            ob.rotation_euler = (r.uniform(0, 3), r.uniform(0, 3), r.uniform(0, 3))
            show(ob, t + 0.04, 1e4, (s * 1.5, s, s * 0.6))
        self.scorch(p, t, radius * 1.3)
        self.smoke_plume(p + Vector((0, 0, 0.3)), t + 0.2, self.seconds + 0.5, size=radius * 0.5)
        for i in range(3):
            self.blob(p + Vector((r.uniform(-.4, .4) * radius, r.uniform(-.4, .4) * radius, 0.25)), t + 0.1, self.seconds + 1, radius * 0.22, (1.0, 0.4, 0.1), kind='glow', alpha=(0.9, 0.6))

    def falling_wreck(self, pos, vel, t, radius):
        """A shot-down aircraft: a burning chunk falls trailing smoke and hits the ground."""
        p, v = V(pos), V(vel)
        fall = math.sqrt(2 * max(0.5, p.z) / 9.8)
        ob = bpy.data.objects.new('wreck', _mesh('chunk')); self.scene.collection.objects.link(ob)
        if not ob.data.materials:
            ob.data.materials.append(solid_mat('wreck', (0.02, 0.02, 0.02), 0.7))
        f0, f1 = frame_of(t), frame_of(t + fall)
        _kf(ob, 'scale', f0 - 1, (0, 0, 0))
        for f in range(f0, f1 + 1):
            x = (f - f0) / FPS
            q = p + v * x * 0.6 + Vector((0, 0, -4.9 * x * x))
            ob.location = (q.x, q.y, max(0.2, q.z)); ob.scale = (radius * 0.45, radius * 0.3, radius * 0.2)
            ob.rotation_euler = (x * 5, x * 3, x * 2)
            ob.keyframe_insert('location', frame=f); ob.keyframe_insert('scale', frame=f); ob.keyframe_insert('rotation_euler', frame=f)
            if f % 2 == 0:
                self.puff(q, x + t, radius * 0.35, (0.08, 0.08, 0.08), life=1.2, rise=0.5, alpha=0.6)
                self.blob(q, x + t, x + t + 0.15, radius * 0.3, (1.0, 0.45, 0.1), kind='glow', alpha=(0.9, 0))
        end = p + v * fall * 0.6; end.z = 0
        self.explosion(end, t + fall, radius * 0.7, ground=True)
        return t + fall

    def smoke_plume(self, pos, t0, t1, size=1.0, color=(0.07, 0.07, 0.07), every=0.14, rise=4.0, wind=(0.8, 0.3, 0)):
        t = t0
        while t < min(t1, self.seconds):
            j = Vector((self.rng.uniform(-.3, .3), self.rng.uniform(-.3, .3), 0)) * size
            self.puff(V(pos) + j, t, size, color, life=2.2, rise=rise, alpha=0.55, drift=wind)
            t += every

    def dust(self, pos, t, size=1.0, n=5):
        """Ring of dust kicked up from the ground (landings, heavy impacts)."""
        p = V(pos)
        for i in range(n):
            a = i / n * 6.28 + self.rng.uniform(0, 0.5)
            self.puff(p + Vector((math.cos(a), math.sin(a), 0.05)) * size * 0.5, t, size * 0.6, self.dust_color, life=1.4, rise=0.5, alpha=0.5,
                      drift=(math.cos(a) * size * 1.5, math.sin(a) * size * 1.5, 0))

    def _rod(self, kind='beam'):
        ob = bpy.data.objects.new('rod', _mesh('rod')); self.scene.collection.objects.link(ob)
        if not ob.data.materials:
            ob.data.materials.append(blob_mat('beam'))
        return ob

    def _place_rod(self, ob, a, b, width, f):
        d = b - a
        ob.location = a
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = d.to_track_quat('X', 'Z') if d.length > 1e-6 else Quaternion()
        ob.scale = (max(1e-4, d.length), width, width)
        ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_quaternion', frame=f); ob.keyframe_insert('scale', frame=f)

    def beam(self, a, b, t0, t1, color=GOLD, width=0.12, core=True, glow_ends=True, fade=0.08):
        """Straight energy beam from a to b (Actors, points or functions of time) between t0 and t1."""
        rods = [(self._rod(), width, (*color, 0.55))]
        if core:
            rods.append((self._rod(), width * 0.35, (*WHITE_HOT, 1.0)))
        f0, f1 = frame_of(t0), max(frame_of(t0) + 1, frame_of(t1))
        for ob, w, col in rods:
            ob.color = col
            _kf(ob, 'scale', f0 - 1, (0, 0, 0))
            for f in range(f0, f1 + 1):
                t = f / FPS
                k = min(1.0, (t - t0) / 0.04 + 0.5, (t1 - t) / max(1e-3, fade) + 0.3)
                self._place_rod(ob, resolve(a, t), resolve(b, t), w * max(0.2, k), f)
            _kf(ob, 'scale', f1 + 1, (0, 0, 0))
        if glow_ends:
            self.blob(resolve(b, t0), t0, t1, (width * 5, width * 7), color, kind='glow', alpha=(0.9, 0.5), move=resolve(b, t1) - resolve(b, t0))
            self.blob(resolve(a, t0), t0, t1, width * 3.5, color, kind='glow', alpha=(0.9, 0.5), move=resolve(a, t1) - resolve(a, t0))
        return rods[0][0]

    def _bolt_obj(self, seed, jag, forks, width):
        r = random.Random(seed)
        cu = bpy.data.curves.new('bolt', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = width; cu.bevel_resolution = 1
        def strand(p0, p1, n, j):
            sp = cu.splines.new('POLY'); sp.points.add(n)
            for i in range(n + 1):
                u = i / n
                p = p0.lerp(p1, u)
                k = math.sin(math.pi * u) * j if i not in (0, n) else 0
                p = p + Vector((0, r.uniform(-1, 1) * k, r.uniform(-1, 1) * k))
                sp.points[i].co = (*p, 1)
            return [Vector(pt.co[:3]) for pt in sp.points]
        main = strand(Vector((0, 0, 0)), Vector((1, 0, 0)), 9, jag)
        for i in range(forks):
            s = main[r.randrange(2, 7)]
            e = s + Vector((r.uniform(0.1, 0.3), r.uniform(-1, 1) * 0.25, r.uniform(-1, 1) * 0.25))
            strand(s, e, 4, jag * 0.4)
        ob = bpy.data.objects.new('bolt', cu); self.scene.collection.objects.link(ob)
        cu.materials.append(blob_mat('beam'))
        return ob

    def lightning(self, a, b, t0, t1, color=GOLD, width=0.06, jag=0.09, forks=2, variants=3, glow_ends=True):
        """Jagged flickering lightning from a to b (Actors, points or functions of time) between t0 and t1."""
        f0, f1 = frame_of(t0), max(frame_of(t0) + 1, frame_of(t1))
        obs = [self._bolt_obj(self.rng.random(), jag, forks, 1.0) for _ in range(variants)]
        for j, ob in enumerate(obs):
            ob.color = (*[min(1.0, c * 0.6 + 0.4) for c in color], 1.0)
            ob.rotation_mode = 'QUATERNION'
            _kf(ob, 'scale', f0 - 1, (0, 0, 0))
            for f in range(f0, f1 + 1):
                t = f / FPS
                pa, pb = resolve(a, t), resolve(b, t)
                d = pb - pa
                on = (f % variants) == j
                ob.location = pa
                ob.rotation_quaternion = d.to_track_quat('X', 'Z') @ Quaternion((1, 0, 0), f * 1.7) if d.length > 1e-6 else Quaternion()
                L = max(1e-4, d.length)
                ob.scale = (L, L, L) if on else (0, 0, 0)
                ob.data.bevel_depth = width / max(1e-3, L)
                ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_quaternion', frame=f); ob.keyframe_insert('scale', frame=f)
                ob.data.keyframe_insert('bevel_depth', frame=f)
            _kf(ob, 'scale', f1 + 1, (0, 0, 0))
        if glow_ends:
            self.blob(resolve(b, t0), t0, t1, (width * 8, width * 10), color, kind='glow', alpha=(0.9, 0.6), move=resolve(b, t1) - resolve(b, t0))
            self.light_flash(resolve(b, t0), t0, 400, color, t1 - t0)
        return obs

    def _arc_emitter(self, actor, p, d, length, width, color, spread, t0, t1, when):
        t1 = self.seconds if t1 is None else t1
        variants = 3
        obs = [self._bolt_obj(self.rng.random(), 0.16 * spread / 0.5, 2, width / max(1e-3, length)) for _ in range(variants)]
        q = d.to_track_quat('X', 'Z')
        for j, ob in enumerate(obs):
            ob.parent = actor.body
            ob.location = p; ob.rotation_mode = 'QUATERNION'
            ob.color = (*[min(1.0, c * 0.6 + 0.4) for c in color], 1.0)
            for f in range(frame_of(t0), frame_of(t1) + 1):
                t = f / FPS
                on = (f % variants) == j and (when is None or actor._state(when, t)) and actor.visible(t)
                k = length * (0.8 + 0.4 * ((f * 7 + j * 3) % 5) / 5)
                if when == 'moving':
                    k *= min(1.6, 0.5 + actor.speed(t) / max(1.0, actor.info.get('speed', 8)))
                ob.scale = (k, k, k) if on else (0, 0, 0)
                ob.rotation_quaternion = q @ Quaternion((1, 0, 0), f * 2.1 + j)
                ob.keyframe_insert('scale', frame=f); ob.keyframe_insert('rotation_quaternion', frame=f)
        g = bpy.data.objects.new('fx', _mesh('ball').copy()); self.scene.collection.objects.link(g)
        g.data.materials.append(blob_mat('glow')); g.parent = actor.body; g.location = p; g.scale = (width * 5,) * 3; g.color = (*color, 0.8)

    def _engine(self, actor, p, size, color, length, t0, t1):
        t1 = self.seconds if t1 is None else t1
        for k, (col, kind, s, L) in enumerate((((*color, 0.9), 'glow', 1.0, length), ((*WHITE_HOT, 1.0), 'hot', 0.45, length * 0.5))):
            g = bpy.data.objects.new('engine', _mesh('ball').copy()); self.scene.collection.objects.link(g)
            g.data.materials.append(blob_mat(kind)); g.parent = actor.body; g.color = col
            for f in range(frame_of(t0), frame_of(t1) + 1, 2):
                fl = 0.9 + 0.2 * ((f * 13 + k * 5) % 7) / 7
                thr = min(1.4, 0.6 + actor.speed(f / FPS) / max(1.0, actor.info.get('speed', 12))) if actor.kind != 'ship' else 1.0
                g.scale = (size * s * L * fl * thr, size * s, size * s)
                g.location = p + Vector((-size * s * L * fl * thr * 0.8, 0, 0))
                g.keyframe_insert('scale', frame=f); g.keyframe_insert('location', frame=f)

    def shield(self, owner, radius=None, color=None, scale=(1, 1, 1), strength=0.35):
        """Shield bubble around an Actor (or at a point). Use .flare(t, pos) for hits and .push(pusher, t0, t1)
        when something forces its way through. It never shatters."""
        if isinstance(owner, Actor):
            radius = radius or owner.radius * 1.25
            color = color or (TERRAN_BLUE if owner.faction == 'terran' else GOLD)
        return Shield(self, owner, radius or 5.0, color or TERRAN_BLUE, scale, strength)

    def _projectile(self, actor, w, org, tp, ts, fl, target, color, boom, i):
        st = w['style']
        terran = actor.faction == 'terran'
        col = color or (TERRAN_ORANGE if terran else GOLD)
        if st in ('laser',) and color is None:
            col = TERRAN_BLUE if terran else GOLD
        if actor.faction == 'shard' and color is None:
            col = SHARD
        fs = w.get('flash', 0)
        if fs:
            self.blob(org, ts, ts + 0.09, (fs * 0.55, fs * 0.25), WHITE_HOT if terran else col, kind='hot', alpha=(1.0, 0.2))
            self.blob(org, ts, ts + 0.14, (fs * 0.9, fs * 0.5), col, kind='glow', alpha=(0.9, 0.0))
            self.light_flash(org, ts, 500 * fs * fs, col, 0.12)
            if terran and st in ('shell', 'mortar'):
                self.puff(org, ts + 0.03, fs * 0.5, (0.3, 0.3, 0.3), life=0.7, rise=0.4, alpha=0.4)
        d = tp - org
        ti = ts + fl
        ground_hit = self.env == 'ground' and tp.z < 0.6
        if st in ('shell', 'tracer'):
            ob = bpy.data.objects.new('shot', _mesh('ball').copy()); self.scene.collection.objects.link(ob)
            ob.data.materials.append(blob_mat('hot')); ob.color = (*col, 1.0)
            L = (1.6 if st == 'shell' else 1.1) * (1 if self.env == 'ground' else 3)
            wd = 0.11 if st == 'shell' else 0.06
            ob.rotation_mode = 'QUATERNION'; ob.rotation_quaternion = d.to_track_quat('X', 'Z')
            f0, f1 = frame_of(ts), max(frame_of(ts) + 1, frame_of(ti))
            _kf(ob, 'scale', f0 - 1, (0, 0, 0))
            for f, p in ((f0, org), (f1, tp)):
                ob.location = p; ob.scale = (L, wd, wd)
                ob.keyframe_insert('location', frame=f); ob.keyframe_insert('scale', frame=f)
            _kf(ob, 'scale', f1 + 1, (0, 0, 0))
        elif st in ('missile', 'mortar', 'bomb'):
            ob = bpy.data.objects.new('shot', _mesh('ball').copy()); self.scene.collection.objects.link(ob)
            ob.data.materials.append(solid_mat('missile_' + actor.faction, (0.25, 0.26, 0.28) if terran else (0.75, 0.6, 0.3), 0.4,
                                               emit=None if terran else GOLD, strength=4.0))
            ob.rotation_mode = 'QUATERNION'
            f0, f1 = frame_of(ts), max(frame_of(ts) + 2, frame_of(ti))
            arc = d.length * (0.12 if st == 'missile' else 0.35 if st == 'mortar' else 0.0)
            side = Vector((-d.y, d.x, 0)).normalized() * (self.rng.uniform(-1, 1) * d.length * 0.06 if st == 'missile' else 0)
            _kf(ob, 'scale', f0 - 1, (0, 0, 0))
            prev = org
            for f in range(f0, f1 + 1):
                u = (f - f0) / (f1 - f0)
                t = ts + u * fl
                end = resolve(target, t) if (st == 'missile' and not isinstance(target, (tuple, list, Vector))) else tp
                if st == 'missile' and u > 0.999:
                    end = tp
                uu = u * u * (0.6 + 0.4 * u) if st == 'missile' else u
                if st == 'bomb':
                    v0 = actor.path(ts) - actor.path(ts - 0.05)
                    p = org.lerp(tp, u); p.z = org.z + (tp.z - org.z) * u * u
                else:
                    p = org.lerp(end if st == 'missile' else tp, uu) + Vector((0, 0, arc * 4 * u * (1 - u))) + side * math.sin(math.pi * u)
                dd = p - prev
                ob.location = p
                if dd.length > 1e-5:
                    ob.rotation_quaternion = dd.to_track_quat('X', 'Z')
                s = 0.16 if st == 'missile' else 0.2 if st == 'mortar' else 0.24
                if self.env == 'space':
                    s *= 2.5
                ob.scale = (s * 3.2, s, s)
                ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_quaternion', frame=f); ob.keyframe_insert('scale', frame=f)
                if st != 'bomb':
                    tt = f / FPS
                    self.blob(p - dd.normalized() * s * 3 if dd.length > 1e-5 else p, tt, tt + 0.1, s * 2.2, col, kind='hot' if st == 'missile' else 'glow', alpha=(1, 0.2))
                    if st == 'missile' or f % 2 == 0:
                        g = 0.6 if terran else 0.5
                        self.puff(p, tt, s * 2.4, (g, g, g) if terran else (0.6, 0.5, 0.3), life=0.8, rise=0.2, alpha=0.4)
                prev = p
            _kf(ob, 'scale', f1 + 1, (0, 0, 0))
        elif st == 'laser':
            dur = 0.12
            self.beam(org, tp, ts, ts + dur, col, width=0.07 * (1 if self.env == 'ground' else 2.5))
            ti = ts + 0.02
        elif st == 'beam':
            dur = max(0.1, w.get('interval', 0.12) * 0.9)
            self.beam(lambda t, a=actor, o=org - actor.pos(ts): a.pos(t) + o, tp, ts, ts + dur, col, width=0.16 * (1 if self.env == 'ground' else 3))
            ti = ts + 0.03
        elif st == 'lightning':
            dur = 0.16
            self.lightning(lambda t, a=actor, o=org - actor.pos(ts): a.pos(t) + o, target if isinstance(target, Actor) and tp == resolve(target, ts + fl) else tp, ts, ts + dur, col, width=0.05 * (1 if self.env == 'ground' else 2.5))
            ti = ts + 0.03
        if boom:
            if st in ('laser', 'lightning', 'tracer'):
                self.sparks(tp, ti, boom)
                if ground_hit:
                    self.puff(tp, ti, boom * 1.5, self.dust_color, life=0.8, rise=0.6, alpha=0.5)
            else:
                self.explosion(tp, ti, boom, ground=ground_hit, color=(1.0, 0.5, 0.12) if terran else (1.0, 0.7, 0.2))
        return ti

    # ---- camera
    def camera_orbit(self, target=(0, 0, 1), radius=18.0, height=6.0, angle=(20, 140), t0=0.0, t1=None, lens=35, look=(0, 0, 0), ease='smooth'):
        """Circle the camera around a target (Actor, point or function of time). radius, height, angle (degrees,
        0 = camera on +X looking back) and lens may be single values or (start, end)."""
        t1 = self.seconds if t1 is None else t1
        pair = lambda v: v if isinstance(v, (tuple, list)) else (v, v)
        self.cam_segs.append(dict(kind='orbit', target=target, r=pair(radius), h=pair(height), a=pair(angle), t0=t0, t1=t1, lens=pair(lens), look=V(look), ease=ease))
        return self

    def camera_path(self, pts, look_at, t0=None, t1=None, lens=35, look=(0, 0, 0)):
        """Move the camera through (t, x, y, z) points while it watches look_at (Actor, point or function of time)."""
        path = Path(pts)
        pair = lambda v: v if isinstance(v, (tuple, list)) else (v, v)
        self.cam_segs.append(dict(kind='path', path=path, target=look_at, t0=path.t[0] if t0 is None else t0, t1=path.t[-1] if t1 is None else t1, lens=pair(lens), look=V(look)))
        return self

    def shake(self, t, amp=0.15, dur=0.4):
        """Camera shake at time t (big hits)."""
        self.shakes.append((t, amp, dur))
        return self

    def _bake_camera(self):
        if not self.cam_segs:
            focus = self.actors[0] if self.actors else (0, 0, 1)
            self.camera_orbit(focus, radius=16, height=6, angle=(25, 150))
        segs = sorted(self.cam_segs, key=lambda s: s['t0'])
        prev_q = None
        rr = random.Random(7)
        noise = [(rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-1, 1)) for _ in range(self.frames + 2)]
        for f in range(self.frames + 1):
            t = f / FPS
            s = segs[0]
            for c in segs:
                if c['t0'] <= t:
                    s = c
            tt = min(max(t, s['t0']), s['t1'])
            u = (tt - s['t0']) / max(1e-6, s['t1'] - s['t0'])
            tgt = resolve(s['target'], tt) + s['look']
            if s['kind'] == 'orbit':
                k = smooth(u) if s['ease'] == 'smooth' else u
                a = math.radians(lerp(s['a'][0], s['a'][1], k))
                r = lerp(s['r'][0], s['r'][1], k); h = lerp(s['h'][0], s['h'][1], k)
                pos = Vector((tgt.x + r * math.cos(a), tgt.y + r * math.sin(a), max(0.4 if self.env == 'ground' else -1e9, tgt.z - s['look'].z + h)))
            else:
                pos = s['path'](tt)
            sh = Vector((0, 0, 0))
            for (ts, amp, dur) in self.shakes:
                x = t - ts
                if 0 <= x < dur:
                    sh += Vector(noise[f]) * amp * (1 - x / dur) ** 2
            pos = pos + sh
            q = (tgt + sh * 0.5 - pos).to_track_quat('-Z', 'Y')
            if prev_q is not None and q.dot(prev_q) < 0:
                q.negate()
            prev_q = q
            self.cam.location = pos; self.cam.rotation_quaternion = q
            self.cam.data.lens = lerp(s['lens'][0], s['lens'][1], smooth(u))
            self.cam.keyframe_insert('location', frame=f); self.cam.keyframe_insert('rotation_quaternion', frame=f)
            self.cam.data.keyframe_insert('lens', frame=f)

    # ---- output
    def bake(self):
        for a in list(self.actors):
            a._bake()
        self._bake_camera()
        # remove unused import templates' influence: templates are never linked to the scene

    def _render_settings(self):
        sc, q = self.scene, self.args.quality
        res, samples = {'draft': ((480, 270), 6), 'mid': ((960, 540), 12), 'final': ((1280, 720), 16)}[q]
        sc.render.engine = 'CYCLES'
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        c = sc.cycles
        c.device = 'CPU'
        c.samples = self.args.samples or samples
        c.use_adaptive_sampling = True; c.adaptive_threshold = 0.05
        c.use_denoising = True
        try:
            c.denoiser = 'OPENIMAGEDENOISE'
            c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
            c.denoising_prefilter = 'FAST'
        except Exception:
            pass
        c.max_bounces = 3; c.diffuse_bounces = 1; c.glossy_bounces = 2; c.transmission_bounces = 2; c.transparent_max_bounces = 10; c.volume_bounces = 0
        c.caustics_reflective = False; c.caustics_refractive = False
        c.sample_clamp_indirect = 4.0
        try:
            c.use_light_tree = False
        except Exception:
            pass
        sc.render.use_persistent_data = True
        if self.args.threads:
            sc.render.threads_mode = 'FIXED'; sc.render.threads = self.args.threads
        sc.render.image_settings.file_format = 'PNG'
        sc.render.image_settings.color_mode = 'RGB'
        sc.render.image_settings.compression = 30
        try:
            sc.view_settings.view_transform = 'AgX'
            sc.view_settings.look = 'AgX - Medium High Contrast'
        except Exception:
            pass
        self._bloom()

    def _bloom(self):
        try:
            sc = self.scene
            tree = bpy.data.node_groups.new('PromoComp', 'CompositorNodeTree')
            sc.compositing_node_group = tree
            rl = tree.nodes.new('CompositorNodeRLayers')
            gl = tree.nodes.new('CompositorNodeGlare')
            out = tree.nodes.new('NodeGroupOutput')
            tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            for k, v in (('Type', 'Bloom'), ('Quality', 'Medium'), ('Threshold', 1.0), ('Strength', 0.7), ('Size', 0.55)):
                try:
                    gl.inputs[k].default_value = v
                except Exception:
                    pass
            tree.links.new(rl.outputs['Image'], gl.inputs['Image'])
            tree.links.new(gl.outputs['Image'], out.inputs[0])
            sc.render.use_compositing = True
        except Exception as e:
            print('bloom unavailable:', e)

    def render(self):
        """Bake everything, render the requested frames, and write an mp4 plus a contact sheet."""
        t_b = time.time()
        self.bake()
        self._render_settings()
        a = self.args
        out = a.out or os.path.join('/home/user/promo-work', self.name, a.quality)
        fdir = os.path.join(out, 'frames')
        os.makedirs(fdir, exist_ok=True)
        if a.save_blend:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, self.name + '.blend'))
        print(f'[promo] baked in {time.time() - t_b:.1f}s, {len(bpy.data.objects)} objects')
        if a.no_render:
            return out
        sc = self.scene
        t0 = time.time()
        if a.stills:
            frames = [int(x) for x in a.stills.split(',')]
            for f in frames:
                sc.frame_set(f)
                sc.render.filepath = os.path.join(fdir, f'{f:04d}.png')
                bpy.ops.render.render(write_still=True)
        else:
            f0, f1 = (int(x) for x in a.frames.split('-')) if a.frames else (0, self.frames - 1)
            sc.frame_start, sc.frame_end = f0, f1
            sc.render.filepath = os.path.join(fdir, '')
            bpy.ops.render.render(animation=True)
            frames = list(range(f0, f1 + 1))
        dt = time.time() - t0
        print(f'[promo] rendered {len(frames)} frames in {dt:.0f}s = {dt / len(frames):.2f} s/frame ({a.quality})')
        sheet = os.path.join(out, f'{self.name}_{a.quality}_sheet.jpg')
        pick = frames if len(frames) <= 12 else [frames[int(i * (len(frames) - 1) / 11)] for i in range(12)]
        contact_sheet([os.path.join(fdir, f'{f:04d}.png') for f in pick], sheet, labels=[f'{f / FPS:.2f}s' for f in pick])
        print('[promo] sheet', sheet)
        if not a.stills:
            mp4 = os.path.join(out, f'{self.name}_{a.quality}.mp4')
            encode(fdir, mp4, sc.frame_start)
            print('[promo] video', mp4)
        return out


def contact_sheet(files, out, labels=None, cols=4, width=1920):
    from PIL import Image, ImageDraw
    ims = [Image.open(f).convert('RGB') for f in files if os.path.exists(f)]
    if not ims:
        return
    cols = min(cols, len(ims))
    w = width // cols
    h = int(w * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (w * cols, h * rows), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y))
        if labels:
            d.text((x + 6, y + 4), labels[i], fill=(255, 255, 0))
    sheet.save(out, quality=88)


def encode(frame_dir, out, start=0):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(start), '-i', os.path.join(frame_dir, '%04d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-movflags', '+faststart', out], check=True)
