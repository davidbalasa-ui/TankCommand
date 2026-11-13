"""The five new pieces the opening video needs, with still renders for approval.

    python tools/cinematics/opening/new_pieces.py --piece=dropship|seedpod|shield|crystalfield|shard|all --out=DIR

Builders (importable): drop_ship(), seed_pod(), shield_dome(), crystal_field(), shard().
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import forge as F  # noqa: E402
import ships as base  # noqa: E402
import arcadian_fleet as AF  # noqa: E402
import arcadian_designs as D  # noqa: E402

VIOLET = (0.45, 0.12, 1.0)


def _mat(name, base_col=(0.1, 0.1, 0.1), emit=None, strength=0.0, transmission=0.0, rough=0.4, metal=0.0, ior=1.45,
         alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base_col, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['IOR'].default_value = ior
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = strength
    return m


def _assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# ================================================================== 1. Terran drop ship
def drop_ship(name='DropShip', cargo=True, hot=False):
    """~9 long armoured lander. Blunt heat-shield nose, four swivel thruster pods on stub wings,
    a Lancer tank clamped under the belly. hot=True adds the glowing re-entry sheath."""
    base._faction('terran')
    m = F.mark()
    secs = []
    for x, w, zb, zt in [(-4.6, 1.5, -0.7, 1.1), (-2.5, 1.8, -0.9, 1.5), (1.0, 1.8, -0.9, 1.5),
                         (3.4, 1.5, -0.8, 1.1), (4.6, 0.9, -0.5, 0.5)]:
        secs.append((x, [(0, zb), (w * 0.8, zb), (w, zb * 0.2), (w * 0.9, zt * 0.6), (w * 0.5, zt), (0, zt)]))
    F.hull(secs, 'hull', bevel=0.05)
    # heat shield: dark ablative plates over the nose and belly front
    F.hull([(2.6, [(0, -0.98), (1.6, -0.95), (1.9, -0.1), (0, -0.1)]),
            (4.75, [(0, -0.55), (0.95, -0.52), (1.0, 0.0), (0, 0.0)])], 'dark', bevel=0.03)
    # cockpit slit, spine, cyan strips, amber lights
    F.box((2.9, 0, 1.05), (0.5, 0.8, 0.12), 'glass', taper=0.7)
    F.box((-1.0, 0, 1.6), (2.6, 0.6, 0.2), 'armor', taper=0.7, bevel=0.03)
    F.sym(F.box((-0.5, 1.82, 0.25), (3.2, 0.02, 0.05), 'glow'))
    for x in (-3.8, -1.0, 1.8):
        F.sym(F.orb((x, 1.6, 1.0), 0.07, 'amber', seg=(8, 5)))
    F.cyl((-3.5, 0, 1.5), (-3.5, 0, 2.6), 0.04, 6, 'barrel')
    # stub wings with four thruster pods
    for x in (-3.0, 1.6):
        F.sym(F.box((x, 2.4, 0.2), (0.6, 0.7, 0.12), 'armor', taper=0.85, bevel=0.03))
        for s in (-1, 1):
            F.cyl((x - 0.9, s * 3.2, 0.2), (x + 0.7, s * 3.2, 0.2), 0.55, 14, 'plate')
            F.tube((x - 0.9, s * 3.2, 0.2), (x - 1.4, s * 3.2, 0.2), [(0, 0.5), (1, 0.62)], 14, 'dark', caps=False)
            F.cyl((x - 1.2, s * 3.2, 0.2), (x - 1.25, s * 3.2, 0.2), 0.5, 14, 'glow')
            F.cyl((x - 0.1, s * 3.2, -0.3), (x - 0.1, s * 3.2, -0.45), 0.35, 12, 'amber')   # down thruster
    # main engines
    for y in (-0.7, 0.7):
        F.tube((-4.6, y, 0.3), (-5.6, y, 0.3), [(0, 0.45), (1, 0.55)], 14, 'dark', caps=False)
        F.cyl((-5.3, y, 0.3), (-5.35, y, 0.3), 0.48, 14, 'glow')
    # cargo clamps
    for x in (-2.4, 1.0):
        F.sym(F.box((x, 0.9, -1.15), (0.25, 0.12, 0.35), 'hazard'))
    ship = base._join(F.since(m), name)
    if cargo:
        tank = C.OS.load_glb(os.path.join(C.MODELS, 'human/lancer.glb'), 3.6)
        tank.hide_render = False
        tank.location = (-0.6, 0, -2.05)
        tank.parent = ship
    if hot:
        sheath = F.lathe([(0.0, 0.0), (1.8, -0.6), (2.8, -2.5), (3.4, -6.0), (3.6, -9.0)], 32, 'glow')
        ob = base._join([sheath], name + '_Sheath')
        ob.rotation_euler = (0, math.radians(90), 0)
        ob.location = (6.4, 0, -0.4)
        ob.scale = (1.0, 0.9, 1.0)
        _assign(ob, _sheath_mat((1.0, 0.35, 0.05)))
        ob.parent = ship
        ob.visible_shadow = False
    return ship


def _sheath_mat(col, strength=6.0):
    """Hot re-entry plasma: bright at the front, fading toward the open end, see-through."""
    m = bpy.data.materials.new('Sheath')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs[1].default_value = -9.0
    mr.inputs[2].default_value = 0.0
    nt.links.new(sep.outputs[2], mr.inputs[0])
    nz = nt.nodes.new('ShaderNodeTexNoise')   # streaks running along the sheath axis (object z)
    nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = 6
    st = nt.nodes.new('ShaderNodeVectorMath')
    st.operation = 'MULTIPLY'
    st.inputs[1].default_value = (3.0, 3.0, 0.22)
    nt.links.new(tc.outputs['Object'], st.inputs[0])
    nt.links.new(st.outputs[0], nz.inputs['Vector'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(mr.outputs[0], mul.inputs[0])
    nt.links.new(nz.outputs['Fac'], mul.inputs[1])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 2.2
    nt.links.new(mul.outputs[0], pw.inputs[0])
    sm = nt.nodes.new('ShaderNodeMath')
    sm.operation = 'MULTIPLY'
    sm.inputs[1].default_value = strength
    nt.links.new(pw.outputs[0], sm.inputs[0])
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs[0].default_value = 0.5
    edge = nt.nodes.new('ShaderNodeMapRange')
    edge.inputs[3].default_value = 0.15
    edge.inputs[4].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], edge.inputs[0])
    sm2 = nt.nodes.new('ShaderNodeMath')
    sm2.operation = 'MULTIPLY'
    nt.links.new(sm.outputs[0], sm2.inputs[0])
    nt.links.new(edge.outputs[0], sm2.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission')
    ramp = nt.nodes.new('ShaderNodeValToRGB')     # red at the open end -> col -> white-hot at the nose
    ramp.color_ramp.elements[0].color = (col[0] * 0.8, col[1] * 0.15, col[2] * 0.1, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (1.0, 0.7, 0.3, 1)
    e = ramp.color_ramp.elements.new(0.6)
    e.color = (*col, 1)
    nt.links.new(mr.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], em.inputs[0])
    nt.links.new(sm2.outputs[0], em.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    return m


# ================================================================== 2. Arcadian seed pod
def seed_pod(name='SeedPod', hot=False):
    """~6 long gold seed: overlapping petal plates wrapped round a glowing core (seen through the
    petal slits), three crescent tail fins and a hanging root spike. Nose is +X (falls nose first)."""
    rnd = random.Random(3)
    with AF.gold_palette():
        base._faction('kesh')
        m = F.mark()
        lens = F.lensfn(-3.2, 3.0, 1.35, 1.35, -1.35, 0.0, nose=0.55, tail=0.8)
        F.body(lens, 'under', nu=20, nv=18)
        for k in range(6):   # petals wrapping the body, gaps between them glow
            F.shell(lens, 0.02, 0.9, k * 60, 46, 'shell' if k % 2 else 'bronze', nu=14, nv=4, thick=0.14,
                    off=0.08, lift=0.06, shape=0.45, front=0.5)
        F.body(F.lensfn(-2.8, 2.6, 1.15, 1.15, -1.15, 0.0, nose=0.55, tail=0.8), 'slat', nu=12, nv=12)
        F.orb((0.4, 0, 0), 0.75, 'core', seg=(18, 12))
        for k in range(3):   # crescent tail fins, floating just off the body
            a = k * 120
            o = F.crescent((0, 0, 0), 2.0, 100, 175, 0.45, 0.16, 'shell', n=12, plane='xz', up=(0, 1, 0))
            F.rot(o, 'X', a)
            F.move(o, (-2.0, 0, 0))
        F.cyl((3.0, 0, 0), (4.4, 0, 0), 0.22, 8, 'bronze', r1=0.01)   # root spike / nose
        AF.oriented_ring((-2.6, 0, 0), (1, 0, 0), 0.9, 0.18, 0.14, 'bronze', gaps=3)
        AF.bolt((-2.6, 0.9, 0.2), (0.4, 0.2, 1.4), rnd, width=0.05, jag=0.25, depth=4, branches=1)
        pod = base._join(F.since(m), name)
    if hot:
        sheath = F.lathe([(0.0, 0.0), (1.4, -0.5), (2.0, -2.0), (2.4, -5.0), (2.5, -8.0)], 32, 'glow')
        ob = base._join([sheath], name + '_Sheath')
        ob.rotation_euler = (0, math.radians(90), 0)
        ob.location = (4.8, 0, 0)
        _assign(ob, _sheath_mat((1.0, 0.55, 0.12), 5.0))
        ob.parent = pod
        ob.visible_shadow = False
    return pod


# ================================================================== 3. gold deflector shield
def shield_dome(size=(34, 28, 16), hit=(30.0, -6.0, 3.0), name='Shield'):
    """Ellipsoid energy shield: faint gold hex lattice that brightens at the rim (fresnel) and a
    bright ripple ring spreading from the impact point `hit` (object space before scaling)."""
    o = C.uv_sphere(name, 1.0, seg=(96, 48))
    o.scale = size
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs[0].default_value = 0.12
    rim = nt.nodes.new('ShaderNodeMath')
    rim.operation = 'POWER'
    rim.inputs[1].default_value = 4.0
    nt.links.new(lw.outputs['Facing'], rim.inputs[0])
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 9.0
    nt.links.new(tc.outputs['Object'], vor.inputs['Vector'])
    hexl = nt.nodes.new('ShaderNodeMath')
    hexl.operation = 'LESS_THAN'
    hexl.inputs[1].default_value = 0.04
    nt.links.new(vor.outputs['Distance'], hexl.inputs[0])
    # ripple: distance from the hit point (in unit-sphere space)
    hp = Vector(hit)
    hp = Vector((hp.x / size[0], hp.y / size[1], hp.z / size[2])).normalized()
    dist = nt.nodes.new('ShaderNodeVectorMath')
    dist.operation = 'DISTANCE'
    dist.inputs[1].default_value = tuple(hp)
    nt.links.new(tc.outputs['Object'], dist.inputs[0])
    wave = nt.nodes.new('ShaderNodeMath')
    wave.operation = 'SINE'
    mulw = nt.nodes.new('ShaderNodeMath')
    mulw.operation = 'MULTIPLY'
    mulw.inputs[1].default_value = 55.0
    nt.links.new(dist.outputs['Value'], mulw.inputs[0])
    nt.links.new(mulw.outputs[0], wave.inputs[0])
    fall = nt.nodes.new('ShaderNodeMapRange')
    fall.inputs[1].default_value = 0.0
    fall.inputs[2].default_value = 0.5
    fall.inputs[3].default_value = 1.0
    fall.inputs[4].default_value = 0.0
    nt.links.new(dist.outputs['Value'], fall.inputs[0])
    rip = nt.nodes.new('ShaderNodeMath')
    rip.operation = 'MULTIPLY'
    nt.links.new(wave.outputs[0], rip.inputs[0])
    nt.links.new(fall.outputs[0], rip.inputs[1])
    ripc = nt.nodes.new('ShaderNodeMath')
    ripc.operation = 'MAXIMUM'
    ripc.inputs[1].default_value = 0.0
    nt.links.new(rip.outputs[0], ripc.inputs[0])
    ripp = nt.nodes.new('ShaderNodeMath')      # thin bright rings instead of a bullseye
    ripp.operation = 'POWER'
    ripp.inputs[1].default_value = 8.0
    nt.links.new(ripc.outputs[0], ripp.inputs[0])
    flare = nt.nodes.new('ShaderNodeMapRange')       # hot spot right at the impact
    flare.inputs[1].default_value = 0.0
    flare.inputs[2].default_value = 0.12
    flare.inputs[3].default_value = 6.0
    flare.inputs[4].default_value = 0.0
    nt.links.new(dist.outputs['Value'], flare.inputs[0])
    # total = rim*1.2 + hex*(0.15 + rim) + ripple*3 + flare
    a1 = nt.nodes.new('ShaderNodeMath')
    a1.operation = 'MULTIPLY_ADD'
    a1.inputs[1].default_value = 1.0
    nt.links.new(hexl.outputs[0], a1.inputs[0])
    nt.links.new(rim.outputs[0], a1.inputs[2])
    hexs = nt.nodes.new('ShaderNodeMath')
    hexs.operation = 'MULTIPLY_ADD'
    hexs.inputs[1].default_value = 0.9
    nt.links.new(rim.outputs[0], hexs.inputs[0])
    hexs.inputs[2].default_value = 0.05
    hx = nt.nodes.new('ShaderNodeMath')
    hx.operation = 'MULTIPLY'
    nt.links.new(hexl.outputs[0], hx.inputs[0])
    nt.links.new(hexs.outputs[0], hx.inputs[1])
    t1 = nt.nodes.new('ShaderNodeMath')
    t1.operation = 'MULTIPLY_ADD'
    t1.inputs[1].default_value = 0.7
    nt.links.new(rim.outputs[0], t1.inputs[0])
    nt.links.new(hx.outputs[0], t1.inputs[2])
    t2 = nt.nodes.new('ShaderNodeMath')
    t2.operation = 'MULTIPLY_ADD'
    t2.inputs[1].default_value = 5.0
    nt.links.new(ripp.outputs[0], t2.inputs[0])
    nt.links.new(t1.outputs[0], t2.inputs[2])
    t3 = nt.nodes.new('ShaderNodeMath')
    t3.operation = 'ADD'
    nt.links.new(t2.outputs[0], t3.inputs[0])
    nt.links.new(flare.outputs[0], t3.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value = (1.0, 0.68, 0.2, 1)
    nt.links.new(t3.outputs[0], em.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    o.data.materials.append(m)
    o.visible_shadow = False
    return o


# ================================================================== 4. crystal field ground
def crystal_mat():
    """Deep violet glassy crystal: glows brightest at the root, clearer toward the tips."""
    m = _mat('Crystal', base_col=(0.42, 0.12, 1.0), emit=(0.38, 0.06, 1.0), strength=0.9, transmission=0.6,
             rough=0.12, ior=1.6)
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs[0].default_value = 0.3
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs[3].default_value = 0.5
    mr.inputs[4].default_value = 2.2
    nt.links.new(lw.outputs['Facing'], mr.inputs[0])
    nt.links.new(mr.outputs[0], b.inputs['Emission Strength'])
    return m


def crystal_cluster(c, size, rnd, mat, n=None):
    """A clump of 3..9 hexagonal crystal spikes leaning out from a common root."""
    parts = []
    n = n or rnd.randint(3, 9)
    for i in range(n):
        h = size * rnd.uniform(0.5, 1.4)
        r = h * rnd.uniform(0.12, 0.2)
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(1.2, 3.0))).normalized()
        p0 = Vector(c) + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), -0.3)) * size
        o = F.tube(tuple(p0), tuple(p0 + d * h), [(0, r), (0.75, r * 0.95), (1.0, 0.0)], 6, 'glow', sharp=20)
        parts.append(o)
    ob = base._join(parts, 'Cluster')
    _assign(ob, mat)
    return ob


def ground(size=600, seed=2, name='Ground', crack_glow=0.0):
    """Displaced rocky ground plane (dusty rock with darker strata)."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=220, y_subdivisions=220, size=size)
    g = bpy.context.active_object
    g.name = name
    tex = bpy.data.textures.new('GroundNoise', 'CLOUDS')
    tex.noise_scale = 18.0
    tex.noise_depth = 4
    mod = g.modifiers.new('Disp', 'DISPLACE')
    mod.texture = tex
    mod.strength = 6.0
    mod.mid_level = 0.5
    bpy.ops.object.modifier_apply(modifier='Disp')
    for p in g.data.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new('GroundMat')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 0.08
    nz.inputs['Detail'].default_value = 12
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.05, 0.045, 0.06, 1)
    ramp.color_ramp.elements[1].color = (0.26, 0.22, 0.24, 1)
    nt.links.new(nz.outputs['Fac'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.9
    bump = nt.nodes.new('ShaderNodeBump')
    fine = nt.nodes.new('ShaderNodeTexNoise')
    fine.inputs['Scale'].default_value = 1.5
    fine.inputs['Detail'].default_value = 8
    nt.links.new(tc.outputs['Object'], fine.inputs['Vector'])
    nt.links.new(fine.outputs['Fac'], bump.inputs['Height'])
    bump.inputs['Strength'].default_value = 0.4
    nt.links.new(bump.outputs[0], b.inputs['Normal'])
    if crack_glow > 0:   # glowing violet cracks (voronoi edges)
        v = nt.nodes.new('ShaderNodeTexVoronoi')
        v.feature = 'DISTANCE_TO_EDGE'
        v.inputs['Scale'].default_value = 0.07
        warp = nt.nodes.new('ShaderNodeTexNoise')
        warp.inputs['Scale'].default_value = 0.05
        warp.inputs['Detail'].default_value = 6
        wmix = nt.nodes.new('ShaderNodeVectorMath')
        wmix.operation = 'MULTIPLY_ADD'
        wmix.inputs[1].default_value = (9.0, 9.0, 9.0)
        nt.links.new(tc.outputs['Object'], warp.inputs['Vector'])
        nt.links.new(warp.outputs['Color'], wmix.inputs[0])
        nt.links.new(tc.outputs['Object'], wmix.inputs[2])
        nt.links.new(wmix.outputs[0], v.inputs['Vector'])
        lt = nt.nodes.new('ShaderNodeMath')
        lt.operation = 'LESS_THAN'
        lt.inputs[1].default_value = 0.008
        nt.links.new(v.outputs['Distance'], lt.inputs[0])
        rad = nt.nodes.new('ShaderNodeVectorMath')
        rad.operation = 'LENGTH'
        nt.links.new(tc.outputs['Object'], rad.inputs[0])
        fall = nt.nodes.new('ShaderNodeMapRange')
        fall.inputs[1].default_value = 10.0
        fall.inputs[2].default_value = 90.0
        fall.inputs[3].default_value = crack_glow
        fall.inputs[4].default_value = 0.0
        nt.links.new(rad.outputs['Value'], fall.inputs[0])
        mm = nt.nodes.new('ShaderNodeMath')
        mm.operation = 'MULTIPLY'
        nt.links.new(lt.outputs[0], mm.inputs[0])
        nt.links.new(fall.outputs[0], mm.inputs[1])
        b.inputs['Emission Color'].default_value = (*VIOLET, 1)
        nt.links.new(mm.outputs[0], b.inputs['Emission Strength'])
    g.data.materials.append(m)
    return g


def sky(top=(0.06, 0.05, 0.12), horizon=(0.55, 0.32, 0.4), strength=1.0, below=None):
    w = bpy.data.worlds.new('Sky')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs[1].default_value = 0.0
    mr.inputs[2].default_value = 0.45
    nt.links.new(sep.outputs[2], mr.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(mr.outputs[0], mix.inputs[0])
    mix.inputs[6].default_value = (*horizon, 1)
    mix.inputs[7].default_value = (*top, 1)
    col = mix.outputs[2]
    if below is not None:
        mr2 = nt.nodes.new('ShaderNodeMapRange')
        mr2.inputs[1].default_value = -0.25
        mr2.inputs[2].default_value = 0.0
        nt.links.new(sep.outputs[2], mr2.inputs[0])
        mix2 = nt.nodes.new('ShaderNodeMix')
        mix2.data_type = 'RGBA'
        nt.links.new(mr2.outputs[0], mix2.inputs[0])
        mix2.inputs[6].default_value = (*below, 1)
        nt.links.new(col, mix2.inputs[7])
        col = mix2.outputs[2]
    nt.links.new(col, bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs[0])


def crystal_field(seed=4, radius=140, count=70, height=None, patches=7):
    """Ground with glowing violet veins plus crystal clusters gathered into a few dense patches."""
    rnd = random.Random(seed)
    g = ground(crack_glow=1.4)
    nt = g.data.materials[0].node_tree
    nt.nodes['Map Range'].inputs[2].default_value = radius * 0.8
    nt.nodes['Math'].inputs[1].default_value = 0.0045
    mat = crystal_mat()
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(g, bpy.context.evaluated_depsgraph_get())

    def zat(x, y):
        hit = bvh.ray_cast(Vector((x, y, 100)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] else 0.0
    centres = [(radius * 0.8 * math.sqrt(rnd.random()), rnd.uniform(0, 2 * math.pi)) for _ in range(patches)]
    centres = [(r * math.cos(a), r * math.sin(a)) for r, a in centres]
    for i in range(count):
        cx, cy = centres[i % patches]
        r = 22 * math.sqrt(rnd.random())
        a = rnd.uniform(0, 2 * math.pi)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        size = rnd.uniform(2.0, 6.5) * (1.5 - r / 22)
        crystal_cluster((x, y, zat(x, y)), size, rnd, mat)
    for i in range(count // 2):   # loose shards scattered between the patches
        x, y = rnd.uniform(-radius, radius), rnd.uniform(-radius, radius)
        crystal_cluster((x, y, zat(x, y)), rnd.uniform(0.8, 2.0), rnd, mat, n=rnd.randint(1, 3))
    return g, bvh


# ================================================================== 5. the Shard
def shard(name='Shard', height=42.0):
    """Huge faceted violet crystal floating over a ruined stone ring: glowing core inside,
    spiral energy ribbons, floating crystal splinters, violet lightning down to the stones."""
    rnd = random.Random(9)
    base._faction('kesh')
    m = F.mark()
    zc = height * 0.5 + 10
    spikes = []
    # main double-ended crystal plus a crown of smaller ones leaning outward, all floating
    spikes.append(F.tube((0, 0, 10), (0, 0, 10 + height), [(0, 0.0), (0.12, 4.6), (0.7, 4.2), (1.0, 0.0)], 6,
                         'glow', sharp=20))
    for i in range(7):
        a = math.radians(i * 51 + rnd.uniform(-12, 12))
        lean = rnd.uniform(0.25, 0.55)
        h = height * rnd.uniform(0.35, 0.62)
        p0 = Vector((math.cos(a) * 3.2, math.sin(a) * 3.2, 10 + rnd.uniform(4, 12)))
        d = Vector((math.cos(a) * lean, math.sin(a) * lean, 1.0)).normalized()
        r = h * rnd.uniform(0.11, 0.15)
        spikes.append(F.tube(tuple(p0 - d * h * 0.2), tuple(p0 + d * h), [(0, 0.0), (0.18, r), (0.75, r * 0.9),
                                                                       (1.0, 0.0)], 6, 'glow', sharp=20))
    for i in range(5):   # stubby shards hanging under it
        a = math.radians(i * 72 + 30)
        p0 = Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, 13))
        d = Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, -1.0)).normalized()
        h = rnd.uniform(5, 9)
        spikes.append(F.tube(tuple(p0), tuple(p0 + d * h), [(0, h * 0.13), (0.7, h * 0.11), (1.0, 0.0)], 6, 'glow',
                             sharp=20))
    crystal = base._join(spikes, name)
    _assign(crystal, _mat('ShardGlass', base_col=(0.45, 0.15, 1.0), emit=(0.4, 0.08, 1.0), strength=0.5,
                          transmission=0.75, rough=0.06, ior=1.7))
    core = C.uv_sphere(name + '_Core', 2.4, seg=(32, 16), mat=C.emit_mat('ShardCore', (0.55, 0.2, 1.0), 9.0))
    core.location = (0, 0, zc - 2)
    core.scale = (1, 1, 1.8)
    # floating splinters
    smat = _mat('Splinter', base_col=(0.5, 0.3, 1.0), emit=VIOLET, strength=2.0, transmission=0.7, rough=0.1)
    parts = []
    for i in range(18):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(9, 16)
        z = rnd.uniform(8, height + 8)
        o = F.ico((r * math.cos(a), r * math.sin(a), z), rnd.uniform(0.6, 1.6), 'glow', sub=1,
                  sq=(0.35, 0.35, 1.0), jitter=0.15, seed=i)
        F.rot(o, 'X', rnd.uniform(-40, 40), (r * math.cos(a), r * math.sin(a), z))
        parts.append(o)
    spl = base._join(parts, name + '_Splinters')
    _assign(spl, smat)
    # spiral energy ribbons
    rib = []
    for k in range(2):
        pts = []
        for i in range(70):
            t = i / 69
            a = k * math.pi + t * 3 * math.pi
            r = 8 + 4 * math.sin(t * math.pi) + 1.2 * math.sin(t * 17 + k)
            pts.append((r * math.cos(a), r * math.sin(a), 4 + t * (height + 4)))
        rib.append(F.sweep(pts, [(0.1, 0.04)] * 70, 'glow', sides=4))
    rb = base._join(rib, name + '_Ribbons')
    _assign(rb, C.emit_mat('Ribbon', (0.6, 0.3, 1.0), 8.0))
    # ruined stone ring of leaning spikes + broken plinth
    stone = []
    for i in range(9):
        a = i * 40 + rnd.uniform(-8, 8)
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        h = rnd.uniform(9, 18)
        stone.append(F.tube((ca * 17, sa * 17, -1), (ca * 15.5 - ca * h * 0.25, sa * 15.5 - sa * h * 0.25, h),
                            [(0, 2.0), (0.7, 1.2), (1.0, 0.0)], 5, 'rock', sharp=20))
    stone.append(F.lathe([(0, 2.5), (12, 2.5), (14, 1.2), (15, -1.5)], 10, 'rock', caps=True))
    for i in range(14):
        a = rnd.uniform(0, 360)
        r = rnd.uniform(12, 22)
        stone.append(F.rock((r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0), rnd.uniform(1, 2.5),
                            'rock', seed=i))
    F.ST['faction'] = 'nature'
    F.ST['mats'] = {}
    st = base._join(stone, name + '_Ruins')
    # violet lightning from the crystal tip-ends to the stones
    pairs = []
    for i in range(5):
        a = math.radians(i * 72 + 20)
        pairs.append(((0, 0, 11), (15 * math.cos(a), 15 * math.sin(a), rnd.uniform(6, 12))))
    base._faction('kesh')
    m2 = F.mark()
    for a, b in pairs:
        AF.bolt(a, b, rnd, width=0.18, jag=0.22, depth=5, branches=2, zone='violet')
    bl = base._join(F.since(m2), name + '_Lightning')
    _assign(bl, C.emit_mat('ShardBolt', (0.75, 0.5, 1.0), 30.0))
    lt = bpy.data.objects.new(name + '_Light', bpy.data.lights.new(name + '_Light', 'POINT'))
    bpy.context.scene.collection.objects.link(lt)
    lt.data.energy = 1.6e5
    lt.data.color = (0.6, 0.35, 1.0)
    lt.data.shadow_soft_size = 4
    lt.location = core.location
    return crystal


# ================================================================== stills
def _studio(dark=True):
    sc = bpy.context.scene
    if dark:
        C.OS.world()


def _light(name, rot, e, col):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = e
    ld.color = col
    ld.angle = math.radians(2)
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]
    return o


def _light_to(name, d, e, col):
    """Sun shining along direction d (world)."""
    o = _light(name, (0, 0, 0), e, col)
    o.rotation_euler = Vector(d).to_track_quat('-Z', 'Y').to_euler()
    return o


def _studio(k=1.0):
    """Key from upper front-left of a camera on the -Y/+X side, cool rim from behind, soft fill."""
    _light_to('Key', (-0.45, 0.75, -0.55), 7.0 * k, (1.0, 0.94, 0.86))
    _light_to('Rim', (0.3, -0.6, -0.2), 5.0 * k, (0.55, 0.72, 1.0))
    _light_to('Fill', (-0.6, 0.3, 0.6), 1.8 * k, (0.8, 0.72, 0.9))


def _cam(p, t, lens=40):
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_end = 5000
        cam.data.clip_start = 0.05
    cam.data.lens = lens
    cam.location = p
    cam.rotation_euler = (Vector(t) - Vector(p)).to_track_quat('-Z', 'Y').to_euler()


def _render(path, samples=32, res=(1280, 720), glass=False):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8 if glass else 4
    sc.cycles.transmission_bounces = 8 if glass else 2
    sc.cycles.transparent_max_bounces = 12
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def bloom_sheet(paths, out, label=None):
    import numpy as np
    from PIL import Image, ImageFilter, ImageDraw

    def bloom(im):
        a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
        lum = a.max(axis=2, keepdims=True)
        b = Image.fromarray((np.clip((lum - 0.72) / 0.28, 0, 1) * a * 255).astype(np.uint8))
        g = np.zeros_like(a)
        for r, w in [(4, 0.45), (12, 0.35), (32, 0.3)]:
            g += np.asarray(b.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255 * w
        return Image.fromarray((np.clip(1 - (1 - a) * (1 - np.clip(g, 0, 1)), 0, 1) * 255).astype(np.uint8))
    ims = [bloom(Image.open(p)) for p in paths]
    W, H = ims[0].size
    if len(ims) == 1:
        sheet = ims[0]
    elif len(ims) == 2:
        sheet = Image.new('RGB', (W * 2, H))
        sheet.paste(ims[0], (0, 0))
        sheet.paste(ims[1].resize((W, H)), (W, 0))
    else:
        sheet = Image.new('RGB', (W + W // 2, H))
        sheet.paste(ims[0], (0, 0))
        for i, im in enumerate(ims[1:3]):
            sheet.paste(im.resize((W // 2, H // 2)), (W, i * H // 2))
    if label:
        d = ImageDraw.Draw(sheet)
        d.rectangle((0, 0, 9 * len(label) + 16, 26), fill=(0, 0, 0))
        d.text((8, 7), label, fill=(235, 235, 235))
    sheet.save(out, quality=90)


def still(piece, out):
    tmp = os.path.join(out, '_views')
    os.makedirs(tmp, exist_ok=True)
    F.begin('terran')
    shots = []
    if piece == 'dropship':
        C.OS.world()
        ship = drop_ship()
        _studio()
        for v, p, t in [('hero', (12, -11, 2.2), (-0.5, 0, -0.8)), ('side', (0, -20, -0.5), (0, 0, -0.6)),
                        ('under', (-13, -9, -4.5), (0, 0, -0.8))]:
            _cam(p, t)
            shots.append(os.path.join(tmp, f'drop_{v}.png'))
            _render(shots[-1])
        label = 'Terran drop ship (carries one tank)'
    elif piece == 'dropship_hot':
        sky(top=(0.0, 0.0, 0.012), horizon=(0.45, 0.6, 0.95), strength=1.0, below=(0.25, 0.32, 0.45))
        ship = drop_ship(hot=True)
        ship.rotation_euler = (0, math.radians(28), 0)
        _light('Key', (40, 10, 120), 4.0, (1.0, 0.9, 0.8))
        _cam((14, -16, -4), (1, 0, -0.5), lens=35)
        shots.append(os.path.join(tmp, 'drop_hot.png'))
        _render(shots[-1])
        label = 'Terran drop ship entering the atmosphere'
    elif piece == 'seedpod':
        C.OS.world()
        pod = seed_pod()
        _studio(1.3)
        for v, p, t in [('hero', (7, -9, 4), (0, 0, 0)), ('side', (0, -12, 0.5), (0, 0, 0)),
                        ('hot', None, None)]:
            if v == 'hot':
                pod2 = seed_pod('SeedPodHot', hot=True)
                pod.hide_render = True
                pod2.rotation_euler = (0, math.radians(35), 0)
                sky(top=(0.0, 0.0, 0.012), horizon=(0.45, 0.6, 0.95), strength=1.0, below=(0.25, 0.32, 0.45))
                _cam((10, -11, -3), (1, 0, -0.3), lens=35)
            else:
                _cam(p, t)
            shots.append(os.path.join(tmp, f'pod_{v}.png'))
            _render(shots[-1])
        label = 'Arcadian seed pod (clean, side, falling through the atmosphere)'
    elif piece == 'shield':
        C.OS.world()
        ship, core = AF.crescent_mothership_v2()
        size = (34, 28, 16)
        hu = Vector((0.62, -0.72, 0.32)).normalized()          # impact on the camera-facing side
        sh = shield_dome(size=size, hit=tuple(hu[i] * size[i] for i in range(3)))
        sh.location = (-6, 0, 3)
        hw = Vector(sh.location) + Vector(tuple(hu[i] * size[i] for i in range(3)))
        # incoming slug just before impact + flash on the shield skin
        d = Vector((-1.0, 0.35, -0.12)).normalized()
        slug = C.uv_sphere('Slug', 1.0, seg=(12, 8), mat=C.emit_mat('SlugMat', (0.45, 0.85, 1.0), 30.0))
        slug.scale = (5, 0.45, 0.45)
        slug.rotation_mode = 'QUATERNION'
        slug.rotation_quaternion = d.to_track_quat('X', 'Z')
        slug.location = hw - d * 9.0
        flash = C.uv_sphere('Hit', 1.0, seg=(16, 10), mat=C.emit_mat('HitMat', (1.0, 0.8, 0.45), 20.0))
        flash.scale = (1.3, 1.3, 1.3)
        flash.location = hw
        _studio(1.1)
        for v, p, t in [('hero', (70, -85, 35), (-2, 0, 2)), ('side', (10, -110, 8), (-4, 0, 2))]:
            _cam(p, t, lens=35)
            shots.append(os.path.join(tmp, f'shield_{v}.png'))
            _render(shots[-1])
        label = 'Gold deflector shield taking a hit (crescent mothership inside)'
    elif piece == 'crystalfield':
        sky(top=(0.012, 0.012, 0.045), horizon=(0.42, 0.2, 0.24), strength=0.9)
        g, bvh = crystal_field()
        rf = C.OS.rift()
        rf.location = (420, 700, 260)
        rf.scale = (170, 170, 170)
        rf.rotation_mode = 'QUATERNION'
        rf.rotation_quaternion = (Vector((-90, -90, 20)) - Vector(rf.location)).to_track_quat('Z', 'Y')
        _light('Sun', (80, 0, 70), 3.5, (1.0, 0.72, 0.5))
        _light('Skyfill', (20, 0, -110), 0.5, (0.5, 0.55, 1.0))
        lancer = C.OS.load_glb(os.path.join(C.MODELS, 'human/lancer.glb'), 3.6)
        stinger = C.OS.load_glb(os.path.join(C.MODELS, 'alien/stinger.glb'), 3.6)
        rnd = random.Random(1)
        for src, x0, y0, n, yaw in ((lancer, -50, -40, 7, 40), (stinger, 10, 15, 7, 220)):
            for i in range(n):
                o = src.copy()
                o.hide_render = False
                bpy.context.scene.collection.objects.link(o)
                x, y = x0 + (i % 4) * 6 + rnd.uniform(-1, 1), y0 + (i // 4) * 7 + rnd.uniform(-1, 1)
                hit = bvh.ray_cast(Vector((x, y, 100)), Vector((0, 0, -1)))
                o.location = (x, y, (hit[0].z if hit[0] else 0) + (1.8 if src is stinger else 0.1))
                o.rotation_euler = (0, 0, math.radians(yaw))
        for v, p, t in [('hero', (-82, -72, 9), (-10, 0, 8)), ('high', (-170, -170, 120), (0, 0, 0)),
                        ('close', (-58, -50, 4), (-38, -26, 1))]:
            _cam(p, t, lens=30 if v != 'close' else 40)
            shots.append(os.path.join(tmp, f'field_{v}.png'))
            _render(shots[-1], glass=True)
        label = 'Crystal fields (tanks for scale)'
    elif piece == 'shard':
        sky(top=(0.015, 0.01, 0.04), horizon=(0.22, 0.1, 0.25), strength=0.8)
        g = ground(size=500, crack_glow=2.0)
        g.location = (0, 0, -3)
        shard()
        rf = C.OS.rift()
        rf.location = (60, 260, 230)
        rf.scale = (120, 120, 120)
        rf.rotation_mode = 'QUATERNION'
        rf.rotation_quaternion = (Vector((-70, -75, 8)) - Vector(rf.location)).to_track_quat('Z', 'Y')
        _light('Sun', (75, 0, 40), 1.0, (1.0, 0.75, 0.6))
        lancer = C.OS.load_glb(os.path.join(C.MODELS, 'human/lancer.glb'), 3.6)
        for i, (x, y) in enumerate([(-44, -36), (-39, -40), (-48, -31), (-43, -43)]):
            o = lancer.copy()
            o.hide_render = False
            bpy.context.scene.collection.objects.link(o)
            o.location = (x, y, 0.2)
            o.rotation_euler = (0, 0, math.radians(45))
        for v, p, t in [('hero', (-70, -75, 8), (0, 0, 20)), ('low', (-26, -30, 1.5), (0, 0, 30))]:
            _cam(p, t, lens=30 if v == 'hero' else 22)
            shots.append(os.path.join(tmp, f'shard_{v}.png'))
            _render(shots[-1], samples=48, glass=True)
        label = 'The Shard (Lancer tanks for scale)'
    return shots, label


if __name__ == '__main__':
    args = dict(a.lstrip('-').split('=', 1) for a in sys.argv[1:] if '=' in a)
    out = args.get('out', '/tmp/pieces')
    names = {'dropship': '01-drop-ship', 'dropship_hot': '01b-drop-ship-entry', 'seedpod': '02-seed-pod',
             'shield': '03-shield', 'crystalfield': '04-crystal-fields', 'shard': '05-shard'}
    todo = list(names) if args.get('piece', 'all') == 'all' else args['piece'].split(',')
    for pc in todo:
        shots, label = still(pc, out)
        bloom_sheet(shots, os.path.join(out, names[pc] + ".jpg"))
        print('DONE', pc, flush=True)
