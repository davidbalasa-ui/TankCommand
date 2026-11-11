"""End-game super weapon crystal, big-unit budget: <= 5,000 triangles, one 512px atlas.

Style target: David's reference (a tall floating faceted violet crystal, a swirling glowing
core, violet energy ribbons spiralling around it). Neutral: it attacks both factions.
Ribbons are a few cheap emissive strips; in game they spin and their texture scrolls.

Run with Blender's Python (pip bpy):
  python crystal.py <atlas_dir> <out.glb> [render_dir]
Nodes: Base (ruined plinth with claws), Crystal (spins slowly), Core, Ribbons (spin faster), Shards (orbit).
"""
import math
import random
import sys

import bpy
import bmesh

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
atlas_dir, out_glb = args[0], args[1]
render_dir = args[2] if len(args) > 2 else None
anim_dir = args[3] if len(args) > 3 else None  # optional: render a looping preview animation here

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
TILES = {
    'facet': (0.0, 0.5, 0.5, 1.0),
    'core': (0.5, 0.5, 1.0, 1.0),
    'ribbon': (0.0, 0.0, 0.5, 0.5),
    'stone': (0.5, 0.0, 1.0, 0.5),
}


def make_mat(name, glass=False, emit_strength=1.0, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    b = t.nodes['Principled BSDF']
    base = t.nodes.new('ShaderNodeTexImage')
    base.image = bpy.data.images.load(f'{atlas_dir}/crystal_atlas.png')
    emi = t.nodes.new('ShaderNodeTexImage')
    emi.image = bpy.data.images.load(f'{atlas_dir}/crystal_emissive.png')
    t.links.new(base.outputs['Color'], b.inputs['Base Color'])
    t.links.new(emi.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = emit_strength
    b.inputs['Roughness'].default_value = 0.0 if glass else 0.8
    if glass:
        # Strong refraction: nearly clear gem glass with a high index and colour fringing.
        # In game this is faked cheaply (environment reflection, fresnel rim, inner facet texture).
        b.inputs['Transmission Weight'].default_value = 0.92
        b.inputs['IOR'].default_value = 2.1
        if 'Dispersion' in b.inputs:
            b.inputs['Dispersion'].default_value = 0.6
        b.inputs['Coat Weight'].default_value = 0.6
    if alpha is not None:
        # Pure glow: dark base, emission does the work, brightness drives the alpha.
        b.inputs['Base Color'].default_value = (0, 0, 0, 1)
        t.links.remove(b.inputs['Base Color'].links[0])
        bw = t.nodes.new('ShaderNodeRGBToBW')
        t.links.new(emi.outputs['Color'], bw.inputs['Color'])
        t.links.new(bw.outputs['Val'], b.inputs['Alpha'])
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'BLENDED'
    return m


glass = make_mat('CrystalGlass', glass=True, emit_strength=0.12)
glow = make_mat('CrystalGlow', emit_strength=10.0, alpha=True)
core_mat = make_mat('CrystalCore', emit_strength=30.0)
stone = make_mat('CrystalStone', emit_strength=2.0)


def fit_uv(obj, tile, margin=0.01, project=True):
    if project:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(False)
    u0, v0, u1, v1 = TILES[tile]
    u0 += margin; v0 += margin; u1 -= margin; v1 -= margin
    for loop in obj.data.uv_layers.active.data:
        u, v = loop.uv
        loop.uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def mesh_from(name, verts, faces, tile, material, smooth=False, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if uvs is not None:
        layer = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                layer.data[li].uv = uvs[vi]
        fit_uv(obj, tile, project=False)
    else:
        fit_uv(obj, tile)
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    return obj


rng = random.Random(3)
FLOAT = 3.0   # gap between plinth and crystal tip
H = 14.0      # crystal height
R = 1.9       # widest radius
SIDES = 10

# --- Crystal: stacked rings, every other ring turned half a step, so the facets are triangles.
rings = [0.0, 0.1, 0.24, 0.4, 0.55, 0.7, 0.84, 1.0]
verts, faces = [], []
verts.append((0, 0, FLOAT))  # bottom tip
ring_idx = []
for k, t in enumerate(rings[1:-1]):
    r = R * math.sin(math.pi * t ** 0.85) ** 0.9 * rng.uniform(0.85, 1.1)
    off = (k % 2) * math.pi / SIDES
    row = []
    for i in range(SIDES):
        a = off + 2 * math.pi * i / SIDES
        rr = r * rng.uniform(0.8, 1.15)
        row.append(len(verts))
        verts.append((rr * math.cos(a), rr * math.sin(a), FLOAT + H * t + rng.uniform(-0.15, 0.15)))
    ring_idx.append(row)
top = len(verts)
verts.append((0, 0, FLOAT + H))
for i in range(SIDES):
    j = (i + 1) % SIDES
    faces.append([0, ring_idx[0][j], ring_idx[0][i]])
    faces.append([top, ring_idx[-1][i], ring_idx[-1][j]])
for a, b in zip(ring_idx, ring_idx[1:]):
    for i in range(SIDES):
        j = (i + 1) % SIDES
        faces.append([a[i], a[j], b[i]])
        faces.append([a[j], b[j], b[i]])
crystal = mesh_from('Crystal', verts, faces, 'facet', glass)


def spike(name, base_c, tip, w, sides, material, tile):
    """A jagged spike from a small base ring (around base_c) to a tip point."""
    import mathutils
    b, t = mathutils.Vector(base_c), mathutils.Vector(tip)
    axis = (t - b).normalized()
    side = axis.cross(mathutils.Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = mathutils.Vector((1, 0, 0))
    side.normalize()
    up = axis.cross(side)
    vs = [tuple(t)]
    for k in range(sides):
        a = 2 * math.pi * k / sides
        vs.append(tuple(b + (side * math.cos(a) + up * math.sin(a)) * w * rng.uniform(0.8, 1.2)))
    vs.append(tuple(b - axis * w * 0.6))
    fs = []
    for k in range(sides):
        j = (k + 1) % sides
        fs.append([0, 1 + k, 1 + j])
        fs.append([sides + 1, 1 + j, 1 + k])
    return mesh_from(name, vs, fs, tile, material)


# Orbiting shards: broken-off splinters that circle the crystal, points turned outward like blades.
shard_objs = []
for k in range(7):
    a = 2 * math.pi * k / 7 + rng.uniform(-0.2, 0.2)
    z = FLOAT + H * rng.uniform(0.25, 0.75)
    r0 = R + 1.6
    c = (r0 * math.cos(a), r0 * math.sin(a), z)
    tip = (c[0] + 1.6 * math.cos(a + 0.5), c[1] + 1.6 * math.sin(a + 0.5), z + rng.uniform(0.6, 1.4))
    shard_objs.append(spike(f'Shard{k}', c, tip, rng.uniform(0.22, 0.32), 4, glass, 'facet'))

# --- Core: a glowing orb at the crystal's heart (an icosphere, low).
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, FLOAT + H * 0.48))
me = bpy.data.meshes.new('Core'); bm.to_mesh(me); bm.free()
core = bpy.data.objects.new('Core', me); scene.collection.objects.link(core)
core.data.materials.append(core_mat); fit_uv(core, 'core')
for p in core.data.polygons:
    p.use_smooth = True

# --- Ribbons: three spiral strips around the crystal. U across the strip, V along it.
rverts, rfaces, ruvs = [], [], []
for s in range(3):
    seg = 48
    a0 = s * 2 * math.pi / 3
    tilt = rng.uniform(-0.35, 0.35)
    base_i = len(rverts)
    for i in range(seg + 1):
        t = i / seg
        a = a0 + t * 1.7 * math.pi
        z = FLOAT + H * (0.12 + 0.76 * t) + math.sin(a) * tilt * 2
        r = R * 1.25 + 0.9 * math.sin(math.pi * t)
        w = 0.5 * math.sin(math.pi * t) + 0.05
        cx, cy = r * math.cos(a), r * math.sin(a)
        rverts.append((cx, cy, z - w))
        rverts.append((cx, cy, z + w))
        ruvs += [(0.0, t), (1.0, t)]
    for i in range(seg):
        p = base_i + 2 * i
        rfaces.append([p, p + 2, p + 3, p + 1])
ribbons = mesh_from('Ribbons', rverts, rfaces, 'ribbon', glow, smooth=True, uvs=ruvs)

# --- Plinth: a cracked octagonal stone slab with broken pillar stumps.
pverts, pfaces = [], []
for z, r in ((0.0, 4.6), (0.6, 4.3), (0.6, 3.2), (1.0, 2.8)):
    for i in range(SIDES):
        a = 2 * math.pi * (i + 0.5) / SIDES
        pverts.append((r * math.cos(a), r * math.sin(a), z))
for ring in range(3):
    for i in range(SIDES):
        j = (i + 1) % SIDES
        a, b = ring * SIDES, (ring + 1) * SIDES
        pfaces.append([a + i, a + j, b + j, b + i])
pfaces.append(list(range(3 * SIDES, 4 * SIDES)))
plinth = [mesh_from('Slab', pverts, pfaces, 'stone', stone)]
# Claws: tall curved stone fangs rising from the plinth and leaning in toward the crystal.
for i in range(6):
    a = 2 * math.pi * (i + 0.25) / 6
    base_c = (3.9 * math.cos(a), 3.9 * math.sin(a), 0.6)
    tip = (2.6 * math.cos(a + 0.25), 2.6 * math.sin(a + 0.25), rng.uniform(4.0, 6.0))
    plinth.append(spike(f'Claw{i}', base_c, tip, 0.5, 5, stone, 'stone'))
for i in range(0, SIDES, 4):
    a = 2 * math.pi * (i + 0.5) / SIDES
    hgt = rng.uniform(0.8, 1.6)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=bm.verts, vec=(0.7, 0.7, hgt))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=__import__('mathutils').Matrix.Rotation(a + rng.uniform(-0.2, 0.2), 3, 'Z'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(3.9 * math.cos(a), 3.9 * math.sin(a), 0.6 + hgt / 2))
    me = bpy.data.meshes.new(f'Pillar{i}'); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(f'Pillar{i}', me); scene.collection.objects.link(o)
    o.data.materials.append(stone); fit_uv(o, 'stone')
    plinth.append(o)


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    return obj


base = join(plinth, 'Base')
shards = join(shard_objs, 'Shards')
root = bpy.data.objects.new('SuperCrystal', None)
scene.collection.objects.link(root)
for o in (base, crystal, core, ribbons, shards):
    o.parent = root

tris = 0
for o in (base, crystal, core, ribbons, shards):
    o.data.calc_loop_triangles()
    tris += len(o.data.loop_triangles)
print('TRIANGLES', tris)
assert tris <= 5000, tris

bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=True, export_yup=True)

if render_dir:
    world = bpy.data.worlds.new('W'); scene.world = world
    world.use_nodes = True
    # A gradient night sky so the refraction has something to bend.
    wn = world.node_tree
    bgn = wn.nodes['Background']
    grad = wn.nodes.new('ShaderNodeTexGradient')
    geo = wn.nodes.new('ShaderNodeTexCoord')
    sep = wn.nodes.new('ShaderNodeSeparateXYZ')
    ramp = wn.nodes.new('ShaderNodeValToRGB')
    wn.links.new(geo.outputs['Generated'], sep.inputs['Vector'])
    wn.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    ramp.color_ramp.elements[0].color = (0.02, 0.01, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.25, 0.08, 0.35, 1)
    wn.links.new(ramp.outputs['Color'], bgn.inputs['Color'])
    bgn.inputs['Strength'].default_value = 1.0
    for k, (col, loc) in enumerate((((1.0, 0.3, 0.6), (-8, 6, 10)), ((0.3, 0.6, 1.0), (8, 8, 14)),
                                    ((0.9, 0.5, 1.0), (-6, -8, 16)))):
        al = bpy.data.objects.new(f'Rim{k}', bpy.data.lights.new(f'Rim{k}', 'AREA'))
        al.data.energy = 1500; al.data.size = 3; al.data.color = col; al.location = loc
        d = [-c for c in loc]
        al.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        scene.collection.objects.link(al)
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 2.5
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(35))
    scene.collection.objects.link(sun)
    inner = bpy.data.objects.new('CoreLight', bpy.data.lights.new('CoreLight', 'POINT'))
    inner.data.energy = 6000; inner.data.color = (0.7, 0.4, 1.0)
    inner.location = (0, 0, FLOAT + H * 0.48)
    scene.collection.objects.link(inner)
    bpy.ops.mesh.primitive_plane_add(size=80)
    ground = bpy.context.object
    gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.045, 0.04, 0.05, 1)
    ground.data.materials.append(gm)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 96
    scene.cycles.transmission_bounces = 16
    scene.cycles.max_bounces = 16
    scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1200, 750
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def look(name, loc, target=(0, 0, 8.0), lens_mm=40):
        cam.location = loc
        d = [t - l for t, l in zip(target, loc)]
        cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
        cam.data.lens = lens_mm
        scene.render.filepath = f'{render_dir}/{name}.png'
        bpy.ops.render.render(write_still=True)

    import os
    if not os.environ.get('FRAMES'):
        look('crystal_front', (15, -15, 2.5), target=(0, 0, 8.0), lens_mm=26)
        look('crystal_rts', (16, -16, 30), target=(0, 0, 4), lens_mm=35)

    if anim_dir:
        # Looping preview: crystal turns once, ribbons the other way twice, shards orbit twice,
        # the core pulses, the crystal bobs, and it fires one beam at the ground mid-loop.
        # In game the same motion is plain rigid rotation plus a material pulse: no extra geometry.
        N = 96
        scene.frame_start, scene.frame_end = 1, N
        scene.render.fps = 24
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
        spin = [(crystal, 1), (core, 1), (ribbons, -2), (shards, 2)]
        for f in (1, N + 1):
            t = (f - 1) / N
            for o, turns in spin:
                o.rotation_euler = (0, 0, 2 * math.pi * turns * t)
                o.keyframe_insert('rotation_euler', frame=f)
        cb = core_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
        for f in range(1, N + 2, 4):
            t = (f - 1) / N
            cb.default_value = 30 + 25 * math.sin(4 * math.pi * t) ** 2
            cb.keyframe_insert('default_value', frame=f)
            for o in (crystal, core, ribbons, shards):
                o.location = (0, 0, 0.35 * math.sin(2 * math.pi * t))
                o.keyframe_insert('location', frame=f)
        # The attack, built from pieces that are all cheap on a phone (in game: billboard quads, ground
        # decals and a few particles): a lock-on ring tightens on the target, the core charges, a
        # flickering beam (white-hot core plus a soft violet glow) fires, the impact flashes, a
        # shockwave ring rolls out, sparks fly, and a scorch mark is left glowing and cooling.
        import mathutils
        import random as _r
        rr = _r.Random(7)
        V = mathutils.Vector
        tgt = V((7.5, -1.5, 0.0))
        cz = FLOAT + H * 0.48
        src = V((0, 0, cz))
        F_LOCK, F_FIRE, F_END = 28, 52, 63

        def glow_mat(name, col, soft=True):
            m = bpy.data.materials.new(name); m.use_nodes = True
            t = m.node_tree
            t.nodes.remove(t.nodes['Principled BSDF'])
            em = t.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*col, 1)
            tr = t.nodes.new('ShaderNodeBsdfTransparent')
            mx = t.nodes.new('ShaderNodeMixShader')
            if soft:  # bright through the middle, fading to nothing at the silhouette
                lw = t.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
                pw = t.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 0.5
                t.links.new(lw.outputs['Facing'], pw.inputs[0]); t.links.new(pw.outputs['Value'], mx.inputs['Fac'])
            else:
                mx.inputs['Fac'].default_value = 0.0
            t.links.new(em.outputs['Emission'], mx.inputs[1]); t.links.new(tr.outputs['BSDF'], mx.inputs[2])
            t.links.new(mx.outputs['Shader'], t.nodes['Material Output'].inputs['Surface'])
            m.surface_render_method = 'BLENDED'
            return m, em.inputs['Strength']

        def key_strength(sock, pts):
            for f, v in pts:
                sock.default_value = v
                sock.keyframe_insert('default_value', frame=f)

        def key_vis(o, on_from, off_from):
            for f, on in ((1, False), (on_from, True), (off_from, False)):
                o.hide_render = not on
                o.keyframe_insert('hide_render', frame=f)

        def aim_obj(o, a, b):
            o.location = (a + b) / 2
            o.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()

        # 1. Lock-on ring: shrinks onto the target and blinks faster as the charge builds.
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.035, major_segments=48, minor_segments=6,
                                         location=(tgt.x, tgt.y, 0.06))
        lock = bpy.context.object
        lm, ls = glow_mat('Lock', (0.7, 0.25, 1.0), soft=False)
        lock.data.materials.append(lm)
        key_vis(lock, F_LOCK, F_FIRE + 1)
        for f in range(F_LOCK, F_FIRE + 1):
            t = (f - F_LOCK) / (F_FIRE - F_LOCK)
            s_ = 4.0 - 2.6 * t
            lock.scale = (s_, s_, 1); lock.keyframe_insert('scale', frame=f)
            blink = 0.5 + 0.5 * math.cos(f * (0.6 + 1.6 * t))
            ls.default_value = 2 + 5 * blink; ls.keyframe_insert('default_value', frame=f)
        # 2. Core charge: a glow ball swelling inside the crystal, then spent while firing.
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0, location=src)
        charge = bpy.context.object
        cm, cs = glow_mat('Charge', (0.9, 0.6, 1.0))
        charge.data.materials.append(cm)
        key_vis(charge, 36, F_END + 2)
        for f, s_, e in ((36, 0.1, 2), (50, 1.0, 6), (F_FIRE, 1.2, 7), (F_END, 0.6, 3), (F_END + 2, 0.2, 0)):
            charge.scale = (s_, s_, s_); charge.keyframe_insert('scale', frame=f)
            cs.default_value = e; cs.keyframe_insert('default_value', frame=f)
        # 3+4. Beam: thin white-hot core and a wider soft glow cone that flares at the ground.
        L = (tgt - src).length
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.08, depth=L)
        bcore = bpy.context.object; aim_obj(bcore, src, tgt)
        bcm, bcs = glow_mat('BeamCore', (1.0, 0.8, 1.0), soft=False)
        bcore.data.materials.append(bcm)
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.4, radius2=0.95, depth=L, end_fill_type='NOTHING')
        bshell = bpy.context.object; aim_obj(bshell, src, tgt)
        bsm, bss = glow_mat('BeamGlow', (0.42, 0.04, 1.0))
        bshell.data.materials.append(bsm)
        for o in (bcore, bshell):
            key_vis(o, F_FIRE, F_END + 1)
        for f in range(F_FIRE, F_END + 1):
            k = 1.0 if f < F_END - 2 else (F_END + 1 - f) / 3
            w = rr.uniform(0.7, 1.3) * k
            bcore.scale = (w, w, 1); bcore.keyframe_insert('scale', frame=f)
            w2 = rr.uniform(0.8, 1.25) * (1.4 if f == F_FIRE else 1.0) * max(k, 0.3)
            bshell.scale = (w2, w2, 1); bshell.keyframe_insert('scale', frame=f)
            bcs.default_value = rr.uniform(6, 9) * k; bcs.keyframe_insert('default_value', frame=f)
            bss.default_value = rr.uniform(3, 5) * k; bss.keyframe_insert('default_value', frame=f)
        # 5. Impact flash: a soft glow pooled on the ground plus a short bright splash at the hit point.
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=1.0, fill_type='TRIFAN', location=(tgt.x, tgt.y, 0.05))
        flash = bpy.context.object
        fl = bpy.data.materials.new('Flash'); fl.use_nodes = True
        ft = fl.node_tree
        ft.nodes.remove(ft.nodes['Principled BSDF'])
        fe = ft.nodes.new('ShaderNodeEmission'); fe.inputs['Color'].default_value = (0.5, 0.1, 1.0, 1)
        ftr = ft.nodes.new('ShaderNodeBsdfTransparent'); fmx = ft.nodes.new('ShaderNodeMixShader')
        fg = ft.nodes.new('ShaderNodeTexGradient'); fg.gradient_type = 'QUADRATIC_SPHERE'
        ftc = ft.nodes.new('ShaderNodeTexCoord')
        ft.links.new(ftc.outputs['Object'], fg.inputs['Vector'])
        finv = ft.nodes.new('ShaderNodeMath'); finv.operation = 'SUBTRACT'; finv.inputs[0].default_value = 1.0
        ft.links.new(fg.outputs['Fac'], finv.inputs[1])
        ft.links.new(finv.outputs['Value'], fmx.inputs['Fac'])
        ft.links.new(fe.outputs['Emission'], fmx.inputs[1]); ft.links.new(ftr.outputs['BSDF'], fmx.inputs[2])
        ft.links.new(fmx.outputs['Shader'], ft.nodes['Material Output'].inputs['Surface'])
        fl.surface_render_method = 'BLENDED'
        flash.data.materials.append(fl)
        fs = fe.inputs['Strength']
        key_vis(flash, F_FIRE, F_END + 8)
        for f, s_, e in ((F_FIRE, 1.5, 8), (F_FIRE + 2, 3.2, 7), (F_END, 3.0, 5), (F_END + 8, 3.8, 0)):
            flash.scale = (s_, s_, 1); flash.keyframe_insert('scale', frame=f)
            fs.default_value = e; fs.keyframe_insert('default_value', frame=f)
        # 6. Shockwave: a ring that rolls out across the ground and fades.
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.09, major_segments=48, minor_segments=8,
                                         location=(tgt.x, tgt.y, 0.1))
        shock = bpy.context.object
        sm, ss = glow_mat('Shock', (0.5, 0.1, 1.0))
        shock.data.materials.append(sm)
        key_vis(shock, F_FIRE + 1, F_FIRE + 20)
        for f in range(F_FIRE + 1, F_FIRE + 20):
            t = (f - F_FIRE - 1) / 18
            s_ = 0.8 + 8.0 * (1 - (1 - t) ** 2)
            shock.scale = (s_, s_, 1 + 2 * (1 - t)); shock.keyframe_insert('scale', frame=f)
            ss.default_value = 5 * (1 - t) ** 1.5; ss.keyframe_insert('default_value', frame=f)
        # 7. Scorch: a ragged burnt patch with ember specks that cool down after the hit.
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=3.0, fill_type='TRIFAN', location=(tgt.x, tgt.y, 0.03))
        scorch = bpy.context.object
        sc = bpy.data.materials.new('Scorch'); sc.use_nodes = True
        st = sc.node_tree; sb = st.nodes['Principled BSDF']
        tc = st.nodes.new('ShaderNodeTexCoord')
        nz = st.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.2; nz.inputs['Detail'].default_value = 6
        st.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        dist = st.nodes.new('ShaderNodeVectorMath'); dist.operation = 'LENGTH'
        st.links.new(tc.outputs['Object'], dist.inputs[0])
        rag = st.nodes.new('ShaderNodeMath'); rag.operation = 'MULTIPLY_ADD'
        rag.inputs[1].default_value = 1.6; rag.inputs[2].default_value = -0.8
        st.links.new(nz.outputs['Fac'], rag.inputs[0])
        edge = st.nodes.new('ShaderNodeMath'); edge.operation = 'ADD'
        st.links.new(dist.outputs['Value'], edge.inputs[0]); st.links.new(rag.outputs['Value'], edge.inputs[1])
        mask = st.nodes.new('ShaderNodeMapRange')
        mask.inputs['From Min'].default_value = 1.4; mask.inputs['From Max'].default_value = 2.6
        mask.inputs['To Min'].default_value = 1.0; mask.inputs['To Max'].default_value = 0.0
        st.links.new(edge.outputs['Value'], mask.inputs['Value'])
        st.links.new(mask.outputs['Result'], sb.inputs['Alpha'])
        nz2 = st.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 3.5; nz2.inputs['Detail'].default_value = 2
        st.links.new(tc.outputs['Object'], nz2.inputs['Vector'])
        emb = st.nodes.new('ShaderNodeMapRange')
        emb.inputs['From Min'].default_value = 0.66; emb.inputs['From Max'].default_value = 0.72
        st.links.new(nz2.outputs['Fac'], emb.inputs['Value'])
        core_m = st.nodes.new('ShaderNodeMath'); core_m.operation = 'MULTIPLY'
        st.links.new(emb.outputs['Result'], core_m.inputs[0]); st.links.new(mask.outputs['Result'], core_m.inputs[1])
        heat = st.nodes.new('ShaderNodeMath'); heat.operation = 'MULTIPLY'
        st.links.new(core_m.outputs['Value'], heat.inputs[0])
        st.links.new(heat.outputs['Value'], sb.inputs['Emission Strength'])
        sb.inputs['Base Color'].default_value = (0.012, 0.009, 0.012, 1); sb.inputs['Roughness'].default_value = 1
        sb.inputs['Emission Color'].default_value = (1.0, 0.4, 0.8, 1)
        sc.surface_render_method = 'BLENDED'
        scorch.data.materials.append(sc)
        key_vis(scorch, F_FIRE + 1, N + 2)
        key_strength(heat.inputs[1], ((F_FIRE + 1, 9), (F_END, 7), (F_END + 12, 2.5), (N, 0.3)))
        # 8. Sparks: short glowing streaks thrown out of the hit, falling under gravity.
        spm, sps = glow_mat('Spark', (1.0, 0.45, 0.95), soft=False)
        sps.default_value = 9
        for k in range(14):
            bpy.ops.mesh.primitive_cylinder_add(vertices=4, radius=0.04, depth=0.45)
            sp = bpy.context.object
            sp.data.materials.append(spm)
            a = rr.uniform(0, 2 * math.pi)
            a = rr.uniform(-0.6, 2.4)  # throw away from the camera side
            vh, vz = rr.uniform(4, 8), rr.uniform(5, 9)
            f0 = F_FIRE + rr.randint(0, 6)
            last = f0
            for f in range(f0, f0 + 14):
                t = (f - f0) / 24
                p = tgt + V((vh * t * math.cos(a), vh * t * math.sin(a), 0.3 + vz * t - 9.8 * t * t))
                if p.z < 0:
                    break
                vel = V((vh * math.cos(a), vh * math.sin(a), vz - 19.6 * t))
                sp.location = p; sp.rotation_euler = vel.to_track_quat('Z', 'Y').to_euler()
                sp.keyframe_insert('location', frame=f); sp.keyframe_insert('rotation_euler', frame=f)
                last = f
            key_vis(sp, f0, last + 1)
        # 9. Light: the hit lights the ground; the core light swells with the charge.
        hit = bpy.data.objects.new('HitLight', bpy.data.lights.new('HitLight', 'POINT'))
        hit.data.color = (0.85, 0.5, 1.0); hit.location = (tgt.x, tgt.y, 1.2)
        scene.collection.objects.link(hit)
        for f, e in ((1, 0), (F_FIRE - 1, 0), (F_FIRE, 9000), (F_END, 6000), (F_END + 8, 800), (N, 100)):
            hit.data.energy = e; hit.data.keyframe_insert('energy', frame=f)
        for f, e in ((1, 6000), (36, 6000), (F_FIRE, 11000), (F_END + 2, 6000)):
            inner.data.energy = e; inner.data.keyframe_insert('energy', frame=f)
        scene.render.resolution_x, scene.render.resolution_y = 800, 500
        scene.cycles.samples = 24
        scene.cycles.use_denoising = True
        look_at = (0, 0, 7.0)
        cam.location = (15, -18, 4.0)
        dd = [t_ - l for t_, l in zip(look_at, cam.location)]
        cam.rotation_euler = (math.atan2(math.hypot(dd[0], dd[1]), -dd[2]), 0, math.atan2(dd[1], dd[0]) - math.pi / 2)
        cam.data.lens = 24
        scene.render.image_settings.file_format = 'PNG'
        import os
        if os.environ.get('FRAMES'):
            for f in [int(x) for x in os.environ['FRAMES'].split(',')]:
                scene.frame_set(f)
                scene.render.filepath = f'{anim_dir}/f_{f:04d}.png'
                bpy.ops.render.render(write_still=True)
        else:
            scene.render.filepath = f'{anim_dir}/f_'
            bpy.ops.render.render(animation=True)
