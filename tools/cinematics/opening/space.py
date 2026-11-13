"""The shared space battle for the 60 s opening video (approved timeline v2, 2026-11-13).

One clock for everything: frame 1 = 0:00, 24 fps, 1,440 frames. Every ship, beam, comet and
explosion is keyed on that clock here, once. A shot is only a camera and a frame range
(see film.py). All randomness uses fixed seeds, so any frame renders the same on any day.

Layout (world units ~ metres, +X points from the Terran line toward the rift):
    planet Vesper far below (centre z = -3100), the Terran line around x = -150 facing +X,
    the Arcadian fleet holding around x = +300 facing -X, the rift at x = +700.
    The squid hunt happens in a quieter patch at SQUID_ZONE.

Build only what a shot needs: Space(need={'terran', 'arcadian', ...}).
"""
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402
from mathutils import Vector, Euler, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import forge as F  # noqa: E402
import ships as base  # noqa: E402
import ships_hd as hd  # noqa: E402
import arcadian_fleet as AF  # noqa: E402
import terran_fleet as T  # noqa: E402
import new_pieces as NP  # noqa: E402
import barrage_pieces as BP  # noqa: E402

FPS = 24
NF = 1440
DREAD_YAW = -65.0
FIGHTER_K = 3.0      # fighters are drawn 3x so they read on a phone screen
OS = C.OS

BLUE = (0.3, 0.7, 1.0)
GOLD = (1.0, 0.62, 0.15)
VIOLET = (0.55, 0.15, 1.0)

RIFT_AT = Vector((700.0, 0.0, 120.0))
SQUID_ZONE = Vector((150.0, 700.0, 80.0))
PLANET_C = Vector((0.0, 0.0, -2600.0))
PLANET_R = 2400.0


_L = Vector((0.604, -0.72, 0.0)).normalized()
SHOT1_CAM = Vector((0.0, 0.0, -2600.0)) + _L * 5400 + Vector((0, 0, 1500))


def fr(t):
    """Global frame at t seconds."""
    return int(round(1 + t * FPS))


# ================================================================== keying helpers
def lin(idblock):
    C.set_interp(idblock, 'LINEAR')


def key_loc(obj, keys, interp='BEZIER'):
    for f, p in keys:
        obj.location = p
        obj.keyframe_insert('location', frame=f)
    C.set_interp(obj, interp)


def key_rot(obj, keys, interp='BEZIER'):
    """keys: [(frame, (rx, ry, rz) degrees)]"""
    obj.rotation_mode = 'XYZ'
    for f, r in keys:
        obj.rotation_euler = [math.radians(a) for a in r]
        obj.keyframe_insert('rotation_euler', frame=f)
    C.set_interp(obj, interp)


def key_scale(obj, keys, interp='BEZIER'):
    for f, s in keys:
        obj.scale = s if isinstance(s, (tuple, list, Vector)) else (s, s, s)
        obj.keyframe_insert('scale', frame=f)
    C.set_interp(obj, interp)


def show(obj, f0, f1, tree=True):
    """Visible only for frames f0..f1 (inclusive)."""
    objs = [obj] + (list(obj.children_recursive) if tree else [])
    for o in objs:
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=1)
        if f0 > 1:
            o.hide_render = True
            o.keyframe_insert('hide_render', frame=f0 - 1)
        o.hide_render = False
        o.keyframe_insert('hide_render', frame=max(1, f0))
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=f1 + 1)
        C.set_interp(o, 'CONSTANT')


def link(o):
    if o.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(o)
    return o


def copy_tree(obj, name=None):
    sc = bpy.context.scene

    def rec(o, parent):
        c = o.copy()
        c.animation_data_clear()
        sc.collection.objects.link(c)
        if parent is not None:
            c.parent = parent
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        for ch in o.children:
            rec(ch, c)
        return c
    c = rec(obj, None)
    if name:
        c.name = name
    return c


def value_node(mat, name, v):
    nt = mat.node_tree
    n = nt.nodes.new('ShaderNodeValue')
    n.name = name
    n.outputs[0].default_value = v
    return n


def key_node(mat, name, keys, interp='LINEAR'):
    nd = mat.node_tree.nodes[name]
    for f, v in keys:
        nd.outputs[0].default_value = v
        nd.outputs[0].keyframe_insert('default_value', frame=f)
    _interp_where(mat.node_tree, f'nodes["{name}"]', interp)


def _interp_where(idblock, path_part, kind):
    """Set interpolation only on the curves whose data path contains path_part (so keying one node
    never changes another node's animation, e.g. a material's running clock)."""
    ad = idblock.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        if path_part in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = kind


def add_fade(mat, name='fade', v=1.0):
    """Insert a final mix with Transparent driven by a Value node `name` (1 = fully shown)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    if not out.inputs['Surface'].links:
        return None
    src = out.inputs['Surface'].links[0].from_socket
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mx = nt.nodes.new('ShaderNodeMixShader')
    val = value_node(mat, name, v)
    nt.links.new(val.outputs[0], mx.inputs[0])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(src, mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    return val


def emit(name, col, s):
    return C.emit_mat(name, col, s)


def aim_quat(d, up='Z'):
    return Vector(d).to_track_quat('X', up)


def halo_mat(name, col, k, power=3.0):
    return BP._halo_mat(name, col, k) if power == 3.0 else BP._halo_mat(name, col, k)


# ================================================================== splitting meshes
def split_mesh(obj, groups, names=None):
    """Split obj into len(groups) copies; groups(face_centre_local) -> index. Returns objects with
    the same transform/materials (no parent, no animation)."""
    out = []
    n = None
    centres = [p.center.copy() for p in obj.data.polygons]
    ids = [groups(c) for c in centres]
    n = max(ids) + 1
    for g in range(n):
        me = obj.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        kill = [f for f in bm.faces if ids[f.index] != g]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new((names[g] if names else f'{obj.name}_part{g}'), me)
        link(o)
        o.matrix_world = obj.matrix_world.copy()
        out.append(o)
    return out


# ================================================================== effects
_n = [0]


def _uid(p):
    _n[0] += 1
    return f'{p}{_n[0]}'


def bolt(p0, p1, f0, frames, col, size=(4.0, 0.12, 0.12), strength=30.0, mat=None):
    """Laser bolt flying p0 -> p1 in `frames` frames starting at f0."""
    m = mat or emit(_uid('BoltM'), col, strength)
    o = C.uv_sphere(_uid('Bolt'), 1.0, seg=(10, 6), mat=m, scale=size)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = aim_quat(Vector(p1) - Vector(p0))
    key_loc(o, [(f0, p0), (f0 + frames, p1)], 'LINEAR')
    show(o, f0, f0 + frames)
    o.visible_shadow = False
    return o


_bmats = {}


def gas_fireball_mat(name, hot, cool, seed=0.0):
    """Billowing gas fireball: churning 4D noise, dense hot core, ragged see-through edges.
    Value nodes 'S' (emission strength) and 'V' (visibility 0..1) are keyed by boom()."""
    m, n = BP._new_mat(name)
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', 1.6)
    nz = n.node('ShaderNodeTexNoise', Scale=1.9, Detail=8.0, Distortion=0.25, Roughness=0.6)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], n.math('ADD', t, seed))
    lw = n.node('ShaderNodeLayerWeight', Blend=0.5)
    body = n.math('POWER', n.math('SUBTRACT', 1.0, lw.outputs['Facing']), 1.4)
    st = n.maprange(nz.outputs['Fac'], 0.35, 0.68, 0.0, 1.0)          # billow structure
    heat = n.math('MULTIPLY', st, body)
    sv = value_node(m, 'S', 3.0).outputs[0]
    vv = value_node(m, 'V', 1.0).outputs[0]
    ramp = n.node('ShaderNodeValToRGB')
    n.set(ramp.inputs[0], heat)
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (*[c * 0.08 for c in cool], 1)
    els[1].position, els[1].color = 1.0, (*[min(1.0, c * 0.4 + 0.6) for c in hot], 1)
    e = els.new(0.35)
    e.color = (*cool, 1)
    e = els.new(0.75)
    e.color = (*hot, 1)
    em = n.node('ShaderNodeEmission')
    n.set(em.inputs['Color'], ramp.outputs[0])
    n.set(em.inputs['Strength'], n.math('MULTIPLY', n.math('POWER', heat, 1.3), n.math('MULTIPLY', sv, 0.7)))
    tr = n.node('ShaderNodeBsdfTransparent')
    mx = n.node('ShaderNodeMixShader')
    alpha = n.math('MULTIPLY', n.math('MULTIPLY_ADD', st, 0.7, 0.3), n.math('MULTIPLY', body, 1.5))
    n.set(mx.inputs[0], n.math('MINIMUM', n.math('MULTIPLY', alpha, vv), 1.0))
    n.set(mx.inputs[1], tr.outputs[0])
    n.set(mx.inputs[2], em.outputs[0])
    n.set(out.inputs['Surface'], mx.outputs[0])
    return m


def boom(p, f0, size, hot=(1.0, 0.45, 0.06), cool=(0.35, 0.03, 0.005), life=1.2, light=0.0, follow=None, seed=0):
    """Fireball at global frame f0 (wraps common.Shot.boom on the global clock)."""
    k = _uid('boom')
    m = gas_fireball_mat(k, hot, cool, seed=_n[0] * 1.7)
    o = C.uv_sphere('B' + k, 1.0, seg=(24, 14), mat=m)
    o.visible_shadow = False
    rnd = random.Random(seed + _n[0])
    o.rotation_euler = (rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6))
    f1 = f0 + life * FPS
    step = 3
    for f, s in [(f0, size * 0.15), (f0 + step, size * 0.75), (f1, size * 1.25)]:
        o.scale = (s, s, s)
        o.keyframe_insert('scale', frame=f)
    for j in range(3):                    # lumpy outline: secondary puffs share the material
        sub = C.uv_sphere('B' + k + f'_{j}', 1.0, seg=(18, 10), mat=m)
        sub.parent = o
        dv = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(0.45, 0.7)
        sub.location = dv
        sc_ = rnd.uniform(0.5, 0.7)
        sub.scale = (sc_, sc_, sc_)
        sub.visible_shadow = False
    o.scale = (1, 1, 1)
    o.location = p
    o.keyframe_insert('location', frame=f0)
    if follow is not None:
        o.location = Vector(p) + Vector(follow) * life
        o.keyframe_insert('location', frame=f1)
    C.key_value(m, 'S', 1, 0.0)
    C.key_value(m, 'S', f0, 0.0)
    C.key_value(m, 'S', f0 + 1, 7.0)
    C.key_value(m, 'S', f0 + 2 * step, 3.5)
    C.key_value(m, 'S', f1, 0.8)
    C.key_value(m, 'V', 1, 1.0)
    C.key_value(m, 'V', f0 + 2 * step, 1.0)
    C.key_value(m, 'V', f1, 0.0)
    show(o, int(f0), int(f1) + 1)
    lin(o)
    lin(m.node_tree)
    if light > 0:
        L = bpy.data.objects.new('L' + k, bpy.data.lights.new('L' + k, 'POINT'))
        link(L)
        L.location = p
        L.data.color = hot
        L.data.shadow_soft_size = size * 0.5
        for f, e in [(1, 0), (f0, 0), (f0 + 1, light), (min(f0 + 3 * step, (f0 + 1 + f1) / 2), light * 0.25), (f1, 0)]:
            L.data.energy = e
            L.data.keyframe_insert('energy', frame=f)
        lin(L.data)
    return o


def blue_boom(p, f0, size, **kw):
    return boom(p, f0, size, hot=(0.2, 0.55, 1.0), cool=(0.01, 0.04, 0.3), **kw)


def gold_boom(p, f0, size, **kw):
    return boom(p, f0, size, hot=(1.0, 0.75, 0.3), cool=(0.4, 0.12, 0.01), **kw)


def violet_boom(p, f0, size, **kw):
    return boom(p, f0, size, hot=(0.8, 0.45, 1.0), cool=(0.2, 0.02, 0.4), **kw)


def shards(p, f0, n, col, size, speed, seed, life=1.5, kind='tri', strength=8.0, frames=None, drift=None):
    """n small flat shards (triangles or hexagons) bursting out of p at f0."""
    rnd = random.Random(seed)
    m = emit(_uid('ShardM'), col, strength)
    objs = []
    for i in range(n):
        me = bpy.data.meshes.new('shard')
        bm = bmesh.new()
        k = 3 if kind == 'tri' else 6
        vs = [bm.verts.new((math.cos(2 * math.pi * j / k) * size * rnd.uniform(0.6, 1.2),
                            math.sin(2 * math.pi * j / k) * size * rnd.uniform(0.6, 1.2), 0)) for j in range(k)]
        bm.faces.new(vs)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(_uid('Shard'), me)
        link(o)
        me.materials.append(m)
        d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        if drift is not None:
            d = (d + Vector(drift)).normalized()
        v = speed * rnd.uniform(0.4, 1.0)
        f1 = int(f0 + life * FPS)
        key_loc(o, [(f0, p), (f1, Vector(p) + d * v * life)], 'LINEAR')
        key_rot(o, [(f0, (rnd.uniform(0, 360), rnd.uniform(0, 360), 0)),
                    (f1, (rnd.uniform(0, 220), rnd.uniform(0, 220), rnd.uniform(0, 100)))], 'LINEAR')
        show(o, f0, f1)
        o.visible_shadow = False
        objs.append(o)
    return objs


def flicker_lightning(pairs, seed, f0, f1, every=2, width=0.3, name='Lightning', zone_col=None, strength=25.0):
    """Static bolt variants shown one at a time between f0 and f1 (fixed seeds)."""
    objs = []
    with AF.gold_palette():
        base._faction('kesh')
        for v in range(3):
            rnd = random.Random(seed * 31 + v)
            m = F.mark()
            for a, b in pairs:
                AF.bolt(Vector(a), Vector(b), rnd, width=width, jag=0.22, depth=5, branches=2)
            objs.append(base._join(F.since(m), f'{name}{v}'))
    for o in objs:
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=1)
    for f in range(f0, f1 + 1, every):
        pick = ((f - f0) // every) % 3
        for i, o in enumerate(objs):
            o.hide_render = (i != pick)
            o.keyframe_insert('hide_render', frame=f)
    for o in objs:
        o.hide_render = True
        o.keyframe_insert('hide_render', frame=f1 + 1)
        C.set_interp(o, 'CONSTANT')
        o.visible_shadow = False
    if zone_col is not None:
        m = emit(_uid('LtM'), zone_col, strength)
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(m)
    return objs


def beam(p0, d, name, col, core_col, r, keys, strength=40.0, glow=8.0):
    """Beam from p0 along direction d. keys: [(frame, length, radius_k)] keyed on the beam length
    (mesh is a unit cylinder along +X from 0 to 1, scaled)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=1.0, radius2=1.0, depth=1.0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.5, 0, 0))
    bm.to_mesh(me)
    bm.free()
    core = bpy.data.objects.new(name, me)
    link(core)
    me.materials.append(emit(name + 'Core', core_col, strength))
    halo = bpy.data.objects.new(name + 'Halo', me.copy())
    link(halo)
    halo.data.materials.clear()
    halo.data.materials.append(BP._halo_mat(name + 'HaloM', col, glow))
    halo.parent = core
    halo.scale = (1, 6.0, 6.0)
    core.location = p0
    core.rotation_mode = 'QUATERNION'
    core.rotation_quaternion = aim_quat(d)
    for f, L, rk in keys:
        core.scale = (max(L, 0.01), r * 0.45 * rk + 1e-4, r * 0.45 * rk + 1e-4)
        core.keyframe_insert('scale', frame=f)
    lin(core)
    for o in (core, halo):
        o.visible_shadow = False
    show(core, keys[0][0], keys[-1][0])
    return core



# ================================================================== laser v2 pieces
def flow_emit(name, col, strength, scale=0.35, speed=4.0, lo=0.55, hi=1.6):
    """Emission whose strength churns with a 4D noise in world space (energy flowing through)."""
    m, n = BP._new_mat(name)
    tc = n.node('ShaderNodeTexCoord')
    t = BP.time_value(m, 'time', speed)
    nz = n.node('ShaderNodeTexNoise', Scale=scale, Detail=4.0)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], t)
    k = n.maprange(nz.outputs['Fac'], 0.3, 0.7, lo, hi)
    BP._add_out(n, n.math('MULTIPLY', k, strength), col, trans=False)
    return m


def beam_twist(src, d, name, col, len_keys, f0, f1, radius=2.2, pitch=14.0, strands=3, width=0.22,
               turns_per_s=1.5, length=900.0):
    """Energy ribbons twisting round a beam. len_keys: [(frame, length)] (world units) keyed on a
    mask so the ribbons grow with the beam; the ribbons spin round the beam axis."""
    root = bpy.data.objects.new(name, None)
    link(root)
    root.location = src
    root.rotation_mode = 'QUATERNION'
    root.rotation_quaternion = aim_quat(d)
    base._faction('terran')
    mk = F.mark()
    nseg = int(length / pitch * 16)
    for j in range(strands):
        ph = 2 * math.pi * j / strands
        pts = []
        for i in range(nseg + 1):
            x = length * i / nseg
            a = ph + 2 * math.pi * x / pitch
            rr = radius * (1.0 + 0.18 * math.sin(x * 0.21 + j))
            pts.append((x, rr * math.cos(a), rr * math.sin(a)))
        F.sweep(pts, [(width, width)] * len(pts), 'glow', sides=4, caps=False)
    rib = base._join(F.since(mk), name + 'Rib')
    m, n = BP._new_mat(name + 'M')
    tc = n.node('ShaderNodeTexCoord')
    sep = n.node('ShaderNodeSeparateXYZ')
    n.set(sep.inputs[0], tc.outputs['Object'])
    lv = value_node(m, 'len', 0.0).outputs[0]
    mask = n.math('LESS_THAN', sep.outputs[0], lv)
    t = BP.time_value(m, 'time', 6.0)
    nz = n.node('ShaderNodeTexNoise', Scale=0.25, Detail=3.0)
    nz.noise_dimensions = '4D'
    n.set(nz.inputs['Vector'], tc.outputs['Object'])
    n.set(nz.inputs['W'], t)
    k = n.maprange(nz.outputs['Fac'], 0.35, 0.65, 0.15, 1.6)
    BP._add_out(n, n.math('MULTIPLY', n.math('MULTIPLY', k, mask), 9.0), col)
    rib.data.materials.clear()
    rib.data.materials.append(m)
    rib.parent = root
    rib.visible_shadow = False
    key_node(m, 'len', [(f, L) for f, L in len_keys])
    rib.rotation_mode = 'XYZ'
    rib.rotation_euler = (0, 0, 0)
    rib.keyframe_insert('rotation_euler', frame=f0)
    rib.rotation_euler = (turns_per_s * 2 * math.pi * (f1 - f0) / FPS, 0, 0)
    rib.keyframe_insert('rotation_euler', frame=f1)
    lin(rib)
    show(root, f0, f1)
    return root


def spark_stream(p, f0, f1, col, drift, seed, every=2, n=7, size=0.35, speed=60, life=0.7, strength=16.0):
    """Continuous spray of thin glowing sparks (streaks aimed along their flight, no spin), a few
    launched every `every` frames from f0 to f1, fading as they cool."""
    rnd = random.Random(seed)
    m = emit(_uid('SparkM'), col, strength)
    src = C.uv_sphere(_uid('SparkSrc'), 1.0, seg=(6, 4), mat=m)
    src.hide_render = True
    for f in range(f0, f1, every):
        for i in range(n):
            d = (Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * 0.8 + Vector(drift))
            d = d.normalized()
            v = speed * rnd.uniform(0.4, 1.0)
            L = size * rnd.uniform(2.0, 4.5)
            o = bpy.data.objects.new(_uid('Spark'), src.data)
            link(o)
            o.scale = (L, size * 0.12, size * 0.12)
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = aim_quat(d)
            f1_ = int(f + life * FPS * rnd.uniform(0.6, 1.0))
            key_loc(o, [(f, Vector(p)), (f1_, Vector(p) + d * v * life)], 'LINEAR')
            show(o, f, f1_)
            o.visible_shadow = False


def impact_flare(p, d, f0, f1, col, size, name):
    """Flattened glow splash where a beam meets a surface, pulsing every 3 frames."""
    o = C.uv_sphere(name, 1.0, seg=(24, 12), mat=BP._halo_mat(name + 'M', col, 10.0))
    o.location = p
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = aim_quat(d)
    keys = []
    for i, f in enumerate(range(f0, f1 + 1, 3)):
        k = size * (1.0 if i % 2 == 0 else 0.78)
        keys.append((f, (k * 0.8, k, k)))
    key_scale(o, keys, 'LINEAR')
    show(o, f0, f1)
    o.visible_shadow = False
    core = C.uv_sphere(name + 'Core', 1.0, seg=(16, 8), mat=emit(name + 'CoreM', (1.0, 0.85, 0.55), 14.0),
                       scale=(size * 0.12, size * 0.3, size * 0.3))
    core.parent = o
    core.scale = (0.3, 0.14, 0.14)
    core.visible_shadow = False
    show(core, f0, f1)
    return o


def torn_hole(parent, loc_l, nrm_l, name, f0, f_grow, r0=1.5, r1=3.4, lift=1.2, petals=9, seed=0,
              heat_keys=None):
    """Hole torn in the hull: a black throat with a molten rim and jagged metal petals peeled
    outward, glowing hot at the hole and cooling toward their tips. Parented to the ship."""
    rnd = random.Random(seed)
    root = bpy.data.objects.new(name, None)
    link(root)
    root.parent = parent
    root.location = loc_l
    root.rotation_mode = 'QUATERNION'
    root.rotation_quaternion = Vector(nrm_l).normalized().to_track_quat('Z', 'Y')
    # petals
    me = bpy.data.meshes.new(name + 'Petals')
    bm = bmesh.new()
    heat = []
    for i in range(petals):
        a0 = 2 * math.pi * (i + rnd.uniform(0.05, 0.2)) / petals
        a1 = 2 * math.pi * (i + rnd.uniform(0.8, 0.95)) / petals
        tip = r0 + (r1 - r0) * rnd.uniform(0.55, 1.15)
        lf = lift * rnd.uniform(0.5, 1.4)
        rows = []
        for t in (0.0, 0.35, 0.7, 1.0):
            r = r0 + (tip - r0) * t
            narrow = 1.0 - 0.75 * t ** 1.5
            am, half = (a0 + a1) / 2, (a1 - a0) / 2 * narrow
            z = lf * t * t + 0.05
            row = []
            for aa in (am - half, am, am + half):
                jag = rnd.uniform(-0.12, 0.12) * t
                row.append(bm.verts.new(((r + jag) * math.cos(aa), (r + jag) * math.sin(aa), z)))
                heat.append(1.0 - t)
            rows.append(row)
        for a, b in zip(rows, rows[1:]):
            bm.faces.new((a[0], a[1], b[1], b[0]))
            bm.faces.new((a[1], a[2], b[2], b[1]))
    bm.to_mesh(me)
    bm.free()
    at = me.attributes.new('heat', 'FLOAT', 'POINT')
    for i, h in enumerate(heat):
        at.data[i].value = h
    pet = bpy.data.objects.new(name + 'Petals', me)
    link(pet)
    m, n = BP._new_mat(name + 'PetalM')
    out = n.node('ShaderNodeOutputMaterial')
    bsdf = n.node('ShaderNodeBsdfPrincipled', Metallic=0.8, Roughness=0.45)
    bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.06, 1)
    ha = n.node('ShaderNodeAttribute')
    ha.attribute_name = 'heat'
    h = n.math('POWER', ha.outputs['Fac'], 2.2)
    ramp = n.node('ShaderNodeValToRGB')
    n.set(ramp.inputs[0], h)
    ramp.color_ramp.elements[0].color = (0.25, 0.02, 0.0, 1)
    ramp.color_ramp.elements[1].color = (1.0, 0.75, 0.35, 1)
    e = ramp.color_ramp.elements.new(0.5)
    e.color = (1.0, 0.25, 0.02, 1)
    gv = value_node(m, 'glow', 18.0).outputs[0]
    n.set(bsdf.inputs['Emission Color'], ramp.outputs[0])
    n.set(bsdf.inputs['Emission Strength'], n.math('MULTIPLY', h, gv))
    n.set(out.inputs['Surface'], bsdf.outputs[0])
    me.materials.append(m)
    pet.parent = root
    # black throat + molten lip
    throat = C.uv_sphere(name + 'Throat', 1.0, seg=(20, 10), mat=emit(name + 'ThroatM', (0, 0, 0), 0.0),
                         scale=(r0 * 0.95, r0 * 0.95, 0.06))
    throat.parent = root
    base._faction('terran')
    lip = base._join([F.lathe([(r0 * 0.9, 0.1), (r0 * 1.15, 0.0), (r0 * 0.95, -0.12)], 24, 'glow')], name + 'Lip')
    lip.data.materials.clear()
    lm = emit(name + 'LipM', (1.0, 0.35, 0.03), 6.0)
    lip.data.materials.append(lm)
    lip.parent = root
    heat_keys = heat_keys or [(f_grow, 18.0), (f_grow + 48, 6.0), (NF, 2.0)]
    key_node(m, 'glow', heat_keys)
    lem = next(nd for nd in lm.node_tree.nodes if nd.type == 'EMISSION')
    for f, g in heat_keys:
        lem.inputs[1].default_value = g * 0.4
        lem.inputs[1].keyframe_insert('default_value', frame=f)
    for o in (pet, throat, lip):
        o.visible_shadow = False
    key_scale(root, [(f0, 0.15), (f_grow, 1.0)], 'LINEAR')
    show(root, f0, NF)
    return root

# ================================================================== Terran triangle shield (keyable)
def tshield(name, size, hit=None, hole=None):
    """Triangle shield (see barrage_pieces.tri_shield) with keyable Value nodes:
    'vis' (0..1 shown), 'hitk' (0..1 hit darkening), 'ring' (ripple radius, unit-sphere units),
    'hole' (hole radius, 0 = none)."""
    o = BP.tri_shield(size, hits=(), hole=None, name=name)
    m = o.data.materials[0]
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    mix = out.inputs['Surface'].links[0].from_node          # Mix(transparent, emission)
    em = mix.inputs[2].links[0].from_node
    opa_sock = mix.inputs[0].links[0].from_socket
    str_sock = em.inputs['Strength'].links[0].from_socket
    col_sock = em.inputs['Color'].links[0].from_socket
    n = BP._NT(m)
    tc = n.node('ShaderNodeTexCoord')
    edge = None
    for nd in nt.nodes:
        if nd.type == 'ATTRIBUTE':
            edge = n.math('SUBTRACT', 1.0, nd.outputs['Fac'])
    vis = value_node(m, 'vis', 1.0).outputs[0]
    hitk = value_node(m, 'hitk', 0.0).outputs[0]
    ring = value_node(m, 'ring', 0.0).outputs[0]
    hole_r = value_node(m, 'hole', 0.0).outputs[0]
    opa, strength, col = opa_sock, str_sock, col_sock
    if hit is not None:
        d = n.node('ShaderNodeVectorMath', operation='DISTANCE')
        n.set(d.inputs[0], tc.outputs['Object'])
        d.inputs[1].default_value = tuple(Vector(hit).normalized())
        dist = d.outputs['Value']
        zone = n.math('MULTIPLY', n.maprange(dist, 0.05, 0.45, 1.0, 0.0), hitk)
        col = n.mix(n.math('MULTIPLY', zone, 0.9), col, (0.0, 0.02, 0.45))
        opa = n.math('MULTIPLY_ADD', zone, 0.5, opa)
        rg = n.math('MULTIPLY', n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', dist, ring)), 0.0, 0.05, 1.0, 0.0),
                    n.math('GREATER_THAN', ring, 0.001))
        rg = n.math('MULTIPLY', rg, edge)
        col = n.mix(n.math('MULTIPLY', rg, 0.8), col, (0.35, 0.75, 1.0))
        opa = n.math('MULTIPLY_ADD', rg, 0.5, opa)
        strength = n.math('MULTIPLY_ADD', rg, 5.0, strength)        # ripples flare as they race out
        flash = n.math('MULTIPLY', n.maprange(dist, 0.0, 0.08, 14.0, 0.0), hitk)
        strength = n.math('ADD', strength, flash)
        # hole
        rim = n.math('MULTIPLY', n.maprange(n.math('ABSOLUTE', n.math('SUBTRACT', dist, hole_r)), 0.0, 0.025, 1.0, 0.0),
                     n.math('GREATER_THAN', hole_r, 0.001))
        strength = n.math('MULTIPLY_ADD', rim, 25.0, strength)
        opa = n.math('ADD', opa, rim)
        inside = n.math('LESS_THAN', dist, n.math('SUBTRACT', hole_r, 0.01))
        opa = n.math('MULTIPLY', opa, n.math('SUBTRACT', 1.0, inside))
    opa = n.math('MULTIPLY', n.math('MINIMUM', opa, 1.0), vis)
    n.set(mix.inputs[0], opa)
    n.set(em.inputs['Strength'], strength)
    n.set(em.inputs['Color'], col)
    return o


def shield_on(o, f_on, flicker=True):
    m = o.data.materials[0]
    keys = [(1, 0.0), (f_on - 1, 0.0)]
    if flicker:
        keys += [(f_on, 0.8), (f_on + 1, 0.15), (f_on + 2, 0.9), (f_on + 3, 0.3), (f_on + 5, 0.65)]
    else:
        keys += [(f_on + 6, 1.0)]
    key_node(m, 'vis', keys, 'CONSTANT' if flicker else 'LINEAR')


# ================================================================== the scene
class Space:
    def __init__(self, need=(), draft=True):
        self.need = set(need)
        self.draft = draft
        self.sh = C.Shot(NF / FPS, FPS, draft)    # F.begin, fps, OS.NF/FPS
        OS.NF = NF
        self.obj = {}
        self.world()
        if self.need & {'arcadian', 'rift_open', 'beam', 'barrage', 'ending', 'dogfight'}:
            self.arcadian_fleet()
        if self.need & {'terran', 'beam', 'barrage', 'ending', 'dogfight', 'squid'}:
            self.terran_fleet()
        if 'beam' in self.need:
            self.flagship_beam()
        if 'barrage' in self.need:
            self.barrage()
        if 'dogfight' in self.need:
            self.dogfight()
        if 'squid' in self.need:
            self.squid_hunt()
        if 'drop' in self.need:
            self.drop()
        if 'ending' in self.need:
            self.ending()

    # -------------------------------------------------------------- world
    def world(self):
        OS.world()
        self.bg = bpy.context.scene.world.node_tree.nodes['Background']
        for f, v in [(1, 0.0), (fr(0.9), 1.0)]:          # 0:00 black, stars fade in
            self.bg.inputs['Strength'].default_value = v
            self.bg.inputs['Strength'].keyframe_insert('default_value', frame=f)
        sun = self.sh.sun(rot=(70, 0, -140), energy=4.0)
        self.sun_obj = sun
        bpy.context.view_layer.update()
        import planet
        self.planet = planet.build(PLANET_C, sun, draft=self.draft)
        # the sun's disc, seen once in shot 1: its edge clears Vesper's limb at 0:02
        c = SHOT1_CAM
        to_p = PLANET_C - c
        alpha = math.asin(PLANET_R * 1.02 / to_p.length)
        axis = to_p.cross(Vector((0, 0, 1))).normalized()
        disc = C.uv_sphere('SunDisc', 520.0, seg=(32, 16), mat=emit('SunDiscM', (1.0, 0.93, 0.8), 60.0))
        disc.visible_shadow = False
        for f, extra in [(1, -1.6), (fr(1.6), -0.9), (fr(3.0), 0.25)]:
            dirn = Matrix.Rotation(alpha + math.radians(extra), 3, axis) @ to_p.normalized()
            disc.location = c + dirn * 40000
            disc.keyframe_insert('location', frame=f)
        lin(disc)
        show(disc, 1, fr(3.0))
        rf = OS.rift()
        rf.location = RIFT_AT
        rf.rotation_mode = 'QUATERNION'
        rf.rotation_quaternion = Vector((-1, 0, 0.05)).to_track_quat('Z', 'Y')
        S = 260.0
        # 0:03 hairline crack -> 0:04 rips open -> stays (a slight breathing)
        key_scale(rf, [(1, (0.01, 0.01, 1)), (fr(3.0) - 1, (0.01, 0.01, 1)), (fr(3.0), (S * 0.6, 0.6, 1)),
                       (fr(3.7), (S * 0.9, 3.0, 1)), (fr(4.4), (S, S, 1)), (fr(5.5), (S * 1.02, S * 1.02, 1)),
                       (NF, (S * 1.05, S * 1.05, 1))])
        show(rf, fr(3.0), NF)
        self.rift = rf
        # black eye just behind the swirl, so ships still inside the rift stay hidden
        eye = C.uv_sphere('RiftEye', 1.0, seg=(48, 8), mat=emit('RiftEyeM', (0, 0, 0), 0.0), scale=(0.47, 0.47, 0.001))
        eye.parent = rf
        eye.location = (0, 0, -3.0)
        eye.visible_shadow = False
        show(eye, fr(3.0), NF)
        # rift light on the scene
        L = bpy.data.objects.new('RiftLight', bpy.data.lights.new('RiftLight', 'POINT'))
        link(L)
        L.location = RIFT_AT + Vector((-120, 0, 0))
        L.data.color = (0.8, 0.45, 1.0)
        L.data.shadow_soft_size = 60
        for f, e in [(1, 0), (fr(3.0), 0), (fr(4.4), 4e7), (NF, 3e7)]:
            L.data.energy = e
            L.data.keyframe_insert('energy', frame=f)
        lin(L.data)
        # gold lightning round the rift rim while it opens (fixed seeds)
        rnd = random.Random(7)
        pairs = []
        for i in range(7):
            a0 = rnd.uniform(0, 2 * math.pi)
            p0 = RIFT_AT + Vector((-5, math.cos(a0) * S * 0.75, math.sin(a0) * S * 0.75))
            a1 = a0 + rnd.uniform(0.3, 0.8)
            p1 = RIFT_AT + Vector((-25, math.cos(a1) * S * 1.15, math.sin(a1) * S * 1.15))
            pairs.append((p0, p1))
        flicker_lightning(pairs, 3, fr(3.8), fr(6.2), every=2, width=2.6, name='RiftBolt', zone_col=(1.0, 0.7, 0.25))

    # -------------------------------------------------------------- fleets
    def terran_fleet(self):
        o = self.obj
        dread, _ = hd.terran_dreadnought()
        for p in dread.data.polygons:
            p.use_smooth = True
        T.neon_lines(dread)
        dread.scale = (1.8, 1.8, 1.8)
        o['dread'] = dread
        bship, muz = T.broadside_battleship()
        T.neon_lines(bship)
        o['bship'] = bship
        self.muzzles = [Vector(m) for m in muz]
        frig = T.terran_frigate_v2()
        T.neon_lines(frig)
        o['frigate'] = frig
        ms, tubes = T.missile_ship()
        T.neon_lines(ms)
        o['missile_ship'] = ms
        self.tubes = [Vector(t) for t in tubes]
        cv = T.terran_corvette()
        T.neon_lines(cv)
        o['corvette0'] = cv
        for i in (1, 2, 3):
            o[f'corvette{i}'] = copy_tree(cv, f'TCorvette{i}')
        # holding formation (facing +X), slow drift forward
        self.T_HOLD = {
            'dread': Vector((-150, 0, 18)),
            'bship': Vector((-135, -70, -4)),
            'frigate': Vector((-170, 62, 6)),
            'missile_ship': Vector((-190, 120, -14)),
            'corvette0': Vector((-120, 34, 30)),
            'corvette1': Vector((-118, -36, 34)),
            'corvette2': Vector((-125, 95, 26)),
            'corvette3': Vector((-128, -110, 22)),
        }
        for k, p in self.T_HOLD.items():
            if k in ('dread', 'bship', 'frigate', 'missile_ship'):
                continue            # these get their own paths below
            key_loc(o[k], [(1, p - Vector((10, 0, 0))), (NF, p + Vector((25, 0, 0)))], 'LINEAR')
        # dreadnought: holds angled (bow 65 deg off the line), is hit side-on at 0:14-0:16,
        # then rolls over burning (see flagship_beam)
        key_rot(o['dread'], [(1, (0, 0, DREAD_YAW)), (NF, (0, 0, DREAD_YAW))])
        key_loc(o['dread'], [(1, self.T_HOLD['dread'] - Vector((8, 0, 0))), (fr(16.0), self.T_HOLD['dread']),
                             (NF, self.T_HOLD['dread'] + Vector((-10, 18, -35)))], 'LINEAR')
        # battleship: holds; the spin is keyed in barrage()
        key_loc(o['bship'], [(1, self.T_HOLD['bship'] - Vector((8, 0, 0))), (NF, self.T_HOLD['bship'] + Vector((10, 0, 0)))],
                'LINEAR')
        # frigate: launches fighters at 0:11, then moves to the squid zone (unseen) for 0:26-0:35
        fz = SQUID_ZONE + Vector((-260, 60, 30))
        key_loc(o['frigate'], [(1, self.T_HOLD['frigate'] - Vector((8, 0, 0))), (fr(12.5), self.T_HOLD['frigate']),
                               (fr(25.5), fz), (fr(31.0), fz + Vector((5, -2, 0)))], 'LINEAR')
        key_loc(o['missile_ship'], [(1, self.T_HOLD['missile_ship']), (fr(22.5), self.T_HOLD['missile_ship']),
                                    (fr(23.4), Vector((40, -150, -20))), (fr(26.0), Vector((52, -150, -20))),
                                    (NF, Vector((90, -140, -20)))], 'LINEAR')
        # shields (blue triangles), on at 0:10.2 .. 0:10.8, one big ship after another
        self.tsh = {}
        self.beam_geom()
        for k, f_on in (('dread', fr(10.25)), ('bship', fr(10.45)), ('frigate', fr(10.65)), ('missile_ship', fr(10.8))):
            ob = o[k]
            dims = Vector(ob.dimensions) / ob.scale.x
            size = (dims.x * 0.62, dims.y * 0.75 + 2.5, dims.z * 1.0 + 2.5)
            cen = sum((Vector(b) for b in ob.bound_box), Vector()) / 8
            hit = self.dread_hit_u if k == 'dread' else None
            sh = tshield(f'TShield_{k}', size, hit=hit)
            sh.parent = ob
            sh.scale = size
            sh.location = cen
            shield_on(sh, f_on)
            self.tsh[k] = sh
        # twin-X squadron: launched from the frigate's bays at 0:11, streaking toward the gold
        core, wname = T.twin_x_fighter('TwinX', seed=4)
        self.twinx_src = core
        self.twinx_wings = wname
        core.location = (0, 0, -9999)
        core.hide_render = True
        for ch in core.children_recursive:
            ch.hide_render = True
        self.fighters = []
        rnd = random.Random(21)
        fp = self.T_HOLD['frigate']
        for i in range(12):
            c = copy_tree(core, f'TwinX{i}')
            c.scale = (FIGHTER_K,) * 3
            for ob in [c] + list(c.children_recursive):
                ob.hide_render = False
            s = 1 if i % 2 else -1
            p0 = fp + Vector((rnd.uniform(-6, 6), s * 6, rnd.uniform(-2, 2)))
            p1 = p0 + Vector((15, s * 6, rnd.uniform(-3, 3)))
            p2 = p1 + Vector((140 + rnd.uniform(-10, 10), rnd.uniform(-40, 40) - 30, rnd.uniform(-15, 15)))
            p3 = p2 + Vector((330, rnd.uniform(-90, 50), rnd.uniform(-30, 30)))
            t0 = 11.0 + 0.08 * i
            key_loc(c, [(fr(t0), p0), (fr(t0 + 0.4), p1), (fr(t0 + 1.6), p2), (fr(t0 + 4.0), p3)], 'BEZIER')
            show(c, fr(t0), fr(t0 + 4.0))
            wings = [ch for ch in c.children_recursive if ch.name.startswith(wname)]
            for w in wings:
                w.rotation_mode = 'XYZ'
                key_rot(w, [(fr(t0), (0, 0, 0)), (fr(t0 + 4.0), (360 * 6, 0, 0))], 'LINEAR')
            self.fighters.append(c)

    def arcadian_fleet(self):
        o = self.obj
        with AF.gold_palette():
            cres, ccore = AF.crescent_mothership_v2()
            shell, score = AF.shell_mothership_v2()
            lens, lcore = AF.lens_mothership_v2()
            acv, _ = AF.arcadian_corvette()
            sting, _ = AF.stingray_fighter()
        cres.scale = (2.6,) * 3
        shell.scale = (1.4,) * 3
        lens.scale = (1.8,) * 3
        o.update(crescent=cres, shell=shell, lens=lens, acorv0=acv, sting=sting)
        self.shell_tip_local = max((v.co for v in shell.data.vertices), key=lambda c: c.x).copy()
        for i in (1, 2):
            o[f'acorv{i}'] = copy_tree(acv, f'ACorvette{i}')
        Y = 180.0
        # crescent: horns poke through the rift at 0:05, slides out 0:06-0:08, holds
        cx = RIFT_AT.x
        key_loc(cres, [(1, Vector((cx + 160, 0, RIFT_AT.z))), (fr(4.6), Vector((cx + 85, 0, RIFT_AT.z))),
                       (fr(5.6), Vector((cx + 45, 0, RIFT_AT.z - 3))), (fr(6.0), Vector((cx + 10, 0, RIFT_AT.z - 8))),
                       (fr(8.5), Vector((cx - 170, 5, RIFT_AT.z - 40))), (fr(12.0), Vector((390, 30, 70))),
                       (NF, Vector((300, 40, 60)))], 'BEZIER')
        key_rot(cres, [(1, (0, 0, Y)), (fr(9.0), (0, 0, Y)), (fr(22.0), (0, 0, Y - 4)), (fr(23.0), (0, 0, Y + 6)),
                       (NF, (0, 0, Y + 8))])
        # shell (hooked) ship: 0:08 out of the rift, holds at the right of the battle, swings its hook
        sh_hold = Vector((300, -70, 10))
        key_loc(shell, [(1, Vector((cx + 200, -40, RIFT_AT.z))), (fr(7.6), Vector((cx + 60, -40, RIFT_AT.z - 10))),
                        (fr(9.5), Vector((cx - 140, -55, 60))), (fr(13.0), sh_hold),
                        (fr(21.0), sh_hold + Vector((-6, 0, 0)))], 'BEZIER')
        self.shell_hold = sh_hold
        key_rot(shell, [(1, (0, 0, Y)), (fr(13.0), (0, 0, Y)), (fr(13.9), (0, 0, Y - 9)), (fr(17.0), (0, 0, Y - 9))])
        # lens ship
        key_loc(lens, [(1, Vector((cx + 220, 60, RIFT_AT.z + 30))), (fr(7.9), Vector((cx + 60, 60, RIFT_AT.z + 20))),
                       (fr(10.0), Vector((cx - 160, 90, 110))), (fr(14.0), Vector((420, 150, 90))),
                       (NF, Vector((360, 150, 85)))], 'BEZIER')
        key_rot(lens, [(1, (0, 0, Y)), (NF, (0, 0, Y))])
        for i in range(3):
            a = o[f'acorv{i}']
            p_hold = Vector((330 - 15 * i, (-1) ** i * (40 + 50 * i), 30 - 12 * i))
            key_loc(a, [(1, Vector((cx + 200, 0, RIFT_AT.z))), (fr(8.2 + 0.2 * i), Vector((cx + 30, 0, RIFT_AT.z - 10))),
                        (fr(10.5 + 0.2 * i), Vector((cx - 160, p_hold.y * 0.6, 80))), (fr(14.0), p_hold),
                        (NF, p_hold - Vector((30, 0, 0)))], 'BEZIER')
            key_rot(a, [(1, (0, 0, Y)), (NF, (0, 0, Y))])
        # stingray flock: pours out around the big ships at 0:08.3
        sting.location = (0, 0, -9999)
        sting.hide_render = True
        self.stingrays = []
        rnd = random.Random(33)
        for i in range(36):
            s = copy_tree(sting, f'Stingray{i}')
            s.hide_render = False
            s.scale = (FIGHTER_K,) * 3
            t0 = 8.3 + rnd.uniform(0, 1.2)
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(20, 110)
            p0 = RIFT_AT + Vector((10, math.cos(a) * r, math.sin(a) * r * 0.6))
            p1 = p0 + Vector((-150 - rnd.uniform(0, 60), rnd.uniform(-60, 60), rnd.uniform(-30, 20)))
            p2 = Vector((250 + rnd.uniform(-40, 60), rnd.uniform(-150, 150), rnd.uniform(-30, 60)))
            p3 = p2 + Vector((rnd.uniform(-160, -60), rnd.uniform(-60, 60), rnd.uniform(-20, 20)))
            key_loc(s, [(fr(t0), p0), (fr(t0 + 1.5), p1), (fr(t0 + 5.0), p2), (fr(28.0), p3)], 'BEZIER')
            key_rot(s, [(fr(t0), (0, 0, Y)), (fr(28.0), (rnd.uniform(-30, 30), 0, Y + rnd.uniform(-40, 40)))])
            show(s, fr(t0), fr(28.0))
            self.stingrays.append(s)
        for k in ('crescent', 'shell', 'lens'):
            show(o[k], fr(4.0) if k == 'crescent' else fr(7.0), NF)
        # gold honeycomb shields flicker on round the big ships at 0:08-0:09
        self.gsh = {}
        for k, f_on in (('crescent', fr(8.4)), ('shell', fr(8.7)), ('lens', fr(9.0))):
            ob = o[k]
            dx, dy, dz = (v / ob.scale.x for v in ob.dimensions)
            size = (dx * 0.62, dy * 0.66 + 2, dz * 0.7 + 2)
            cen = sum((Vector(b) for b in ob.bound_box), Vector()) / 8
            hitp = (size[0] * 0.9, -size[1] * 0.3, size[2] * 0.2)
            sh = NP.shield_dome(size=size, hit=hitp, name=f'GShield_{k}')
            sh.scale = size
            sh.parent = ob
            sh.location = cen
            m = sh.data.materials[0]
            add_fade(m, 'vis', 0.0)
            key_node(m, 'vis', [(1, 0.0), (f_on - 1, 0.0), (f_on, 0.7), (f_on + 1, 0.1), (f_on + 2, 0.8),
                                (f_on + 4, 0.45)], 'CONSTANT')
            self.gsh[k] = sh

    # -------------------------------------------------------------- 5A: the beam on the flagship
    dread_hit_u = (0.9, -0.2, 0.05)
    F_GLOW, F_BEAM, F_CUT, F_BREAK, F_EXIT, F_OFF = 312, 336, 348, 360, 372, 384

    def beam_geom(self):
        """Where the Arcadian beam starts (hook tip at the moment of firing), where it meets the
        dreadnought's shield, enters and leaves the hull. Fills self.dread_hit_u (shield-local)."""
        o = self.obj
        if 'shell' not in o:
            return
        sc = bpy.context.scene
        sc.frame_set(self.F_BEAM)
        dread, shell = o['dread'], o['shell']
        src = shell.matrix_world @ self.shell_tip_local
        cen_l = sum((Vector(b) for b in dread.bound_box), Vector()) / 8
        tgt = dread.matrix_world @ (cen_l + Vector((2.0, 0, 0.3)))
        d = (tgt - src).normalized()
        dims = Vector(dread.dimensions) / dread.scale.x
        size_l = Vector((dims.x * 0.62, dims.y * 0.75 + 2.5, dims.z * 1.0 + 2.5))
        inv = dread.matrix_world.inverted()
        src_l = inv @ src
        d_l = (inv.to_3x3() @ d).normalized()
        hit_l, u = BP.ellipsoid_hit(cen_l, size_l, src_l, d_l)
        ok, entry, nrm, _ = dread.ray_cast(src_l, d_l)
        far_l = inv @ (tgt + d * 400)
        ok2, exit_, _, _ = dread.ray_cast(far_l, -d_l)
        W = dread.matrix_world
        self.beam = dict(src=src, d=d, shield_w=W @ hit_l, entry_w=W @ entry if ok else tgt,
                         exit_w=W @ exit_ if ok2 else tgt, entry_l=entry if ok else inv @ tgt,
                         exit_l=exit_ if ok2 else inv @ tgt, nrm_l=nrm, d_l=d_l)
        self.dread_hit_u = tuple(u)
        sc.frame_set(1)

    def world_at(self, obj, local, f):
        bpy.context.scene.frame_set(f)
        return obj.matrix_world @ Vector(local)

    def flagship_beam(self):
        """0:13 glow at the hook tip, 0:14 beam on (crosses in 3 frames), 1 s on the shield, shield
        breaks at 0:15, 0.5 s on the hull, out the far side at 0:15.5, off at 0:16, then the
        flagship goes dark section by section and rolls over burning."""
        o, b = self.obj, self.beam
        dread, shell = o['dread'], o['shell']
        G = (1.0, 0.7, 0.25)
        # charge glow at the hook tip (parented, so it follows the hook)
        glow = C.uv_sphere('HookGlow', 1.0, seg=(24, 12), mat=BP._halo_mat('HookGlowM', G, 9.0))
        glow.parent = shell
        glow.location = self.shell_tip_local
        key_scale(glow, [(self.F_GLOW, 0.3), (self.F_BEAM, 5.0), (self.F_OFF, 4.0), (self.F_OFF + 6, 0.1)])
        show(glow, self.F_GLOW, self.F_OFF + 6)
        glow.visible_shadow = False
        tipw = self.world_at(shell, self.shell_tip_local, self.F_GLOW + 12)
        back = self.world_at(shell, self.shell_tip_local + Vector((-25, 0, 6)), self.F_GLOW + 12)
        flicker_lightning([(back, tipw), (back + Vector((0, 8, -4)), tipw)], 41, self.F_GLOW + 4, self.F_OFF,
                          width=0.9, name='HookBolt', zone_col=(1.0, 0.75, 0.3))
        # the beam
        src, d = b['src'], b['d']
        Ls = (b['shield_w'] - src).length
        Le = (b['entry_w'] - src).length
        Lx = (b['exit_w'] - src).length
        bkeys = [(self.F_BEAM, 0.5, 1.0), (self.F_BEAM + 3, Ls, 1.0), (self.F_BREAK - 1, Ls, 1.05), (self.F_BREAK, Ls + 3, 1.1),
                 (self.F_EXIT - 1, Le + 2, 1.1), (self.F_EXIT, Lx, 1.15), (self.F_EXIT + 2, Lx + 420, 1.15),
                 (self.F_OFF, Lx + 420, 1.0), (self.F_OFF + 2, Lx + 420, 0.0)]
        bc = beam(src, d, 'GoldBeam', (1.0, 0.5, 0.08), (1.0, 0.9, 0.6), 0.9, bkeys, glow=2.6)
        bc.data.materials[0] = flow_emit('GoldBeamFlow', (1.0, 0.78, 0.4), 9.0)
        # v2: twisting energy ribbons, crackle along the beam, splash + sparks where it touches
        beam_twist(src, d, 'GoldTwist', (1.0, 0.55, 0.12), [(f, L) for f, L, _ in bkeys[:-1]] + [(self.F_OFF + 2, 0.0)],
                   self.F_BEAM, self.F_OFF + 2, radius=1.1, pitch=9.0, width=0.09)
        rnd_c = random.Random(43)

        def crackle(a, bb, n_, f0, f1, seed):
            pairs = []
            for i in range(n_):
                t0, t1 = i / n_, (i + 1) / n_
                off = lambda: Vector((rnd_c.uniform(-1, 1), rnd_c.uniform(-1, 1), rnd_c.uniform(-1, 1))) * 0.45
                pairs.append((a.lerp(bb, t0) + off(), a.lerp(bb, t1) + off()))
            flicker_lightning(pairs, seed, f0, f1, every=2, width=0.08, name=f'BeamArc{seed}',
                              zone_col=(1.0, 0.6, 0.15), strength=7.0)
        nrm_w = (self.world_at(dread, b['entry_l'] + b['nrm_l'], self.F_BREAK) - b['entry_w']).normalized()
        impact_flare(b['shield_w'] - d * 0.5, d, self.F_BEAM + 3, self.F_BREAK, (1.0, 0.6, 0.2), 4.0, 'ShieldSplash')
        impact_flare(b['entry_w'] - d * 0.3, d, self.F_BREAK + 1, self.F_EXIT + 4, (1.0, 0.5, 0.15), 3.5, 'HullSplash')
        spark_stream(b['shield_w'] - d * 1.0, self.F_BEAM + 3, self.F_BREAK, (1.0, 0.75, 0.3), -d * 0.9, 80,
                     size=0.3, speed=55)
        spark_stream(b['entry_w'] - d * 0.5, self.F_BREAK + 1, self.F_OFF, (1.0, 0.5, 0.12), nrm_w * 1.3 - d * 0.4,
                     81, size=0.28, speed=50)
        spark_stream(b['exit_w'] + d * 1.0, self.F_EXIT, self.F_OFF + 6, (1.0, 0.55, 0.15), d * 1.6, 82,
                     n=9, size=0.35, speed=80, life=0.9)
        torn_hole(dread, b['entry_l'], b['nrm_l'], 'EntryHole', self.F_BREAK + 3, self.F_EXIT + 2,
                  r0=0.6, r1=1.5, lift=0.5, seed=5)
        torn_hole(dread, b['exit_l'], b['d_l'], 'ExitHole', self.F_EXIT, self.F_EXIT + 4,
                  r0=0.8, r1=2.2, lift=1.2, petals=11, seed=6)
        L = bpy.data.objects.new('BeamLight', bpy.data.lights.new('BeamLight', 'POINT'))
        link(L)
        L.location = b['shield_w'] - d * 6
        L.data.color = G
        L.data.shadow_soft_size = 4
        for f, e in [(1, 0), (self.F_BEAM, 0), (self.F_BEAM + 3, 6e5), (self.F_OFF, 6e5), (self.F_OFF + 2, 0)]:
            L.data.energy = e
            L.data.keyframe_insert('energy', frame=f)
        lin(L.data)
        # shield (David 21:26): the beam hits and the shield warbles, faster and faster; it pops open
        # where the beam punches through; when the ship loses power the whole shield peels back from
        # the hole and pulls away from the hull, gone. Nothing of it is left while the ship burns.
        sh = self.tsh['dread']
        sm = sh.data.materials[0]
        key_node(sm, 'hitk', [(1, 0.0), (self.F_BEAM + 2, 0.0), (self.F_BEAM + 4, 0.7), (self.F_BREAK - 1, 1.0),
                              (self.F_BREAK + 2, 1.0), (self.F_OFF + 2, 0.6)])
        rk, f, n_ = [(1, 0.0)], float(self.F_BEAM + 3), 0
        while f < self.F_BREAK - 1:                    # ripples racing outward, each one quicker
            u = (f - self.F_BEAM) / float(self.F_BREAK - self.F_BEAM)
            per = max(2.0, 8.0 - 6.5 * u)
            rk += [(int(round(f)), 0.03), (int(round(f + per)) - 1, 0.45 + 0.2 * u)]
            f += per
        rk += [(self.F_BREAK, 0.0)]
        key_node(sm, 'ring', rk)
        key_node(sm, 'hole', [(1, 0.0), (self.F_BREAK - 1, 0.0), (self.F_BREAK + 1, 0.16), (self.F_BREAK + 4, 0.24),
                              (self.F_OFF, 0.34), (self.F_OFF + 4, 0.8), (self.F_OFF + 9, 2.2)])
        # brightens as it strains, then fades as it peels away (vis keys are stepped, so key each frame)
        key_node(sm, 'vis', [(self.F_BEAM + 6 + 3 * k, min(1.0, 0.7 + 0.06 * k)) for k in range(6)]
                 + [(self.F_OFF + 2 + k, 1.0 * (1 - k / 7.0)) for k in range(8)], 'CONSTANT')
        # warble: the field wobbles under the beam, faster and harder until it gives
        s0 = Vector(sh.scale)
        ph = 0.0
        for f in range(self.F_BEAM, self.F_OFF + 10):
            if f <= self.F_BREAK:
                u = (f - self.F_BEAM) / float(self.F_BREAK - self.F_BEAM)
                amp, w = 0.01 + 0.05 * u * u, 0.35 + 2.2 * u
            else:
                amp, w = 0.02, 1.5
            ph += w
            pull = 0.0 if f <= self.F_OFF else 0.22 * ((f - self.F_OFF) / 9.0) ** 1.5   # pulls away, gone
            sh.scale = (s0.x * (1 + amp * math.sin(ph) + pull), s0.y * (1 - amp * math.sin(ph + 1.7) + pull),
                        s0.z * (1 + amp * math.sin(ph + 3.1) + pull))
            sh.keyframe_insert('scale', frame=f)
        show(sh, 1, self.F_OFF + 9, tree=False)
        shards(b['shield_w'], self.F_BREAK, 30, (0.35, 0.7, 1.0), 1.6, 70, seed=60, life=1.4, drift=-d * 0.6)
        blue_boom(b['shield_w'], self.F_BREAK, 4.0, life=0.5, light=2e5)
        # hull: white-hot spot (0:15-0:15.5), molten hole, spray out of the far side (0:15.5)
        hot = C.uv_sphere('HullHot', 1.0, seg=(20, 10), mat=emit('HullHotM', (1.0, 0.85, 0.6), 30.0))
        hot.parent = dread
        hot.location = b['entry_l']
        key_scale(hot, [(self.F_BREAK, 0.2), (self.F_EXIT, 1.6), (self.F_EXIT + 8, 0.3)])
        show(hot, self.F_BREAK, self.F_EXIT + 8)
        hm = hot.data.materials[0]
        em = next(n for n in hm.node_tree.nodes if n.type == 'EMISSION')
        for f, col, st in [(self.F_BREAK, (1, 0.9, 0.7), 30), (self.F_OFF, (1, 0.7, 0.35), 25), (self.F_OFF + 30, (1, 0.35, 0.05), 8),
                           (NF, (0.9, 0.2, 0.03), 4)]:
            em.inputs[0].default_value = (*col, 1)
            em.inputs[1].default_value = st
            em.inputs[0].keyframe_insert('default_value', frame=f)
            em.inputs[1].keyframe_insert('default_value', frame=f)
        hot.visible_shadow = False
        boom(b['exit_w'] + d * 3, self.F_EXIT, 6.0, life=0.9, light=3e5, follow=d * 10)
        spark_stream(b['exit_w'] + d * 2, self.F_EXIT, self.F_EXIT + 1, (1.0, 0.55, 0.15), d * 1.4, 61,
                     n=50, size=0.5, speed=90, life=1.2, strength=14.0)
        # lights go out section by section (each neon material), then it rolls over, burning
        neon = [sl.material for sl in dread.material_slots if sl.material and sl.material.name.endswith('_neon')]
        for i, m in enumerate(neon):
            e = [n for n in m.node_tree.nodes if n.type == 'EMISSION'][-1]
            f0 = self.F_OFF + 3 + i * 5
            for f, c in [(1, T.NEON), (f0, T.NEON), (f0 + 1, (0.8, 0.9, 1.0)), (f0 + 2, T.NEON), (f0 + 4, (0, 0, 0))]:
                e.inputs['Color'].default_value = (*c, 1)
                e.inputs['Color'].keyframe_insert('default_value', frame=f)
        key_rot(dread, [(1, (0, 0, DREAD_YAW)), (self.F_OFF, (0, 0, DREAD_YAW)), (NF, (95, 0, DREAD_YAW - 10))])
        rnd = random.Random(62)
        for i in range(7):
            f = self.F_OFF + 2 + i * 4
            lp = Vector((rnd.uniform(-16, 16), rnd.uniform(-4, 4), rnd.uniform(0, 3)))
            boom(self.world_at(dread, lp, f), f, rnd.uniform(4, 8), life=1.4, light=6e4 if i % 3 == 0 else 0,
                 follow=(0, 0, 2))
        # long-lived fires on the hull for the rest of the minute
        fm = gas_fireball_mat('HullFire', (1.0, 0.45, 0.06), (0.35, 0.03, 0.005))
        C.key_value(fm, 'S', 1, 3.0)
        C.key_value(fm, 'V', 1, 1.0)
        for i, lp in enumerate([b['entry_l'], b['exit_l'], Vector((-8, 2, 3)), Vector((9, -3, 2))]):
            fo = C.uv_sphere(f'HullFire{i}', 1.0, seg=(16, 10), mat=fm, scale=(2.5, 2.5, 2.5))
            fo.parent = dread
            fo.location = lp
            key_rot(fo, [(self.F_OFF, (0, 0, 0)), (NF, (300 + i * 40, 200, 500))], 'LINEAR')
            show(fo, self.F_OFF + 4 * i, NF)
            fo.visible_shadow = False
        bpy.context.scene.frame_set(1)

    def barrage(self):
        """0:17 battleship spins 1.25 turns and stops hard, cannons on the shell ship; 0:18 charge
        ribbons round cannons 1-2-3; 10 comets every 6 frames from frame 444, 12-frame flights:
        hits 1-4 on the gold shield, 5 shatters it, 6-7 break hull pieces (hook tip first),
        8 punches inside, 9-10 rip the ship into three."""
        o = self.obj
        bs, shell = o['bship'], o['shell']
        F0, F1 = 409, 432
        key_rot(bs, [(1, (0, 0, 0)), (F0, (0, 0, 0)), (F0 + 3, (0, 0, 20)), (F1 - 4, (0, 0, 459)), (F1, (0, 0, 450)),
                     (NF, (0, 0, 452))])
        # thruster bursts while spinning
        tm = emit('ThrusterM', (0.5, 0.8, 1.0), 25.0)
        rnd = random.Random(70)
        for i in range(10):
            th = C.uv_sphere(f'Thruster{i}', 1.0, seg=(10, 6), mat=tm, scale=(1.4, 0.5, 0.5))
            th.parent = bs
            th.location = (rnd.uniform(-22, 22), (-1) ** i * 10.5, rnd.uniform(-3, 3))
            th.visible_shadow = False
            for f in range(1, NF, 1):
                pass
            vis = [(1, True)]
            for f in range(F0 + i % 3, F1, 3):
                vis += [(f, False), (f + 1, True)]
            for f, h in vis:
                th.hide_render = h
                th.keyframe_insert('hide_render', frame=f)
            C.set_interp(th, 'CONSTANT')
        # twin-X fighters ripping past the camera while it turns
        bw = self.world_at(bs, (0, 0, 0), F0)
        for i in range(4):
            c = copy_tree(self.twinx_src, f'PassX{i}')
            c.scale = (FIGHTER_K,) * 3
            for ob in [c] + list(c.children_recursive):
                ob.hide_render = False
            t0 = F0 + 2 + i * 5
            p0 = bw + Vector((-60, -48 + i * 4, 10 - i * 3))
            p1 = bw + Vector((90, -30 + i * 6, -4 + i * 2))
            key_loc(c, [(t0, p0), (t0 + 14, p1)], 'LINEAR')
            show(c, t0, t0 + 14)
        # charge ribbons: helix round each barrel near the muzzle, 4 frames each
        base._faction('terran')
        rib_m = emit('RibbonM', (0.45, 0.8, 1.0), 22.0)
        for ci, mz in enumerate(self.muzzles):
            pts = []
            for k in range(60):
                t = k / 59
                a = t * 4 * 2 * math.pi
                pts.append((mz.x + 2.2 * math.cos(a), mz.y + 7.0 * (1 - t), mz.z + 2.2 * math.sin(a)))
            r = F.sweep(pts, [(0.18, 0.18)] * 60, 'glow', sides=4)
            ro = base._join([r], f'ChargeRibbon{ci}')
            ro.data.materials.clear()
            ro.data.materials.append(rib_m)
            ro.parent = bs
            ro.visible_shadow = False
            show(ro, 433 + 4 * ci, 433 + 4 * ci + 5)
        # comets
        sb = self.gsh['shell']
        sm = sb.data.materials[0]
        cen_l = sum((Vector(v) for v in shell.bound_box), Vector()) / 8
        rnd = random.Random(71)
        hit_frames = []
        self.comet_targets = []
        for k in range(10):
            ff = 444 + 6 * k
            fh = ff + 12
            ci = k % 3
            src = self.world_at(bs, self.muzzles[ci], ff)
            fire = (self.world_at(bs, self.muzzles[ci] + Vector((0, -1, 0)), ff) - src).normalized()
            if k < 5:     # on the shield skin facing the battleship
                cw = self.world_at(shell, cen_l, fh)
                toward = (src - cw).normalized()
                tgt = cw + toward * (sb.scale.x * shell.scale.x * 0.97) + Vector((0, rnd.uniform(-8, 8), rnd.uniform(-6, 6)))
            elif k == 5:
                tgt = self.world_at(shell, self.shell_tip_local, fh)
            elif k == 6:
                tgt = self.world_at(shell, cen_l + Vector((8, -6, 10)), fh)
            else:
                tgt = self.world_at(shell, cen_l + Vector((-12 + 10 * (k - 7), rnd.uniform(-4, 4), rnd.uniform(-3, 3))), fh)
            cm = BP.comet(f'Comet{k}', scale=2.6, seed=k)
            cm.rotation_mode = 'QUATERNION'
            cm.rotation_quaternion = aim_quat(tgt - src)
            key_loc(cm, [(ff, src + fire * 3), (fh, tgt)], 'LINEAR')
            show(cm, ff, fh)
            fl = T.muzzle_flash(f'MFlash{k}', scale=2.2, bolt=False)
            fl.location = src
            fl.rotation_mode = 'QUATERNION'
            fl.rotation_quaternion = aim_quat(fire)
            show(fl, ff, ff + 3)
            blue_boom(tgt, fh, 9.0 if k < 5 else 12.0, life=0.9, light=2.5e5)
            hit_frames.append(fh)
            self.comet_targets.append((ff, fh, src, tgt))
        # shield flares on each hit, shatters on hit 5 (frame 480)
        vk = [(1, 0.0)]
        fk = sm.node_tree.nodes['vis']
        vk = []
        for fh in hit_frames[:4]:
            vk += [(fh - 1, 0.45), (fh, 1.0), (fh + 3, 0.6)]
        vk += [(479, 0.6), (480, 1.0), (481, 0.0)]
        key_node(sm, 'vis', vk, 'LINEAR')
        cw = self.world_at(shell, cen_l, 480)
        shards(self.comet_targets[4][3], 480, 70, (1.0, 0.7, 0.25), 2.4, 60, seed=72, life=1.6, kind='hex')
        shards(cw, 480, 50, (1.0, 0.75, 0.3), 2.0, 45, seed=73, life=1.8, kind='hex')
        # hull pieces off (486 hook tip, 492 a dorsal chunk), then rip into three (504/510)
        tip = self.shell_tip_local
        xs = [v.co.x for v in shell.data.vertices]
        x0, x1 = min(xs), max(xs)

        def grp(c):
            if c.x > tip.x - 9:
                return 0
            if c.z > cen_l.z + 9 and abs(c.x - (cen_l.x + 8)) < 9:
                return 1
            t = (c.x - x0) / (x1 - x0)
            return 2 if t < 0.36 else (3 if t < 0.66 else 4)
        parts = split_mesh(shell, grp, names=['ShellHook', 'ShellChunk', 'ShellAft', 'ShellMid', 'ShellFore'])
        for p_ in parts:
            p_.parent = shell
            p_.matrix_parent_inverse.identity()
            p_.location = (0, 0, 0)
            p_.rotation_euler = (0, 0, 0)
            p_.scale = (1, 1, 1)
        shell.keyframe_insert('hide_render', frame=485)
        shell.hide_render = True
        shell.keyframe_insert('hide_render', frame=486)
        shell.hide_render = True
        shell.keyframe_insert('hide_render', frame=NF)
        C.set_interp(shell, 'CONSTANT')
        bf = {0: 486, 1: 492, 2: 510, 3: 510, 4: 510}
        drift = {0: (14, 4, 6), 1: (2, -5, 14), 2: (-10, -6, -4), 3: (2, 9, -8), 4: (12, -4, 5)}
        spin = {0: (200, 90, 300), 1: (120, 300, 60), 2: (-30, 20, -25), 3: (35, -25, 15), 4: (-20, 40, 30)}
        for i, p_ in enumerate(parts):
            show(p_, 486, NF)
            v = Vector(drift[i])
            key_loc(p_, [(1, (0, 0, 0)), (bf[i], (0, 0, 0)), (bf[i] + 24, v * 0.6), (NF, v * (NF - bf[i]) / 24 * 0.45)], 'LINEAR')
            key_rot(p_, [(1, (0, 0, 0)), (bf[i], (0, 0, 0)), (NF, spin[i])], 'LINEAR')
        for f_, off, sz, lt in [(498, (0, 0, 0), 14.0, 4e5), (504, (-10, 0, 0), 22.0, 6e5), (510, (0, 0, 0), 36.0, 1.2e6)]:
            pw = self.world_at(shell, cen_l + Vector(off), f_)
            blue_boom(pw, f_, sz * 0.55, life=0.35, light=lt * 0.5)        # energy flash
            gold_boom(pw, f_ + 1, sz, life=1.4 + sz / 40, light=lt * 0.5)   # the ship's own fire
        shards(self.world_at(shell, cen_l, 510), 510, 160, (1.0, 0.7, 0.3), 0.9, 80, seed=74, life=2.4, kind='hex',
               strength=12.0)
        # 0:22 the battleship's cannons glow and vent; the Crescent gathers lightning between its horns
        vm = emit('VentM', (0.5, 0.75, 1.0), 12.0)
        for ci, mz in enumerate(self.muzzles):
            g = C.uv_sphere(f'Vent{ci}', 1.0, seg=(16, 8), mat=BP._halo_mat(f'VentHalo{ci}', (0.4, 0.7, 1.0), 6.0))
            g.parent = bs
            g.location = mz + Vector((0, -1.5, 0))
            key_scale(g, [(500, 0.1), (512, 3.5), (552, 2.0), (600, 0.1)])
            show(g, 500, 600)
            g.visible_shadow = False
        cres = o['crescent']
        vs = [v.co for v in cres.data.vertices]
        hl = max((v for v in vs if v.y > 3), key=lambda v: v.x)
        hr = max((v for v in vs if v.y < -3), key=lambda v: v.x)
        fcen = 540
        pw = [(self.world_at(cres, hl, fcen), self.world_at(cres, hr, fcen)),
              (self.world_at(cres, hl + Vector((-6, -2, 1)), fcen), self.world_at(cres, hr + Vector((-6, 2, -1)), fcen))]
        flicker_lightning(pw, 75, 530, 600, width=2.4, name='HornBolt', zone_col=(1.0, 0.75, 0.3))
        bpy.context.scene.frame_set(1)

    def dogfight(self):
        import dogfight
        dogfight.Dogfight(self)

    def squid_hunt(self):
        import squid
        squid.SquidHunt(self)

    def camera_for(self, sid):
        if sid == '08a':
            return self.drop_data.camera(sid)
        if sid.startswith('07'):
            return self.squid.camera(sid)
        if sid == '06':
            return self.dogfight_data.camera(sid)
        return None

    def drop(self):
        import drop
        drop.Drop(self)

    def ending(self):
        pass
