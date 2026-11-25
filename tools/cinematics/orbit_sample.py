"""Sample cinematic shot: Terran and Kesh fleets fighting in orbit over Vesper, the rift behind.

    /home/user/artenv/bin/python tools/cinematics/orbit_sample.py --out=DIR [--frames=A-B] [--still=N]
          [--res=1280x576] [--samples=24]

Writes PNG frames to DIR/frames (or one still). Bloom and encoding are done by post.py.
Units: Blender units; a fighter is 1.4 long, the Terran dreadnought ~38. Front is +X.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector, Euler, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ships  # noqa: E402
import forge as F  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
FPS = 24
SECONDS = 8.0
NF = int(FPS * SECONDS)

args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
OUT = args.get('out', '/tmp/orbit')
RES = [int(v) for v in args.get('res', '1280x576').split('x')]
SAMPLES = int(args.get('samples', 24))
rnd = random.Random(7)


def T(sec):
    return 1 + sec * FPS


# ------------------------------------------------------------------ materials
def emit_mat(name, col, strength, alpha_fade=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value = (*col, 1)
    em.inputs[1].default_value = strength
    if alpha_fade:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = 1.0
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
    return m


def fireball_mat(name, hot=(1.0, 0.45, 0.06), cool=(0.35, 0.03, 0.005)):
    """Noisy fireball: emission strength (node 'S') and visibility (node 'V') get keyframed."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 4.0
    noise.inputs['Detail'].default_value = 6.0
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs[0].default_value = 0.5
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(noise.outputs['Fac'], mul.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs[1].default_value = 0.3
    mr.inputs[2].default_value = 0.75
    nt.links.new(noise.outputs['Fac'], mr.inputs[0])
    nt.links.new(mr.outputs[0], mul.inputs[0])
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.2
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])
    nt.links.new(inv.outputs[0], mul.inputs[1])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (*cool, 1)
    ramp.color_ramp.elements[1].position = 0.65
    ramp.color_ramp.elements[1].color = (*hot, 1)
    nt.links.new(mul.outputs[0], ramp.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(ramp.outputs[0], em.inputs[0])
    s = nt.nodes.new('ShaderNodeValue')
    s.name = 'S'
    smul = nt.nodes.new('ShaderNodeMath')
    smul.operation = 'MULTIPLY'
    nt.links.new(mul.outputs[0], smul.inputs[0])
    nt.links.new(s.outputs[0], smul.inputs[1])
    nt.links.new(smul.outputs[0], em.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    v = nt.nodes.new('ShaderNodeValue')
    v.name = 'V'
    # visible where the noise is above (1 - V): the ball breaks up as it fades
    thr = nt.nodes.new('ShaderNodeMath')
    thr.operation = 'GREATER_THAN'
    one_minus = nt.nodes.new('ShaderNodeMath')
    one_minus.operation = 'SUBTRACT'
    one_minus.inputs[0].default_value = 1.0
    nt.links.new(v.outputs[0], one_minus.inputs[1])
    nt.links.new(noise.outputs['Fac'], thr.inputs[0])
    nt.links.new(one_minus.outputs[0], thr.inputs[1])
    nt.links.new(thr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def key_value(mat, node, frame, value, interp='LINEAR'):
    nd = mat.node_tree.nodes[node]
    nd.outputs[0].default_value = value
    nd.outputs[0].keyframe_insert('default_value', frame=frame)


def set_interp(idblock, kind='LINEAR'):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:   # Blender 4.4+: layered actions
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT' if fc.data_path == 'hide_render' else kind


def mesh_obj(name, verts_fn):
    me = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def uv_sphere(name, r=1.0, seg=(16, 10), mat=None, scale=(1, 1, 1)):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg[0], v_segments=seg[1], radius=r)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = scale
    if mat:
        me.materials.append(mat)
    return obj


def show_between(obj, f0, f1):
    """Visible for frames f0..f1 only."""
    for f, h in [(1, True), (f0, False), (f1, True)]:
        if f < 1:
            continue
        obj.hide_render = h
        obj.keyframe_insert('hide_render', frame=f)


# ------------------------------------------------------------------ environment
def world():
    w = bpy.data.worlds.new('Space')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # stars: tiny voronoi cells, random brightness
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 260.0
    nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
    dist = nt.nodes.new('ShaderNodeMath')
    dist.operation = 'LESS_THAN'
    dist.inputs[1].default_value = 0.075
    nt.links.new(vor.outputs['Distance'], dist.inputs[0])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(vor.outputs['Color'], sep.inputs[0])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 6.0
    nt.links.new(sep.outputs[0], pw.inputs[0])
    star = nt.nodes.new('ShaderNodeMath')
    star.operation = 'MULTIPLY'
    nt.links.new(dist.outputs[0], star.inputs[0])
    nt.links.new(pw.outputs[0], star.inputs[1])
    star2 = nt.nodes.new('ShaderNodeMath')
    star2.operation = 'MULTIPLY'
    star2.inputs[1].default_value = 6.0
    nt.links.new(star.outputs[0], star2.inputs[0])
    # faint nebula band
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 1.6
    nz.inputs['Detail'].default_value = 8.0
    nt.links.new(tc.outputs['Generated'], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.012, 0.004, 0.025, 1)
    nt.links.new(nz.outputs['Fac'], ramp.inputs[0])
    add = nt.nodes.new('ShaderNodeMix')
    add.data_type = 'RGBA'
    add.blend_type = 'ADD'
    add.inputs[0].default_value = 1.0
    nt.links.new(ramp.outputs[0], add.inputs[6])
    nt.links.new(star2.outputs[0], add.inputs[7])
    nt.links.new(add.outputs[2], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    nt.links.new(bg.outputs[0], out.inputs[0])


def planet():
    R = 2400.0
    p = uv_sphere('Vesper', R, seg=(128, 64))
    p.location = (500, 200, -R - 140)
    m = bpy.data.materials.new('Vesper')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    land = nt.nodes.new('ShaderNodeTexNoise')
    land.inputs['Scale'].default_value = 9.0
    land.inputs['Detail'].default_value = 12.0
    land.inputs['Roughness'].default_value = 0.62
    nt.links.new(tc.outputs['Generated'], land.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.48, (0.012, 0.04, 0.08, 1)        # sea
    els[1].position, els[1].color = 0.72, (0.32, 0.24, 0.15, 1)         # high desert
    e = els.new(0.52)
    e.color = (0.12, 0.13, 0.06, 1)                                     # lowland
    e = els.new(0.5)
    e.color = (0.03, 0.08, 0.1, 1)                                      # shore
    nt.links.new(land.outputs['Fac'], ramp.inputs[0])
    clouds = nt.nodes.new('ShaderNodeTexNoise')
    clouds.inputs['Scale'].default_value = 22.0
    clouds.inputs['Detail'].default_value = 10.0
    mapn = nt.nodes.new('ShaderNodeMapping')
    mapn.inputs['Scale'].default_value = (1.0, 1.6, 1.0)
    nt.links.new(tc.outputs['Generated'], mapn.inputs['Vector'])
    nt.links.new(mapn.outputs[0], clouds.inputs['Vector'])
    cr = nt.nodes.new('ShaderNodeMapRange')
    cr.inputs[1].default_value = 0.52
    cr.inputs[2].default_value = 0.68
    nt.links.new(clouds.outputs['Fac'], cr.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(cr.outputs[0], mix.inputs[0])
    nt.links.new(ramp.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (0.5, 0.52, 0.55, 1)
    nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.85
    p.data.materials.append(m)
    # atmosphere: rim glow shell
    a = uv_sphere('Atmosphere', R * 1.012, seg=(128, 64))
    a.location = p.location
    am = bpy.data.materials.new('Atmo')
    am.use_nodes = True
    nt = am.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs[0].default_value = 0.25
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 4.0
    nt.links.new(lw.outputs['Facing'], pw.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value = (0.25, 0.55, 1.0, 1)
    sm = nt.nodes.new('ShaderNodeMath')
    sm.operation = 'MULTIPLY'
    sm.inputs[1].default_value = 1.2
    nt.links.new(pw.outputs[0], sm.inputs[0])
    nt.links.new(sm.outputs[0], em.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    a.data.materials.append(am)
    a.visible_shadow = False
    return p


def rift():
    """Swirling tear in space behind the Kesh fleet: violet core, gold rim."""
    import bmesh
    me = bpy.data.meshes.new('Rift')
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new('Rift', me)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (1250, 520, 330)
    obj.scale = (300, 300, 300)
    obj.rotation_euler = (math.radians(90), 0, math.radians(102))   # face the camera (-X)
    m = bpy.data.materials.new('Rift')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # radius and a twist that grows toward the centre
    length = nt.nodes.new('ShaderNodeVectorMath')
    length.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], length.inputs[0])
    tw = nt.nodes.new('ShaderNodeMath')
    tw.operation = 'MULTIPLY_ADD'
    tw.inputs[1].default_value = -5.0
    tw.inputs[2].default_value = 5.0
    nt.links.new(length.outputs['Value'], tw.inputs[0])
    vr = nt.nodes.new('ShaderNodeVectorRotate')
    vr.rotation_type = 'Z_AXIS'
    nt.links.new(tc.outputs['Object'], vr.inputs['Vector'])
    nt.links.new(tw.outputs[0], vr.inputs['Angle'])
    tw.name = 'twist'
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 3.0
    nz.inputs['Detail'].default_value = 8.0
    nz.inputs['Distortion'].default_value = 0.6
    nz.name = 'noise'
    nt.links.new(vr.outputs[0], nz.inputs['Vector'])
    # radial falloff: dark eye in the middle, bright band, fade at the edge
    band = nt.nodes.new('ShaderNodeFloatCurve')
    c = band.mapping.curves[0]
    c.points[0].location = (0.0, 0.05)
    c.points[1].location = (1.0, 0.0)
    c.points.new(0.18, 0.15)
    c.points.new(0.38, 1.0)
    c.points.new(0.7, 0.35)
    band.mapping.update()
    nt.links.new(length.outputs['Value'], band.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(nz.outputs['Fac'], mul.inputs[0])
    nt.links.new(band.outputs[0], mul.inputs[1])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.05, (0.0, 0.0, 0.0, 1)
    els[1].position, els[1].color = 0.66, (1.0, 0.35, 0.03, 1)
    e = els.new(0.3)
    e.color = (0.14, 0.0, 0.5, 1)
    nt.links.new(mul.outputs[0], ramp.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[1].default_value = 1.4
    nt.links.new(ramp.outputs[0], em.inputs[0])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    me.materials.append(m)
    # slow spin
    obj.keyframe_insert('rotation_euler', frame=1)
    obj.rotation_euler[2] += 0.0
    nzw = nz.inputs['W'] if 'W' in nz.inputs else None
    if nzw is not None:
        nz.noise_dimensions = '4D'
        nzw.default_value = 0.0
        nzw.keyframe_insert('default_value', frame=1)
        nzw.default_value = 0.25
        nzw.keyframe_insert('default_value', frame=NF)
    tw.inputs[2].default_value = 5.0
    tw.inputs[2].keyframe_insert('default_value', frame=1)
    tw.inputs[2].default_value = 5.8
    tw.inputs[2].keyframe_insert('default_value', frame=NF)
    set_interp(m.node_tree)
    obj.visible_shadow = False
    return obj


# ------------------------------------------------------------------ fighters
def load_glb(path, length):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    for o in meshes:   # bake parenting into the mesh
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    keep = obj.name
    names = []
    for o in new:
        try:
            names.append(o.name)
        except ReferenceError:
            pass
    for n in names:
        if n != keep and n in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[n])
    xs = [v.co.x for v in obj.data.vertices]
    k = length / (max(xs) - min(xs))
    obj.data.transform(Matrix.Diagonal((k, k, k, 1)))
    obj.hide_render = True
    obj.location = (0, 0, -9999)
    return obj


def fly(src, name, path, t0, t1, bank=0.0):
    """Linked copy flying through the given points between t0 and t1 seconds (Catmull-like via keys)."""
    o = src.copy()
    o.name = name
    o.hide_render = False
    bpy.context.scene.collection.objects.link(o)
    n = len(path)
    for i, p in enumerate(path):
        f = T(t0 + (t1 - t0) * i / (n - 1))
        d = Vector(path[min(i + 1, n - 1)]) - Vector(path[max(i - 1, 0)])
        q = d.to_track_quat('X', 'Z')
        o.rotation_mode = 'QUATERNION'
        roll = Matrix.Rotation(bank * math.sin(i * 1.7), 4, 'X')
        o.rotation_quaternion = (q.to_matrix().to_4x4() @ roll).to_quaternion()
        o.location = p
        o.keyframe_insert('location', frame=f)
        o.keyframe_insert('rotation_quaternion', frame=f)
    set_interp(o, 'BEZIER')
    return o


# ------------------------------------------------------------------ build
def main():
    F.begin('terran')
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, NF
    world()
    planet()
    rift()

    # ---------------- Terran fleet (moving +X)
    flag, muzzles = ships.terran_dreadnought('Flagship')
    frig = ships.terran_frigate('FrigateSrc')
    dread2 = flag.copy()
    dread2.name = 'Dreadnought2'
    sc.collection.objects.link(dread2)
    terran = []   # (obj, p0, v)
    VT = Vector((3.0, 0, 0))
    terran.append((flag, Vector((0, 0, 0)), VT))
    terran.append((dread2, Vector((10, -95, -26)), VT))
    frigs = []
    for i, p in enumerate([(52, -42, -7), (40, 48, 9), (110, -20, -16), (85, 70, -4), (-20, -60, 14)]):
        o = frig if i == 0 else frig.copy()
        if i:
            o.name = f'Frigate{i}'
            sc.collection.objects.link(o)
        frigs.append(o)
        terran.append((o, Vector(p), VT * 1.15))
    for o, p0, v in terran:
        o.location = p0
        o.keyframe_insert('location', frame=1)
        o.location = p0 + v * SECONDS
        o.keyframe_insert('location', frame=NF)
        set_interp(o)

    # ---------------- Kesh fleet (moving -X, facing the Terrans)
    moth, core = ships.kesh_mothership('Mothership')
    MS = 3.2
    moth.scale = (MS, MS, MS)
    moth.rotation_euler = (math.radians(4), 0, math.radians(188))
    cru, _ = ships.kesh_cruiser('CruiserSrc')
    kesh = [(moth, Vector((330, 75, 22)), Vector((-1.5, 0, 0)))]
    crus = []
    for i, p in enumerate([(205, -38, 4), (240, 120, 30), (180, 52, -14), (265, -10, 40)]):
        o = cru if i == 0 else cru.copy()
        if i:
            o.name = f'Cruiser{i}'
            sc.collection.objects.link(o)
        o.rotation_euler = (0, 0, math.radians(180 + rnd.uniform(-12, 12)))
        o.scale = (1.4, 1.4, 1.4)
        crus.append(o)
        kesh.append((o, Vector(p), Vector((-4.0, 0, 0))))
    for o, p0, v in kesh:
        o.location = p0
        o.keyframe_insert('location', frame=1)
        o.location = p0 + v * SECONDS
        o.keyframe_insert('location', frame=NF)
        set_interp(o)

    def at(obj, p0, v, local, t):
        """World position of a local point on a moving ship at time t."""
        return (Matrix.Translation(p0 + v * t) @ obj.matrix_basis.to_3x3().to_4x4().inverted_safe().inverted()
                @ Matrix.Translation(Vector(local))).translation if False else \
            p0 + v * t + (Euler(obj.rotation_euler).to_matrix() @ (Vector(local) * obj.scale[0]))

    # ---------------- materials for effects
    bolt_m = emit_mat('BoltCyan', (0.12, 0.65, 1.0), 16.0)
    plasma_m = emit_mat('PlasmaGold', (1.0, 0.3, 0.02), 5.0)
    beam_m = emit_mat('BeamGold', (1.0, 0.45, 0.08), 0.0)

    def bolt(mat, p_from, p_to, t0, speed, size=(3.6, 0.08, 0.08), name='bolt'):
        d = Vector(p_to) - Vector(p_from)
        dur = d.length / speed
        o = uv_sphere(name, 1.0, seg=(10, 6), mat=mat, scale=size)
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = d.to_track_quat('X', 'Z')
        o.location = p_from
        o.keyframe_insert('location', frame=T(t0))
        o.location = p_to
        o.keyframe_insert('location', frame=T(t0 + dur))
        show_between(o, int(T(t0)), int(T(t0 + dur)) + 1)
        set_interp(o)
        o.visible_shadow = False
        return t0 + dur

    booms = []

    def boom(p, t, size, hot=(1.0, 0.45, 0.06), cool=(0.35, 0.03, 0.005), life=1.2, light=0.0, follow=None):
        m = fireball_mat(f'boom{len(booms)}', hot, cool)
        o = uv_sphere(f'Boom{len(booms)}', 1.0, seg=(24, 14), mat=m)
        o.visible_shadow = False
        o.rotation_euler = (rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6))
        f0, f1 = T(t), T(t + life)
        for f, s in [(f0, size * 0.15), (f0 + 3, size * 0.75), (f1, size * 1.25)]:
            o.scale = (s, s, s)
            o.keyframe_insert('scale', frame=f)
        o.location = p
        o.keyframe_insert('location', frame=f0)
        if follow is not None:
            o.location = Vector(p) + follow * life
            o.keyframe_insert('location', frame=f1)
        key_value(m, 'S', 1, 0.0)
        key_value(m, 'S', f0, 0.0)
        key_value(m, 'S', f0 + 1, 7.0)
        key_value(m, 'S', f0 + 6, 3.5)
        key_value(m, 'S', f1, 0.8)
        key_value(m, 'V', 1, 1.0)
        key_value(m, 'V', f0 + 6, 1.0)
        key_value(m, 'V', f1, 0.0)
        show_between(o, int(f0), int(f1) + 1)
        set_interp(o)
        set_interp(m.node_tree)
        if light > 0:
            L = bpy.data.objects.new(f'Flash{len(booms)}', bpy.data.lights.new(f'Flash{len(booms)}', 'POINT'))
            sc.collection.objects.link(L)
            L.location = p
            L.data.color = hot
            L.data.shadow_soft_size = size * 0.5
            for f, e in [(1, 0), (f0, 0), (f0 + 1, light), (f0 + 10, light * 0.25), (f1, 0)]:
                L.data.energy = e
                L.data.keyframe_insert('energy', frame=f)
            set_interp(L.data)
        booms.append(o)
        return o

    # ---------------- Terran fire: turret batteries at the Kesh ships
    targets = [(moth, kesh[0][1], kesh[0][2], Vector((rnd.uniform(-14, 18), rnd.uniform(-10, 10), rnd.uniform(-2, 4))))
               for _ in range(6)]
    targets += [(c, kesh[i + 1][1], kesh[i + 1][2], Vector((rnd.uniform(-5, 6), 0, 0))) for i, c in enumerate(crus)]
    for i, mz in enumerate(muzzles):
        t = 0.15 + (i * 0.37) % 0.9
        while t < SECONDS - 0.4:
            tgt, p0, v, loc = rnd.choice(targets)
            src = at(flag, Vector((0, 0, 0)), VT, mz, t)
            dst = at(tgt, p0, v, loc, t + 1.4)
            t_hit = bolt(bolt_m, src, dst, t, 170.0, name=f'Bolt{i}')
            if t_hit < SECONDS:
                boom(dst, t_hit, rnd.uniform(0.8, 1.4), hot=(0.6, 0.9, 1.0), cool=(0.1, 0.3, 0.9), life=0.6)
            t += rnd.uniform(0.7, 1.3)
    # frigates fire too
    for fi, (o, p0, v) in enumerate(terran[2:]):
        t = rnd.uniform(0, 0.8)
        while t < SECONDS - 0.5:
            tgt, tp0, tv, loc = rnd.choice(targets)
            src = at(o, p0, v, (9.2, 0, 0.75), t)
            dst = at(tgt, tp0, tv, loc, t + 1.2)
            t_hit = bolt(bolt_m, src, dst, t, 170.0, size=(3.0, 0.07, 0.07))
            if t_hit < SECONDS:
                boom(dst, t_hit, rnd.uniform(0.7, 1.2), hot=(0.6, 0.9, 1.0), cool=(0.1, 0.3, 0.9), life=0.5)
            t += rnd.uniform(0.9, 1.6)

    # ---------------- Kesh fire: cruisers lob gold plasma at the Terran ships
    hits_on = [(flag, Vector((0, 0, 0)), VT, Vector((x, s * 3.2, 0.5))) for x in (-8, 4, 12) for s in (-1, 1)]
    hits_on += [(o, p0, v, Vector((0, 0, 0))) for (o, p0, v) in terran[1:]]
    for ci, c in enumerate(crus):
        _, p0, v = kesh[ci + 1]
        t = 0.3 + ci * 0.45
        while t < SECONDS - 0.5:
            tgt, tp0, tv, loc = rnd.choice(hits_on)
            src = at(c, p0, v, (9.8, 0, 0.2), t)
            dst = at(tgt, tp0, tv, loc, t + 1.6)
            t_hit = bolt(plasma_m, src, dst, t, 120.0, size=(1.4, 0.4, 0.4), name=f'Plasma{ci}')
            if t_hit < SECONDS:
                boom(dst, t_hit, rnd.uniform(1.0, 1.8), life=0.9, light=0.0)
            t += rnd.uniform(1.0, 1.6)

    # ---------------- the mothership's core beam kills a frigate (frigate 2, low and ahead)
    victim, vp0, vv = terran[4]
    t_beam0, t_kill = 3.6, 5.0
    core_w = lambda t: at(moth, kesh[0][1], kesh[0][2], core, t)  # noqa: E731
    beam = uv_sphere('Beam', 1.0, seg=(16, 6), mat=beam_m)
    beam.visible_shadow = False
    beam.rotation_mode = 'QUATERNION'
    for f in range(int(T(t_beam0)), int(T(t_kill + 0.8)) + 1, 2):
        t = (f - 1) / FPS
        a, b = core_w(t), vp0 + vv * t
        d = b - a
        beam.location = (a + b) / 2
        beam.rotation_quaternion = d.to_track_quat('X', 'Z')
        grow = min(1.0, (t - t_beam0) / 0.25)
        w = 0.55 * grow * (1.0 + 0.25 * math.sin(f * 1.9))
        beam.scale = (d.length / 2, w, w)
        for path in ('location', 'rotation_quaternion', 'scale'):
            beam.keyframe_insert(path, frame=f)
    em = beam_m.node_tree.nodes['Emission']
    for f, s in [(1, 0), (T(t_beam0), 0), (T(t_beam0) + 3, 16), (T(t_kill + 0.5), 12), (T(t_kill + 0.8), 0)]:
        em.inputs[1].default_value = s
        em.inputs[1].keyframe_insert('default_value', frame=f)
    show_between(beam, int(T(t_beam0)), int(T(t_kill + 0.8)) + 1)
    set_interp(beam)
    set_interp(beam_m.node_tree)
    # charge glow on the core
    boom(core_w(t_beam0 - 0.4), t_beam0 - 0.4, 7.0, hot=(1.0, 0.75, 0.3), cool=(0.8, 0.3, 0.05), life=0.8)
    # frigate dies: fireballs, then it is replaced by tumbling halves
    kp = vp0 + vv * t_kill
    for k in range(5):
        off = Vector((rnd.uniform(-5, 5), rnd.uniform(-2, 2), rnd.uniform(-1.5, 1.5)))
        boom(kp + off, t_kill + k * 0.12, rnd.uniform(2.5, 4.0), life=1.8, light=6e5 if k == 0 else 0, follow=vv * 0.6)
    boom(kp, t_kill + 0.05, 6.5, hot=(1.0, 0.7, 0.3), cool=(0.6, 0.12, 0.01), life=1.0, follow=vv * 0.6)
    show_between(victim, 1, int(T(t_kill + 0.15)))
    for half, (x0, x1) in enumerate([(-8, 0), (0, 9)]):
        F.ST['parts'] = []
        piece = victim.copy()
        piece.data = victim.data.copy()
        piece.name = f'Wreck{half}'
        sc.collection.objects.link(piece)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(piece.data)
        dead = [v for v in bm.verts if not (x0 <= v.co.x <= x1)]
        bmesh.ops.delete(bm, geom=dead, context='VERTS')
        bm.to_mesh(piece.data)
        bm.free()
        piece.animation_data_clear()
        f0 = int(T(t_kill + 0.15))
        piece.location = kp
        piece.rotation_euler = (0, 0, 0)
        piece.keyframe_insert('location', frame=f0)
        piece.keyframe_insert('rotation_euler', frame=f0)
        drift = Vector((vv.x * 0.6 + (4 if half else -4), (-3 if half else 3), (2 if half else -2)))
        piece.location = kp + drift * (SECONDS - t_kill)
        piece.rotation_euler = ((0.9 if half else -1.2), (0.5 if half else -0.4), (0.6 if half else -0.3))
        piece.keyframe_insert('location', frame=NF)
        piece.keyframe_insert('rotation_euler', frame=NF)
        show_between(piece, f0, NF + 1)
        set_interp(piece)

    # ---------------- fighters
    falcon = load_glb(os.path.join(REPO, 'public/assets/models/human/falcon.glb'), 1.4)
    halo = load_glb(os.path.join(REPO, 'public/assets/models/alien/halo.glb'), 1.5)
    # Falcons launch past the camera toward the Kesh line
    for i in range(14):
        y, z = rnd.uniform(-14, 18), rnd.uniform(-3, 11)
        t0 = rnd.uniform(-1.5, 4.5)
        sp = rnd.uniform(28, 36)
        p0 = Vector((-30 + rnd.uniform(-6, 6), y, z))
        mid = p0 + Vector((sp * 4, rnd.uniform(-8, 8), rnd.uniform(-4, 4)))
        end = mid + Vector((sp * 4, rnd.uniform(-20, 20), rnd.uniform(-8, 8)))
        fly(falcon, f'Falcon{i}', [p0, mid, end], t0, t0 + 8, bank=0.6)
    # Halos stream in from the Kesh side
    for i in range(16):
        t0 = rnd.uniform(-2, 4)
        p0 = Vector((rnd.uniform(200, 260), rnd.uniform(-40, 80), rnd.uniform(-10, 35)))
        mid = Vector((rnd.uniform(60, 110), rnd.uniform(-35, 45), rnd.uniform(-8, 20)))
        end = Vector((rnd.uniform(-60, 0), rnd.uniform(-60, 60), rnd.uniform(-15, 25)))
        fly(halo, f'Halo{i}', [p0, mid, end], t0, t0 + 9, bank=0.9)
    # a few Falcon tracers
    for i in range(10):
        t = rnd.uniform(0.5, 7.0)
        a = Vector((rnd.uniform(40, 90), rnd.uniform(-20, 30), rnd.uniform(-4, 12)))
        bolt(bolt_m, a, a + Vector((60, rnd.uniform(-6, 6), rnd.uniform(-3, 3))), t, 200.0, size=(1.2, 0.05, 0.05))

    # ---------------- lights
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sc.collection.objects.link(sun)
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.95, 0.88)
    sun.data.angle = math.radians(0.6)
    sun.rotation_euler = (math.radians(58), 0, math.radians(-128))
    rim = bpy.data.objects.new('RiftLight', bpy.data.lights.new('RiftLight', 'SUN'))
    sc.collection.objects.link(rim)
    rim.data.energy = 0.9
    rim.data.color = (0.55, 0.3, 1.0)
    rim.rotation_euler = (math.radians(80), 0, math.radians(-75))
    fill = bpy.data.objects.new('PlanetFill', bpy.data.lights.new('PlanetFill', 'SUN'))
    sc.collection.objects.link(fill)
    fill.data.energy = 0.25
    fill.data.color = (0.35, 0.5, 0.8)
    fill.rotation_euler = (math.radians(175), 0, 0)
    fill.data.use_shadow = False

    # ---------------- camera: glide over the flagship's spine toward the Kesh line
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 28
    cam.data.clip_end = 20000
    cam.data.sensor_width = 36
    keys = [(0.0, (-34, 13, 8.5), (40, 0, 0)),
            (3.0, (-14, 9.5, 7.0), (110, 15, 2)),
            (6.0, (4, 7.5, 6.0), (175, 12, -2)),
            (SECONDS, (14, 6.5, 5.6), (215, 18, 0))]
    for t, p, tgt in keys:
        pw = Vector(p) + VT * t
        tw = Vector(tgt)
        cam.location = pw
        cam.rotation_euler = (tw - pw).to_track_quat('-Z', 'Y').to_euler()
        cam.rotation_euler[1] += math.radians(-4 + 3 * t / SECONDS)    # slight roll
        cam.keyframe_insert('location', frame=T(t))
        cam.keyframe_insert('rotation_euler', frame=T(t))
    set_interp(cam, 'BEZIER')

    # ---------------- render settings
    r = sc.render
    r.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 3
    sc.cycles.diffuse_bounces = 1
    sc.cycles.glossy_bounces = 2
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.sample_clamp_indirect = 4.0
    r.resolution_x, r.resolution_y = RES
    r.resolution_percentage = 100
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.45
    r.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in \
        [i.identifier for i in sc.view_settings.bl_rna.properties['look'].enum_items] else 'None'
    sc.view_settings.exposure = 0.0
    os.makedirs(OUT, exist_ok=True)
    if 'blend' in args:
        bpy.ops.wm.save_as_mainfile(filepath=args['blend'])
    if 'still' in args:
        for f in args['still'].split(','):
            sc.frame_set(int(f))
            r.filepath = os.path.join(OUT, f'still_{int(f):04d}.png')
            bpy.ops.render.render(write_still=True)
    else:
        a, b = (args.get('frames', f'1-{NF}')).split('-')
        sc.frame_start, sc.frame_end = int(a), int(b)
        r.filepath = os.path.join(OUT, 'frames', 'f_')
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
